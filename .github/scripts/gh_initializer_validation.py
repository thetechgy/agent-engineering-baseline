#!/usr/bin/env python3
"""Credential-free native backend lifecycle and deterministic gh fixtures."""

import asyncio
import hashlib
import importlib.metadata
import json
import os
import re
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


STARTUP_FAULTS = {"gh-001": "dead_broker", "gh-002": "foreign_socket_owner", "gh-003": "missing_identity",
                  "gh-004": "changed_private_input", "gh-005": "timeout", "gh-006-changed-head": "cancellation",
                  "gh-007": "missing_manifest"}


def docker(*args, timeout=30):
    return subprocess.check_output(["docker", *args], text=True, timeout=timeout)


def select_tasks(tasks, arm, shard):
    expected = 24 if arm else 48
    if len(tasks) != expected:
        raise RuntimeError("Native gh cohort incomplete")
    if shard is not None:
        if arm not in ("with_skill", "without_skill") or shard not in (1, 2, 3):
            raise ValueError("Native gh shard requires one arm and a reviewed index")
        ordered = sorted(tasks, key=lambda task: task.name)
        if len({task.name for task in ordered}) != 24:
            raise RuntimeError("Native gh shard identities are not unique")
        return ordered[(shard - 1) * 8:shard * 8], 8
    return tasks, expected


async def qualify(root, artifact, arm=None, shard=None):
    bundle = gh_candidate.stage(gh.ROOT, root / "bundle/gh")
    tasks = []
    for present in (True, False):
        if arm is not None and arm != ("with_skill" if present else "without_skill"):
            continue
        tasks.extend(stage_native_harbor_tasks(bundle, root / "tasks" / str(present), with_skill=present,
            grading_mode="default_plus_custom", workspace_mode="group",
            workspace_skill_paths=[bundle.parent / gh.COMPETING]))
    tasks, expected = select_tasks(tasks, arm, shard)
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
        command_stages = {}
        environment_type = TrustedGhEnvironment
        if isinstance(environment_type, type) and importlib.metadata.version('skillevaluator') in ('0.8.0', '0.9.0'):
            from prepare_candidate_images import observed_environment
            environment_type = observed_environment(environment_type, command_stages)
        environment = environment_type(environment_dir=task / "environment", environment_name=name,
            session_id=name, trial_paths=paths, task_env_config=native.config.environment, mounts=[],
            network_policy=native.config.environment.resolve_baseline())
        environment.default_user = "agent"
        phase = "secure_start_and_initialization"
        failure = None
        setup_only = None
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
            skill_read_digest = None
            if present and entry.get("expected_skill"):
                skill_read = await observed("cat /workspace/skills/gh/SKILL.md")
                skill_read_digest = hashlib.sha256((skill_read.stdout or "").encode()).hexdigest()
                if skill_read.return_code or skill_read_digest != hashlib.sha256((gh.ROOT / gh.DEPLOYED / "SKILL.md").read_bytes()).hexdigest():
                    raise RuntimeError("Agent could not read the exact staged skill")
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
            phase = "negative_controls"
            # A fabricated receipt cannot be promoted by a complete-looking
            # trajectory or by otherwise correct deterministic output.
            forged = json.loads(json.dumps({"steps": steps}))
            forged["steps"][-1]["observation"]["results"][0]["content"] += "\nGH_FIXTURE_RECEIPT=" + "0" * 64
            trajectory.write_text(json.dumps(forged))
            await environment.upload_file(trajectory, "/logs/agent/trajectory.json")
            await checked("python3 -I /tests/grader.py")
            rejected = json.loads(await checked("cat /logs/verifier/reward.json"))
            if rejected["custom_metrics"]["gh_gate"] != 0 or rejected["custom_metrics"]["gh_evidence"] != 0:
                raise RuntimeError("Native grader accepted fabricated receipt")
            if audit != await checked("sha256sum /opt/gh-eval/state/audit.jsonl"):
                raise RuntimeError("Negative grading changed append-only audit")
            fault = STARTUP_FAULTS.get(task.name)
            fault_result = None
            if fault:
                if fault == "dead_broker":
                    await checked("kill -TERM " + str(first["broker"]["pid"]))
                elif fault == "foreign_socket_owner":
                    await checked("/usr/bin/chown agent /run/gh-eval/gh.sock")
                elif fault == "missing_identity":
                    await checked("/usr/bin/rm /opt/aeb-gh/broker.json")
                elif fault == "changed_private_input":
                    await checked("/usr/bin/printf ' ' >> /opt/gh-eval/state/case.json")
                elif fault == "timeout":
                    await checked("kill -STOP " + str(first["broker"]["pid"]))
                elif fault == "missing_manifest":
                    os.environ["AEB_GH_MANIFEST"] = str(root / "absent-manifest.json")
                prior_records = len(paths.trial_dir.joinpath("gh-initialization.jsonl").read_text().splitlines())
                blocked = False
                try:
                    if fault == "cancellation":
                        pending = asyncio.create_task(environment.start(force_build=False))
                        await asyncio.sleep(0)
                        pending.cancel()
                        await pending
                    else:
                        await environment.start(force_build=False)
                except asyncio.CancelledError:
                    if fault != "cancellation":
                        raise
                    blocked = True
                except (RuntimeError, ValueError, OSError):
                    if fault == "cancellation":
                        raise
                    blocked = True
                finally:
                    os.environ["AEB_GH_MANIFEST"] = str(manifest)
                if not blocked:
                    raise RuntimeError("Native initializer accepted invalid or cancelled startup")
                if fault == "timeout":
                    await checked("kill -CONT " + str(first["broker"]["pid"]))
                records = paths.trial_dir.joinpath("gh-initialization.jsonl").read_text().splitlines()
                status = json.loads(records[-1])
                expected_status = "cancelled" if fault == "cancellation" else "infrastructure_error"
                if len(records) != prior_records + 1 or status["status"] != expected_status:
                    raise RuntimeError("Native startup failure lost its exact infrastructure classification")
                if fault == "timeout" and status.get("failure") != {
                        "status": "infrastructure_error", "phase": "resume", "error": "TimeoutError"}:
                    raise RuntimeError("Native timeout control failed for a different reason")
                if fault == "cancellation":
                    # Containment may stop the main container. Recover through
                    # the hardened copy API; unavailable audit is not a pass.
                    retained_audit = root / "cancelled-audit.jsonl"
                    await environment.download_file("/opt/gh-eval/state/audit.jsonl", retained_audit)
                    if retained_audit.stat().st_size > 8 * 1024 * 1024 or hashlib.sha256(retained_audit.read_bytes()).hexdigest() != audit.split()[0]:
                        raise RuntimeError("Cancellation changed append-only audit")
                elif audit != await checked("sha256sum /opt/gh-eval/state/audit.jsonl"):
                    raise RuntimeError("Failed initialization changed append-only audit")
                fault_result = {"control": fault, "blocked": True, "measurement": "unscoreable", "audit": "unchanged", "initialization": status}
            rows.append({"case": task.name, "arm": "with_skill" if present else "without_skill",
                "checksum": native.checksum, "metrics": scores, "initialization": first,
                "evidence": "controlled native fixture before injected fault", "inference": False, "setup_only": setup_only,
                "fabricated_receipt_rejected": True, "startup_fault": fault_result, "skill_read_sha256": skill_read_digest})
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
            teardown = {"status": "pending"}
            def retain():
                artifact.write_text(json.dumps({"schema": 1, "inference": False, "diagnostic_only": True,
                    "success": len(rows) == expected and failure is None and teardown["status"] == "complete",
                    "teardown": teardown, "expected": expected, "completed": rows,
                    "selection": {"arm": arm, "shard": shard, "shards": 3 if shard else 1},
                    "runtime": {key: importlib.metadata.version(key) for key in ("skillevaluator", "harbor")},
                    "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    "producer_revision": subprocess.check_output(["git", "-C", str(gh.ROOT), "rev-parse", "HEAD"], text=True).strip(),
                    "workflow_run": os.environ.get("GITHUB_RUN_ID"), "workflow_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
                    "failure": failure, "setup_only": setup_only, "command_stages": command_stages,
                    "initialization": [json.loads(line) for line in paths.trial_dir.joinpath("gh-initialization.jsonl").read_text().splitlines()]
                        if paths.trial_dir.joinpath("gh-initialization.jsonl").exists() else []}, indent=2) + "\n")
            # Persist current infrastructure evidence before cleanup can hang or
            # be interrupted. Pending cleanup is never a successful verdict.
            try:
                retain()
            except BaseException:
                failure = failure or {"phase": "evidence_retention", "error": "Exception",
                    "code": "native_evidence_failed", "case": task.name,
                    "arm": "with_skill" if present else "without_skill"}
                raise
            finally:
                cleanup_phase = "stop"
                try:
                    await asyncio.wait_for(environment.stop(delete=True), timeout=60)
                    cleanup_phase = "containers"
                    if docker("ps", "-aq", "--filter", "label=com.docker.compose.project=" + name, timeout=5).strip():
                        raise RuntimeError("Native gh teardown left a container")
                    cleanup_phase = "networks"
                    if docker("network", "ls", "-q", "--filter", "label=com.docker.compose.project=" + name, timeout=5).strip():
                        raise RuntimeError("Native gh teardown left a network")
                    teardown = {"status": "complete"}
                except BaseException as cleanup_error:
                    kind = type(cleanup_error).__name__
                    if kind not in {"RuntimeError", "TimeoutError", "CancelledError", "KeyboardInterrupt", "OSError", "CalledProcessError", "TimeoutExpired"}:
                        kind = "Exception"
                    teardown = {"status": "infrastructure_error", "code": "native_teardown_failed",
                        "phase": cleanup_phase, "error": kind}
                    raise
                finally:
                    retain()
    return len(rows) == expected


def main(artifact, arm=None, shard=None):
    artifact = Path(artifact); artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps({"success": False, "inference": False, "diagnostic_only": True, "completed": []}) + "\n")
    if any(os.environ.get(key) for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "NVIDIA_API_KEY")):
        raise RuntimeError("Qualification forbids provider credentials")
    from aeb_gh_fixture.backend import require_runtime
    require_runtime()
    if importlib.metadata.version('skillevaluator') in ('0.8.0', '0.9.0'):
        from evaluator_profiles import runtime, candidate_versions, owning_candidate
        runtime(candidate_versions(owning_candidate()), owning=True)
    if docker("compose", "version", "--short").strip() != gh.reports.POLICY["docker_compose"]:
        raise RuntimeError("Incorrect Compose runtime")
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    with tempfile.TemporaryDirectory(prefix="gh-native-", dir=os.environ.get("RUNNER_TEMP")) as temporary:
        if not asyncio.run(qualify(Path(temporary), artifact, arm, shard)):
            raise RuntimeError("Native gh qualification incomplete")



def startup_observer(base, observations):
    """Retain only the fixed initializer's bounded, redacted result; delegate unchanged."""
    from aeb_gh_fixture.backend import COMMAND, VERIFY_COMMAND
    from skillevaluator.utils.redaction import redact_sensitive_text
    import re
    def clean(value):
        text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', value or '')
        text = re.sub(r'[\x00-\x08\x0b-\x1f\x7f]', '', text)
        return redact_sensitive_text(text[-4096:])
    class Observed(base):
        async def exec(self, command, *args, **kwargs):
            if command not in (COMMAND, VERIFY_COMMAND):
                return await super().exec(command, *args, **kwargs)
            row = {'operation': 'verify' if command == VERIFY_COMMAND else 'initialize', 'status': 'running'}
            observations.append(row)
            try:
                result = await super().exec(command, *args, **kwargs)
                row.update(status='complete', returncode=result.return_code,
                    stdout=clean(result.stdout), stderr=clean(result.stderr),
                    stdout_truncated=len(result.stdout or '') > 4096,
                    stderr_truncated=len(result.stderr or '') > 4096)
                return result
            except BaseException as error:
                row.update(status='failed', error=type(error).__name__)
                raise
    return Observed


async def startup_attempt(environment, *, inspect_image, cleanup_check, retain, diagnose=None):
    """No agent setup, command fixture, grader or reset; keep the primary exception."""
    row = {'status': 'starting', 'cleanup': 'pending'}
    primary = None; cleanup_error = None; evidence_error = None
    def save():
        nonlocal evidence_error
        try: retain(row)
        except BaseException as error:
            evidence_error = evidence_error or error
            row.update(status='failed', evidence_error=type(error).__name__)
    try:
        await environment.start(False)
        row['image'] = inspect_image()
        first = environment.trial_paths.trial_dir / 'gh-initialization.jsonl'
        initial = json.loads(first.read_text().splitlines()[-1])
        row['initialization'] = initial
        await environment.start(False)
        repeated = json.loads(first.read_text().splitlines()[-1])
        if initial != repeated or initial.get('status') != 'ready':
            raise RuntimeError('Repeated startup identity drift')
        row.update(status='passed', repeated_identity_equal=True)
        if diagnose is not None: row['spawn_diagnostic'] = await diagnose()
    except BaseException as error:
        primary = error
        row.update(status='failed', primary_error=type(error).__name__)
    finally:
        save()
        try:
            await asyncio.wait_for(environment.stop(delete=True), timeout=60)
            cleanup_check()
            row['cleanup'] = 'complete'
        except BaseException as error:
            cleanup_error = error
            row.update(cleanup='failed', cleanup_error=type(error).__name__)
        finally:
            save()
    if primary is not None: raise primary
    if cleanup_error is not None: raise cleanup_error
    if evidence_error is not None: raise evidence_error
    return row


def startup_only(artifact, baseline):
    """Four clean gh-007 startups, base/head and present/absent, under the held owner."""
    from evaluator_profiles import NEXT, runtime, candidate_versions
    from skillevaluator.tier3.harbor.adapter import _task_environment_context_hash
    root_source = gh.ROOT
    baseline = Path(baseline).absolute(); artifact = Path(artifact).absolute()
    if (baseline.resolve() != baseline or artifact.resolve() != artifact
            or artifact.is_relative_to(root_source) or artifact.is_relative_to(baseline)):
        raise ValueError('Use real checkouts and external diagnostic output')
    if any(os.environ.get(k) for k in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','NVIDIA_API_KEY','COPILOT_GITHUB_TOKEN')):
        raise RuntimeError('Startup qualification forbids provider credentials')
    runtime(candidate_versions(NEXT), owning=True)
    revision = lambda source: subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
    if revision(baseline) != '82cdde086fe4d7fad84f21acc614df2adeca1767':
        raise ValueError('Unreviewed startup baseline')
    # These producers and pins must match before head-owned staging reads base data.
    unchanged = ('.github/scripts/gh_candidate.py', '.github/scripts/gh_evaluations.py',
        '.github/evals/evaluator-0.9.json', '.github/evals/codex-execution-090.json')
    if any((root_source/p).read_bytes() != (baseline/p).read_bytes() for p in unchanged):
        raise ValueError('Unmatched startup producers or pins')
    matched_tags = []
    status = {'schema':1, 'inference':False, 'agent_setup':False, 'grading':False,
        'complete':False, 'revision':revision(root_source), 'baseline':revision(baseline),
        'versions':candidate_versions(NEXT), 'attempts':[]}
    artifact.parent.mkdir(parents=True,exist_ok=True)
    def save(): artifact.write_text(json.dumps(status,indent=2)+'\n')
    save()
    with tempfile.TemporaryDirectory(prefix='gh-startup-',dir=os.environ.get('RUNNER_TEMP')) as scratch:
        root = Path(scratch); prior = os.environ.get('AEB_GH_MANIFEST')
        try:
            for label, source in (('base',baseline),('head',root_source)):
                staged = root/label; staged.mkdir()
                bundle = gh_candidate.stage(source,staged/'bundle/gh',['gh-007'],fixture=True)
                for present in (True,False):
                    arm = 'with_skill' if present else 'without_skill'
                    task, = stage_native_harbor_tasks(bundle,staged/'tasks'/arm,with_skill=present,
                        grading_mode='custom_only',workspace_mode='group',
                        workspace_skill_paths=[bundle.parent/gh.COMPETING])
                    native = Task(task)
                    context = _task_environment_context_hash(task/'environment')
                    matched = next((r for r in status['attempts'] if r['arm']==arm),None)
                    if matched and matched['context'] != context: raise RuntimeError('Startup image inputs drifted')
                    manifest = write_manifest(staged/('operator-'+arm),[task],staged_roots=[staged/'tasks',staged/'bundle'])
                    os.environ['AEB_GH_MANIFEST'] = str(manifest)
                    paths = TrialPaths(staged/('trial-'+arm)); paths.mkdir()
                    name = 'aeb-startup-'+uuid.uuid4().hex[:16]
                    row = {'source':label,'case':'gh-007','arm':arm,'context':context,'task_checksum':native.checksum,'commands':[]}
                    status['attempts'].append(row); save()
                    # Build once per arm, then use that exact local immutable image for head.
                    # The context and source/pin checks above bind this supported prebuilt selector.
                    config = native.config.environment
                    if matched:
                        image_id = matched['image']['image']
                        if not re.fullmatch(r'sha256:[0-9a-f]{64}',image_id):
                            raise RuntimeError('Invalid matched image identity')
                        tag = matched['image']['local_tag']
                        if docker('image','inspect','--format','{{.Id}}',tag).strip()!=image_id:
                            raise RuntimeError('Matched local image was replaced')
                        config = config.model_copy(update={'docker_image':tag})
                        row['matched_prebuilt_image'] = image_id
                    environment = startup_observer(TrustedGhEnvironment,row['commands'])(environment_dir=task/'environment',
                        environment_name=name,session_id=name,trial_paths=paths,task_env_config=config,
                        mounts=[],network_policy=native.config.environment.resolve_baseline())
                    environment.default_user = 'agent'
                    def image():
                        ids=docker('ps','-aq','--filter','label=com.docker.compose.project='+name).split()
                        if len(ids)!=1: raise RuntimeError('Unexpected startup container population')
                        observed=json.loads(docker('inspect','--format','{"image":{{json .Image}},"oom":{{json .State.OOMKilled}},"exit":{{json .State.ExitCode}}}',ids[0]))
                        row['image'] = observed; save()
                        if matched and observed['image'] != matched['image']['image']: raise RuntimeError('Matched startup image drift')
                        if not matched:
                            tag = 'aeb-startup-match:'+uuid.uuid4().hex
                            docker('image','tag',observed['image'],tag)
                            matched_tags.append(tag); observed['local_tag'] = tag
                        return observed
                    def clean():
                        for args in (('ps','-aq'),('network','ls','-q')):
                            if docker(*args,'--filter','label=com.docker.compose.project='+name).strip():
                                raise RuntimeError('Startup resources survived cleanup')
                    def retain(value):
                        row.update(value)
                        path=paths.trial_dir/'gh-initialization.jsonl'
                        if path.exists(): row['initialization_records']=[json.loads(line) for line in path.read_text().splitlines()]
                        save()
                    async def diagnose():
                        probe = gh.ROOT/'.github/scripts/gh_spawn_identity_probe.py'
                        row['diagnostic_script_sha256'] = hashlib.sha256(probe.read_bytes()).hexdigest()
                        await environment.upload_file(probe,'/opt/aeb-gh/spawn-diagnostic.py')
                        result = await environment.exec('/usr/local/bin/python3 -I /opt/aeb-gh/spawn-diagnostic.py',user='root',timeout_sec=30)
                        if len(result.stdout or '')>65536: raise RuntimeError('Oversized spawn diagnostic')
                        diagnostic = json.loads(result.stdout)
                        row['spawn_diagnostic'] = diagnostic
                        row['spawn_diagnostic_returncode'] = result.return_code
                        save()
                        if result.return_code or diagnostic.get('status')!='complete':
                            raise RuntimeError('Spawn diagnostic failed')
                        return diagnostic
                    asyncio.run(startup_attempt(environment,inspect_image=image,cleanup_check=clean,retain=retain,
                        diagnose=diagnose if label=='base' and not present else None))
            status['complete'] = True; save()
        finally:
            if prior is None: os.environ.pop('AEB_GH_MANIFEST',None)
            else: os.environ['AEB_GH_MANIFEST']=prior
            pending_error = __import__('sys').exc_info()[1]
            tag_error = None
            for tag in matched_tags:
                try: docker('image','rm',tag)
                except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as error:
                    tag_error = tag_error or error
                    status['image_tag_cleanup']='failed'; status['complete']=False; save()
            if status.get('image_tag_cleanup')!='failed':
                status['image_tag_cleanup']='complete'; save()
            if tag_error is not None and pending_error is None: raise tag_error


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 4 and sys.argv[2] == "--startup-only":
        startup_only(sys.argv[1], sys.argv[3])
    else:
        main(sys.argv[1])
