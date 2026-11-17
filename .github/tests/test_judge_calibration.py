"""Judge-only authorization and evidence boundaries; no provider credentials."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))
import evaluation_campaign_protocol as shared
from evaluation_campaign_selection import selected_task, owning_evaluator
import evaluator_profiles as profiles
import judge_calibration_campaign as campaign
import judge_calibration_inputs as inputs
import skill_reports as reports


class JudgeContracts(unittest.TestCase):
    def setUp(self):
        self.task = selected_task('judge-calibration-090-v1')

    def test_judge_selection_has_no_agent_evidence_and_separates_acceptance_metadata(self):
        frozen = shared.frozen(self.task)
        self.assertEqual(owning_evaluator(self.task), profiles.ACCOUNTING)
        self.assertIsNone(frozen['agent_runtime'])
        self.assertIsNone(frozen['agent_cleanup'])
        self.assertEqual([r['variant'] for r in frozen['schedule']], [None] * 7)
        self.assertNotIn('skill', self.task.definition)
        for row in frozen['inputs']:
            self.assertEqual(set(row), {'id', 'dimension', 'question', 'submission', 'reference', 'expected_behavior'})
        self.assertEqual(frozen['protocol']['max_http_attempts'], 14)
        self.assertFalse(frozen['protocol']['budget']['billing_limit_enforced'])

    def test_unsupported_provider_and_changed_owner_fail_closed(self):
        original = reports.read_json
        for field in ('provider', 'model'):
            changed = copy.deepcopy(shared.protocol(self.task))
            changed['request'][field] = 'unsupported'
            def read(path):
                return changed if path == ROOT / self.task.definition['protocol'] else original(path)
            with patch.object(reports, 'read_json', side_effect=read), self.assertRaisesRegex(ValueError, 'Unsupported judge provider'):
                inputs.protocol(self.task)
        changed = {**profiles.ACCOUNTING, 'patch_sha256': '0'*64}
        def read(path):
            return changed if path == ROOT / self.task.definition['runtime_profile'] else original(path)
        with patch.object(reports, 'read_json', side_effect=read), self.assertRaisesRegex(ValueError, 'owner drift'):
            inputs.protocol(self.task)

    def test_fixture_origin_has_no_paid_gate_or_real_allocation(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, 'protected workflow'):
            shared.runtime_gate(self.task)
        from campaign_authentication_qualification import run_case
        with tempfile.TemporaryDirectory() as directory:
            run_case(Path(directory) / 'closed', self.task, 'closed-allocation')
            run_case(Path(directory) / 'wrong-artifact', self.task, 'wrong-artifact')

    def test_frozen_historical_profiles_are_preserved(self):
        import hashlib
        value = reports.read_json(ROOT / '.github/evals/custom-metrics.json')
        original = {**value, 'profiles': {k:v for k,v in value['profiles'].items() if '-source-v25-' not in k}}
        self.assertEqual(len(original['profiles']), 839)
        from evaluation_evidence import source_manifest
        import skill_evidence as evidence
        additions = [k for k in value['profiles'] if '-source-v25-' in k]
        self.assertEqual(len(additions), 35)
        for key in additions:
            row = value['profiles'][key]
            old = value['profiles'][key.replace('-source-v25-', '-source-v24-')]
            self.assertEqual({k:v for k,v in row.items() if k not in ('id', 'runtime_digest')},
                             {k:v for k,v in old.items() if k not in ('id', 'runtime_digest')})
            self.assertEqual(row['runtime_digest'], evidence.identity(source_manifest(ROOT, row['skill_id'], key)))
        self.assertEqual(hashlib.sha256(json.dumps(original, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                         '81c8de65793bd75fe4b900b7213532ba3f27cb3f6a03936e51c59c00136b78af')


@unittest.skipUnless(os.environ.get('JUDGE_CALIBRATION_EVIDENCE'), 'actual preparation evidence supplied by qualification')
class RetainedEvidence(unittest.TestCase):
    def setUp(self):
        self.task = selected_task('judge-calibration-090-v1')
        self.reference = Path(os.environ['JUDGE_CALIBRATION_EVIDENCE'])

    def test_actual_preparation_consumes_and_reproduces_without_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(campaign.check(self.reference, Path(directory) / 'consumer', self.task))
        proof = reports.read_json(self.reference / 'authentication-consumption.json')
        self.assertTrue(proof['actual_preparation'])
        self.assertFalse(proof['live_authority'])

    def test_fixture_disagreements_and_unknowns_do_not_retry_or_relabel(self):
        root = self.reference.parent / 'scenarios/complete/evidence'
        value = campaign.admit_run(root, self.task)
        self.assertEqual(value['state'], 'completed')
        self.assertEqual(value['accounting_summary']['http_attempts'], 7)
        self.assertIsNone(value['entries'][2]['results']['behavior_check']['results'][0]['passed'])
        self.assertTrue(value['entries'][1]['results']['behavior_check']['results'][0]['passed'])
        self.assertTrue(value['entries'][4]['results']['behavior_check']['results'][0]['passed'])

    def test_missing_accounting_and_diagnostics_cannot_be_reported_as_complete(self):
        import shutil
        for member in ('judge_accounting.json', 'judge_attempts.json', 'judgments.json'):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / 'run'
                shutil.copytree(self.reference.parent / 'scenarios/complete/evidence', root)
                (root / 'records/control-01' / member).unlink()
                with self.assertRaises(ValueError):
                    campaign.admit_run(root, self.task)


if __name__ == '__main__': unittest.main()
