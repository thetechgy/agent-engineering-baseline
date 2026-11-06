"""Small native-event fixtures plus retained attempt-five evidence; no inference."""
import copy,json,unittest
from pathlib import Path
import accounting,allocation,live
from test_allocation import A,usable

U={'input_tokens':63206,'cached_input_tokens':36025,'cache_write_input_tokens':27114,'output_tokens':633,'reasoning_output_tokens':49,'total_tokens':63839}
def fixture(failed=False):
    details={'total_usage':dict(U),'completion_event':True,'session_evidence':{'rollout_files':1,'malformed_lines':0,'usage_before_terminal':True}}
    native={'failure_cause':'unclassified' if failed else None,'exceptions':[{'exception_type':'NonZeroAgentExitCodeError'}] if failed else []}
    terminal=[{'type':'thread.started'},{'type':'turn.started'},({'type':'turn.failed','exact_budget_exhaustion':True} if failed else {'type':'turn.completed','usage':{k:U[k] for k in accounting.CATEGORIES}})]
    return native,details,terminal

class AccountingTests(unittest.TestCase):
    def test_usable_terminal_failure_does_not_require_success(self):
        n,d,t=fixture(True);assessment=accounting.assess(n,d,t,live.usage_estimate(U))
        self.assertEqual(assessment['execution_assessment']['outcome'],'agent_token_budget_exhausted')
        self.assertTrue(assessment['accounting_assessment']['usable_for_scheduling'])
        r=usable('missing_deliverable');r.update(assessment,execution_completed=False,projection=[n])
        self.assertTrue(allocation.gate(r,A)['allowed']);self.assertEqual(n['failure_cause'],'unclassified')
    def test_fixture_rollout_and_terminal_parser_through_collector(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'agent').mkdir()
            events=[{'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':U}}}, {'type':'event_msg','payload':{'type':'task_complete','last_agent_message':None}}]
            (root/'agent/rollout-synthetic.jsonl').write_text('\n'.join(map(json.dumps,events)))
            n,_,_=fixture(True);details=live.usage_and_activation(root)
            terminal=accounting.terminal_events('\n'.join(map(json.dumps,[{'type':'thread.started'},{'type':'turn.failed','error':{'message':accounting.BUDGET_ERROR}}])))
            self.assertTrue(accounting.assess(n,details,terminal,live.usage_estimate(U))['accounting_assessment']['usable_for_scheduling'])
    def test_success_counters_must_match_and_session_must_be_complete(self):
        n,d,t=fixture();self.assertTrue(accounting.assess(n,d,t,.641555)['accounting_assessment']['usable_for_scheduling'])
        for change in ('missing_terminal','mismatch','incomplete_session','missing_category'):
            nn,dd,tt=copy.deepcopy((n,d,t));estimate=.641555
            if change=='missing_terminal':tt=tt[:-1]
            elif change=='mismatch':tt[-1]['usage']['input_tokens']+=1
            elif change=='incomplete_session':dd['session_evidence']['malformed_lines']=1
            else:estimate=None
            self.assertFalse(accounting.assess(nn,dd,tt,estimate)['accounting_assessment']['usable_for_scheduling'])
    def test_infrastructure_and_generic_exits_never_become_budget_failure(self):
        for cause in ('model_provider_failed','environment_start_failed','verifier_timeout','unclassified'):
            n,d,t=fixture(True);n['failure_cause']=cause
            if cause=='unclassified':t[-1]['exact_budget_exhaustion']=False
            result=accounting.assess(n,d,t,.641555)
            self.assertFalse(result['execution_assessment']['interpretable']);self.assertFalse(result['accounting_assessment']['usable_for_scheduling'])
    def test_model_or_tool_text_cannot_claim_native_failure(self):
        events=[{'type':'item.completed','item':{'text':accounting.BUDGET_ERROR}}, {'type':'error','message':accounting.BUDGET_ERROR}]
        self.assertEqual(accounting.terminal_events('\n'.join(map(json.dumps,events))),[])
    def test_retained_attempt_five_native_error_and_usage_remain_separate(self):
        evidence=json.loads(Path(__file__).with_name('results').joinpath('allocation-evidence.json').read_text())
        # After closure, the original immutable metadata is nested in history.
        if evidence['allocation_id']!= 'sol-high-smoke-20261105':evidence=next(x for x in evidence['allocation_history'] if x['allocation_id']=='sol-high-smoke-20261105')
        a=evidence['arms']['current']['attempt'];diag=evidence['arms']['current']['launch-diagnostics']
        terminal=accounting.terminal_events(diag['primary_failure']['stdout'])
        result=accounting.assess(a['projection'][0],a['usage_and_activation'],terminal,live.usage_estimate(a['usage_and_activation']['total_usage']))
        self.assertEqual(result['execution_assessment']['outcome'],'agent_token_budget_exhausted')
        self.assertEqual(result['accounting_assessment']['observed_usage_estimate_usd'],.641555)
        # Historical capture lacks ordered raw-session evidence. Do not invent it.
        self.assertIn('session_coverage_unverified',result['accounting_assessment']['reasons'])
        self.assertIsNone(result['accounting_assessment']['provider_bill_usd'])

if __name__=='__main__':unittest.main()
