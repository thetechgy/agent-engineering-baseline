"""Static scanner provenance is immutable evidence, including omission attacks."""

import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / '.github/scripts'))
import skill_evidence as evidence


class ScannerRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.native = self.root / 'native'
        shutil.copytree(REPO / '.github/tests/fixtures/skill_evidence/static-synthetic', self.native)
        self.versions = evidence.read_json(self.native / 'versions.json')
        self.versions.update(scanner_runtime=copy.deepcopy(evidence.SCANNER_RUNTIME),
                             scanners=copy.deepcopy(evidence.SCANNER_RUNTIME['versions']),
                             skillspector_revision=evidence.SCANNER_RUNTIME['skillspector_revision'])

    def write_versions(self, value):
        (self.native / 'versions.json').write_text(json.dumps(value))

    def test_source_lock_and_executed_versions_reject_unknown_and_contradictory_identity(self):
        for field in ('skillspector_revision', 'skillspector_lock', 'semgrep_lock', 'adapter_patch'):
            changed = copy.deepcopy(self.versions)
            changed['scanner_runtime'][field] = 'unknown'
            self.write_versions(changed)
            with self.assertRaises(ValueError):
                evidence.normalize_static(self.native, 'podman')
        for version in ('99.0.0', '2.13.3'):
            changed = copy.deepcopy(self.versions)
            changed['scanners']['skillspector'] = version
            self.write_versions(changed)
            with self.assertRaises(ValueError):
                evidence.normalize_static(self.native, 'podman')
        changed = copy.deepcopy(self.versions)
        del changed['scanner_runtime']
        self.write_versions(changed)
        with self.assertRaisesRegex(ValueError, 'Missing scanner runtime'):
            evidence.normalize_static(self.native, 'podman')

    def test_versions_survive_projection_and_cannot_be_removed_from_captured_claims(self):
        self.write_versions(self.versions)
        normalized = evidence.normalize_static(self.native, 'podman')
        public = evidence.project(normalized)
        self.assertEqual(public['scanner_runtime'], self.versions['scanner_runtime'])
        evidence.validate_public(public)
        changed = copy.deepcopy(dict(normalized))
        del changed['scanner_runtime']
        with self.assertRaisesRegex(ValueError, 'Static claims differ'):
            evidence.project(changed, static_bundle=self.native)

    def test_altered_original_versions_invalidate_captured_publication(self):
        self.write_versions(self.versions)
        normalized = evidence.normalize_static(self.native, 'podman')
        changed = copy.deepcopy(self.versions)
        changed['scanners']['semgrep'] = '99.0.0'
        self.write_versions(changed)
        with self.assertRaises(ValueError):
            evidence.write_outputs({'public-report.json': evidence.project(normalized)}, self.root / 'rejected')

    def test_unpatched_scanner_profile_keeps_its_original_identity(self):
        self.versions['scanner_runtime'] = copy.deepcopy(evidence.SCANNER_RUNTIME_UNPATCHED)
        self.versions['scanners'] = copy.deepcopy(evidence.SCANNER_RUNTIME_UNPATCHED['versions'])
        self.write_versions(self.versions)
        public = evidence.project(evidence.normalize_static(self.native, 'podman'))
        self.assertEqual(public['scanner_runtime'], evidence.SCANNER_RUNTIME_UNPATCHED)
        self.assertNotIn('adapter_patch', public['scanner_runtime'])
        self.assertNotIn('coverage_caveats', public)

    def test_previous_scanner_lock_remains_admitted_without_relabeling(self):
        self.versions['scanner_runtime'] = copy.deepcopy(evidence.SCANNER_RUNTIME_PREVIOUS)
        self.versions['scanners'] = copy.deepcopy(evidence.SCANNER_RUNTIME_PREVIOUS['versions'])
        self.write_versions(self.versions)
        public = evidence.project(evidence.normalize_static(self.native, 'podman'))
        self.assertEqual(public['scanner_runtime'], evidence.SCANNER_RUNTIME_PREVIOUS)
        self.assertNotEqual(public['scanner_runtime'], evidence.SCANNER_RUNTIME)

    def test_historical_records_keep_their_identity_without_invented_scanner_versions(self):
        original = evidence.normalize_static(self.native, 'podman')
        public = evidence.project(original)
        self.assertNotIn('scanner_runtime', original)
        self.assertNotIn('scanner_runtime', public)
        self.assertEqual(evidence.identity(public), evidence.identity(evidence.project(original)))


if __name__ == '__main__':
    unittest.main()
