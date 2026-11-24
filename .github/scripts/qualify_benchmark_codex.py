"""Run the production Docker benchmark against an offline loopback provider."""
import argparse
import asyncio
import base64
from contextlib import nullcontext
from importlib.metadata import version
import json
import idna
import os
from pathlib import Path
import shlex
import shutil
import time
import tempfile
import subprocess

from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks
from skillevaluator.tier3.harbor.collector import collect_harbor_results
from skillevaluator.tier3.harbor.report import display_findings_report
from skillevaluator.tier3.harbor.runner import build_harbor_run_command

import gh_evaluations as gh
from qualify_codex_1691 import acquire
from skill_reports import POLICY, read_json, require, write_json

RELEASE = version('skillevaluator') == '1.0.1'
if RELEASE:
    from aeb_gh_fixture.benchmark_codex import BenchmarkCodex
else:
    from skillevaluator.tier3.harbor.benchmark_codex import BenchmarkCodex

CASE = "gh-001"
PROFILE = gh.ROOT / ".github/evals/codex-execution-1710.json"
ENDPOINT = "http://127.0.0.1:8765/v1"
SENTINEL = "pilot-not-a-credential"
VENDOR = "/opt/reviewed/node_modules/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/"


# Run as the trial user. Other UIDs' /proc/exe links are intentionally unreadable.
INTERRUPT_AGENT = r"""
import os
from pathlib import Path
import signal

matches = []
for proc in Path("/proc").glob("[0-9]*"):
    try:
        if proc.stat().st_uid != os.getuid():
            continue
        argv = (proc / "cmdline").read_bytes().split(b"\0")
    except (FileNotFoundError, PermissionError):
        continue
    if len(argv) > 2 and argv[0].split(b"/")[-1] == b"codex" and argv[1] == b"exec":
        matches.append(int(proc.name))
if len(matches) != 1:
    raise RuntimeError(f"Expected one trial Codex exec, found {len(matches)}")
os.kill(matches[0], signal.SIGINT)
"""


class OfflineCodex(BenchmarkCodex):
    """Replace Internet installation only. Harbor owns execution and log conversion."""

    async def install(self, environment):
        profile = read_json(PROFILE)
        expected = {"bin/codex": profile["cli_executable_sha256"], **profile["helper_sha256"]}
        require(self._version == profile["cli"], "Generated dispatch version drift")
        # npm omits the standalone archive's optional exec-server. Exercise the
        # installed package exactly as published, including its native launcher.
        del expected["bin/codex-exec-server"]
        await self.exec_as_root(environment, "test ! -e " + VENDOR + "bin/codex-exec-server")
        for name, sha in expected.items():
            result = await self.exec_as_root(environment, "sha256sum " + VENDOR + name)
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
    if RELEASE:
        import gh_candidate
        bundle = gh_candidate.stage(gh.ROOT, root / "bundle/gh", [CASE], fixture=True)
    else:
        bundle = gh.stage(gh.ROOT, root / "bundle/gh", [CASE])
    task, = stage_native_harbor_tasks(bundle, root / "tasks", with_skill=present, grading_mode="custom_only",
        workspace_mode="group", workspace_skill_paths=[bundle.parent / gh.COMPETING])
    descriptor = task / "task.toml"
    source = descriptor.read_text()
    require('network_mode = "public"' in source, "Unknown source networking")
    descriptor.write_text(source.replace('network_mode = "public"', 'network_mode = "no-network"'))
    image = task / "environment"
    if RELEASE:
        # The operator-owned loopback responder is inside the same network namespace.
        # Harbor must leave this service on loopback instead of joining the egress sidecar.
        with (image / "docker-compose.yaml").open("x", encoding="utf-8") as override:
            override.write("services:\n  main:\n    network_mode: none\n")
        reviewed = image / "reviewed"
        reviewed.mkdir()
        # Keep packaged executables out of the broker's bounded task tree.
        # Install scripts are disabled and every executable is checked in install().
        launcher = VENDOR + "bin/codex"
        package = "@openai/codex@" + POLICY["codex"]
        install = ("RUN npm install --prefix /opt/reviewed --no-audit --no-fund --ignore-scripts "
                   "--registry=https://registry.npmjs.org/ " + package + "\n"
                   + "ENV PATH=" + VENDOR + "codex-path:$PATH\n")
    else:
        shutil.copytree(assets / "lib/node_modules", image / "reviewed/node_modules", symlinks=True)
        launcher = "/opt/reviewed/node_modules/@openai/codex/bin/codex.js"
        install = ""
    shutil.copy2(gh.ROOT / ".github/scripts/codex_pilot_stub.py", image / "reviewed/stub.py")
    with (image / "Dockerfile").open("a") as build:
        build.write("\nCOPY reviewed /opt/reviewed\n" + install + "RUN chmod -R a+rX /opt/reviewed /workspace/skills"
                    " && ln -s " + launcher + " /usr/local/bin/codex\n")
    # The production verifier reads real ATIF and the private broker audit. Copy
    # only the loopback request and the produced edit into this local fixture.
    # The standard verifier image carries idna. Custom-only mode omits its
    # judge dependencies, so stage the same locked pure-Python import.
    shutil.copytree(Path(idna.__file__).parent, task / "tests/idna", ignore=shutil.ignore_patterns("__pycache__"))
    verify = task / "tests/test.sh"
    if RELEASE:
        verify.write_text("#!/bin/sh\nset -eu\npython3 -I /tests/grader.py\n")
    with verify.open("a") as script:
        script.write("\ncp /opt/reviewed/request.json /logs/verifier/provider.json\n"
                     "test ! -e /tmp/codex-secrets\ntest -z \"$(find /home/agent -maxdepth 1 -name '.codex-benchmark.*')\"\n"
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
    write_json(fixture_file, {"scenario": "benchmark-interruption" if interrupt else "benchmark-priced", "commands": calls})
    jobs = root.parent / "jobs"
    job_name = "gh-interrupted" if interrupt else "gh-codex-" + ("with" if present else "without")
    mode = "aeb-gh-fixture" if RELEASE else "docker"
    argv = build_harbor_run_command(dataset_path=task.parent, job_name=job_name, jobs_dir=jobs,
        agent="codex", model=POLICY["model"], env_mode=mode, n_concurrent=1)
    env = dict(os.environ, PYTHONPATH=str(gh.ROOT / ".github/scripts"), BENCHMARK_CODEX_FIXTURE=str(fixture_file))
    if RELEASE:
        from aeb_gh_fixture.manifest import write_manifest
        manifest = write_manifest(root / "operator", [task], staged_roots=[root / "tasks", root / "bundle"])
        env["AEB_GH_MANIFEST"] = str(manifest)
        require(argv[argv.index("--env") + 1] == "aeb_gh_fixture.backend:TrustedGhEnvironment",
                "Unexpected benchmark environment")
        require("version=" + json.dumps(POLICY["codex"]) in argv and 'reasoning_effort="high"' in argv,
                "Workflow dispatch pin drift")
        index = argv.index("--agent") + 1
    else:
        require(argv[argv.index("--ak") + 1] == "version=" + POLICY["codex"], "Workflow dispatch pin drift")
        index = argv.index("--agent-import-path") + 1
    require(argv[index] == BenchmarkCodex.__module__ + ":BenchmarkCodex", "Unexpected benchmark agent")
    argv[index] = "qualify_benchmark_codex:OfflineCodex"
    with subprocess.Popen(argv, env=env) as job:
        try:
            if interrupt:
                deadline = time.monotonic() + 420
                while time.monotonic() < deadline and job.poll() is None:
                    log = next((jobs / job_name).glob("*/agent/codex.txt"), None)
                    if log and '"item.started"' in log.read_text(errors="replace"):
                        container = read_json(log.parent.parent / "fixture-container.json")["id"]
                        subprocess.run(["docker", "exec", "--user", "agent", container,
                                        "python3", "-c", INTERRUPT_AGENT], check=True)
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
        require((result.get("exception_info") or {}).get("exception_type") == "NonZeroAgentExitCodeError"
                and any(e["type"] == "item.started" and e["item"]["type"] == "command_execution" for e in events)
                and not any(e["type"] == "turn.completed" for e in events), "Interrupted trial looked complete")
        usage = result.get("agent_result") or {}
        require(all(usage.get(key) is None for key in ("n_input_tokens", "n_cache_tokens", "n_output_tokens", "cost_usd")),
                "Incomplete usage was presented as a final measurement")
        return {"execution": "interrupted", "exception": result["exception_info"]["exception_type"],
                "usage": None, "cleanup": True}
    require(result.get("exception_info") is None, "Trial failed: " + str(result.get("exception_info")))
    native_reward = read_json(trial / "verifier/custom_reward.json")
    require("error" not in native_reward, "Native custom verifier failed: " + str(native_reward.get("error")))
    request = read_json(trial / "verifier/provider.json")
    require(request["requests"] == 2 and all(row["model"] == POLICY["model"] and row["reasoning"]["effort"] == "high"
        and row["path"] == "/v1/responses" and row["authorization_matches_sentinel"] for row in request["request_observations"]),
        "Unexpected provider identity")
    require(read_json(trial / "verifier/edited.json") == fixture["expected"], "Native patch output changed")
    completed = [e["item"]["type"] for e in events if e["type"] == "item.completed"]
    require(("command_execution" if present else "file_change") in completed, "Native action missing")
    require(result["agent_info"]["version"] == POLICY["codex"], "Reported executable version drift")
    metrics = native_reward["custom_metrics"]
    require(metrics["gh_authorization"] == int(present) and metrics["gh_evidence"] == 1,
            "Verifier could not bind these native operations to the private broker audit: " + str(metrics))
    usage = result["agent_result"]
    require([usage.get(key) for key in ("n_input_tokens", "n_cache_tokens", "n_output_tokens")] == [300, 100, 30],
            "Collector usage drift")
    return {"version": result["agent_info"]["version"], "requests": request["requests"], "model": request["model"],
            "reasoning": request["reasoning"]["effort"], "actions": completed, "cleanup": True,
            "input_tokens": usage["n_input_tokens"], "cache_tokens": usage["n_cache_tokens"],
            "output_tokens": usage["n_output_tokens"], "authorization": metrics["gh_authorization"]}


def judge_requests():
    from unittest.mock import patch
    from skillevaluator.tier3.harbor.templates import eval as verifier
    from judge_transport_090 import Responder, SETTINGS

    responder = Responder()
    settings = {**SETTINGS, "SKILL_EVAL_LLM_MODEL": POLICY["model"], "SKILL_EVAL_JUDGE_MODEL": POLICY["model"]}
    # v0.3 uses its own JSON score schema. Reuse the loopback transport and capture every POST.
    def reply(payload):
        responder.requests.append(payload)
        result = {"score": 1, "achieved": True, "reason": "Fixture",
                  "results": [{"step": 1, "passed": True, "reason": "Fixture"}], "summary": "Fixture"}
        # Each judge receives an invalid first response to exercise its repair route.
        content = 'invalid fixture response' if len(responder.requests) % 2 else json.dumps(result)
        return 200, json.dumps({"choices": [{"message": {"content": content}}]}).encode()

    with patch.dict(os.environ, settings, clear=True), patch.object(responder, "respond", reply), responder.boundary():
        for judge, args in ((verifier.judge_accuracy, ("Return 42", "42", "42")),
                            (verifier.judge_goal_accuracy, ("Return 42", "42", "42")),
                            (verifier.judge_behavior_check, ("Returned 42", ["Return 42"]))):
            before = len(responder.requests)
            result = judge(*args)
            require(result.get("score") == 1, "Native judge rejected fixture response: " + judge.__name__)
            require(len(responder.requests) == before + 2, "Missing native judge repair request: " + judge.__name__)
    with patch.dict(os.environ, {"LLM_JUDGE_FALLBACK_MODELS": "unapproved-model"}, clear=True):
        require(verifier._selected_judge_model() == POLICY["model"] and
                verifier._fallback_models(POLICY["model"]) == [POLICY["model"]],
                "Unconfigured verifier or inherited retry model drift")
    require(all(p.get("model") == "gpt-6.2-sol" and "max_completion_tokens" in p
                and "temperature" not in p and "reasoning_effort" not in p for p in responder.requests),
            "Production Chat Completions judge payload drift")
    return {"model": POLICY["model"], "endpoint": "/v1/chat/completions", "requests": len(responder.requests)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    root = parser.parse_args().output.resolve()
    require(not any(os.getenv(k) for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "CODEX_AUTH_JSON_PATH",
        "CODEX_FORCE_AUTH_JSON", "CODEX_API_KEY", "SKILL_EVAL_LLM_API_KEY", "NVIDIA_API_KEY")),
        "Real credentials are prohibited")
    if RELEASE:
        from qualify_benchmark_101 import fixture_owner, verifier_requests
    else:
        fixture_owner, verifier_requests = nullcontext, judge_requests
    with fixture_owner() as versions:
        qualify(root, verifier_requests, versions)


def qualify(root, verifier_requests, versions):
    root.mkdir()
    npm_prefix = root / "npm"
    if not RELEASE:
        assets = root / "release"
        assets.mkdir()
        profile = read_json(PROFILE)
        acquire(profile, assets)
        with tempfile.TemporaryDirectory(prefix="codex-npm-cache-") as cache:
            subprocess.run(["npm", "install", "--global", "--prefix", str(npm_prefix), "--cache", cache,
                "--no-audit", "--no-fund", "--ignore-scripts", "@openai/codex@" + profile["cli"]], check=True)
    rows = [run(root / arm, npm_prefix, arm == "with") for arm in ("with", "without")]
    partial = run(root / "interrupted", npm_prefix, True, interrupt=True)
    report = root / "report"
    options = {"env_mode": "aeb-gh-fixture", "grading_mode": "custom_only"} if RELEASE else {"env_mode": "docker"}
    collected = collect_harbor_results("gh", ["codex"], report, root / "jobs", expected_cases=1,
        expected_case_ids=[CASE], expected_trials=1, n_attempts=1, stop_on_pass=False,
        agent_models={"codex": {"model": POLICY["model"], "source": "cli"}}, **options)
    for arm in ("with", "without"):
        scores = collected["agents"]["codex"]["custom_" + arm + "_skill"]
        if not RELEASE:
            require(scores.get("gh_authorization") == int(arm == "with"), "Native authorization grade drift")
        if arm == "with":
            require(scores.get("gh_task") == 1 and scores.get("gh_gate") == 1, "Approved gh task failed")
    display_findings_report(collected, "gh", ["codex"], report)
    summary = {"inference": False, "agent": rows, "judges": verifier_requests(), "interruption": partial,
               "with_skill_gate": collected["agents"]["codex"]["custom_with_skill"]["gh_gate"]}
    if versions is not None:
        summary["runtime"] = versions
    write_json(root / "qualification.json", summary)
    print(json.dumps(summary, sort_keys=True), flush=True)
    print("Production dispatch, broker, agent, verifier, collector and report passed", flush=True)


if __name__ == "__main__":
    main()
