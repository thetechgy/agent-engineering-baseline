"""Score-preservation gate controls, including real frozen-runtime probes when configured."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import evaluator_scoring_compatibility as scoring


class ScoringGateTests(unittest.TestCase):
    def result(self, version):
        # Shape-only fixtures. Real native functions are exercised separately.
        return {'schema': 1, 'runtime': {'skillevaluator': version, **scoring.PINS[version]},
            'python': '3.13.18', 'lock_sha256': scoring.LOCKS[version],
            'sources': {key: hashes[0] for key, hashes in scoring.SOURCES[version].items()},
            'metrics': list(scoring.METRICS), 'definition': 'Controlled schema fixture',
            'native_score_policy': None if version == '0.3.0' else 'skill-evaluator-dimension-mean-v1',
            'scores': [0.5] * len(scoring.vectors()), 'network_attempts': [],
            'inference': False, 'remote_judges': False}

    def test_controlled_probe_population_covers_every_binary_vector_and_fractional_inputs(self):
        values = scoring.vectors()
        self.assertEqual(len(values), 73)
        self.assertEqual(len({tuple(row.values()) for row in values[:64]}), 64)
        self.assertTrue(all(set(row) == set(scoring.METRICS) for row in values))
        self.assertTrue(any(0.5 in row.values() for row in values))

    def test_comparison_preserves_observed_scores_and_reports_incompatibility(self):
        before, after = self.result('0.3.0'), self.result('0.7.2')
        self.assertEqual(scoring.compare(before, after)['status'], 'compatible')
        after['scores'][1] = 0.6
        result = scoring.compare(before, after)
        self.assertEqual(result['status'], 'incompatible')
        self.assertEqual(result['code'], 'standard_score_policy_changed')
        self.assertEqual(result['differences'], [{'case': 1, 'metrics': scoring.vectors()[1], 'retained': 0.5, 'candidate': 0.6}])
        self.assertTrue(result['fixture_only']); self.assertFalse(result['inference']); self.assertFalse(result['remote_judges'])
        self.assertEqual(before['scores'][1], 0.5)

    def test_missing_or_invalid_retained_interpreter_never_falls_back(self):
        for executable in (None, '', 'python', 'relative/python'):
            with self.subTest(executable=executable), patch.object(scoring, 'probe') as called:
                result = scoring.qualify(sys.executable, Path('.'), Path('uv.lock'), executable)
                self.assertEqual(result['status'], 'unqualified')
                self.assertEqual(result['code'], 'retained_evaluator_python_required')
                called.assert_not_called()
        with self.assertRaises(ValueError): scoring.probe('python', '0.3.0')

    def test_wrong_runtime_lock_source_metric_set_and_activity_reject(self):
        mutations = [
            ('runtime', {'skillevaluator': '0.7.2', **scoring.PINS['0.3.0']}),
            ('lock_sha256', '0' * 64), ('sources', {}), ('metrics', ['fabricated']),
            ('network_attempts', ['socket.connect']), ('inference', True), ('remote_judges', True),
            ('python', '3.14.0'), ('native_score_policy', 'invented'), ('extra', 'unapproved'),
        ]
        for key, value in mutations:
            report = self.result('0.3.0'); report[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): scoring.validate_probe(report, '0.3.0')

    def test_missing_duplicate_and_nonfinite_score_carriers_reject(self):
        for scores in ([], [0] * 72, [0] * 74, [True] * 73, [float('nan')] * 73,
                       [float('inf')] * 73, ['0'] * 73, [-1] * 73, [2] * 73, [10**1000] * 73):
            report = self.result('0.3.0'); report['scores'] = scores
            with self.subTest(scores=str(scores[:1])), self.assertRaises(ValueError): scoring.validate_probe(report, '0.3.0')

    def test_probe_failures_are_unqualified_and_cannot_be_successful_comparisons(self):
        for error in (OSError(), ValueError(), subprocess.TimeoutExpired('probe', 30)):
            with self.subTest(error=type(error).__name__), patch.object(scoring, 'probe', side_effect=error):
                result = scoring.qualify(sys.executable, Path('.'), Path('uv.lock'), sys.executable)
                self.assertEqual(result['status'], 'unqualified')
                self.assertEqual(result['code'], 'native_score_probe_rejected')
                self.assertNotIn('scores', result)

    def test_request_is_fixed_isolated_and_does_not_forward_provider_credentials(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'dummy-must-not-be-forwarded', 'PYTHONPATH': 'dummy-module-override'}), \
                patch.object(subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, json.dumps(self.result('0.3.0')).encode())) as called:
            scoring.probe(sys.executable, '0.3.0')
        args, kwargs = called.call_args
        self.assertEqual(args[0][:4], [sys.executable, '-I', '-B', '-c'])
        self.assertEqual(args[0][4], scoring.PROBE)
        self.assertNotIn('OPENAI_API_KEY', kwargs['env']); self.assertNotIn('PYTHONPATH', kwargs['env'])
        self.assertEqual(kwargs['timeout'], 30)

    def test_malformed_oversized_and_failed_worker_outputs_reject(self):
        for code, raw in ((1, b'{}'), (0, b'{'), (0, b' ' * (scoring.LIMIT + 1)), (0, b'NaN')):
            with self.subTest(code=code, size=len(raw)), \
                    patch.object(subprocess, 'run', return_value=subprocess.CompletedProcess([], code, raw)), self.assertRaises(ValueError):
                scoring.probe(sys.executable, '0.3.0')

    def test_real_native_runtime_comparison_preserves_the_blocker(self):
        retained = os.environ.get('SKILL_LEGACY_REVIEW_PYTHON')
        candidate = os.environ.get('SKILL_CANDIDATE_PYTHON')
        source = os.environ.get('SCORE_CANDIDATE_SOURCE')
        lock = os.environ.get('SCORE_CANDIDATE_LOCK')
        if not all((retained, candidate, source, lock)):
            self.skipTest('Frozen native interpreters and approved candidate snapshot not configured')
        result = scoring.qualify(candidate, Path(source), Path(lock), retained)
        self.assertEqual(result['status'], 'incompatible', result)
        self.assertEqual(result['vectors'], 73)
        self.assertEqual(len(result['differences']), 56)
        for zero, expected in (('skill_execution', 0.8), ('goal_accuracy', 0.9)):
            vector = {key: int(key != zero) for key in scoring.METRICS}
            row = next(row for row in result['differences'] if row['metrics'] == vector)
            self.assertEqual(row['retained'], 0.8333); self.assertEqual(row['candidate'], expected)
        for probe in result['probes'].values():
            self.assertEqual(probe['network_attempts'], [])
            self.assertFalse(probe['inference']); self.assertFalse(probe['remote_judges'])


if __name__ == '__main__':
    unittest.main()
