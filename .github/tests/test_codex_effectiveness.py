"""Prospective admission, discrimination and matched deployment controls; no inference."""
import copy
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))
import codex_pilot as pilot
import codex_pilot_effectiveness as effect
import skill_evidence as evidence
import skill_reports as reports
from codex_pilot_effectiveness import runner_bytes

CANDIDATE = importlib.util.find_spec('skillevaluator') and importlib.metadata.version('skillevaluator') == '0.8.0'


def prospective_grader():
    module = __import__('types').ModuleType('prospective_grader')
    exec(compile(effect.grader_bytes(), 'prospective_grader', 'exec'), module.__dict__)
    return module


def local_semantic_fixture(payload, files, manifest):
    """Existing local component probe, shared by frozen and exploratory controls.

    The production runner and grader own execution semantics. This test helper
    only maps the reviewed workspace path and supplies verifier-owned fixtures.
    Hosted Docker qualification remains the source of isolation evidence.
    """
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / 'input').mkdir()
        (root / 'output').mkdir()
        candidate = root / 'output/Subject.Tests.ps1'
        candidate.write_bytes(payload.replace(b'/workspace', str(root).encode()))
        runner = root / 'Runner.ps1'
        runner.write_bytes(runner_bytes())
        profile = root / 'profile.json'
        profile.write_bytes(files['profile.json'])
        subject = json.loads(files['profile.json']).get('subject', 'Subject.ps1')
        results = []
        variants = ['reference/Subject.ps1'] + sorted(k for k in files if k.startswith('mutants/'))
        for variant in variants:
            (root / 'input' / subject).write_bytes(files[variant])
            process = subprocess.run([os.environ.get('CI_PWSH', 'pwsh'), '-NoLogo', '-NoProfile',
                '-NonInteractive', '-File', str(runner), '-Candidate', str(candidate), '-Profile', str(profile),
                '-Workspace', str(root), '-PesterManifest', manifest],
                text=True, capture_output=True, check=True, timeout=35)
            results.append(json.loads(process.stdout))
        return results


class Protocol(unittest.TestCase):
    def test_native_qualification_overview_is_distinct_from_synthetic_judge_transport(self):
        import skill_analysis as analysis
        record = {'custom': {'purpose': effect.CONTROL_PURPOSE},
                  'policy': {'producer_profile': 'skillevaluator-0.8.0-offline-v4'}}
        self.assertEqual(analysis.coverage_label({'behavioral_results':[record]}),
                         'Credential-free prospective grading qualification')
        record.pop('custom')
        self.assertEqual(analysis.coverage_label({'behavioral_results':[record]}),
                         'Includes synthetic candidate qualification; candidate quality unavailable')

    def test_schedule_has_twelve_unique_attempts_and_balanced_first_arms(self):
        rows = effect.schedule()
        self.assertEqual([r['position'] for r in rows], list(range(1, 13)))
        self.assertEqual({(r['case'], r['arm'], r['trial']) for r in rows},
                         {(case, arm, trial) for case in effect.PRIMARY_CASES for arm in pilot.ARMS for trial in (1, 2, 3)})
        for offset in (0, 4, 8):
            self.assertEqual({rows[offset]['arm'], rows[offset+2]['arm']}, set(pilot.ARMS))
        self.assertNotIn('pester-001', {r['case'] for r in rows})

    def test_supported_profiles_render_defects_and_admission_diagnostics(self):
        import skill_report as report
        import skill_analysis as analysis
        run = {'record_id': 'synthetic-report', 'custom': {
            'complete_paired_population': False, 'purpose': effect.CONTROL_PURPOSE,
            'agent': 'oracle', 'metrics': [],
            'outcomes': {arm: {kind: 0 for kind in (*evidence.CUSTOM_OUTCOMES, 'missing')}
                         for arm in ('with_skill', 'without_skill')}}}
        value = {'custom': {'agent_version': 'oracle', 'cases': [], 'definitions': []}, 'observations': []}
        for attempt, (detected, basis, outcome) in enumerate(((1, 'assertion', 'passed'), (0, 'survived', 'failed'), (None, 'unavailable', 'unsupported')), 1):
            value['observations'].append({'id': f'synthetic-observation-{attempt}',
                'case_id': 'pester-003', 'arm': 'with_skill', 'attempt': attempt,
                'custom': {'outcome': outcome, 'admission_reason': 'test_failure_kind', 'measurements': [],
                    'defects': [{'id': 'forwarding', 'detected': detected, 'basis': basis}],
                    'usage': {key: None for key in ('n_input_tokens', 'n_cache_tokens', 'n_output_tokens',
                                                 'agent_execution_seconds', 'verifier_seconds')}}})
        profiles = ('pester-effectiveness-v3', 'pester-effectiveness-v4', 'pester-effectiveness-v5',
                    effect.PROFILE_ID, 'pester-cli-pilot-retained-v6')
        for profile in dict.fromkeys(profiles):
            with self.subTest(profile=profile):
                value['custom']['profile_id'] = profile
                value['custom']['purpose'] = effect.CONTROL_PURPOSE
                self.assertTrue(analysis.pilot_record(value))
                original = copy.deepcopy(value)
                html = report.custom_measurements(run, value)
                self.assertIn('<caption>Pilot admission diagnostics</caption>', html)
                self.assertIn('test_failure_kind', html)
                if profile.startswith('pester-effectiveness-'):
                    self.assertIn('<caption>Seeded contract defects by case and arm</caption>', html)
                    defects = html.split('<caption>Seeded contract defects by case and arm</caption>', 1)[1].split('</table>', 1)[0]
                    self.assertIn('>Attempt<', defects)
                    for observation in value['observations']:
                        self.assertIn(f'>{observation["attempt"]}<', defects)
                        self.assertIn(report.link('observation', (run['record_id'], observation['id']), 'Trial and evidence'), defects)
                    for label in ('forwarding', '>Detected<', '>Missed<', '>Unavailable<', 'assertion', 'survived'):
                        self.assertIn(label, html)
                else:
                    self.assertNotIn('Seeded contract defects by case and arm', html)
                self.assertEqual(value, original)

    def test_profile_hashes_and_historical_profiles_are_distinct(self):
        profile, _, _ = evidence.custom_contract('powershell-pester-6', ROOT, purpose=effect.PURPOSE)
        identities = evidence.custom_input_identities(ROOT, 'powershell-pester-6', purpose=effect.PURPOSE)
        self.assertTrue(all(profile[k] == v for k, v in identities.items()))
        self.assertEqual(profile['cases']['pester-003']['denominators']['pester_mutation_detection'], 5)
        self.assertEqual(profile['qualification_cases'], {k: v['case'] for k, v in effect.fixtures().items()})
        registry = evidence.custom_registry(ROOT)
        self.assertEqual(registry['active_profiles']['powershell-pester-6'], 'pester-pilot-v3')
        self.assertNotEqual(registry['profiles']['pester-cli-pilot-retained-v2']['runtime_digest'],
                            registry['profiles']['pester-cli-pilot-retained-v3']['runtime_digest'])
        self.assertEqual(registry['profiles']['pester-cli-pilot-retained-v2']['grader_digest'],
                         registry['profiles']['pester-cli-pilot-retained-v3']['grader_digest'])

    def test_real_assertion_failure_cannot_claim_mutant_detection(self):
        grader = prospective_grader()
        def result(failed):
            return dict(status='executed', version='6.2.0', powershell_version='7.6.9', total=1,
                        passed=1-failed, failed=failed, skipped=0, not_run=0, inconclusive=0,
                        failed_blocks=0, failed_containers=0, assertion_failures=failed, mock_failures=0)
        status, detail = grader.assess(result(1), [result(1)] * 5)
        self.assertEqual((status, detail['reference_pass'], detail['mutants_detected']), ('failed', 0, 0))
        self.assertEqual(detail['variant_detections'], [0]*5)
        runtime_failure = result(1); runtime_failure['assertion_failures'] = 0; runtime_failure['mock_failures'] = 1
        status, detail = grader.assess(result(0), [runtime_failure])
        self.assertEqual((status, detail['variant_failure_kinds']), ('passed', ['mock_parameter_mismatch']))
        unknown_failure = result(1); unknown_failure['assertion_failures'] = 0
        self.assertEqual(grader.assess(result(0), [unknown_failure]), ('unsupported', {'code':'test_failure_kind'}))
        malformed = result(0); malformed['assertion_failures'] = 1
        self.assertEqual(grader.assess(malformed, [result(1)])[0], 'invalid')
        status, detail = grader.assess(result(0), [result(1), result(0)])
        self.assertEqual((status, detail['mutants_detected']), ('failed', 1))
        for unavailable in ('invalid', 'unsupported', 'timeout', 'infrastructure_error'):
            self.assertEqual(grader.assess(result(0), [{'status': unavailable, 'code': 'fixture'}]),
                             (unavailable, {'code': 'fixture'}))

    @unittest.skipUnless(shutil.which('pwsh'), 'PowerShell parser required')
    def test_guided_invocation_forms_are_versioned_and_scope_rejections_remain(self):
        from codex_pilot_iteration import runner_bytes as legacy
        selected = ('invocation-options', 'module-parameters', 'exclusive-misuse',
                    'parameters-protected', 'verifiable-target', 'verifiable-scope')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);candidate=root/'Subject.Tests.ps1';runner=root/'Runner.ps1'
            for name in selected:
                fixture=effect.fixtures()[('pester-004-' if name=='verifiable-scope' else 'pester-003-')+name];candidate.write_bytes(fixture['payload'])
                outcomes=[]
                for raw in (legacy(), effect.runner_bytes()):
                    runner.write_bytes(raw)
                    result=subprocess.run(['pwsh','-NoLogo','-NoProfile','-NonInteractive','-File',str(runner),
                        '-Candidate',str(candidate),'-Profile',str(ROOT/'.github/evals/powershell-pester-6/support/cases'/fixture['case']/'profile.json'),
                        '-AdmissionOnly'],capture_output=True,text=True,check=True,timeout=15)
                    outcomes.append(json.loads(result.stdout)['status'])
                with self.subTest(style=name):
                    self.assertEqual(outcomes[1], 'admitted' if fixture['outcome']=='passed' else 'unsupported')
                    if fixture['outcome']=='passed': self.assertEqual(outcomes[0], 'unsupported')

    @unittest.skipUnless(shutil.which('pwsh'), 'PowerShell parser required')
    def test_every_fixture_has_its_declared_admission_and_restrictions_stay_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = root / 'Runner.ps1'; runner.write_bytes(runner_bytes())
            cases = effect.fixtures()
            for name, fixture in cases.items():
                if name.endswith('-missing'): continue
                candidate = root / 'Subject.Tests.ps1'; candidate.write_bytes(fixture['payload'])
                result = subprocess.run(['pwsh', '-NoLogo', '-NoProfile', '-NonInteractive', '-File', str(runner),
                    '-Candidate', str(candidate), '-Profile', str(ROOT / '.github/evals/powershell-pester-6/support/cases' / fixture['case'] / 'profile.json'),
                    '-AdmissionOnly'], capture_output=True, text=True, timeout=15, check=True)
                actual = json.loads(result.stdout)
                with self.subTest(control=name):
                    self.assertEqual(actual['status'], 'unsupported' if fixture['outcome']=='unsupported' and not name.endswith('-unclassified-failure') else 'admitted')

    @unittest.skipUnless(CANDIDATE and os.environ.get('APM_EXECUTABLE'), 'Pinned candidate and APM required')
    def test_actual_clean_staging_only_differs_by_target_skill_and_rejects_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, tasks, captured = pilot.stage(root, effectiveness=True)
            self.assertTrue(effect.verify_arms(tasks, captured)['complete'])
            dataset = reports.read_json(bundle / 'evals/evals.json')
            dataset['evals'] = [r for r in dataset['evals'] if r['id'] in effect.PRIMARY_CASES]
            reports.write_json(bundle / 'evals/evals.json', dataset)
            capture = evidence.custom_capture(ROOT, 'powershell-pester-6', bundle,
                [r for r in captured if r['case_id'] in effect.PRIMARY_CASES],
                purpose=effect.PURPOSE, attempts=3, agent='codex', execution_policy={
                    'environment':'docker', 'concurrency':1, 'timeout_multiplier':1.0, 'stop_on_pass':False})
            evidence.validate_custom_capture(capture, 'powershell-pester-6', ROOT)
            control_root = root / 'controls'; control_root.mkdir()
            control_bundle, _, control_capture = pilot.stage(control_root, controls=True, effectiveness=True)
            value = evidence.custom_capture(ROOT, 'powershell-pester-6', control_bundle, control_capture,
                purpose=effect.CONTROL_PURPOSE, attempts=1, agent='oracle', execution_policy={
                    'environment':'docker', 'concurrency':2, 'timeout_multiplier':1.0, 'stop_on_pass':False})
            evidence.validate_custom_capture(value, 'powershell-pester-6', ROOT)
            changed = copy.deepcopy(captured)
            changed[0]['members']['instruction.md'] = 'sha256:' + '0'*64
            with self.assertRaises(AssertionError): effect.verify_arms(tasks, changed)
            task = tasks['with_skill'][0]
            (task / 'tests/Runner.ps1').write_bytes(b'substituted')
            with self.assertRaisesRegex(ValueError, 'runner drift'):
                evidence.capture_custom_tasks(ROOT, 'powershell-pester-6', [task], 'with_skill', purpose=effect.PURPOSE)

    @unittest.skipUnless(os.environ.get('PESTER_EFFECTIVENESS_LOCAL_SEMANTICS') == '1', 'Optional pinned local Pester semantic check')
    def test_real_runner_discriminates_references_and_each_contract_mutant(self):
        # Supplemental local execution only. Hosted Docker qualification owns isolation evidence.
        manifest = subprocess.check_output(['pwsh','-NoLogo','-NoProfile','-Command',
            '(Get-Module -ListAvailable Pester | Where-Object Version -EQ 6.2.0 | Select-Object -First 1).Path'], text=True).strip()
        grader = prospective_grader()
        for name, fixture in effect.fixtures().items():
            if (fixture['outcome'] not in ('passed','failed') and not name.endswith('-unclassified-failure')) or name.endswith('-wrong-scope'): continue
            with self.subTest(control=name):
                results = local_semantic_fixture(fixture['payload'], effect.case_files(ROOT, fixture['case']), manifest)
                status, detail = grader.assess(results[0], results[1:])
                self.assertEqual(status, fixture['outcome'], (name, results))
                if fixture['signature'] is not None:
                    self.assertEqual(detail['variant_detections'], fixture['signature'])


if __name__ == '__main__':
    unittest.main()
