"""Terminal and usage evidence for this pinned, single-session Codex trial."""
import json
BUDGET_ERROR='shared rollout token budget exhausted'
CATEGORIES=('input_tokens','cached_input_tokens','cache_write_input_tokens','output_tokens','reasoning_output_tokens')

def terminal_events(text):
    events=[]
    for line in text.splitlines():
        try:e=json.loads(line)
        except ValueError:continue
        if not isinstance(e,dict):continue
        kind=e.get('type')
        if kind in ('thread.started','turn.started','turn.completed','turn.failed'):
            safe={'type':kind}
            if kind=='turn.failed':safe['exact_budget_exhaustion']=e.get('error',{}).get('message')==BUDGET_ERROR
            if kind=='turn.completed':safe['usage']={k:e.get('usage',{}).get(k) for k in CATEGORIES if type(e.get('usage',{}).get(k)) is int}
            events.append(safe)
    return events

def assess(native,details,terminal,estimate):
    kinds=[e['type'] for e in terminal]
    single=kinds in ([first,*middle,last] for first in ('thread.started',) for middle in ([],['turn.started']) for last in ('turn.completed','turn.failed'))
    budget=single and terminal[-1]['type']=='turn.failed' and terminal[-1].get('exact_budget_exhaustion') is True
    exceptions=[e.get('exception_type') for e in native.get('exceptions',[])]
    completed=single and terminal[-1]['type']=='turn.completed' and native.get('failure_cause') is None and not exceptions
    recognized=budget and native.get('failure_cause')=='unclassified' and exceptions==['NonZeroAgentExitCodeError']
    outcome='completed' if completed else 'agent_token_budget_exhausted' if recognized else 'unresolved_execution_failure'
    reasons=[];session=details.get('session_evidence',{})
    if not (completed or recognized):reasons.append('unrecognized_or_missing_native_terminal')
    if estimate is None:reasons.append('missing_or_inconsistent_usage_categories')
    if session.get('rollout_files')!=1 or session.get('malformed_lines')!=0 or session.get('usage_before_terminal') is not True:
        reasons.append('session_coverage_unverified')
    if not details.get('completion_event'):reasons.append('session_terminal_missing')
    if completed:
        observed=details.get('total_usage') or {}
        if any(terminal[-1].get('usage',{}).get(k)!=observed.get(k) or k not in terminal[-1].get('usage',{}) for k in CATEGORIES):
            reasons.append('terminal_usage_does_not_match_session')
    return {'execution_assessment':{'outcome':outcome,'interpretable':completed or recognized,'native_fields_unchanged':True},
        'accounting_assessment':{'coverage':'terminal_session_observations' if not reasons else 'incomplete',
            'usable_for_scheduling':not reasons,'reasons':reasons,'observed_usage_estimate_usd':estimate,
            'billing_certainty':'unknown','provider_bill_usd':None,
            'basis':'Native terminal plus one parseable session with usage before its terminal; successful turns also require matching CLI terminal counters. Exact budget failure is a local post-usage termination, not arbitrary tool/model text. This bounds recorded session accounting, not provider billing.'}}
