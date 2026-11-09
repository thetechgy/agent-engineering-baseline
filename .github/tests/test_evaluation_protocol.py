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

    def test_report_labels_prospective_live_separately_from_nonforwarding_controls(self):
        import skill_analysis as analysis
        task=self.task()
        live={'custom':{'purpose':campaign.purpose(task,'live')}}
        probe={'custom':{'purpose':campaign.purpose(task,'experiment-probe')}}
        self.assertIn('Prospective exploratory',analysis.coverage_label({'behavioral_results':[live]}))
        self.assertIn('Credential-free',analysis.coverage_label({'behavioral_results':[probe]}))


if __name__=='__main__':unittest.main()
