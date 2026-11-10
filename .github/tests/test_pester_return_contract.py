"""Frozen candidate source and task-owned control contracts; no inference."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))
from evaluation_tasks import load
from evaluation_campaign import purpose
import skill_evidence as evidence
import skill_reports as reports

BASE = ROOT / '.github/evals/pester-return-contract'

class ReturnContract(unittest.TestCase):
    def test_snapshots_and_frozen_inputs(self):
        frozen = reports.read_json(BASE / 'freeze.json')
        for member, digest in frozen['files'].items():
            self.assertEqual(hashlib.sha256((ROOT / member).read_bytes()).hexdigest(), digest, member)
        current = BASE / 'variants/current/powershell-pester-6'
        candidate = BASE / 'variants/candidate/powershell-pester-6'
        self.assertEqual({p.relative_to(current).as_posix(): p.read_bytes() for p in reports.regular_tree(current)},
                         {p.relative_to(ROOT / '.apm/skills/powershell-pester-6').as_posix(): p.read_bytes() for p in reports.regular_tree(ROOT / '.apm/skills/powershell-pester-6')})
        for path in reports.regular_tree(current):
            if path.name != 'SKILL.md': self.assertEqual(path.read_bytes(), (candidate / path.relative_to(current)).read_bytes())
        for case in ('development', 'transfer'):
            definitions=[]
            version='v2' if case=='transfer' else 'v1'
            for variant in ('current', 'candidate'):
                task=load(ROOT / ('.github/evals/campaigns/pester-return-'+case+'-'+variant+'-'+version+'.json'))
                definitions.append(task.definition)
                controls=load(ROOT / ('.github/evals/campaigns/pester-return-'+case+'-'+variant+'-controls-'+version+'.json'))
                for mode in ('oracle','probe'):
                    selected=purpose(controls,mode)
                    profile,_,_=evidence.custom_contract('powershell-pester-6',purpose=selected)
                    self.assertEqual(profile['skill_source']['digest'],evidence.skill_content(ROOT/task.definition['source'])['digest'])
                    self.assertTrue(all(profile[k]==v for k,v in evidence.custom_input_identities(ROOT,'powershell-pester-6',purpose=selected).items()))
                from evaluation_campaign_protocol import protocol
                self.assertEqual(protocol(task)['attempt_slots'],6)
            self.assertEqual(definitions[0]['candidate'],definitions[1]['candidate'])
            self.assertEqual(definitions[0]['runtime_profile'],definitions[1]['runtime_profile'])
            self.assertEqual(definitions[0]['trials'],3)
        self.assertEqual(frozen['proposed_attempts'],24)
        transfer=load(ROOT/'.github/evals/campaigns/pester-return-transfer-candidate-controls-v2.json')
        for scenario in ('completed','task-failure','invalid'):
            for position in range(1,7):
                self.assertIn(transfer.fixture_control(scenario,{'position':position}),transfer.controls())


    def test_selected_source_identity_and_tampered_binding(self):
        import copy
        from evaluation_evidence import selected_source, selected_identity
        for variant in ('current','candidate'):
            task=load(ROOT / ('.github/evals/campaigns/pester-return-development-'+variant+'-controls-v1.json'))
            profile,_,_=evidence.custom_contract('powershell-pester-6',purpose=purpose(task,'oracle'))
            original=evidence.source('powershell-pester-6','local','thetechgy/agent-engineering-baseline',
                                     '9f81a66b343f340b681759db8c7c38a4e9e016c5','.apm/skills/powershell-pester-6')
            selected=selected_identity(ROOT,profile,original)
            self.assertEqual(selected['source_path'],task.definition['source'])
            self.assertEqual(selected['content']['digest'],profile['skill_source']['digest'])
            self.assertEqual(original['source_path'],'.apm/skills/powershell-pester-6')
            wrong=copy.deepcopy(profile);wrong['skill_source']['digest']='sha256:'+'0'*64
            with self.assertRaisesRegex(ValueError,'Unregistered campaign skill source'):
                selected_source(ROOT,wrong)

    @unittest.skipUnless(os.environ.get('PESTER_EFFECTIVENESS_LOCAL_SEMANTICS')=='1','Optional pinned local semantics')
    def test_transfer_controls_through_existing_runner_and_grader(self):
        from test_codex_effectiveness import local_semantic_fixture, prospective_grader
        manifest=subprocess.check_output([os.environ.get('CI_PWSH','pwsh'),'-NoProfile','-Command',
            '(Get-Module -ListAvailable Pester | Where-Object Version -EQ 6.2.0 | Select-Object -First 1).Path'],text=True).strip()
        self.assertTrue(manifest)
        task=load(ROOT/'.github/evals/campaigns/pester-return-transfer-candidate-v2.json')
        grader=prospective_grader();rows=[]
        for control in task.controls():
            result=local_semantic_fixture(task.payload(control),task.files(),manifest)
            status,details=grader.assess(result[0],result[1:])
            task.check(control,True,dict(classification=status,**details),{})
            from unittest.mock import patch
            with tempfile.TemporaryDirectory() as directory:
                target=Path(directory)
                reports.write_json(target/'entry.json',{'id':'pester-transfer-'+control,'grading_mode':'custom_only'})
                with patch.dict(os.environ,{'HARBOR_REWARD_JSON':str(target/'reward.json')}):
                    grader.emit(target,status,details)
                reward=reports.read_json(target/'custom_reward.json')
                sidecar=reports.read_json(target/'skill_evaluator_reward.json')
                self.assertEqual(reward['details']['outcome']['classification'],status)
                if status=='invalid':
                    self.assertNotIn('custom_metrics',reward)
                    self.assertEqual(sidecar['evaluation_status'],'failed')
                else:
                    self.assertEqual(reward['custom_metrics']['pester_test_quality'],float(status=='passed'))
            if control=='overrestricted': self.assertEqual(details['reference_pass'],0)
            rows.append(dict(control=control,classification=status,details=details,runs=result))
        target=os.environ.get('PESTER_RETURN_EVIDENCE')
        if target: reports.write_json(Path(target)/'transfer-controls.json',rows)
