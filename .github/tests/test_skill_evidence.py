"""Offline inventory, pinned native ingestion, and public-boundary regressions."""

import copy
from datetime import datetime, timezone
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
                        patch.object(evidence, 'git_revision') as revision:
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
                                patch.object(evidence, 'git_revision') as revision:
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

    def test_inventory_dataset_uses_one_validated_buffer(self):
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
                        suite = evidence.inventory(root)['skills'][0]['suite']
                        self.assertEqual(suite['case_ids'], ['1'])
                        self.assertEqual(suite['authored_digest'], evidence.digest_bytes(captured))
                    else:
                        with self.assertRaises(ValueError):
                            evidence.inventory(root)
                self.assertEqual(reads, [captured])

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
        static_report['evaluated_source'] = {'repository': 'example/fixture', 'commit': rev}
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
                git('init', '-q'); git('add', '.apm')
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
            git(repo, 'init', '-q'); git(repo, 'add', '.apm')
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
        git('init', '-q'); git('add', '.apm')
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
                git('init', '-q'); git('add', '.apm')
                git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                    'commit', '-qm', 'Historical root fixture')
                rev = git('rev-parse', 'HEAD')
                self.mutate(behavioral, '/run_config.json', lambda d: d['evaluated_source'].update(commit=rev))
                self.mutate(behavioral, '/result.json', lambda d: d['run_config']['evaluated_source'].update(commit=rev))
                self.mutate(behavioral, '/provenance.json', lambda d: d.update(revision=rev))
                static_report['evaluated_source'] = {'repository': 'example/fixture', 'commit': rev}
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
        git('init', '-q'); git('add', '.apm')
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
                report['evaluated_source'] = {'repository': 'example/fixture', 'commit': rev}; write(static_path, report)
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
                git('init', '-q'); git('add', '.apm')
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
        base['availability'].update(status='incomplete', reasons=['coverage_missing'])
        base['policy']['attempts']['maximum'] = None
        base['policy']['id'] = evidence.identity({k: base['policy'][k] for k in
                                                ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
        for public in (False, True):
            data = evidence.project(base) if public else copy.deepcopy(base)
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
        data['availability'].update(status='incomplete', reasons=['reference_expired'])
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

    def test_unscored_native_trial_keeps_identity(self):
        root = self.native(); run = next((root/'results/podman').iterdir())
        path = next((run/'codex/with-skill/trials').glob('*/result.json'))
        record = evidence.read_json(path); trial = record['trial_name']
        reward = evidence.read_json(path.parent/'reward.json'); case = reward['entry_id']
        record['verifier_result'] = None; record['exception_info'] = {'diagnostic': 'discarded'}
        write(path, record); (path.parent/'reward.json').unlink()
        summary_path = run/'codex/with-skill/summary.json'; summary = evidence.read_json(summary_path)
        prior = summary['pass_at_k']['cases'][case]['attempts'][0]
        prior.update(score=None, passed=None)
        summary['scored_attempts'] = 9; summary['execution_status'] = 'incomplete'
        summary['pass_at_k']['passed_cases'] -= 1
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
            summary['pass_at_k']['k'] = 3
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
        data = self.data()
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
        evidence.project(data)

    def test_shared_stop_on_pass_policy_consistency(self):
        for field, attempt in itertools.product((None, False, True), repeat=2):
            with self.subTest(field=field, attempt=attempt):
                data = self.data()
                data['policy']['fields']['stop_on_pass'] = field
                data['policy']['attempts']['stop_on_pass'] = attempt
                data['policy']['id'] = evidence.identity({k: data['policy'][k] for k in
                    ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
                if field is None or attempt is None or field == attempt:
                    evidence.project(data)
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

    def test_missing_historical_metadata(self):
        root = self.native(); (root/'provenance.json').unlink(); (root/'versions.json').unlink()
        data = evidence.normalize_behavioral(root, 'podman')
        self.assertEqual(len(data['observations']), 20)
        self.assertIn('metadata_missing', data['availability']['reasons'])
        self.assertIsNone(data['policy']['fields']['evaluator_revision'])

    def test_failed_gate_preserved(self):
        data = self.data(); obs = data['observations'][0]
        obs['deterministic_gate'] = 0
        obs['deterministic_scores'] = {k:0 if k in ('authorization','gate') else 1 for k in evidence.GATE_FIELDS}
        self.assertEqual(evidence.project(data)['observations'][0]['score'], obs['score'])
        self.assertEqual(evidence.project(data)['observations'][0]['deterministic_gate'], 0)

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
        base['source']['content'] = evidence.content([
            {'member': 'SKILL.md', 'digest': evidence.digest_bytes(b'Synthetic')}], 'configured')
        base['availability'].update(status='complete', reasons=[])
        base['findings'] = []
        for scan in base['scans']:
            scan.update(status='passed', passed=True, severity_counts=dict.fromkeys(scan['severity_counts'], 0))
        evidence.project(base)
        for index in range(len(base['scans'])):
            with self.subTest(scan=index):
                data = copy.deepcopy(base); data['scans'][index]['references'] = []
                self.assert_project_rejects(data, 'Complete scan missing reference')
                data['availability'].update(status='incomplete', reasons=['reference_unavailable'])
                evidence.project(data)

    def test_static_projection_retains_known_scan_limitations(self):
        for status in ('incomplete', 'skipped'):
            with self.subTest(status=status):
                data = evidence.normalize_static(FIXTURES / 'static-synthetic', 'podman')
                for scan in data['scans']: scan.update(status='passed', passed=True)
                data['scans'][1].update(status=status, passed=None)
                data['availability']['reasons'].remove('scan_incomplete')
                self.assert_project_rejects(data, 'Missing scan limitation')
                data['availability']['reasons'].append('scan_incomplete')
                self.assertIn('scan_incomplete', evidence.project(data)['availability']['reasons'])

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
                if scanner_count != 0 and aggregate_count != 0:
                    evidence.project(data); evidence.validate_public(data)
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
        evidence.project(totals)  # Unknown counts do not invent a sum equality.

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
        git('init', '-q'); git('add', '.apm')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Static source fixture')
        rev = git('rev-parse', 'HEAD')
        for declared, complete in ((None, False), ({'repository': 'example/fixture', 'commit': 'f'*40}, False),
                                   ({'repository': 'example/fixture', 'commit': rev}, True)):
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
        read = evidence.read_bytes
        baseline = evidence.normalize_behavioral(root, 'podman')
        for target in members:
            with self.subTest(member=target.relative_to(root)):
                original = target.read_bytes(); calls = []
                def replace_after_read(path):
                    raw = read(path); calls.append(path)
                    if path == target:
                        value = json.loads(raw); value['replaced_after_read'] = True; write(path, value)
                    return raw
                try:
                    with patch.object(evidence, 'read_bytes', side_effect=replace_after_read):
                        data = evidence.normalize_behavioral(root, 'podman')
                    self.assertEqual(evidence.encoded(data), evidence.encoded(baseline))
                    self.assertEqual(calls.count(target), 1)
                    refs = [r for r in data['references'] if r['member'] == target.relative_to(root).as_posix()]
                    self.assertTrue(refs)
                    self.assertTrue(all(r['digest'] == evidence.digest_bytes(original) for r in refs))
                    evidence.project(data)
                finally:
                    target.write_bytes(original)

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
        for index in range(2500):
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
            self.assertEqual(result.returncode, 0, result.stderr)
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

    def snapshot(self, root):
        return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
                for p in root.rglob('*')}

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


if __name__ == '__main__':
    unittest.main()
