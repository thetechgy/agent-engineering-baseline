"""Verify the registered archive and the active grading cutover."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import evaluation_archive as archive
import evaluation_identity as bindings
import skill_evidence as evidence


class RegistryArchiveTests(unittest.TestCase):
    def test_archive_members_and_resolved_legacy_registry_match_the_previous_checkout(self):
        index = archive.archive_index(evidence.ROOT)
        for member, digest in index['members'].items():
            with self.subTest(member=member):
                self.assertEqual(evidence.digest_bytes(archive.read_member(evidence.ROOT, member)), digest)
        self.assertEqual(evidence.identity(evidence.custom_registry()),
                         'sha256:c897b61af032fba9fb33c8fa65c6d46bb1a0d6dbf0afe24c617e1218f06628ec')

    def test_active_grading_resolves_without_legacy_files_and_keeps_each_contract(self):
        active = evidence.active_registry()
        legacy = evidence.custom_registry()
        projected = {}
        for key, value in legacy['profiles'].items():
            if key.startswith('campaign-') and '-lifecycle-v1-source-v53-' in key:
                stable = key.replace('-lifecycle-v1-source-v53-', '-lifecycle-v2-')
            elif key == 'pester-effectiveness-v56':
                stable = bindings.EFFECTIVENESS
            else:
                continue
            projected[stable] = {**{name: item for name, item in value.items() if name != 'runtime_digest'},
                                 'id': stable}
        self.assertEqual({key: value for key, value in active['profiles'].items() if bindings.reusable(key)}, projected)
        self.assertEqual(active['metrics'], legacy['metrics'])
        self.assertEqual(active['active_profiles'], legacy['active_profiles'])
        with patch.object(evidence, 'custom_registry', side_effect=AssertionError('Legacy archive loaded')):
            for key, expected in active['profiles'].items():
                with self.subTest(profile=key):
                    selected, _, _ = evidence.custom_contract(expected['skill_id'], profile_id=key)
                    self.assertEqual(selected['id'], key)

    def test_missing_archive_refuses_a_working_tree_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder)
            index = workspace / archive.INDEX
            index.parent.mkdir(parents=True)
            index.write_bytes((evidence.ROOT / archive.INDEX).read_bytes())
            (workspace / evidence.CUSTOM_REGISTRY).write_bytes(b'{}')
            with self.assertRaisesRegex(ValueError, 'archive unavailable'):
                archive.read_member(workspace, evidence.CUSTOM_REGISTRY)

    def test_archive_refuses_a_blob_with_the_wrong_digest(self):
        index = archive.archive_index(evidence.ROOT)
        member = evidence.CUSTOM_REGISTRY
        with patch.object(evidence, 'historical_blob', return_value=b'changed'):
            with self.assertRaisesRegex(ValueError, 'archive digest mismatch'):
                archive.verified_members(evidence.ROOT, index['revision'], ((member, 'sha256:' + '0' * 64),))
