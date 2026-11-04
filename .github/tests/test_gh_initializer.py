"""No inference: native staging, approval, startup ordering and failure admission."""

import asyncio
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".github/scripts"))


@unittest.skipUnless(os.environ.get("CANDIDATE_EVIDENCE_CHILD") == "1", "candidate owning lock only")
class InitializerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import gh_evaluations as gh
        from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks
        cls.temporary = tempfile.TemporaryDirectory(prefix="trusted-gh-controls-")
        cls.root = Path(cls.temporary.name)
        import gh_candidate
        cls.bundle = gh_candidate.stage(ROOT, cls.root / "bundle/gh")
        cls.tasks = []
        for present in (True, False):
            cls.tasks.extend(stage_native_harbor_tasks(cls.bundle, cls.root / str(present), with_skill=present,
                grading_mode="default_plus_custom", workspace_mode="group",
                workspace_skill_paths=[cls.bundle.parent / gh.COMPETING]))

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        from aeb_gh_fixture import manifest
        self.manifest = manifest
        self.scratch = tempfile.TemporaryDirectory(prefix="gh-approval-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.path = manifest.write_manifest(self.root / "operator", self.tasks, staged_roots=[self.bundle, *self.tasks])

    def test_failed_start_retains_evidence_even_when_teardown_fails(self):
        import gh_initializer_validation as native
        for fault in ("none", "teardown", "teardown-timeout", "evidence"):
            with self.subTest(fault=fault):
                teardown_fails = fault.startswith("teardown")
                root = self.root / fault
                root.mkdir()
                artifact = root / "native-gh.json"
                original_write = Path.write_text
                writes = []
                def write(path, text, *args, **kwargs):
                    if path == artifact:
                        writes.append(path)
                        if fault == "evidence" and len(writes) == 1:
                            raise OSError("evidence write failed")
                    return original_write(path, text, *args, **kwargs)
                async def cleanup(*, delete):
                    self.assertTrue(delete)
                    if fault == "evidence":
                        self.assertFalse(artifact.exists())
                    else:
                        pending = json.loads(artifact.read_text())
                        self.assertFalse(pending["success"])
                        self.assertEqual(pending["teardown"]["status"], "pending")
                    if fault == "teardown-timeout":
                        raise subprocess.TimeoutExpired(["docker", "ps"], 5)
                    if teardown_fails:
                        raise RuntimeError("cleanup failed")
                environment = SimpleNamespace(
                    start=AsyncMock(side_effect=RuntimeError("secure startup failed")),
                    stop=AsyncMock(side_effect=cleanup))
                with patch.object(native, "TrustedGhEnvironment", return_value=environment), \
                        patch.object(native, "docker", return_value=""), \
                        patch.object(Path, "write_text", write), patch.dict(os.environ):
                    with self.assertRaises((RuntimeError, OSError, subprocess.TimeoutExpired)):
                        asyncio.run(native.qualify(root, artifact))
                retained = json.loads(artifact.read_text())
                self.assertFalse(retained["success"])
                self.assertEqual(retained["completed"], [])
                self.assertEqual(retained["failure"]["phase"], "secure_start_and_initialization")
                self.assertEqual(retained["teardown"]["status"],
                    "infrastructure_error" if teardown_fails else "complete")
                if teardown_fails:
                    self.assertEqual(retained["teardown"]["error"],
                        "TimeoutExpired" if fault == "teardown-timeout" else "RuntimeError")
                environment.stop.assert_awaited_once_with(delete=True)

    def test_fixed_native_shards_cover_all_24_cases_once_per_arm(self):
        from gh_initializer_validation import select_tasks
        for arm, tasks in (("with_skill", self.tasks[:24]), ("without_skill", self.tasks[24:])):
            selected = []
            for shard in (1, 2, 3):
                cases, expected = select_tasks(tasks, arm, shard)
                self.assertEqual(expected, 8)
                self.assertEqual(len(cases), 8)
                selected.extend(case.name for case in cases)
            self.assertEqual(len(selected), len(set(selected)))
            self.assertEqual(set(selected), {task.name for task in tasks})
            with self.assertRaises(RuntimeError): select_tasks(tasks[:-1], arm, 1)
        with self.assertRaises(ValueError): select_tasks(self.tasks, None, 1)

    def test_pester_package_preparation_uses_fixed_probe_without_agent_setup(self):
        import prepare_candidate_images as preparation
        task = preparation.staged_task(self.root / "source")
        root = self.root / "prepare"; root.mkdir()
        artifact = root / "preparation.json"
        environment = SimpleNamespace(start=AsyncMock(), stop=AsyncMock(), setup=AsyncMock(),
            exec=AsyncMock(return_value=SimpleNamespace(return_code=0, stdout="7.6.9\n6.2.0\n")))
        with patch.object(preparation, "staged_task", return_value=task), \
                patch.object(preparation, "SkillEvaluatorSecureDockerEnvironment", return_value=environment), \
                patch.object(preparation.subprocess, "check_output", return_value=""):
            observed = asyncio.run(preparation.prepare(root, artifact))
        self.assertEqual(observed["status"], "prepared")
        self.assertEqual(observed["qualification_context"], "cache_prepared")
        self.assertEqual(observed["teardown"], "complete")
        self.assertFalse(observed["inference"])
        environment.start.assert_awaited_once_with(force_build=True)
        environment.exec.assert_awaited_once_with(preparation.RUNTIME_COMMAND, user="root", timeout_sec=20)
        environment.stop.assert_awaited_once_with(delete=True)
        environment.setup.assert_not_awaited()

    def test_pester_package_preparation_failures_remain_infrastructure(self):
        import prepare_candidate_images as preparation
        task = preparation.staged_task(self.root / "source")
        for fault in ("startup", "timeout", "cancel", "version", "teardown"):
            with self.subTest(fault=fault):
                root = self.root / fault; root.mkdir()
                artifact = root / "preparation.json"
                error = {"startup": RuntimeError(), "timeout": TimeoutError(), "cancel": asyncio.CancelledError()}.get(fault)
                environment = SimpleNamespace(start=AsyncMock(side_effect=error), setup=AsyncMock(),
                    stop=AsyncMock(side_effect=RuntimeError() if fault == "teardown" else None),
                    exec=AsyncMock(return_value=SimpleNamespace(return_code=0,
                        stdout="7.6.9\n6.1.0\n" if fault == "version" else "7.6.9\n6.2.0\n")))
                with patch.object(preparation, "staged_task", return_value=task), \
                        patch.object(preparation, "SkillEvaluatorSecureDockerEnvironment", return_value=environment), \
                        patch.object(preparation.subprocess, "check_output", return_value=""):
                    with self.assertRaises((RuntimeError, TimeoutError, asyncio.CancelledError)):
                        asyncio.run(preparation.prepare(root, artifact))
                retained = json.loads(artifact.read_text())
                self.assertEqual(retained["status"], "cancelled" if fault == "cancel" else "infrastructure_error")
                self.assertNotIn("metrics", retained)
                environment.stop.assert_awaited_once_with(delete=True)
                environment.setup.assert_not_awaited()

    def test_package_preparation_retries_transient_build_in_new_environment(self):
        import prepare_candidate_images as preparation
        task = preparation.staged_task(self.root / "source")
        root = self.root / "prepare"; root.mkdir()
        transient = ("Docker compose command failed: E: Failed to fetch https://snapshot.debian.org/pkg "
                     "TooManyRequests 503 No healthy backends\napt-get failed: exit code: 100")
        self.assertTrue(preparation.transient_snapshot_failure(transient))
        for detail in ("Fixture input digest mismatch", "Hash Sum mismatch", "GPG error", "signature invalid",
                       "certificate verification failed"):
            self.assertFalse(preparation.transient_snapshot_failure(transient + "\n" + detail))
        self.assertFalse(preparation.transient_snapshot_failure("snapshot.debian.org warning 503; exit code: 1"))
        failed = SimpleNamespace(start=AsyncMock(side_effect=RuntimeError(transient)), stop=AsyncMock(), setup=AsyncMock())
        ready = SimpleNamespace(start=AsyncMock(), stop=AsyncMock(), setup=AsyncMock(),
            exec=AsyncMock(return_value=SimpleNamespace(return_code=0, stdout="7.6.9\n6.2.0\n")))
        with patch.object(preparation, "staged_task", return_value=task), \
                patch.object(preparation, "SkillEvaluatorSecureDockerEnvironment", side_effect=[failed, ready]) as create, \
                patch.object(preparation.subprocess, "check_output", return_value=""), \
                patch.object(preparation.asyncio, "sleep", new_callable=AsyncMock):
            observed = asyncio.run(preparation.prepare(root, root / "preparation.json"))
        self.assertEqual(create.call_count, 2)
        self.assertEqual(observed["status"], "prepared")
        self.assertEqual(len(observed["attempts"]), 2)
        self.assertEqual(observed["attempts"][0]["code"], "debian_snapshot_unavailable")
        self.assertEqual(observed["attempts"][0]["teardown"], "complete")
        self.assertTrue(observed["attempts"][0]["retry"])
        for environment in (failed, ready):
            environment.start.assert_awaited_once_with(force_build=True)
            environment.stop.assert_awaited_once_with(delete=True)
            environment.setup.assert_not_awaited()

    def test_gh_package_preparation_retains_operator_manifest_and_backend(self):
        import prepare_candidate_images as preparation
        import aeb_gh_fixture.backend as backend
        root = self.root / "prepare"; root.mkdir()
        original_manifest = os.environ.get("AEB_GH_MANIFEST")
        async def approved_start(*, force_build):
            row, _ = self.manifest.approve(os.environ["AEB_GH_MANIFEST"], self.tasks[0])
            self.assertEqual(row["case"], "gh-001")
            self.assertTrue(force_build)
        environment = SimpleNamespace(start=AsyncMock(side_effect=approved_start), stop=AsyncMock(), setup=AsyncMock(),
            exec=AsyncMock(return_value=SimpleNamespace(return_code=0, stdout="v20.19.2\n")))
        with patch.object(preparation, "staged_task", return_value=self.tasks[0]), \
                patch.object(backend, "TrustedGhEnvironment", return_value=environment), \
                patch.object(preparation.subprocess, "check_output", return_value=""):
            observed = asyncio.run(preparation.prepare(root, root / "preparation.json", "gh", "with_skill", 1))
        self.assertEqual(observed["status"], "prepared")
        self.assertEqual(observed["node"], "20.19.2")
        self.assertEqual(os.environ.get("AEB_GH_MANIFEST"), original_manifest)
        environment.exec.assert_awaited_once_with(preparation.GH_RUNTIME_COMMAND, user="root", timeout_sec=20)
        environment.setup.assert_not_awaited()

    def test_existing_authored_healthcheck_still_rejects_baseline(self):
        import gh_evaluations as gh
        from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks
        bundle = gh.stage(ROOT, self.root / "old/gh", ["gh-002"])
        with self.assertRaisesRegex(ValueError, "healthcheck"):
            stage_native_harbor_tasks(bundle, self.root / "rejected", with_skill=False, grading_mode="default_plus_custom")

    def test_all_24_cases_both_arms_bind_native_checksums_and_initializer(self):
        self.assertEqual(len(self.tasks), 48)
        identities = []
        for task in self.tasks:
            row, digest = self.manifest.approve(self.path, task)
            identities.append((row["case"], row["arm"]))
            self.assertEqual(len(digest), 64)
            self.assertNotIn("healthcheck", (task / "task.toml").read_text())
            dockerfile = (task / "environment/Dockerfile").read_text()
            self.assertIn("ENTRYPOINT []", dockerfile)
            self.assertIn("HEALTHCHECK NONE", dockerfile)
        self.assertEqual(len(set(identities)), 48)

    def test_native_restaging_preserves_approved_content_identity(self):
        import gh_evaluations as gh
        from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks
        restaged = stage_native_harbor_tasks(self.bundle, self.root / "native-restaged", with_skill=True,
            grading_mode="default_plus_custom", workspace_mode="group",
            workspace_skill_paths=[self.bundle.parent / gh.COMPETING])
        self.assertEqual(len(restaged), 24)
        for task in restaged:
            self.manifest.approve(self.path, task)

    def test_missing_corrupt_altered_linked_and_hardlinked_manifests_reject(self):
        with self.assertRaises((ValueError, OSError)):
            self.manifest.approve(self.path.with_name("absent.json"), self.tasks[0])
        original = self.path.read_bytes()
        for raw in (b"{", original + b" ", original.replace(b'"schema":1', b'"schema":2')):
            self.path.write_bytes(raw)
            with self.assertRaises(ValueError):
                self.manifest.approve(self.path, self.tasks[0])
        self.path.write_bytes(original)
        linked = self.root / "linked.json"; linked.symlink_to(self.path)
        with self.assertRaises(ValueError): self.manifest.approve(linked, self.tasks[0])
        os.link(self.path, self.root / "hard.json")
        with self.assertRaises(ValueError): self.manifest.approve(self.path, self.tasks[0])

    def test_changed_payload_arm_checksum_context_and_task_links_reject(self):
        import aeb_gh_fixture.manifest as manifest
        with patch.object(manifest, "payload_digest", return_value="0" * 64):
            with self.assertRaises(ValueError): manifest.approve(self.path, self.tasks[0])
        copied = self.root / "copy" / self.tasks[0].name; shutil.copytree(self.tasks[0], copied)
        # Native CLI restaging may choose a different private host directory.
        self.assertEqual(manifest.approve(self.path, copied)[0], manifest.approve(self.path, self.tasks[0])[0])
        path = manifest.write_manifest(self.root / "copy-approval", [copied], staged_roots=[copied])
        entry = copied / "tests/entry.json"; original = entry.read_bytes()
        data = json.loads(original); data["has_skill"] = not data["has_skill"]
        entry.write_text(json.dumps(data))
        with self.assertRaises(ValueError): manifest.approve(path, copied)
        entry.write_bytes(original)
        context = copied / "environment/Dockerfile"; raw = context.read_bytes()
        context.write_bytes(raw + b"\n# changed\n")
        with self.assertRaises(ValueError): manifest.approve(path, copied)
        context.write_bytes(raw)
        entry.unlink(); entry.symlink_to(self.tasks[0] / "tests/entry.json")
        with self.assertRaises(ValueError): manifest.approve(path, copied)
        with self.assertRaises(ValueError): manifest.approve(self.path, copied)

    def test_manifest_is_operator_owned_outside_tasks(self):
        with self.assertRaises(ValueError):
            self.manifest.write_manifest(self.tasks[0] / "operator", self.tasks, staged_roots=self.tasks)
        self.path.chmod(0o644)
        with self.assertRaises(ValueError): self.manifest.approve(self.path, self.tasks[0])

    def test_plugin_real_dispatch_pins_codex_and_denies_task_configuration(self):
        from aeb_gh_fixture import backend_spec
        from skillevaluator.tier3.harbor.runner import build_harbor_run_command
        from skillevaluator.tier3_environments import load_custom_backend
        spec = load_custom_backend("aeb-gh-fixture")
        self.assertEqual(spec, backend_spec())
        self.assertEqual(spec.environment_kwargs, frozenset())
        self.assertEqual(spec.host_env_vars, frozenset({"AEB_GH_MANIFEST"}))
        command = build_harbor_run_command(dataset_path=self.tasks[0].parent, agent="codex", job_name="fixture",
            env_mode="aeb-gh-fixture")
        self.assertIn("aeb_gh_fixture.backend:TrustedGhEnvironment", command)
        self.assertIn('version="0.155.1"', command)
        self.assertNotIn('version="0.161.0"', command)
        from skillevaluator.tier3.harbor.runner import _resolve_runtime_env
        values, errors = _resolve_runtime_env({"AEB_GH_MANIFEST": "/agent/manifest"}, env_mode="aeb-gh-fixture")
        self.assertEqual(values, {})
        self.assertTrue(errors)
        for key in ("manifest", "command", "executable", "initializer"):
            with self.assertRaises(ValueError):
                build_harbor_run_command(dataset_path=self.tasks[0].parent, agent="codex", job_name="fixture",
                    env_mode="aeb-gh-fixture", environment_kwargs={key: "agent-supplied"})

    def test_real_cli_selects_plugin_and_rejects_missing_credentials(self):
        import subprocess
        import skillevaluator
        with tempfile.TemporaryDirectory() as home:
            launcher = (
                "import sys; sys.path.insert(0, sys.argv.pop(1)); "
                "sys.argv[0]='skillevaluator'; "
                "from skillevaluator.cli import cli; cli()"
            )
            env = {"PATH": os.environ["PATH"], "HOME": home, "COLUMNS": "300",
                   "PYTHON_DOTENV_DISABLED": "1", "SKILL_EVAL_LLM_PROVIDER": "openai",
                   "PYTHONDONTWRITEBYTECODE": "1"}
            arguments = [sys.executable, "-I", "-B", "-c", launcher,
                         str(Path(skillevaluator.__file__).resolve().parents[1])]
            help_result = subprocess.run([*arguments, "tier3", "--help"], env=env,
                capture_output=True, text=True, timeout=30)
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            self.assertIn("aeb-gh-fixture", "".join(help_result.stdout.split()))
            result = subprocess.run([*arguments, "tier3", "doctor", "--agents", "codex",
                "--env-mode", "aeb-gh-fixture"], env=env, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("OPENAI_API_KEY", result.stdout + result.stderr)

    def test_start_awaits_secure_start_and_records_failures_without_agent_setup(self):
        from aeb_gh_fixture.backend import TrustedGhEnvironment, COMMAND, VERIFY_COMMAND
        from skillevaluator.tier3.harbor.secure_docker_environment import SkillEvaluatorSecureDockerEnvironment as Base
        async def exercise(fault):
            task = self.tasks[0]
            trial = self.root / fault; trial.mkdir()
            environment = object.__new__(TrustedGhEnvironment)
            environment.environment_dir = task / "environment"
            environment.trial_paths = SimpleNamespace(trial_dir=trial)
            order = []
            async def secure_start(*args, **kwargs):
                order.append("secure")
                if fault == "secure-failure": raise RuntimeError("startup failed")
            async def execute(_self, command, **kwargs):
                self.assertEqual(order[0], "secure")
                self.assertEqual(kwargs["user"], "root")
                order.append(command)
                if command in (COMMAND, VERIFY_COMMAND):
                    if fault == "cancel": raise asyncio.CancelledError()
                    if fault == "timeout": raise TimeoutError()
                    if fault == "failed": return SimpleNamespace(return_code=1, stdout="")
                    return SimpleNamespace(return_code=0, stdout=json.dumps({"status": "ready", "uid": 0,
                        "pid": 123, "start": "99", "socket_inode": 7}))
                return SimpleNamespace(return_code=0, stdout="")
            with patch.dict(os.environ, {"AEB_GH_MANIFEST": str(self.path)}), \
                    patch.object(Base, "start", secure_start), \
                    patch.object(TrustedGhEnvironment, "exec", execute), \
                    patch.object(TrustedGhEnvironment, "upload_file", AsyncMock()):
                if fault == "success":
                    await environment.start(force_build=True)
                    await environment.start(force_build=False)
                    self.assertEqual(order.count("secure"), 1)
                    self.assertEqual(order[-1], VERIFY_COMMAND)
                else:
                    with self.assertRaises(BaseException): await environment.start(force_build=True)
            records = [json.loads(line) for line in (trial / "gh-initialization.jsonl").read_text().splitlines()]
            self.assertEqual(records[-1]["status"], "ready" if fault == "success" else "cancelled" if fault == "cancel" else "infrastructure_error")
            self.assertEqual(len(records), 2 if fault == "success" else 1)
        for fault in ("success", "secure-failure", "failed", "cancel", "timeout"):
            asyncio.run(exercise(fault))

    def test_repeat_verification_never_rebuilds_or_creates_a_new_broker(self):
        from aeb_gh_fixture.backend import TrustedGhEnvironment
        from skillevaluator.tier3.harbor.secure_docker_environment import SkillEvaluatorSecureDockerEnvironment as Base
        for failed, force in ((False, True), (True, False)):
            trial = self.root / ("failed" if failed else "rebuild"); trial.mkdir()
            environment = object.__new__(TrustedGhEnvironment)
            environment.environment_dir = self.tasks[0] / "environment"
            environment.trial_paths = SimpleNamespace(trial_dir=trial)
            environment._aeb_ready = not failed
            environment._aeb_failed = failed
            with patch.dict(os.environ, {"AEB_GH_MANIFEST": str(self.path)}), \
                    patch.object(Base, "start", AsyncMock()) as secure_start:
                with self.assertRaises(RuntimeError): asyncio.run(environment.start(force_build=force))
                secure_start.assert_not_awaited()
        from aeb_gh_fixture import initialize
        import hashlib
        control = self.root / "private-control"; control.mkdir()
        state = self.root / "private-state"; state.mkdir()
        names = ("case.json", "fixture.py", "setup.py", "client.py")
        for name in names: (state / name).write_bytes(b"controlled fixture")
        (state / "audit.jsonl").write_bytes(b"retained audit\n")
        (control / "approved.json").write_text(json.dumps({name: hashlib.sha256((state / name).read_bytes()).hexdigest() for name in names}))
        with patch.multiple(initialize, STATE=state, CONTROL=control, SOCKET=self.root / "absent/gh.sock"), \
                patch.object(initialize, "private", return_value=SimpleNamespace(st_size=1)), \
                patch.object(initialize.os, "geteuid", return_value=0), \
                patch.object(sys, "argv", ["initialize", "--verify"]), \
                patch.object(initialize.subprocess, "Popen") as spawn:
            with self.assertRaises(RuntimeError): initialize.initialize()
            spawn.assert_not_called()
        self.assertEqual((state / "audit.jsonl").read_bytes(), b"retained audit\n")

    def test_candidate_grader_loads_standalone_verifier_without_installed_runtime(self):
        import subprocess
        task = self.tasks[0]
        trajectory = self.root / "trajectory.json"; trajectory.write_text('{"steps": []}')
        script = """
import runpy, sys
class NoRuntime:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'skillevaluator' or fullname.startswith('skillevaluator.'):
            raise ModuleNotFoundError('Installed runtime forbidden')
sys.meta_path.insert(0, NoRuntime())
runpy.run_path(sys.argv[1], run_name='__main__')
"""
        result = subprocess.run([sys.executable, "-I", "-B", "-c", script, str(task / "tests/grader.py")],
            env={"PATH": os.environ["PATH"], "HARBOR_TESTS_DIR": str(task / "tests"),
                 "HARBOR_ENTRY_JSON": str(task / "tests/entry.json"), "HARBOR_ATIF_PATH": str(trajectory),
                 "HARBOR_WORKSPACE": str(self.root), "HARBOR_REWARD_JSON": str(self.root / "reward.json"),
                 "HARBOR_REWARD_TXT": str(self.root / "reward.txt")}, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.root / "reward.json").read_text())["custom_metrics"]["gh_gate"], 0)

    def test_native_trial_failure_cannot_enter_agent_setup(self):
        from harbor.trial.trial import Trial
        for error in (RuntimeError("fixture failed"), TimeoutError(), asyncio.CancelledError()):
            start = AsyncMock(side_effect=error)
            setup = AsyncMock(side_effect=AssertionError("Agent setup must not run"))
            fixture = SimpleNamespace(_task_trajectory_error=None, _validate_agent_capabilities=lambda: None,
                _setup_agent_environment=start, _setup_agent=setup)
            with self.assertRaises(BaseException):
                asyncio.run(Trial._prepare(fixture))
            start.assert_awaited_once()
            setup.assert_not_called()

    def test_root_probe_rejects_foreign_stale_dead_and_pid_reused_brokers(self):
        from aeb_gh_fixture import initialize
        expected = {"pid": 123, "start": "99"}
        import stat
        info = SimpleNamespace(st_mode=stat.S_IFSOCK | 0o666, st_uid=0, st_nlink=1, st_ino=7)
        import struct
        from unittest.mock import MagicMock
        for fault in ("foreign", "stale", "dead", "pid-reused", "healthy"):
            connection = MagicMock(); connection.__enter__.return_value = connection
            connection.getsockopt.return_value = struct.pack("3i", 123, 1000 if fault == "foreign" else 0, 0)
            connection.makefile.return_value.__enter__.return_value.readline.return_value = b'{"error":"invalid broker request"}\n'
            if fault == "stale": connection.connect.side_effect = ConnectionRefusedError()
            def fingerprint(pid):
                if fault == "dead": raise FileNotFoundError()
                return "98" if fault == "pid-reused" else "99"
            with patch.object(initialize, "private"), patch.object(Path, "lstat", return_value=info), \
                    patch.object(initialize.socket, "socket", return_value=connection), \
                    patch.object(initialize, "fingerprint", fingerprint):
                if fault == "healthy": self.assertEqual(initialize.probe(expected)["uid"], 0)
                else:
                    with self.assertRaises((RuntimeError, OSError)): initialize.probe(expected)
            if fault == "healthy": connection.sendall.assert_called_once_with(b"{}\n")
            else: connection.sendall.assert_not_called()


if __name__ == "__main__":
    unittest.main()
