"""Accounting and provenance controls; native execution is exercised by hosted fixtures."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))


class DeadlineEvidence(unittest.TestCase):
    def test_partial_native_usage_cannot_become_complete_accounting(self):
        from codex_pilot_runtime import usage_record
        from evaluation_campaign_core import accounting
        value = {'trial_name': 'native-fixture', 'agent_result': {'n_input_tokens': 100,
                 'n_cache_tokens': 20, 'n_output_tokens': 10, 'metadata': {'execution_complete': False}}}
        usage = usage_record(value, probe=True)
        self.assertEqual(usage['completeness'], 'partial')
        self.assertGreater(usage['observed_estimated_usd'], 0)
        self.assertIsNone(usage['estimated_usd'])
        with self.assertRaisesRegex(ValueError, 'Unknown usage'):
            accounting([{'state': 'failed', 'usage': usage}])
        self.assertEqual(usage['n_input_tokens'], 100)
        self.assertIn('no model usage', usage['billing'])
        empty = usage_record({'trial_name': 'native-empty'}, probe=True)
        self.assertEqual(empty['completeness'], 'unavailable')
        self.assertIsNone(empty['estimated_usd'])

    def test_timeout_and_cancellation_remain_distinct_unmeasured_outcomes(self):
        from evaluation_runtime import native_outcome, failure_reason
        runtime = {'profile': {'adapter': 'codex'}}
        for exception, outcome in [('AgentTimeoutError', 'timeout'), ('CancelledError', 'interrupted')]:
            trial = {'exception_info': {'exception_type': exception}}
            self.assertEqual(native_outcome(runtime, trial, 'unknown'), outcome)
        self.assertEqual(failure_reason('AgentTimeoutError'), 'agent_timeout')
        self.assertNotEqual(failure_reason('CancelledError'), failure_reason('AgentTimeoutError'))

    def test_entire_starting_registry_is_preserved(self):
        registry = json.loads((ROOT / '.github/evals/custom-metrics.json').read_text())
        registry['profiles'] = {k:v for k,v in registry['profiles'].items()
            if '-lifecycle-v1-' not in k and k not in ('pester-cli-pilot-retained-v10', 'pester-effectiveness-v11',
                'pester-cli-pilot-retained-v11', 'pester-effectiveness-v12', 'pester-cli-pilot-retained-v12', 'pester-effectiveness-v13', 'pester-effectiveness-v14', 'pester-effectiveness-v15', 'pester-effectiveness-v16')}
        digest = hashlib.sha256(json.dumps(registry, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(digest, 'e29fd6c9b62dc9018d2afa74e33deb3e8a894507e25b9487a391a7618225fee5')
