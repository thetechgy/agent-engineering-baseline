"""Versioned campaign preparation, data-only authorization and shared stop policy.

This module never launches a task or owns a grader/runtime. The campaign entry
point owns execution. Reuse the existing bounded artifact transport and GitHub API.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from evaluation_campaign_core import require, schedule
from evaluation_runtime import ROOT, read_profile
import evaluator_profiles as profiles
import skill_evidence as evidence
import skill_reports as reports

REPO = 'thetechgy/agent-engineering-baseline'
WORKFLOW = '.github/workflows/evaluation-campaign.yml'
SCENARIOS = ('complete', 'interruption', 'missing-evidence', 'unsupported-runtime',
             'invalid', 'unsupported-grading', 'threshold', 'unknown-usage')


def revision():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True,
        env={k:v for k,v in os.environ.items() if not re.search('TOKEN|SECRET|API_KEY|PASSWORD',k)}).strip()


def digest(path):
    return evidence.digest_bytes(evidence.read_bytes(path))


def protocol(task):
    require('protocol' in task.definition, 'Qualification definition cannot authorize inference')
    value = reports.read_json(ROOT / task.definition['protocol'])
    rows = schedule(tuple(task.cases('live')), tuple(v['id'] for v in task.definition['variants']), task.definition['trials'])
    require(value['definition'] == task.member and value['id'] == task.definition['id']
            and value['authorized_live_attempts'] == task.definition['authorized_live_attempts'] == 0
            and value['version'] == 1 and value['attempt_slots'] == len(rows) == task.definition['attempt_limit']
            and value['trials_per_arm'] == task.definition['trials']
            and value['automatic_retries'] == value['replacements'] == 0 and value['concurrency'] == 1
            and value['budget']['stop_estimate_usd'] == task.definition['stop_estimate_usd'], 'Unqualified live protocol')
    runtime = read_profile(ROOT / task.definition['runtime_profile'])
    require(runtime['profile']['capabilities'] == ['non-forwarding-cli-probe', 'exact-authorized-live']
            and runtime['profile']['inference_enabled'] is False
            and value['agent_seconds'] == runtime['resolved']['agent_seconds']
            and value['budget']['prices_per_million'] == runtime['resolved']['prices_per_million'], 'Protocol/runtime drift')
    return value


def frozen(task):
    from evaluation_campaign import purpose
    return {'revision': revision(), 'protocol': protocol(task), 'protocol_digest': digest(ROOT / task.definition['protocol']),
            'definition': task.definition, 'runtime': read_profile(ROOT / task.definition['runtime_profile']),
            'evaluator': profiles.CANDIDATE, 'authorized_live_attempts': 0,
            'schedule': schedule(tuple(task.cases('live')), tuple(v['id'] for v in task.definition['variants']), task.definition['trials']),
            'source_identities': {mode: evidence.custom_input_identities(ROOT, task.definition['skill'], purpose=purpose(task, mode))
                                  for mode in ('live', 'experiment-probe')}}


def check(reference, staging, task, *, qualified=True):
    """Exact fresh staging comparison, before any credential handoff."""
    from codex_pilot_descriptors import compare_descriptors
    profiles.runtime(profiles.candidate_versions(), owning=True)
    expected = frozen(task)
    proposal = reports.read_json(reference / 'frozen-proposal.json')
    require(proposal == expected, 'Preparation/source/protocol/runtime drift')
    if qualified:
        ready = reports.read_json(reference / 'preparation.json')
        require(ready == {'complete': True, 'inference': False, 'revision': revision(),
                          'protocol_digest': expected['protocol_digest'], 'authorized_live_attempts': 0}, 'Unqualified preparation')
        proof = reports.read_json(reference / 'scheduler-qualification.json')
        require(proof.get('complete') is True and proof.get('revision') == revision()
                and proof.get('protocol_digest') == expected['protocol_digest'] and proof.get('inference') is False
                and set(proof.get('scenarios',{})) == set(SCENARIOS), 'Unqualified scheduler')
        from skill_report import generate
        inputs = [reference.parent / 'scenarios' / name / 'evidence/public' for name in SCENARIOS]
        generate(inputs, reference / 'analysis/analysis.json', staging / 'report-reproduction')
        require(digest(staging / 'report-reproduction/report.html') == digest(reference / 'consolidated/report.html')
                == digest(reference / 'reproduced/report.html'), 'Consumed public-only report reproduction failed')
    require(reports.read_json(reference / 'deployment.json') == reports.read_json(staging / 'deployment.json'), 'Deployment drift')
    require(reports.read_json(reference / 'staging.json') == reports.read_json(staging / 'staging.json'), 'Complete staged-member drift')
    result = compare_descriptors(reference, staging)
    reports.write_json(staging / 'preparation-check.json', dict(result, complete=True, revision=revision(), inference=False))
    return result


def stop_reason(row):
    if not row.get('cleanup'): return 'cleanup_failure'
    if row.get('returncode'): return 'execution_infrastructure_failure'
    if row.get('native_exception'):
        from evaluation_runtime import failure_reason
        return failure_reason(row['native_exception'])
    if not row.get('grading_present'): return 'missing_grading_evidence'
    classification = row.get('outcome', {}).get('classification')
    if classification == 'unsupported': return 'unsupported_grading'
    if classification in ('timeout', 'infrastructure_error'): return 'verifier_failure'
    if classification not in ('passed', 'failed'): return 'missing_usable_evidence'
    cost = row.get('usage', {}).get('estimated_usd')
    from evaluation_campaign_core import accounting
    try: accounting([{'state':'completed', 'usage':{'estimated_usd':cost}}])
    except ValueError: return 'unknown_usage'
    return None


def allocation(value, task):
    p = protocol(task)
    pattern = f'campaign-{revision()}-{p["id"]}-prep([1-9][0-9]*)-usd{p['budget']['planning_allocation_usd']}-([A-Za-z0-9_-]{{8,40}})'
    match = re.fullmatch(pattern, value)
    require(match is not None and os.environ.get('GITHUB_RUN_ATTEMPT') == '1'
            and os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch', 'Exact allocation and first dispatch attempt required')
    return match.groups()


def validate_receipt(receipt, approval, task):
    artifact, nonce = allocation(approval, task)
    require(receipt == {**receipt, 'artifact': artifact, 'dispatch': nonce, 'allocation': approval,
                       'revision': revision(), 'protocol_digest': digest(ROOT / task.definition['protocol']),
                       'run_id': os.environ.get('GITHUB_RUN_ID'), 'first_dispatch': True,
                       'authentication': 'github-api-producer-and-digest'}
            and re.fullmatch('sha256:[0-9a-f]{64}', receipt.get('artifact_digest', '')) is not None,
            'Stale or unauthenticated campaign receipt')


def runtime_gate(task):
    require(os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('GITHUB_REPOSITORY') == REPO
            and os.environ.get('GITHUB_JOB') == 'live'
            and not os.environ.get('OPENAI_BASE_URL')
            and not any(k.startswith('AEB_') and k not in ('AEB_CAMPAIGN_APPROVAL', 'AEB_CAMPAIGN_RECEIPT') for k in os.environ),
            'Live runtime requires protected workflow; overrides refused')
    receipt = reports.read_json(Path(os.environ['AEB_CAMPAIGN_RECEIPT']))
    validate_receipt(receipt, os.environ['AEB_CAMPAIGN_APPROVAL'], task)
    return receipt


def claim(root, receipt):
    temporary = Path(os.environ['RUNNER_TEMP'])
    require(temporary.is_absolute() and temporary.resolve() == temporary and root == temporary / 'campaign-live', 'Fixed live output required')
    target = temporary / ('campaign-claim-' + hashlib.sha256(receipt['allocation'].encode()).hexdigest() + '.json')
    with target.open('x') as stream:
        json.dump(receipt, stream); stream.flush(); os.fsync(stream.fileno())


def authenticate(output, approval, task):
    from codex_pilot_dispatch import api, extract, REPO_ID, LIMIT
    from evaluation_campaign import no_credentials
    no_credentials()
    require(os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('GITHUB_REPOSITORY') == REPO, 'Reviewed Actions workflow required')
    artifact_id, nonce = allocation(approval, task)
    current = api('actions/runs/' + os.environ['GITHUB_RUN_ID'])
    require(current['head_sha'] == revision() and current['path'] == WORKFLOW
            and current['repository']['id'] == REPO_ID, 'Dispatch source mismatch')
    runs=[]
    for page in range(1,101):
        batch=api(f'actions/workflows/evaluation-campaign.yml/runs?event=workflow_dispatch&per_page=100&page={page}')['workflow_runs']
        runs.extend(batch)
        if len(batch)<100: break
    else: raise ValueError('Incomplete dispatch history')
    first_dispatch(runs, approval, os.environ['GITHUB_RUN_ID'])
    artifact=api('actions/artifacts/'+artifact_id); producer=api('actions/runs/'+str(artifact['workflow_run']['id']))
    authenticate_metadata(artifact, producer, revision(), REPO_ID, LIMIT)
    output.mkdir(parents=True,exist_ok=False)
    archive=output/'preparation.zip'
    with archive.open('xb') as stream:
        subprocess.run(['gh','api',f'repos/{REPO}/actions/artifacts/{artifact_id}/zip'],stdout=stream,check=True,timeout=120)
    extract(archive,output/'downloaded',artifact)
    reference=output/'downloaded/preparation/evidence'
    require(reports.read_json(reference/'frozen-proposal.json')==frozen(task), 'Unqualified source artifact')
    ready=reports.read_json(reference/'preparation.json')
    require(ready.get('complete') is True and ready.get('revision')==revision() and ready.get('inference') is False
            and ready.get('protocol_digest')==digest(ROOT/task.definition['protocol']), 'Incomplete preparation')
    receipt={'artifact':artifact_id,'artifact_digest':artifact['digest'],'producer_run':producer['id'],'revision':revision(),
             'protocol_digest':digest(ROOT/task.definition['protocol']),'dispatch':nonce,'run_id':os.environ['GITHUB_RUN_ID'],
             'allocation':approval,'first_dispatch':True,'authentication':'github-api-producer-and-digest'}
    reports.write_json(reference/'dispatch-authentication.json',receipt)
    reports.write_json(output/'artifact.json',artifact); reports.write_json(output/'producer-run.json',producer)
    return reference


def first_dispatch(runs, approval, run_id):
    matching=[r for r in runs if r.get('display_title')=='Evaluation campaign '+approval]
    require(matching and min(r['id'] for r in matching)==int(run_id), 'Allocation already claimed')
    current=next((r for r in matching if r['id']==int(run_id)),{})
    require(current.get('run_attempt')==1 and current.get('event')=='workflow_dispatch', 'Workflow replay refused')


def authenticate_metadata(artifact, run, source, repo_id, limit):
    origin=artifact.get('workflow_run',{})
    require(run.get('repository',{}).get('id')==repo_id and run['repository']['full_name']==REPO
            and run.get('head_repository',{}).get('id')==repo_id
            and origin.get('repository_id')==origin.get('head_repository_id')==repo_id
            and origin.get('id')==run.get('id') and origin.get('head_sha')==run.get('head_sha')==source
            and run.get('path')==WORKFLOW and run.get('event') in ('pull_request','workflow_dispatch')
            and run.get('status')=='completed' and run.get('conclusion')=='success'
            and artifact.get('name')==f'reusable-evaluation-{run["run_attempt"]}' and artifact.get('expired') is False
            and type(artifact.get('size_in_bytes')) is int and 0<artifact['size_in_bytes']<=limit
            and re.fullmatch('sha256:[0-9a-f]{64}',artifact.get('digest','')), 'Preparation producer authentication failed')


def prepare(root, task, qualification):
    """Qualify the actual experiment orchestration through the non-forwarding CLI."""
    from evaluation_campaign import run, stage, revision, no_credentials
    no_credentials(); protocol(task)
    require(qualification is not None, 'Native control qualification required')
    ready=reports.read_json(qualification/'qualification.json')
    require(ready.get('complete') is True and ready.get('inference') is False and ready.get('revision')==revision()
            and ready.get('records')==4, 'Both native task families must qualify at this revision')
    root.mkdir(parents=True,exist_ok=False); retained=root/'evidence'; retained.mkdir()
    reports.write_json(retained/'frozen-proposal.json',frozen(task))
    stage(root, task, 'live') # Preparation only: no inference path is invoked.
    reports.write_json(retained/'control-qualification.json',ready)
    expected={'interruption':'execution_infrastructure_failure', 'missing-evidence':'missing_native_observation',
              'unsupported-runtime':'unsupported_runtime_protocol', 'invalid':'missing_usable_evidence',
              'unsupported-grading':'unsupported_grading', 'threshold':'estimated_usage_threshold','unknown-usage':'unknown_usage'}
    summaries={}; inputs=[]
    for scenario in SCENARIOS:
        result=run(root/'scenarios'/scenario,task,'experiment-probe',reference=retained,fixture=scenario)
        launched=[r for r in result['entries'] if r['state']!='unlaunched']
        require(result['cleanup_complete'] and 'report_failure' not in result, 'Scenario cleanup/report incomplete: '+scenario)
        if scenario=='complete':
            require(result['state']=='completed' and len(launched)==protocol(task)['attempt_slots'], 'Wrong experiment population')
            for row in launched:
                task.check(task.fixture_control(scenario,row),
                           next(v['present'] for v in task.definition['variants'] if v['id'] == row['variant']), row['outcome'], {})
            require(len({r['agent_id'] for r in launched})==len(launched) and all('submission' in r for r in launched), 'Missing submissions or reused environment')
        else:
            require(len(launched)==1 and result.get('stop_reason')==expected[scenario], 'Extra launch or wrong stop: '+scenario)
        summaries[scenario]={'state':result['state'],'launched':len(launched),'stop_reason':result.get('stop_reason')}
        inputs.append(root/'scenarios'/scenario/'evidence/public')
    from evaluation_campaign_core import render
    render(inputs, retained)
    reports.write_json(retained/'scheduler-qualification.json',{'complete':True,'revision':revision(),'inference':False,
        'protocol_digest':digest(ROOT/task.definition['protocol']),'scenarios':summaries,
        'limits':['non-forwarding CLI responses do not establish authentication or arbitrary live event compatibility',
                  'missing/unsupported observations are declared adapter injections after real CLI execution',
                  'threshold/unknown usage are declared host injections; native records remain intact']})
    reports.write_json(retained/'preparation.json',{'complete':True,'inference':False,'revision':revision(),
        'protocol_digest':digest(ROOT/task.definition['protocol']),'authorized_live_attempts':0})


def entry(args, task, root):
    from evaluation_campaign import stage, run, no_credentials
    if args.action=='authenticate':
        return authenticate(root,args.approval,task)
    if args.action=='check-preparation':
        no_credentials(); require(args.preparation is not None,'Preparation required')
        root.mkdir(parents=True,exist_ok=False); stage(root,task,'live')
        return check(args.preparation,root/'evidence',task)
    from qualify_evaluator_candidate import native_compose_config
    if args.action == 'live': runtime_gate(task)
    held = {k:os.environ.pop(k) for k in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','NVIDIA_API_KEY') if k in os.environ}
    try: native_compose_config(ROOT)
    finally: os.environ.update(held)
    if args.action=='prepare':
        return prepare(root,task,args.qualification)
    require(args.action=='live' and args.preparation is not None,'Approved preparation required')
    require(args.approval==os.environ.get('AEB_CAMPAIGN_APPROVAL'),'Approval input mismatch')
    runtime_gate(task)
    result=run(root,task,'live',reference=args.preparation)
    require(result['state']=='completed' and result['cleanup_complete'] and 'report_failure' not in result,
            'Experiment stopped; no continuation or replacement authorized')
    return result
