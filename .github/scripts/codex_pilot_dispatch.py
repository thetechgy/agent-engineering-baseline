"""Authenticate one existing cohort preparation and claim one Actions dispatch.

Only GitHub read APIs are used. No model secret or environment approval is needed.
Downloaded files are bounded data; nothing in an artifact is executed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import zipfile

from codex_pilot_contract import ROOT
from codex_pilot_cohort import PROTOCOL, allocation, no_credentials, revision
import skill_reports as reports

REPO = 'thetechgy/agent-engineering-baseline'
REPO_ID = 1299967456
WORKFLOW = '.github/workflows/codex-pilot.yml'
LIMIT = 64 * 1024**2


def api(path):
    return json.loads(subprocess.check_output(['gh', 'api', f'repos/{REPO}/{path}'], text=True, timeout=60))


def authenticate_metadata(artifact, run, source):
    origin = artifact.get('workflow_run', {})
    reports.require(run.get('repository',{}).get('id') == REPO_ID
                    and run['repository']['full_name'] == REPO
                    and run.get('head_repository',{}).get('id') == REPO_ID
                    and origin.get('repository_id') == origin.get('head_repository_id') == REPO_ID
                    and origin.get('id') == run.get('id') and origin.get('head_sha') == run.get('head_sha') == source
                    and run.get('path') == WORKFLOW and run.get('event') in ('pull_request', 'workflow_dispatch')
                    and run.get('status') == 'completed' and run.get('conclusion') == 'success'
                    and artifact.get('name') == f'pester-effectiveness-preparation-{run["run_attempt"]}'
                    and artifact.get('expired') is False and type(artifact.get('size_in_bytes')) is int
                    and 0 < artifact['size_in_bytes'] <= LIMIT and re.fullmatch(r'sha256:[0-9a-f]{64}', artifact.get('digest','')),
                    'Preparation artifact producer/source authentication failed')


def first_dispatch(runs, approval, run_id):
    matching = [r for r in runs if r.get('display_title') == 'Codex cohort ' + approval]
    reports.require(matching and min(r['id'] for r in matching) == int(run_id), 'Allocation already claimed by a different dispatch')
    current = next((r for r in matching if r['id'] == int(run_id)), {})
    reports.require(current.get('run_attempt') == 1 and current.get('event') == 'workflow_dispatch', 'Workflow replay refused')


def extract(archive, target, metadata):
    reports.require(archive.stat().st_size == metadata['size_in_bytes'] and archive.stat().st_size <= LIMIT
                    and 'sha256:' + hashlib.sha256(archive.read_bytes()).hexdigest() == metadata['digest'], 'Archive digest mismatch')
    target.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as bundle:
        entries = bundle.infolist(); seen = set()
        reports.require(len(entries) <= 20000 and sum(e.file_size for e in entries) <= 256*1024**2, 'Archive expansion limit')
        for entry in entries:
            path = PurePosixPath(entry.filename); mode = entry.external_attr >> 16
            reports.require(entry.filename and not path.is_absolute() and '..' not in path.parts
                            and '\\' not in entry.filename and ':' not in entry.filename
                            and str(path) not in seen and not stat.S_ISLNK(mode)
                            and stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR) and entry.file_size <= 32*1024**2,
                            'Unsafe archive member')
            seen.add(str(path)); destination = target.joinpath(*path.parts)
            if entry.is_dir(): destination.mkdir(parents=True, exist_ok=True); continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('xb') as stream: stream.write(bundle.read(entry))


def authenticate(output, approval):
    no_credentials()
    reports.require(os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('GITHUB_REPOSITORY') == REPO,
                    'Cohort dispatch must use the reviewed Actions workflow')
    match = re.fullmatch(f'cohort-{revision()}-{PROTOCOL}-prep([1-9][0-9]*)-usd15-([A-Za-z0-9_-]{{8,40}})', approval)
    reports.require(match is not None, 'Invalid or stale cohort allocation')
    artifact_id, dispatch = match.groups()
    allocation(approval, revision(), artifact_id, dispatch)
    run_id = os.environ['GITHUB_RUN_ID']
    current = api('actions/runs/' + run_id)
    reports.require(current['head_sha'] == revision() and current['path'] == WORKFLOW
                    and current['repository']['id'] == REPO_ID, 'Dispatch source mismatch')
    runs = []
    for page in range(1, 101):
        batch = api(f'actions/workflows/codex-pilot.yml/runs?event=workflow_dispatch&per_page=100&page={page}')['workflow_runs']
        runs.extend(batch)
        if len(batch) < 100: break
    else: raise ValueError('Incomplete dispatch history; cannot prove unique allocation')
    first_dispatch(runs, approval, run_id)
    artifact = api('actions/artifacts/' + artifact_id)
    producer = api('actions/runs/' + str(artifact['workflow_run']['id']))
    authenticate_metadata(artifact, producer, revision())
    output.mkdir(parents=True, exist_ok=False)
    archive = output / 'preparation.zip'
    with archive.open('xb') as stream:
        subprocess.run(['gh', 'api', f'repos/{REPO}/actions/artifacts/{artifact_id}/zip'], stdout=stream, check=True, timeout=120)
    extract(archive, output / 'downloaded', artifact)
    reference = output / 'downloaded/pester-effectiveness/evidence'
    reports.require(reports.read_json(reference / 'scheduler-qualification.json').get('revision') == revision(), 'Unqualified cohort source')
    receipt = {'artifact': artifact_id, 'artifact_digest': artifact['digest'], 'producer_run': producer['id'],
               'revision': revision(), 'protocol': PROTOCOL, 'dispatch': dispatch, 'run_id': run_id, 'allocation': approval,
               'first_dispatch': True, 'authentication': 'github-api-producer-and-digest'}
    reports.write_json(reference / 'dispatch-authentication.json', receipt)
    reports.write_json(output / 'producer-run.json', producer)
    reports.write_json(output / 'artifact.json', artifact)
    return reference


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--approval', required=True)
    args = parser.parse_args()
    authenticate(args.output, args.approval)
