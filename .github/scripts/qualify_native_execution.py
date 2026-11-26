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
import pester_evaluations as pester
from benchmark_codex_fixture import TOOL_ROUTE
from qualify_benchmark_101 import restrict_network
from qualify_benchmark_codex import OfflineCodex, OfflinePodmanCodex
from skill_reports import MODES, POLICY, benchmark_artifacts, read_json, require, write_json


CASES = {"podman": "1", "gh": "gh-001"}
PESTER_SOLUTIONS = {"pester-001": "classic.Tests.ps1", "pester-002": "classic.Tests.ps1",
                    "pester-003": "external.Tests.ps1", "pester-004": "discovery.Tests.ps1",
                    "pester-005": "good.json"}
SENTINEL = "native-launcher-test-not-a-provider-credential"


class FixtureInput:
    async def install(self, environment):
        fixture_home = Path(os.environ["NATIVE_LAUNCHER_FIXTURE_HOME"])
        job = self.logs_dir.parent.parent.name
        identity = job
        if job in {f"{pester.NAME}-codex-with", f"{pester.NAME}-codex-without"}:
            case = self.logs_dir.parent.name.split("__", 1)[0]
            require(case in PESTER_SOLUTIONS, "Unexpected Pester fixture case")
            identity += "-" + case
        fixture = fixture_home / (identity + ".json")
        require(fixture.is_file(),
                "Unexpected released launcher fixture job")
        self._fixture_path = fixture
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
        suite, arm = job.rsplit("-codex-", 1)
        skill = f"/workspace/skills/{suite}/SKILL.md"
        condition = f"test -r {skill} && test ! -w {skill}" if arm == "with" else f"test ! -e {skill}"
        if suite == "gh":
            other = "/workspace/skills/github-actions-hardening/SKILL.md"
            condition += f" && test -r {other} && test ! -w {other}"
        result = await self.exec_as_agent(environment, "test -x /workspace/skills && " + condition)
        require(result.return_code == 0, "Native fixture skill visibility or permissions changed")

    def fixture_path(self):
        return self._fixture_path

    def record_startup(self, stage):
        write_json(self.logs_dir.parent / "fixture-startup.json", {"stage": stage})


class GhFixture(FixtureInput, OfflineCodex):
    pass


class PodmanFixture(FixtureInput, OfflinePodmanCodex):
    pass


class PesterFixture(FixtureInput, OfflineCodex):
    async def verify_trial_user(self, environment):
        version = await self.exec_as_agent(environment, "codex --version")
        require(version.return_code == 0 and version.stdout.strip() == "codex-cli " + self._version,
                "Pester trial could not invoke the pinned Codex executable")
        user = await self.exec_as_agent(environment, "id -u")
        require(user.return_code == 0 and user.stdout.strip() == "1000", "Pester trial did not run as UID 1000")
        isolation = await self.exec_as_agent(environment, "test ! -e /tests/entry.json && test ! -e /opt/pester-runtime/Runner.ps1")
        require(isolation.return_code == 0, "Pester trial exposed a protected verifier input")

    async def run(self, instruction, environment, context):
        await super().run(instruction, environment, context)
        request = await self.exec_as_root(environment, "cat /opt/reviewed/request.json")
        require(request.return_code == 0, "Missing loopback request receipt")
        write_json(self.logs_dir / "pester-codex-requests.json", json.loads(request.stdout))


def isolate_task(task, *, standard_judges=True):
    """Replace the provider route and preserve the released grader sequence."""
    descriptor = task / "task.toml"
    source = descriptor.read_text()
    marker = 'network_mode = "allowlist"\nallowed_hosts = ["api.openai.com"]'
    require(source.count(marker) == 1, "Released task does not use its declared provider boundary")
    descriptor.write_text(source.replace(marker, 'network_mode = "no-network"'))
    image = task / "environment"
    reviewed = image / "reviewed"
    reviewed.mkdir(exist_ok=True)
    shutil.copyfile(native.ROOT / ".github/scripts/benchmark_codex_fixture.py", reviewed / "stub.py")
    with (image / "Dockerfile").open("a") as build:
        if not standard_judges:
            build.write("\nCOPY --chown=0:0 reviewed/stub.py /opt/reviewed/stub.py\n"
                        "RUN chmod a+r /opt/reviewed/stub.py\n")
            return
        shutil.copyfile(native.ROOT / ".github/scripts/qualify_benchmark_podman.py", reviewed / "podman_fixture.py")
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
    preflight = root / "runtime-preflight-codex.json"
    write_json(preflight, {"scenario": "benchmark-priced", "commands": ["printf runtime-ready"]})
    fixtures["runtime-preflight-codex"] = preflight
    for arm, present in (("with", True), ("without", False)):
        job = f"{name}-codex-{arm}"
        if name == pester.NAME:
            support = native.ROOT / pester.OVERLAY / "support"
            for case, filename in PESTER_SOLUTIONS.items():
                submitted = (support / "qualification" / case / filename).read_text()
                destination = ("summary.json" if filename.endswith(".json") else "Subject.Tests.ps1")
                payload = ["printf %s " + shlex.quote(submitted) + " > output/" + destination]
                write_json(root / (job + "-" + case + ".json"), {"scenario": "benchmark-priced", "commands": payload})
            fixtures[job] = root
        else:
            path = root / (job + ".json")
            write_json(path, {"scenario": "benchmark-priced", "commands": commands(name, present)})
            fixtures[job] = path
    return fixtures


def inspect_trial(result_path, *, preflight, suite):
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
    request_path = (trial / "agent/pester-codex-requests.json" if suite == pester.NAME
                    else verifier / "codex-requests.json")
    requests = read_json(request_path)["request_observations"]
    require(len(requests) == 2 and all(item["model"] == POLICY["model"] and item["path"] == "/v1/responses"
            and item["reasoning"]["effort"] == "high" and item["authorization_matches_sentinel"]
            and item["native_tool_route"] == TOOL_ROUTE for item in requests),
            "Codex fixture request contract differs")
    if suite == pester.NAME:
        raw = read_json(verifier / "custom_reward.json")
        sidecar = read_json(verifier / "skill_evaluator_reward.json")
        require(not (verifier / "judge-requests.json").exists() and sidecar["evaluation_status"] == "complete"
                and raw["entry_id"] == sidecar["entry_id"]
                and raw["details"]["outcome"]["classification"] == "passed", "Pester fixture grading differs")
        return {"codex_requests": len(requests), "judge_requests": 0,
                "custom": raw["custom_metrics"], "teardown_complete": teardown}
    judge = read_json(verifier / "judge-requests.json")
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


def qualify_publication(root, destination, name):
    """Check the artifact boundary without creating a candidate history record."""
    import skill_evidence as evidence

    benchmark_artifacts(native.ROOT, root, name, destination)
    original = evidence.project(evidence.normalize_behavioral(root, name, native_layout=True))
    retained = evidence.project(evidence.normalize_behavioral(destination, name))
    for key in ("dataset", "policy", "metrics", "availability"):
        require(retained[key] == original[key], "Redacted released report changed its measured claims")
    for observed, published in zip(original["observations"], retained["observations"], strict=True):
        keys = ("id", "score", "scores", "deterministic_gate", "deterministic_scores")
        require(all(observed[key] == published[key] for key in keys),
                "Redaction changed a released trial's measurements")
    require(retained["dataset"]["case_ids"] == [CASES[name]], "Unexpected released publication fixture scope")
    try:
        evidence.require_released_report_population(retained)
    except ValueError as error:
        require(str(error) == "Released benchmark requires an authenticated complete cohort",
                "Released fixture was rejected at the wrong publication boundary")
    else:
        raise ValueError("Scoped released fixture entered public history")


def qualify(output, name, revision, *, mode="standard"):
    require(not any(os.getenv(key) for key in PROVIDER_CREDENTIALS), "Docker fixture requires absent provider credentials")
    attempts = MODES[mode]
    native.require_revision(native.ROOT, revision)
    output = output.absolute()
    require(output.resolve() == output and not output.is_relative_to(native.ROOT), "Unsafe Docker fixture output")
    output.mkdir(mode=0o700, exist_ok=False)
    require(subprocess.check_output(["docker", "compose", "version", "--short"], text=True, timeout=20).strip()
            == POLICY["docker_compose"], "Unexpected Docker Compose identity")
    fixtures = controls(output / "fixtures", name)
    disconnected = output / "fixtures/disconnected.yaml"
    disconnected.write_text("services:\n  main:\n    network_mode: none\n")
    local_skill = native.local_skill
    gh_task = native.configure_gh_task
    podman_task = native.configure_openai_task
    pester_task = native.configure_pester_task
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

    fixture_agent = "qualify_native_execution:" + {
        "gh": "GhFixture", "podman": "PodmanFixture", pester.NAME: "PesterFixture",
    }[name]

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

    def configure_pester(task, profile):
        pester_task(task, profile)
        isolate_task(task, standard_judges=False)

    root = output / "run"
    with (patch.object(native, "local_skill", return_value=subset),
          patch.object(native, "configure_gh_task", side_effect=configure_gh),
          patch.object(native, "configure_openai_task", side_effect=configure_podman),
          patch.object(native, "configure_pester_task", side_effect=configure_pester)):
        native.prepare(workspace, root, name, mode, revision,
                       gh_cases=[CASES[name]] if name == "gh" else None)
        sys.addaudithook(restrict_network)
        with (patch.object(runtime_preflight, "probe_model", side_effect=catalog),
              patch.object(runner, "build_harbor_run_command", side_effect=build_fixture),
              patch.object(runtime_preflight, "build_harbor_run_command", side_effect=build_fixture),
              patch.object(runner, "_harbor_launch_environment", side_effect=launch_env),
              patch.object(runtime_preflight, "_harbor_launch_environment", side_effect=launch_env)):
            result = native.execute(workspace, root, name, mode, revision, SENTINEL,
                                    progress_reporter=PlainProgressReporter())
    failure = EvaluationService.failure_reason(result)
    if failure is not None or result.get("report_status") != "complete":
        write_json(output / "failure.json", {"schema_version": 1, "revision": revision, "suite": name,
            "cases": list(PESTER_SOLUTIONS) if name == pester.NAME else [CASES[name]],
            "status": "incomplete", "history_eligible": False,
            "execution_status": result.get("execution_status"), "report_status": result.get("report_status")})
        raise ValueError("Released launcher fixture failed. Inspect the bounded native progress output.")
    jobs = Path(result["harbor_jobs_dir"])
    observed = {}
    for job in fixtures:
        preflight = job == "runtime-preflight-codex"
        results = sorted((jobs / job).glob("*/result.json"))
        cases = len(PESTER_SOLUTIONS) if name == pester.NAME else 1
        require(len(results) == (1 if preflight else attempts * cases), "Released fixture attempt count differs")
        observed[job] = [inspect_trial(path, preflight=preflight, suite=name) for path in results]
    if name == pester.NAME:
        try:
            qualify_pester_publication(workspace, output, root, mode, revision, fixture_agent, observed)
        except (KeyError, OSError, TypeError, ValueError) as error:
            write_json(output / "failure.json", {"schema_version": 1, "revision": revision, "suite": name,
                "status": "diagnostic_handoff_failed", "failure_type": type(error).__name__,
                "observed": observed, "history_eligible": False, "provider_requests": 0})
            raise
        return
    run = Path(result["run_dir"])
    native.validate_collected_pair(result, run, root, name, mode, revision, [CASES[name]],
                                   agent_selector=fixture_agent)
    invalid = deepcopy(result)
    invalid["run_dir"] = str(run.with_name("unselected-report"))
    try:
        native.validate_collected_pair(invalid, run, root, name, mode, revision, [CASES[name]],
                                       agent_selector=fixture_agent)
    except ValueError as error:
        require(str(error) == "Missing or unsafe released benchmark report", "Wrong report selection rejection")
    else:
        raise ValueError("Released score projection accepted a substituted report path")
    invalid = deepcopy(result)
    invalid["agents"]["codex"]["pass_at_k"]["with_skill"]["cases"][CASES[name]]["attempts"][0]["trial"] = "unmatched"
    try:
        native.validate_collected_pair(invalid, run, root, name, mode, revision, [CASES[name]],
                                       agent_selector=fixture_agent)
    except ValueError as error:
        require(str(error) == "Released trial summary differs from the complete arm", "Wrong trial population rejection")
    else:
        raise ValueError("Released score projection accepted a substituted trial identity")
    rejection = {"podman": "Prepared benchmark scope differs",
                 "gh": "Released score report requires the full authored gh cohort"}[name]
    try:
        native.score_record(workspace, root, name, mode, revision)
    except ValueError as error:
        require(str(error) == rejection, "Native fixture was rejected at the wrong report boundary")
    else:
        raise ValueError("Partial native fixture entered the full-cohort score report")
    qualify_publication(root, output / "retained", name)
    if name == "gh":
        for arm, gate in (("with", 1), ("without", 0)):
            expected = {"gh_evidence": 1, "gh_activation": gate, native.GH_ACCESS_METRIC: gate, "gh_gate": gate}
            require(all(trial["custom"] == expected for trial in observed["gh-codex-" + arm]),
                    "Released grouped custom grader changed its expected authorization outcomes")
    receipt = {"schema_version": 2, "revision": revision, "producer": native.NATIVE_PRODUCER,
               "patch_sha256": native.NATIVE_PATCH_DIGEST, "suite": name, "case": CASES[name], "observed": observed,
               "mode": mode, "scored_attempts": 2 * attempts, "provider_requests": 0, "history_eligible": False,
               "full_cohort_report_rejected": True, "redacted_replay_verified": True,
               "origin": "non_forwarding_fixture"}
    if not all(trial["teardown_complete"] for trials in observed.values() for trial in trials):
        write_json(output / "failure.json", {**receipt, "status": "teardown_incomplete"})
        raise ValueError("Fixture left Compose resources")
    write_json(output / "qualification.json", receipt)


def qualify_pester_publication(workspace, output, root, mode, revision, fixture_agent, observed):
    import skill_evidence as evidence
    import skill_reports as reports

    with (patch.object(native, "CODEX_AGENT", fixture_agent), patch.dict(os.environ, GITHUB_SHA=revision)):
        native.diagnostic_report(workspace, root, pester.NAME, mode, revision)
        require(not (root / "released-scores.json").exists(), "Pester acquired standard scores")
        retained = output / "retained"
        reports.benchmark_artifacts(workspace, root, pester.NAME, retained)
        destination = output / "public"
        reports.public_benchmark(workspace, retained, pester.NAME, mode, destination)
        members = (destination / "skills" / pester.NAME / "behavioral").glob("*/public-report.json")
        public = read_json(next(members))
        require(public["availability"]["status"] == "complete"
                and public["policy"]["producer_profile"] == native.NATIVE_PRODUCER
                and public["policy"]["judge"]["enabled"] is False
                and public["policy"]["published_id"] is None, "Pester replay changed diagnostic status")
    try:
        evidence.normalize_behavioral(retained, pester.NAME, workspace=workspace)
    except ValueError as error:
        require(str(error) == "Native producer or runtime identity mismatch", "Fixture identity rejected at the wrong boundary")
    else:
        raise ValueError("Fixture adapter was admitted as production Codex")
    require(all(row["teardown_complete"] for job in observed.values() for row in job),
            "Pester fixture left Compose resources")
    write_json(output / "qualification.json", {"schema_version": 1, "revision": revision, "suite": pester.NAME,
        "producer": native.NATIVE_PRODUCER, "cases": sorted(PESTER_SOLUTIONS), "observed": observed, "mode": mode,
        "provider_requests": 0, "history_eligible": False, "redacted_replay_verified": True,
        "fixture_agent_rejected_in_production": True, "origin": "non_forwarding_fixture"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("suite", choices=(*CASES, pester.NAME))
    parser.add_argument("revision")
    parser.add_argument("--mode", choices=MODES, default="standard")
    args = parser.parse_args()
    qualify(args.output, args.suite, args.revision, mode=args.mode)


if __name__ == "__main__":
    main()
