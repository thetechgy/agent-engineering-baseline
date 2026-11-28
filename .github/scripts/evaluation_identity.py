"""Resolve reusable grading profiles and bind execution to a reviewed Git tree."""
from pathlib import Path
import re

from evaluation_campaign_core import require

REGISTRY = '.github/evals/grading-registry.json'
LEGACY_INPUTS = '.github/evals/campaign-source-v53-inputs.json'
EFFECTIVENESS = 'pester-effectiveness-grading-v1'
EFFECTIVENESS_PURPOSES = ('skill_effectiveness', 'skill_effectiveness_control', 'skill_effectiveness_probe')
CAMPAIGN = re.compile(r'(campaign-[a-z0-9-]+)-lifecycle-v2-(oracle|probe|experiment-probe|live|replay)')
SOURCE_PATHS = ('.github', '.apm', '.agents', 'apm.yml', 'apm.lock.yaml', '.apm-version', 'scripts')
REPLAY_ADAPTER = '.github/scripts/evaluation_codex.py'


def campaign_profile(campaign, mode):
    return f'campaign-{campaign}-lifecycle-v2-{mode}'


def reusable(profile_id):
    return type(profile_id) is str and (profile_id == EFFECTIVENESS or CAMPAIGN.fullmatch(profile_id) is not None)


def profile_for_capture(purpose):
    return EFFECTIVENESS if purpose in EFFECTIVENESS_PURPOSES else purpose if reusable(purpose) else None


def resolve_profile(workspace, registry, profile_id):
    """Resolve active grading or a reviewed, task-owned qualification profile."""
    from evaluation_registration import registered_file, task_families
    from skill_evidence import closed, custom_authored_digest, read_json, sha, validate_custom_metrics

    require(reusable(profile_id), 'Unknown reusable grading profile')
    metrics = registry['metrics']
    if profile_id in registry['profiles']:
        profile = registry['profiles'][profile_id]
        match = CAMPAIGN.fullmatch(profile_id)
        require('runtime_digest' not in profile
                and (match is None or profile.get('campaign', {}).get('mode') == match[2]),
                'Reusable grading profile mode or runtime binding mismatch')
        return profile, metrics

    resolved = []
    for family in task_families(workspace).values():
        member = Path(family.member).with_name('grading.json').as_posix()
        if not (workspace / member).exists() and not (workspace / member).is_symlink():
            continue
        data = read_json(registered_file(workspace, member))
        closed(data, ('version', 'metrics', 'profiles'))
        require(type(data['version']) is int and data['version'] == 1 and type(data['metrics']) is dict
                and type(data['profiles']) is dict and 0 < len(data['profiles']) <= 128
                and not (metrics.keys() & data['metrics'].keys())
                and all(key.startswith(f'{family.skill}.') for key in data['metrics']),
                'Invalid task grading registry')
        validate_custom_metrics({**metrics, **data['metrics']})
        if profile_id not in data['profiles']:
            continue
        profile = data['profiles'][profile_id]
        campaign = profile['campaign']
        definition = campaign['definition']
        require(profile.get('id') == profile_id and profile.get('skill_id') == family.skill
                and profile.get('grading') == 'custom_only' and 'runtime_digest' not in profile
                and definition in family.definitions and campaign.get('dataset') is not None,
                'Unregistered grading profile owner')
        task = read_json(registered_file(workspace, definition))
        mode = campaign.get('mode')
        require(profile_id == campaign_profile(task['id'], mode) and mode in ('oracle', 'probe')
                and 'protocol' not in task and not campaign.get('scheduler'), 'Unregistered grading profile purpose')
        for key in ('grader_digest', 'fixture_digest'):
            sha(profile[key])
        custom_authored_digest(workspace, family.skill, profile)
        resolved.append((profile, {**metrics, **data['metrics']}))
    require(len(resolved) == 1, 'Unknown or duplicate reusable grading profile')
    return resolved[0]


def grading_definition(profile):
    # Runtime, scheduler and selection stay in the execution contract.
    fields = ('skill_id', 'grading', 'cases', 'qualification_cases', 'dataset_digest',
              'grader_digest', 'fixture_digest', 'semantics')
    return {key: profile[key] for key in fields if key in profile}


def legacy_inputs(workspace, values):
    from evaluation_archive import archive_index, configured, read_json
    from skill_evidence import sha

    base = archive_index(workspace)['source_inputs'] if configured(workspace) else {}
    pinned = {**base, **read_json(workspace, LEGACY_INPUTS)}
    for digest in pinned.values():
        sha(digest)
    return [dict(row, digest=pinned[row['member']]) if row['member'] in pinned else row for row in values]


def checked_revision(value):
    require(type(value) is str and re.fullmatch(r'[0-9a-f]{40}', value) is not None,
            'Invalid execution source revision')
    return value


def source_registry(raw):
    from skill_evidence import closed, parse_json

    value = parse_json(raw)
    closed(value, ('version', 'retained_source_revisions'))
    retained = value['retained_source_revisions']
    require(type(value['version']) is int and value['version'] == 1 and type(retained) is list
            and len(retained) <= 128, 'Invalid grading registry version')
    require(len({checked_revision(item) for item in retained}) == len(retained), 'Duplicate retained source revision')
    return value


def campaign_inputs(workspace, revision, campaign, budget):
    """Bind the selection and frozen runtime files from the producer's tree."""
    from evaluation_campaign_selection import registry_path
    from skill_evidence import digest_bytes, historical_blob, parse_json, read_bytes

    members = {}

    def retain(member, *, frozen=True):
        raw = historical_blob(workspace, f'{revision}:{member}', budget=budget)
        require(raw is not None, 'Reviewed campaign input is unavailable')
        if frozen:
            require(raw == read_bytes(workspace / member), 'Frozen campaign input drift')
        members[member] = digest_bytes(raw)
        return raw

    task = parse_json(retain(campaign['definition']))
    runtime = parse_json(retain(task['runtime_profile']))
    retain(runtime['frozen_profile'])
    if 'protocol' in task:
        retain(task['protocol'])
    retain(registry_path(task['id']).relative_to(workspace).as_posix(), frozen=False)
    return members


def execution_binding(workspace, profile, purpose, contract, *, recorded=None):
    from skill_evidence import (ReadBudget, closed, digest_bytes, historical_blob, identity,
                                offline_git, resolve_git_revision)

    budget = ReadBudget()
    head = checked_revision(resolve_git_revision(workspace, budget))
    if recorded is None:
        revision = head
        status = offline_git(workspace, '-c', 'core.fsmonitor=false', 'status', '--porcelain=v1', '-z', '--untracked-files=all',
                             '--', *SOURCE_PATHS, max_entries=4096, budget=budget)
        require(status.returncode == 0 and not status.stdout, 'Execution source must match its committed tree')
    else:
        closed(recorded, ('version', 'revision', 'tree', 'profile', 'purpose', 'grading', 'policy', 'replay_adapter'))
        revision = checked_revision(recorded['revision'])
        if revision != head:
            config = historical_blob(workspace, f'{head}:{REGISTRY}', budget=budget)
            require(config is not None, 'Reviewed grading registry is unavailable')
            retained = source_registry(config)['retained_source_revisions']
            require(revision in retained or offline_git(workspace, 'merge-base', '--is-ancestor',
                                                        revision, head, budget=budget).returncode == 0,
                    'Execution source revision is outside reviewed history')
    config = historical_blob(workspace, f'{revision}:{REGISTRY}', budget=budget)
    require(config is not None, 'Reviewed grading registry is unavailable')
    source_registry(config)
    tree_result = offline_git(workspace, 'rev-parse', f'{revision}^{{tree}}', text=True, budget=budget)
    tree = checked_revision(tree_result.stdout.strip())
    campaign = profile.get('campaign', {})
    adapter = None
    if 'adapter_sha256' in campaign:
        raw = historical_blob(workspace, f'{revision}:{REPLAY_ADAPTER}', budget=budget)
        require(raw is not None, 'Reviewed replay adapter is unavailable')
        adapter = digest_bytes(raw)
    policy = {key: value for key, value in profile.items() if key not in ('runtime_digest', 'campaign')}
    if campaign:
        policy['campaign'] = {key: value for key, value in campaign.items() if key != 'adapter_sha256'}
        policy['inputs'] = campaign_inputs(workspace, revision, campaign, budget)
    expected = {'version': 1, 'revision': revision, 'tree': tree, 'profile': profile['id'], 'purpose': purpose,
                'grading': contract, 'policy': identity(policy), 'replay_adapter': adapter}
    if recorded is not None:
        require(type(recorded['version']) is int and recorded == expected, 'Execution binding mismatch')
    budget.verify_repository()
    return expected


def validate_skill_source(workspace, profile, binding, source):
    from evaluation_evidence import registered_family, task
    from skill_evidence import historical_content
    from skill_reports import RETAINED_GH_REVISION

    member = task(profile).definition['source'] if 'campaign' in profile else '.apm/skills/' + profile['skill_id']
    local = profile['skill_id'] == 'powershell-pester-6' or registered_family(profile, workspace) is not None
    if local:
        require(source['owner'] == 'local' and source['revision'] == binding['revision']
                and source['source_path'] == member, 'Execution skill owner or source revision drift')
    else:
        require(profile['skill_id'] == 'gh' and source['owner'] == 'upstream' and source['repository'] == 'cli/cli'
                and source['revision'] == profile.get('upstream_revision', RETAINED_GH_REVISION)
                and source['source_path'] == 'skills/gh', 'Execution skill owner or source revision drift')
    expected = historical_content(workspace, binding['revision'], member)
    require(expected['digest'] is not None and source['content']['digest'] == expected['digest'],
            'Execution skill source drift')
