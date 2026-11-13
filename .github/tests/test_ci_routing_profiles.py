"""Routing successors preserve every historical profile and experimental input."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))
import skill_evidence as evidence


class RoutingProfiles(unittest.TestCase):
    def test_append_only_source_profiles_change_only_id_and_runtime_digest(self):
        registry = json.loads((ROOT / '.github/evals/custom-metrics.json').read_text())
        original = copy.deepcopy(registry)
        added = [k for k in registry['profiles'] if '-source-v8-' in k or k in ('pester-effectiveness-v17', 'pester-cli-pilot-retained-v13')]
        for key in added: del original['profiles'][key]
        successors = [k for k in registry['profiles'] if '-source-v7-' in k or k == 'pester-effectiveness-v16']
        self.assertEqual(len(successors), 28)
        for key in successors:
            previous = key.replace('-source-v7-', '-source-v6-') if key.startswith('campaign-') else 'pester-effectiveness-v15'
            new = registry['profiles'][key]; old = registry['profiles'][previous]
            self.assertEqual({k: v for k, v in new.items() if k not in ('id', 'runtime_digest')},
                             {k: v for k, v in old.items() if k not in ('id', 'runtime_digest')})
            self.assertNotEqual(new['runtime_digest'], old['runtime_digest'])
            del original['profiles'][key]
        digest = hashlib.sha256(json.dumps(original, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(digest, '85b150175df87e5cf58bfadafe7d4c19e010fb129fd42546d98c704fcf0d5d78')

    def test_failure_audit_successors_preserve_all_prior_profiles(self):
        registry = json.loads((ROOT / '.github/evals/custom-metrics.json').read_text())
        added = [k for k in registry['profiles'] if '-source-v8-' in k or k in ('pester-effectiveness-v17', 'pester-cli-pilot-retained-v13')]
        self.assertEqual(len(added), 29)
        for key in added:
            previous = key.replace('-source-v8-', '-source-v7-') if key.startswith('campaign-') else {'pester-effectiveness-v17': 'pester-effectiveness-v16', 'pester-cli-pilot-retained-v13': 'pester-cli-pilot-retained-v12'}[key]
            new = registry['profiles'][key]; old = registry['profiles'][previous]
            self.assertEqual({k:v for k,v in new.items() if k not in ('id','runtime_digest')},
                             {k:v for k,v in old.items() if k not in ('id','runtime_digest')})
            purpose = key if key.startswith('campaign-') else 'skill_effectiveness' if key.startswith('pester-effectiveness') else 'cli_pilot'
            self.assertEqual(evidence.custom_input_identities(ROOT, new['skill_id'], purpose=purpose)['runtime_digest'], new['runtime_digest'])
            self.assertNotEqual(new['runtime_digest'], old['runtime_digest'])
            del registry['profiles'][key]
        digest = hashlib.sha256(json.dumps(registry, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(digest, '20c02e22482cbb6c0b047bc89d718e08a9a7b424b911a4e6a871395b247b027b')

    def test_freeze_successor_changes_only_routing_and_preserves_original_bytes(self):
        base = ROOT / '.github/evals/pester-return-contract'
        current = json.loads((base / 'freeze.json').read_text())
        raw = (base / current['previous']['manifest']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), current['previous']['sha256'])
        old = json.loads(raw)
        workflow = '.github/workflows/pester-return-qualification.yml'
        self.assertEqual(old['files'][workflow], '2078943a7ee5330caab85187ec7b3bbcbfe92489cdf4dc046d302c1b1319b0b0')
        self.assertEqual(current['files'][workflow], hashlib.sha256((ROOT / workflow).read_bytes()).hexdigest())
        for key in old:
            if key not in ('id', 'previous', 'revision_purpose', 'files'):
                self.assertEqual(old[key], current[key], key)
        self.assertEqual({k: v for k, v in old['files'].items() if k != workflow},
                         {k: v for k, v in current['files'].items() if k != workflow})
