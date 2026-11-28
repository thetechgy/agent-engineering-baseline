"""Pinned admission boundaries and immutable original replay, without inference."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_codex_effectiveness import ROOT, prospective_grader
from codex_pilot_effectiveness import runner_bytes as original_runner
from evaluation_tasks import load
from evaluation_campaign import purpose
from evaluation_campaign_core import drive, schedule
from evaluation_campaign_protocol import protocol, stop_reason
from evaluation_campaign_selection import selected_task
from evaluation_identity import REPLAY_ADAPTER, execution_binding
from codex_pilot_replay import campaign_corpus, campaign_payload, campaign_retrospective, validate_campaign_retrospective
from pester_admission import runner_bytes
import skill_evidence as evidence


class Admission(unittest.TestCase):
    def task(self, name='pester-transfer-retrospective-v1'):
        return load(ROOT / f'.github/evals/campaigns/{name}.json')

    def test_exact_retained_bytes_and_original_unmeasured_outcome(self):
        task = self.task()
        root, manifest, original = campaign_corpus(definition=task.definition)
        payload = campaign_payload(definition=task.definition)
        self.assertEqual(len(payload), 1536)
        self.assertEqual(hashlib.sha256(payload).hexdigest(), 'c985298ef4fbe7a02ca8d1645fc0a07a3ed478084aafbf0489e6537748ffc0bf')
        self.assertEqual(original['observations'][0]['custom']['outcome'], 'unsupported')
        self.assertTrue(all(m['value'] is None for o in original['observations'] for m in o['custom']['measurements']))
        self.assertEqual(manifest['source']['run'], 42911213479)
        profile, _, _ = evidence.custom_contract('powershell-pester-6', purpose=purpose(task, 'replay'))
        meta = campaign_retrospective(profile, adapter_revision='a'*40)
        self.assertTrue(meta['after_output_inspection'])
        self.assertFalse(meta['new_inference'])
        validate_campaign_retrospective(meta, profile)
        meta['submission_digests']['with_skill'] = 'sha256:'+'0'*64
        with self.assertRaises(ValueError): validate_campaign_retrospective(meta, profile)

    def test_retained_unsupported_grade_stops_after_measured_work(self):
        root, _, public = campaign_corpus(definition=self.task().definition)
        retained = evidence.read_json(root / 'attempt-ledger.json')
        rejection = retained['entries'][0]
        self.assertEqual(rejection['outcome'], {'classification': 'unsupported', 'code': 'expression_policy'})
        self.assertEqual(public['observations'][0]['custom']['admission_reason'], rejection['outcome']['code'])
        self.assertIsNone(public['observations'][0]['score'])

        task = selected_task('pester-return-transfer-current-v6-sol62')
        contract = protocol(task)
        slots = schedule(tuple(task.cases('live')), tuple(v['id'] for v in task.definition['variants']),
                         contract['trials_per_arm'])
        rows = [dict(slot, state='unlaunched') for slot in slots]
        ledger = {'entries': rows}
        measured = ['passed', 'failed', 'passed']
        launched = []

        def attempt(row, _total):
            launched.append(row['position'])
            if row['position'] == 4:
                self.assertEqual(row['variant'], rejection['variant'])
                row.update({key: rejection[key] for key in ('cleanup', 'returncode', 'grading_present', 'outcome', 'usage')})
            else:
                self.assertLess(row['position'], 4, 'The scheduler launched after unsupported grading')
                row.update(cleanup=True, returncode=0, grading_present=True,
                           outcome={'classification': measured[row['position'] - 1]}, usage={'estimated_usd': 0.01})
            reason = stop_reason(row)
            row['state'] = 'failed' if reason else 'completed'
            return reason

        drive(ledger, attempt, save=lambda: None, resources=lambda: (), baseline=(),
              threshold=contract['budget']['stop_estimate_usd'])
        self.assertEqual(launched, [1, 2, 3, 4])
        self.assertEqual(ledger['state'], 'stopped')
        self.assertEqual(ledger['stop_reason'], 'unsupported_grading')
        self.assertIn(ledger['stop_reason'], contract['stop_rules'])
        self.assertEqual([row['outcome']['classification'] for row in rows[:4]], [*measured, 'unsupported'])
        self.assertEqual([row['state'] for row in rows], ['completed'] * 3 + ['failed', 'unlaunched', 'unlaunched'])

    def test_correction_preserves_every_member_except_admission_and_successor_document(self):
        old = self.task('pester-transfer-original-v1').expected_members('pester-transfer-batch-v1', 'with_skill')
        new = self.task().expected_members('pester-transfer-batch-v1', 'with_skill')
        self.assertEqual({k for k in old if old[k] != new[k]}, {'tests/Runner.ps1', 'environment/input/EXECUTION-PROFILE.md'})
        for name, mode in [('pester-transfer-original-v1','oracle'),('pester-transfer-retrospective-v1','replay'),('pester-admission-controls-v2','oracle')]:
            task = self.task(name)
            selected = purpose(task, mode)
            profile, _, contract = evidence.custom_contract('powershell-pester-6', purpose=selected)
            inputs = evidence.custom_input_identities(ROOT, 'powershell-pester-6', purpose=selected)
            self.assertTrue(all(profile[key] == inputs[key] for key in ('grader_digest', 'fixture_digest')))
            binding = execution_binding(ROOT, profile, selected, contract)
            self.assertEqual(binding['grading'], contract)
            adapter = evidence.digest_bytes((ROOT / REPLAY_ADAPTER).read_bytes()) if mode == 'replay' else None
            self.assertEqual(binding['replay_adapter'], adapter)
            self.assertEqual(profile['qualification_cases'], {case: task.definition['source_case'] for case in task.cases(mode)})

    @unittest.skipUnless(shutil.which('pwsh'), 'Parser required; full isolation is hosted')
    def test_first_failure_and_concealed_type_failure_then_combined_admission(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root/'Subject.Tests.ps1'; runner = root/'Runner.ps1'
            candidate.write_bytes(campaign_payload(definition=self.task().definition))
            profile = ROOT/'.github/evals/pester-return-contract/transfer/profile.json'
            def admit(raw, policy=profile):
                runner.write_bytes(raw)
                result = subprocess.run(['pwsh','-NoProfile','-NonInteractive','-File',str(runner),'-Candidate',str(candidate),'-Profile',str(policy),'-AdmissionOnly'],capture_output=True,text=True,check=True,timeout=20)
                return json.loads(result.stdout)
            self.assertEqual(admit(original_runner()), {'status':'unsupported','code':'expression_policy'})
            # Diagnostic runner labels only. No candidate statements execute.
            member = original_runner().replace(b"$__pePolicy.properties -notcontains $__peNode.Member.Value) { throw 'admission' }", b"$__pePolicy.properties -notcontains $__peNode.Member.Value) { $__peResult.code = 'diagnostic_member'; throw 'admission' }")
            self.assertEqual(admit(member)['code'], 'diagnostic_member')
            count_policy = root/'count-profile.json'
            policy=json.loads(profile.read_text()); policy['properties'].append('Count');count_policy.write_text(json.dumps(policy))
            self.assertEqual(admit(member,count_policy)['code'], 'expression_policy')
            self.assertEqual(admit(runner_bytes())['status'], 'admitted')

    @unittest.skipUnless(shutil.which('pwsh'), 'Parser required')
    def test_supported_combinations_and_adjacent_prohibited_forms(self):
        task=self.task('pester-admission-controls-v2')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);runner=root/'Runner.ps1';runner.write_bytes(runner_bytes());candidate=root/'Subject.Tests.ps1'
            for name, control in task.controls().items():
                candidate.write_bytes(task.payload(name))
                result=subprocess.run(['pwsh','-NoProfile','-NonInteractive','-File',str(runner),'-Candidate',str(candidate),'-Profile',str(ROOT/'.github/evals/pester-return-contract/transfer/profile.json'),'-AdmissionOnly'],capture_output=True,text=True,check=True,timeout=20)
                actual=json.loads(result.stdout)['status']
                expected='unsupported' if control['outcome']=='unsupported' else 'invalid' if name=='malformed' else 'admitted'
                self.assertEqual(actual,expected,name)

    def test_unavailable_evidence_remains_unmeasured(self):
        grader=prospective_grader()
        for status in ('unsupported','invalid','timeout','infrastructure_error'):
            self.assertEqual(grader.assess({'status':status,'code':'fixture'},[]),(status,{'code':'fixture'}))
