"""Run one bounded pair through the released launcher with isolated fixture providers."""

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from unittest.mock import patch

from skillevaluator.evaluation import EvaluationService
from skillevaluator.tier3.harbor import runner, runtime_preflight
from skillevaluator.tier3.harbor.progress import PlainProgressReporter

import benchmark_native as native
from benchmark_podman import compose_teardown_complete
from benchmark_smoke import PROVIDER_CREDENTIALS
import gh_evaluations as gh
from qualify_benchmark_101 import restrict_network
from qualify_benchmark_codex import OfflineCodex, OfflinePodmanCodex
from skill_reports import POLICY, read_json, require, write_json


CASES = {"podman": "1", "gh": "gh-001"}
SENTINEL = "native-launcher-test-not-a-provider-credential"


class FixtureInput:
    async def install(self, environment):
        fixture_home = Path(os.environ["NATIVE_LAUNCHER_FIXTURE_HOME"])
        job = self.logs_dir.parent.parent.name
        fixture = fixture_home / (job + ".json")
        require(job in {"runtime-preflight-codex", "gh-codex-with", "gh-codex-without",
                        "podman-codex-with", "podman-codex-without"} and fixture.is_file(),
                "Unexpected released launcher fixture job")
        os.environ["BENCHMARK_CODEX_FIXTURE"] = str(fixture)
        await super().install(environment)
        trial = self.logs_dir.parent
        resource = read_json(trial / "fixture-container.json")
        project = subprocess.check_output(
            ["docker", "inspect", "--format", '{{ index .Config.Labels "com.docker.compose.project" }}', resource["id"]],
            text=True, timeout=20,
        ).strip()
        write_json(trial / "fixture-container.json", {**resource, "project": project})
        if job == "runtime-preflight-codex":
            return
        suite, _, arm = job.split("-")
        skill = f"/workspace/skills/{suite}/SKILL.md"
        condition = f"test -r {skill} && test ! -w {skill}" if arm == "with" else f"test ! -e {skill}"
        if suite == "gh":
            other = "/workspace/skills/github-actions-hardening/SKILL.md"
            condition += f" && test -r {other} && test ! -w {other}"
        result = await self.exec_as_agent(environment, "test -x /workspace/skills && " + condition)
        require(result.return_code == 0, "Native fixture skill visibility or permissions changed")

    def record_startup(self, stage):
        write_json(self.logs_dir.parent / "fixture-startup.json", {"stage": stage})


class GhFixture(FixtureInput, OfflineCodex):
    pass


class PodmanFixture(FixtureInput, OfflinePodmanCodex):
    pass


def isolate_task(task):
    """Replace the provider route and preserve the released grader sequence."""
    descriptor = task / "task.toml"
    source = descriptor.read_text()
    marker = 'network_mode = "allowlist"\nallowed_hosts = ["api.openai.com"]'
    require(source.count(marker) == 1, "Released task does not use its declared provider boundary")
    descriptor.write_text(source.replace(marker, 'network_mode = "no-network"'))
    image = task / "environment"
    reviewed = image / "reviewed"
    reviewed.mkdir(exist_ok=True)
    shutil.copyfile(native.ROOT / ".github/scripts/codex_pilot_stub.py", reviewed / "stub.py")
    shutil.copyfile(native.ROOT / ".github/scripts/qualify_benchmark_podman.py", reviewed / "podman_fixture.py")
    with (image / "Dockerfile").open("a") as build:
        build.write("\nCOPY --chown=0:0 reviewed/stub.py reviewed/podman_fixture.py /opt/reviewed/\n"
                    "RUN chmod a+r /opt/reviewed/stub.py /opt/reviewed/podman_fixture.py\n")
    verifier = task / "tests/test.sh"
    source = verifier.read_text()
    stage = 'python3 -I "${evaluator_dir}/eval.py"'
    require(source.count(stage) == 1, "Unexpected released verifier entry point")
    verifier.write_text(source.replace(stage, "python3 -I /opt/reviewed/podman_fixture.py --verify"))


def commands(name, present):
    if name == "podman":
        return ["head -n 8 /workspace/skills/podman/SKILL.md" if present else
                "test ! -e /workspace/skills/podman/SKILL.md && printf baseline"]
    contract = gh.dataset(selected=[CASES[name]])[0]["contract"]
    expected = json.dumps(contract["expected"])
    if present:
        return ["cat /workspace/skills/gh/SKILL.md",
                *(shlex.join(["gh", *cmd]) for cmd in contract["good_commands"]),
                "printf '%s\\n' " + shlex.quote(expected) + " > output/result.json"]
    return [{"tool": "apply_patch", "expect_failure": False, "input":
             "*** Begin Patch\n*** Add File: output/result.json\n+" + expected + "\n*** End Patch"}]


def controls(root, name):
    root.mkdir(mode=0o700)
    fixtures = {}
    for job, present in (("runtime-preflight-codex", True), (f"{name}-codex-with", True),
                         (f"{name}-codex-without", False)):
        path = root / (job + ".json")
        payload = ["printf runtime-ready"] if job == "runtime-preflight-codex" else commands(name, present)
        write_json(path, {"scenario": "benchmark-priced", "commands": payload})
        fixtures[job] = path
    return fixtures


def inspect_trial(job, *, preflight, suite):
    result_path, = job.glob("*/result.json")
    result = read_json(result_path)
    require(result["exception_info"] is None and result["agent_info"]["version"] == POLICY["codex"],
            "Fixture trial or installed Codex failed")
    trial = result_path.parent
    resource = read_json(trial / "fixture-container.json")
    removed = subprocess.run(["docker", "container", "inspect", resource["id"]], capture_output=True,
                             timeout=20).returncode != 0
    teardown = removed and compose_teardown_complete(resource["project"])
    usage = result["agent_result"]
    require([usage[key] for key in ("n_input_tokens", "n_output_tokens", "n_cache_tokens")] == [300, 30, 100],
            "Fixture token accounting changed")
    if suite == "gh":
        startup = trial / "gh-initialization.jsonl"
        started = [json.loads(line)["status"] for line in startup.read_text().splitlines()]
        require(started == ["ready"], "Trusted gh initialization did not finish before the fixture agent")
    if preflight:
        require(result["verifier_result"] is None, "Runtime preflight performed verification")
        return {"codex": result["agent_info"]["version"], "teardown_complete": teardown, "verification_disabled": True}
    verifier = trial / "verifier"
    judge = read_json(verifier / "judge-requests.json")
    requests = read_json(verifier / "codex-requests.json")["request_observations"]
    require(len(requests) == 2 and all(item["model"] == POLICY["model"] and item["path"] == "/v1/responses"
            and item["reasoning"]["effort"] == "high" and item["authorization_matches_sentinel"] for item in requests),
            "Codex fixture request contract differs")
    require(len(judge) == 3 and {item["metric"] for item in judge} == {"accuracy", "behavior_check", "goal_accuracy"}
            and all(item["request_policy_matches"] for item in judge), "Verifier fixture request contract differs")
    reward = read_json(verifier / "skill_evaluator_reward.json")
    require(reward["judge_contract"] == "skill-evaluator-judges-v2" and reward["accuracy"] == 0.8,
            "Released judge score contract differs")
    custom = None
    if (verifier / "custom_reward.json").exists():
        metrics = read_json(verifier / "custom_reward.json")["custom_metrics"]
        custom = {key: metrics[key] for key in ("gh_evidence", "gh_activation", native.GH_ACCESS_METRIC, "gh_gate")}
    return {"codex_requests": len(requests), "judge_requests": len(judge), "accuracy": reward["accuracy"],
            "custom": custom, "teardown_complete": teardown}


def qualify(output, name, revision):
    require(not any(os.getenv(key) for key in PROVIDER_CREDENTIALS), "Docker fixture requires absent provider credentials")
    native.require_revision(native.ROOT, revision)
    output = output.absolute()
    require(output.resolve() == output and not output.is_relative_to(native.ROOT), "Unsafe Docker fixture output")
    output.mkdir(mode=0o700, exist_ok=False)
    require(subprocess.check_output(["docker", "compose", "version", "--short"], text=True, timeout=20).strip()
            == POLICY["docker_compose"], "Unexpected Docker Compose identity")
    fixtures = controls(output / "fixtures", name)
    disconnected = output / "fixtures/disconnected.yaml"
    disconnected.write_text("services:\n  main:\n    network_mode: none\n")
    stage_gh = native.stage_gh
    local_skill = native.local_skill
    gh_task = native.configure_gh_task
    podman_task = native.configure_openai_task
    build = runner.build_harbor_run_command
    launch_environment = runner._harbor_launch_environment
    workspace = native.ROOT
    subset = None
    if name == "podman":
        subset = output / "fixture-source/podman"
        shutil.copytree(local_skill(workspace, name, dataset=True), subset)
        subprocess.run(["git", "init", "--quiet", "--template=", str(subset)], check=True, timeout=20,
                       env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"})
        source = subset / "evals/evals.json"
        dataset = read_json(source)
        dataset["evals"] = [row for row in dataset["evals"] if str(row["id"]) == CASES[name]]
        require(len(dataset["evals"]) == 1, "Unexpected Podman fixture scope")
        write_json(source, dataset)

    fixture_agent = "qualify_native_execution:" + ("GhFixture" if name == "gh" else "PodmanFixture")

    def build_fixture(**kwargs):
        argv = build(**kwargs)
        index = argv.index("--agent") + 1
        require(argv[index] == native.CODEX_AGENT and kwargs["job_name"] in fixtures,
                "Released runner did not choose the reviewed agent or fixture job")
        argv[index] = fixture_agent
        return argv + ["--extra-docker-compose", str(disconnected)]

    def catalog(provider):
        require(provider.provider == "openai" and provider.model == POLICY["model"] and provider.api_key == SENTINEL,
                "Unexpected credential route in Docker fixture")
        return runtime_preflight.ModelProbeResult(True, provider.provider, provider.model, "Non-forwarding catalog fixture")

    def launch_env(values):
        return {**launch_environment(values), "PYTHONPATH": str(workspace / ".github/scripts"), "PYTHONDONTWRITEBYTECODE": "1",
                "NATIVE_LAUNCHER_FIXTURE_HOME": str(disconnected.parent)}

    def configure_gh(task, profile):
        gh_task(task, profile)
        isolate_task(task)

    def configure_podman(task, assets, profile):
        podman_task(task, assets, profile)
        isolate_task(task)

    root = output / "run"
    with (patch.object(native, "stage_gh", side_effect=lambda source, dest: stage_gh(source, dest, [CASES[name]])),
          patch.object(native, "local_skill", return_value=subset),
          patch.object(native, "configure_gh_task", side_effect=configure_gh),
          patch.object(native, "configure_openai_task", side_effect=configure_podman)):
        native.prepare(workspace, root, name, "standard", revision)
        sys.addaudithook(restrict_network)
        with (patch.object(runtime_preflight, "probe_model", side_effect=catalog),
              patch.object(runner, "build_harbor_run_command", side_effect=build_fixture),
              patch.object(runtime_preflight, "build_harbor_run_command", side_effect=build_fixture),
              patch.object(runner, "_harbor_launch_environment", side_effect=launch_env),
              patch.object(runtime_preflight, "_harbor_launch_environment", side_effect=launch_env)):
            result = native.execute(workspace, root, name, "standard", revision, SENTINEL,
                                    progress_reporter=PlainProgressReporter())
    failure = EvaluationService.failure_reason(result)
    if failure is not None or result.get("report_status") != "complete":
        write_json(output / "failure.json", {"schema_version": 1, "revision": revision, "suite": name,
            "case": CASES[name], "status": "incomplete", "history_eligible": False,
            "execution_status": result.get("execution_status"), "report_status": result.get("report_status")})
        raise ValueError("Released launcher fixture failed. Inspect the bounded native progress output.")
    jobs = Path(result["harbor_jobs_dir"])
    observed = {job: inspect_trial(jobs / job, preflight=job == "runtime-preflight-codex", suite=name)
                for job in fixtures}
    run = Path(result["run_dir"])
    native.validate_collected_pair(result, run, root, name, "standard", revision, [CASES[name]],
                                   agent_selector=fixture_agent)
    invalid = deepcopy(result)
    invalid["run_dir"] = str(run.with_name("unselected-report"))
    try:
        native.validate_collected_pair(invalid, run, root, name, "standard", revision, [CASES[name]],
                                       agent_selector=fixture_agent)
    except ValueError as error:
        require(str(error) == "Missing or unsafe released benchmark report", "Wrong report selection rejection")
    else:
        raise ValueError("Released score projection accepted a substituted report path")
    invalid = deepcopy(result)
    invalid["agents"]["codex"]["pass_at_k"]["with_skill"]["cases"][CASES[name]]["attempts"][0]["trial"] = "unmatched"
    try:
        native.validate_collected_pair(invalid, run, root, name, "standard", revision, [CASES[name]],
                                       agent_selector=fixture_agent)
    except ValueError as error:
        require(str(error) == "Released trial summary differs from the complete arm", "Wrong trial population rejection")
    else:
        raise ValueError("Released score projection accepted a substituted trial identity")
    rejection = {"podman": "Prepared benchmark scope differs",
                 "gh": "Released score report requires the full authored gh cohort"}[name]
    try:
        native.score_record(workspace, root, name, "standard", revision)
    except ValueError as error:
        require(str(error) == rejection, "Native fixture was rejected at the wrong report boundary")
    else:
        raise ValueError("Partial native fixture entered the full-cohort score report")
    if name == "gh":
        require(observed["gh-codex-with"]["custom"] == {"gh_evidence": 1, "gh_activation": 1, native.GH_ACCESS_METRIC: 1, "gh_gate": 1}
                and observed["gh-codex-without"]["custom"] == {
                    "gh_evidence": 1, "gh_activation": 0, native.GH_ACCESS_METRIC: 0, "gh_gate": 0},
                "Released grouped custom grader changed its expected authorization outcomes")
    receipt = {"schema_version": 1, "revision": revision, "producer": native.NATIVE_PRODUCER,
               "patch_sha256": native.NATIVE_PATCH_DIGEST, "suite": name, "case": CASES[name], "observed": observed,
               "scored_attempts": 2, "provider_requests": 0, "history_eligible": False,
               "full_cohort_report_rejected": True, "origin": "non_forwarding_fixture"}
    if not all(trial["teardown_complete"] for trial in observed.values()):
        write_json(output / "failure.json", {**receipt, "status": "teardown_incomplete"})
        raise ValueError("Fixture left Compose resources")
    write_json(output / "qualification.json", receipt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("suite", choices=CASES)
    parser.add_argument("revision")
    args = parser.parse_args()
    qualify(args.output, args.suite, args.revision)


if __name__ == "__main__":
    main()
