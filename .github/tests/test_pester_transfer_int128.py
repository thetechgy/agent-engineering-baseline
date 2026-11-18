"""The retained native qualification binds the task-owned v2 member set."""

import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
TASK = ROOT / '.github/evals/pester-return-contract/grader-v2'
RECEIPTS = ROOT / 'docs/evaluations/pester-transfer-decision/diagnostics'


def load_module(name):
    spec = importlib.util.spec_from_file_location(f'_transfer_v2_{name}', TASK / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TransferNativeCoverage(unittest.TestCase):
    def test_native_qualification_binds_exact_stage_and_historical_inputs(self):
        native = load_module('native')
        verifier = load_module('verify_qualification')
        receipt = json.loads((RECEIPTS / 'quantity-int128-native-v2.json').read_bytes())
        history_raw = (RECEIPTS / 'quantity-int128.json').read_bytes()
        self.assertEqual(receipt['historical_replay'], native.digest(history_raw))
        members = native.native_members()
        self.assertEqual(receipt['member_digests'], {key: native.digest(raw) for key, raw in members.items()})

        task = native.load(ROOT / '.github/evals/campaigns/pester-return-transfer-current-v6.json')
        prior = task.expected_members(task.definition['source_case'], 'without_skill')
        self.assertEqual(set(members) - set(prior), {native.EXTRA_REFERENCE})
        self.assertEqual({key for key, raw in prior.items() if members[key] != raw},
                         {'tests/verifier/grader.py', 'tests/entry.json'})
        self.assertEqual(sum(key.startswith('tests/case/mutants/') for key in members), 5)

        historical = json.loads(history_raw)
        observed = verifier.verify(receipt, historical)
        self.assertTrue(observed['verified'])
        self.assertEqual(observed['counts'], {'passed': 0, 'failed': 12, 'unmeasured': 0})
        for row in receipt['observations']:
            grade, detail = verifier.native_observation(row)
            self.assertEqual(grade, 'failed')
            self.assertEqual(detail['valid_references'], {'original': 1, 'quantity-int128': 0})
            self.assertEqual(detail['mutants_detected'], 0)
