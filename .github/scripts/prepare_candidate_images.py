"""Operator package preparation; no agent setup, grading or model execution."""

import argparse
import asyncio
import hashlib
import importlib.metadata
import inspect
import json
import os
import re
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import uuid

import pester_container_validation as pilot
from harbor.models.task.task import Task
from harbor.models.trial.paths import TrialPaths
from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks, _task_environment_context_hash
from skillevaluator.tier3.harbor.secure_docker_environment import SkillEvaluatorSecureDockerEnvironment

RUNTIME_COMMAND = (
    "/opt/microsoft/powershell/7/pwsh -NoLogo -NoProfile -NonInteractive -Command "
    "'[Console]::WriteLine($PSVersionTable.PSVersion.ToString()); "
    "Import-Module /opt/pester/Modules/Pester/6.2.0/Pester.psd1 -RequiredVersion 6.2.0 -ErrorAction Stop; "
    "[Console]::WriteLine((Get-Module Pester).Version.ToString())'"
)


from evaluator_profiles import CANDIDATE, owning_candidate
try:
    CANDIDATE = owning_candidate()
except ValueError:
    pass

RUNTIMES = {"current": {"skillevaluator": CANDIDATE['version'], "harbor": CANDIDATE['harbor']}, "candidate": {"skillevaluator": "0.7.2", "harbor": "0.24.0"},
            "retained": {"skillevaluator": "0.3.0", "harbor": "0.13.2"}}

BUILD_ATTEMPT_SECONDS = 300
INTEGRITY_ERRORS = ("digest mismatch", "hash sum mismatch", "gpg error", "not signed",
                    "signature", "certificate verification")

GH_RUNTIME_COMMAND = "/usr/bin/node --version"


def staged_task(root, suite="pester", arm=None, shard=None, runtime="candidate"):
    if suite == "gh":
        if runtime != "candidate":
            raise ValueError("Trusted gh preparation requires the candidate runtime")
        import gh_candidate
        import gh_initializer_validation as native
        import gh_evaluations as gh
        bundle = gh_candidate.stage(gh.ROOT, root / "bundle/gh")
        tasks = []
        for present in (True, False):
            if arm is not None and arm != ("with_skill" if present else "without_skill"):
                continue
            tasks.extend(stage_native_harbor_tasks(bundle, root / "tasks" / str(present), with_skill=present,
                grading_mode="default_plus_custom", workspace_mode="group", workspace_skill_paths=[bundle.parent / gh.COMPETING]))
        selected, _ = native.select_tasks(tasks, arm, shard)
        return selected[0]
    if suite != "pester":
        raise ValueError("Unsupported preparation suite")
    bundle, fixtures = pilot.qualification_bundle(root, candidate=runtime in ("candidate", "current"))
    tasks = stage_native_harbor_tasks(bundle, root / "tasks", with_skill=True, grading_mode="custom_only")
    if len(tasks) != 26 or len(fixtures) != 26:
        raise RuntimeError("Incomplete package preparation source cohort")
    return next(task for task in tasks if task.name == "pester-001-classic")


def transient_snapshot_failure(message):
    # Require the observed fatal APT fetch failure, rather than an earlier
    # warning followed by an integrity/signature failure elsewhere in build.
    return ("Docker compose command failed" in message and "exit code: 100" in message
            and not any(value in message.lower() for value in INTEGRITY_ERRORS)
            and any("Failed to fetch" in line and "snapshot.debian.org" in line
                    and re.search(r"\b(?:503|504)\b", line) for line in message.splitlines()))


def retryable_build_timeout(entry):
    commands = entry.get("commands", [])
    if entry.get("commands_truncated") or not commands:
        return False
    last = commands[-1]
    return (last.get("kind") == "compose" and last.get("operation") == "build"
            and last.get("status") == "timed_out"
            and not last.get("build_progress", {}).get("integrity_failure"))


def observed_environment(base, entry):
    """Record bounded command phases while delegating every hardened operation."""
    async def observe(kind, command, invoke, progress=None):
        allowed = {"build", "up", "down", "exec", "cp", "ps", "logs", "stop", "rm", "config", "image", "info", "inspect", "network", "version"}
        operation = command[0] if command and command[0] in allowed else "other"
        events = entry.setdefault("commands", [])
        event = {"kind": kind, "operation": operation, "status": "running"}
        if progress is not None:
            event["build_progress"] = progress
        if len(events) < 32:
            events.append(event)
        else:
            entry["commands_truncated"] = True
        started = time.monotonic()
        try:
            if kind == "compose" and operation == "build":
                result = await asyncio.wait_for(invoke(), timeout=entry.get("build_timeout_sec", BUILD_ATTEMPT_SECONDS))
            else:
                result = await invoke()
            event["status"] = "complete"
            return result
        except BaseException as error:
            event["status"] = ("timed_out" if isinstance(error, TimeoutError) else
                               "cancelled" if isinstance(error, asyncio.CancelledError) else "failed")
            if isinstance(error, RuntimeError) and transient_snapshot_failure(str(error)):
                event["code"] = "debian_snapshot_unavailable"
            raise
        finally:
            event["elapsed_sec"] = round(time.monotonic() - started, 3)

    class Observed(base):
        async def _run_docker_compose_command(self, command, *args, **kwargs):
            parent = super()._run_docker_compose_command
            signature = inspect.signature(parent)
            # Only the candidate owning API supports redacted build streaming.
            # Retained commands keep their original collector and arguments.
            if command and command[0] == "build" and "on_output" in signature.parameters:
                arguments = signature.bind(command, *args, **kwargs)
                original = arguments.arguments.get("on_output")
                progress, tail = {}, ""
                async def classify(text, stream):
                    nonlocal tail
                    tail = (tail + text)[-4096:]
                    stages = (("load metadata for", "base_image_metadata"),
                              ("transferring context", "context_transfer"),
                              ("apt-get update", "package_install"),
                              ("apt-get install", "package_install"),
                              ("install-runtime.py", "runtime_install"),
                              ("exporting layers", "layer_export"))
                    for token, stage in stages:
                        if token in text:
                            progress["stage"] = stage
                    for code, description in (("503", "Service Unavailable|No healthy backends"),
                                              ("504", "Gateway Time-out|Gateway Timeout")):
                        if re.search(r"\b" + code + r"\s+(?:" + description + r")\b", tail, re.I):
                            progress["http_" + code] = True
                    if "snapshot.debian.org" in tail:
                        progress["debian_snapshot"] = True
                    if any(token in tail.lower() for token in INTEGRITY_ERRORS):
                        progress["integrity_failure"] = True
                    if original is not None:
                        await original(text, stream)
                arguments.arguments["on_output"] = classify
                return await observe("compose", command, lambda: parent(*arguments.args, **arguments.kwargs), progress)
            return await observe("compose", command, lambda: parent(command, *args, **kwargs))

        async def _run_trusted_docker_command(self, command):
            parent = super()._run_trusted_docker_command
            return await observe("docker", command, lambda: parent(command))

    return Observed


async def prepare(root, artifact, suite="pester", arm=None, shard=None, runtime="candidate"):
    status = {"schema": 1, "status": "preparing", "diagnostic_only": True, "inference": False,
              "phase": "stage", "suite": suite, "arm": arm, "shard": shard, "runtime_name": runtime,
              "qualification_context": "cache_prepared", "attempts": [],
              "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    old_manifest = os.environ.get("AEB_GH_MANIFEST")
    def retain():
        artifact.write_text(json.dumps(status, indent=2) + "\n")
    try:
        versions = {key: importlib.metadata.version(key) for key in ("skillevaluator", "harbor")}
        status["runtime"] = versions
        dependencies = {key: importlib.metadata.version(key) for key in ("openai", "pydantic")}
        status["dependencies"] = dependencies
        expected_python = (3, 14) if runtime == "current" else (3, 13)
        expected_dependencies = {key: CANDIDATE['dependencies'][key] for key in ('openai', 'pydantic')} if runtime == "current" else {"openai": "2.44.0", "pydantic": "2.13.4"}
        if (runtime not in RUNTIMES or versions != RUNTIMES[runtime] or sys.version_info[:2] != expected_python
                or dependencies != expected_dependencies):
            raise RuntimeError("Unqualified package preparation runtime")
        task = staged_task(root, suite, arm, shard, runtime)
        native = Task(task)
        status.update(task_checksum=native.checksum, environment_context=_task_environment_context_hash(task / "environment"))
        environment_type = SkillEvaluatorSecureDockerEnvironment
        command, expected = RUNTIME_COMMAND, ["7.6.9", "6.2.0"]
        if suite == "gh":
            from aeb_gh_fixture.backend import TrustedGhEnvironment
            from aeb_gh_fixture.manifest import write_manifest
            environment_type = TrustedGhEnvironment
            manifest = write_manifest(root / "operator", [task], staged_roots=[task.parent, root / "bundle", root / "tasks"])
            os.environ["AEB_GH_MANIFEST"] = str(manifest)
            command, expected = GH_RUNTIME_COMMAND, ["v20.19.2"]
        deadline = time.monotonic() + 1100
        maximum_attempts = 1 if runtime == "current" else 3
        for number in range(1, maximum_attempts + 1):
            paths = TrialPaths(root / ("trial-" + str(number))); paths.mkdir()
            name = "aeb-image-packages-" + uuid.uuid4().hex[:16]
            entry = {"attempt": number, "status": "preparing", "phase": "secure_start", "retry": False}
            status["attempts"].append(entry)
            environment = None
            try:
                environment = observed_environment(environment_type, entry)(environment_dir=task / "environment", environment_name=name,
                    session_id=name, trial_paths=paths, task_env_config=native.config.environment, mounts=[],
                    network_policy=native.config.environment.resolve_baseline())
                environment.default_user = "agent"
                remaining = deadline - time.monotonic() - 90
                if remaining <= 0:
                    raise TimeoutError("Preparation budget exhausted")
                entry["build_timeout_sec"] = min(BUILD_ATTEMPT_SECONDS, remaining)
                status["phase"] = "secure_start"
                retain()
                # Only operator package acquisition uses this separate budget.
                # Native trials retain their original startup/execution limits.
                await asyncio.wait_for(environment.start(force_build=True), timeout=remaining)
                status["phase"] = entry["phase"] = "runtime_check"
                measured = await environment.exec(command, user="root", timeout_sec=20)
                if measured.return_code or (measured.stdout or "").splitlines() != expected:
                    raise RuntimeError("Prepared fixture runtime differs from its pins")
                if Task(task).checksum != status["task_checksum"]:
                    raise RuntimeError("Package preparation changed staged inputs")
                entry["status"] = "prepared"
            except BaseException as error:
                kind = type(error).__name__
                entry.update(status="cancelled" if isinstance(error, asyncio.CancelledError) else "infrastructure_error",
                    error=kind if kind in {"RuntimeError", "TimeoutError", "CancelledError", "KeyboardInterrupt", "OSError"} else "Exception")
                message = str(error)
                transient = (entry["phase"] == "secure_start" and isinstance(error, RuntimeError)
                             and transient_snapshot_failure(message))
                build_timeout = (entry["phase"] == "secure_start" and isinstance(error, TimeoutError)
                                 and retryable_build_timeout(entry))
                entry["code"] = ("debian_snapshot_unavailable" if transient else
                                 "build_timeout" if build_timeout else "preparation_failed")
                delay = 30 * 2 ** (number - 1)
                if (transient or build_timeout) and number < maximum_attempts and deadline - time.monotonic() > 90 + delay:
                    entry.update(retry=True, retry_delay_sec=delay)
                else:
                    status.update(status=entry["status"], error=entry["error"])
                    raise
            finally:
                status["teardown"] = entry["teardown"] = "pending"
                try:
                    retain()
                except BaseException:
                    status.update(status="infrastructure_error", phase="evidence_retention", error="Exception")
                    raise
                finally:
                    try:
                        if environment is not None:
                            await asyncio.wait_for(environment.stop(delete=True), timeout=60)
                            for check in (["docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=" + name],
                                          ["docker", "network", "ls", "-q", "--filter", "label=com.docker.compose.project=" + name]):
                                if subprocess.check_output(check, text=True, timeout=5).strip():
                                    raise RuntimeError("Package preparation left a resource")
                        status["teardown"] = entry["teardown"] = "complete"
                    except BaseException as error:
                        status.update(status="infrastructure_error", teardown="infrastructure_error", phase="teardown")
                        kind = type(error).__name__
                        status["error"] = kind if kind in {"RuntimeError", "TimeoutError", "CancelledError", "CalledProcessError", "TimeoutExpired"} else "Exception"
                        entry["teardown"] = "infrastructure_error"
                        raise
                    finally:
                        evidence = paths.trial_dir / "gh-initialization.jsonl"
                        if suite == "gh" and evidence.exists():
                            if evidence.stat().st_size > 4096:
                                raise RuntimeError("Preparation initialization evidence exceeds its bound")
                            entry["initialization"] = [json.loads(line) for line in evidence.read_text().splitlines()]
                        retain()
            if entry["retry"]:
                await asyncio.sleep(entry["retry_delay_sec"])
                continue
            status.update(status="prepared", phase="complete")
            if suite == "pester":
                status.update(powershell="7.6.9", pester="6.2.0")
            else:
                status["node"] = "20.19.2"
            break
    except BaseException as error:
        if status["status"] == "preparing":
            status["status"] = "infrastructure_error"
        if "error" not in status:
            kind = type(error).__name__
            status["error"] = kind if kind in {"RuntimeError", "ValueError", "TimeoutError", "OSError", "CancelledError", "KeyboardInterrupt"} else "Exception"
        raise
    finally:
        if old_manifest is None:
            os.environ.pop("AEB_GH_MANIFEST", None)
        else:
            os.environ["AEB_GH_MANIFEST"] = old_manifest
        retain()
    return status


def main(artifact, suite="pester", arm=None, shard=None, runtime="candidate"):
    artifact = Path(artifact); artifact.parent.mkdir(parents=True, exist_ok=True)
    if any(os.environ.get(key) for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "NVIDIA_API_KEY")):
        raise RuntimeError("Package preparation forbids provider credentials")
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    from qualify_evaluator_candidate import native_compose_config
    native_compose_config(Path(__file__).resolve().parents[2])
    with tempfile.TemporaryDirectory(prefix="evaluator-packages-", dir=os.environ.get("RUNNER_TEMP")) as temporary:
        root = Path(temporary)
        home = root / "empty-home"; home.mkdir(mode=0o700)
        original = dict(os.environ)
        clean = {key: original[key] for key in ("PATH", "TMPDIR", "RUNNER_TEMP", "DOCKER_CONFIG", "COMPOSE_PLUGIN_ROOT") if key in original}
        clean.update(HOME=str(home), PYTHONDONTWRITEBYTECODE="1", PYTHON_DOTENV_DISABLED="1",
                     SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE=str(root / "private/key"))
        try:
            os.environ.clear(); os.environ.update(clean)
            prepare_result = asyncio.run(prepare(root, artifact, suite, arm, shard, runtime))
        finally:
            os.environ.clear(); os.environ.update(original)
    if prepare_result["status"] != "prepared" or prepare_result["teardown"] != "complete":
        raise RuntimeError("Package preparation incomplete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime", choices=tuple(RUNTIMES), required=True)
    arguments = parser.parse_args()
    main(arguments.output, runtime=arguments.runtime)
