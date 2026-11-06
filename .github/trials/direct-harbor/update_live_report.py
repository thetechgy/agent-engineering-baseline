"""Append this allocation's reviewed metadata to the existing single report."""
import json,os,shutil,sys
from pathlib import Path
import run as trial
from allocation import ID,ATTEMPTS

def read(path):return json.loads(path.read_text()) if path.is_file() else None

def main(root,out):
    source=Path(__file__).with_name('results');shutil.copytree(source,out)
    data=read(out/'results.json');public=root/'public'
    closure=read(public/'allocation/closed.json')
    if closure is None:raise RuntimeError('Allocation closure evidence unavailable; preserve reservations for manual reconciliation')
    prior_evidence=read(out/'allocation-evidence.json')
    prior_allocation=data.get('live_allocation')
    arms={v:{name:read(public/v/(name+'.json')) for name in ('attempt','manifest','boundary','installation','container-policy','effective-config','configuration-load','budget-preflight','launch-diagnostics')} for v in ATTEMPTS}
    evidence={'allocation_id':ID,'commit':os.environ.get('GITHUB_SHA'),'run_id':os.environ.get('GITHUB_RUN_ID'),
        'profile':read(Path(__file__).with_name('runtime-profile.json')),'closure':closure,'arms':arms,
        'deployment_comparison':read(public/'comparison-manifest.json'),
        'second_arm_gate':read(public/'allocation/second-arm-gate.json'),
        'reservations':[read(p) for p in sorted((public/'allocation').glob('attempt-*.json'))],
        'budget_usd':5,'reserve_usd':2.5,'headroom_usd':0.5,'actual_billing_usd':None,
        'usage_note':'CLI-reported cumulative totals are retained without summing repeated token-count events. Cached reads and writes are input subsets; reasoning is an output subset. Conservative estimate charges all input at $10/M and output at $15/M, without adding subset counts. These are estimates, not provider bills.',
        'limits':['One attempt per arm cannot establish skill effectiveness; comparisons with historical CLI/model profiles are not skill-only comparisons',
            'File-access attempts are not successful reads, instruction following or causal skill benefit',
            'Native cleanup permission errors are retained; whole disposable-container removal is checked independently',
            'The API credential is available to the evaluated process. Unrelated credentials, raw transcripts and authentication files are excluded. Only the exact declared agent submission may be retained after credential/protected-content checks and download verification, for 30 days',
            'Pinned native pricing may be unavailable; historical cumulative spending remains unknown; $5 is an operational budget with possible overshoot, not a provider-enforced cap']}
    evidence['allocation_history']=list((prior_evidence or {}).get('allocation_history',[]))
    if prior_evidence and prior_evidence['allocation_id']!=ID:
        evidence['allocation_history'].append({k:v for k,v in prior_evidence.items() if k!='allocation_history'})
    if prior_allocation and prior_allocation['id']!=ID:
        data.setdefault('live_allocation_history',[]).append(prior_allocation)
    trial.write(out/'allocation-evidence.json',evidence)
    rows=[]
    for variant,files in arms.items():
        r=files['attempt'] or {};native=(r.get('projection') or [{}])[0];handoff=r.get('handoff',{});c=handoff.get('classification',{});observed=native.get('outcome',{})
        usage=r.get('usage_and_activation',{})
        reserved=any(item['variant']==variant for item in evidence['reservations'])
        execution=r.get('execution_assessment',{}).get('outcome','not_scheduled' if not reserved else 'unresolved_execution_failure')
        rows.append({'variant':variant,'attempt':ATTEMPTS[variant],
            'scheduled':reserved,'reserved':reserved,'credentialed_launch_started':r.get('credentialed_launch_started',None if reserved else False),'submission_retention':r.get('submission_retention'),'session_completed':r.get('execution_completed'),'execution_outcome':execution,
            'task_completion_measured':c.get('task_completion_measured',False),'task_completed':c.get('task_completed'),
            'outcome':c.get('classification','not_scheduled' if not r else 'missing_evidence'),
            'handoff':handoff.get('upload_status'),'admission':observed.get('admission_rule') or observed.get('admission_reason') or observed.get('code'),
            'admission_diagnostic':observed.get('admission_diagnostic'),
            'valid_grade':native.get('measured',False),'reference_pass':observed.get('reference_pass') if native.get('measured') else None,
            'mutants_detected':observed.get('mutants_detected') if native.get('measured') else None,
            'mutants_executed':observed.get('mutants_executed') if native.get('measured') else None,
            'skill_file_access_attempts':usage.get('skill_file_access_attempts'),
            'tool_calls':usage.get('tool_calls'),'tool_errors':usage.get('tool_error_flags'),
            'failure_cause':native.get('failure_cause'),'timing':native.get('timing'),'duration_seconds':r.get('duration_seconds'),
            'usage':usage.get('total_usage'),'accounting_assessment':r.get('accounting_assessment'),
            'execution_assessment':r.get('execution_assessment'),'native_terminal':r.get('native_terminal'),'conservative_estimate_usd':r.get('usage_estimate_usd'),
            'native_pricing_estimate_usd':r.get('native_pricing_estimate_usd'),'api_bill_usd':None,
            'evidence_complete':r.get('result_extraction_succeeded',False),
            'containers_removed':(r.get('agent_container_removed') is True and r.get('verifier_container_removed') is True) if r else None})
    usable=all(r['scheduled'] and (r.get('execution_assessment') or {}).get('interpretable') and (r.get('accounting_assessment') or {}).get('usable_for_scheduling') and r['evidence_complete'] and r['containers_removed'] and (r.get('submission_retention') or {}).get('status') in ('published_verified','missing') and
        r['outcome'] in ('graded_passed','graded_failed','missing_deliverable','rejected_output') for r in rows)
    data['live_allocation']={'id':ID,'rows':rows,'closure':closure,'operationally_usable':usable,'profile':evidence['profile']['id'],'limits':evidence['limits'],'usage_note':evidence['usage_note']}
    evidence['admission_preflight'] = read(public/'admission-preflight.json')
    data['live_allocation']['admission_preflight'] = evidence['admission_preflight']
    data['retention_validation']=read(Path(__file__).with_name('results')/'retention-validation.json')
    trial.write(out/'allocation-evidence.json', evidence)
    observed_estimates=[r['conservative_estimate_usd'] for r in rows if r['conservative_estimate_usd'] is not None]
    data['live_allocation']['observed_usage_conservative_estimate_usd']=sum(observed_estimates) if observed_estimates else None
    data['live_allocation']['reviewed_notes']=[
        'Both arms use the fully disabled supplemental rollout-budget feature, including reminders; the CLI feature listing is checked before credentials and after Harbor uploads its effective configuration. Attempt five used a different budget profile and is historical evidence, not a matched comparison.',
        'Execution outcome, task completion, independent correctness, session usage coverage and provider billing are assessed separately. A recognized agent failure can be interpretable without a valid correctness grade.',
        'Historical attempt five remains a native NonZeroAgentExitCodeError / unclassified with the exact Codex budget-exhaustion event. Retained usage estimates remain available; ordered raw-session coverage was not retained, so complete accounting is not retroactively asserted.']
    data['state']='live_allocation_closed';data['agent_attempts']=closure['campaign_attempts_consumed'];data['paid_attempts_reserved']=0
    data['budget'].update(scheduling_stopped=True,planned_live_attempts=0,stop_reason='New allocation closed. No additional paid execution authorized.')
    data['api_spend_usd']=None
    data['decision']=('The live evaluation produced two interpretable outcomes under the new profile. This establishes operational evidence, not skill effectiveness or adoption readiness.' if usable else 'The allocation is closed with partial or unreliable comparison evidence. Inspect the first-arm gate and retained failures before any further paid work.')
    data['summary']='This separate allocation planned campaign attempts '+str(list(ATTEMPTS.values()))+' at most; all previous allocations and unused reservation identities remain closed. Historical recovery remains 4/4; historical live results were not rescored. No skill, task, grader acceptance criteria, dependency pin, production workflow or Pages behavior changed.'
    data['allocation_budget']={'operational_usd':5,'reserve_before_second_usd':2.5,'headroom_usd':0.5,'conservative_input_usd_per_million':10,'conservative_output_usd_per_million':15,'provider_enforced_cap':False}
    data['spending_note']='Historical allocation accounting (unchanged): '+data['spending_note']+' New allocation: '+str(len(closure['reserved_slots_consumed']))+'/2 slots consumed; conservative incremental estimate USD '+str(closure['incremental_conservative_estimate_usd'] if closure['incremental_conservative_estimate_usd'] is not None else 'unknown')+'. Estimate for retained usage alone: USD '+str(data['live_allocation']['observed_usage_conservative_estimate_usd'])+'; this is not a complete or observed bill. Actual incremental bill and cumulative spending remain unknown. No new scheduling is enabled. Campaign ledger: '+str(data['agent_attempts'])+'/36; previous recovery remains 4/4.'
    data['recovery_runs'].append({'url':'https://github.com/thetechgy/agent-engineering-baseline/actions/runs/'+str(os.environ.get('GITHUB_RUN_ID')),'label':'GPT-6.1 Sol/High, rollout budget disabled','summary':'One current and one absent attempt at most; checkpointed and then closed.'})
    trial.report(out,data)
    with (out/'workflow-evidence.txt').open('a') as f:
        f.write('\nNew live allocation '+ID+'; executed commit '+str(os.environ.get('GITHUB_SHA'))+'; run '+str(os.environ.get('GITHUB_RUN_ID'))+'\n')
        for r in rows:f.write(json.dumps(r)+'\n')
        f.write(json.dumps(closure)+'\n')
    print(json.dumps({'operationally_usable':usable,'consumed':closure['reserved_slots_consumed'],'scheduling_disabled':True}))

if __name__=='__main__':main(*(Path(x).resolve() for x in sys.argv[1:3]))
