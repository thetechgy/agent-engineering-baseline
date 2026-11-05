"""One explicitly authorized two-slot allocation; no service or reusable scheduler."""
import json,math,os,subprocess
from pathlib import Path

HERE=Path(__file__).parent
ID='sol-high-smoke-20261105'
ATTEMPTS={'current':5,'absent':6}

def validate(launch,env):
    a=launch.get('allocation',{})
    if launch.get('paid_execution_enabled') is not True or launch.get('scheduling_stopped') is not False:
        raise RuntimeError('Paid allocation is disabled')
    assert launch['phase']=='live-pair' and a['id']==ID and a['state']=='armed'
    assert launch['paid_attempts_used']==4 and launch['recovery_live_attempt_limit']==4
    assert launch['paid_attempt_limit']==36 and launch['paid_attempts_reserved']==2
    assert a['attempts']==ATTEMPTS and a['limit']==2 and a['prior_campaign_attempts']==4
    assert (a['budget_usd'],a['second_attempt_reserve_usd'],a['headroom_usd'])==(5,2.5,0.5)
    assert env.get('GITHUB_REPOSITORY')=='thetechgy/agent-engineering-baseline'
    assert env.get('GITHUB_REF')=='refs/heads/trial/direct-harbor' and env.get('GITHUB_EVENT_NAME')=='push'
    assert env.get('GITHUB_RUN_ATTEMPT')=='1', 'Workflow reruns cannot spend'
    assert str(a['workflow_run_number'])==env.get('GITHUB_RUN_NUMBER'), 'Allocation belongs to one workflow run number'
    assert env.get('GITHUB_RUN_ID','').isdigit()
    return a

def active():
    launch=json.loads((HERE/'launch.json').read_text());a=validate(launch,os.environ)
    assert subprocess.check_output(['git','rev-parse','HEAD^'],text=True).strip()==a['code_commit']
    changed=subprocess.check_output(['git','diff-tree','--no-commit-id','--name-only','-r','HEAD'],text=True).splitlines()
    assert changed==['.github/trials/direct-harbor/launch.json'], 'Arming commit may change only allocation metadata'
    assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==os.environ['GITHUB_SHA']
    return a

def gate(record,a):
    """Correctness is not a gate; trustworthy evidence and available reserve are."""
    reasons=[]
    if not record.get('result_extraction_succeeded'):reasons.append('incomplete_evidence')
    if record.get('harbor_returncode')!=0:reasons.append('native_process_failure')
    if record.get('usage_and_activation',{}).get('tool_error_flags',{}).get('runtime_tool_error',0):reasons.append('runtime_tool_error')
    if not record.get('execution_completed'):reasons.append('execution_incomplete')
    if not record.get('usage_complete'):reasons.append('incomplete_new_usage')
    if not record.get('agent_container_removed') or not record.get('verifier_container_removed'):reasons.append('disposal_unconfirmed')
    rows=record.get('projection',[])
    if len(rows)!=1 or rows[0].get('failure_cause') is not None:reasons.append('native_execution_failure')
    classification=record.get('handoff',{}).get('classification',{}).get('classification')
    if classification not in ('graded_passed','graded_failed','missing_deliverable','rejected_output'):
        reasons.append('unreliable_or_unsupported_outcome')
    cost=record.get('usage_estimate_usd')
    if type(cost) not in (float,int) or not math.isfinite(cost) or cost<0:reasons.append('unknown_new_cost_estimate')
    elif cost+a['second_attempt_reserve_usd']+a['headroom_usd']>a['budget_usd']:reasons.append('insufficient_spending_reserve')
    return {'allowed':not reasons,'reasons':reasons,'conservative_spend_usd':cost,
        'second_attempt_reserve_usd':a['second_attempt_reserve_usd'],'headroom_usd':a['headroom_usd'],'budget_usd':a['budget_usd']}

def receipt_path(root,variant):return root/'public/allocation'/('attempt-'+str(ATTEMPTS[variant])+'.json')

def reserve(root,variant):
    assert not os.environ.get('OPENAI_API_KEY'), 'Reserve before the credentialed step'
    a=active();assert variant in ATTEMPTS
    assert json.loads((root/'public/preflight.json').read_text())['passed']
    assert not (root/'public/allocation/closed.json').exists(), 'Allocation already closed'
    if variant=='absent':
        first=json.loads((root/'public/current/attempt.json').read_text())
        decision=gate(first,a)
        (root/'public/allocation/second-arm-gate.json').write_text(json.dumps(decision,indent=2)+'\n')
        assert decision['allowed'], decision['reasons']
    value={'allocation_id':ID,'attempt':ATTEMPTS[variant],'variant':variant,'state':'reserved_consumed_if_launch_unknown',
           'commit':os.environ['GITHUB_SHA'],'run_id':os.environ['GITHUB_RUN_ID'],'run_number':os.environ['GITHUB_RUN_NUMBER']}
    path=receipt_path(root,variant);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:json.dump(value,f,indent=2)
    return value

def close(root):
    receipts=[json.loads(p.read_text()) for p in (root/'public/allocation').glob('attempt-*.json')]
    record={'allocation_id':ID,'state':'closed','paid_execution_enabled':False,'reserved_slots_consumed':[r['attempt'] for r in receipts],
        'campaign_attempts_consumed':4+len(receipts),'previous_recovery_consumed':4,'previous_recovery_limit':4,
        'incremental_api_bill_usd':None,'historical_cumulative_api_bill_usd':None,
        'note':'Reservations conservatively consume slots if credentialed launch evidence is lost. No receipt means that arm was not scheduled.'}
    estimates=[]
    for r in receipts:
        p=root/'public'/r['variant']/'attempt.json';d=json.loads(p.read_text()) if p.is_file() else {}
        estimates.append(d.get('usage_estimate_usd') if d.get('usage_complete') else None)
    record['incremental_conservative_estimate_usd']=sum(estimates) if estimates and all(v is not None for v in estimates) else None
    destination=root/'public/allocation/closed.json';destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record))

if __name__=='__main__':
    import sys
    if sys.argv[1]=='validate':active()
    elif sys.argv[1]=='reserve':reserve(Path(sys.argv[2]),sys.argv[3])
    elif sys.argv[1]=='close':close(Path(sys.argv[2]))
