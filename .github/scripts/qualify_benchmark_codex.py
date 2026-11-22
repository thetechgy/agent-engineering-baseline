"""Run the production Docker benchmark against an offline loopback provider."""
import argparse
import asyncio
import base64
import json
import os
from pathlib import Path
import shlex
import shutil
import time
import subprocess

from harbor.agents.installed.codex import Codex
from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks
from skillevaluator.tier3.harbor.collector import collect_harbor_results
from skillevaluator.tier3.harbor.report import display_findings_report
from skillevaluator.tier3.harbor.runner import build_harbor_run_command

import gh_evaluations as gh
from qualify_codex_1691 import acquire
from skill_reports import POLICY, read_json, require, write_json

CASE = "gh-001"
PROFILE = gh.ROOT / ".github/evals/codex-execution-1710.json"
ENDPOINT = "http://127.0.0.1:8765/v1"
SENTINEL = "pilot-not-a-credential"


class OfflineCodex(Codex):
    """Replace Internet installation only. Harbor owns execution and log conversion."""

    async def install(self, environment):
        profile = read_json(PROFILE)
        expected = {"bin/codex": profile["cli_executable_sha256"], **profile["helper_sha256"]}
        require(self._version == profile["cli"], "Generated dispatch version drift")
        for name, sha in expected.items():
            result = await self.exec_as_root(environment, "sha256sum /opt/reviewed/" + name)
            require(result.stdout.split()[0] == sha, "Container release bytes differ")
        result = await self.exec_as_agent(environment, "codex --version && id -u && test -S /run/gh-eval/gh.sock && test ! -r /opt/gh-eval/state/case.json")
        require(result.stdout.splitlines() == ["codex-cli " + self._version, "1000"], "Agent identity or CLI drift")
        container = (await environment._run_docker_compose_command(["ps", "--quiet", "main"])).stdout.strip()
        inspected, = json.loads(subprocess.check_output(["docker", "inspect", container]))
        require(inspected["HostConfig"]["NetworkMode"] == "none", "Fixture requires isolated networking")
        write_json(self.logs_dir.parent / "fixture-container.json", {"id": container})

        # Every byte supplied to the native agent is public fixture data.
        fixture = read_json(Path(os.environ["BENCHMARK_CODEX_FIXTURE"]))
        commands = base64.b64encode(json.dumps(fixture["commands"]).encode()).decode()
        argv = ["python3", "/opt/reviewed/stub.py", "/opt/reviewed/request.json", fixture["scenario"],
                "Zml4dHVyZQ==", commands]
        await self.exec_as_root(environment, shlex.join(argv) + " >/opt/reviewed/provider.log 2>&1 </dev/null &")
        ready = "python3 -c " + shlex.quote("import socket; socket.create_connection(('127.0.0.1',8765),1).close()")
        for _ in range(50):
            if (await environment.exec(ready, user="agent")).return_code == 0:
                break
            await asyncio.sleep(.1)
        else:
            raise ValueError("Loopback responder failed to start")
        self._extra_env.update(OPENAI_API_KEY=SENTINEL, OPENAI_BASE_URL=ENDPOINT)


def stage(root, assets, present):
    bundle = gh.stage(gh.ROOT, root / "bundle/gh", [CASE])
    task, = stage_native_harbor_tasks(bundle, root / "tasks", with_skill=present, grading_mode="custom_only",
        workspace_mode="group", workspace_skill_paths=[bundle.parent / gh.COMPETING])
    descriptor = task / "task.toml"
    source = descriptor.read_text()
    require('network_mode = "public"' in source, "Unknown source networking")
    descriptor.write_text(source.replace('network_mode = "public"', 'network_mode = "no-network"'))
    image = task / "environment"
    for member in ("bin", "codex-resources", "codex-path"):
        shutil.copytree(assets / member, image / "reviewed" / member)
    shutil.copy2(gh.ROOT / ".github/scripts/codex_pilot_stub.py", image / "reviewed/stub.py")
    with (image / "Dockerfile").open("a") as build:
        build.write("\nCOPY reviewed /opt/reviewed\nRUN ln -s /opt/reviewed/bin/codex /usr/local/bin/codex\n")
    # The production verifier reads real ATIF and the private broker audit. Copy
    # only the loopback request and the produced edit into this local fixture.
    verify = task / "tests/test.sh"
    with verify.open("a") as script:
        script.write("\ncp /opt/reviewed/request.json /logs/verifier/provider.json\n"
                     "test ! -e /tmp/codex-secrets && test ! -e /tmp/codex-home\n"
                     "cp /workspace/output/result.json /logs/verifier/edited.json\n")
    return task


def run(root, assets, present, *, interrupt=False):
    task = stage(root, assets, present)
    fixture = gh.dataset(selected=[CASE])[0]["contract"]
    output = json.dumps(fixture["expected"])
    if present:
        calls = ["cat /workspace/skills/gh/SKILL.md"]
        calls.extend(shlex.join(["gh", *cmd]) for cmd in fixture["good_commands"])
        calls.append("printf '%s\\n' " + shlex.quote(output) + " > output/result.json")
    else:
        # gh-001 permits one literal shell write. A real patch must be
        # observable, and must fail that existing authorization metric.
        calls = [{"tool": "apply_patch", "expect_failure": False, "input":
            "*** Begin Patch\n*** Add File: output/result.json\n+" + output + "\n*** End Patch"}]
    fixture_file = root / "provider.json"
    write_json(fixture_file, {"scenario": "interruption" if interrupt else "priced-success", "commands": calls})
    jobs = root.parent / "jobs"
    job_name = "gh-interrupted" if interrupt else "gh-codex-" + ("with" if present else "without")
    argv = build_harbor_run_command(dataset_path=task.parent, job_name=job_name, jobs_dir=jobs,
        agent="codex", model=POLICY["model"], env_mode="docker", n_concurrent=1)
    require(argv[argv.index("--ak") + 1] == "version=" + POLICY["codex"], "Workflow dispatch pin drift")
    index = argv.index("-a")
    require(argv[index + 1] == "codex", "Unexpected benchmark agent")
    argv[index:index + 2] = ["--agent-import-path", "qualify_benchmark_codex:OfflineCodex"]
    env = dict(os.environ, PYTHONPATH=str(gh.ROOT / ".github/scripts"), BENCHMARK_CODEX_FIXTURE=str(fixture_file))
    with subprocess.Popen(argv, env=env) as job:
        try:
            if interrupt:
                deadline = time.monotonic() + 420
                while time.monotonic() < deadline and job.poll() is None:
                    log = next((jobs / job_name).glob("*/agent/codex.txt"), None)
                    if log and '"item.started"' in log.read_text(errors="replace"):
                        container = read_json(log.parent.parent / "fixture-container.json")["id"]
                        # Only signal this fixture's verified executable in its own container.
                        terminate = ("import os,signal; from pathlib import Path; "
                            "pids=[int(p.name) for p in Path('/proc').iterdir() if p.name.isdigit() "
                            "and os.path.realpath(p/'exe')=='/opt/reviewed/bin/codex']; "
                            "assert len(pids)==1; os.kill(pids[0],signal.SIGINT)")
                        subprocess.run(["docker", "exec", "--user", "root", container, "python3", "-c", terminate], check=True)
                        break
                    time.sleep(.25)
                else:
                    raise ValueError("No started native command to interrupt")
            require(job.wait(timeout=480) == 0 or interrupt, "Harbor job exited unsuccessfully")
        finally:
            if job.poll() is None:
                job.terminate()
                job.wait(timeout=30)
    trial, = (jobs / job_name).glob("*/fixture-container.json")
    container = read_json(trial)["id"]
    require(subprocess.run(["docker", "container", "inspect", container], capture_output=True).returncode != 0,
            "Native trial container survived teardown")
    trial = trial.parent
    result = read_json(trial / "result.json")
    events = [json.loads(line) for line in (trial / "agent/codex.txt").read_text().splitlines() if line.startswith("{")]
    if interrupt:
        require(result.get("exception_info") and any(e["type"] == "item.started" for e in events)
                and not any(e["type"] == "turn.completed" for e in events), "Interrupted trial looked complete")
        return {"execution": "interrupted", "exception": result["exception_info"]["exception_type"],
                "usage": None, "cleanup": True}
    require(result.get("exception_info") is None, "Trial failed: " + str(result.get("exception_info")))
    request = read_json(trial / "verifier/provider.json")
    require(request["requests"] == 2 and all(row["model"] == POLICY["model"] and row["reasoning"]["effort"] == "high"
        and row["path"] == "/v1/responses" and row["authorization_matches_sentinel"] for row in request["request_observations"]),
        "Unexpected provider identity")
    require(read_json(trial / "verifier/edited.json") == fixture["expected"], "Native patch output changed")
    completed = [e["item"]["type"] for e in events if e["type"] == "item.completed"]
    require(("command_execution" if present else "file_change") in completed, "Native action missing")
    usage = result["agent_result"]
    require([usage.get(key) for key in ("n_input_tokens", "n_cache_tokens", "n_output_tokens")] == [300, 100, 30],
            "Collector usage drift")
    return {"version": result["agent_info"]["version"], "requests": request["requests"], "model": request["model"],
            "reasoning": request["reasoning"]["effort"], "actions": completed, "cleanup": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    root = parser.parse_args().output.resolve()
    require(not any(os.getenv(k) for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "CODEX_AUTH_JSON_PATH",
        "CODEX_FORCE_AUTH_JSON", "NVIDIA_API_KEY")), "Real credentials are prohibited")
    root.mkdir()
    assets = root / "release"
    assets.mkdir()
    acquire(read_json(PROFILE), assets)
    rows = [run(root / arm, assets, arm == "with") for arm in ("with", "without")]
    partial = run(root / "interrupted", assets, True, interrupt=True)
    report = root / "report"
    collected = collect_harbor_results("gh", ["codex"], report, root / "jobs", expected_cases=1,
        expected_case_ids=[CASE], expected_trials=1, n_attempts=1, env_mode="docker", stop_on_pass=False,
        agent_models={"codex": {"model": POLICY["model"], "source": "cli"}})
    for arm in ("with", "without"):
        scores = collected["agents"]["codex"]["custom_" + arm + "_skill"]
        require(scores.get("gh_authorization") == int(arm == "with"), "Native authorization grade drift")
        if arm == "with":
            require(scores.get("gh_task") == 1 and scores.get("gh_gate") == 1, "Approved gh task failed")
    display_findings_report(collected, "gh", ["codex"], report)
    write_json(root / "qualification.json", {"inference": False, "agent": rows, "interruption": partial, "results": collected["agents"]["codex"]})
    print("Production dispatch, broker, agent, verifier, collector and report passed", flush=True)


if __name__ == "__main__":
    main()
