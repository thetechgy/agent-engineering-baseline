"""Exercise the regeneration boundary through Git and native subprocesses."""

import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("apm_regeneration", REPO / "scripts/apm_regeneration.py")
regeneration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(regeneration)


class RegenerationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="regeneration-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.git("init", "--quiet")
        self.git("remote", "add", "origin", "https://github.com/example/baseline.git")
        self.write("apm.lock.yaml", "locked\n")
        self.write("apm.yml", "source\n")
        self.write(".codex/config.toml", "reviewed config\n")
        self.write(".gitignore", "apm_modules/\n")
        self.write(".agents/skills/fixture/SKILL.md", "reviewed\n")
        self.git("add", "--all")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "--quiet", "-m", "fixture")
        self.apm = self.root / "apm"
        self.apm.write_text("#!/bin/sh\nexit 0\n")
        self.apm.chmod(0o755)

    def git(self, *arguments):
        return subprocess.check_output(["git", *arguments], cwd=self.source)

    def write(self, name, content):
        path = self.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    @staticmethod
    def materialize(apm, scratch, refresh, environment=None):
        skill = scratch / ".agents/skills/fixture/SKILL.md"
        assert not skill.exists(), "Cold regeneration reused deployed skills"
        assert not (scratch / ".apm-local").exists(), "Local identity was copied"
        assert not (scratch / "private.txt").exists(), "Untracked user data was copied"
        assert not (scratch / "apm_modules").exists(), "Local modules were copied"
        skill.parent.mkdir(parents=True)
        skill.write_text("refreshed\n" if refresh else "reviewed\n")

    def invoke(self, mode="validate", implementation=None):
        with patch.object(regeneration, "native_checks", side_effect=implementation or self.materialize):
            regeneration.regenerate(self.source, self.apm, mode)

    def test_cold_repeat_preserves_worktree_index_untracked_and_local_state(self):
        self.write("private.txt", "user data\n")
        self.write(".apm-local/.gitignore", "*\n")
        self.write(".apm-local/installation", "original identity\n")
        self.write("apm_modules/private", "original modules\n")
        self.write("apm.yml", "staged source\n")
        self.git("add", "apm.yml")
        self.write("apm.yml", "unstaged source\n")
        before = regeneration.inventory(self.source)
        staged = self.git("diff", "--cached", "--binary")

        def check(apm, scratch, refresh, environment):
            self.materialize(apm, scratch, refresh)
            self.assertNotEqual(environment["HOME"], os.environ.get("HOME"))
            self.assertNotIn("APM_HOME", environment)
            self.assertEqual((scratch / "apm.yml").read_text(), "unstaged source\n")
            self.assertEqual(regeneration.git(scratch, "remote", "get-url", "origin"),
                             b"https://github.com/example/baseline.git\n")
            self.assertIn(b".agents/skills/fixture/SKILL.md", regeneration.git(scratch, "ls-files"))

        self.invoke(implementation=check)
        self.invoke(implementation=check)
        self.assertEqual(before, regeneration.inventory(self.source))
        self.assertEqual(staged, self.git("diff", "--cached", "--binary"))
        self.assertEqual((self.source / ".apm-local/installation").read_text(), "original identity\n")
        self.assertEqual((self.source / "apm_modules/private").read_text(), "original modules\n")

    def test_generated_drift_fails_without_repairing_the_caller(self):
        self.write(".agents/skills/fixture/SKILL.md", "caller edit\n")
        before = regeneration.inventory(self.source)
        with self.assertRaisesRegex(RuntimeError, "differs from checkout"):
            self.invoke()
        self.assertEqual(before, regeneration.inventory(self.source))

    def test_git_path_environment_cannot_redirect_the_caller_index(self):
        original = self.git("ls-files", "--stage", "-z")
        foreign_index = self.root / "foreign-index"
        foreign_index.write_text("must remain untouched\n")
        with patch.dict(os.environ, {"GIT_DIR": str(self.root / "missing-repo"),
                                     "GIT_WORK_TREE": str(self.root), "GIT_INDEX_FILE": str(foreign_index)}):
            self.invoke()
        self.assertEqual(self.git("ls-files", "--stage", "-z"), original)
        self.assertEqual(foreign_index.read_text(), "must remain untouched\n")

    @unittest.skipIf(os.name == "nt", "Executable file mode is a Unix boundary")
    def test_generated_executable_mode_drift_fails(self):
        def changed_mode(apm, scratch, refresh, environment):
            self.materialize(apm, scratch, refresh)
            (scratch / ".agents/skills/fixture/SKILL.md").chmod(0o755)

        with self.assertRaisesRegex(RuntimeError, "differs from checkout"):
            self.invoke(implementation=changed_mode)

    def test_refresh_publishes_only_outputs_and_preserves_untracked_files(self):
        self.write("private.txt", "keep\n")
        self.invoke("refresh")
        self.assertEqual((self.source / ".agents/skills/fixture/SKILL.md").read_text(), "refreshed\n")
        self.assertEqual((self.source / "private.txt").read_text(), "keep\n")

    def test_unexpected_source_edit_or_extra_output_blocks_refresh(self):
        for name in ("apm.yml", "unexpected.txt"):
            with self.subTest(path=name):
                before = regeneration.inventory(self.source)

                def change(apm, scratch, refresh, environment):
                    self.materialize(apm, scratch, refresh)
                    (scratch / name).write_text("unexpected\n")

                with self.assertRaisesRegex(RuntimeError, "non-output paths"):
                    self.invoke("refresh", change)
                self.assertEqual(before, regeneration.inventory(self.source))

    def test_untracked_output_collision_and_concurrent_edit_block_refresh(self):
        self.write(".agents/skills/new/SKILL.md", "user skill\n")

        def collide(apm, scratch, refresh, environment):
            self.materialize(apm, scratch, refresh)
            path = scratch / ".agents/skills/new/SKILL.md"
            path.parent.mkdir(parents=True)
            path.write_text("generated\n")

        with self.assertRaisesRegex(RuntimeError, "untracked caller files"):
            self.invoke("refresh", collide)
        self.assertEqual((self.source / ".agents/skills/new/SKILL.md").read_text(), "user skill\n")

        def concurrent(apm, scratch, refresh, environment):
            self.materialize(apm, scratch, refresh)
            self.write("apm.yml", "concurrent edit\n")

        with self.assertRaisesRegex(RuntimeError, "Checkout changed"):
            self.invoke("refresh", concurrent)
        self.assertEqual((self.source / "apm.yml").read_text(), "concurrent edit\n")

    def test_failed_native_command_never_publishes(self):
        before = regeneration.inventory(self.source)
        with self.assertRaises(subprocess.CalledProcessError):
            self.invoke("refresh", lambda *args: regeneration.run(["sh", "-c", "exit 23"], self.root))
        self.assertEqual(before, regeneration.inventory(self.source))

    def test_refresh_refuses_preexisting_generated_edits(self):
        self.write(".agents/skills/fixture/SKILL.md", "caller edit\n")
        with self.assertRaisesRegex(RuntimeError, "unchanged generated outputs"):
            self.invoke("refresh")
        self.assertEqual((self.source / ".agents/skills/fixture/SKILL.md").read_text(), "caller edit\n")

    def test_refresh_preserves_ignored_caller_files_before_any_publication(self):
        private = self.source / ".agents/skills/new/SKILL.md"
        self.write(".agents/skills/new/SKILL.md", "private caller data\n")
        with (self.source / ".git/info/exclude").open("a") as exclude:
            exclude.write("\n.agents/skills/new/\n")
        before = regeneration.inventory(self.source)
        self.assertNotIn(".agents/skills/new/SKILL.md", before)

        def collide(apm, scratch, refresh, environment):
            self.materialize(apm, scratch, refresh)
            output = scratch / ".agents/skills/new/SKILL.md"
            output.parent.mkdir(parents=True)
            output.write_text("generated replacement\n")

        with self.assertRaisesRegex(RuntimeError, "untracked caller files"):
            self.invoke("refresh", collide)
        self.assertEqual(private.read_text(), "private caller data\n")
        self.assertEqual(before, regeneration.inventory(self.source))

    def test_failed_publication_restores_prior_output_bytes_and_modes(self):
        before = regeneration.inventory(self.source)
        copy = regeneration.shutil.copy2

        def fail_second_output(source, destination):
            if destination == self.source / ".codex/config.toml":
                raise OSError("Injected publication failure")
            return copy(source, destination)

        def change(apm, scratch, refresh, environment):
            self.materialize(apm, scratch, refresh)
            (scratch / ".agents/skills/fixture/SKILL.md").chmod(0o755)
            (scratch / ".codex/config.toml").write_text("refreshed config\n")

        with patch.object(regeneration.shutil, "copy2", side_effect=fail_second_output):
            with self.assertRaisesRegex(OSError, "Injected publication failure"):
                self.invoke("refresh", change)
        self.assertEqual(before, regeneration.inventory(self.source))


@unittest.skipIf(os.name == "nt", "Full validation uses the Linux script PTY utility")
class NativeAuditTests(unittest.TestCase):
    def test_refresh_reconciles_executable_assets_and_stops_on_command_failure(self):
        commands = ["update --yes", "install --trust-bin", "install --frozen --trust-bin",
                    "compile --target codex,copilot --validate", "compile --target codex,copilot"]
        for failed in ("", *commands[:3]):
            with self.subTest(failed=failed), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "apm.lock.yaml").write_text("locked\n")
                apm = root / "apm"
                log = root / "calls"
                apm.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALL_LOG"\n'
                               '[ "$*" != "$FAIL_COMMAND" ] || exit 23\nexit 0\n')
                apm.chmod(0o755)
                with patch.dict(os.environ, {"CALL_LOG": str(log), "FAIL_COMMAND": failed}):
                    if failed:
                        with self.assertRaises(subprocess.CalledProcessError):
                            regeneration.native_checks(apm, root, True)
                    else:
                        regeneration.native_checks(apm, root, True)
                self.assertEqual(log.read_text().splitlines(), commands[:commands.index(failed) + 1]
                                 if failed else commands)

    def test_real_pty_propagates_failure_and_stops_before_packaging(self):
        for audit_status in (0, 37):
            with self.subTest(audit_status=audit_status), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "apm.lock.yaml").write_text("locked\n")
                apm = root / "apm fixture"
                log = root / "calls"
                apm.write_text(
                    '#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALL_LOG"\n'
                    'case "$1" in\n'
                    f' audit) exit {audit_status} ;;\n'
                    ' pack) exit 39 ;;\n'
                    'esac\nexit 0\n')
                apm.chmod(0o755)
                with patch.dict(os.environ, {"CALL_LOG": str(log)}):
                    with self.assertRaises(subprocess.CalledProcessError) as failure:
                        regeneration.native_checks(apm, root, False)
                self.assertEqual(failure.exception.returncode, audit_status or 39)
                calls = log.read_text().splitlines()
                self.assertIn("audit --ci", calls)
                self.assertEqual("pack --dry-run" in calls, audit_status == 0)

    def test_first_frozen_install_cannot_rewrite_the_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "apm.lock.yaml").write_text("locked\n")
            apm = root / "apm"
            apm.write_text('#!/bin/sh\ncase "$*" in\n'
                           ' "install --frozen --trust-bin") printf changed > apm.lock.yaml ;;\n'
                           'esac\nexit 0\n')
            apm.chmod(0o755)
            with self.assertRaisesRegex(RuntimeError, "Frozen regeneration changed lockfile"):
                regeneration.native_checks(apm, root, True)


if __name__ == "__main__":
    unittest.main()
