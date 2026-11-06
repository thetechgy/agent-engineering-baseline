"""Real parsing of public-contract cases, independent of the retained submission."""
import json,os,shutil,unittest
from pathlib import Path
import template_checks

ROOT=Path(__file__).resolve().parents[3]
SUPPORT=ROOT/'.github/evals/powershell-pester-6/support'
PWSH=os.environ.get('PESTER_TEST_PWSH') or shutil.which('pwsh')

@unittest.skipUnless(PWSH,'PowerShell admission-only parser unavailable')
class TemplateContractTests(unittest.TestCase):
    def test_public_fields_forms_and_deliberate_boundaries(self):
        result=template_checks.checks(PWSH,SUPPORT/'Runner.ps1',SUPPORT/'cases',SUPPORT/'qualification/pester-002')
        self.assertTrue(result['passed'],[r for r in result['controls'] if not r['passed']])

class TemplatePolicyTests(unittest.TestCase):
    def test_case_review_preserves_member_access_and_adds_only_public_template_names(self):
        # Independent pre-change member policies; new template-only permission must
        # never enlarge these sets. Cases three/four had no terminology mismatch.
        original={case:[x for x in fields if x not in ('Endpoint','BaseMilliseconds')] for case,fields in template_checks.FIELDS.items()}
        for case,members in original.items():
            profile=json.loads((SUPPORT/'cases'/case/'profile.json').read_text())
            self.assertEqual(profile['properties'],members)
            self.assertEqual(profile['admission_policy_version'],3)
            self.assertEqual(profile['template_fields'],template_checks.FIELDS[case])

class RetrospectiveBoundaryTests(unittest.TestCase):
    def test_qualification_workflow_has_no_model_secret_or_paid_environment(self):
        import yaml
        workflow=yaml.safe_load((ROOT/'.github/workflows/direct-harbor-trial.yml').read_text())
        job=workflow['jobs']['retrospective']
        self.assertNotIn('environment',job)
        self.assertNotIn('secrets.',json.dumps(job))
        self.assertIn('github.run_attempt == 1',job['if'])
        self.assertEqual(job['permissions'],{'contents':'read','actions':'read'})
        self.assertIn('retrospective.py',json.dumps(job))
        self.assertNotIn('live.py current',json.dumps(job))
