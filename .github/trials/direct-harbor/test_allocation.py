"""Focused synthetic allocation checks: never inject a credential or launch an agent."""
import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import allocation,live

A={'id':allocation.ID,'state':'armed','attempts':allocation.ATTEMPTS,'reservation_ids':allocation.RESERVATIONS,'limit':2,
   'prior_campaign_attempts':5,'budget_usd':5,'second_attempt_reserve_usd':2.5,'headroom_usd':0.5,'workflow_run_number':17}
ENV={'GITHUB_REPOSITORY':'thetechgy/agent-engineering-baseline','GITHUB_REF':'refs/heads/trial/direct-harbor',
     'GITHUB_EVENT_NAME':'push','GITHUB_RUN_ATTEMPT':'1','GITHUB_RUN_NUMBER':'17','GITHUB_RUN_ID':'123','GITHUB_SHA':'fixture'}
LAUNCH={'phase':'live-pair','paid_execution_enabled':True,'scheduling_stopped':False,'paid_attempts_used':5,
        'paid_attempts_reserved':2,'paid_attempt_limit':36,'recovery_live_attempt_limit':4,'allocation':A}

def usable(classification='graded_failed'):
    return {'harbor_returncode':0,'result_extraction_succeeded':True,'execution_completed':True,'execution_assessment':{'outcome':'completed','interpretable':True},'accounting_assessment':{'usable_for_scheduling':True},
        'agent_container_removed':True,'verifier_container_removed':True,'projection':[{'failure_cause':None}],
        'handoff':{'classification':{'classification':classification}},'usage_estimate_usd':0.8}

class AllocationTests(unittest.TestCase):
    def test_explicit_allocation_and_disabled_default(self):
        self.assertEqual(allocation.validate(LAUNCH,ENV)['attempts'],{'current':6,'absent':7})
        for field,value in [('paid_execution_enabled',False),('paid_attempts_used',2),('paid_attempts_reserved',3),('recovery_live_attempt_limit',6)]:
            d=copy.deepcopy(LAUNCH);d[field]=value
            with self.assertRaises((AssertionError,RuntimeError)):allocation.validate(d,ENV)
    def test_reruns_other_pushes_and_contexts_cannot_spend(self):
        for field,value in [('GITHUB_RUN_ATTEMPT','2'),('GITHUB_RUN_NUMBER','18'),('GITHUB_EVENT_NAME','workflow_dispatch'),('GITHUB_REF','refs/heads/main'),('GITHUB_REPOSITORY','other/repo')]:
            with self.assertRaises(AssertionError):allocation.validate(LAUNCH,{**ENV,field:value})
    def test_interpretable_failures_allow_second_arm(self):
        for outcome in ('graded_passed','graded_failed','missing_deliverable','rejected_output'):
            self.assertTrue(allocation.gate(usable(outcome),A)['allowed'])
    def test_unknown_usage_broken_handoff_or_excess_spend_stops(self):
        for outcome in ('missing_evidence','collection_failure','transfer_failure','unsupported_submission'):
            self.assertFalse(allocation.gate(usable(outcome),A)['allowed'])
        for field,value in [('harbor_returncode',1),('accounting_assessment',{'usable_for_scheduling':False}),('execution_assessment',{'interpretable':False}),('agent_container_removed',False),('verifier_container_removed',None),('usage_estimate_usd',None),('usage_estimate_usd',float('nan')),('usage_estimate_usd',2.01)]:
            r=usable();r[field]=value;self.assertFalse(allocation.gate(r,A)['allowed'])
        r=usable();r['projection'][0]['failure_cause']='model_provider_failed';self.assertFalse(allocation.gate(r,A)['allowed'])
    def test_reservation_survives_interruption_and_cannot_be_replayed(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,ENV,clear=True),patch.object(allocation,'active',return_value=A):
            root=Path(temp);(root/'public/current').mkdir(parents=True)
            (root/'public/preflight.json').write_text('{"passed":true}')
            self.assertEqual(allocation.reserve(root,'current')['attempt'],6)
            with self.assertRaises(FileExistsError):allocation.reserve(root,'current')
            with self.assertRaises(FileNotFoundError):allocation.reserve(root,'absent')
            (root/'public/current/attempt.json').write_text(json.dumps(usable('missing_deliverable')))
            self.assertEqual(allocation.reserve(root,'absent')['attempt'],7)
            with self.assertRaises(FileExistsError):allocation.reserve(root,'absent')
            allocation.close(root)
            closed=json.loads((root/'public/allocation/closed.json').read_text());self.assertEqual(closed['campaign_attempts_consumed'],7)
            self.assertEqual(len(set(closed['reservation_ids'])),2)
            with self.assertRaises(AssertionError):allocation.reserve(root,'absent')
    def test_categories_are_not_double_counted_or_missing_to_zero(self):
        u={'input_tokens':60000,'cached_input_tokens':45000,'cache_write_input_tokens':5000,'output_tokens':4000,'reasoning_output_tokens':3000,'total_tokens':64000}
        self.assertEqual(live.usage_estimate(u),0.66)
        for key in u:
            missing=dict(u);missing.pop(key);self.assertIsNone(live.usage_estimate(missing))
        self.assertIsNone(live.usage_estimate({**u,'cached_input_tokens':60000}))
        self.assertIsNone(live.usage_estimate({**u,'reasoning_output_tokens':5000}))
    def test_workflow_uses_protected_environment_one_run_and_checkpoint_order(self):
        import yaml
        workflow=yaml.safe_load((live.trial.ROOT/'.github/workflows/direct-harbor-trial.yml').read_text())
        job=workflow['jobs']['live'];self.assertEqual(job['environment'],'skill-benchmark')
        self.assertIn('github.run_attempt == 1',job['if']);self.assertFalse(workflow['concurrency']['cancel-in-progress'])
        steps=job['steps'];names=[s['name'] for s in steps if 'name' in s]
        self.assertLess(names.index('Checkpoint current attempt before absent arm'),names.index('Gate and reserve campaign attempt seven without credentials'))
        credentials=[s for s in steps if 'OPENAI_API_KEY' in s.get('env',{})]
        self.assertEqual(len(credentials),2)
        self.assertEqual([s['env']['OPENAI_API_KEY'] for s in credentials],['${{ secrets.OPENAI_API_KEY }}']*2)
        for s in steps:
            if s.get('uses','').startswith('actions/checkout@'):self.assertFalse(s['with']['persist-credentials'])

if __name__=='__main__':unittest.main()
