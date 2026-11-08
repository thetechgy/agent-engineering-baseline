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
PROVENANCE = CORPUS + '-provenance-v1.json'
PROVENANCE_SHA = 'c6cb6a8f3b05ea59984cc6ccb5fef3dc2778e1d1e6b0f65ac02722029a91056c'
REPLAY_PRODUCER = 'codex-retained-replay-v2'
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


def validate_source(artifact, run, repository):
    """Check source identities, independently of current remote availability."""
    origin = artifact['workflow_run']
    if not (artifact['id'] == ARTIFACT and artifact['name'] == 'codex-pilot-live-1'
            and origin['id'] == run['id'] == RUN
            and origin['head_sha'] == run['head_sha'] == REVISION
            and origin['repository_id'] == origin['head_repository_id'] == repository['id'] == 1299967456
            and repository['full_name'] == 'thetechgy/agent-engineering-baseline'
            and run['run_attempt'] == 1 and run['event'] == 'workflow_dispatch'
            and run['path'] == '.github/workflows/codex-pilot.yml'
            and run['status'] == 'completed' and run['conclusion'] == 'success'
            and 0 < artifact['size_in_bytes'] <= 32*1024**2
            and artifact['digest'] == 'sha256:' + ARCHIVE_SHA):
        raise ValueError('Original workflow artifact authentication failed')


def retained_provenance(workspace=ROOT):
    """Repository-reviewed authentication snapshot; never a fresh GitHub check."""
    import skill_evidence as evidence
    root, manifest, _, _ = corpus(workspace)
    raw = evidence.read_bytes(workspace / PROVENANCE)
    if hashlib.sha256(raw).hexdigest() != PROVENANCE_SHA:
        raise ValueError('Retained provenance changed')
    value = json.loads(raw)
    validate_source(value['artifact'], value['run'], value['repository'])
    expected = [{'retained_member': row['member'], 'sha256': row['sha256'], 'bytes': row['bytes']}
                for row in manifest['files']]
    actual = [{key: row[key] for key in ('retained_member', 'sha256', 'bytes')}
              for row in value['archive_members']]
    if not (value['schema_version'] == 1 and value['source'] == manifest['source']
            and value['permanent_manifest_sha256'] == MANIFEST_SHA and actual == expected
            and value['authentication'] == 'previously_authenticated_retained_evidence'
            and value['fresh_github_verification'] is False):
        raise ValueError('Inconsistent retained provenance')
    return {'schema_version': 2, 'producer': REPLAY_PRODUCER,
            'authentication': value['authentication'], 'fresh_github_verification': False,
            **verify_identity(), 'retained_provenance_sha256': 'sha256:' + PROVENANCE_SHA}


def verify_identity():
    return {'source_run': RUN, 'source_artifact': ARTIFACT, 'archive_sha256': 'sha256:' + ARCHIVE_SHA,
            'permanent_manifest_sha256': 'sha256:' + MANIFEST_SHA, 'submission_hashes_verified': True,
            'original_outcomes_unchanged': True}


def retain_originals(directory):
    """Retain required evidence before native execution, without network or credentials."""
    import shutil
    import skill_reports as reports
    proof = retained_provenance()
    shutil.copytree(ROOT / CORPUS, directory / 'original')
    shutil.copyfile(ROOT / PROVENANCE, directory / 'original-provenance.json')
    reports.write_json(directory / 'original-authentication.json', proof)


def verify_retained_originals(directory, workspace=ROOT):
    import skill_evidence as evidence
    verify_original_copy(directory / 'original', workspace)
    proof = retained_provenance(workspace)
    if (evidence.read_bytes(directory / 'original-provenance.json') != evidence.read_bytes(workspace / PROVENANCE)
            or evidence.read_json(directory / 'original-authentication.json') != proof):
        raise ValueError('Retained replay authentication mismatch')


def fetch(output):
    """Optional fresh remote audit; failure never changes the retained evidence."""
    output.mkdir(parents=True)
    prefix = 'repos/thetechgy/agent-engineering-baseline/'
    def api(path):
        return json.loads(subprocess.check_output(['gh', 'api', prefix + path], text=True))
    artifact, run = api('actions/artifacts/' + str(ARTIFACT)), api('actions/runs/' + str(RUN))
    validate_source(artifact, run, run['repository'])
    if artifact['expired']:
        raise ValueError('Original remote artifact expired; retained replay remains available')
    for name, value in (('artifact.json', artifact), ('run.json', run)):
        (output / name).write_text(json.dumps(value, indent=2) + '\n')
    archive = output / 'live.zip'
    with archive.open('xb') as stream:
        subprocess.run(['gh', 'api', prefix + 'actions/artifacts/' + str(ARTIFACT) + '/zip'], stdout=stream, check=True)
    proof = verify_archive(archive)
    proof.update(schema_version=2, producer=REPLAY_PRODUCER,
                 authentication='fresh_github_verification', fresh_github_verification=True)
    (output / 'authentication.json').write_text(json.dumps(proof, indent=2) + '\n')


def verify_archive(archive, workspace=ROOT):
    """Match permanent originals to authenticated bytes without executing or extracting code."""
    import stat
    import skill_evidence as evidence
    if hashlib.sha256(evidence.read_bytes(archive, limit=32*1024**2)).hexdigest() != ARCHIVE_SHA:
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
        retained_provenance(workspace)
        receipt = evidence.read_json(workspace / PROVENANCE)
        for row in receipt['archive_members']:
            if evidence.read_bytes(root / row['retained_member']) != bundle.read(row['archive_member']):
                raise ValueError('Original retained evidence bytes changed')
    return verify_identity()


def original_public(output):
    """Preserve the original record in the existing public reporting layout."""
    corpus()
    folder = output / 'skills/powershell-pester-6/behavioral/live-pilot'; folder.mkdir(parents=True)
    raw = (ROOT / CORPUS / 'original-public-report.json').read_bytes()
    (folder / 'public-report.json').write_bytes(raw)
    inventory = output / 'inventory'; inventory.mkdir()
    (inventory / 'inventory.json').write_bytes((ROOT / CORPUS / 'original-inventory.json').read_bytes())
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('fetch', 'validate', 'replay'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if any(os.environ.get(key) for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'NVIDIA_API_KEY')):
        parser.error('Credential-free replay received model credentials')
    if args.action == 'fetch':
        fetch(args.output); return
    retained_provenance()
    if args.action == 'validate':
        args.output.mkdir(parents=True)
        retain_originals(args.output)
        verify_retained_originals(args.output)
        return
    import evaluator_profiles as profiles
    import codex_pilot as pilot
    import skill_reports as reports
    from qualify_evaluator_candidate import native_compose_config
    profiles.runtime(profiles.candidate_versions(), owning=True)
    native_compose_config(ROOT)
    args.output.mkdir(parents=True)
    evidence = args.output / 'evidence'; evidence.mkdir()
    original = original_public(evidence / 'original-public')
    retain_originals(evidence)
    _, _, submissions, _ = corpus()
    pilot.run(args.output, replay=retrospective_metadata(), submissions=submissions, original_public=original)
    outcomes = reports.read_json(evidence / 'grading-outcomes.json')
    complete = len(outcomes) == 2 and all(o['outcome'].get('classification') in ('passed', 'failed')
        and o['outcome'].get('mutants_executed') == 2
        and o['outcome'].get('powershell_version') == '7.6.9'
        and o['outcome'].get('pester_version') == '6.2.0' for o in outcomes)
    reports.write_json(evidence / 'replay-check.json', {'complete': complete, 'producer': REPLAY_PRODUCER,
        'retrospective': retrospective_metadata(), 'inference': False, 'originals_preserved': True})
    if not complete:
        raise ValueError('Retrospective paired grading incomplete; original and native outcomes retained')


if __name__ == '__main__':
    main()
