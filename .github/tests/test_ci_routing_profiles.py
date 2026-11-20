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
        registry['profiles'].pop('gh-deterministic-gate-v6')
        registry['profiles'].pop('gh-native-oracle-v2')
        registry['active_profiles']['gh'] = 'gh-deterministic-gate-v5'
        registry['profiles'] = {k:v for k,v in registry['profiles'].items() if '-source-v11-' not in k and '-source-v12-' not in k and '-source-v13-' not in k and '-source-v14-' not in k and '-source-v15-' not in k and '-source-v16-' not in k and '-source-v17-' not in k and '-source-v18-' not in k and '-source-v19-' not in k and '-source-v20-' not in k and '-source-v21-' not in k and '-source-v22-' not in k and '-source-v23-' not in k and '-source-v24-' not in k and '-source-v33-' not in k and '-source-v31-' not in k and '-source-v30-' not in k and '-source-v29-' not in k and '-source-v28-' not in k and '-source-v27-' not in k and '-source-v26-' not in k and k not in ('pester-effectiveness-v30', 'pester-cli-pilot-retained-v18', 'pester-effectiveness-v31', 'pester-cli-pilot-retained-v19', 'pester-effectiveness-v32', 'pester-effectiveness-v33', 'pester-effectiveness-v34', 'pester-effectiveness-v36', 'pester-cli-pilot-retained-v20') and '-source-v25-' not in k and k not in ('pester-effectiveness-v20', 'pester-effectiveness-v21', 'pester-effectiveness-v22', 'pester-effectiveness-v23', 'pester-effectiveness-v24', 'pester-effectiveness-v25', 'pester-cli-pilot-retained-v16', 'pester-effectiveness-v26', 'pester-effectiveness-v27', 'pester-effectiveness-v28', 'pester-cli-pilot-retained-v17', 'pester-effectiveness-v29')}
        registry['metrics'].pop('gh.authorization.v2')
        original = copy.deepcopy(registry)
        added = [k for k in registry['profiles'] if ('-source-v8-' in k or '-source-v9-' in k or '-source-v10-' in k) or k in ('pester-effectiveness-v17', 'pester-cli-pilot-retained-v13', 'pester-effectiveness-v18', 'pester-cli-pilot-retained-v14', 'pester-effectiveness-v19', 'pester-cli-pilot-retained-v15')]
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
        registry['profiles'].pop('gh-deterministic-gate-v6')
        registry['profiles'].pop('gh-native-oracle-v2')
        registry['active_profiles']['gh'] = 'gh-deterministic-gate-v5'
        registry['profiles'] = {k:v for k,v in registry['profiles'].items() if '-source-v11-' not in k and '-source-v12-' not in k and '-source-v13-' not in k and '-source-v14-' not in k and '-source-v15-' not in k and '-source-v16-' not in k and '-source-v17-' not in k and '-source-v18-' not in k and '-source-v19-' not in k and '-source-v20-' not in k and '-source-v21-' not in k and '-source-v22-' not in k and '-source-v23-' not in k and '-source-v24-' not in k and '-source-v33-' not in k and '-source-v31-' not in k and '-source-v30-' not in k and '-source-v29-' not in k and '-source-v28-' not in k and '-source-v27-' not in k and '-source-v26-' not in k and k not in ('pester-effectiveness-v30', 'pester-cli-pilot-retained-v18', 'pester-effectiveness-v31', 'pester-cli-pilot-retained-v19', 'pester-effectiveness-v32', 'pester-effectiveness-v33', 'pester-effectiveness-v34', 'pester-effectiveness-v36', 'pester-cli-pilot-retained-v20') and '-source-v25-' not in k and k not in ('pester-effectiveness-v20', 'pester-effectiveness-v21', 'pester-effectiveness-v22', 'pester-effectiveness-v23', 'pester-effectiveness-v24', 'pester-effectiveness-v25', 'pester-cli-pilot-retained-v16', 'pester-effectiveness-v26', 'pester-effectiveness-v27', 'pester-effectiveness-v28', 'pester-cli-pilot-retained-v17', 'pester-effectiveness-v29')}
        registry['metrics'].pop('gh.authorization.v2')
        for key in [k for k in registry['profiles'] if '-source-v9-' in k or '-source-v10-' in k or k in ('pester-effectiveness-v18', 'pester-cli-pilot-retained-v14', 'pester-effectiveness-v19', 'pester-cli-pilot-retained-v15')]: del registry['profiles'][key]
        added = [k for k in registry['profiles'] if '-source-v8-' in k or k in ('pester-effectiveness-v17', 'pester-cli-pilot-retained-v13')]
        self.assertEqual(len(added), 29)
        for key in added:
            previous = key.replace('-source-v8-', '-source-v7-') if key.startswith('campaign-') else {'pester-effectiveness-v17': 'pester-effectiveness-v16', 'pester-cli-pilot-retained-v13': 'pester-cli-pilot-retained-v12'}[key]
            new = registry['profiles'][key]; old = registry['profiles'][previous]
            self.assertEqual({k:v for k,v in new.items() if k not in ('id','runtime_digest')},
                             {k:v for k,v in old.items() if k not in ('id','runtime_digest')})
            purpose = key if key.startswith('campaign-') else 'skill_effectiveness' if key.startswith('pester-effectiveness') else 'cli_pilot'
            self.assertNotEqual(new['runtime_digest'], old['runtime_digest'])
            del registry['profiles'][key]
        digest = hashlib.sha256(json.dumps(registry, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(digest, '20c02e22482cbb6c0b047bc89d718e08a9a7b424b911a4e6a871395b247b027b')

    def test_verifier_observation_profiles_preserve_all_prior_profiles(self):
        registry = json.loads((ROOT / '.github/evals/custom-metrics.json').read_text())
        registry['profiles'].pop('gh-deterministic-gate-v6')
        registry['profiles'].pop('gh-native-oracle-v2')
        registry['active_profiles']['gh'] = 'gh-deterministic-gate-v5'
        registry['profiles'] = {k:v for k,v in registry['profiles'].items() if '-source-v11-' not in k and '-source-v12-' not in k and '-source-v13-' not in k and '-source-v14-' not in k and '-source-v15-' not in k and '-source-v16-' not in k and '-source-v17-' not in k and '-source-v18-' not in k and '-source-v19-' not in k and '-source-v20-' not in k and '-source-v21-' not in k and '-source-v22-' not in k and '-source-v23-' not in k and '-source-v24-' not in k and '-source-v33-' not in k and '-source-v31-' not in k and '-source-v30-' not in k and '-source-v29-' not in k and '-source-v28-' not in k and '-source-v27-' not in k and '-source-v26-' not in k and k not in ('pester-effectiveness-v30', 'pester-cli-pilot-retained-v18', 'pester-effectiveness-v31', 'pester-cli-pilot-retained-v19', 'pester-effectiveness-v32', 'pester-effectiveness-v33', 'pester-effectiveness-v34', 'pester-effectiveness-v36', 'pester-cli-pilot-retained-v20') and '-source-v25-' not in k and k not in ('pester-effectiveness-v20', 'pester-effectiveness-v21', 'pester-effectiveness-v22', 'pester-effectiveness-v23', 'pester-effectiveness-v24', 'pester-effectiveness-v25', 'pester-cli-pilot-retained-v16', 'pester-effectiveness-v26', 'pester-effectiveness-v27', 'pester-effectiveness-v28', 'pester-cli-pilot-retained-v17', 'pester-effectiveness-v29')}
        registry['metrics'].pop('gh.authorization.v2')
        for key in [k for k in registry['profiles'] if '-source-v10-' in k or k in ('pester-effectiveness-v19', 'pester-cli-pilot-retained-v15')]: del registry['profiles'][key]
        added = [k for k in registry['profiles'] if '-source-v9-' in k or k in ('pester-effectiveness-v18', 'pester-cli-pilot-retained-v14')]
        self.assertEqual(len(added), 29)
        for key in added:
            previous = key.replace('-source-v9-', '-source-v8-') if key.startswith('campaign-') else {'pester-effectiveness-v18': 'pester-effectiveness-v17', 'pester-cli-pilot-retained-v14': 'pester-cli-pilot-retained-v13'}[key]
            new = registry['profiles'][key]; old = registry['profiles'][previous]
            self.assertEqual({k:v for k,v in new.items() if k not in ('id','runtime_digest')},
                             {k:v for k,v in old.items() if k not in ('id','runtime_digest')})
            purpose = key if key.startswith('campaign-') else 'skill_effectiveness' if key.startswith('pester-effectiveness') else 'cli_pilot'
            self.assertNotEqual(new['runtime_digest'], old['runtime_digest'])
            del registry['profiles'][key]
        digest = hashlib.sha256(json.dumps(registry, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(digest, '22244f4d7409497afac7605dde7be65cc472e3cc98be06e7849f3e02d8a9aa4c')

    def test_metadata_transport_profiles_preserve_all_prior_profiles(self):
        registry = json.loads((ROOT / '.github/evals/custom-metrics.json').read_text())
        registry['profiles'].pop('gh-deterministic-gate-v6')
        registry['profiles'].pop('gh-native-oracle-v2')
        registry['active_profiles']['gh'] = 'gh-deterministic-gate-v5'
        registry['profiles'] = {k:v for k,v in registry['profiles'].items() if '-source-v11-' not in k and '-source-v12-' not in k and '-source-v13-' not in k and '-source-v14-' not in k and '-source-v15-' not in k and '-source-v16-' not in k and '-source-v17-' not in k and '-source-v18-' not in k and '-source-v19-' not in k and '-source-v20-' not in k and '-source-v21-' not in k and '-source-v22-' not in k and '-source-v23-' not in k and '-source-v24-' not in k and '-source-v33-' not in k and '-source-v31-' not in k and '-source-v30-' not in k and '-source-v29-' not in k and '-source-v28-' not in k and '-source-v27-' not in k and '-source-v26-' not in k and k not in ('pester-effectiveness-v30', 'pester-cli-pilot-retained-v18', 'pester-effectiveness-v31', 'pester-cli-pilot-retained-v19', 'pester-effectiveness-v32', 'pester-effectiveness-v33', 'pester-effectiveness-v34', 'pester-effectiveness-v36', 'pester-cli-pilot-retained-v20') and '-source-v25-' not in k and k not in ('pester-effectiveness-v20', 'pester-effectiveness-v21', 'pester-effectiveness-v22', 'pester-effectiveness-v23', 'pester-effectiveness-v24', 'pester-effectiveness-v25', 'pester-cli-pilot-retained-v16', 'pester-effectiveness-v26', 'pester-effectiveness-v27', 'pester-effectiveness-v28', 'pester-cli-pilot-retained-v17', 'pester-effectiveness-v29')}
        registry['metrics'].pop('gh.authorization.v2')
        added = [k for k in registry['profiles'] if '-source-v10-' in k or k in ('pester-effectiveness-v19', 'pester-cli-pilot-retained-v15')]
        self.assertEqual(len(added), 29)
        for key in added:
            previous = key.replace('-source-v10-', '-source-v9-') if key.startswith('campaign-') else {'pester-effectiveness-v19': 'pester-effectiveness-v18', 'pester-cli-pilot-retained-v15': 'pester-cli-pilot-retained-v14'}[key]
            new = registry['profiles'][key]; old = registry['profiles'][previous]
            self.assertEqual({k:v for k,v in new.items() if k not in ('id','runtime_digest')},
                             {k:v for k,v in old.items() if k not in ('id','runtime_digest')})
            purpose = key if key.startswith('campaign-') else 'skill_effectiveness' if key.startswith('pester-effectiveness') else 'cli_pilot'
            if not key.startswith(('campaign-', 'pester-effectiveness-')):
                # v15 is retained history; the current adapter now owns v16.
                # The complete historical registry digest below still binds v15.
                self.assertNotEqual(evidence.custom_input_identities(ROOT, new['skill_id'], purpose=purpose)['runtime_digest'], new['runtime_digest'])
            self.assertNotEqual(new['runtime_digest'], old['runtime_digest'])
            del registry['profiles'][key]
        digest = hashlib.sha256(json.dumps(registry, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(digest, 'cc7a4f209714b15b2c2eda28c99e13bdceae793e379d8a3fbe297774856dcc45')

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
