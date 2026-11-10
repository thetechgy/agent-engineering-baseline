#!/usr/bin/env python3
"""Bounded skill campaigns through pinned Harbor and consolidated reporting."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

import evaluation_campaign_core as core
from evaluation_runtime import ROOT, read_profile
import evaluation_runtime as runtime_adapter
from evaluation_tasks import load
import evaluator_profiles as profiles
import skill_evidence as evidence
import skill_reports as reports


def purpose(task, mode):
    identity = {'boolean-contract-v1':'boolean-contract-v3', 'gh-read-v1':'gh-read-v3', 'boolean-effectiveness-v1':'boolean-effectiveness-v2'}.get(task.definition['id'], task.definition['id'])
    return 'campaign-' + identity + '-' + ('probe' if mode == 'experiment-probe' else mode)


def revision():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def no_credentials():
    core.require(not any(os.environ.get(k) for k in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','NVIDIA_API_KEY','COPILOT_GITHUB_TOKEN')), 'Credential-free campaign received credentials')


def stage(root, task, mode):
    from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks
    selected_runtime = read_profile(ROOT / task.definition['runtime_profile'])
    runtime = selected_runtime['resolved']; adapter = runtime_adapter.adapter_for(selected_runtime)
    (root / 'evidence').mkdir(exist_ok=True)
    deployed = adapter.deploy(root, task.definition)
    shutil.copyfile(root / 'deployment.json', root / 'evidence/deployment.json')
    bundle = task.bundle(root, mode)
    variants = task.definition['variants']
    core.require(len(variants) == 2 and {r['present'] for r in variants} == {True, False}
                 and all(type(r['present']) is bool for r in variants), 'Report bridge requires one present and one absent variant per comparison')
    tasks = {}; captured = []
    for variant in variants:
        present = variant['present']; arm = 'with_skill' if present else 'without_skill'
        kwargs = task.staging_options(bundle)
        native = stage_native_harbor_tasks(bundle, root / 'tasks' / variant['id'], with_skill=present, grading_mode='custom_only', **kwargs)
        for path in native:
            task.configure(path, task.cases(mode)[path.name], mode, present)
            adapter.prepare_task(path, mode, runtime)
            actual = path / 'environment/skills' / task.definition['skill']
            core.require(adapter.manifest(actual) == adapter.manifest(deployed) if present else not actual.exists(), 'Matched APM/native deployment drift')
        tasks[variant['id']] = {path.name:path for path in native}
        captured.extend(evidence.capture_custom_tasks(ROOT, task.definition['skill'], native, arm, purpose=purpose(task, mode)))
    # Every member other than the target skill must agree across variants.
    for case in task.cases(mode):
        rows = [r for r in captured if r['case_id'] == case]
        prefix = 'environment/skills/' + task.definition['skill'] + '/'
        members = [{k:v for k,v in r['members'].items() if not k.startswith(prefix) and k not in ('task.toml','tests/entry.json')} for r in rows]
        core.require(members[0] == members[1], 'Matched variant task drift')
    reports.write_json(root / 'evidence/staging.json', captured)
    from codex_pilot_descriptors import retain_descriptors
    retain_descriptors(root / 'evidence', {('with_skill' if v['present'] else 'without_skill'): list(tasks[v['id']].values()) for v in variants}, captured)
    for case in task.cases(mode):
        members = [r['members']['task.toml'] for r in captured if r['case_id'] == case]
        core.require(len(set(members)) == 1, 'Matched variant descriptor drift')
    extra = task.operator_environment(root, tasks)
    return bundle, tasks, captured, extra


def collection_parameters(task, mode):
    ids = sorted(task.cases(mode))
    return {'expected_cases':len(ids), 'expected_case_ids':ids,
            # Validate recorded job totals separately from the planned per-case population.
            'expected_trials':None if mode in ('live','experiment-probe','replay') else len(ids),
            'n_attempts':task.definition['trials'],
            'stop_on_pass':False}


def collection_run_id(task, mode, fixture=None):
    identity = purpose(task, mode)
    if mode == 'experiment-probe':
        from evaluation_campaign_protocol import SCENARIOS
        core.require(fixture in SCENARIOS, 'Unknown rehearsal report identity')
        identity += '-' + fixture
    return identity


def collect(root, task, mode, bundle, captured, rows, *, fixture=None):
    from skillevaluator.tier3.harbor.collector import collect_harbor_results
    from evaluation_campaign_core import aggregates
    # The pinned collector/report schema is paired. Variant labels remain explicit
    # in the frozen definition and ledger; this bridge maps presence only.
    aggregates(root, skill=task.definition['skill'], carrier=read_profile(ROOT / task.definition['runtime_profile'])['resolved']['agent'])
    skill = task.definition['skill']; ids = sorted(task.cases(mode)); raw = root / 'raw'
    run = raw / 'results' / skill / collection_run_id(task, mode, fixture)
    runtime = read_profile(ROOT / task.definition['runtime_profile'])['resolved']
    data = collect_harbor_results(skill, [runtime['agent']], run, root / 'jobs', **collection_parameters(task, mode),
        grading_mode='custom_only', agent_models={runtime['agent']: {'model': runtime['model'] if mode in ('probe', 'experiment-probe', 'live') else 'credential-free-oracle', 'source': task.definition['runtime_profile']}})
    config = {'grading': {'mode': 'custom_only'}, 'judge': {'enabled': False},
        'qualification': {'producer': 'retained_submission_replay' if mode == 'replay' else 'cli_probe' if mode in ('probe', 'experiment-probe') else 'live' if mode == 'live' else 'oracle', 'inference': mode == 'live'},
        'harbor': {'n_attempts': task.definition['trials'], 'stop_on_pass': False},
        'provider': {'name': runtime['provider'] if mode in ('probe', 'experiment-probe', 'live') else 'fixture', 'model': runtime['model'] if mode in ('probe', 'experiment-probe', 'live') else 'credential-free-oracle'}}
    reports.write_json(run / 'run_config.json', config)
    reports.write_json(run / 'result.json', {**data, 'skill_name': skill, 'report_status': 'complete' if all(r['state']=='completed' for r in rows) else 'incomplete', 'diagnostic_only': True, 'run_config': config})
    profile, _, _ = evidence.custom_contract(skill, purpose=purpose(task, mode))
    numeric = evidence.capture_custom_numeric_fields(ROOT, skill, root / 'jobs', root, captured, purpose=purpose(task, mode))
    reports.write_json(raw / evidence.CUSTOM_CAPTURE, evidence.custom_capture(ROOT, skill, bundle, captured,
        purpose=purpose(task, mode), attempts=task.definition['trials'], agent=runtime['agent'] if mode in ('probe', 'experiment-probe', 'live') else 'oracle',
        retrospective=reports.read_json(root/'evidence/attempt-ledger.json').get('retrospective'),
        execution_policy={'environment': profile['campaign']['environment_mode'], 'concurrency': 1, 'timeout_multiplier': 1.0, 'stop_on_pass': False}, numeric_excerpts=numeric))
    artifact = root / 'evidence'
    reports.benchmark_artifacts(ROOT, raw, skill, artifact / 'native')
    reports.public_benchmark(ROOT, artifact / 'native', skill, 'confirmation', artifact / 'public')
    core.render([artifact / 'public', artifact / 'original-public'] if mode == 'replay' else [artifact / 'public'], artifact)
    return artifact / 'public'


def run(root, task, mode, *, reference=None, fixture=None):
    from harbor.models.trial.config import TrialConfig
    from harbor.models.task.task import Task
    from qualify_evaluator_candidate import run_native
    from evaluation_campaign_protocol import stop_reason
    if mode != 'live': no_credentials()
    # Hold the future key only in this parent; staging, git, Docker observations,
    # accounting and report collection never inherit it.
    live_key = os.environ.pop('OPENAI_API_KEY', None) if mode == 'live' else None
    profiles.runtime(profiles.candidate_versions(), owning=True)
    root.mkdir(parents=True, exist_ok=False); artifact = root / 'evidence'; artifact.mkdir()
    definition = task.definition; variants = {v['id']:v for v in definition['variants']}
    rows = [{**r, 'state':'unlaunched'} for r in core.schedule(tuple(task.cases(mode)), tuple(variants), definition['trials'])]
    replaying = mode == 'replay'
    if replaying:
        core.require('retrospective' in definition and definition['attempt_limit']==1,'Unqualified replay population')
        rows = [row for row in rows if variants[row['variant']]['present']]
        core.require(len(rows)==1,'Retained source population mismatch')
    experiment = mode in ('live', 'experiment-probe')
    authorization = None
    if experiment:
        from evaluation_campaign_protocol import protocol, runtime_gate, claim
        protocol(task)
        core.require(len(rows) == protocol(task)['attempt_slots'] and reference is not None, 'Unqualified experiment population')
        if mode == 'live':
            authorization = runtime_gate(task); claim(root, authorization)
        else: core.require(fixture in __import__('evaluation_campaign_protocol').SCENARIOS, 'Unknown fixture')
    else:
        core.require(len(rows) <= definition['attempt_limit'] and definition['trials'] == 1 and 'protocol' not in definition, 'Unqualified campaign population')
    ledger = {'definition': definition, 'runtime': read_profile(ROOT / definition['runtime_profile']), 'revision': revision(),
        'mode': mode, 'inference': mode == 'live', 'fixture': fixture, 'entries': rows, 'state':'preparing', 'authorized_live_attempts':len(rows) if mode == 'live' else 0}
    if experiment:
        from evaluation_campaign_protocol import digest
        ledger.update(protocol=protocol(task), authorization=authorization,
                      preparation_digest=digest(reference / 'frozen-proposal.json'))
    if replaying:
        from codex_pilot_replay import retain_campaign_originals
        replay_profile,_,_ = evidence.custom_contract(definition['skill'],purpose=purpose(task,mode))
        ledger['retrospective'] = retain_campaign_originals(artifact,task,replay_profile)
    def save():
        target = artifact / 'attempt-ledger.json'; temporary = target.with_suffix('.new')
        with temporary.open('w') as stream:
            json.dump(ledger, stream, indent=2, allow_nan=False); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, target)
        with (artifact / 'transitions.jsonl').open('a') as stream:
            stream.write(json.dumps(ledger, allow_nan=False) + '\n'); stream.flush(); os.fsync(stream.fileno())
        directory = os.open(artifact, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
    adapter = runtime_adapter.adapter_for(ledger['runtime'])
    save(); before = adapter.resources(); bundle = None
    old = {sig:signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    def interrupted(*_args):
        raise KeyboardInterrupt
    for sig in old: signal.signal(sig, interrupted)
    try:
        held = {k:os.environ.pop(k) for k in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','NVIDIA_API_KEY') if k in os.environ}
        try:
            bundle, tasks, captured, extra = stage(root, task, mode)
            if experiment:
                from evaluation_campaign_protocol import check
                check(reference, artifact, task, qualified=mode == 'live')
        finally: os.environ.update(held)
        profile, _, _ = evidence.custom_contract(definition['skill'], purpose=purpose(task, mode))
        def attempt(row, total):
            if experiment:
                from evaluation_campaign_protocol import frozen
                core.require(reports.read_json(reference / 'frozen-proposal.json') == frozen(task), 'Source drift before launch')
            native = tasks[row['variant']][row['case']]
            present = variants[row['variant']]['present']; arm = 'with_skill' if present else 'without_skill'
            expected = next(r for r in captured if r['arm']==arm and r['case_id']==row['case'])
            core.require(Task(native).checksum == expected['task_checksum'], 'Task checksum drift before launch')
            trial_name = ('campaign-' + row['case'] + '-attempt' + str(row['trial']) + '__slot' + str(row['position']) if experiment
                          else row['case'] + '__campaign' + str(row['position']))
            if replaying: trial_name = 'retained-' + row['case'] + '-attempt1__replay'
            job = root / 'jobs' / (definition['skill'] + '-' + ledger['runtime']['resolved']['agent'] + '-' + ('with' if present else 'without'))
            trial = job / trial_name
            core.require(not trial.exists(), 'Duplicate native attempt refused')
            config = TrialConfig.model_validate({'task': {'path':str(native)}, 'trial_name':trial_name, 'trials_dir':str(job),
                'agent': adapter.agent_config(task, mode, task.cases(mode)[row['case']], ledger['runtime']['resolved'], present),
                'environment':{'import_path':profile['campaign']['environment_import']}, 'timeout_multiplier':1.0})
            path = root / 'launches' / (str(row['position']) + '.json')
            reports.write_json(path, json.loads(config.model_dump_json()))
            row.update(config_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), task_checksum=Task(native).checksum, native_trial=trial.relative_to(root).as_posix()); save()
            env = {k:v for k,v in os.environ.items() if not re.search('TOKEN|SECRET|API_KEY|PASSWORD', k) and not k.startswith(('CODEX_','AEB_','SKILL_EVAL_'))}
            env.update(extra, PYTHONPATH=str(ROOT / '.github/scripts'), PYTHON_DOTENV_DISABLED='1', HARBOR_TELEMETRY='0')
            if mode in ('probe', 'experiment-probe'):
                env['AEB_PILOT_PROBE']='1'
            if mode == 'experiment-probe':
                env.update(adapter.fixture_environment(task, fixture, row))
            if mode == 'live':
                env.update(OPENAI_API_KEY=live_key or '',
                           AEB_CAMPAIGN_APPROVAL=os.environ['AEB_CAMPAIGN_APPROVAL'],
                           AEB_CAMPAIGN_RECEIPT=os.environ['AEB_CAMPAIGN_RECEIPT'])
            started = time.monotonic()
            try:
                with path.with_suffix('.log').open('w') as log:
                    code = run_native([str(Path(sys.executable).parent / 'harbor'), 'trials','start','--config',str(path)], env=env, log=log, timeout=1200)
            finally:
                from skillevaluator.utils.redaction import redact_sensitive_text
                diagnostic = path.with_suffix('.log').read_text(errors='replace')[-32768:]
                (artifact / ('launch-' + str(row['position']) + '.log')).write_text(
                    redact_sensitive_text(diagnostic).replace(str(root), '<campaign>').replace(str(ROOT), '<checkout>'))
            row.update(returncode=code, cleanup=adapter.resources()==before, usage=adapter.usage(trial, mode),
                       elapsed_seconds=round(time.monotonic()-started, 3))
            core.require(Task(native).checksum == expected['task_checksum'], 'Task checksum drift across launch')
            native_result = reports.read_json(trial / 'result.json') if (trial / 'result.json').exists() else {}
            row['native_exception'] = (native_result.get('exception_info') or {}).get('exception_type')
            rewards = list(trial.glob('verifier/skill_evaluator_reward.json'))
            row['grading_present'] = len(rewards) == 1
            reward = reports.read_json(rewards[0]) if row['grading_present'] else {}
            row.update(state='completed', outcome=reward.get('details',{}).get('outcome',{}))
            if not experiment:
                reason = stop_reason(row)
                if row['native_exception'] or code or not row['grading_present'] or not row['cleanup']:
                    row['state'] = 'failed'; return reason
                if replaying:
                    reason = stop_reason(row)
                    if reason: row['state']='failed'; return reason
                    task.validate_result(row['outcome'],(native_result.get('verifier_result') or {}).get('rewards') or {})
                else:
                    task.check(task.cases(mode)[row['case']], present, row['outcome'], reward.get('custom_metrics',{}))
                # Qualification's invalid/unsupported controls remain expected outcomes.
                if mode == 'probe':
                    adapter.native_observation(trial, native, present, row, rows, output=task.output)
                return 'unknown_usage' if row['usage']['estimated_usd'] is None else None
            reason = stop_reason(row)
            if not reason:
                try: task.validate_result(row['outcome'], (native_result.get('verifier_result') or {}).get('rewards') or {})
                except (ValueError, KeyError, TypeError):
                    row['state'] = 'failed'; return 'missing_usable_evidence'
            if not reason:
                try:
                    adapter.native_observation(trial, native, present, row, rows, output=task.output, live=mode == 'live')
                except (ValueError, OSError, KeyError):
                    row['state'] = 'failed'; return 'security_or_identity_drift'
            # Explicit host accounting observations exercise scheduling stop rules.
            # Original native usage/grades remain unchanged and retained.
            if fixture in ('threshold', 'unknown-usage'):
                row['native_usage'] = row['usage']
                row['usage'] = dict(row['usage'], estimated_usd=5 if fixture == 'threshold' else None)
                row['observation_injection'] = fixture
                reason = stop_reason(row)
            if reason: row['state'] = 'failed'
            return reason
        core.drive(ledger, attempt, save=save, resources=adapter.resources, baseline=before, threshold=definition['stop_estimate_usd'])
    except BaseException as error:
        ledger.update(state='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed', failure=type(error).__name__,
                      stop_reason='interrupted' if isinstance(error, KeyboardInterrupt) else 'missing_usable_evidence')
        raise
    finally:
        try:
            # Keep native logs, submissions and partial grades even on interruption.
            if (root / 'jobs').exists():
                from skillevaluator.utils.redaction import redact_sensitive_text
                for path in sorted((root / 'jobs').rglob('*')):
                    if path.is_file() and not path.is_symlink() and (path.name in (*adapter.RETAINED_MEMBERS, *task.retained_members) or path.name==task.output and 'artifacts' in path.parts):
                        raw = evidence.read_bytes(path, limit=16*1024*1024).decode(errors='replace')
                        target = artifact / 'retained' / path.relative_to(root / 'jobs'); target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text(redact_sensitive_text(raw).replace(str(root), '<campaign>').replace(str(ROOT), '<checkout>'))
                if bundle is not None:
                    try: collect(root, task, mode, bundle, captured, rows, fixture=fixture)
                    except Exception as error:
                        ledger['report_failure']=type(error).__name__ + ': ' + str(error)[:500]
        finally:
            ledger['cleanup_complete']=adapter.resources()==before
            reports.write_json(artifact / 'cleanup.json', {'complete':ledger['cleanup_complete'], 'unlaunched_positions':[r['position'] for r in rows if r['state']=='unlaunched']})
            save()
            for sig, handler in old.items(): signal.signal(sig,handler)
    if experiment:
        return ledger
    core.require(ledger['state']=='completed' and ledger['cleanup_complete'] and 'report_failure' not in ledger, 'Campaign incomplete: ' + str(ledger.get('report_failure', ledger.get('stop_reason'))))
    reports.write_json(artifact / 'qualification.json', {'complete':True,'inference':False,'revision':revision(), 'profile':purpose(task,mode), 'attempts':len(rows), 'report_reproduced':True, **({'retrospective':True} if replaying else {})})
    return artifact / 'public'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['qualify','prepare','check-preparation','authenticate','live','replay'])
    parser.add_argument('--definition', type=Path, action='append', required=True)
    parser.add_argument('--mode', choices=['oracle','probe','all'], default='all')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--preparation', type=Path)
    parser.add_argument('--qualification', type=Path)
    parser.add_argument('--approval', default='')
    args = parser.parse_args()
    if args.action != 'live': no_credentials()
    root = args.output.absolute()
    core.require(root.resolve()==root and not root.exists() and not root.is_relative_to(ROOT), 'Use a new real persistent output outside checkout')
    if args.action == 'replay':
        from qualify_evaluator_candidate import native_compose_config
        native_compose_config(ROOT)
        core.require(len(args.definition)==1,'One retained source definition required')
        return run(root,load(args.definition[0].absolute()),'replay')
    if args.action != 'qualify':
        from evaluation_campaign_protocol import entry
        core.require(len(args.definition) == 1, 'One frozen experiment definition required')
        return entry(args, load(args.definition[0].absolute()), root)
    root.mkdir(parents=True)
    from qualify_evaluator_candidate import native_compose_config
    native_compose_config(ROOT)
    inputs=[]
    for path in args.definition:
        task=load(path.absolute())
        for mode in ('oracle','probe') if args.mode=='all' else (args.mode,):
            inputs.append(run(root / task.definition['id'] / mode, task, mode))
    core.render(inputs, root / 'report')
    reports.write_json(root / 'qualification.json', {'complete':True,'inference':False,'revision':revision(), 'records':len(inputs),'report_reproduced':True,'authorized_live_attempts':0})


if __name__=='__main__':
    main()
