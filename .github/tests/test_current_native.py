"""Candidate-only native staging and provenance controls; no Docker or model."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))


@unittest.skipUnless(os.environ.get('CURRENT_NATIVE_CONTROLS') == '1', 'frozen 0.8.0 runtime only')
class NativeCurrentTests(unittest.TestCase):
    def test_complete_oracle_staging_preserves_production_profile_and_rejects_entry_drift(self):
        import gh_oracle_validation as native
        import skill_evidence as e
        from harbor.models.task.task import Task
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            os.environ['SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE'] = str(root / 'key')
            bundle, fixtures, rows, arms, manifest = native.prepare(root)
            self.assertEqual(len(rows), 48)
            self.assertEqual(e.custom_registry()['active_profiles']['gh'], 'gh-deterministic-gate-v5')
            self.assertEqual({(r['arm'], r['case_id']) for r in rows},
                {(arm, case) for arm in ('with_skill', 'without_skill') for case in fixtures})
            self.assertEqual({r['task_checksum'] for r in rows},
                {Task(task).checksum for tasks in arms.values() for task in tasks})
            capture = e.custom_capture(ROOT, 'gh', bundle, rows, purpose='oracle_qualification',
                attempts=1, agent='oracle', execution_policy={'environment':'aeb-gh-fixture',
                'concurrency':2, 'timeout_multiplier':1.0, 'stop_on_pass':False})
            profile, _ = e.validate_custom_capture(capture, 'gh', ROOT)
            self.assertEqual(profile['id'], 'gh-native-oracle-v1')
            self.assertEqual(profile['grading'], 'custom_only')
            capture['execution_policy']['environment'] = 'docker'
            with self.assertRaisesRegex(ValueError, 'Execution policy drift'):
                e.validate_custom_capture(capture, 'gh', ROOT)
            task = arms['with_skill'][0]
            (task / 'tests/test.sh').write_text('echo forged')
            with self.assertRaisesRegex(ValueError, 'verifier entry'):
                e.capture_custom_tasks(ROOT, 'gh', [task], 'with_skill', purpose='oracle_qualification')
