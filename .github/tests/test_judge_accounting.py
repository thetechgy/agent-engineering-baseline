"""Physical accounting, missingness and independent outcome preservation."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / '.github/scripts'), str(ROOT / '.github/tests')]
import judge_accounting as accounting
import skill_reports as reports


class AccountingTests(unittest.TestCase):
    def owning_budget(self):
        try:
            from skillevaluator.tier3.harbor.run_budget import BudgetController
        except ModuleNotFoundError as error:
            if error.name not in ('skillevaluator', 'skillevaluator.tier3.harbor.run_budget'):
                raise
            self.skipTest('Requires the opt-in accounting owner')
        if not hasattr(BudgetController, 'used_judge_transport_attempts'):
            self.skipTest('Requires the opt-in accounting owner')
        return BudgetController

    def envelope(self, directory):
        path = Path(directory) / 'judge_accounting.json'
        accounting.start(path)
        j = accounting.begin_judgment('accuracy', 'openai')
        accounting.logical_attempt(1)
        a = accounting.model_attempt(1)
        row = accounting.initiated('openai', 'fixture-model')
        return path, row, a, j

    def test_interruption_is_retained_and_stops_admission(self):
        with tempfile.TemporaryDirectory() as directory:
            path, row, a, j = self.envelope(directory)
            interrupted = reports.read_json(path)
            summary = accounting.summarize([interrupted, None])
            self.assertEqual(summary['http_attempts'], 1)
            self.assertEqual(summary['completion_unknown'], 1)
            self.assertIsNone(summary['known_tokens']['input'])
            self.assertEqual(summary['expected_trials'], 2)
            with self.assertRaisesRegex(ValueError, 'unknown judge accounting'):
                accounting.require_complete(summary, max_http_attempts=10)
            accounting.end_attempt(a); accounting.end_judgment(j)
            accounting.finish()

    def test_persistence_does_not_swallow_the_native_deadline_alarm(self):
        with tempfile.TemporaryDirectory() as directory:
            accounting.start(Path(directory)/'judge_accounting.json')
            with patch.object(Path,'replace',side_effect=TimeoutError('native judge deadline')):
                with self.assertRaises(TimeoutError): accounting.persist()

    def test_complete_usage_subsets_duplicate_and_budget_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            path, row, a, j = self.envelope(directory)
            u = accounting.usage({'input':19, 'output':7, 'total':26,
                                  'cached_input':5, 'reasoning_output':3})
            accounting.received(row, 200, u)
            accounting.end_attempt(a); accounting.end_judgment(j); accounting.finish()
            envelope = reports.read_json(path)
            summary = accounting.summarize([envelope])
            self.assertTrue(summary['complete'])
            self.assertEqual(summary['known_tokens']['total'], 26)
            self.assertEqual(summary['known_tokens']['cached_input'], 5)
            self.assertEqual(summary['known_tokens']['reasoning_output'], 3)
            self.assertIsNone(summary['cost_estimate_usd'])
            accounting.require_complete(summary, max_http_attempts=2)
            with self.assertRaisesRegex(ValueError, 'exhausted'):
                accounting.require_complete(summary, max_http_attempts=1)
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                accounting.summarize([envelope, envelope])
            changed = copy.deepcopy(envelope); changed['transports'].append(copy.deepcopy(row))
            with self.assertRaises(ValueError): accounting.validate(changed)

    def test_known_response_usage_survives_later_transport_cleanup_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path,row,a,j=self.envelope(directory)
            accounting.received(row,200,accounting.usage({'input':19,'output':7}))
            accounting.failed(row)
            accounting.end_attempt(a); accounting.end_judgment(j); accounting.finish()
            summary=accounting.summarize([reports.read_json(path)])
            self.assertTrue(summary['complete'])
            self.assertEqual(summary['responses_received'],1)
            self.assertEqual(summary['known_tokens']['input'],19)

    def test_partial_malformed_inconsistent_and_zero_are_distinct(self):
        for tokens, status in (({}, 'missing'), ({'input':True, 'output':7}, 'malformed'),
                ({'input':19,'output':7,'total':99}, 'inconsistent'),
                ({'input':19,'output':7,'reasoning_output':8}, 'inconsistent'),
                ({'input':0,'output':0,'total':0}, 'complete')):
            with self.subTest(tokens=tokens): self.assertEqual(accounting.usage(tokens)['status'], status)
        self.assertEqual(accounting.usage({'input':'bad','output':7})['counters']['output'], 7)

    def test_openai_provider_detail_keys_include_reported_prediction_zeros(self):
        self.owning_budget()
        from openai.types.completion_usage import CompletionUsage
        from skillevaluator.tier3.harbor.templates.eval import _openai_accounting_usage
        raw = CompletionUsage(prompt_tokens=19, completion_tokens=7, total_tokens=26,
            prompt_tokens_details={'cached_tokens':5, 'audio_tokens':0, 'cache_write_tokens':2},
            completion_tokens_details={'reasoning_tokens':3, 'audio_tokens':0,
                'accepted_prediction_tokens':2, 'rejected_prediction_tokens':0})
        observed = _openai_accounting_usage(json.dumps({'usage':raw.model_dump()}))
        self.assertEqual(observed, accounting.usage({'input':19, 'output':7, 'total':26,
            'cached_input':5, 'audio_input':0, 'cache_write_input':2,
            'reasoning_output':3, 'audio_output':0, 'accepted_prediction':2, 'rejected_prediction':0}))

    def test_patch_stages_exact_shared_code_and_preserves_historical_profile(self):
        import evaluator_profiles as profiles
        import hashlib
        p = ROOT / '.github/patches/skillevaluator-v0.9.0-accounting-v1.patch'
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), profiles.ACCOUNTING['patch_sha256'])
        self.assertEqual(profiles.NEXT['id'], 'skillevaluator-0.9.0-offline-v3')
        self.assertNotEqual(profiles.NEXT['source_tree_digest'], profiles.ACCOUNTING['source_tree_digest'])
        self.assertEqual(profiles.NEXT['dependencies'], profiles.ACCOUNTING['dependencies'])
        marker = '+++ b/src/skillevaluator/tier3/eval_core/judge_accounting.py\n'
        section = p.read_text().split(marker)[1].split('\ndiff --git ', 1)[0]
        staged = '\n'.join(line[1:] for line in section.splitlines() if line.startswith('+')) + '\n'
        self.assertEqual(staged, (ROOT / '.github/scripts/judge_accounting.py').read_text())


    def test_source_successors_preserve_all_803_historical_profiles(self):
        import hashlib
        import skill_evidence as evidence
        registry=reports.read_json(ROOT/evidence.CUSTOM_REGISTRY)
        registry['profiles'].pop('gh-deterministic-gate-v6')
        registry['profiles'].pop('gh-native-oracle-v2')
        registry['active_profiles']['gh'] = 'gh-deterministic-gate-v5'
        registry['profiles'] = {k:v for k,v in registry['profiles'].items() if '-source-v33-' not in k and '-source-v31-' not in k and '-source-v30-' not in k and '-source-v29-' not in k and '-source-v28-' not in k and '-source-v27-' not in k and '-source-v26-' not in k and k not in ('pester-effectiveness-v30', 'pester-cli-pilot-retained-v18', 'pester-effectiveness-v31', 'pester-cli-pilot-retained-v19', 'pester-effectiveness-v32', 'pester-effectiveness-v33', 'pester-effectiveness-v34', 'pester-effectiveness-v36', 'pester-cli-pilot-retained-v20') and '-source-v25-' not in k}
        added=[k for k in registry['profiles'] if '-source-v24-' in k or k=='pester-effectiveness-v29']
        self.assertEqual(len(added),36)
        for key in added:
            previous=key.replace('-source-v24-','-source-v23-') if key.startswith('campaign-') else 'pester-effectiveness-v28'
            current=registry['profiles'][key]; old=registry['profiles'][previous]
            self.assertEqual({k:v for k,v in current.items() if k not in ('id','runtime_digest')},
                             {k:v for k,v in old.items() if k not in ('id','runtime_digest')})
            purpose=key if key.startswith('campaign-') else 'skill_effectiveness'
            # Source-v24 is historical after the judge adapter. Its exact bytes
            # remain protected by the registry snapshot; source-v25 owns current
            # campaign implementation at adoption. The noncampaign source also has a later successor.
            if not key.startswith('campaign-'):
                self.assertNotEqual(current['runtime_digest'], evidence.custom_input_identities(ROOT, current['skill_id'], purpose=purpose)['runtime_digest'])
            del registry['profiles'][key]
        self.assertEqual(len(registry['profiles']),803)
        self.assertEqual(hashlib.sha256(json.dumps(registry,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                         '05febe880dc5d4f90caee1fc87a0440a1f73de23f88d7252c6b90d84a8387b2a')

    def test_native_budget_counts_physical_requests_and_stops_on_unknown_or_replay(self):
        BudgetController = self.owning_budget()
        with tempfile.TemporaryDirectory() as directory:
            path, row, a, j = self.envelope(directory)
            accounting.received(row, 200, accounting.usage({'input':19,'output':7}))
            accounting.end_attempt(a); accounting.end_judgment(j); accounting.finish()
            summary=accounting.summarize([reports.read_json(path)])
            budget=BudgetController(max_judge_calls=1)
            budget.record_usage({'judge_calls':1,'judge_accounting':summary})
            self.assertEqual(budget.used_judge_transport_attempts,1)
            self.assertEqual(budget.used_judge_calls,1)
            self.assertFalse(budget.admit_many([{'agent':'fixture','arm':'with','case_id':'1','attempt':2}]))
            budget.record_usage({'judge_calls':1,'judge_accounting':summary})
            self.assertEqual(budget.used_judge_transport_attempts,1)
            self.assertEqual(budget.used_judge_calls,1)
            self.assertTrue(budget.judge_accounting_unknown)
            budget=BudgetController()
            budget.record_usage({'judge_calls':1,'judge_accounting':accounting.summarize([None])})
            self.assertFalse(budget.admit_many([{'agent':'fixture','arm':'with','case_id':'1','attempt':2}]))

    def test_orphan_transport_and_missing_trials_remain_in_native_usage(self):
        BudgetController = self.owning_budget()
        from skillevaluator.tier3.harbor.runner import _budget_usage
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            path, row, a, j=self.envelope(root/'trial/verifier')
            reports.write_json(root/'result.json', {'n_total_trials':2})
            self.assertFalse(_budget_usage(root/'missing-job')['judge_accounting']['complete'])
            summary=_budget_usage(root)['judge_accounting']
            self.assertEqual(summary['expected_trials'],2)
            self.assertEqual(summary['http_attempts'],1)
            self.assertEqual(summary['completion_unknown'],1)
            self.assertFalse(summary['complete'])
            budget=BudgetController()
            budget.record_usage({'judge_calls':0,'judge_accounting':summary})
            self.assertEqual(budget.used_judge_transport_attempts,1)
            self.assertTrue(budget.judge_accounting_unknown)
            accounting.end_attempt(a); accounting.end_judgment(j)


@unittest.skipUnless(os.environ.get('JUDGE_090_EVIDENCE'), 'requires owning local responder entry point')
class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output=Path(os.environ['JUDGE_090_EVIDENCE'])
        cls.proof=reports.read_json(cls.output/'qualification.json')
        cls.record=reports.read_json(next((cls.output/'admitted/public').rglob('public-report.json')))

    def test_responder_reference_matches_each_native_control(self):
        for row in self.proof['controls']:
            a=row['accounting']
            self.assertEqual(a['http_attempts'], row['requests'])
            if row['scenario']=='valid' and row['requests']:
                self.assertTrue(a['complete'])
                self.assertEqual(a['known_tokens']['input'],19*row['requests'])
                self.assertEqual(a['known_tokens']['output'],7*row['requests'])
            if row['scenario'] in ('schema_fallback','transient_retry','partial','provider_error','missing_usage','timeout','retry_exhausted_schema','malformed_usage','inconsistent_usage','interrupt'):
                self.assertFalse(a['complete'])
            if row['scenario']=='schema_fallback': self.assertEqual((row['requests'],row['attempts']),(4,3))
            if row['scenario']=='transient_retry': self.assertEqual((row['requests'],row['attempts']),(6,3))
            if row['scenario'] in ('refusal','wrong_envelope','wrong_shape'):
                self.assertEqual(a['known_tokens']['input'],19*row['requests'])

    def test_valid_judgments_and_task_failure_independent_of_accounting(self):
        # Reuse PR148's outcome assertions verbatim, against the new admitted report.
        from test_standard_judges import NativeTests as Original
        original=Original(); original.record=self.record
        original.test_independent_failure_partial_failure_and_missingness_survive()
        self.assertFalse(self.record['benchmark']['judge_accounting']['complete'])
        by_case={o['case_id']:o['id'] for o in self.record['observations'] if o['arm']=='with_skill'}
        rows={o['observation_id']:o for o in self.record['benchmark']['observations']}
        self.assertEqual(rows[by_case['6']]['judge_accounting']['status'],'absent')
        self.assertEqual(rows[by_case['1']]['outcome'],'passed')
        retained = rows[by_case['1']]['judge_accounting']
        self.assertEqual(retained['status'],'observed')
        self.assertEqual(accounting.summarize([retained['evidence']])['known_tokens']['input'],57)
        summary=self.record['benchmark']['judge_accounting']
        self.assertEqual(summary['observed_trials'],18)
        self.assertEqual(summary['http_attempts'],sum(r['requests'] for r in self.proof['controls'] if 'case' in r and r['case']!='6'))
        self.assertGreater(summary['known_tokens']['input'],0)
        self.assertEqual(summary['known_tokens']['accepted_prediction'],80)
        self.assertEqual(summary['known_tokens']['rejected_prediction'],0)
        self.assertEqual(summary['token_coverage']['rejected_prediction'],40)
        self.assertIsNone(self.record['benchmark']['judge_accounting']['cost_estimate_usd'])

    def test_malformed_collected_accounting_keeps_valid_task_judgments(self):
        import benchmark_evidence as benchmark
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            shutil.copytree(self.output/'sanitized',root/'sanitized')
            member=next((root/'sanitized').glob('results/podman/*/codex/with-skill/trials/skillevaluator-1__*/judge_accounting.json'))
            reports.write_json(member, {'version':'invalid'})
            record=benchmark.report(ROOT,root/'sanitized','podman','standard',root/'admitted')
            identity=next(o['id'] for o in record['observations'] if o['case_id']=='1' and o['arm']=='with_skill')
            observed=next(o for o in record['benchmark']['observations'] if o['observation_id']==identity)
            self.assertEqual(observed['outcome'],'passed')
            self.assertEqual(observed['judge_accounting']['status'],'invalid')
            self.assertFalse(record['benchmark']['judge_accounting']['complete'])

    def test_successor_recovery_retains_incomplete_accounting_and_original_failure(self):
        import benchmark_evidence as benchmark
        import evaluator_profiles as profiles
        from qualify_benchmark_evidence import fixture
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            native=fixture(root/'fixture','interrupted',producer=profiles.ACCOUNTING)
            reports.benchmark_artifacts(ROOT,native,'podman',root/'sanitized')
            record=benchmark.report(ROOT,root/'sanitized','podman','standard',root/'admitted')
            self.assertTrue(record['benchmark']['recovery'])
            self.assertFalse(record['benchmark']['judge_accounting']['complete'])
            self.assertEqual(record['benchmark']['judge_accounting']['expected_trials'],20)
            self.assertFalse(benchmark.history_admission(record)['eligible'])

    def test_public_admission_rejects_duplicate_and_inflated_accounting(self):
        import skill_evidence as evidence
        import benchmark_evidence as benchmark
        self.assertFalse(benchmark.history_admission(self.record)['eligible'])
        value=copy.deepcopy(self.record)
        value['benchmark']['judge_accounting']['http_attempts']+=1
        with self.assertRaises(ValueError): evidence.validate_public(value)
        value=copy.deepcopy(self.record)
        rows=[r for r in value['benchmark']['observations'] if r['judge_accounting']['evidence']]
        rows[1]['judge_accounting']=copy.deepcopy(rows[0]['judge_accounting'])
        with self.assertRaises(ValueError): evidence.validate_public(value)
        self.assertEqual(self.proof['live_judgments'],'UNRUN')
        self.assertFalse(self.proof['paid_authority'])
