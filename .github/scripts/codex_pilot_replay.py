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


# A second immutable corpus uses the same retained-data/replay/report mechanisms.
# This is one current-arm submission, not another slot in the closed allocation.
CAMPAIGN_CORPUS = '.github/evals/codex-retrospective/42695478931'
CAMPAIGN_MANIFEST_SHA = 'd21f8b5d6b18e21aab9acf471646f4ce48ad400bb1a52864ddd3b049fb379f87'
CAMPAIGN_PROVENANCE_SHA = '966e2b49b6fefaa8213b62cf763f3155f00492aa1ceb752239cb8c4aff62119c'


def campaign_corpus(workspace=ROOT, *, definition=None, profile=None):
    selected = (definition or {}).get('retrospective', CAMPAIGN_CORPUS + '/manifest.json')
    if profile is not None:
        from evaluation_evidence import task
        selected = task(profile).definition['retrospective']
    binding = dict(root=CAMPAIGN_CORPUS, manifest=CAMPAIGN_MANIFEST_SHA,
        provenance=CAMPAIGN_PROVENANCE_SHA, run=42695478931, artifact=13708468986,
        revision='97124cf6b09d2acd4bda6243d0345dff06aea989',
        archive='0d9cc2aa7125f86656224251e4c84531b5dfd72fd211c1e8b079513a27112deb',
        size=471, submission='3215b6097fa3e5f592989f2b8f4523207e28ebd4893cc7d11437b19189795981',
        purpose='campaign-boolean-effectiveness-v1-live')
    if selected == '.github/evals/codex-retrospective/42911213479/manifest.json':
        from pester_transfer_replay import BINDING
        binding = BINDING
    elif selected != CAMPAIGN_CORPUS + '/manifest.json':
        raise ValueError('Unregistered retained source')
    import skill_evidence as evidence
    root = workspace / binding['root']
    raw = evidence.read_bytes(root / 'manifest.json')
    if hashlib.sha256(raw).hexdigest() != binding['manifest']:
        raise ValueError('Retained campaign manifest changed')
    manifest = json.loads(raw)
    expected = {row['member'] for row in manifest['files']} | {'manifest.json','provenance.json'}
    if {p.relative_to(root).as_posix() for p in evidence.safe_tree(root)} != expected:
        raise ValueError('Unexpected retained campaign member')
    for row in manifest['files']:
        evidence.relative(row['member'])
        data = evidence.read_bytes(root / row['member'])
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Retained campaign bytes changed')
    provenance = evidence.read_bytes(root / 'provenance.json')
    if hashlib.sha256(provenance).hexdigest() != binding['provenance']:
        raise ValueError('Retained campaign provenance changed')
    proof = json.loads(provenance); source = manifest['source']
    artifact, run, job = proof['artifact'], proof['run'], proof['uploader_job']
    origin = artifact['workflow_run']
    if not (source['run'] == run['id'] == origin['id'] == binding['run']
            and source['artifact'] == artifact['id'] == binding['artifact']
            and source['revision'] == run['head_sha'] == origin['head_sha'] == binding['revision']
            and artifact['digest'] == 'sha256:' + source['archive_sha256']
            and source['archive_sha256'] == binding['archive']
            and run['repository']['id'] == run['head_repository']['id'] == origin['repository_id'] == origin['head_repository_id'] == 1299967456
            and run['path'] == source['workflow'] == '.github/workflows/evaluation-campaign.yml'
            and run['run_attempt'] == source['attempt'] == 1 and run['event'] == source['event'] == 'workflow_dispatch'
            and run['status'] == 'completed' and run['conclusion'] == 'failure' and artifact['name'] == 'campaign-live-1'
            and job['conclusion'] == 'failure' and any(step['name'] == 'Retain all slots and partial native evidence after stopping'
                and step['conclusion'] == 'success' for step in job['steps'])
            and proof['manifest_sha256'] == binding['manifest']):
        raise ValueError('Retained campaign producer authentication mismatch')
    submission = evidence.read_bytes(root / 'Subject.Tests.ps1')
    if len(submission) != binding['size'] or hashlib.sha256(submission).hexdigest() != binding['submission']:
        raise ValueError('Retained campaign submission mismatch')
    original = evidence.read_json(root / 'original-public-report.json')
    evidence.validate_custom_evidence(original, public=True)
    if (evidence.identity(original) != source['original_record_id']
            or original['custom']['capture_digest'] != source['original_capture_digest']
            or original['custom']['purpose'] != binding['purpose']
            or len(original['observations']) != 1
            or original['observations'][0]['arm'] != 'with_skill'
            or any(m['value'] is not None for o in original['observations'] for m in o['custom']['measurements'])
            or any(d['detected'] is not None for o in original['observations'] for d in o['custom']['defects'])):
        raise ValueError('Original unmeasured campaign result changed')
    return root, manifest, original


def campaign_retrospective(profile, *, adapter_revision=None, workspace=ROOT):
    root, manifest, _ = campaign_corpus(workspace, profile=profile)
    source = manifest['source']
    if adapter_revision is None:
        if subprocess.check_output(['git','status','--porcelain'],cwd=workspace,text=True).strip():
            raise ValueError('Retrospective publication requires a clean committed adapter revision')
        adapter_revision = subprocess.check_output(['git','rev-parse','HEAD'],cwd=workspace,text=True).strip()
    import re
    if not isinstance(adapter_revision,str) or re.fullmatch('[0-9a-f]{40}',adapter_revision) is None:
        raise ValueError('Invalid corrected adapter revision')
    return {'source_run':source['run'], 'source_artifact':source['artifact'], 'source_revision':source['revision'],
        'source_archive_sha256':'sha256:'+source['archive_sha256'], 'source_slot':1, 'source_attempt':1,
        'original_record_id':source['original_record_id'], 'original_capture_digest':source['original_capture_digest'],
        'submission_digests':{'with_skill':'sha256:'+hashlib.sha256((root/'Subject.Tests.ps1').read_bytes()).hexdigest()},
        'source_trace_sha256':'sha256:'+hashlib.sha256((root/'codex.txt').read_bytes()).hexdigest(),
        'corrected_adapter_revision':adapter_revision, 'corrected_adapter_sha256':profile['campaign']['adapter_sha256'],
        'after_output_inspection':True, 'new_inference':False}


def validate_campaign_retrospective(value, profile, workspace=ROOT):
    if not isinstance(value,dict) or value != campaign_retrospective(profile,
            adapter_revision=value.get('corrected_adapter_revision'),workspace=workspace):
        raise ValueError('Retrospective campaign identity mismatch')


def campaign_payload(workspace=ROOT, *, definition=None):
    root, _, _ = campaign_corpus(workspace, definition=definition)
    return (root/'Subject.Tests.ps1').read_bytes()


def retain_campaign_originals(destination, task, profile):
    import shutil
    import skill_evidence as evidence
    import skill_reports as reports
    root, manifest, original = campaign_corpus(definition=task.definition)
    staged = reports.read_json(root/'staging.json')
    old = next(r['members'] for r in staged if r['arm']=='with_skill' and r['case_id']==task.definition['source_case'])
    # Task inputs, reference, all five mutants, grader and verifier entry point
    # must be the original frozen bytes, not an output-informed replacement.
    members = task.expected_members(task.definition['source_case'],'with_skill')
    allowed = task.replay_changes(old)
    if not all(old.get(key)==evidence.digest_bytes(value) for key,value in members.items() if key not in allowed):
        raise ValueError('Original task/grader drift')
    shutil.copytree(root,destination/'original')
    public = destination/'original-public'
    folder = public/'skills'/task.definition['skill']/'behavioral'/original['run_id'];folder.mkdir(parents=True)
    shutil.copyfile(root/'original-public-report.json',folder/'public-report.json')
    (public/'inventory').mkdir();shutil.copyfile(root/'original-inventory.json',public/'inventory/inventory.json')
    # Parse data through the owning adapter. No recorded command is executed.
    from evaluation_codex import CampaignCodex, exec_trajectory
    from evaluation_runtime import read_profile
    adapter = object.__new__(CampaignCodex)
    adapter.profile = read_profile(ROOT/task.definition['runtime_profile'])['resolved']
    adapter.model_name = adapter.profile['model'];adapter.live=True # Source trace describes the original live turn.
    trajectory = exec_trajectory((root/'codex.txt').read_text(),adapter)
    reports.write_json(destination/'retrospective-trajectory.json',json.loads(trajectory.model_dump_json(exclude_none=True)))
    meta = campaign_retrospective(profile)
    if meta['corrected_adapter_sha256'] != evidence.digest_bytes((ROOT/'.github/scripts/evaluation_codex.py').read_bytes()):
        raise ValueError('Corrected adapter source drift')
    reports.write_json(destination/'trace-replay.json',{'retrospective':meta,'new_inference':False,
        'normalized_trajectory_sha256':evidence.digest_bytes((destination/'retrospective-trajectory.json').read_bytes()),
        'recorded_commands_executed':False,'originals_preserved':True})
    return meta


def validate_campaign_pair(record, original):
    import skill_evidence as evidence
    meta = record['custom']['retrospective']
    profile, _, _ = evidence.custom_contract('powershell-pester-6', purpose=record['custom']['purpose'])
    _, manifest, expected = campaign_corpus(profile=profile)
    if (original != expected or evidence.identity(original) != meta['original_record_id']
            or set(meta['submission_digests']) != {'with_skill'}
            or any(o['arm'] != 'with_skill' for o in record['observations'])):
        raise ValueError('Retrospective campaign original or enrolled arm mismatch')

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
