"""Use actual pinned Harbor result semantics, including handled step exceptions."""
from pathlib import Path
import tempfile
import unittest
from harbor.models.trial.result import TrialResult, ExceptionInfo
from harbor.models.trial.config import TrialConfig, TaskConfig
import run as trial
from sandboxed_codex import sandbox_command


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

    def test_sandbox_extension_changes_only_launch_policy(self):
        command='codex exec --dangerously-bypass-approvals-and-sandbox --json -- public-task'
        actual=sandbox_command(command)
        self.assertEqual(actual,'codex exec --sandbox workspace-write -c approval_policy=never --json -- public-task')
        with self.assertRaises(ValueError): sandbox_command('codex exec --json')

if __name__=='__main__': unittest.main()
