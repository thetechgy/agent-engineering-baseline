"""Unscored collector projections stay diagnostics with bound native provenance."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import skill_evidence as evidence


def carriers():
    reward = {'metric_set': 'skill-evaluator-default-v2', 'entry_id': 'pester-002',
              'evaluation_status': 'failed', 'evaluation_errors': {'applicability': 'Unscoreable trial'},
              'agent': 'codex', 'variant': 'with_skill', 'model': 'fixture-model', 'model_source': 'fixture-source'}
    trial = {'trial_name': 'pester-002__attempt1', 'task_name': 'pester-002',
             'agent_info': {'name': 'codex', 'model_info': {'name': 'fixture-model'}},
             'exception_info': {'exception_type': 'ValueError', 'exception_message': 'Observation unavailable',
                                'occurred_at': '2026-11-10T23:31:11Z'},
             'verifier_result': {'rewards': {'overall': 0.0}}}
    failure = {**reward, 'status': 'unscored', 'trial': trial['trial_name'],
               'trial_name': trial['trial_name'], 'task_name': trial['task_name'],
               'error': {'type': 'ValueError', 'message': 'Observation unavailable',
                         'occurred_at': '2026-11-10T23:31:11Z'}}
    return reward, failure, trial


class DiagnosticContract(unittest.TestCase):
    def test_exact_diagnostic_has_no_invented_identity_or_measurement(self):
        values = carriers(); before = copy.deepcopy(values)
        evidence.validate_unscored_diagnostic(*values, 'pester-002', 'with_skill')
        self.assertEqual(values, before)
        self.assertNotIn('trial_id', values[0])

    def test_wrong_identity_claims_and_measurement_surfaces_rejected(self):
        for target, key, value in (
            (0, 'trial_id', 'wrong-trial'), (0, 'entry_id', 'wrong-case'),
            (0, 'variant', 'without_skill'), (0, 'agent', 'other-agent'),
            (0, 'model', 'other-model'), (0, 'custom_metrics', {'quality': 1}),
            (0, 'details', {'outcome': {'classification': 'passed'}}),
            (0, 'overall', 1), (0, 'evaluation_status', 'complete'),
            (1, 'trial', 'wrong-trial'), (1, 'trial_name', 'wrong-trial'),
            (1, 'task_name', 'wrong-task'), (1, 'status', 'scored'),
            (1, 'model_source', 'other-source'), (1, 'evaluation_errors', {}),
            (1, 'error', {'type': 'OtherError'}),
            (2, 'exception_info', None), (2, 'verifier_result', {'rewards': {'overall': 1.0}})):
            with self.subTest(target=target, key=key):
                values = carriers(); values[target][key] = value
                with self.assertRaises(ValueError):
                    evidence.validate_unscored_diagnostic(*values, 'pester-002', 'with_skill')

    def test_native_normalization_preserves_unavailability_and_rejects_mutation(self):
        from test_custom_metrics import synthetic_native, write
        with tempfile.TemporaryDirectory() as directory:
            native, run = synthetic_native(Path(directory))
            path = run / 'codex/with-skill/trials/pester-002__attempt1'
            reward, failure, details = carriers()
            trial = json.loads((path / 'result.json').read_text())
            trial.update({k: details[k] for k in ('exception_info', 'verifier_result')})
            trial['agent_info']['model_info'] = details['agent_info']['model_info']
            write(path / 'result.json', trial); write(path / 'reward.json', reward)
            write(path / 'failure.json', failure)
            result = evidence.normalize_behavioral(native, 'powershell-pester-6')
            row = next(r for r in result['observations'] if r['arm'] == 'with_skill' and r['native_trial'] == trial['trial_name'])
            self.assertEqual(row['custom']['outcome'], 'unknown')
            self.assertTrue(all(m['value'] is None and m['status'] == 'unavailable' for m in row['custom']['measurements']))
            self.assertNotIn('trial_id', json.loads((path / 'reward.json').read_text()))
            (path / 'failure.json').unlink()
            with self.assertRaisesRegex(ValueError, 'lacks native failure identity'):
                evidence.normalize_behavioral(native, 'powershell-pester-6')
            write(path / 'failure.json', failure)
            write(path / 'reward.json', {**reward, 'trial_id': 'wrong-trial'})
            with self.assertRaisesRegex(ValueError, 'Reward identity mismatch'):
                evidence.normalize_behavioral(native, 'powershell-pester-6')


if __name__ == '__main__':
    unittest.main()
