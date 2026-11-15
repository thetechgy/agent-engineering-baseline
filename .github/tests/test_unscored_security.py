"""Closed diagnostic population controls; no model, agent, or judge execution."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))
import unscored_security as schema


class SecurityProjectionTests(unittest.TestCase):
    def finding(self):
        return {'type': 'secret_exposure', 'severity': 'critical', 'message': 'Known fixture finding',
                'evidence': '[redacted secret exposure]', 'source': 'tool_observation', 'score_impact': True}

    def test_bounded_missing_malformed_oversized_duplicate_and_contradictory_populations(self):
        finding = self.finding()
        for security, reason in ((None, 'missing'), ({'findings': {}}, 'malformed'),
                ({'findings': [finding] * 65}, 'oversized'),
                ({'findings': [{**finding, 'message': 'x' * 2049}]}, 'oversized'),
                ({'passed': True, 'findings': [finding]}, 'contradictory'),
                ({'findings': [{**finding, 'attribution': 'skill_caused'}]}, 'malformed')):
            with self.subTest(reason=reason):
                result = schema.project_security({'security': security}, str)
                self.assertEqual(result, {'findings': [], 'evidence_status': 'unavailable', 'evidence_errors': [reason]})
        retained = schema.project_security({'security': {'findings': [finding, finding]}}, str)
        self.assertEqual(len(retained['findings']), 1)
        self.assertNotIn('tool', retained['findings'][0])
        partial = schema.merge_security([retained, schema.project_security({}, str)])
        self.assertEqual(partial['evidence_status'], 'partial')
        self.assertEqual(partial['findings'], retained['findings'])
        for mutate in ('duplicate', 'id', 'score', 'status'):
            bad = copy.deepcopy(retained)
            if mutate == 'duplicate': bad['findings'] *= 2
            elif mutate == 'id': bad['findings'][0]['id'] = 'sha256:' + '0' * 64
            elif mutate == 'score': bad['score'] = 1
            else: bad['evidence_status'] = 'unavailable'
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): schema.validate_security(bad)

    @unittest.skipUnless(os.environ.get('EVALUATOR_ADOPTION_CONTROLS') == '1', 'owning 0.9 collector only')
    def test_actual_collector_handles_secondary_sidecar_failure_without_losing_known_finding(self):
        import skillevaluator.tier3.unscored_security as installed
        from skillevaluator.tier3.harbor.collector import _failed_judge_diagnostic
        self.assertEqual(Path(installed.__file__).read_bytes(), (ROOT / '.github/scripts/unscored_security.py').read_bytes())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            primary = root / 'verifier/skill_evaluator_reward.json'; primary.parent.mkdir()
            primary.write_text(json.dumps({'entry_id': 'fixture', 'evaluation_status': 'failed',
                'evaluation_errors': {'evidence': 'Required execution evidence is unsupported'},
                'details': {'security': {'passed': None, 'supported': False, 'findings': [self.finding()]}}}))
            secondary = root / 'steps/secondary/verifier/skill_evaluator_reward.json'; secondary.parent.mkdir(parents=True)
            secondary.write_text('{"evaluation_status":"failed","details":{"security":{"findings":[],"findings":[]}}}')
            result = _failed_judge_diagnostic(root)
            self.assertEqual(result['details']['security']['evidence_status'], 'partial')
            self.assertEqual(len(result['details']['security']['findings']), 1)
            self.assertIn('collector', result['evaluation_errors'])
            self.assertIn('evidence', result['evaluation_errors'])
            self.assertNotIn('overall', result)
            primary.unlink()
            result = _failed_judge_diagnostic(root)
            self.assertEqual(result['details']['security']['evidence_status'], 'unavailable')
            self.assertFalse(result['details']['security']['findings'])
