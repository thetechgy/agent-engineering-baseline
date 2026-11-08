#!/usr/bin/env python3
"""Credential-free replay of one authenticated immutable live-output corpus."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

from codex_pilot_contract import ROOT

RUN = 42448389611
ARTIFACT = 13605202225
REVISION = '633014bdbc4e9df3b37955950a6ef9efa1473547'
ARCHIVE_SHA = '2f67c417dfad3f04f9015ff580c75eded5223240a15e4adb83a6b886c5dbec99'
CORPUS = '.github/evals/codex-retrospective/42448389611'
MANIFEST_SHA = '75ce871fdbd0f0f8d3f8df36e2b1659d7c65b242b23ca9b8ce0b23a0cf8507dd'
SUBMISSIONS = {
    'with_skill': 'd265ce3f26d8a4d3bb630927153ebc4527cd00876aed8ddec5583ec54c4a4a03',
    'without_skill': '406dac7a20ca8912bed39a2c4ad1293dc0eba405c8814ef160faef851630bce5',
}
ORIGINAL_RECORD = 'sha256:1f790f911b84ca62f005914a255da7bba53e8a90a331eb8953e67be125295593'
ORIGINAL_CAPTURE = 'sha256:9a785ac5f3d2c95deb13afa2da8b5bf4e7d07dc814687dd75db05dd751a33794'


def retrospective_metadata():
    return {'source_run': RUN, 'source_artifact': ARTIFACT, 'source_revision': REVISION,
            'source_archive_sha256': 'sha256:' + ARCHIVE_SHA,
            'original_record_id': ORIGINAL_RECORD, 'original_capture_digest': ORIGINAL_CAPTURE,
            'submission_digests': {arm: 'sha256:' + value for arm, value in SUBMISSIONS.items()},
            'after_output_inspection': True, 'new_inference': False}


def validate_retrospective(value):
    if value != retrospective_metadata():
        raise ValueError('Retrospective source or submission identity mismatch')


def corpus(workspace=ROOT):
    import skill_evidence as evidence
    root = workspace / CORPUS
    manifest_raw = evidence.read_bytes(root / 'manifest.json')
    if hashlib.sha256(manifest_raw).hexdigest() != MANIFEST_SHA:
        raise ValueError('Immutable replay manifest changed')
    manifest = json.loads(manifest_raw)
    expected_members = {row['member'] for row in manifest['files']} | {'manifest.json'}
    if {p.relative_to(root).as_posix() for p in evidence.safe_tree(root)} != expected_members:
        raise ValueError('Unexpected replay corpus member')
    for row in manifest['files']:
        member = PurePosixPath(row['member'])
        if member.is_absolute() or '..' in member.parts or '\\' in row['member']:
            raise ValueError('Invalid replay corpus member')
        raw = evidence.read_bytes(root.joinpath(*member.parts))
        if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Immutable replay corpus changed')
    submissions = {arm: evidence.read_bytes(root / arm / 'Subject.Tests.ps1') for arm in SUBMISSIONS}
    if any(hashlib.sha256(raw).hexdigest() != SUBMISSIONS[arm] for arm, raw in submissions.items()):
        raise ValueError('Retained submission digest mismatch')
    original = evidence.read_json(root / 'original-public-report.json')
    evidence.validate_custom_evidence(original, public=True)
    if evidence.identity(original) != ORIGINAL_RECORD or original['custom']['capture_digest'] != ORIGINAL_CAPTURE:
        raise ValueError('Original public identity mismatch')
    if any(o['custom']['outcome'] != 'unsupported' or o['custom']['admission_reason'] != 'ast_kind'
           or o['score'] is not None or any(m['value'] is not None for m in o['custom']['measurements'])
           for o in original['observations']):
        raise ValueError('Original unmeasured outcomes changed')
    return root, manifest, submissions, original



def verify_original_copy(directory, workspace=ROOT):
    import skill_evidence as evidence
    root, manifest, _, _ = corpus(workspace)
    expected = {row['member'] for row in manifest['files']} | {'manifest.json'}
    if {p.relative_to(directory).as_posix() for p in evidence.safe_tree(directory)} != expected:
        raise ValueError('Original evidence copy is incomplete')
    for member in expected:
        if evidence.read_bytes(directory / member) != evidence.read_bytes(root / member):
            raise ValueError('Original evidence bytes changed')


def fetch(output):
    """Fresh GitHub authentication; the archive is data, not a program source."""
    output.mkdir(parents=True)
    prefix = 'repos/thetechgy/agent-engineering-baseline/'
    def api(path):
        return json.loads(subprocess.check_output(['gh', 'api', prefix + path], text=True))
    artifact, run = api('actions/artifacts/' + str(ARTIFACT)), api('actions/runs/' + str(RUN))
    origin = artifact['workflow_run']
    if not (origin['id'] == RUN and origin['head_sha'] == run['head_sha'] == REVISION
            and origin['repository_id'] == origin['head_repository_id'] == 1299967456
            and run['run_attempt'] == 1 and run['event'] == 'workflow_dispatch'
            and run['path'] == '.github/workflows/codex-pilot.yml' and run['conclusion'] == 'success'
            and not artifact['expired'] and artifact['size_in_bytes'] <= 32*1024**2
            and artifact['digest'] == 'sha256:' + ARCHIVE_SHA):
        raise ValueError('Original workflow artifact authentication failed')
    for name, value in (('artifact.json', artifact), ('run.json', run)):
        (output / name).write_text(json.dumps(value, indent=2) + '\n')
    archive = output / 'live.zip'
    with archive.open('xb') as stream:
        subprocess.run(['gh', 'api', prefix + 'actions/artifacts/' + str(ARTIFACT) + '/zip'], stdout=stream, check=True)
    verify_archive(archive)


def verify_archive(archive, workspace=ROOT):
    """Match permanent originals to authenticated bytes without executing or extracting code."""
    import stat
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA:
        raise ValueError('Original artifact digest mismatch')
    root, manifest, _, _ = corpus(workspace)
    with zipfile.ZipFile(archive) as bundle:
        if len(bundle.infolist()) > 2000 or sum(m.file_size for m in bundle.infolist()) > 128*1024**2:
            raise ValueError('Original artifact limits exceeded')
        seen = set()
        for item in bundle.infolist():
            path = PurePosixPath(item.filename)
            if (path.is_absolute() or '..' in path.parts or '\\' in item.filename or item.filename in seen
                    or path.as_posix() != item.filename.rstrip('/') or item.flag_bits & 1
                    or stat.S_IFMT(item.external_attr >> 16) not in (0, stat.S_IFREG, stat.S_IFDIR)
                    or item.file_size > 16*1024**2):
                raise ValueError('Unsafe original artifact member')
            seen.add(item.filename)
        prefix = 'pilot-live/evidence/'
        entries = json.loads(bundle.read(prefix + 'submissions.json'))
        if len(entries) != 2:
            raise ValueError('Original submission cardinality mismatch')
        for entry in entries:
            arm = 'with_skill' if '/powershell-pester-6-codex-with/' in '/' + entry['member'] else 'without_skill'
            raw = bundle.read(prefix + entry['member'])
            if hashlib.sha256(raw).hexdigest() != SUBMISSIONS[arm] or raw != (root / arm / 'Subject.Tests.ps1').read_bytes():
                raise ValueError('Original submission bytes changed')
        comparisons = {'original-inventory.json': 'public/inventory/inventory.json', 'original-outcomes.json': 'outcomes.json',
                       'original-grading-outcomes.json': 'grading-outcomes.json',
                       'original-public-report.json': 'public/skills/powershell-pester-6/behavioral/live-pilot/public-report.json'}
        for local, member in comparisons.items():
            if (root / local).read_bytes() != bundle.read(prefix + member):
                raise ValueError('Original outcome bytes changed')
    return {'source_run': RUN, 'source_artifact': ARTIFACT, 'archive_sha256': 'sha256:' + ARCHIVE_SHA,
            'permanent_manifest_sha256': 'sha256:' + MANIFEST_SHA, 'submission_hashes_verified': True,
            'original_outcomes_unchanged': True}


def original_public(output):
    """Preserve the original record in the existing public reporting layout."""
    _, _, _, original = corpus()
    folder = output / 'skills/powershell-pester-6/behavioral/live-pilot'; folder.mkdir(parents=True)
    raw = (ROOT / CORPUS / 'original-public-report.json').read_bytes()
    (folder / 'public-report.json').write_bytes(raw)
    inventory = output / 'inventory'; inventory.mkdir()
    (inventory / 'inventory.json').write_bytes((ROOT / CORPUS / 'original-inventory.json').read_bytes())
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('fetch', 'replay'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--authenticated', type=Path)
    args = parser.parse_args()
    if any(os.environ.get(key) for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'NVIDIA_API_KEY')):
        parser.error('Credential-free replay received model credentials')
    if args.action == 'fetch':
        fetch(args.output); return
    if args.authenticated is None:
        parser.error('Authenticated original artifact required')
    proof = verify_archive(args.authenticated / 'live.zip')
    import evaluator_profiles as profiles
    import codex_pilot as pilot
    import skill_reports as reports
    from qualify_evaluator_candidate import native_compose_config
    profiles.runtime(profiles.candidate_versions(), owning=True)
    native_compose_config(ROOT)
    args.output.mkdir(parents=True)
    evidence = args.output / 'evidence'; evidence.mkdir()
    original = original_public(evidence / 'original-public')
    reports.write_json(evidence / 'original-authentication.json', proof)
    # Preserve originals and their source archive even when replay is incomplete.
    import shutil
    shutil.copytree(ROOT / CORPUS, evidence / 'original')
    shutil.copyfile(args.authenticated / 'live.zip', evidence / 'original-live.zip')
    for name in ('artifact.json', 'run.json'):
        shutil.copyfile(args.authenticated / name, evidence / ('original-source-' + name))
    _, _, submissions, _ = corpus()
    pilot.run(args.output, replay=retrospective_metadata(), submissions=submissions, original_public=original)
    outcomes = reports.read_json(evidence / 'grading-outcomes.json')
    complete = len(outcomes) == 2 and all(o['outcome'].get('classification') in ('passed', 'failed')
        and o['outcome'].get('mutants_executed') == 2
        and o['outcome'].get('powershell_version') == '7.6.9'
        and o['outcome'].get('pester_version') == '6.2.0' for o in outcomes)
    reports.write_json(evidence / 'replay-check.json', {'complete': complete,
        'retrospective': retrospective_metadata(), 'inference': False, 'originals_preserved': True})
    if not complete:
        raise ValueError('Retrospective paired grading incomplete; original and native outcomes retained')


if __name__ == '__main__':
    main()
