#!/usr/bin/env python3
"""Credential-free gh-014 probe; stops at unchanged report admission."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
REVISION = 'f878f99a9cd4a85dd04043feb43e5bd6a777f64b'
HARBOR = 'fdba28fc411e47e8765420a1a063b4918fce3def'


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def worker(args):
    # No network access except the existing local Unix-socket fixture broker.
    def offline(event, values):
        if event in ('socket.getaddrinfo', 'http.client.connect'):
            raise PermissionError('probe_network_forbidden')
        if event == 'socket.connect' and not isinstance(values[1], (str, bytes)):
            raise PermissionError('probe_network_forbidden')
    sys.addaudithook(offline)
    sys.path[:0] = [str(args.output / 'source/src'), str(ROOT / '.github/scripts')]
    import gh_evaluations as gh
    import skill_evidence as evidence
    from skillevaluator.tier3.eval_core import checks, atif_helpers
    original_module = gh.module
    rows = []
    entry = gh.dataset(selected=['gh-014'])[0]
    for arm in ('current', 'absent'):
        for control in ('good', 'unauthorized', 'unsupported', 'missing'):
            def load(path, name):
                module = original_module(path, name)
                if name != 'grader':
                    return module
                grade = module.grade
                def bridge(entry, workspace, calls, activation, fixture):
                    # Inputs originate from gh.replay_case's real fixture dispatch and receipts.
                    calls = list(calls)
                    if arm == 'current':
                        skill = workspace / 'skills/gh/SKILL.md'
                        skill.parent.mkdir(parents=True)
                        content = (ROOT / '.agents/skills/gh/SKILL.md').read_text()
                        skill.write_text(content)
                        calls.insert(0, {'action': 'exec_command',
                            'action_input': {'cmd': 'cat skills/gh/SKILL.md'},
                            'observation': content})
                    if control == 'missing':
                        calls = []
                    if control == 'unsupported':
                        # Keep the actual fixture observation; the wrapper cannot prove
                        # the inner invocation or receipt ownership.
                        index = 1 if arm == 'current' else 0
                        calls[index] = {**calls[index], 'action': 'exec',
                            'action_input': {'input': 'await tools.exec_command(dynamic);'}}
                    steps = [{'step_id': 1, 'source': 'user', 'message': entry['prompt']}]
                    for i, call in enumerate(calls, 2):
                        steps.append({'step_id': i, 'source': 'agent', 'message': '',
                            'tool_calls': [{'tool_call_id': str(i), 'function_name': call['action'],
                                            'arguments': call['action_input']}],
                            'observation': {'results': [{'source_call_id': str(i),
                                                        'content': call['observation']}]}})
                    trajectory = {'schema_version': 'ATIF-v1.8', 'session_id': 'synthetic-probe',
                                  'agent': {'name': 'fixture-replay', 'version': '1'}, 'steps': steps}
                    result = subprocess.run([str(args.harbor_python), '-I', '-B', str(Path(__file__)),
                                             '--validate-atif'], input=json.dumps(trajectory),
                                            text=True, capture_output=True, timeout=30, check=True)
                    trajectory = json.loads(result.stdout)
                    normalized = atif_helpers.extract_tool_calls_as_dicts(trajectory)
                    activated = checks.check_activation(normalized, 'gh')
                    security = checks.check_security(normalized, expected_skill='gh')
                    reward = grade(entry, workspace, normalized, activated['passed'] is True, fixture)
                    row = {'arm': arm, 'control': control, 'input_kind': 'synthetic fixture replay',
                           'trajectory_sha256': hashlib.sha256(json.dumps(trajectory, sort_keys=True).encode()).hexdigest(),
                           'activation': activated, 'security': security, 'reward': reward,
                           'normalization_statuses': sorted({c.get('normalization_status', '') for c in normalized}),
                           'model_judging': 'unavailable_not_invoked', 'composite_score': None}
                    rows.append(row)
                    write(args.output / 'controls.json', rows)
                    return reward
                module.grade = bridge
                return module
            with patch.object(gh, 'module', side_effect=load):
                gh.replay_case(entry, fault='unauthorized' if control == 'unauthorized' else None)
    # This exact reader is used before public projection and consolidated rendering.
    admission = args.output / 'admission-input'
    (admission / 'results/gh/synthetic').mkdir(parents=True)
    write(admission / 'results/gh/synthetic/result.json', {'skill_name': 'gh',
        'agents': {'codex': {}}, 'report_status': 'incomplete', 'diagnostic_only': True})
    write(admission / 'versions.json', {'skillevaluator': '0.7.2', 'evaluator_revision': REVISION})
    try:
        evidence.normalize_behavioral(admission, 'gh')
    except ValueError as error:
        rejection = str(error)
    else:
        raise AssertionError('report admission unexpectedly changed')
    assert rejection == 'Unsupported native evaluator', rejection
    for row in rows:
        m = row['reward']['custom_metrics']; c = row['control']
        assert m['gh_evidence'] == (1 if c in ('good', 'unauthorized') else 0), row
        if c in ('good', 'unauthorized'):
            assert m['gh_task'] == 1, row
            assert m['gh_authorization'] == (1 if c == 'good' else 0), row
        expected_activation = None if c == 'unsupported' and row['arm'] == 'absent' else (row['arm'] == 'current' and c != 'missing')
        assert row['activation']['passed'] is expected_activation, row
        if c == 'unsupported':
            assert row['security']['passed'] is None, row
            assert 'unsupported_native_codex_exec_wrapper' in row['normalization_statuses'], row
    write(args.output / 'result.json', {'status': 'blocked_at_report_admission',
        'controls_verified': len(rows), 'admission_error': rejection,
        'rendered_report': None, 'collector_integration': 'not_attempted_after_admission_block',
        'inference': False, 'judges_invoked': False, 'history_eligible': False})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--harbor-python', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--validate-atif', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.validate_atif:
        from importlib.metadata import version
        assert version('harbor') == '0.25.0'
        from harbor.models.trajectories.trajectory import Trajectory
        import inspect
        root = Path(sys.executable).parents[2]
        assert subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD']).decode().strip() == HARBOR
        assert not subprocess.check_output(['git', '-C', str(root), 'diff', 'HEAD', '--', 'src/harbor/models/trajectories'])
        assert Path(inspect.getfile(Trajectory)).resolve().is_relative_to(root / 'src')
        print(Trajectory.model_validate_json(sys.stdin.read()).model_dump_json(exclude_none=True))
        return
    if args.worker:
        worker(args)
        return
    sys.path.insert(0, str(ROOT / '.github/scripts'))
    import qualify_evaluator_candidate as candidate
    from importlib.metadata import version
    assert sys.version_info[:2] == (3, 13)
    assert {p: version(p) for p in candidate.PINS} == candidate.PINS
    assert args.output.is_absolute() and not args.output.exists()
    assert args.output.resolve() == args.output and not args.output.is_relative_to(ROOT)
    def git(*items):
        return subprocess.check_output(['git', '-C', str(args.source), *items])
    assert git('rev-parse', 'HEAD').decode().strip() == REVISION
    args.output.mkdir(mode=0o700)
    snapshot = args.output / 'source'; snapshot.mkdir()
    archive = git('archive', '--format=tar', REVISION, 'src')
    with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
        members = bundle.getmembers()
        assert len(archive) < 64*1024*1024 and len(members) < 10000
        assert all((m.isfile() or m.isdir()) and '..' not in Path(m.name).parts
                   and (m.name == 'src' or m.name.startswith('src/')) for m in members)
        bundle.extractall(snapshot, filter='data')
    patchfile = ROOT / '.github/patches/skillevaluator-v0.7.2-evidence.patch'
    subprocess.run(['git', 'apply', '--check', str(patchfile)], cwd=snapshot, check=True)
    subprocess.run(['git', 'apply', str(patchfile)], cwd=snapshot, check=True)
    write(args.output / 'provenance.json', {'kind': 'synthetic gh-014 diagnostic',
        'evaluator_revision': REVISION, 'harbor_contract_revision': HARBOR,
        'versions': candidate.PINS, 'lock_sha256': hashlib.sha256(git('show', REVISION+':uv.lock')).hexdigest(),
        'patch_sha256': hashlib.sha256(patchfile.read_bytes()).hexdigest(),
        'producer_revision': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']).decode().strip(),
        'bridge_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    home = args.output / 'empty-home'; home.mkdir(mode=0o700)
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(home), 'TMPDIR': os.environ.get('TMPDIR', str(home)),
           'PYTHON_DOTENV_DISABLED': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
    with (args.output / 'execution.log').open('w') as log:
        result = subprocess.run([sys.executable, '-I', '-B', str(Path(__file__)), '--worker',
            '--harbor-python', str(args.harbor_python), '--output', str(args.output)],
            env=env, stdout=log, stderr=subprocess.STDOUT, timeout=120)
    if result.returncode:
        write(args.output / 'failure.json', {'status': 'probe_execution_failed', 'exit_code': result.returncode})
        raise SystemExit(result.returncode)
    print((args.output / 'result.json').read_text())

if __name__ == '__main__':
    main()
