"""Exercise Pages entry points over retained public/native fixtures and disposable Git remotes.

Synthetic API responses test admission only; they do not establish hosted execution.
The oracle fixture is a hash-pinned public projection of an actual no-inference run.
"""
import copy
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile

import yaml

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import skill_analysis as analysis
import skill_evidence as evidence
import skill_pages as pages
import skill_report as report
import test_skill_analysis as fixtures
from test_skill_report import Document

ROOT = evidence.ROOT
PINNED = ROOT / '.github/tests/fixtures/skill_pages'


def bundle(root, records=(), extra=()):
    configs = {record['source']['skill_id']: fixtures.configuration(record['source']['skill_id'],
               record.get('dataset', {}).get('case_ids', ('1',)), record['source']) for record in records}
    configs.update({name: fixtures.configuration(name) for name in extra})
    inv = {'schema_version': 1, 'kind': 'inventory', 'skills': [configs[name] for name in sorted(configs)]}
    pages.write(root, 'inventory/inventory.json', evidence.encoded(inv))
    for record in records:
        tail = 'static' if record['kind'] == 'static' else 'behavioral/' + record['run_id']
        pages.write(root, f'skills/{record["source"]["skill_id"]}/{tail}/public-report.json', evidence.encoded(record))
    return root


def archive(root):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as output:
        for member, raw in pages.tree(root).items():
            output.writestr(member, raw)
    return stream.getvalue()


def prov(revision, run_id=20, attempt=1, *, kind='validate'):
    return {'repository': pages.REPOSITORY, 'workflow_id': 100 if kind == 'validate' else 200,
            'workflow_path': pages.WORKFLOWS[kind], 'event': 'push' if kind == 'validate' else 'workflow_dispatch',
            'revision': revision, 'run_id': run_id, 'attempt': attempt, 'artifact_id': run_id + 100,
            'archive_digest': 'sha256:' + 'b' * 64}


def ledger_data(record):
    policy = pages.published_policy(record)
    member = f'{record["source"]["skill_id"]}/{policy}/data.js'
    extra = f'Dataset {record["dataset"]["staged_digest"]}; policy {policy}'
    revision = record['source']['revision']
    data = {'lastUpdate': 100, 'repoUrl': f'https://github.com/{pages.REPOSITORY}',
            'entries': {'Agent skill benchmark (standard)': [{
                'commit': {'id': revision, 'url': f'https://github.com/{pages.REPOSITORY}/commit/{revision}',
                           'message': 'Public historical control; no run/attempt provenance'},
                'date': 100, 'tool': 'customBiggerIsBetter',
                'benches': [{**metric, 'extra': extra} for metric in record['metrics']]}]}}
    return member, b'window.BENCHMARK_DATA = ' + pages.encoded(data)


class FixtureAPI:
    def __init__(self, revision, parent, source):
        self.revision = revision; self.parent = parent; self.source = source
        self.run = {'id': 20, 'run_attempt': 1, 'workflow_id': 100, 'path': pages.WORKFLOWS['validate'],
                    'head_sha': revision, 'head_branch': 'main', 'event': 'push', 'status': 'completed', 'conclusion': 'success',
                    'repository': {'full_name': pages.REPOSITORY}, 'head_repository': {'full_name': pages.REPOSITORY, 'id': 1}}
        names = ['Enforce native collection and dataset contracts', 'Generate validated public quality evidence and findings summary',
                 'Verify evaluator left the checkout unchanged', 'Upload validated public quality evidence']
        self.jobs = [self.job('Skill quality (advisory findings)', names)]
        raw = archive(source)
        self.raw_bytes = raw
        self.artifacts = [{'id': 120, 'name': 'skill-public-quality-20-1', 'digest': 'sha256:' + pages.digest(raw), 'expired': False,
                           'workflow_run': {'id': 20, 'head_sha': revision, 'head_repository_id': 1}}]

    def job(self, name, steps):
        return {'name': name, 'run_id': 20, 'run_attempt': 1, 'head_sha': self.revision, 'conclusion': 'success',
                'steps': [{'name': name, 'conclusion': 'success'} for name in steps]}

    def get(self, path):
        if path == '': return {'full_name': pages.REPOSITORY, 'default_branch': 'main'}
        if path == 'git/ref/heads/main': return {'object': {'sha': self.revision}}
        if path == 'git/ref/heads/gh-pages': return {'object': {'sha': self.parent}}
        if '/attempts/' in path: return self.run
        if path.startswith('actions/workflows/'): return {'id': self.run['workflow_id'], 'path': self.run['path']}
        raise AssertionError(path)

    def listing(self, path, key):
        return self.jobs if key == 'jobs' else self.artifacts

    def raw(self, path):
        return self.raw_bytes


class PagesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.historical = evidence.project(evidence.normalize_behavioral(fixtures.FIXTURES / 'podman-native', 'podman'))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pages-test-'); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.site = self.root / 'site'; self.site.mkdir()
        self.revision = pages.git(ROOT, 'rev-parse', 'HEAD')
        self.state = {'schema_version': 1, 'current': None, 'slots': {}}
        bundle(self.site / 'report/current', extra=('podman', 'gh', 'unevaluated'))
        self.state['current'] = {'revision': self.revision,
            'digest': pages.digest((self.site / 'report/current/inventory/inventory.json').read_bytes())}
        self.save()
        self.member, self.raw_ledger = ledger_data(self.historical)
        pages.write(self.site, self.member, self.raw_ledger)

    def save(self):
        pages.write(self.site, 'report/publication.json', pages.encoded(self.state))

    def quality(self, name='alpha', revision=None):
        value = fixtures.static_control(name)
        value['source'].update(repository=pages.REPOSITORY, revision=revision or self.revision)
        return value

    def admit(self, slot, records, provenance=None, suffix=''):
        source = bundle(self.root / ('input-' + slot + suffix), records)
        value = provenance or prov(self.revision)
        changed = pages.admit(self.site, self.state, slot, value, source, ROOT)
        self.save()
        return changed

    def test_build_determinism_ledger_only_and_compatibility_links(self):
        self.admit('quality', [self.quality()])
        rows = pages.build(self.site)
        self.assertEqual(rows[0]['detail'], 'ledger_only')
        first = pages.tree(self.site)
        pages.build(self.site)
        self.assertEqual(first, pages.tree(self.site))
        self.assertEqual((self.site / self.member).read_bytes(), self.raw_ledger)
        html = first['index.html'].decode()
        for text in ('PUBLIC · CANONICAL PAGES', 'Ledger only', '0.1207', 'unevaluated', 'Current main configuration', self.revision):
            self.assertIn(text, html)
        self.assertNotIn('Keep this file private', html)
        self.assertNotIn('cdn.jsdelivr', html)
        doc = Document(html)
        self.assertEqual(len(doc.ids), len(set(doc.ids)))
        for href in doc.links:
            if href.startswith('#'): self.assertIn(href[1:], doc.ids)
            else: self.assertTrue((self.site / href.split('#')[0]).is_file(), href)
        compatibility = (self.site / self.member.replace('data.js', 'index.html')).read_text()
        self.assertIn('../../index.html#' + report.anchor('history', 'podman', self.member.split('/')[1]), compatibility)
        self.assertNotIn('<script', compatibility)

    def test_standard_detail_matches_staged_dataset_and_native_policy(self):
        self.admit('standard--podman', [self.historical], prov(self.historical['source']['revision'], kind='benchmark'))
        self.assertEqual(pages.build(self.site)[0]['detail'], 'public_detail_available')
        self.assertIn('Supporting public detail', (self.site / 'index.html').read_text())
        # A later ledger-only measurement does not remove previous detailed evidence.
        value = pages.parse(self.raw_ledger.removeprefix(b'window.BENCHMARK_DATA = '))
        row = copy.deepcopy(value['entries']['Agent skill benchmark (standard)'][0])
        row['date'] += 1; row['commit']['id'] = self.revision
        row['commit']['url'] = f'https://github.com/{pages.REPOSITORY}/commit/{self.revision}'
        value['entries']['Agent skill benchmark (standard)'].append(row)
        pages.write(self.site, self.member, b'window.BENCHMARK_DATA = ' + pages.encoded(value))
        self.assertEqual([r['detail'] for r in pages.build(self.site)], ['public_detail_available', 'ledger_only'])
        self.assertIn('standard--podman', pages.load_state(self.site)['slots'])

    def test_conflicting_standard_values_block_and_preserve_generated_index(self):
        self.admit('standard--podman', [self.historical], prov(self.historical['source']['revision'], kind='benchmark'))
        pages.build(self.site)
        before = (self.site / 'index.html').read_bytes()
        data = pages.parse(self.raw_ledger.removeprefix(b'window.BENCHMARK_DATA = '))
        data['entries']['Agent skill benchmark (standard)'][0]['benches'][0]['value'] = 0.5
        pages.write(self.site, self.member, b'window.BENCHMARK_DATA = ' + pages.encoded(data))
        with self.assertRaisesRegex(ValueError, 'conflicts with ledger values'): pages.build(self.site)
        self.assertEqual(before, (self.site / 'index.html').read_bytes())

    def test_malformed_and_conflicting_ledgers_are_blocking(self):
        for raw in (self.raw_ledger + b'; alert(1)', b'window.BENCHMARK_DATA = {"entries":NaN}',
                    self.raw_ledger.replace(b'0.1207', b'true'), self.raw_ledger.replace(b'"Skill Lift"', b'"Wrong"')):
            with self.subTest(raw=raw[:30]):
                pages.write(self.site, self.member, raw)
                with self.assertRaises((ValueError, TypeError)): pages.ledger(self.site)

    def test_same_revision_ordering_duplicate_and_stale_slots(self):
        self.assertTrue(self.admit('quality', [self.quality()]))
        self.assertFalse(self.admit('quality', [self.quality()], suffix='duplicate'))
        old = copy.deepcopy(self.state['slots']['quality'])
        self.assertFalse(self.admit('quality', [self.quality()], prov(self.revision, 19), suffix='stale'))
        self.assertEqual(old, self.state['slots']['quality'])
        self.assertTrue(self.admit('quality', [self.quality()], prov(self.revision, attempt=2), suffix='attempt2'))
        with self.assertRaisesRegex(ValueError, 'Conflicting duplicate'):
            self.admit('quality', [self.quality('changed')], prov(self.revision, attempt=2), suffix='conflict')
        history = self.root / 'ancestry'; history.mkdir(); pages.git(history, 'init', '--quiet')
        pages.git(history, '-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '--quiet', '--allow-empty', '-m', 'Older')
        older = pages.git(history, 'rev-parse', 'HEAD')
        pages.git(history, '-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '--quiet', '--allow-empty', '-m', 'Newer')
        newer = pages.git(history, 'rev-parse', 'HEAD')
        self.assertTrue(pages.newer(history, prov(newer, 1), prov(older, 999)))
        self.assertFalse(pages.newer(history, prov(older, 999), prov(newer, 1)))

    def test_oracle_fixture_preserves_52_outcomes_and_no_standard_scores(self):
        origin = pages.parse((PINNED / 'oracle-origin.json').read_bytes())
        raw = (PINNED / 'oracle-public.json').read_bytes()
        self.assertEqual(pages.digest(raw), origin['sha256'])
        record = pages.parse(raw)
        self.assertEqual(len(record['observations']), 52)
        self.assertFalse(record['metrics'])
        self.admit('oracle--powershell-pester-6', [record], prov(origin['revision']))
        self.admit('quality', [self.quality()])
        rows = pages.build(self.site)
        self.assertEqual(len(rows), 1)
        saved = pages.parse((self.site / 'report/analysis.json').read_bytes())
        run = next(s for s in saved['skills'] if s['skill'] == 'powershell-pester-6')['behavioral_results'][0]
        self.assertEqual(run['custom']['purpose'], 'oracle_qualification')
        self.assertEqual({obs['custom']['outcome'] for obs in record['observations']}, {'passed', 'failed', 'invalid', 'unsupported', 'timeout', 'infrastructure_error'})
        self.assertEqual(run['custom']['outcomes'], analysis.analyze_custom(record)['outcomes'])
        html = (self.site / 'index.html').read_text()
        for text in ('Diagnostic oracle qualification', 'excluded from qualified performance history', 'not_applicable', 'Custom cross-run numeric comparisons'):
            self.assertIn(text, html)

    def test_retained_hashes_and_credential_exclusion(self):
        self.admit('quality', [self.quality()])
        member = next((self.site / 'report/bundles/quality/skills').rglob('public-report.json'))
        member.write_bytes(member.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'): pages.build(self.site)
        bad = self.quality(); bad['source']['repository'] = 'x/ghp_' + 'a' * 36
        with self.assertRaises(ValueError): self.admit('quality', [bad], suffix='credential')

    def test_archive_digest_layout_links_and_json(self):
        good = bundle(self.root / 'good', [self.quality()])
        raw = archive(good)
        self.assertTrue(pages.extract_public(raw, 'sha256:' + pages.digest(raw), self.root / 'unzip').records)
        with self.assertRaisesRegex(ValueError, 'digest'): pages.extract_public(raw, 'sha256:' + '0' * 64, self.root / 'digest')
        for name, mode, payload in (('../escape.json', 0, b'{}'), ('secrets.txt', 0, b'x'),
                                   ('inventory/inventory.json', stat.S_IFLNK | 0o777, b'x'),
                                   ('inventory/inventory.json', 0, b'{"kind":1,"kind":2}')):
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w') as out:
                item = zipfile.ZipInfo(name); item.external_attr = mode << 16
                out.writestr(item, payload)
                out.writestr('skills/alpha/static/public-report.json', b'{}')
            raw = stream.getvalue()
            with self.assertRaises((ValueError, KeyError)):
                pages.extract_public(raw, 'sha256:' + pages.digest(raw), self.root / 'invalid')
            if (self.root / 'invalid').exists(): shutil.rmtree(self.root / 'invalid')

    def test_archive_expansion_member_and_duplicate_limits(self):
        import warnings
        oversized = io.BytesIO()
        with zipfile.ZipFile(oversized, 'w', compression=zipfile.ZIP_DEFLATED) as out:
            out.writestr('inventory/inventory.json', b' ' * (8 * 1024 * 1024 + 1))
        many = io.BytesIO()
        with zipfile.ZipFile(many, 'w') as out:
            for index in range(513): out.writestr(f'skills/a{index}/static/public-report.json', b'{}')
        duplicate = io.BytesIO()
        with warnings.catch_warnings(), zipfile.ZipFile(duplicate, 'w') as out:
            warnings.simplefilter('ignore', UserWarning)
            out.writestr('inventory/inventory.json', b'{}'); out.writestr('inventory/inventory.json', b'{}')
        for stream, message in ((oversized, 'Expanded archive limit'), (many, 'Archive member limit'), (duplicate, 'Duplicate archive members')):
            raw = stream.getvalue(); output = self.root / 'reject-before-write'
            with self.assertRaisesRegex(ValueError, message):
                pages.extract_public(raw, 'sha256:' + pages.digest(raw), output)
            self.assertFalse(output.exists())

    def test_recovery_payload_has_no_executable_selectors(self):
        self.assertIsNone(pages.request('repository_dispatch', {'action': pages.RECOVERY_EVENT}))
        self.assertEqual(pages.request('repository_dispatch', {'action': pages.RECOVERY_EVENT, 'client_payload': {'run_id': 5, 'attempt': 2}}), (5, 2))
        for payload in ({'ref': 'feature'}, {'repository': 'x/y'}, {'url': 'https://example.com'}, {'path': '/tmp/x'},
                        {'run_id': '5', 'attempt': 2}, {'run_id': True, 'attempt': 1}, {'run_id': 1}, {'attempt': 0, 'run_id': 1}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                pages.request('repository_dispatch', {'action': pages.RECOVERY_EVENT, 'client_payload': payload})
        with self.assertRaises(ValueError): pages.request('workflow_dispatch', {})

    def api(self):
        source = bundle(self.root / 'api-source', [self.quality()])
        return FixtureAPI(self.revision, 'f' * 40, source)

    def test_exact_api_admission_rejects_pr_feature_failure_foreign_and_step_failure(self):
        api = self.api()
        self.assertEqual(pages.authenticate(api, 20, 1, ROOT, self.revision)[0], 'validate')
        benchmark = copy.deepcopy(api)
        benchmark.run.update(workflow_id=200, path=pages.WORKFLOWS['benchmark'], event='workflow_dispatch')
        self.assertEqual(pages.authenticate(benchmark, 20, 1, ROOT, self.revision)[0], 'benchmark')
        for key, value in (('event', 'pull_request'), ('head_branch', 'feature'), ('conclusion', 'failure'),
                           ('status', 'in_progress'), ('run_attempt', 2), ('path', 'fake.yml'), ('workflow_id', 200)):
            with self.subTest(key=key):
                modified = copy.deepcopy(api); modified.run[key] = value
                if key == 'workflow_id':
                    original = modified.get
                    modified.get = lambda path: {'id': 100, 'path': pages.WORKFLOWS['validate']} if path.startswith('actions/workflows') else original(path)
                with self.assertRaises(ValueError): pages.authenticate(modified, 20, 1, ROOT, self.revision)
        modified = copy.deepcopy(api); modified.run['head_repository']['full_name'] = 'foreign/repo'
        with self.assertRaises(ValueError): pages.authenticate(modified, 20, 1, ROOT, self.revision)
        api.jobs[0]['steps'][0]['conclusion'] = 'skipped'
        with self.assertRaisesRegex(ValueError, 'step did not succeed'):
            pages.acquire(api, api.run, api.jobs, 'validate', self.site, self.state, ROOT, self.root / 'download')

    def test_standard_and_confirmation_handoffs_are_independent_of_quality(self):
        source = bundle(self.root / 'benchmark-source', [self.historical])
        api = FixtureAPI(self.historical['source']['revision'], 'f' * 40, source)
        api.run.update(workflow_id=200, path=pages.WORKFLOWS['benchmark'], event='workflow_dispatch')
        api.artifacts[0]['name'] = 'skill-public-benchmark-podman-standard-20-1'
        evaluation = ['Validate selection and clean checkout', 'Run native with-skill and without-skill evaluation',
            'Summarize native results and prepare standard metrics', 'Verify evaluator left the checkout unchanged',
            'Generate validated public benchmark evidence', 'Verify public reporting left the checkout unchanged',
            'Upload validated public benchmark evidence']
        history = ['Validate metric allowlist and canonical series', 'Append standard result to durable history',
                   'Capture and verify the exact published history commit']
        api.jobs = [api.job('evaluate', evaluation), api.job('publish-history', history)]
        pages.acquire(api, api.run, api.jobs, 'benchmark', self.site, self.state, ROOT, self.root / 'download-standard')
        self.save()
        self.assertEqual(pages.build(self.site)[0]['detail'], 'public_detail_available')
        retained = copy.deepcopy(self.state['slots'])
        api.artifacts = []  # Public detail was never uploaded; native ledger is still admitted.
        warning = pages.acquire(api, api.run, api.jobs, 'benchmark', self.site, self.state, ROOT, self.root / 'absent')
        self.assertTrue(warning)
        self.assertEqual(retained, self.state['slots'])
        api.jobs[1]['conclusion'] = 'failure'
        with self.assertRaises(ValueError):
            pages.acquire(api, api.run, api.jobs, 'benchmark', self.site, self.state, ROOT, self.root / 'failed')
        # Synthetic native custom confirmation contains failed/unscoreable outcomes.
        # Producer workflow success must not turn those outcomes into passes.
        import test_custom_metrics as custom
        native, _ = custom.synthetic_native(self.root / 'custom')
        record = evidence.project(evidence.normalize_behavioral(native, 'powershell-pester-6'))
        source = bundle(self.root / 'confirmation-source', [record])
        api = FixtureAPI(self.revision, 'f' * 40, source)
        api.run.update(workflow_id=200, path=pages.WORKFLOWS['benchmark'], event='workflow_dispatch')
        api.jobs = [api.job('evaluate', evaluation)]
        api.artifacts[0]['name'] = 'skill-public-benchmark-powershell-pester-6-confirmation-20-1'
        pages.acquire(api, api.run, api.jobs, 'benchmark', self.site, self.state, ROOT, self.root / 'download-confirmation')
        self.save()
        self.assertIn('standard--podman', self.state['slots'])
        self.assertIn('confirmation--powershell-pester-6', self.state['slots'])
        self.assertEqual(len(pages.build(self.site)), 1)
        self.assertIn('Diagnostic confirmation', (self.site / 'index.html').read_text())
        self.assertEqual({obs['custom']['outcome'] for obs in record['observations']}, set(evidence.CUSTOM_OUTCOMES))

    def test_missing_standard_detail_is_unavailable_but_supplied_invalid_detail_blocks(self):
        source = bundle(self.root / 'benchmark-expiring', [self.historical])
        api = FixtureAPI(self.historical['source']['revision'], 'f' * 40, source)
        api.run.update(workflow_id=200, path=pages.WORKFLOWS['benchmark'], event='workflow_dispatch')
        api.artifacts[0]['name'] = 'skill-public-benchmark-podman-standard-20-1'
        api.jobs = [api.job('evaluate', ['Validate selection and clean checkout',
            'Run native with-skill and without-skill evaluation', 'Summarize native results and prepare standard metrics',
            'Verify evaluator left the checkout unchanged', 'Generate validated public benchmark evidence',
            'Verify public reporting left the checkout unchanged', 'Upload validated public benchmark evidence']),
            api.job('publish-history', ['Validate metric allowlist and canonical series',
                'Append standard result to durable history', 'Capture and verify the exact published history commit'])]
        api.artifacts[0]['expired'] = True
        pages.acquire(api, api.run, api.jobs, 'benchmark', self.site, self.state, ROOT, self.root / 'expired')
        self.assertFalse(self.state['slots'])
        api.artifacts[0]['expired'] = False; api.raw_bytes = b'corrupted'
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            pages.acquire(api, api.run, api.jobs, 'benchmark', self.site, self.state, ROOT, self.root / 'corrupt')
        self.assertFalse(self.state['slots'])

    def test_production_prepare_and_offline_cli_rebuild(self):
        api = self.api()
        retained = self.root / 'retained'; retained.mkdir()
        shutil.copytree(self.site, retained / 'benchmarks')
        # Initial legacy state has no report manifest.
        shutil.rmtree(retained / 'benchmarks/report')
        pages.git(retained, 'init', '--quiet')
        pages.git(retained, 'add', '.')
        pages.git(retained, '-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '--quiet', '-m', 'Retained ledger')
        api.parent = pages.git(retained, 'rev-parse', 'HEAD')
        output = self.root / 'candidate'
        result = pages.prepare(ROOT, retained, output, 'workflow_run', {'workflow_run': {'id': 20, 'run_attempt': 1}}, api)
        self.assertIn('detailed evidence unavailable for 1', result[-1])
        seal = pages.verify_candidate(output)
        before = pages.tree(output / 'benchmarks')
        command = [sys.executable, '-B', str(ROOT / '.github/scripts/skill_pages.py'), 'build', '--site', str(output / 'benchmarks')]
        run = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(before, pages.tree(output / 'benchmarks'))
        self.assertEqual(seal, pages.verify_candidate(output))

    def test_pages_excludes_analyst_attachments(self):
        captured = analysis.capture_inputs([self.site / 'report/current'])
        value = analysis.build_analysis(captured)
        with self.assertRaisesRegex(ValueError, 'Analyst attachments'):
            report.render_report(value, captured, reviews=object(), pages_context={})

    def test_disposable_remote_fast_forward_conflict_tamper_and_ledger_preservation(self):
        pages.build(self.site)
        remote = self.root / 'remote.git'; remote.mkdir(); pages.git(remote, 'init', '--bare', '--quiet')
        seed = self.root / 'seed'; seed.mkdir(); pages.git(seed, 'init', '--quiet')
        pages.git(seed, 'checkout', '--quiet', '-b', 'gh-pages')
        shutil.copytree(self.site, seed / 'benchmarks')
        pages.write(seed, 'unrelated.txt', b'preserve')
        pages.git(seed, 'add', '.')
        pages.git(seed, '-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '--quiet', '-m', 'Seed')
        pages.git(seed, 'remote', 'add', 'origin', str(remote)); pages.git(seed, 'push', '--quiet', 'origin', 'gh-pages')
        candidate = self.root / 'candidate'; candidate.mkdir(); shutil.copytree(self.site, candidate / 'benchmarks')
        parent = pages.git(seed, 'rev-parse', 'HEAD'); pages.seal(candidate, parent)
        revision = pages.commit(candidate, self.root / 'write', str(remote))
        self.assertEqual(revision, parent)  # Exact duplicate is idempotent, no empty commit.
        self.assertEqual(pages.git(remote, 'show', f'{revision}:unrelated.txt'), 'preserve')
        self.admit('quality', [self.quality()]); pages.build(self.site)
        shutil.rmtree(candidate / 'benchmarks'); shutil.copytree(self.site, candidate / 'benchmarks'); pages.seal(candidate, parent)
        revision = pages.commit(candidate, self.root / 'write2', str(remote))
        self.assertNotEqual(revision, parent)
        self.assertEqual(pages.git(remote, 'rev-parse', f'{revision}^'), parent)
        self.assertEqual(pages.git(remote, 'show', f'{revision}:benchmarks/{self.member}'), self.raw_ledger.decode().strip())
        with self.assertRaisesRegex(ValueError, 'branch moved'): pages.commit(candidate, self.root / 'conflict', str(remote))
        pages.seal(candidate, revision)
        pages.write(candidate, 'benchmarks/index.html', b'tampered')
        with self.assertRaisesRegex(ValueError, 'hashes differ'): pages.commit(candidate, self.root / 'tamper', str(remote))
        pages.seal(candidate, revision)
        pages.write(candidate, 'benchmarks/' + self.member, b'changed ledger'); pages.seal(candidate, revision)
        with self.assertRaisesRegex(ValueError, 'changed native history'): pages.commit(candidate, self.root / 'history-change', str(remote))

    def test_deployment_entry_point_refuses_cached_commit_after_branch_movement(self):
        import shlex
        remote = self.root / 'deployment-remote.git'; remote.mkdir(); pages.git(remote, 'init', '--bare', '--quiet')
        checkout = self.root / 'deploy-checkout'; checkout.mkdir(); pages.git(checkout, 'init', '--quiet')
        pages.git(checkout, 'checkout', '--quiet', '-b', 'gh-pages')
        pages.write(checkout, 'benchmarks/index.html', b'<!doctype html><title>Fixture</title>')
        pages.git(checkout, 'add', '.')
        pages.git(checkout, '-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '--quiet', '-m', 'First')
        parent = pages.git(checkout, 'rev-parse', 'HEAD')
        pages.git(checkout, '-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '--quiet', '--allow-empty', '-m', 'Prepared')
        prepared = pages.git(checkout, 'rev-parse', 'HEAD')
        pages.git(checkout, 'remote', 'add', 'origin', str(remote)); pages.git(checkout, 'push', '--quiet', 'origin', 'gh-pages')
        bin_dir = self.root / 'api-bin'; bin_dir.mkdir()
        gh = bin_dir / 'gh'
        gh.write_text('#!/bin/sh\nexec git --git-dir=' + shlex.quote(str(remote)) + ' rev-parse refs/heads/gh-pages\n')
        gh.chmod(0o700)
        workflow = yaml.safe_load((ROOT / '.github/workflows/publish-skill-report.yml').read_text())
        check = next(step['run'] for step in workflow['jobs']['deploy']['steps'] if 'run' in step and 'remote_sha=' in step['run'])
        environment = {**os.environ, 'PATH': str(bin_dir) + os.pathsep + os.environ['PATH'],
                       'PUBLICATION_SHA': prepared, 'GITHUB_REPOSITORY': pages.REPOSITORY}
        current = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', check], cwd=checkout, env=environment, capture_output=True)
        self.assertEqual(current.returncode, 0, current.stderr)
        pages.git(remote, 'update-ref', 'refs/heads/gh-pages', parent)
        stale = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', check], cwd=checkout, env=environment, capture_output=True)
        self.assertNotEqual(stale.returncode, 0)
        self.assertEqual(pages.git(checkout, 'rev-parse', 'HEAD'), prepared)

    def test_trusted_seal_digest_rejects_a_resealed_candidate(self):
        pages.build(self.site)
        candidate = self.root / 'sealed'; candidate.mkdir()
        shutil.copytree(self.site, candidate / 'benchmarks')
        pages.seal(candidate, self.revision)
        trusted = pages.digest((candidate / 'candidate.json').read_bytes())
        pages.verify_candidate(candidate, trusted)
        pages.write(candidate, 'benchmarks/index.html', b'replacement')
        pages.seal(candidate, self.revision)
        with self.assertRaisesRegex(ValueError, 'trusted preparation output'):
            pages.verify_candidate(candidate, trusted)

    def test_rendering_boundary_rejects_an_external_ledger_link(self):
        captured = analysis.capture_inputs([self.site / 'report/current'])
        result = analysis.build_analysis(captured)
        inv = next(iter(captured.records))
        context = {'current': {**self.state['current'], 'inventory_record_id': inv}, 'slots': [], 'history': pages.ledger(self.site)}
        context['history'][0]['member'] = 'javascript:alert(1)'
        with self.assertRaisesRegex(ValueError, 'ledger link'):
            report.render_report(result, captured, pages_context=context)

    def test_reporting_setup_entry_point_never_dispatches_scanners_compose_or_evaluation(self):
        if sys.version_info[:2] != (3, 13): self.skipTest('Pinned Python 3.13 setup contract')
        # Command fixtures exercise the real Bash routing; they are not an install qualification.
        bin_dir = self.root / 'bin'; bin_dir.mkdir()
        log = self.root / 'calls'
        uv = """import os,pathlib,sys,shlex
args=sys.argv[1:]
with open(os.environ['CALL_LOG'],'a') as f: f.write('uv '+ ' '.join(args)+'\\n')
if args==['--version']: print('uv 0.13.5')
elif args[0]=='sync':
 root=pathlib.Path(args[args.index('--project')+1])/'.venv/bin'; root.mkdir(parents=True)
 (root/'python').write_text('#!/bin/sh\\nexec '+shlex.quote(sys.executable)+' \"$@\"\\n'); (root/'python').chmod(0o700)
 (root/'skillevaluator').write_text('#!/bin/sh\\necho skillevaluator-0.3.0\\n'); (root/'skillevaluator').chmod(0o700)
elif args[:2]==['pip','list']: print('[]')
else: raise SystemExit('Unexpected reporting setup dependency operation')
"""
        git = """import os,pathlib,sys
args=sys.argv[1:]
with open(os.environ['CALL_LOG'],'a') as f: f.write('git '+ ' '.join(args)+'\\n')
if args[0]=='init': pathlib.Path(args[-1]).mkdir(parents=True)
if 'rev-parse' in args: print('ac0a04905100acdafc6c95829311a9739c340ff6')
if 'apply' in args: raise SystemExit('Reporting must not patch evaluator execution')
"""
        for name, source in [('uv', uv), ('git', git), *[(name, "raise SystemExit('Forbidden reporting operation')") for name in ('curl', 'docker', 'semgrep', 'skillspector')]]:
            path = bin_dir / name; path.write_text('#!' + sys.executable + '\n' + source); path.chmod(0o700)
        environment = {**os.environ, 'PATH': str(bin_dir) + os.pathsep + os.environ['PATH'], 'CALL_LOG': str(log),
            'RUNNER_TEMP': str(self.root / 'tools'), 'GITHUB_WORKSPACE': str(ROOT),
            'GITHUB_ENV': str(self.root / 'env'), 'GITHUB_PATH': str(self.root / 'path')}
        run = subprocess.run(['bash', str(ROOT / '.github/scripts/setup-skillevaluator.sh'), 'reporting'], env=environment,
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('SKILL_EVALUATION_KIND=reporting', (self.root / 'env').read_text())
        calls = log.read_text()
        self.assertNotIn('semgrep', calls); self.assertNotIn('skillspector', calls); self.assertNotIn('benchmark', calls)
        self.assertIn('--frozen --no-dev --extra security --extra tier3', calls)

    def test_workflow_permissions_queue_and_trusted_checkout(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/publish-skill-report.yml').read_text())
        triggers = workflow.get('on', workflow.get(True))
        self.assertEqual(set(triggers), {'workflow_run', 'repository_dispatch'})
        self.assertEqual(triggers['workflow_run']['branches'], ['main'])
        self.assertEqual(triggers['repository_dispatch']['types'], [pages.RECOVERY_EVENT])
        self.assertEqual(workflow['permissions'], {})
        jobs = workflow['jobs']
        self.assertEqual(jobs['prepare']['permissions'], {'contents': 'read', 'actions': 'read'})
        self.assertEqual(jobs['commit']['permissions'], {'contents': 'write'})
        self.assertEqual(jobs['deploy']['permissions'], {'contents': 'read', 'pages': 'write', 'id-token': 'write'})
        benchmark = yaml.safe_load((ROOT / '.github/workflows/benchmark-skills.yml').read_text())
        self.assertEqual(workflow['concurrency'], benchmark['jobs']['publish-history']['concurrency'])
        self.assertEqual(workflow['concurrency'], {'group': 'skill-report-publication', 'queue': 'max', 'cancel-in-progress': False})
        self.assertNotIn('deploy-pages', benchmark['jobs'])
        self.assertNotIn('OPENAI_API_KEY', json.dumps(workflow))
        for job in jobs.values():
            for step in job['steps']:
                if 'uses' in step: self.assertRegex(step['uses'], r'@[0-9a-f]{40}$')
                if step.get('uses', '').startswith('actions/checkout@'): self.assertFalse(step['with']['persist-credentials'])
        checkout = jobs['deploy']['steps'][0]
        self.assertEqual(checkout['with']['ref'], '${{ needs.commit.outputs.publication_sha }}')
        validation = yaml.safe_load((ROOT / '.github/workflows/validate.yml').read_text())
        steps = validation['jobs']['pester-eval-feasibility']['steps']
        upload = next(step for step in steps if step['name'] == 'Upload validated public Pester oracle evidence')
        self.assertIn("steps.qualification.outcome == 'success'", upload['if'])
        self.assertIn("steps.pester-integrity.outcome == 'success'", upload['if'])
        self.assertNotIn('consolidated', upload['with']['path'])


if __name__ == '__main__':
    unittest.main()
