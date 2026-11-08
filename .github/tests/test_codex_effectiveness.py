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
from codex_pilot_iteration import runner_bytes

CANDIDATE = importlib.util.find_spec('skillevaluator') and importlib.metadata.version('skillevaluator') == '0.8.0'


def prospective_grader():
    module = __import__('types').ModuleType('prospective_grader')
    exec(compile(effect.grader_bytes(), 'prospective_grader', 'exec'), module.__dict__)
    return module


class Protocol(unittest.TestCase):
    def test_schedule_has_twelve_unique_attempts_and_balanced_first_arms(self):
        rows = effect.schedule()
        self.assertEqual([r['position'] for r in rows], list(range(1, 13)))
        self.assertEqual({(r['case'], r['arm'], r['trial']) for r in rows},
                         {(case, arm, trial) for case in effect.PRIMARY_CASES for arm in pilot.ARMS for trial in (1, 2, 3)})
        for offset in (0, 4, 8):
            self.assertEqual({rows[offset]['arm'], rows[offset+2]['arm']}, set(pilot.ARMS))
        self.assertNotIn('pester-001', {r['case'] for r in rows})

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
                        failed_blocks=0, failed_containers=0, assertion_failures=failed)
        status, detail = grader.assess(result(1), [result(1)] * 5)
        self.assertEqual((status, detail['reference_pass'], detail['mutants_detected']), ('failed', 0, 0))
        self.assertEqual(detail['variant_detections'], [0]*5)
        status, detail = grader.assess(result(0), [result(1), result(0)])
        self.assertEqual((status, detail['mutants_detected']), ('failed', 1))
        for unavailable in ('invalid', 'unsupported', 'timeout', 'infrastructure_error'):
            self.assertEqual(grader.assess(result(0), [{'status': unavailable, 'code': 'fixture'}]),
                             (unavailable, {'code': 'fixture'}))

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
                    self.assertEqual(actual['status'], 'unsupported' if fixture['outcome']=='unsupported' else 'admitted')

    @unittest.skipUnless(CANDIDATE and os.environ.get('APM_EXECUTABLE'), 'Pinned candidate and APM required')
    def test_actual_clean_staging_only_differs_by_target_skill_and_rejects_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, tasks, captured = pilot.stage(root, effectiveness=True)
            self.assertTrue(effect.verify_arms(tasks, captured)['complete'])
            capture = evidence.custom_capture(ROOT, 'powershell-pester-6', bundle, captured,
                purpose=effect.PURPOSE, attempts=1, agent='codex', execution_policy={
                    'environment':'docker', 'concurrency':2, 'timeout_multiplier':1.0, 'stop_on_pass':False})
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
            if fixture['outcome'] not in ('passed','failed') or name.endswith('-wrong-scope'): continue
            with self.subTest(control=name), tempfile.TemporaryDirectory() as directory:
                root=Path(directory);(root/'input').mkdir();(root/'output').mkdir()
                candidate=root/'output/Subject.Tests.ps1'
                candidate.write_bytes(fixture['payload'].replace(b'/workspace', str(root).encode()))
                runner=root/'Runner.ps1';runner.write_bytes(runner_bytes())
                files=effect.case_files(ROOT, fixture['case'])
                profile=root/'profile.json';profile.write_bytes(files['profile.json'])
                subject=json.loads(files['profile.json']).get('subject','Subject.ps1')
                results=[]
                variants=['reference/Subject.ps1']+sorted(k for k in files if k.startswith('mutants/'))
                for variant in variants:
                    (root/'input'/subject).write_bytes(files[variant])
                    process=subprocess.run(['pwsh','-NoLogo','-NoProfile','-NonInteractive','-File',str(runner),
                        '-Candidate',str(candidate),'-Profile',str(profile),'-Workspace',str(root),'-PesterManifest',manifest],
                        text=True,capture_output=True,check=True,timeout=35)
                    results.append(json.loads(process.stdout))
                status, detail=grader.assess(results[0],results[1:])
                self.assertEqual(status,fixture['outcome'], (name,results))
                if fixture['signature'] is not None:
                    self.assertEqual(detail['variant_detections'],fixture['signature'])


if __name__ == '__main__':
    unittest.main()
