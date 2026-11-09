"""Registered campaign extension to existing native evidence admission.

Task adapters validate protected task members; the shared native normalizer still
checks every native checksum, reward, metric, failure, coverage and reference.
"""
import hashlib
from pathlib import Path

from evaluation_campaign_core import require
from evaluation_tasks import ROOT, load
import skill_reports as reports


def task(profile):
    return load(ROOT / profile['campaign']['definition'])


def source_manifest(workspace, name, purpose):
    import skill_evidence as e
    profile, _, _ = e.custom_contract(name, workspace, purpose=purpose)
    adapter = task(profile)
    # Preserve original overlay ownership; add the reviewed extension and candidate.
    values = adapter.source_inputs(workspace)
    files = ['.github/scripts/evaluation_campaign.py', '.github/scripts/evaluation_campaign_core.py',
        '.github/scripts/evaluation_runtime.py', '.github/scripts/evaluation_tasks.py',
        '.github/scripts/evaluation_evidence.py', '.github/scripts/skill_evidence.py', '.github/scripts/skill_analysis.py',
        '.github/scripts/skill_report.py', '.github/scripts/skill_reports.py', adapter.member,
        adapter.definition['runtime_profile'], '.github/workflows/evaluation-campaign.yml']
    from evaluation_runtime import read_profile, source_inputs
    values.extend(source_inputs(read_profile(ROOT / adapter.definition['runtime_profile']), workspace))
    values.extend({'member': 'campaign/' + member, 'digest': e.digest_bytes(e.read_bytes(workspace / member))} for member in sorted(set(files)))
    return values


def identities(workspace, name, purpose, inputs=None):
    import skill_evidence as e
    profile, _, _ = e.custom_contract(name, workspace, purpose=purpose)
    adapter = task(profile)
    members = adapter.expected_members(next(iter(adapter.cases(profile['campaign']['mode']))), 'with_skill')
    grader = {k:e.digest_bytes(v) for k,v in members.items() if k.startswith('tests/') and not k.startswith('tests/case/') and k != 'tests/entry.json'}
    fixtures = {k:e.digest_bytes(v) for k,v in members.items() if k.startswith(('tests/case/', 'environment/input/', 'environment/private/')) or k == 'instruction.md'}
    return {'grader_digest': e.identity(grader), 'fixture_digest': e.identity(fixtures),
        'runtime_digest': e.identity(inputs if inputs is not None else source_manifest(workspace, name, purpose))}


def capture_tasks(workspace, profile, tasks, arm):
    import skill_evidence as e
    rows = []
    adapter = task(profile)
    for native in tasks:
        members = {p.relative_to(native).as_posix(): e.digest_bytes(e.read_bytes(p)) for p in e.safe_tree(native)}
        row = {'case_id': native.name, 'source_case_id': adapter.definition['source_case'], 'arm': arm,
               'task_checksum': e.custom_task_checksum(members), 'members': members}
        validate_task(profile, members, native.name, arm)
        rows.append(row)
    return sorted(rows, key=lambda row: row['case_id'])


def validate_policy(profile, fields, attempts, agent_version):
    from evaluation_runtime import read_profile
    runtime = read_profile(ROOT / task(profile).definition['runtime_profile'])['resolved']
    probe = profile['campaign']['mode'] == 'probe'
    expected = {'environment': profile['campaign']['environment_mode'], 'concurrency': 1, 'timeout_multiplier': 1.0,
        'model': runtime['model'] if probe else 'credential-free-oracle', 'provider': runtime['provider'] if probe else 'fixture'}
    require(attempts == 1 and all(fields[k] == v for k,v in expected.items()), 'Campaign public execution policy drift')
    require(not probe or agent_version in (None, runtime['cli']), 'Campaign CLI version drift')


def validate_task(profile, members, case, arm):
    from evaluation_runtime import adapter_for, read_profile
    adapter = task(profile)
    adapter.validate_members(members, case, arm)
    runtime = adapter_for(read_profile(ROOT / adapter.definition['runtime_profile']))
    runtime.validate_members(members, profile['campaign']['mode'])


def native_outcome(profile, trial, outcome):
    from evaluation_runtime import native_outcome as interpret, read_profile
    return interpret(read_profile(ROOT / task(profile).definition['runtime_profile']), trial, outcome)
