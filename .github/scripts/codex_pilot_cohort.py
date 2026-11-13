"""Frozen twelve-slot cohort, using the pinned Harbor trial CLI and existing reports.

There is no resume mode. An exclusive ledger claims the dispatch before launch;
Actions authenticates preparation and rejects a second dispatch of its allocation.
"""
import hashlib
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import uuid

import codex_pilot as pilot
import codex_pilot_effectiveness as effect
from codex_pilot_contract import ROOT, PROFILE as P, configuration
from codex_pilot_descriptors import compare_descriptors
import evaluator_profiles as profiles
import skill_evidence as evidence
import skill_reports as reports

PROTOCOL = 'pester-effectiveness-v3'
FIXTURE_SCENARIOS = ('complete', 'threshold', 'unknown-usage', 'unsupported', 'infrastructure', 'cleanup', 'interruption')
SECRET_KEYS = ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'NVIDIA_API_KEY')


def revision():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def no_credentials():
    reports.require(not any(os.environ.get(k) for k in SECRET_KEYS), 'Credential-free cohort received credentials')


def allocation(value, source, artifact, dispatch):
    reports.require(bool(re.fullmatch(r'[1-9][0-9]*', str(artifact))) and
                    bool(re.fullmatch(r'[A-Za-z0-9_-]{8,40}', dispatch)), 'Invalid allocation binding')
    expected = f'cohort-{source}-{PROTOCOL}-prep{artifact}-usd15-{dispatch}'
    reports.require(value == expected and os.environ.get('GITHUB_RUN_ATTEMPT') == '1'
                    and os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch',
                    'Exact qualified cohort, preparation, one dispatch and first attempt required')


def check(reference, staging, *, qualified=True):
    """Data-only receipt consumption and full fresh identity checks; no credential delivery."""
    no_credentials()
    profiles.runtime(profiles.candidate_versions(), owning=True)
    proposal = reports.read_json(reference / 'frozen-proposal.json')
    ready = reports.read_json(reference / 'qualification.json')
    reports.require(ready.get('complete') is True and ready.get('inference') is False
                    and ready.get('revision') == proposal.get('qualified_revision') == revision()
                    and ready.get('profile') == proposal.get('profile') == effect.PROFILE_ID
                    and proposal.get('schedule') == effect.schedule()
                    and proposal.get('protocol') == reports.read_json(ROOT / effect.PROTOCOL)
                    and proposal.get('runtime') == effect.RUNTIME and proposal.get('evaluator') == profiles.CANDIDATE
                    and proposal.get('authorized_live_attempts') == 0
                    and proposal.get('source_identities') == evidence.custom_input_identities(ROOT, P['skill'], purpose=effect.PURPOSE),
                    'Wrong preparation or source/runtime/evaluator identity drift')
    reports.require(proposal.get('deployment') == reports.read_json(staging / 'workspace-profile.json'), 'Deployment drift')
    candidate = staging / 'evidence'
    reports.require(compare_descriptors(reference / 'prospective', candidate)['configurations_equal'], 'Descriptor drift')
    def members(directory):
        return {(r['arm'], r['case_id']): {k: v for k,v in r['members'].items() if k != 'task.toml'}
                for r in reports.read_json(directory / 'staging.json')}
    reports.require(members(reference / 'prospective') == members(candidate), 'Staged task member drift')
    controls = reference / 'controls'
    reports.require(reports.read_json(controls / 'cleanup.json') == {'complete': True, 'unlaunched_arms': []}
                    and reports.read_json(controls / 'readiness.json').get('complete') is True,
                    'Incomplete native grading preparation')
    reports.require(pilot.sha(controls / 'consolidated/report.html') == proposal['html_sha256']
                    and pilot.sha(reference / 'reproduced/report.html') == proposal['html_sha256'], 'Preparation report drift')
    if qualified:
        proof = reports.read_json(reference / 'scheduler-qualification.json')
        reports.require(proof.get('complete') is True and proof.get('inference') is False
                        and proof.get('revision') == revision() and proof.get('protocol') == PROTOCOL,
                        'Missing final-revision scheduler qualification')
    result = {'complete': True, 'revision': revision(), 'protocol': PROTOCOL,
              'proposal_sha256': pilot.sha(reference / 'frozen-proposal.json'), 'inference': False}
    reports.write_json(candidate / 'cohort-preparation-check.json', result)
    return result


def staged(root):
    bundle, tasks, captured = pilot.stage(root, effectiveness=True)
    effect.verify_arms(tasks, captured)
    reports.write_json(root / 'evidence/staging.json', captured)
    shutil.copyfile(root / 'workspace-profile.json', root / 'evidence/workspace-profile.json')
    return bundle, tasks, captured


def launch_config(root, row, task):
    """One pinned native trial, one task, a unique home/container/log namespace."""
    from harbor.models.trial.config import TrialConfig
    arm = 'with' if row['arm'] == 'with_skill' else 'without'
    job = root / 'jobs' / f'{P["skill"]}-codex-{arm}'
    # Pinned collector recognizes this runner-owned ordinal structure.
    name = f'cohort-{row["case"]}-attempt{row["trial"]:03}__slot{row["position"]:02}'
    config = TrialConfig.model_validate({
        'task': {'path': str(task)}, 'trial_name': name, 'trials_dir': str(job),
        'agent': {'import_path': 'codex_pilot_agent:PilotCodex', 'model_name': P['model'],
                  'kwargs': {'version': P['cli'], 'reasoning_effort': P['reasoning_effort']}},
        'environment': {'import_path': 'codex_pilot_environment:PilotEnvironment'},
        'timeout_multiplier': 1.0})
    target = root / 'launches' / f'{row["position"]:02}.json'
    reports.write_json(target, json.loads(config.model_dump_json()))
    return target, job / name


def stop_reason(row, usage, clean, *, code, audits, grades):
    """Fail closed on operational uncertainty, preserving measured task failures."""
    if not clean or len(audits) != 1 or audits[0].get('cleanup') != 'complete': return 'cleanup_failure'
    if code or not audits[0].get('boundary_after'): return 'execution_infrastructure_failure'
    if len(grades) != 1: return 'missing_grading_evidence'
    outcome = grades[0].get('classification')
    if outcome == 'unsupported': return 'unsupported_grading'
    if outcome in ('infrastructure_error', 'timeout'): return 'verifier_failure'
    if outcome not in ('passed', 'failed'): return 'missing_usable_evidence'
    if len(usage) != 1 or usage[0].get('estimated_usd') is None: return 'unknown_usage'
    return None


def boundary_stop(audits, finals):
    """Missing/malformed trusted observations are gaps, not observed drift.

    All three observations must identify the same dedicated containers, images
    and policy. A failed task never exempts this independent admission check.
    """
    if len(audits) != 1 or len(finals) != 1 or not isinstance(audits[0], dict):
        return 'missing_security_evidence'
    observations = [audits[0].get('boundary_before'), audits[0].get('boundary_after'), finals[0]]
    fields = ('agent_id', 'controller_id', 'agent_image', 'controller_image', 'policy_sha256')
    for observation in observations:
        if not isinstance(observation, dict):
            return 'missing_security_evidence'
        for field in fields:
            value = observation.get(field)
            if field.endswith('_image') and isinstance(value, str):
                value = value.removeprefix('sha256:')
            if not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{64}', value) is None:
                return 'missing_security_evidence'
    if any(any(value[field] != observations[0][field] for field in fields) for value in observations[1:]):
        return 'security_or_identity_drift'
    return None


from evaluation_campaign_core import accounting, drive


def aggregates(root, *, skill=P['skill'], carrier='codex'):
    from evaluation_campaign_core import aggregates as shared_aggregates
    return shared_aggregates(root, skill=skill, carrier=carrier)


def claim_dispatch(root, receipt):
    """A local exclusive claim complements Actions history, including same-job repeats."""
    temporary = Path(os.environ['RUNNER_TEMP'])
    reports.require(temporary.is_absolute() and temporary.resolve() == temporary
                    and root == temporary / 'cohort-live' and os.environ.get('GITHUB_ACTIONS') == 'true',
                    'Live cohort requires its fixed Actions output directory')
    target = temporary / ('cohort-claim-' + hashlib.sha256(receipt['allocation'].encode()).hexdigest() + '.json')
    with target.open('x') as stream:
        json.dump(receipt, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def execute(root, reference, *, fixture=None, approval='', receipt=None):
    if fixture is not None:
        no_credentials(); reports.require(fixture in FIXTURE_SCENARIOS, 'Unknown fixture scenario')
    else:
        reports.require(not any(k.startswith('AEB_') for k in os.environ) and not os.environ.get('OPENAI_BASE_URL'), 'Probe/provider overrides refused in live mode')
        reports.require(receipt is not None, 'Authenticated dispatch receipt required')
        allocation(approval, revision(), receipt['artifact'], receipt['dispatch'])
        reports.require(receipt.get('run_id') == os.environ.get('GITHUB_RUN_ID') and receipt.get('revision') == revision()
                        and receipt.get('allocation') == approval and receipt.get('first_dispatch') is True
                        and receipt.get('protocol') == PROTOCOL and receipt.get('authentication') == 'github-api-producer-and-digest', 'Stale dispatch receipt')
    root.mkdir(parents=True, exist_ok=False)
    if fixture is None: claim_dispatch(root, receipt)
    artifact = root / 'evidence'; artifact.mkdir()
    # The caller's exclusive output directory and claim survive even preflight failure.
    rows = [{**r, 'state': 'unlaunched'} for r in effect.schedule()]
    ledger = {'protocol': PROTOCOL, 'revision': revision(), 'fixture': fixture, 'inference': fixture is None,
              'allocation': approval, 'dispatch': receipt, 'state': 'preparing', 'entries': rows}
    def save():
        target = artifact / 'attempt-ledger.json'; scratch = target.with_suffix('.new')
        with scratch.open('w') as stream:
            json.dump(ledger, stream, indent=2, allow_nan=False); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(scratch, target)
    save()
    bundle = None; before = None
    old_handlers = {}
    def interrupted(_signum, _frame): raise KeyboardInterrupt('Cohort interrupted; no continuation')
    for sig in (signal.SIGTERM, signal.SIGINT): old_handlers[sig] = signal.signal(sig, interrupted)
    try:
        # Preflight deliberately sees no provider credentials. Credentials remain
        # only in the parent until the already-verified attempt subprocess launch.
        held = {k: os.environ.pop(k) for k in SECRET_KEYS if k in os.environ}
        try:
            bundle, tasks, captured = staged(root)
            check(reference, root, qualified=fixture is None)
        finally:
            os.environ.update(held)
        primary = [r for r in captured if r['case_id'] in effect.PRIMARY_CASES]
        dataset = reports.read_json(bundle / 'evals/evals.json')
        dataset['evals'] = [r for r in dataset['evals'] if r['id'] in effect.PRIMARY_CASES]
        reports.write_json(bundle / 'evals/evals.json', dataset)
        before = pilot.resources(); stages = []
        reports.write_json(artifact / 'command-stages.json', stages)
        ledger['state'] = 'running'; save()
        def attempt(row, total):
            # Every launch verifies immutable source, runtime and staged task bytes.
            profiles.runtime(profiles.candidate_versions(), owning=True)
            reports.require(evidence.custom_input_identities(ROOT, P['skill'], purpose=effect.PURPOSE) ==
                            reports.read_json(reference / 'frozen-proposal.json')['source_identities'], 'Source identity drift before launch')
            task = next(t for t in tasks[row['arm']] if t.name == row['case'])
            from harbor.models.task.task import Task
            expected = next(r for r in primary if r['arm'] == row['arm'] and r['case_id'] == row['case'])
            reports.require(Task(task).checksum == expected['task_checksum'], 'Task identity drift before launch')
            config, trial = launch_config(root, row, task)
            reports.require(not trial.exists(), 'Duplicate attempt launch refused')
            row.update(state='launching', task_checksum=expected['task_checksum'],
                       config_sha256=pilot.sha(config), native_trial=trial.relative_to(root).as_posix(), estimated_usd_before=total)
            save()  # Durable before the subprocess can obtain credentials.
            environment = {k:v for k,v in os.environ.items() if not k.startswith(('CODEX_', 'ANTHROPIC_', 'NVIDIA_', 'SKILL_EVAL_', 'AEB_'))
                           and k not in ('GH_TOKEN', 'GITHUB_TOKEN', 'OPENAI_BASE_URL')}
            environment.update(PYTHONPATH=str(ROOT / '.github/scripts'), PYTHON_DOTENV_DISABLED='1', HARBOR_TELEMETRY='0')
            if fixture:
                name = row['case'] + ('-external' if row['case']=='pester-003' else '-explicit')
                if row['position'] % 3 == 0: name = row['case'] + '-weak'
                if fixture == 'unsupported': name = row['case'] + '-unsupported'
                environment.update(AEB_PILOT_PROBE='1', AEB_COHORT_FIXTURE=name,
                    AEB_PILOT_SCENARIO='command-failure' if fixture == 'infrastructure' else 'interruption' if fixture=='interruption' else 'success')
            from qualify_evaluator_candidate import run_native
            from skillevaluator.utils.redaction import redact_sensitive_text
            log_path = root / 'launches' / f'{row["position"]:02}.log'
            with log_path.open('w') as log:
                code = run_native([str(Path(sys.executable).parent / 'harbor'), 'trials', 'start', '--config', str(config)],
                                  env=environment, log=log, timeout=1200)
            diagnostic = redact_sensitive_text(log_path.read_text(errors='replace')[-32768:])
            (artifact / f'diagnostics-{row["position"]:02}.txt').write_text(diagnostic.replace(str(root), '<cohort>').replace(str(ROOT), '<checkout>'))
            # Preserve all current raw evidence through the established redaction/retention path.
            usage = pilot.retain(root, artifact, probe=fixture is not None)
            audits = [reports.read_json(p) for p in trial.rglob('pilot-runtime.json')]
            grades = [reports.read_json(p).get('details', {}).get('outcome', {}) for p in trial.glob('verifier/skill_evaluator_reward.json')]
            current = [u for u in usage if u['trial'] == trial.name]
            clean = pilot.resources() == before
            if fixture in ('threshold', 'unknown-usage', 'cleanup'):
                # Explicit host-side stop-observation faults, after the actual CLI,
                # native verifier and disposal. Never modify original evidence.
                row['fixture_observation_injection'] = fixture
                if fixture == 'threshold' and current: current = [{**current[0], 'estimated_usd': 10.01}]
                if fixture == 'unknown-usage': current = [{**u, 'estimated_usd': None} for u in current]
                if fixture == 'cleanup': clean = False
            row.update(state='completed', returncode=code, usage=current[0] if len(current)==1 else None,
                       agent_returncode=audits[0].get('returncode') if len(audits)==1 else None,
                       grade=grades[0] if len(grades)==1 else None, cleanup=clean)
            if fixture: row['inference'] = False
            native = reports.read_json(trial / 'result.json')
            exception = (native.get('exception_info') or {}).get('exception_type')
            row['native_exception'] = exception
            row['agent_failure'] = exception if exception and (exception in ('AgentTimeoutError', 'NonZeroAgentExitCodeError') or row['agent_returncode'] not in (None, 0)) else None
            row['verifier_failure'] = exception if exception and not row['agent_failure'] and (native.get('verifier') or {}).get('started_at') else None
            row['infrastructure_failure'] = exception if exception and not (row['agent_failure'] or row['verifier_failure']) else None
            reason = stop_reason(row, current, clean, code=code, audits=audits, grades=grades)
            if exception and reason != 'cleanup_failure': reason = 'execution_infrastructure_failure' if not row['agent_failure'] or fixture in ('infrastructure','interruption') else reason
            if reason:
                row['state'] = 'interrupted' if fixture == 'interruption' else 'failed'
                ledger['stop_reason'] = reason
            # Keep the operational cause even when independent security admission
            # also stops the cohort. Missing evidence must never imply observed drift.
            row['execution_stop_reason'] = reason
            finals = [reports.read_json(p) for p in trial.rglob('pilot-final-policy.json')]
            security = boundary_stop(audits, finals)
            if len(audits) == 1 and isinstance(audits[0], dict):
                audit = audits[0]
                row['secondary_failures'] = {key: audit[key] for key in (
                    'boundary_observation_exception', 'boundary_observation_unavailable',
                    'collection_or_cleanup_exception') if key in audit}
                before_audit = audit.get('boundary_before')
                agent_id = before_audit.get('agent_id') if isinstance(before_audit, dict) else None
                row['agent_id'] = agent_id
                if agent_id and any(previous is not row and previous.get('agent_id')==agent_id for previous in rows):
                    security = 'environment_reuse'
                expected_config = configuration('http://127.0.0.1:8765/v1' if fixture else None)
                if (audit.get('prompt_sha256') != hashlib.sha256((task / 'instruction.md').read_bytes()).hexdigest()
                    or audit.get('effective_config') != expected_config or audit.get('skill_deployed') != (row['arm']=='with_skill')):
                    security = 'security_or_identity_drift'
            if security:
                row['security_failure'] = security
                ledger['stop_reason'] = security; row['state'] = 'failed'
            stages.append({'arm': row['arm'], 'case': row['case'], 'trial': row['trial'], 'returncode': code, 'status': row['state']})
            reports.write_json(artifact / 'command-stages.json', stages)
            save()
            reports.require(Task(task).checksum == expected['task_checksum'], 'Task identity drift across execution')
            return ledger.get('stop_reason')
        drive(ledger, attempt, save=save, resources=pilot.resources, baseline=before, threshold=10)
        ledger['state'] = 'stopped' if ledger.get('stop_reason') else 'completed'
    except BaseException as error:
        ledger.update(state='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed', failure=type(error).__name__)
        for row in rows:
            if row['state'] == 'launching': row['state'] = 'interrupted' if isinstance(error, KeyboardInterrupt) else 'failed'
        raise
    finally:
        save()
        if bundle is not None and (artifact / 'command-stages.json').exists():
            try:
                pilot.retain(root, artifact, probe=fixture is not None)
            except Exception as error:
                reports.write_json(artifact / 'retention-failure.json', {'error': type(error).__name__})
                ledger['retention_failure'] = type(error).__name__
            try:
                aggregates(root)
                pilot.collect(root, artifact, bundle, primary, effectiveness=True, probe=fixture is not None, cohort=True)
            except Exception as error:
                reports.write_json(artifact / 'collection-failure.json', {'error': type(error).__name__})
                ledger['report_failure'] = type(error).__name__
        clean = before is None or pilot.resources() == before
        reports.write_json(artifact / 'cleanup.json', {'complete': clean, 'unlaunched_positions': [r['position'] for r in rows if r['state']=='unlaunched']})
        ledger['cleanup_complete'] = clean; save()
        for sig, handler in old_handlers.items(): signal.signal(sig, handler)
    return ledger


def qualify(root, reference):
    """Real CLI/container executions, with deterministic non-forwarding responses."""
    no_credentials()
    root.mkdir(parents=True, exist_ok=False)
    results = {}
    expected = {'threshold': 'estimated_usage_threshold', 'unknown-usage': 'unknown_usage', 'unsupported': 'unsupported_grading',
                'infrastructure': 'execution_infrastructure_failure', 'cleanup': 'cleanup_failure', 'interruption': 'execution_infrastructure_failure'}
    for scenario in FIXTURE_SCENARIOS:
        result = execute(root / scenario, reference, fixture=scenario)
        launched = [r for r in result['entries'] if r['state'] != 'unlaunched']
        reports.require('report_failure' not in result and 'retention_failure' not in result and result['cleanup_complete'], 'Fixture report/cleanup incomplete: ' + scenario)
        if scenario == 'complete':
            reports.require(result['state']=='completed' and len(launched)==12 and
                            [{k:r[k] for k in ('position','case','arm','trial')} for r in launched]==effect.schedule(), 'Wrong cohort order or population')
            reports.require(all(r['grade']['classification']==('failed' if r['position']%3==0 else 'passed') for r in launched), 'Measured task failure lost')
            reports.require(len(reports.read_json(root / scenario / 'evidence/submissions.json')) == 12
                            and len(list((root / scenario / 'jobs').rglob('pilot-runtime.json'))) == 12, 'Missing evidence or extra native launches')
        else:
            # Threshold is checked immediately before the next launch.
            reports.require(len(launched)==1 and result.get('stop_reason')==expected[scenario], 'Wrong stop/extra launch: ' + scenario)
        if scenario in ('infrastructure', 'interruption'):
            evidence_root = root / scenario / 'evidence'
            audits = reports.read_json(evidence_root / 'runtime-audits.json')
            finals = reports.read_json(evidence_root / 'final-policy-audits.json')
            reports.require(boundary_stop(audits, finals) is None, 'Failure-path independent audit incomplete')
            reports.require(launched[0]['native_exception'] == 'RuntimeError'
                            and audits[0]['returncode'] != 0 and audits[0]['execution_exception'] == 'RuntimeError'
                            and launched[0]['execution_stop_reason'] == expected[scenario], 'Primary execution failure lost')
            public = list((evidence_root / 'public').rglob('public-report.json'))
            observations = [o for path in public for o in reports.read_json(path).get('observations', [])]
            reports.require(len(observations) == 1 and all(m['status'] == 'unavailable' and m['value'] is None
                            for m in observations[0]['custom']['measurements']), 'Failed execution became task quality')
        results[scenario] = {'state': result['state'], 'launched': len(launched), 'stop_reason': result.get('stop_reason')}
    value = {'complete': True, 'inference': False, 'protocol': PROTOCOL, 'revision': revision(), 'scenarios': results,
             'limits': ['non-forwarding fixtures, not provider authentication or effectiveness',
                       'threshold, unknown usage and cleanup include explicit host observation injections']}
    reports.write_json(root / 'scheduler-qualification.json', value)
    shutil.copyfile(root / 'scheduler-qualification.json', reference / 'scheduler-qualification.json')


def entry(args):
    reports.require(args.preparation is not None, 'Prospective authenticated preparation required')
    if args.action == 'check-cohort':
        no_credentials(); args.output.mkdir(parents=True, exist_ok=False); staged(args.output)
        check(args.preparation, args.output)
    elif args.action == 'qualify-cohort':
        from qualify_evaluator_candidate import native_compose_config
        native_compose_config(ROOT)
        qualify(args.output, args.preparation)
    else:
        from qualify_evaluator_candidate import native_compose_config
        native_compose_config(ROOT)
        receipt = reports.read_json(args.preparation / 'dispatch-authentication.json')
        result = execute(args.output, args.preparation, approval=args.approval, receipt=receipt)
        reports.require(result['state']=='completed' and 'report_failure' not in result and result['cleanup_complete'],
                        'Cohort stopped or evidence incomplete; no continuation authorized')
