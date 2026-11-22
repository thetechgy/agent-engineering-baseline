"""Credential-free qualification of the real allocation-bound CLI, with fixture gh IO.

No network fallback, live action, credential, or real claim is permitted. Fixture
receipts live only in disposable storage and are never published as authorization.
"""
import argparse
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

import evaluation_campaign_protocol as protocol
from evaluation_campaign_selection import binding, registration, selected_task, owning_evaluator
from evaluation_runtime import ROOT
import evaluator_profiles as profiles
import skill_reports as reports

CASES = ('accepted', 'wrong-source', 'wrong-campaign', 'wrong-protocol', 'wrong-producer',
         'tampered-archive', 'task-identity', 'expired-artifact', 'mismatched-authority',
         'duplicate-dispatch', 'replayed-dispatch', 'incomplete-preparation',
         'missing-dependency', 'receipt-write-failure', 'incomplete-receipt',
         'missing-proof', 'incomplete-proof', 'injected-receipt')


def case_names(task):
    return (CASES + (('expired-authority',) if protocol.protocol(task).get('authorization_expires_at') else ())
            + (('closed-allocation', 'wrong-artifact', 'wrong-corpus', 'wrong-profile') if task.definition.get('type') == 'judge-only' else ()))


def expected(task):
    owner = owning_evaluator(task)
    return {'version': 1, 'revision': protocol.revision(), 'campaign': task.definition['id'],
            **binding(task), 'protocol_digest': protocol.digest(ROOT / task.definition['protocol']),
            'runtime': profiles.candidate_versions(owner), 'python': owner['python'],
            'entry_point': '.github/scripts/evaluation_campaign_selection.py',
            'implementation': {name: protocol.digest(ROOT / '.github/scripts' / name) for name in
                ('setup-campaign-authentication.sh', 'campaign_authentication_qualification.py',
                 'evaluation_campaign_selection.py', 'evaluation_campaign_protocol.py')},
            'fixture_only': True, 'live_authority': False, 'network': False}


def validate(proof, task):
    reports.require(proof == {**expected(task), 'complete': True, 'inference': False,
                              'cases': {name: 'passed' for name in case_names(task)}},
                    'Incomplete or stale authentication CLI qualification')


GH = '''#!/usr/bin/env python3
import json, os, pathlib, sys
root=pathlib.Path(os.environ['AUTHENTICATION_FIXTURE'])
args=sys.argv[1:]
if len(args)!=2 or args[0]!='api': raise SystemExit('Fixture gh refuses non-API IO')
path=args[1]
with (root/'calls.jsonl').open('a') as f: f.write(json.dumps(args)+'\\n')
if path.endswith('/actions/artifacts/7000002/zip'):
 sys.stdout.buffer.write((root/'fixture.zip').read_bytes())
else:
 data=json.loads((root/'api.json').read_text())
 if path not in data: raise SystemExit('Fixture gh refuses unknown API')
 print(json.dumps(data[path]))
'''

# This changes only the failing persistence boundary. Parsing, selection,
# authenticate, frozen identities, member generation and admission stay real.
WRITE_FAILURE = '''import pathlib, runpy, sys
sys.path.insert(0, str(pathlib.Path(sys.argv[1]).parent))
import skill_reports
original=skill_reports.write_json
def fail(path, value):
 if path.name == 'dispatch-authentication.pending':
  if __import__('os').environ.get('FIXTURE_WRITE_MODE') == 'incomplete-receipt':
   return original(path,{k:v for k,v in value.items() if k != 'producer_run'})
  path.parent.mkdir(parents=True,exist_ok=True)
  path.write_text('{"partial":')
  raise OSError('fixture receipt persistence failure')
 return original(path,value)
skill_reports.write_json=fail
sys.argv=sys.argv[1:]
runpy.run_path(sys.argv[0],run_name='__main__')
'''


MISSING_OWNER = """import pathlib, runpy, sys
sys.path.insert(0, str(pathlib.Path(sys.argv[1]).parent))
from evaluation_campaign_selection import selected_task, owning_evaluator
import evaluator_profiles as profiles
# This is the same owning guard used by setup-campaign-authentication.sh.
# Some adapters compute metadata without evaluator imports, but the workflow's
# mandatory setup must still reject absent owning dependencies before its CLI.
campaign=sys.argv[sys.argv.index('--campaign')+1]
owner=owning_evaluator(selected_task(campaign))
profiles.runtime(profiles.candidate_versions(owner),owning=True)
sys.argv=sys.argv[1:]
runpy.run_path(sys.argv[0],run_name='__main__')
"""


EXPIRED = """import datetime, pathlib, runpy, sys
sys.path.insert(0, str(pathlib.Path(sys.argv[1]).parent))
import evaluation_campaign_protocol as protocol
class Clock(datetime.datetime):
 @classmethod
 def now(cls,tz=None): return datetime.datetime(2099,1,1,tzinfo=datetime.timezone.utc)
protocol.datetime=Clock
sys.argv=sys.argv[1:]
runpy.run_path(sys.argv[0],run_name='__main__')
"""

ERRORS = {'wrong-source': 'Dispatch source mismatch', 'wrong-campaign': 'Exact allocation and first dispatch attempt required',
          'wrong-protocol': 'Unqualified source artifact', 'wrong-producer': 'Unregistered preparation producer/layout',
          'tampered-archive': 'digest mismatch', 'task-identity': 'Unqualified source artifact',
          'expired-artifact': 'Preparation producer authentication failed', 'mismatched-authority': 'Allocation already claimed',
          'duplicate-dispatch': 'Allocation already claimed', 'replayed-dispatch': 'Exact allocation and first dispatch attempt required',
          'incomplete-preparation': 'Incomplete preparation', 'missing-dependency': 'No package metadata was found for skillevaluator',
          'receipt-write-failure': 'fixture receipt persistence failure', 'incomplete-receipt': 'Stale or unauthenticated campaign receipt',
          'missing-proof': 'Missing or linked JSON report: authentication-qualification.json',
          'incomplete-proof': 'Incomplete or stale authentication CLI qualification',
          'injected-receipt': 'Preparation contains dispatch authorization',
          'expired-authority': 'Campaign authorization expired', 'closed-allocation': 'Allocation already claimed',
          'wrong-artifact': 'Preparation artifact identity mismatch', 'wrong-corpus': 'Unqualified source artifact',
          'wrong-profile': 'Unqualified source artifact'}


def fixture(root, task, name, preparation=None):
    """Build independently bound test data, never a real preparation or claim."""
    source = protocol.revision(); repo = {'id': 1299967456, 'full_name': protocol.REPO}
    producer_spec = registration(task)['producers'][0]
    producer = {'id': 7000001, 'repository': repo, 'head_repository': repo, 'head_sha': source,
                'path': producer_spec['workflow'], 'event': 'pull_request', 'status': 'completed',
                'conclusion': 'success', 'run_attempt': 1}
    approval = (f'campaign-{source}-{task.definition["id"]}-prep7000002-'
                f'usd{protocol.protocol(task)["budget"]["planning_allocation_usd"]}-fixture_only_7000003')
    current = {**producer, 'id': 7000003, 'path': protocol.WORKFLOW, 'event': 'workflow_dispatch',
               'display_title': 'Evaluation campaign ' + approval}
    proposal = copy.deepcopy(protocol.frozen(task))
    ready = {'complete': True, 'inference': False, 'revision': source,
             'protocol_digest': proposal['protocol_digest'], 'authorized_live_attempts': 0}
    # Fixture preparation documents exercise admission; they make no assertion
    # that native qualification ran. Only the final outer proof is qualification.
    files = {'frozen-proposal.json': proposal, 'preparation.json': ready,
             'scheduler-qualification.json': {**ready, 'scenarios': {n: {} for n in protocol.scenarios(task)}},
             'authentication-qualification.json': {**expected(task), 'complete': True,
                 'inference': False, 'cases': {n: 'passed' for n in case_names(task)}}}
    if name == 'wrong-protocol': proposal['protocol_digest'] = 'sha256:' + '0'*64
    if name == 'task-identity': proposal['source_identities']['live']['fixture_digest'] = 'sha256:' + '0'*64
    if name == 'wrong-corpus': proposal['source_identities']['live'][task.definition['corpus']] = 'sha256:' + '0'*64
    if name == 'wrong-profile': proposal['evaluator']['patch_sha256'] = '0'*64
    if name == 'incomplete-preparation': ready['complete'] = False
    if name == 'missing-proof': del files['authentication-qualification.json']
    if name == 'incomplete-proof': files['authentication-qualification.json']['complete'] = False
    if name == 'injected-receipt': files['dispatch-authentication.json'] = {'fixture_only': True}
    location = producer_spec['location']
    archive = root/'fixture.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        if preparation is not None:
            reports.require(name == 'accepted', 'Actual preparation is only the positive authentication control')
            for path in reports.regular_tree(preparation.parent):
                bundle.write(path, str(Path(location).parent / path.relative_to(preparation.parent)))
        else:
            for member, value in files.items(): bundle.writestr(location + '/' + member, json.dumps(value))
    artifact = {'id': 7000002, 'workflow_run': {'id': producer['id'], 'repository_id': repo['id'],
                'head_repository_id': repo['id'], 'head_sha': source},
                'name': producer_spec['artifact'] + '-1', 'expired': False,
                'expires_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                'size_in_bytes': archive.stat().st_size,
                'digest': 'sha256:' + hashlib.sha256(archive.read_bytes()).hexdigest()}
    if name == 'wrong-source': current['head_sha'] = '0'*40
    if name == 'wrong-producer': producer['path'] = '.github/workflows/unregistered.yml'
    if name == 'tampered-archive': archive.write_bytes(archive.read_bytes() + b'tamper')
    if name == 'expired-artifact': artifact['expires_at'] = '2000-01-01T00:00:00Z'
    if name == 'wrong-artifact': artifact['id'] = 7000009
    history = [current]
    if name == 'duplicate-dispatch': history.append({**current, 'id': 7000000})
    if name == 'closed-allocation': history.append({**current, 'id': 7000000, 'status': 'completed', 'conclusion': 'cancelled'})
    if name == 'replayed-dispatch': current['run_attempt'] = 2
    data = {'actions/runs/7000003': current, 'actions/runs/7000001': producer,
            'actions/artifacts/7000002': artifact,
            'actions/workflows/evaluation-campaign.yml/runs?event=workflow_dispatch&per_page=100&page=1': {'workflow_runs': history}}
    reports.write_json(root/'api.json', {'repos/' + protocol.REPO + '/' + k: v for k,v in data.items()})
    (root/'gh').write_text(GH); (root/'gh').chmod(0o700)
    env = {k: os.environ[k] for k in ('PATH', 'TMPDIR', 'LANG', 'SYSTEMROOT') if k in os.environ}
    env.update(getattr(task, 'selector', {}))
    env.update(PATH=str(root) + os.pathsep + env.get('PATH', '/usr/bin:/bin'),
        HOME=str(root), GITHUB_ACTIONS='true', GITHUB_REPOSITORY=protocol.REPO,
        GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_RUN_ATTEMPT='2' if name == 'replayed-dispatch' else '1',
        GITHUB_RUN_ID='7000003', GITHUB_JOB='authentication-qualification', RUNNER_TEMP=str(root),
        AUTHENTICATION_FIXTURE=str(root), PYTHONDONTWRITEBYTECODE='1')
    if name == 'mismatched-authority': approval += '_mismatch'
    return approval, env


def run_case(root, task, name, *, python=None, preparation=None):
    root.mkdir()
    approval, env = fixture(root, task, name, preparation)
    output = root/'authentication'
    campaign = task.definition["id"]
    if campaign == "case-observation":
        campaign = "case-observation-1691"
    command = [python or sys.executable]
    if name == 'missing-dependency': command.append('-S')
    command += ['-B']
    if name in ('receipt-write-failure', 'incomplete-receipt'):
        bootstrap = root/'write-failure.py'; bootstrap.write_text(WRITE_FAILURE); command.append(str(bootstrap))
        env['FIXTURE_WRITE_MODE'] = name
    if name == 'missing-dependency':
        bootstrap = root/'missing-owner.py'; bootstrap.write_text(MISSING_OWNER); command.append(str(bootstrap))
    if name == 'expired-authority':
        bootstrap = root/'expired.py'; bootstrap.write_text(EXPIRED); command.append(str(bootstrap))
    command += [str(ROOT/'.github/scripts/evaluation_campaign_selection.py'), 'authenticate',
                '--campaign', ('gh-runtime-090-v1' if task.definition['id'].startswith('boolean-effectiveness-') else 'boolean-effectiveness-v1') if name == 'wrong-campaign' else campaign,
                '--approval', approval, '--output', str(output)]
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=120)
    receipt_path = output/'downloaded/preparation/evidence/dispatch-authentication.json'
    if name == 'accepted':
        reports.require(result.returncode == 0, 'Actual authentication CLI failed: ' + result.stderr[-4000:])
        receipt = reports.read_json(receipt_path)
        # Round-trip precisely the production authentication artifact layout as
        # data, then use the actual downstream receipt validator. No live entry.
        packed = root/'authenticated.zip'
        with zipfile.ZipFile(packed, 'w') as bundle:
            for path in reports.regular_tree(output): bundle.write(path, path.relative_to(output))
        from codex_pilot_dispatch import extract
        extract(packed, root/'consumer', {'size_in_bytes': packed.stat().st_size,
            'digest': 'sha256:' + hashlib.sha256(packed.read_bytes()).hexdigest()})
        consumed = reports.read_json(root/'consumer/downloaded/preparation/evidence/dispatch-authentication.json')
        from unittest.mock import patch
        with patch.dict(os.environ, env, clear=True):
            protocol.validate_receipt(consumed, approval, task)
            for missing in consumed:
                try: protocol.validate_receipt({k:v for k,v in consumed.items() if k != missing}, approval, task)
                except (ValueError, TypeError): pass
                else: raise ValueError('Incomplete receipt admitted: ' + missing)
            # Isolated fixture authority must not authorize a real live job.
            try: protocol.runtime_gate(task)
            except ValueError: pass
            else: raise ValueError('Fixture unexpectedly authorized live execution')
        reports.require(receipt == consumed, 'Authentication artifact round-trip differs')
    else:
        reports.require(result.returncode != 0, 'Invalid authentication unexpectedly succeeded: ' + name)
        reports.require(not list(output.rglob('dispatch-authentication.*')), 'Failed authentication retained receipt: ' + name)
        reports.require(ERRORS[name] in result.stderr, 'Wrong rejection for ' + name + ': ' + result.stderr[-1500:])
        if name == 'missing-dependency':
            reports.require(not output.exists(), 'Missing owner crossed the mandatory setup boundary')
        else:
            failure = reports.read_json(output/'authentication-failure.json')
            reports.require(failure.get('complete') is False and failure.get('authorization_produced') is False,
                            'Failed authentication lacks bounded diagnostic: ' + name)
    reports.require(not list(root.glob('campaign-claim-*')), 'Fixture left a live claim')
    return {'returncode': result.returncode, 'receipt_present': receipt_path.exists(),
            'stderr': result.stderr[-4000:]}


def qualify(output, task):
    from evaluation_campaign import no_credentials
    no_credentials()
    owner = owning_evaluator(task)
    profiles.runtime(profiles.candidate_versions(owner), owning=True)
    output.mkdir(parents=True, exist_ok=False)
    result = {**expected(task), 'complete': False, 'inference': False, 'cases': {}}
    # These values come from the interpreter actually running this qualification.
    from importlib.metadata import version
    result['python'] = '.'.join(map(str, sys.version_info[:3]))
    result['runtime'].update(skillevaluator=version('skillevaluator'), harbor=version('harbor'))
    reports.write_json(output/'authentication-qualification.json', result)
    with tempfile.TemporaryDirectory(prefix='campaign-auth-fixtures-') as directory:
        for name in case_names(task):
            try: run_case(Path(directory)/name, task, name)
            except BaseException as exc:
                reports.write_json(output/'authentication-qualification.json', result)
                reports.write_json(output/'qualification-failure.json', {'complete': False, 'case': name,
                    'error_type': type(exc).__name__, 'inference': False})
                raise
            result['cases'][name] = 'passed'
    result['complete'] = True
    validate(result, task)
    reports.write_json(output/'authentication-qualification.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.absolute()
    reports.require(output.resolve() == output and not output.exists() and not output.is_relative_to(ROOT),
                    'New qualification output outside checkout required')
    qualify(output, selected_task(args.campaign))


if __name__ == '__main__': main()
