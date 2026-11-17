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
                              ('.github/patches/skillevaluator-v0.9.0-evidence-v3.patch', 'patch_sha256')):
            self.assertEqual(hashlib.sha256((ROOT / member).read_bytes()).hexdigest(), profiles.NEXT[field])
        self.assertEqual(profiles.NEXT['revision'], 'b78d14618a694dec84bc9601468f8f711df5cab3')
        self.assertEqual((profiles.CANDIDATE['version'], profiles.CANDIDATE['harbor']), ('0.8.0', '0.24.0'))

    def test_source_successors_preserve_every_historical_registry_entry(self):
        registry = evidence.custom_registry(ROOT)
        # These successors preserve this stopped source-v17 population unchanged.
        registry['profiles'] = {k:v for k,v in registry['profiles'].items()
            if '-source-v18-' not in k and '-source-v19-' not in k and '-source-v20-' not in k and '-source-v21-' not in k and '-source-v22-' not in k and '-source-v23-' not in k and '-source-v24-' not in k and k not in ('pester-effectiveness-v27', 'pester-effectiveness-v28', 'pester-effectiveness-v29')}
        registry['metrics'].pop('gh.authorization.v2')
        old = copy.deepcopy(registry)
        added = [key for key in registry['profiles'] if '-source-v17-' in key]
        self.assertEqual(len(added), 31)
        added.extend(('pester-effectiveness-v26', 'pester-cli-pilot-retained-v17'))
        for key in added:
            new = registry['profiles'][key]
            predecessor = (key.replace('-source-v17-', '-source-v16-') if key.startswith('campaign-') else
                           'pester-effectiveness-v25' if key == 'pester-effectiveness-v26' else 'pester-cli-pilot-retained-v16')
            previous = registry['profiles'][predecessor]
            normalized = copy.deepcopy(new)
            if 'adapter_sha256' in new.get('campaign', {}):
                self.assertEqual(new['campaign']['adapter_sha256'], 'sha256:97d47ea3250eceaa876f1086f8c1ad1830908b6372cfe4cea4ce52c57997cbb8')
                normalized['campaign']['adapter_sha256'] = previous['campaign']['adapter_sha256']
            if new.get('campaign', {}).get('mode') in ('live', 'experiment-probe'):
                self.assertEqual(normalized['campaign'].pop('scheduler'), 'campaign-scheduler-v1')
            self.assertEqual({k:v for k,v in normalized.items() if k not in ('id', 'runtime_digest')},
                             {k:v for k,v in previous.items() if k not in ('id', 'runtime_digest')})
            purpose = key if key.startswith('campaign-') else 'skill_effectiveness' if key.startswith('pester-effectiveness') else 'cli_pilot'
            current = evidence.custom_input_identities(ROOT, new['skill_id'], purpose=purpose)['runtime_digest']
            if key.startswith('campaign-') or key == 'pester-effectiveness-v26':
                self.assertNotEqual(current, new['runtime_digest'])  # Superseded source; historical bytes stay bound below.
            else:
                self.assertEqual(current, new['runtime_digest'])
            del old['profiles'][key]
        digest = hashlib.sha256(json.dumps(old, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(digest, '9f6da16a495515bded95fe199d2996c5a09ea5712a19786f47b71c50b7c703ed')  # Complete stopped-report revision, 562 profiles.

    @unittest.skipUnless(importlib.util.find_spec('aeb_gh_fixture'), 'Requires the candidate owning backend')
    def test_native_gh_entry_point_selects_actual_owning_profile(self):
        import gh_initializer_validation as native
        class ReachedCompose(RuntimeError):
            pass
        with tempfile.TemporaryDirectory() as directory, patch.object(native, 'docker', side_effect=ReachedCompose) as compose:
            with self.assertRaises(ReachedCompose):
                native.main(Path(directory) / 'native.json', 'with_skill', 1)
            compose.assert_called_once_with('compose', 'version', '--short')

    @unittest.skipUnless(importlib.util.find_spec('aeb_gh_fixture'), 'Requires the candidate owning backend')
    def test_native_gh_oracle_entry_point_selects_actual_owning_profile(self):
        import os
        import gh_oracle_validation as native
        class ReachedPrepare(RuntimeError):
            pass
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}), \
                patch.object(native.signal, 'signal'), \
                patch.object(native, 'prepare', side_effect=ReachedPrepare) as prepare:
            for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'NVIDIA_API_KEY'):
                os.environ.pop(key, None)
            with self.assertRaises(ReachedPrepare):
                native.main(Path(directory) / 'native')
            prepare.assert_called_once()

    def test_retained_backend_wheel_bytes_and_new_wheel_reproducibility(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('wheel_builder', ROOT / '.github/evaluator-backends/build_wheel.py')
        builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            retained = builder.build(root / 'retained').read_bytes()
            candidate = builder.build(root / 'candidate', candidate_next=True).read_bytes()
            repeat = builder.build(root / 'repeat', candidate_next=True).read_bytes()
            self.assertEqual(hashlib.sha256(retained).hexdigest(), '3d577d926bc0b64703d376cf1d39e4cddeca7336b51051585d205543f9a3f89b')
            self.assertEqual(hashlib.sha256(candidate).hexdigest(), profiles.NEXT['backend_wheel_sha256'])
            self.assertEqual(candidate, repeat)

    def test_same_package_version_does_not_alias_retained_producer(self):
        old = profiles.RETAINED_NEXT
        self.assertEqual(old['id'], 'skillevaluator-0.9.0-offline-v2')
        self.assertIs(profiles.runtime(profiles.candidate_versions(old)), old)
        self.assertEqual(hashlib.sha256((ROOT / '.github/patches/skillevaluator-v0.9.0-evidence.patch').read_bytes()).hexdigest(), old['patch_sha256'])
        self.assertNotEqual(profiles.NEXT['patch_sha256'], old['patch_sha256'])
        self.assertNotEqual(profiles.NEXT['source_tree_digest'], old['source_tree_digest'])
        self.assertEqual(old['dependencies'], profiles.NEXT['dependencies'])
        forged = profiles.candidate_versions(old); forged['patch_sha256'] = '0' * 64
        with self.assertRaises(ValueError): profiles.runtime(forged)
        old_policy = evidence.make_policy({'evaluator_revision': old['revision'], 'python': old['python'], 'harbor': old['harbor']},
            'sha256:' + old['patch_sha256'], judge={'model': None, 'provider': None, 'enabled': False}, provenance='runtime_recorded')
        self.assertEqual(old_policy['producer_profile'], old['id'])
        evidence.validate_policy(old_policy)
