"""Real HTTP/verifier evidence and fixture admission; no model/provider calls."""
import copy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))
import qualify_standard_judges as qualification
import skill_evidence as evidence
import skill_reports as reports


class CorpusTests(unittest.TestCase):
    def test_qualification_leaves_select_existing_owners(self):
        import ci_routing
        for name in (*qualification.SOURCES, '.github/evals/judge-calibration-090/corpus.json',
                     '.github/tests/test_standard_judges.py'):
            selected = ci_routing.select([name])
            self.assertEqual({key for key,value in selected.items() if value}, {'contracts', 'evaluator'})

    def test_frozen_sources_and_unrun_labels(self):
        value = qualification.corpus()
        self.assertEqual(len(value['items']), 7)
        self.assertEqual({r['label_basis'] for r in value['items']},
                         {'executable_check', 'reviewed_reference', 'bounded_human_assessment'})
        for field, replacement in (('observed', 'PASS'), ('sources', [{'path': '../missing', 'sha256': '0'*64}])):
            changed = copy.deepcopy(value); changed['items'][0][field] = replacement
            with self.subTest(field=field), patch.object(reports, 'read_json', return_value=changed), self.assertRaises(ValueError):
                qualification.corpus()


@unittest.skipUnless(os.environ.get('JUDGE_090_EVIDENCE'), 'requires actual local HTTP/verifier qualification')
class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output = Path(os.environ['JUDGE_090_EVIDENCE'])
        cls.proof = reports.read_json(cls.output / 'qualification.json')
        cls.requests = reports.read_json(cls.output / 'requests.json')
        cls.record = reports.read_json(next((cls.output / 'admitted/public').rglob('public-report.json')))

    def row(self, case):
        ident = next(o['id'] for o in self.record['observations'] if o['case_id'] == case and o['arm'] == 'with_skill')
        return next(r for r in self.record['benchmark']['observations'] if r['observation_id'] == ident)

    def test_independent_failure_partial_failure_and_missingness_survive(self):
        self.assertEqual(self.row('1')['outcome'], 'passed')
        self.assertEqual(self.row('3')['quality']['required_failure'], 'security')
        self.assertEqual(self.row('4')['outcome'], 'judgment_unavailable')
        self.assertIsNone(self.row('4')['quality']['passed'])
        self.assertEqual(self.row('4')['metrics']['accuracy']['value'], 1)
        self.assertIsNone(self.row('4')['metrics']['goal_accuracy']['value'])
        self.assertEqual(self.row('5')['outcome'], 'unsupported')
        self.assertIsNone(self.row('5')['quality']['security_clean'])
        self.assertTrue(self.row('5')['security_evidence']['findings'])
        self.assertEqual(self.row('6')['outcome'], 'runtime_failure')
        self.assertEqual(self.row('8')['dimensions']['efficiency']['status'], 'not_applicable')
        self.assertIsNone(self.row('10')['quality']['passed'])

    def test_exact_request_counts_and_diagnostics(self):
        expected = {'1':3,'2':3,'3':3,'4':3,'5':0,'6':3,'7':4,'8':3,'9':6,'10':3}
        for control in self.proof['controls']:
            if 'case' in control:
                self.assertEqual(control['requests'], expected[control['case']])
                if control['case'] == '7': self.assertFalse(control['errors'])
        schema = [r['payload'] for r in self.requests if r['scenario']=='schema_fallback']
        self.assertIn('response_format', schema[0]); self.assertNotIn('response_format', schema[1])
        self.assertEqual(self.proof['native_budget_usage'], {'judge_calls':48})
        self.assertEqual(self.proof['http_requests'],70)
        self.assertTrue(any(r.get('supplied_usage') for r in self.requests))
        self.assertTrue(any(r['scenario']=='missing_usage' and not r.get('supplied_usage') for r in self.requests))
        self.assertNotIn('usage', json.dumps([self.row('1')['metrics']]))

    def test_fixture_cannot_enter_live_or_history(self):
        import benchmark_evidence as benchmark
        import skill_history as history
        from test_skill_pages import prov
        self.assertFalse(benchmark.history_admission(self.record)['eligible'])
        for stripped in (False, True):
            value=copy.deepcopy(self.record)
            if stripped: value.pop('benchmark')
            with self.assertRaisesRegex(ValueError, 'production history'):
                history.observation(value, 'standard--podman', prov('a'*40, kind='benchmark'), '2026-11-16T00:00:00Z')
        value=copy.deepcopy(self.record); value['benchmark']['judgments']='live'
        with self.assertRaises(ValueError): evidence.validate_public(value)
        original=reports.read_json
        for field in ('handoff', 'sources'):
            value=copy.deepcopy(self.proof); value[field]={}
            def missing(path): return value if path.name=='qualification.json' else original(path)
            with self.subTest(field=field), patch.object(reports, 'read_json', side_effect=missing), self.assertRaises(ValueError):
                qualification.render(self.output)
        value=copy.deepcopy(self.proof); value['paid_authority']=True
        original=reports.read_json
        def changed(path): return value if path.name=='qualification.json' else original(path)
        with patch.object(reports, 'read_json', side_effect=changed), self.assertRaises(ValueError): qualification.render(self.output)


if __name__ == '__main__':
    unittest.main()
