"""Consequential 0.9 adoption boundaries, exercised without credentials or judges."""
import copy
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))


@unittest.skipUnless(os.environ.get('EVALUATOR_ADOPTION_CONTROLS') == '1', '0.9 owning runtime qualification')
class AdoptionTests(unittest.TestCase):
    def test_released_status_keeps_confirmed_failure_and_missing_coverage(self):
        import skill_reports as reports
        from skillevaluator.models import ValidationResult, Finding, Severity
        from skillevaluator.reporting.json_reporter import JSONReporter
        result = ValidationResult(validator_name='Security Scan')
        result.add_finding(Finding(category='SECURITY', severity=Severity.HIGH,
                                  check_name='known_violation', message='Controlled violation',
                                  file_path='SKILL.md', line_number=1))
        result.mark_scan_incomplete('skillspector')
        native = json.loads(JSONReporter(include_timestamp=False).render_all([result]))
        self.assertEqual(native['overall_status'], 'failed')
        self.assertEqual(native['incomplete_scans'], ['skillspector'])
        self.assertEqual(native['results'][0]['status'], 'failed')
        self.assertEqual(len(reports.released_static_results(native)), 1)
        for key, value in (('overall_status', 'incomplete'), ('overall_passed', True)):
            bad = copy.deepcopy(native); bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                reports.released_static_results(bad)
        bad = copy.deepcopy(native); bad['results'][0]['status'] = 'passed'
        with self.assertRaises(ValueError): reports.released_static_results(bad)
        # Exercise the repository's actual catalog and public projection boundaries.
        import skill_evidence as evidence
        import evaluator_profiles as profiles
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory) / 'work'
            skill = work / '.apm/skills/scanner-control'; skill.mkdir(parents=True)
            (skill / 'SKILL.md').write_text('---\nname: scanner-control\ndescription: Fixture.\n---\n')
            bundle = Path(directory) / 'native'
            destination = bundle / 'reports/scanner-control'; destination.mkdir(parents=True)
            filename = 'skillevaluator-output-20261114000000.json'
            native['skills'] = [{'name': 'scanner-control'}]
            reports.write_json(destination / filename, native)
            for suffix in ('.md', '.html'):
                (destination / Path(filename).with_suffix(suffix)).write_text('Controlled human report')
            reports.write_json(bundle / 'reports/catalog-summary.json', {'total': 1, 'failed': 1, 'skills': [
                {'name': 'scanner-control', 'passed': False, 'reason': 'validation failed', 'json_report': filename}]})
            (bundle / 'catalog.exit').write_text('1\n')
            reports.write_json(bundle / 'versions.json', dict(profiles.candidate_versions(profiles.NEXT),
                fixture='synthetic', scanner_runtime=evidence.SCANNER_RUNTIME_NEXT,
                scanners=evidence.SCANNER_RUNTIME_NEXT['versions'],
                skillspector_revision=evidence.SCANNER_RUNTIME_NEXT['skillspector_revision']))
            reports.catalog_report(work, bundle)
            captured = evidence.normalize_static(bundle, 'scanner-control', workspace=work)
            public = evidence.project(captured)
            self.assertEqual(public['availability']['status'], 'incomplete')
            self.assertTrue(any(row['scanner'] == 'SECURITY' and row['status'] == 'failed' for row in public['scans']))
            self.assertTrue(any(row['scanner'] == 'skillspector' and row['status'] == 'incomplete' for row in public['scans']))
            self.assertTrue(any(row['check'] == 'known_violation' for row in public['findings']))
            changed = copy.deepcopy(dict(captured)); changed['findings'] = []
            with self.assertRaises(ValueError): evidence.project(changed)
            forged = copy.deepcopy(dict(public))
            forged['policy'] = evidence.make_policy({'evaluator_revision': profiles.HISTORICAL_REVISION}, provenance='runtime_recorded')
            with self.assertRaisesRegex(ValueError, 'Scanner adapter and public producer differ'):
                evidence.validate_public(forged)

    def test_actual_native_verifier_and_unscored_collection_visibility(self):
        # Invoke the installed verifier's real file reader and reward writer.
        # Its pre-judge refusal is tested in a fresh process, without mocks.
        from skillevaluator.tier3.harbor.templates import eval as verifier
        runner = """import sys

def offline(event, args):
    if event.startswith('socket.') or event in ('subprocess.Popen', 'os.system'):
        raise AssertionError('No network or child process is permitted')
sys.addaudithook(offline)
from skillevaluator.tier3.harbor.templates.eval import main
main()
"""
        for known in ('secret_exposure', 'sensitive_path_access', None):
            with self.subTest(known=known), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                call = {'tool_call_id': 'unknown', 'function_name': 'exec',
                        'arguments': {'input': 'await tools.exec_command(dynamic);'}}
                calls = [call]
                output = 'Authorization: Bearer sk-' + 'abcdefgh12345678' if known == 'secret_exposure' else 'fixture'
                observations = [{'source_call_id': 'unknown', 'content': output}]
                if known == 'sensitive_path_access':
                    calls.append({'tool_call_id': 'known', 'function_name': 'exec_command',
                                  'arguments': {'cmd': 'cat /etc/shadow'}})
                    observations.append({'source_call_id': 'known', 'content': 'fixture'})
                (root / 'trajectory.json').write_text(json.dumps({'steps': [{'source': 'agent',
                    'tool_calls': calls, 'observation': {'results': observations}}]}))
                (root / 'entry.json').write_text(json.dumps({'id': 'control', 'expected_skill': 'gh'}))
                env = {key: os.environ[key] for key in ('PATH', 'TMPDIR', 'LANG') if key in os.environ}
                env.update(PYTHONDONTWRITEBYTECODE='1', PYTHON_DOTENV_DISABLED='1',
                           HARBOR_LOGS_DIR=str(root), HARBOR_AGENT_LOGS_DIR=str(root),
                           HARBOR_ATIF_PATH=str(root / 'trajectory.json'),
                           HARBOR_VERIFIER_DIR=str(root / 'verifier'), HARBOR_ENTRY_JSON=str(root / 'entry.json'))
                run = subprocess.run([sys.executable, '-I', '-B', '-c', runner], env=env,
                                     capture_output=True, text=True, timeout=30)
                self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
                rich = json.loads((root / 'verifier/skill_evaluator_reward.json').read_text())
                self.assertEqual(rich['evaluation_status'], 'failed')
                self.assertTrue(all(rich.get(metric) is None for metric in verifier.DISPLAY_METRICS))
                self.assertEqual(json.loads((root / 'verifier/reward.json').read_text()), {'overall': 0.0})
                findings = rich['details']['security']['findings']
                self.assertEqual(sum(f['type'] == 'unsupported_tool_wrapper' for f in findings), 1)
                if known:
                    self.assertEqual(sum(f['type'] == known and f['score_impact'] is True for f in findings), 1)
                    self.assertTrue(any(f['severity'] == 'critical' for f in findings))
                else:
                    self.assertFalse(any(f['score_impact'] for f in findings))
                self.assertNotIn('abcdefgh12345678', json.dumps(rich))
                if known:
                    from skillevaluator.tier3.harbor.collector import _save_unscored_trials
                    job = root / 'job'; trial = job / 'control'; trial.mkdir(parents=True)
                    shutil.copytree(root / 'verifier', trial / 'verifier')
                    (trial / 'agent').mkdir()
                    shutil.copyfile(root / 'trajectory.json', trial / 'agent/trajectory.json')
                    (trial / 'result.json').write_text(json.dumps({'trial_name': 'control',
                        'task_name': 'control', 'verifier_result': {'rewards': {'overall': 0.0}},
                        'exception_info': {'exception_type': 'VerifierError', 'exception_message': 'Controlled verifier refusal'}}))
                    collected = root / 'collected'
                    _save_unscored_trials([], collected, job, agent='codex', variant='with_skill',
                                          persisted_names={'control': 'control'})
                    diagnostic = json.loads((collected / 'control/reward.json').read_text())
                    self.assertEqual(diagnostic['evaluation_status'], 'failed')
                    self.assertNotIn('details', diagnostic)
                    self.assertNotIn('findings', diagnostic)
                    self.assertEqual(json.loads((collected / 'control/failure.json').read_text())['status'], 'unscored')
                    # This is a retained adoption blocker, not evidence that the
                    # raw known finding survives the collected report boundary.


    def test_unlinked_multi_wrapper_secret_is_retained_once_without_attribution(self):
        from skillevaluator.tier3.eval_core.atif_helpers import extract_tool_calls_as_dicts
        from skillevaluator.tier3.eval_core.checks import check_security
        source = 'const r=await tools.exec_command({cmd:"pwd"}); text(r.output);'
        trajectory = {'steps': [{'source': 'agent', 'tool_calls': [
            {'function_name': 'exec', 'arguments': {'input': source}},
            {'function_name': 'exec', 'arguments': {'input': source}}],
            'observation': {'results': [{'content': 'Authorization: Bearer sk-' + 'abcdefgh12345678'}]}}]}
        calls = extract_tool_calls_as_dicts(trajectory)
        self.assertTrue(all(c['observation'] == '' for c in calls))
        self.assertTrue(all(c['observation_status'] == 'unobserved_inner_call' for c in calls))
        result = check_security(calls)
        findings = [f for f in result['findings'] if f['type'] == 'secret_exposure']
        self.assertEqual(len(findings), 1)
        self.assertNotIn('tool', findings[0])
        self.assertNotIn('target_skill_used_before', findings[0])

    def test_held_consumers_refuse_candidate_before_execution(self):
        import evaluator_profiles as profiles
        import skill_reports as reports
        import skill_review
        import skill_report_reviews
        with self.assertRaises(ValueError):
            reports.validate_benchmark_versions(dict(profiles.candidate_versions(profiles.NEXT), docker_compose='5.7.1'))
        with self.assertRaises(ValueError):
            skill_review.versions()
        with self.assertRaisesRegex(ValueError, 'Pinned validator environment required'):
            skill_report_reviews.load([Path('not-opened.json')], None)

    @unittest.skipUnless(os.environ.get('EVALUATOR_ADOPTION_SCAN_OUTPUT'), 'requires retained native scanner assessment')
    def test_repository_dataset_blocker_remains_failed_with_findings_visible(self):
        root = Path(os.environ['EVALUATOR_ADOPTION_SCAN_OUTPUT']) / 'repository-caveats'
        gate = json.loads((root / 'collection-gate.json').read_text())
        self.assertEqual(gate['status'], 'failed')
        self.assertIs(gate['adoption_ready'], False)
        self.assertEqual(list(gate['datasets']), ['podman'])
        dataset = gate['datasets']['podman']
        self.assertEqual(dataset['exit'], 1)
        failed = [row for row in dataset['checks'] if row['status'] != 'ok']
        self.assertEqual(len(failed), 1)
        self.assertEqual((failed[0]['path'], failed[0]['status']), ('entry 8', 'warning'))
        self.assertIn("expected_output grades skill use ('podman skill')", failed[0]['message'])
        html = (root / 'report.html').read_text()
        for marker in ('reference_missing', 'complete_with_caveats', 'RA1'):
            self.assertIn(marker, html)
