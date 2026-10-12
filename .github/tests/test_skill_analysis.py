"""Offline production CLI, retained historical evidence, and synthetic comparison controls."""

import copy
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from io import StringIO
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import skill_analysis as analysis
import skill_evidence as evidence

REPO = evidence.ROOT
FIXTURES = Path(__file__).parent / 'fixtures/skill_evidence'
CLOCK = datetime(2026, 10, 12, tzinfo=timezone.utc)


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(evidence.encoded(data))


def configuration(name, cases=('1',), source=None):
    return {'source': source or synthetic_source(name), 'deployment': None,
            'suite': {'owner': 'local', 'path': f'.apm/skills/{name}/evals/evals.json',
                      'authored_digest': evidence.identity(list(cases)), 'case_ids': sorted(cases), 'status': 'configured'},
            'behavioral_status': 'configured',
            'measurement': {'status': 'unavailable', 'reasons': ['results_not_supplied']}}


def synthetic_source(name):
    # Synthetic control identities, never claims about execution or actual skill bytes.
    content = evidence.content([{'member': 'SKILL.md', 'digest': evidence.identity(name)}], 'synthetic')
    return evidence.source(name, 'local', 'example/controls', 'a' * 40, '.apm/skills/' + name, content)


def synthetic(name='alpha', run='run-a', maximum=1, scores=(0.8, 0.6), cases=('1',)):
    """Explicitly synthetic, fully recorded control for comparison and arithmetic tests."""
    fields = {**evidence.reports.POLICY, 'workspace_mode': 'isolated'}
    policy = evidence.make_policy(fields, evidence.identity('synthetic-patch'), 'skill-evaluator-default-v2',
        {'model': 'synthetic-judge', 'provider': 'synthetic', 'enabled': True},
        {'mode': 'confirmation' if maximum == 3 else 'standard', 'maximum': maximum,
         'stop_on_pass': False, 'pass_threshold': 0.5}, 'synthetic')
    value = evidence.evidence(name, 'behavioral', cases, synthetic_source(name), policy)
    value['run_id'] = run
    value['dataset'].update(owner='local', authored_digest=evidence.identity('synthetic-authored'),
        staged_digest=evidence.identity('synthetic-staged'), staged_algorithm='skill-evaluator-dataset-snapshot/1',
        authored_provenance='synthetic', staged_provenance='synthetic')
    value['availability'] = {'status': 'complete', 'reasons': [], 'provenance': 'synthetic'}
    value['metrics'] = [{'name': name, 'unit': 'score', 'value': score}
                        for name, score in zip(evidence.reports.METRICS, (0.2, 0.8, 0.9, 0.7))]
    for arm, score in zip(('with_skill', 'without_skill'), scores):
        condition = evidence.condition(arm == 'with_skill', 'synthetic', 'isolated',
            instructions=evidence.identity('synthetic-instructions'), build=evidence.identity('synthetic-build'),
            fixture=evidence.identity('synthetic-fixture'), execution={'environment': 'docker',
            'base_image_mode': 'synthetic', 'task_source': None, 'authorization_policy': None, 'fixture_boundary': None})
        value['arms'].append({'name': arm, 'condition': condition, 'coverage': {}, 'execution_status': 'succeeded',
                             'execution_error_count': 0, 'rubric': {}})
        for case in sorted(cases):
            for attempt in range(1, maximum + 1):
                ref = {'artifact_id': 'synthetic-' + run, 'artifact_digest': None,
                       'member': f'results/{name}/{run}/codex/{arm}/case-{case}-{attempt}.json', 'locator': [],
                       'digest': evidence.identity([run, arm, case, attempt]), 'provenance': 'synthetic', 'availability': 'available'}
                ref['id'] = evidence.identity({key: ref[key] for key in ('artifact_id', 'member', 'locator', 'digest')})
                value['references'].append(ref)
                value['observations'].append({'id': evidence.identity([run, arm, case, attempt]), 'arm': arm,
                    'case_id': case, 'attempt': attempt, 'score': score,
                    'scores': {key: score if key == 'overall' else None for key in evidence.SCORE_FIELDS},
                    'rubric_pass': score >= 0.5, 'deterministic_gate': None,
                    'deterministic_scores': dict.fromkeys(evidence.GATE_FIELDS), 'references': [ref['id']]})
    reconcile(value)
    return value


def reconcile(value, *, partial=False):
    """Mutated synthetic controls retain the public producer's coverage/rubric contract."""
    maximum = value['policy']['attempts']['maximum']
    for arm in value['arms']:
        obs = [row for row in value['observations'] if row['arm'] == arm['name']]
        total = len(value['dataset']['case_ids'])
        arm['coverage'] = {'expected_cases': total, 'expected_attempts': total * maximum if maximum else None,
                           'recorded_attempts': len(obs), 'scored_attempts': sum(row['score'] is not None for row in obs),
                           'unscored_attempts': sum(row['score'] is None for row in obs),
                           'case_details': 'partial' if partial else 'complete'}
        arm['rubric'] = {'threshold': 0.5, 'passed_cases': len({row['case_id'] for row in obs if row['rubric_pass']}),
                         'total_cases': total}
        if partial: arm['execution_status'] = 'incomplete'
    if partial or any(row['score'] is None for row in value['observations']):
        value['availability'].update(status='incomplete', reasons=['coverage_missing', 'execution_incomplete'] +
                                    (['case_details_missing'] if partial else []))
    if evidence.behavioral_identity_missing(value) or any(row['attempt'] is None for row in value['observations']):
        value['availability']['status'] = 'incomplete'
        value['availability']['reasons'].append('metadata_missing')
    evidence.validate_public(value)


class AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.object(evidence, 'utc_now', return_value=CLOCK):
            cls.historical = evidence.project(evidence.normalize_behavioral(FIXTURES / 'podman-native', 'podman'))
            cls.static = evidence.project(evidence.normalize_static(FIXTURES / 'static-synthetic', 'podman'))
        cls.gh = evidence.read_json(FIXTURES / 'gh-no-model.json')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        clock = patch.object(evidence, 'utc_now', return_value=CLOCK)
        clock.start(); self.addCleanup(clock.stop)

    def bundle(self, name, reports=(), configs=None, flat=False):
        root = self.root / name
        if configs is None:
            configs = [configuration(value['source']['skill_id'], value['dataset']['case_ids'], value['source'])
                       for value in reports]
            configs = list({row['source']['skill_id']: row for row in configs}.values())
        inventory = {'schema_version': 1, 'kind': 'inventory',
                     'skills': sorted(configs, key=lambda row: row['source']['skill_id'])}
        write(root / ('inventory.json' if flat else 'inventory/inventory.json'), inventory)
        for record in reports:
            tail = 'static' if record['kind'] == 'static' else 'behavioral/' + str(record['run_id'])
            member = 'public-report.json' if flat else f"skills/{record['source']['skill_id']}/{tail}/public-report.json"
            write(root / member, record)
        return root

    def analyze(self, *roots):
        captured = analysis.capture_inputs(roots)
        result = analysis.build_analysis(captured)
        analysis.validate_analysis(result, captured)
        return result, captured

    def result(self, record):
        value, _ = self.analyze(self.bundle('input', [record]))
        return value['skills'][0]['behavioral_results'][0]

    def test_pinned_environment(self):
        self.assertEqual(importlib.metadata.version('skillevaluator'), '0.3.0')
        self.assertEqual(sys.version_info[:2], (3, 13))

    def test_historical_native_metrics_regressions_and_denominators(self):
        configs = [configuration('podman', self.historical['dataset']['case_ids']),
                   configuration('gh', self.gh['dataset']['case_ids'], self.gh['source'])]
        result, captured = self.analyze(self.bundle('historic', [self.historical], configs))
        run = next(row for row in result['skills'] if row['skill'] == 'podman')['behavioral_results'][0]
        self.assertEqual({row['name']: row['value'] for row in run['native_metrics']}, evidence.REVIEWED_METRIC_VALUES)
        self.assertEqual(run['case_summary']['matched_cases'], 10)
        self.assertEqual(run['case_summary']['scored_observations'], 20)
        self.assertEqual([arm['rubric']['passed_cases'] for arm in run['arms']], [10, 8])
        self.assertEqual([arm['rubric']['total_cases'] for arm in run['arms']], [10, 10])
        regressions = {row['case_id']: row['with_minus_without']['display']
                       for row in run['case_summary']['cases'] if row['with_minus_without']['direction'] == 'negative'}
        self.assertEqual(regressions, {'2': '-0.0346', '7': '-0.0134'})
        from decimal import Decimal
        self.assertEqual(sum(Decimal(row['with_minus_without']['value']) for row in run['case_summary']['cases']) / 10,
                         Decimal('0.12075'))
        self.assertEqual(run['native_metrics'][0]['value'], 0.1207)
        markdown = analysis.render_summary(result).decode()
        for text in ('+0.1207', '-0.0346', '-0.0134', '10 matched cases', '20 scored trials', '10/10', '8/10', '24 configured cases'):
            self.assertIn(text, markdown)
        self.assertIn('No supplied model-backed measurement', markdown)
        self.assertNotIn('manifest', run['source'])
        self.assertNotIn('references', run)
        self.assertNotIn(str(self.root), evidence.encoded(result).decode())
        self.assertTrue(captured.records)

    def test_complete_repeated_arm_means_not_trial_pairing(self):
        record = synthetic(maximum=3)
        for obs in record['observations']:
            if obs['arm'] == 'with_skill':
                obs['score'] = obs['scores']['overall'] = [0.9, 0.6, 0.3][obs['attempt'] - 1]
                obs['rubric_pass'] = obs['score'] >= 0.5
        reconcile(record)
        case = self.result(record)['case_summary']['cases'][0]
        self.assertEqual(case['arm_means']['with_skill']['display'], '0.6000')
        self.assertEqual(case['with_minus_without']['display'], '0.0000')
        self.assertEqual(len(case['observation_ids']['with_skill']), 3)

    def test_missing_attempt_score_unknown_maximum_and_adaptive_stop(self):
        for defect in ('attempt', 'score', 'maximum', 'adaptive', 'unknown_stop', 'ordinal'):
            with self.subTest(defect=defect):
                record = synthetic(maximum=3)
                if defect == 'attempt': record['observations'].pop()
                if defect == 'score':
                    record['observations'][0].update(score=None, rubric_pass=None)
                    record['observations'][0]['scores']['overall'] = None
                if defect == 'maximum': record['policy']['attempts']['maximum'] = None
                if defect in ('adaptive', 'unknown_stop'):
                    stop = True if defect == 'adaptive' else None
                    record['policy']['attempts']['stop_on_pass'] = stop
                    record['policy']['fields']['stop_on_pass'] = stop
                if defect == 'ordinal': record['observations'][0]['attempt'] = None
                record['policy']['id'] = evidence.identity({key: record['policy'][key] for key in
                    ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
                reconcile(record, partial=True)
                root = self.bundle(defect, [record])
                result, _ = self.analyze(root)
                case = result['skills'][0]['behavioral_results'][0]['case_summary']['cases'][0]
                self.assertIsNone(case['with_minus_without'])
                self.assertTrue(case['unavailable_reasons'])

    def test_partial_run_preserves_complete_cases(self):
        record = synthetic(cases=('1', '2'))
        record['observations'] = [obs for obs in record['observations'] if not
                                  (obs['arm'] == 'without_skill' and obs['case_id'] == '2')]
        reconcile(record, partial=True)
        run = self.result(record)
        self.assertEqual(run['case_summary']['matched_cases'], 1)
        self.assertEqual(run['availability']['status'], 'incomplete')
        self.assertEqual(run['case_summary']['cases'][0]['with_minus_without']['display'], '0.2000')

    def test_direction_survives_display_rounding(self):
        record = synthetic(scores=(0.60000001, 0.60000002))
        case = self.result(record)['case_summary']['cases'][0]
        self.assertEqual(case['with_minus_without']['display'], '-0.0000')
        self.assertEqual(case['with_minus_without']['direction'], 'negative')

    def test_smallest_native_score_contribution_survives_repeated_mean(self):
        record = synthetic(maximum=3)
        for obs in record['observations']:
            score = 1.0 if obs['attempt'] == 1 else 5e-324 if obs['arm'] == 'without_skill' and obs['attempt'] == 2 else 0
            obs.update(score=score, rubric_pass=score >= 0.5)
            obs['scores']['overall'] = score
        reconcile(record)
        delta = self.result(record)['case_summary']['cases'][0]['with_minus_without']
        self.assertEqual(delta['direction'], 'negative')
        self.assertEqual(delta['display'], '-0.0000')

    def test_failed_and_unknown_gates_separate_from_rubric(self):
        record = synthetic(name='gh')
        obs = record['observations'][0]
        obs['deterministic_scores'] = dict.fromkeys(evidence.GATE_FIELDS, 1)
        obs['deterministic_scores'].update(authorization=0, recovery=0, gate=0)
        obs['deterministic_gate'] = 0
        run = self.result(record)
        self.assertEqual(run['arms'][0]['rubric']['passed_cases'], 1)
        self.assertEqual(run['gates']['unknown_observations'], 1)
        self.assertEqual(run['gates']['failed'][0]['components'], ['authorization', 'recovery'])
        self.assertEqual(run['gates']['failed'][0]['observation_id'], obs['id'])

    def test_inventory_only_configured_unmeasured_and_static_are_separate(self):
        root = self.bundle('static', [self.static], [configuration('podman'), configuration('gh', self.gh['dataset']['case_ids'])])
        result, _ = self.analyze(root)
        podman = next(row for row in result['skills'] if row['skill'] == 'podman')
        self.assertFalse(podman['behavioral_results'])
        self.assertEqual(len(podman['static_results']), 1)
        self.assertEqual(len(podman['static_results'][0]['detailed_findings']), 1)
        self.assertTrue(any(row['kind'] == 'incomplete_scans' for row in result['findings']))
        inv_result, _ = self.analyze(self.bundle('inv', configs=[configuration('alpha')]))
        self.assertEqual(inv_result['skills'][0]['comparison_status'], 'insufficient_run_evidence')
        self.assertTrue(any(row['kind'] == 'configured_unmeasured' for row in inv_result['findings']))

    def test_differing_snapshots_and_historical_revisions_remain_separate(self):
        old = self.bundle('old', [self.historical])
        config = configuration('podman'); config['source']['revision'] = 'b' * 40
        new = self.bundle('new', configs=[config])
        result, _ = self.analyze(old, new)
        skill = result['skills'][0]
        self.assertEqual(len(skill['configurations']), 2)
        self.assertEqual(len(skill['behavioral_results']), 1)
        self.assertEqual(skill['behavioral_results'][0]['source']['revision'], self.historical['source']['revision'])

    def pair(self, mutation=None, *, name='alpha'):
        left, right = synthetic(name, 'run-a'), synthetic(name, 'run-b')
        if mutation: mutation(right)
        roots = self.bundle('left-' + name, [left]), self.bundle('right-' + name, [right])
        result, _ = self.analyze(*roots)
        return result['skills'][0]['comparisons'][0]

    def test_controlled_target_revision_is_direct_and_order_is_semantic(self):
        def mutate(record):
            record['source']['revision'] = 'b' * 40
            record['source']['content'] = evidence.content([{'member': 'SKILL.md', 'digest': evidence.identity('new target')}], 'synthetic')
            record['policy']['fields']['upstream_revision'] = 'b' * 40
            record['policy']['id'] = evidence.identity({key: record['policy'][key] for key in
                ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
        pair = self.pair(mutate)
        self.assertEqual(pair['classification'], 'directly_comparable')
        self.assertLess(pair['left_record_id'], pair['right_record_id'])
        self.assertEqual(pair['native_metrics'][0]['right_minus_left']['display'], '0.0000')

    def test_recorded_lineage_required_for_ownership_conversion(self):
        def mutate(record):
            record['source'].update(owner='upstream', repository='example/upstream', source_path='skills/alpha')
        pair = self.pair(mutate)
        self.assertEqual(pair['classification'], 'incompatible_or_unknown')
        with tempfile.TemporaryDirectory() as temp:
            original = self.root; self.root = Path(temp)
            def lineage(record):
                mutate(record)
                record['source']['lineage'] = {'repository': 'example/controls', 'revision': 'a' * 40, 'source_path': '.apm/skills/alpha'}
            self.assertEqual(self.pair(lineage)['classification'], 'directly_comparable')
            self.root = original

    def test_changed_unknown_benchmark_and_coverage_classifications(self):
        mutations = [
            ('incompatible_or_unknown', lambda r: r['dataset'].update(authored_digest=evidence.identity('different suite'))),
            ('incompatible_or_unknown', lambda r: r['policy']['fields'].update(model='changed-model')),
            ('incompatible_or_unknown', lambda r: r['policy']['fields'].update(model=None)),
            ('exploratory', lambda r: r['arms'][0]['condition'].update(instruction_digest=None)),
            ('incompatible_or_unknown', lambda r: r['arms'][0]['condition'].update(fixture_digest=evidence.identity('changed fixture'))),
            ('exploratory', lambda r: (r['observations'].pop(), reconcile(r, partial=True))),
        ]
        for index, (expected, mutate) in enumerate(mutations):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as temp:
                self.root = Path(temp)
                def mutation(record):
                    mutate(record)
                    record['policy']['id'] = evidence.identity({key: record['policy'][key] for key in
                        ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
                    for arm in record['arms']:
                        arm['condition']['id'] = evidence.identity({k: v for k, v in arm['condition'].items() if k != 'id'})
                pair = self.pair(mutation)
                self.assertEqual(pair['classification'], expected)
                self.assertTrue(all(row['right_minus_left'] is None for row in pair['native_metrics']))
                self.assertTrue(all(all(delta is None for delta in row['right_minus_left'].values()) for row in pair['cases']))

    def test_gh_missing_custom_grader_identity_blocks_direct(self):
        left, right = synthetic('gh', 'run-a'), synthetic('gh', 'run-b')
        for record in (left, right):
            record['policy']['fields']['grading'] = 'gh-custom-v1'
            record['policy']['id'] = evidence.identity({key: record['policy'][key] for key in
                ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
        result, _ = self.analyze(self.bundle('l', [left]), self.bundle('r', [right]))
        pair = result['skills'][0]['comparisons'][0]
        self.assertEqual(pair['classification'], 'incompatible_or_unknown')
        self.assertIn('unknown:custom_grader.identity', pair['reasons'])
        # A default label on gh cannot stand in for the absent custom-grader identity.
        for record in (left, right):
            record['policy']['fields']['grading'] = 'default'
            record['policy']['id'] = evidence.identity({key: record['policy'][key] for key in
                ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
        default, _ = self.analyze(self.bundle('default-l', [left]), self.bundle('default-r', [right]))
        self.assertIn('unknown:custom_grader.identity', default['skills'][0]['comparisons'][0]['reasons'])

    def test_direct_differences_are_right_minus_left_and_findings_link_originals(self):
        left = synthetic(run='run-a', scores=(0.8, 0.6))
        right = synthetic(run='run-b', scores=(0.7, 0.6))
        right['metrics'][0]['value'] = 0.1
        right['metrics'][1]['value'] = 0.9
        result, captured = self.analyze(self.bundle('pair', [left, right]))
        pair = result['skills'][0]['comparisons'][0]
        self.assertEqual(pair['classification'], 'directly_comparable')
        from decimal import Decimal
        for metric in pair['native_metrics']:
            self.assertEqual(Decimal(metric['right_minus_left']['value']),
                             Decimal(str(metric['right'])) - Decimal(str(metric['left'])))
        row = pair['cases'][0]
        for arm in row['right_minus_left']:
            self.assertEqual(Decimal(row['right_minus_left'][arm]['value']),
                             Decimal(row['right_arm_means'][arm]['value']) - Decimal(row['left_arm_means'][arm]['value']))
        for item in result['findings']:
            linked_records = [captured.records[key] for key in item['record_ids']]
            observations = {obs['id'] for record in linked_records if record['kind'] != 'inventory' for obs in record['observations']}
            references = {ref['id'] for record in linked_records if record['kind'] != 'inventory' for ref in record['references']}
            self.assertLessEqual(set(item['observation_ids']), observations)
            self.assertLessEqual(set(item['reference_ids']), references)
        self.assertTrue(any(item['kind'] == 'run_metric_regression' for item in result['findings']))

    def test_unmeasured_gh_and_recovered_unknown_context_stay_unknown(self):
        root = self.bundle('configured-gh', [self.gh], flat=True)
        result, _ = self.analyze(root)
        run = result['skills'][0]['behavioral_results'][0]
        self.assertFalse(run['measured'])
        self.assertEqual(run['native_metrics'], [])
        self.assertTrue(all(row['with_minus_without'] is None for row in run['case_summary']['cases']))
        self.assertEqual(result['skills'][0]['comparison_status'], 'insufficient_run_evidence')
        recovered = synthetic()
        recovered['policy']['attempts']['maximum'] = None
        recovered['policy']['patch_digest'] = None
        recovered['policy']['fields']['model'] = None
        recovered['policy']['id'] = evidence.identity({key: recovered['policy'][key] for key in
            ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
        reconcile(recovered, partial=True)
        run = self.result(recovered)
        self.assertEqual(run['native_metrics'], recovered['metrics'])
        self.assertIsNone(run['policy']['fields']['model'])
        self.assertIsNone(run['arms'][0]['coverage']['expected_attempts'])
        self.assertIsNone(run['case_summary']['cases'][0]['with_minus_without'])
        zero = synthetic(); zero['observations'] = []; zero['references'] = []; zero['metrics'] = []
        reconcile(zero, partial=True)
        result, _ = self.analyze(self.bundle('zero-execution', [zero]))
        self.assertFalse(result['skills'][0]['behavioral_results'][0]['measured'])
        self.assertTrue(any(item['kind'] == 'incomplete_execution' for item in result['findings']))
        self.assertTrue(any(item['kind'] == 'configured_unmeasured' for item in result['findings']))

    def test_more_than_two_runs_never_enumerate_pairs(self):
        root = self.bundle('many', [synthetic(run='run-' + str(i)) for i in range(3)])
        with patch.object(analysis, 'cross_run', side_effect=AssertionError('must not compare')):
            result, _ = self.analyze(root)
        skill = result['skills'][0]
        self.assertEqual(skill['comparison_status'], 'comparison_limit_exceeded')
        self.assertEqual(skill['comparisons'], [])
        self.assertEqual(len(skill['behavioral_results']), 3)

    def test_16_comparison_boundary_and_index_join_bounds(self):
        for count in (16, 17):
            records = [synthetic('skill-' + str(i), 'run-' + arm) for i in range(count) for arm in ('a', 'b')]
            root = self.bundle('pairs-' + str(count), records)
            original = analysis.cross_run
            with patch.object(analysis, 'cross_run', wraps=original) as compare, \
                    patch.object(analysis, 'case_index', wraps=analysis.case_index) as index:
                captured = analysis.capture_inputs([root]); result = analysis.build_analysis(captured)
            self.assertEqual(index.call_count, 2 * count)
            self.assertEqual(compare.call_count, count if count == 16 else 0)
            self.assertEqual(result['comparison_scope']['performed_pairs'], count if count == 16 else 0)
            if count == 17:
                self.assertTrue(all(skill['comparison_status'] == 'invocation_comparison_limit_exceeded' for skill in result['skills']))
        records = [synthetic(run='run-a'), synthetic(run='run-b')]
        for record in records:
            record['dataset']['case_ids'] = sorted(str(i) for i in range(1, 1001))
            record['dataset']['case_cohort_digest'] = evidence.identity(record['dataset']['case_ids'])
            record['observations'] = []; record['references'] = []
            reconcile(record, partial=True)
        result, _ = self.analyze(self.bundle('case-bound', records))
        self.assertEqual(len(result['skills'][0]['comparisons'][0]['cases']), 1000)

    def test_dedup_does_not_increase_measurement_counts(self):
        record = synthetic()
        result, _ = self.analyze(self.bundle('one', [record]), self.bundle('two', [record]))
        self.assertEqual(len(result['skills'][0]['behavioral_results']), 1)
        self.assertEqual(result['skills'][0]['comparison_status'], 'insufficient_run_evidence')
        self.assertEqual(len(result['record_index']), 2)
        self.assertEqual(len(result['input_provenance']), 1)

    def test_reordering_inputs_discovery_and_json_formatting(self):
        a, b = self.bundle('a', [self.historical]), self.bundle('b', [self.static])
        first, _ = self.analyze(a, b)
        safe_tree = evidence.safe_tree
        with patch.object(evidence, 'safe_tree', side_effect=lambda *args, **kw: list(reversed(safe_tree(*args, **kw)))):
            reordered, _ = self.analyze(b, a)
        self.assertEqual(evidence.encoded(first), evidence.encoded(reordered))
        def reverse_keys(value):
            if isinstance(value, dict): return {key: reverse_keys(value[key]) for key in reversed(value)}
            if isinstance(value, list): return [reverse_keys(item) for item in value]
            return value
        for root in (a, b):
            for path in root.rglob('*.json'):
                data = reverse_keys(json.loads(path.read_bytes()))
                path.write_text(json.dumps(data, sort_keys=False, separators=(',', ':')) + '\n\n')
        formatted, _ = self.analyze(b, a)
        self.assertNotEqual(first['input_provenance'], formatted['input_provenance'])
        self.assertEqual({k: v for k, v in first.items() if k != 'input_provenance'},
                         {k: v for k, v in formatted.items() if k != 'input_provenance'})
        self.assertEqual(analysis.render_summary(first), analysis.render_summary(formatted))

    def test_independent_validation_rejects_corrupted_output_and_links(self):
        result, captured = self.analyze(self.bundle('input', [synthetic(name='gh', scores=(0.4, 0.6))]))
        # Reacquire the public originals independently, then validate a serialized round trip.
        reacquired = analysis.capture_inputs(captured.roots)
        analysis.validate_analysis(evidence.parse_json(evidence.encoded(result), limit=analysis.JSON_LIMIT), reacquired)
        for mutate in (
            lambda r: r['skills'][0]['behavioral_results'][0]['native_metrics'][0].update(value=0.1),
            lambda r: r['skills'][0]['behavioral_results'][0]['case_summary']['cases'][0]['with_minus_without'].update(value='0'),
            lambda r: r['skills'][0]['behavioral_results'][0]['case_summary'].update(matched_cases=0),
            lambda r: r['skills'][0]['behavioral_results'][0]['arms'][0]['rubric'].update(total_cases=10),
            lambda r: r['skills'][0]['behavioral_results'][0]['gates'].update(unknown_observations=0),
            lambda r: r['findings'][0].update(record_ids=[evidence.identity('invented')]),
            lambda r: r['findings'][0].update(reference_ids=[evidence.identity('invented')]),
            lambda r: r['skills'][0].update(extra=True),
            lambda r: r['record_index'].pop(),
        ):
            corrupted = copy.deepcopy(result); mutate(corrupted)
            with self.assertRaises(ValueError): analysis.validate_analysis(corrupted, captured)
        pair_result, pair_captured = self.analyze(self.bundle('pair', [synthetic(run='one'), synthetic(run='two')]))
        pair_result['skills'][0]['comparisons'][0]['classification'] = 'exploratory'
        with self.assertRaises(ValueError): analysis.validate_analysis(pair_result, pair_captured)

    def test_documented_saved_analysis_rejects_duplicate_keys(self):
        quality = self.bundle('quality', configs=[configuration('alpha')])
        benchmark = self.bundle('benchmark', [synthetic()])
        result, _ = self.analyze(quality, benchmark)
        saved = self.root / 'saved'; saved.mkdir()
        report = saved / 'analysis.json'
        (saved / 'summary.md').write_bytes(analysis.render_summary(result))
        documentation = (REPO / '.github/evals/REPORT-EVIDENCE.md').read_text()
        section = documentation.split('### Independent validation and downstream evidence\n', 1)[1]
        example = section.split('```python\n', 1)[1].split('```', 1)[0]
        for original, replacement in (('/tmp/public-quality', quality),
                                      ('/tmp/public-benchmark', benchmark),
                                      ('/tmp/new-analysis', saved)):
            example = example.replace(original, str(replacement))
        code = compile(example, 'REPORT-EVIDENCE.md', 'exec')
        raw = evidence.encoded(result)
        report.write_bytes(raw)
        exec(code, {})
        marker = b'"maximum_pairs": 16'
        self.assertIn(marker, raw)
        for ambiguous in (b'{"schema_version":999,' + raw[1:],
                          b'{"schema_version":1,' + raw[1:],
                          raw.replace(marker, b'"maximum_pairs":999,"maximum_pairs":16', 1),
                          raw.replace(marker, b'"maximum_pairs":16,"maximum_pairs":16', 1)):
            with self.subTest(ambiguous=ambiguous[:40]):
                # Last-value decoding loses the ambiguity before recomputation.
                analysis.validate_analysis(json.loads(ambiguous), analysis.capture_inputs([quality, benchmark]))
                report.write_bytes(ambiguous)
                with self.assertRaisesRegex(ValueError, 'Duplicate JSON key'):
                    exec(code, {})

    def test_saved_analysis_explicit_limit_preserves_large_round_trip(self):
        result, captured = self.analyze(self.bundle('input', [synthetic()]))
        raw = evidence.encoded(result)
        raw += b' ' * (evidence.JSON_LIMIT + 1 - len(raw))
        path = self.root / 'analysis.json'; path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'Invalid bounded JSON'):
            evidence.parse_json(raw)
        loaded = evidence.parse_json(evidence.read_bytes(path, limit=analysis.JSON_LIMIT),
                                     limit=analysis.JSON_LIMIT)
        analysis.validate_analysis(loaded, captured)
        with self.assertRaisesRegex(ValueError, 'Invalid bounded JSON'):
            evidence.parse_json(raw, limit=len(raw) - 1)
        self.assertEqual(evidence.parse_json(raw, limit=len(raw)), loaded)

    def test_conflicting_behavioral_and_original_static_claims_reject(self):
        left = synthetic(); right = copy.deepcopy(left); right['metrics'][0]['value'] = 0.3
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            self.analyze(self.bundle('a', [left]), self.bundle('b', [right]))
        left = self.static; right = copy.deepcopy(left); right['run_id'] = 'different-run'
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            self.analyze(self.bundle('c', [left]), self.bundle('d', [right]))

    def test_layout_reconciliation_missing_inventory_unsafe_and_corrupt_inputs(self):
        for defect in ('missing_inventory', 'wrong_skill', 'wrong_run', 'extra', 'empty_dir', 'symlink',
                       'hardlink', 'duplicate_key', 'invalid_json', 'credential', 'unsupported_revision'):
            with self.subTest(defect=defect):
                root = self.bundle(defect, [synthetic()])
                report = next(root.glob('skills/**/public-report.json'))
                if defect == 'missing_inventory': (root / 'inventory/inventory.json').unlink()
                elif defect == 'wrong_skill': report.parent.parent.parent.rename(root / 'skills/wrong')
                elif defect == 'wrong_run': report.parent.rename(report.parent.with_name('wrong'))
                elif defect == 'extra': write(root / 'extra.json', {})
                elif defect == 'empty_dir': (root / 'empty').mkdir()
                elif defect == 'symlink': report.rename(root / 'retained'); report.symlink_to(root / 'retained')
                elif defect == 'hardlink': os.link(report, root / 'link')
                elif defect == 'duplicate_key': report.write_bytes(b'{"kind":"behavioral","kind":"behavioral"}')
                elif defect == 'invalid_json': report.write_bytes(b'{')
                elif defect == 'credential':
                    value = json.loads(report.read_bytes()); value['policy']['judge']['model'] = 'sk-syntheticcredential'
                    value['policy']['id'] = evidence.identity({key: value['policy'][key] for key in
                        ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
                    write(report, value)
                elif defect == 'unsupported_revision':
                    value = json.loads(report.read_bytes()); value['policy']['fields']['evaluator_revision'] = 'b' * 40
                    value['policy']['id'] = evidence.identity({key: value['policy'][key] for key in
                        ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
                    write(report, value)
                with self.assertRaises((ValueError, OSError)):
                    self.analyze(root)
        flat, _ = self.analyze(self.bundle('flat', [synthetic()], flat=True))
        self.assertEqual(len(flat['skills']), 1)

    def test_resource_limits_fail_closed_before_output(self):
        root = self.bundle('input', [synthetic()])
        for target, name, bound in ((analysis, 'MAX_INPUTS', 0), (analysis, 'MAX_REPORTS', 0),
                                    (analysis, 'MAX_SKILLS', 0), (analysis, 'MAX_ENTRIES', 2),
                                    (evidence, 'NORMALIZATION_LIMIT', 100), (evidence, 'JSON_LIMIT', 100),
                                    (analysis, 'JSON_LIMIT', 100), (analysis, 'MARKDOWN_LIMIT', 100)):
            output = self.root / ('out-' + name)
            with patch.object(target, name, bound), self.assertRaises(ValueError), redirect_stdout(StringIO()):
                analysis.main(['--input', str(root), '--output', str(output)])
            self.assertFalse(output.exists())
        a = self.bundle('a', configs=[configuration('one')]); b = self.bundle('b', configs=[configuration('two')])
        with patch.object(analysis, 'MAX_ENTRIES', 3), self.assertRaises(ValueError): self.analyze(a, b)
        with self.assertRaises(ValueError): self.analyze(root, root / 'skills')

    def test_actual_root_report_and_skill_boundaries(self):
        root = self.bundle('roots', configs=[configuration('alpha')])
        self.analyze(*([root] * 32))
        with self.assertRaisesRegex(ValueError, 'root limit'): self.analyze(*([root] * 33))
        reports = [synthetic(run='run-' + str(i)) for i in range(128)]
        accepted, _ = self.analyze(self.bundle('128-reports', reports))
        self.assertEqual(len(accepted['skills'][0]['behavioral_results']), 128)
        with self.assertRaisesRegex(ValueError, 'report limit'):
            self.analyze(self.bundle('129-reports', reports + [synthetic(run='last-run')]))
        first = self.bundle('first-skills', configs=[configuration('skill-' + str(i)) for i in range(500)])
        second = self.bundle('second-skills', configs=[configuration('skill-' + str(i)) for i in range(500, 1000)])
        accepted, _ = self.analyze(first, second)
        self.assertEqual(len(accepted['skills']), 1000)
        with self.assertRaisesRegex(ValueError, 'skill limit'):
            self.analyze(first, second, self.bundle('extra-skill', configs=[configuration('last-skill')]))

    def test_exact_shared_capture_budget_and_output_caps(self):
        a, b = self.bundle('a', [synthetic()]), self.bundle('b', configs=[configuration('other')])
        size = sum(path.stat().st_size for root in (a, b) for path in root.rglob('*.json'))
        with patch.object(evidence, 'NORMALIZATION_LIMIT', size): result, captured = self.analyze(a, b)
        with patch.object(evidence, 'NORMALIZATION_LIMIT', size - 1), self.assertRaisesRegex(ValueError, 'byte limit'):
            self.analyze(a, b)
        size = len(evidence.encoded(result))
        with patch.object(analysis, 'JSON_LIMIT', size): analysis.validate_analysis(result, captured)
        with patch.object(analysis, 'JSON_LIMIT', size - 1), self.assertRaisesRegex(ValueError, 'JSON size'):
            analysis.validate_analysis(result, captured)
        size = len(analysis.render_summary(result))
        with patch.object(analysis, 'MARKDOWN_LIMIT', size): analysis.render_summary(result)
        with patch.object(analysis, 'MARKDOWN_LIMIT', size - 1), self.assertRaisesRegex(ValueError, 'Markdown size'):
            analysis.render_summary(result)

    def test_stale_expiry_rejects_refreshed_projection_preserves_scores(self):
        root = self.bundle('old', [self.historical])
        later = datetime(2026, 10, 20, tzinfo=timezone.utc)
        with patch.object(evidence, 'utc_now', return_value=later):
            with self.assertRaisesRegex(ValueError, 'expired'): self.analyze(root)
            refreshed = evidence.project(evidence.normalize_behavioral(FIXTURES / 'podman-native', 'podman'))
            result, _ = self.analyze(self.bundle('refresh', [refreshed]))
        run = result['skills'][0]['behavioral_results'][0]
        self.assertEqual(run['native_metrics'], self.historical['metrics'])
        self.assertEqual(run['case_summary']['matched_cases'], 10)
        self.assertIn('reference_expired', run['availability']['reasons'])
        self.assertTrue(any(row['kind'] == 'unavailable_support' for row in result['findings']))

    def test_cli_blocks_network_subprocess_graders_and_scanners(self):
        root = self.bundle('cli', [self.historical])
        output = self.root / 'analysis'
        before = {path: path.read_bytes() for path in root.rglob('*.json')}
        with ExitStack() as stack:
            for target, name in ((subprocess, 'Popen'), (subprocess, 'run'), (socket, 'socket'),
                                 (evidence, 'offline_git'), (evidence, 'normalize_behavioral'), (evidence, 'normalize_static'),
                                 (evidence.reports, 'benchmark'), (evidence.reports, 'static')):
                if hasattr(target, name): stack.enter_context(patch.object(target, name, side_effect=AssertionError('offline boundary')))
            with redirect_stdout(StringIO()):
                analysis.main(['--input', str(root), '--output', str(output)])
        self.assertEqual(sorted(path.name for path in output.iterdir()), ['analysis.json', 'summary.md'])
        self.assertEqual({path: path.read_bytes() for path in root.rglob('*.json')}, before)
        self.assertEqual(output.stat().st_mode & 0o777, 0o700)
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in output.iterdir()))
        result = subprocess.run([sys.executable, '-B', str(REPO / '.github/scripts/skill_analysis.py'),
                                 '--input', str(root), '--output', str(self.root / 'second')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / 'second/analysis.json').read_bytes(), (output / 'analysis.json').read_bytes())
        bad = subprocess.run([sys.executable, '-B', str(REPO / '.github/scripts/skill_analysis.py'),
                              '--input', str(root), '--output', str(output)], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)
        self.assertEqual(bad.stdout, '')
        self.assertNotIn(str(self.root), bad.stderr)
        pair_root = self.bundle('paired-cli', [synthetic(run='one'), synthetic(run='two')])
        with patch.object(analysis, 'cross_run', wraps=analysis.cross_run) as compare, \
                patch.object(analysis, 'case_index', wraps=analysis.case_index) as cases, \
                patch.object(analysis, 'condition_identity', wraps=analysis.condition_identity) as conditions, \
                redirect_stdout(StringIO()):
            analysis.main(['--input', str(pair_root), '--output', str(self.root / 'paired-output')])
        self.assertEqual(compare.call_count, 1)
        self.assertEqual(cases.call_count, 2)
        self.assertEqual(conditions.call_count, 2)

    def test_output_overlap_all_inputs_change_guard_and_cleanup(self):
        a, b = self.bundle('a', [synthetic()]), self.bundle('b', configs=[configuration('other')])
        for parent in (a, b, REPO):
            with self.assertRaisesRegex(ValueError, 'overlap|outside checkout'), redirect_stdout(StringIO()):
                analysis.main(['--input', str(a), '--input', str(b), '--output', str(parent / 'new-analysis')])
            self.assertFalse((parent / 'new-analysis').exists())
        for parent in (a, b):
            with patch.dict(os.environ, {'TMPDIR': str(parent)}), self.assertRaises(ValueError), redirect_stdout(StringIO()):
                analysis.main(['--input', str(a), '--input', str(b)])
        original = analysis.render_summary
        def changed(result):
            payload = original(result)
            path = b / 'inventory/inventory.json'; path.write_bytes(path.read_bytes() + b'\n')
            return payload
        output = self.root / 'changed'
        with patch.object(analysis, 'render_summary', side_effect=changed), self.assertRaisesRegex(ValueError, 'changed'), redirect_stdout(StringIO()):
            analysis.main(['--input', str(a), '--input', str(b), '--output', str(output)])
        self.assertFalse(output.exists())
        captured = analysis.capture_inputs([a])
        result = analysis.build_analysis(captured)
        open_fd = os.open
        def failed(name, flags, *args, **kwargs):
            if name == 'summary.md' and flags & os.O_CREAT: raise OSError('synthetic write failure')
            return open_fd(name, flags, *args, **kwargs)
        with patch.object(os, 'open', side_effect=failed), self.assertRaises(OSError):
            evidence.write_outputs({'analysis.json': result}, output, rendered={'summary.md': analysis.render_summary(result)},
                                   input_paths=captured.roots, input_guards=captured.guards)
        self.assertFalse(output.exists())
        with patch.dict(os.environ, {'TMPDIR': str(self.root)}), redirect_stdout(StringIO()):
            temporary = analysis.main(['--input', str(a)])
        self.assertEqual(temporary.parent, self.root)
        self.assertEqual(sorted(path.name for path in temporary.iterdir()), ['analysis.json', 'summary.md'])


if __name__ == '__main__':
    unittest.main()
