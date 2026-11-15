"""No-workload qualification of the production live launch construction boundary.

Fixture authorization and clock controls exist only here, never in runtime_gate.
The worker uses the released Trial.create and live CampaignCodex constructor.
An audit hook blocks network and all subprocesses except fixed read-only Git identity/version
queries. A test fixture runs the real gh startup consumer only as far as verified manifest approval;
its first container-start operation is intercepted before any workload or key
handoff. No probe flag, allocation claim, provider or judge is used.
"""
import argparse
import asyncio
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from evaluation_campaign_core import require
from evaluation_runtime import ROOT
import skill_reports as reports


class FixtureClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 11, 15, 12, tzinfo=timezone.utc)


class StopBeforeWorkload(Exception):
    pass


def worker(config_path):
    import evaluation_campaign_protocol as protocol
    from harbor.models.trial.config import TrialConfig
    from harbor.trial.trial import Trial
    from skillevaluator.tier3.harbor.secure_docker_environment import SkillEvaluatorSecureDockerEnvironment
    config = TrialConfig.model_validate(reports.read_json(config_path))
    blocked = []; reached = []
    identity_queries = (
        ['git', 'rev-parse', 'HEAD'], ['git', 'rev-parse', '--git-dir'],
        ['git', 'rev-parse', '--abbrev-ref', 'HEAD'], ['git', 'branch', '--contains'],
        ['git', 'describe', '--tags', '--dirty', '--always', '--long', '--match', '[[:digit:]]*'],
        ['git', 'rev-list', 'HEAD', '--left-right'], ['git', 'show', '-s', '--format=%ci', 'HEAD'])

    def deny(event, args):
        if event in ('socket.connect', 'socket.getaddrinfo'):
            import traceback
            blocked.append({'event': event, 'callers': [Path(f.filename).name + ':' + f.name for f in traceback.extract_stack(limit=6)]})
            raise AssertionError('Launch qualification forbids network')
        if event == 'subprocess.Popen' and (Path(str(args[0])).name != 'git'
                or list(args[1]) not in identity_queries):
            blocked.append({'event': event, 'command': list(args[1])})
            raise AssertionError('Launch qualification forbids workload processes')
    sys.addaudithook(deny)

    async def stop(_environment, _force_build):
        reached.append('environment_start_before_container_start')
        raise StopBeforeWorkload

    trial_holder = []

    def after_agent(trial):
        require(trial.agent.live is True, 'Qualification did not initialize the live agent')
        require(os.environ.get('AEB_PILOT_PROBE') is None, 'Probe bypass in valid qualification')
        trial_holder.append(trial)
        reached.append('live_agent_initialized')
        raise StopBeforeWorkload

    async def construct():
        # Stop at the requested agent-initialization boundary. Do not invent a
        # successful kernel-readiness result or start a diagnostic container.
        initialize_agent = Trial._init_agent
        def initialize_then_stop(trial):
            initialize_agent(trial)
            after_agent(trial)
        with patch.object(Trial, '_init_agent', initialize_then_stop):
            try:
                if hasattr(Trial, 'create'): await Trial.create(config)
                else: Trial(config)
            except StopBeforeWorkload:
                pass
        require(len(trial_holder) == 1, 'Live agent initialization not reached')
        trial = trial_holder[0]
        # Exercise the real startup consumer with the real task/trial paths.
        # This fixture supplies only attributes used before the first environment
        # start, which is intercepted; it is not an initialized environment.
        from importlib import import_module
        module, name = config.environment.import_path.split(':')
        environment_class = getattr(import_module(module), name)
        environment = object.__new__(environment_class)
        environment.environment_dir = trial.task.paths.environment_dir
        environment.trial_paths = trial.paths
        environment.logger = trial.logger
        try:
            await environment.start(False)
        except StopBeforeWorkload:
            pass
        if trial.agent.task.definition['adapter'] == 'gh-fixture':
            status = json.loads((trial.paths.trial_dir / 'gh-initialization.jsonl').read_text().splitlines()[-1])
            require(status['manifest'] == config.agent.kwargs['launch_context']['manifest_digest']
                    and status['arm'] == ('with_skill' if trial.agent.expected_present else 'without_skill'),
                    'Manifest did not reach the legitimate gh startup consumer')
            identity = {'manifest_digest': status['manifest'], 'task_checksum': status['checksum']}
        else:
            identity = {}
        return {'result': 'accepted_to_stop_boundary', 'reached': reached, **identity,
                'cli': trial.agent.profile['cli'], 'model': trial.agent.model_name,
                'reasoning_effort': trial.agent.profile['reasoning_effort'], 'provider': trial.agent.profile['provider'],
                'endpoint': trial.agent.profile['base_url']}

    try:
        with patch.object(protocol, 'datetime', FixtureClock), patch.object(SkillEvaluatorSecureDockerEnvironment, 'start', stop):
            result = asyncio.run(construct())
    except (ValueError, KeyError, OSError, TypeError) as error:
        result = {'result': 'rejected', 'error_type': type(error).__name__, 'reached': reached}
    require(not blocked, 'Qualification attempted network or workload execution: ' + json.dumps(blocked))
    print(json.dumps({**result, 'network_attempts': 0, 'workload_processes': 0,
                      'credential_handoffs': 0, 'inference': False, 'cleanup': 'worker_exit'}))


def qualify(output, task, reference):
    from evaluation_campaign import stage, construct_launch, no_credentials
    import evaluation_campaign_protocol as protocol
    from evaluation_campaign_selection import binding, registration
    from codex_pilot_descriptors import compare_descriptors
    no_credentials()
    output.mkdir(parents=True, exist_ok=False)
    root = output / 'campaign-live'; root.mkdir()
    _, tasks, _, extra = stage(root, task, 'live')
    compared = compare_descriptors(reference, root / 'evidence')
    require(reports.read_json(reference / 'deployment.json') == reports.read_json(root / 'evidence/deployment.json'),
            'Launch qualification deployment drift')
    rev = protocol.revision(); nonce = 'fixture_launch_boundary'
    allocation = f'campaign-{rev}-{task.definition["id"]}-prep7000002-usd{protocol.protocol(task)["budget"]["planning_allocation_usd"]}-{nonce}'
    receipt = {'artifact': '7000002', 'dispatch': nonce, 'allocation': allocation, 'revision': rev,
        'protocol_digest': protocol.digest(ROOT / task.definition['protocol']), 'run_id': '7000003',
        'first_dispatch': True, 'authentication': 'github-api-producer-and-digest', **binding(task),
        'preparation_location': registration(task)['producers'][0]['location'], 'artifact_digest': 'sha256:' + 'a'*64}
    receipt_path = output / 'test-only-receipt.json'; reports.write_json(receipt_path, receipt)
    home = output / 'empty-home'; home.mkdir(mode=0o700)
    base = {k:v for k,v in os.environ.items() if k in
            ('PATH', 'TMPDIR', 'TMP', 'TEMP', 'SYSTEMROOT', 'WINDIR', 'PATHEXT', 'LANG', 'LC_ALL')}
    base['HOME'] = str(home)
    base.update(GITHUB_ACTIONS='true', GITHUB_REPOSITORY=protocol.REPO, GITHUB_JOB='live',
        GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_RUN_ATTEMPT='1', GITHUB_RUN_ID='7000003', RUNNER_TEMP=str(output),
        AEB_CAMPAIGN_APPROVAL=allocation, AEB_CAMPAIGN_RECEIPT=str(receipt_path))
    base.pop('OPENAI_BASE_URL', None)
    results = []; configs = output / 'configurations'
    variants = task.definition['variants']
    for variant in variants:
        present = variant['present']; native = tasks[variant['id']][task.definition['source_case']]
        job = root / 'jobs' / (task.definition['skill'] + '-codex-' + ('with' if present else 'without'))
        with patch.dict(os.environ, base, clear=True), patch.object(protocol, 'datetime', FixtureClock):
            config, env = construct_launch(root, task, 'live', native, present, 'valid-' + variant['id'], job, extra,
                                           live_key='fixture-not-a-credential')
        mutations = ['valid', 'unexpected-aeb', 'probe', 'control', 'provider', 'authorization', 'replay']
        if extra:
            mutations += ['missing-manifest', 'substituted-manifest', 'tampered-manifest', 'wrong-binding', 'wrong-manifest-population']
        for name in mutations:
            candidate = copy.deepcopy(config); child = dict(env)
            candidate.trial_name = name + '-' + variant['id']
            before = None
            if name == 'unexpected-aeb': child['AEB_UNREVIEWED'] = '1'
            if name == 'probe': child['AEB_PILOT_PROBE'] = '1'
            if name == 'control': candidate.agent.kwargs['control'] = 'good'
            if name == 'provider': child['OPENAI_BASE_URL'] = 'http://127.0.0.1:1/v1'
            if name == 'authorization': child['AEB_CAMPAIGN_APPROVAL'] += '-mismatch'
            if name == 'replay': child['GITHUB_RUN_ATTEMPT'] = '2'
            if name == 'missing-manifest': child.pop('AEB_GH_MANIFEST')
            if name == 'substituted-manifest':
                import shutil
                other = output / 'other'; other.mkdir(mode=0o700, exist_ok=True)
                substitute = other / Path(extra['AEB_GH_MANIFEST']).name
                shutil.copyfile(extra['AEB_GH_MANIFEST'], substitute); substitute.chmod(0o600)
                from aeb_gh_fixture.manifest import load_manifest
                load_manifest(substitute)  # Valid seal/content, unauthorized location.
                child['AEB_GH_MANIFEST'] = str(substitute)
            if name == 'tampered-manifest':
                manifest = Path(extra['AEB_GH_MANIFEST']); before = manifest.read_bytes(); manifest.write_bytes(before + b' ')
            if name == 'wrong-binding':
                other = next(v for v in variants if v['present'] != present)
                candidate.agent.kwargs['launch_context']['task'] = str(tasks[other['id']][task.definition['source_case']])
            if name == 'wrong-manifest-population':
                import shutil
                from aeb_gh_fixture.manifest import write_manifest
                other = next(v for v in variants if v['present'] != present)
                substitute = write_manifest(output / ('other-population-' + variant['id']),
                    [tasks[other['id']][task.definition['source_case']]], staged_roots=[root / 'tasks', root / 'bundle'])
                target = root / 'operator' / substitute.name
                shutil.copyfile(substitute, target); target.chmod(0o600)
                child['AEB_GH_MANIFEST'] = str(target)
                candidate.agent.kwargs['launch_context']['manifest_digest'] = target.name[9:-5]
            path = configs / (candidate.trial_name + '.json')
            reports.write_json(path, json.loads(candidate.model_dump_json()))
            try:
                child.update(PYTHONDONTWRITEBYTECODE='1', LITELLM_LOCAL_MODEL_COST_MAP='True')
                from qualify_evaluator_candidate import run_native
                log_path = output / 'diagnostics' / (candidate.trial_name + '.log')
                log_path.parent.mkdir(exist_ok=True)
                with log_path.open('w') as log:
                    code = run_native([sys.executable, '-B', str(Path(__file__)), '--worker', str(path)],
                                      env=child, log=log, timeout=45)
                diagnostic = log_path.read_text()[-16384:]
                require(code == 0, 'Live construction worker failed: ' + diagnostic[-2000:])
                result = json.loads(diagnostic.strip().splitlines()[-1])
            finally:
                if before is not None: manifest.write_bytes(before)
            require(result['result'] == ('accepted_to_stop_boundary' if name == 'valid' else 'rejected'),
                    'Wrong live construction outcome: ' + name)
            if name != 'valid': require(not result['reached'], 'Rejected launch reached workload boundary')
            results.append({'variant': variant['id'], 'case': name, **result})
    # Parent failures must occur before even looking at the key-to-be-delivered.
    class NoHandoff:
        def __bool__(self): raise AssertionError('Rejected preparation touched the provider key')
    for name, change in [('ambient-metadata', extra), ('unexpected-aeb', {'AEB_UNREVIEWED': '1'}),
                         ('probe', {'AEB_PILOT_PROBE': '1'}), ('provider', {'OPENAI_BASE_URL': 'http://127.0.0.1:1/v1'}),
                         ('authorization', {'AEB_CAMPAIGN_APPROVAL': allocation + '-mismatch'})]:
        if name == 'ambient-metadata' and not extra: continue
        with patch.dict(os.environ, {**base, **change}, clear=True), patch.object(protocol, 'datetime', FixtureClock):
            try:
                construct_launch(root, task, 'live', native, present, 'parent-rejected', job, extra, live_key=NoHandoff())
            except (ValueError, KeyError): pass
            else: raise ValueError('Parent accepted ' + name)
        results.append({'case': name, 'phase': 'parent_before_key_attachment', 'result': 'rejected', 'credential_handoffs': 0})
    if extra:
        with patch.dict(os.environ, base, clear=True), patch.object(protocol, 'datetime', FixtureClock):
            try:
                construct_launch(root, task, 'live', native, present, 'parent-missing', job, {}, live_key=NoHandoff())
            except ValueError: pass
            else: raise ValueError('Parent accepted missing task metadata')
        results.append({'case': 'missing-manifest', 'phase': 'parent_before_key_attachment', 'result': 'rejected', 'credential_handoffs': 0})
    if protocol.protocol(task).get('authorization_expires_at'):
        class ExpiredClock(FixtureClock):
            @classmethod
            def now(cls, tz=None): return cls(2100, 1, 1, tzinfo=timezone.utc)
        with patch.dict(os.environ, base, clear=True), patch.object(protocol, 'datetime', ExpiredClock):
            try:
                construct_launch(root, task, 'live', native, present, 'parent-expired', job, extra, live_key=NoHandoff())
            except ValueError: pass
            else: raise ValueError('Parent accepted expired authority')
        results.append({'case': 'expired', 'phase': 'parent_before_key_attachment', 'result': 'rejected', 'credential_handoffs': 0})
    result = {'schema': 1, 'complete': True, 'revision': rev, 'campaign': task.definition['id'], 'inference': False,
        'test_only_receipts': True, 'allocation_claimed': False, 'probe_flags_on_valid_path': False,
        'descriptor_comparison': compared, 'deployment_equal': True, 'records': results,
        'provider_requests': 0, 'workload_launches': 0, 'cleanup_complete': True,
        'boundary': 'actual Trial.create and live agent initialization; real task startup consumer fixture; stop before environment start'}
    validate(result, task)
    reports.write_json(output / 'live-launch-qualification.json', result)
    return result


def validate(proof, task):
    from evaluation_campaign_protocol import revision, protocol
    from evaluation_runtime import read_profile
    require(proof.get('schema') == 1 and proof.get('complete') is True and proof.get('revision') == revision()
            and proof.get('campaign') == task.definition['id'] and proof.get('inference') is False
            and proof.get('test_only_receipts') is True and proof.get('allocation_claimed') is False
            and proof.get('probe_flags_on_valid_path') is False and proof.get('provider_requests') == 0
            and proof.get('workload_launches') == 0 and proof.get('cleanup_complete') is True
            and proof.get('deployment_equal') is True
            and proof.get('descriptor_comparison') == {'algorithm': 'sha256-typed-toml-v1', 'configurations_equal': True, 'descriptors': 2},
            'Unqualified live launch construction')
    manifest = task.definition['adapter'] == 'gh-fixture'
    cases = {'valid', 'unexpected-aeb', 'probe', 'control', 'provider', 'authorization', 'replay'}
    if manifest: cases |= {'missing-manifest', 'substituted-manifest', 'tampered-manifest', 'wrong-binding', 'wrong-manifest-population'}
    expected = {(v['id'], case) for v in task.definition['variants'] for case in cases}
    parents = {'unexpected-aeb', 'probe', 'provider', 'authorization'}
    if manifest: parents |= {'ambient-metadata', 'missing-manifest'}
    if protocol(task).get('authorization_expires_at'): parents.add('expired')
    expected |= {('parent', case) for case in parents}
    records = proof.get('records')
    require(type(records) is list and len(records) == len(expected), 'Incomplete launch rejection inventory')
    seen = set(); selected = read_profile(ROOT / task.definition['runtime_profile'])['resolved']
    for row in records:
        key = ('parent' if row.get('phase') == 'parent_before_key_attachment' else row.get('variant'), row.get('case'))
        require(key in expected and key not in seen and row.get('credential_handoffs') == 0, 'Unexpected or repeated launch proof')
        seen.add(key)
        if key[0] == 'parent':
            require(row.get('result') == 'rejected', 'Parent rejection missing')
            continue
        require(row.get('network_attempts') == row.get('workload_processes') == 0 and row.get('inference') is False
                and row.get('cleanup') == 'worker_exit', 'Launch boundary cleanup or network proof missing')
        if row['case'] == 'valid':
            require(row.get('result') == 'accepted_to_stop_boundary'
                    and row.get('reached') == ['live_agent_initialized', 'environment_start_before_container_start']
                    and all(row.get(k) == selected[k] for k in ('cli', 'model', 'reasoning_effort', 'provider'))
                    and row.get('endpoint') == selected['base_url'], 'Live agent identity or consumer boundary missing')
            if manifest:
                require(__import__('re').fullmatch('[0-9a-f]{64}', row.get('manifest_digest', ''))
                        and __import__('re').fullmatch('[0-9a-f]{64}', row.get('task_checksum', '')), 'Missing actual manifest consumer identity')
        else:
            require(row.get('result') == 'rejected' and row.get('reached') == [], 'Rejected constructor reached execution')
    require(seen == expected, 'Missing launch proof cases')
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', required=True, type=Path)
    worker(parser.parse_args().worker)
