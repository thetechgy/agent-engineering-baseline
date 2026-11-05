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
    arms={v:{name:read(public/v/(name+'.json')) for name in ('attempt','manifest','boundary','installation','container-policy','effective-config','configuration-load','launch-diagnostics')} for v in ATTEMPTS}
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
            'The API credential is available to the evaluated process. Unrelated credentials, raw transcripts, submission contents and authentication files are excluded from artifacts',
            'Pinned native pricing may be unavailable; historical cumulative spending remains unknown; $5 is an operational budget with possible overshoot, not a provider-enforced cap']}
    trial.write(out/'allocation-evidence.json',evidence)
    rows=[]
    for variant,files in arms.items():
        r=files['attempt'] or {};native=(r.get('projection') or [{}])[0];handoff=r.get('handoff',{});c=handoff.get('classification',{});observed=native.get('outcome',{})
        usage=r.get('usage_and_activation',{})
        execution='completed' if r.get('execution_completed') else 'not_scheduled' if not r else 'incomplete'
        primary=(files.get('launch-diagnostics') or {}).get('primary_failure') or {}
        events=[]
        for line in primary.get('stdout','').splitlines():
            try:events.append(json.loads(line))
            except ValueError:pass
        if any(e.get('type')=='turn.failed' and e.get('error',{}).get('message')=='shared rollout token budget exhausted' for e in events):
            execution='agent_token_budget_exhausted'
        reviewed_missing=(execution=='agent_token_budget_exhausted' and observed.get('admission_reason')=='missing' and
            handoff.get('agent_observation',{}).get('artifact',{}).get('exists') is False and
            handoff.get('host_artifact',{}).get('exists') is False and handoff.get('verifier_observation',{}).get('artifact',{}).get('exists') is False)
        rows.append({'variant':variant,'attempt':ATTEMPTS[variant],
            'scheduled':bool(r),'session_completed':r.get('execution_completed'),'execution_outcome':execution,
            'task_completion_measured':True if reviewed_missing else c.get('task_completion_measured',False),'task_completed':False if reviewed_missing else c.get('task_completed'),
            'outcome':'missing_after_budget_exhaustion' if reviewed_missing else c.get('classification','not_scheduled' if not r else 'missing_evidence'),
            'handoff':handoff.get('upload_status'),'admission':observed.get('admission_reason') or observed.get('code'),
            'valid_grade':native.get('measured',False),'reference_pass':observed.get('reference_pass') if native.get('measured') else None,
            'mutants_detected':observed.get('mutants_detected') if native.get('measured') else None,
            'mutants_executed':observed.get('mutants_executed') if native.get('measured') else None,
            'skill_file_access_attempts':usage.get('skill_file_access_attempts'),
            'tool_calls':usage.get('tool_calls'),'tool_errors':usage.get('tool_error_flags'),
            'failure_cause':native.get('failure_cause'),'timing':native.get('timing'),'duration_seconds':r.get('duration_seconds'),
            'usage':usage.get('total_usage'),'conservative_estimate_usd':r.get('usage_estimate_usd'),
            'native_pricing_estimate_usd':r.get('native_pricing_estimate_usd'),'api_bill_usd':None,
            'evidence_complete':r.get('result_extraction_succeeded',False),
            'containers_removed':r.get('agent_container_removed') is True and r.get('verifier_container_removed') is True})
    usable=all(r['scheduled'] and r['session_completed'] and r['evidence_complete'] and r['containers_removed'] and
        r['outcome'] in ('graded_passed','graded_failed','missing_deliverable','rejected_output') and r['failure_cause'] is None for r in rows)
    data['live_allocation']={'id':ID,'rows':rows,'closure':closure,'operationally_usable':usable,'profile':evidence['profile']['id'],'limits':evidence['limits'],'usage_note':evidence['usage_note']}
    observed_estimates=[r['conservative_estimate_usd'] for r in rows if r['conservative_estimate_usd'] is not None]
    data['live_allocation']['observed_usage_conservative_estimate_usd']=sum(observed_estimates) if observed_estimates else None
    data['live_allocation']['reviewed_notes']=[]
    exhausted=next((r for r in rows if r['execution_outcome']=='agent_token_budget_exhausted'),None)
    if exhausted:
        u=exhausted['usage'];weighted=u['input_tokens']-u['cached_input_tokens']+5*u['output_tokens']
        notes=['Codex emitted the exact terminal error shared rollout token budget exhausted. Harbor retained NonZeroAgentExitCodeError with native failure cause unclassified; this report identifies agent token-budget exhaustion without changing the native result or reward validity.',
            'The producer, host and verifier all confirmed no submission. This is a missing deliverable at budget exhaustion, not a demonstrated collection/transfer defect. Reference correctness and mutation detection remain unmeasured.',
            'All six cumulative CLI usage categories were retained. The conservative scheduling flag also requires normal execution completion, so it remained false; it does not mean those observations are absent or zero. Complete billing remains unverified.',
            'Observed usage reconstructs '+str(weighted)+' weighted fallback units against the 30,000 limit (noncached input plus five times output), consistent with the terminal error. Provider budget units are not serialized, so the precise meter branch is unconfirmed.',
            'The absent arm was prepared and verified but never reserved or launched. Slot six is closed unused. No retry or replacement allocation is scheduled.',
            'No concrete skill weakness or causal skill benefit is established. The next necessary decision is to calibrate the supplemental token budget for the full frozen deployment and recognize this Codex-specific budget termination before considering another allocation.']
        data['live_allocation']['reviewed_notes']=notes
        evidence['reviewed_execution_classification']={'outcome':'agent_token_budget_exhausted','basis':'Native CLI turn.failed event','native_failure_cause_unchanged':True,'weighted_fallback_units_from_usage':weighted,'notes':notes}
        trial.write(out/'allocation-evidence.json',evidence)
    data['state']='live_allocation_closed';data['agent_attempts']=closure['campaign_attempts_consumed'];data['paid_attempts_reserved']=0
    data['budget'].update(scheduling_stopped=True,planned_live_attempts=0,stop_reason='New allocation closed. No additional paid execution authorized.')
    data['api_spend_usd']=None
    data['decision']=('The live evaluation produced two interpretable outcomes under the new profile. This establishes operational evidence, not skill effectiveness or adoption readiness.' if usable else 'The allocation is closed with partial or unreliable comparison evidence. Inspect the first-arm gate and retained failures before any further paid work.')
    if exhausted:data['decision']='The planned live skill comparison is not yet operationally usable: the current arm exhausted its supplemental token budget before producing the deliverable. Diagnostics now establish that cause; the absent arm was not scheduled. Calibrate the execution budget before another allocation.'
    data['summary']='This separate allocation used campaign slots five and six at most. Historical recovery remains 4/4; historical live results were not rescored. No skill, task, grader acceptance criteria, dependency pin, production workflow or Pages behavior changed.'
    data['allocation_budget']={'operational_usd':5,'reserve_before_second_usd':2.5,'headroom_usd':0.5,'conservative_input_usd_per_million':10,'conservative_output_usd_per_million':15,'provider_enforced_cap':False}
    data['spending_note']='Historical allocation accounting (unchanged): '+data['spending_note']+' New allocation: '+str(len(closure['reserved_slots_consumed']))+'/2 slots consumed; conservative incremental estimate USD '+str(closure['incremental_conservative_estimate_usd'] if closure['incremental_conservative_estimate_usd'] is not None else 'unknown')+'. Estimate for retained usage alone: USD '+str(data['live_allocation']['observed_usage_conservative_estimate_usd'])+'; this is not a complete or observed bill. Actual incremental bill and cumulative spending remain unknown. No new scheduling is enabled. Campaign ledger: '+str(data['agent_attempts'])+'/36; previous recovery remains 4/4.'
    data['recovery_runs'].append({'url':'https://github.com/thetechgy/agent-engineering-baseline/actions/runs/'+str(os.environ.get('GITHUB_RUN_ID')),'label':'GPT-6.1 Sol/High live allocation','summary':'One current and one absent attempt at most; checkpointed and then closed.'})
    trial.report(out,data)
    with (out/'workflow-evidence.txt').open('a') as f:
        f.write('\nNew live allocation '+ID+'; executed commit '+str(os.environ.get('GITHUB_SHA'))+'; run '+str(os.environ.get('GITHUB_RUN_ID'))+'\n')
        for r in rows:f.write(json.dumps(r)+'\n')
        f.write(json.dumps(closure)+'\n')
    print(json.dumps({'operationally_usable':usable,'consumed':closure['reserved_slots_consumed'],'scheduling_disabled':True}))

if __name__=='__main__':main(*(Path(x).resolve() for x in sys.argv[1:3]))
