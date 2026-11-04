"""No inference: native staging, approval, startup ordering and failure admission."""

import asyncio
import importlib.util
import json
import os
from pathlib import Path
import shutil
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
        from aeb_gh_fixture.backend import TrustedGhEnvironment, COMMAND
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
                if command == COMMAND:
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
                    await environment.start(force_build=True)
                else:
                    with self.assertRaises(BaseException): await environment.start(force_build=True)
            records = [json.loads(line) for line in (trial / "gh-initialization.jsonl").read_text().splitlines()]
            self.assertEqual(records[-1]["status"], "ready" if fault == "success" else "cancelled" if fault == "cancel" else "infrastructure_error")
            self.assertEqual(len(records), 2 if fault == "success" else 1)
        for fault in ("success", "secure-failure", "failed", "cancel", "timeout"):
            asyncio.run(exercise(fault))

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
