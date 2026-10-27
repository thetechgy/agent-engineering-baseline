"""Pester pilot feasibility contracts. No inference or host container installation."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))
import pester_evaluations as pilot
import skill_reports as reports

SOURCE = ROOT / pilot.OVERLAY / 'support'


def grader():
    spec = importlib.util.spec_from_file_location('pester_pilot_grader', ROOT / pilot.OVERLAY / 'evals/grader.py')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class SelectionTests(unittest.TestCase):
    def test_shared_selection_preparation_preserves_other_suites(self):
        self.assertEqual(reports.benchmark_options('podman')['grading_mode'], 'default')
        self.assertEqual(reports.benchmark_options('gh')['grading_mode'], 'default_plus_custom')
        self.assertEqual(reports.benchmark_options('gh')['workspace_mode'], 'group')
        self.assertEqual(reports.benchmark_options(pilot.NAME)['grading_mode'], 'custom_only')
        self.assertTrue(reports.benchmark_options(pilot.NAME)['diagnostic_only'])
        self.assertEqual(reports.benchmark_policy(pilot.NAME)['grading'], 'custom_only')
        self.assertEqual(reports.benchmark_skill(ROOT, 'podman'), ROOT / '.apm/skills/podman')
        self.assertEqual(reports.benchmark_skill(ROOT, 'gh'), ROOT / '.github/evals/gh')
        with tempfile.TemporaryDirectory() as directory:
            prepared = reports.prepare_benchmark(ROOT, Path(directory), pilot.NAME)
            self.assertEqual(prepared, Path(directory) / 'bundle' / pilot.NAME)
            self.assertEqual(reports.benchmark_skill(ROOT, pilot.NAME, Path(directory)), prepared)
            self.assertFalse((prepared / 'evals/qualification').exists())
            self.assertFalse((prepared / 'evals/cases').exists())
            (prepared / 'SKILL.md').write_text('substituted')
            with self.assertRaisesRegex(ValueError, 'drift'):
                reports.benchmark_skill(ROOT, pilot.NAME, Path(directory))

    def test_direct_publication_cannot_admit_pilot_even_with_forged_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with self.assertRaisesRegex(ValueError, 'cannot publish history'):
                reports.publish_metrics(ROOT, path, pilot.NAME)
            with self.assertRaisesRegex(ValueError, 'cannot publish history'):
                reports.validate_metrics({}, ROOT, pilot.NAME, '0' * 40)
            with self.assertRaises(ValueError):
                reports.public_benchmark(ROOT, path, pilot.NAME, 'confirmation', path / 'public')

    def test_shared_cli_rejects_standard_and_declares_diagnostic_eligibility(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'output'
            env = {**os.environ, 'GITHUB_WORKSPACE': str(ROOT), 'GITHUB_OUTPUT': str(output), 'PYTHONDONTWRITEBYTECODE': '1'}
            command = [sys.executable, '-B', str(ROOT / '.github/scripts/skill_reports.py'), 'select', pilot.NAME]
            rejected = subprocess.run([*command, 'standard'], env=env, capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertFalse(output.exists())
            accepted = subprocess.run([*command, 'confirmation'], env=env, capture_output=True, text=True)
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            self.assertIn('history_eligible=false\n', output.read_text())
            self.assertIn('public_supported=true\n', output.read_text())

    def test_workflow_uses_shared_routing_and_independent_history_guards(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/benchmark-skills.yml').read_text())
        jobs = workflow['jobs']; steps = jobs['evaluate']['steps']
        prepare = next(s for s in steps if s.get('id') == 'preparation')
        evaluate = next(s for s in steps if s.get('id') == 'evaluation')
        self.assertIn('skill_reports.py prepare', prepare['run'])
        self.assertNotIn('powershell-pester-6', json.dumps(workflow))
        self.assertNotIn('BENCHMARK_SKILL', evaluate['run'])
        self.assertEqual(evaluate['env']['GRADING_MODE'], '${{ steps.preparation.outputs.grading_mode }}')
        self.assertIn("history_eligible == 'true'", jobs['publish-history']['if'])
        metrics = next(s for s in steps if s.get('with', {}).get('name') == 'skill-metrics')
        self.assertIn("history_eligible == 'true'", metrics['if'])
        public = next(s for s in steps if s.get('id') == 'public-benchmark')
        self.assertIn("public_supported == 'true'", public['if'])

    def test_actual_artifact_allowlist_rejects_protected_payloads_in_all_carriers(self):
        carriers = ['result.json', 'report.html', 'dataset_snapshot.json',
                    'codex/with-skill/trials/trial/reward.json',
                    'codex/with-skill/trials/trial/trial.log',
                    'codex/with-skill/trials/trial/failure.json',
                    'codex/with-skill/trials/trial/exception.txt',
                    'codex/with-skill/trials/trial/trajectory.json',
                    'codex/with-skill/trials/trial/codex.txt']
        for carrier in carriers:
            with self.subTest(carrier=carrier), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / 'raw'; root.mkdir()
                path = root / 'results' / pilot.NAME / 'run' / carrier
                path.parent.mkdir(parents=True)
                secret = 'PESTER_VERIFIER_ONLY_FIXTURE_CANARY'
                path.write_text(json.dumps({'diagnostic': secret}) if path.suffix == '.json' else secret)
                destination = Path(directory) / 'artifact'
                with self.assertRaisesRegex(ValueError, 'Protected verifier'):
                    reports.benchmark_artifacts(ROOT, root, pilot.NAME, destination)
                self.assertFalse(any(p.is_file() for p in destination.rglob('*')))

    def test_artifact_set_keeps_native_diagnostics_but_excludes_execution_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'raw'; run = root / 'results' / pilot.NAME / 'run'
            trial = run / 'codex/without-skill/trials/trial'
            trial.mkdir(parents=True)
            (trial / 'reward.json').write_text(json.dumps({'overall': 0, 'evaluation_status': 'failed',
                                                       'custom_details': {'outcome': {'classification': 'unsupported'}}}))
            for filename in ('trial.log', 'exception.txt', 'trajectory.json'):
                (trial / filename).write_text('{}' if filename.endswith('.json') else 'fixed diagnostic')
            (trial / 'candidate.Tests.ps1').write_text('not an artifact')
            (run / '_harbor-tasks/private').mkdir(parents=True)
            (run / '_harbor-tasks/private/grader.py').write_text('PESTER_VERIFIER_ONLY_NOT_PUBLISHED')
            destination = Path(directory) / 'artifact'
            with contextlib.redirect_stdout(io.StringIO()):
                reports.benchmark_artifacts(ROOT, root, pilot.NAME, destination)
            files = {p.name for p in destination.rglob('*') if p.is_file()}
            self.assertEqual(files, {'reward.json', 'trial.log', 'exception.txt', 'trajectory.json'})
            self.assertIn('unsupported', next(destination.rglob('reward.json')).read_text())


@unittest.skipUnless(importlib.util.find_spec('skillevaluator'), 'Requires the pinned evaluator environment')
class NativeStagingTests(unittest.TestCase):
    def test_qualification_fixtures_use_native_staging_without_identity_edits(self):
        from click.testing import CliRunner
        from skillevaluator.cli import cli
        from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks
        import pester_container_validation as qualification

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, fixtures = qualification.qualification_bundle(root)
            self.assertEqual(len(fixtures), 26)
            self.assertEqual(len(pilot.dataset(ROOT)), 5)
            with patch.dict(os.environ, {'SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE': str(root / 'private/key')}):
                result = CliRunner().invoke(cli, ['tier3', 'validate', str(bundle), '--strict', '--harbor-contract', '--json'])
                self.assertEqual(result.exit_code, 0, result.output)
                staged = stage_native_harbor_tasks(bundle, root / 'tasks', with_skill=False, grading_mode='custom_only')
            self.assertEqual({task.name for task in staged}, set(fixtures))
            for task in staged:
                entry = reports.read_json(task / 'tests/entry.json')
                self.assertEqual(entry['id'], task.name)
                self.assertFalse(entry['has_skill'])
                for member in reports.regular_tree(task / 'environment'):
                    self.assertNotIn(b'PESTER_VERIFIER_ONLY_', member.read_bytes())
            self.assertIn('n_concurrent=2', (ROOT / '.github/scripts/pester_container_validation.py').read_text())

    def test_recovery_retains_incomplete_native_trials_and_blocks_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports.prepare_benchmark(ROOT, root, pilot.NAME)
            run = root / 'results' / pilot.NAME / '20261025_000000'
            jobs = run / '_harbor-jobs'
            jobs.mkdir(parents=True)
            with contextlib.redirect_stdout(io.StringIO()):
                reports.recover_benchmark(ROOT, root, pilot.NAME, 'confirmation', 'cancelled')
            result = reports.read_json(run / 'result.json')
            self.assertEqual(result['report_status'], 'incomplete')
            self.assertTrue(result['diagnostic_only'])
            self.assertEqual(reports.read_json(root / 'provenance.json')['status'], 'incomplete')
            # A falsely successful downstream step must not erase recovery.
            with self.assertRaisesRegex(ValueError, 'Interrupted diagnostic recovery'):
                reports.benchmark_report(ROOT, root, pilot.NAME, 'confirmation', root / 'metrics')
            self.assertFalse((root / 'metrics').exists())

    def test_diagnostic_completion_validates_each_native_outcome_without_standard_fields(self):
        from skillevaluator.evaluation import EvaluationService
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports.prepare_benchmark(ROOT, root, pilot.NAME)
            run = root / 'results' / pilot.NAME / 'run'; run.mkdir(parents=True)
            attempts = reports.MODES['confirmation']
            case_ids = [entry['id'] for entry in pilot.dataset(ROOT)]
            total = attempts * len(case_ids)
            agent = {'model': reports.POLICY['model'], 'conditions': {}}
            config = {'grading': {'mode': 'custom_only'}, 'judge': {'enabled': False},
                      'provider': {'name': 'openai', 'model': reports.POLICY['model']},
                      'evaluated_source': {}, 'harbor': {'environment': {'value': 'docker'},
                      'n_attempts': attempts, 'n_concurrent': 2, 'stop_on_pass': False,
                      'timeout_multiplier': reports.POLICY['timeout_multiplier']}}
            for arm in ('with_skill', 'without_skill'):
                agent['conditions'][arm] = {'execution_status': 'succeeded', 'execution_errors': [],
                                            'scored_attempts': total, 'expected_attempts': total}
                for index in range(total):
                    reports.write_json(run / 'codex' / arm.replace('_', '-') / 'trials' / str(index) / 'reward.json', {
                        'entry_id': case_ids[index // attempts], 'has_skill': arm == 'with_skill', 'evaluation_status': 'complete',
                        'custom_details': {'outcome': {'classification': 'failed' if index == 0 else 'passed'}}})
            reports.write_json(run / 'result.json', {'report_status': 'complete', 'skill_name': pilot.NAME,
                               'run_config': config, 'dataset_summary': {'total_tasks': len(case_ids)}, 'agents': {'codex': agent}})
            reports.write_json(root / 'versions.json', {'python': '3.13.17', 'skillevaluator': '0.3.0',
                               'harbor': '0.13.2', 'docker_compose': '5.6.1'})
            # These are explicitly synthetic report-policy inputs, not execution
            # evidence. Native execution/collection is qualified separately.
            with patch.object(EvaluationService, 'discover_latest_results', return_value=run), \
                    patch.object(EvaluationService, 'failure_reason', return_value=None), \
                    patch('skillevaluator.source_identity.evaluated_source_revision', return_value='a' * 40), \
                    patch.dict(os.environ, {'GITHUB_SHA': 'a' * 40}), contextlib.redirect_stdout(io.StringIO()) as summary:
                reports.benchmark_report(ROOT, root, pilot.NAME, 'confirmation', root / 'metrics')
                self.assertFalse((root / 'metrics').exists())
                self.assertTrue(reports.read_json(root / 'provenance.json')['diagnostic_only'])
                self.assertIn('Public reporting is supported', summary.getvalue())
                self.assertIn('projection and upload success are reported separately', summary.getvalue())
                self.assertIn('history remains ineligible', summary.getvalue())
                self.assertNotIn('public normalization and history are unavailable', summary.getvalue())
                reward = run / 'codex/with-skill/trials/0/reward.json'
                data = reports.read_json(reward)
                data['custom_details']['outcome']['classification'] = 'unsupported'
                reports.write_json(reward, data)
                with self.assertRaisesRegex(ValueError, 'Unscoreable or unclassified'):
                    reports.benchmark_report(ROOT, root, pilot.NAME, 'confirmation', root / 'metrics')

    def test_strict_validation_and_paired_projection(self):
        from click.testing import CliRunner
        from skillevaluator.cli import cli
        from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks
        import tomllib

        with tempfile.TemporaryDirectory(prefix='pester-native-contract-') as directory:
            root = Path(directory)
            bundle = pilot.stage(ROOT, root / 'bundle' / pilot.NAME)
            with patch.dict(os.environ, {'SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE': str(root / 'private/key')}):
                validated = CliRunner().invoke(cli, ['tier3', 'validate', str(bundle), '--strict', '--harbor-contract', '--json'])
                self.assertEqual(validated.exit_code, 0, validated.output)
                arms = []
                for present in (True, False):
                    tasks = stage_native_harbor_tasks(bundle, root / str(present), with_skill=present, grading_mode='custom_only')
                    arms.append({task.name: task for task in tasks})
                    self.assertEqual(len(tasks), 5)
                    for task in tasks:
                        self.check_task_projection(task, present, tomllib)
                for case in arms[0]:
                    self.assertEqual(pilot.manifest(arms[0][case] / 'environment/input'), pilot.manifest(arms[1][case] / 'environment/input'))
                    self.assertEqual((arms[0][case] / 'instruction.md').read_bytes(), (arms[1][case] / 'instruction.md').read_bytes())

    def check_task_projection(self, task, present, tomllib):
        config = tomllib.loads((task / 'task.toml').read_text())
        self.assertEqual(config['agent']['user'], 'agent')
        self.assertEqual(config['verifier']['environment_mode'], 'separate')
        self.assertEqual(config['verifier']['environment']['network_mode'], 'no-network')
        self.assertEqual(config['verifier']['timeout_sec'], 240)
        self.assertEqual(config['verifier'].get('env', {}), {})
        self.assertEqual((task / 'environment/skills' / pilot.NAME / 'SKILL.md').exists(), present)
        self.assertFalse(list((task / 'environment/skills').glob('*/evals')))
        for member in reports.regular_tree(task / 'environment'):
            self.assertNotIn(b'PESTER_VERIFIER_ONLY_', member.read_bytes(), member.name)
        self.assertIn('PESTER_VERIFIER_ONLY_', (task / 'tests/Runner.ps1').read_text())
        self.assertFalse((task / 'environment/.github').exists())
        public = task / 'environment/input'
        original = SOURCE / 'cases' / task.name / 'input'
        for member in original.iterdir():
            self.assertEqual((public / member.name).read_bytes(), member.read_bytes())
        if task.name == 'pester-005':
            self.assertFalse((public / 'EXECUTION-PROFILE.md').exists())
            self.assertEqual(config['artifacts'], ['/workspace/output/summary.json'])
        else:
            self.assertTrue((public / 'EXECUTION-PROFILE.md').exists())
        self.assertIn('--mode custom_only', (task / 'tests/test.sh').read_text())

    def test_shared_inventory_records_local_overlay_once(self):
        import skill_evidence as evidence
        inventory = evidence.inventory(ROOT)
        rows = [r for r in inventory['skills'] if r['source']['skill_id'] == pilot.NAME]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['source']['owner'], 'local')
        self.assertEqual(rows[0]['suite']['owner'], 'overlay')

    def test_native_runner_collector_and_report_do_not_score_unsupported_zero(self):
        from skillevaluator.tier3.harbor.collector import collect_harbor_results
        from skillevaluator.evaluation.tier3_report import agent_eval_result_from_directory, render_agent_eval_html_report
        from skillevaluator.tier3.harbor.adapter import TEMPLATES_DIR
        runner = TEMPLATES_DIR / 'custom_grader_runner.py'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); jobs = root / 'jobs'
            for arm in ('with', 'without'):
                job = jobs / f'demo-codex-{arm}'; trial = job / 'pester-001__attempt'; verifier = trial / 'verifier'
                verifier.mkdir(parents=True)
                reports.write_json(job / 'result.json', {'n_total_trials': 1, 'stats': {'n_trials': 1, 'n_errors': 0,
                    'evals': {'agent__model___harbor-tasks': {'n_trials': 1, 'n_errors': 0,
                        'reward_stats': {'reward': {str(0.0 if arm == 'with' else 1.0): ['pester-001__attempt']}}}}}})
                script = verifier / 'synthetic.py'
                reward = {'overall': 0.0 if arm == 'with' else 1.0, 'entry_id': 'pester-001',
                          'details': {'outcome': {'classification': 'unsupported' if arm == 'with' else 'passed'}}}
                script.write_text('from pathlib import Path\nimport json\nPath(' + repr(str(verifier / 'reward.json')) +
                                  ').write_text(json.dumps(' + repr(reward) + '))\n')
                if arm == 'with':
                    failure = {'evaluation_status': 'failed', 'evaluation_errors': {'applicability': 'Unsupported candidate; unassessed'},
                               'custom_details': reward['details']}
                    with script.open('a') as output:
                        output.write('Path(' + repr(str(verifier / 'skill_evaluator_reward.json')) +
                                     ').write_text(json.dumps(' + repr(failure) + '))\n')
                command = subprocess.run([sys.executable, '-B', str(runner), '--mode', 'custom_only'],
                    env={'PATH': os.environ['PATH'], 'HARBOR_VERIFIER_DIR': str(verifier), 'HARBOR_GRADER': str(script)},
                    capture_output=True, text=True, timeout=15)
                self.assertEqual(command.returncode, 0, command.stderr)
                reports.write_json(trial / 'result.json', {'task_name': 'pester-001',
                    'config': {'task': {'path': '/tasks/pester-001'}},
                    'verifier_result': {'rewards': reports.read_json(verifier / 'reward.json')}})
            destination = root / 'results'
            result = collect_harbor_results('demo', ['codex'], destination, jobs, expected_cases=1,
                                           expected_case_ids=['pester-001'], expected_trials=1)
            self.assertEqual(result['execution_status'], 'failed')
            self.assertFalse(result['agents']['codex']['custom_lift'])
            summary = reports.read_json(destination / 'codex/with-skill/summary.json')
            self.assertEqual(summary['scored_attempts'], 0)
            self.assertIsNone(summary['overall_score'])
            self.assertFalse(summary['pass_at_k'])
            retained = reports.read_json(next((destination / 'codex/with-skill/trials').glob('*/reward.json')))
            self.assertEqual(retained['custom_details']['outcome']['classification'], 'unsupported')
            skill = root / 'demo'; skill.mkdir()
            reports.write_json(destination / 'run_config.json', {'grading': {'mode': 'custom_only'}})
            payload = agent_eval_result_from_directory(skill, destination, use_llm_judge=False).metadata['agent_eval']
            self.assertIsNone(payload['overall_score'])
            self.assertIsNone(payload['overall_lift'])
            html = render_agent_eval_html_report(skill, destination, use_llm_judge=False).read_text()
            self.assertTrue('Unsupported candidate' in html, 'Native report lost the unsupported diagnosis')


@unittest.skipUnless(sys.platform == 'linux', 'Execution profile targets Linux')
class ClassificationTests(unittest.TestCase):
    def test_negative_control_is_separate_from_pester_quality(self):
        g = grader()
        expected = json.loads((SOURCE / 'cases/pester-005/reference/summary.json').read_text())
        good = (SOURCE / 'qualification/pester-005/good.json').read_bytes()
        self.assertEqual(g.assess_summary(good, expected)[0], 'passed')
        self.assertEqual(g.assess_summary((SOURCE / 'qualification/pester-005/wrong.json').read_bytes(), expected)[0], 'failed')
        for value in ({**expected, 'total': True}, {**expected, 'passed': 2.0}, {**expected, 'other': 0}, []):
            self.assertEqual(g.assess_summary(json.dumps(value).encode(), expected)[0], 'failed')
        self.assertEqual(g.assess_summary(b'not JSON', expected)[0], 'invalid')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'entry.json').write_text(json.dumps({'id': 'pester-005'}))
            with patch.dict(os.environ, {'HARBOR_REWARD_JSON': str(root / 'logs/reward.json')}):
                status, detail = g.assess_summary(good, expected)
                g.emit(root, status, detail)
            reward = reports.read_json(root / 'logs/reward.json')
            self.assertEqual(reward['custom_metrics'], {'negative_control_correct': 1.0})
            self.assertFalse(any(key.startswith('pester_') for key in reward['custom_metrics']))

    def test_worker_output_rejects_oversized_valid_prefix_and_trailing_payload(self):
        g = grader()
        good = b'{"status":"admitted","code":"ok"}'
        self.assertEqual(g.read_result(io.BytesIO(good)), {'status': 'admitted', 'code': 'ok'})
        malicious = good + b' ' * g.OUTPUT_BYTES + b'{"status":"invalid"}'
        self.assertEqual(g.read_result(io.BytesIO(malicious)), {'status': 'invalid', 'code': 'output_budget'})
        for payload in (good + b'{}', b'[]', b'\xff', b''):
            with self.subTest(payload=payload):
                self.assertEqual(g.read_result(io.BytesIO(payload)), {'status': 'invalid', 'code': 'protocol'})

    def test_classifications_and_mutant_evidence(self):
        g = grader()
        good = dict(status='executed', version='6.2.0', powershell_version='7.6.6', total=3, passed=3, failed=0,
                    skipped=0, not_run=0, inconclusive=0, failed_blocks=0, failed_containers=0, assertion_failures=0)
        detected = {**good, 'passed': 2, 'failed': 1, 'assertion_failures': 1}
        self.assertEqual(g.assess(good, [detected])[0], 'passed')
        self.assertEqual(g.assess(good, [good])[0], 'failed')
        self.assertEqual(g.assess(good, [{**detected, 'assertion_failures': 0}])[0], 'failed')
        # Pester attributes this BeforeEach error to an executed It. It is a
        # completed reference failure, not an empty or undiscovered suite.
        scope_error = {**detected, 'assertion_failures': 0}
        status, detail = g.assess(scope_error, [scope_error])
        self.assertEqual(status, 'failed')
        self.assertEqual(detail['reference_pass'], 0)
        self.assertEqual(detail['mutants_detected'], 0)
        for field in ('skipped', 'not_run', 'inconclusive', 'failed_blocks', 'failed_containers'):
            with self.subTest(field=field):
                self.assertEqual(g.assess({**good, field: 1}, [detected])[0], 'invalid')
        self.assertEqual(g.assess({**good, 'total': 0, 'passed': 0}, [detected])[0], 'invalid')
        self.assertEqual(g.assess({**good, 'version': '6.1.0'}, [detected])[0], 'invalid')
        for status in g.UNSCORED:
            self.assertEqual(g.assess({'status': status, 'code': 'fixture'}, [detected])[0], status)
        self.assertLessEqual(g.MAX_VARIANTS * (g.RUN_SECONDS + g.REAP_SECONDS) + 15 + 10 + 20, g.CASE_SECONDS)

    def test_artifact_reads_reject_links_directories_and_oversize(self):
        g = grader()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / 'candidate'
            source.write_bytes(b'ok')
            self.assertEqual(g.regular_bytes(source), b'ok')
            (root / 'link').symlink_to(source)
            (root / 'directory').mkdir()
            os.mkfifo(root / 'fifo')
            os.link(source, root / 'hardlink')
            for path in (source, root / 'link', root / 'directory', root / 'fifo'):
                with self.assertRaises(ValueError): g.regular_bytes(path)
            (root / 'hardlink').unlink(); source.write_bytes(b'x' * (g.LIMIT + 1))
            with self.assertRaises(ValueError): g.regular_bytes(source)

    def test_unscoreable_reward_preserves_status_without_custom_zero_metrics(self):
        g = grader()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'entry.json').write_text(json.dumps({'id': 'pester-001', 'has_skill': True}))
            with patch.dict(os.environ, {'HARBOR_REWARD_JSON': str(root / 'logs/reward.json')}):
                for status in g.UNSCORED:
                    g.emit(root, status, {'code': 'fixture'})
                    reward = json.loads((root / 'logs/reward.json').read_text())
                    sidecar = json.loads((root / 'logs/skill_evaluator_reward.json').read_text())
                    self.assertNotIn('custom_metrics', reward)
                    self.assertEqual(sidecar['evaluation_status'], 'failed')
                    self.assertEqual(sidecar['custom_details']['outcome']['classification'], status)

    def test_malformed_private_entry_stays_an_infrastructure_failure(self):
        g = grader()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for entry in ('[]', 'null', '{}', 'malformed'):
                (root / 'entry.json').write_text(entry)
                with patch.dict(os.environ, {'HARBOR_REWARD_JSON': str(root / 'logs/reward.json')}):
                    g.emit(root, 'passed', {'negative_control_correct': 1})
                reward = reports.read_json(root / 'logs/reward.json')
                self.assertNotIn('custom_metrics', reward)
                self.assertEqual(reward['details']['outcome']['classification'], 'infrastructure_error')
                self.assertEqual(reports.read_json(root / 'logs/skill_evaluator_reward.json')['evaluation_status'], 'failed')


@unittest.skipUnless(shutil.which('pwsh'), 'PowerShell not available for parser qualification')
class RealParserTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'linux', 'Worker resource limits target Linux')
    def test_trusted_powershell_starts_under_actual_worker_resource_limits(self):
        # A fixed version command only: no submitted tests execute on the host.
        # Container identity, cgroups, and Pester execution remain hosted checks.
        g = grader()
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([shutil.which('pwsh'), '-NoLogo', '-NoProfile', '-NonInteractive',
                                     '-Command', '$PSVersionTable.PSVersion.ToString()'],
                cwd=directory, env={'PATH': '/usr/bin:/bin', 'HOME': directory, 'TMPDIR': directory,
                                   'DOTNET_EnableDiagnostics': '0', 'POWERSHELL_TELEMETRY_OPTOUT': '1'},
                preexec_fn=g.worker_limits, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, 'Trusted PowerShell startup failed under worker limits')
            self.assertRegex(result.stdout.strip(), r'^7\.\d+\.\d+$')

    def admission(self, text, case='pester-001'):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / 'Subject.Tests.ps1'; candidate.write_text(text)
            result = subprocess.run(['pwsh', '-NoLogo', '-NoProfile', '-NonInteractive', '-File', str(SOURCE / 'Runner.ps1'),
                                     '-Candidate', str(candidate), '-Profile', str(SOURCE / 'cases' / case / 'profile.json'),
                                     '-AdmissionOnly'], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0)
            return json.loads(result.stdout)['status']

    def test_independent_valid_solutions_are_admitted(self):
        for case in ('pester-001', 'pester-002', 'pester-003', 'pester-004'):
            for solution in sorted((SOURCE / 'qualification' / case).glob('*.Tests.ps1')):
                with self.subTest(case=case, solution=solution.name):
                    self.assertEqual(self.admission(solution.read_text(), case), 'admitted')

    def test_module_commands_cannot_target_other_modules_or_dependencies(self):
        submissions = [
            "Import-Module '/tests/private.psm1'", "Import-Module $path",
            "Import-Module '/workspace/input/Probe.psm1' -ArgumentList @('private')",
            "InModuleScope Pester { 1 | Should-Be 1 }", "InModuleScope $name { 1 | Should-Be 1 }",
            "Mock Get-EndpointStatus { $true }", "Mock Test-ProbeConnection { $true } -ModuleName Pester",
            "Mock $command { $true } -ModuleName Probe", "Mock Test-ProbeConnection { $true } -OutVariable __peRun",
            "Should-Invoke Get-Content -ModuleName Probe -Times 0",
            "Should -Invoke -CommandName Test-ProbeConnection -ModuleName $name -Times 0",
        ]
        for submission in submissions:
            with self.subTest(submission=submission):
                self.assertEqual(self.admission(submission, 'pester-003'), 'unsupported')

    def test_prohibited_execution_and_binding_paths_never_execute(self):
        submissions = [
            "Get-Content '/tests/grader.py'", ". '/tests/grader.py'", "& 'Get-ActivePort'",
            "Invoke-Expression 'Get-Content /tests/grader.py'", "[System.IO.File]::ReadAllText('/tests/grader.py')",
            "function Should-Be { }; Describe 'x' { It 'y' { 1 | Should-Be 2 } }",
            "$global:ErrorActionPreference='SilentlyContinue'", "$script:__peResult=@{status='executed'}",
            "$PSScriptRoot='/tests'; . \"$PSScriptRoot/../input/Subject.ps1\"",
            "foreach ($PSScriptRoot in @('/tests')) { . \"$PSScriptRoot/../input/Subject.ps1\" }",
            "Describe 'x' { It '<Get-Content /tests/grader.py>' { 1 | Should-Be 1 } }",
            'Describe x { It "<Get-Content /tests/grader.py> $x" { 1 | Should-Be 1 } }',
            "Describe 'x' { It 'y' -ForEach @{PSScriptRoot='/tests'} { 1 | Should-Be 1 } }",
            "#requires -Modules PrivateControl\nDescribe 'x' { It 'y' { 1 | Should-Be 1 } }",
            "Should-Be -Actual 1 -Expected 2 -ErrorAction Ignore", 'Get-ActivePort &',
            "Mock Get-ActivePort { 1 }", "Import-Module '/tests/private'", "$x=[scriptblock]'Get-Content /tests/private'",
            "$name='<Get-Content /tests/grader.py>'; Describe $name { It x { 1 | Should-Be 1 } }",
            "$parts='<Name>'; $name=$parts[0]+'Get-Content /tests/grader.py'+$parts[-1]; Describe $name { It x { 1 | Should-Be 1 } }",
            "Describe 'safe' -Name ('<Get-Content /tests/grader.py>') { It x { 1 | Should-Be 1 } }",
            "$options=@{Name='<Get-Content /tests/grader.py>'}; Describe 'safe' @options { It x { 1 | Should-Be 1 } }",
            "$____Pester=@{Name='forged'}; Describe 'x' { It y { 1 | Should-Be 1 } }",
            "1 | Out-Null -OutVariable global:__peResult",
            "Get-ActivePort -PipelineVariable __peRun",
        ]
        for text in submissions:
            with self.subTest(text=text): self.assertEqual(self.admission(text), 'unsupported')


if __name__ == '__main__':
    unittest.main()
