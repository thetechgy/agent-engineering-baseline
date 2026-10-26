"""Synthetic native carriers exercise admission; hosted oracle supplies execution evidence.

These freshly staged controls are not retained oracle runs and make no claims of
actual Codex/model execution. No provider, judge or container is invoked here.
"""
import copy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import skill_evidence as evidence
import skill_analysis as analysis
import skill_report as report
import skill_reports as reports
import skill_review as review
import pester_evaluations as pester

ROOT = evidence.ROOT
NAME = pester.NAME


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(evidence.encoded(value))


def synthetic_native(root, *, complete=False):
    from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks
    from harbor.models.task.task import Task
    bundle = pester.stage(ROOT, root / 'bundle' / NAME)
    task_rows = []
    with patch.dict('os.environ', {'SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE': str(root / 'key')}):
        for present in (True, False):
            tasks = stage_native_harbor_tasks(bundle, root / 'tasks' / str(present), with_skill=present, grading_mode='custom_only')
            rows = evidence.capture_custom_tasks(ROOT, NAME, tasks, 'with_skill' if present else 'without_skill')
            for task, row in zip(sorted(tasks), rows):
                assert Task(task).checksum == row['task_checksum'], 'Captured checksum must match pinned Harbor'
            task_rows.extend(rows)
    capture = evidence.custom_capture(ROOT, NAME, bundle, task_rows, purpose='benchmark', attempts=3, agent='codex',
        execution_policy={'environment': 'docker', 'concurrency': 2, 'timeout_multiplier': 2.0, 'stop_on_pass': False})
    native = root / 'native'; run = native / 'results' / NAME / 'synthetic-control'
    write(native / evidence.CUSTOM_CAPTURE, capture)
    config = {'grading': {'mode': 'custom_only'}, 'judge': {'enabled': False},
              'harbor': {'n_attempts': 3, 'stop_on_pass': False}, 'synthetic_control': True}
    write(run / 'run_config.json', config)
    conditions = {}
    for arm in ('with_skill', 'without_skill'):
        side = run / 'codex' / arm.replace('_', '-')
        count = 0; values = []; failures = []
        for task in (r for r in task_rows if r['arm'] == arm):
            case = task['case_id']
            statuses = {
                'pester-001': ('passed', 'failed', 'unsupported'),
                'pester-002': ('invalid', 'timeout', 'infrastructure_error'),
                'pester-003': ('interrupted', 'unknown', 'passed'),
                'pester-004': ('passed', 'passed', 'passed'),
                'pester-005': ('passed', 'failed', 'passed'),
            }[case]
            for ordinal in range(1, 4):
                outcome = 'passed' if complete else statuses[ordinal - 1]
                trial_name = case + '__attempt' + str(ordinal)
                trial = side / 'trials' / trial_name
                measured = outcome in evidence.CUSTOM_MEASURED
                details = {'classification': outcome, 'code': 'evaluated' if measured else 'fixture'}
                metrics = {}
                if measured:
                    count += 1
                    score = float(outcome == 'passed')
                    if case == 'pester-005':
                        metrics = {'negative_control_correct': score}
                        details['negative_control_correct'] = int(score)
                    else:
                        denominator = 4 if case == 'pester-004' else 2
                        metrics = {'pester_reference_pass': 1.0, 'pester_mutation_detection': score, 'pester_test_quality': score}
                        details.update(reference_pass=1, mutants_detected=int(score) * denominator,
                                       mutants_executed=denominator, tests_executed=3,
                                       pester_version='6.2.0', powershell_version='7.6.6')
                numeric = {'overall': float(outcome == 'passed'), **metrics}
                reward = {**numeric, 'entry_id': case, 'trial_id': trial_name, 'has_skill': arm == 'with_skill',
                          'evaluation_status': 'complete' if measured else 'failed', 'custom_details': {'outcome': details}}
                if metrics: reward['custom_metrics'] = metrics; values.append(metrics)
                if not measured: failures.append({'trial': trial_name, 'reason': 'Synthetic unscoreable carrier'})
                write(trial / 'reward.json', reward)
                write(trial / 'result.json', {'id': 'id-' + trial_name, 'trial_name': trial_name, 'task_name': case,
                    'task_checksum': task['task_checksum'], 'config': {'task': {'path': '/tasks/' + case}, 'agent': {'name': 'codex'}, 'timeout_multiplier': 2.0,
                               'environment': {'import_path': 'skillevaluator.tier3.harbor.secure_docker_environment:SkillEvaluatorSecureDockerEnvironment'}},
                    'agent_info': {'name': 'codex', 'version': '0.155.1'}, 'verifier_result': {'rewards': numeric},
                    'exception_info': None, 'started_at': '2026-10-26T00:00:00Z', 'finished_at': '2026-10-26T00:00:02Z',
                    'verifier': {'started_at': '2026-10-26T00:00:01Z', 'finished_at': '2026-10-26T00:00:02Z'},
                    'agent_result': {'n_input_tokens': None, 'n_cache_tokens': None, 'n_output_tokens': None}})
        condition = {'execution_status': 'succeeded' if complete else 'failed', 'execution_errors': [] if complete else ['Synthetic unscoreable fixtures'],
                     'expected_attempts': 15, 'scored_attempts': count}
        conditions[arm] = condition
        scores = {key: round(sum(v[key] for v in values if key in v) / sum(key in v for v in values), 4)
                  for key in {key for v in values for key in v}} if complete else {}
        write(side / 'summary.json', {**condition, 'num_trials': count, 'custom_scores': scores, 'pass_at_k': {}, 'trial_failures': failures})
    write(run / 'result.json', {'skill_name': NAME, 'report_status': 'complete' if complete else 'incomplete',
                               'run_config': config, 'metric_set': 'custom-only', 'agents': {'codex': {'conditions': conditions}}, 'synthetic_control': True})
    return native, run


def synthetic_gh_native(root):
    """Pinned collector over synthetic default+custom rewards; no model inference."""
    import gh_evaluations as gh
    from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks
    from skillevaluator.tier3.harbor.collector import collect_harbor_results
    from skillevaluator.tier3.harbor.report_data import build_dataset_snapshot
    from skillevaluator.tier3.dataset_utils import load_dataset_entries
    bundle = gh.stage(ROOT, root / 'bundle/gh')
    ids = sorted(entry['id'] for entry in gh.dataset(ROOT)); rows = []; jobs = root / 'jobs'
    with patch.dict('os.environ', {'SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE': str(root / 'key')}):
        for present in (True, False):
            arm = 'with_skill' if present else 'without_skill'
            tasks = stage_native_harbor_tasks(bundle, root / 'tasks' / str(present), with_skill=present,
                                              grading_mode='default_plus_custom', workspace_mode='group')
            captured = evidence.capture_custom_tasks(ROOT, 'gh', tasks, arm); rows.extend(captured)
            job = jobs / ('gh-codex-with' if present else 'gh-codex-without')
            names = []
            for item in captured:
                name = item['case_id'] + '__attempt1'; names.append(name); trial = job / name
                default = dict.fromkeys(('security', 'skill_execution', 'skill_efficiency', 'accuracy', 'goal_accuracy', 'behavior_check'), 1.0)
                custom = {'gh_' + key: 1.0 for key in evidence.GATE_FIELDS}
                if not present: custom.update(gh_activation=0.0, gh_gate=0.0)
                numeric = {**default, 'overall': 1.0, **custom}
                write(trial / 'verifier/reward.json', numeric)
                write(trial / 'verifier/skill_evaluator_reward.json', {**default, 'overall': 1.0,
                    'metric_set': 'skill-evaluator-default-v2', 'entry_id': item['case_id'], 'has_skill': present,
                    'evaluation_status': 'complete', 'custom_metrics': custom})
                write(trial / 'result.json', {'id': 'id-' + name, 'trial_name': name, 'task_name': item['case_id'],
                    'task_checksum': item['task_checksum'], 'config': {'task': {'path': '/tasks/' + item['case_id']},
                        'agent': {'name': 'codex'}, 'timeout_multiplier': 2.0,
                        'environment': {'import_path': 'skillevaluator.tier3.harbor.secure_docker_environment:SkillEvaluatorSecureDockerEnvironment'}},
                    'agent_info': {'name': 'codex', 'version': '0.155.1'}, 'verifier_result': {'rewards': numeric},
                    'exception_info': None, 'started_at': '2026-10-26T00:00:00Z', 'finished_at': '2026-10-26T00:00:02Z',
                    'verifier': {'started_at': '2026-10-26T00:00:01Z', 'finished_at': '2026-10-26T00:00:02Z'}})
            write(job / 'result.json', {'n_total_trials': len(ids), 'stats': {'n_trials': len(ids), 'n_errors': 0,
                  'evals': {'synthetic__model___tasks': {'n_trials': len(ids), 'n_errors': 0,
                          'reward_stats': {'reward': {'1.0': names}}}}}})
    native = root / 'native'; run = native / 'results/gh/synthetic-gh'
    collected = collect_harbor_results('gh', ['codex'], run, jobs, expected_cases=len(ids), expected_case_ids=ids,
                                      expected_trials=len(ids), agent_models={'codex': {'model': reports.POLICY['model'], 'source': 'synthetic_control'}})
    config = {'grading': {'mode': 'default_plus_custom'},
              'judge': {'model': reports.POLICY['model'], 'provider': 'openai', 'enabled': True},
              'provider': {'name': 'openai', 'model': reports.POLICY['model']},
              'harbor': {'n_attempts': 1, 'n_concurrent': 2, 'timeout_multiplier': 2.0, 'stop_on_pass': False,
                         'environment': {'value': 'docker'}},
              'evaluated_source': {'repository': 'thetechgy/agent-engineering-baseline', 'commit': evidence.git_revision(ROOT)}}
    snapshot = build_dataset_snapshot(load_dataset_entries(bundle / 'evals/evals.json'), evaluator_version='0.3.0')
    write(run / 'dataset_snapshot.json', snapshot)
    write(run / 'run_config.json', config)
    write(run / 'result.json', {**collected, 'skill_name': 'gh', 'report_status': 'complete', 'run_config': config,
        'dataset_digest': snapshot['dataset_digest'], 'dataset_summary': snapshot['dataset_summary']})
    write(native / 'versions.json', {'python': '3.13.17', 'skillevaluator': '0.3.0', 'harbor': '0.13.2',
          'docker_compose': '5.6.1', 'evaluator_revision': reports.POLICY['evaluator_revision']})
    write(native / 'provenance.json', {'schema_version': 1, 'skill': 'gh', 'mode': 'standard',
          'policy': reports.benchmark_policy('gh'), 'revision': evidence.git_revision(ROOT),
          'patch_sha256': evidence.digest_bytes(evidence.read_bytes(ROOT / reports.PATCH)).removeprefix('sha256:')})
    write(native / evidence.CUSTOM_CAPTURE, evidence.custom_capture(ROOT, 'gh', bundle, rows,
        purpose='benchmark', attempts=1, agent='codex', execution_policy={'environment': 'docker',
        'concurrency': 2, 'timeout_multiplier': 2.0, 'stop_on_pass': False},
        numeric_excerpts=evidence.capture_custom_numeric_fields(ROOT, 'gh', jobs, root, rows)))
    return native, run


@unittest.skipUnless(importlib.util.find_spec('skillevaluator'), 'Requires pinned evaluator')
class CustomMetricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = tempfile.TemporaryDirectory(prefix='custom-metric-controls-')
        cls.addClassCleanup(cls.store.cleanup)
        cls.base = Path(cls.store.name)
        for complete in (False, True):
            synthetic_native(cls.base / str(complete), complete=complete)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='custom-metric-case-'); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def native(self, complete=False):
        native = self.root / 'native'
        shutil.copytree(self.base / str(complete) / 'native', native)
        return native, native / 'results' / NAME / 'synthetic-control'

    def normalize(self, complete=False):
        native, run = self.native(complete)
        return native, run, evidence.normalize_behavioral(native, NAME)

    def public_bundle(self, complete=False):
        native, run = self.native(complete)
        public = self.root / 'public'
        reports.public_benchmark(ROOT, native, NAME, 'confirmation', public)
        return native, public

    def test_native_classifications_applicability_and_true_zero(self):
        native, run, value = self.normalize()
        self.assertEqual(value['schema_version'], 2)
        self.assertFalse(value['metrics'])
        self.assertEqual(value['dataset']['owner'], 'overlay')
        self.assertEqual({obs['custom']['outcome'] for obs in value['observations']}, set(evidence.CUSTOM_OUTCOMES))
        for obs in value['observations']:
            for measurement in obs['custom']['measurements']:
                if obs['custom']['outcome'] not in evidence.CUSTOM_MEASURED:
                    self.assertIsNone(measurement['value'])
                if obs['case_id'] == 'pester-005' and 'negative-control' not in measurement['metric_id']:
                    self.assertEqual(measurement['applicability'], 'not_applicable')
                    self.assertIsNone(measurement['value'])
        self.assertTrue(any(m['value'] == 0 for obs in value['observations'] for m in obs['custom']['measurements']))
        self.assertEqual(evidence.project(value), evidence.project(json.loads(evidence.encoded(value)), behavioral_bundle=native))

    def test_complete_population_permits_only_metric_specific_means(self):
        native, run, value = self.normalize(True)
        public = evidence.project(value)
        result = analysis.analyze_custom(public)
        self.assertTrue(result['complete_paired_population'])
        self.assertEqual({m['with_minus_without']['direction'] for m in result['metrics']}, {'zero'})
        self.assertEqual({m['coverage']['with_skill']['expected_applicable'] for m in result['metrics']}, {3, 12})

    def test_incomplete_population_suppresses_all_aggregate_differences(self):
        native, run, value = self.normalize()
        result = analysis.analyze_custom(evidence.project(value))
        self.assertFalse(result['complete_paired_population'])
        self.assertTrue(all(m['with_minus_without'] is None and all(v is None for v in m['arm_means'].values()) for m in result['metrics']))

    def test_public_only_analysis_html_and_review_after_native_removal(self):
        native, public = self.public_bundle()
        captured = analysis.capture_inputs([public]); result = analysis.validate_analysis(None, captured)
        saved = self.root / 'analysis/analysis.json'; write(saved, result)
        rid = next(key for key, row in captured.records.items() if row['kind'] == 'behavioral')
        html = report.render_report(result, captured)
        context = review.prepare([public], saved, NAME, rid)
        shutil.rmtree(native)
        again = analysis.capture_inputs([public])
        self.assertEqual(analysis.validate_analysis(result, again), result)
        self.assertEqual(report.render_report(result, again), html)
        self.assertEqual(review.prepare([public], saved, NAME, rid).value, context.value)
        output = report.generate([public], saved, self.root / 'rendered')
        text = (output / 'report.html').read_text()
        for expected in ('Seeded mutation detection', 'Reference correctness', 'not_applicable', 'unsupported',
                         'Structurally validated reported evidence', 'not independently authenticated', 'not collected in custom-only'):
            self.assertIn(expected, text)
        self.assertNotIn('PESTER_VERIFIER_ONLY_', text)
        from test_skill_report import Document
        document = Document(text)
        self.assertEqual(len(document.ids), len(set(document.ids)))
        self.assertTrue(all(h[1:] in document.ids for h in document.links if h.startswith('#')))

    def test_forged_normalized_record_needs_matching_native_witness(self):
        native, run, value = self.normalize(True)
        forged = copy.deepcopy(value)
        obs = next(row for row in forged['observations'] if row['case_id'] == 'pester-005')
        obs['custom']['outcome'] = 'failed'
        m = next(m for m in obs['custom']['measurements'] if m['status'] == 'measured')
        m['value'] = m['numerator'] = 0
        evidence.validate_evidence(forged)
        with self.assertRaisesRegex(ValueError, 'claims differ'): evidence.project(forged)
        plain = json.loads(evidence.encoded(value))
        with self.assertRaisesRegex(ValueError, 'Retained native'): evidence.project(plain)
        shutil.rmtree(native)
        with self.assertRaises((ValueError, FileNotFoundError)): evidence.project(plain, behavioral_bundle=native)

    def test_public_mutation_cannot_grant_execution_authentication(self):
        native, run, value = self.normalize(True)
        public = evidence.project(value)
        public['custom']['assurance']['execution_authentication'] = 'verified'
        with self.assertRaises(ValueError): evidence.validate_public(public)

    def test_native_tampering_rejects(self):
        changes = ('denominator', 'value', 'definition', 'runtime', 'grader', 'dataset', 'task', 'duplicate', 'arm', 'completion', 'aggregate')
        for change in changes:
            with self.subTest(change=change):
                target = self.root / change; shutil.copytree(self.base / 'True/native', target)
                run = target / 'results' / NAME / 'synthetic-control'
                reward_path = next(run.glob('codex/with-skill/trials/pester-001*/reward.json'))
                reward = evidence.read_json(reward_path)
                capture = evidence.read_json(target / evidence.CUSTOM_CAPTURE)
                if change == 'denominator': reward['custom_details']['outcome']['mutants_executed'] = 0
                elif change == 'value': reward['custom_metrics']['pester_mutation_detection'] = 0.3
                elif change == 'definition': capture['contract_digest'] = evidence.identity('forged')
                elif change == 'runtime': capture['runtime']['pester'] = '6.1.0'
                elif change == 'grader': capture['tasks'][0]['members']['tests/grader.py'] = evidence.identity('forged')
                elif change == 'dataset': capture['authored_digest'] = evidence.identity('changed')
                elif change == 'task': capture['tasks'][0]['task_checksum'] = '0' * 64
                elif change == 'duplicate': capture['tasks'][1] = capture['tasks'][0]
                elif change == 'arm': reward['has_skill'] = False
                elif change == 'completion':
                    path = reward_path.with_name('result.json'); trial = evidence.read_json(path); trial['finished_at'] = None; write(path, trial)
                elif change == 'aggregate':
                    path = run / 'codex/with-skill/summary.json'; summary = evidence.read_json(path); summary['custom_scores']['pester_reference_pass'] = 0; write(path, summary)
                write(reward_path, reward); write(target / evidence.CUSTOM_CAPTURE, capture)
                with self.assertRaises((ValueError, KeyError)): evidence.normalize_behavioral(target, NAME)

    def test_unknown_metric_and_public_arithmetic_fail_closed(self):
        native, run, value = self.normalize(True)
        for change in ('namespace', 'definition', 'arithmetic', 'applicability', 'zero-denominator'):
            with self.subTest(change=change):
                data = copy.deepcopy(evidence.project(value)); obs = data['observations'][0]
                m = next(m for m in obs['custom']['measurements'] if m['status'] == 'measured')
                if change == 'namespace': m['metric_id'] = 'unknown.metric.v1'
                elif change == 'definition': data['custom']['definitions'][0]['definition'] = 'forged'
                elif change == 'arithmetic': m['value'] = 0.25
                elif change == 'applicability': m['applicability'] = 'not_applicable'
                else: m['denominator'] = 0
                with self.assertRaises(ValueError): evidence.validate_public(data)

    def test_gh_default_plus_custom_native_admission_preserves_routing_and_gate_semantics(self):
        native, run = synthetic_gh_native(self.root)
        data = evidence.normalize_behavioral(native, 'gh')
        public = evidence.project(data)
        evidence.validate_public(public)
        self.assertEqual(len(public['metrics']), 4)
        for obs in public['observations']:
            if obs['arm'] == 'without_skill':
                values = {m['metric_id']: m['value'] for m in obs['custom']['measurements']}
                self.assertEqual(values['gh.activation.v1'], 0)
                self.assertEqual(values['gh.gate.v1'], 0)
                self.assertEqual(values['gh.task.v1'], 1)
        result = analysis.behavioral_result(evidence.identity(public), public, analysis.analyze_cases(public, analysis.case_index(public)))
        self.assertFalse(result['gates']['failed'])
        self.assertEqual(result['gates']['passed_observations'], 24)
        import gh_evaluations as gh
        capture = evidence.read_json(native / evidence.CUSTOM_CAPTURE)
        excerpts = evidence.custom_numeric_excerpts(capture, evidence.custom_contract('gh')[1])
        self.assertEqual(len(gh.deterministic_gate(run, sorted(public['dataset']['case_ids']), 1, numeric_excerpts=excerpts)), 48)
        output = self.root / 'public-gh'
        reports.public_benchmark(ROOT, native, 'gh', 'standard', output)
        captured = analysis.capture_inputs([output]); checked = analysis.validate_analysis(None, captured)
        saved = self.root / 'gh-analysis/analysis.json'; write(saved, checked)
        review.prepare([output], saved, 'gh', evidence.identity(public))
        with self.assertRaises(ValueError):
            path = next(run.glob('codex/with-skill/trials/*/reward.json'))
            payload = evidence.read_json(path); payload['custom_metrics']['gh_authorization'] = 0; payload['custom_metrics']['gh_gate'] = 0; write(path, payload)
            import gh_evaluations as gh
            gh.deterministic_gate(run, sorted(public['dataset']['case_ids']), 1)

    def test_missing_retained_results_stay_visible_and_suppress_comparison(self):
        native, run = self.native(True)
        path = next(run.glob('codex/with-skill/trials/pester-001*/result.json'))
        shutil.rmtree(path.parent)
        data = evidence.normalize_behavioral(native, NAME)
        self.assertIn('case_details_missing', data['availability']['reasons'])
        self.assertIn('coverage_missing', data['availability']['reasons'])
        result = analysis.analyze_custom(evidence.project(data))
        self.assertEqual(result['outcomes']['with_skill']['missing'], 1)
        self.assertTrue(all(m['with_minus_without'] is None for m in result['metrics']))

    def test_empty_results_and_inventory_only_are_not_zero_quality(self):
        native, run = self.native(True)
        payload = evidence.read_json(run / 'result.json'); payload['report_status'] = 'incomplete'
        for arm in ('with_skill', 'without_skill'):
            directory = run / 'codex' / arm.replace('_', '-')
            shutil.rmtree(directory / 'trials')
            condition = {'execution_status': 'failed', 'execution_errors': ['Synthetic missing execution'], 'expected_attempts': 15, 'scored_attempts': 0}
            payload['agents']['codex']['conditions'][arm] = condition
            write(directory / 'summary.json', {**condition, 'num_trials': 0, 'custom_scores': {}, 'pass_at_k': {}})
        write(run / 'result.json', payload)
        value = evidence.project(evidence.normalize_behavioral(native, NAME))
        self.assertFalse(value['observations'])
        custom = analysis.analyze_custom(value)
        self.assertEqual(custom['outcomes']['with_skill']['missing'], 15)
        self.assertTrue(all(m['arm_means']['with_skill'] is None for m in custom['metrics']))
        inventory_only = self.root / 'inventory-only'; write(inventory_only / 'inventory.json', evidence.inventory(ROOT))
        captured = analysis.capture_inputs([inventory_only]); result = analysis.validate_analysis(None, captured)
        html = report.render_report(result, captured).decode()
        self.assertIn('Configured suite without measurement', html)
        self.assertFalse(next(s for s in result['skills'] if s['skill'] == NAME)['behavioral_results'])

    def test_missing_capture_does_not_retroactively_admit_native_pilot(self):
        native, run = self.native()
        (native / evidence.CUSTOM_CAPTURE).unlink()
        with self.assertRaises((ValueError, KeyError)): evidence.normalize_behavioral(native, NAME)

    def test_duplicate_mismatched_or_unknown_attempt_identities_reject(self):
        for change in ('id', 'case', 'ordinal', 'reordered-capture'):
            with self.subTest(change=change):
                target = self.root / change; shutil.copytree(self.base / 'True/native', target)
                run = target / 'results' / NAME / 'synthetic-control'
                paths = sorted(run.glob('codex/with-skill/trials/pester-001*/result.json'))
                data = evidence.read_json(paths[1])
                if change == 'id': data['id'] = evidence.read_json(paths[0])['id']; write(paths[1], data)
                elif change == 'case': data['task_name'] = 'pester-005'; data['config']['task']['path'] = '/tasks/pester-005'; write(paths[1], data)
                elif change == 'ordinal':
                    destination = paths[1].parent.with_name('pester-001__attempt1-copy')
                    paths[1].parent.rename(destination)
                    data['trial_name'] = destination.name; write(destination / 'result.json', data)
                    reward = evidence.read_json(destination / 'reward.json'); reward['trial_id'] = destination.name; write(destination / 'reward.json', reward)
                else:
                    capture = evidence.read_json(target / evidence.CUSTOM_CAPTURE); capture['tasks'].reverse(); write(target / evidence.CUSTOM_CAPTURE, capture)
                with self.assertRaises((ValueError, KeyError)): evidence.normalize_behavioral(target, NAME)

    def test_reordered_directory_enumeration_does_not_reassign_attempts(self):
        native, run = self.native(True)
        original = evidence.project(evidence.normalize_behavioral(native, NAME))
        scan = evidence.safe_tree
        def reversed_scan(*args, **kwargs): return list(reversed(scan(*args, **kwargs)))
        with patch.object(evidence, 'safe_tree', side_effect=reversed_scan):
            reordered = evidence.project(evidence.normalize_behavioral(native, NAME))
        self.assertEqual(original, reordered)

    def test_known_original_unavailability_preserves_reported_measurements(self):
        native, public = self.public_bundle(True)
        path = next(public.glob('skills/*/behavioral/*/public-report.json'))
        data = evidence.read_json(path)
        values = copy.deepcopy([obs['custom']['measurements'] for obs in data['observations']])
        for ref in data['references']: ref['availability'] = 'unavailable'
        data['availability'].update(status='incomplete', reasons=['reference_unavailable'])
        write(path, data); shutil.rmtree(native)
        captured = analysis.capture_inputs([public]); result = analysis.validate_analysis(None, captured)
        record = next(r for r in captured.records.values() if r['kind'] == 'behavioral')
        self.assertEqual([obs['custom']['measurements'] for obs in record['observations']], values)
        self.assertIn('Original support is unavailable', report.render_report(result, captured).decode())
        rid = evidence.identity(record); saved = self.root / 'analysis/analysis.json'; write(saved, result)
        context = review.prepare([public], saved, NAME, rid)
        self.assertEqual(context.value['analysis']['behavioral_results'][0]['custom']['assurance']['execution_authentication'], 'not_established')

    def test_changed_runtime_policy_and_unknown_namespace_fail_admission(self):
        for change in ('policy', 'agent', 'evaluator', 'namespace', 'unscoreable-zero', 'cache'):
            with self.subTest(change=change):
                target = self.root / change; shutil.copytree(self.base / 'True/native', target)
                run = target / 'results' / NAME / 'synthetic-control'
                path = next(run.glob('codex/with-skill/trials/pester-001*/result.json'))
                trial = evidence.read_json(path); reward_path = path.with_name('reward.json'); reward = evidence.read_json(reward_path)
                capture = evidence.read_json(target / evidence.CUSTOM_CAPTURE)
                if change == 'policy': trial['config']['timeout_multiplier'] = 1.0
                elif change == 'agent': trial['agent_info']['version'] = '0.155.0'
                elif change == 'evaluator': capture['evaluator_version'] = '0.6.0'
                elif change == 'namespace': reward['custom_metrics']['forged_metric'] = 1
                elif change == 'unscoreable-zero':
                    reward['evaluation_status'] = 'failed'; reward['custom_details']['outcome']['classification'] = 'unsupported'
                else: trial['agent_result'].update(n_input_tokens=1, n_cache_tokens=2)
                write(path, trial); write(reward_path, reward); write(target / evidence.CUSTOM_CAPTURE, capture)
                with self.assertRaises((ValueError, KeyError)): evidence.normalize_behavioral(target, NAME)

    def test_native_input_guards_survive_projection_and_reject_late_tampering(self):
        native, run, record = self.normalize(True)
        public = evidence.project(record)
        path = next(run.glob('codex/with-skill/trials/*/reward.json'))
        raw = path.read_bytes(); path.write_bytes(raw + b' ')
        with self.assertRaises(ValueError):
            evidence.write_outputs({'public-report.json': public}, self.root / 'rejected', ROOT, native,
                                   input_guards=evidence.record_guards(public))
        self.assertFalse((self.root / 'rejected').exists())

    def test_invalid_public_bundle_and_saved_analysis_are_rejected(self):
        native, public = self.public_bundle(True)
        captured = analysis.capture_inputs([public]); result = analysis.validate_analysis(None, captured)
        modified = copy.deepcopy(result)
        run = next(s for s in modified['skills'] if s['skill'] == NAME)['behavioral_results'][0]
        run['custom']['metrics'][0]['with_minus_without']['value'] = '0.5'
        with self.assertRaises(ValueError): analysis.validate_analysis(modified, captured)
        extra = public / 'protected-fixture.txt'; extra.write_text('not a public member')
        with self.assertRaises(ValueError): analysis.capture_inputs([public])

    def test_registered_old_profile_remains_interpretable_when_active_profile_changes(self):
        native, run, value = self.normalize(True)
        public = evidence.project(value)
        registry = evidence.custom_registry()
        old_id = registry['active_profiles'][NAME]
        registry['profiles']['pester-future-control-v2'] = copy.deepcopy(registry['profiles'][old_id])
        registry['profiles']['pester-future-control-v2']['id'] = 'pester-future-control-v2'
        registry['active_profiles'][NAME] = 'pester-future-control-v2'
        with patch.object(evidence, 'custom_registry', return_value=registry):
            evidence.validate_public(public)
            self.assertEqual(public['custom']['profile_id'], old_id)
            self.assertNotEqual(evidence.custom_contract(NAME)[2], public['custom']['contract_digest'])

    def test_native_exception_classification_and_missing_reward_do_not_become_zero(self):
        native, run = self.native()
        path = next(run.glob('codex/with-skill/trials/pester-003__attempt2/result.json'))
        value = evidence.read_json(path); value['exception_info'] = {'exception_type': 'VerifierTimeoutError'}; write(path, value)
        public = evidence.project(evidence.normalize_behavioral(native, NAME))
        row = next(obs for obs in public['observations'] if obs['case_id'] == 'pester-003' and obs['arm'] == 'with_skill' and obs['attempt'] == 2)
        self.assertEqual(row['custom']['outcome'], 'timeout')
        self.assertTrue(all(m['value'] is None for m in row['custom']['measurements']))
        (run / 'codex/with-skill/trials/pester-001__attempt1/reward.json').unlink()
        incomplete = evidence.project(evidence.normalize_behavioral(native, NAME))
        self.assertIn('case_details_missing', incomplete['availability']['reasons'])

    def test_dataset_identity_excludes_target_revision_and_staging_nonce(self):
        capture = evidence.read_json(self.base / 'True/native' / evidence.CUSTOM_CAPTURE)
        before = evidence.custom_staged_inputs(capture['tasks'], capture['purpose'])
        changed = copy.deepcopy(capture['tasks'])
        for task in changed:
            task['members']['tests/entry.json'] = evidence.identity('different staging metadata')
            for key in list(task['members']):
                if key.startswith('environment/skills/'):
                    task['members'][key] = evidence.identity('candidate skill revision')
        self.assertEqual(evidence.custom_staged_inputs(changed, capture['purpose']), before)
        changed[0]['members']['environment/input/README.md'] = evidence.identity('changed case input')
        with self.assertRaisesRegex(ValueError, 'input drift'):
            evidence.custom_staged_inputs(changed, capture['purpose'])

    def test_custom_record_saved_review_uses_new_frozen_public_only_profile(self):
        import skill_report_reviews as attachments
        from test_skill_review import judgment, CONFIG
        native, public = self.public_bundle()
        shutil.rmtree(native)
        captured = analysis.capture_inputs([public])
        saved = self.root / 'analysis/analysis.json'
        write(saved, analysis.validate_analysis(None, captured))
        rid = next(key for key, row in captured.records.items() if row['kind'] == 'behavioral')
        context = review.prepare([public], saved, NAME, rid)
        value = review.make_review(judgment(context), context, review.ModelConfig(**CONFIG),
            review.Usage(preflight_input_tokens=1000, input_tokens=1000, output_tokens=500, total_tokens=1500))
        document = self.root / 'saved/skill-review.json'; write(document, value)
        markdown = review.render_review(value, context)
        document.with_suffix('.md').write_bytes(markdown)
        spec = {'schema_version': 1, 'profile': 'custom-metrics-v2', 'tooling': str(ROOT),
            'skill': NAME, 'record_id': rid, 'review': str(document),
            'review_digest': evidence.digest_bytes(document.read_bytes()),
            'markdown_digest': evidence.digest_bytes(markdown), 'inputs': [str(public)],
            'analysis': str(saved), 'source': None, 'support': None, 'selection': None, 'assessments': []}
        attachment = self.root / 'attachment.json'; write(attachment, spec)
        validated = attachments.load([attachment], captured)
        html = report.render_report(analysis.validate_analysis(None, captured), captured, reviews=validated)
        self.assertIn(b'Seeded mutation detection', html)
        self.assertIn(b'No recommendations supplied', html)

    def test_ai_numeric_gate_exception_does_not_allow_credentials_or_other_locations(self):
        for value in ('secret', '<redacted>', True, 2):
            with self.subTest(value=value), self.assertRaises(ValueError):
                review.screen_payload({'records': {'id': {'observations': [
                    {'deterministic_scores': {'authorization': value}}]}}})
        with self.assertRaises(ValueError):
            review.screen_payload({'authorization': 1})

    def test_history_and_custom_cross_run_stay_disabled(self):
        native, public = self.public_bundle(True)
        captured = analysis.capture_inputs([public])
        original = next(record for record in captured.records.values() if record['kind'] == 'behavioral')
        second = copy.deepcopy(original); second['run_id'] = 'synthetic-second'
        a, b = evidence.identity(original), evidence.identity(second)
        records = {a: original, b: second}
        results = {key: analysis.behavioral_result(key, record, analysis.analyze_cases(record, analysis.case_index(record))) for key, record in records.items()}
        conditions = {key: analysis.condition_identity(record) for key, record in records.items()}
        comparison = analysis.cross_run(a, b, records, results, conditions)
        self.assertEqual(comparison['classification'], 'custom_comparison_deferred')
        self.assertTrue(all(m['right_minus_left'] is None for m in comparison['native_metrics']))
        with self.assertRaisesRegex(ValueError, 'cannot publish history'): reports.publish_metrics(ROOT, self.root, NAME)
        with self.assertRaisesRegex(ValueError, 'cannot publish history'): reports.validate_metrics({}, ROOT, NAME, '0' * 40)


if __name__ == '__main__': unittest.main()
