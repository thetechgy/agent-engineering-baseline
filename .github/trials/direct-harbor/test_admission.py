"""Admission diagnostics, preflight failures, and evidence propagation; no inference."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

import admission_checks
import live
import run as trial
import update_live_report

SUPPORT = trial.ROOT / trial.pilot.OVERLAY / 'support'
RUNNER = SUPPORT / 'Runner.ps1'
PROFILE = SUPPORT / 'cases/pester-002/profile.json'
FIXTURES = SUPPORT / 'qualification/pester-002'
PWSH = os.environ.get('PESTER_TEST_PWSH')
PESTER = os.environ.get('PESTER_TEST_MANIFEST')


def grader():
    spec = importlib.util.spec_from_file_location('admission_grader', SUPPORT.parent/'evals/grader.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AdmissionEvidenceTests(unittest.TestCase):
    def test_unrelated_admission_predicates_remain_unchanged(self):
        source=RUNNER.read_text()
        argument=source[source.index('function __peArgument'):source.index('$__peResult =',source.index('function __peArgument'))]
        policy=source[source.index('        $__peNodes ='):source.index("        $__peResult = @{ status = 'admitted'")]
        normalized=re.sub(r"__peReject '[a-z_]+' \$[A-Za-z_]+", "throw 'admission'",argument+policy)
        # Preserve every original predicate outside the explicitly versioned
        # template allowlist/validation change; native contract tests cover that change.
        normalized=re.sub(r'        \$__peTemplateFields =.*?(?=        \$__peBlocks =)', '', normalized, flags=re.S)
        normalized=normalized.replace("foreach ($__peField in $__peTemplateFields + @('_'))", "foreach ($__peField in @($__pePolicy.properties) + @('_'))")
        self.assertEqual(hashlib.sha256(normalized.encode()).hexdigest(),
            '03b6465e9395a6cc458daaa392de6d22fba30dd9eda10a9f355871039e8001e6')

    def test_rules_are_fixed_and_supported_by_the_consumer(self):
        rules = set(re.findall(r"__peReject '([a-z_]+)'", RUNNER.read_text()))
        self.assertEqual(rules, grader().ADMISSION_RULES)
        self.assertGreater(len(rules), 1)

    def test_bounded_details_survive_but_arbitrary_text_does_not(self):
        g = grader()
        result = {'status': 'unsupported', 'code': 'admission', 'admission_rule': 'command_not_allowed',
                  'admission_diagnostic': {'ast_kind': 'CommandAst', 'line': 3, 'column': 2},
                  'message': 'PRIVATE_SOURCE', 'source': 'PRIVATE_SOURCE'}
        status, details = g.admission_result(result)
        self.assertEqual(status, 'unsupported')
        self.assertEqual(details['admission_rule'], 'command_not_allowed')
        self.assertEqual(details['admission_diagnostic']['line'], 3)
        self.assertNotIn('PRIVATE_SOURCE', json.dumps(details))
        for invalid in ({**result, 'admission_rule': 'PRIVATE_SOURCE'},
                        {**result, 'admission_diagnostic': {'ast_kind': 'CommandAst', 'line': True, 'column': 2}},
                        {**result, 'admission_diagnostic': {'ast_kind': 'CommandAst', 'line': 0, 'column': 2}},
                        {'status': 'unsupported', 'code': 'admission'}):
            self.assertEqual(g.admission_result(invalid), ('infrastructure_error', {'code': 'admission_protocol'}))
        self.assertEqual(g.admission_result({'status': 'infrastructure_error', 'code': 'admission_runner'}),
                         ('infrastructure_error', {'code': 'admission_runner'}))

    def test_rule_and_location_reach_the_single_report_without_a_grade(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = json.loads((Path(__file__).parent/'results/allocation-evidence.json').read_text())
            histories = [evidence, *reversed(evidence.get('allocation_history', []))]
            current = copy.deepcopy(next(item['arms']['current']['attempt'] for item in histories
                                         if item['arms']['current']['attempt'] is not None))
            g = grader()
            status, details = g.admission_result({'status': 'unsupported', 'code': 'admission',
                'admission_rule': 'command_not_allowed',
                'admission_diagnostic': {'ast_kind': 'CommandAst', 'line': 12, 'column': 4}})
            native = root/'jobs/current/fixture'
            tests = root/'tests'
            trial.write(tests/'entry.json', {'id': 'pester-002', 'grading_mode': 'custom_only'})
            with patch.dict(os.environ, {'HARBOR_REWARD_JSON': str(native/'verifier/reward.json')}):
                g.emit(tests, status, details)
            from harbor.models.trial.result import TrialResult
            from harbor.models.trial.config import TrialConfig, TaskConfig
            result = TrialResult(task_name='pester-002', trial_name='fixture', trial_uri='file:///fixture',
                task_id={'path': 'fixture'}, task_checksum='0'*64,
                config=TrialConfig(task=TaskConfig(path=Path('fixture'))),
                agent_info={'name': 'oracle', 'version': '0.25.0'}, verifier_result={'rewards': {'overall': 0}})
            trial.write(native/'result.json', result.model_dump(mode='json'))
            current['projection'] = trial.project(root/'jobs', {})
            trial.write(root/'public/current/attempt.json', current)
            trial.write(root/'public/allocation/attempt-fixture.json', {'variant': 'current'})
            trial.write(root/'public/allocation/closed.json', evidence['closure'])
            trial.write(root/'public/admission-preflight.json', {'passed': True, 'kind': 'admission_parser_checks'})
            with patch('builtins.print'):
                update_live_report.main(root, root/'report')
            saved = json.loads((root/'report/results.json').read_text())['live_allocation']['rows'][0]
            self.assertEqual(saved['admission'], 'command_not_allowed')
            self.assertFalse(saved['valid_grade'])
            self.assertIsNone(saved['reference_pass'])
            html = (root/'report/report.html').read_text()
            self.assertIn('command_not_allowed (CommandAst at 12:4)', html)
            self.assertIn('Credential-free admission checks: passed', html)

    def test_diagnostic_detail_is_opt_in_and_verifier_only(self):
        import toml
        from harbor.models.task.task import Task
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for enabled in (False, True):
                native, _ = trial.stage(root/str(enabled), admission_diagnostics=enabled)
                task = native/'pester-002'
                config = toml.load(task/'task.toml')
                self.assertEqual(config['verifier'].get('env', {}),
                                 {'PESTER_ADMISSION_DIAGNOSTICS': '1'} if enabled else {})
                self.assertEqual(Task(task).config.verifier.env, config['verifier'].get('env', {}))
                self.assertNotIn('PESTER_ADMISSION_DIAGNOSTICS', json.dumps(config['agent']))
                self.assertFalse((task/'environment/admission-fixtures').exists())


class AdmissionPreflightTests(unittest.TestCase):
    def test_credential_free_diagnostics_work_after_later_closed_allocations(self):
        import handoff
        closed = {'paid_execution_enabled': False, 'scheduling_stopped': True}
        with patch.dict(os.environ, {}, clear=True), patch.object(handoff.Path, 'read_text', return_value=json.dumps(closed)):
            handoff.no_credentials()
        armed = {'paid_execution_enabled': True, 'scheduling_stopped': False}
        with patch.dict(os.environ, {}, clear=True), patch.object(handoff.Path, 'read_text', return_value=json.dumps(armed)):
            with self.assertRaises(AssertionError):
                handoff.no_credentials()
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'sentinel'}, clear=True):
            with self.assertRaisesRegex(AssertionError, 'Credential-free'):
                handoff.no_credentials()

    def test_old_attempt_count_is_not_a_new_allocation_requirement(self):
        previous = {'grading_smoke_qualified': True, 'agent_attempts': 6, 'api_spend_usd': 1}
        live.validate_prior_results(previous, {'prior_campaign_attempts': 6})
        live.validate_prior_results(previous)
        with self.assertRaisesRegex(RuntimeError, 'disagree'):
            live.validate_prior_results(previous, {'prior_campaign_attempts': 5})

    def test_offline_workflow_and_container_command_are_credential_free(self):
        import ast,yaml
        source=Path(__file__).with_name('admission_validation.py').read_text()
        function=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='control')
        script=next(n.value.value for n in function.body if isinstance(n,ast.Assign) and n.targets[0].id=='script')
        compile(script,'docker-control','exec')
        workflow=yaml.safe_load((trial.ROOT/'.github/workflows/direct-harbor-trial.yml').read_text())
        job=workflow['jobs']['admission'];self.assertNotIn('environment',job)
        self.assertNotIn('secrets.',json.dumps(job));self.assertIn("== 'admission'",job['if'])
        self.assertNotIn('--privileged',source);self.assertNotIn('--volume',source)

    def test_probe_failure_is_checkpointed_and_stops_preflight(self):
        for first in (Mock(returncode=1, stdout=b'{"kind":"admission_parser_checks","passed":false}', stderr=b'PRIVATE'),
                      Mock(returncode=0, stdout=b'broken JSON PRIVATE', stderr=b'PRIVATE'),
                      Mock(returncode=0, stdout=b'{"kind":"admission_parser_checks","passed":true}', stderr=b''),
                      Mock(returncode=0, stdout=b'{"kind":"admission_parser_checks","passed":true,"inference":false,"candidate_execution":false,"controls":null}', stderr=b''),
                      subprocess.TimeoutExpired('docker', 120)):
            with tempfile.TemporaryDirectory() as directory:
                destination = Path(directory)/'check.json'
                with patch.object(live.subprocess, 'run', side_effect=[first, Mock(returncode=0)]) as execute:
                    with self.assertRaisesRegex(RuntimeError, 'preflight failed'):
                        live.admission_preflight('fixed-verifier', destination)
                saved = destination.read_text()
                self.assertFalse(json.loads(saved)['passed'])
                self.assertNotIn('PRIVATE', saved)
                command = execute.call_args_list[0].args[0]
                self.assertIn('none', command)
                self.assertIn('--read-only', command)
                self.assertNotIn('--env', command)
                self.assertEqual(execute.call_args_list[1].args[0][:3], ['docker', 'rm', '--force'])

    def test_report_failure_cannot_leave_success_metadata_or_html(self):
        import admission_validation
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'run';out=Path(directory)/'report'
            with patch.object(admission_validation,'no_credentials'), patch.object(trial,'stage',return_value=(Path(directory),{})), \
                 patch.object(admission_validation,'stage_admission_checks'), patch.object(admission_validation.subprocess,'run'), \
                 patch.object(admission_validation.subprocess,'check_output',return_value='fixture-image'), \
                 patch.object(admission_validation,'admission_preflight',return_value={'passed':True}), \
                 patch.object(admission_validation,'control',return_value={'passed':True}), \
                 patch.object(trial,'report',side_effect=RuntimeError('PRIVATE_REPORT_FAILURE')):
                self.assertEqual(admission_validation.main(root,out),1)
            evidence=json.loads((root/'public/admission-validation.json').read_text())
            self.assertFalse(evidence['passed']);self.assertEqual(evidence['code'],'report_validation')
            self.assertNotIn('PRIVATE_REPORT_FAILURE',json.dumps(evidence))
            self.assertFalse((out/'report.html').exists())
            self.assertFalse(json.loads((out/'results.json').read_text())['admission_validation']['passed'])

    def test_failed_cleanup_cannot_leave_a_passing_record(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(live.subprocess, 'run', side_effect=[
                Mock(returncode=0, stdout=json.dumps({'kind':'admission_parser_checks','passed':True,'inference':False,'candidate_execution':False,'controls':[{'control':k,'passed':True} for k in ('classic','weak','unsupported_command','unexpected_runner_error')]}).encode()),
                Mock(returncode=1, stderr=b'daemon unavailable')]):
            destination = Path(directory)/'check.json'
            with self.assertRaises(RuntimeError):
                live.admission_preflight('fixed-verifier', destination)
            self.assertEqual(json.loads(destination.read_text())['code'], 'probe_cleanup')


@unittest.skipUnless(PWSH, 'Set PESTER_TEST_PWSH for native parser checks; live preflight requires them in its image')
class NativeAdmissionTests(unittest.TestCase):
    def test_extended_real_parser_controls(self):
        result = admission_checks.checks(PWSH, RUNNER, PROFILE, FIXTURES, extended=True)
        self.assertTrue(result['passed'], result['controls'])

    def test_default_reason_does_not_require_verbose_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory)/'candidate.ps1'
            candidate.write_text("Write-Output 'PRIVATE_SOURCE'")
            result = admission_checks.inspect(PWSH, RUNNER, PROFILE, candidate)
            self.assertEqual(result, {'status': 'unsupported', 'code': 'admission', 'admission_rule': 'command_not_allowed'})

    @unittest.skipUnless(PESTER, 'Set PESTER_TEST_MANIFEST for trusted reference/mutation component checks')
    def test_existing_good_data_and_weak_controls_keep_their_grades(self):
        g = grader()
        variants = [SUPPORT/'cases/pester-002/reference/Subject.ps1',
                    *sorted((SUPPORT/'cases/pester-002/mutants').glob('*.ps1'))]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'input').mkdir()
            (root/'output').mkdir()
            candidate = root/'output/Subject.Tests.ps1'
            for style, expected, detected in [('classic', 'passed', 2), ('data', 'passed', 2), ('weak', 'failed', 0)]:
                candidate.write_text((FIXTURES/(style+'.Tests.ps1')).read_text().replace('/workspace/', str(root)+'/'))
                runs = []
                for variant in variants:
                    shutil.copyfile(variant, root/'input/Subject.ps1')
                    command = [PWSH, '-NoLogo', '-NoProfile', '-NonInteractive', '-File', str(RUNNER),
                               '-Candidate', str(candidate), '-Profile', str(PROFILE), '-Workspace', str(root),
                               '-PesterManifest', PESTER]
                    process = subprocess.run(command, capture_output=True, timeout=30, check=True)
                    runs.append(json.loads(process.stdout))
                status, details = g.assess(runs[0], runs[1:])
                self.assertEqual(status, expected, runs)
                self.assertEqual(details['reference_pass'], 1)
                self.assertEqual(details['mutants_detected'], detected)


if __name__ == '__main__':
    unittest.main()
