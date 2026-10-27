#!/usr/bin/env python3
"""Trusted Pages preparation, offline reproduction, and exact-commit handoff.

Only prepare uses the Actions API. Public inputs are data, never executable code.
The write-token commit command uses only the standard library and sealed files.
"""
import argparse
import base64
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import selectors
import time
import stat
import subprocess
import tempfile
import zipfile

REPOSITORY = 'thetechgy/agent-engineering-baseline'
RECOVERY_EVENT = 'recover-skill-report'
WORKFLOWS = {'validate': '.github/workflows/validate.yml', 'benchmark': '.github/workflows/benchmark-skills.yml'}
LIMIT = 32 * 1024 * 1024
MAX_FILES = 2048
NAME = r'[a-z0-9][a-z0-9_-]{0,100}'
SERIES = re.compile(r'(?P<skill>' + NAME + r')/(?P<policy>[0-9a-f]{16})/data\.js')
PUBLIC = re.compile(r'inventory/inventory\.json|skills/' + NAME + r'/(?:static|behavioral/[A-Za-z0-9_.-]+)/public-report\.json')
SLOT = re.compile(r'quality|standard--' + NAME + r'|oracle--' + NAME + r'|confirmation--' + NAME)


class PublicationError(ValueError):
    pass


def require(value, message):
    if not value:
        raise PublicationError(message)


def sha(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{40}', value), 'Invalid commit identity')
    return value


def number(value):
    require(type(value) is int and 0 < value < 10**15, 'Expected bounded numeric run/attempt identity')
    return value


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def parse(raw):
    require(len(raw) <= LIMIT, 'JSON size limit')
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: require(False, 'Nonfinite JSON'))


def tree(root):
    require(root.is_dir() and root.resolve() == root.absolute(), 'Linked or missing publication tree')
    result = {}
    size = 0
    count = 0
    def fail(error):
        raise error
    for parent, dirs, files in os.walk(root, followlinks=False, onerror=fail):
        count += len(dirs) + len(files)
        require(count <= MAX_FILES * 2, 'Publication entry limit')
        for name in dirs + files:
            path = Path(parent) / name
            mode = path.lstat().st_mode
            require(stat.S_ISDIR(mode) or stat.S_ISREG(mode), 'Nonregular publication member')
        for name in files:
            path = Path(parent) / name
            size += path.stat().st_size
            require(size <= 128 * 1024 * 1024 and len(result) < MAX_FILES, 'Publication tree limit')
            result[path.relative_to(root).as_posix()] = path.read_bytes()
    return result


def write(root, member, raw):
    path = root / member
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def git(root, *args, env=None):
    result = subprocess.run(['git', '-C', str(root), *args], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=env, timeout=120, check=False)
    require(result.returncode == 0, 'Git operation failed: ' + args[0])
    return result.stdout.decode().strip()


class GitHub:
    """Fixed-host authenticated API paths; no payload-controlled repositories/URLs."""
    def raw(self, path):
        require(path == f'repos/{REPOSITORY}' or path.startswith(f'repos/{REPOSITORY}/'), 'Unexpected API repository')
        deadline = time.monotonic() + 120
        with subprocess.Popen(['gh', 'api', path], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as child:
            try:
                chunks = []; size = 0
                with selectors.DefaultSelector() as selector:
                    selector.register(child.stdout, selectors.EVENT_READ)
                    while True:
                        remaining = deadline - time.monotonic()
                        require(remaining > 0, 'API response deadline')
                        require(selector.select(remaining), 'API response deadline')
                        chunk = os.read(child.stdout.fileno(), 65536)
                        if not chunk:
                            break
                        size += len(chunk)
                        require(size <= LIMIT, 'API response limit')
                        chunks.append(chunk)
                require(child.wait(timeout=10) == 0, 'GitHub API request failed')
                return b''.join(chunks)
            finally:
                if child.poll() is None:
                    child.kill()

    def get(self, path):
        return parse(self.raw(f'repos/{REPOSITORY}/{path}'.rstrip('/')))

    def listing(self, path, key):
        rows = []
        for page in range(1, 21):
            data = self.get(f'{path}{"&" if "?" in path else "?"}per_page=100&page={page}')
            batch = data[key]
            require(type(batch) is list, 'Invalid API collection')
            rows.extend(batch)
            if len(batch) < 100:
                require(len(rows) == data['total_count'], 'Incomplete API collection')
                return rows
        raise ValueError('API pagination limit')


def request(event_name, event):
    if event_name == 'workflow_run':
        value = event['workflow_run']
        return number(value['id']), number(value['run_attempt'])
    require(event_name == 'repository_dispatch' and event['action'] == RECOVERY_EVENT,
            'Unsupported publication event')
    payload = event.get('client_payload', {})
    require(type(payload) is dict and set(payload) in (set(), {'run_id', 'attempt'}),
            'Recovery accepts only run_id and attempt, or an empty rebuild request')
    if not payload:
        return None
    return number(payload['run_id']), number(payload['attempt'])


def successful_job(jobs, name, steps):
    selected = [job for job in jobs if job['name'] == name]
    require(len(selected) == 1 and selected[0]['conclusion'] == 'success', 'Producer job did not succeed')
    for name in steps:
        values = [step for step in selected[0]['steps'] if step['name'] == name]
        require(len(values) == 1 and values[0]['conclusion'] == 'success', 'Producer step did not succeed: ' + name)
    return selected[0]


def authenticate(api, run_id, attempt, workspace, main_sha):
    """Authenticate exact attempt, workflow identity, repository and main ancestry."""
    run = api.get(f'actions/runs/{number(run_id)}/attempts/{number(attempt)}')
    require(run['id'] == run_id and run['run_attempt'] == attempt, 'Run attempt mismatch')
    require(run['repository']['full_name'] == REPOSITORY and run['head_repository']['full_name'] == REPOSITORY,
            'Foreign producer repository')
    require(run['head_branch'] == 'main' and run['status'] == 'completed' and run['conclusion'] == 'success',
            'Only completed successful main producers are eligible')
    revision = sha(run['head_sha'])
    require(ancestor(workspace, revision, main_sha), 'Producer commit is not on verified main')
    kind = next((key for key, path in WORKFLOWS.items() if run['path'] == path), None)
    require(kind is not None, 'Unexpected producer workflow path')
    workflow = api.get('actions/workflows/' + WORKFLOWS[kind].rsplit('/', 1)[1])
    require(workflow['id'] == run['workflow_id'] and workflow['path'] == WORKFLOWS[kind], 'Workflow identity mismatch')
    require(run['event'] == ('push' if kind == 'validate' else 'workflow_dispatch'), 'Unexpected producer event')
    jobs = api.listing(f'actions/runs/{run_id}/attempts/{attempt}/jobs', 'jobs')
    require(all(job['run_id'] == run_id and job['run_attempt'] == attempt and job['head_sha'] == revision
                for job in jobs), 'Job provenance mismatch')
    return kind, run, jobs


def ancestor(workspace, older, newer):
    sha(older); sha(newer)
    result = subprocess.run(['git', '-C', str(workspace), 'merge-base', '--is-ancestor', older, newer],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    require(result.returncode in (0, 1), 'Commit ancestry unavailable')
    return result.returncode == 0


def newer(workspace, incoming, retained):
    if incoming['revision'] == retained['revision']:
        return (incoming['run_id'], incoming['attempt']) > (retained['run_id'], retained['attempt'])
    if ancestor(workspace, retained['revision'], incoming['revision']):
        return True
    require(ancestor(workspace, incoming['revision'], retained['revision']), 'Conflicting evidence ancestry')
    return False


def extract_public(raw, expected_digest, destination):
    require(expected_digest == 'sha256:' + digest(raw), 'Artifact archive digest mismatch')
    require(len(raw) <= LIMIT and not destination.exists(), 'Archive size or destination invalid')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        require(0 < len(members) <= 512, 'Archive member limit')
        names = [item.filename for item in members]
        require(len(names) == len(set(names)), 'Duplicate archive members')
        total = 0
        files = {}
        for item in members:
            require(not item.is_dir() and PUBLIC.fullmatch(item.filename) and all(part not in ('.', '..') for part in item.filename.split('/')), 'Unexpected public archive layout')
            mode = item.external_attr >> 16
            require(stat.S_IFMT(mode) in (0, stat.S_IFREG) and not item.flag_bits & 1, 'Nonregular/encrypted archive member')
            total += item.file_size
            require(item.file_size <= 8 * 1024 * 1024 and total <= LIMIT, 'Expanded archive limit')
            files[item.filename] = archive.read(item)
        require('inventory/inventory.json' in files and len(files) > 1, 'Empty public evidence bundle')
    for member, contents in files.items():
        write(destination, member, contents)
    import skill_analysis as analysis
    return analysis.capture_inputs([destination])


def provenance(run, artifact):
    return {'repository': REPOSITORY, 'workflow_id': run['workflow_id'], 'workflow_path': run['path'],
            'event': run['event'], 'revision': run['head_sha'], 'run_id': run['id'], 'attempt': run['run_attempt'],
            'artifact_id': artifact['id'], 'archive_digest': artifact['digest']}


def validate_provenance(value):
    require(set(value) == {'repository', 'workflow_id', 'workflow_path', 'event', 'revision', 'run_id',
                           'attempt', 'artifact_id', 'archive_digest'}, 'Unexpected provenance fields')
    require(value['repository'] == REPOSITORY and value['workflow_path'] in WORKFLOWS.values(), 'Invalid retained producer')
    sha(value['revision'])
    for key in ('workflow_id', 'run_id', 'attempt', 'artifact_id'):
        number(value[key])
    require(re.fullmatch('sha256:[0-9a-f]{64}', value['archive_digest']), 'Invalid retained archive digest')
    require(value['event'] == ('push' if value['workflow_path'] == WORKFLOWS['validate'] else 'workflow_dispatch'),
            'Invalid retained producer event')


def bundle_claims(captured, slot, prov):
    import skill_evidence as evidence
    validate_provenance(prov)
    expected_workflow = WORKFLOWS['validate' if slot == 'quality' or slot.startswith('oracle--') else 'benchmark']
    require(prov['workflow_path'] == expected_workflow, 'Evidence purpose/workflow mismatch')
    records = [record for record in captured.records.values() if record['kind'] != 'inventory']
    require(bool(records), 'Evidence bundle has no reports')
    for record in records:
        if slot == 'quality':
            require(record['kind'] == 'static', 'Nonstatic quality bundle')
        else:
            purpose, name = slot.split('--', 1)
            require(record['kind'] == 'behavioral' and record['source']['skill_id'] == name, 'Behavioral slot mismatch')
            mode = record['policy']['attempts']['mode']
            if purpose != 'oracle':
                require(mode == ('standard' if purpose == 'standard' else 'confirmation'), 'Behavioral purpose mismatch')
            oracle = record.get('custom', {}).get('purpose') == 'oracle_qualification'
            require(oracle == (purpose == 'oracle'), 'Oracle qualification purpose mismatch')
        source = record['source']
        # Upstream skill ownership remains upstream; execution is bound separately.
        if source['owner'] == 'local':
            require(source['repository'] == REPOSITORY and source['revision'] == prov['revision'], 'Public evaluated revision mismatch')
        evidence.reports.public_strings(record)
    return records


def load_state(site):
    files = tree(site)
    manifest = files.get('report/publication.json')
    if manifest is None:
        require(not any(name.startswith('report/') for name in files), 'Unmanifested retained evidence')
        return {'schema_version': 1, 'current': None, 'slots': {}}
    value = parse(manifest)
    require(set(value) == ({'schema_version', 'current', 'slots'} if value.get('schema_version') == 1 else {'schema_version', 'current', 'slots', 'history_digest'}) and type(value['schema_version']) is int and value['schema_version'] in (1, 2), 'Publication manifest version')
    if value['schema_version'] == 2:
        import skill_history as history
        require(digest(files.get('report/history.json', b'')) == value['history_digest'], 'History digest mismatch')
        history.validate(parse(files['report/history.json']))
    require(type(value['slots']) is dict and len(value['slots']) <= 100, 'Publication slot limit')
    import skill_analysis as analysis
    for slot, item in value['slots'].items():
        require(SLOT.fullmatch(slot), 'Invalid evidence slot')
        require(set(item) == {'provenance', 'members'}, 'Unexpected slot fields')
        validate_provenance(item['provenance'])
        prefix = f'report/bundles/{slot}/'
        actual = {name[len(prefix):]: digest(raw) for name, raw in files.items() if name.startswith(prefix)}
        require(actual == item['members'] and actual, 'Retained evidence member hash mismatch')
        captured = analysis.capture_inputs([site / prefix])
        bundle_claims(captured, slot, item['provenance'])
    current = value['current']
    require(type(current) is dict and set(current) == {'revision', 'digest'}, 'Current inventory metadata required')
    sha(current['revision'])
    require(digest(files.get('report/current/inventory/inventory.json', b'')) == current['digest'], 'Current inventory digest mismatch')
    analysis.capture_inputs([site / 'report/current'])
    allowed = {'report/publication.json', 'report/analysis.json', 'report/current/inventory/inventory.json'}
    if value['schema_version'] == 2:
        allowed.add('report/history.json')
    allowed.update(f'report/bundles/{slot}/{member}' for slot, item in value['slots'].items() for member in item['members'])
    require(all(not name.startswith('report/') or name in allowed for name in files), 'Unmanifested publication member')
    return value


def admit(site, state, slot, prov, incoming, workspace):
    require(SLOT.fullmatch(slot), 'Invalid evidence slot')
    validate_provenance(prov)
    import skill_analysis as analysis
    captured = analysis.capture_inputs([incoming])
    bundle_claims(captured, slot, prov)
    files = tree(incoming)
    item = {'provenance': prov, 'members': {name: digest(raw) for name, raw in files.items()}}
    old = state['slots'].get(slot)
    if old:
        if (prov['run_id'], prov['attempt']) == (old['provenance']['run_id'], old['provenance']['attempt']):
            require(item == old, 'Conflicting duplicate admission')
            return False
        if not newer(workspace, prov, old['provenance']):
            return False
    target = site / f'report/bundles/{slot}'
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(incoming, target)
    state['slots'][slot] = item
    return True


def validate_ledger_metrics(benches, policy):
    require(type(benches) is list and len(benches) == 4, 'History metric cardinality')
    names = ['Skill Lift', 'Effectiveness', 'Correctness', 'Discoverability']
    extras = set()
    for name, metric in zip(names, benches):
        require(type(metric) is dict and set(metric) == {'name', 'value', 'unit', 'extra'}
                and metric['name'] == name and metric['unit'] == 'score', 'Invalid ledger metric')
        val = metric['value']
        require(type(val) in (int, float) and math.isfinite(val) and (-1 if name == 'Skill Lift' else 0) <= val <= 1, 'Invalid ledger value')
        require(type(metric['extra']) is str, 'Invalid ledger identity')
        extras.add(metric['extra'])
    require(len(extras) == 1, 'Conflicting ledger identities')
    identity = re.fullmatch(r'Dataset (sha256:[0-9a-f]{64}); policy ([0-9a-f]{16})', next(iter(extras)))
    require(identity and identity[2] == policy, 'Ledger dataset/policy mismatch')
    return identity[1]


def ledger(site):
    """Parse the native action's fixed assignment as JSON, never JavaScript."""
    rows = []
    identities = {}
    for member, raw in sorted(tree(site).items()):
        match = SERIES.fullmatch(member)
        if not match:
            continue
        require(len(raw) <= 8 * 1024 * 1024 and raw.startswith(b'window.BENCHMARK_DATA = '), 'Invalid history assignment')
        data = parse(raw[len(b'window.BENCHMARK_DATA = '):])
        require(set(data) == {'lastUpdate', 'repoUrl', 'entries'} and data['repoUrl'] == f'https://github.com/{REPOSITORY}', 'Invalid history envelope')
        require(type(data['lastUpdate']) is int and data['lastUpdate'] >= 0, 'Invalid history timestamp')
        require(type(data['entries']) is dict and set(data['entries']) == {'Agent skill benchmark (standard)'}, 'Invalid history series')
        import skill_reports as reports
        reports.public_strings(data)
        entries = data['entries']['Agent skill benchmark (standard)']
        require(type(entries) is list and len(entries) <= 10000, 'History entry limit')
        for entry in entries:
            require(set(entry) == {'commit', 'date', 'tool', 'benches'} and entry['tool'] == 'customBiggerIsBetter', 'Invalid history entry')
            require(type(entry['date']) is int and entry['date'] >= 0, 'Invalid measurement timestamp')
            commit = entry['commit']; revision = sha(commit['id'])
            require(commit['url'] == f'https://github.com/{REPOSITORY}/commit/{revision}', 'Foreign ledger commit URL')
            benches = entry['benches']
            dataset = validate_ledger_metrics(benches, match['policy'])
            row = {'skill': match['skill'], 'policy': match['policy'], 'dataset': dataset,
                   'revision': revision, 'date': entry['date'], 'metrics': benches, 'member': member,
                   'detail': 'ledger_only', 'record_id': None, 'provenance': 'run_and_attempt_not_recorded'}
            key = (row['skill'], row['policy'], row['dataset'], revision, row['date'])
            require(key not in identities, 'Duplicate or conflicting ledger measurement')
            identities[key] = row
            rows.append(row)
    return rows


def published_policy(record):
    policy = record['policy']
    if policy['published_id'] is not None:
        return policy['published_id']
    if policy['patch_digest'] is None:
        return None
    fields = {key: value for key, value in policy['fields'].items() if value is not None}
    return digest(json.dumps([fields, policy['patch_digest'].removeprefix('sha256:')], sort_keys=True).encode())[:16]


def reconcile_history(rows, captured, standard_revisions=None):
    standard_revisions = standard_revisions or {}
    for rid, record in captured.records.items():
        if record['kind'] != 'behavioral' or record['policy']['attempts']['mode'] != 'standard':
            continue
        revision = standard_revisions.get(rid, record['source']['revision'])
        same_source = [row for row in rows if row['skill'] == record['source']['skill_id'] and row['revision'] == revision]
        same_identity = [row for row in same_source if row['policy'] == published_policy(record)
                         and row['dataset'] == record['dataset']['staged_digest']]
        require(same_identity, 'Supplied standard detail conflicts with or is absent from admitted ledger identities')
        actual = {metric['name']: metric['value'] for metric in record['metrics']}
        matching = [row for row in same_identity if actual == {metric['name']: metric['value'] for metric in row['metrics']}]
        require(matching, 'Supplied standard detail conflicts with ledger values')
        for row in matching:
            require(row['record_id'] in (None, rid), 'Ambiguous ledger detail')
            row.update(detail='public_detail_available', record_id=rid)
    return rows


def validate_context(context, captured):
    require(type(context) is dict and set(context) == {'current', 'slots', 'history'}, 'Invalid Pages context')
    current = context['current']
    require(type(current) is dict and set(current) == {'revision', 'digest', 'inventory_record_id'}, 'Invalid current Pages inventory')
    sha(current['revision'])
    require(current['inventory_record_id'] in captured.records and captured.records[current['inventory_record_id']]['kind'] == 'inventory', 'Current inventory context mismatch')
    require(any(member['record_id'] == current['inventory_record_id'] and member['raw_digest'] == 'sha256:' + current['digest']
                for manifest in captured.manifests for member in manifest['members']), 'Current inventory digest context mismatch')
    require(type(context['slots']) is list and len(context['slots']) <= 100, 'Invalid Pages slot population')
    seen = set(); revisions = {}
    for item in context['slots']:
        require(type(item) is dict and set(item) == {'slot', 'provenance', 'members'}, 'Unexpected Pages slot fields')
        require(SLOT.fullmatch(item['slot']) and item['slot'] not in seen, 'Invalid or duplicate Pages evidence slot')
        seen.add(item['slot'])
        validate_provenance(item['provenance'])
        require(type(item['members']) is dict and 0 < len(item['members']) <= 512, 'Invalid Pages member population')
        require(all(PUBLIC.fullmatch(member) and re.fullmatch('[0-9a-f]{64}', value)
                    for member, value in item['members'].items()), 'Invalid Pages member path/digest')
        manifests = [manifest for manifest in captured.manifests if item['members'] == {
            member['member']: member['raw_digest'].removeprefix('sha256:') for member in manifest['members']}]
        require(len(manifests) == 1, 'Pages slot is not bound to captured public members')
        subset = type(captured)({member['record_id']: captured.records[member['record_id']]
                                for member in manifests[0]['members']}, manifests)
        bundle_claims(subset, item['slot'], item['provenance'])
        if item['slot'].startswith('standard--'):
            revisions.update({rid: item['provenance']['revision'] for rid, record in subset.records.items() if record['kind'] == 'behavioral'})
    require(type(context['history']) is list and len(context['history']) <= 10000, 'Pages history population limit')
    for row in context['history']:
        require(type(row) is dict and set(row) == {'skill', 'policy', 'dataset', 'revision', 'date', 'metrics', 'member',
                'detail', 'record_id', 'provenance'}, 'Invalid Pages ledger row')
        sha(row['revision'])
        require(SERIES.fullmatch(row['member']) and row['member'] == f'{row["skill"]}/{row["policy"]}/data.js', 'Invalid Pages ledger link')
        require(type(row['date']) is int and 0 <= row['date'] < 10**15, 'Invalid Pages ledger date')
        require(re.fullmatch('sha256:[0-9a-f]{64}', row['dataset']), 'Invalid Pages ledger dataset')
        require(row['provenance'] == 'run_and_attempt_not_recorded', 'Inferred ledger provenance')
        validate_ledger_metrics(row['metrics'], row['policy'])
        require(all(metric['extra'] == f'Dataset {row["dataset"]}; policy {row["policy"]}' for metric in row['metrics']), 'Pages ledger identity mismatch')
        require(row['detail'] in ('ledger_only', 'public_detail_available'), 'Invalid ledger detail status')
        require(row['record_id'] is None or row['record_id'] in captured.records, 'Dangling ledger detail')
    replay = [{**row, 'detail': 'ledger_only', 'record_id': None} for row in context['history']]
    require(reconcile_history(replay, captured, revisions) == context['history'], 'Pages ledger support context mismatch')


def build(site):
    """Revalidate retained bundles, analyze, save, independently reload and render."""
    import skill_analysis as analysis
    import skill_evidence as evidence
    import skill_report as report
    import skill_history as history
    state = load_state(site)
    require(state['current'] is not None, 'Current inventory required')
    roots = [site / 'report/current'] + [site / f'report/bundles/{slot}' for slot in sorted(state['slots'])]
    captured = analysis.capture_inputs(roots)
    result = analysis.build_analysis(captured)
    analysis.validate_analysis(result, captured)
    write(site, 'report/analysis.json', evidence.encoded(result))
    saved = evidence.parse_json((site / 'report/analysis.json').read_bytes(), limit=analysis.JSON_LIMIT)
    standard_revisions = {}
    for slot, item in state['slots'].items():
        if slot.startswith('standard--'):
            bundle = analysis.capture_inputs([site / f'report/bundles/{slot}'])
            standard_revisions.update({rid: item['provenance']['revision'] for rid, record in bundle.records.items() if record['kind'] == 'behavioral'})
    rows = reconcile_history(ledger(site), captured, standard_revisions)
    context = {'current': {**state['current'], 'inventory_record_id': evidence.identity(evidence.parse_json((site / 'report/current/inventory/inventory.json').read_bytes()))}, 'slots': [{'slot': slot, **item} for slot, item in sorted(state['slots'].items())], 'history': rows}
    for value in (state, rows):
        evidence.reports.public_strings(value)
    historical = history.validate(parse((site / 'report/history.json').read_bytes())) if state['schema_version'] == 2 else None
    write(site, 'index.html', report.render_report(saved, captured, pages_context=context, historical=historical))
    write(site, '.nojekyll', b'')
    for member in sorted({row['member'] for row in rows}):
        skill, policy, _ = member.split('/')
        target = '../../index.html#' + report.anchor('history', skill, policy)
        page = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; base-uri \'none\'; form-action \'none\'">'
                '<title>Benchmark history</title></head><body><h1>Benchmark history</h1>'
                f'<p><a href="{target}">Open canonical {skill} history</a></p>'
                '<p><a href="data.js" download>Download the unchanged native ledger</a></p></body></html>')
        write(site, member.removesuffix('data.js') + 'index.html', page.encode())
    allowed = {'index.html', '.nojekyll'}
    allowed.update(row['member'] for row in rows)
    allowed.update(row['member'].removesuffix('data.js') + 'index.html' for row in rows)
    require(all(name.startswith('report/') or name in allowed for name in tree(site)), 'Unexpected publication file')
    return rows


def execution_times(jobs, slot):
    if slot == 'quality':
        name = 'Skill quality (advisory findings)'
    elif slot.startswith('oracle--'):
        name = 'Pester evaluation feasibility (no inference)'
    else:
        name = 'evaluate'
    job = next(j for j in jobs if j['name'] == name)
    return {key: job.get(key) for key in ('started_at', 'completed_at')}


def acquire(api, run, jobs, kind, site, state, workspace, temporary, historical=None, observed_at=None):
    run_id = run['id']; attempt = run['run_attempt']
    artifacts = api.listing(f'actions/runs/{run_id}/artifacts', 'artifacts')
    selected = []
    if kind == 'validate':
        successful_job(jobs, 'Skill quality (advisory findings)', [
            'Enforce native collection and dataset contracts', 'Generate validated public quality evidence and findings summary',
            'Verify evaluator left the checkout unchanged', 'Upload validated public quality evidence'])
        selected.append(('quality', f'skill-public-quality-{run_id}-{attempt}'))
        # Older eligible producers may predate the public-only oracle handoff.
        oracle_name = f'skill-public-oracle-powershell-pester-6-{run_id}-{attempt}'
        if any(item['name'] == oracle_name for item in artifacts):
            successful_job(jobs, 'Pester evaluation feasibility (no inference)', [
                'Qualify native Pester execution and diagnostic containment', 'Verify checkout integrity',
                'Upload validated public Pester oracle evidence'])
            selected.append(('oracle--powershell-pester-6', oracle_name))
    else:
        successful_job(jobs, 'evaluate', ['Validate selection and clean checkout',
            'Run native with-skill and without-skill evaluation', 'Summarize native results and prepare standard metrics',
            'Verify evaluator left the checkout unchanged'])
        pattern = re.compile(r'skill-public-benchmark-(' + NAME + r')-(standard|confirmation)-' + str(run_id) + '-' + str(attempt))
        matches = [(item, pattern.fullmatch(item['name'])) for item in artifacts]
        matches = [(item, match) for item, match in matches if match]
        require(len(matches) <= 1, 'Ambiguous public benchmark handoff')
        if not matches:
            # A standard result may already be validly admitted to the ledger.
            successful_job(jobs, 'publish-history', ['Validate metric allowlist and canonical series',
                'Append standard result to durable history', 'Capture and verify the exact published history commit'])
            require(any(row['revision'] == run['head_sha'] for row in ledger(site)), 'Producer has no admitted ledger measurement')
            return ['Detailed benchmark evidence unavailable; ledger remains authoritative.']
        _, match = matches[0]
        name, mode = match.groups()
        if mode == 'standard':
            successful_job(jobs, 'publish-history', ['Validate metric allowlist and canonical series',
                'Append standard result to durable history', 'Capture and verify the exact published history commit'])
        successful_job(jobs, 'evaluate', ['Generate validated public benchmark evidence',
            'Verify public reporting left the checkout unchanged', 'Upload validated public benchmark evidence'])
        selected.append((('standard' if mode == 'standard' else 'confirmation') + '--' + name, match[0]))
    warnings = []
    for slot, name in selected:
        items = [item for item in artifacts if item['name'] == name]
        if not items or all(item['expired'] for item in items):
            # Missing/expired detail is unavailable; supplied malformed detail is blocking.
            if slot.startswith('standard--'):
                warnings.append('Warning: detailed evidence for this standard producer is unavailable/expired; retained detail is preserved.')
                continue
            raise ValueError('Required public producer artifact unavailable')
        require(len(items) == 1 and not items[0]['expired'], 'Ambiguous/expired public artifact')
        item = items[0]
        number(item['id'])
        require(item['workflow_run']['id'] == run_id and item['workflow_run']['head_sha'] == run['head_sha']
                and item['workflow_run']['head_repository_id'] == run['head_repository']['id'], 'Artifact provenance mismatch')
        raw = api.raw(f'repos/{REPOSITORY}/actions/artifacts/{item["id"]}/zip')
        destination = temporary / slot
        captured = extract_public(raw, item['digest'], destination)
        prov = provenance(run, item)
        records = bundle_claims(captured, slot, prov)
        if slot.startswith('standard--'):
            reconcile_history(ledger(site), captured, {rid: prov['revision'] for rid in captured.records})
        if historical is not None:
            import skill_history as history
            execution = execution_times(jobs, slot)
            for record in records:
                history.add(historical, history.observation(record, slot, prov, observed_at, execution))
        admit(site, state, slot, prov, destination, workspace)
    return warnings


def seal(candidate, parent_sha):
    sha(parent_sha)
    files = tree(candidate / 'benchmarks')
    value = {'schema_version': 1, 'parent_sha': parent_sha,
             'files': {name: digest(raw) for name, raw in files.items()}}
    write(candidate, 'candidate.json', encoded(value))
    return value


def prepare(workspace, retained, output, event_name, event, api=None):
    import skill_evidence as evidence
    require(not output.exists(), 'Preparation output already exists')
    api = api or GitHub()
    repo = api.get('')
    require(repo['full_name'] == REPOSITORY and repo['default_branch'] == 'main', 'Unexpected publisher repository/default branch')
    main_sha = sha(git(workspace, 'rev-parse', 'HEAD'))
    remote_main = sha(api.get('git/ref/heads/main')['object']['sha'])
    require(main_sha == remote_main, 'Main moved after trusted checkout; rerun preparation')
    parent_sha = sha(git(retained, 'rev-parse', 'HEAD'))
    require(parent_sha == api.get('git/ref/heads/gh-pages')['object']['sha'], 'Retained branch moved before preparation')
    requested = request(event_name, event)
    output.mkdir()
    site = output / 'benchmarks'
    if (retained / 'benchmarks').exists():
        tree(retained / 'benchmarks')
        shutil.copytree(retained / 'benchmarks', site)
    else:
        site.mkdir()
    state = load_state(site)
    import skill_history as history
    from datetime import datetime, timezone
    observed_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    historical = history.validate(parse((site / 'report/history.json').read_bytes())) if state['schema_version'] == 2 else history.empty(observed_at)
    if state['schema_version'] == 1:
        import skill_analysis as analysis
        for slot, item in state['slots'].items():
            captured = analysis.capture_inputs([site / f'report/bundles/{slot}'])
            execution = None
            try:
                _, _, jobs = authenticate(api, item['provenance']['run_id'], item['provenance']['attempt'], workspace, main_sha)
                execution = execution_times(jobs, slot)
            except (ValueError, KeyError, StopIteration):
                pass  # Valid retained evidence survives unavailable chronology metadata.
            for record in bundle_claims(captured, slot, item['provenance']):
                history.add(historical, history.observation(record, slot, item['provenance'], observed_at, execution))
    warnings = []
    if requested:
        kind, run, jobs = authenticate(api, *requested, workspace, main_sha)
        with tempfile.TemporaryDirectory(prefix='skill-pages-input-') as temporary:
            warnings = acquire(api, run, jobs, kind, site, state, workspace, Path(temporary), historical, observed_at)
    if state['current'] is not None:
        require(ancestor(workspace, state['current']['revision'], main_sha), 'Current inventory would rewind or diverge')
    current = evidence.inventory(workspace)
    for guard in evidence.record_guards(current):
        guard()
    raw = evidence.encoded(current)
    evidence.reports.public_strings(current)
    write(site, 'report/current/inventory/inventory.json', raw)
    state['current'] = {'revision': main_sha, 'digest': digest(raw)}
    cfg = parse((workspace / '.github/evals/orchestration.json').read_bytes())
    baselines = {(v['reference']['run_id'], v['reference']['attempt']) for v in cfg['suites'].values() if v.get('reference')}
    history.retain(historical, observed_at, baselines)
    history_raw = encoded(historical)
    write(site, 'report/history.json', history_raw)
    state.update(schema_version=2, history_digest=digest(history_raw))
    write(site, 'report/publication.json', encoded(state))
    rows = build(site)
    seal(output, parent_sha)
    missing = sum(row['detail'] == 'ledger_only' for row in rows)
    if missing:
        warnings.append(f'Warning: supporting public detail is unavailable for {missing} admitted measurements; ledger values are preserved.')
    return warnings + [f'Ledger: {len(rows)} admitted measurements; detailed evidence unavailable for {missing}.']


def verify_candidate(candidate, expected_digest=None):
    values = tree(candidate)
    require('candidate.json' in values, 'Candidate seal missing')
    raw_seal = values.pop('candidate.json')
    if expected_digest is not None:
        require(re.fullmatch('[0-9a-f]{64}', expected_digest) and digest(raw_seal) == expected_digest, 'Candidate seal differs from trusted preparation output')
    seal_value = parse(raw_seal)
    require(set(seal_value) == {'schema_version', 'parent_sha', 'files'} and type(seal_value['schema_version']) is int and seal_value['schema_version'] == 1, 'Invalid candidate seal')
    sha(seal_value['parent_sha'])
    actual = {}
    for member, raw in values.items():
        require(member.startswith('benchmarks/'), 'Unexpected candidate path')
        name = member[len('benchmarks/'):]
        require(name in ('index.html', '.nojekyll', 'report/publication.json', 'report/analysis.json',
                         'report/current/inventory/inventory.json', 'report/history.json')
                or SERIES.fullmatch(name) or SERIES.fullmatch(name.removesuffix('index.html') + 'data.js')
                or re.fullmatch(r'report/bundles/(' + SLOT.pattern + r')/(' + PUBLIC.pattern + ')', name), 'Unexpected generated file')
        actual[name] = digest(raw)
    require(actual == seal_value['files'], 'Candidate member hashes differ')
    require(all(name in actual for name in ('index.html', 'report/publication.json', 'report/analysis.json')), 'Candidate incomplete')
    return seal_value


def commit(candidate, checkout, remote=None, *, expected_digest=None):
    """No imports from evaluator; no artifact code execution; no force push."""
    value = verify_candidate(candidate, expected_digest)
    env = os.environ.copy()
    env.update(GIT_AUTHOR_NAME='github-actions[bot]', GIT_AUTHOR_EMAIL='41898282+github-actions[bot]@users.noreply.github.com',
               GIT_COMMITTER_NAME='github-actions[bot]', GIT_COMMITTER_EMAIL='41898282+github-actions[bot]@users.noreply.github.com')
    if remote is None:
        remote = f'https://github.com/{REPOSITORY}.git'
        token = os.environ['GH_TOKEN']
        auth = base64.b64encode(('x-access-token:' + token).encode()).decode()
        env.update(GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',
                   GIT_CONFIG_VALUE_0='AUTHORIZATION: basic ' + auth)
    checkout.mkdir()
    git(checkout, 'init', '--quiet', env=env)
    git(checkout, 'remote', 'add', 'origin', remote, env=env)
    git(checkout, 'fetch', '--quiet', 'origin', 'refs/heads/gh-pages', env=env)
    require(git(checkout, 'rev-parse', 'FETCH_HEAD') == value['parent_sha'], 'Publication branch moved; rebuild without force-pushing')
    git(checkout, 'checkout', '--quiet', '-b', 'gh-pages', 'FETCH_HEAD', env=env)
    # Native ledger bytes are immutable for the reporting publisher.
    previous = tree(checkout / 'benchmarks') if (checkout / 'benchmarks').exists() else {}
    incoming = tree(candidate / 'benchmarks')
    require({name: raw for name, raw in previous.items() if name.endswith('/data.js')}
            == {name: raw for name, raw in incoming.items() if name.endswith('/data.js')}, 'Candidate changed native history')
    if (checkout / 'benchmarks').exists():
        shutil.rmtree(checkout / 'benchmarks')
    shutil.copytree(candidate / 'benchmarks', checkout / 'benchmarks')
    git(checkout, 'add', '--', 'benchmarks', env=env)
    if git(checkout, 'diff', '--cached', '--name-only'):
        git(checkout, 'commit', '--quiet', '-m', 'Publish consolidated skill report', env=env)
        git(checkout, 'push', '--quiet', 'origin', 'HEAD:refs/heads/gh-pages', env=env)
    revision = sha(git(checkout, 'rev-parse', 'HEAD'))
    require(git(checkout, 'ls-remote', 'origin', 'refs/heads/gh-pages', env=env).split()[0] == revision, 'Exact remote publication SHA mismatch')
    return revision


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare')
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--retained', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p = commands.add_parser('build')
    p.add_argument('--site', type=Path, required=True)
    p = commands.add_parser('commit')
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--checkout', type=Path, required=True)
    p.add_argument('--seal-digest', required=True)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        messages = prepare(args.workspace.absolute(), args.retained.absolute(), args.output.absolute(),
                           os.environ['GITHUB_EVENT_NAME'], parse(Path(os.environ['GITHUB_EVENT_PATH']).read_bytes()))
        summary = '\n'.join(messages + ['Site deployment: pending exact-commit deployment job.']) + '\n'
        print(summary)
        for message in messages:
            if message.startswith('Warning: '):
                print('::warning::' + message.removeprefix('Warning: '))
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
            stream.write('candidate_sha256=' + digest((args.output / 'candidate.json').read_bytes()) + '\n')
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as stream:
                stream.write(summary)
    elif args.command == 'build':
        build(args.site.absolute())
    else:
        revision = commit(args.candidate.absolute(), args.checkout.absolute(), expected_digest=args.seal_digest)
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
            stream.write('publication_sha=' + revision + '\n')


if __name__ == '__main__':
    try:
        main()
    except PublicationError as error:
        raise SystemExit('Pages publication rejected: ' + str(error) + '. Inspect durable commit and site deployment outcomes separately.')
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile, subprocess.SubprocessError):
        raise SystemExit('Pages publication failed validation; retained/live state is unchanged unless the durable commit step already succeeded.')
