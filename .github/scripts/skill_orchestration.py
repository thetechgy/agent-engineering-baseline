#!/usr/bin/env python3
"""Inference-free planning and authenticated dispatch of the existing benchmark.

Actions artifacts and run metadata are operational records, not evaluation evidence.
Only dispatch() writes remote state; it issues one POST per already-uploaded intent.
"""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import skill_pages as pages
import skill_reports as reports

REPOSITORY = pages.REPOSITORY
WORKFLOW = '.github/workflows/orchestrate-skill-evaluations.yml'
BENCHMARK = pages.WORKFLOWS['benchmark']
POLICY_FILE = '.github/evals/orchestration.json'
SUITES = ('podman', 'gh', 'powershell-pester-6')
RUNTIME_FILES = ('.github/workflows/benchmark-skills.yml', '.github/scripts/setup-compose.sh',
                 '.github/scripts/setup-skillevaluator.sh', '.github/scripts/skill_reports.py',
                 '.github/patches/')
SUITE_FILES = {'podman': ('.apm/skills/podman/',),
               'gh': ('.github/evals/gh/evals/', '.github/scripts/gh_evaluations.py',
                      '.github/evals/custom-metrics.json', '.github/scripts/skill_evidence.py'),
               'powershell-pester-6': ('.apm/skills/powershell-pester-6/',
                                      '.github/evals/powershell-pester-6/evals/',
                                      '.github/evals/powershell-pester-6/support/',
                                      '.github/scripts/pester_evaluations.py',
                                      '.github/evals/custom-metrics.json', '.github/scripts/skill_evidence.py')}
TITLE = re.compile(r'Benchmark (podman|gh|powershell-pester-6) \((standard|confirmation)\)(?: \[([0-9a-f]{64})\])?')
require = reports.require


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def timestamp(value):
    require(type(value) is str and re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ', value), 'Invalid UTC timestamp')
    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)


def now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def git(workspace, *args):
    result = subprocess.run(['git', '-C', str(workspace), *args], capture_output=True, timeout=60, check=False)
    require(result.returncode == 0 and len(result.stdout) <= pages.LIMIT, 'Repository input unavailable')
    return result.stdout


def blob(workspace, revision, member):
    pages.sha(revision)
    return git(workspace, 'show', revision + ':' + member)


def manifest(workspace, revision):
    result = {}
    for row in git(workspace, 'ls-tree', '-rz', '--full-tree', pages.sha(revision)).split(b'\0'):
        if row:
            metadata, member = row.split(b'\t', 1)
            mode, kind, oid = metadata.decode().split()
            name = member.decode('utf-8')
            require(not name.startswith('/') and '..' not in Path(name).parts, 'Unsafe tracked path')
            result[name] = (mode, kind, oid)
    require(len(result) <= 100000, 'Repository entry limit')
    return result


def subset(files, prefixes):
    selected = {name: value for name, value in files.items()
                if any(name.startswith(p) if p.endswith('/') else name == p for p in prefixes)}
    require(all(mode in ('100644', '100755') and kind == 'blob' for mode, kind, _ in selected.values()),
            'Linked or special evaluation input')
    return selected


def sources(workspace, revision, files):
    """One source per authored skill or APM owner; generated copies are verification only."""
    import yaml
    try:
        lock = yaml.safe_load(blob(workspace, revision, 'apm.lock.yaml'))
    except yaml.YAMLError:
        raise ValueError('Invalid APM ownership encoding') from None
    require(type(lock) is dict and type(lock.get('dependencies')) is list, 'Invalid APM ownership')
    result = {}
    for name in sorted({Path(p).parts[2] for p in files if re.fullmatch(r'\.apm/skills/[^/]+/SKILL\.md', p)}):
        require(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name), 'Invalid authored skill identity')
        result[name] = identity(subset(files, ('.apm/skills/' + name + '/',)))
    for owner in lock['dependencies']:
        name = owner['name']
        require(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name) and name not in result, 'Ambiguous skill owner')
        hashes = owner['deployed_file_hashes']
        require(type(hashes) is dict and hashes, 'Missing deployed hashes')
        for member, expected in hashes.items():
            require(member.startswith('.agents/skills/' + name + '/') and '..' not in Path(member).parts,
                    'Unexpected managed skill member')
            # The publication boundary intentionally omits some large upstream indexes/binaries.
            # Their declared hashes still detect refreshes; only actual suite dependencies need all bytes.
            if member not in files:
                require(name not in ('gh', 'github-actions-hardening'), 'Suite dependency bytes unavailable')
                continue
            subset(files, (member,))
            require('sha256:' + hashlib.sha256(blob(workspace, revision, member)).hexdigest() == expected,
                    'Managed skill hash mismatch')
        require(set(subset(files, ('.agents/skills/' + name + '/',))) <= set(hashes), 'Unowned deployed file')
        result[name] = identity({'owner': owner['repo_url'], 'path': owner['virtual_path'], 'files': hashes})
    return result


def snapshots(workspace, revision):
    files = manifest(workspace, revision)
    catalog = sources(workspace, revision, files)
    runtime = subset(files, RUNTIME_FILES)
    require(all(any(name.startswith(p) if p.endswith('/') else name == p for name in runtime) for p in RUNTIME_FILES),
            'Missing runtime input')
    suites = {}
    for name in SUITES:
        root = '.apm/skills/podman' if name == 'podman' else '.github/evals/' + name
        dataset = pages.parse(blob(workspace, revision, root + '/evals/evals.json'))
        require(dataset['skill_name'] == name and type(dataset['evals']) is list and dataset['evals'], 'Invalid dataset')
        dependencies = {name: catalog[name]}
        if name == 'gh':
            dependencies['github-actions-hardening'] = catalog['github-actions-hardening']
        suites[name] = {'cases': len(dataset['evals']), 'runtime': identity(runtime),
                        'fingerprint': identity({'source': dependencies, 'runtime': runtime,
                                                 'inputs': subset(files, SUITE_FILES[name])})}
    return catalog, suites, identity(subset(files, ('.apm/instructions/',)))


def policy(workspace):
    value = pages.parse((workspace / POLICY_FILE).read_bytes())
    require(set(value) == {'schema_version', 'due_days', 'suites'} and value['schema_version'] == 1
            and value['due_days'] == 30 and set(value['suites']) == {'podman', 'gh'}, 'Unsupported orchestration policy')
    for name, entry in value['suites'].items():
        require(set(entry) == {'enabled', 'max_cases', 'reference'} and type(entry['enabled']) is bool
                and type(entry['max_cases']) is int and 0 < entry['max_cases'] <= 100, 'Invalid suite policy')
        ref = entry['reference']
        if ref is not None:
            require(type(ref) is dict and set(ref) == {'run_id', 'attempt'}, 'Invalid reference identity')
            pages.number(ref['run_id']); pages.number(ref['attempt'])
    return value


def authenticate(api, workspace, main, run_id, attempt, path, *, success=False):
    run = api.get(f'actions/runs/{pages.number(run_id)}/attempts/{pages.number(attempt)}')
    require(run['id'] == run_id and run['run_attempt'] == attempt and run['path'] == path,
            'Producer run identity mismatch')
    require(run['repository']['full_name'] == run['head_repository']['full_name'] == REPOSITORY
            and run['head_branch'] == 'main' and pages.ancestor(workspace, run['head_sha'], main), 'Untrusted producer source')
    allowed = ('push',) if path == pages.WORKFLOWS['validate'] else (
        ('workflow_dispatch',) if path == BENCHMARK else ('workflow_run', 'schedule', 'workflow_dispatch'))
    require(run['event'] in allowed, 'Untrusted producer event')
    workflow = api.get('actions/workflows/' + path.rsplit('/', 1)[1])
    require(workflow['id'] == run['workflow_id'] and workflow['path'] == path, 'Producer workflow mismatch')
    if success:
        require(run['status'] == 'completed' and run['conclusion'] == 'success', 'Producer did not succeed')
    jobs = api.listing(f'actions/runs/{run_id}/attempts/{attempt}/jobs', 'jobs')
    require(all(j['run_id'] == run_id and j['run_attempt'] == attempt and j['head_sha'] == run['head_sha'] for j in jobs),
            'Producer job identity mismatch')
    return run, jobs


def read_artifact(api, run, name):
    matches = [a for a in api.listing(f'actions/runs/{run["id"]}/artifacts', 'artifacts') if a['name'] == name]
    require(len(matches) == 1 and not matches[0]['expired'], 'Operational record unavailable')
    artifact = matches[0]
    require(artifact['workflow_run']['id'] == run['id']
            and artifact['workflow_run']['head_sha'] == run['head_sha']
            and artifact['workflow_run']['head_repository_id'] == run['head_repository']['id'], 'Artifact producer mismatch')
    raw = api.raw(f'repos/{REPOSITORY}/actions/artifacts/{pages.number(artifact["id"])}/zip')
    require(len(raw) <= 1024 * 1024 and artifact['digest'] == 'sha256:' + hashlib.sha256(raw).hexdigest(),
            'Operational archive digest mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        require(len(entries) == 1 and entries[0].filename == 'record.json' and entries[0].file_size <= 256 * 1024
                and entries[0].compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                and not entries[0].flag_bits & 1
                and (entries[0].external_attr >> 16) & 0o170000 in (0, 0o100000), 'Invalid operational archive')
        return pages.parse(archive.read(entries[0]))


def run_scope(run):
    match = TITLE.fullmatch(run.get('display_title', ''))
    return match.groups() if match else (None, None, None)


def qualified(api, workspace, main, run, name, current, ledger):
    run, jobs = authenticate(api, workspace, main, run['id'], run['run_attempt'], BENCHMARK, success=True)
    require(run_scope(run)[:2] == (name, 'standard'), 'Reference scope mismatch')
    pages.successful_job(jobs, 'evaluate', ['Validate selection and clean checkout',
        'Run native with-skill and without-skill evaluation', 'Summarize native results and prepare standard metrics',
        'Verify evaluator left the checkout unchanged'])
    pages.successful_job(jobs, 'publish-history', ['Validate metric allowlist and canonical series',
        'Append standard result to durable history', 'Capture and verify the exact published history commit'])
    previous = snapshots(workspace, run['head_sha'])[1][name]
    require(previous['runtime'] == current['runtime'], 'Reference runtime requires qualification')
    patch = hashlib.sha256((workspace / reports.PATCH).read_bytes()).hexdigest()
    published_policy = hashlib.sha256(json.dumps([reports.benchmark_policy(name), patch], sort_keys=True).encode()).hexdigest()[:16]
    rows = [r for r in ledger if r['skill'] == name and r['revision'] == run['head_sha'] and r['policy'] == published_policy]
    require(rows, 'Admitted current-policy history unavailable')
    return {**previous, 'run_id': run['id'], 'attempt': run['run_attempt'], 'revision': run['head_sha'],
            'completed_at': run['updated_at'], 'policy': published_policy}


def validation(api, workspace, main):
    runs = api.listing('actions/workflows/validate.yml/runs?event=push&branch=main&head_sha=' + main, 'workflow_runs')
    if not runs:
        return None, 'validation_unavailable'
    latest = max(runs, key=lambda r: r['id'])
    run, jobs = authenticate(api, workspace, main, latest['id'], latest['run_attempt'], pages.WORKFLOWS['validate'])
    require(run['head_sha'] == main and jobs, 'Validation revision/jobs mismatch')
    if run['status'] != 'completed' or run['conclusion'] != 'success' or any(j['conclusion'] != 'success' for j in jobs):
        return {'run_id': run['id'], 'attempt': run['run_attempt']}, 'validation_unsuccessful'
    return {'run_id': run['id'], 'attempt': run['run_attempt']}, None


def demand(name, snapshot, anchor):
    return identity([name, snapshot['fingerprint'], anchor])


def stale_skip(api, run, jobs, request):
    """A missing receipt is not proof that inference was skipped."""
    if run['status'] != 'completed' or run['run_attempt'] != 1:
        return False
    evaluations = [j for j in jobs if j['name'] == 'evaluate']
    if len(evaluations) != 1:
        return False
    evaluation = evaluations[0]
    if evaluation['conclusion'] == 'skipped':
        contexts = [j for j in jobs if j['name'] == 'context']
        require(len(contexts) == 1, 'Context job unavailable')
        for name in ('Publish scope and authorization context before requesting approval', 'Retain preapproval scope'):
            steps = [s for s in contexts[0].get('steps', []) if s['name'] == name]
            require(len(steps) == 1 and steps[0]['conclusion'] == 'success', 'Context receipt producer unavailable')
        record = read_artifact(api, run, f'skill-benchmark-context-{run["id"]}-1')
        phase = 'preapproval'
    else:
        steps = {s['name']: s['conclusion'] for s in evaluation.get('steps', [])}
        if steps.get('Run native with-skill and without-skill evaluation') != 'skipped' or any(
            steps.get(name) != 'success' for name in ('Validate dataset, runtime, and final eligibility before inference',
                                                     'Retain postapproval authorization decision')):
            return False
        record = read_artifact(api, run, f'skill-benchmark-authorization-{run["id"]}-1')
        phase = 'postapproval'
    return (record.get('schema_version') == 1 and record.get('kind') == 'benchmark_context'
            and record.get('run_id') == run['id'] and record.get('attempt') == 1
            and record.get('revision') == run['head_sha'] and record.get('phase') == phase
            and record.get('status') == 'stale' and record.get('execute') is False
            and record.get('skill') == request['skill'] and record.get('mode') == 'standard'
            and record.get('request_id') == request['request_id'])


def prior_requests(api, workspace, main, benchmark_runs, since, *, exclude=None):
    """Reconcile retained intents with native run metadata; absence is not a retry permit."""
    runs = api.listing('actions/workflows/' + WORKFLOW.rsplit('/', 1)[1] + '/runs?branch=main', 'workflow_runs')
    requests = []
    for candidate in runs:
        if timestamp(candidate['created_at']) < since or candidate['id'] == (exclude or (None,))[0]:
            continue
        run, jobs = authenticate(api, workspace, main, candidate['id'], candidate['run_attempt'], WORKFLOW)
        # Every attempt can have an uploaded intent, including an earlier attempt of a failed rerun.
        for attempt in range(1, run['run_attempt'] + 1):
            old, old_jobs = (run, jobs) if attempt == run['run_attempt'] else authenticate(
                api, workspace, main, run['id'], attempt, WORKFLOW)
            steps = [s for j in old_jobs if j['name'] == 'plan' for s in j.get('steps', [])
                     if s['name'] == 'Upload immutable plan and dispatch intents' and s['conclusion'] == 'success']
            dispatched = any(j['name'] == 'dispatch' and j['status'] != 'queued' for j in old_jobs)
            if not steps:
                require(not dispatched, 'Dispatch intent unavailable')
                continue
            record = read_artifact(api, old, f'skill-evaluation-plan-{run["id"]}-{attempt}')
            validate_plan(record, old)
            for request in record['requests']:
                matches = [b for b in benchmark_runs if run_scope(b)[2] == request['request_id']]
                require(len(matches) <= 1, 'Ambiguous dispatch correlation')
                state = 'dispatch_unresolved'
                if matches:
                    benchmark, benchmark_jobs = authenticate(api, workspace, main, matches[0]['id'],
                                                             matches[0]['run_attempt'], BENCHMARK)
                    state = 'already_requested'
                    if stale_skip(api, benchmark, benchmark_jobs, request):
                        state = 'stale_without_inference'
                requests.append({**request, 'state': state})
    return requests


def validate_plan(record, run):
    require(type(record) is dict and set(record) == {'schema_version', 'kind', 'revision', 'run_id', 'attempt',
            'observed_at', 'validation', 'health', 'source_changes', 'shared_instructions_changed', 'requests'}
            and record['schema_version'] == 1 and record['kind'] == 'evaluation_plan'
            and record['run_id'] == run['id'] and record['attempt'] == run['run_attempt']
            and record['revision'] == run['head_sha'], 'Invalid plan provenance')
    pages.number(record['run_id']); pages.number(record['attempt']); timestamp(record['observed_at'])
    require(type(record['requests']) is list and len(record['requests']) <= 2, 'Request bound exceeded')
    seen = set()
    for request in record['requests']:
        require(set(request) == {'skill', 'fingerprint', 'demand_id', 'request_id', 'reference', 'cases', 'trials', 'reason'}
                and request['skill'] in ('podman', 'gh') and request['skill'] not in seen, 'Invalid request scope')
        seen.add(request['skill'])
        require(all(type(request[k]) is str and re.fullmatch('[0-9a-f]{64}', request[k])
                    for k in ('fingerprint', 'demand_id', 'request_id')), 'Invalid request identity')
        require(type(request['cases']) is int and 0 < request['cases'] <= 100
                and type(request['trials']) is int and request['trials'] == request['cases'] * 2
                and request['reason'] in ('inputs_changed', 'measurement_missing', 'periodic_due'), 'Invalid request limits')
        reference = request['reference']
        require(type(reference) is dict and set(reference) == {'run_id', 'attempt'}, 'Invalid qualification reference')
        pages.number(reference['run_id']); pages.number(reference['attempt'])


def assess(workspace, retained, api, event_name, event, *, exclude=None, benchmark_id=None):
    main = pages.sha(git(workspace, 'rev-parse', 'HEAD').decode().strip())
    require(event_name in ('workflow_run', 'schedule', 'workflow_dispatch'), 'Unsupported planning event')
    if event_name == 'workflow_run':
        source = event['workflow_run']
        authenticate(api, workspace, main, source['id'], source['run_attempt'], pages.WORKFLOWS['validate'])
    cfg = policy(workspace)
    catalog, current, instructions = snapshots(workspace, main)
    try:
        parent = git(workspace, 'rev-parse', main + '^').decode().strip()
        previous, _, previous_instructions = snapshots(workspace, parent)
    except ValueError:
        previous, previous_instructions = {}, None
    result = {'schema_version': 1, 'kind': 'evaluation_plan', 'revision': main,
              'run_id': int(os.environ.get('GITHUB_RUN_ID', '1')), 'attempt': int(os.environ.get('GITHUB_RUN_ATTEMPT', '1')),
              'observed_at': now().strftime('%Y-%m-%dT%H:%M:%SZ'), 'validation': None, 'health': [],
              'source_changes': sorted(n for n in catalog.keys() | previous.keys() if catalog.get(n) != previous.get(n)),
              'shared_instructions_changed': instructions != previous_instructions, 'requests': []}
    validation_record, validation_error = validation(api, workspace, main)
    result['validation'] = validation_record
    if api.get('git/ref/heads/main')['object']['sha'] != main:
        validation_error = 'source_revision_stale'
    require(git(retained, 'rev-parse', 'HEAD').decode().strip() == api.get('git/ref/heads/gh-pages')['object']['sha'],
            'Retained history snapshot moved')
    ledger = pages.ledger(retained / 'benchmarks')
    runs = api.listing('actions/workflows/benchmark-skills.yml/runs', 'workflow_runs')
    for name in SUITES:
        snap = current[name]
        row = {'skill': name, **snap, 'status': 'diagnostic_only', 'reason': 'diagnostic_only', 'reference': None,
               'last_qualified': None, 'coverage': 'configured'}
        result['health'].append(row)
        try:
            reports.benchmark_skill(workspace, name)
            with tempfile.TemporaryDirectory(prefix='skill-plan-') as temporary:
                reports.prepare_benchmark(workspace, Path(temporary), name)
        except (ValueError, OSError, KeyError):
            row.update(status='blocked', reason='dependency_or_dataset_unavailable')
            continue
        if name == 'powershell-pester-6':
            continue
        suite_policy = cfg['suites'][name]
        row['status'] = 'disabled' if not suite_policy['enabled'] else 'blocked'
        compatible = []
        for candidate in runs:
            if candidate['status'] == 'completed' and candidate['conclusion'] == 'success' and run_scope(candidate)[:2] == (name, 'standard'):
                try:
                    compatible.append(qualified(api, workspace, main, candidate, name, snap, ledger))
                except ValueError:
                    continue
        compatible.sort(key=lambda r: timestamp(r['completed_at']), reverse=True)
        matching = [r for r in compatible if r['fingerprint'] == snap['fingerprint']]
        latest = matching[0] if matching else None
        row['last_qualified'] = latest
        row['reason'] = 'inputs_changed' if compatible and not latest else 'measurement_missing'
        if latest:
            age = now() - timestamp(latest['completed_at'])
            require(age >= timedelta(0), 'Future measurement timestamp')
            row['reason'] = 'periodic_due' if age >= timedelta(days=cfg['due_days']) else 'fresh'
        reference = suite_policy['reference']
        if reference is not None:
            try:
                ref_run = api.get(f'actions/runs/{reference["run_id"]}/attempts/{reference["attempt"]}')
                row['reference'] = qualified(api, workspace, main, ref_run, name, snap, ledger)
            except ValueError:
                row.update(status='blocked', reason='reference_requires_qualification')
                continue
        if validation_error:
            row.update(status='blocked', reason=validation_error)
        elif snap['cases'] > suite_policy['max_cases']:
            row.update(status='blocked', reason='scope_ceiling_exceeded')
        elif not suite_policy['enabled']:
            pass
        elif row['reference'] is None:
            row.update(status='blocked', reason='qualification_required')
        elif row['reason'] == 'fresh':
            row['status'] = 'fresh'
        else:
            anchor = compatible[0] if compatible else row['reference']
            key = demand(name, snap, [anchor['run_id'], anchor['attempt']])
            prior = prior_requests(api, workspace, main, runs, timestamp(anchor['completed_at']), exclude=exclude)
            duplicate = next((p for p in prior if p['demand_id'] == key and p['state'] != 'stale_without_inference'), None)
            active = [r for r in runs if r['id'] != benchmark_id and r['status'] != 'completed']
            if duplicate:
                row.update(status='blocked', reason=duplicate['state'])
            elif any(run_scope(r)[0] in (None, name) for r in active) or len(active) >= 2:
                row.update(status='blocked', reason='benchmark_outstanding')
            else:
                row['status'] = 'selected'
                result['requests'].append({'skill': name, 'fingerprint': snap['fingerprint'], 'demand_id': key,
                    'request_id': identity([key, main]), 'reference': reference, 'cases': snap['cases'],
                    'trials': snap['cases'] * 2, 'reason': row['reason']})
    for name in sorted(catalog.keys() - set(SUITES)):
        result['health'].append({'skill': name, 'status': 'coverage_gap', 'coverage': 'not_configured', 'reason': 'no_supported_suite'})
    return result


def display(record):
    lines = ['## Skill evaluation planning (no inference)', '',
             '| Suite | Disposition | Reason |', '| --- | --- | --- |']
    lines += [f'| {r["skill"]} | {r["status"]} | {r["reason"]} |' for r in record['health']]
    lines += ['', 'Shared instruction changes require coverage review; current suites do not measure repository-wide instructions.',
              'Selection, execution, history admission, and Pages publication are separate outcomes.',
              'Costs: native agent subtotals may be estimates; judging/preflight and actual billed totals can be unknown.']
    reports.summary(lines)


def load_intent(api, workspace, main, run_id, attempt):
    run, jobs = authenticate(api, workspace, main, run_id, attempt, WORKFLOW)
    pages.successful_job(jobs, 'plan', ['Plan evaluation health without inference', 'Upload immutable plan and dispatch intents'])
    record = read_artifact(api, run, f'skill-evaluation-plan-{run_id}-{attempt}')
    validate_plan(record, run)
    return record


def dispatch(workspace, retained, api, record, post):
    """Exactly one POST attempt for each authenticated, still-eligible intent; no retries."""
    original = load_intent(api, workspace, record['revision'], record['run_id'], record['attempt'])
    require(original == record, 'Substituted dispatch plan')
    require(int(os.environ['GITHUB_RUN_ATTEMPT']) == 1, 'Automatic dispatch reruns require manual reconciliation')
    fresh = assess(workspace, retained, api, 'workflow_dispatch', {}, exclude=(record['run_id'], record['attempt']))
    responses = []
    for request in record['requests']:
        require(request in fresh['requests'] and fresh['revision'] == record['revision'], 'Dispatch intent no longer eligible')
        require(api.get('git/ref/heads/main')['object']['sha'] == record['revision'], 'Main moved before dispatch')
        response = post({'ref': 'main', 'return_run_details': True, 'inputs': {
            'skill': request['skill'], 'mode': 'standard', 'request_id': request['request_id'],
            'planner_run_id': str(record['run_id']), 'planner_attempt': str(record['attempt']),
            'expected_revision': record['revision']}})
        run_id = pages.number(response['workflow_run_id'])
        require(response['run_url'] == f'https://api.github.com/repos/{REPOSITORY}/actions/runs/{run_id}'
                and response['html_url'] == f'https://github.com/{REPOSITORY}/actions/runs/{run_id}', 'Dispatch response mismatch')
        responses.append({'request_id': request['request_id'], 'run_id': run_id})
    return {'schema_version': 1, 'kind': 'dispatch_response', 'responses': responses}


def context(workspace, retained, api, inputs, *, phase):
    name, mode = inputs['skill'], inputs['mode']
    require(name in SUITES and mode in reports.MODES, 'Unsupported benchmark scope')
    require(not reports.benchmark_options(name)['diagnostic_only'] or mode == 'confirmation', 'Diagnostic suite requires confirmation')
    revision = pages.sha(git(workspace, 'rev-parse', 'HEAD').decode().strip())
    request_id = inputs.get('request_id', '')
    value = {'schema_version': 1, 'kind': 'benchmark_context', 'revision': revision,
             'run_id': int(os.environ['GITHUB_RUN_ID']), 'attempt': int(os.environ['GITHUB_RUN_ATTEMPT']),
             'request_id': request_id, 'skill': name, 'mode': mode, 'phase': phase, 'execute': True, 'status': 'manual',
             'cases': None, 'trials': None, 'reference': None, 'reason': 'explicit_manual_dispatch'}
    if request_id:
        require(re.fullmatch('[0-9a-f]{64}', request_id) and mode == 'standard', 'Invalid automatic request')
        planner_id = pages.number(int(inputs['planner_run_id'])); attempt = pages.number(int(inputs['planner_attempt']))
        expected = pages.sha(inputs['expected_revision'])
        require(os.environ['GITHUB_REF'] == 'refs/heads/main' and value['attempt'] == 1, 'Automatic benchmark requires initial main dispatch')
        intent = load_intent(api, workspace, revision, planner_id, attempt)
        requests = [r for r in intent['requests'] if r['request_id'] == request_id and r['skill'] == name]
        require(len(requests) == 1 and intent['revision'] == expected, 'Request not bound to intent')
        request = requests[0]
        value.update(cases=request['cases'], trials=request['trials'], reference=request['reference'], reason=request['reason'])
        if expected != revision or api.get('git/ref/heads/main')['object']['sha'] != revision:
            value.update(execute=False, status='stale')
        else:
            fresh = assess(workspace, retained, api, 'workflow_dispatch', {}, exclude=(planner_id, attempt), benchmark_id=value['run_id'])
            value.update(execute=request in fresh['requests'], status='eligible' if request in fresh['requests'] else 'ineligible')
    else:
        require(not any(inputs.get(k) for k in ('planner_run_id', 'planner_attempt', 'expected_revision')), 'Partial automatic request')
        if os.environ['GITHUB_REF'] == 'refs/heads/main':
            _, error = validation(api, workspace, revision)
            if error or api.get('git/ref/heads/main')['object']['sha'] != revision:
                value.update(execute=False, status='stale' if not error else error)
        with tempfile.TemporaryDirectory(prefix='skill-context-') as temporary:
            selected = reports.prepare_benchmark(workspace, Path(temporary), name)
            value['cases'] = len(reports.read_json(selected / 'evals/evals.json')['evals'])
            value['trials'] = value['cases'] * reports.MODES[mode] * 2
    reports.summary(['## Benchmark scope before inference', '',
        f'Suite: `{name}`; mode: `{mode}`; cases: {value["cases"]}; task trials: {value["trials"]}.',
        f'Evaluated revision: `{revision}`.',
        f'Selection rationale: `{value["reason"]}`. Eligibility: `{value["status"]}`.',
        'Qualification reference: ' + (f'[run {value["reference"]["run_id"]}, attempt {value["reference"]["attempt"]}]'
            f'(https://github.com/{REPOSITORY}/actions/runs/{value["reference"]["run_id"]})'
            if value['reference'] else 'none; explicit manual qualification/review required'),
        'Provider preflight and judging add work. Native costs may be estimated; missing usage and total billed cost remain unknown.',
        'The protected job requires human approval. A separate eligibility check runs after approval immediately before inference.'])
    return value


def post_dispatch(payload):
    result = subprocess.run(['gh', 'api', '--method', 'POST', '-H', 'X-GitHub-Api-Version: 2022-11-28',
        f'repos/{REPOSITORY}/actions/workflows/benchmark-skills.yml/dispatches', '--input', '-'],
        input=json.dumps(payload).encode(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=60, check=False)
    require(result.returncode == 0, 'Dispatch outcome uncertain; reconcile the uploaded intent before any retry')
    return pages.parse(result.stdout)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('plan', 'dispatch', 'context', 'guard'))
    parser.add_argument('--workspace', type=Path, default=Path(os.environ.get('GITHUB_WORKSPACE', '.')))
    parser.add_argument('--retained', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    workspace = args.workspace.resolve()
    require(os.environ.get('GITHUB_REPOSITORY') == REPOSITORY, 'Unexpected repository')
    require(git(workspace, 'rev-parse', 'HEAD').decode().strip() == os.environ['GITHUB_SHA'], 'Dispatched revision mismatch')
    require(not git(workspace, 'status', '--porcelain=v1', '--untracked-files=all', '--ignored'), 'Checkout must be clean')
    event = pages.parse(Path(os.environ['GITHUB_EVENT_PATH']).read_bytes())
    api = pages.GitHub()
    if args.command == 'plan':
        record = assess(workspace, args.retained, api, os.environ['GITHUB_EVENT_NAME'], event)
        display(record)
        reports.outputs(has_requests=str(bool(record['requests'])).lower())
    elif args.command == 'dispatch':
        record = load_intent(api, workspace, git(workspace, 'rev-parse', 'HEAD').decode().strip(),
                             int(os.environ['GITHUB_RUN_ID']), int(os.environ['GITHUB_RUN_ATTEMPT']))
        record = dispatch(workspace, args.retained, api, record, post_dispatch)
    else:
        require(os.environ['GITHUB_EVENT_NAME'] == 'workflow_dispatch', 'Benchmark requires workflow dispatch')
        record = context(workspace, args.retained, api, event['inputs'], phase='preapproval' if args.command == 'context' else 'postapproval')
        reports.outputs(execute=str(record['execute']).lower())
    require(not args.output.resolve().is_relative_to(workspace), 'Operational records must be outside checkout')
    reports.write_json(args.output, record)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile, subprocess.TimeoutExpired):
        # Never print API bodies, arbitrary native strings, or credentials.
        raise SystemExit('Evaluation orchestration unavailable; no retry is authorized. Inspect authenticated run records.')
