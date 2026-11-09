"""Prospective campaign authorization and measured-failure boundaries; no provider."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.github/scripts'))
import evaluation_campaign as campaign
import evaluation_campaign_core as core
import evaluation_campaign_protocol as protocol
import evaluation_runtime as runtime
from evaluation_tasks import load
import skill_evidence as evidence
import skill_reports as reports


class ProtocolContracts(unittest.TestCase):
    def task(self):
        return load(ROOT/'.github/evals/campaigns/boolean-effectiveness-v1.json')

    def test_six_slots_match_original_case_and_unchanged_model_with_separate_profiles(self):
        task=self.task(); proposal=protocol.frozen(task)
        self.assertEqual([r['variant'] for r in proposal['schedule']],['current','absent','absent','current','current','absent'])
        self.assertEqual([r['trial'] for r in proposal['schedule']],[1,1,2,2,3,3])
        self.assertEqual(set(r['case'] for r in proposal['schedule']),{'pester-004'})
        self.assertEqual(task.cases('live'),{'pester-004':None})
        self.assertEqual(task.entry()['prompt']+'\n',(ROOT/'.github/evals/pester-ceiling/candidate/prompt.txt').read_text())
        qualified=runtime.read_profile(ROOT/'.github/evals/campaigns/codex-qualified.json')
        self.assertEqual(proposal['runtime']['resolved'],qualified['resolved'])
        self.assertFalse(proposal['runtime']['profile']['inference_enabled'])
        for mode in ('live','experiment-probe'):
            purpose=campaign.purpose(task,mode)
            profile,_,_=evidence.custom_contract(task.definition['skill'],purpose=purpose)
            self.assertEqual(profile['campaign']['trials'],3)
            self.assertTrue(all(profile[k]==v for k,v in proposal['source_identities'][mode].items()))
        with self.assertRaisesRegex(ValueError,'cannot authorize'):
            protocol.protocol(load(ROOT/'.github/evals/campaigns/boolean-contract.json'))

    def test_live_bundle_preserves_original_case_without_self_copy_or_solution(self):
        task=self.task()
        with tempfile.TemporaryDirectory() as directory:
            bundle=task.bundle(Path(directory),'live')
            native=bundle/'evals/harbor'
            self.assertEqual([p.name for p in native.iterdir() if p.is_dir()],['pester-004'])
            self.assertFalse((native/'pester-004/solution').exists())
            self.assertEqual((native/'pester-004/instruction.md').read_text(),task.entry()['prompt']+'\n')
            self.assertEqual([r['id'] for r in reports.read_json(bundle/'evals/evals.json')['evals']],['pester-004'])

    def test_live_failure_is_measured_but_invalid_unknown_and_runtime_failures_stop(self):
        row={'cleanup':True,'returncode':0,'grading_present':True,'usage':{'estimated_usd':0},'outcome':{'classification':'passed'}}
        for outcome in ('passed','failed'):
            row['outcome']['classification']=outcome
            self.assertIsNone(protocol.stop_reason(row))
        for outcome,reason in [('unsupported','unsupported_grading'),('invalid','missing_usable_evidence'),('unknown','missing_usable_evidence'),('timeout','verifier_failure')]:
            row['outcome']['classification']=outcome;self.assertEqual(protocol.stop_reason(row),reason)
        row['outcome']['classification']='failed'
        for key,value,reason in [('cleanup',False,'cleanup_failure'),('returncode',124,'execution_infrastructure_failure'),
                                 ('grading_present',False,'missing_grading_evidence'),('native_exception','MissingCodexObservation','missing_native_observation'),
                                 ('native_exception','UnsupportedCodexProtocol','unsupported_runtime_protocol')]:
            self.assertEqual(protocol.stop_reason({**row,key:value}),reason)
        for cost in (None,True,-1,float('nan'),float('inf')):
            self.assertEqual(protocol.stop_reason({**row,'usage':{'estimated_usd':cost}}),'unknown_usage')
        # Known-control qualification still refuses an unexpected failing strong suite.
        with self.assertRaisesRegex(ValueError,'Unexpected Boolean'):
            self.task().check('identity',True,{'classification':'failed'},{})

    def test_actual_result_validation_does_not_require_a_strong_control(self):
        task=self.task()
        for reference,detections in [(1,[1,1,0,1,1]),(0,[0]*5),(1,[1]*5)]:
            passed=bool(reference and all(detections))
            outcome={'classification':'passed' if passed else 'failed','code':'evaluated',
                     'reference_pass':reference,'variant_detections':detections,'mutants_detected':sum(detections)}
            metrics={'pester_reference_pass':reference,'pester_mutation_detection':sum(detections)/5,'pester_test_quality':int(passed)}
            task.validate_result(outcome,metrics)
            with self.assertRaises(ValueError):task.validate_result(outcome,{})
            with self.assertRaises(ValueError):task.validate_result({**outcome,'mutants_detected':9},metrics)

    def test_every_stop_retains_five_slots_and_no_retry(self):
        for reason in protocol.protocol(self.task())['stop_rules']:
            rows=[{**r,'state':'unlaunched'} for r in protocol.frozen(self.task())['schedule']]
            ledger={'entries':rows};snapshots=[]
            def attempt(row,total):
                self.assertEqual(snapshots[-1]['entries'][0]['state'],'launching')
                row.update(state='failed',usage={'estimated_usd':0});return reason
            core.drive(ledger,attempt,save=lambda:snapshots.append(copy.deepcopy(ledger)),resources=lambda:(),baseline=(),threshold=5)
            self.assertEqual([r['state'] for r in rows],['failed']+['unlaunched']*5)
            self.assertEqual(ledger['stop_reason'],reason)

    def test_exact_receipt_first_dispatch_and_durable_local_claim(self):
        task=self.task();source='a'*40;approval=f'campaign-{source}-boolean-effectiveness-v1-prep123-usd8-one_dispatch'
        env={'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ATTEMPT':'1','GITHUB_RUN_ID':'10'}
        with patch.object(protocol,'revision',return_value=source),patch.dict(os.environ,env):
            receipt={'artifact':'123','dispatch':'one_dispatch','allocation':approval,'revision':source,
                     'protocol_digest':protocol.digest(ROOT/task.definition['protocol']),'run_id':'10','first_dispatch':True,
                     'authentication':'github-api-producer-and-digest','artifact_digest':'sha256:'+'b'*64}
            protocol.validate_receipt(receipt,approval,task)
            for key,value in [('revision','b'*40),('artifact','124'),('protocol_digest','wrong'),('run_id','11'),('first_dispatch',False)]:
                with self.assertRaises(ValueError):protocol.validate_receipt({**receipt,key:value},approval,task)
            with patch.dict(os.environ,GITHUB_RUN_ATTEMPT='2'),self.assertRaises(ValueError):protocol.allocation(approval,task)
            runs=[{'id':n,'display_title':'Evaluation campaign '+approval,'run_attempt':1,'event':'workflow_dispatch'} for n in (10,11)]
            protocol.first_dispatch(runs,approval,'10')
            with self.assertRaises(ValueError):protocol.first_dispatch(runs,approval,'11')
            with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,RUNNER_TEMP=d):
                protocol.claim(Path(d)/'campaign-live',receipt)
                with self.assertRaises(FileExistsError):protocol.claim(Path(d)/'campaign-live',receipt)
                with self.assertRaises(ValueError):protocol.claim(Path(d)/'another',receipt)

    def test_fresh_consumption_accepts_only_toml_presentation_changes(self):
        try: import dirhash
        except ImportError: self.skipTest('Owning descriptor runtime required')
        from codex_pilot_descriptors import retain_descriptors
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);ref=root/'reference';new=root/'new'
            ref.mkdir();new.mkdir();task=self.task()
            proposal={'protocol_digest':'synthetic'}
            reports.write_json(ref/'frozen-proposal.json',proposal)
            for destination,raw in [(ref,b'[agent]\ntimeout_sec=600.0\nuser="agent"\n'),
                                    (new,b'[agent]\nuser="agent"\ntimeout_sec=600.0\n')]:
                native=destination/'task';native.mkdir();(native/'task.toml').write_bytes(raw)
                members={'task.toml':evidence.digest_bytes(raw),'instruction.md':'sha256:'+'a'*64}
                captured=[{'arm':'with_skill','case_id':'task','members':members,'task_checksum':evidence.custom_task_checksum(members)}]
                reports.write_json(destination/'staging.json',captured)
                reports.write_json(destination/'deployment.json',{'same':'deployment'})
                retain_descriptors(destination,{'with_skill':[native]},captured)
            with patch.object(protocol,'frozen',return_value=proposal),patch.object(protocol.profiles,'runtime'):
                self.assertTrue(protocol.check(ref,new,task,qualified=False)['configurations_equal'])
                raw=b'[agent]\nuser="agent"\ntimeout_sec=601.0\n'
                (new/'task/task.toml').write_bytes(raw)
                captured=reports.read_json(new/'staging.json')
                captured[0]['members']['task.toml']=evidence.digest_bytes(raw)
                captured[0]['task_checksum']=evidence.custom_task_checksum(captured[0]['members'])
                reports.write_json(new/'staging.json',captured)
                retain_descriptors(new,{'with_skill':[new/'task']},captured)
                with self.assertRaisesRegex(ValueError,'configurations differ'):protocol.check(ref,new,task,qualified=False)

    def test_preparation_metadata_rejects_untrusted_producer_and_wrong_attempt(self):
        repo={'id':42,'full_name':protocol.REPO}
        run={'id':10,'repository':repo,'head_repository':repo,'head_sha':'a'*40,'path':protocol.WORKFLOW,
             'event':'pull_request','status':'completed','conclusion':'success','run_attempt':1}
        artifact={'workflow_run':{'repository_id':42,'head_repository_id':42,'id':10,'head_sha':'a'*40},
                  'name':'reusable-evaluation-1','expired':False,'size_in_bytes':10,'digest':'sha256:'+'b'*64}
        protocol.authenticate_metadata(artifact,run,'a'*40,42,100)
        for key,value in [('conclusion','failure'),('path','.github/workflows/other.yml'),('head_sha','b'*40),('run_attempt',2)]:
            with self.assertRaises(ValueError):protocol.authenticate_metadata(artifact,{**run,key:value},'a'*40,42,100)
        for key,value in [('expired',True),('digest','wrong'),('size_in_bytes',101),('name','reusable-evaluation-2')]:
            with self.assertRaises(ValueError):protocol.authenticate_metadata({**artifact,key:value},run,'a'*40,42,100)

    def test_qualification_refuses_credentials_and_live_requires_protected_job(self):
        with patch.dict(os.environ,OPENAI_API_KEY='synthetic-not-a-key'),self.assertRaises(ValueError):campaign.no_credentials()
        with patch.dict(os.environ,GITHUB_ACTIONS='false'),self.assertRaises(ValueError):protocol.runtime_gate(self.task())
        selected=runtime.read_profile(ROOT/'.github/evals/campaigns/codex-authorized-v1.json')
        with self.assertRaises(ValueError):runtime.validate_codex({**selected['profile'],'inference_enabled':True})

    def test_pinned_collector_preserves_three_trial_and_stopped_denominators(self):
        try:
            from importlib.metadata import version
            if version('skillevaluator') != '0.8.0': self.skipTest('Owning collector runtime required')
        except ImportError: self.skipTest('Owning collector runtime required')
        from datetime import datetime, timezone, timedelta
        from harbor.models.trial.result import TrialResult
        from harbor.models.task.task import Task
        from skillevaluator.tier3.harbor.collector import collect_harbor_results
        import shutil
        task=self.task();skill=task.definition['skill']
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);native=task.bundle(root,'live')/'evals/harbor/pester-004'
            checksum=Task(native).checksum;start=datetime.now(timezone.utc)
            for arm in ('with','without'):
                job=root/'jobs'/f'{skill}-codex-{arm}'
                for ordinal in (1,2,3):
                    name=f'campaign-pester-004-attempt{ordinal}__{arm}'
                    passed=ordinal != 2
                    metrics={'pester_reference_pass':1.0,'pester_mutation_detection':1.0 if passed else .8,'pester_test_quality':float(passed)}
                    value=TrialResult.model_validate({'task_name':'pester-004','trial_name':name,'trial_uri':(job/name).as_uri(),
                        'task_id':{'path':str(native)},'task_checksum':checksum,
                        'config':{'task':{'path':str(native)},'trial_name':name,'trials_dir':str(job),'agent':{'name':'codex'}},
                        'agent_info':{'name':'codex','version':'0.167.0'},'verifier_result':{'rewards':{'overall':float(passed),**metrics}},
                        'started_at':start.isoformat(),'finished_at':(start+timedelta(seconds=2)).isoformat(),
                        'verifier':{'started_at':(start+timedelta(seconds=1)).isoformat(),'finished_at':(start+timedelta(seconds=2)).isoformat()}})
                    reports.write_json(job/name/'result.json',json.loads(value.model_dump_json()))
                    reports.write_json(job/name/'verifier/skill_evaluator_reward.json',{'entry_id':'pester-004','trial_id':name,
                        'evaluation_status':'complete','overall':float(passed),'custom_metrics':metrics,
                        'details':{'outcome':{'classification':'passed' if passed else 'failed','code':'evaluated'}}})
            core.aggregates(root,skill=skill,carrier='codex')
            parameters=campaign.collection_parameters(task,'experiment-probe')
            def collect(destination):
                return collect_harbor_results(skill,['codex'],destination,root/'jobs',grading_mode='custom_only',**parameters)
            wrong=collect_harbor_results(skill,['codex'],root/'wrong-one-trial-policy',root/'jobs',grading_mode='custom_only',
                **{**parameters,'n_attempts':1})
            self.assertNotEqual(wrong['agents']['codex']['conditions']['with_skill']['execution_status'],'succeeded')
            value=collect(root/'complete')
            self.assertEqual(value['attempt_policy']['max_attempts'],3)
            for row in value['agents']['codex']['conditions'].values():
                self.assertEqual(row['expected_attempts'],3)
                self.assertEqual(row['scored_attempts'],3)
                self.assertEqual(row['execution_status'],'succeeded')
            shutil.rmtree(root/'jobs'/f'{skill}-codex-without')
            job=root/'jobs'/f'{skill}-codex-with'
            for ordinal in (2,3):shutil.rmtree(job/f'campaign-pester-004-attempt{ordinal}__with')
            core.aggregates(root,skill=skill,carrier='codex')
            partial=collect(root/'stopped')['agents']['codex']['conditions']
            self.assertEqual(partial['with_skill']['expected_attempts'],3)
            self.assertEqual(partial['without_skill']['expected_attempts'],3)
            self.assertEqual(partial['with_skill']['scored_attempts'],1)
            self.assertEqual(partial['without_skill']['scored_attempts'],0)
            self.assertNotEqual(partial['with_skill']['execution_status'],'succeeded')
            self.assertNotEqual(partial['without_skill']['execution_status'],'succeeded')

    def test_report_admission_preserves_inference_and_population_boundaries(self):
        task=self.task()
        config={'qualification':{'producer':'live','inference':True},'harbor':{'n_attempts':3,'stop_on_pass':False}}
        live=campaign.purpose(task,'live');probe=campaign.purpose(task,'experiment-probe')
        evidence.validate_custom_execution_config(live,config,3)
        fixture={**config,'qualification':{'producer':'cli_probe','inference':False}}
        evidence.validate_custom_execution_config(probe,fixture,3)
        with self.assertRaisesRegex(ValueError,'Live campaign purpose mismatch'):evidence.validate_custom_execution_config(live,fixture,3)
        with self.assertRaisesRegex(ValueError,'CLI probe purpose mismatch'):evidence.validate_custom_execution_config(probe,config,3)
        with self.assertRaisesRegex(ValueError,'execution policy mismatch'):evidence.validate_custom_execution_config(live,config,4)

    def test_report_labels_prospective_live_separately_from_nonforwarding_controls(self):
        import skill_analysis as analysis
        task=self.task()
        live={'custom':{'purpose':campaign.purpose(task,'live')}}
        probe={'custom':{'purpose':campaign.purpose(task,'experiment-probe')}}
        self.assertIn('Prospective exploratory',analysis.coverage_label({'behavioral_results':[live]}))
        self.assertIn('Credential-free',analysis.coverage_label({'behavioral_results':[probe]}))


if __name__=='__main__':unittest.main()
