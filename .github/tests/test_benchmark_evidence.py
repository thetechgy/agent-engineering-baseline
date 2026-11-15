"""Versioned behavioral admission controls; no provider or model is invoked."""
import copy
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))
import benchmark_evidence as benchmark
import evaluator_profiles as profiles
import skill_evidence as evidence
import skill_reports as reports


class ProfileTests(unittest.TestCase):
    def test_explicit_offline_profile_preserves_old_production_selection(self):
        self.assertIs(benchmark.profile('behavioral-090-offline-v1'), profiles.benchmark_profile('behavioral-090-offline-v1'))
        self.assertEqual(reports.POLICY['evaluator_revision'], profiles.HISTORICAL_REVISION)
        self.assertFalse(profiles.benchmark_profile('behavioral-090-offline-v1')['production_history'])
        for value in ('0.9.0', profiles.NEXT['id'], profiles.CANDIDATE['id'], None):
            with self.subTest(value=value), self.assertRaises(ValueError): benchmark.profile(value)
        for origin in ('live', 'recovered', 'synthetic'):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                benchmark.metadata({'profile':profiles.benchmark_profile('behavioral-090-offline-v1')['id'], 'origin':origin, 'judgments':'simulated'})


@unittest.skipUnless(os.environ.get('BENCHMARK_090_EVIDENCE'), 'requires actual released fixture collection')
class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(os.environ['BENCHMARK_090_EVIDENCE'])
        cls.records = {scenario:reports.read_json(next((cls.root / scenario / 'admitted/public/skills/podman/behavioral').glob('*/public-report.json')))
                       for scenario in ('complete','unavailable','interrupted')}

    def rows(self, scenario, case, arm='with_skill'):
        r = self.records[scenario]
        ids = {o['id'] for o in r['observations'] if o['arm'] == arm and o['case_id'] == case}
        return [o for o in r['benchmark']['observations'] if o['observation_id'] in ids]

    def test_positive_negative_and_na_use_released_semantics(self):
        complete = self.records['complete']
        self.assertEqual(complete['benchmark']['native_status'], 'complete')
        self.assertEqual(len(complete['observations']),20)
        self.assertEqual(self.rows('complete','1')[0]['outcome'], 'passed')
        negative = self.rows('complete','2')[0]
        self.assertEqual(negative['outcome'], 'failed')
        self.assertGreater(negative['quality']['overall'],0.5)
        self.assertFalse(negative['quality']['correct_answer'])
        self.assertTrue(negative['quality']['security_clean'])
        self.assertEqual(negative['quality']['required_failure'], 'wrong_answer')
        security = self.rows('complete','3')[0]
        self.assertTrue(security['quality']['correct_answer'])
        self.assertFalse(security['quality']['security_clean'])
        self.assertEqual(security['quality']['required_failure'],'security')
        self.assertTrue(all(a['execution_status'] == 'succeeded' for a in complete['arms']))
        na = self.rows('complete','8')[0]
        self.assertEqual(na['dimensions']['efficiency'], {'status':'not_applicable','value':None})
        self.assertEqual(self.rows('complete','1','without_skill')[0]['metrics']['skill_execution']['status'],'not_applicable')
        self.assertFalse(complete['metrics'])

    def test_unavailable_judgment_retains_deterministic_observations_and_findings(self):
        unavailable = self.rows('unavailable','4')[0]
        self.assertEqual(unavailable['outcome'],'judgment_unavailable')
        self.assertIsNone(unavailable['quality']['passed'])
        self.assertEqual(unavailable['metrics']['security'], {'status':'observed','value':1.0})
        self.assertEqual(unavailable['dimensions']['correctness'], {'status':'observed','value':1.0})
        self.assertEqual(unavailable['metrics']['goal_accuracy'], {'status':'unavailable','value':None})
        self.assertEqual(unavailable['dimensions']['effectiveness'], {'status':'unavailable','value':None})
        unsupported = self.rows('unavailable','5')[0]
        self.assertEqual(unsupported['outcome'],'unsupported')
        self.assertIsNone(unsupported['quality']['overall'])
        self.assertEqual(sum(f['score_impact'] for f in unsupported['security_evidence']['findings']),1)
        self.assertNotIn('abcdefgh12345678', json.dumps(self.records['unavailable']))
        self.assertIsNone(unsupported['quality']['security_clean'])
        self.assertEqual(self.rows('unavailable','1')[0]['outcome'],'passed')
        self.assertEqual(self.rows('unavailable','6')[0]['outcome'],'runtime_failure')
        self.assertIsNone(self.rows('unavailable','6')[0]['quality']['passed'])

    def test_failed_judge_and_transport_values_cannot_acquire_measurements(self):
        from evaluator_090 import diagnostic_observations
        path = self.root / 'unavailable/sanitized/results/podman/unavailable/codex/with-skill/trials/skillevaluator-4__attempt001'
        reward = reports.read_json(path / 'reward.json'); trial = reports.read_json(path / 'result.json')
        self.assertEqual(diagnostic_observations(reward,trial)['accuracy'],1.0)
        for key,value in (('goal_accuracy',0.0), ('overall',False), ('unknown_metric',1.0)):
            changed = copy.deepcopy(trial); changed['verifier_result']['rewards'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): diagnostic_observations(reward,changed)
        unsupported = copy.deepcopy(reward); unsupported['evaluation_errors'] = {'execution_evidence':'unsupported'}
        with self.assertRaises(ValueError): diagnostic_observations(unsupported,trial)

    def test_recovery_keeps_primary_outcome_absence_and_unaffected_baseline(self):
        record = self.records['interrupted']
        self.assertTrue(record['benchmark']['recovery'])
        self.assertEqual(record['benchmark']['native_status'],'incomplete')
        provenance = reports.read_json(self.root / 'interrupted/sanitized/provenance.json')
        self.assertEqual(provenance['evaluation_outcome'],'cancelled')
        self.assertEqual(provenance['policy']['evaluator_revision'], profiles.NEXT['revision'])
        self.assertEqual(provenance['policy']['grading'],'default')
        self.assertEqual(provenance['patch_sha256'],profiles.NEXT['patch_sha256'])
        pop = record['benchmark']['populations']
        self.assertEqual(pop['with_skill']['correctness']['absent'],1)
        self.assertEqual(pop['without_skill']['correctness']['absent'],0)
        self.assertEqual(pop['with_skill']['correctness']['expected'],10)
        self.assertEqual(len([o for o in record['observations'] if o['arm']=='without_skill']),10)
        self.assertIn('recovered',benchmark.history_admission(record)['reasons'])

    def test_history_and_mixed_policy_comparisons_refuse_fixture_promotion(self):
        import skill_analysis as analysis
        import skill_history as history
        import skill_pages as pages
        from test_skill_pages import prov
        record = self.records['complete']
        for r in self.records.values():
            self.assertFalse(benchmark.history_admission(r)['eligible'])
            stripped = copy.deepcopy(r); stripped.pop('benchmark')
            with self.assertRaisesRegex(ValueError,'production history'):
                history.observation(stripped,'standard--podman',prov('a'*40,kind='benchmark'),'2026-11-15T00:00:00Z')
            with self.assertRaisesRegex(ValueError,'production history'):
                history.observation(r,'standard--podman',prov('a'*40,kind='benchmark'),'2026-11-15T00:00:00Z')
            from types import SimpleNamespace
            with self.assertRaisesRegex(ValueError,'production history'):
                pages.bundle_claims(SimpleNamespace(records={'fixture':r}), 'standard--podman', prov('a'*40,kind='benchmark'))
        legacy = copy.deepcopy(record); legacy.pop('benchmark')
        self.assertEqual(analysis.classify(record, legacy, analysis.condition_identity(record),analysis.condition_identity(legacy))[0], 'incompatible_or_unknown')
        for field in ('model','grading','codex','harbor'):
            changed = copy.deepcopy(record); changed['policy']['fields'][field] = 'different'
            self.assertNotEqual(analysis.classify(record,changed,analysis.condition_identity(record),analysis.condition_identity(changed))[0],'directly_comparable')
        changed = copy.deepcopy(record); changed['dataset']['staged_digest']='sha256:'+'f'*64
        self.assertNotEqual(benchmark.comparison_identity(record),benchmark.comparison_identity(changed))
        for mutate in ('profile','origin','policy_id','judgments'):
            changed = copy.deepcopy(record); changed['benchmark'][mutate]='wrong'
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): evidence.validate_public(changed)
        fake = {'schema_version':1,'skill':'podman','mode':'standard','revision':'a'*40,
                'policy':dict(reports.POLICY,evaluator_revision=profiles.NEXT['revision']),
                'patch_sha256':profiles.NEXT['patch_sha256'],'dataset_digest':record['dataset']['staged_digest'],
                'metrics':[]}
        with self.assertRaisesRegex(ValueError,'policy mismatch'):
            reports.validate_metrics(fake,ROOT,'podman','a'*40)

    def test_changed_native_dimensions_and_model_are_rejected(self):
        native = self.root / 'complete/sanitized'
        run = native / 'results/podman/complete'
        member = run / 'result.json'; original = member.read_bytes()
        try:
            changed = json.loads(original)
            changed['agents']['codex']['dimensions_with_skill']['correctness']['score'] = 0.2
            reports.write_json(member, changed)
            with self.assertRaisesRegex(ValueError,'applicability mismatch'):
                evidence.normalize_behavioral(native,'podman',workspace=ROOT)
        finally: member.write_bytes(original)
        config_path = run / 'run_config.json'; config_original = config_path.read_bytes()
        try:
            config = json.loads(config_original); config['provider']['model'] = 'different-model'
            changed = json.loads(original); changed['run_config'] = config
            reports.write_json(member,changed); reports.write_json(config_path,config)
            with self.assertRaisesRegex(ValueError,'Runtime/policy disagreement'):
                evidence.normalize_behavioral(native,'podman',workspace=ROOT)
        finally:
            member.write_bytes(original); config_path.write_bytes(config_original)

    def test_witness_and_native_policy_mismatches_reject_before_projection(self):
        native = self.root / 'complete/sanitized'
        admitted = evidence.normalize_behavioral(native,'podman',workspace=ROOT)
        changed = copy.deepcopy(admitted)
        changed['benchmark']['observations'][0]['quality']['overall']=0.1
        with self.assertRaisesRegex(ValueError,'claims differ'):
            evidence.project(changed)
        member = native / 'provenance.json'; original = member.read_bytes()
        try:
            value = json.loads(original); value['benchmark']['profile']='wrong'
            reports.write_json(member,value)
            with self.assertRaisesRegex(ValueError,'Unsupported behavioral'):
                evidence.normalize_behavioral(native,'podman',workspace=ROOT)
        finally: member.write_bytes(original)
        member = native / 'versions.json'; original = member.read_bytes()
        try:
            reports.write_json(member,profiles.candidate_versions(profiles.RETAINED_NEXT))
            with self.assertRaises(ValueError): evidence.normalize_behavioral(native,'podman',workspace=ROOT)
        finally: member.write_bytes(original)
        # A cached witness cannot project after any captured member changed.
        with self.assertRaises(ValueError):
            for guard in evidence.record_guards(evidence.project(admitted)): guard()
