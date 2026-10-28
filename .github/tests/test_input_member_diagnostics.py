"""Failure-only diagnostics through production input-integrity guards."""
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import traceback
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import skill_evidence as evidence


class InputMemberDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / 'PRIVATE-TENANT-token=credential\nmember'
        self.path.write_text('PRIVATE-CONTENT-token=credential')
        self.directories = {}
        evidence.safe_path(self.path, directory_identities=self.directories)

    def diagnostic(self, error, phase, role='input_file', error_type=evidence.EvidenceBoundaryError):
        self.assertIs(type(error), error_type)
        self.assertEqual(str(error), 'Input member changed')
        if error_type is evidence.EvidenceBoundaryError:
            self.assertEqual(error.boundary, 'integrity')
        self.assertEqual(len(error.__notes__), 1)
        note = error.__notes__[0]
        self.assertTrue(note.startswith('Input member diagnostic: '))
        self.assertLess(len(note), 384)
        self.assertNotRegex(note, r'PRIVATE|credential|token=|\d|/|\\')
        self.assertNotIn(str(self.root), note)
        self.assertIn(note, ''.join(traceback.format_exception_only(error)))
        data = json.loads(note.removeprefix('Input member diagnostic: '))
        self.assertEqual(set(data), {'phase', 'role', 'changed_fields', 'failed_requirements',
                                     'observed_type', 'observed_links'})
        self.assertEqual((data['phase'], data['role']), (phase, role))
        return data

    def test_revalidation_reports_each_identity_difference(self):
        original = self.path.stat()
        expected = evidence.file_state(original)
        fields = {'device': 'st_dev', 'inode': 'st_ino', 'size': 'st_size',
                  'mtime': 'st_mtime_ns', 'ctime': 'st_ctime_ns'}
        native_stat = os.stat
        for name, field in fields.items():
            with self.subTest(field=name):
                values = {key: getattr(original, key) for key in (*fields.values(), 'st_mode', 'st_nlink')}
                values[field] += 987654321
                def observed(path, *args, **kwargs):
                    if path == self.path.name and kwargs.get('dir_fd') is not None:
                        return SimpleNamespace(**values)
                    return native_stat(path, *args, **kwargs)
                with patch.object(evidence.os, 'stat', side_effect=observed):
                    with self.assertRaises(evidence.EvidenceBoundaryError) as caught:
                        evidence.verify_file_states({self.path: expected}, self.directories, {})
                data = self.diagnostic(caught.exception, 'member_revalidation')
                self.assertEqual(data['changed_fields'], [name])
                self.assertEqual(data['failed_requirements'], [])
                self.assertEqual((data['observed_type'], data['observed_links']), ('regular', 'single'))

    def test_revalidation_reports_type_and_link_requirements(self):
        original = self.path.stat(); native_stat = os.stat
        for mode, links, kind, count, failures in (
            (stat.S_IFIFO, 1, 'fifo', 'single', ['file_type']),
            (stat.S_IFDIR, 1, 'directory', 'single', ['file_type']),
            (stat.S_IFLNK, 1, 'symlink', 'single', ['file_type']),
            (stat.S_IFSOCK, 1, 'socket', 'single', ['file_type']),
            (stat.S_IFCHR, 1, 'device', 'single', ['file_type']),
            (stat.S_IFREG, 0, 'regular', 'zero', ['link_count']),
            (stat.S_IFREG, 987654321, 'regular', 'multiple', ['link_count']),
            (stat.S_IFIFO, 2, 'fifo', 'multiple', ['file_type', 'link_count']),
        ):
            with self.subTest(kind=kind, count=count):
                values = {key: getattr(original, key) for key in (
                    'st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode', 'st_nlink')}
                values.update(st_mode=mode, st_nlink=links)
                def observed(path, *args, **kwargs):
                    return SimpleNamespace(**values) if path == self.path.name and kwargs.get('dir_fd') is not None else native_stat(path, *args, **kwargs)
                with patch.object(evidence.os, 'stat', side_effect=observed):
                    with self.assertRaises(evidence.EvidenceBoundaryError) as caught:
                        evidence.verify_file_states({self.path: evidence.file_state(original)}, self.directories, {})
                data = self.diagnostic(caught.exception, 'member_revalidation')
                self.assertEqual(data['changed_fields'], [])
                self.assertEqual(data['failed_requirements'], failures)
                self.assertEqual((data['observed_type'], data['observed_links']), (kind, count))

    def test_real_fifo_and_hardlink_rejections(self):
        expected = evidence.file_state(self.path.stat())
        os.link(self.path, self.root / 'PRIVATE-alias')
        with self.assertRaises(evidence.EvidenceBoundaryError) as caught:
            evidence.verify_file_states({self.path: expected}, self.directories, {})
        self.assertIn('link_count', self.diagnostic(caught.exception, 'member_revalidation')['failed_requirements'])
        self.path.unlink(); os.mkfifo(self.path)
        with self.assertRaises(evidence.EvidenceBoundaryError) as caught:
            evidence.verify_file_states({self.path: expected}, self.directories, {})
        data = self.diagnostic(caught.exception, 'member_revalidation')
        self.assertEqual((data['observed_type'], data['failed_requirements']), ('fifo', ['file_type']))

    def test_unknown_labels_are_closed_and_notes_reach_unittest_failures(self):
        expected = list(evidence.file_state(self.path.stat())); expected[2] += 1
        for _ in range(2):
            with self.assertRaises(evidence.EvidenceBoundaryError) as caught:
                evidence.verify_file_states({self.path: tuple(expected)}, self.directories, {},
                    phase='PRIVATE-phase-token=credential', role='PRIVATE-role-token=credential')
            data = self.diagnostic(caught.exception, 'unknown', 'unknown')
            self.assertEqual(data['changed_fields'], ['size'])
            note = caught.exception.__notes__[0]
            if _ == 0: first = note
            else: self.assertEqual(note, first)
        path, directories = self.path, self.directories
        class OriginalAssertion(unittest.TestCase):
            def runTest(self):
                with self.assertRaisesRegex(ValueError, 'Oversized historical blob'):
                    evidence.verify_file_states({path: tuple(expected)}, directories, {})
        output = io.StringIO()
        result = unittest.TextTestRunner(stream=output).run(OriginalAssertion())
        self.assertEqual(len(result.failures), 1)
        text = output.getvalue()
        self.assertIn('Input member changed', text)
        self.assertIn('Input member diagnostic:', text)
        self.assertIn('"changed_fields":["size"]', text)
        self.assertNotRegex(text, r'PRIVATE|credential|token=')
        self.assertNotIn(str(self.root), text)

    def test_read_open_rejects_before_budget_or_content_capture(self):
        expected = list(evidence.file_state(self.path.stat())); expected[1] += 1
        budget = evidence.ReadBudget()
        with patch.object(budget, 'consume') as consume:
            with self.assertRaises(evidence.EvidenceBoundaryError) as caught:
                evidence.read_bytes(self.path, budget=budget, file_states={self.path: tuple(expected)})
        consume.assert_not_called()
        self.assertEqual(self.diagnostic(caught.exception, 'read_open')['changed_fields'], ['inode'])

    def test_read_complete_reports_actual_growth(self):
        fdopen = os.fdopen
        class ChangedStream:
            def __init__(self, stream, path): self.stream, self.path = stream, path
            def __enter__(self): return self
            def __exit__(self, *args): self.stream.close()
            def fileno(self): return self.stream.fileno()
            def read(self, size):
                raw = self.stream.read(size)
                with self.path.open('ab') as output: output.write(b'changed')
                return raw
        with patch.object(evidence.os, 'fdopen', side_effect=lambda *a, **k: ChangedStream(fdopen(*a, **k), self.path)):
            with self.assertRaises(evidence.EvidenceBoundaryError) as caught:
                evidence.read_bytes(self.path, file_states={})
        self.assertIn('size', self.diagnostic(caught.exception, 'read_complete')['changed_fields'])

    def test_tree_capture_preserves_plain_value_error(self):
        expected = list(evidence.file_state(self.path.stat())); expected[2] += 1
        with self.assertRaises(ValueError) as caught:
            evidence.safe_tree(self.root, file_states={self.path: tuple(expected)})
        data = self.diagnostic(caught.exception, 'tree_capture', error_type=ValueError)
        self.assertEqual(data['changed_fields'], ['size'])

    def test_inventory_presence_uses_the_production_guard(self):
        skill = self.root / '.apm/skills/alpha'; skill.mkdir(parents=True)
        (skill / 'SKILL.md').write_text('---\nname: alpha\ndescription: Synthetic fixture\n---\n')
        lock = self.root / 'apm.lock.yaml'; lock.write_text('dependencies: []\ndeployments: []\n')
        scan = evidence.safe_tree
        def captured(path, **kwargs):
            files = scan(path, **kwargs)
            if path == self.root / '.apm/skills':
                expected = list(evidence.file_state(lock.stat())); expected[2] += 1
                kwargs['file_states'][lock] = tuple(expected)
            return files
        with patch.object(evidence, 'safe_tree', side_effect=captured):
            with self.assertRaises(ValueError) as caught:
                evidence.inventory(self.root)
        data = self.diagnostic(caught.exception, 'inventory_presence', error_type=ValueError)
        self.assertEqual(data['changed_fields'], ['size'])

    def repository(self):
        repo = self.root / 'repo'; repo.mkdir()
        def git(*args):
            return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()
        git('init', '-q'); git('config', 'remote.origin.url', 'https://github.com/example/fixture.git')
        (repo / 'synthetic').write_text('synthetic')
        git('add', 'synthetic'); git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Fixture')
        return repo, git

    def test_repository_revalidation_classifies_real_object_change(self):
        repo, git = self.repository()
        oid = git('rev-parse', 'HEAD:synthetic')
        path = repo / '.git/objects' / oid[:2] / oid[2:]; path.chmod(0o600)
        budget = evidence.ReadBudget(); evidence.workspace_repository(repo, budget=budget)
        with path.open('ab') as stream: stream.write(b'changed')
        with self.assertRaises(evidence.EvidenceBoundaryError) as caught:
            budget.verify_repository()
        data = self.diagnostic(caught.exception, 'repository_revalidation', 'git_object_store')
        self.assertIn('size', data['changed_fields'])
        self.assertNotIn(oid, caught.exception.__notes__[0])

    def test_repository_revalidation_classifies_metadata_and_references(self):
        repo, git = self.repository()
        for kind in ('git_metadata', 'git_reference'):
            with self.subTest(role=kind):
                budget = evidence.ReadBudget()
                evidence.workspace_repository(repo, budget=budget)
                evidence.inventory_revision(repo, budget)
                path = repo / '.git/config' if kind == 'git_metadata' else next((repo / '.git/refs/heads').iterdir())
                with path.open('ab') as stream: stream.write(b'\n')
                with self.assertRaises(evidence.EvidenceBoundaryError) as caught:
                    budget.verify_repository()
                self.assertIn('size', self.diagnostic(caught.exception, 'repository_revalidation', kind)['changed_fields'])

    def test_unchanged_guards_are_silent(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err), \
                patch.object(evidence.json, 'dumps', side_effect=AssertionError('No diagnostic formatting on success')):
            evidence.read_bytes(self.path, file_states={})
            evidence.safe_tree(self.root)
            with patch.object(evidence.ReadBudget, 'member_role', side_effect=AssertionError('No role classification on success')) as role:
                evidence.verify_file_states({self.path: evidence.file_state(self.path.stat())}, self.directories, {}, role=role)
        self.assertEqual((out.getvalue(), err.getvalue()), ('', ''))

    def test_diagnostic_failure_cannot_replace_the_guard_rejection(self):
        expected = list(evidence.file_state(self.path.stat())); expected[2] += 1
        with patch.object(evidence.json, 'dumps', side_effect=RuntimeError('PRIVATE-token=credential')):
            with self.assertRaises(evidence.EvidenceBoundaryError) as caught:
                evidence.verify_file_states({self.path: tuple(expected)}, self.directories, {})
        self.assertIs(type(caught.exception), evidence.EvidenceBoundaryError)
        self.assertEqual(str(caught.exception), 'Input member changed')
        self.assertEqual(caught.exception.boundary, 'integrity')
        self.assertEqual(caught.exception.__notes__, ['Input member diagnostic: unavailable'])
        self.assertNotRegex(''.join(traceback.format_exception(caught.exception)), r'PRIVATE|credential|token=')

    def test_oversized_rejection_keeps_its_original_precedence(self):
        with self.path.open('wb') as stream: stream.truncate(evidence.JSON_LIMIT + 1)
        expected = list(evidence.file_state(self.path.stat())); expected[2] += 1
        with self.assertRaises(evidence.EvidenceBoundaryError) as caught:
            evidence.read_bytes(self.path, file_states={self.path: tuple(expected)})
        self.assertEqual(str(caught.exception), 'Special, hard-linked or oversized input')
        self.assertFalse(hasattr(caught.exception, '__notes__'))
