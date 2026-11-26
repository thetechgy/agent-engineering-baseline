"""Compare the offline 1.0.1 reader to saved synthetic cases from all original validators."""

import importlib.metadata
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import skill_analysis as analysis
import skill_evidence as evidence
import skill_report as report
import skill_report_reviews as attachments
from review_snapshots import parity_archive, restore_parity_case


@unittest.skipUnless(importlib.metadata.version('skillevaluator') == '1.0.1', 'Use the private review candidate')
class HistoricalReviewReplayTests(unittest.TestCase):
    def setUp(self):
        self.archive = self.enterContext(parity_archive())
        self.catalog = evidence.parse_json(self.archive.read('catalog.json'))

    def restore(self, key, root):
        spec, path, _ = restore_parity_case(self, self.archive, root, key=key)
        return spec, path, analysis.capture_inputs([Path(name) for name in spec['inputs']])

    def test_saved_bytes_have_identical_admission_across_all_profiles(self):
        self.assertEqual({row['attachment']['profile'] for row in self.catalog.values()}, set(attachments.PROFILES))
        for key, expected in self.catalog.items():
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                spec, path, captured = self.restore(key, root)
                result = attachments.load([path], captured)
                item, = result.items
                self.assertEqual(item['validator_execution'], 'skillevaluator-1.0.1-private-review-offline-v1')
                self.assertEqual(evidence.identity(item['report']), expected['validated_report'])
                self.assertEqual(item['report']['provenance']['implementation_digest'], expected['validated_implementation'])
                output = report.render_report(analysis.validate_analysis(None, captured), captured, reviews=result)
                self.assertIn(b'not_quality_qualified', output)
                self.assertNotIn(str(root).encode(), output)

    def test_substituted_version_context_result_and_attachment_authority_reject(self):
        for field, substitute in (('versions', {'skillevaluator': '1.0.1'}),
                                  ('context_digest', evidence.identity('substituted')),
                                  ('usage', {'total_tokens': 1})):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                spec, path, captured = self.restore('current-v5', root)
                result = root / spec['review']
                raw = evidence.parse_json(result.read_bytes())
                raw['provenance'][field] = substitute
                result.write_bytes(evidence.encoded(raw))
                spec['review_digest'] = evidence.digest_bytes(result.read_bytes())
                path.write_bytes(evidence.encoded(spec))
                with self.assertRaises(ValueError):
                    attachments.load([path], captured)
        with tempfile.TemporaryDirectory() as directory:
            spec, path, captured = self.restore('current-v5', Path(directory))
            spec['validator_execution'] = 'skillevaluator-1.0.1-private-review-offline-v1'
            path.write_bytes(evidence.encoded(spec))
            with self.assertRaises(ValueError):
                attachments.load([path], captured)

    def test_custom_only_pester_review_replays_from_public_projection(self):
        with parity_archive(pester=True) as archive, tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec, path, expected = restore_parity_case(self, archive, root)
            captured = analysis.capture_inputs([Path(name) for name in spec['inputs']])
            result = attachments.load([path], captured)
            item, = result.items
            self.assertEqual(evidence.identity(item['report']), expected['validated_report'])
            output = report.render_report(analysis.validate_analysis(None, captured), captured, reviews=result)
            self.assertIn(b'Seeded mutation detection', output)
            self.assertIn(b'No recommendations supplied', output)
            spec.update(profile='current-v3', tooling=str(evidence.ROOT))
            path.write_bytes(evidence.encoded(spec))
            with self.assertRaisesRegex(ValueError, 'Unreviewed validator module'):
                attachments.load([path], captured)

    def test_substituted_source_registry_and_snapshot_paths_reject(self):
        replacements = {'source': 'source/SKILL.md', 'registry': 'tooling/.github/evals/custom-metrics.json',
                        'validator': 'tooling/.github/scripts/skill_review.py'}
        for key, member in replacements.items():
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                _, path, captured = self.restore('current-v5', root)
                replaced = root / member
                replaced.write_bytes(replaced.read_bytes() + b' ')
                with self.assertRaises(ValueError):
                    attachments.load([path], captured)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec, path, captured = self.restore('current-v5', root)
            (root / 'moved-source').symlink_to(root / spec['source'], target_is_directory=True)
            spec['source'] = 'moved-source'
            path.write_bytes(evidence.encoded(spec))
            with self.assertRaises(ValueError):
                attachments.load([path], captured)
