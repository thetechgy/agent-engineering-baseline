"""Admission controls use the real parser; execution semantics are qualified in Docker."""
import json,os,shutil,unittest
from pathlib import Path
import boolean_checks
ROOT=Path(__file__).resolve().parents[3]
SUPPORT=ROOT/'.github/evals/powershell-pester-6/support'
PWSH=os.environ.get('PESTER_TEST_PWSH') or shutil.which('pwsh')

@unittest.skipUnless(PWSH,'PowerShell admission-only parser unavailable')
class BooleanAdmissionTests(unittest.TestCase):
    def test_boolean_forms_and_intentional_restrictions(self):
        result=boolean_checks.checks(PWSH,SUPPORT/'Runner.ps1',SUPPORT/'cases/pester-002/profile.json')
        self.assertTrue(result['passed'],[r for r in result['controls'] if not r['passed']])

class BooleanWorkflowTests(unittest.TestCase):
    def test_replay_cannot_select_paid_job_or_change_original_ledger(self):
        import yaml
        workflow=yaml.safe_load((ROOT/'.github/workflows/direct-harbor-trial.yml').read_text())
        job=workflow['jobs']['retrospective'];text=json.dumps(job)
        self.assertNotIn('secrets.',text);self.assertNotIn('environment',job)
        self.assertEqual(job['permissions'],{'contents':'read','actions':'read'})
        self.assertIn('boolean_replay.py',text)
        self.assertNotIn('allocation.py reserve',text);self.assertNotIn('live.py current',text)
        config=json.loads((ROOT/'.github/trials/direct-harbor/boolean-replay.json').read_text())
        self.assertEqual([config['submissions'][v]['identity']['attempt'] for v in ('current','absent')],[8,9])
