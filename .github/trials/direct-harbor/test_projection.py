"""Failed/missing evidence must never become measured success or zero usage."""
import json
from pathlib import Path
import tempfile
import unittest
import run as trial


class ProjectionTests(unittest.TestCase):
    def project(self, carrier=None, exception=None, reward=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            native = root / 'job/trial'
            native.mkdir(parents=True)
            trial.write(native / 'result.json', {'task_name': 'fixture', 'exception_info': exception})
            if carrier is not None:
                trial.write(native / 'verifier/skill_evaluator_reward.json', carrier)
            if reward is not None:
                trial.write(native / 'verifier/reward.json', reward)
            return trial.project(root, {'fixture': 'passed'})[0]

    def test_reward_without_terminal_evidence_is_ungradeable(self):
        row = self.project(reward={'overall': 1})
        self.assertEqual(row['outcome']['classification'], 'verifier_failure')
        self.assertFalse(row['matches'])
        self.assertIsNone(row['tokens'])
        self.assertIsNone(row['cost_usd'])

    def test_prearmed_failure_wins_over_claimed_success(self):
        row = self.project({'evaluation_status': 'failed', 'details': {'outcome': {'classification': 'passed'}}})
        self.assertEqual(row['outcome']['classification'], 'verifier_failure')

    def test_native_failure_wins_over_valid_reward(self):
        row = self.project({'evaluation_status': 'complete', 'details': {'outcome': {'classification': 'passed'}}},
                           {'exception_type': 'AgentTimeoutError'})
        self.assertEqual(row['outcome']['classification'], 'infrastructure_error')
        self.assertEqual(row['outcome']['code'], 'AgentTimeoutError')

    def test_unsupported_and_wrong_output_are_distinct(self):
        for classification, status in [('unsupported', 'failed'), ('failed', 'complete')]:
            with self.subTest(classification=classification):
                row = self.project({'evaluation_status': status, 'details': {'outcome': {'classification': classification}}})
                self.assertEqual(row['outcome']['classification'], classification)


if __name__ == '__main__':
    unittest.main()
