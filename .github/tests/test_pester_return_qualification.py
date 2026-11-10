"""Credential-free hosted coverage of the exact frozen return-contract pairs."""
import hashlib
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]

class HostedReturnContract(unittest.TestCase):
    def test_workflow_covers_both_sources_and_cases_without_live_capability(self):
        raw=(ROOT/'.github/workflows/pester-return-qualification.yml').read_text()
        workflow=yaml.safe_load(raw)
        expected=[{'case':'development','version':'v1'},{'case':'transfer','version':'v2'}]
        self.assertEqual(workflow['permissions'],{})
        for job in workflow['jobs'].values():
            self.assertEqual(job['permissions'],{'contents':'read'})
            self.assertNotIn('environment',job)
            self.assertEqual(job['strategy']['matrix']['include'],expected)
        for token in ('secrets.', 'OPENAI_API_KEY', ' live ', ' authenticate ', 'allocation:'):
            self.assertNotIn(token,raw)
        self.assertIn('for variant in current candidate',raw)
        for command in (' qualify ', ' prepare ', ' check-preparation '):
            self.assertIn(command,raw)
        self.assertIn('controls/qualification.json',raw)
        self.assertIn('report/consolidated/report.html',raw)
        self.assertIn('setup-compose.sh cleanup',raw)

    def test_prior_freeze_and_all_prior_profile_values_are_retained(self):
        import json
        base=ROOT/'.github/evals/pester-return-contract'
        frozen=json.loads((base/'freeze.json').read_text())
        previous=base/frozen['previous']['manifest']
        self.assertEqual(hashlib.sha256(previous.read_bytes()).hexdigest(),frozen['previous']['sha256'])
        registry=json.loads((ROOT/'.github/evals/custom-metrics.json').read_text())
        previous_profiles=json.loads((base/'history/ea26668-profile-digests.json').read_text())
        for key,digest in previous_profiles.items():
            raw=json.dumps(registry['profiles'][key],sort_keys=True,separators=(',',':')).encode()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),digest,key)
