"""Use actual pinned Harbor result semantics, including handled step exceptions."""
from pathlib import Path
import tempfile
import json
from unittest.mock import patch, Mock, AsyncMock
import unittest
from harbor.models.trial.result import TrialResult, ExceptionInfo
from harbor.models.trial.config import TrialConfig, TaskConfig
import run as trial
from pinned_codex import PinnedCodex
from harbor.agents.installed.codex import Codex


class ProjectionTests(unittest.TestCase):
    def project(self, classification='passed', status='complete', error=None, rewards=True, step_error=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); native = root / 'job/trial'; native.mkdir(parents=True)
            def exception(name):
                return ExceptionInfo(exception_type=name, exception_message='fixture failure', exception_traceback='', occurred_at='2026-11-05T00:00:00Z') if name else None
            result = TrialResult(task_name='fixture', trial_name='trial', trial_uri='file:///fixture',
                task_id={'path':'fixture'}, task_checksum='0'*64, config=TrialConfig(task=TaskConfig(path=Path('fixture'))),
                agent_info={'name':'oracle','version':'0.25.0'}, exception_info=exception(error),
                verifier_result={'rewards':{'overall':int(classification=='passed')}} if rewards else None,
                step_results=[{'step_name':'fixture','exception_info':exception(step_error)}] if step_error else None)
            trial.write(native/'result.json',result.model_dump(mode='json'))
            if classification is not None:
                trial.write(native/'verifier/skill_evaluator_reward.json',{'evaluation_status':status,'details':{'outcome':{'classification':classification}}})
            return trial.project(root,{'fixture':'passed'})[0]

    def test_correct_and_incorrect_completed_work(self):
        for status in ('passed','failed'):
            row=self.project(status)
            self.assertTrue(row['measured']); self.assertIsNone(row['failure_cause'])
            self.assertEqual(row['outcome']['classification'],status)

    def test_agent_timeout_preserves_valid_independent_grade(self):
        row=self.project(error='AgentTimeoutError')
        self.assertEqual(row['failure_cause'],'agent_exhausted_budget')
        self.assertTrue(row['measured']); self.assertEqual(row['outcome']['classification'],'passed')
        self.assertEqual(row['exceptions'][0]['exception_type'],'AgentTimeoutError')

    def test_provider_environment_and_verifier_failures_preserve_diagnostic_grade(self):
        for error,cause in [('ApiRateLimitError','model_provider_failed'),('EnvironmentStartTimeoutError','sandbox_failed'),('VerifierTimeoutError','verifier_failed')]:
            with self.subTest(error=error):
                row=self.project(error=error)
                self.assertEqual(row['failure_cause'],cause); self.assertFalse(row['measured'])
                self.assertEqual(row['outcome']['classification'],'passed')

    def test_step_exception_also_invalidates_reward(self):
        self.assertFalse(self.project(step_error='VerifierTimeoutError')['measured'])

    def test_numeric_reward_missing_unsupported_or_incomplete_evidence_is_unmeasured(self):
        for classification,status in [(None,'complete'),('unsupported','failed'),('invalid','failed'),('passed','failed')]:
            self.assertFalse(self.project(classification,status)['measured'])
        self.assertFalse(self.project(rewards=False)['measured'])

    def test_unknown_usage_stays_unknown(self):
        row=self.project()
        self.assertTrue(all(v is None for v in row['tokens'].values())); self.assertIsNone(row['cost_usd'])

    def test_postrun_mutation_cannot_pass(self):
        with self.assertRaisesRegex(RuntimeError,'Task input mutation'):
            trial.validate_control([self.project()], 'fixture','before','after',0)

    def test_postrun_failure_returns_nonzero_and_persists_false(self):
        row = self.project()
        row['task'] = 'pester-002-good'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = root / 'native/pester-002'
            (task / 'environment').mkdir(parents=True)
            (task / 'tests').mkdir()
            (task / 'task.toml').write_text('[environment]\n[verifier.environment]\n')
            output = root / 'output'
            with patch.object(trial, 'stage', return_value=(task.parent, {})), \
                 patch.object(trial.importlib.metadata, 'version', return_value='0.25.0'), \
                 patch.object(trial.subprocess, 'run', return_value=Mock(returncode=0)), \
                 patch.object(trial.subprocess, 'check_output', return_value='sha256:fixture'), \
                 patch('harbor.models.task.task.Task', return_value=Mock(checksum='same')), \
                 patch.object(trial, 'project', return_value=[row]), \
                 patch.object(trial, 'validate_control', side_effect=RuntimeError('Task input mutation')), \
                 patch.dict(trial.os.environ, {}, clear=True), patch('builtins.print'):
                self.assertEqual(trial.control('good', output), 1)
            self.assertEqual((output / 'tasks/pester-002-good/solution/solve.sh').stat().st_mode & 0o777, 0o755)
            saved = json.loads((output / 'control.json').read_text())
            self.assertFalse(saved['qualification_passed'])
            self.assertEqual(saved['integration_failure']['message'], 'Task input mutation')
            self.assertTrue(saved['calibration'][0]['measured'])

    def test_cost_estimate_includes_cached_input_and_missing_is_unknown(self):
        self.assertEqual(trial.conservative_usage_cost({'input_including_cache':60000,'cached_input':50000,'output':4000}), 1.32)
        self.assertIsNone(trial.conservative_usage_cost({'input_including_cache':None,'output':4000}))
        self.assertIsNone(trial.conservative_usage_cost({'input_including_cache':10,'cached_input':20,'output':0}))

    def test_extension_inherits_stock_launch_and_exec(self):
        self.assertIs(PinnedCodex.run, Codex.run)
        self.assertIs(PinnedCodex.exec_as_agent, Codex.exec_as_agent)

class PinTests(unittest.IsolatedAsyncioTestCase):
    async def test_version_warning_does_not_replace_the_exact_pin(self):
        from pinned_codex import check_pin
        for output,code,matched in [('WARNING: path aliases unavailable\ncodex-cli 0.155.1\n',0,True),('codex-cli 0.155.2\n',0,False),('codex-cli 0.155.1\n',1,False),('warning only',0,False)]:
            env=Mock(exec=AsyncMock(return_value=Mock(stdout=output,return_code=code)))
            self.assertEqual((await check_pin(env))['matched'],matched)
            self.assertEqual(env.exec.call_args.kwargs['user'],'agent')

class LiveMetadataTests(unittest.TestCase):
    def test_rollout_usage_is_numeric_and_activation_is_separate(self):
        import live
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'agent').mkdir()
            events=[{'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':1000,'cached_input_tokens':900,'output_tokens':25,'untrusted':'do not export'}}}},
                    {'type':'response_item','payload':{'type':'function_call','arguments':'cat .agents/skills/powershell-pester-6/SKILL.md'}}]
            (root/'agent/rollout-fixture.jsonl').write_text('\n'.join(json.dumps(x) for x in events))
            result=live.usage_and_activation(root)
            self.assertEqual(result['total_usage']['cached_input_tokens'],900)
            self.assertNotIn('untrusted',result['total_usage'])
            self.assertEqual(result['skill_file_access_attempts'],['powershell-pester-6/SKILL.md'])
            self.assertFalse(result['completion_event'])
            self.assertNotIn('correctness',result)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(live.usage_and_activation(Path(tmp))['total_usage'])

    def test_partial_or_unknown_usage_stops_additional_scheduling(self):
        import live
        self.assertFalse(live.can_schedule({'usage_complete':False,'usage_estimate_usd':0.1}))
        self.assertFalse(live.can_schedule({'usage_complete':True,'usage_estimate_usd':None}))
        self.assertFalse(live.can_schedule({'usage_complete':True,'usage_estimate_usd':3}))
        self.assertTrue(live.can_schedule({'usage_complete':True,'usage_estimate_usd':0.1}))

    def test_remote_tools_and_retry_settings_match_arms(self):
        import live
        settings=live.config()
        self.assertEqual(settings['web_search'],'disabled')
        self.assertTrue(all(v['enabled'] is False for v in settings['mcp_servers'].values()))
        self.assertEqual(settings['model_providers']['openai']['request_max_retries'],0)
        self.assertEqual(settings['model_providers']['openai']['stream_max_retries'],0)
        self.assertEqual(len(live.expected_files('current'))-len(live.expected_files('absent')),3)

if __name__=='__main__': unittest.main()

class DiagnosticRetentionTests(unittest.TestCase):
    def test_failed_native_command_exits_nonzero_and_checkpoints_without_secret(self):
        import subprocess,sys
        from diagnostics import SENTINEL
        program=r'''
import asyncio,json,logging,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
from harbor.agents.installed.codex import Codex
from diagnostics import LaunchDiagnostics
root=Path(sys.argv[1]);secret=sys.argv[2]
a=Codex(logs_dir=root,model_name='gpt-5.6-sol',version='0.155.1')
h=LaunchDiagnostics(root/'launch-diagnostics.json',(secret,));a.logger.addHandler(h)
class Fixture:
 async def exec(self,command,**kwargs):
  r=subprocess.run(command,shell=True,executable='/bin/bash',capture_output=True,text=True)
  return SimpleNamespace(return_code=r.returncode,stdout=r.stdout,stderr=r.stderr)
async def check():
 try:
  await a.exec_as_agent(Fixture(),'printf "startup failure Authorization: Bearer '+secret+'\\n" >&2; exit 23')
 except Exception as exc:
  h.exception(exc)
  assert json.loads(h.destination.read_text())['primary_failure']['exit_status']==23
  try:await a.exec_as_agent(Fixture(),'# rm -rf cleanup fixture\nexit 24')
  except Exception:pass
  return 1
 return 0
raise SystemExit(asyncio.run(check()))
'''
        with tempfile.TemporaryDirectory() as tmp:
            result=subprocess.run([sys.executable,'-c',program,tmp,SENTINEL],cwd=Path(__file__).parent,
                capture_output=True,text=True)
            self.assertEqual(result.returncode,1,result.stderr)
            artifact=(Path(tmp)/'launch-diagnostics.json').read_text()
            self.assertNotIn(SENTINEL,artifact+result.stdout+result.stderr)
            saved=json.loads(artifact)
            self.assertEqual(saved['primary_failure']['exit_status'],23)
            self.assertEqual(saved['cleanup_failures'][0]['exit_status'],24)
            self.assertIn('startup failure',saved['native_exception']['message'])
            self.assertIn('command',saved['primary_failure'])
            self.assertIn('cwd',saved['primary_failure'])
