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

    def test_correction_preserves_every_member_except_admission_and_successor_document(self):
        old = self.task('pester-transfer-original-v1').expected_members('pester-transfer-batch-v1', 'with_skill')
        new = self.task().expected_members('pester-transfer-batch-v1', 'with_skill')
        self.assertEqual({k for k in old if old[k] != new[k]}, {'tests/Runner.ps1', 'environment/input/EXECUTION-PROFILE.md'})
        for name, mode in [('pester-transfer-original-v1','oracle'),('pester-transfer-retrospective-v1','replay'),('pester-admission-controls-v1','oracle')]:
            task = self.task(name)
            profile, _, _ = evidence.custom_contract('powershell-pester-6', purpose=purpose(task,mode))
            self.assertTrue(all(profile[k] == v for k,v in evidence.custom_input_identities(ROOT,'powershell-pester-6',purpose=purpose(task,mode)).items()))

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
        task=self.task('pester-admission-controls-v1')
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
