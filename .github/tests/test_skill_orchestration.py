"""Production planning/dispatch entry points over Git repositories and synthetic Actions state.

The API fixture records POSTs; no provider, model, Docker, or remote dispatch is used.
"""
import copy
from datetime import datetime, timezone, timedelta
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import yaml

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import skill_orchestration as orchestration
import skill_pages as pages
import skill_reports as reports

ROOT = Path(__file__).resolve().parents[2]
CLOCK = datetime(2026, 11, 30, 12, tzinfo=timezone.utc)


def git(root, *args):
    return orchestration.git(root, *args).decode().strip()


def commit(root, message='Fixture change'):
    git(root, 'add', '.')
    git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', message)
    return git(root, 'rev-parse', 'HEAD')


def stamp(days):
    return (CLOCK - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')


class API:
    def __init__(self, main, retained):
        self.main, self.retained = main, retained
        self.runs, self.jobs, self.artifacts, self.archives = {}, {}, {}, {}
        self.validation_runs, self.benchmark_runs, self.planner_runs = [], [], []
        self.paths = {pages.WORKFLOWS['validate']: 100, orchestration.BENCHMARK: 200, orchestration.WORKFLOW: 300}
        self.posts = []

    def run(self, number, path, revision=None, *, conclusion='success', status='completed', attempt=1, days=0, title=''):
        event = 'push' if path == pages.WORKFLOWS['validate'] else 'workflow_dispatch'
        value = {'id': number, 'run_attempt': attempt, 'path': path, 'workflow_id': self.paths[path],
                 'repository': {'full_name': pages.REPOSITORY},
                 'head_repository': {'full_name': pages.REPOSITORY, 'id': 1}, 'head_branch': 'main',
                 'head_sha': revision or self.main, 'event': event, 'status': status, 'conclusion': conclusion,
                 'created_at': stamp(days), 'updated_at': stamp(days), 'display_title': title}
        self.runs[number, attempt] = value
        self.jobs[number, attempt] = []
        rows = self.validation_runs if path == pages.WORKFLOWS['validate'] else (
            self.benchmark_runs if path == orchestration.BENCHMARK else self.planner_runs)
        rows.append(value)
        return value

    def job(self, run, name, steps=(), *, conclusion='success', status='completed'):
        value = {'name': name, 'run_id': run['id'], 'run_attempt': run['run_attempt'], 'head_sha': run['head_sha'],
                 'status': status, 'conclusion': conclusion,
                 'steps': [{'name': step, 'conclusion': 'success'} for step in steps]}
        self.jobs[run['id'], run['run_attempt']].append(value)
        return value

    def artifact(self, run, name, record):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('record.json', pages.encoded(record))
        raw = buffer.getvalue()
        number = len(self.archives) + 1000
        value = {'id': number, 'name': name, 'expired': False, 'digest': 'sha256:' + pages.digest(raw),
                 'workflow_run': {'id': run['id'], 'head_sha': run['head_sha'], 'head_repository_id': 1}}
        self.artifacts.setdefault(run['id'], []).append(value)
        self.archives[number] = raw
        return value

    def get(self, path):
        if path == 'git/ref/heads/main': return {'object': {'sha': self.main}}
        if path == 'git/ref/heads/gh-pages': return {'object': {'sha': self.retained}}
        if '/attempts/' in path:
            parts = path.split('/')
            value = self.runs.get((int(parts[2]), int(parts[4])))
            if value is None: raise ValueError('Requested run unavailable')
            return value
        if path.startswith('actions/workflows/'):
            source = '.github/workflows/' + path.split('/')[-1]
            return {'id': self.paths[source], 'path': source}
        raise AssertionError('Unexpected API read: ' + path)

    def listing(self, path, key):
        if path.endswith('/jobs'):
            parts = path.split('/')
            return self.jobs[int(parts[2]), int(parts[4])]
        if path.endswith('/artifacts'): return self.artifacts.get(int(path.split('/')[2]), [])
        if 'validate.yml/runs' in path: return [r for r in self.validation_runs if r['head_sha'] == self.main]
        if 'benchmark-skills.yml/runs' in path: return self.benchmark_runs
        if 'orchestrate-skill-evaluations.yml/runs' in path: return self.planner_runs
        raise AssertionError('Unexpected API list: ' + path)

    def raw(self, path):
        return self.archives[int(path.split('/')[-2])]

    def post(self, payload):
        self.posts.append(payload)
        return {'workflow_run_id': 90, 'run_url': f'https://api.github.com/repos/{pages.REPOSITORY}/actions/runs/90',
                'html_url': f'https://github.com/{pages.REPOSITORY}/actions/runs/90'}


class OrchestrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_temp = tempfile.TemporaryDirectory(prefix='skill-orchestration-base-')
        cls.base = Path(cls.base_temp.name)
        prefixes = ('.apm/', '.agents/skills/', '.github/evals/', '.github/scripts/', '.github/patches/', '.github/workflows/', '.github/evaluator-backends/')
        members = git(ROOT, 'ls-files').splitlines()
        members += [orchestration.POLICY_FILE, orchestration.WORKFLOW, '.github/scripts/skill_orchestration.py']
        for name in sorted(set(members)):
            if name.startswith(prefixes) or name in ('apm.lock.yaml', 'apm.yml'):
                source, target = ROOT / name, cls.base / name
                if source.is_file() and not source.is_symlink():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
        # Synthetic runs must not inherit production qualification or activation.
        cfg = orchestration.policy(cls.base)
        for suite in cfg['suites'].values():
            suite.update(enabled=False, reference=None)
        reports.write_json(cls.base / orchestration.POLICY_FILE, cfg)
        git(cls.base, 'init', '-q', '-b', 'main')
        cls.base_revision = commit(cls.base, 'Fixture runtime and skills')

    @classmethod
    def tearDownClass(cls):
        cls.base_temp.cleanup()

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='skill-orchestration-'); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.workspace = self.root / 'source'
        subprocess.run(['git', 'clone', '-q', '--shared', str(self.base), str(self.workspace)], check=True)
        self.retained = self.root / 'retained'; self.retained.mkdir()
        (self.retained / 'benchmarks').mkdir()
        (self.retained / 'benchmarks/.keep').touch()
        git(self.retained, 'init', '-q', '-b', 'gh-pages')
        self.retained_revision = commit(self.retained)
        self.api = API(self.base_revision, self.retained_revision)
        clock = patch.object(orchestration, 'now', return_value=CLOCK); clock.start(); self.addCleanup(clock.stop)
        env = patch.dict(os.environ, {'GITHUB_REPOSITORY': pages.REPOSITORY, 'GITHUB_RUN_ID': '30',
            'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_REF': 'refs/heads/main', 'PYTHONDONTWRITEBYTECODE': '1'})
        env.start(); self.addCleanup(env.stop)
        self.validate()

    def validate(self, conclusion='success'):
        self.api.validation_runs.clear()
        run = self.api.run(20, pages.WORKFLOWS['validate'], conclusion=conclusion)
        self.api.job(run, 'Full validation (PowerShell 7 and Bash)', conclusion=conclusion)
        self.api.job(run, 'native-deadline', conclusion='skipped')
        self.api.job(run, 'pester-admission', conclusion='skipped')
        self.api.job(run, 'Selected validation results', ['Require every selected check to succeed'],
                     conclusion=conclusion)
        return run

    def change(self, member, text='\nFixture update\n'):
        with (self.workspace / member).open('a') as stream: stream.write(text)
        self.api.main = commit(self.workspace)
        self.validate()

    def enable(self, *names):
        cfg = orchestration.policy(self.workspace)
        for name in names:
            cfg['suites'][name].update(enabled=True, reference={'run_id': 10 if name == 'podman' else 11, 'attempt': 1})
        reports.write_json(self.workspace / orchestration.POLICY_FILE, cfg)
        self.api.main = commit(self.workspace)
        self.validate()

    def reference(self, name='podman', days=35, revision=None):
        run = self.api.run(10 if name == 'podman' else 11, orchestration.BENCHMARK,
                           revision or self.base_revision, days=days, title=f'Benchmark {name} (standard)')
        self.api.job(run, 'evaluate', ['Validate selection and clean checkout',
            'Run native with-skill and without-skill evaluation', 'Summarize native results and prepare standard metrics',
            'Verify evaluator left the checkout unchanged'])
        self.api.job(run, 'publish-history', ['Validate metric allowlist and canonical series',
            'Append standard result to durable history', 'Capture and verify the exact published history commit'])
        if orchestration.NATIVE_BENCHMARK_POLICY in orchestration.manifest(self.workspace, run['head_sha']):
            from benchmark_native import score_series

            policy = score_series(name, 'standard')
        else:
            patch_digest = hashlib.sha256((self.workspace / reports.PATCH).read_bytes()).hexdigest()
            policy = hashlib.sha256(json.dumps([reports.benchmark_policy(name), patch_digest], sort_keys=True).encode()).hexdigest()[:16]
        metrics = [{'name': title, 'value': 0.1, 'unit': 'score', 'extra': f'Dataset sha256:{"b" * 64}; policy {policy}'} for title in reports.METRICS]
        row = {'commit': {'id': run['head_sha'], 'url': f'https://github.com/{pages.REPOSITORY}/commit/{run["head_sha"]}', 'message': 'Fixture'},
               'date': 100, 'tool': 'customBiggerIsBetter', 'benches': metrics}
        pages.write(self.retained / 'benchmarks', f'{name}/{policy}/data.js', b'window.BENCHMARK_DATA = ' + pages.encoded(
            {'lastUpdate': 100, 'repoUrl': f'https://github.com/{pages.REPOSITORY}', 'entries': {'Agent skill benchmark (standard)': [row]}}))
        self.api.retained = commit(self.retained)
        return run

    def assess(self, event_name='schedule', event=None, **kwargs):
        return orchestration.assess(self.workspace, self.retained, self.api, event_name, event or {}, **kwargs)

    def intent(self, record, *, days=0):
        run = self.api.run(record['run_id'], orchestration.WORKFLOW, record['revision'], days=days)
        self.api.job(run, 'plan', ['Plan evaluation health without inference', 'Upload immutable plan and dispatch intents'])
        self.api.artifact(run, f'skill-evaluation-plan-{run["id"]}-1', record)
        return run

    def selected(self):
        self.reference(); self.enable('podman')
        return self.assess()

    def test_disabled_health_and_coverage_are_not_measurements(self):
        result = self.assess()
        self.assertFalse(result['requests'])
        rows = {r['skill']: r for r in result['health']}
        self.assertEqual(rows['podman']['status'], 'disabled')
        self.assertEqual(rows['gh']['reason'], 'measurement_missing')
        self.assertEqual(rows['powershell-pester-6']['status'], 'diagnostic_only')
        self.assertEqual(rows['dependabot']['status'], 'coverage_gap')
        self.assertEqual(rows['a11y']['coverage'], 'not_configured')

    def test_periodic_due_boundary_and_per_suite_qualification(self):
        self.reference(days=30); self.enable('podman', 'gh')
        result = self.assess()
        self.assertEqual([r['skill'] for r in result['requests']], ['podman'])
        self.assertEqual(result['requests'][0]['trials'], 20)
        self.api.runs[10, 1]['updated_at'] = stamp(29)
        self.assertFalse(self.assess()['requests'])

    def test_failed_rerun_does_not_erase_successful_reference_attempt(self):
        reference = self.reference(days=1); self.enable('podman')
        failed = self.api.run(10, orchestration.BENCHMARK, reference['head_sha'], conclusion='failure',
                              attempt=2, title='Benchmark podman (standard)')
        # GitHub's workflow-run listing exposes the latest attempt, while the
        # configured successful attempt remains available through its exact URL.
        self.api.benchmark_runs = [failed]
        result = self.assess()
        self.assertFalse(result['requests'])
        row = next(r for r in result['health'] if r['skill'] == 'podman')
        self.assertEqual(row['status'], 'fresh')
        self.assertEqual(row['last_qualified']['attempt'], 1)

    def test_meaningful_change_survives_following_irrelevant_merge(self):
        self.reference(days=1); self.enable('podman')
        self.change('.apm/skills/podman/SKILL.md')
        self.change('apm.yml', '\n# Unrelated manifest comment\n')
        result = self.assess()
        self.assertEqual(result['requests'][0]['reason'], 'inputs_changed')

    def test_overlay_runbook_is_irrelevant_but_grader_changes_select_gh(self):
        self.reference('gh', days=1); self.enable('gh')
        self.change('.github/evals/gh/EVALS.md')
        self.assertFalse(self.assess()['requests'])
        self.change('.github/evals/gh/evals/files/fixture.py', '\n# Grader contract changed\n')
        self.assertEqual([r['skill'] for r in self.assess()['requests']], ['gh'])

    def test_generated_copies_lock_timestamp_and_shared_instructions(self):
        before = orchestration.snapshots(self.workspace, self.api.main)[1]
        self.change('.agents/skills/podman/SKILL.md')
        self.change('apm.lock.yaml', '\n# Refresh timestamp only\n')
        self.change('.apm/instructions/personal.instructions.md')
        after = orchestration.snapshots(self.workspace, self.api.main)[1]
        self.assertEqual(before, after)
        result = self.assess()
        self.assertTrue(result['shared_instructions_changed'])
        self.assertFalse(result['requests'])

    def test_production_release_fingerprint_requires_all_runtime_members(self):
        files = {name.removesuffix('/') + ('/fixture.py' if name.endswith('/') else ''):
                 ('100644', 'blob', 'a' * 40)
                 for name in orchestration.NATIVE_RUNTIME_FILES + orchestration.RUNTIME_FILES}
        pinned = orchestration.benchmark_runtime_inputs(files)
        for member in ('.github/scripts/benchmark_native.py', '.github/scripts/skill_reports.py',
                       '.github/evaluator-backends/candidate-101/benchmark_codex.py',
                       '.github/evaluator-backends/candidate-101/codex-catalog/models.json',
                       '.github/patches/skillevaluator-v1.2.1-benchmark-staging.patch',
                       '.github/patches/skillevaluator-v1.2.1-benchmark-recovery.patch',
                       '.github/patches/skillevaluator-v1.2.1-benchmark-evidence.patch'):
            with self.subTest(member=member):
                self.assertNotEqual(orchestration.identity(pinned), orchestration.identity(
                    orchestration.benchmark_runtime_inputs({**files, member: ('100644', 'blob', 'b' * 40)})))
                with self.assertRaisesRegex(ValueError, 'Missing runtime input'):
                    orchestration.benchmark_runtime_inputs({key: value for key, value in files.items() if key != member})
        files.pop(orchestration.NATIVE_BENCHMARK_POLICY)
        files.pop(orchestration.PREVIOUS_NATIVE_BENCHMARK_POLICY, None)
        self.assertEqual(orchestration.benchmark_runtime_inputs(files), orchestration.subset(files, orchestration.RUNTIME_FILES))

    def test_candidate_fingerprint_binds_release_and_dataset_without_rewriting_historical_fingerprint(self):
        (self.workspace / orchestration.NATIVE_BENCHMARK_POLICY).unlink()
        (self.workspace / orchestration.PREVIOUS_NATIVE_BENCHMARK_POLICY).unlink()
        self.api.main = commit(self.workspace, 'Select the pre-adoption benchmark runtime')
        before = orchestration.snapshots(self.workspace, self.api.main)[1]
        fingerprint = orchestration.candidate_podman_fingerprint(self.workspace, self.api.main)
        self.change('.github/scripts/benchmark_smoke.py', '\n# Candidate diagnostics changed\n')
        self.assertEqual(before, orchestration.snapshots(self.workspace, self.api.main)[1])
        self.assertNotEqual(fingerprint, orchestration.candidate_podman_fingerprint(self.workspace, self.api.main))
        for member in ('.github/scripts/setup-static-evaluator.sh',
                       '.github/evaluator-backends/candidate-101/benchmark_codex.py',
                       '.github/evaluator-backends/candidate-101/codex-catalog/models.json',
                       '.apm/skills/podman/evals/evals.json'):
            with self.subTest(member=member):
                self.change(member)
                changed = orchestration.candidate_podman_fingerprint(self.workspace, self.api.main)
                self.assertNotEqual(fingerprint, changed)
                fingerprint = changed
        (self.workspace / '.github/evals/evaluator-1.0.1-benchmark-candidate-v3.json').unlink()
        revision = commit(self.workspace, 'Remove the candidate release lock identity')
        with self.assertRaisesRegex(ValueError, 'Missing candidate benchmark input'):
            orchestration.candidate_podman_fingerprint(self.workspace, revision)

    def test_compatibility_scope_requires_exact_initial_dispatch_and_preapproval(self):
        import benchmark_smoke as smoke
        from benchmark_native import native_versions
        from benchmark_podman import scope

        revision = self.api.main
        retained = scope(self.workspace, revision)
        self.assertEqual(retained['agent']['cli'], '0.171.0')
        env = dict(os.environ, GITHUB_SHA=revision, GITHUB_EVENT_NAME='workflow_dispatch',
                   GITHUB_REF='refs/heads/' + smoke.BRANCH)
        inputs = {'mode': smoke.MODE, 'skill': 'podman', 'expected_revision': revision}
        record = smoke.reviewed_scope(self.workspace, env, inputs)
        self.assertEqual(record['runtime'], native_versions())
        self.assertEqual(record['scope']['agent']['cli'], '0.172.0')
        self.assertEqual(record['scope']['fingerprint'],
                         orchestration.candidate_podman_fingerprint(self.workspace, revision, released=True))
        self.assertEqual(record['scope']['case'], '1')
        self.assertEqual(record['scope']['arms'], ['with_skill', 'without_skill'])
        self.assertEqual(record['scope']['planned_trials'], 2)
        self.assertFalse(record['scope']['history_eligible'])
        self.assertEqual(record['scope']['agent']['tool_surface'], record['runtime']['codex_tool_surface'])
        baseline = smoke.reviewed_scope(self.workspace, env, {**inputs, 'candidate_smoke_arms': 'without-skill'})
        self.assertEqual(baseline['scope'], {**record['scope'], 'arms': ['without_skill'], 'planned_trials': 1})
        self.assertEqual(baseline['provider_policy'], record['provider_policy'])
        self.assertEqual(baseline['cost_estimate']['usd'], 1.80)
        fixture_inputs = {**inputs, 'candidate_smoke_arms': 'without-skill',
                          'candidate_smoke_workload': 'file-edit-fixture'}
        fixture = smoke.reviewed_scope(self.workspace, env, fixture_inputs)
        self.assertEqual(fixture['scope'], {
            **baseline['scope'], 'case': smoke.FILE_EDIT_CASE,
            'fixture_digest': 'sha256:' + orchestration.identity(smoke.FILE_EDIT_DATASET),
        })
        self.assertEqual(fixture['provider_policy'], baseline['provider_policy'])
        self.assertEqual(fixture['runtime'], baseline['runtime'])
        for updates in ({'mode': 'confirmation'}, {'skill': 'gh'}, {'expected_revision': 'f' * 40},
                        {'request_id': 'autodispatch'}, {'planner_run_id': '20'},
                        {'candidate_smoke_arms': 'with-skill'},
                        {'candidate_smoke_workload': 'file-edit-fixture'},
                        {'candidate_smoke_workload': 'unknown'}):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                smoke.reviewed_scope(self.workspace, env, {**inputs, **updates})
        for updates in ({'GITHUB_RUN_ATTEMPT': '2'}, {'GITHUB_REF': 'refs/heads/main'},
                        {'GITHUB_EVENT_NAME': 'push'}):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                smoke.reviewed_scope(self.workspace, {**env, **updates}, inputs)
        run = self.api.run(30, orchestration.BENCHMARK, revision, status='in_progress')
        run['head_branch'] = smoke.BRANCH
        original_get = self.api.get
        def feature_get(path):
            if path == 'git/ref/heads/' + smoke.BRANCH:
                return {'object': {'sha': self.api.main}}
            return original_get(path)
        self.api.main = revision
        with patch.object(self.api, 'get', side_effect=feature_get):
            with self.assertRaisesRegex(ValueError, 'Operational record unavailable'):
                smoke.guard(self.api, record)
            artifact = self.api.artifact(run, smoke.artifact_name(record), record)
            smoke.guard(self.api, record)
            for other in (baseline, fixture):
                with self.assertRaisesRegex(ValueError, 'preapproval scope mismatch'):
                    smoke.guard(self.api, other)
            altered = {**record, 'provider_policy': {}}
            with self.assertRaisesRegex(ValueError, 'preapproval scope mismatch'):
                smoke.guard(self.api, altered)
            altered = {**record, 'runtime': {**record['runtime'], 'patch_sha256': 'a' * 64}}
            with self.assertRaisesRegex(ValueError, 'preapproval scope mismatch'):
                smoke.guard(self.api, altered)
            self.api.main = 'f' * 40
            with self.assertRaisesRegex(ValueError, 'branch changed'):
                smoke.guard(self.api, record)
            artifact['expired'] = True
            with self.assertRaisesRegex(ValueError, 'Operational record unavailable'):
                smoke.guard(self.api, record)

    @unittest.skipUnless(os.environ.get('SKILL_EVALUATION_KIND') == 'benchmark', 'requires the patched 1.0.1 runtime')
    def test_compatibility_file_edit_stages_one_isolated_baseline(self):
        import benchmark_smoke as smoke
        from harbor.models.task.task import Task

        revision = self.api.main
        env = dict(os.environ, GITHUB_SHA=revision, GITHUB_EVENT_NAME='workflow_dispatch',
                   GITHUB_REF='refs/heads/' + smoke.BRANCH)
        inputs = {'mode': smoke.MODE, 'skill': 'podman', 'expected_revision': revision,
                  'candidate_smoke_arms': 'without-skill', 'candidate_smoke_workload': 'file-edit-fixture'}
        expected = smoke.reviewed_scope(self.workspace, env, inputs)
        authored = self.workspace / '.apm/skills/podman/evals/evals.json'
        original = authored.read_bytes()
        stage = self.root / 'file-edit'
        with patch('qualify_codex_1691.acquire', side_effect=lambda _, dest: reports.write_json(dest / 'integrity.json', {})), \
                patch.object(smoke, 'configure_openai_task', side_effect=lambda task, *_: Task(task)):
            receipt = smoke.prepare(self.workspace, stage, expected)
        task, = (stage / 'without_skill/tasks').iterdir()
        self.assertEqual(task.name, smoke.FILE_EDIT_CASE)
        self.assertEqual(receipt['tasks'], {'without_skill': Task(task).checksum})
        self.assertFalse((stage / 'with_skill').exists())
        self.assertTrue((stage / 'fixture/podman/.git').is_dir())
        entry = reports.read_json(task / 'tests/entry.json')
        self.assertIs(entry['has_skill'], False)
        self.assertEqual(entry['question'], smoke.FILE_EDIT_DATASET['evals'][0]['prompt'])
        self.assertEqual(authored.read_bytes(), original)

    def test_compatibility_receipt_requires_a_complete_verifier_measurement(self):
        import benchmark_smoke as smoke

        job = self.root / 'job'
        trial = job / 'podman-1__fixture'
        usage = {'n_input_tokens': 11, 'n_output_tokens': 5, 'n_cache_tokens': None}
        reports.write_json(trial / 'result.json', {
            'exception_info': None, 'finished_at': stamp(0),
            'agent_info': {'version': '0.171.0'}, 'agent_result': usage,
        })
        selected = {'case': '1', 'agent': {'cli': '0.171.0'}, 'verifier': {'model': 'gpt-6.2-sol'}}
        reward_path = trial / 'verifier' / 'skill_evaluator_reward.json'
        identity = {'entry_id': '1', 'has_skill': False, 'score_policy': 'skill-evaluator-dimension-mean-v1'}
        metrics = ('accuracy', 'behavior_check', 'goal_accuracy')
        details = {metric: {'judge_model_used': 'gpt-6.2-sol', 'judge_reasoning_effort': None,
                            'judge_fallback_used': False, 'score': 0.8} for metric in metrics}
        measured = {**identity, 'judge_contract': 'skill-evaluator-judges-v2', 'details': details}
        private_text = 'private verifier output'
        blocked = {**identity, 'evaluation_status': 'failed', 'evaluation_errors': {'execution_evidence': private_text}}
        incomplete = (
            ({**identity, 'evaluation_status': 'failed', 'error': 'No trajectory or reconstructible agent log'},
             'trajectory_unavailable', {}),
            (blocked, 'unsupported_execution_evidence', {}),
            ({**blocked, 'details': {'security': {'findings': [None, {'type': private_text}],
                                                  'supported': False, 'passed': None}}},
             'unsupported_execution_evidence', {}),
            ({**blocked, 'details': {'security': {'findings': [
                {'type': 'unsupported_tool_wrapper', 'evidence': private_text},
                {'type': private_text}, {'type': 'unsupported_path_evidence', 'message': private_text},
                {'type': 'unsupported_tool_wrapper'},
             ], 'supported': False, 'passed': None}}},
             'unsupported_execution_evidence',
             {'execution_evidence_reasons': ['unsupported_path_evidence', 'unsupported_tool_wrapper']}),
            ({**blocked, 'details': {'security': {'findings': [], 'passed': True, 'score': 1.0}}},
             'unsupported_execution_evidence', {'execution_evidence_reasons': ['missing_or_ambiguous_tool_result']}),
            ({**measured, 'evaluation_status': 'failed', 'evaluation_errors': {'accuracy': private_text}},
             'required_judge_failed', {'failed_judges': ['accuracy']}),
            ({**measured, 'has_skill': True}, 'reward_identity', {}),
            ({**measured, 'judge_contract': None}, 'judge_contract', {}),
            ({**measured, 'details': {**details, 'accuracy': {'score': 0.8}}}, 'judge_observation', {}),
        )
        for reward, reason, diagnostic in incomplete:
            with self.subTest(reason=reason, diagnostic=diagnostic):
                reports.write_json(reward_path, reward)
                receipt = {'state': 'started'}
                with self.assertRaises(ValueError):
                    smoke.trial_receipt(job, arm='without_skill', selected=selected, receipt=receipt)
                self.assertEqual(receipt, {
                    'state': 'incomplete', 'agent_usage': usage, 'failure_reason': reason, **diagnostic,
                })
        reports.write_json(reward_path, measured)
        receipt = {'state': 'started'}
        smoke.trial_receipt(job, arm='without_skill', selected=selected, receipt=receipt)
        self.assertEqual(receipt, {'state': 'complete', 'agent_usage': usage, 'judge_scores': dict.fromkeys(metrics, 0.8)})

        selected['agent']['tool_surface'] = smoke.native_versions()['codex_tool_surface']
        atif = trial / 'agent/trajectory.json'
        for names in ((), ('exec',), ('exec', 'exec_command')):
            reports.write_json(atif, {'steps': [{'tool_calls': [{'function_name': name} for name in names]}]})
            receipt = {'state': 'started'}
            with self.assertRaisesRegex(ValueError, 'reviewed direct tool route'):
                smoke.trial_receipt(job, arm='without_skill', selected=selected, receipt=receipt)
            self.assertEqual(receipt['failure_reason'], 'tool_route_unavailable')
        reports.write_json(atif, {'steps': [{'tool_calls': [{'function_name': 'exec_command'}]}]})
        receipt = {'state': 'started'}
        smoke.trial_receipt(job, arm='without_skill', selected=selected, receipt=receipt)
        self.assertEqual(receipt, {'state': 'complete', 'agent_usage': usage, 'native_tool_route': 'direct',
                                   'judge_scores': dict.fromkeys(metrics, 0.8)})

    def test_production_workflow_is_manual_protected_and_uses_the_released_owner(self):
        workflow = yaml.safe_load((ROOT / orchestration.BENCHMARK).read_text())
        inputs = workflow.get('on', workflow.get(True))['workflow_dispatch']['inputs']
        self.assertEqual(inputs['mode']['default'], 'standard')
        self.assertEqual(inputs['mode']['options'], ['standard', 'confirmation'])
        self.assertNotIn('candidate_smoke_arms', inputs)
        jobs = workflow['jobs']
        self.assertEqual(set(jobs), {'context', 'evaluate', 'publish-history'})
        job = jobs['evaluate']
        self.assertEqual(job['environment'], {'name': 'skill-benchmark', 'deployment': False})
        self.assertEqual(job['permissions'], {'contents': 'read', 'actions': 'read'})
        steps = job['steps']
        index = next(i for i, step in enumerate(steps) if step.get('id') == 'evaluation')
        self.assertEqual(steps[index - 1]['id'], 'preparation')
        self.assertIn('benchmark_native.py prepare', steps[index - 1]['run'])
        self.assertIn('skill_orchestration.py guard', steps[index - 1]['run'].splitlines()[-2])
        self.assertEqual(steps[index]['if'], "steps.preparation.outputs.execute == 'true'")
        self.assertIn('benchmark_native.py execute', steps[index]['run'])
        uploads = [step for step in steps if step.get('with', {}).get('name') == 'skill-metrics']
        self.assertEqual(len(uploads), 1)
        self.assertTrue(uploads[0]['with']['path'].endswith('/released-scores.json'))
        self.assertIn("inputs.mode == 'standard'", uploads[0]['if'])
        self.assertIn('history_eligible', uploads[0]['if'])

    @unittest.skipUnless(os.environ.get('SKILL_EVALUATION_KIND') == 'benchmark', 'requires the patched 1.0.1 verifier')
    def test_compatibility_path_observation_uses_the_native_classifier_and_redacts_the_source(self):
        import benchmark_smoke as smoke
        from skillevaluator.tier3.harbor.templates import eval as verifier

        job = self.root / 'job'
        trial = job / 'podman-1__fixture'
        marker = 'private fixture command and observation'
        trajectory = {'steps': [{'source': 'agent', 'tool_calls': [
            {'function_name': 'exec_command', 'tool_call_id': 'unsupported',
             'arguments': {'cmd': "printf '%s' 'mention /run/podman/podman.sock' | wc -c"}},
            {'function_name': 'exec_command', 'tool_call_id': 'literal',
             'arguments': {'cmd': "printf '%s' '/run/podman/podman.sock " + marker + "'"}},
        ], 'observation': {'results': [
            {'source_call_id': call_id, 'content': marker} for call_id in ('unsupported', 'literal')
        ]}}]}
        calls = verifier.extract_tool_calls_as_dicts(trajectory)
        security = verifier.check_security(trajectory, calls)
        self.assertIs(security['supported'], False)
        reports.write_json(trial / 'agent/trajectory.json', trajectory)
        self.assertEqual(smoke.path_syntax('x' * 65537), 'source_limit')
        usage = {'n_input_tokens': 11, 'n_output_tokens': 5, 'n_cache_tokens': None}
        reports.write_json(trial / 'result.json', {
            'exception_info': None, 'finished_at': stamp(0),
            'agent_info': {'version': '0.171.0'}, 'agent_result': usage,
        })
        reward = {
            'entry_id': '1', 'has_skill': False, 'score_policy': 'skill-evaluator-dimension-mean-v1',
            'evaluation_status': 'failed', 'evaluation_errors': {'execution_evidence': marker},
            'details': {'security': security}, 'trajectory_source': 'trajectory.json',
        }
        entry = trial / 'tests/entry.json'
        reports.write_json(entry, {'id': '1', 'has_skill': False})
        selected = {'case': '1', 'agent': {'cli': '0.171.0'}, 'verifier': {'model': 'gpt-6.2-sol'}}
        for source, expected in (('trajectory.json', ['shell_control_operator']), ('agent-log', None)):
            with self.subTest(source=source):
                reports.write_json(trial / 'verifier/skill_evaluator_reward.json',
                                   {**reward, 'trajectory_source': source})
                receipt = {}
                with self.assertRaisesRegex(ValueError, 'Native verifier did not produce a complete measurement'):
                    smoke.trial_receipt(job, arm='without_skill', selected=selected, receipt=receipt, entry_path=entry)
                self.assertEqual(receipt.get('path_evidence_syntax'), expected)
                self.assertEqual(receipt['execution_evidence_reasons'], ['unsupported_path_evidence'])
                self.assertNotIn(marker, json.dumps(receipt))
                self.assertNotIn('podman.sock', json.dumps(receipt))

        security['findings'].append(security['findings'][0])
        reports.write_json(trial / 'verifier/skill_evaluator_reward.json', reward)
        receipt = {}
        with self.assertRaisesRegex(ValueError, 'Native verifier did not produce a complete measurement'):
            smoke.trial_receipt(job, arm='without_skill', selected=selected, receipt=receipt, entry_path=entry)
        self.assertNotIn('path_evidence_syntax', receipt)

    def test_gh_competing_refresh_is_one_canonical_change_and_blocks_unreviewed_pin(self):
        lock_path = self.workspace / 'apm.lock.yaml'
        lock = yaml.safe_load(lock_path.read_text())
        owner = next(r for r in lock['dependencies'] if r['name'] == 'github-actions-hardening')
        member = next(iter(owner['deployed_file_hashes']))
        with (self.workspace / member).open('a') as stream: stream.write('\nChanged upstream content\n')
        owner['deployed_file_hashes'][member] = 'sha256:' + hashlib.sha256((self.workspace / member).read_bytes()).hexdigest()
        owner['resolved_commit'] = 'e' * 40
        lock_path.write_text(yaml.safe_dump(lock))
        self.api.main = commit(self.workspace); self.validate()
        result = self.assess()
        self.assertEqual(result['source_changes'], ['github-actions-hardening'])
        self.assertEqual(next(r for r in result['health'] if r['skill'] == 'gh')['reason'], 'dependency_or_dataset_unavailable')

    def test_validation_failure_and_superseded_revision_cannot_dispatch(self):
        self.selected(); self.validate('failure')
        self.assertFalse(self.assess()['requests'])
        self.validate(); self.api.main = 'e' * 40
        # Remote main moves; the source checkout is still pinned to its original revision.
        with patch.object(orchestration, 'validation', return_value=({'run_id': 20, 'attempt': 1}, None)):
            result = self.assess()
        self.assertFalse(result['requests'])

    def test_intent_upload_precedes_single_post_and_direct_correlation(self):
        result = self.selected()
        with self.assertRaises(ValueError):
            orchestration.dispatch(self.workspace, self.retained, self.api, result, self.api.post)
        self.assertFalse(self.api.posts)
        self.intent(result)
        response = orchestration.dispatch(self.workspace, self.retained, self.api, result, self.api.post)
        self.assertEqual(response['responses'][0]['run_id'], 90)
        self.assertIs(self.api.posts[0]['return_run_details'], True)
        self.assertEqual(self.api.posts[0]['inputs']['expected_revision'], self.api.main)
        self.assertEqual(self.api.posts[0]['ref'], 'main')

    def test_duplicate_trigger_and_uncertain_dispatch_block_resubmission(self):
        result = self.selected(); self.intent(result)
        later = self.assess()
        self.assertFalse(later['requests'])
        self.assertEqual(next(r for r in later['health'] if r['skill'] == 'podman')['reason'], 'dispatch_unresolved')
        with patch.dict(os.environ, {'GITHUB_RUN_ATTEMPT': '2'}):
            with self.assertRaises(ValueError): orchestration.dispatch(self.workspace, self.retained, self.api, result, self.api.post)
        self.assertFalse(self.api.posts)

    def test_failed_benchmark_reconciles_but_never_qualifies_or_retries(self):
        result = self.selected(); self.intent(result)
        request = result['requests'][0]
        self.api.run(90, orchestration.BENCHMARK, conclusion='failure', title=f'Benchmark podman (standard) [{request["request_id"]}]')
        self.assertFalse(self.assess()['requests'])
        self.assertEqual(next(r for r in self.assess()['health'] if r['skill'] == 'podman')['reason'], 'already_requested')

    def test_failed_preapproval_setup_is_a_failed_request_not_a_stale_retry(self):
        result = self.selected(); self.intent(result)
        request = result['requests'][0]
        run = self.api.run(90, orchestration.BENCHMARK, conclusion='failure',
                           title=f'Benchmark podman (standard) [{request["request_id"]}]')
        self.api.job(run, 'context', conclusion='failure')
        self.api.job(run, 'evaluate', conclusion='skipped')
        result = self.assess()
        self.assertFalse(result['requests'])
        self.assertEqual(next(r for r in result['health'] if r['skill'] == 'podman')['reason'], 'already_requested')

    def test_two_suites_and_outstanding_same_suite_are_bounded(self):
        self.reference(); self.reference('gh'); self.enable('podman', 'gh')
        self.assertEqual(len(self.assess()['requests']), 2)
        self.api.run(90, orchestration.BENCHMARK, status='waiting', conclusion=None, title='Benchmark podman (standard)')
        self.assertEqual([r['skill'] for r in self.assess()['requests']], ['gh'])

    def test_stale_preapproval_skip_can_be_replaced_without_cancelling_protected_work(self):
        result = self.selected(); self.intent(result)
        request = result['requests'][0]
        run = self.api.run(90, orchestration.BENCHMARK, title=f'Benchmark podman (standard) [{request["request_id"]}]')
        self.api.job(run, 'context', ['Publish scope and authorization context before requesting approval', 'Retain preapproval scope'], conclusion='failure')
        self.api.job(run, 'evaluate', conclusion='skipped')
        self.api.artifact(run, 'skill-benchmark-context-90-1', {'schema_version': 1, 'kind': 'benchmark_context',
            'run_id': 90, 'attempt': 1, 'revision': run['head_sha'], 'phase': 'preapproval', 'status': 'stale',
            'execute': False, 'skill': 'podman', 'mode': 'standard', 'request_id': request['request_id']})
        self.change('apm.yml', '\n# Main advanced\n')
        replacement = self.assess()['requests']
        self.assertEqual(len(replacement), 1)
        self.assertNotEqual(replacement[0]['request_id'], request['request_id'])

    def test_context_precedes_approval_and_postapproval_rechecks_main(self):
        result = self.selected(); self.intent(result)
        request = result['requests'][0]
        inputs = {'skill': 'podman', 'mode': 'standard', 'request_id': request['request_id'],
                  'planner_run_id': '30', 'planner_attempt': '1', 'expected_revision': result['revision']}
        with patch.dict(os.environ, {'GITHUB_RUN_ID': '90'}):
            with patch.object(reports, 'summary'):
                first = orchestration.context(self.workspace, self.retained, self.api, inputs, phase='preapproval')
                self.api.main = 'e' * 40
                second = orchestration.context(self.workspace, self.retained, self.api, inputs, phase='postapproval')
        self.assertTrue(first['execute'])
        self.assertFalse(second['execute'])
        self.assertEqual(second['status'], 'stale')

    def test_postapproval_stale_skip_requires_receipt_and_native_step_evidence(self):
        result = self.selected(); self.intent(result)
        request = result['requests'][0]
        run = self.api.run(90, orchestration.BENCHMARK, title=f'Benchmark podman (standard) [{request["request_id"]}]')
        job = self.api.job(run, 'evaluate', ['Validate dataset, runtime, and final eligibility before inference',
                                          'Retain postapproval authorization decision'])
        step = {'name': 'Run native with-skill and without-skill evaluation', 'conclusion': 'skipped'}
        job['steps'].append(step)
        record = {'schema_version': 1, 'kind': 'benchmark_context', 'run_id': 90, 'attempt': 1,
                  'revision': run['head_sha'], 'phase': 'postapproval', 'status': 'stale', 'execute': False,
                  'skill': 'podman', 'mode': 'standard', 'request_id': request['request_id']}
        self.api.artifact(run, 'skill-benchmark-authorization-90-1', record)
        self.change('apm.yml', '\n# Superseding main\n')
        self.assertEqual(len(self.assess()['requests']), 1)
        step['conclusion'] = 'failure'
        self.assertFalse(self.assess()['requests'])

    def test_main_moving_during_postapproval_assessment_blocks_inference(self):
        result = self.selected(); self.intent(result)
        request = result['requests'][0]
        inputs = {'skill': 'podman', 'mode': 'standard', 'request_id': request['request_id'],
                  'planner_run_id': '30', 'planner_attempt': '1', 'expected_revision': result['revision']}
        original = orchestration.assess
        def main_moves(*args, **kwargs):
            assessment = original(*args, **kwargs)
            self.api.main = 'e' * 40
            return assessment
        with patch.dict(os.environ, {'GITHUB_RUN_ID': '90'}), patch.object(reports, 'summary'), \
                patch.object(orchestration, 'assess', side_effect=main_moves):
            value = orchestration.context(self.workspace, self.retained, self.api, inputs, phase='postapproval')
        self.assertFalse(value['execute'])
        self.assertEqual(value['status'], 'stale')

    def test_forged_producer_attempt_workflow_and_digest_are_rejected(self):
        result = self.selected(); run = self.intent(result)
        for key, value in [('head_branch', 'feature'), ('event', 'pull_request'), ('workflow_id', 999), ('run_attempt', 2)]:
            with self.subTest(key=key):
                original = run[key]; run[key] = value
                with self.assertRaises(ValueError): orchestration.load_intent(self.api, self.workspace, self.api.main, 30, 1)
                run[key] = original
        artifact = self.api.artifacts[30][0]
        artifact['digest'] = 'sha256:' + '0' * 64
        with self.assertRaises(ValueError): orchestration.load_intent(self.api, self.workspace, self.api.main, 30, 1)

    def test_expired_intent_and_missing_qualification_are_not_success(self):
        result = self.selected(); self.intent(result)
        self.api.artifacts[30][0]['expired'] = True
        with self.assertRaises(ValueError): self.assess()

    def test_failed_planning_with_skipped_dispatch_is_proven_nonexecution(self):
        self.selected()
        run = self.api.run(31, orchestration.WORKFLOW, conclusion='failure')
        self.api.job(run, 'plan', conclusion='failure')
        self.api.job(run, 'dispatch', conclusion='skipped')
        self.assertEqual(len(self.assess()['requests']), 1)

    def test_started_dispatch_without_intent_record_remains_blocked(self):
        self.selected()
        run = self.api.run(31, orchestration.WORKFLOW, conclusion='failure')
        self.api.job(run, 'plan', conclusion='failure')
        self.api.job(run, 'dispatch', conclusion='failure')
        with self.assertRaises(ValueError): self.assess()

    def test_incomplete_api_listing_blocks_dispatch(self):
        result = self.selected(); self.intent(result)
        original = self.api.listing
        def incomplete(path, key):
            if 'benchmark-skills.yml/runs' in path: raise ValueError('Incomplete API collection')
            return original(path, key)
        with patch.object(self.api, 'listing', side_effect=incomplete):
            with self.assertRaises(ValueError):
                orchestration.dispatch(self.workspace, self.retained, self.api, result, self.api.post)
        self.assertFalse(self.api.posts)

    def test_scope_ceiling_and_runtime_change_require_review(self):
        self.selected()
        cfg = orchestration.policy(self.workspace); cfg['suites']['podman']['max_cases'] = 9
        reports.write_json(self.workspace / orchestration.POLICY_FILE, cfg)
        self.api.main = commit(self.workspace); self.validate()
        self.assertFalse(self.assess()['requests'])
        self.change('.github/scripts/setup-compose.sh', '\n# Runtime acquisition changed\n')
        self.assertEqual(next(r for r in self.assess()['health'] if r['skill'] == 'podman')['reason'], 'reference_requires_qualification')

    def test_production_cli_with_synthetic_event_and_no_dispatch(self):
        event = self.root / 'event.json'; reports.write_json(event, {'workflow_run': self.api.validation_runs[0]})
        output, github_output = self.root / 'out/record.json', self.root / 'github-output'
        with patch.dict(os.environ, {'GITHUB_EVENT_NAME': 'workflow_run', 'GITHUB_EVENT_PATH': str(event),
                                   'GITHUB_OUTPUT': str(github_output), 'GITHUB_SHA': self.api.main}), patch.object(pages, 'GitHub', return_value=self.api), patch.object(reports, 'summary'):
            result = orchestration.main(['plan', '--workspace', str(self.workspace), '--retained', str(self.retained), '--output', str(output)])
        self.assertEqual(result, 0)
        saved = pages.parse(output.read_bytes())
        self.assertEqual(saved['validation']['run_id'], 20)
        self.assertEqual(next(row for row in saved['health'] if row['skill'] == 'gh')['status'], 'disabled')
        self.assertEqual(github_output.read_text(), 'has_requests=false\n')
        self.assertFalse(self.api.posts)

    def test_dispatch_context_and_guard_cli_entry_points(self):
        record = self.selected(); self.intent(record)
        event, out = self.root / 'event.json', self.root / 'output/record.json'
        common = {'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_EVENT_PATH': str(event),
                  'GITHUB_OUTPUT': str(self.root / 'github-output'), 'GITHUB_SHA': self.api.main}
        args = ['--workspace', str(self.workspace), '--retained', str(self.retained), '--output', str(out)]
        with patch.dict(os.environ, common), patch.object(pages, 'GitHub', return_value=self.api), patch.object(reports, 'summary'):
            reports.write_json(event, {})
            with patch.object(orchestration, 'post_dispatch', side_effect=self.api.post):
                self.assertEqual(orchestration.main(['dispatch', *args]), 0)
            inputs = self.api.posts[0]['inputs']
            reports.write_json(event, {'inputs': inputs})
            with patch.dict(os.environ, {'GITHUB_RUN_ID': '90'}):
                for command, phase in [('context', 'preapproval'), ('guard', 'postapproval')]:
                    self.assertEqual(orchestration.main([command, *args]), 0)
                    saved = pages.parse(out.read_bytes())
                    self.assertTrue(saved['execute'])
                    self.assertEqual(saved['phase'], phase)

    def test_manual_diagnostic_context_and_partial_automatic_inputs(self):
        with patch.object(reports, 'summary'):
            inputs = {'skill': 'powershell-pester-6', 'mode': 'confirmation'}
            value = orchestration.context(self.workspace, self.retained, self.api, inputs, phase='preapproval')
            self.assertEqual(value['trials'], 30)
            with self.assertRaises(ValueError):
                orchestration.context(self.workspace, self.retained, self.api, {**inputs, 'mode': 'standard'}, phase='preapproval')
            with self.assertRaises(ValueError):
                orchestration.context(self.workspace, self.retained, self.api, {**inputs, 'planner_run_id': '30'}, phase='preapproval')

    def test_main_manual_context_accepts_selected_validation_with_intentional_skips(self):
        inputs = {'skill': 'podman', 'mode': 'standard'}
        for phase in ('preapproval', 'postapproval'):
            with self.subTest(phase=phase), patch.object(reports, 'summary'):
                value = orchestration.context(self.workspace, self.retained, self.api, inputs, phase=phase)
                self.assertTrue(value['execute'])
                self.assertEqual(value['status'], 'manual')

    def test_validation_rejects_incomplete_selected_gate_after_green_workflow(self):
        run = self.api.validation_runs[0]
        key = run['id'], run['run_attempt']
        jobs = self.api.jobs[key]
        gate = jobs[-1]
        missing_gate = jobs[:-1]
        gate_step = gate['steps'][0]
        cases = {
            'missing job': missing_gate,
            'duplicate job': [*jobs, gate],
            'skipped job': [*missing_gate, dict(gate, conclusion='skipped')],
            'missing step': [*missing_gate, dict(gate, steps=[])],
            'duplicate step': [*missing_gate, dict(gate, steps=[gate_step, gate_step])],
            'failed step': [*missing_gate, dict(gate, steps=[dict(gate_step, conclusion='failure')])],
            'cancelled sibling': [dict(jobs[0], conclusion='cancelled'), *jobs[1:]],
        }
        for label, roster in cases.items():
            with self.subTest(label=label):
                self.api.jobs[key] = roster
                selected, error = orchestration.validation(self.api, self.workspace, self.api.main)
                self.assertEqual(selected, {'run_id': 20, 'attempt': 1})
                self.assertEqual(error, 'validation_unsuccessful')

    def test_validation_does_not_fall_back_while_latest_run_is_queued(self):
        self.api.run(21, pages.WORKFLOWS['validate'], conclusion=None, status='queued')
        selected, error = orchestration.validation(self.api, self.workspace, self.api.main)
        self.assertEqual(selected, {'run_id': 21, 'attempt': 1})
        self.assertEqual(error, 'validation_unsuccessful')

    def test_main_manual_context_requires_authenticated_validation(self):
        self.validate('failure')
        with patch.object(reports, 'summary'):
            value = orchestration.context(self.workspace, self.retained, self.api,
                                          {'skill': 'podman', 'mode': 'standard'}, phase='preapproval')
        self.assertFalse(value['execute'])
        self.assertEqual(value['status'], 'validation_unsuccessful')


class WorkflowAndUsageTests(unittest.TestCase):
    def test_dispatch_adapter_requests_direct_run_details_once(self):
        payload = {'ref': 'main', 'return_run_details': True, 'inputs': {'skill': 'podman', 'mode': 'standard'}}
        result = subprocess.CompletedProcess([], 0, b'{"workflow_run_id":90}', b'')
        with patch.object(subprocess, 'run', return_value=result) as call:
            self.assertEqual(orchestration.post_dispatch(payload)['workflow_run_id'], 90)
        self.assertEqual(call.call_count, 1)
        self.assertIn('X-GitHub-Api-Version: 2022-11-28', call.call_args.args[0])
        self.assertIs(json.loads(call.call_args.kwargs['input'])['return_run_details'], True)
        with patch.object(subprocess, 'run', side_effect=subprocess.TimeoutExpired('gh', 60)) as call:
            with self.assertRaises(subprocess.TimeoutExpired): orchestration.post_dispatch(payload)
            self.assertEqual(call.call_count, 1)

    def test_operational_archive_rejects_links_and_multiple_members(self):
        api = API('a' * 40, 'b' * 40)
        run = api.run(30, orchestration.WORKFLOW)
        item = api.artifact(run, 'record', {})
        for linked in (False, True):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w') as archive:
                entry = zipfile.ZipInfo('record.json'); entry.external_attr = (0o120777 if linked else 0o100600) << 16
                archive.writestr(entry, b'{}')
                if not linked: archive.writestr('../other.json', b'{}')
            api.archives[item['id']] = buffer.getvalue()
            item['digest'] = 'sha256:' + pages.digest(buffer.getvalue())
            with self.assertRaises(ValueError): orchestration.read_artifact(api, run, 'record')

    def test_trust_permissions_approval_order_and_no_inference_in_planner(self):
        workflow = yaml.safe_load((ROOT / orchestration.WORKFLOW).read_text())
        triggers = workflow.get('on', workflow.get(True))
        self.assertEqual(set(triggers), {'workflow_run', 'schedule', 'workflow_dispatch'})
        self.assertEqual(triggers['schedule'], [{'cron': '37 10 * * 2'}])
        self.assertNotIn('OPENAI_API_KEY', json.dumps(workflow))
        self.assertEqual(workflow['jobs']['plan']['permissions'], {'contents': 'read', 'actions': 'read'})
        self.assertEqual(workflow['jobs']['dispatch']['permissions'], {'contents': 'read', 'actions': 'write'})
        benchmark = yaml.safe_load((ROOT / orchestration.BENCHMARK).read_text())
        context, evaluate = benchmark['jobs']['context'], benchmark['jobs']['evaluate']
        self.assertNotIn('environment', context)
        self.assertEqual(evaluate['needs'], 'context')
        self.assertEqual(evaluate['environment'], {'name': 'skill-benchmark', 'deployment': False})
        steps = evaluate['steps']; guard = next(i for i, s in enumerate(steps) if s.get('id') == 'preparation')
        self.assertEqual(steps[guard + 1]['id'], 'evaluation')
        self.assertIn('skill_orchestration.py guard', steps[guard]['run'].split('docker info > /dev/null')[1])
        self.assertEqual(steps[guard + 1]['if'], "steps.preparation.outputs.execute == 'true'")
        self.assertEqual(benchmark['concurrency'], {'group': 'benchmark-skills', 'queue': 'max', 'cancel-in-progress': False})
        self.assertIn("needs.evaluate.outputs.execution_success == 'true'", benchmark['jobs']['publish-history']['if'])
        self.assertEqual(set(benchmark['jobs']), {'context', 'evaluate', 'publish-history'})
        self.assertEqual(sum(step.get('run', '').endswith(' native-benchmark-121') for step in steps), 1)
        self.assertNotIn('OPENAI_API_KEY', steps[guard]['env'])
        self.assertIn('"$SKILL_NATIVE_BENCHMARK_PYTHON"', steps[guard + 1]['run'])
        publisher = yaml.safe_load((ROOT / '.github/workflows/publish-skill-report.yml').read_text())
        self.assertEqual(publisher.get('on', publisher.get(True))['workflow_run']['workflows'], ['Validate', 'Benchmark skills'])

    def test_released_launcher_qualification_is_isolated_from_protected_execution(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/current-evaluator.yml').read_text())
        jobs = workflow['jobs']
        harness = jobs['benchmark-121-launcher']
        self.assertNotIn('environment', harness)
        self.assertNotIn('secrets.', json.dumps(harness))
        self.assertEqual(workflow['permissions'], {'contents': 'read'})
        self.assertEqual(harness['strategy']['matrix']['include'], [
            {'suite': 'podman', 'mode': 'standard'}, {'suite': 'gh', 'mode': 'confirmation'}])
        for name in ('cohorts', 'native-gh', 'report', 'startup', 'benchmark-121'):
            self.assertIn('!inputs.benchmark-121-launcher', jobs[name]['if'])
        steps = [step.get('run', '') for step in harness['steps']]
        setup = steps.index('bash .github/scripts/setup-static-evaluator.sh native-benchmark-121')
        qualify = next(index for index, step in enumerate(steps) if 'qualify_native_benchmark.py' in step)
        self.assertLess(setup, qualify)
        self.assertIn('"$SKILL_NATIVE_BENCHMARK_PYTHON"', steps[qualify])
        self.assertIn('"$GITHUB_SHA"', steps[qualify])
        installed = steps.index('bash .github/scripts/setup-compose.sh')
        executed = next(index for index, step in enumerate(steps) if 'qualify_native_execution.py' in step)
        self.assertLess(qualify, installed)
        self.assertLess(installed, executed)
        self.assertIn('"$SKILL_NATIVE_BENCHMARK_PYTHON"', steps[executed])
        self.assertIn('"$GITHUB_SHA"', steps[executed])
        self.assertIn('--mode "$QUALIFICATION_MODE"', steps[executed])

    def test_full_regression_validation_is_reused_on_main_and_preapproval_on_features(self):
        workflow = yaml.safe_load((ROOT / orchestration.BENCHMARK).read_text())
        context = workflow['jobs']['context']
        protected = workflow['jobs']['evaluate']
        selector = '.github/scripts/test_evaluation_contracts.py'
        self.assertFalse(any(selector in step.get('run', '') or '-m unittest discover' in step.get('run', '')
                             for step in protected['steps']))
        expected = [
            f'"$SKILL_NATIVE_BENCHMARK_PYTHON" -B {selector} released-contracts',
            f'"$SKILL_REVIEW_CANDIDATE_PYTHON" -B {selector} private-review',
            f'"$SKILL_NATIVE_BENCHMARK_CANDIDATE_PYTHON" -B {selector} fixture-contracts',
            f'"$SKILL_DATA_PYTHON" -B {selector} presentation',
        ]
        tests = [step for step in context['steps'] if selector in step.get('run', '')]
        self.assertEqual([step['run'] for step in tests], expected)
        self.assertTrue(all(step['if'] == "github.ref != 'refs/heads/main'" for step in tests))
        self.assertEqual(tests[0]['env']['SKILL_EVALUATION_KIND'], 'benchmark')
        validate = yaml.safe_load((ROOT / '.github/workflows/validate.yml').read_text())
        validate_steps = validate['jobs']['ci-contracts']['steps']
        for steps in (context['steps'], validate_steps):
            setup = next(step for step in steps
                         if step.get('run') == 'bash .github/scripts/setup-static-evaluator.sh review-contracts')
            review = next(step for step in steps if step.get('run') == expected[1])
            self.assertLess(steps.index(setup), steps.index(review))
            self.assertNotIn('secrets.', json.dumps([setup, review]))
            release = next(step for step in steps if step.get('run') ==
                           'bash .github/scripts/setup-static-evaluator.sh native-benchmark-candidate')
            gh = next(step for step in steps if 'test_gh_evaluations.GhNativeTests' in step.get('run', ''))
            self.assertLess(steps.index(release), steps.index(gh))
            self.assertIn('"$SKILL_NATIVE_BENCHMARK_CANDIDATE_PYTHON"', gh['run'])
            self.assertNotIn('secrets.', json.dumps([release, gh]))
        for command in expected:
            self.assertEqual(sum(command in step.get('run', '') for step in validate_steps), 1)
        self.assertNotIn('SKILL_REVIEW_PYTHON', json.dumps(validate_steps))
        scanner_setup = next(step for step in validate_steps if step.get('run') ==
                             'bash .github/scripts/setup-static-evaluator.sh scanner-contracts')
        scanner_command = f'"$SKILL_SCANNER_CONTRACT_PYTHON" -B {selector} scanner-contracts'
        scanner = next(step for step in validate_steps if scanner_command in step.get('run', ''))
        self.assertLess(validate_steps.index(scanner_setup), validate_steps.index(scanner))
        self.assertEqual(scanner['env'], {'SKILL_EVALUATION_KIND': 'scanner-contracts',
                                          'SKILLEVALUATOR_REQUIRE_SEMGREP': '1'})
        self.assertNotIn('secrets.', json.dumps([scanner_setup, scanner]))
        for command, setup_kind in ((expected[0], 'native-benchmark-121'), (expected[2], 'native-benchmark-candidate')):
            for steps in (context['steps'], validate_steps):
                setup = next(step for step in steps if step.get('run', '').endswith(' ' + setup_kind))
                test = next(step for step in steps if command in step.get('run', ''))
                self.assertLess(steps.index(setup), steps.index(test))
                self.assertNotIn('secrets.', json.dumps([setup, test]))
        qualifier = yaml.safe_load((ROOT / '.github/workflows/current-evaluator.yml').read_text())
        for steps in (context['steps'], validate_steps, qualifier['jobs']['cohorts']['steps']):
            data_setup = next(s for s in steps if 'setup-static-evaluator.sh data-host' in s.get('run', ''))
            presentation = next(s for s in steps if s.get('run') == expected[-1])
            self.assertLess(steps.index(data_setup), steps.index(presentation))
            self.assertNotIn('secrets.', json.dumps([data_setup, presentation]))
        gate = next(s for s in protected['steps'] if s.get('id') == 'preparation')
        self.assertEqual(gate['timeout-minutes'], 5)
        self.assertIn('benchmark_native.py prepare', gate['run'])
        self.assertIn('skill_orchestration.py guard', gate['run'])

    def test_contract_discovery_keeps_tests_outside_the_released_owners(self):
        from test_evaluation_contracts import contract_suite, scanner_suite

        class Test(unittest.TestCase):
            def runTest(self):
                pass

        identities = ['test_skill_review.ReviewTests.test_review', 'test_skill_report.ReportTests.test_deterministic',
                      'test_historical_review_replay.HistoricalReviewReplayTests.test_saved_bytes',
                      'test_skill_analysis.AnalysisTests.test_pinned_environment',
                      'test_custom_metrics.CustomMetricTests.test_fixture',
                      'test_scanner_caveats.ScannerCaveatTests.test_retained_adapter_compatibility_contracts',
                      'test_semgrep.SemgrepTests.test_unavailable_scanner_is_incomplete',
                      'test_skillspector.SkillSpectorTests.test_failed_and_unavailable_scanners_cannot_pass',
                      'test_cli.CliTests.test_reports']
        discovered = []
        for identity in identities:
            entry = Test()
            entry.id = lambda value=identity: value
            discovered.append(entry)
        loader = unittest.TestLoader()
        loader.discover = lambda _path: unittest.TestSuite([unittest.TestSuite(discovered)])
        self.assertEqual([case.id() for case in contract_suite(loader)], identities[4:])
        self.assertEqual([case.id() for case in contract_suite(loader, released=True)], [identities[-1]])
        with patch.dict(os.environ, {'SKILL_EVALUATION_KIND': 'scanner-contracts'}), \
                patch('static_evaluator.validate_install') as authenticate, \
                patch.object(loader, 'loadTestsFromNames') as load:
            scanner_suite(loader)
        authenticate.assert_called_once_with(scanner_contracts=True)
        load.assert_called_once_with(('test_scanner_caveats', 'test_semgrep', 'test_skillspector'))

    def test_inference_free_jobs_use_the_released_data_host(self):
        planner = yaml.safe_load((ROOT / orchestration.WORKFLOW).read_text())
        benchmark = yaml.safe_load((ROOT / orchestration.BENCHMARK).read_text())
        for jobs, name, command in ((planner['jobs'], 'plan', 'plan'),
                                    (planner['jobs'], 'dispatch', 'dispatch'),
                                    (benchmark['jobs'], 'context', 'context')):
            steps = jobs[name]['steps']
            setup = next(s for s in steps if 'setup-static-evaluator.sh' in s.get('run', ''))
            self.assertEqual(setup['run'], 'bash .github/scripts/setup-static-evaluator.sh data-host')
            caller = next(s for s in steps if 'skill_orchestration.py ' + command in s.get('run', ''))
            self.assertLess(steps.index(setup), steps.index(caller))
            self.assertIn('"$SKILL_DATA_PYTHON"', caller['run'])
        self.assertFalse(any('setup-skillevaluator.sh reporting' in s.get('run', '')
                             for s in benchmark['jobs']['context']['steps']))

    def test_mutable_history_is_read_after_setup_and_before_consumption(self):
        planner = yaml.safe_load((ROOT / orchestration.WORKFLOW).read_text())
        benchmark = yaml.safe_load((ROOT / orchestration.BENCHMARK).read_text())
        for job in (planner['jobs']['plan'], planner['jobs']['dispatch'], benchmark['jobs']['context'], benchmark['jobs']['evaluate']):
            steps = job['steps']
            history = next(i for i, step in enumerate(steps) if step.get('with', {}).get('ref') == 'gh-pages')
            setups = [i for i, step in enumerate(steps) if 'setup-skillevaluator.sh' in step.get('run', '')
                      or 'setup-static-evaluator.sh' in step.get('run', '')]
            self.assertTrue(setups and all(history > i for i in setups))
            features = [i for i, step in enumerate(steps) if 'test_evaluation_contracts.py' in step.get('run', '')]
            self.assertTrue(all(history > i for i in features))

    def test_usage_conflicts_unknowns_and_cache_accounting(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for folder, tokens in [('a', 100), ('duplicate', 100)]:
                reports.write_json(root / f'codex/with-skill/trials/{folder}/result.json',
                    {'id': 'same', 'agent_result': {'n_input_tokens': tokens, 'n_cache_tokens': 20, 'n_output_tokens': 30}})
            value = reports.usage_observations(root)
            self.assertEqual(value['arms']['with-skill']['fields']['n_input_tokens']['subtotal'], 100)
            self.assertIsNone(value['actual_billed_cost_usd'])
            self.assertIsNone(value['arms']['without-skill']['fields']['cost_usd']['subtotal'])
            reports.write_json(root / 'codex/with-skill/trials/conflict/result.json', {'id': 'same', 'agent_result': {'n_input_tokens': 101}})
            value = reports.usage_observations(root)['arms']['with-skill']
            self.assertEqual(value['conflicting_trials'], 1)
            self.assertIsNone(value['fields']['n_input_tokens']['subtotal'])

    def test_operation_cli_preserves_unknown_usage_and_measured_duration(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); output = root / 'operation.json'
            env = {'GITHUB_WORKSPACE': str(ROOT), 'GITHUB_RUN_ID': '90', 'GITHUB_RUN_ATTEMPT': '1',
                   'GITHUB_SHA': 'a' * 40, 'INFERENCE_STARTED': '100', 'INFERENCE_FINISHED': '145'}
            with patch.dict(os.environ, env), patch.object(sys, 'argv', ['skill_reports.py', 'operation', str(root),
                                                  'podman', 'standard', 'skipped', str(output)]):
                reports.main()
            record = pages.parse(output.read_bytes())
            self.assertEqual(record['inference_step_seconds'], 45)
            self.assertIsNone(record['usage'])
            self.assertEqual(record['history_admission'], 'not_established_by_operational_receipt')


if __name__ == '__main__':
    unittest.main()
