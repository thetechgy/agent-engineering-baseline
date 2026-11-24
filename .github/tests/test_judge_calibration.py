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


HISTORICAL_AUTHENTICATION_CLI = '''import runpy
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

# run_case invokes <python> -B <selection CLI> authenticate ...
sys.argv = sys.argv[2:]
sys.path.insert(0, str(Path(sys.argv[0]).parent))
import evaluation_campaign_protocol as protocol

with patch.object(protocol, 'datetime', wraps=datetime) as clock:
    clock.now.return_value = datetime(2026, 11, 17, 18, tzinfo=timezone.utc)
    runpy.run_path(sys.argv[0], run_name='__main__')
'''


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
        self.assertEqual(frozen['protocol']['max_http_attempts'], 12)
        self.assertFalse(inputs.applicable(frozen['inputs'][6], 'goal_accuracy'))
        self.assertIsNone(frozen['inputs'][6]['reference'])
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
            root = Path(directory)
            # run_case starts a child interpreter. Patch only its protocol clock.
            python = root / 'historical-python'
            python.write_text(f'#!{sys.executable} -B\n' + HISTORICAL_AUTHENTICATION_CLI)
            python.chmod(0o700)
            for case in ('closed-allocation', 'wrong-artifact'):
                with self.subTest(case=case):
                    run_case(root / case, self.task, case, python=python)
            run_case(root / 'expired-authority', self.task, 'expired-authority')

    def test_missing_reference_cannot_be_replaced_by_an_invented_success_target(self):
        original = reports.read_json
        for index, reference, error in ((6, 'Tests succeeded', 'Unfrozen reference input'),
                                        (0, '{"title":"invented","untrusted_instruction":false}', 'Factual reference differs')):
            changed = copy.deepcopy(original(ROOT / self.task.definition['rubric']))
            changed['records'][index]['reference'] = reference
            def read(path):
                return changed if path == ROOT / self.task.definition['rubric'] else original(path)
            with patch.object(reports, 'read_json', side_effect=read), self.assertRaisesRegex(ValueError, error):
                inputs.records(self.task)

    def test_cost_estimate_prices_cache_writes_without_fabricating_usage(self):
        from judge_accounting import usage
        def response(writes):
            return {'outcome': 'http_response', 'usage': usage({'input': 19, 'output': 7,
                'total': 26, 'cached_input': 5, 'cache_write_input': writes})}
        for writes, expected in ((0, 0.000198), (4, 0.000202), (None, 0.000212)):
            row = response(writes)
            self.assertAlmostEqual(campaign.transport_estimate([row], self.task), expected)
            self.assertEqual(row['usage']['counters']['cache_write_input'], writes)
        self.assertIsNone(campaign.transport_estimate([response(15)], self.task))

    def test_frozen_historical_profiles_are_preserved(self):
        import hashlib
        value = reports.read_json(ROOT / '.github/evals/custom-metrics.json')
        value['profiles'].pop('gh-deterministic-gate-v6')
        value['profiles'].pop('gh-native-oracle-v2')
        value['active_profiles']['gh'] = 'gh-deterministic-gate-v5'
        original = {**value, 'profiles': {k:v for k,v in value['profiles'].items() if '-source-v33-' not in k and '-source-v35-' not in k and '-source-v36-' not in k and '-source-v32-' not in k and '-source-v31-' not in k and '-source-v30-' not in k and '-source-v29-' not in k and '-source-v28-' not in k and '-source-v27-' not in k and '-source-v26-' not in k and k not in ('pester-effectiveness-v30', 'pester-cli-pilot-retained-v18', 'pester-effectiveness-v31', 'pester-cli-pilot-retained-v19', 'pester-effectiveness-v32', 'pester-effectiveness-v33', 'pester-effectiveness-v34', 'pester-effectiveness-v35', 'pester-effectiveness-v39', 'pester-effectiveness-v38', 'pester-effectiveness-v36', 'pester-cli-pilot-retained-v20') and '-source-v25-' not in k}}
        self.assertEqual(len(original['profiles']), 839)
        from evaluation_evidence import source_manifest
        import skill_evidence as evidence
        additions = [k for k in value['profiles'] if '-source-v25-' in k]
        self.assertEqual(len(additions), 35)
        current = evidence.custom_registry(ROOT)
        for key in additions:
            row = value['profiles'][key]
            old = value['profiles'][key.replace('-source-v25-', '-source-v24-')]
            self.assertEqual({k:v for k,v in row.items() if k not in ('id', 'runtime_digest')},
                             {k:v for k,v in old.items() if k not in ('id', 'runtime_digest')})
            active = key.replace('-source-v25-', '-source-v43-')
            successor = current['profiles'][active]
            self.assertEqual(successor['runtime_digest'],
                             evidence.identity(source_manifest(ROOT, successor['skill_id'], active)))
        self.assertEqual(hashlib.sha256(json.dumps(original, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                         '81c8de65793bd75fe4b900b7213532ba3f27cb3f6a03936e51c59c00136b78af')


@unittest.skipUnless(os.environ.get('JUDGE_CALIBRATION_EVIDENCE'), 'actual preparation evidence supplied by qualification')
class RetainedEvidence(unittest.TestCase):
    def setUp(self):
        self.task = selected_task(os.environ.get('CAMPAIGN_ID', 'judge-calibration-090-v1-sol62'))
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
        self.assertEqual(value['accounting_summary']['http_attempts'], 6)
        self.assertEqual(value['entries'][6]['results']['goal_accuracy']['status'], 'not_applicable')
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

    def test_success_and_stop_evidence_matches_the_actual_live_upload_contract(self):
        import yaml
        workflow = yaml.safe_load((ROOT / '.github/workflows/evaluation-campaign.yml').read_text())
        paths = next(s['with']['path'] for s in workflow['jobs']['live']['steps']
                     if s.get('name') == 'Retain all slots and partial native evidence after stopping')
        self.assertIn('${{ runner.temp }}/campaign-live/evidence/', paths)
        for scenario in ('complete', 'interruption', 'retention-failure', 'cache-cost-stop', 'redirect-stop'):
            root = self.reference.parent / 'scenarios' / scenario
            self.assertFalse((root / 'attempt-ledger.json').exists())
            self.assertTrue((root / 'evidence/consolidated/report.html').is_file())
            value = campaign.admit_run(root / 'evidence', self.task)
            self.assertEqual(value['scenario'], scenario)
            with tempfile.TemporaryDirectory() as directory:
                reproduced = campaign.render([root / 'evidence'], Path(directory) / 'report', self.task)
            self.assertEqual(reproduced, (root / 'evidence/consolidated/report.html').read_bytes())

    def test_valid_behavior_text_is_redacted_without_changing_verdicts(self):
        from judge_transport_090 import SENTINEL
        root = self.reference.parent / 'scenarios/complete/evidence'
        record = campaign.admit_run(root, self.task)['entries'][1]
        self.assertTrue(record['results']['behavior_check']['results'][0]['passed'])
        for path in (root / 'attempt-ledger.json', root / 'records/control-02/judgments.json',
                     root / 'records/control-02/judge_attempts.json', root / 'consolidated/report.html',
                     self.reference / 'consolidated/report.html'):
            self.assertNotIn(SENTINEL, path.read_text())


if __name__ == '__main__': unittest.main()
