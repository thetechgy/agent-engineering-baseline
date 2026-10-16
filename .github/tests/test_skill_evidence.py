"""Offline inventory, pinned native ingestion, and public-boundary regressions."""

import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import itertools
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import skill_evidence as evidence

REPO = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / 'fixtures/skill_evidence'


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(evidence.encoded(data))


@contextmanager
def git_trace(path):
    """Explicit fixture instrumentation after the production environment boundary."""
    popen = subprocess.Popen
    def traced(command, *args, **kwargs):
        if command[0] == 'git' and kwargs.get('env') is not None:
            env = kwargs['env']
            assert env['GIT_NO_LAZY_FETCH'] == env['GIT_NO_REPLACE_OBJECTS'] == '1'
            assert all(value == '0' for key, value in env.items() if key.startswith('GIT_TRACE'))
            kwargs['env'] = {**env, 'GIT_TRACE2_EVENT': str(path),
                             'GIT_TRACE2_ENV_VARS': 'GIT_NO_LAZY_FETCH,GIT_NO_REPLACE_OBJECTS',
                             'GIT_TRACE2_CONFIG_PARAMS': ''}
        return popen(command, *args, **kwargs)
    with patch.object(subprocess, 'Popen', side_effect=traced):
        yield


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # Replay the reviewed fixture before expiry; boundary tests advance this clock explicitly.
        clock = patch.object(evidence, 'utc_now', return_value=datetime(2026, 10, 10, tzinfo=timezone.utc))
        clock.start(); self.addCleanup(clock.stop)

    def native(self):
        target = self.root / 'native'
        shutil.copytree(FIXTURES / 'podman-native', target)
        # Mutated cases test ordinary native artifacts, independently of the reviewed extract.
        (target / 'extract-manifest.json').unlink()
        return target

    def data(self):
        return evidence.normalize_behavioral(FIXTURES / 'podman-native', 'podman')

    def unscore_case(self, summary, case):
        payload = summary['pass_at_k']; row = payload['cases'][case]
        was_passed = row['passed']
        row['attempts'][0].update(score=None, passed=None)
        row.update(passed=False, first_pass_attempt=None, best_score=None)
        payload['passed_cases'] -= was_passed; payload['failed_cases'] += was_passed
        payload['rate'] = round(payload['passed_cases'] / payload['total_cases'], 4)

    def repo(self):
        root = self.root / 'repo'
        root.mkdir()
        self.local(root, 'alpha')
        return root

    def local(self, root, name, dataset=False):
        path = root / '.apm/skills' / name
        path.mkdir(parents=True, exist_ok=True)
        (path / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: Synthetic fixture\n---\n')
        if dataset:
            self.dataset(path, name)
        return path

    def dataset(self, root, name):
        write(root / 'evals/evals.json', {'skill_name': name, 'evals': [
            {'id': 1, 'prompt': 'Synthetic fixture', 'expected_output': 'Synthetic outcome'}]})

    def imported(self, root, name='beta'):
        deployed = root / '.agents/skills' / name
        deployed.mkdir(parents=True)
        (deployed / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: Synthetic imported fixture\n---\n')
        member = (deployed / 'SKILL.md').relative_to(root).as_posix()
        sha = evidence.digest_bytes((deployed / 'SKILL.md').read_bytes())
        owner = 'example/skills/skills/' + name
        lock = {'dependencies': [{'name': name, 'repo_url': 'example/skills', 'virtual_path': 'skills/' + name,
                 'resolved_commit': 'a' * 40, 'deployed_file_hashes': {member: sha}}],
                'deployments': [{'value': member, 'target': 'codex', 'active_owner': owner, 'owners': [owner], 'content_hash': sha}]}
        (root / 'apm.lock.yaml').write_text(yaml.safe_dump(lock))
        self.dataset(root / '.github/evals' / name, name)
        return lock

    def mutate(self, root, suffix, fn):
        path = next(p for p in root.rglob('*.json') if p.as_posix().endswith(suffix))
        data = evidence.read_json(path); fn(data); write(path, data)
        return path

    def test_current_discovery(self):
        inv = evidence.inventory()
        self.assertEqual(sum(r['source']['owner'] == 'local' for r in inv['skills']), 6)
        self.assertEqual(sum(r['suite'] is not None for r in inv['skills']), 2)
        gh = next(r for r in inv['skills'] if r['source']['skill_id'] == 'gh')
        self.assertEqual(gh['source']['repository'], 'cli/cli')
        self.assertEqual(len(gh['suite']['case_ids']), 24)
        self.assertEqual(gh['measurement']['status'], 'unavailable')

    def test_inventory_local_revision_matches_committed_manifest(self):
        for change in ('clean', 'unstaged', 'staged', 'untracked', 'deleted', 'unrelated', 'committed'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / 'checkout'; authored = self.local(root, 'alpha')
                (authored / 'README.md').write_text('Committed fixture')
                def git(*args):
                    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True,
                                          text=True, timeout=30).stdout.strip()
                git('init', '-q')
                git('config', 'remote.origin.url', 'https://github.com/thetechgy/agent-engineering-baseline.git')
                git('add', '.apm')
                git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Fixture')
                if change in ('unstaged', 'staged', 'committed'):
                    (authored / 'README.md').write_text('Changed fixture')
                    if change != 'unstaged': git('add', '.apm')
                    if change == 'committed':
                        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Updated fixture')
                elif change == 'untracked': (authored / 'extra.md').write_text('Untracked fixture')
                elif change == 'deleted': (authored / 'README.md').unlink()
                elif change == 'unrelated': (root / 'unrelated.txt').write_text('Unrelated work')
                expected = git('rev-parse', 'HEAD') if change in ('clean', 'unrelated', 'committed') else None
                before = self.snapshot(root); stdout = StringIO(); inventory = evidence.inventory
                output = Path(temp) / 'output'
                with patch.object(evidence, 'inventory', side_effect=lambda: inventory(root)), redirect_stdout(stdout):
                    evidence.main(['inventory', '--output', str(output)])
                value = evidence.read_json(output / 'inventory.json')
                self.assertEqual(value['skills'][0]['source']['revision'], expected)
                self.assertEqual(evidence.encoded(inventory(root)), evidence.encoded(value))
                self.assertEqual(self.snapshot(root), before)

    def test_inventory_revision_comparison_shares_read_budget(self):
        root = self.repo(); authored = root / '.apm/skills/alpha'
        (authored / 'README.md').write_text('Committed fixture')
        def git(*args):
            subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True, timeout=30)
        git('init', '-q')
        git('config', 'remote.origin.url', 'https://github.com/thetechgy/agent-engineering-baseline.git')
        git('add', '.apm')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Fixture')
        budget = evidence.ReadBudget(); before = self.snapshot(root)
        with patch.object(evidence, 'ReadBudget', return_value=budget) as budgets:
            baseline = evidence.inventory(root)
        self.assertEqual(budgets.call_count, 1)
        consumed = evidence.NORMALIZATION_LIMIT - budget.remaining
        self.assertGreater(consumed, sum(p.stat().st_size for p in authored.iterdir()))
        with patch.object(evidence, 'NORMALIZATION_LIMIT', consumed):
            self.assertEqual(evidence.encoded(evidence.inventory(root)), evidence.encoded(baseline))
        output = self.root / 'rejected-revision-budget'; inventory = evidence.inventory
        with patch.object(evidence, 'NORMALIZATION_LIMIT', consumed - 1), \
                patch.object(evidence, 'inventory', side_effect=lambda: inventory(root)), \
                self.assertRaisesRegex(ValueError, 'Normalization byte limit'), redirect_stdout(StringIO()):
            evidence.main(['inventory', '--output', str(output)])
        self.assertFalse(output.exists()); self.assertEqual(self.snapshot(root), before)

    def test_imported_manifest_rejects_changed_lock_validated_member(self):
        root = self.repo(); lock = self.imported(root)
        authored = root / '.agents/skills/beta'
        (authored / 'README.md').write_text('Reviewed content')
        for member in ('evals/evals.json', 'nested/SKILL.md', 'nested/evals/evals.json', 'results/output.json'):
            path = authored / member; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('Fixture')
        owner = lock['dependencies'][0]; ownership = owner['repo_url'] + '/' + owner['virtual_path']
        owner['deployed_file_hashes'] = {p.relative_to(root).as_posix(): evidence.digest_bytes(p.read_bytes())
                                       for p in authored.rglob('*') if p.is_file()}
        lock['deployments'] = [{'value': member, 'target': 'codex', 'active_owner': ownership,
                               'owners': [ownership], 'content_hash': digest}
                              for member, digest in owner['deployed_file_hashes'].items()]
        (root / 'apm.lock.yaml').write_text(yaml.safe_dump(lock))
        baseline = next(row for row in evidence.inventory(root)['skills'] if row['source']['skill_id'] == 'beta')
        self.assertEqual([row['member'] for row in baseline['source']['content']['manifest']],
                         ['README.md', 'SKILL.md', 'nested/SKILL.md'])
        original_require = evidence.require; checked = 0
        def replace_after_lock(condition, message):
            nonlocal checked
            original_require(condition, message)
            if message == 'Ambiguous deployment ownership':
                checked += 1
                if checked == len(owner['deployed_file_hashes']):
                    (authored / 'README.md').write_text('Replacement content')
        with patch.object(evidence, 'require', side_effect=replace_after_lock):
            with self.assertRaisesRegex(ValueError, 'Input member changed'): evidence.inventory(root)
        self.assertEqual(checked, len(owner['deployed_file_hashes']))

    def test_inventory_skill_limit_precedes_processing(self):
        root = self.root / 'catalog'
        for index in range(1000): self.local(root, 's-' + str(index))
        self.assertEqual(len(evidence.inventory(root)['skills']), 1000)
        for kind in ('local', 'overlay'):
            with self.subTest(kind=kind):
                if kind == 'local': extra = self.local(root, 'excess')
                else:
                    extra = root / '.github/evals/excess'
                    self.dataset(extra, 'excess')
                with patch.object(evidence, 'validate_skill_metadata') as metadata, \
                        patch.object(evidence, 'skill_content') as hashing, \
                        patch.object(evidence, 'resolve_git_revision') as revision:
                    with self.assertRaisesRegex(ValueError, 'Inventory limit'):
                        evidence.inventory(root)
                    self.assertEqual((metadata.call_count, hashing.call_count, revision.call_count), (0, 0, 0))
                shutil.rmtree(extra)

    def test_lock_record_limits_and_alias_duplicates(self):
        root = self.repo()
        for key, limit in (('dependencies', evidence.MAX_CASES), ('deployments', evidence.MAX_INPUT_ENTRIES)):
            for size in (limit, limit + 1):
                with self.subTest(key=key, size=size):
                    lock = {'dependencies': [], 'deployments': []}
                    lock[key] = [{}] * size
                    (root / 'apm.lock.yaml').write_text(yaml.safe_dump(lock))
                    if size == limit:
                        self.assertEqual(len(evidence.inventory(root)['skills']), 1)
                    else:
                        with patch.object(evidence, 'validate_skill_metadata') as metadata, \
                                patch.object(evidence, 'skill_content') as hashing, \
                                patch.object(evidence, 'resolve_git_revision') as revision:
                            with self.assertRaisesRegex(ValueError, 'Ownership record limit'):
                                evidence.inventory(root)
                            self.assertEqual((metadata.call_count, hashing.call_count, revision.call_count), (0, 0, 0))
        for key in ('dependencies', 'deployments'):
            with self.subTest(duplicate_alias=key), tempfile.TemporaryDirectory() as temp:
                checkout = Path(temp); self.local(checkout, 'alpha'); lock = self.imported(checkout)
                lock[key].append(lock[key][0])  # An alias remains a second ownership record.
                (checkout / 'apm.lock.yaml').write_text(yaml.safe_dump(lock))
                with self.assertRaises(ValueError): evidence.inventory(checkout)

    def test_yaml_alias_graph_has_bounded_depth_work(self):
        checkout = self.root / 'checkout'; self.local(checkout, 'alpha')
        scripts = checkout / '.github/scripts'; scripts.mkdir(parents=True)
        for name in ('skill_evidence.py', 'skill_reports.py'):
            shutil.copyfile(REPO / '.github/scripts' / name, scripts / name)
        lock = checkout / 'apm.lock.yaml'
        text = 'dependencies: []\ndeployments: []\na0: &a0 [0]\n'
        text += ''.join(f'a{i}: &a{i} [*a{i-1}, *a{i-1}]\n' for i in range(1, 31))
        lock.write_text(text)
        output = self.root / 'alias-output'
        result = subprocess.run([sys.executable, str(scripts / 'skill_evidence.py'),
                                 'inventory', '--output', str(output)],
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(lock.read_text(), text)
        with patch.object(evidence, 'require', wraps=evidence.require) as checks:
            value = evidence.read_yaml(lock)
            self.assertLess(checks.call_count, 4000)
        self.assertIs(value['a30'][0], value['a30'][1])
        for unsafe in ('cycle: &cycle [*cycle]\n', 'number: .nan\n'):
            lock.write_text(unsafe)
            with self.assertRaises(ValueError): evidence.read_yaml(lock)
        shared = [0]; nested = shared
        for _ in range(32): nested = [nested]
        with self.assertRaises(ValueError): evidence.depth({'short': shared, 'deep': nested}, 32)

    def test_future_source_and_suite(self):
        root = self.repo(); self.local(root, 'future', True)
        rows = evidence.inventory(root)['skills']
        self.assertEqual([r['source']['skill_id'] for r in rows], ['alpha', 'future'])
        self.assertEqual(rows[0]['behavioral_status'], 'not_configured')
        self.assertEqual(rows[1]['suite']['case_ids'], ['1'])

    def test_inventory_dataset_rejects_changed_captured_buffer(self):
        for captured_valid in (True, False):
            with self.subTest(captured_valid=captured_valid), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); authored = self.local(root, 'alpha', True)
                path = authored / 'evals/evals.json'
                original = evidence.read_json(path)
                replacement = copy.deepcopy(original)
                replacement['evals'][0]['id'] = 2
                if not captured_valid:
                    del original['evals'][0]['expected_output']
                write(path, original)
                captured = path.read_bytes()
                read = evidence.read_bytes
                reads = []
                def replacing(member, *args, **kwargs):
                    raw = read(member, *args, **kwargs)
                    if Path(member) == path:
                        reads.append(raw)
                        write(path, replacement)
                    return raw
                with patch.object(evidence, 'read_bytes', side_effect=replacing):
                    if captured_valid:
                        with self.assertRaisesRegex(ValueError, 'Input member changed'): evidence.inventory(root)
                    else:
                        with self.assertRaises(ValueError):
                            evidence.inventory(root)
                self.assertEqual(reads, [captured])

    def test_inventory_shared_budget_and_single_capture(self):
        for imported in (False, True):
            with self.subTest(imported=imported), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); self.local(root, 'alpha', True)
                if imported: self.imported(root)
                else: self.local(root, 'beta', True)
                reads = {}; read = evidence.read_bytes
                def counted(path, *args, **kwargs):
                    raw = read(path, *args, **kwargs)
                    reads[path] = reads.get(path, 0) + 1
                    return raw
                before = self.snapshot(root)
                with patch.object(evidence, 'read_bytes', side_effect=counted):
                    baseline = evidence.inventory(root)
                self.assertTrue(all(n == 1 for n in reads.values()))
                total = sum(p.stat().st_size for p in reads)
                with patch.object(evidence, 'NORMALIZATION_LIMIT', total):
                    self.assertEqual(evidence.encoded(evidence.inventory(root)), evidence.encoded(baseline))
                with patch.object(evidence, 'NORMALIZATION_LIMIT', total - 1):
                    with self.assertRaisesRegex(ValueError, 'Normalization byte limit'):
                        evidence.inventory(root)
                self.assertEqual(self.snapshot(root), before)

    def test_inventory_gh_delegated_reads_share_budget_and_default_behavior(self):
        import gh_evaluations as gh
        reads = {}; read = evidence.read_bytes
        budget = evidence.ReadBudget()
        def counted(path, *args, **kwargs):
            raw = read(path, *args, **kwargs)
            reads[path] = reads.get(path, 0) + 1
            return raw
        with patch.object(evidence, 'read_bytes', side_effect=counted), patch.object(evidence, 'ReadBudget', return_value=budget):
            baseline = evidence.inventory(REPO)
        self.assertTrue(all(n == 1 for n in reads.values()))
        total = evidence.NORMALIZATION_LIMIT - budget.remaining
        self.assertGreater(total, sum(p.stat().st_size for p in reads))
        with patch.object(evidence, 'NORMALIZATION_LIMIT', total):
            self.assertEqual(evidence.encoded(evidence.inventory(REPO)), evidence.encoded(baseline))
        for helper in (gh.verify_skill, gh.verify_competing, gh.dataset):
            self.assertEqual(helper(REPO), helper(REPO, read_bytes=evidence.read_bytes))
        targets = (REPO / 'apm.lock.yaml', REPO / '.agents/skills/gh/SKILL.md',
                   REPO / '.agents/skills/github-actions-hardening/SKILL.md',
                   REPO / '.github/evals/gh/evals/evals.json')
        for target in targets:
            with self.subTest(target=target.relative_to(REPO)):
                attempts = []
                def exhausted(path, *args, **kwargs):
                    if path == target:
                        kwargs['budget'].remaining = 0
                        attempts.append(path)
                    return read(path, *args, **kwargs)
                with patch.object(evidence, 'read_bytes', side_effect=exhausted):
                    with self.assertRaisesRegex(ValueError, 'Normalization byte limit'):
                        evidence.inventory(REPO)
                self.assertEqual(attempts, [target])

    def test_inventory_native_optional_files_use_captured_bytes(self):
        contents = {'grader.py': '# reward.json\n', 'grader.sh': '# reward.txt\n',
                    'config.yml': 'schema_version: 1\n',
                    'environment/Dockerfile': 'FROM scratch\n',
                    'environment/mcp_servers.toml': 'mcp_servers = []\n'}
        for member, text in contents.items():
            with self.subTest(member=member), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); authored = self.local(root, 'alpha', True)
                path = authored / 'evals' / member; path.parent.mkdir(exist_ok=True)
                path.write_text(text); raw = path.read_bytes(); read = evidence.read_bytes; reads = []
                def captured(target, *args, **kwargs):
                    result = read(target, *args, **kwargs)
                    if target == path:
                        reads.append(result)
                    return result
                with patch.object(evidence, 'read_bytes', side_effect=captured):
                    evidence.inventory(root)
                self.assertEqual(reads, [raw])
                def replaced(target, *args, **kwargs):
                    result = read(target, *args, **kwargs)
                    if target == path: path.write_text('invalid syntax !')
                    return result
                with patch.object(evidence, 'read_bytes', side_effect=replaced), \
                        self.assertRaisesRegex(ValueError, 'Input member changed'): evidence.inventory(root)
                path.write_text(text)
                def exhausted(target, *args, **kwargs):
                    if target == path: kwargs['budget'].remaining = 0
                    return read(target, *args, **kwargs)
                from skillevaluator.tier3 import evals_spec
                with patch.object(evidence, 'read_bytes', side_effect=exhausted), \
                        patch.object(evals_spec, '_run_file_checks') as validate:
                    with self.assertRaisesRegex(ValueError, 'Normalization byte limit'):
                        evidence.inventory(root)
                validate.assert_not_called()

    def test_inventory_source_markers_reject_before_authentication(self):
        from skillevaluator.tier3.harbor import adapter
        from skillevaluator.tier3 import output_provenance
        marker = output_provenance.GENERATED_OUTPUT_MARKER
        for imported, directory in itertools.product((False, True), (False, True)):
            with self.subTest(imported=imported, directory=directory), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); authored = self.local(root, 'alpha', True)
                if imported:
                    self.imported(root); authored = root / '.agents/skills/beta'
                marked = authored / 'nested'; marked.mkdir()
                target = marked / marker
                if directory: target.mkdir()
                else: target.write_text('untrusted marker')
                before = self.snapshot(root)
                with patch.object(adapter, '_runtime_skill_copy_ignore') as selector, \
                        patch.object(adapter, 'is_generated_output_root') as authenticate, \
                        patch.object(output_provenance, '_load_existing_key') as key:
                    with self.assertRaisesRegex(ValueError, 'Generated output inside inventory source'):
                        evidence.inventory(root)
                authenticate.assert_not_called(); key.assert_not_called()
                if not imported: selector.assert_not_called()
                self.assertEqual(self.snapshot(root), before)
                shutil.rmtree(marked)
                unrelated = root / 'generated'; unrelated.mkdir(); (unrelated / marker).write_text('unrelated')
                evidence.inventory(root)

    def test_inventory_marker_guard_uses_captured_tree_entries(self):
        from skillevaluator.tier3.harbor import adapter
        from skillevaluator.tier3.output_provenance import GENERATED_OUTPUT_MARKER
        for directory in (False, True):
            with self.subTest(directory=directory), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); authored = self.local(root, 'alpha')
                marker = authored / GENERATED_OUTPUT_MARKER
                if directory: marker.mkdir()
                else: marker.write_text('untrusted marker')
                with patch.object(Path, 'rglob', return_value=iter(())) as pathname_scan, \
                        patch.object(adapter, '_runtime_skill_copy_ignore') as selector:
                    with self.assertRaisesRegex(ValueError, 'Generated output inside inventory source'):
                        evidence.inventory(root)
                pathname_scan.assert_not_called(); selector.assert_not_called()

    def test_inventory_reads_retain_scanned_source_directories(self):
        from skillevaluator.tier3.harbor import adapter
        from skillevaluator.tier3 import output_provenance
        for imported, marked, nested in itertools.product((False, True), (False, True), (False, True)):
            with self.subTest(imported=imported, marked=marked, nested=nested), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); authored = self.local(root, 'alpha')
                if imported:
                    self.imported(root); authored = root / '.agents/skills/beta'
                target = authored / 'references' if nested else authored
                if nested: target.mkdir(); (target / 'original.md').write_text('scanned source')
                retained = root / 'retained'; scan = evidence.safe_tree; inventory = evidence.inventory
                output = root / 'rejected-output'; snapshots = []
                def replaced(path, **kwargs):
                    files = scan(path, **kwargs)
                    if path == authored and not retained.exists():
                        target.rename(retained); shutil.copytree(retained, target)
                        extra = output_provenance.GENERATED_OUTPUT_MARKER if marked else 'extra.md'
                        (target / extra).write_text('unscanned source')
                        snapshots.append(self.snapshot(root))
                    return files
                with patch.object(evidence, 'safe_tree', side_effect=replaced), \
                        patch.object(evidence, 'inventory', side_effect=lambda: inventory(root)), \
                        patch.object(adapter, '_runtime_skill_copy_ignore', return_value=lambda *_: set()) as selector, \
                        patch.object(adapter, 'is_generated_output_root') as authenticate, \
                        patch.object(output_provenance, '_load_existing_key') as key:
                    with self.assertRaisesRegex(ValueError, 'Input directory (?:entries )?changed'), redirect_stdout(StringIO()):
                        evidence.main(['inventory', '--output', str(output)])
                authenticate.assert_not_called(); key.assert_not_called()
                if not imported: selector.assert_not_called()
                self.assertFalse(output.exists()); self.assertEqual(self.snapshot(root), snapshots[0])

    def test_inventory_reads_retain_auxiliary_directory_identities(self):
        targets = ('.github/evals', '.agents/skills/github-actions-hardening',
                   '.apm/skills/alpha/evals/environment')
        for relative, empty in itertools.product(targets, (False, True)):
            with self.subTest(target=relative, empty=empty), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); authored = self.local(root, 'alpha', True)
                environment = authored / 'evals/environment'; environment.mkdir()
                (environment / 'Dockerfile').write_text('FROM scratch\n')
                for member in ('.agents/skills/gh', '.agents/skills/github-actions-hardening', '.github/evals/gh'):
                    shutil.copytree(REPO / member, root / member)
                shutil.copyfile(REPO / 'apm.lock.yaml', root / 'apm.lock.yaml')
                target = root / relative; retained = root / 'retained'; scan = evidence.safe_tree
                read = evidence.read_bytes
                def replace():
                    if not retained.exists():
                        target.rename(retained)
                        if empty: target.mkdir()
                        else: shutil.copytree(retained, target)
                        (target / 'extra.md').write_text('unscanned input')
                def scanned(path, **kwargs):
                    files = scan(path, **kwargs)
                    if path == target: replace()
                    return files
                def captured(path, *args, **kwargs):
                    raw = read(path, *args, **kwargs)
                    if relative.endswith('/environment') and path == authored / 'evals/evals.json': replace()
                    return raw
                with patch.object(evidence, 'safe_tree', side_effect=scanned), \
                        patch.object(evidence, 'read_bytes', side_effect=captured):
                    with self.assertRaisesRegex(ValueError, 'Input directory changed'):
                        evidence.inventory(root)
                self.assertTrue(retained.exists())

    def test_inventory_budget_rejects_before_capture_and_growth_validation(self):
        from skillevaluator.tier3 import evals_spec
        root = self.repo(); authored = root / '.apm/skills/alpha'; self.dataset(authored, 'alpha')
        path = authored / 'evals/grader.py'; path.write_text('# reward.json\n')
        before = self.snapshot(root); fdopen = evidence.os.fdopen; streams = []
        class Stream:
            def __init__(self, stream): self.stream = stream; self.reads = 0
            def __enter__(self): return self
            def __exit__(self, *args): self.stream.close()
            def fileno(self): return self.stream.fileno()
            def read(self, size): self.reads += 1; return self.stream.read(size)
        def tracked(*args, **kwargs):
            stream = Stream(fdopen(*args, **kwargs)); streams.append(stream); return stream
        read = evidence.read_bytes
        for growth in (False, True):
            with self.subTest(growth=growth):
                streams.clear(); fstat = evidence.os.fstat; target_info = path.stat()
                def changed_size(fd):
                    info = fstat(fd)
                    if growth and info.st_ino == target_info.st_ino and info.st_dev == target_info.st_dev:
                        fields = {k: getattr(info, k) for k in ('st_mode', 'st_nlink', 'st_size', 'st_ino', 'st_dev', 'st_uid', 'st_gid',
                                                              'st_mtime_ns', 'st_ctime_ns')}
                        fields['st_size'] -= 1
                        from types import SimpleNamespace
                        return SimpleNamespace(**fields)
                    return info
                def exhausted(target, *args, **kwargs):
                    if target == path: kwargs['budget'].remaining = path.stat().st_size - 1
                    return read(target, *args, **kwargs)
                with patch.object(evidence.os, 'fdopen', side_effect=tracked), \
                        patch.object(evidence.os, 'fstat', side_effect=changed_size), \
                        patch.object(evidence, 'read_bytes', side_effect=exhausted), \
                        patch.object(evals_spec, '_run_file_checks') as validate:
                    with self.assertRaisesRegex(ValueError, 'Input member changed' if growth else 'Normalization byte limit'):
                        evidence.inventory(root)
                self.assertEqual(streams[-1].reads, 0); validate.assert_not_called()
        self.assertEqual(self.snapshot(root), before)

    def test_inventory_per_file_limit_precedes_capture(self):
        root = self.repo(); path = root / '.apm/skills/alpha/README.md'
        with path.open('wb') as stream: stream.truncate(evidence.JSON_LIMIT + 1)
        with self.assertRaisesRegex(ValueError, 'oversized input'):
            evidence.inventory(root)

    def test_inventory_cli_rejects_real_aggregate_without_allocating_output(self):
        root = self.root / 'large-inventory'; alpha = self.local(root, 'alpha'); beta = self.local(root, 'beta')
        metadata_bytes = sum((p / 'SKILL.md').stat().st_size for p in (alpha, beta))
        for index in range(8):
            path = (alpha if index < 4 else beta) / f'file-{index}.bin'
            size = evidence.JSON_LIMIT - metadata_bytes if index == 7 else evidence.JSON_LIMIT
            with path.open('wb') as stream: stream.truncate(size)
        self.assertEqual(sum(p.stat().st_size for p in root.glob('.apm/skills/*/*')), evidence.NORMALIZATION_LIMIT)
        baseline = evidence.inventory(root)
        self.assertEqual(evidence.encoded(evidence.inventory(root)), evidence.encoded(baseline))
        with path.open('ab') as stream: stream.write(b'x')
        scripts = root / '.github/scripts'; scripts.mkdir(parents=True)
        for name in ('skill_evidence.py', 'skill_reports.py'):
            shutil.copyfile(REPO / '.github/scripts' / name, scripts / name)
        before = self.snapshot(root); output = self.root / 'inventory-rejected'
        cli = subprocess.run([sys.executable, str(scripts / 'skill_evidence.py'), 'inventory',
                              '--output', str(output)], capture_output=True, text=True)
        self.assertEqual(cli.returncode, 1); self.assertFalse(output.exists())
        self.assertEqual(cli.stderr, 'Evidence contract rejected (ValueError)\n')
        self.assertEqual(self.snapshot(root), before)

    def test_inventory_dataset_matches_pinned_strict_checks(self):
        from skillevaluator.tier3.evals_spec import validate_skillevaluators
        for kind in ('valid', 'empty', 'missing_prompt', 'missing_expected', 'duplicate_id',
                     'invalid_id', 'unknown_file', 'bad_dockerfile', 'bad_config', 'bad_grader'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                authored = self.local(Path(temp), 'alpha', True)
                path = authored / 'evals/evals.json'
                data = evidence.read_json(path)
                if kind == 'empty': data['evals'] = []
                elif kind == 'missing_prompt': del data['evals'][0]['prompt']
                elif kind == 'missing_expected': del data['evals'][0]['expected_output']
                elif kind == 'duplicate_id': data['evals'].append(copy.deepcopy(data['evals'][0]))
                elif kind == 'invalid_id': data['evals'][0]['id'] = '../escape'
                elif kind == 'unknown_file': (path.parent / 'unknown.txt').write_text('fixture')
                elif kind == 'bad_dockerfile':
                    (path.parent / 'environment').mkdir()
                    (path.parent / 'environment/Dockerfile').write_text('RUN invalid')
                elif kind == 'bad_config': (path.parent / 'config.yml').write_text('schema_version: 999')
                elif kind == 'bad_grader': (path.parent / 'grader.py').write_text('invalid syntax !')
                write(path, data)
                expected = all(check.status == 'ok' for check in validate_skillevaluators(authored))
                try:
                    suite = evidence.strict_dataset(path, 'alpha')
                    accepted = True
                    self.assertEqual(suite['authored_digest'], evidence.digest_bytes(path.read_bytes()))
                except ValueError:
                    accepted = False
                self.assertEqual(accepted, expected)

    def test_inventory_recognition_matches_pinned_entry_semantics(self):
        from skillevaluator.tier3 import evals_spec
        recognise = evals_spec._check_unrecognised
        for kind in ('known', 'hidden', 'environment_directory', 'unknown_file',
                     'unknown_directory', 'unknown_environment_file'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); authored = self.local(root, 'alpha', True)
                contents = {'config.yml': 'schema_version: 1\n', 'config.yaml': 'schema_version: 1\n',
                            'grader.py': '# reward.json\n', 'grader.sh': '# reward.txt\n', 'EVAL.md': '# Fixture\n',
                            'environment/Dockerfile': 'FROM scratch\n',
                            'environment/mcp_servers.toml': 'mcp_servers = []\n',
                            'environment/docker-compose.yaml': 'services: {}\n',
                            'environment/docker-compose.yml': 'services: {}\n',
                            'files/input.txt': 'fixture', 'harbor/task/input.txt': 'fixture',
                            'results/run/input.txt': 'fixture'}
                additions = {'hidden': ('.hidden.txt', '.hidden-dir/input.txt', '__pycache__/input.txt',
                                        'environment/.hidden.txt', 'environment/.git/input.txt',
                                        'environment/__pycache__/input.txt'),
                             'environment_directory': ('environment/seed/input.txt',),
                             'unknown_file': ('unknown.txt',),
                             'unknown_directory': ('unknown/input.txt',),
                             'unknown_environment_file': ('environment/unknown.txt',)}
                contents.update({name: 'fixture' for name in additions.get(kind, ())})
                for name, text in contents.items():
                    member = authored / 'evals' / name; member.parent.mkdir(parents=True, exist_ok=True)
                    member.write_text(text)
                expected = []; recognise(authored, expected)
                self.assertEqual(bool(expected), kind.startswith('unknown'))
                before = self.snapshot(root)
                def compared(target, checks):
                    observed = []; recognise(target, observed)
                    self.assertEqual(observed, expected); checks.extend(observed)
                with patch.object(evals_spec, '_check_unrecognised', side_effect=compared) as recognition:
                    if expected:
                        with self.assertRaisesRegex(ValueError, 'Strict dataset contract failed'):
                            evidence.inventory(root)
                    else:
                        self.assertEqual(evidence.inventory(root)['skills'][0]['suite']['case_ids'], ['1'])
                    recognition.assert_called_once()
                self.assertEqual(self.snapshot(root), before)

    def test_inventory_native_helpers_use_captured_path_membership(self):
        from skillevaluator.tier3 import evals_spec
        root = self.repo(); authored = root / '.apm/skills/alpha'; self.dataset(authored, 'alpha')
        (authored / 'evals/config.yaml').write_text('schema_version: 1\n')
        environment = authored / 'evals/environment'; environment.mkdir()
        (environment / 'Dockerfile').write_text('FROM scratch\n')
        before = self.snapshot(root)
        def bounded(helper):
            def run(*args):
                with patch.object(Path, 'exists', side_effect=AssertionError('Live native existence lookup')), \
                        patch.object(Path, 'is_dir', side_effect=AssertionError('Live native directory lookup')), \
                        patch.object(Path, 'iterdir', side_effect=AssertionError('Live native enumeration')):
                    return helper(*args)
            return run
        with patch.object(evals_spec, '_run_file_checks', side_effect=bounded(evals_spec._run_file_checks)), \
                patch.object(evals_spec, '_check_unrecognised', side_effect=bounded(evals_spec._check_unrecognised)):
            self.assertEqual(evidence.inventory(root)['skills'][0]['suite']['case_ids'], ['1'])
        self.assertEqual(self.snapshot(root), before)

    def test_inventory_recognition_rejects_substituted_tree_without_enumeration(self):
        from skillevaluator.tier3 import evals_spec
        for name in ('evals', 'evals/environment'):
            with self.subTest(directory=name), tempfile.TemporaryDirectory() as temp, patch.object(self, 'root', Path(temp)):
                root = self.repo(); authored = root / '.apm/skills/alpha'; self.dataset(authored, 'alpha')
                environment = authored / 'evals/environment'; environment.mkdir()
                (environment / 'Dockerfile').write_text('FROM scratch\n')
                target = authored / name; retained = self.root / 'retained'; output = self.root / 'rejected'
                recognise = evals_spec._check_unrecognised; inventory = evidence.inventory; snapshots = []
                def substituted(captured, checks):
                    target.rename(retained); target.mkdir()
                    for index in range(20): (target / f'unscanned-{index}.txt').write_text('replacement')
                    snapshots.append(self.snapshot(root))
                    with patch.object(Path, 'iterdir', side_effect=AssertionError('Replacement enumeration')) as listing:
                        recognise(captured, checks)
                        listing.assert_not_called()
                with patch.object(evals_spec, '_check_unrecognised', side_effect=substituted), \
                        patch.object(evidence, 'inventory', side_effect=lambda: inventory(root)), redirect_stdout(StringIO()):
                    with self.assertRaisesRegex(ValueError, 'Input directory (?:entries )?changed'):
                        evidence.main(['inventory', '--output', str(output)])
                self.assertEqual(len(snapshots), 1); self.assertTrue(retained.is_dir())
                self.assertFalse(output.exists()); self.assertEqual(self.snapshot(root), snapshots[0])

    def test_imported_owner_and_local_replacement(self):
        root = self.repo(); self.imported(root)
        before = next(r for r in evidence.inventory(root)['skills'] if r['source']['skill_id'] == 'beta')
        historical = evidence.evidence('beta', 'behavioral', ['1'], before['source'])
        frozen = evidence.encoded(historical)
        self.local(root, 'beta')
        with self.assertRaises(ValueError):
            evidence.inventory(root)
        (root / 'apm.lock.yaml').write_text(yaml.safe_dump({'dependencies': [], 'deployments': []}))
        after = next(r for r in evidence.inventory(root)['skills'] if r['source']['skill_id'] == 'beta')
        self.assertEqual(before['source']['skill_id'], after['source']['skill_id'])
        self.assertEqual(after['source']['owner'], 'local')
        self.assertEqual(after['suite']['owner'], 'overlay')
        evidence.project(historical)
        self.assertEqual(frozen, evidence.encoded(historical))
        self.assertEqual(historical['source']['owner'], 'upstream')

    def test_conflicting_datasets(self):
        root = self.repo(); path = self.local(root, 'alpha', True)
        self.dataset(root / '.github/evals/alpha', 'alpha')
        with self.assertRaises(ValueError):
            evidence.inventory(root)
        shutil.rmtree(root / '.github')
        write(path / 'evals/evals.jsonl', {})
        with self.assertRaises(ValueError):
            evidence.inventory(root)

    def test_inventory_overlay_discovery_rejects_transient_absence(self):
        for member in ('.github', '.github/evals'):
            with self.subTest(member=member), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); self.local(root, 'alpha'); self.imported(root)
                target = root / member; hidden = self.root / 'hidden-overlay'; before = self.snapshot(root)
                exists = Path.exists; changed = False
                def absent(path):
                    nonlocal changed
                    if path == root / '.github/evals':
                        target.rename(hidden); changed = True
                        try: return exists(path)
                        finally: hidden.rename(target)
                    return exists(path)
                with patch.object(Path, 'exists', absent):
                    try:
                        rows = evidence.inventory(root)['skills']
                    except ValueError:
                        self.assertTrue(changed)
                    else:
                        self.assertEqual({row['source']['skill_id'] for row in rows}, {'alpha', 'beta'})
                self.assertEqual(self.snapshot(root), before)

    def test_inventory_optional_presence_retains_parent_state(self):
        for member in ('.github', '.github/evals', 'apm.lock.yaml'):
            with self.subTest(member=member), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); self.local(root, 'alpha'); self.imported(root)
                target = root / member; hidden = self.root / 'hidden-optional'; before = self.snapshot(root)
                checked = os.stat; changed = False
                def absent(path, *args, **kwargs):
                    nonlocal changed
                    fd = kwargs.get('dir_fd')
                    if not changed and str(path) == target.name and fd is not None \
                            and (os.fstat(fd).st_dev, os.fstat(fd).st_ino) == (target.parent.stat().st_dev, target.parent.stat().st_ino):
                        target.rename(hidden); changed = True
                        try: return checked(path, *args, **kwargs)
                        finally: hidden.rename(target)
                    return checked(path, *args, **kwargs)
                with patch.object(os, 'stat', side_effect=absent), self.assertRaisesRegex(ValueError, 'Input directory entries changed'):
                    evidence.inventory(root)
                self.assertTrue(changed); self.assertEqual(self.snapshot(root), before)

    def test_dataset_format_discovery(self):
        for owner, formats in itertools.product(
                ('local', 'local_overlay', 'imported_overlay'),
                ((), ('json',), ('jsonl',), ('yaml',), ('json', 'jsonl'), ('jsonl', 'yaml'))):
            with self.subTest(owner=owner, formats=formats), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                authored = self.local(root, 'alpha')
                if owner == 'imported_overlay':
                    self.imported(root)
                    name = 'beta'
                    suite_root = root / '.github/evals/beta'
                    (suite_root / 'evals/evals.json').unlink()
                else:
                    name = 'alpha'
                    suite_root = authored if owner == 'local' else root / '.github/evals/alpha'
                for extension in formats:
                    if extension == 'json':
                        self.dataset(suite_root, name)
                    else:
                        write(suite_root / ('evals/evals.' + extension), {})
                if formats not in ((), ('json',)):
                    with self.assertRaises(ValueError):
                        evidence.inventory(root)
                else:
                    rows = evidence.inventory(root)['skills']
                    row = next((row for row in rows if row['source']['skill_id'] == name), None)
                    if owner == 'imported_overlay' and not formats:
                        self.assertIsNone(row)  # No overlay dataset means no imported target.
                    else:
                        self.assertEqual(row['behavioral_status'], 'configured' if formats else 'not_configured')
                        if formats:
                            self.assertEqual(row['suite']['owner'], 'local' if owner == 'local' else 'overlay')

    def test_partial_clones_never_fetch_missing_objects(self):
        def git(root, *args):
            return subprocess.run(['git', '-C', str(root), *args], check=True,
                                  capture_output=True, text=True, timeout=30).stdout.strip()
        origin = self.root / 'origin'
        origin.mkdir()
        self.local(origin, 'podman', True)
        git(origin, 'init', '-q')
        git(origin, 'add', '.apm')
        git(origin, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
            'commit', '-qm', 'Synthetic source')
        rev = git(origin, 'rev-parse', 'HEAD')
        blob = git(origin, 'rev-parse', 'HEAD:.apm/skills/podman/SKILL.md')
        tree = git(origin, 'rev-parse', 'HEAD^{tree}')
        root = self.native()
        self.mutate(root, '/run_config.json', lambda d: d['evaluated_source'].update(commit=rev))
        result_path = next((root / 'results/podman').glob('*/result.json'))
        result = evidence.read_json(result_path)
        result['run_config']['evaluated_source']['commit'] = rev
        write(result_path, result)
        self.mutate(root, '/provenance.json', lambda d: d.update(revision=rev))
        static = self.root / 'static-partial'; shutil.copytree(FIXTURES / 'static-synthetic', static)
        static_path = next((static / 'reports/podman').glob('*.json'))
        static_report = evidence.read_json(static_path)
        static_report['evaluated_source'] = {'repository': 'thetechgy/agent-engineering-baseline', 'commit': rev}
        write(static_path, static_report)
        for kind, oid in (('blob:none', blob), ('tree:0', tree)):
            with self.subTest(filter=kind):
                clone = self.root / kind.replace(':', '-')
                subprocess.run(['git', 'clone', '--no-checkout', '--filter=' + kind,
                                '--upload-pack=git -c uploadpack.allowFilter=true upload-pack',
                                origin.as_uri(), str(clone)], check=True, capture_output=True, timeout=30)
                self.assertTrue(list((clone / '.git/objects/pack').glob('*.promisor')))
                absent = subprocess.run(['git', '-C', str(clone), 'cat-file', '-e', oid],
                                        env={**os.environ, 'GIT_NO_LAZY_FETCH': '1'}, capture_output=True)
                self.assertNotEqual(absent.returncode, 0)
                git(clone, 'config', 'remote.origin.url', 'https://github.com/thetechgy/agent-engineering-baseline.git')
                trace = self.root / (clone.name + '-trace.jsonl')
                with patch.dict(os.environ, {'GIT_NO_LAZY_FETCH': '0'}), git_trace(trace):
                    self.assertEqual(evidence.git_revision(clone), rev)
                    contents = evidence.historical_content(clone, rev, '.apm/skills/podman')
                    data = evidence.normalize_behavioral(root, 'podman', workspace=clone)
                    scan = evidence.normalize_static(static, 'podman', workspace=clone)
                events = [json.loads(line) for line in trace.read_text().splitlines()]
                fetches = [event for event in events if event.get('event') == 'child_start'
                           and 'fetch' in event.get('argv', [])]
                self.assertEqual(fetches, [], 'Production object reads must not invoke fetch')
                self.assertIsNone(contents['digest'])
                self.assertEqual(contents['provenance'], 'unknown')
                self.assertIsNone(data['source']['content']['digest'])
                self.assertIsNone(scan['source']['content']['digest'])
                self.assertEqual(scan['availability']['status'], 'incomplete')
                self.assertIn('source_unavailable', scan['availability']['reasons'])
                self.assertIsNone(data['dataset']['authored_digest'])
                self.assertEqual(data['dataset']['authored_provenance'], 'unknown')
                self.assertIn('source_unavailable', data['availability']['reasons'])
                self.assertEqual(len(data['observations']), 20)
                evidence.project(data)

    def test_historical_blob_size_boundaries(self):
        root = self.native()
        for member, size in itertools.product(('SKILL.md', 'evals/evals.json'),
                                              (evidence.JSON_LIMIT, evidence.JSON_LIMIT + 1)):
            with self.subTest(member=member, size=size), tempfile.TemporaryDirectory() as temp:
                repo = Path(temp)
                authored = self.local(repo, 'podman', True)
                path = authored / member
                payload = path.read_bytes()
                path.write_bytes(payload + b' ' * (size - len(payload)))
                def git(*args):
                    return subprocess.run(['git', '-C', str(repo), *args], check=True,
                                          capture_output=True, text=True).stdout.strip()
                git('init', '-q')
                git('config', 'remote.origin.url', 'https://github.com/thetechgy/agent-engineering-baseline.git')
                git('add', '.apm')
                git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                    'commit', '-qm', 'Synthetic bounded source')
                rev = git('rev-parse', 'HEAD')
                oid = git('rev-parse', 'HEAD:' + path.relative_to(repo).as_posix())
                self.mutate(root, '/run_config.json', lambda d: d['evaluated_source'].update(commit=rev))
                self.mutate(root, '/result.json', lambda d: d['run_config']['evaluated_source'].update(commit=rev))
                self.mutate(root, '/provenance.json', lambda d: d.update(revision=rev))
                trace = repo / 'trace.jsonl'
                with patch.dict(os.environ, {'GIT_NO_LAZY_FETCH': '0'}), git_trace(trace):
                    if size > evidence.JSON_LIMIT:
                        with self.assertRaisesRegex(ValueError, 'Oversized historical blob'):
                            evidence.normalize_behavioral(root, 'podman', workspace=repo)
                    else:
                        data = evidence.normalize_behavioral(root, 'podman', workspace=repo)
                        if member == 'SKILL.md':
                            self.assertEqual(data['source']['content']['manifest'],
                                             [{'member': member, 'digest': evidence.digest_bytes(path.read_bytes())}])
                        else:
                            self.assertEqual(data['dataset']['authored_digest'], evidence.digest_bytes(path.read_bytes()))
                            self.assertEqual(data['dataset']['authored_provenance'], 'reconstructed_from_declared_revision')
                        evidence.project(data)
                events = [json.loads(line) for line in trace.read_text().splitlines()]
                commands = [event['argv'] for event in events if event.get('event') == 'start']
                spec = oid if member == 'SKILL.md' else rev + ':' + path.relative_to(repo).as_posix()
                self.assertTrue(any(argv[-3:] == ['cat-file', '-s', spec] for argv in commands))
                reads = [argv for argv in commands if argv[-3:] == ['cat-file', 'blob', spec]]
                self.assertEqual(len(reads), 0 if size > evidence.JSON_LIMIT else 1)
                self.assertFalse(any('show' in argv for argv in commands))
                self.assertFalse(any(event.get('event') == 'child_start' and 'fetch' in event.get('argv', [])
                                     for event in events))

    def test_historical_reads_ignore_replacement_refs(self):
        root = self.native()
        for kind in ('commit', 'tree', 'blob'):
            with self.subTest(replacement=kind), tempfile.TemporaryDirectory() as temp:
                repo = Path(temp)
                authored = self.local(repo, 'podman', True)
                def git(*args):
                    return subprocess.run(['git', '-C', str(repo), *args], check=True,
                                          capture_output=True, text=True).stdout.strip()
                def commit():
                    git('add', '.apm')
                    git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                        'commit', '-qm', 'Synthetic replacement fixture')
                    return git('rev-parse', 'HEAD')
                git('init', '-q')
                git('config', 'remote.origin.url', 'https://github.com/thetechgy/agent-engineering-baseline.git')
                rev = commit()
                skill_bytes = (authored / 'SKILL.md').read_bytes()
                dataset_bytes = (authored / 'evals/evals.json').read_bytes()
                specs = ['HEAD', 'HEAD:.apm/skills/podman', 'HEAD:.apm/skills/podman/SKILL.md',
                         'HEAD:.apm/skills/podman/evals/evals.json']
                original = [git('rev-parse', spec) for spec in specs]
                (authored / 'SKILL.md').write_text('Synthetic replacement source')
                write(authored / 'evals/evals.json', {'skill_name': 'podman', 'evals': []})
                replacement_rev = commit()
                replacement = [git('rev-parse', spec) for spec in specs]
                indexes = (0,) if kind == 'commit' else (1,) if kind == 'tree' else (2, 3)
                for index in indexes:
                    git('replace', original[index], replacement[index])
                self.mutate(root, '/run_config.json', lambda d: d['evaluated_source'].update(commit=rev))
                self.mutate(root, '/result.json', lambda d: d['run_config']['evaluated_source'].update(commit=rev))
                self.mutate(root, '/provenance.json', lambda d: d.update(revision=rev))
                trace = repo / 'trace.jsonl'
                with patch.dict(os.environ, {'GIT_NO_LAZY_FETCH': '0'}), git_trace(trace):
                    os.environ.pop('GIT_NO_REPLACE_OBJECTS', None)
                    self.assertEqual(evidence.git_revision(repo), replacement_rev)
                    contents = evidence.historical_content(repo, rev, '.apm/skills/podman')
                    self.assertEqual(contents['manifest'], [{'member': 'SKILL.md', 'digest': evidence.digest_bytes(skill_bytes)}])
                    data = evidence.normalize_behavioral(root, 'podman', workspace=repo)
                self.assertEqual(data['source']['revision'], rev)
                self.assertEqual(data['source']['content'], contents)
                self.assertEqual(data['dataset']['authored_digest'], evidence.digest_bytes(dataset_bytes))
                evidence.project(data)
                events = [json.loads(line) for line in trace.read_text().splitlines()]
                self.assertFalse(any(event.get('event') == 'child_start' and 'fetch' in event.get('argv', [])
                                     for event in events))

    def test_git_reads_ignore_inherited_repository_selectors(self):
        native = self.native()
        def git(repo, *args):
            return subprocess.run(['git', '-C', str(repo), *args], check=True,
                                  capture_output=True, text=True).stdout.strip()
        repos = []
        for name in ('requested', 'foreign'):
            repo = self.root / name; repo.mkdir()
            authored = self.local(repo, 'podman', True)
            with (authored / 'SKILL.md').open('a') as stream: stream.write(name)
            git(repo, 'init', '-q')
            git(repo, 'config', 'remote.origin.url', 'https://github.com/thetechgy/agent-engineering-baseline.git')
            git(repo, 'add', '.apm')
            git(repo, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                'commit', '-qm', name)
            repos.append(repo)
        repo, foreign = repos
        rev = git(repo, 'rev-parse', 'HEAD')
        linked = self.root / 'linked'
        git(repo, 'worktree', 'add', '--detach', str(linked), rev)
        self.mutate(native, '/run_config.json', lambda d: d['evaluated_source'].update(commit=rev))
        self.mutate(native, '/result.json', lambda d: d['run_config']['evaluated_source'].update(commit=rev))
        self.mutate(native, '/provenance.json', lambda d: d.update(revision=rev))
        settings = [
            {'GIT_DIR': str(foreign / '.git')},
            {'GIT_COMMON_DIR': str(foreign / '.git')},
            {'GIT_OBJECT_DIRECTORY': str(foreign / '.git/objects')},
            {'GIT_WORK_TREE': str(foreign), 'GIT_INDEX_FILE': str(foreign / '.git/index')},
            {'GIT_SHALLOW_FILE': str(self.root / 'absent-shallow'), 'GIT_GRAFT_FILE': str(self.root / 'absent-grafts')},
            {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'core.worktree', 'GIT_CONFIG_VALUE_0': str(foreign)},
        ]
        trace = self.root / 'selectors-trace.jsonl'
        for checkout, setting in itertools.product((repo, linked), settings):
            with self.subTest(linked=checkout == linked, selectors=list(setting)), \
                    patch.dict(os.environ, {**setting, 'GIT_NO_LAZY_FETCH': '0'}), git_trace(trace):
                self.assertEqual(evidence.git_revision(checkout), rev)
                inventory = evidence.inventory(checkout)
                self.assertEqual(inventory['skills'][0]['source']['revision'], rev)
                data = evidence.normalize_behavioral(native, 'podman', workspace=checkout)
                current = evidence.skill_content(checkout / '.apm/skills/podman')
                self.assertEqual(data['source']['content']['digest'], current['digest'])
                self.assertEqual(data['source']['content']['manifest'], current['manifest'])
                self.assertEqual(data['dataset']['authored_digest'], evidence.digest_bytes(
                    (checkout / '.apm/skills/podman/evals/evals.json').read_bytes()))
                evidence.project(data)
        events = [json.loads(line) for line in trace.read_text().splitlines()]
        self.assertFalse(any(event.get('event') == 'child_start' and 'fetch' in event.get('argv', [])
                             for event in events))

    def test_git_trace_destinations_do_not_mutate_inputs(self):
        repo = self.root / 'trace-repo'; repo.mkdir(); self.local(repo, 'podman', True)
        def git(*args):
            return subprocess.run(['git', '-C', str(repo), *args], check=True,
                                  capture_output=True, text=True).stdout.strip()
        git('init', '-q')
        git('config', 'remote.origin.url', 'https://github.com/thetechgy/agent-engineering-baseline.git')
        git('add', '.apm')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Trace fixture')
        rev = git('rev-parse', 'HEAD'); native = self.native()
        self.mutate(native, '/run_config.json', lambda d: d['evaluated_source'].update(commit=rev))
        self.mutate(native, '/result.json', lambda d: d['run_config']['evaluated_source'].update(commit=rev))
        self.mutate(native, '/provenance.json', lambda d: d.update(revision=rev))
        targets = (repo / 'trace.log', native / 'trace.log', self.root / 'external-trace.log')
        keys = ('GIT_TRACE', 'GIT_TRACE_SETUP', 'GIT_TRACE_PERFORMANCE', 'GIT_TRACE_REFS',
                'GIT_TRACE2', 'GIT_TRACE2_PERF', 'GIT_TRACE2_EVENT')
        for target, key in itertools.product(targets, keys):
            with self.subTest(destination=target.parent.name, key=key):
                target.write_text('Retained marker\n'); before_repo = self.snapshot(repo); before_input = self.snapshot(native)
                with patch.dict(os.environ, {key: str(target)}):
                    self.assertEqual(evidence.git_revision(repo), rev)
                    evidence.inventory(repo)
                    evidence.normalize_behavioral(native, 'podman', workspace=repo)
                self.assertEqual(target.read_text(), 'Retained marker\n')
                self.assertEqual(self.snapshot(repo), before_repo); self.assertEqual(self.snapshot(native), before_input)
        # Clearing environment targets must not fall back to global Trace2 configuration.
        config = self.root / 'trace-config'
        config.write_text('[trace2]\n' + ''.join(f'\t{key}Target = {targets[1]}\n' for key in ('normal', 'perf', 'event')))
        before = self.snapshot(native)
        with patch.dict(os.environ, {'GIT_CONFIG_GLOBAL': str(config), 'GIT_CONFIG_NOSYSTEM': '1'}):
            evidence.git_revision(repo); evidence.normalize_behavioral(native, 'podman', workspace=repo)
        self.assertEqual(self.snapshot(native), before)
        output = self.root / 'trace-cli-output'
        result = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
                                 'normalize', '--kind', 'behavioral', '--skill', 'podman',
                                 '--input', str(native), '--output', str(output)],
                                env={**os.environ, 'GIT_TRACE2_EVENT': str(targets[1])}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.snapshot(native), before)
        evidence.validate_public(evidence.read_json(output / 'public-report.json'))
        missing = native / 'never-create.trace'
        with patch.dict(os.environ, {'GIT_TRACE2_EVENT': str(missing)}): evidence.git_revision(repo)
        self.assertFalse(missing.exists())
        before = self.snapshot(native)
        with patch.dict(os.environ, {'GIT_TRACE2_EVENT': str(native)}): evidence.git_revision(repo)
        self.assertEqual(self.snapshot(native), before)  # Directory targets must not create per-process traces.

    def test_historical_source_requires_skill_directory_and_manifest(self):
        behavioral = self.native()
        static = self.root / 'static-root'; shutil.copytree(FIXTURES / 'static-synthetic', static)
        static_path = next((static / 'reports/podman').glob('*.json'))
        static_report = evidence.read_json(static_path)
        for kind in ('blob', 'no_manifest', 'manifest_directory', 'manifest_symlink', 'valid'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                repo = Path(temp); authored = repo / '.apm/skills/podman'
                authored.parent.mkdir(parents=True)
                if kind == 'blob': authored.write_text('Not a skill directory')
                else:
                    authored.mkdir()
                    (authored / 'README.md').write_text('Synthetic source')
                    if kind == 'manifest_directory':
                        (authored / 'SKILL.md').mkdir(); (authored / 'SKILL.md/file').write_text('Not a manifest')
                    elif kind == 'manifest_symlink': (authored / 'SKILL.md').symlink_to('README.md')
                    elif kind == 'valid': (authored / 'SKILL.md').write_text('Synthetic authored skill')
                def git(*args):
                    return subprocess.run(['git', '-C', str(repo), *args], check=True,
                                          capture_output=True, text=True).stdout.strip()
                git('init', '-q')
                git('config', 'remote.origin.url', 'https://github.com/thetechgy/agent-engineering-baseline.git')
                git('add', '.apm')
                git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                    'commit', '-qm', 'Historical root fixture')
                rev = git('rev-parse', 'HEAD')
                self.mutate(behavioral, '/run_config.json', lambda d: d['evaluated_source'].update(commit=rev))
                self.mutate(behavioral, '/result.json', lambda d: d['run_config']['evaluated_source'].update(commit=rev))
                self.mutate(behavioral, '/provenance.json', lambda d: d.update(revision=rev))
                static_report['evaluated_source'] = {'repository': 'thetechgy/agent-engineering-baseline', 'commit': rev}
                write(static_path, static_report)
                trace = self.root / (kind + '-root-trace.jsonl')
                with patch.dict(os.environ, {'GIT_NO_LAZY_FETCH': '0'}), git_trace(trace):
                    if kind != 'valid':
                        with self.assertRaises(ValueError): evidence.historical_content(repo, rev, '.apm/skills/podman')
                        with self.assertRaises(ValueError): evidence.normalize_behavioral(behavioral, 'podman', workspace=repo)
                        with self.assertRaises(ValueError): evidence.normalize_static(static, 'podman', workspace=repo)
                    else:
                        expected = evidence.skill_content(authored)
                        for data in (evidence.normalize_behavioral(behavioral, 'podman', workspace=repo),
                                     evidence.normalize_static(static, 'podman', workspace=repo)):
                            self.assertEqual(data['source']['content']['digest'], expected['digest'])
                            self.assertEqual(data['source']['content']['manifest'], expected['manifest'])
                            evidence.verify_source_snapshot(authored, data['source'])
                            evidence.project(data)
                events = [json.loads(line) for line in trace.read_text().splitlines()]
                if kind != 'valid':
                    self.assertFalse(any(e.get('event') == 'start' and 'cat-file' in e.get('argv', [])
                                         and any(arg in e['argv'] for arg in ('-s', 'blob')) for e in events))
                self.assertFalse(any(e.get('event') == 'child_start' and 'fetch' in e.get('argv', []) for e in events))

    def test_historical_revisions_require_exact_commit_objects(self):
        repo = self.root / 'object-types'; repo.mkdir(); authored = self.local(repo, 'podman', True)
        def git(*args):
            return subprocess.run(['git', '-C', str(repo), *args], check=True,
                                  capture_output=True, text=True).stdout.strip()
        git('init', '-q')
        git('config', 'remote.origin.url', 'https://github.com/thetechgy/agent-engineering-baseline.git')
        git('add', '.apm')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Object type fixture')
        commit = git('rev-parse', 'HEAD')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'tag', '-a', 'fixture', '-m', 'Annotated fixture')
        objects = (git('rev-parse', 'HEAD^{tree}'), git('rev-parse', 'HEAD:.apm/skills/podman/SKILL.md'),
                   git('rev-parse', 'fixture'))
        native = self.native(); run = next((native / 'results/podman').iterdir())
        config = evidence.read_json(run / 'run_config.json'); result = evidence.read_json(run / 'result.json')
        provenance = evidence.read_json(native / 'provenance.json')
        static = self.root / 'static-types'; shutil.copytree(FIXTURES / 'static-synthetic', static)
        static_path = next((static / 'reports/podman').glob('*.json')); report = evidence.read_json(static_path)
        for rev in objects:
            with self.subTest(revision=rev):
                config['evaluated_source']['commit'] = rev; result['run_config'] = config
                provenance['revision'] = rev
                write(run / 'run_config.json', config); write(run / 'result.json', result)
                write(native / 'provenance.json', provenance)
                report['evaluated_source'] = {'repository': 'thetechgy/agent-engineering-baseline', 'commit': rev}; write(static_path, report)
                trace = self.root / (rev + '.jsonl')
                with patch.dict(os.environ, {'GIT_NO_LAZY_FETCH': '0'}), git_trace(trace):
                    with self.assertRaisesRegex(ValueError, 'Historical revision must be a commit'):
                        evidence.historical_content(repo, rev, '.apm/skills/podman')
                    with self.assertRaisesRegex(ValueError, 'Historical revision must be a commit'):
                        evidence.historical_blob(repo, rev + ':.apm/skills/podman/evals/evals.json')
                    with self.assertRaisesRegex(ValueError, 'Historical revision must be a commit'):
                        evidence.normalize_behavioral(native, 'podman', workspace=repo)
                    with self.assertRaisesRegex(ValueError, 'Historical revision must be a commit'):
                        evidence.normalize_static(static, 'podman', workspace=repo)
                events = [json.loads(line) for line in trace.read_text().splitlines()]
                commands = [e['argv'] for e in events if e.get('event') == 'start']
                self.assertFalse(any('ls-tree' in argv or 'blob' in argv for argv in commands))
                self.assertFalse(any(e.get('event') == 'child_start' and 'fetch' in e.get('argv', []) for e in events))
        self.assertEqual(evidence.historical_content(repo, commit, '.apm/skills/podman')['digest'],
                         evidence.skill_content(authored)['digest'])
        dataset = authored / 'evals/evals.json'; dataset.unlink(); dataset.mkdir()
        (dataset / 'member.json').write_text('{}')
        git('add', '.apm'); git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                              'commit', '-qm', 'Directory at dataset path')
        with self.assertRaisesRegex(ValueError, 'Historical member must be a blob'):
            evidence.historical_blob(repo, git('rev-parse', 'HEAD') + ':.apm/skills/podman/evals/evals.json')

    def test_historical_tree_entry_limit_precedes_blob_reads(self):
        for entries in (1000, 1001):
            with self.subTest(entries=entries), tempfile.TemporaryDirectory() as temp:
                repo = Path(temp)
                authored = self.local(repo, 'podman')
                for index in range(entries - 1):
                    (authored / (str(index) + '.md')).write_text('Synthetic member')
                def git(*args):
                    return subprocess.run(['git', '-C', str(repo), *args], check=True,
                                          capture_output=True, text=True).stdout.strip()
                git('init', '-q')
                git('config', 'remote.origin.url', 'https://github.com/thetechgy/agent-engineering-baseline.git')
                git('add', '.apm')
                git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                    'commit', '-qm', 'Synthetic tree boundary')
                rev = git('rev-parse', 'HEAD')
                trace = repo / 'trace.jsonl'
                with patch.dict(os.environ, {'GIT_NO_LAZY_FETCH': '0'}), git_trace(trace):
                    if entries > 1000:
                        with self.assertRaisesRegex(ValueError, 'Historical tree listing limit'):
                            evidence.historical_content(repo, rev, '.apm/skills/podman')
                    else:
                        contents = evidence.historical_content(repo, rev, '.apm/skills/podman')
                        self.assertEqual(len(contents['manifest']), entries)
                        evidence.validate_content(contents)
                events = [json.loads(line) for line in trace.read_text().splitlines()]
                reads = [event for event in events if event.get('event') == 'start'
                         and 'cat-file' in event.get('argv', [])
                         and any(arg in event['argv'] for arg in ('-s', 'blob'))]
                self.assertEqual(len(reads), 0 if entries > 1000 else 2 * entries)
                self.assertFalse(any(event.get('event') == 'child_start' and 'fetch' in event.get('argv', [])
                                     for event in events))

    def test_historical_tree_byte_limit_precedes_parsing(self):
        repo = self.repo()
        def git(*args, input=None):
            return subprocess.run(['git', '-C', str(repo), *args], input=input, check=True,
                                  capture_output=True).stdout.strip()
        git('init', '-q')
        git('config', 'remote.origin.url', 'https://github.com/thetechgy/agent-engineering-baseline.git')
        blob = git('hash-object', '-w', '--stdin', input=b'Synthetic member')
        # Git plumbing can represent names too long for the local filesystem.
        tree = git('mktree', '-z', input=b'100644 blob ' + blob + b'\t' + b'a' * evidence.JSON_LIMIT + b'\0')
        root_tree = git('mktree', '-z', input=b'040000 tree ' + tree + b'\tpodman\0')
        rev = git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                  'commit-tree', root_tree.decode(), '-m', 'Synthetic listing byte boundary').decode()
        trace = repo / 'trace.jsonl'
        with patch.dict(os.environ, {'GIT_NO_LAZY_FETCH': '0'}), git_trace(trace):
            with self.assertRaisesRegex(ValueError, 'Historical tree listing limit'):
                evidence.historical_content(repo, rev, 'podman')
        events = [json.loads(line) for line in trace.read_text().splitlines()]
        self.assertFalse(any(event.get('event') == 'start' and 'cat-file' in event.get('argv', [])
                             and any(arg in event['argv'] for arg in ('-s', 'blob')) for event in events))

    def test_coverage_unknown_and_known_count_combinations(self):
        base = evidence.read_json(FIXTURES / 'gh-no-model.json')
        base['availability'].update(status='incomplete', reasons=['coverage_missing', 'execution_incomplete',
                                                                'case_details_missing', 'source_unavailable',
                                                                'metadata_missing'])
        base['policy']['attempts']['maximum'] = None
        base['policy']['id'] = evidence.identity({k: base['policy'][k] for k in
                                                ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
        for public in (False, True):
            # No observations/private identity fields: the same shape exercises
            # both validators without authenticating invented coverage as a run.
            data = copy.deepcopy(base)
            validate = evidence.validate_public if public else evidence.validate_evidence
            for expected, recorded, scored, unscored in itertools.product(
                    (None, 0, 10), (None, 0, 5, 10, 11), (None, 0, 5, 10, 11), (None, 0, 5, 10, 11)):
                valid = ((expected is None or all(v is None or v <= expected for v in (recorded, scored)))
                         and (unscored is None if recorded is None or scored is None
                              else scored <= recorded and unscored == recorded - scored))
                data['arms'][0]['coverage'].update(expected_attempts=expected, recorded_attempts=recorded,
                                                 scored_attempts=scored, unscored_attempts=unscored)
                with self.subTest(public=public, counts=(expected, recorded, scored, unscored)):
                    if valid:
                        validate(data)
                    else:
                        with self.assertRaises(ValueError):
                            validate(data)

    def test_all_overlapping_policy_and_arm_fields_agree(self):
        base = self.data(); self.synthetic_skill_references(base, 'podman')
        base['source']['content'] = evidence.content([
            {'member': 'SKILL.md', 'digest': evidence.digest_bytes(b'Synthetic')}], 'configured')
        base['availability'].update(status='complete', reasons=[])
        for key in ('environment', 'authorization_policy', 'fixture_boundary', 'workspace_mode'):
            values = (None, 'isolated', 'group') if key == 'workspace_mode' else (None, 'first', 'second')
            for selected, declared, observed in itertools.product(('with_skill', 'without_skill'), values, values):
                with self.subTest(key=key, arm=selected, declared=declared, observed=observed):
                    data = copy.deepcopy(base); data['policy']['fields'][key] = declared
                    data['policy']['id'] = evidence.identity({k: data['policy'][k] for k in
                        ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
                    for arm in data['arms']:
                        target = arm['condition'] if key == 'workspace_mode' else arm['condition']['execution']
                        target[key] = observed if arm['name'] == selected else declared
                        arm['condition']['id'] = evidence.identity({k: v for k, v in arm['condition'].items() if k != 'id'})
                    if declared is None or observed is None or declared == observed: self.project_grading_fixture(data)
                    else: self.assert_project_rejects(data, 'Arm condition policy mismatch')

    def test_task_source_policy_matches_native_and_projected_conditions(self):
        root = self.native(); run = next((root / 'results/podman').iterdir())
        config = evidence.read_json(run / 'run_config.json'); config['task_source'] = 'runtime_tasks'
        write(run / 'run_config.json', config)
        result = evidence.read_json(run / 'result.json'); result['run_config'] = config; write(run / 'result.json', result)
        provenance = evidence.read_json(root / 'provenance.json'); provenance['policy']['task_source'] = 'declared_tasks'
        write(root / 'provenance.json', provenance)
        with self.assertRaisesRegex(ValueError, 'Runtime/policy disagreement'):
            evidence.normalize_behavioral(root, 'podman')
        output = self.root / 'rejected-task-source'; before = self.snapshot(root)
        result = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'), 'normalize',
                                 '--kind', 'behavioral', '--skill', 'podman', '--input', str(root),
                                 '--output', str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1); self.assertFalse(output.exists()); self.assertEqual(self.snapshot(root), before)
        for declared, observed in itertools.product((None, 'native_harbor', 'other_tasks'), repeat=2):
            with self.subTest(declared=declared, observed=observed):
                data = evidence.read_json(FIXTURES / 'gh-no-model.json')
                data['policy']['fields']['task_source'] = declared
                data['policy']['id'] = evidence.identity({k: data['policy'][k] for k in
                    ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
                for arm in data['arms']:
                    arm['condition']['execution']['task_source'] = observed
                    arm['condition']['id'] = evidence.identity({k: v for k, v in arm['condition'].items() if k != 'id'})
                if declared is None or observed is None or declared == observed: evidence.project(data)
                else: self.assert_project_rejects(data, 'Task source policy mismatch')

    def test_trial_task_case_matches_reward_and_summary(self):
        root = self.native(); run = next((root / 'results/podman').iterdir())
        for arm, known_case, has_reward in itertools.product(('with-skill', 'without-skill'), (True, False), (True, False)):
            with self.subTest(arm=arm, known_case=known_case, reward=has_reward):
                path = next((run / 'codex' / arm / 'trials').glob('*/result.json'))
                original = evidence.read_json(path); reward_path = path.parent / 'reward.json'
                reward_bytes = reward_path.read_bytes(); case = evidence.parse_json(reward_bytes)['entry_id']
                changed = copy.deepcopy(original)
                changed['task_name'] = 'nvidia/skillevaluator-' + ('2' if case == '1' else '1') if known_case else 'nvidia/skillevaluator-999'
                write(path, changed)
                if not has_reward: reward_path.unlink()
                with self.assertRaisesRegex(ValueError, 'Trial task case identity mismatch'):
                    evidence.normalize_behavioral(root, 'podman')
                before = self.snapshot(root); output = self.root / f'rejected-task-{arm}-{known_case}-{has_reward}'
                result = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'), 'normalize',
                                         '--kind', 'behavioral', '--skill', 'podman', '--input', str(root),
                                         '--output', str(output)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 1); self.assertFalse(output.exists()); self.assertEqual(self.snapshot(root), before)
                write(path, original); reward_path.write_bytes(reward_bytes)
        baseline = evidence.normalize_behavioral(root, 'podman')
        for path in run.glob('codex/*/trials/*/result.json'):
            native = evidence.read_json(path); native['task_name'] += '-attempt1'; write(path, native)
        suffixed = evidence.normalize_behavioral(root, 'podman')
        self.assertEqual(suffixed['metrics'], baseline['metrics'])
        self.assertEqual([row['id'] for row in suffixed['observations']], [row['id'] for row in baseline['observations']])

    def test_reward_identity_matches_native_run(self):
        root = self.native(); run = next((root / 'results/podman').iterdir())
        for arm, key, replacement in itertools.product(('with-skill', 'without-skill'),
                ('agent', 'model', 'metric_set'), ('different_identity',)):
            with self.subTest(arm=arm, key=key):
                path = next((run / 'codex' / arm / 'trials').glob('*/reward.json'))
                original = evidence.read_json(path); changed = copy.deepcopy(original); changed[key] = replacement
                write(path, changed)
                with self.assertRaisesRegex(ValueError, 'Reward identity mismatch'):
                    evidence.normalize_behavioral(root, 'podman')
                before = self.snapshot(root); output = self.root / f'rejected-{arm}-{key}'
                result = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'), 'normalize',
                                         '--kind', 'behavioral', '--skill', 'podman', '--input', str(root),
                                         '--output', str(output)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 1); self.assertFalse(output.exists()); self.assertEqual(self.snapshot(root), before)
                write(path, original)
        baseline = evidence.normalize_behavioral(root, 'podman')
        for path in run.glob('codex/*/trials/*/reward.json'):
            reward = evidence.read_json(path)
            for key in ('agent', 'model', 'metric_set'): reward.pop(key, None)
            write(path, reward)
        missing = evidence.normalize_behavioral(root, 'podman')
        self.assertEqual(missing['metrics'], baseline['metrics'])
        self.assertEqual([row['id'] for row in missing['observations']], [row['id'] for row in baseline['observations']])

    def test_policy_runtime_contradictions(self):
        conflicts = {'evaluator_revision': 'b' * 40, 'harbor': '0.12.0', 'docker_compose': '4.0.0',
                     'python': '3.12', 'model': 'other-model', 'provider': 'other-provider',
                     'grading': 'default_plus_custom', 'environment': 'other-environment',
                     'concurrency': 3, 'timeout_multiplier': 3.0, 'stop_on_pass': True}
        for field, value in conflicts.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / 'native'
                shutil.copytree(FIXTURES / 'podman-native', root)
                (root / 'extract-manifest.json').unlink()
                self.mutate(root, '/provenance.json', lambda d: d['policy'].update({field: value}))
                with self.assertRaises(ValueError):
                    evidence.normalize_behavioral(root, 'podman')

    def assert_native_cli_rejects(self, root):
        before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        output = root.parent / 'rejected-output'
        result = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
                                 'normalize', '--kind', 'behavioral', '--skill', 'podman',
                                 '--input', str(root), '--output', str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, 'Evidence contract rejected (ValueError)\n')
        self.assertFalse(output.exists())
        self.assertEqual(before, {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_native_summary_agent_and_model_identity(self):
        for arm, field, declared in itertools.product(
                ('with-skill', 'without-skill'), ('agent', 'model'), (True, False)):
            with self.subTest(arm=arm, field=field, declared=declared), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / 'native'; shutil.copytree(FIXTURES / 'podman-native', root)
                (root / 'extract-manifest.json').unlink()
                run = next((root / 'results/podman').iterdir())
                summary_path = run / 'codex' / arm / 'summary.json'
                summary = evidence.read_json(summary_path)
                summary[field] = 'different-identity'; write(summary_path, summary)
                if not declared:
                    self.mutate(root, '/provenance.json', lambda d: d['policy'].pop('model'))
                with self.assertRaisesRegex(ValueError, 'Native .* identity mismatch'):
                    evidence.normalize_behavioral(root, 'podman')
                self.assert_native_cli_rejects(root)
        root = self.native()
        for summary_path in root.rglob('summary.json'):
            summary = evidence.read_json(summary_path)
            summary.pop('model'); summary.pop('agent'); write(summary_path, summary)
        data = evidence.normalize_behavioral(root, 'podman')
        self.assertEqual(len(data['observations']), 20)
        self.assertEqual(data['policy']['fields']['model'], 'gpt-5.6-sol')

    def test_native_aggregate_and_summary_pass_data_agree(self):
        for arm, field in itertools.product(('with_skill', 'without_skill'), ('passed_cases', 'rate', 'k', 'case_score')):
            with self.subTest(arm=arm, field=field), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / 'native'; shutil.copytree(FIXTURES / 'podman-native', root)
                (root / 'extract-manifest.json').unlink()
                run = next((root / 'results/podman').iterdir())
                path = run / 'result.json'; result = evidence.read_json(path)
                carrier = result['agents']['codex']['pass_at_k'][arm]
                if field == 'case_score': next(iter(carrier['cases'].values()))['attempts'][0]['score'] = 0
                else: carrier[field] = 0
                write(path, result)
                with self.assertRaisesRegex(ValueError, 'Conflicting native pass data'):
                    evidence.normalize_behavioral(root, 'podman')
                self.assert_native_cli_rejects(root)
        root = self.native(); run = next((root / 'results/podman').iterdir())
        path = run / 'result.json'; result = evidence.read_json(path)
        result['agents']['codex'].pop('pass_at_k'); write(path, result)
        self.assertEqual(len(evidence.normalize_behavioral(root, 'podman')['observations']), 20)

    def test_native_dataset_digest_algorithm_agrees(self):
        root = self.native(); run = next((root / 'results/podman').iterdir())
        path = run / 'result.json'; result = evidence.read_json(path)
        result['dataset_digest_algorithm'] = 'different-algorithm'; write(path, result)
        with self.assertRaisesRegex(ValueError, 'Snapshot/result algorithm mismatch'):
            evidence.normalize_behavioral(root, 'podman')
        self.assert_native_cli_rejects(root)
        result.pop('dataset_digest_algorithm'); write(path, result)
        data = evidence.normalize_behavioral(root, 'podman')
        self.assertEqual(data['dataset']['staged_algorithm'], 'skill-evaluator-dataset-snapshot/1')

    def test_native_rubric_threshold_matches_attempt_policy(self):
        root = self.native(); run = next((root / 'results/podman').iterdir())
        path = run / 'attempt_policy.json'; policy = evidence.read_json(path)
        policy['pass_threshold'] = 0.9; write(path, policy)
        with self.assertRaisesRegex(ValueError, 'Rubric attempt-policy threshold mismatch'):
            evidence.normalize_behavioral(root, 'podman')
        self.assert_native_cli_rejects(root)
        data = self.data(); data['policy']['attempts']['pass_threshold'] = 0.9
        data['policy']['id'] = evidence.identity({k: data['policy'][k] for k in
            ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
        self.assert_project_rejects(data, 'Rubric attempt-policy threshold mismatch')

    def test_native_execution_error_arrays_and_cardinality(self):
        root = self.native(); run = next((root / 'results/podman').iterdir())
        result_path = run / 'result.json'; result_original = evidence.read_json(result_path)
        for arm in ('with_skill', 'without_skill'):
            summary_path = run / 'codex' / arm.replace('_', '-') / 'summary.json'
            summary_original = evidence.read_json(summary_path)
            for errors in ('failed', {'error': 'failed'}, None, True, [False], [{}], [1]):
                with self.subTest(arm=arm, errors=errors):
                    result = copy.deepcopy(result_original); result['report_status'] = 'incomplete'
                    result['agents']['codex']['conditions'][arm].update(execution_status='failed', execution_errors=errors)
                    summary = copy.deepcopy(summary_original); summary.update(execution_status='failed', execution_errors=errors)
                    write(result_path, result); write(summary_path, summary)
                    with self.assertRaisesRegex(ValueError, 'Invalid native execution errors'):
                        evidence.normalize_behavioral(root, 'podman')
                    before = self.snapshot(root); output = self.root / 'rejected-output'
                    cli = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
                        'normalize', '--kind', 'behavioral', '--skill', 'podman', '--input', str(root),
                        '--output', str(output)], capture_output=True, text=True)
                    self.assertEqual(cli.returncode, 1); self.assertFalse(output.exists())
                    self.assertEqual(cli.stderr, 'Evidence contract rejected (ValueError)\n')
                    self.assertEqual(self.snapshot(root), before)
            result = copy.deepcopy(result_original); result['report_status'] = 'incomplete'
            result['agents']['codex']['conditions'][arm].update(execution_status='failed', execution_errors=['first', 'second'])
            summary = copy.deepcopy(summary_original); summary.update(execution_status='failed', execution_errors=['first'])
            write(result_path, result); write(summary_path, summary)
            with self.assertRaisesRegex(ValueError, 'Conflicting native error count'):
                evidence.normalize_behavioral(root, 'podman')
            # The actual pinned loader appends job/trial failures to the arm's summary errors.
            summary.update(job_failure='Synthetic job failure',
                trial_failures=[{'trial': 'fixture', 'reason': 'Synthetic failure'}])
            write(summary_path, summary)
            from skillevaluator.tier3.harbor.report_data import load_agent_data
            loader_root = self.root / 'loader'
            for variant in ('with_skill', 'without_skill'):
                loader_summary = evidence.read_json(run / 'codex' / variant.replace('_', '-') / 'summary.json')
                # Reviewed extracts omit scores; the production loader requires their carrier.
                loader_summary['scores'] = {}
                write(loader_root / 'codex' / variant.replace('_', '-') / 'summary.json', loader_summary)
            native_errors = load_agent_data(loader_root)['codex']['conditions'][arm]['execution_errors']
            self.assertEqual(len(native_errors), 3)
            result['agents']['codex']['conditions'][arm]['execution_errors'] = native_errors; write(result_path, result)
            data = evidence.normalize_behavioral(root, 'podman')
            self.assertEqual(next(row for row in data['arms'] if row['name'] == arm)['execution_error_count'], 3)
            self.assertEqual(data['metrics'], self.data()['metrics'])
            write(result_path, result_original); write(summary_path, summary_original)

    def test_shared_rubric_threshold_known_unknown_combinations(self):
        for policy_threshold, rubric_threshold in itertools.product((None, 0.5, 0.9), repeat=2):
            with self.subTest(policy=policy_threshold, rubric=rubric_threshold):
                data = evidence.read_json(FIXTURES / 'gh-no-model.json')
                data['policy']['attempts']['pass_threshold'] = policy_threshold
                data['policy']['id'] = evidence.identity({k: data['policy'][k] for k in
                    ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
                for arm in data['arms']: arm['rubric']['threshold'] = rubric_threshold
                if policy_threshold is None or rubric_threshold is None or policy_threshold == rubric_threshold:
                    evidence.project(data)
                else:
                    with self.assertRaisesRegex(ValueError, 'Rubric attempt-policy threshold mismatch'):
                        evidence.project(data)

    def test_runtime_observations_against_supplied_policy(self):
        config_changes = (
            ('provider', 'model', 'other-model'), ('provider', 'name', 'other-provider'),
            ('grading', 'mode', 'default_plus_custom'), ('harbor', 'n_concurrent', 3),
            ('harbor', 'timeout_multiplier', 3.0), ('harbor', 'stop_on_pass', True),
        )
        for section, key, value in config_changes:
            with self.subTest(section=section, key=key), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / 'native'
                shutil.copytree(FIXTURES / 'podman-native', root)
                (root / 'extract-manifest.json').unlink()
                run = next((root / 'results/podman').iterdir())
                config = evidence.read_json(run / 'run_config.json')
                config[section][key] = value
                write(run / 'run_config.json', config)
                result = evidence.read_json(run / 'result.json')
                result['run_config'] = config
                write(run / 'result.json', result)
                with self.assertRaises(ValueError):
                    evidence.normalize_behavioral(root, 'podman')
        root = self.native()
        self.mutate(root, '/versions.json', lambda d: d.update(evaluator_revision='b' * 40))
        with self.assertRaises(ValueError):
            evidence.normalize_behavioral(root, 'podman')
        self.mutate(root, '/versions.json', lambda d: d.update(evaluator_revision=evidence.reports.POLICY['evaluator_revision']))
        result = next((root / 'results/podman').glob('*/result.json'))
        self.mutate(root, '/' + result.parent.name + '/result.json',
                    lambda d: d['agents']['codex'].update(model='other-model'))
        with self.assertRaises(ValueError):
            evidence.normalize_behavioral(root, 'podman')

    def test_missing_runtime_metadata_and_attempt_fallback(self):
        root = self.native()
        self.mutate(root, '/versions.json', lambda d: d.clear())
        data = evidence.normalize_behavioral(root, 'podman')
        self.assertIn('metadata_missing', data['availability']['reasons'])
        self.assertEqual(data['policy']['fields']['python'], '3.13')  # Preserve declared policy.
        run = next((root / 'results/podman').iterdir())
        config = evidence.read_json(run / 'run_config.json')
        for key in ('n_attempts', 'stop_on_pass', 'n_concurrent', 'environment'):
            config['harbor'].pop(key)
        config.pop('provider')
        config.pop('grading')
        write(run / 'run_config.json', config)
        result = evidence.read_json(run / 'result.json')
        result['run_config'] = config
        write(run / 'result.json', result)
        data = evidence.normalize_behavioral(root, 'podman')
        self.assertEqual(data['policy']['attempts']['maximum'], 1)
        self.assertIs(data['policy']['attempts']['stop_on_pass'], False)
        evidence.project(data)
        (root / 'provenance.json').unlink()
        self.mutate(root, '/attempt_policy.json', lambda d: d.update(stop_on_pass=True))
        config['harbor']['stop_on_pass'] = False
        write(run / 'run_config.json', config)
        result['run_config'] = config
        write(run / 'result.json', result)
        with self.assertRaises(ValueError):
            evidence.normalize_behavioral(root, 'podman')  # Native disagreement also fails without policy.
        static = self.root / 'static'
        shutil.copytree(FIXTURES / 'static-synthetic', static)
        self.mutate(static, '/versions.json', lambda d: d.pop('evaluator_revision'))
        data = evidence.normalize_static(static, 'podman')
        self.assertIsNone(data['policy']['fields']['evaluator_revision'])
        evidence.project(data)

    def test_native_stop_on_pass_disagreement(self):
        root = self.native()
        self.mutate(root, '/attempt_policy.json', lambda d: d.update(stop_on_pass=True))
        with self.assertRaises(ValueError):
            evidence.normalize_behavioral(root, 'podman')

    def test_static_evaluator_revision(self):
        root = self.root / 'static'
        shutil.copytree(FIXTURES / 'static-synthetic', root)
        self.mutate(root, '/versions.json', lambda d: d.update(evaluator_revision='b' * 40))
        with self.assertRaises(ValueError):
            evidence.normalize_static(root, 'podman')

    def test_compatible_python_precision_and_historical_policy(self):
        root = self.native()
        for python in ('3', '3.13', '3.13.15'):
            with self.subTest(python=python):
                self.mutate(root, '/provenance.json', lambda d: d['policy'].update(python=python))
                data = evidence.normalize_behavioral(root, 'podman')
                self.assertEqual(data['policy']['fields']['python'], python)
                evidence.project(data)
        self.mutate(root, '/provenance.json', lambda d: d['policy'].update(timeout_multiplier=2))
        evidence.project(evidence.normalize_behavioral(root, 'podman'))
        self.mutate(root, '/provenance.json', lambda d: d['policy'].update(python='3.13.14'))
        with self.assertRaises(ValueError):
            evidence.normalize_behavioral(root, 'podman')
        self.mutate(root, '/versions.json', lambda d: d.update(harbor='0.12.0', docker_compose='4.0.0'))
        self.mutate(root, '/provenance.json', lambda d: d['policy'].update(
            harbor='0.12.0', docker_compose='4.0.0', python='3.13', model='historical-model'))
        run = next((root / 'results/podman').iterdir())
        config = evidence.read_json(run / 'run_config.json')
        config['provider']['model'] = config['agents']['codex']['model'] = 'historical-model'
        write(run / 'run_config.json', config)
        result = evidence.read_json(run / 'result.json')
        result['run_config'] = config
        result['agents']['codex']['model'] = 'historical-model'
        write(run / 'result.json', result)
        for summary_path in run.rglob('summary.json'):
            summary = evidence.read_json(summary_path); summary['model'] = 'historical-model'
            write(summary_path, summary)
        for reward_path in run.glob('codex/*/trials/*/reward.json'):
            reward = evidence.read_json(reward_path); reward['model'] = 'historical-model'
            write(reward_path, reward)
        data = evidence.normalize_behavioral(root, 'podman')
        self.assertEqual(data['policy']['fields']['harbor'], '0.12.0')
        self.assertEqual(data['policy']['fields']['model'], 'historical-model')
        self.assertEqual(data['policy']['judge']['model'], 'gpt-5.6-sol')
        evidence.project(data)

    def test_ambiguous_owner_and_deployment_drift(self):
        for mutation in ('owner', 'hash', 'deployment', 'revision'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); self.local(root, 'alpha'); lock = self.imported(root)
                if mutation == 'owner':
                    lock['dependencies'].append(copy.deepcopy(lock['dependencies'][0]))
                elif mutation == 'hash':
                    next((root / '.agents').rglob('SKILL.md')).write_text('Drift')
                elif mutation == 'deployment':
                    lock['deployments'][0]['owners'].append('other/owner')
                else:
                    lock['dependencies'][0]['resolved_commit'] = 'bad'
                (root / 'apm.lock.yaml').write_text(yaml.safe_dump(lock))
                with self.assertRaises(ValueError):
                    evidence.inventory(root)

    def test_unsafe_source_trees(self):
        for kind in ('link', 'hardlink', 'fifo'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); path = self.local(root, 'alpha')
                target = path / 'unsafe'
                if kind == 'link': target.symlink_to(path / 'SKILL.md')
                elif kind == 'hardlink': os.link(path / 'SKILL.md', target)
                else: os.mkfifo(target)
                with self.assertRaises(ValueError):
                    evidence.inventory(root)

    def test_malformed_metadata_and_case_collisions(self):
        root = self.repo(); path = root / '.apm/skills/alpha'
        (path / 'SKILL.md').write_text('---\nname: beta\ndescription: Fixture\n---\n')
        with self.assertRaises(ValueError): evidence.inventory(root)
        self.local(root, 'alpha', True)
        for invalid in ([1, '1'], ['Case', 'case'], ['../escape'], [True]):
            with self.subTest(invalid=invalid):
                write(path / 'evals/evals.json', {'skill_name': 'alpha', 'evals': [
                    {'id': i, 'prompt': 'Synthetic', 'expected_output': 'Synthetic'} for i in invalid]})
                with self.assertRaises(ValueError): evidence.inventory(root)

    def test_escaping_fixture_reference(self):
        root = self.repo(); path = root / '.apm/skills/alpha'
        self.dataset(path, 'alpha')
        self.mutate(root, '/evals/evals.json', lambda d: d['evals'][0].update(files=['../outside']))
        with self.assertRaises(ValueError): evidence.inventory(root)

    def test_exact_podman_observations(self):
        data = self.data()
        self.assertEqual([r['value'] for r in data['metrics']], [0.1207, 0.7730, 0.9600, 0.6937])
        self.assertEqual(len(data['observations']), 20)
        self.assertEqual({o['case_id'] for o in data['observations'] if o['arm'] == 'with_skill'},
                         {o['case_id'] for o in data['observations'] if o['arm'] == 'without_skill'})
        self.assertEqual([a['rubric']['passed_cases'] for a in data['arms']], [10, 8])
        self.assertEqual([o['score'] for o in data['observations'] if o['case_id'] == '2'], [0.6896, 0.7242])
        self.assertEqual(data['dataset']['staged_digest'], 'sha256:cecc0bcea480a3c197e1b4c527009958ada3be67eb0205325f6c16123f9355fe')
        self.assertEqual(data['policy']['patch_digest'], 'sha256:d48af476c19f06d94297e2e143f4643c74580abbcd631a599fe7b296244f3962')
        self.assertNotEqual(data['policy']['patch_digest'], evidence.digest_bytes((REPO / evidence.reports.PATCH).read_bytes()))
        # A shallow CI checkout need not contain the historical Git objects.
        if data['source']['content']['digest'] is None:
            self.assertEqual(data['source']['content']['provenance'], 'unknown')
            self.assertIn('source_unavailable', data['availability']['reasons'])
        else:
            self.assertEqual(data['source']['content']['provenance'], 'reconstructed_from_declared_revision')
            self.assertEqual(data['availability']['status'], 'complete')
        evidence.validate_public(evidence.project(data))

    def test_no_invented_gh_model_run(self):
        data = evidence.read_json(FIXTURES / 'gh-no-model.json'); evidence.validate_evidence(data)
        self.assertEqual(len(data['dataset']['case_ids']), 24)
        self.assertIsNone(data['run_id']); self.assertEqual(data['observations'], [])
        self.assertEqual(data['availability'], {'status': 'unavailable', 'reasons': ['results_not_supplied'], 'provenance': 'unknown'})
        self.assertEqual(data['arms'][0]['condition']['competing_skills'][0]['revision'], '143a3d976b3c1603cc8932984d5e1f28501cb5fc')
        for arm in data['arms']:
            self.assertIsNone(arm['coverage']['recorded_attempts'])
        data['arms'][0]['coverage']['recorded_attempts'] = 24
        with self.assertRaises(ValueError): evidence.project(data)

    def test_stable_identity_and_order(self):
        first = self.data(); self.assertEqual(evidence.encoded(first), evidence.encoded(self.data()))
        root = self.native()
        summaries = list(root.rglob('summary.json'))
        for p in summaries:
            data = evidence.read_json(p); data['pass_at_k']['cases'] = dict(reversed(list(data['pass_at_k']['cases'].items())))
            write(p, data)
        second = evidence.normalize_behavioral(root, 'podman')
        self.assertEqual([o['id'] for o in first['observations']], [o['id'] for o in second['observations']])
        self.assertEqual([o['native_id'] for o in first['observations']], [o['native_id'] for o in second['observations']])

    def test_policy_and_condition_identities_are_independent(self):
        data = evidence.read_json(FIXTURES / 'gh-no-model.json')
        target = data['source']['content']['digest']; dataset = data['dataset']['authored_digest']
        original = data['arms'][0]['condition']
        for key, value in [('instruction_digest', 'sha256:' + 'a'*64), ('build_digest', 'sha256:' + 'b'*64), ('fixture_digest', 'sha256:' + 'c'*64)]:
            cond = copy.deepcopy(original); cond[key] = value
            cond['id'] = evidence.identity({k:v for k,v in cond.items() if k != 'id'}); evidence.validate_condition(cond)
            self.assertNotEqual(cond['id'], original['id'])
        cond = copy.deepcopy(original); cond['execution']['base_image_mode'] = 'disabled'
        cond['id'] = evidence.identity({k:v for k,v in cond.items() if k != 'id'}); self.assertNotEqual(cond['id'], original['id'])
        cond = copy.deepcopy(original); cond['competing_skills'][0]['revision'] = 'c'*40
        cond['id'] = evidence.identity({k:v for k,v in cond.items() if k != 'id'}); self.assertNotEqual(cond['id'], original['id'])
        policy = copy.deepcopy(data['policy']); policy['fields']['competing_revision'] = 'c'*40
        policy['id'] = evidence.identity({k:policy[k] for k in ('fields','patch_digest','metric_set','judge','attempts')})
        evidence.validate_policy(policy); self.assertNotEqual(policy['id'], data['policy']['id'])
        self.assertEqual(target, data['source']['content']['digest']); self.assertEqual(dataset, data['dataset']['authored_digest'])

    def test_expired_references_cannot_promote(self):
        data = self.data(); data['references'][0]['availability'] = 'expired'
        with self.assertRaises(ValueError): evidence.project(data)
        data['availability'].update(status='incomplete',
                                    reasons=sorted(set(data['availability']['reasons']) | {'reference_expired'}))
        evidence.project(data)
        with self.assertRaises(ValueError): evidence.verify_reference(self.root, data['references'][0])

    def test_reviewed_extract_requires_pinned_manifest_identity(self):
        root = self.root / 'forged'; shutil.copytree(FIXTURES / 'podman-native', root)
        manifest_path = root / 'extract-manifest.json'; manifest = evidence.read_json(manifest_path)
        result_path = next(root.glob('results/podman/*/result.json'))
        native = evidence.read_json(result_path); native['untrusted_claim'] = 'self-reviewed replacement'
        write(result_path, native)
        member = result_path.relative_to(root).as_posix()
        row = next(row for row in manifest['members'] if row['member'] == member)
        row.update(extract_digest=evidence.digest_bytes(result_path.read_bytes()), original_digest='sha256:' + 'a'*64)
        write(manifest_path, manifest)
        output = self.root / 'rejected'; before = self.snapshot(root)
        result = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
                                 'normalize', '--kind', 'behavioral', '--skill', 'podman',
                                 '--input', str(root), '--output', str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('Evidence contract rejected', result.stderr)
        self.assertFalse(output.exists()); self.assertEqual(self.snapshot(root), before)
        with self.assertRaisesRegex(ValueError, 'Unrecognized reviewed extract manifest'):
            evidence.normalize_behavioral(root, 'podman')
        copied = self.root / 'recognized'; shutil.copytree(FIXTURES / 'podman-native', copied)
        self.assertEqual(evidence.encoded(evidence.normalize_behavioral(copied, 'podman')), evidence.encoded(self.data()))

    def test_reviewed_extract_expiration_boundary_and_cli(self):
        root = FIXTURES / 'podman-native'
        deadline = datetime.fromisoformat(evidence.read_json(root / 'extract-manifest.json')['origin']['expires_at'])
        before = self.data()
        for now, expired in ((deadline.replace(second=deadline.second-1), False),
                             (deadline, True), (deadline.replace(second=deadline.second+1), True)):
            with self.subTest(now=now), patch.object(evidence, 'utc_now', return_value=now):
                data = evidence.normalize_behavioral(root, 'podman')
                self.assertTrue(all(r['availability'] == ('expired' if expired else 'available') for r in data['references']))
                self.assertEqual('reference_expired' in data['availability']['reasons'], expired)
                if expired: self.assertEqual(data['availability']['status'], 'incomplete')
                for key in ('metrics', 'observations', 'arms'):
                    self.assertEqual(data[key], before[key])
                self.assertEqual([(r['id'], r['digest']) for r in data['references']],
                                 [(r['id'], r['digest']) for r in before['references']])
                evidence.project(data)
        output = self.root / 'expired-output'; snapshot = self.snapshot(root)
        with patch.object(evidence, 'utc_now', return_value=deadline), redirect_stdout(StringIO()):
            evidence.main(['normalize', '--kind', 'behavioral', '--skill', 'podman',
                           '--input', str(root), '--output', str(output)])
        public = evidence.read_json(output / 'public-report.json'); evidence.validate_public(public)
        self.assertIn('reference_expired', public['availability']['reasons'])
        self.assertEqual(self.snapshot(root), snapshot)
        with self.assertRaisesRegex(ValueError, 'unavailable or expired'):
            evidence.verify_reference(root, public['references'][0])
        ordinary = self.native()
        with patch.object(evidence, 'utc_now', return_value=deadline):
            data = evidence.normalize_behavioral(ordinary, 'podman')
        self.assertTrue(all(r['availability'] == 'available' for r in data['references']))
        self.assertNotIn('reference_expired', data['availability']['reasons'])

    def test_serialized_reviewed_expiry_rechecked_before_cli_allocation(self):
        base = self.data()
        public = evidence.project(base)
        deadline = datetime.fromisoformat(evidence.read_json(
            FIXTURES / 'podman-native/extract-manifest.json')['origin']['expires_at'])
        path = self.root / 'evidence.json'; write(path, base)
        output = self.root / 'rejected-expiry'
        before = self.snapshot(self.root)
        for now in (deadline, deadline + timedelta(seconds=1)):
            with self.subTest(now=now), patch.object(evidence, 'utc_now', return_value=now):
                with self.assertRaisesRegex(ValueError, 'Reviewed reference must be expired'), redirect_stdout(StringIO()):
                    evidence.main(['project', '--input', str(path), '--output', str(output)])
                self.assertFalse(output.exists())
                self.assertEqual(self.snapshot(self.root), before)
                with self.assertRaisesRegex(ValueError, 'Reviewed reference must be expired'):
                    evidence.validate_evidence(base)
                with self.assertRaisesRegex(ValueError, 'Reviewed reference must be expired'):
                    evidence.validate_public(public)

    def test_reviewed_projection_expiry_boundaries_and_limitations(self):
        base = self.data()
        deadline = datetime.fromisoformat(evidence.read_json(
            FIXTURES / 'podman-native/extract-manifest.json')['origin']['expires_at'])
        public_before = evidence.project(base)
        with patch.object(evidence, 'utc_now', side_effect=[deadline - timedelta(seconds=1), deadline]) as clock:
            self.assertEqual(evidence.project(base), public_before)
            self.assertEqual(clock.call_count, 1)  # Internal and public checks share one observation.
        expired = copy.deepcopy(base)
        for ref in expired['references']: ref['availability'] = 'expired'
        expired['availability'].update(status='incomplete', reasons=sorted(
            set(base['availability']['reasons']) | {'reference_expired'}))
        for now in (deadline, deadline + timedelta(seconds=1)):
            with self.subTest(now=now), patch.object(evidence, 'utc_now', return_value=now):
                public = evidence.project(expired)
                evidence.validate_evidence(expired); evidence.validate_public(public)
                for key in ('metrics', 'observations', 'arms', 'run_id', 'policy', 'dataset', 'source'):
                    self.assertEqual(public[key], public_before[key])
                self.assertEqual([r['id'] for r in public['references']], [r['id'] for r in public_before['references']])
                for change, message in (('available', 'Reviewed reference must be expired'),
                                        ('unavailable', 'Reviewed reference must be expired'),
                                        ('provenance', 'Unrecognized reviewed reference identity'),
                                        ('reason', 'Missing reference limitation'),
                                        ('complete', 'Missing reference limitation')):
                    bad = copy.deepcopy(expired)
                    if change in ('available', 'unavailable'):
                        bad['references'][0]['availability'] = change
                    elif change == 'provenance':
                        for ref in bad['references']:
                            ref.update(provenance='runtime_recorded', availability='available')
                        bad['availability']['provenance'] = 'runtime_recorded'
                    elif change == 'reason':
                        bad['availability']['reasons'] = ['metadata_missing']
                    else:
                        bad['availability'].update(status='complete', reasons=[])
                    with self.subTest(change=change):
                        with self.assertRaisesRegex(ValueError, message): evidence.validate_evidence(bad)
                        bad_public = copy.deepcopy(bad)
                        for obs in bad_public['observations']:
                            for key in ('native_id', 'native_trial', 'native_task'): obs.pop(key)
                        with self.assertRaisesRegex(ValueError, message): evidence.validate_public(bad_public)
                        path = self.root / 'expired.json'; write(path, bad)
                        before = self.snapshot(self.root); output = self.root / 'rejected-expiry'
                        with self.assertRaisesRegex(ValueError, message), redirect_stdout(StringIO()):
                            evidence.main(['project', '--input', str(path), '--output', str(output)])
                        self.assertFalse(output.exists()); self.assertEqual(self.snapshot(self.root), before)
                path = self.root / 'expired.json'; write(path, expired)
                output = self.root / ('accepted-' + str(now.second))
                before = path.read_bytes()
                with redirect_stdout(StringIO()):
                    evidence.main(['project', '--input', str(path), '--output', str(output)])
                self.assertEqual(evidence.read_json(output / 'public-report.json'), public)
                self.assertEqual(path.read_bytes(), before)

    def test_retained_member_verification(self):
        root = self.native(); path = root / 'versions.json'
        ref = evidence.reference(root, path, 'fixture', ('skillevaluator',))
        self.assertEqual(evidence.verify_reference(root, ref), '0.3.0')
        ref['locator'] = ['missing']; ref['id'] = evidence.identity({k:ref[k] for k in ('artifact_id','member','locator','digest')})
        with self.assertRaises(ValueError): evidence.verify_reference(root, ref)
        path.write_text('{}')
        with self.assertRaises(ValueError): evidence.verify_reference(root, ref)

    def test_reference_parses_the_verified_bytes(self):
        path = self.root / 'record.json'
        write(path, {'value': 'verified'})
        ref = evidence.reference(self.root, path, 'fixture', ('value',))
        read = evidence.read_bytes
        calls = []
        def replace_after_read(member, *args, **kwargs):
            raw = read(member, *args, **kwargs)
            calls.append(member)
            write(path, {'value': 'replacement'})
            return raw
        with patch.object(evidence, 'read_bytes', side_effect=replace_after_read):
            self.assertEqual(evidence.verify_reference(self.root, ref), 'verified')
        self.assertEqual(len(calls), 1)
        self.assertEqual(evidence.read_json(path)['value'], 'replacement')

    def test_exact_source_and_staging_boundary(self):
        root = self.repo(); path = self.local(root, 'alpha', True)
        (path / 'references').mkdir(); (path / 'references/a.md').write_text('Synthetic source')
        src = evidence.source('alpha', 'local', contents=evidence.skill_content(path))
        evidence.verify_source_snapshot(path, src)
        self.assertNotIn('evals/evals.json', [r['member'] for r in src['content']['manifest']])
        (path / 'references/a.md').write_text('Changed')
        with self.assertRaises(ValueError): evidence.verify_source_snapshot(path, src)
        self.assertEqual(evidence.historical_content(REPO, 'f'*40, '.apm/skills/podman')['provenance'], 'unknown')

    def test_missing_details_stay_incomplete(self):
        root = self.native(); p = next(root.rglob('*/trials/*/result.json')); p.unlink()
        data = evidence.normalize_behavioral(root, 'podman')
        self.assertEqual(data['availability']['status'], 'incomplete')
        self.assertIn('case_details_missing', data['availability']['reasons'])
        data['availability'] = {'status':'complete', 'reasons':[], 'provenance':'runtime_recorded'}
        with self.assertRaises(ValueError): evidence.project(data)

    def test_orphan_native_rewards_cannot_claim_complete_details(self):
        for arm, reward_shape in itertools.product(('with_skill', 'without_skill'), ('valid', 'contradictory', 'malformed')):
            with self.subTest(arm=arm, reward=reward_shape), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / 'native'; shutil.copytree(FIXTURES / 'podman-native', root)
                (root / 'extract-manifest.json').unlink(); run = next((root / 'results/podman').iterdir())
                trials = run / 'codex' / arm.replace('_', '-') / 'trials'
                reward = evidence.read_json(next(trials.glob('*/reward.json')))
                reward.update(trial_id='orphan-trial', overall=0)
                if reward_shape == 'contradictory': reward.update(entry_id='unknown-case', model='different-model')
                if reward_shape == 'malformed': reward = ['unparsed orphan']
                write(trials / 'orphan-trial/reward.json', reward)
                before = self.snapshot(root); output = Path(temp) / 'partial-output'; stdout = StringIO()
                with redirect_stdout(stdout):
                    evidence.main(['normalize', '--kind', 'behavioral', '--skill', 'podman', '--input', str(root),
                                   '--output', str(output)])
                data = evidence.read_json(output / 'evidence.json'); public = evidence.read_json(output / 'public-report.json')
                for carrier in (data, public):
                    self.assertEqual(next(a for a in carrier['arms'] if a['name'] == arm)['coverage']['case_details'], 'partial')
                    self.assertIn('case_details_missing', carrier['availability']['reasons'])
                    self.assertEqual(len(carrier['observations']), 20)
                normalized = evidence.normalize_behavioral(root, 'podman')
                normalized['availability']['reasons'].remove('case_details_missing')
                with self.assertRaises(ValueError): evidence.project(normalized)
                with patch.object(evidence, 'MAX_TRIALS', 20), self.assertRaisesRegex(ValueError, 'Trial input limit'):
                    evidence.normalize_behavioral(root, 'podman')
                self.assertEqual(self.snapshot(root), before)

    def test_snapshotless_partial_cohort_uses_either_arm_and_summary_carrier(self):
        for retained, carrier in itertools.product(('with_skill', 'without_skill'), ('aggregate', 'summary')):
            with self.subTest(retained=retained, carrier=carrier), tempfile.TemporaryDirectory() as temp, patch.object(self, 'root', Path(temp)):
                repo, git = self.repository_fixture(); root = self.native(); run = next((root / 'results/podman').iterdir())
                (run / 'dataset_snapshot.json').unlink()
                missing = 'without_skill' if retained == 'with_skill' else 'with_skill'
                summary_path = run / 'codex' / missing.replace('_', '-') / 'summary.json'
                shutil.rmtree(summary_path.parent / 'trials')
                result = evidence.read_json(run / 'result.json'); agent = result['agents']['codex']
                result['report_status'] = 'incomplete'; result.pop('dataset_snapshot', None)
                for obj in (result, agent):
                    if 'scored_attempts' in obj: obj['scored_attempts'] = 10
                for key in ('lift', 'dimensions_with_skill', 'dimensions_without_skill'): agent.pop(key, None)
                condition = agent['conditions'][missing]
                condition.update(scored_attempts=0, execution_status='incomplete', execution_errors=['Synthetic failure'])
                agent['num_trials_with' if missing == 'with_skill' else 'num_trials_without'] = 0
                agent['pass_at_k'].pop(missing)
                if carrier == 'summary': agent['pass_at_k'].pop(retained)
                write(run / 'result.json', result)
                summary = evidence.read_json(summary_path)
                summary.update(condition, num_trials=0, pass_at_k=None); write(summary_path, summary)
                self.mutate(root, '/provenance.json', lambda d: (d.pop('dataset_digest', None), d.pop('metrics', None)))
                before = self.snapshot(root); normalizer = evidence.normalize_behavioral
                with patch.object(evidence, 'normalize_behavioral', side_effect=lambda *a: normalizer(*a, workspace=repo)), redirect_stdout(StringIO()):
                    output = self.root / 'output'
                    evidence.main(['normalize', '--kind', 'behavioral', '--skill', 'podman', '--input', str(root), '--output', str(output)])
                    value = evidence.read_json(output / 'evidence.json')
                    public = evidence.project(value, behavioral_bundle=root)
                self.assertEqual(len(value['dataset']['case_ids']), 10)
                self.assertEqual(len(value['observations']), 10)
                self.assertEqual({row['arm'] for row in value['observations']}, {retained})
                self.assertEqual(public['availability']['status'], 'incomplete')
                self.assertIn('metadata_missing', public['availability']['reasons'])
                self.assertIn('execution_incomplete', public['availability']['reasons'])
                self.assertIsNone(value['dataset']['staged_digest'])
                self.assertEqual(self.snapshot(root), before)

    def test_snapshotless_cohort_reconciles_disjoint_arms_and_shared_limit(self):
        repo, git = self.repository_fixture(); root = self.native(); run = next((root / 'results/podman').iterdir())
        (run / 'dataset_snapshot.json').unlink()
        result = evidence.read_json(run / 'result.json'); result.update(report_status='incomplete')
        result.pop('dataset_snapshot', None); agent = result['agents']['codex']
        for obj in (result, agent):
            if 'scored_attempts' in obj: obj['scored_attempts'] = 10
        for key in ('lift', 'dimensions_with_skill', 'dimensions_without_skill'): agent.pop(key, None)
        for index, arm in enumerate(('with_skill', 'without_skill')):
            path = run / 'codex' / arm.replace('_', '-') / 'summary.json'; summary = evidence.read_json(path)
            payload = summary['pass_at_k']; ids = set(sorted(payload['cases'])[index * 5:(index + 1) * 5])
            payload['cases'] = {key: row for key, row in payload['cases'].items() if key in ids}
            passed = sum(row['passed'] for row in payload['cases'].values())
            payload.update(attempts_used=5, avg_attempts_used=0.5, passed_cases=passed, failed_cases=10-passed, rate=round(passed/10, 4))
            payload.pop('rate_interval', None)
            for reward_path in (path.parent / 'trials').glob('*/reward.json'):
                if evidence.read_json(reward_path)['entry_id'] not in ids: shutil.rmtree(reward_path.parent)
            summary.update(num_trials=5, scored_attempts=5, execution_status='incomplete'); write(path, summary)
            agent['conditions'][arm].update(scored_attempts=5, execution_status='incomplete')
            agent['num_trials_with' if index == 0 else 'num_trials_without'] = 5
            agent['pass_at_k'][arm] = payload
        write(run / 'result.json', result)
        self.mutate(root, '/provenance.json', lambda d: (d.pop('dataset_digest', None), d.pop('metrics', None)))
        normalizer = evidence.normalize_behavioral
        with patch.object(evidence, 'normalize_behavioral', side_effect=lambda *a: normalizer(*a, workspace=repo)):
            value = evidence.normalize_behavioral(root, 'podman')
            self.assertEqual(len(value['dataset']['case_ids']), 10); self.assertEqual(len(value['observations']), 10)
            self.assertEqual(evidence.project(dict(value), behavioral_bundle=root)['availability']['status'], 'incomplete')
            reader = evidence.read_bytes
            def no_trials(path, **kwargs):
                self.assertNotIn('trials', Path(path).parts)
                return reader(path, **kwargs)
            with patch.object(evidence, 'MAX_CASES', 9), patch.object(evidence, 'read_bytes', side_effect=no_trials):
                with self.assertRaisesRegex(ValueError, 'Case limit'): evidence.normalize_behavioral(root, 'podman')
            result['agents']['codex']['pass_at_k']['without_skill']['cases'] = {}
            write(run / 'result.json', result)
            with self.assertRaisesRegex(ValueError, 'Conflicting native pass data'): evidence.normalize_behavioral(root, 'podman')

    def test_missing_summary_never_invents_zero_trials(self):
        root = self.native(); next(root.rglob('summary.json')).unlink()
        data = evidence.normalize_behavioral(root, 'podman')
        self.assertIn('metadata_missing', data['availability']['reasons'])
        self.assertTrue(any(arm['coverage']['recorded_attempts'] is None for arm in data['arms']))
        self.assertEqual(len(data['observations']), 20)
        evidence.project(data)

    def test_duplicate_trials_rejected(self):
        root = self.native(); path = next(root.rglob('*/trials/*/result.json'))
        shutil.copytree(path.parent, path.parent.with_name('duplicate'))
        with self.assertRaises(ValueError): evidence.normalize_behavioral(root, 'podman')

    def test_summary_attempt_entries_reconcile_before_publication(self):
        for arm, mutation in itertools.product(('with_skill', 'without_skill'),
                ('extra', 'orphan', 'duplicate', 'excess', 'entry', 'row', 'list',
                 'trial', 'score', 'passed', 'ordinal', 'zero', 'bool')):
            with self.subTest(arm=arm, mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / 'native'; shutil.copytree(FIXTURES / 'podman-native', root)
                (root / 'extract-manifest.json').unlink()
                run = next((root / 'results/podman').iterdir())
                path = run / 'codex' / arm.replace('_', '-') / 'summary.json'
                summary = evidence.read_json(path); cases = summary['pass_at_k']['cases']
                row = cases['1']; attempt = row['attempts'][0]
                if mutation == 'extra': row['attempts'].append({**attempt, 'trial': 'orphan', 'attempt': 2})
                elif mutation == 'orphan': attempt['trial'] = 'orphan'
                elif mutation == 'duplicate': cases['2']['attempts'][0]['trial'] = attempt['trial']
                elif mutation == 'excess': row['attempts'] *= evidence.MAX_TRIALS + 1
                elif mutation == 'entry': row['attempts'][0] = []
                elif mutation == 'row': cases['1'] = []
                elif mutation == 'list': row['attempts'] = {}
                elif mutation == 'trial': attempt['trial'] = 1
                elif mutation == 'score': attempt['score'] = '0.7'
                elif mutation == 'passed': attempt['passed'] = 1
                elif mutation == 'ordinal': attempt['attempt'] = 2
                elif mutation == 'zero': attempt['attempt'] = 0
                elif mutation == 'bool': attempt['attempt'] = True
                write(path, summary)
                result_path = run / 'result.json'; result = evidence.read_json(result_path)
                result['agents']['codex']['pass_at_k'][arm] = copy.deepcopy(summary['pass_at_k'])
                if mutation == 'extra':
                    # Allow the second ordinal so the aggregate count is the rejecting boundary.
                    config_path = run / 'run_config.json'; config = evidence.read_json(config_path)
                    config['harbor']['n_attempts'] = 3; write(config_path, config)
                    result['run_config'] = config
                    policy_path = run / 'attempt_policy.json'; policy = evidence.read_json(policy_path)
                    policy['max_attempts'] = 3; write(policy_path, policy)
                    provenance = evidence.read_json(root / 'provenance.json')
                    provenance['mode'] = 'confirmation'; write(root / 'provenance.json', provenance)
                    for variant in ('with_skill', 'without_skill'):
                        result['agents']['codex']['conditions'][variant]['expected_attempts'] = 30
                        member = run / 'codex' / variant.replace('_', '-') / 'summary.json'
                        value = evidence.read_json(member); value['expected_attempts'] = 30; write(member, value)
                write(result_path, result)
                before = self.snapshot(root); output = self.root / ('summary-rejected-' + arm + '-' + mutation)
                with self.assertRaises(ValueError):
                    data = evidence.normalize_behavioral(root, 'podman')
                    evidence.write_outputs({'public.json': evidence.project(data)}, output, workspace=REPO, input_path=root)
                self.assertFalse(output.exists()); self.assertEqual(self.snapshot(root), before)

    def test_headline_metrics_reconcile_native_components_without_provenance(self):
        root = self.native(); run = next((root / 'results/podman').iterdir()); path = run / 'result.json'
        self.mutate(root, '/provenance.json', lambda d: d.pop('metrics', None))
        original = evidence.read_json(path); baseline = evidence.normalize_behavioral(root, 'podman')
        mutations = [(('lift', 'overall', 'delta'), -0.5), (('lift', 'overall', 'with_skill'), 0.1),
            (('lift', 'overall', 'without_skill'), 0.1), (('lift', 'accuracy', 'delta'), 0.9),
            (('lift', 'accuracy', 'direction'), 'down'), (('lift', 'accuracy', 'with_skill'), 0.1),
            (('with_skill',), {'accuracy': 0.1}), (('without_skill',), {'accuracy': 0.1}),
            (('dimensions_with_skill', 'correctness', 'score'), 0.1),
            (('dimensions_with_skill', 'effectiveness', 'score'), 0.1),
            (('dimensions_with_skill', 'discoverability', 'score'), 0.1),
            (('dimensions_with_skill', 'correctness', 'sources'), {'accuracy': 0.5})]
        for fields, value in mutations:
            with self.subTest(fields=fields):
                result = copy.deepcopy(original); carrier = result['agents']['codex']
                for field in fields[:-1]: carrier = carrier[field]
                carrier[fields[-1]] = value; write(path, result); before = self.snapshot(root)
                with self.assertRaisesRegex(ValueError, 'Native metric'):
                    evidence.normalize_behavioral(root, 'podman')
                with self.assertRaisesRegex(ValueError, 'Native metric'):
                    evidence.project(dict(baseline), behavioral_bundle=root)
                with patch.object(evidence, 'write_outputs') as publish:
                    with self.assertRaises(ValueError):
                        evidence.main(['normalize', '--kind', 'behavioral', '--skill', 'podman', '--input', str(root)])
                    publish.assert_not_called()
                self.assertEqual(self.snapshot(root), before)
        write(path, original)
        self.assertEqual(evidence.encoded(baseline), evidence.encoded(evidence.normalize_behavioral(root, 'podman')))
        original['agents']['codex']['lift'] = {'overall': original['agents']['codex']['lift']['overall']}
        write(path, original)
        partial = evidence.normalize_behavioral(root, 'podman')
        self.assertIn('coverage_missing', evidence.project(dict(partial), behavioral_bundle=root)['availability']['reasons'])

    def test_metric_reconciliation_preserves_native_rounding(self):
        from skillevaluator.tier3.harbor.collector import _compute_lift
        from skillevaluator.tier3.harbor.metrics import DEFAULT_METRICS, dimension_scores
        with_scores = dict.fromkeys(DEFAULT_METRICS, 0.7)
        without_scores = dict.fromkeys(DEFAULT_METRICS, 0.6); without_scores['accuracy'] = 0.6003
        lift = _compute_lift(with_scores, without_scores); overall = lift['overall']
        self.assertNotEqual(overall['delta'], round(overall['with_skill'] - overall['without_skill'], 4))
        agent = {'with_skill': with_scores, 'without_skill': without_scores, 'lift': lift,
                 'dimensions_with_skill': dimension_scores(with_scores),
                 'dimensions_without_skill': dimension_scores(without_scores)}
        self.assertTrue(evidence.validate_native_metrics(agent))
        partial = copy.deepcopy(agent); partial.pop('with_skill'); partial.pop('without_skill')
        partial['lift'].pop('security')
        self.assertFalse(evidence.validate_native_metrics(partial))
        agent['lift'] = {'overall': lift['overall']}; agent.pop('with_skill'); agent.pop('without_skill')
        self.assertFalse(evidence.validate_native_metrics(agent))
        agent['lift']['overall']['delta'] = 0.5
        with self.assertRaisesRegex(ValueError, 'Native metric'):
            evidence.validate_native_metrics(agent)

    def test_native_report_carriers_reconcile_with_retained_trials(self):
        from skillevaluator.tier3.harbor.collector import _compute_lift
        from skillevaluator.tier3.harbor.metrics import DEFAULT_METRICS, dimension_scores
        root = self.native(); run = next((root / 'results/podman').iterdir())
        self.mutate(root, '/provenance.json', lambda d: d.pop('metrics', None))
        baseline = evidence.normalize_behavioral(root, 'podman')
        paths = [run / 'result.json', *(run / 'codex').glob('*/summary.json'),
                 *(run / 'codex').glob('*/trials/*/result.json'), *(run / 'codex').glob('*/trials/*/reward.json')]
        originals = {path: evidence.read_json(path) for path in paths}
        for arm, mutation in itertools.product(('with_skill', 'without_skill'),
                ('headline', 'summary_scores', 'summary_dimensions', 'trial_component',
                 'agent_runtime_failures', 'trial_failures', 'job_failures')):
            with self.subTest(arm=arm, mutation=mutation):
                for path, value in originals.items(): write(path, value)
                result = copy.deepcopy(originals[run / 'result.json']); agent = result['agents']['codex']
                summary_path = run / 'codex' / arm.replace('_', '-') / 'summary.json'
                summary = copy.deepcopy(originals[summary_path])
                if mutation == 'headline':
                    scores = {side: {key: agent['lift'][key][side] for key in DEFAULT_METRICS}
                              for side in ('with_skill', 'without_skill')}
                    scores[arm] = dict.fromkeys(DEFAULT_METRICS, 0.1)
                    agent.update(scores); agent['lift'] = _compute_lift(scores['with_skill'], scores['without_skill'])
                    for side in scores: agent['dimensions_' + side] = dimension_scores(scores[side])
                elif mutation == 'summary_scores': summary['scores'] = {'accuracy': 0.1}
                elif mutation == 'summary_dimensions': summary['dimensions'] = {'correctness': {'score': 0.1}}
                elif mutation == 'trial_component':
                    path = next((summary_path.parent / 'trials').glob('*/result.json'))
                    trial = copy.deepcopy(originals[path]); trial['verifier_result']['rewards']['accuracy'] = 0.1
                    reward_path = path.with_name('reward.json'); reward = copy.deepcopy(originals[reward_path]); reward['accuracy'] = 0.1
                    write(path, trial); write(reward_path, reward)
                else: agent[mutation] = {arm: 'private diagnostic' if mutation == 'job_failures' else [{'reason': 'private diagnostic'}]}
                write(run / 'result.json', result); write(summary_path, summary); before = self.snapshot(root)
                with self.assertRaises(ValueError): evidence.normalize_behavioral(root, 'podman')
                with self.assertRaises(ValueError): evidence.project(dict(baseline), behavioral_bundle=root)
                with patch.object(evidence, 'write_outputs') as publish:
                    with self.assertRaises(ValueError): evidence.main(['normalize', '--kind', 'behavioral', '--skill', 'podman', '--input', str(root)])
                    publish.assert_not_called()
                self.assertEqual(self.snapshot(root), before)

    def test_native_arm_carriers_accept_success_and_consistent_partial_failures(self):
        from skillevaluator.tier3.harbor.collector import _average_overall
        from skillevaluator.tier3.harbor.metrics import average_metrics, dimension_scores
        for arm in ('with_skill', 'without_skill'):
            with self.subTest(arm=arm), tempfile.TemporaryDirectory() as temp, patch.object(self, 'root', Path(temp)):
                root = self.native(); run = next((root / 'results/podman').iterdir())
                summary_path = run / 'codex' / arm.replace('_', '-') / 'summary.json'
                rewards = [evidence.read_json(p) for p in (summary_path.parent / 'trials').glob('*/reward.json')]
                means = average_metrics(rewards)[0]; summary = evidence.read_json(summary_path)
                summary.update(scores=means, dimensions=dimension_scores(means), overall_score=_average_overall(rewards))
                write(summary_path, summary)
                baseline = evidence.normalize_behavioral(root, 'podman')
                self.assertEqual(baseline['metrics'], self.data()['metrics'])
                path = next((summary_path.parent / 'trials').glob('*/result.json'))
                trial = evidence.read_json(path); reward = evidence.read_json(path.with_name('reward.json'))
                trial.update(verifier_result=None, exception_info={'diagnostic': 'PRIVATE-DIAGNOSTIC'})
                write(path, trial); path.with_name('reward.json').unlink()
                self.unscore_case(summary, reward['entry_id'])
                failure = {'reason': 'PRIVATE-DIAGNOSTIC'}
                summary.update(scored_attempts=9, execution_status='incomplete', trial_failures=[failure])
                write(summary_path, summary)
                result = evidence.read_json(run / 'result.json'); result['report_status'] = 'incomplete'
                agent = result['agents']['codex']
                agent['conditions'][arm].update(scored_attempts=9, execution_status='incomplete', execution_errors=['PRIVATE-DIAGNOSTIC'])
                agent['pass_at_k'][arm] = summary['pass_at_k']; agent['trial_failures'] = {arm: [failure]}
                write(run / 'result.json', result)
                data = evidence.normalize_behavioral(root, 'podman'); public = evidence.project(dict(data), behavioral_bundle=root)
                self.assertIn('execution_incomplete', public['availability']['reasons'])
                self.assertNotIn('PRIVATE-DIAGNOSTIC', evidence.encoded(public).decode())
                data['availability']['reasons'].remove('execution_incomplete')
                with self.assertRaises(ValueError): evidence.project(data)

    def test_summary_case_rollups_reconcile_in_both_arms_and_projection(self):
        root = self.native(); run = next((root / 'results/podman').iterdir())
        baseline = evidence.normalize_behavioral(root, 'podman')
        originals = {p: evidence.read_json(p) for p in (run / 'result.json',
            run / 'codex/with-skill/summary.json', run / 'codex/without-skill/summary.json')}
        mutations = [('passed', False), ('passed', 1), ('best_score', 0), ('attempts_used', 0),
                     ('attempts_used', True), ('first_pass_attempt', None), ('attempts_skipped', 1),
                     ('attempts_missing', 1), ('aggregate_attempts_used', 0), ('aggregate_failed_cases', 1),
                     ('aggregate_rate', 0), ('aggregate_avg_attempts_used', 0),
                     ('aggregate_max_attempts_possible', 0), ('aggregate_k', 2), ('aggregate_stop_on_pass', True)]
        for arm, (field, value) in itertools.product(('with_skill', 'without_skill'), mutations):
            with self.subTest(arm=arm, field=field, value=value):
                path = run / 'codex' / arm.replace('_', '-') / 'summary.json'; result_path = run / 'result.json'
                original = originals[path]; result_original = originals[result_path]
                summary = copy.deepcopy(original); result = copy.deepcopy(result_original)
                carrier = summary['pass_at_k'] if field.startswith('aggregate_') else next(
                    row for row in summary['pass_at_k']['cases'].values() if row['passed'])
                carrier[field.removeprefix('aggregate_')] = value
                result['agents']['codex']['pass_at_k'][arm] = copy.deepcopy(summary['pass_at_k'])
                write(path, summary); write(result_path, result); before = self.snapshot(root)
                with self.assertRaisesRegex(ValueError, 'Summary .*rollup'):
                    evidence.normalize_behavioral(root, 'podman')
                with self.assertRaisesRegex(ValueError, 'Summary .*rollup'):
                    evidence.project(dict(baseline), behavioral_bundle=root)
                with patch.object(evidence, 'write_outputs') as publish:
                    with self.assertRaises(ValueError):
                        evidence.main(['normalize', '--kind', 'behavioral', '--skill', 'podman', '--input', str(root)])
                    publish.assert_not_called()
                self.assertEqual(self.snapshot(root), before)
                write(path, original); write(result_path, result_original)
        for path, original in originals.items(): write(path, original)
        self.assertEqual(evidence.encoded(baseline), evidence.encoded(evidence.normalize_behavioral(root, 'podman')))

    def test_summary_attempts_accept_partial_retained_trials(self):
        root = self.native()
        for arm in ('with_skill', 'without_skill'):
            path = next(root.glob('results/*/*/codex/' + arm.replace('_', '-') + '/trials/*/result.json'))
            shutil.rmtree(path.parent)
        before = self.snapshot(root)
        data = evidence.normalize_behavioral(root, 'podman')
        self.assertEqual([a['coverage']['case_details'] for a in data['arms']], ['partial', 'partial'])
        self.assertEqual(len(data['observations']), 18)
        evidence.project(data); self.assertEqual(self.snapshot(root), before)

    def test_partial_summary_rollups_still_bound_aggregate_passes(self):
        for arm in ('with_skill', 'without_skill'):
            with self.subTest(arm=arm), tempfile.TemporaryDirectory() as temp, patch.object(self, 'root', Path(temp)):
                root = self.native(); run = next((root / 'results/podman').iterdir())
                base = run / 'codex' / arm.replace('_', '-'); path = base / 'summary.json'
                summary = evidence.read_json(path); payload = summary['pass_at_k']
                removed = payload['cases'].pop('2')
                for attempt in removed['attempts']: shutil.rmtree(base / 'trials' / attempt['trial'])
                result_path = run / 'result.json'; result = evidence.read_json(result_path)
                result['agents']['codex']['pass_at_k'][arm] = copy.deepcopy(payload)
                write(path, summary); write(result_path, result)
                baseline = evidence.normalize_behavioral(root, 'podman')
                self.assertEqual(next(a for a in baseline['arms'] if a['name'] == arm)['coverage']['case_details'], 'partial')
                payload.update(passed_cases=0, failed_cases=payload['total_cases'], rate=0.0)
                result['agents']['codex']['pass_at_k'][arm] = copy.deepcopy(payload)
                write(path, summary); write(result_path, result)
                with self.assertRaisesRegex(ValueError, 'Summary aggregate rollup'):
                    evidence.normalize_behavioral(root, 'podman')
                with self.assertRaisesRegex(ValueError, 'Summary aggregate rollup'):
                    evidence.project(dict(baseline), behavioral_bundle=root)

    def test_summary_unscored_orphan_cannot_claim_complete_details(self):
        for arm in ('with_skill', 'without_skill'):
            with self.subTest(arm=arm), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / 'native'; shutil.copytree(FIXTURES / 'podman-native', root)
                (root / 'extract-manifest.json').unlink()
                run = next((root / 'results/podman').iterdir())
                base = run / 'codex' / arm.replace('_', '-')
                path = next((base / 'trials').glob('*/result.json'))
                record = evidence.read_json(path); trial = record['trial_name']
                reward = evidence.read_json(path.parent / 'reward.json'); case = reward['entry_id']
                record['verifier_result'] = None; write(path, record); (path.parent / 'reward.json').unlink()
                summary_path = base / 'summary.json'; summary = evidence.read_json(summary_path)
                self.unscore_case(summary, case)
                summary['pass_at_k']['cases'][case]['attempts'][0]['trial'] = 'orphan'
                summary.update(scored_attempts=9, execution_status='incomplete')
                write(summary_path, summary)
                result_path = run / 'result.json'; result = evidence.read_json(result_path)
                result.update(report_status='incomplete', execution_status='incomplete')
                result['agents']['codex']['conditions'][arm].update(scored_attempts=9, execution_status='incomplete')
                result['agents']['codex']['pass_at_k'][arm] = copy.deepcopy(summary['pass_at_k'])
                write(result_path, result)
                with self.assertRaisesRegex(ValueError, 'Unmatched summary attempts'):
                    evidence.normalize_behavioral(root, 'podman')

    def test_reward_scores_require_retained_verifier_values(self):
        for arm, state in itertools.product(('with_skill', 'without_skill'), ('missing', None, {}, {'rewards': None}, {'rewards': {}})):
            with self.subTest(arm=arm, verifier=state), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / 'native'; shutil.copytree(FIXTURES / 'podman-native', root)
                (root / 'extract-manifest.json').unlink(); run = next((root / 'results/podman').iterdir())
                arm_dir = run / 'codex' / arm.replace('_', '-')
                path = next((arm_dir / 'trials').glob('*/result.json')); record = evidence.read_json(path)
                reward = evidence.read_json(path.parent / 'reward.json'); case = reward['entry_id']
                if state == 'missing': record.pop('verifier_result', None)
                else: record['verifier_result'] = state
                write(path, record)
                summary_path = arm_dir / 'summary.json'; summary = evidence.read_json(summary_path)
                self.unscore_case(summary, case)
                summary.update(scored_attempts=9, execution_status='incomplete')
                write(summary_path, summary)
                result_path = run / 'result.json'; result = evidence.read_json(result_path)
                result.update(report_status='incomplete', execution_status='incomplete')
                result['agents']['codex']['conditions'][arm].update(scored_attempts=9, execution_status='incomplete')
                result['agents']['codex']['pass_at_k'][arm] = copy.deepcopy(summary['pass_at_k']); write(result_path, result)
                before = self.snapshot(root); output = Path(temp) / 'rejected-reward'
                with self.assertRaisesRegex(ValueError, 'Reward score mismatch'), redirect_stdout(StringIO()):
                    evidence.main(['normalize', '--kind', 'behavioral', '--skill', 'podman', '--input', str(root),
                                   '--output', str(output)])
                self.assertFalse(output.exists()); self.assertEqual(self.snapshot(root), before)

    def test_unscored_native_trial_keeps_identity(self):
        root = self.native(); run = next((root/'results/podman').iterdir())
        path = next((run/'codex/with-skill/trials').glob('*/result.json'))
        record = evidence.read_json(path); trial = record['trial_name']
        reward = evidence.read_json(path.parent/'reward.json'); case = reward['entry_id']
        record['verifier_result'] = None; record['exception_info'] = {'diagnostic': 'discarded'}
        write(path, record); (path.parent/'reward.json').unlink()
        summary_path = run/'codex/with-skill/summary.json'; summary = evidence.read_json(summary_path)
        self.unscore_case(summary, case)
        summary['scored_attempts'] = 9; summary['execution_status'] = 'incomplete'
        write(summary_path, summary)
        result_path = run/'result.json'; result = evidence.read_json(result_path)
        result.update(report_status='incomplete', execution_status='incomplete')
        result['agents']['codex']['conditions']['with_skill'].update(scored_attempts=9, execution_status='incomplete')
        result['agents']['codex']['pass_at_k']['with_skill'] = copy.deepcopy(summary['pass_at_k'])
        write(result_path, result)
        for state in ('missing', None, {}, {'rewards': None}, {'rewards': {}}):
            with self.subTest(verifier=state):
                if state == 'missing':
                    record.pop('verifier_result', None)
                else:
                    record['verifier_result'] = state
                write(path, record)
                data = evidence.normalize_behavioral(root, 'podman')
                obs = next(o for o in data['observations'] if o['native_trial'] == trial)
                self.assertIsNone(obs['score']); self.assertEqual(obs['native_id'], record['id'])
                self.assertEqual(data['arms'][0]['coverage']['unscored_attempts'], 1)
                self.assertEqual(data['availability']['status'], 'incomplete')
                for carrier in (data, evidence.project(data)):
                    for ref in carrier['references']:
                        if ref['availability'] == 'available':
                            evidence.verify_reference(root, ref)

    def test_confirmation_native_attempts(self):
        root = self.native(); run = next((root/'results/podman').iterdir())
        config_path = run/'run_config.json'; config = evidence.read_json(config_path)
        config['harbor']['n_attempts'] = 3; write(config_path, config)
        result_path = run/'result.json'; result = evidence.read_json(result_path)
        result['run_config'] = config
        for arm in ('with_skill', 'without_skill'):
            result['agents']['codex']['conditions'][arm].update(expected_attempts=30, scored_attempts=30)
            base = run/'codex'/arm.replace('_','-')
            summary_path = base/'summary.json'; summary = evidence.read_json(summary_path)
            summary.update(expected_attempts=30, scored_attempts=30, num_trials=30)
            summary['pass_at_k'].update(k=3, attempts_used=30, max_attempts_possible=30, avg_attempts_used=3.0)
            for case, row in summary['pass_at_k']['cases'].items():
                original = row['attempts'][0]; original_trial = base/'trials'/original['trial']
                for ordinal in (2,3):
                    new_trial = original['trial'] + '-attempt' + str(ordinal)
                    target = base/'trials'/new_trial; shutil.copytree(original_trial, target)
                    trial_result = evidence.read_json(target/'result.json')
                    trial_result.update(id=trial_result['id']+'-'+str(ordinal), trial_name=new_trial)
                    write(target/'result.json', trial_result)
                    reward = evidence.read_json(target/'reward.json'); reward['trial_id'] = new_trial
                    write(target/'reward.json', reward)
                    row['attempts'].append({**original, 'attempt':ordinal, 'trial':new_trial})
                row['attempts_used'] = 3
            write(summary_path, summary)
            result['agents']['codex']['pass_at_k'][arm] = copy.deepcopy(summary['pass_at_k'])
        write(result_path, result)
        attempts = evidence.read_json(run/'attempt_policy.json'); attempts['max_attempts'] = 3
        write(run/'attempt_policy.json', attempts)
        prov = evidence.read_json(root/'provenance.json'); prov['mode'] = 'confirmation'; write(root/'provenance.json', prov)
        data = evidence.normalize_behavioral(root, 'podman')
        self.assertEqual(len(data['observations']), 60)
        self.assertEqual({o['attempt'] for o in data['observations']}, {1,2,3})
        self.assertEqual(data['policy']['attempts']['mode'], 'confirmation')
        evidence.project(data)
        prov['mode'] = 'standard'; write(root / 'provenance.json', prov)
        with self.assertRaisesRegex(ValueError, 'Benchmark mode attempt count mismatch'):
            evidence.normalize_behavioral(root, 'podman')

    def test_policy_mode_attempt_consistency(self):
        for mode, maximum in itertools.product(('standard', 'confirmation', 'unknown'), (None, 0, 1, 2, 3)):
            with self.subTest(mode=mode, maximum=maximum):
                policy = evidence.make_policy(attempts={'mode': mode, 'maximum': maximum,
                                                       'stop_on_pass': None, 'pass_threshold': None},
                                              provenance='runtime_recorded')
                valid = maximum is None or maximum > 0 and (mode == 'unknown' or maximum == evidence.reports.MODES[mode])
                if valid:
                    evidence.validate_policy(policy)
                else:
                    with self.assertRaises(ValueError):
                        evidence.validate_policy(policy)

    def assert_project_rejects(self, data, message):
        with self.assertRaisesRegex(ValueError, message): evidence.validate_evidence(data)
        public = copy.deepcopy(data)
        for obs in public['observations']:
            for key in ('native_id', 'native_trial', 'native_task'): obs.pop(key)
        with self.assertRaisesRegex(ValueError, message): evidence.validate_public(public)
        path = self.root / 'invalid.json'; write(path, data)
        before = path.read_bytes(); output = self.root / 'rejected-output'
        result = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
                                 'project', '--input', str(path), '--output', str(output)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, 'Evidence contract rejected (ValueError)\n')
        self.assertFalse(output.exists())
        self.assertEqual(path.read_bytes(), before)

    def test_exact_content_requires_root_manifest(self):
        for manifest in ([], [{'member': 'references/only.md', 'digest': evidence.digest_bytes(b'Synthetic')}]):
            with self.subTest(manifest=manifest):
                data = self.data()
                data['source']['content'] = evidence.content(manifest, 'reconstructed_from_declared_revision')
                self.assert_project_rejects(data, 'Skill content missing root SKILL.md')
        evidence.validate_content(evidence.content())
        evidence.validate_content(evidence.content([
            {'member': 'SKILL.md', 'digest': evidence.digest_bytes(b'Synthetic')}], 'configured'))

    def test_complete_behavioral_requires_nonempty_cohort(self):
        data = self.data(); self.synthetic_skill_references(data, 'podman')
        data['source']['content'] = evidence.content([
            {'member': 'SKILL.md', 'digest': evidence.digest_bytes(b'Synthetic')}], 'configured')
        data['dataset'].update(case_ids=[], case_cohort_digest=evidence.identity([]))
        data['observations'] = []
        for arm in data['arms']:
            arm['coverage'].update(expected_cases=0, expected_attempts=0, recorded_attempts=0,
                                   scored_attempts=0, unscored_attempts=0, case_details='complete')
            arm['rubric'].update(passed_cases=0, total_cases=0)
        data['availability'].update(status='complete', reasons=[])
        self.assert_project_rejects(data, 'Empty complete cohort')
        data['availability'].update(status='incomplete', reasons=['coverage_missing'])
        self.project_grading_fixture(data)

    def test_projection_preserves_known_execution_limitations(self):
        for arm, status, errors in itertools.product(('with_skill', 'without_skill'),
                                                     ('failed', 'incomplete', 'unknown'), (0, 1)):
            with self.subTest(arm=arm, status=status, errors=errors):
                data = self.data(); self.synthetic_skill_references(data, 'podman')
                selected = next(row for row in data['arms'] if row['name'] == arm)
                selected.update(execution_status=status, execution_error_count=errors)
                data['availability'].update(status='incomplete', reasons=['metadata_missing', 'source_unavailable'])
                self.assert_project_rejects(data, 'Missing execution limitation')
                data['availability']['reasons'].append('execution_incomplete')
                self.assertIn('execution_incomplete', self.project_grading_fixture(data)['availability']['reasons'])
        # Configured arms with no observed execution do not invent a failed run.
        self.project_grading_fixture(evidence.read_json(FIXTURES / 'gh-no-model.json'))

    def test_complete_case_details_require_known_rubric_outcomes(self):
        for arm, status, score in itertools.product(('with_skill', 'without_skill'),
                                                    ('complete', 'incomplete'), (0.25, 0.75)):
            with self.subTest(arm=arm, status=status, score=score):
                data = self.data(); self.synthetic_skill_references(data, 'podman')
                data['source']['content'] = evidence.content([
                    {'member': 'SKILL.md', 'digest': evidence.digest_bytes(b'Synthetic')}], 'configured')
                data['availability'].update(status=status, reasons=[] if status == 'complete' else ['metadata_missing'])
                row = next(row for row in data['observations'] if row['arm'] == arm)
                row['score'] = row['scores']['overall'] = score
                row['rubric_pass'] = None
                selected = next(item for item in data['arms'] if item['name'] == arm)
                selected['rubric']['passed_cases'] = len({item['case_id'] for item in data['observations']
                                                          if item['arm'] == arm and item['rubric_pass'] is True})
                self.assert_project_rejects(data, 'Missing scored rubric outcome')
                row['rubric_pass'] = score >= selected['rubric']['threshold']
                selected['rubric']['passed_cases'] = len({item['case_id'] for item in data['observations']
                                                          if item['arm'] == arm and item['rubric_pass'] is True})
                self.project_grading_fixture(data)
        data = self.data(); self.synthetic_skill_references(data, 'podman'); data['observations'][0]['rubric_pass'] = None
        data['arms'][0]['rubric'].update(threshold=None, passed_cases=9)
        data['policy']['attempts']['pass_threshold'] = None
        data['policy']['id'] = evidence.identity({k: data['policy'][k] for k in
                                                ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
        self.project_grading_fixture(data)  # Unknown thresholds do not invent an outcome.
        data = self.data(); self.synthetic_skill_references(data, 'podman'); data['observations'][0]['rubric_pass'] = None
        data['arms'][0]['coverage']['case_details'] = 'partial'
        data['availability'].update(status='incomplete', reasons=sorted(set(
            data['availability']['reasons']) | {'case_details_missing'}))
        self.project_grading_fixture(data)  # Partial case details remain explicitly incomplete.

    def test_policy_only_threshold_bypass_rejected_by_cli(self):
        data = self.data(); self.synthetic_skill_references(data, 'podman')
        for arm in data['arms']: arm['rubric'].update(threshold=None, passed_cases=0)
        for obs in data['observations']: obs['rubric_pass'] = None
        path = self.root / 'policy-only.json'; write(path, data)
        before = self.snapshot(self.root); output = self.root / 'rejected-policy'
        result = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
                                 'project', '--input', str(path), '--output', str(output)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stderr, 'Evidence contract rejected (ValueError)\n')
        self.assertFalse(output.exists()); self.assertEqual(self.snapshot(self.root), before)
        self.assert_project_rejects(data, 'Missing scored rubric outcome')

    def test_effective_threshold_outcomes_and_unchanged_carriers(self):
        for policy, arm_threshold, arm_name, score in itertools.product(
                (None, 0.0, 0.5), (None, 0.0, 0.5), ('with_skill', 'without_skill'), (0.0, 0.5, 0.75)):
            with self.subTest(policy=policy, threshold=arm_threshold, arm=arm_name, score=score):
                data = self.data(); self.synthetic_skill_references(data, 'podman')
                data['policy']['attempts']['pass_threshold'] = policy
                data['policy']['id'] = evidence.identity({k: data['policy'][k] for k in
                    ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
                effective = arm_threshold if arm_threshold is not None else policy
                for arm in data['arms']: arm['rubric']['threshold'] = arm_threshold
                selected = next(arm for arm in data['arms'] if arm['name'] == arm_name)
                row = next(obs for obs in data['observations'] if obs['arm'] == arm_name)
                row['score'] = row['scores']['overall'] = score
                for obs in data['observations']:
                    obs['rubric_pass'] = obs['score'] >= effective if effective is not None else None
                for arm in data['arms']:
                    arm['rubric']['passed_cases'] = len({obs['case_id'] for obs in data['observations']
                                                       if obs['arm'] == arm['name'] and obs['rubric_pass'] is True})
                if policy is not None and arm_threshold is not None and policy != arm_threshold:
                    with self.assertRaisesRegex(ValueError, 'Rubric attempt-policy threshold mismatch'):
                        self.project_grading_fixture(data)
                    continue
                public = self.project_grading_fixture(data)
                self.assertEqual(public['policy'], data['policy']); self.assertEqual(public['arms'], data['arms'])
                evidence.validate_evidence(data); evidence.validate_public(public)
                if effective is None: continue
                def rejects(message):
                    with self.assertRaisesRegex(ValueError, message): evidence.validate_evidence(data)
                    with self.assertRaisesRegex(ValueError, message): self.project_grading_fixture(data)
                    public = copy.deepcopy(data)
                    for obs in public['observations']:
                        for key in ('native_id', 'native_trial', 'native_task'): obs.pop(key)
                    with self.assertRaisesRegex(ValueError, message): evidence.validate_public(public)
                row['rubric_pass'] = not (score >= effective)
                selected['rubric']['passed_cases'] = len({obs['case_id'] for obs in data['observations']
                                                         if obs['arm'] == arm_name and obs['rubric_pass'] is True})
                rejects('Contradictory native rubric pass')
                row['rubric_pass'] = None
                selected['rubric']['passed_cases'] = len({obs['case_id'] for obs in data['observations']
                                                         if obs['arm'] == arm_name and obs['rubric_pass'] is True})
                rejects('Missing scored rubric outcome')
                selected['coverage']['case_details'] = 'partial'
                data['availability'].update(status='incomplete', reasons=sorted(
                    set(data['availability']['reasons']) | {'case_details_missing'}))
                self.project_grading_fixture(data)  # Missing partial details do not invent outcomes.
                row['rubric_pass'] = not (score >= effective)
                rejects('Contradictory native rubric pass')

    def test_rubric_aggregates_require_numerator_and_denominator_together(self):
        for arm, status, passes in itertools.product(('with_skill', 'without_skill'),
                                                     ('complete', 'incomplete'), (0, 8, 10, 1000)):
            with self.subTest(arm=arm, status=status, passes=passes):
                data = self.data(); self.synthetic_skill_references(data, 'podman')
                data['source']['content'] = evidence.content([
                    {'member': 'SKILL.md', 'digest': evidence.digest_bytes(b'Synthetic')}], 'configured')
                data['availability'].update(status=status, reasons=[] if status == 'complete' else ['metadata_missing'])
                rubric = next(row for row in data['arms'] if row['name'] == arm)['rubric']
                original = copy.deepcopy(rubric)
                rubric.update(passed_cases=passes, total_cases=None)
                self.assert_project_rejects(data, 'Missing rubric aggregate pair')
                rubric.update(passed_cases=None)
                self.project_grading_fixture(data)  # Both unknown aggregates stay null.
                rubric.update(total_cases=10)
                self.assert_project_rejects(data, 'Missing rubric aggregate pair')
                rubric.update(original)
                self.project_grading_fixture(data)
                rubric['passed_cases'] = 1
                self.assert_project_rejects(data, 'Rubric count mismatch')

    def test_behavioral_evidence_rejects_static_scan_claims(self):
        for status, finding in itertools.product(('complete', 'incomplete'), (False, True)):
            with self.subTest(status=status, finding=finding):
                data = self.data(); self.synthetic_skill_references(data, 'podman')
                data['source']['content'] = evidence.content([
                    {'member': 'SKILL.md', 'digest': evidence.digest_bytes(b'Synthetic')}], 'configured')
                data['availability'].update(status=status, reasons=[] if status == 'complete' else ['metadata_missing'])
                ref = data['observations'][0]['references'][0]
                data['scans'] = [{'scanner': 'fabricated', 'status': 'passed', 'passed': True,
                                 'severity_counts': dict.fromkeys(('critical', 'high', 'medium', 'low'), 0),
                                 'references': [ref]}]
                if finding:
                    data['findings'] = [{'scanner': 'fabricated', 'severity': 'info', 'check': None,
                                         'member': None, 'line': None, 'reference': ref}]
                self.assert_project_rejects(data, 'Behavioral report implies static scans')
                data['scans'] = []; data['findings'] = []
                self.project_grading_fixture(data)

    def test_projection_preserves_missing_behavioral_coverage(self):
        for arm, key, value in itertools.product(('with_skill', 'without_skill'),
                ('recorded_attempts', 'scored_attempts'), (None, 9)):
            with self.subTest(arm=arm, key=key, value=value):
                data = self.data(); self.synthetic_skill_references(data, 'podman'); selected = next(row for row in data['arms'] if row['name'] == arm)
                cov = selected['coverage']; cov[key] = value
                if key == 'recorded_attempts' and value is not None: cov['scored_attempts'] = value
                cov.update(unscored_attempts=cov['recorded_attempts'] - cov['scored_attempts']
                           if cov['recorded_attempts'] is not None and cov['scored_attempts'] is not None else None,
                           case_details='partial')
                if value == 9:
                    last = next(row for row in reversed(data['observations']) if row['arm'] == arm)
                    data['observations'].remove(last)
                data['availability'].update(status='incomplete', reasons=['metadata_missing', 'source_unavailable',
                                                                       'case_details_missing'])
                self.assert_project_rejects(data, 'Missing coverage limitation')
                data['availability']['reasons'].append('coverage_missing')
                self.assertIn('coverage_missing', self.project_grading_fixture(data)['availability']['reasons'])

    def test_projection_preserves_missing_behavioral_case_details(self):
        for arm, details in itertools.product(('with_skill', 'without_skill'), ('partial', 'unavailable')):
            with self.subTest(arm=arm, details=details):
                data = self.data(); self.synthetic_skill_references(data, 'podman'); selected = next(row for row in data['arms'] if row['name'] == arm)
                selected['coverage']['case_details'] = details
                data['availability'].update(status='incomplete', reasons=['metadata_missing', 'source_unavailable'])
                self.assert_project_rejects(data, 'Missing case detail limitation')
                data['availability']['reasons'].append('case_details_missing')
                self.assertIn('case_details_missing', self.project_grading_fixture(data)['availability']['reasons'])

    def test_projection_preserves_unavailable_behavioral_source(self):
        data = self.data(); data['source']['content'] = evidence.content()
        data['availability'].update(status='incomplete', reasons=['metadata_missing'])
        self.assert_project_rejects(data, 'Behavioral source unavailable')
        data['availability']['reasons'].append('source_unavailable')
        self.assertIn('source_unavailable', evidence.project(data)['availability']['reasons'])
        evidence.project(evidence.read_json(FIXTURES / 'gh-no-model.json'))

    def test_missing_behavioral_identities_retain_metadata_limitation(self):
        for missing in ('maximum', 'staged_digest', 'evaluator_revision', 'patch_digest', 'run_id'):
            with self.subTest(missing=missing):
                data = self.data(); self.synthetic_skill_references(data, 'podman'); data['source']['content'] = evidence.content()
                data['availability'].update(status='incomplete', reasons=['source_unavailable'])
                if missing == 'maximum': data['policy']['attempts']['maximum'] = None
                elif missing == 'staged_digest':
                    data['dataset'].update(staged_digest=None, staged_algorithm=None, staged_provenance='unknown')
                elif missing == 'evaluator_revision': data['policy']['fields']['evaluator_revision'] = None
                elif missing == 'patch_digest': data['policy']['patch_digest'] = None
                else:
                    data['run_id'] = None
                    for row in data['observations']:
                        row['id'] = evidence.observation_id(None, row['arm'], row['case_id'], row['native_id'],
                                                           row['native_trial'], row['attempt'])
                data['policy']['id'] = evidence.identity({k: data['policy'][k] for k in
                    ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
                self.assert_project_rejects(data, 'Missing behavioral identity limitation')
                data['availability']['reasons'].append('metadata_missing')
                self.assertIn('metadata_missing', self.project_grading_fixture(data)['availability']['reasons'])
        root = self.native(); run = next((root / 'results/podman').iterdir())
        paths = [root / 'provenance.json', run / 'result.json', run / 'run_config.json',
                 run / 'attempt_policy.json', run / 'dataset_snapshot.json']
        original = {path: path.read_bytes() for path in paths}
        for missing in ('maximum', 'staged_digest', 'evaluator_revision', 'patch_digest'):
            with self.subTest(native_missing=missing):
                provenance = evidence.read_json(root / 'provenance.json')
                if missing == 'maximum':
                    config = evidence.read_json(run / 'run_config.json'); config['harbor']['n_attempts'] = None
                    write(run / 'run_config.json', config)
                    result = evidence.read_json(run / 'result.json'); result['run_config'] = config; write(run / 'result.json', result)
                    attempts = evidence.read_json(run / 'attempt_policy.json'); attempts['max_attempts'] = None
                    write(run / 'attempt_policy.json', attempts)
                elif missing == 'staged_digest':
                    (run / 'dataset_snapshot.json').unlink(); provenance.pop('dataset_digest', None)
                elif missing == 'evaluator_revision': provenance['policy'].pop('evaluator_revision', None)
                else: provenance.pop('patch_sha256', None)
                write(root / 'provenance.json', provenance)
                data = evidence.normalize_behavioral(root, 'podman')
                self.assertIn('metadata_missing', data['availability']['reasons']); self.project_grading_fixture(data)
                for path, raw in original.items(): path.write_bytes(raw)

    def test_projection_retains_unknown_attempt_metadata(self):
        for arm in ('with_skill', 'without_skill'):
            with self.subTest(arm=arm):
                data = self.data(); self.synthetic_skill_references(data, 'podman')
                row = next(row for row in data['observations'] if row['arm'] == arm)
                row['attempt'] = None
                row['id'] = evidence.observation_id(data['run_id'], row['arm'], row['case_id'], row['native_id'],
                                                     row['native_trial'], row['attempt'])
                data['source']['content'] = evidence.content()
                data['availability'].update(status='incomplete', reasons=['source_unavailable'])
                self.assert_project_rejects(data, 'Missing attempt metadata limitation')
                data['availability']['reasons'].append('metadata_missing')
                public = self.project_grading_fixture(data)
                self.assertIn('metadata_missing', public['availability']['reasons'])
                self.assertIsNone(next(item for item in public['observations'] if item['id'] == row['id'])['attempt'])

    def test_reviewed_extract_member_budget_matches_trial_companions(self):
        root = self.root / 'extract-budget'; root.mkdir()
        manifest = evidence.read_json(FIXTURES / 'podman-native/extract-manifest.json')
        for size in (20100, 20101):
            with self.subTest(size=size):
                manifest['members'] = [{'member': f'trials/member-{i}.json',
                                        'original_digest': evidence.digest_bytes(b'original'),
                                        'extract_digest': evidence.digest_bytes(b'extract')} for i in range(size)]
                path = root / 'extract-manifest.json'; write(path, manifest)
                approved = frozenset({evidence.digest_bytes(path.read_bytes())})
                with patch.object(evidence, 'REVIEWED_EXTRACT_MANIFESTS', approved):
                    if size == 20100:
                        self.assertEqual(len(evidence.load_extract(root)['members']), size)
                    else:
                        with self.assertRaisesRegex(ValueError, 'Extract limit'): evidence.load_extract(root)

    def test_shared_stop_on_pass_policy_consistency(self):
        for field, attempt in itertools.product((None, False, True), repeat=2):
            with self.subTest(field=field, attempt=attempt):
                data = self.data(); self.synthetic_skill_references(data, 'podman')
                data['policy']['fields']['stop_on_pass'] = field
                data['policy']['attempts']['stop_on_pass'] = attempt
                data['policy']['id'] = evidence.identity({k: data['policy'][k] for k in
                    ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
                if field is None or attempt is None or field == attempt:
                    self.project_grading_fixture(data)
                else:
                    self.assert_project_rejects(data, 'Stop-on-pass policy mismatch')

    def test_inventory_cli_rejects_malformed_frontmatter_without_traceback(self):
        checkout = self.root / 'checkout'
        authored = self.local(checkout, 'alpha')
        scripts = checkout / '.github/scripts'; scripts.mkdir(parents=True)
        for name in ('skill_evidence.py', 'skill_reports.py'):
            shutil.copyfile(REPO / '.github/scripts' / name, scripts / name)
        for front in ('name: alpha\ndescription: [', 'name: alpha\ndescription: "unterminated'):
            with self.subTest(front=front):
                (authored / 'SKILL.md').write_text('---\n' + front + '\n---\n')
                before = {p.relative_to(checkout): p.read_bytes() for p in checkout.rglob('*') if p.is_file()}
                output = self.root / 'rejected-output'
                env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
                result = subprocess.run([sys.executable, str(scripts / 'skill_evidence.py'),
                                         'inventory', '--output', str(output)], env=env,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stderr, 'Evidence contract rejected (ValueError)\n')
                self.assertFalse(output.exists())
                self.assertEqual(before, {p.relative_to(checkout): p.read_bytes() for p in checkout.rglob('*') if p.is_file()})

    def test_trial_member_cap_is_shared_before_any_trial_read(self):
        root = self.native()
        run = next((root / 'results/podman').iterdir())
        with patch.object(evidence, 'MAX_TRIALS', 20):
            self.assertEqual(len(evidence.normalize_behavioral(root, 'podman')['observations']), 20)
        for arm in ('with-skill', 'without-skill'):
            trials = run / 'codex' / arm / 'trials'
            for index in range(5990):
                member = trials / ('extra-' + str(index)) / 'result.json'
                member.parent.mkdir(); member.write_bytes(b'')
        read = evidence.read_bytes
        def no_trials(path, *args, **kwargs):
            self.assertNotIn('trials', Path(path).parts, 'Trial member read before aggregate cap')
            return read(path, *args, **kwargs)
        with patch.object(evidence, 'read_bytes', side_effect=no_trials):
            with self.assertRaisesRegex(ValueError, 'Trial input limit'):
                evidence.normalize_behavioral(root, 'podman')
        paths = sorted(p.relative_to(root) for p in root.rglob('*'))
        output = self.root / 'rejected-output'
        result = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
                                 'normalize', '--kind', 'behavioral', '--skill', 'podman',
                                 '--input', str(root), '--output', str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, 'Evidence contract rejected (ValueError)\n')
        self.assertFalse(output.exists())
        self.assertEqual(paths, sorted(p.relative_to(root) for p in root.rglob('*')))

    def test_zero_attempt_maximum_cannot_publish_complete_evidence(self):
        data = self.data()
        data['source']['content'] = evidence.content([
            {'member': 'SKILL.md', 'digest': evidence.digest_bytes(b'Synthetic source')}],
            'reconstructed_from_declared_revision')
        data['availability'].update(status='complete', reasons=[])
        data['observations'] = []
        data['policy']['attempts'].update(mode='unknown', maximum=0)
        data['policy']['id'] = evidence.identity({k: data['policy'][k] for k in
                                                ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
        for arm in data['arms']:
            arm['coverage'].update(expected_attempts=0, recorded_attempts=0, scored_attempts=0,
                                   unscored_attempts=0, case_details='complete')
            arm['rubric']['passed_cases'] = 0
        with self.assertRaisesRegex(ValueError, 'Zero attempts'):
            evidence.validate_evidence(data)
        public = copy.deepcopy(data)
        with self.assertRaisesRegex(ValueError, 'Zero attempts'):
            evidence.validate_public(public)
        path = self.root / 'zero.json'; write(path, data)
        before = path.read_bytes(); output = self.root / 'output'
        result = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
                                 'project', '--input', str(path), '--output', str(output)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, 'Evidence contract rejected (ValueError)\n')
        self.assertFalse(output.exists())
        self.assertEqual(path.read_bytes(), before)

    def test_standard_attempt_field_matches_active_standard_maximum(self):
        for mode, maximum, standard in itertools.product(
                ('standard', 'confirmation', 'unknown'), (None, 1, 3), (None, 1, 3)):
            with self.subTest(mode=mode, maximum=maximum, standard=standard):
                policy = evidence.make_policy(fields={'standard_attempts': standard},
                                              attempts={'mode': mode, 'maximum': maximum,
                                                        'stop_on_pass': None, 'pass_threshold': None},
                                              provenance='runtime_recorded')
                valid = ((maximum is None or mode == 'unknown' or maximum == evidence.reports.MODES[mode])
                         and (mode != 'standard' or maximum is None or standard is None or standard == maximum))
                if valid:
                    evidence.validate_policy(policy)
                else:
                    with self.assertRaises(ValueError): evidence.validate_policy(policy)

    def test_native_standard_attempt_field_contradiction_rejected(self):
        root = self.native()
        self.mutate(root, '/provenance.json', lambda d: d['policy'].update(standard_attempts=3))
        with self.assertRaisesRegex(ValueError, 'Standard attempt policy mismatch'):
            evidence.normalize_behavioral(root, 'podman')
        before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        output = self.root / 'output'
        result = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
                                 'normalize', '--kind', 'behavioral', '--skill', 'podman',
                                 '--input', str(root), '--output', str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, 'Evidence contract rejected (ValueError)\n')
        self.assertFalse(output.exists())
        self.assertEqual(before, {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_contradictory_recovery_rejected(self):
        root = self.native(); write(root / 'provenance.json', {'schema_version':1,'status':'incomplete','diagnostic_only':True})
        with self.assertRaises(ValueError): evidence.normalize_behavioral(root, 'podman')
        self.mutate(root, '/podman/' + next((root/'results/podman').iterdir()).name + '/result.json', lambda d: d.update(report_status='incomplete', diagnostic_only=True))
        data = evidence.normalize_behavioral(root, 'podman')
        self.assertEqual(data['availability']['status'], 'incomplete')

    def test_recovery_provenance_reconciles_supplied_identities(self):
        root = self.native(); run = next((root / 'results/podman').iterdir())
        result = evidence.read_json(run / 'result.json')
        result.update(report_status='incomplete', diagnostic_only=True); write(run / 'result.json', result)
        path = root / 'provenance.json'; original = evidence.read_json(path); original['status'] = 'incomplete'
        for key, invalid in (('skill', 'another-skill'), ('schema_version', 2),
                             ('schema_version', True), ('schema_version', '1'), ('mode', 'unsupported')):
            with self.subTest(key=key, invalid=invalid):
                value = copy.deepcopy(original); value[key] = invalid; write(path, value)
                with self.assertRaisesRegex(ValueError, 'Provenance identity mismatch|Unknown benchmark mode'):
                    evidence.normalize_behavioral(root, 'podman')
                before = self.snapshot(root); output = self.root / 'rejected-output'
                cli = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
                    'normalize', '--kind', 'behavioral', '--skill', 'podman', '--input', str(root),
                    '--output', str(output)], capture_output=True, text=True)
                self.assertEqual(cli.returncode, 1); self.assertFalse(output.exists())
                self.assertEqual(cli.stderr, 'Evidence contract rejected (ValueError)\n')
                self.assertEqual(self.snapshot(root), before)
        write(path, original)
        valid = evidence.normalize_behavioral(root, 'podman')
        self.assertIn('execution_incomplete', valid['availability']['reasons'])
        self.assertEqual(valid['metrics'], self.data()['metrics'])

    def test_normalization_aggregate_byte_budget_precedes_parsing(self):
        root = self.native(); read = evidence.read_bytes; consumed = []
        def counted(path, *args, **kwargs):
            raw = read(path, *args, **kwargs); consumed.append(len(raw)); return raw
        with patch.object(evidence, 'read_bytes', side_effect=counted):
            baseline = evidence.normalize_behavioral(root, 'podman', workspace=self.root)
        total = sum(consumed)
        with patch.object(evidence, 'NORMALIZATION_LIMIT', total, create=True):
            self.assertEqual(evidence.encoded(evidence.normalize_behavioral(root, 'podman', workspace=self.root)),
                             evidence.encoded(baseline))
        parsed = []; parse = evidence.parse_json
        def parsed_buffer(raw):
            parsed.append(len(raw)); return parse(raw)
        with patch.object(evidence, 'NORMALIZATION_LIMIT', total - 1, create=True), \
                patch.object(evidence, 'parse_json', side_effect=parsed_buffer):
            with self.assertRaisesRegex(ValueError, 'Normalization byte limit'):
                evidence.normalize_behavioral(root, 'podman', workspace=self.root)
        self.assertLessEqual(sum(parsed), total - 1)
        # Actual CLI inputs stay below the per-file limit while exceeding the aggregate limit.
        for path in sorted(root.glob('results/*/*/codex/*/trials/*/result.json'))[:10]:
            value = evidence.read_json(path); value['synthetic_padding'] = 'x' * (7 * 1024 * 1024)
            write(path, value); self.assertLess(path.stat().st_size, evidence.JSON_LIMIT)
        before = self.snapshot(root); output = self.root / 'rejected-output'
        parsed.clear()
        with patch.object(evidence, 'parse_json', side_effect=parsed_buffer):
            with self.assertRaisesRegex(ValueError, 'Normalization byte limit'):
                evidence.normalize_behavioral(root, 'podman', workspace=self.root)
        self.assertLessEqual(sum(parsed), evidence.NORMALIZATION_LIMIT)
        cli = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
            'normalize', '--kind', 'behavioral', '--skill', 'podman', '--input', str(root),
            '--output', str(output)], capture_output=True, text=True)
        self.assertEqual(cli.returncode, 1); self.assertFalse(output.exists())
        self.assertEqual(cli.stderr, 'Evidence contract rejected (ValueError)\n')
        self.assertEqual(self.snapshot(root), before)

    def test_historical_blob_shares_normalization_budget_before_capture(self):
        repo = self.repo(); path = repo / '.apm/skills/alpha/SKILL.md'
        def git(*args):
            return subprocess.run(['git', '-C', str(repo), *args], check=True,
                                  capture_output=True, text=True).stdout.strip()
        git('init', '-q')
        git('config', 'remote.origin.url', 'https://github.com/thetechgy/agent-engineering-baseline.git')
        git('add', '.apm')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
            'commit', '-qm', 'Budget fixture')
        spec = git('rev-parse', 'HEAD') + ':.apm/skills/alpha/SKILL.md'
        for remaining in (path.stat().st_size, path.stat().st_size - 1):
            with self.subTest(remaining=remaining):
                budget = evidence.ReadBudget(); evidence.workspace_repository(repo, budget=budget)
                budget.remaining = remaining
                trace = self.root / f'budget-{remaining}.jsonl'
                with git_trace(trace):
                    if remaining == path.stat().st_size:
                        self.assertEqual(evidence.historical_blob(repo, spec, budget=budget), path.read_bytes())
                        self.assertEqual(budget.remaining, 0)
                    else:
                        with self.assertRaisesRegex(ValueError, 'Normalization byte limit'):
                            evidence.historical_blob(repo, spec, budget=budget)
                commands = [e['argv'] for e in map(json.loads, trace.read_text().splitlines())
                            if e.get('event') == 'start']
                self.assertEqual(any('cat-file' in argv and 'blob' in argv for argv in commands),
                                 remaining == path.stat().st_size)

    def test_static_versions_share_aggregate_budget_before_parsing(self):
        root = self.root / 'static-budget'; shutil.copytree(FIXTURES / 'static-synthetic', root)
        total = sum(path.stat().st_size for path in root.rglob('*.json'))
        baseline = evidence.normalize_static(root, 'podman')
        with patch.object(evidence, 'NORMALIZATION_LIMIT', total):
            self.assertEqual(evidence.encoded(evidence.normalize_static(root, 'podman')), evidence.encoded(baseline))
        before = self.snapshot(root); output = self.root / 'rejected-output'
        for entry in ('api', 'cli'):
            with self.subTest(entry=entry), patch.object(evidence, 'NORMALIZATION_LIMIT', total - 1), \
                    patch.object(evidence, 'parse_json', wraps=evidence.parse_json) as parse:
                with self.assertRaisesRegex(ValueError, 'Normalization byte limit'):
                    if entry == 'api': evidence.normalize_static(root, 'podman')
                    else: evidence.main(['normalize', '--kind', 'static', '--skill', 'podman',
                                         '--input', str(root), '--output', str(output)])
                self.assertEqual(parse.call_count, 2, 'Versions parsed after byte budget exhausted')
                self.assertFalse(output.exists()); self.assertEqual(self.snapshot(root), before)

    def test_missing_historical_metadata(self):
        root = self.native(); (root/'provenance.json').unlink(); (root/'versions.json').unlink()
        data = evidence.normalize_behavioral(root, 'podman')
        self.assertEqual(len(data['observations']), 20)
        self.assertIn('metadata_missing', data['availability']['reasons'])
        self.assertIsNone(data['policy']['fields']['evaluator_revision'])

    def test_known_staged_digest_requires_algorithm(self):
        data = self.data(); self.synthetic_skill_references(data, 'podman')
        data['source']['content'] = evidence.content([
            {'member': 'SKILL.md', 'digest': evidence.digest_bytes(b'Synthetic')}], 'configured')
        data['availability'].update(status='complete', reasons=[])
        data['dataset']['staged_algorithm'] = None
        self.assert_project_rejects(data, 'Missing staged digest algorithm')
        data['dataset']['staged_algorithm'] = 'skill-evaluator-dataset-snapshot/1'; self.project_grading_fixture(data)
        data['dataset'].update(staged_digest=None, staged_algorithm=None, staged_provenance='unknown')
        data['availability'].update(status='incomplete', reasons=['metadata_missing'])
        self.assertIsNone(self.project_grading_fixture(data)['dataset']['staged_digest'])

    def test_partial_behavioral_metrics_retain_coverage_limitation(self):
        for size in range(4):
            with self.subTest(size=size):
                data = self.data(); data['source']['content'] = evidence.content()
                data['metrics'] = data['metrics'][:size]
                data['availability'].update(status='incomplete', reasons=['source_unavailable'])
                self.assert_project_rejects(data, 'Missing metric coverage limitation')
                data['availability']['reasons'].append('coverage_missing')
                self.assertEqual(len(evidence.project(data)['metrics']), size)
        root = self.native(); run = next((root / 'results/podman').iterdir())
        result = evidence.read_json(run / 'result.json'); result['agents']['codex'].pop('lift')
        write(run / 'result.json', result)
        provenance = evidence.read_json(root / 'provenance.json'); provenance.pop('metrics', None)
        write(root / 'provenance.json', provenance)
        data = evidence.normalize_behavioral(root, 'podman')
        self.assertEqual(data['metrics'], [])
        self.assertIn('coverage_missing', evidence.project(data)['availability']['reasons'])

    def test_unavailable_evidence_retains_results_limitation(self):
        for kind in ('behavioral', 'static'):
            with self.subTest(kind=kind):
                data = evidence.read_json(FIXTURES / 'gh-no-model.json') if kind == 'behavioral' else evidence.evidence('alpha', 'static')
                data['availability']['reasons'] = ['metadata_missing']
                self.assert_project_rejects(data, 'Unavailable evidence missing results limitation')
                data['availability']['reasons'].append('results_not_supplied')
                self.assertIn('results_not_supplied', evidence.project(data)['availability']['reasons'])

    def test_shared_projection_enforces_supported_evaluator_revision(self):
        for kind in ('behavioral', 'static'):
            with self.subTest(kind=kind):
                data = self.data() if kind == 'behavioral' else evidence.normalize_static(FIXTURES / 'static-synthetic', 'podman')
                if kind == 'behavioral':
                    self.synthetic_skill_references(data, 'podman')
                    data['source']['content'] = evidence.content([
                        {'member': 'SKILL.md', 'digest': evidence.digest_bytes(b'Synthetic')}], 'configured')
                    data['availability'].update(status='complete', reasons=[])
                data['policy']['fields']['evaluator_revision'] = 'f' * 40
                data['policy']['id'] = evidence.identity({k: data['policy'][k] for k in
                    ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
                self.assert_project_rejects(data, 'Unsupported native evaluator')
                data['policy']['fields']['evaluator_revision'] = evidence.reports.POLICY['evaluator_revision']
                data['policy']['id'] = evidence.identity({k: data['policy'][k] for k in
                    ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
                self.project_grading_fixture(data)
                data['policy']['fields']['evaluator_revision'] = None
                data['policy']['id'] = evidence.identity({k: data['policy'][k] for k in
                    ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
                data['availability'].update(status='incomplete', reasons=sorted(
                    set(data['availability']['reasons']) | {'metadata_missing'}))
                self.assertIsNone(evidence.validate_evidence(data)['policy']['fields']['evaluator_revision'])

    def test_shared_deterministic_grading_is_binary_and_gh_only(self):
        base = self.data(); row = base['observations'][0]
        row['deterministic_gate'] = 1
        row['deterministic_scores'] = dict.fromkeys(evidence.GATE_FIELDS, 1)
        with self.subTest(skill='podman'):
            self.assert_project_rejects(base, 'Unsupported custom grading contract')
        self.synthetic_skill_references(base, 'gh')
        for key in evidence.GATE_FIELDS:
            if key == 'gate': continue
            with self.subTest(fractional=key):
                data = copy.deepcopy(base); row = data['observations'][0]
                row['deterministic_scores'][key] = 0.5
                row['deterministic_scores']['gate'] = row['deterministic_gate'] = 0
                self.assert_project_rejects(data, 'Invalid deterministic observation')
        partial = copy.deepcopy(base); row = partial['observations'][0]
        row['deterministic_gate'] = None; row['deterministic_scores'] = dict.fromkeys(evidence.GATE_FIELDS)
        row['deterministic_scores']['commands'] = 1
        self.assert_project_rejects(partial, 'Invalid deterministic observation')
        for gate in (0, 1, 0.0, 1.0):
            data = copy.deepcopy(base); row = data['observations'][0]
            row['deterministic_scores']['authorization'] = row['deterministic_scores']['gate'] = row['deterministic_gate'] = gate
            self.assertEqual(self.project_grading_fixture(data)['observations'][0]['deterministic_gate'], gate)
        self.project_grading_fixture(self.data())
        self.project_grading_fixture(evidence.read_json(FIXTURES / 'gh-no-model.json'))

    def test_failed_gate_preserved(self):
        data = self.data(); self.synthetic_skill_references(data, 'gh'); obs = data['observations'][0]
        obs['deterministic_gate'] = 0
        obs['deterministic_scores'] = {k:0 if k in ('authorization','gate') else 1 for k in evidence.GATE_FIELDS}
        self.assertEqual(self.project_grading_fixture(data)['observations'][0]['score'], obs['score'])
        self.assertEqual(self.project_grading_fixture(data)['observations'][0]['deterministic_gate'], 0)

    def synthetic_skill_references(self, data, name):
        # Grading-only fixtures need coherent synthetic identities, not reassigned approved bytes.
        prior = data['source']['skill_id']; data['source']['skill_id'] = name
        data['availability']['provenance'] = 'synthetic'; replacements = {}
        for ref in data['references']:
            old = ref['id']; ref['member'] = ref['member'].replace('results/' + prior + '/', 'results/' + name + '/', 1)
            ref.update(artifact_id='synthetic-grading', artifact_digest=None, provenance='synthetic')
            ref['id'] = evidence.identity({k: ref[k] for k in ('artifact_id', 'member', 'locator', 'digest')})
            replacements[old] = ref['id']
        for obs in data['observations']:
            obs['references'] = [replacements[ref] for ref in obs['references']]

    def project_grading_fixture(self, data):
        # These trusted in-memory controls exercise grading/shape rules only.
        # Serialized runtime authentication is tested through project/main below.
        if data['kind'] == 'behavioral' and data['references'] \
                and all(ref['provenance'] == 'synthetic' for ref in data['references']):
            data = evidence._BehavioralEvidence(data, evidence.behavioral_claim_identity(data))
        return evidence.project(data)

    def test_behavioral_runtime_projection_binds_native_claims(self):
        root = self.native(); data = evidence.normalize_behavioral(root, 'podman')
        original = evidence.project(data)
        self.assertNotIn('_claim_digest', evidence.encoded(data).decode())
        with self.assertRaises(AttributeError): data._claim_digest = 'forged'
        plain = json.loads(evidence.encoded(data))
        with self.assertRaisesRegex(ValueError, 'Retained native behavioral bundle required'):
            evidence.project(plain)
        self.assertEqual(evidence.project(plain, behavioral_bundle=root), original)
        for field in ('score', 'metric', 'model', 'unknown-provenance'):
            with self.subTest(field=field):
                forged = copy.deepcopy(data)
                if field in ('score', 'unknown-provenance'):
                    obs = forged['observations'][0]
                    obs['score'] = obs['scores']['overall'] = obs['score'] + 0.0001
                    if field == 'unknown-provenance':
                        forged['availability']['provenance'] = 'unknown'
                        for ref in forged['references']: ref['provenance'] = 'unknown'
                elif field == 'metric': forged['metrics'][0]['value'] += 0.0001
                else:
                    forged['policy']['fields']['model'] = 'tampered-model'
                    forged['policy']['id'] = evidence.identity({k: forged['policy'][k] for k in
                        ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
                evidence.validate_evidence(forged)
                with self.assertRaises(ValueError): evidence.project(forged)
                path = root / 'evidence.json'; write(path, forged); before = self.snapshot(root)
                output = self.root / ('forged-behavior-' + field)
                with self.assertRaises(ValueError), redirect_stdout(StringIO()):
                    evidence.main(['project', '--input', str(path), '--output', str(output)])
                self.assertFalse(output.exists()); self.assertEqual(self.snapshot(root), before)
        write(root / 'evidence.json', data)
        before = self.snapshot(root); output = self.root / 'valid-behavior'
        with redirect_stdout(StringIO()):
            evidence.main(['project', '--input', str(root / 'evidence.json'), '--output', str(output)])
        self.assertEqual(evidence.read_json(output / 'public-report.json'), original)
        self.assertEqual(self.snapshot(root), before)
        for path in root.glob('results/*/*/codex/*/trials/*/result.json'): path.unlink()
        with self.assertRaises(ValueError), redirect_stdout(StringIO()):
            evidence.main(['project', '--input', str(root / 'evidence.json'), '--output', str(self.root / 'missing-native')])
        self.assertFalse((self.root / 'missing-native').exists())

    def test_relabeling_behavioral_claims_cannot_remove_native_authentication(self):
        root = self.native(); data = json.loads(evidence.encoded(evidence.normalize_behavioral(root, 'podman')))
        data['availability']['provenance'] = 'synthetic'; replacements = {}
        for ref in data['references']:
            old = ref['id']; ref.update(artifact_id='relabeled-native', provenance='synthetic')
            ref['id'] = evidence.identity({k: ref[k] for k in ('artifact_id', 'member', 'locator', 'digest')})
            replacements[old] = ref['id']
        for obs in data['observations']: obs['references'] = [replacements[ref] for ref in obs['references']]
        obs = data['observations'][0]
        obs['score'] = obs['scores']['overall'] = obs['score'] + 0.0001
        data['metrics'][0]['value'] += 0.0001
        evidence.validate_evidence(data)
        with self.assertRaisesRegex(ValueError, 'Retained native behavioral bundle required'): evidence.project(data)
        with self.assertRaisesRegex(ValueError, 'Behavioral claims differ'): evidence.project(data, behavioral_bundle=root)
        path = root / 'evidence.json'; write(path, data); before = self.snapshot(root)
        output = self.root / 'rejected-relabeling'
        with self.assertRaises(ValueError), redirect_stdout(StringIO()):
            evidence.main(['project', '--input', str(path), '--output', str(output)])
        self.assertFalse(output.exists()); self.assertEqual(self.snapshot(root), before)

    def test_behavioral_witness_binds_availability_provenance(self):
        root = self.native(); native = evidence.normalize_behavioral(root, 'podman')
        for provenance in ('synthetic', 'configured', 'unknown'):
            with self.subTest(provenance=provenance):
                forged = json.loads(evidence.encoded(native)); forged['availability']['provenance'] = provenance
                evidence.validate_evidence(forged)
                with self.assertRaisesRegex(ValueError, 'Behavioral claims differ'):
                    evidence.project(forged, behavioral_bundle=root)
                path = root / 'evidence.json'; write(path, forged); before = self.snapshot(root)
                output = self.root / ('rejected-provenance-' + provenance)
                with self.assertRaises(ValueError), redirect_stdout(StringIO()):
                    evidence.main(['project', '--input', str(path), '--output', str(output)])
                self.assertFalse(output.exists()); self.assertEqual(self.snapshot(root), before)

    def test_behavioral_witness_preserves_native_required_limitations(self):
        root = self.native(); result = next(root.glob('results/podman/*/result.json'))
        raw = evidence.read_json(result); raw['diagnostic_only'] = True; write(result, raw)
        native = evidence.normalize_behavioral(root, 'podman')
        self.assertNotIn('_required_reasons', evidence.encoded(native).decode())
        with self.assertRaises(AttributeError): native._required_reasons = ()
        self.assertIn('execution_incomplete', evidence.project(native)['availability']['reasons'])
        forged = copy.deepcopy(native); forged['availability']['reasons'].remove('execution_incomplete')
        forged['availability']['status'] = 'incomplete' if forged['availability']['reasons'] else 'complete'
        evidence.validate_evidence(forged)
        for data in (forged, copy.deepcopy(forged)):
            with self.assertRaisesRegex(ValueError, 'Native behavioral limitations removed'): evidence.project(data)
        plain = json.loads(evidence.encoded(forged))
        with self.assertRaisesRegex(ValueError, 'Native behavioral limitations removed'):
            evidence.project(plain, behavioral_bundle=root)
        path = root / 'evidence.json'; write(path, plain); before = self.snapshot(root)
        output = self.root / 'rejected-diagnostic-promotion'
        with self.assertRaises(ValueError), redirect_stdout(StringIO()):
            evidence.main(['project', '--input', str(path), '--output', str(output)])
        self.assertFalse(output.exists()); self.assertEqual(self.snapshot(root), before)
        conservative = copy.deepcopy(native)
        conservative['references'][0]['availability'] = 'unavailable'
        conservative['availability']['reasons'] = sorted(set(conservative['availability']['reasons']) | {'reference_unavailable'})
        self.assertIn('execution_incomplete', evidence.project(conservative)['availability']['reasons'])

    def test_reviewed_availability_provenance_binds_pinned_references(self):
        native = self.data()
        for provenance in ('synthetic', 'configured', 'unknown'):
            with self.subTest(provenance=provenance):
                forged = copy.deepcopy(native); forged['availability']['provenance'] = provenance
                self.assert_project_rejects(forged, 'Reviewed availability provenance mismatch')

    def test_normalization_optional_members_use_captured_entries(self):
        for kind in ('behavioral', 'static'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / 'native'
                shutil.copytree(FIXTURES / ('podman-native' if kind == 'behavioral' else 'static-synthetic'), root)
                if kind == 'behavioral': (root / 'extract-manifest.json').unlink()
                versions = root / 'versions.json'; data = evidence.read_json(versions)
                data['skillevaluator'] = '0.9.0'; write(versions, data)
                exists = Path.exists; hidden = []
                def absent(path):
                    if path == versions: hidden.append(True); return False
                    return exists(path)
                before = self.snapshot(root); output = Path(temp) / 'rejected-hidden-versions'
                with patch.object(Path, 'exists', absent), self.assertRaisesRegex(ValueError, 'Unsupported native evaluator'), \
                        redirect_stdout(StringIO()):
                    evidence.main(['normalize', '--kind', kind, '--skill', 'podman', '--input', str(root),
                                   '--output', str(output)])
                self.assertFalse(hidden); self.assertFalse(output.exists()); self.assertEqual(self.snapshot(root), before)

    @contextmanager
    def hide_member_during_scan(self, member):
        scan = os.scandir; parent = member.parent; state = parent.stat(); hidden = parent.parent / 'hidden-scan-member'
        class CapturedEntries:
            def __init__(self, entries): self.entries = entries
            def __enter__(self): return iter(self.entries)
            def __exit__(self, *_): return False
        def subset(path):
            if type(path) is int and (os.fstat(path).st_dev, os.fstat(path).st_ino) == (state.st_dev, state.st_ino):
                member.rename(hidden)
                try:
                    with scan(path) as entries: captured = list(entries)
                finally:
                    hidden.rename(member)
                    os.utime(parent, ns=(state.st_atime_ns, state.st_mtime_ns))
                return CapturedEntries(captured)
            return scan(path)
        with patch.object(os, 'scandir', subset): yield

    def test_native_scan_rejects_transient_hidden_metadata(self):
        for kind in ('behavioral', 'static'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / 'native'
                shutil.copytree(FIXTURES / ('podman-native' if kind == 'behavioral' else 'static-synthetic'), root)
                if kind == 'behavioral': (root / 'extract-manifest.json').unlink()
                before = self.snapshot(root); output = Path(temp) / 'rejected-hidden-scan'
                with self.hide_member_during_scan(root / 'versions.json'), \
                        self.assertRaisesRegex(ValueError, 'Input directory entries changed'), redirect_stdout(StringIO()):
                    evidence.main(['normalize', '--kind', kind, '--skill', 'podman', '--input', str(root),
                                   '--output', str(output)])
                self.assertFalse(output.exists()); self.assertEqual(self.snapshot(root), before)

    def test_inventory_scan_rejects_transient_hidden_marker(self):
        from skillevaluator.tier3.harbor import adapter
        from skillevaluator.tier3 import output_provenance
        root = self.repo(); authored = root / '.apm/skills/alpha'
        marker = authored / output_provenance.GENERATED_OUTPUT_MARKER; marker.write_text('hidden marker')
        before = self.snapshot(root)
        with self.hide_member_during_scan(marker), \
                patch.object(adapter, '_runtime_skill_copy_ignore', return_value=lambda *_: set()) as selector, \
                patch.object(adapter, 'is_generated_output_root') as authenticate, \
                patch.object(output_provenance, '_load_existing_key') as key:
            with self.assertRaisesRegex(ValueError, 'Input directory entries changed'): evidence.inventory(root)
        selector.assert_not_called(); authenticate.assert_not_called(); key.assert_not_called()
        self.assertEqual(self.snapshot(root), before)

    def test_scan_state_rejects_changes_after_last_capture(self):
        for operation in ('static', 'inventory'):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / 'input'; output = Path(temp) / 'rejected-late-change'
                if operation == 'static':
                    shutil.copytree(FIXTURES / 'static-synthetic', root)
                    target = root / 'versions.json'; changed_tree = root
                    args = ['normalize', '--kind', 'static', '--skill', 'podman', '--input', str(root)]
                else:
                    changed_tree = self.local(root, 'alpha', True)
                    target = changed_tree / 'evals/evals.json'; args = ['inventory']
                read = evidence.read_bytes; inventory = evidence.inventory; snapshots = []
                def changed(path, *args, **kwargs):
                    raw = read(path, *args, **kwargs)
                    if path == target:
                        (changed_tree / 'late-unscanned.txt').write_text('late namespace change')
                        snapshots.append(self.snapshot(root))
                    return raw
                with patch.object(evidence, 'read_bytes', side_effect=changed), \
                        patch.object(evidence, 'inventory', side_effect=lambda: inventory(root)), \
                        self.assertRaisesRegex(ValueError, 'Input directory entries changed'), redirect_stdout(StringIO()):
                    evidence.main([*args, '--output', str(output)])
                self.assertFalse(output.exists()); self.assertEqual(self.snapshot(root), snapshots[0])

    def test_member_state_rejects_transient_in_place_edits(self):
        for operation, stage in itertools.product(('static', 'behavioral', 'inventory'), ('before', 'during', 'after')):
            with self.subTest(operation=operation, stage=stage), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / 'input'; output = Path(temp) / 'rejected-member-change'
                if operation == 'inventory':
                    target = self.local(root, 'alpha') / 'SKILL.md'
                    changed = target.read_bytes().replace(b'Synthetic fixture', b'Transient fixture')
                    args = ['inventory']
                else:
                    shutil.copytree(FIXTURES / ('static-synthetic' if operation == 'static' else 'podman-native'), root)
                    if operation == 'static':
                        target = root / 'versions.json'; value = evidence.read_json(target); value.pop('fixture')
                    else:
                        (root / 'extract-manifest.json').unlink()
                        target = next(root.glob('results/podman/*/result.json'))
                        value = evidence.read_json(target); value['report_status'] = 'diagnostic_only'
                    changed = evidence.encoded(value)
                    args = ['normalize', '--kind', operation, '--skill', 'podman', '--input', str(root)]
                original = target.read_bytes(); state = target.stat(); before = self.snapshot(root)
                read = evidence.read_bytes; inventory = evidence.inventory; attempted = False
                def restored(path, *args, **kwargs):
                    nonlocal attempted
                    if path != target or stage == 'during': return read(path, *args, **kwargs)
                    attempted = True
                    if stage == 'after': raw = read(path, *args, **kwargs)
                    target.write_bytes(changed)
                    try:
                        if stage == 'before': raw = read(path, *args, **kwargs)
                    finally:
                        target.write_bytes(original); os.utime(target, ns=(state.st_atime_ns, state.st_mtime_ns))
                    return raw
                fdopen = os.fdopen
                class EditingRead:
                    def __init__(self, stream): self.stream = stream
                    def __enter__(self): return self
                    def __exit__(self, *args): return self.stream.__exit__(*args)
                    def fileno(self): return self.stream.fileno()
                    def read(self, *args):
                        nonlocal attempted
                        attempted = True; target.write_bytes(changed)
                        try: return self.stream.read(*args)
                        finally:
                            target.write_bytes(original); os.utime(target, ns=(state.st_atime_ns, state.st_mtime_ns))
                def edited_stream(fd, *args, **kwargs):
                    stream = fdopen(fd, *args, **kwargs)
                    return EditingRead(stream) if stage == 'during' and (os.fstat(fd).st_dev, os.fstat(fd).st_ino) \
                        == (state.st_dev, state.st_ino) else stream
                with patch.object(evidence, 'read_bytes', side_effect=restored), \
                        patch.object(os, 'fdopen', side_effect=edited_stream), \
                        patch.object(evidence, 'inventory', side_effect=lambda: inventory(root)), \
                        self.assertRaisesRegex(ValueError, 'Input member changed'), redirect_stdout(StringIO()):
                    evidence.main([*args, '--output', str(output)])
                self.assertTrue(attempted); self.assertFalse(output.exists()); self.assertEqual(self.snapshot(root), before)

    def test_behavioral_trials_use_captured_scan_entries(self):
        root = self.native(); trials = next(root.glob('results/podman/*/codex/with-skill/trials'))
        original = next(trials.glob('*/result.json')); extra = trials / 'hidden-extra'; extra.mkdir()
        data = evidence.read_json(original); data.update(trial_name=extra.name, id='extra-native-id')
        write(extra / 'result.json', data)
        retained = self.root / 'temporarily-hidden'; glob = Path.glob; hidden = []
        def subset(path, pattern, *args, **kwargs):
            if path == trials and pattern == '*/result.json':
                extra.rename(retained)
                try: members = list(glob(path, pattern, *args, **kwargs))
                finally: retained.rename(extra)
                hidden.append(True)
                return iter(members)
            return glob(path, pattern, *args, **kwargs)
        before = self.snapshot(root); output = self.root / 'rejected-subset'
        with patch.object(Path, 'glob', subset), self.assertRaisesRegex(ValueError, 'Native trial/summary score mismatch'), \
                redirect_stdout(StringIO()):
            evidence.main(['normalize', '--kind', 'behavioral', '--skill', 'podman', '--input', str(root),
                           '--output', str(output)])
        self.assertFalse(hidden); self.assertFalse(output.exists()); self.assertEqual(self.snapshot(root), before)

    def test_behavioral_run_selection_uses_captured_entries(self):
        root = self.native(); base = root / 'results/podman'; original = next(base.iterdir())
        second = base / 'other-recorded-run'; shutil.copytree(original, second)
        retained = self.root / 'temporarily-hidden-run'; iterdir = Path.iterdir; hidden = []
        def subset(path):
            if path == base:
                second.rename(retained)
                try: members = list(iterdir(path))
                finally: retained.rename(second)
                hidden.append(True); return iter(members)
            return iterdir(path)
        before = self.snapshot(root); output = self.root / 'rejected-hidden-run'
        with patch.object(Path, 'iterdir', subset), self.assertRaisesRegex(ValueError, 'Explicit --run required'), \
                redirect_stdout(StringIO()):
            evidence.main(['normalize', '--kind', 'behavioral', '--skill', 'podman', '--input', str(root),
                           '--output', str(output)])
        self.assertFalse(hidden); self.assertFalse(output.exists()); self.assertEqual(self.snapshot(root), before)

    def test_tree_scan_enumerates_validated_directory_descriptors(self):
        root = self.root / 'scanned'; root.mkdir(); (root / 'original.json').write_text('{}')
        subset = self.root / 'subset'; subset.mkdir(); retained = self.root / 'retained'
        before = self.snapshot(root); scan = evidence.os.scandir; swapped = False
        def replacing(path):
            nonlocal swapped
            if not swapped:
                swapped = True; root.rename(retained); subset.rename(root)
                try: entries = scan(path)
                finally: root.rename(subset); retained.rename(root)
                return entries
            return scan(path)
        with patch.object(evidence.os, 'scandir', side_effect=replacing):
            with self.assertRaisesRegex(ValueError, 'Input directory entries changed'):
                evidence.safe_tree(root)
        self.assertTrue(swapped); self.assertEqual(self.snapshot(root), before)

    def test_static_projection_binds_claims_to_retained_native_bytes(self):
        root = self.root / 'retained-static'
        shutil.copytree(FIXTURES / 'static-synthetic', root)
        data = evidence.normalize_static(root, 'podman')
        original = evidence.project(data)
        self.assertNotIn('_claim_digest', evidence.encoded(data).decode())
        forged = copy.deepcopy(data)
        forged['scans'][1]['blocking'] = False
        forged['scans'][0]['passed'] = True
        # A self-consistent shape alone cannot authenticate the native gate.
        evidence.validate_evidence(forged); evidence.validate_public(forged)
        with self.assertRaisesRegex(ValueError, 'Static claims differ'):
            evidence.project(forged)
        with self.assertRaises(AttributeError): data._claim_digest = 'forged'
        plain = json.loads(evidence.encoded(data))
        with self.assertRaisesRegex(ValueError, 'Retained native static bundle required'):
            evidence.project(plain)
        self.assertEqual(evidence.project(plain, static_bundle=root), original)
        for case, record in (('original', data), ('forged', forged)):
            with self.subTest(case=case):
                path = root / 'evidence.json'; write(path, record)
                before = self.snapshot(root); output = self.root / case
                result = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
                    'project', '--input', str(path), '--output', str(output)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0 if case == 'original' else 1, result.stderr)
                self.assertEqual(self.snapshot(root), before)
                self.assertEqual(output.exists(), case == 'original')
                if case == 'original':
                    self.assertEqual(evidence.read_json(output / 'public-report.json'), original)
        write(root / 'evidence.json', data)
        next((root / 'reports/podman').glob('*.json')).unlink()
        before = self.snapshot(root); output = self.root / 'missing'
        result = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
            'project', '--input', str(root / 'evidence.json'), '--output', str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1); self.assertFalse(output.exists())
        self.assertEqual(self.snapshot(root), before)

    def test_static_projection_cli_protects_retained_bundle(self):
        for placement in ('explicit-root', 'explicit-nested', 'relative-root', 'temporary-root', 'temporary-nested'):
            with self.subTest(placement=placement):
                root = self.root / placement
                shutil.copytree(FIXTURES / 'static-synthetic', root)
                write(root / 'evidence.json', evidence.normalize_static(root, 'podman'))
                before = self.snapshot(root)
                command = [sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
                           'project', '--input', str(root / 'evidence.json')]
                env = {**os.environ, 'TMPDIR': str(self.root)}
                if placement.startswith('temporary'):
                    env['TMPDIR'] = str(root / 'reports' if placement.endswith('nested') else root)
                else:
                    output = root / 'reports/podman/published' if placement.endswith('nested') else root / 'published'
                    command.extend(['--output', str(output)])
                    if placement == 'relative-root':
                        command[command.index('--input') + 1] = f'{root.name}/evidence.json'
                        command[-1] = f'{root.name}/published'
                result = subprocess.run(command, cwd=self.root, env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('Evidence contract rejected', result.stderr)
                self.assertEqual(self.snapshot(root), before)

        # External temporary output still publishes the same verified projection.
        result = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
            'project', '--input', str(root / 'evidence.json')],
            env={**os.environ, 'TMPDIR': str(self.root)}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = Path(result.stdout.strip())
        self.assertEqual(evidence.read_json(output / 'public-report.json'),
                         evidence.project(evidence.normalize_static(root, 'podman')))
        self.assertEqual(self.snapshot(root), before)

    def test_static_native_contract_and_diagnostic_exclusion(self):
        data = evidence.normalize_static(FIXTURES/'static-synthetic', 'podman')
        self.assertEqual(data['availability']['status'], 'incomplete')
        self.assertEqual(data['availability']['provenance'], 'synthetic')
        self.assertEqual(data['scans'][0]['severity_counts']['high'], 1)
        self.assertEqual(data['findings'][0]['member'], 'SKILL.md')
        report = evidence.encoded(evidence.project(data)).decode()
        self.assertNotIn('Synthetic diagnostic', report)
        self.assertEqual(data['metrics'], [])
        data['availability'].update(status='complete', reasons=[])
        with self.assertRaises(ValueError): evidence.project(data)

    def test_complete_static_scans_require_references(self):
        base = evidence.normalize_static(FIXTURES / 'static-synthetic', 'podman')
        base['scans'] = base['scans'][:2]  # A passing fixture omits the underlying unavailable diagnostic.
        base['source']['content'] = evidence.content([
            {'member': 'SKILL.md', 'digest': evidence.digest_bytes(b'Synthetic')}], 'configured')
        base['availability'].update(status='complete', reasons=[])
        base['findings'] = []
        for scan in base['scans']:
            scan.update(status='passed', passed=True, severity_counts=dict.fromkeys(scan['severity_counts'], 0))
        evidence.validate_evidence(base)
        for index in range(len(base['scans'])):
            with self.subTest(scan=index):
                data = copy.deepcopy(base); data['scans'][index]['references'] = []
                self.assert_project_rejects(data, 'Complete scan missing reference')
                data['availability'].update(status='incomplete', reasons=['reference_unavailable'])
                evidence.validate_evidence(data)

    def test_observed_static_evidence_requires_catalog_aggregate(self):
        for status in ('complete', 'incomplete'):
            with self.subTest(status=status):
                data = evidence.normalize_static(FIXTURES / 'static-synthetic', 'podman')
                if status == 'complete':
                    data['scans'] = data['scans'][:2]
                    data['source']['content'] = evidence.content([
                        {'member': 'SKILL.md', 'digest': evidence.digest_bytes(b'Synthetic')}], 'configured')
                    data['availability'].update(status='complete', reasons=[])
                    data['findings'] = []
                    for scan in data['scans']:
                        scan.update(status='passed', passed=True,
                                    severity_counts=dict.fromkeys(scan['severity_counts'], 0))
                evidence.validate_evidence(data)
                aggregate = next(scan for scan in data['scans'] if scan['scanner'] == 'catalog-total')
                data['scans'].remove(aggregate)
                self.assert_project_rejects(data, 'Static evidence missing aggregate scan')
                data['scans'].append(aggregate); evidence.validate_evidence(data)
                data['scans'].append(copy.deepcopy(aggregate))
                self.assert_project_rejects(data, 'Duplicate scanner')
        evidence.project(evidence.evidence('podman', 'static'))

    def test_static_aggregate_requires_known_severity_totals(self):
        for status, levels in itertools.product(('complete', 'incomplete'),
                [('critical',), ('high',), ('medium',), ('low',), ('critical', 'high', 'medium', 'low')]):
            with self.subTest(status=status, levels=levels):
                data = evidence.normalize_static(FIXTURES / 'static-synthetic', 'podman')
                if status == 'complete':
                    data['scans'] = data['scans'][:2]
                    data['source']['content'] = evidence.content([
                        {'member': 'SKILL.md', 'digest': evidence.digest_bytes(b'Synthetic')}], 'configured')
                    data['availability'].update(status='complete', reasons=[]); data['findings'] = []
                    for scan in data['scans']:
                        scan.update(status='passed', passed=True,
                                    severity_counts=dict.fromkeys(scan['severity_counts'], 0))
                aggregate = next(scan for scan in data['scans'] if scan['scanner'] == 'catalog-total')
                counts = copy.deepcopy(aggregate['severity_counts'])
                for level in levels: aggregate['severity_counts'][level] = None
                self.assert_project_rejects(data, 'Unknown static aggregate totals')
                aggregate['severity_counts'] = counts
                self.assertEqual(evidence.validate_evidence(data)['scans'][0]['severity_counts'], counts)

    def test_static_aggregate_retains_native_pass_boolean(self):
        data = evidence.normalize_static(FIXTURES / 'static-synthetic', 'podman')
        aggregate = next(scan for scan in data['scans'] if scan['scanner'] == 'catalog-total')
        aggregate.update(status='incomplete', passed=None)
        self.assert_project_rejects(data, 'Missing static aggregate pass result')
        for passed in (True, False):
            aggregate['passed'] = passed
            data['scans'][1]['blocking'] = not passed
            self.assertEqual(evidence.validate_evidence(data)['scans'][0]['passed'], passed)
        aggregate['status'] = 'skipped'
        self.assert_project_rejects(data, 'Invalid enum')  # Native overall status is never skipped.

    def test_reviewed_reference_provenance_matches_pinned_member_identity(self):
        root = self.native(); ordinary = evidence.normalize_behavioral(root, 'podman')
        for archive in (None, 'sha256:' + 'a' * 64):
            with self.subTest(archive=archive):
                data = copy.deepcopy(ordinary)
                data['references'][0].update(provenance='reviewed_extract', artifact_digest=archive)
                self.assert_project_rejects(data, 'Unrecognized reviewed reference identity')
        claimed = copy.deepcopy(ordinary); claimed['availability']['provenance'] = 'reviewed_extract'
        self.assert_project_rejects(claimed, 'Reviewed availability missing reviewed references')
        approved = self.data(); ref = approved['references'][0]
        for key, value in (('artifact_id', 'another-artifact'), ('artifact_digest', 'sha256:' + 'a' * 64),
                           ('member', 'another.json'), ('digest', 'sha256:' + 'b' * 64)):
            with self.subTest(key=key):
                data = copy.deepcopy(approved); changed = data['references'][0]; old_id = changed['id']
                changed[key] = value
                changed['id'] = evidence.identity({k: changed[k] for k in ('artifact_id', 'member', 'locator', 'digest')})
                for observation in data['observations']:
                    observation['references'] = [changed['id'] if item == old_id else item for item in observation['references']]
                self.assert_project_rejects(data, 'Unrecognized reviewed reference identity')
        evidence.project(approved)
        manifest_path = FIXTURES / 'podman-native/extract-manifest.json'
        self.assertIn(evidence.digest_bytes(manifest_path.read_bytes()), evidence.REVIEWED_EXTRACT_MANIFESTS)
        manifest = evidence.read_json(manifest_path)
        self.assertEqual(evidence.REVIEWED_REFERENCE_EXPIRY,
                         {(manifest['artifact_id'], manifest['archive_digest']): manifest['origin']['expires_at']})
        identities = {evidence.identity({'artifact_id': manifest['artifact_id'], 'artifact_digest': manifest['archive_digest'],
                                        'member': row['member'], 'digest': row['original_digest'],
                                        'locator': ['verifier_result', 'rewards'] if '/trials/' in row['member']
                                        and row['member'].endswith('/result.json') else []}) for row in manifest['members']}
        self.assertEqual(identities, evidence.REVIEWED_REFERENCE_IDENTITIES)

    def test_reviewed_identity_cannot_be_stripped_to_bypass_expiry(self):
        base = self.data()
        deadline = datetime.fromisoformat(next(iter(evidence.REVIEWED_REFERENCE_EXPIRY.values())))
        for archive, provenance, mutate in itertools.product((False, True), (False, True), (False, True)):
            if not archive and not provenance: continue
            with self.subTest(archive=archive, provenance=provenance, mutate=mutate):
                data = copy.deepcopy(base); ids = [r['id'] for r in data['references']]
                if archive:
                    for ref in data['references']: ref['artifact_digest'] = None
                if provenance:
                    data['availability']['provenance'] = 'runtime_recorded'
                    for ref in data['references']: ref['provenance'] = 'runtime_recorded'
                if mutate:
                    data['metrics'][0]['value'] += 0.0001
                    obs = data['observations'][0]; obs['score'] = obs['scores']['overall'] = obs['score'] + 0.0001
                self.assertEqual([r['id'] for r in data['references']], ids)
                with patch.object(evidence, 'utc_now', return_value=deadline):
                    with self.assertRaises(ValueError): evidence.validate_evidence(data)
                    with self.assertRaises(ValueError): evidence.project(data)
                    public = copy.deepcopy(data)
                    for obs in public['observations']:
                        for key in ('native_id', 'native_trial', 'native_task'): obs.pop(key)
                    with self.assertRaises(ValueError): evidence.validate_public(public)
                path = self.root / 'stripped-evidence.json'; write(path, data)
                before = self.snapshot(self.root); output = self.root / 'stripped-output'
                with patch.object(evidence, 'utc_now', return_value=deadline), redirect_stdout(StringIO()):
                    with self.assertRaises(ValueError):
                        evidence.main(['project', '--input', str(path), '--output', str(output)])
                self.assertFalse(output.exists()); self.assertEqual(self.snapshot(self.root), before)

        with patch.object(evidence, 'utc_now', return_value=deadline):
            ordinary = evidence.normalize_behavioral(self.native(), 'podman')
            evidence.project(ordinary)
            self.assertTrue(all(ref['availability'] == 'available' for ref in ordinary['references']))

    def test_normalization_retains_scanned_bundle_identity(self):
        for kind in ('static', 'behavioral'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                parent = Path(temp); root = parent / 'input'; retained = parent / 'retained'
                source = FIXTURES / ('static-synthetic' if kind == 'static' else 'podman-native')
                shutil.copytree(source, root)
                before = self.snapshot(root); scan = evidence.safe_tree; swapped = False
                def replacing(path, *args, **kwargs):
                    nonlocal swapped
                    files = scan(path, *args, **kwargs)
                    if Path(path) == root and not swapped:
                        swapped = True; root.rename(retained); shutil.copytree(retained, root)
                    return files
                output = parent / 'output'
                with patch.object(evidence, 'safe_tree', side_effect=replacing), \
                        patch.object(evidence, 'parse_json', wraps=evidence.parse_json) as parse, \
                        redirect_stdout(StringIO()):
                    with self.assertRaisesRegex(ValueError, 'Input directory changed'):
                        evidence.main(['normalize', '--kind', kind, '--skill', 'podman',
                                       '--input', str(root), '--output', str(output)])
                self.assertTrue(swapped)
                parse.assert_not_called(); self.assertFalse(output.exists())
                self.assertEqual(self.snapshot(root), before); self.assertEqual(self.snapshot(retained), before)

    def test_reviewed_reference_locators_match_approved_reference_identity(self):
        base = self.data()
        trial = next(ref for ref in base['references'] if '/trials/' in ref['member'] and ref['member'].endswith('/result.json'))
        for locator in ([], ['task_name'], ['verifier_result'], ['verifier_result', 'rewards', 'overall']):
            with self.subTest(locator=locator):
                # These are valid locators in the retained extract, but not its approved reference location.
                retained = evidence.read_json(FIXTURES / 'podman-native' / trial['member'])
                for component in locator: retained = retained[component]
                data = copy.deepcopy(base); changed = next(ref for ref in data['references'] if ref['id'] == trial['id'])
                changed['locator'] = locator
                changed['id'] = evidence.identity({k: changed[k] for k in ('artifact_id', 'member', 'locator', 'digest')})
                for row in data['observations']:
                    row['references'] = [changed['id'] if ref == trial['id'] else ref for ref in row['references']]
                self.assert_project_rejects(data, 'Unrecognized reviewed reference identity')
        self.assertEqual(evidence.project(base)['references'], base['references'])

    def test_observation_references_bind_native_trial_and_arm(self):
        base = self.data(); receiver = base['observations'][0]
        refs = {ref['id']: ref for ref in base['references']}
        for boundary in ('case', 'arm'):
            donor = next(obs for obs in base['observations'] if
                (obs['arm'] == receiver['arm'] and obs['case_id'] != receiver['case_id'] if boundary == 'case'
                 else obs['arm'] != receiver['arm'] and obs['case_id'] == receiver['case_id']))
            for role in ('all', 'result.json', 'reward.json', 'summary.json'):
                if role == 'summary.json' and boundary == 'case': continue
                with self.subTest(boundary=boundary, role=role):
                    data = copy.deepcopy(base); target = data['observations'][0]
                    if role == 'all': target['references'] = donor['references'][:]
                    else:
                        replacement = next(ref for ref in donor['references'] if refs[ref]['member'].endswith('/' + role))
                        target['references'] = [replacement if refs[ref]['member'].endswith('/' + role) else ref
                                                for ref in target['references']]
                    with self.assertRaisesRegex(ValueError, 'Observation reference origin mismatch'): evidence.project(data)
                    path = self.root / 'reassigned.json'; write(path, data); before = path.read_bytes()
                    output = self.root / 'rejected-output'
                    result = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
                        'project', '--input', str(path), '--output', str(output)], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 1); self.assertFalse(output.exists())
                    self.assertEqual(path.read_bytes(), before)
        self.assertEqual(evidence.project(base)['references'], base['references'])

    def test_reviewed_observations_bind_immutable_payload(self):
        base = self.data()
        public = evidence.project(base)
        for mutation in ('swap', 'score'):
            with self.subTest(mutation=mutation):
                data = copy.deepcopy(base); first, second = data['observations'][:2]
                self.assertEqual(first['arm'], second['arm'])
                if mutation == 'swap':
                    for key in ('native_trial', 'native_id', 'native_task', 'references'):
                        first[key], second[key] = second[key], first[key]
                    for obs in (first, second):
                        obs['id'] = evidence.observation_id(data['run_id'], obs['arm'], obs['case_id'],
                            obs['native_id'], obs['native_trial'], obs['attempt'])
                else: first['score'] = first['scores']['overall'] = 0.99
                self.assert_project_rejects(data, 'Unrecognized reviewed observation payload')
        expired = copy.deepcopy(base)
        for ref in expired['references']: ref['availability'] = 'expired'
        expired['availability']['status'] = 'incomplete'
        expired['availability']['reasons'].append('reference_expired')
        self.assertEqual(evidence.project(expired)['observations'], public['observations'])
        self.assertEqual({evidence.identity(obs) for obs in public['observations']},
                         evidence.REVIEWED_OBSERVATION_PAYLOADS)

    def test_reviewed_metrics_bind_approved_values(self):
        base = self.data()
        for index, metric in enumerate(base['metrics']):
            with self.subTest(metric=metric['name']):
                data = copy.deepcopy(base); data['metrics'][index]['value'] = 0.99
                self.assert_project_rejects(data, 'Unrecognized reviewed metric value')
        self.assertEqual({row['name']: row['value'] for row in base['metrics']}, evidence.REVIEWED_METRIC_VALUES)
        data = copy.deepcopy(base); data['metrics'] = data['metrics'][:1]
        data['availability'].update(status='incomplete', reasons=sorted(set(data['availability']['reasons']) | {'coverage_missing'}))
        self.assertEqual(evidence.project(data)['metrics'], base['metrics'][:1])

    def test_reviewed_source_binds_complete_approved_identity(self):
        base = self.data()
        for changed in ('repository', 'revision', 'content', 'owner', 'source_path', 'lineage'):
            with self.subTest(changed=changed):
                data = copy.deepcopy(base)
                values = {'repository': 'example/other', 'revision': 'a' * 40, 'owner': 'upstream',
                          'source_path': 'skills/other', 'lineage': {'repository': 'example/other', 'revision': 'a' * 40,
                          'source_path': 'skills/other'}, 'content': evidence.content([
                          {'member': 'SKILL.md', 'digest': evidence.digest_bytes(b'Synthetic other source')}],
                          'reconstructed_from_declared_revision')}
                data['source'][changed] = values[changed]
                self.assert_project_rejects(data, 'Unrecognized reviewed source identity')
        unknown = copy.deepcopy(base); unknown['source']['content'] = evidence.content()
        unknown['availability'].update(status='incomplete', reasons=sorted(set(unknown['availability']['reasons']) | {'source_unavailable'}))
        self.assertIsNone(evidence.project(unknown)['source']['content']['digest'])
        self.assertIn(evidence.identity(base['source']), evidence.REVIEWED_SOURCE_IDENTITIES)
        self.assertIn(evidence.identity(unknown['source']), evidence.REVIEWED_SOURCE_IDENTITIES)

    def test_reviewed_execution_contract_binds_metadata_carriers(self):
        base = self.data()
        for changed in ('model', 'staged_digest', 'authored_digest', 'instruction_digest', 'build_digest'):
            with self.subTest(changed=changed):
                data = copy.deepcopy(base)
                if changed == 'model':
                    data['policy']['fields']['model'] = 'different-model'
                    data['policy']['id'] = evidence.identity({key: data['policy'][key] for key in
                        ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
                elif changed in ('staged_digest', 'authored_digest'):
                    data['dataset'][changed] = evidence.digest_bytes(b'Synthetic other dataset')
                    if changed == 'authored_digest': data['dataset']['authored_provenance'] = 'reconstructed_from_declared_revision'
                else:
                    for arm in data['arms']:
                        arm['condition'][changed] = evidence.digest_bytes(b'Synthetic other contract')
                        arm['condition']['id'] = evidence.identity({key: value for key, value in arm['condition'].items() if key != 'id'})
                self.assert_project_rejects(data, 'Unrecognized reviewed execution contract')
        known = {key: base[key] for key in ('run_id', 'dataset', 'policy', 'arms')}
        self.assertIn(evidence.identity(known), evidence.REVIEWED_EXECUTION_CONTRACTS)
        unknown = copy.deepcopy(base); unknown['dataset'].update(authored_digest=None, authored_provenance='unknown')
        self.assertEqual(evidence.project(unknown)['metrics'], base['metrics'])
        unavailable = evidence.normalize_behavioral(FIXTURES / 'podman-native', 'podman', workspace=self.root)
        self.assertIsNone(unavailable['source']['content']['digest'])
        self.assertIsNone(unavailable['dataset']['authored_digest'])
        self.assertEqual(evidence.project(unavailable)['metrics'], base['metrics'])

    def test_static_references_bind_declared_skill(self):
        base = evidence.normalize_static(FIXTURES / 'static-synthetic', 'podman')
        data = copy.deepcopy(base); data['source']['skill_id'] = 'gh'
        self.assert_project_rejects(data, 'Static reference skill mismatch')
        data = copy.deepcopy(base); replacements = {}
        for ref in data['references']:
            if ref['member'].startswith('reports/podman/'):
                old = ref['id']; ref['member'] = ref['member'].replace('reports/podman/', 'reports/gh/', 1)
                ref['id'] = evidence.identity({key: ref[key] for key in ('artifact_id', 'member', 'locator', 'digest')})
                replacements[old] = ref['id']
        for scan in data['scans']: scan['references'] = [replacements.get(ref, ref) for ref in scan['references']]
        for finding in data['findings']: finding['reference'] = replacements.get(finding['reference'], finding['reference'])
        self.assert_project_rejects(data, 'Static reference skill mismatch')
        self.assertEqual(evidence.project(base)['scans'], base['scans'])

    def test_static_claim_references_bind_structured_positions(self):
        root = self.root / 'static-positions'; shutil.copytree(FIXTURES / 'static-synthetic', root)
        path = next((root / 'reports/podman').glob('*.json')); native = evidence.read_json(path)
        second = copy.deepcopy(native['results'][0]); second['validator'] = 'SECOND'
        native['results'].append(second); native['total_validators'] = 2; native['severity_counts']['high'] = 2
        write(path, native); base = evidence.normalize_static(root, 'podman')
        for changed in ('scan', 'finding', 'aggregate', 'finding-to-scan'):
            with self.subTest(changed=changed):
                data = copy.deepcopy(base)
                if changed == 'scan': data['scans'][1]['references'] = data['scans'][2]['references'][:]
                elif changed == 'finding': data['findings'][0]['reference'] = data['findings'][1]['reference']
                elif changed == 'aggregate': data['scans'][0]['references'] = data['scans'][1]['references'][:]
                else: data['findings'][0]['reference'] = data['scans'][1]['references'][0]
                self.assert_project_rejects(data, 'Static claim locator mismatch')
        self.assertEqual(evidence.project(base)['scans'], base['scans'])

    def test_created_output_replacement_does_not_mutate_input(self):
        for temporary, stage, empty in itertools.product((False, True), ('created', 'directory_open'), (False, True)):
            with self.subTest(temporary=temporary, stage=stage, empty=empty), tempfile.TemporaryDirectory() as temp:
                base = Path(temp); parent = base / 'parent'; parent.mkdir()
                bundle = base / 'input'; bundle.mkdir(mode=0o700)
                if not empty: write(bundle / 'member.json', {'fixture': 'original'})
                before = self.snapshot(bundle); created = None; replaced = False
                mkdir = os.mkdir; opened = os.open
                def replace(name):
                    nonlocal replaced
                    (parent / name).rename(base / 'retained-output'); bundle.rename(parent / name); replaced = True
                def create(name, *args, **kwargs):
                    nonlocal created
                    result = mkdir(name, *args, **kwargs)
                    if kwargs.get('dir_fd') is not None:
                        created = str(name)
                        if stage == 'created': replace(created)
                    return result
                def directory_open(name, flags, *args, **kwargs):
                    if stage == 'directory_open' and str(name) == created and flags & os.O_DIRECTORY: replace(created)
                    return opened(name, flags, *args, **kwargs)
                with patch.object(os, 'mkdir', side_effect=create), patch.object(os, 'open', side_effect=directory_open), \
                        patch.dict(os.environ, {'TMPDIR': str(parent)}):
                    with self.assertRaisesRegex(ValueError, 'Output directory changed'):
                        evidence.write_outputs({'evidence.json': {}}, None if temporary else parent / 'output',
                                               workspace=base / 'checkout', input_path=bundle)
                self.assertTrue(replaced); self.assertEqual(self.snapshot(parent / created), before)
                self.assertEqual(list((base / 'retained-output').iterdir()), [])

    def test_static_projection_reconciles_aggregate_required_gates(self):
        base = evidence.normalize_static(FIXTURES / 'static-synthetic', 'podman')
        for complete in (False, True):
            with self.subTest(complete=complete):
                data = copy.deepcopy(base)
                if complete:
                    data['source']['content'] = evidence.content([
                        {'member': 'SKILL.md', 'digest': evidence.digest_bytes(b'Synthetic')}], 'configured')
                    data['availability'].update(status='complete', reasons=[])
                    data['scans'] = data['scans'][:2]
                    for scan in data['scans']: scan.update(status='failed', passed=False)
                aggregate = data['scans'][0]; aggregate.update(status='passed', passed=True)
                self.assert_project_rejects(data, 'Static aggregate gate contradiction')
        status = copy.deepcopy(base); status['scans'][0]['status'] = 'failed'
        self.assert_project_rejects(status, 'Static aggregate status contradiction')
        legacy = copy.deepcopy(base)
        for scan in legacy['scans']: scan.pop('blocking')
        self.assertEqual(evidence.project(legacy)['scans'], legacy['scans'])
        for invalid in (None, 1, 'false'):
            data = copy.deepcopy(base); data['scans'][1]['blocking'] = invalid
            self.assert_project_rejects(data, 'Invalid boolean')

    def test_ordinary_input_directory_replacement_rejects_validated_identity(self):
        root = self.root / 'ordinary-input'; shutil.copytree(FIXTURES / 'static-synthetic', root)
        before = self.snapshot(root); outside = self.root / 'ordinary-outside'; shutil.copytree(root, outside)
        versions = evidence.read_json(outside / 'versions.json'); versions.pop('fixture'); write(outside / 'versions.json', versions)
        target = root / 'versions.json'; retained = self.root / 'ordinary-retained'; safe = evidence.safe_path; replaced = False
        validations = 0
        def validated(path, **kwargs):
            nonlocal replaced, validations
            result = safe(path, **kwargs)
            if result == target: validations += 1
            if result == target and not replaced and validations == 2:
                root.rename(retained); outside.rename(root); replaced = True
            return result
        with patch.object(evidence, 'safe_path', side_effect=validated):
            with self.assertRaisesRegex(ValueError, 'Input directory changed'):
                evidence.normalize_static(root, 'podman')
        self.assertTrue(replaced); self.assertEqual(self.snapshot(retained), before)

    def test_ordinary_output_parent_replacement_does_not_mutate_input(self):
        for temporary in (False, True):
            with self.subTest(temporary=temporary), tempfile.TemporaryDirectory() as temp:
                base = Path(temp); parent = base / 'parent'; parent.mkdir()
                bundle = base / 'input'; bundle.mkdir(); write(bundle / 'member.json', {'fixture': 'original'})
                before = self.snapshot(bundle); retained = base / 'retained'; opened = evidence.open_directory
                replaced = False
                def replaced_parent(path, *args):
                    nonlocal replaced
                    if path == parent and not replaced:
                        parent.rename(retained); bundle.rename(parent); replaced = True
                    return opened(path, *args)
                with patch.object(evidence, 'open_directory', side_effect=replaced_parent), \
                        patch.dict(os.environ, {'TMPDIR': str(parent)}):
                    with self.assertRaisesRegex(ValueError, 'Output parent directory changed'):
                        evidence.write_outputs({'evidence.json': {}}, None if temporary else parent / 'output',
                                               workspace=base / 'checkout', input_path=bundle)
                self.assertTrue(replaced)
                self.assertEqual(self.snapshot(parent), before)
                self.assertEqual(list(retained.iterdir()), [])

    def test_historical_listing_applies_remaining_budget_during_capture(self):
        repo = self.repo(); authored = repo / '.apm/skills/alpha'
        for index in range(10): (authored / f'member-{index}.md').write_text('Synthetic')
        def git(*args):
            return subprocess.run(['git', '-C', str(repo), *args], check=True,
                                  capture_output=True, text=True).stdout.strip()
        git('init', '-q')
        git('config', 'remote.origin.url', 'https://github.com/thetechgy/agent-engineering-baseline.git')
        git('add', '.apm')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
            'commit', '-qm', 'Listing budget fixture')
        rev = git('rev-parse', 'HEAD')
        listing = evidence.offline_git(repo, 'ls-tree', '-rz', rev, '--', '.apm/skills/alpha', max_entries=1000)
        total = len(listing.stdout) + sum(path.stat().st_size for path in authored.iterdir())
        baseline = evidence.historical_content(repo, rev, '.apm/skills/alpha')
        for remaining in (37, total):
            with self.subTest(remaining=remaining):
                budget = evidence.ReadBudget(); evidence.workspace_repository(repo, budget=budget)
                budget.remaining = remaining
                captured = []; processes = []; trace = self.root / f'listing-budget-{remaining}.jsonl'
                with git_trace(trace):
                    popen = subprocess.Popen
                    def tracked(*args, **kwargs):
                        process = popen(*args, **kwargs)
                        if 'ls-tree' in args[0]:
                            processes.append(process); stream = process.stdout
                            class CountingPipe:
                                def read(self, size):
                                    raw = stream.read(size); captured.append(len(raw)); return raw
                                def __getattr__(self, name): return getattr(stream, name)
                            process.stdout = CountingPipe()
                        return process
                    with patch.object(subprocess, 'Popen', side_effect=tracked):
                        if remaining == total:
                            self.assertEqual(evidence.historical_content(repo, rev, '.apm/skills/alpha', budget=budget), baseline)
                            self.assertEqual(budget.remaining, 0)
                        else:
                            with self.assertRaisesRegex(ValueError, 'Normalization byte limit'):
                                evidence.historical_content(repo, rev, '.apm/skills/alpha', budget=budget)
                self.assertTrue(processes); self.assertTrue(all(p.poll() is not None for p in processes))
                self.assertLessEqual(sum(captured), remaining + 1)  # One byte distinguishes EOF from excess.
                if remaining != total:
                    commands = [e['argv'] for e in map(json.loads, trace.read_text().splitlines()) if e.get('event') == 'start']
                    self.assertFalse(any('cat-file' in argv and 'blob' in argv for argv in commands))

    def test_static_projection_retains_known_scan_limitations(self):
        for status in ('incomplete', 'skipped'):
            with self.subTest(status=status):
                data = evidence.normalize_static(FIXTURES / 'static-synthetic', 'podman')
                data['scans'] = data['scans'][:2]
                for scan in data['scans']: scan.update(status='passed', passed=True)
                data['scans'][1].update(status=status, passed=None)
                data['scans'][0].update(status='incomplete' if status == 'incomplete' else 'failed', passed=False)
                data['availability']['reasons'].remove('scan_incomplete')
                self.assert_project_rejects(data, 'Missing scan limitation')
                data['availability']['reasons'].append('scan_incomplete')
                self.assertIn('scan_incomplete', evidence.validate_evidence(data)['availability']['reasons'])

    def test_projection_reconciles_known_severity_counts(self):
        base = evidence.normalize_static(FIXTURES / 'static-synthetic', 'podman')
        for level, scanner_count, aggregate_count in itertools.product(
                ('critical', 'high', 'medium', 'low'), (None, 0, 1), (None, 0, 1)):
            with self.subTest(level=level, scanner=scanner_count, aggregate=aggregate_count):
                data = copy.deepcopy(base)
                data['findings'][0]['severity'] = level
                for scan, total in zip(data['scans'][:2], (aggregate_count, scanner_count)):
                    scan['severity_counts'] = dict.fromkeys(scan['severity_counts'], 0)
                    scan['severity_counts'][level] = total
                # Native aggregate totals are always known; per-scanner totals may be unknown.
                if scanner_count != 0 and aggregate_count == 1:
                    evidence.validate_evidence(data); evidence.validate_public(data)
                else:
                    with self.assertRaises(ValueError): evidence.project(data)
                    with self.assertRaises(ValueError): evidence.validate_public(data)
        invalid = copy.deepcopy(base)
        for scan in invalid['scans'][:2]: scan['severity_counts']['high'] = 0
        path = self.root / 'normalized.json'; write(path, invalid)
        output = self.root / 'rejected-projection'
        result = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
                                 'project', '--input', str(path), '--output', str(output)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stderr, 'Evidence contract rejected (ValueError)\n')
        self.assertFalse(output.exists())
        # Reported scanner totals must also fit the aggregate, even with partial details.
        totals = copy.deepcopy(base); totals['findings'] = []
        totals['scans'][1]['severity_counts']['high'] = 2
        with self.assertRaises(ValueError): evidence.project(totals)
        totals['scans'] = totals['scans'][:2]
        totals['scans'][1]['severity_counts']['high'] = 0
        with self.assertRaises(ValueError): evidence.project(totals)
        totals['scans'][1]['severity_counts']['high'] = None
        evidence.validate_evidence(totals)  # Unknown counts do not invent a sum equality.

    def test_cli_rejects_nonobject_codex_agent_without_traceback(self):
        root = self.native(); path = next(root.glob('results/podman/*/result.json'))
        original = evidence.read_json(path)
        for malformed in (None, True, 42, 3.5, 'malformed', [], ['malformed']):
            with self.subTest(malformed=malformed):
                native = copy.deepcopy(original); native['agents']['codex'] = malformed; write(path, native)
                before = self.snapshot(root); output = self.root / 'rejected-agent'
                result = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
                                         'normalize', '--kind', 'behavioral', '--skill', 'podman',
                                         '--input', str(root), '--output', str(output)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stderr, 'Evidence contract rejected (ValueError)\n')
                self.assertFalse(output.exists()); self.assertEqual(self.snapshot(root), before)
                with self.assertRaisesRegex(ValueError, 'Native identity/agent mismatch'):
                    evidence.normalize_behavioral(root, 'podman')
        # Other malformed nested native objects must also keep CLI diagnostics bounded.
        native = copy.deepcopy(original)
        config_path = path.parent / 'run_config.json'; config = evidence.read_json(config_path)
        config['harbor'] = 'malformed'; native['run_config'] = config
        write(path, native); write(config_path, config)
        result = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
                                 'normalize', '--kind', 'behavioral', '--skill', 'podman', '--input', str(root)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('Evidence contract rejected', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertNotIn(str(REPO), result.stderr); self.assertNotIn(str(root), result.stderr)

    def test_static_completeness_requires_exact_source(self):
        root = self.root / 'static-source'; shutil.copytree(FIXTURES / 'static-synthetic', root)
        path = next((root / 'reports/podman').glob('*.json')); native = evidence.read_json(path)
        native.update(overall_passed=True, overall_status='passed', incomplete_scans=[],
                      severity_counts=dict.fromkeys(native['severity_counts'], 0))
        scan = native['results'][0]
        scan.update(passed=True, status='passed', incomplete_scans=[], findings=[])
        for level in native['severity_counts']: scan['summary'][level + '_count'] = 0
        self.mutate(root, '/catalog-summary.json', lambda d: (
            d.update(failed=0), d['skills'][0].update(passed=True, reason='')))
        repo = self.root / 'source-repo'; repo.mkdir(); self.local(repo, 'podman')
        def git(*args):
            return subprocess.run(['git', '-C', str(repo), *args], check=True,
                                  capture_output=True, text=True).stdout.strip()
        git('init', '-q')
        git('config', 'remote.origin.url', 'https://github.com/thetechgy/agent-engineering-baseline.git')
        git('add', '.apm')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Static source fixture')
        rev = git('rev-parse', 'HEAD')
        for declared, complete in ((None, False), ({'repository': 'thetechgy/agent-engineering-baseline', 'commit': 'f'*40}, False),
                                   ({'repository': 'thetechgy/agent-engineering-baseline', 'commit': rev}, True)):
            with self.subTest(declared=declared):
                native['evaluated_source'] = declared; write(path, native)
                data = evidence.normalize_static(root, 'podman', workspace=repo)
                self.assertEqual(data['availability']['status'], 'complete' if complete else 'incomplete')
                self.assertEqual('source_unavailable' in data['availability']['reasons'], not complete)
                evidence.project(data)
                if not complete:
                    data['availability'].update(status='complete', reasons=[])
                    with self.assertRaises(ValueError): evidence.project(data)
                    with self.assertRaises(ValueError): evidence.validate_public(data)

    def test_behavioral_references_hash_each_parsed_buffer_once(self):
        root = self.native(); run = next((root / 'results/podman').iterdir())
        members = [run / 'result.json', run / 'run_config.json', root / 'provenance.json', root / 'versions.json',
                   run / 'dataset_snapshot.json', run / 'attempt_policy.json',
                   next(run.glob('codex/*/summary.json')), next(run.glob('codex/*/trials/*/result.json')),
                   next(run.glob('codex/*/trials/*/reward.json'))]
        with patch.object(evidence, 'read_bytes', wraps=evidence.read_bytes) as read, \
                patch.object(evidence, 'digest_bytes', wraps=evidence.digest_bytes) as digest:
            data = evidence.normalize_behavioral(root, 'podman')
        for target in members:
            with self.subTest(member=target.relative_to(root)):
                original = target.read_bytes()
                self.assertEqual(sum(call.args[0] == target for call in read.call_args_list), 1)
                self.assertEqual(sum(call.args[0] == original for call in digest.call_args_list), 1)
                refs = [r for r in data['references'] if r['member'] == target.relative_to(root).as_posix()]
                self.assertTrue(refs)
                self.assertTrue(all(r['digest'] == evidence.digest_bytes(original) for r in refs))
        evidence.project(data)

    def test_snapshot_buffer_preserves_pinned_validation(self):
        from skillevaluator.tier3.harbor import report_data as native
        root = self.native(); run = next((root / 'results/podman').iterdir()); path = run / 'dataset_snapshot.json'
        raw = path.read_bytes()
        for size in (native._MAX_JSON_BYTES, native._MAX_JSON_BYTES + 1):
            with self.subTest(size=size):
                path.write_bytes(raw + b' ' * (size - len(raw)))
                accepted = native.load_dataset_snapshot(run) is not None
                self.assertEqual(accepted, size == native._MAX_JSON_BYTES)
                if accepted:
                    data = evidence.normalize_behavioral(root, 'podman')
                    ref = next(r for r in data['references'] if r['member'].endswith('/dataset_snapshot.json'))
                    self.assertEqual(ref['digest'], evidence.digest_bytes(path.read_bytes()))
                else:
                    with self.assertRaises(ValueError): evidence.normalize_behavioral(root, 'podman')
        snapshot = json.loads(raw); snapshot['extra_nodes'] = [0] * native._MAX_JSON_NODES
        write(path, snapshot)
        self.assertIsNone(native.load_dataset_snapshot(run))
        with patch.object(native, 'build_dataset_snapshot', side_effect=AssertionError('Node bound must precede snapshot building')):
            with self.assertRaises(ValueError): evidence.normalize_behavioral(root, 'podman')

    def test_static_preserves_known_per_scanner_counts(self):
        root = self.root / 'static-counts'; shutil.copytree(FIXTURES / 'static-synthetic', root)
        path = next((root / 'reports/podman').glob('*.json')); native = evidence.read_json(path)
        levels = tuple(native['severity_counts'])
        for missing in (None, *levels):
            with self.subTest(missing=missing):
                report = copy.deepcopy(native)
                if missing: report['results'][0]['summary'].pop(missing + '_count')
                write(path, report)
                data = evidence.normalize_static(root, 'podman')
                known = {k: report['results'][0]['summary'].get(k + '_count') for k in levels}
                self.assertEqual(data['scans'][1]['severity_counts'], known)
                self.assertEqual(evidence.project(data)['scans'][1]['severity_counts'], known)
                self.assertEqual(data['scans'][0]['severity_counts'], native['severity_counts'])
                self.assertTrue(all(v is None for v in data['scans'][2]['severity_counts'].values()))

    def test_static_aggregate_matches_pinned_required_gate_outcomes(self):
        # JSONReporter.render_all / reporting.base at the supported evaluator pin:
        # explicit nonblocking results and advisory AGENT_EVAL skips permit a pass.
        cases = [
            ('SECRETS', True, 'passed', {}, True),
            ('SECRETS', False, 'failed', {}, False),
            ('SECRETS', False, 'failed', {'gating': {'blocking': True}}, False),
            ('SECRETS', False, 'failed', {'gating': {'blocking': False}}, True),
            ('AGENT_EVAL', False, 'skipped', {'tier3': {'provenance': {'advisory': True, 'reason': 'skipped'}}}, True),
            ('AGENT_EVAL', False, 'failed', {'gating': {'blocking': True},
                'tier3': {'provenance': {'advisory': True, 'reason': 'skipped'}}}, False),
            ('SECRETS', False, 'incomplete', {}, False),
        ]
        for validator, passed, status, extra, gate in cases:
            for overall in (False, True):
                with self.subTest(validator=validator, status=status, extra=extra, overall=overall), \
                        tempfile.TemporaryDirectory() as temp:
                    root = Path(temp) / 'static'; shutil.copytree(FIXTURES / 'static-synthetic', root)
                    path = next((root / 'reports/podman').glob('*.json')); native = evidence.read_json(path)
                    scan = native['results'][0]
                    scan.update(validator=validator, passed=passed, status=status, **extra)
                    scan['incomplete_scans'] = ['gitleaks'] if status == 'incomplete' else []
                    native.update(overall_passed=overall, incomplete_scans=scan['incomplete_scans'],
                                  overall_status='incomplete' if status == 'incomplete' else 'passed' if overall else 'failed')
                    write(path, native)
                    self.mutate(root, '/catalog-summary.json', lambda d: (
                        d.update(failed=0 if overall else 1), d['skills'][0].update(
                            passed=overall, reason='' if overall else 'validation failed')))
                    if overall == gate:
                        data = evidence.normalize_static(root, 'podman'); evidence.project(data)
                        self.assertEqual(data['scans'][1]['status'], status)
                    else:
                        with self.assertRaisesRegex(ValueError, 'Static required gate contradiction'):
                            evidence.normalize_static(root, 'podman')
        root = self.root / 'contradictory-status'; shutil.copytree(FIXTURES / 'static-synthetic', root)
        path = next((root / 'reports/podman').glob('*.json')); native = evidence.read_json(path)
        second = copy.deepcopy(native['results'][0])
        second.update(validator='SECOND', passed=True, status='failed', incomplete_scans=[], findings=[])
        second['summary']['high_count'] = 0
        native['results'].append(second); native['total_validators'] = 2
        write(path, native)
        # A first failing gate must not skip consistency checks on later results.
        with self.assertRaisesRegex(ValueError, 'Static validator status contradiction'):
            evidence.normalize_static(root, 'podman')

    def test_static_detailed_severity_counts_do_not_exceed_totals(self):
        for level, total, reported in itertools.product(('critical', 'high', 'medium', 'low'),
                                                        (0, 1, 2), (None, 0, 1, 2)):
            with self.subTest(level=level, total=total, reported=reported), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / 'static'; shutil.copytree(FIXTURES / 'static-synthetic', root)
                path = next((root / 'reports/podman').glob('*.json'))
                native = evidence.read_json(path)
                native['severity_counts'] = dict.fromkeys(native['severity_counts'], 0)
                native['severity_counts'][level] = total
                scan = native['results'][0]
                scan['findings'][0]['severity'] = level
                for key in native['severity_counts']:
                    scan['summary'][key + '_count'] = 0
                if reported is None:
                    scan['summary'].pop(level + '_count')
                else:
                    scan['summary'][level + '_count'] = reported
                write(path, native)
                valid = total >= 1 and (reported is None or reported == total and reported >= 1)
                if valid:
                    evidence.project(evidence.normalize_static(root, 'podman'))
                else:
                    with self.assertRaises(ValueError): evidence.normalize_static(root, 'podman')
        # Balanced aggregate totals must still reject a deficient individual scanner.
        root = self.root / 'balanced'; shutil.copytree(FIXTURES / 'static-synthetic', root)
        path = next((root / 'reports/podman').glob('*.json')); native = evidence.read_json(path)
        scan = native['results'][0]; scan['summary']['high_count'] = 0
        second = copy.deepcopy(scan); second.update(validator='SECOND', status='failed', findings=[], incomplete_scans=[])
        second['summary']['high_count'] = 1
        native['results'] = [scan, second]; native['total_validators'] = 2
        write(path, native)
        with self.assertRaisesRegex(ValueError, 'Detailed findings exceed scanner total'):
            evidence.normalize_static(root, 'podman')

    def test_static_finding_limit_precedes_reference_creation(self):
        root = self.root / 'static'; shutil.copytree(FIXTURES / 'static-synthetic', root)
        path = next((root / 'reports/podman').glob('*.json'))
        native = evidence.read_json(path)
        finding = {**native['results'][0]['findings'][0], 'severity': 'info'}
        native['results'][0]['findings'] = [finding] * (evidence.MAX_TRIALS + 1)
        write(path, native)
        def unexpected(*args, **kwargs):
            raise AssertionError('Reference construction preceded finding limit')
        with patch.object(evidence, 'reference', side_effect=unexpected), \
                patch.object(evidence, 'reference_from_digest', side_effect=unexpected, create=True):
            with self.assertRaisesRegex(ValueError, 'Finding limit'):
                evidence.normalize_static(root, 'podman')

    def test_static_report_is_read_and_hashed_once(self):
        root = self.root / 'static'; shutil.copytree(FIXTURES / 'static-synthetic', root)
        path = next((root / 'reports/podman').glob('*.json'))
        native = evidence.read_json(path)
        native['results'][0]['findings'] *= 100
        native['results'][0]['summary']['high_count'] = native['severity_counts']['high'] = 100
        write(path, native); raw = path.read_bytes()
        with patch.object(evidence, 'read_bytes', wraps=evidence.read_bytes) as read, \
                patch.object(evidence, 'digest_bytes', wraps=evidence.digest_bytes) as digest:
            data = evidence.normalize_static(root, 'podman')
        self.assertEqual(sum(call.args[0] == path for call in read.call_args_list), 1)
        self.assertEqual(sum(call.args[0] == raw for call in digest.call_args_list), 1)
        self.assertEqual(len(data['findings']), 100)
        evidence.project(data)
        for ref in data['references']:
            evidence.verify_reference(root, ref)
        native['results'][0]['findings'] = [{**f, 'severity': 'info'} for f in native['results'][0]['findings']]
        write(path, native)
        informational = evidence.normalize_static(root, 'podman')
        self.assertTrue(all(f['severity'] == 'info' for f in informational['findings']))
        evidence.project(informational)

    def test_unknown_keys_rejected_at_every_object(self):
        # Mutate every nested object, including records within arrays.
        base = self.data()
        def paths(value, prefix=()):
            if type(value) is dict:
                yield prefix
                for key, child in value.items(): yield from paths(child, prefix+(key,))
            elif type(value) is list:
                for index, child in enumerate(value): yield from paths(child, prefix+(index,))
        for path in list(paths(base)):
            with self.subTest(path=path):
                data = copy.deepcopy(base); value = data
                for key in path: value = value[key]
                value['injected_prompt'] = 'private content'
                with self.assertRaises(ValueError): evidence.project(data)
        public = evidence.project(base)
        for path in list(paths(public)):
            data = copy.deepcopy(public); value = data
            for key in path: value = value[key]
            value['html'] = '<script>'
            with self.assertRaises(ValueError): evidence.validate_public(data)
        for base in (evidence.normalize_static(FIXTURES/'static-synthetic', 'podman'),
                     evidence.read_json(FIXTURES/'gh-no-model.json')):
            for path in list(paths(base)):
                data = copy.deepcopy(base); value = data
                for key in path: value = value[key]
                value['commentary'] = 'not public'
                with self.assertRaises(ValueError): evidence.project(data)

    def test_actual_public_serialized_limit(self):
        data = evidence.read_json(FIXTURES/'gh-no-model.json')
        prototype = self.data()['references'][0]
        prototype.update(provenance='synthetic', artifact_id='synthetic-public-limit', artifact_digest=None)
        for index in range(3500):
            ref = copy.deepcopy(prototype); ref['member'] = 'members/' + str(index) + '.json'
            ref['id'] = evidence.identity({k:ref[k] for k in ('artifact_id','member','locator','digest')})
            data['references'].append(ref)
        evidence.validate_evidence(data)
        self.assertGreater(len(evidence.encoded(data)), evidence.PUBLIC_LIMIT)
        with self.assertRaises(ValueError): evidence.project(data)

    def test_ambiguous_yaml_metadata(self):
        root = self.repo()
        (root/'apm.lock.yaml').write_text('dependencies: []\ndependencies: []\ndeployments: []\n')
        with self.assertRaises(ValueError): evidence.inventory(root)
        (root/'apm.lock.yaml').unlink()
        (root/'.apm/skills/alpha/SKILL.md').write_text('---\nname: alpha\nname: beta\ndescription: Fixture\n---\n')
        with self.assertRaises(ValueError): evidence.inventory(root)

    def test_extract_manifest_tamper_and_missing_git_objects(self):
        root = self.root/'extract'; shutil.copytree(FIXTURES/'podman-native', root)
        self.mutate(root, '/versions.json', lambda d:d.update(python='3.13.99'))
        with self.assertRaises(ValueError): evidence.normalize_behavioral(root, 'podman')
        root = self.native()
        data = evidence.normalize_behavioral(root, 'podman', workspace=self.root)
        self.assertIsNone(data['source']['content']['digest'])
        self.assertIn('source_unavailable', data['availability']['reasons'])
        self.assertEqual(len(data['observations']), 20)
        data['availability'].update(status='complete', reasons=[])
        with self.assertRaises(ValueError): evidence.project(data)

    def test_native_prose_cannot_enter_projection(self):
        root = self.native()
        self.mutate(root, '/result.json', lambda d:d.update(transcript='DO-NOT-PUBLISH', metadata={'prompt':'DO-NOT-PUBLISH'}))
        report = evidence.encoded(evidence.project(evidence.normalize_behavioral(root, 'podman')))
        self.assertNotIn(b'DO-NOT-PUBLISH', report)
        with self.assertRaises(ValueError): evidence.project(evidence.read_json(next(root.rglob('result.json'))))

    def test_numeric_and_denominator_failures(self):
        for invalid in (True, float('nan'), float('inf'), 1.1):
            data = self.data(); data['metrics'][1]['value'] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError): evidence.project(data)
        data = self.data(); data['arms'][0]['coverage']['expected_attempts'] = 9
        with self.assertRaises(ValueError): evidence.project(data)
        data = self.data(); data['arms'][0]['rubric']['passed_cases'] = 11
        with self.assertRaises(ValueError): evidence.project(data)

    def test_json_limits_duplicate_keys_and_depth(self):
        path = self.root/'input.json'
        for value in ('{"a":1,"a":2}', '{"x":NaN}', '['*34+'0'+']'*34, '['*2000+'0'+']'*2000):
            path.write_text(value)
            with self.assertRaises(ValueError): evidence.read_json(path)
        result = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
                                 'project', '--input', str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, 'Evidence contract rejected (ValueError)\n')
        path.write_bytes(b' '* (evidence.JSON_LIMIT+1))
        with self.assertRaises(ValueError): evidence.read_json(path)
        data = self.data(); data['observations'] *= 501
        with self.assertRaises(ValueError): evidence.project(data)
        data = self.data(); data['dataset']['case_ids'] = [str(i) for i in range(1001)]
        with self.assertRaises(ValueError): evidence.project(data)

    def test_explicit_json_limit_retains_strict_parsing(self):
        raw = b'{"value": 1}'
        self.assertEqual(evidence.parse_json(raw, limit=len(raw)), {'value': 1})
        with self.assertRaisesRegex(ValueError, 'Invalid bounded JSON'):
            evidence.parse_json(raw, limit=len(raw) - 1)
        with patch.object(evidence, 'JSON_LIMIT', len(raw) - 1):
            with self.assertRaisesRegex(ValueError, 'Invalid bounded JSON'):
                evidence.parse_json(raw)
            self.assertEqual(evidence.parse_json(raw, limit=len(raw)), {'value': 1})
        for invalid in (b'{"a":1,"a":2}', b'{"x":NaN}', b'{"x":Infinity}',
                        b'[' * 34 + b'0' + b']' * 34, b'{', b'"\xff"'):
            with self.subTest(invalid=invalid[:40]), self.assertRaises(ValueError):
                evidence.parse_json(invalid, limit=1024)
        for limit in (True, -1, 0, 1.5, '1024'):
            with self.subTest(limit=limit), self.assertRaisesRegex(ValueError, 'Invalid JSON limit'):
                evidence.parse_json(raw, limit=limit)

    def test_reference_escape_and_public_size(self):
        for member in ('../escape','/absolute','C:\\private','safe/../escape','a//b'):
            data = self.data(); data['references'][0]['member'] = member
            with self.subTest(member=member), self.assertRaises(ValueError): evidence.project(data)
        data = self.data(); data['observations'][0]['references'] = ['sha256:'+'f'*64]
        with self.assertRaises(ValueError): evidence.project(data)
        # Enforce the serialized boundary independently of row-count limits.
        import unittest.mock
        with unittest.mock.patch.object(evidence, 'PUBLIC_LIMIT', 100):
            with self.assertRaises(ValueError): evidence.project(self.data())

    def test_linked_input_components(self):
        root = self.native(); alias = self.root/'alias'; alias.symlink_to(root, target_is_directory=True)
        with self.assertRaises(ValueError): evidence.normalize_behavioral(alias, 'podman')
        p = root/'versions.json'; os.link(p, self.root/'hardlinked')
        with self.assertRaises(ValueError): evidence.normalize_behavioral(root, 'podman')

    def test_authored_tree_entry_limit_includes_empty_directories(self):
        root = self.repo(); authored = root / '.apm/skills/alpha'
        for index in range(1999):
            (authored / str(index)).mkdir()
        self.assertIsNotNone(evidence.skill_content(authored)['digest'])
        (authored / 'excess').mkdir()
        with self.assertRaisesRegex(ValueError, 'Input tree entry limit'):
            evidence.skill_content(authored)
        authored = self.local(self.root / 'file-repo', 'beta')
        for index in range(999):
            (authored / (str(index) + '.txt')).touch()
        self.assertEqual(len(evidence.skill_content(authored)['manifest']), 1000)
        (authored / 'excess.txt').touch()
        with patch.object(evidence, 'read_bytes') as read:
            with self.assertRaisesRegex(ValueError, 'Input tree entry limit'):
                evidence.skill_content(authored)
            read.assert_not_called()

    def test_normalize_cli_rejects_excessive_unused_input_entries(self):
        root = self.root / 'static'
        shutil.copytree(FIXTURES / 'static-synthetic', root)
        unused = root / 'unused'; unused.mkdir()
        for index in range(100000):
            (unused / str(index)).touch()
        result = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
                                 'normalize', '--kind', 'static', '--skill', 'podman', '--input', str(root)],
                                capture_output=True, text=True)
        if result.returncode == 0:
            self.addCleanup(shutil.rmtree, Path(result.stdout.strip()))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('Evidence contract rejected', result.stderr)
        self.assertEqual(result.stdout, '')

    def test_ambiguous_run_requires_selection(self):
        root = self.native(); base = root/'results/podman'; run = next(base.iterdir())
        shutil.copytree(run, base/'second-run')
        with self.assertRaises(ValueError): evidence.normalize_behavioral(root, 'podman')
        data = evidence.normalize_behavioral(root, 'podman', run.name)
        self.assertEqual(data['run_id'], run.name)
        (base/'latest').symlink_to(run, target_is_directory=True)
        with self.assertRaises(ValueError): evidence.normalize_behavioral(root, 'podman', run.name)

    def test_cli_and_unchanged_inputs(self):
        root = self.native()
        before = {p.relative_to(root):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
        commands = [['inventory'], ['normalize','--kind','behavioral','--skill','podman','--input',str(root)],
                    ['normalize','--kind','static','--skill','podman','--input',str(FIXTURES/'static-synthetic')],
                    ['project','--input',str(FIXTURES/'gh-no-model.json')]]
        for command in commands:
            result = subprocess.run([sys.executable,str(REPO/'.github/scripts/skill_evidence.py'),*command], capture_output=True,text=True)
            label = command[0] + (' ' + command[2] if command[0] == 'normalize' else '')
            self.assertEqual(result.returncode, 0, label + ': ' + result.stderr)
            output = Path(result.stdout.strip()); self.addCleanup(shutil.rmtree, output)
            self.assertFalse(output.is_relative_to(REPO)); self.assertTrue(output.is_dir())
            for p in output.glob('*.json'):
                self.assertEqual(p.read_bytes(), evidence.encoded(evidence.read_json(p)))
        after = {p.relative_to(root):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_rejected_destinations(self):
        values = {'public-report.json': evidence.project(self.data())}
        for path in (REPO/'new-output', self.root, self.root/'missing/child', self.root/'../escape'):
            with self.subTest(path=path), self.assertRaises(ValueError): evidence.write_outputs(values, path)
        alias = self.root/'alias'; alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError): evidence.write_outputs(values, alias/'new')
        destination = self.root/'new'; evidence.write_outputs(values, destination)
        with self.assertRaises(ValueError): evidence.write_outputs(values, destination)

    def test_output_directory_replacement_cannot_redirect_writes(self):
        for stage in ('created', 'file_open'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as temp:
                parent = Path(temp); workspace = parent / 'checkout'; workspace.mkdir()
                bundle = parent / 'input'; bundle.mkdir(); (bundle / 'marker').write_text('Retained')
                destination = parent / 'output'; retained = parent / 'renamed-output'
                before_input = self.snapshot(bundle); before_workspace = self.snapshot(workspace)
                replaced = False
                def replace():
                    nonlocal replaced
                    if not replaced:
                        destination.rename(retained); destination.symlink_to(bundle, target_is_directory=True)
                        replaced = True
                mkdir = os.mkdir; open_file = Path.open; open_fd = os.open
                def created(path, *args, **kwargs):
                    result = mkdir(path, *args, **kwargs)
                    if stage == 'created' and (Path(path) == destination or str(path) == destination.name): replace()
                    return result
                def opened_path(path, *args, **kwargs):
                    if stage == 'file_open' and path.parent == destination: replace()
                    return open_file(path, *args, **kwargs)
                def opened_fd(path, flags, *args, **kwargs):
                    if stage == 'file_open' and flags & os.O_CREAT: replace()
                    return open_fd(path, flags, *args, **kwargs)
                with patch.object(os, 'mkdir', side_effect=created), patch.object(Path, 'open', opened_path), \
                        patch.object(os, 'open', side_effect=opened_fd):
                    with self.assertRaises((ValueError, OSError)):
                        evidence.write_outputs({'evidence.json': {'synthetic': True}}, destination,
                                               workspace=workspace, input_path=bundle)
                self.assertTrue(replaced)
                self.assertEqual(self.snapshot(bundle), before_input)
                self.assertEqual(self.snapshot(workspace), before_workspace)

    def test_failed_normalization_publication_cleans_outputs_and_allows_retry(self):
        for temporary, failure in itertools.product((False, True), ('parent_stat', 'initial_stat', 'directory_open', 'directory_stat', 'directory_list', 'open', 'write', 'flush')):
            with self.subTest(temporary=temporary, failure=failure), tempfile.TemporaryDirectory() as temp:
                parent = Path(temp); root = parent / 'native'
                shutil.copytree(FIXTURES / 'static-synthetic', root)
                output_parent = parent / 'outputs'; output_parent.mkdir(mode=0o700)
                destination = output_parent / 'explicit'; before = self.snapshot(root)
                args = ['normalize', '--kind', 'static', '--skill', 'podman', '--input', str(root)]
                if not temporary: args += ['--output', str(destination)]
                opened = os.open; fdopen = os.fdopen; fstat = os.fstat; listdir = os.listdir
                output_fds = set(); directory_fds = set(); attempted = []; created_parent = None; parent_failed = False
                mkdir = os.mkdir
                def captured_mkdir(path, *args, **kwargs):
                    nonlocal created_parent
                    result = mkdir(path, *args, **kwargs)
                    if str(path) == 'explicit' or str(path).startswith('skill-evidence-'): created_parent = kwargs.get('dir_fd')
                    return result
                stat_path = os.stat; initial_stat_failed = False
                def failing_initial_stat(path, *args, **kwargs):
                    nonlocal initial_stat_failed
                    if failure == 'initial_stat' and not initial_stat_failed and kwargs.get('dir_fd') is not None \
                            and (str(path) == 'explicit' or str(path).startswith('skill-evidence-')):
                        initial_stat_failed = True
                        raise OSError(5, 'Synthetic output initial stat failure')
                    return stat_path(path, *args, **kwargs)
                def failing_open(path, flags, *args, **kwargs):
                    output_directory = flags & os.O_DIRECTORY and (str(path) == 'explicit' or str(path).startswith('skill-evidence-'))
                    if output_directory and failure == 'directory_open':
                        raise OSError(24, 'Synthetic output directory descriptor limit')
                    if flags & os.O_CREAT:
                        attempted.append(str(path))
                        if str(path) == 'public-report.json' and failure == 'open':
                            raise OSError('Synthetic output open failure')
                    fd = opened(path, flags, *args, **kwargs)
                    if output_directory: directory_fds.add(fd)
                    if flags & os.O_CREAT and str(path) == 'public-report.json': output_fds.add(fd)
                    return fd
                def failing_stat(fd):
                    nonlocal parent_failed
                    if failure == 'parent_stat' and fd == created_parent and not parent_failed:
                        parent_failed = True
                        raise OSError(5, 'Synthetic output parent stat failure')
                    if fd in directory_fds and failure == 'directory_stat':
                        raise OSError('Synthetic output directory stat failure')
                    return fstat(fd)
                def failing_list(path):
                    if isinstance(path, int) and path in directory_fds and failure == 'directory_list':
                        raise OSError(24, 'Synthetic output directory listing descriptor limit')
                    return listdir(path)
                class FailingStream:
                    def __init__(self, stream): self.stream = stream
                    def __enter__(self): return self
                    def write(self, payload):
                        if failure == 'write':
                            self.stream.write(payload[:8]); raise OSError('Synthetic output write failure')
                        return self.stream.write(payload)
                    def __exit__(self, *args):
                        try:
                            if failure == 'flush':
                                self.stream.flush(); raise OSError('Synthetic output flush failure')
                        finally: self.stream.close()
                        return False
                def failing_stream(fd, *args, **kwargs):
                    stream = fdopen(fd, *args, **kwargs)
                    return FailingStream(stream) if fd in output_fds else stream
                with patch.dict(os.environ, {'TMPDIR': str(output_parent)}), \
                        patch.object(os, 'mkdir', side_effect=captured_mkdir), \
                        patch.object(os, 'open', side_effect=failing_open), \
                        patch.object(os, 'fdopen', side_effect=failing_stream), \
                        patch.object(os, 'fstat', side_effect=failing_stat), \
                        patch.object(os, 'stat', side_effect=failing_initial_stat), \
                        patch.object(os, 'listdir', side_effect=failing_list), \
                        self.assertRaisesRegex(OSError, 'Synthetic output'), redirect_stdout(StringIO()):
                    evidence.main(args)
                self.assertEqual(attempted, [] if failure.startswith('directory_') or failure in ('initial_stat', 'parent_stat') else ['evidence.json', 'public-report.json'])
                self.assertEqual(list(output_parent.iterdir()), []); self.assertEqual(self.snapshot(root), before)
                stdout = StringIO()
                with patch.dict(os.environ, {'TMPDIR': str(output_parent)}), redirect_stdout(stdout): evidence.main(args)
                output = Path(stdout.getvalue().strip())
                self.assertEqual({p.name for p in output.iterdir()}, {'evidence.json', 'public-report.json'})
                for path in output.iterdir(): self.assertEqual(path.read_bytes(), evidence.encoded(evidence.read_json(path)))
                self.assertEqual(self.snapshot(root), before)

    def test_persistent_reservation_metadata_failure_is_bounded_and_fail_closed(self):
        parent = self.root / 'outputs'; parent.mkdir(); destination = parent / 'output'
        mkdir = os.mkdir; fstat = os.fstat; parent_fd = None; calls = 0
        def created(path, *args, **kwargs):
            nonlocal parent_fd
            result = mkdir(path, *args, **kwargs)
            if str(path) == destination.name: parent_fd = kwargs.get('dir_fd')
            return result
        def failed(fd):
            nonlocal calls
            if fd == parent_fd:
                calls += 1; raise OSError(5, 'Persistent metadata failure')
            return fstat(fd)
        with patch.object(os, 'mkdir', side_effect=created), patch.object(os, 'fstat', side_effect=failed):
            with self.assertRaisesRegex(OSError, 'Persistent metadata failure'):
                evidence.write_outputs({'evidence.json': {}}, destination)
        self.assertEqual(calls, 2)
        # Without a safe identity, leave the empty reservation rather than guessing.
        self.assertTrue(destination.is_dir()); self.assertEqual(list(destination.iterdir()), [])

    def test_output_descriptor_failure_preserves_replacement_directories(self):
        for temporary, replacement, stage in itertools.product((False, True), ('directory', 'symlink', 'removed'), ('open', 'initial_stat')):
            with self.subTest(temporary=temporary, replacement=replacement, stage=stage), tempfile.TemporaryDirectory() as temp:
                parent = Path(temp); retained = parent / 'retained'; target = parent / 'target'; target.mkdir(mode=0o700)
                destination = parent / 'explicit'; opened = os.open; stat_path = os.stat; replaced = False
                def replace(path):
                    nonlocal replaced, destination
                    destination = parent / str(path); destination.rename(retained); replaced = True
                    if replacement == 'directory': target.rename(destination)
                    elif replacement == 'symlink': destination.symlink_to(target, target_is_directory=True)
                    raise OSError(24 if stage == 'open' else 5, 'Synthetic reservation failure')
                def failing_open(path, flags, *args, **kwargs):
                    if stage == 'open' and flags & os.O_DIRECTORY and (str(path) == 'explicit' or str(path).startswith('skill-evidence-')):
                        replace(path)
                    return opened(path, flags, *args, **kwargs)
                def failing_stat(path, *args, **kwargs):
                    if stage == 'initial_stat' and not replaced and kwargs.get('dir_fd') is not None \
                            and (str(path) == 'explicit' or str(path).startswith('skill-evidence-')):
                        replace(path)
                    return stat_path(path, *args, **kwargs)
                with patch.object(os, 'open', side_effect=failing_open), patch.object(os, 'stat', side_effect=failing_stat), \
                        patch.dict(os.environ, {'TMPDIR': str(parent)}):
                    with self.assertRaisesRegex(OSError, 'Synthetic reservation failure'):
                        evidence.write_outputs({'evidence.json': {}}, None if temporary else destination)
                self.assertTrue(replaced); self.assertEqual(list(retained.iterdir()), [])
                if replacement == 'directory': self.assertTrue(destination.is_dir()); self.assertEqual(list(destination.iterdir()), [])
                elif replacement == 'symlink': self.assertTrue(destination.is_symlink()); self.assertEqual(list(target.iterdir()), [])
                else: self.assertFalse(destination.exists())

    def test_in_memory_capture_rejects_changed_inputs_before_output_allocation(self):
        root = self.root / 'native'; shutil.copytree(FIXTURES / 'static-synthetic', root)
        data = copy.deepcopy(evidence.normalize_static(root, 'podman'))
        public = evidence.project(data); target = root / 'versions.json'
        raw = target.read_bytes(); target.write_bytes(raw + b' ')
        output = self.root / 'rejected'
        with patch.object(os, 'mkdir') as mkdir:
            with self.assertRaisesRegex(ValueError, 'Input member changed'):
                evidence.write_outputs({'evidence.json': data, 'public-report.json': public}, output)
            mkdir.assert_not_called()
        self.assertFalse(output.exists()); self.assertNotIn(b'_input_guards', evidence.encoded(public))

    def test_projection_capture_keeps_strict_json_object_boundary(self):
        value = evidence.read_json(FIXTURES / 'gh-no-model.json')
        source = self.root / 'pairs.json'; write(source, list(value.items()))
        before = source.read_bytes(); output = self.root / 'rejected-pairs'
        result = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
                                 'project', '--input', str(source), '--output', str(output)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 1); self.assertNotIn('Traceback', result.stderr)
        self.assertLess(len(result.stderr), 200); self.assertFalse(output.exists())
        self.assertEqual(source.read_bytes(), before)

    def test_inputs_remain_anchored_through_publication(self):
        for mode, mutation, stage in itertools.product(('inventory', 'static', 'behavioral', 'project-static', 'project-behavioral', 'project-reviewed'), ('replace', 'edit'), ('allocation', 'last_member')):
            with self.subTest(mode=mode, mutation=mutation, stage=stage), tempfile.TemporaryDirectory() as temp, patch.object(self, 'root', Path(temp)):
                repo, git = self.repository_fixture(); root = self.root / 'native'
                kind = 'static' if 'static' in mode else 'behavioral'
                if mode == 'inventory': target = repo / '.apm/skills/alpha/SKILL.md'
                else:
                    shutil.copytree(FIXTURES / ('static-synthetic' if kind == 'static' else 'podman-native'), root)
                    if kind == 'behavioral' and mode != 'project-reviewed': (root / 'extract-manifest.json').unlink()
                    target = root / 'versions.json'
                inventory = evidence.inventory; normalizer = getattr(evidence, 'normalize_' + kind)
                with patch.object(evidence, 'inventory', side_effect=lambda: inventory(repo)), \
                        patch.object(evidence, 'normalize_' + kind, side_effect=lambda *a: normalizer(*a, workspace=repo)):
                    if mode.startswith('project-'):
                        value = getattr(evidence, 'normalize_' + kind)(root, 'podman')
                        input_file = root / 'evidence.json'; write(input_file, value)
                        if mode == 'project-reviewed': target = input_file
                        args = ['project', '--input', str(input_file)]
                    elif mode == 'inventory': args = ['inventory']
                    else: args = ['normalize', '--kind', kind, '--skill', 'podman', '--input', str(root)]
                    raw = target.read_bytes(); metadata = target.stat(); output = self.root / 'output'
                    opened = os.open; mkdir = os.mkdir; changed = False
                    def change():
                        nonlocal changed
                        changed = True
                        if mutation == 'replace':
                            replacement = target.with_name('replacement'); replacement.write_bytes(raw); replacement.replace(target)
                        else:
                            target.write_bytes(raw + b' '); target.write_bytes(raw)
                            os.utime(target, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
                    def changed_input(path, flags, *a, **kw):
                        if stage == 'last_member' and flags & os.O_CREAT and not changed \
                                and str(path) == ('inventory.json' if mode == 'inventory' else 'public-report.json'):
                            change()
                        return opened(path, flags, *a, **kw)
                    def changed_allocation(path, *a, **kw):
                        result = mkdir(path, *a, **kw)
                        if stage == 'allocation' and not changed and str(path) == output.name: change()
                        return result
                    with patch.object(os, 'open', side_effect=changed_input), patch.object(os, 'mkdir', side_effect=changed_allocation), redirect_stdout(StringIO()):
                        with self.assertRaisesRegex(ValueError, 'Input (member|directory)'):
                            evidence.main([*args, '--output', str(output)])
                    self.assertTrue(changed); self.assertFalse(output.exists()); self.assertEqual(target.read_bytes(), raw)
                    with redirect_stdout(StringIO()): evidence.main([*args, '--output', str(output)])
                    self.assertTrue(output.is_dir())

    def test_relocatable_output_parents_reject_before_writes(self):
        for temporary, component in itertools.product((False, True), ('parent', 'ancestor')):
            with self.subTest(temporary=temporary, component=component), tempfile.TemporaryDirectory() as temp:
                base = Path(temp); parent = base / 'parent'; parent.mkdir(mode=0o700)
                bundle = base / 'input'; bundle.mkdir(); write(bundle / 'member.json', {'fixture': 'original'})
                (parent if component == 'parent' else base).chmod(0o777)
                destination = parent / 'output'; before = self.snapshot(bundle); opened = os.open
                attempted = False
                def relocated(path, flags, *args, **kwargs):
                    nonlocal attempted
                    if flags & os.O_CREAT:
                        attempted = True
                        if component == 'parent':
                            next(parent.iterdir()).rename(bundle / 'moved-output')
                        else:
                            parent.rename(bundle / 'moved-parent')
                    return opened(path, flags, *args, **kwargs)
                with patch.object(os, 'open', side_effect=relocated), patch.dict(os.environ, {'TMPDIR': str(parent)}):
                    with self.assertRaises((ValueError, OSError)):
                        evidence.write_outputs({'evidence.json': {'synthetic': True}}, None if temporary else destination,
                                               input_path=bundle)
                self.assertEqual(self.snapshot(bundle), before)
                self.assertFalse(attempted)
                self.assertEqual(list(parent.iterdir()), [])

    def test_output_parent_replacement_cannot_redirect_directory_creation(self):
        for temporary in (False, True):
            with self.subTest(temporary=temporary), tempfile.TemporaryDirectory() as temp:
                base = Path(temp); parent = base / 'parent'; parent.mkdir()
                bundle = base / 'input'; bundle.mkdir(); (bundle / 'marker').write_text('Retained')
                retained = base / 'retained-parent'; before = self.snapshot(bundle); replaced = False
                mkdir = os.mkdir
                def replace_parent(path, *args, **kwargs):
                    nonlocal replaced
                    if not replaced:
                        parent.rename(retained); parent.symlink_to(bundle, target_is_directory=True); replaced = True
                    return mkdir(path, *args, **kwargs)
                with patch.object(os, 'mkdir', side_effect=replace_parent), patch.dict(os.environ, {'TMPDIR': str(parent)}):
                    with self.assertRaises((ValueError, OSError)):
                        evidence.write_outputs({'evidence.json': {}}, None if temporary else parent / 'output',
                                               input_path=bundle)
                self.assertTrue(replaced); self.assertEqual(self.snapshot(bundle), before)

    def test_input_parent_replacement_does_not_redirect_reads(self):
        for stage in ('validated', 'file_open'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as temp:
                base = Path(temp); parent = base / 'input'; parent.mkdir()
                outside = base / 'outside'; outside.mkdir()
                target = parent / 'member.json'; write(target, {'value': 'inside'})
                write(outside / 'member.json', {'value': 'outside'})
                retained = base / 'retained'; replaced = False
                safe = evidence.safe_path; opened = os.open
                def replace():
                    nonlocal replaced
                    if not replaced:
                        parent.rename(retained); parent.symlink_to(outside, target_is_directory=True); replaced = True
                def validated(path, **kwargs):
                    result = safe(path, **kwargs)
                    if stage == 'validated' and result == target: replace()
                    return result
                def file_open(path, flags, *args, **kwargs):
                    if stage == 'file_open' and not flags & os.O_DIRECTORY: replace()
                    return opened(path, flags, *args, **kwargs)
                with patch.object(evidence, 'safe_path', side_effect=validated), patch.object(os, 'open', side_effect=file_open):
                    if stage == 'validated':
                        with self.assertRaises((ValueError, OSError)): evidence.read_json(target)
                    else:
                        self.assertEqual(evidence.read_json(target), {'value': 'inside'})
                self.assertTrue(replaced)

    def test_static_normalization_uses_anchored_input_bytes(self):
        root = self.root / 'static-anchored'; shutil.copytree(FIXTURES / 'static-synthetic', root)
        before = self.snapshot(root)
        outside = self.root / 'outside-static'; shutil.copytree(root, outside)
        versions = evidence.read_json(outside / 'versions.json'); versions.pop('fixture')
        write(outside / 'versions.json', versions)
        target = root / 'versions.json'; retained = self.root / 'retained-static'; opened = os.open; replaced = False
        def file_open(path, flags, *args, **kwargs):
            nonlocal replaced
            swap = not replaced and not flags & os.O_DIRECTORY and (Path(path) == target or str(path) == target.name)
            if swap:
                root.rename(retained); root.symlink_to(outside, target_is_directory=True); replaced = True
            try:
                return opened(path, flags, *args, **kwargs)
            finally:
                if swap:
                    root.unlink(); retained.rename(root)
        with patch.object(os, 'open', side_effect=file_open):
            with self.assertRaisesRegex(ValueError, 'Input directory entries changed'):
                evidence.normalize_static(root, 'podman')
        self.assertTrue(replaced)
        self.assertEqual(self.snapshot(root), before)

    def test_output_names_and_descriptor_support_fail_before_creation(self):
        for name in ('../escape.json', '/escape.json', 'nested/output.json'):
            with self.subTest(name=name):
                destination = self.root / 'rejected-output'
                with self.assertRaises(ValueError): evidence.write_outputs({name: {}}, destination)
                self.assertFalse(destination.exists())
        with patch.object(evidence, 'SECURE_DIRECTORY_OUTPUT', False):
            with self.assertRaisesRegex(ValueError, 'Secure directory output unsupported'):
                evidence.write_outputs({'evidence.json': {}}, self.root / 'unsupported')
        self.assertFalse((self.root / 'unsupported').exists())

    def snapshot(self, root):
        return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
                for p in root.rglob('*')}

    def test_behavioral_reference_budget_supports_reward_companions(self):
        from skillevaluator.tier3.harbor import report_data as native_reports
        from skillevaluator.tier3.harbor.collector import _pass_summary
        root = self.native(); run = next((root / 'results/podman').iterdir())
        entries = [{'id': str(i), 'question': 'Synthetic question', 'ground_truth': 'Synthetic answer',
                    'expected_skill': 'podman', 'skill_workspace_mode': 'isolated'} for i in range(1, 1001)]
        snapshot = native_reports.build_dataset_snapshot(entries, evaluator_version='0.3.0')
        write(run / 'dataset_snapshot.json', snapshot)
        config = evidence.read_json(run / 'run_config.json'); config['harbor']['n_attempts'] = 3
        write(run / 'run_config.json', config)
        result = evidence.read_json(run / 'result.json'); result['run_config'] = config
        for key in ('dataset_digest', 'dataset_digest_algorithm', 'dataset_summary'): result[key] = snapshot[key]
        policy = evidence.read_json(run / 'attempt_policy.json'); policy['max_attempts'] = 3
        write(run / 'attempt_policy.json', policy)
        provenance = evidence.read_json(root / 'provenance.json')
        provenance.update(mode='confirmation', dataset_digest=snapshot['dataset_digest'])
        write(root / 'provenance.json', provenance)
        for arm in ('with_skill', 'without_skill'):
            base = run / 'codex' / arm.replace('_', '-')
            summary = evidence.read_json(base / 'summary.json')
            templates = {}
            for case, row in summary['pass_at_k']['cases'].items():
                trial = base / 'trials' / row['attempts'][0]['trial']
                templates[case] = (evidence.read_json(trial / 'result.json'), evidence.read_json(trial / 'reward.json'))
            shutil.rmtree(base / 'trials')
            rewards = []
            for case in range(1, 1001):
                for attempt in range(1, 4):
                    native, reward = copy.deepcopy(templates[str((case - 1) % 10 + 1)])
                    trial = f'{case}__fixture-attempt{attempt}'
                    native.update(id=f'{arm}-{case}-{attempt}', trial_name=trial,
                                  task_name=f'nvidia/skillevaluator-{case}')
                    reward.update(entry_id=str(case), trial_id=trial)
                    write(base / 'trials' / trial / 'result.json', native)
                    write(base / 'trials' / trial / 'reward.json', reward)
                    rewards.append({**reward, '_trial_name': trial})
            summary.update(expected_attempts=3000, scored_attempts=3000, num_trials=3000)
            summary['pass_at_k'] = _pass_summary(rewards, n_attempts=3, pass_threshold=policy['pass_threshold'],
                                               expected_cases=1000, expected_case_ids=[str(i) for i in range(1, 1001)])
            write(base / 'summary.json', summary)
            result['agents']['codex']['conditions'][arm].update(expected_attempts=3000, scored_attempts=3000)
            result['agents']['codex']['pass_at_k'][arm] = summary['pass_at_k']
        write(run / 'result.json', result)
        data = evidence.normalize_behavioral(root, 'podman')
        self.assertEqual(len(data['observations']), 6000)
        self.assertGreater(len(data['references']), 12000)
        self.assertEqual(len({row['id'] for row in data['references']}), len(data['references']))
        self.assertEqual(data['metrics'], self.data()['metrics'])
        with self.assertRaisesRegex(ValueError, 'Public report size'):
            evidence.project(data)

    def test_behavioral_reference_id_lookup_work_is_linear(self):
        root = self.native(); baseline = evidence.normalize_behavioral(root, 'podman')
        lookups = 0
        class CountingReference(dict):
            def __getitem__(self, key):
                nonlocal lookups
                if key == 'id': lookups += 1
                return super().__getitem__(key)
        reference = evidence.reference_from_digest; validate = evidence.validate_evidence
        def counted(*args, **kwargs): return CountingReference(reference(*args, **kwargs))
        def plain_validation(data, **kwargs):
            data['references'] = [dict(row) for row in data['references']]
            return validate(data, **kwargs)
        with patch.object(evidence, 'reference_from_digest', side_effect=counted), \
                patch.object(evidence, 'validate_evidence', side_effect=plain_validation):
            actual = evidence.normalize_behavioral(root, 'podman')
        self.assertEqual(evidence.encoded(actual), evidence.encoded(baseline))
        self.assertLessEqual(lookups, 8 * len(actual['references']))

    def test_reviewed_extract_reference_lookup_avoids_manifest_rescans(self):
        root = self.root / 'large-extract'
        shutil.copytree(FIXTURES / 'podman-native', root)
        baseline = evidence.normalize_behavioral(root, 'podman')
        path = root / 'extract-manifest.json'; manifest = evidence.read_json(path)
        padding = evidence.MAX_REFERENCES - len(manifest['members'])
        manifest['members'] = [{'member': f'padding/member-{i}.json',
                               'original_digest': evidence.digest_bytes(b'original'),
                               'extract_digest': evidence.digest_bytes(b'extract')} for i in range(padding)] + manifest['members']
        write(path, manifest)
        visits = 0
        class CountingMembers(list):
            def __iter__(self):
                nonlocal visits
                for row in super().__iter__():
                    visits += 1
                    yield row
        load = evidence.load_extract
        def counted_load(directory, **kwargs):
            extract = load(directory, **kwargs)
            extract['members'] = CountingMembers(extract['members'])
            return extract
        with patch.object(evidence, 'REVIEWED_EXTRACT_MANIFESTS', frozenset({evidence.digest_bytes(path.read_bytes())})), \
                patch.object(evidence, 'load_extract', side_effect=counted_load):
            actual = evidence.normalize_behavioral(root, 'podman')
            self.assertEqual(evidence.encoded(actual), evidence.encoded(baseline))
            self.assertLessEqual(visits, evidence.MAX_REFERENCES)
            extract = load(root)
            for member, digest in (('missing.json', evidence.digest_bytes(b'missing')),
                                   (manifest['members'][-1]['member'], evidence.digest_bytes(b'wrong'))):
                with self.assertRaisesRegex(ValueError, 'Reviewed extract mismatch'):
                    evidence.reference_from_digest(root, root / member, extract['artifact_id'], digest, extract=extract)

    def test_standalone_cli_disables_repository_bytecode_writes(self):
        checkout = self.repo(); scripts = checkout / '.github/scripts'; scripts.mkdir(parents=True)
        for name in ('skill_evidence.py', 'skill_reports.py', 'gh_evaluations.py'):
            shutil.copyfile(REPO / '.github/scripts' / name, scripts / name)
        inputs = checkout / 'fixtures'; shutil.copytree(FIXTURES, inputs)
        commands = [['inventory'], ['normalize', '--kind', 'behavioral', '--skill', 'podman',
                    '--input', str(inputs / 'podman-native')], ['normalize', '--kind', 'static',
                    '--skill', 'podman', '--input', str(inputs / 'static-synthetic')],
                    ['project', '--input', str(inputs / 'gh-no-model.json')]]
        env = {k: v for k, v in os.environ.items() if k not in ('PYTHONDONTWRITEBYTECODE', 'PYTHONPYCACHEPREFIX')}
        before = self.snapshot(checkout)
        for index, command in enumerate(commands):
            with self.subTest(command=command[0], index=index):
                output = self.root / f'cli-output-{index}'
                result = subprocess.run([sys.executable, str(scripts / 'skill_evidence.py'), *command,
                                         '--output', str(output)], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.snapshot(checkout), before)
                self.assertTrue(output.is_dir())
                self.assertFalse(any(checkout.rglob('__pycache__')))

    def test_cli_rejects_temporary_parent_inside_input_without_mutation(self):
        root = self.native()
        before = self.snapshot(root)
        result = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
                                 'normalize', '--kind', 'behavioral', '--skill', 'podman', '--input', str(root)],
                                env={**os.environ, 'TMPDIR': str(root)}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('Evidence contract rejected', result.stderr)
        self.assertEqual(self.snapshot(root), before)

    def test_rejects_temporary_parent_inside_checkout_without_mutation(self):
        workspace = self.repo()
        before = self.snapshot(workspace)
        with patch.dict(os.environ, {'TMPDIR': str(workspace)}), patch.object(evidence.tempfile, 'tempdir', None):
            with self.assertRaisesRegex(ValueError, 'outside checkout'):
                evidence.write_outputs({'evidence.json': {}}, workspace=workspace)
        self.assertEqual(self.snapshot(workspace), before)

    def test_unsafe_temporary_parents_do_not_fall_back(self):
        parent = self.root / 'parent'; parent.mkdir()
        alias = self.root / 'alias'; alias.symlink_to(parent, target_is_directory=True)
        file = self.root / 'file'; file.write_text('fixture')
        for candidate in (alias, self.root / 'missing', file):
            with self.subTest(parent=candidate), patch.dict(os.environ, {'TMPDIR': str(candidate)}), \
                    patch.object(evidence.tempfile, 'tempdir', None):
                before = self.snapshot(parent)
                with self.assertRaises(ValueError), patch.object(evidence.tempfile, 'mkdtemp') as create:
                    evidence.write_outputs({'evidence.json': {}})
                create.assert_not_called()
                self.assertEqual(self.snapshot(parent), before)

    def test_valid_temporary_parent_and_explicit_output(self):
        parent = self.root / 'parent'; parent.mkdir()
        workspace = self.repo()
        values = {'evidence.json': {'schema_version': 1}}
        with patch.dict(os.environ, {'TMPDIR': str(parent)}), patch.object(evidence.tempfile, 'tempdir', None):
            output = evidence.write_outputs(values, workspace=workspace)
        self.assertEqual(output.parent, parent)
        self.assertEqual((output / 'evidence.json').read_bytes(), evidence.encoded(values['evidence.json']))
        # An explicit destination does not depend on temporary settings.
        with patch.dict(os.environ, {'TMPDIR': str(workspace)}):
            explicit = evidence.write_outputs(values, self.root / 'explicit', workspace=workspace)
        self.assertEqual((explicit / 'evidence.json').read_bytes(), (output / 'evidence.json').read_bytes())
        before = self.snapshot(workspace)
        with self.assertRaises(ValueError):
            evidence.write_outputs(values, workspace / 'new', workspace=workspace)
        self.assertEqual(self.snapshot(workspace), before)


    def repository_fixture(self):
        repo = self.repo(); self.local(repo, 'podman', True)
        def git(*args):
            return subprocess.run(['git', '-C', str(repo), *args], check=True,
                                  capture_output=True, text=True).stdout.strip()
        git('init', '-q'); git('add', '.apm')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Source fixture')
        git('remote', 'add', 'origin', 'https://github.com/thetechgy/agent-engineering-baseline.git')
        return repo, git

    def test_workspace_origin_association_across_readers(self):
        repo, git = self.repository_fixture(); rev = git('rev-parse', 'HEAD')
        native = self.native()
        static = self.root / 'static'; shutil.copytree(FIXTURES / 'static-synthetic', static)
        path = next((static / 'reports/podman').glob('*.json'))
        report = evidence.read_json(path)
        def declare(name):
            declaration = {'repository': name, 'commit': rev}
            self.mutate(native, '/run_config.json', lambda d: d.update(evaluated_source=declaration))
            self.mutate(native, '/result.json', lambda d: d['run_config'].update(evaluated_source=declaration))
            self.mutate(native, '/provenance.json', lambda d: d.update(revision=rev))
            report['evaluated_source'] = declaration; write(path, report)
        for origin in ('https://github.com/Example/Fixture.git', 'git@github.com:example/fixture.git',
                       'ssh://git@github.com/example/fixture', 'https://github.com/example/fixture'):
            with self.subTest(origin=origin):
                git('remote', 'set-url', 'origin', origin); declare('EXAMPLE/Fixture')
                before = self.snapshot(repo)
                inv = evidence.inventory(repo)
                self.assertTrue(all(row['source']['repository'] == 'example/fixture' for row in inv['skills']))
                data = evidence.normalize_behavioral(native, 'podman', workspace=repo)
                scan = evidence.normalize_static(static, 'podman', workspace=repo)
                for value in (data, scan):
                    self.assertEqual(value['source']['repository'], 'example/fixture')
                    self.assertIsNotNone(value['source']['content']['digest'])
                    evidence.project(value)
                self.assertIsNotNone(data['dataset']['authored_digest'])
                self.assertEqual(self.snapshot(repo), before)
                declare('microsoft/vscode')
                with patch.object(evidence, 'historical_content') as contents, patch.object(evidence, 'historical_blob') as blob:
                    for kind in ('behavioral', 'static'):
                        output = self.root / 'conflicting-output'
                        original = getattr(evidence, 'normalize_' + kind)
                        with patch.object(evidence, 'normalize_' + kind,
                                side_effect=lambda *a, fn=original: fn(*a, workspace=repo)):
                            with self.assertRaisesRegex(ValueError, 'repository conflicts'):
                                evidence.main(['normalize', '--kind', kind, '--skill', 'podman',
                                               '--input', str(native if kind == 'behavioral' else static), '--output', str(output)])
                        self.assertFalse(output.exists())
                    contents.assert_not_called(); blob.assert_not_called()
        declare(None)
        for value in (evidence.normalize_behavioral(native, 'podman', workspace=repo),
                      evidence.normalize_static(static, 'podman', workspace=repo)):
            self.assertIsNone(value['source']['repository'])
            self.assertIsNone(value['source']['content']['digest'])
            self.assertIn('source_unavailable', value['availability']['reasons'])
        declare('example/fixture')
        linked = self.root / 'linked'; git('worktree', 'add', '--detach', str(linked), rev)
        self.assertEqual(evidence.inventory(linked)['skills'][0]['source']['repository'], 'example/fixture')
        self.assertEqual(evidence.normalize_behavioral(native, 'podman', workspace=linked)['source']['revision'], rev)
        self.assertEqual(evidence.normalize_static(static, 'podman', workspace=linked)['source']['revision'], rev)
        for origin in (None, 'file:///tmp/repository', 'https://example.invalid/example/fixture',
                       'https://user:password@github.com/example/fixture', 'https://github.com/example/fixture?query'):
            with self.subTest(missing_or_unsupported=origin):
                git('config', '--unset-all', 'remote.origin.url')
                if origin is not None: git('config', 'remote.origin.url', origin)
                with patch.object(evidence, 'historical_content') as contents, patch.object(evidence, 'historical_blob') as blob:
                    inv = evidence.inventory(repo)
                    self.assertIsNone(inv['skills'][0]['source']['repository'])
                    self.assertIsNone(inv['skills'][0]['source']['revision'])
                    data = evidence.normalize_behavioral(native, 'podman', workspace=repo)
                    scan = evidence.normalize_static(static, 'podman', workspace=repo)
                    for value in (data, scan):
                        self.assertIsNone(value['source']['repository'])
                        self.assertIsNone(value['source']['revision'])
                        self.assertIsNone(value['source']['content']['digest'])
                        self.assertIn('source_unavailable', value['availability']['reasons'])
                        evidence.project(value)
                    self.assertIsNone(data['dataset']['authored_digest'])
                    contents.assert_not_called(); blob.assert_not_called()
                if origin is None: git('config', 'remote.origin.url', 'placeholder')

    def test_reviewed_source_unknown_without_workspace_association(self):
        data = evidence.normalize_behavioral(FIXTURES / 'podman-native', 'podman', workspace=self.root)
        self.assertEqual(data['source'], evidence.source('podman', path='.apm/skills/podman'))
        self.assertIsNone(data['dataset']['authored_digest'])
        self.assertIn('source_unavailable', data['availability']['reasons'])
        self.assertEqual(evidence.project(data)['metrics'], self.data()['metrics'])
        for key, value in (('skill_id', 'other'), ('repository', 'microsoft/vscode'), ('revision', 'a' * 40)):
            changed = copy.deepcopy(data); changed['source'][key] = value
            with self.assertRaises(ValueError): evidence.project(changed)

    def test_native_failure_carriers_reconcile_scores_and_execution(self):
        root = self.native(); run = next((root / 'results/podman').iterdir())
        baseline = evidence.normalize_behavioral(root, 'podman')
        carriers = ('reward', 'trial', 'exception', 'verifier', 'nested_reward',
                    'step', 'step_exception', 'step_verifier', 'step_reward', 'step_incomplete')
        for arm, carrier in itertools.product(('with_skill', 'without_skill'), carriers):
            with self.subTest(arm=arm, carrier=carrier):
                path = next((run / 'codex' / arm.replace('_', '-') / 'trials').glob('*/result.json'))
                reward_path = path.parent / 'reward.json'
                result_path = run / 'result.json'
                summary_path = run / 'codex' / arm.replace('_', '-') / 'summary.json'
                originals = {p: evidence.read_json(p) for p in (path, reward_path, result_path, summary_path)}
                record = copy.deepcopy(originals[path]); reward = copy.deepcopy(originals[reward_path])
                if carrier.startswith('step'):
                    step = {'step_name': 'fixture', 'verifier_result': copy.deepcopy(record['verifier_result'])}
                    record['step_results'] = [step]
                    target = step if carrier in ('step', 'step_exception') else step['verifier_result'] if carrier == 'step_verifier' else step['verifier_result']['rewards']
                    if carrier == 'step_exception': target['exception_info'] = {}
                    elif carrier == 'step_incomplete': target.pop('accuracy')
                    else: target['evaluation_status'] = 'FaIlEd'
                elif carrier == 'exception': record['exception_info'] = {'exception_message': 'PRIVATE-DIAGNOSTIC'}
                else:
                    target = {'reward': reward, 'trial': record, 'verifier': record['verifier_result'],
                              'nested_reward': record['verifier_result']['rewards']}[carrier]
                    target['evaluation_status'] = 'ERROR'
                    target['evaluation_errors'] = ['PRIVATE-DIAGNOSTIC']
                write(path, record); write(reward_path, reward)
                before = self.snapshot(root); output = self.root / 'failure-output'
                with self.assertRaisesRegex(ValueError, 'Native failure contradicts'):
                    evidence.normalize_behavioral(root, 'podman')
                with self.assertRaisesRegex(ValueError, 'Native failure contradicts'):
                    evidence.project(dict(baseline), behavioral_bundle=root)
                cli = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'),
                    'normalize', '--kind', 'behavioral', '--skill', 'podman', '--input', str(root),
                    '--output', str(output)], capture_output=True, text=True)
                self.assertEqual(cli.returncode, 1); self.assertFalse(output.exists())
                self.assertEqual(cli.stderr, 'Evidence contract rejected (ValueError)\n')
                self.assertEqual(self.snapshot(root), before)
                # Preserve the failed carrier while making its authoritative scores unscored.
                for key in evidence.SCORE_FIELDS:
                    record['verifier_result']['rewards'].pop(key, None); reward.pop(key, None)
                write(path, record); write(reward_path, reward)
                summary = copy.deepcopy(originals[summary_path]); result = copy.deepcopy(originals[result_path])
                self.unscore_case(summary, reward['entry_id'])
                summary.update(scored_attempts=9, execution_status='incomplete')
                result['report_status'] = 'incomplete'
                result['agents']['codex']['conditions'][arm].update(scored_attempts=9, execution_status='incomplete')
                result['agents']['codex']['pass_at_k'][arm] = copy.deepcopy(summary['pass_at_k'])
                write(summary_path, summary); write(result_path, result)
                data = evidence.normalize_behavioral(root, 'podman')
                public = evidence.project(dict(data), behavioral_bundle=root)
                self.assertIn('execution_incomplete', public['availability']['reasons'])
                self.assertNotIn('PRIVATE-DIAGNOSTIC', evidence.encoded(public).decode())
                stripped = copy.deepcopy(dict(data)); stripped['availability']['reasons'].remove('execution_incomplete')
                with self.assertRaises(ValueError): evidence.project(stripped, behavioral_bundle=root)
                for p, value in originals.items(): write(p, value)
        self.assertEqual(evidence.encoded(baseline), evidence.encoded(evidence.normalize_behavioral(root, 'podman')))

    def test_snapshot_markers_and_shared_read_budget(self):
        from skillevaluator.tier3 import output_provenance
        path = self.local(self.root, 'alpha')
        (path / 'README.md').write_text('Additional captured member')
        src = evidence.source('alpha', contents=evidence.skill_content(path))
        for kind in ('file', 'directory'):
            marker = path / output_provenance.GENERATED_OUTPUT_MARKER
            if kind == 'file': marker.write_text('{}')
            else: marker.mkdir()
            with patch.object(output_provenance, '_load_existing_key') as key, \
                    patch.object(evidence, 'skill_projection_files') as selector:
                with self.assertRaisesRegex(ValueError, 'Generated output'):
                    evidence.verify_source_snapshot(path, src)
                key.assert_not_called(); selector.assert_not_called()
            if kind == 'file': marker.unlink()
            else: marker.rmdir()
        consumed = sum(p.stat().st_size for p in path.iterdir())
        with patch.object(evidence, 'NORMALIZATION_LIMIT', consumed): evidence.verify_source_snapshot(path, src)
        with patch.object(evidence, 'NORMALIZATION_LIMIT', consumed - 1):
            with self.assertRaisesRegex(ValueError, 'Normalization byte limit'):
                evidence.verify_source_snapshot(path, src)

    def test_snapshot_rechecks_directory_membership_after_capture(self):
        path = self.local(self.root, 'alpha'); (path / 'nested').mkdir()
        src = evidence.source('alpha', contents=evidence.skill_content(path))
        original = evidence.read_bytes; changed = False
        def addition(*args, **kwargs):
            nonlocal changed
            raw = original(*args, **kwargs)
            if not changed:
                changed = True; (path / 'nested/added.md').write_text('New source member')
            return raw
        with patch.object(evidence, 'read_bytes', side_effect=addition):
            with self.assertRaisesRegex(ValueError, 'Input directory'):
                evidence.verify_source_snapshot(path, src)
        self.assertTrue(changed)

    def test_source_projection_never_invokes_native_filesystem_selector(self):
        from skillevaluator.tier3.harbor import adapter
        from skillevaluator.tier3 import output_provenance
        path = self.local(self.root, 'alpha')
        for member in ('nested/skill.md', 'nested/EVALS/private.json', 'nested/evals', 'examples/evals/visible.json',
                       'results/private.json', 'README.md'):
            target = path / member; target.parent.mkdir(parents=True, exist_ok=True); target.write_text('{}')
        files = evidence.safe_tree(path)
        ignore = adapter._runtime_skill_copy_ignore(path)
        expected = [p for p in files if not adapter._runtime_projection_path_is_ignored(p, path, ignore)]
        with patch.object(adapter, '_runtime_skill_copy_ignore', side_effect=AssertionError('Filesystem selector invoked')), \
                patch.object(output_provenance, '_load_existing_key') as key:
            self.assertEqual(evidence.skill_projection_files(path, files), expected)
            evidence.skill_content(path)
            key.assert_not_called()

    def test_retrieval_rechecks_trusted_expiry_before_member_access(self):
        data = self.data(); ref = data['references'][0]
        deadline = datetime.fromisoformat(evidence.REVIEWED_REFERENCE_EXPIRY[(ref['artifact_id'], ref['artifact_digest'])])
        for delta in (-1, 0, 1):
            with self.subTest(delta=delta), patch.object(evidence, 'utc_now', return_value=deadline + timedelta(microseconds=delta)), \
                    patch.object(evidence, 'read_bytes', wraps=evidence.read_bytes) as reader:
                if delta < 0:
                    # The reviewed extract is not the retained original member.
                    with self.assertRaisesRegex(ValueError, 'member digest mismatch'):
                        evidence.verify_reference(FIXTURES / 'podman-native', ref)
                    self.assertEqual(reader.call_count, 1)
                else:
                    with self.assertRaisesRegex(ValueError, 'expired'):
                        evidence.verify_reference(FIXTURES / 'podman-native', ref)
                    reader.assert_not_called()

    def test_oversized_numbers_are_bounded_cli_rejections(self):
        root = self.native(); run = next((root / 'results/podman').iterdir())
        path = run / 'result.json'; original = evidence.read_json(path)
        for kind in ('metric', 'summary', 'constituent', 'project'):
            with self.subTest(kind=kind):
                result = copy.deepcopy(original)
                trial_path = next((run / 'codex/with-skill/trials').glob('*/result.json'))
                trial = evidence.read_json(trial_path)
                if kind == 'metric': result['agents']['codex']['lift']['overall']['delta'] = 10 ** 400
                elif kind == 'summary':
                    next(iter(result['agents']['codex']['pass_at_k']['with_skill']['cases'].values()))['attempts'][0]['score'] = 10 ** 400
                elif kind == 'constituent':
                    step = copy.deepcopy(trial['verifier_result']); step['rewards']['accuracy'] = 10 ** 400
                    write(trial_path, {**trial, 'step_results': [{'step_name': 'fixture', 'verifier_result': step}]})
                write(path, result)
                args = ['normalize', '--kind', 'behavioral', '--skill', 'podman', '--input', str(root)]
                if kind == 'project':
                    data = self.data(); data['metrics'][0]['value'] = 10 ** 400
                    input_path = self.root / 'huge.json'; write(input_path, data)
                    args = ['project', '--input', str(input_path)]
                output = self.root / ('oversized-output-' + kind); before = self.snapshot(root)
                cli = subprocess.run([sys.executable, str(REPO / '.github/scripts/skill_evidence.py'), *args,
                                      '--output', str(output)], capture_output=True, text=True)
                self.assertEqual(cli.returncode, 1); self.assertFalse(output.exists())
                self.assertRegex(cli.stderr, r'^Evidence contract rejected \((ValueError|OverflowError)\)\n$')
                self.assertEqual(self.snapshot(root), before)
                write(path, original); write(trial_path, trial)


    def test_inventory_gh_checks_never_reenumerate_captured_trees(self):
        with patch.object(evidence.reports, 'regular_tree', side_effect=AssertionError('Unbounded re-enumeration')) as walker:
            value = evidence.inventory(REPO)
            self.assertIn('gh', [row['source']['skill_id'] for row in value['skills']])
            walker.assert_not_called()

    def test_inventory_gh_replacements_reject_without_unbounded_walk(self):
        import gh_evaluations as gh
        for target_name in ('.agents/skills/gh', '.agents/skills/' + gh.COMPETING, '.github/evals/gh'):
            with self.subTest(target=target_name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / 'workspace'; self.local(root, 'alpha')
                for member in ('.agents/skills/gh', '.agents/skills/' + gh.COMPETING, '.github/evals/gh'):
                    shutil.copytree(REPO / member, root / member)
                shutil.copyfile(REPO / 'apm.lock.yaml', root / 'apm.lock.yaml')
                original = evidence.safe_tree; swapped = False
                def scanned(path, **kwargs):
                    nonlocal swapped
                    files = original(path, **kwargs)
                    if Path(path) == root / '.agents/skills' / gh.COMPETING and not swapped:
                        swapped = True
                        target = root / target_name; target.rename(Path(temp) / 'retained')
                        target.mkdir(); (target / 'unexpected').mkdir()
                    return files
                with patch.object(evidence, 'safe_tree', side_effect=scanned), \
                        patch.object(evidence.reports, 'regular_tree', side_effect=AssertionError('Unbounded re-enumeration')) as walker:
                    with self.assertRaisesRegex(ValueError, 'Input directory'):
                        evidence.inventory(root)
                    walker.assert_not_called()
                self.assertTrue(swapped)

    def test_native_upstream_attribution_requires_reviewed_skill_identity(self):
        import gh_evaluations as gh
        for name, field in itertools.product(('podman', 'gh'), ('upstream_revision', 'competing_revision')):
            with self.subTest(skill=name, field=field):
                root = self.native()
                if name == 'gh':
                    (root / 'results/podman').rename(root / 'results/gh')
                    self.mutate(root, '/result.json', lambda d: d.update(skill_name='gh'))
                    self.mutate(root, '/provenance.json', lambda d: d.update(skill='gh'))
                provenance_path = root / 'provenance.json'; original = evidence.read_json(provenance_path)
                baseline = evidence.normalize_behavioral(root, name)
                approved = evidence.reports.benchmark_policy('gh')[field]
                for revision in ('f' * 40, approved):
                    with self.subTest(revision=revision):
                        provenance = copy.deepcopy(original); provenance['policy'][field] = revision
                        write(provenance_path, provenance)
                        if name == 'gh' and revision == approved:
                            data = evidence.normalize_behavioral(root, name)
                            if field == 'upstream_revision':
                                self.assertEqual(data['source']['owner'], 'upstream')
                                self.assertEqual(data['source']['repository'], 'cli/cli')
                                self.assertEqual(data['source']['revision'], gh.UPSTREAM)
                            else:
                                self.assertEqual(data['arms'][0]['condition']['competing_skills'][0]['revision'], approved)
                            evidence.project(dict(data), behavioral_bundle=root)
                        else:
                            output = self.root / 'upstream-rejected'
                            before = self.snapshot(root)
                            with self.assertRaisesRegex(ValueError, 'Unreviewed upstream attribution'):
                                evidence.normalize_behavioral(root, name)
                            with self.assertRaisesRegex(ValueError, 'Unreviewed upstream attribution'):
                                evidence.project(dict(baseline), behavioral_bundle=root)
                            with self.assertRaisesRegex(ValueError, 'Unreviewed upstream attribution'):
                                evidence.main(['normalize', '--kind', 'behavioral', '--skill', name,
                                               '--input', str(root), '--output', str(output)])
                            self.assertFalse(output.exists())
                            self.assertEqual(self.snapshot(root), before)
                shutil.rmtree(root)


    def test_origin_parser_uses_captured_config_and_rejects_transient_replacement(self):
        repo, git = self.repository_fixture(); config = repo / '.git/config'
        expected = 'thetechgy/agent-engineering-baseline'
        for replacement in (False, True):
            with self.subTest(replacement=replacement):
                original = config.read_bytes(); info = config.stat(); retained = self.root / 'retained-config'
                forged = original.replace(expected.encode(), b'forged/repo')
                popen = subprocess.Popen; invoked = False
                def swapped(command, *args, **kwargs):
                    nonlocal invoked
                    if command[0] != 'git' or 'config' not in command:
                        return popen(command, *args, **kwargs)
                    invoked = True
                    if replacement: config.rename(retained)
                    config.write_bytes(forged)
                    process = popen(command, *args, **kwargs); wait = process.wait; restored = False
                    def restore(*a, **kw):
                        nonlocal restored
                        result = wait(*a, **kw)
                        if not restored:
                            if replacement:
                                config.unlink(); retained.rename(config)
                            else: config.write_bytes(original)
                            os.utime(config, ns=(info.st_atime_ns, info.st_mtime_ns))
                            restored = True
                        return result
                    process.wait = restore
                    return process
                with patch.object(subprocess, 'Popen', side_effect=swapped):
                    with self.assertRaisesRegex(ValueError, 'Input (directory|member)'):
                        evidence.workspace_repository(repo)
                self.assertTrue(invoked)
                self.assertEqual(config.read_bytes(), original)
                self.assertEqual(evidence.workspace_repository(repo), expected)
        budget = evidence.ReadBudget(); evidence.workspace_repository(repo, budget=budget)
        consumed = evidence.NORMALIZATION_LIMIT - budget.remaining
        self.assertEqual(consumed, config.stat().st_size)
        with patch.object(evidence, 'NORMALIZATION_LIMIT', consumed):
            self.assertEqual(evidence.workspace_repository(repo), expected)
        with patch.object(evidence, 'NORMALIZATION_LIMIT', consumed - 1):
            with self.assertRaisesRegex(ValueError, 'Normalization byte limit'):
                evidence.workspace_repository(repo)

    def test_origin_metadata_revalidated_at_all_publication_boundaries(self):
        repo, git = self.repository_fixture()
        linked = self.root / 'linked'; git('worktree', 'add', '--detach', str(linked), 'HEAD')
        gitdir = Path((linked / '.git').read_text().strip().removeprefix('gitdir: '))
        native = self.native(); static = self.root / 'static'; shutil.copytree(FIXTURES / 'static-synthetic', static)
        report_path = next((static / 'reports/podman').glob('*.json'))
        report = evidence.read_json(report_path)
        report['evaluated_source'] = {'repository': 'thetechgy/agent-engineering-baseline', 'commit': git('rev-parse', 'HEAD')}
        write(report_path, report)
        targets = ((repo, repo / '.git/config'), (linked, linked / '.git'),
                   (linked, gitdir / 'gitdir'), (linked, gitdir / 'commondir'))
        resolver = evidence.workspace_repository
        for kind, (workspace, target) in itertools.product(('inventory', 'behavioral', 'static'), targets):
            with self.subTest(kind=kind, metadata=target.name):
                raw = target.read_bytes(); info = target.stat(); changed = False
                def transient(path, **kwargs):
                    nonlocal changed
                    value = resolver(path, **kwargs)
                    target.write_bytes(raw + b'\n'); target.write_bytes(raw)
                    os.utime(target, ns=(info.st_atime_ns, info.st_mtime_ns)); changed = True
                    return value
                output = self.root / 'metadata-rejected'
                name = 'inventory' if kind == 'inventory' else 'normalize_' + kind
                operation = getattr(evidence, name)
                invoke = (lambda: operation(workspace)) if kind == 'inventory' else (lambda *a: operation(*a, workspace=workspace))
                args = ['inventory'] if kind == 'inventory' else ['normalize', '--kind', kind, '--skill', 'podman',
                                                               '--input', str(native if kind == 'behavioral' else static)]
                with patch.object(evidence, 'workspace_repository', side_effect=transient), \
                        patch.object(evidence, name, side_effect=invoke), patch.object(evidence, 'write_outputs') as publish:
                    with self.assertRaisesRegex(ValueError, 'Input member changed'):
                        evidence.main([*args, '--output', str(output)])
                    publish.assert_not_called()
                self.assertTrue(changed); self.assertFalse(output.exists()); self.assertEqual(target.read_bytes(), raw)


    def test_unrelated_git_directory_pointers_leave_attribution_unknown(self):
        repo, git = self.repository_fixture()
        git('remote', 'set-url', 'origin', 'https://github.com/unrelated-owner/unrelated-repo.git')
        linked = self.root / 'linked'; git('worktree', 'add', '--detach', str(linked), 'HEAD')
        gitdir = Path((linked / '.git').read_text().strip().removeprefix('gitdir: '))
        workspace = self.root / 'unrelated'; self.local(workspace, 'podman', True)
        native = self.native(); static = self.root / 'static'; shutil.copytree(FIXTURES / 'static-synthetic', static)
        declaration = {'repository': 'unrelated-owner/unrelated-repo', 'commit': git('rev-parse', 'HEAD')}
        self.mutate(native, '/run_config.json', lambda d: d.update(evaluated_source=declaration))
        self.mutate(native, '/result.json', lambda d: d['run_config'].update(evaluated_source=declaration))
        self.mutate(native, '/provenance.json', lambda d: d.update(revision=declaration['commit']))
        path = next((static / 'reports/podman').glob('*.json')); report = evidence.read_json(path)
        report['evaluated_source'] = declaration; write(path, report)
        original = evidence.read_bytes; before = self.snapshot(repo)
        def guarded(path, **kwargs):
            self.assertNotEqual(path, repo / '.git/config', 'Unrelated config must not be read')
            return original(path, **kwargs)
        fabricated = self.root / 'fabricated'; fabricated.mkdir()
        (fabricated / 'gitdir').write_text(str(workspace / '.git') + '\n')
        (fabricated / 'commondir').write_text(str(repo / '.git') + '\n')
        for target in (repo / '.git', gitdir, fabricated, None):
            with self.subTest(target=target.name if target else 'direct-commondir'):
                if target:
                    (workspace / '.git').write_text('gitdir: ' + str(target) + '\n')
                else:
                    (workspace / '.git').unlink(); (workspace / '.git').mkdir()
                    (workspace / '.git/commondir').write_text(str(repo / '.git') + '\n')
                with patch.object(evidence, 'read_bytes', side_effect=guarded), \
                        patch.object(evidence, 'historical_content') as contents, patch.object(evidence, 'historical_blob') as blobs:
                    self.assertIsNone(evidence.workspace_repository(workspace))
                    values = (evidence.inventory(workspace)['skills'][0],
                              evidence.normalize_behavioral(native, 'podman', workspace=workspace),
                              evidence.normalize_static(static, 'podman', workspace=workspace))
                    for value in values:
                        self.assertIsNone(value['source']['repository']); self.assertIsNone(value['source']['revision'])
                        self.assertNotIn(b'unrelated-owner', evidence.encoded(value))
                    contents.assert_not_called(); blobs.assert_not_called()
        self.assertEqual(self.snapshot(repo), before)
        self.assertEqual(evidence.workspace_repository(linked), 'unrelated-owner/unrelated-repo')

    def test_inventory_rejects_transient_revision_metadata_changes(self):
        for kind, stage in itertools.product(('head', 'loose', 'packed', 'linked-head', 'linked-loose'), ('lookup', 'publication')):
            with self.subTest(kind=kind, stage=stage), tempfile.TemporaryDirectory() as temp, patch.object(self, 'root', Path(temp)):
                repo, git = self.repository_fixture(); rev = git('rev-parse', 'HEAD')
                branch = git('symbolic-ref', 'HEAD')
                git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '--allow-empty', '-qm', 'Same source')
                alternate = git('rev-parse', 'HEAD'); git('update-ref', 'HEAD', rev)
                workspace = repo
                if kind.startswith('linked'):
                    workspace = self.root / 'linked'
                    git('worktree', 'add', '--detach', str(workspace), rev)
                    gitdir = Path((workspace / '.git').read_text().strip().removeprefix('gitdir: '))
                    if kind == 'linked-loose': (gitdir / 'HEAD').write_text('ref: ' + branch + '\n')
                if kind == 'head':
                    git('checkout', '--detach', rev); target = repo / '.git/HEAD'
                elif kind == 'linked-head': target = gitdir / 'HEAD'
                elif kind == 'packed':
                    git('pack-refs', '--all', '--prune'); target = repo / '.git/packed-refs'
                else: target = repo / '.git' / branch
                raw = target.read_bytes(); info = target.stat(); changed = False
                name = 'resolve_git_revision' if stage == 'lookup' else 'historical_content'
                original = getattr(evidence, name)
                def transient(*args, **kwargs):
                    nonlocal changed
                    target.write_bytes(raw.replace(rev.encode(), alternate.encode())); changed = True
                    try: return original(*args, **kwargs)
                    finally:
                        target.write_bytes(raw); os.utime(target, ns=(info.st_atime_ns, info.st_mtime_ns))
                operation = evidence.inventory; output = self.root / 'revision-rejected'
                with patch.object(evidence, name, side_effect=transient), \
                        patch.object(evidence, 'inventory', side_effect=lambda: operation(workspace)), \
                        patch.object(evidence, 'write_outputs') as publish:
                    with self.assertRaisesRegex(ValueError, 'Input (directory|member)'):
                        evidence.main(['inventory', '--output', str(output)])
                    publish.assert_not_called()
                self.assertTrue(changed); self.assertFalse(output.exists()); self.assertEqual(target.read_bytes(), raw)
                self.assertEqual(evidence.inventory(workspace)['skills'][0]['source']['revision'], rev)

    def test_inventory_reference_capture_limits_and_absent_storage(self):
        repo, git = self.repository_fixture(); rev = git('rev-parse', 'HEAD')
        budget = evidence.ReadBudget(); evidence.workspace_repository(repo, budget=budget)
        self.assertEqual(evidence.inventory_revision(repo, budget), rev)
        consumed = evidence.NORMALIZATION_LIMIT - budget.remaining
        expected = sum(path.stat().st_size for path in (repo / '.git/config', repo / '.git/HEAD',
                                                        repo / '.git' / git('symbolic-ref', 'HEAD')))
        self.assertEqual(consumed, expected)
        for limit in (consumed, consumed - 1):
            with self.subTest(limit=limit), patch.object(evidence, 'NORMALIZATION_LIMIT', limit):
                budget = evidence.ReadBudget(); evidence.workspace_repository(repo, budget=budget)
                if limit == consumed: self.assertEqual(evidence.inventory_revision(repo, budget), rev)
                else:
                    with self.assertRaisesRegex(ValueError, 'Normalization byte limit'):
                        evidence.inventory_revision(repo, budget)
        budget = evidence.ReadBudget(); evidence.workspace_repository(repo, budget=budget)
        with patch.object(evidence, 'MAX_INPUT_ENTRIES', 1):
            with self.assertRaisesRegex(ValueError, 'Git reference entry limit'):
                evidence.inventory_revision(repo, budget)
        original = evidence.resolve_git_revision; packed = repo / '.git/packed-refs'
        def transient(path, budget):
            packed.write_text('# transient reference storage\n'); packed.unlink()
            return original(path, budget)
        with patch.object(evidence, 'resolve_git_revision', side_effect=transient):
            with self.assertRaisesRegex(ValueError, 'Input directory'):
                evidence.inventory(repo)
        git('update-ref', '-d', 'HEAD')
        self.assertIsNone(evidence.inventory(repo)['skills'][0]['source']['revision'])

    def test_inventory_cardinality_rejects_before_git_revision_capture(self):
        repo, _ = self.repository_fixture()
        with patch.object(evidence, 'MAX_CASES', 1), patch.object(evidence, 'inventory_revision') as capture:
            with self.assertRaisesRegex(ValueError, 'Inventory limit'): evidence.inventory(repo)
            capture.assert_not_called()

    def test_missing_origin_metadata_is_anchored_and_rechecked(self):
        repo, git = self.repository_fixture()
        linked = self.root / 'linked'; git('worktree', 'add', '--detach', str(linked), 'HEAD')
        gitdir = Path((linked / '.git').read_text().strip().removeprefix('gitdir: '))
        targets = ((repo, repo / '.git'), (repo, repo / '.git/config'),
                   (linked, linked / '.git'), (linked, gitdir / 'gitdir'),
                   (linked, gitdir / 'commondir'), (linked, repo / '.git/config'))
        original_stat = os.stat
        for workspace, target in targets:
            with self.subTest(workspace=workspace.name, target=target.name):
                parent = target.parent.stat(); retained = self.root / 'absent-metadata'; hidden = False
                def transient(path, *args, **kwargs):
                    nonlocal hidden
                    fd = kwargs.get('dir_fd')
                    if not hidden and path == target.name and fd is not None:
                        info = os.fstat(fd)
                        if (info.st_dev, info.st_ino) == (parent.st_dev, parent.st_ino):
                            hidden = True; target.rename(retained)
                            try: return original_stat(path, *args, **kwargs)
                            finally: retained.rename(target)
                    return original_stat(path, *args, **kwargs)
                with patch.object(os, 'stat', side_effect=transient):
                    with self.assertRaisesRegex(ValueError, 'Input directory'):
                        evidence.workspace_repository(workspace)
                self.assertTrue(hidden)
                self.assertEqual(evidence.workspace_repository(workspace), 'thetechgy/agent-engineering-baseline')

    def test_absent_origin_metadata_revalidated_before_publication(self):
        repo, git = self.repository_fixture()
        native = self.native(); static = self.root / 'static'; shutil.copytree(FIXTURES / 'static-synthetic', static)
        report_path = next((static / 'reports/podman').glob('*.json')); report = evidence.read_json(report_path)
        report['evaluated_source'] = {'repository': 'thetechgy/agent-engineering-baseline', 'commit': git('rev-parse', 'HEAD')}
        write(report_path, report)
        resolver = evidence.workspace_repository
        for kind, target in itertools.product(('inventory', 'behavioral', 'static'), (repo / '.git', repo / '.git/config')):
            with self.subTest(kind=kind, target=target.name):
                retained = self.root / 'absent-metadata'; restored = False
                target.rename(retained)
                try:
                    budget = evidence.ReadBudget()
                    self.assertIsNone(resolver(repo, budget=budget))
                    budget.verify_repository()  # Stable absence is valid unknown attribution.
                    def restore(path, **kwargs):
                        nonlocal restored
                        value = resolver(path, **kwargs)
                        retained.rename(target); restored = True
                        return value
                    name = 'inventory' if kind == 'inventory' else 'normalize_' + kind
                    operation = getattr(evidence, name)
                    invoke = (lambda: operation(repo)) if kind == 'inventory' else (lambda *a: operation(*a, workspace=repo))
                    args = ['inventory'] if kind == 'inventory' else ['normalize', '--kind', kind, '--skill', 'podman',
                                                                   '--input', str(native if kind == 'behavioral' else static)]
                    output = self.root / 'absence-rejected'
                    with patch.object(evidence, 'workspace_repository', side_effect=restore), \
                            patch.object(evidence, name, side_effect=invoke), patch.object(evidence, 'write_outputs') as publish:
                        with self.assertRaisesRegex(ValueError, 'Input directory'):
                            evidence.main([*args, '--output', str(output)])
                        publish.assert_not_called()
                    self.assertTrue(restored); self.assertFalse(output.exists())
                finally:
                    if not restored: retained.rename(target)

    def test_alternate_object_stores_rejected_across_git_readers(self):
        repo, git = self.repository_fixture()
        donor = self.root / 'donor'; shutil.copytree(repo, donor)
        member = donor / '.apm/skills/podman/SKILL.md'
        member.write_text(member.read_text() + '\nUnrelated donor source\n')
        def donor_git(*args):
            return subprocess.run(['git', '-C', str(donor), *args], check=True,
                                  capture_output=True, text=True).stdout.strip()
        donor_git('add', '.apm')
        donor_git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                  'commit', '-qm', 'Unrelated source')
        rev = donor_git('rev-parse', 'HEAD')
        linked = self.root / 'linked'; git('worktree', 'add', '--detach', str(linked), 'HEAD')
        native = self.native(); static = self.root / 'static'; shutil.copytree(FIXTURES / 'static-synthetic', static)
        report_path = next((static / 'reports/podman').glob('*.json')); report = evidence.read_json(report_path)
        report['evaluated_source'] = {'repository': 'thetechgy/agent-engineering-baseline', 'commit': rev}
        write(report_path, report)
        alternate = repo / '.git/objects/info/alternates'
        alternate.write_text(str(donor / '.git/objects') + '\n')
        before = self.snapshot(repo)
        for workspace in (repo, linked):
            for kind in ('content', 'dataset', 'revision', 'inventory'):
                with self.subTest(workspace=workspace.name, kind=kind):
                    with self.assertRaisesRegex(ValueError, 'Alternate Git object store'):
                        if kind == 'content': evidence.historical_content(workspace, rev, '.apm/skills/podman')
                        elif kind == 'dataset': evidence.historical_blob(workspace, rev + ':.apm/skills/podman/evals/evals.json')
                        elif kind == 'revision': evidence.git_revision(workspace)
                        else: evidence.inventory(workspace)
            for kind, root in (('behavioral', native), ('static', static)):
                with self.subTest(workspace=workspace.name, kind=kind):
                    operation = getattr(evidence, 'normalize_' + kind); output = self.root / 'alternate-rejected'
                    with patch.object(evidence, 'normalize_' + kind,
                                      side_effect=lambda *args, fn=operation: fn(*args, workspace=workspace)), \
                            patch.object(evidence, 'write_outputs') as publish:
                        with self.assertRaisesRegex(ValueError, 'Alternate Git object store'):
                            evidence.main(['normalize', '--kind', kind, '--skill', 'podman', '--input', str(root), '--output', str(output)])
                        publish.assert_not_called(); self.assertFalse(output.exists())
        self.assertEqual(self.snapshot(repo), before)
        alternate.unlink()
        self.assertIsNone(evidence.historical_content(repo, rev, '.apm/skills/podman')['digest'])

    def test_transient_alternates_and_object_directory_swaps_rejected(self):
        repo, git = self.repository_fixture(); rev = git('rev-parse', 'HEAD')
        linked = self.root / 'linked'; git('worktree', 'add', '--detach', str(linked), 'HEAD')
        original = subprocess.run
        for workspace in (repo, linked):
            for kind in ('alternate', 'missing-info', 'objects-swap'):
                with self.subTest(workspace=workspace.name, kind=kind):
                    info = repo / '.git/objects/info'
                    if kind == 'missing-info': info.rmdir()
                    changed = False
                    def transient(command, *args, **kwargs):
                        nonlocal changed
                        if not changed and 'cat-file' in command:
                            changed = True
                            if kind == 'objects-swap':
                                objects = info.parent; saved = repo / '.git/saved-objects'
                                objects.rename(saved); shutil.copytree(saved, objects)
                                try: return original(command, *args, **kwargs)
                                finally: shutil.rmtree(objects); saved.rename(objects)
                            info.mkdir(exist_ok=True)
                            alternate = info / 'alternates'; alternate.write_text(str(info.parent) + '\n')
                            try: return original(command, *args, **kwargs)
                            finally:
                                alternate.unlink()
                                if kind == 'missing-info': info.rmdir()
                        return original(command, *args, **kwargs)
                    try:
                        with patch.object(subprocess, 'run', side_effect=transient):
                            with self.assertRaisesRegex(ValueError, 'Input directory'):
                                evidence.historical_content(workspace, rev, '.apm/skills/podman')
                        self.assertTrue(changed)
                    finally: info.mkdir(exist_ok=True)
        budget = evidence.ReadBudget(); evidence.workspace_repository(repo, budget=budget)
        alternate = repo / '.git/objects/info/alternates'
        alternate.write_text(str(repo / '.git/objects') + '\n'); alternate.unlink()
        with self.assertRaisesRegex(ValueError, 'Input directory'): budget.verify_repository()

    def test_entire_git_object_store_rejects_links(self):
        repo, git = self.repository_fixture(); donor = self.root / 'donor'; shutil.copytree(repo, donor)
        member = donor / '.apm/skills/podman/SKILL.md'; member.write_text(member.read_text() + '\nDonor-only content\n')
        def donor_git(*args):
            return subprocess.run(['git', '-C', str(donor), *args], check=True,
                                  capture_output=True, text=True).stdout.strip()
        donor_git('add', '.apm')
        donor_git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Donor-only revision')
        rev = donor_git('rev-parse', 'HEAD'); oid = donor_git('rev-parse', 'HEAD:.apm/skills/podman/SKILL.md')
        donor_git('repack', '-a')
        linked = self.root / 'linked'; git('worktree', 'add', '--detach', str(linked), 'HEAD')
        native = self.native(); static = self.root / 'static'; shutil.copytree(FIXTURES / 'static-synthetic', static)
        report_path = next((static / 'reports/podman').glob('*.json')); report = evidence.read_json(report_path)
        report['evaluated_source'] = {'repository': 'thetechgy/agent-engineering-baseline', 'commit': rev}
        write(report_path, report)
        for kind in ('pack', 'fanout', 'blob-link', 'blob-hardlink'):
            objects = repo / '.git/objects'; target = objects / ('pack' if kind == 'pack' else oid[:2])
            retained = self.root / 'retained-object-directory'
            existed = target.exists()
            if existed: target.rename(retained)
            if kind in ('pack', 'fanout'):
                target.symlink_to(donor / '.git/objects' / target.name, target_is_directory=True)
            else:
                target.mkdir(); path = target / oid[2:]; source = donor / '.git/objects' / oid[:2] / oid[2:]
                if kind == 'blob-link': path.symlink_to(source)
                else: os.link(source, path)
            try:
                for workspace in (repo, linked):
                    with self.subTest(kind=kind, workspace=workspace.name):
                        with self.assertRaises(ValueError):
                            if kind == 'pack': evidence.historical_content(workspace, rev, '.apm/skills/podman')
                            else: evidence.historical_blob(workspace, oid)
                        with self.assertRaises(ValueError): evidence.inventory(workspace)
                        if kind == 'pack':
                            for mode, root in (('behavioral', native), ('static', static)):
                                operation = getattr(evidence, 'normalize_' + mode); output = self.root / 'linked-store-rejected'
                                before = self.snapshot(root)
                                with patch.object(evidence, 'normalize_' + mode,
                                                  side_effect=lambda *args, fn=operation: fn(*args, workspace=workspace)), \
                                        patch.object(evidence, 'write_outputs') as publish:
                                    with self.assertRaises(ValueError):
                                        evidence.main(['normalize', '--kind', mode, '--skill', 'podman', '--input', str(root), '--output', str(output)])
                                    publish.assert_not_called(); self.assertFalse(output.exists())
                                self.assertEqual(self.snapshot(root), before)
            finally:
                if target.is_symlink(): target.unlink()
                else: shutil.rmtree(target)
                if existed: retained.rename(target)
        self.assertIsNone(evidence.historical_content(repo, rev, '.apm/skills/podman')['digest'])

    def test_git_object_members_revalidated_and_tree_bounded(self):
        repo, git = self.repository_fixture(); rev = git('rev-parse', 'HEAD')
        oid = git('rev-parse', 'HEAD:.apm/skills/podman/SKILL.md')
        path = repo / '.git/objects' / oid[:2] / oid[2:]; path.chmod(0o600)
        raw = path.read_bytes(); metadata = path.stat(); original = subprocess.run; changed = False
        def transient(command, *args, **kwargs):
            nonlocal changed
            if not changed and 'cat-file' in command:
                changed = True; path.write_bytes(raw + b'transient')
                try: return original(command, *args, **kwargs)
                finally:
                    path.write_bytes(raw); os.utime(path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
            return original(command, *args, **kwargs)
        with patch.object(subprocess, 'run', side_effect=transient):
            with self.assertRaisesRegex(ValueError, 'Input member'):
                evidence.historical_content(repo, rev, '.apm/skills/podman')
        self.assertTrue(changed); self.assertEqual(path.read_bytes(), raw)
        with patch.object(evidence, 'MAX_INPUT_ENTRIES', 1), patch.object(evidence, 'run_offline_git') as native:
            with self.assertRaisesRegex(ValueError, 'Input tree entry limit'): evidence.inventory(repo)
            native.assert_not_called()

    def test_historical_retrieval_bounds_object_store_revalidation_work(self):
        repo, git = self.repository_fixture()
        for index in range(20): (repo / '.apm/skills/podman' / f'member-{index}.md').write_text(str(index))
        git('add', '.apm'); git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Many source members')
        objects = repo / '.git/objects'; count = len([p for p in objects.rglob('*') if p.is_file()])
        verify = evidence.verify_file_states; visits = 0
        def counted(states, *args, **kwargs):
            nonlocal visits
            visits += sum(path.is_relative_to(objects) for path in states)
            return verify(states, *args, **kwargs)
        with patch.object(evidence, 'verify_file_states', side_effect=counted):
            contents = evidence.historical_content(repo, git('rev-parse', 'HEAD'), '.apm/skills/podman')
        self.assertEqual(len(contents['manifest']), 21)
        self.assertLessEqual(visits, 10 * count)

    def test_inventory_bounds_object_store_revalidation_across_skills(self):
        repo, git = self.repository_fixture()
        for index in range(20): self.local(repo, f'skill-{index}')
        git('add', '.apm'); git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Many skills')
        rev = git('rev-parse', 'HEAD'); before = self.snapshot(repo)
        objects = repo / '.git/objects'; count = len([p for p in objects.rglob('*') if p.is_file()])
        verify = evidence.verify_file_states; visits = 0
        def counted(states, *args, **kwargs):
            nonlocal visits
            visits += sum(path.is_relative_to(objects) for path in states)
            return verify(states, *args, **kwargs)
        operation = evidence.inventory; output = self.root / 'many-skills-output'
        with patch.object(evidence, 'verify_file_states', side_effect=counted), \
                patch.object(evidence, 'inventory', side_effect=lambda: operation(repo)), redirect_stdout(StringIO()):
            evidence.main(['inventory', '--output', str(output)])
        value = evidence.read_json(output / 'inventory.json')
        self.assertEqual(len(value['skills']), 22)
        self.assertTrue(all(row['source']['revision'] == rev for row in value['skills']))
        self.assertEqual(self.snapshot(repo), before)
        self.assertLessEqual(visits, 16 * count)

    def test_inventory_batch_rejects_transient_object_changes_before_publication(self):
        repo, git = self.repository_fixture()
        oid = git('rev-parse', 'HEAD:.apm/skills/podman/SKILL.md')
        path = repo / '.git/objects' / oid[:2] / oid[2:]; path.chmod(0o600)
        raw = path.read_bytes(); metadata = path.stat(); before = self.snapshot(repo)
        original = evidence.historical_content; calls = 0
        def transient(*args, **kwargs):
            nonlocal calls
            value = original(*args, **kwargs); calls += 1
            if calls == 1:
                path.write_bytes(raw + b'transient'); path.write_bytes(raw)
                os.utime(path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
            return value
        operation = evidence.inventory; output = self.root / 'batch-rejected'
        with patch.object(evidence, 'historical_content', side_effect=transient), \
                patch.object(evidence, 'inventory', side_effect=lambda: operation(repo)), \
                patch.object(evidence, 'write_outputs') as publish:
            with self.assertRaisesRegex(ValueError, 'Input member changed'):
                evidence.main(['inventory', '--output', str(output)])
            publish.assert_not_called()
        self.assertGreaterEqual(calls, 1); self.assertFalse(output.exists())
        self.assertEqual(self.snapshot(repo), before)

    def test_historical_blob_growth_is_bounded_during_capture(self):
        import zlib
        repo, git = self.repository_fixture()
        oid = git('rev-parse', 'HEAD:.apm/skills/podman/SKILL.md')
        member = repo / '.git/objects' / oid[:2] / oid[2:]; original_bytes = member.read_bytes()
        member.chmod(0o600)
        budget = evidence.ReadBudget(); evidence.workspace_repository(repo, budget=budget)
        popen = subprocess.Popen; captured = []; changed = False
        def counted(command, *args, **kwargs):
            nonlocal changed
            if 'blob' in command:
                changed = True; payload = b'x' * 512
                member.write_bytes(zlib.compress(b'blob 512\0' + payload))
            process = popen(command, *args, **kwargs)
            if 'blob' in command:
                communicate = process.communicate; stream = process.stdout
                def communicated(*args, **kwargs):
                    result = communicate(*args, **kwargs); captured.append(len(result[0])); return result
                process.communicate = communicated
                class CountingPipe:
                    def read(self, size):
                        raw = stream.read(size); captured.append(len(raw)); return raw
                    def __getattr__(self, name): return getattr(stream, name)
                process.stdout = CountingPipe()
            return process
        try:
            with patch.object(evidence, 'JSON_LIMIT', 128), \
                    patch.object(subprocess, 'Popen', side_effect=counted):
                with self.assertRaises(ValueError): evidence.historical_blob(repo, oid, budget=budget)
            self.assertTrue(changed); self.assertTrue(captured)
            self.assertLessEqual(sum(captured), 129)
        finally: member.write_bytes(original_bytes)

    def test_historical_generated_markers_reject_before_blob_reads(self):
        from skillevaluator.tier3 import output_provenance
        marker = output_provenance.GENERATED_OUTPUT_MARKER
        for member in (marker, 'nested/' + marker + '/payload.json', 'results/' + marker, 'evals/' + marker):
            with self.subTest(member=member), tempfile.TemporaryDirectory() as temp, patch.object(self, 'root', Path(temp)):
                repo, git = self.repository_fixture()
                path = repo / '.apm/skills/podman' / member; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('{}'); git('add', '.apm')
                git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Generated marker fixture')
                rev = git('rev-parse', 'HEAD'); native = self.native()
                self.mutate(native, '/run_config.json', lambda d: d['evaluated_source'].update(commit=rev))
                self.mutate(native, '/result.json', lambda d: d['run_config']['evaluated_source'].update(commit=rev))
                self.mutate(native, '/provenance.json', lambda d: d.update(revision=rev))
                static = self.root / 'static'; shutil.copytree(FIXTURES / 'static-synthetic', static)
                static_path = next((static / 'reports/podman').glob('*.json')); report = evidence.read_json(static_path)
                report['evaluated_source'] = {'repository': 'thetechgy/agent-engineering-baseline', 'commit': rev}
                write(static_path, report)
                before = self.snapshot(repo)
                with patch.object(evidence, 'historical_blob', wraps=evidence.historical_blob) as blobs, \
                        patch.object(output_provenance, '_load_existing_key') as key:
                    with self.assertRaisesRegex(ValueError, 'Generated output'):
                        evidence.historical_content(repo, rev, '.apm/skills/podman')
                    for kind, root in (('behavioral', native), ('static', static)):
                        original = getattr(evidence, 'normalize_' + kind)
                        with patch.object(evidence, 'normalize_' + kind, side_effect=lambda *a, fn=original: fn(*a, workspace=repo)), \
                                patch.object(evidence, 'write_outputs') as publish:
                            with self.assertRaisesRegex(ValueError, 'Generated output'):
                                evidence.main(['normalize', '--kind', kind, '--skill', 'podman', '--input', str(root)])
                            publish.assert_not_called()
                    blobs.assert_not_called(); key.assert_not_called()
                self.assertEqual(self.snapshot(repo), before)


class RenderedOutputTests(unittest.TestCase):
    """The analysis writer extension preserves JSON callers and publication isolation."""

    def test_rendered_bytes_and_multiple_input_boundaries(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp); workspace = parent / 'checkout'; workspace.mkdir()
            roots = (parent / 'first', parent / 'second')
            for root in roots: root.mkdir()
            for root in roots:
                with self.assertRaisesRegex(ValueError, 'Output overlaps input'):
                    evidence.write_outputs({}, root / 'out', workspace, input_paths=roots,
                                           rendered={'summary.md': b'# Fixed summary\n'})
                with patch.dict(os.environ, {'TMPDIR': str(root)}), self.assertRaisesRegex(ValueError, 'Output overlaps input'):
                    evidence.write_outputs({}, workspace=workspace, input_paths=roots)
            output = parent / 'out'; calls = []
            evidence.write_outputs({'analysis.json': {'schema_version': 1}}, output, workspace,
                                   input_paths=roots, input_guards=(lambda: calls.append('checked'),),
                                   rendered={'summary.md': b'# Fixed summary\n'})
            self.assertEqual(calls, ['checked', 'checked'])
            self.assertEqual((output / 'analysis.json').read_bytes(), evidence.encoded({'schema_version': 1}))
            self.assertEqual((output / 'summary.md').read_bytes(), b'# Fixed summary\n')
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)
            self.assertTrue(all(member.stat().st_mode & 0o777 == 0o600 for member in output.iterdir()))

    def test_invalid_rendered_members_reject_before_reservation(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'out'
            for values, rendered in (({}, {'summary.md': 'not bytes'}),
                                     ({'same.json': {}}, {'same.json': b'overlap'}),
                                     ({}, {'nested/summary.md': b'unsafe'})):
                with self.assertRaises(ValueError):
                    evidence.write_outputs(values, output, rendered=rendered)
                self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
