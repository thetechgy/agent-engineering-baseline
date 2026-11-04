"""Operator package preparation; no agent setup, grading or model execution."""

import asyncio
import hashlib
import importlib.metadata
import json
import os
import re
from pathlib import Path
import signal
import subprocess
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


GH_RUNTIME_COMMAND = "/usr/bin/node --version"


def staged_task(root, suite="pester", arm=None, shard=None):
    if suite == "gh":
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
    bundle, fixtures = pilot.qualification_bundle(root, candidate=True)
    tasks = stage_native_harbor_tasks(bundle, root / "tasks", with_skill=True, grading_mode="custom_only")
    if len(tasks) != 26 or len(fixtures) != 26:
        raise RuntimeError("Incomplete package preparation source cohort")
    return next(task for task in tasks if task.name == "pester-001-classic")


def transient_snapshot_failure(message):
    # Require the observed fatal APT fetch failure, rather than an earlier
    # warning followed by an integrity/signature failure elsewhere in build.
    integrity = ("digest mismatch", "hash sum mismatch", "gpg error", "not signed",
                 "signature", "certificate verification")
    return ("Docker compose command failed" in message and "exit code: 100" in message
            and not any(value in message.lower() for value in integrity)
            and any("Failed to fetch" in line and "snapshot.debian.org" in line
                    and re.search(r"\b(?:503|504)\b", line) for line in message.splitlines()))


async def prepare(root, artifact, suite="pester", arm=None, shard=None):
    status = {"schema": 1, "status": "preparing", "diagnostic_only": True, "inference": False,
              "phase": "stage", "suite": suite, "arm": arm, "shard": shard,
              "qualification_context": "cache_prepared", "attempts": [],
              "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    old_manifest = os.environ.get("AEB_GH_MANIFEST")
    def retain():
        artifact.write_text(json.dumps(status, indent=2) + "\n")
    try:
        versions = {key: importlib.metadata.version(key) for key in ("skillevaluator", "harbor")}
        status["runtime"] = versions
        if versions != {"skillevaluator": "0.7.2", "harbor": "0.24.0"}:
            raise RuntimeError("Unqualified package preparation runtime")
        task = staged_task(root, suite, arm, shard)
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
        for number in range(1, 4):
            paths = TrialPaths(root / ("trial-" + str(number))); paths.mkdir()
            name = "aeb-image-packages-" + uuid.uuid4().hex[:16]
            entry = {"attempt": number, "status": "preparing", "phase": "secure_start", "retry": False}
            status["attempts"].append(entry)
            environment = None
            try:
                environment = environment_type(environment_dir=task / "environment", environment_name=name,
                    session_id=name, trial_paths=paths, task_env_config=native.config.environment, mounts=[],
                    network_policy=native.config.environment.resolve_baseline())
                environment.default_user = "agent"
                remaining = deadline - time.monotonic() - 90
                if remaining <= 0:
                    raise TimeoutError("Preparation budget exhausted")
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
                entry["code"] = "debian_snapshot_unavailable" if transient else "preparation_failed"
                if transient and number < 3 and deadline - time.monotonic() > 95:
                    entry["retry"] = True
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
                await asyncio.sleep(5)
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


def main(artifact, suite="pester", arm=None, shard=None):
    artifact = Path(artifact); artifact.parent.mkdir(parents=True, exist_ok=True)
    if any(os.environ.get(key) for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "NVIDIA_API_KEY")):
        raise RuntimeError("Package preparation forbids provider credentials")
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    with tempfile.TemporaryDirectory(prefix="pester-packages-", dir=os.environ.get("RUNNER_TEMP")) as temporary:
        prepare_result = asyncio.run(prepare(Path(temporary), artifact, suite, arm, shard))
    if prepare_result["status"] != "prepared" or prepare_result["teardown"] != "complete":
        raise RuntimeError("Package preparation incomplete")
