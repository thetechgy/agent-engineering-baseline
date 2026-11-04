#!/usr/bin/env python3
"""Credential-free native backend lifecycle and deterministic gh fixtures."""

import asyncio
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import tempfile
import uuid

import gh_candidate
import gh_evaluations as gh
from aeb_gh_fixture.backend import TrustedGhEnvironment
from aeb_gh_fixture.manifest import write_manifest
from harbor.models.task.task import Task
from harbor.models.trial.paths import TrialPaths
from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True, timeout=30)


async def qualify(root, artifact, arm=None):
    bundle = gh_candidate.stage(gh.ROOT, root / "bundle/gh")
    tasks = []
    for present in (True, False):
        if arm is not None and arm != ("with_skill" if present else "without_skill"):
            continue
        tasks.extend(stage_native_harbor_tasks(bundle, root / "tasks" / str(present), with_skill=present,
            grading_mode="default_plus_custom", workspace_mode="group",
            workspace_skill_paths=[bundle.parent / gh.COMPETING]))
    expected = 24 if arm else 48
    if len(tasks) != expected:
        raise RuntimeError("Native gh cohort incomplete")
    manifest = write_manifest(root / "operator", tasks, staged_roots=[bundle.parent, root / "tasks"])
    os.environ["AEB_GH_MANIFEST"] = str(manifest)
    fixtures = {entry["id"]: entry for entry in gh.dataset()}
    rows = []
    for index, task in enumerate(tasks):
        native = Task(task)
        paths = TrialPaths(root / "trials" / str(index)); paths.mkdir()
        entry = json.loads((task / "tests/entry.json").read_text())
        present = entry["has_skill"]
        name = "aeb-gh-qualification-" + uuid.uuid4().hex[:16]
        environment = TrustedGhEnvironment(environment_dir=task / "environment", environment_name=name,
            session_id=name, trial_paths=paths, task_env_config=native.config.environment, mounts=[],
            network_policy=native.config.environment.resolve_baseline())
        environment.default_user = "agent"
        phase = "secure_start_and_initialization"
        failure = None
        try:
            await environment.start(force_build=True)
            async def checked(command, user="root"):
                result = await environment.exec(command, user=user, timeout_sec=30)
                if result.return_code:
                    raise RuntimeError("Native gh operation failed")
                return result.stdout or ""
            if (await checked("id -u", "agent")).strip() != "1000":
                raise RuntimeError("Agent UID changed")
            phase = "setup_only"
            setup_only = None
            if index == 0:
                from skillevaluator.tier3.harbor.installed_agents import SkillEvaluatorCodex
                from skillevaluator.tier3.harbor.runner import _harbor_agent_kwargs
                from unittest.mock import AsyncMock, patch
                pin = _harbor_agent_kwargs("codex", gh.reports.POLICY["model"], "aeb-gh-fixture")["version"]
                if pin != "0.155.1":
                    raise RuntimeError("Generated Codex dispatch pin changed")
                installed = await environment.exec("npm install --global --ignore-scripts @openai/codex@0.155.1", user="root", timeout_sec=180)
                if installed.return_code:
                    raise RuntimeError("Pinned setup-only Codex acquisition failed")
                agent = SkillEvaluatorCodex(logs_dir=paths.agent_dir, version=pin)
                with patch.object(SkillEvaluatorCodex, "run", AsyncMock(side_effect=AssertionError("Inference forbidden"))) as inference:
                    await agent.setup(environment)
                    inference.assert_not_called()
                measured = agent.parse_version(await checked("codex --version", "agent"))
                if measured != pin:
                    raise RuntimeError("Installed setup-only Codex version mismatch")
                setup_only = {"installed_codex": measured, "inference": False}
            phase = "repeated_startup"
            before = await checked("sha256sum /opt/gh-eval/state/audit.jsonl")
            # Repeated native startup must retain live identity and append-only state.
            first = json.loads(paths.trial_dir.joinpath("gh-initialization.jsonl").read_text().splitlines()[-1])
            await environment.start(force_build=False)
            second = json.loads(paths.trial_dir.joinpath("gh-initialization.jsonl").read_text().splitlines()[-1])
            if first != second or before != await checked("sha256sum /opt/gh-eval/state/audit.jsonl"):
                raise RuntimeError("Readiness mutated broker identity or audit")
            phase = "agent_private_access"
            for command in ("cat /opt/gh-eval/state/case.json", "cat /opt/gh-eval/state/audit.jsonl",
                            "cat /opt/aeb-gh/approved.json", "printf forged > /usr/local/bin/gh",
                            "printf forged > /run/gh-eval/gh.sock"):
                result = await environment.exec(command, user="agent", timeout_sec=5)
                if not result.return_code:
                    raise RuntimeError("Agent accessed protected fixture")
            phase = "modeled_operations"
            steps = []
            async def observed(command):
                result = await environment.exec(command, user="agent", timeout_sec=35)
                identity = str(len(steps))
                steps.append({"source": "agent", "tool_calls": [{"tool_call_id": identity,
                    "function_name": "exec_command", "arguments": {"cmd": command}}],
                    "observation": {"results": [{"source_call_id": identity, "content": (result.stdout or "") + (result.stderr or "")}]}})
                return result
            if present and entry.get("expected_skill"):
                await observed("cat /workspace/skills/gh/SKILL.md")
            elif not present:
                await checked("test ! -e /workspace/skills/gh", "agent")
            fixture = fixtures[task.name]
            for command in fixture["contract"]["good_commands"]:
                issued = ["gh", *command]
                if command[:2] == ["run", "watch"]:
                    issued = ["timeout", "30s", *issued]
                await observed(shlex.join(issued))
            if not fixture["contract"]["good_commands"]:
                await observed("git status --porcelain")
            await observed("printf '%s\\n' " + shlex.quote(json.dumps(fixture["contract"]["expected"])) + " > output/result.json")
            trajectory = root / "trajectory.json"; trajectory.write_text(json.dumps({"steps": steps}))
            await checked("install -d -m 700 /tests /logs/agent /logs/verifier")
            await environment.upload_dir(task / "tests", "/tests")
            await checked("chown -R root:root /tests && chmod 700 /tests")
            await environment.upload_file(trajectory, "/logs/agent/trajectory.json")
            # This calls the actual native custom grader and its staged normalizer;
            # standard remote judges are deliberately never invoked.
            phase = "native_grading"
            await checked("python3 -I /tests/grader.py")
            reward = json.loads(await checked("cat /logs/verifier/reward.json"))
            scores = reward["custom_metrics"]
            expected_metrics = {"gh_" + key for key in ("evidence", "activation", "commands", "task", "recovery", "authorization", "efficiency", "gate")}
            if set(scores) != expected_metrics or any(type(value) not in (int, float) or value not in (0, 1) for value in scores.values()):
                raise RuntimeError("Native gh metric schema mismatch")
            if scores["gh_gate"] != float(present or entry.get("expected_skill") is None) or any(scores["gh_" + key] != 1 for key in
                    ("evidence", "commands", "task", "recovery", "authorization", "efficiency")):
                raise RuntimeError("Native deterministic gh outcome mismatch")
            audit = await checked("sha256sum /opt/gh-eval/state/audit.jsonl")
            await environment.start(force_build=False)
            if audit != await checked("sha256sum /opt/gh-eval/state/audit.jsonl"):
                raise RuntimeError("Readiness modified completed audit")
            rows.append({"case": task.name, "arm": "with_skill" if present else "without_skill",
                "checksum": native.checksum, "metrics": scores, "initialization": first,
                "evidence": "controlled native fixture", "inference": False, "setup_only": setup_only})
        except BaseException as error:
            kind = type(error).__name__
            if kind not in {"RuntimeError", "ValueError", "OSError", "FileNotFoundError", "TypeError", "KeyError", "AttributeError", "TimeoutError", "CancelledError", "KeyboardInterrupt"}:
                kind = "Exception"
            diagnostic_code = "native_lifecycle_failed"
            message = str(error)
            if "snapshot.debian.org" in message and any(value in message for value in ("503", "504")):
                diagnostic_code = "debian_snapshot_unavailable"
            elif "Docker compose command failed" in message:
                diagnostic_code = "secure_docker_command_failed"
            elif "Trusted gh initialization failed" in message:
                diagnostic_code = "broker_initialization_failed"
            failure = {"phase": phase, "error": kind, "code": diagnostic_code, "case": task.name,
                       "arm": "with_skill" if present else "without_skill"}
            raise
        finally:
            await environment.stop(delete=True)
            if docker("ps", "-aq", "--filter", "label=com.docker.compose.project=" + name).strip():
                raise RuntimeError("Native gh teardown left a container")
            if docker("network", "ls", "-q", "--filter", "label=com.docker.compose.project=" + name).strip():
                raise RuntimeError("Native gh teardown left a network")
            artifact.write_text(json.dumps({"schema": 1, "inference": False, "diagnostic_only": True,
                "success": len(rows) == expected, "expected": expected, "completed": rows,
                "runtime": {key: importlib.metadata.version(key) for key in ("skillevaluator", "harbor")},
                "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "failure": failure,
                "initialization": [json.loads(line) for line in paths.trial_dir.joinpath("gh-initialization.jsonl").read_text().splitlines()]
                    if paths.trial_dir.joinpath("gh-initialization.jsonl").exists() else []}, indent=2) + "\n")
    return len(rows) == expected


def main(artifact, arm=None):
    artifact = Path(artifact); artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps({"success": False, "inference": False, "diagnostic_only": True, "completed": []}) + "\n")
    if any(os.environ.get(key) for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "NVIDIA_API_KEY")):
        raise RuntimeError("Qualification forbids provider credentials")
    if (importlib.metadata.version("skillevaluator"), importlib.metadata.version("harbor")) != ("0.7.2", "0.24.0"):
        raise RuntimeError("Incorrect gh qualification runtime")
    if docker("compose", "version", "--short").strip() != gh.reports.POLICY["docker_compose"]:
        raise RuntimeError("Incorrect Compose runtime")
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    with tempfile.TemporaryDirectory(prefix="gh-native-", dir=os.environ.get("RUNNER_TEMP")) as temporary:
        if not asyncio.run(qualify(Path(temporary), artifact, arm)):
            raise RuntimeError("Native gh qualification incomplete")


if __name__ == "__main__":
    import sys
    main(sys.argv[1])
