"""Immutable original evidence and credential-free replay through actual staging."""
import copy
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

CANDIDATE_RUNTIME = bool(importlib.util.find_spec('skillevaluator')) and importlib.metadata.version('skillevaluator') == '0.8.0'
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))
import codex_pilot as pilot
import codex_pilot_replay as replay
import skill_evidence as evidence
import skill_report as report


class RetrospectiveEvidence(unittest.TestCase):
    def test_originals_keep_exact_hashes_and_unmeasured_outcomes(self):
        root, _, submissions, original = replay.corpus()
        self.assertEqual(len(original['observations']), 2)
        for arm, raw in submissions.items():
            self.assertEqual(hashlib.sha256(raw).hexdigest(), replay.SUBMISSIONS[arm])
            reward = evidence.read_json(root / arm / 'original-reward.json')
            self.assertEqual(reward['details']['outcome']['classification'], 'unsupported')
            self.assertEqual(reward['details']['outcome']['code'], 'ast_kind')
        self.assertEqual(evidence.identity(original), replay.ORIGINAL_RECORD)
        for observation in original['observations']:
            self.assertIsNone(observation['score'])
            self.assertTrue(all(m['value'] is None for m in observation['custom']['measurements']))

    def test_missing_changed_and_extra_original_evidence_is_rejected(self):
        root, _, _, _ = replay.corpus()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'original'
            shutil.copytree(root, target)
            replay.verify_original_copy(target)
            subject = target / 'with_skill/Subject.Tests.ps1'
            raw = subject.read_bytes()
            subject.write_bytes(raw + b'\n')
            with self.assertRaises(ValueError): replay.verify_original_copy(target)
            subject.write_bytes(raw); subject.unlink()
            with self.assertRaises(ValueError): replay.verify_original_copy(target)
            subject.write_bytes(raw); (target / 'extra.json').write_text('{}')
            with self.assertRaises(ValueError): replay.verify_original_copy(target)

    def test_retrospective_metadata_cannot_waive_source_or_hashes(self):
        meta = replay.retrospective_metadata()
        replay.validate_retrospective(meta)
        for key in meta:
            changed = copy.deepcopy(meta); changed[key] = None
            with self.subTest(key=key), self.assertRaises(ValueError): replay.validate_retrospective(changed)
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / 'wrong.zip'; archive.write_bytes(b'not the authenticated archive')
            with self.assertRaisesRegex(ValueError, 'digest mismatch'): replay.verify_archive(archive)

    def test_existing_report_juxtaposes_originals_and_posthoc_results(self):
        _, _, _, original = replay.corpus()
        # Presentation fixture only: native execution and normalization are hosted controls.
        after = copy.deepcopy(original)
        after['custom']['retrospective'] = replay.retrospective_metadata()
        for observation in after['observations']:
            observation['custom']['outcome'] = 'failed'
            for measurement in observation['custom']['measurements']:
                measurement.update(status='measured', value=0, numerator=0)
        html = report.retrospective_outcomes(after, {replay.ORIGINAL_RECORD: original})
        for phrase in ('after inspection', 'not prospectively frozen', 'Unmeasured', 'unsupported', 'ast_kind', 'failed'):
            self.assertIn(phrase, html)
        for digest in replay.SUBMISSIONS.values(): self.assertIn(digest, html)
        with self.assertRaises(KeyError): report.retrospective_outcomes(after, {})

    @unittest.skipUnless(os.environ.get('APM_EXECUTABLE') and CANDIDATE_RUNTIME, 'Verified APM and owning candidate runtime required')
    def test_exact_replay_stage_capture_and_no_model_command(self):
        _, _, submissions, _ = replay.corpus()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            bundle, tasks, rows = pilot.stage(target, replay=replay.retrospective_metadata(), submissions=submissions)
            for arm, values in tasks.items():
                self.assertEqual(len(values), 1)
                task = values[0]
                self.assertEqual((task / 'solution/candidate').read_bytes(), submissions[arm])
                self.assertFalse((task / 'environment/build/codex_pilot_probe.py').exists())
                self.assertIn(b'ForStatementAst', (task / 'tests/Runner.ps1').read_bytes())
            capture = evidence.custom_capture(ROOT, 'powershell-pester-6', bundle, rows,
                purpose='cli_pilot_replay', attempts=1, agent='oracle', retrospective=replay.retrospective_metadata(),
                execution_policy={'environment':'docker','concurrency':2,'timeout_multiplier':1.0,'stop_on_pass':False})
            evidence.validate_custom_capture(capture, 'powershell-pester-6', ROOT)
            command = pilot.command(target, 'with_skill', replay=True)
            self.assertEqual(command[command.index('--agent') + 1], 'oracle')
            self.assertNotIn('--model', command)
            self.assertEqual(command[command.index('--max-retries') + 1], '0')
            capture['retrospective']['submission_digests']['with_skill'] = 'sha256:' + '0'*64
            with self.assertRaises(ValueError): evidence.validate_custom_capture(capture, 'powershell-pester-6', ROOT)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'exact submission identity'):
                pilot.stage(Path(directory), replay=replay.retrospective_metadata(),
                            submissions={**submissions, 'with_skill': submissions['with_skill'] + b'\n'})


if __name__ == '__main__':
    unittest.main()
