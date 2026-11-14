"""Release-specific compatibility and historical identity boundaries; no inference."""
import copy
import hashlib
import importlib.util
import tempfile
from unittest.mock import patch
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))
import evaluator_profiles as profiles
import skill_evidence as evidence


class Release090Contracts(unittest.TestCase):
    def test_candidate_identity_cannot_alias_an_older_producer_or_omit_provenance(self):
        versions = profiles.candidate_versions(profiles.NEXT)
        self.assertIs(profiles.runtime(versions), profiles.NEXT)
        self.assertIs(profiles.runtime(profiles.candidate_versions()), profiles.CANDIDATE)
        self.assertEqual(profiles.runtime({})['version'], '0.3.0')
        for key in versions:
            altered = dict(versions); altered.pop(key)
            with self.subTest(missing=key), self.assertRaises(ValueError):
                profiles.runtime(altered)
        for version in ('0.3.0', '0.8.0'):
            with self.subTest(version=version), self.assertRaises(ValueError):
                profiles.runtime(dict(versions, skillevaluator=version))

    def test_lock_and_patch_match_the_admitted_source_identity(self):
        for member, field in (('.github/locks/evaluator-0.9.lock', 'lock_sha256'),
                              ('.github/patches/skillevaluator-v0.9.0-evidence.patch', 'patch_sha256')):
            self.assertEqual(hashlib.sha256((ROOT / member).read_bytes()).hexdigest(), profiles.NEXT[field])
        self.assertEqual(profiles.NEXT['revision'], 'b78d14618a694dec84bc9601468f8f711df5cab3')
        self.assertEqual((profiles.CANDIDATE['version'], profiles.CANDIDATE['harbor']), ('0.8.0', '0.24.0'))

    def test_source_successors_preserve_every_historical_registry_entry(self):
        registry = evidence.custom_registry(ROOT)
        old = copy.deepcopy(registry)
        added = [key for key in registry['profiles'] if '-source-v11-' in key]
        self.assertEqual(len(added), 27)
        added.append('pester-effectiveness-v20')
        for key in added:
            new = registry['profiles'][key]
            previous = registry['profiles'][key.replace('-source-v11-', '-source-v10-') if key.startswith('campaign-') else 'pester-effectiveness-v19']
            self.assertEqual({k:v for k,v in new.items() if k not in ('id', 'runtime_digest')},
                             {k:v for k,v in previous.items() if k not in ('id', 'runtime_digest')})
            self.assertEqual(evidence.custom_input_identities(ROOT, new['skill_id'], purpose=key if key.startswith('campaign-') else 'skill_effectiveness')['runtime_digest'], new['runtime_digest'])
            del old['profiles'][key]
        digest = hashlib.sha256(json.dumps(old, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(digest, 'aaca89849f7fddc587d20b312e155dfb2710b65a3b6b299b02cc01eaaf7e7316')

    @unittest.skipUnless(importlib.util.find_spec('aeb_gh_fixture'), 'Requires the candidate owning backend')
    def test_native_gh_entry_point_selects_actual_owning_profile(self):
        import gh_initializer_validation as native
        class ReachedCompose(RuntimeError):
            pass
        with tempfile.TemporaryDirectory() as directory, patch.object(native, 'docker', side_effect=ReachedCompose) as compose:
            with self.assertRaises(ReachedCompose):
                native.main(Path(directory) / 'native.json', 'with_skill', 1)
            compose.assert_called_once_with('compose', 'version', '--short')
