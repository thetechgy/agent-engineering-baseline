"""Credential-free prospective contract and selection controls for the one-pair pilot."""
import importlib.util
import importlib.metadata
import json
import os
import shutil
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

CANDIDATE_RUNTIME = bool(importlib.util.find_spec('skillevaluator')) and importlib.metadata.version('skillevaluator') == '0.8.0'
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.github/scripts'))
from codex_pilot_contract import PROFILE, configuration, runner_bytes
import codex_pilot as pilot
import skill_evidence as evidence


class PilotContracts(unittest.TestCase):
    def test_config_keeps_sandbox_model_provider_and_disables_retries(self):
        c=configuration()
        self.assertEqual((c['model'],c['model_reasoning_effort']),('gpt-6.1-sol','high'))
        self.assertEqual(c['sandbox_mode'],'workspace-write')
        self.assertFalse(c['sandbox_workspace_write']['network_access'])
        self.assertEqual(c['model_providers']['pilot']['base_url'],'https://api.openai.com/v1')
        self.assertEqual(c['model_providers']['pilot']['request_max_retries'],0)
        self.assertNotIn('rollout_budget',c['features'])
        probe=configuration('http://127.0.0.1:8765/v1')
        probe['model_providers']['pilot']['base_url']=c['model_providers']['pilot']['base_url']
        self.assertEqual(probe,c)

    def test_runner_correction_is_prospective_and_names_fixed_reasons(self):
        old=(ROOT/'.github/evals/powershell-pester-6/support/Runner.ps1').read_bytes()
        new=runner_bytes()
        self.assertNotEqual(old,new)
        self.assertNotIn(b"'Be', 'BeTrue', 'BeFalse'",old)
        self.assertIn(b"'Be', 'BeTrue', 'BeFalse'",new)
        self.assertIn(b"$__peResult.code = 'test_name_template'",new)
        self.assertIn(b"$__peResult.code = 'command_parameter'",new)
        self.assertIn(b"$__peText.Contains('<') -or $__peText.Contains('>')",new)

    def test_frozen_pilot_has_one_case_one_attempt_and_preserves_active_profile(self):
        self.assertEqual(PROFILE['case'],'pester-001')
        self.assertEqual(PROFILE['attempts_per_arm'],1)
        registry=evidence.custom_registry(ROOT)
        self.assertEqual(registry['active_profiles']['powershell-pester-6'],'pester-pilot-v3')
        profile,_,_=evidence.custom_contract('powershell-pester-6',ROOT,purpose='cli_pilot')
        self.assertEqual(set(profile['cases']),{'pester-001'})
        self.assertEqual(profile['runtime']['codex'],'0.167.0')
        identities=evidence.custom_input_identities(ROOT,'powershell-pester-6',purpose='cli_pilot')
        self.assertTrue(all(profile[k]==v for k,v in identities.items()))

    @unittest.skipUnless(CANDIDATE_RUNTIME,'Requires qualified 0.8.0 owning runtime')
    def test_native_command_has_no_retry_and_exact_runtime(self):
        with tempfile.TemporaryDirectory() as d:
            cmd=pilot.command(Path(d),'with_skill')
        self.assertEqual(cmd[cmd.index('--n-attempts')+1],'1')
        self.assertEqual(cmd[cmd.index('--max-retries')+1],'0')
        self.assertIn('version="0.167.0"',cmd)
        self.assertNotIn('version="0.155.1"',cmd)
        self.assertIn('codex_pilot_agent:PilotCodex',cmd)
        self.assertEqual(cmd[cmd.index('--model')+1],'gpt-6.1-sol')

    @unittest.skipUnless(shutil.which('pwsh'), 'Requires local PowerShell for admission')
    def test_actual_admission_boolean_and_template_controls(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            fixed=root/'Runner.ps1'; fixed.write_bytes(runner_bytes())
            original=ROOT/'.github/evals/powershell-pester-6/support/Runner.ps1'
            profile=ROOT/'.github/evals/powershell-pester-6/support/cases/pester-001/profile.json'
            cases={
                'boolean': ("Describe 'boolean' { It 'asserts' { $true | Should -BeTrue; $false | Should -BeFalse } }", 'admitted', 'ok'),
                'template': ("Describe 'reject <$(1)>' { It 'asserts' { 1 | Should -Be 1 } }", 'unsupported', 'test_name_template'),
                'parameter': ("Describe 'reject' { It 'asserts' { 1 | Should -Be 2 -ErrorAction SilentlyContinue } }", 'unsupported', 'command_parameter'),
                'dynamic': ("Describe 'reject' { It 'asserts' { & 'Get-Content' '/tests/case/profile.json' } }", 'unsupported', 'command_policy'),
            }
            for name,(text,status,code) in cases.items():
                candidate=root/(name+'.ps1');candidate.write_text(text)
                def invoke(runner):
                    result=subprocess.run(['pwsh','-NoLogo','-NoProfile','-NonInteractive','-File',str(runner),'-Candidate',str(candidate),'-Profile',str(profile),'-AdmissionOnly'],capture_output=True,text=True,check=True,timeout=20)
                    return json.loads(result.stdout)
                self.assertEqual(invoke(fixed),{'status':status,'code':code})
                if name=='boolean': self.assertEqual(invoke(original),{'status':'unsupported','code':'admission'})

    @unittest.skipUnless(os.environ.get('APM_EXECUTABLE') and CANDIDATE_RUNTIME, 'Requires verified APM and owning runtime')
    def test_actual_staging_capture_rejects_cohort_runner_and_attempt_drift(self):
        from harbor.models.task.task import Task
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for controls in (False, True):
                target=root/str(controls);target.mkdir()
                bundle,tasks,rows=pilot.stage(target,controls=controls)
                purpose='cli_pilot_control' if controls else 'cli_pilot'
                self.assertEqual(len(rows),14 if controls else 2)
                capture=evidence.custom_capture(ROOT,PROFILE['skill'],bundle,rows,purpose=purpose,
                    attempts=1,agent='oracle' if controls else 'codex',execution_policy={
                    'environment':'docker','concurrency':2,'timeout_multiplier':1.0,'stop_on_pass':False})
                evidence.validate_custom_capture(capture,PROFILE['skill'],ROOT)
                self.assertEqual({Task(t).checksum for arm in tasks.values() for t in arm},{r['task_checksum'] for r in rows})
                capture['attempts']=2
                with self.assertRaisesRegex(ValueError,'attempts drift'):
                    evidence.validate_custom_capture(capture,PROFILE['skill'],ROOT)
                capture['attempts']=1
                capture['case_ids'].append('pester-002')
                with self.assertRaises(ValueError): evidence.validate_custom_capture(capture,PROFILE['skill'],ROOT)

    @unittest.skipUnless(CANDIDATE_RUNTIME, 'Requires qualified owning runtime')
    def test_exec_json_usage_keeps_missing_unknown_and_rejects_invalid_counts(self):
        from codex_pilot_agent import PilotCodex
        from harbor.models.agent.context import AgentContext
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); context=AgentContext(); agent=SimpleNamespace(logs_dir=root)
            (root/'codex.txt').write_text('{"type":"turn.failed","error":{"message":"refused"}}\n')
            PilotCodex.populate_context_post_run(agent,context)
            self.assertIsNone(context.n_input_tokens)
            (root/'codex.txt').write_text(json.dumps({'type':'turn.completed','usage':{
                'input_tokens':100,'cached_input_tokens':20,'output_tokens':10}})+'\n')
            PilotCodex.populate_context_post_run(agent,context)
            self.assertEqual((context.n_input_tokens,context.n_cache_tokens,context.n_output_tokens),(100,20,10))
            (root/'codex.txt').write_text(json.dumps({'type':'turn.completed','usage':{
                'input_tokens':100,'cached_input_tokens':101,'output_tokens':10}})+'\n')
            with self.assertRaises(ValueError): PilotCodex.populate_context_post_run(agent,context)

    @unittest.skipUnless(CANDIDATE_RUNTIME, 'Requires qualified owning runtime')
    def test_exact_submission_handoff_rejects_changed_verifier_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);trial=root/'jobs/job/trial';artifact=root/'evidence';artifact.mkdir()
            path=trial/'artifacts/workspace/output/Subject.Tests.ps1';path.parent.mkdir(parents=True)
            path.write_bytes(b"Describe 'proof' { It 'checks' { 1 | Should -Be 1 } }\n")
            receipt={'sha256':pilot.sha(path),'bytes':path.stat().st_size}
            for directory,name in (('agent','pilot-produced-submission.json'),('verifier','pilot-verified-submission.json')):
                target=trial/directory/name;target.parent.mkdir(parents=True);target.write_text(json.dumps(receipt))
            pilot.retain(root,artifact)
            self.assertEqual(next((artifact/'submissions').rglob('Subject.Tests.ps1')).read_bytes(),path.read_bytes())
            (trial/'verifier/pilot-verified-submission.json').write_text(json.dumps({**receipt,'sha256':'0'*64}))
            with self.assertRaisesRegex(ValueError,'handoff mismatch'): pilot.retain(root,artifact)

    @unittest.skipUnless(importlib.util.find_spec('skillevaluator'), 'Requires pinned evidence runtime')
    def test_historical_public_record_cannot_claim_pilot_identity(self):
        from test_custom_metrics import synthetic_native
        with tempfile.TemporaryDirectory() as d:
            native,_=synthetic_native(Path(d),complete=True)
            public=json.loads(evidence.encoded(evidence.project(evidence.normalize_behavioral(native,PROFILE['skill']))))
            public['custom']['purpose']='cli_pilot'
            with self.assertRaisesRegex(ValueError,'Pilot profile/purpose mismatch'):
                evidence.validate_custom_evidence(public,public=True)

    def test_wrong_allocation_rejects_before_native_setup(self):
        with patch.object(sys,'argv',['pilot','live','--output','unused','--approval','wrong']), self.assertRaises(SystemExit):
            pilot.main()


if __name__=='__main__': unittest.main()
