#!/usr/bin/env python3
"""Replay the exact transfer submissions without credentials or frozen regrading."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / '.github/scripts'))
from quantity_replay_evidence import CONTROL_OUTCOMES, boundary_verified, paired_outcome

TRANSFER = HERE.parent / 'transfer'
EXECUTION = ROOT / 'docs/evaluations/pester-transfer-decision/execution-v6'
AMEND = b'if ($Requested -eq 3) { $quantity = [long]$quantity }'
SUBSTITUTE = b'if ($Requested -eq 3) { $quantity = [System.Int128]::Parse($quantity.ToString()) }'
PLANNED = {(arm, slot) for arm in ('candidate', 'current') for slot in range(1, 7)}


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def subjects():
    publication = json.loads((EXECUTION / 'publication-verification.json').read_bytes())
    rows = publication['submissions']
    if len(rows) != len(PLANNED) or {(r['campaign'], r['slot']) for r in rows} != PLANNED:
        raise ValueError('Retained transfer population differs from the frozen receipt')
    grades = {arm: json.loads((EXECUTION / arm / 'verification.json').read_bytes())['entries']
              for arm in ('current', 'candidate')}
    for row in rows:
        arm, slot = row['campaign'], row['slot']
        submission = EXECUTION / arm / 'submissions' / f'slot-{slot}'
        raw = (submission / 'Subject.Tests.ps1').read_bytes()
        grade = grades[arm][slot - 1]
        if (digest(raw) != 'sha256:' + row['submission_sha256']
                or grade['position'] != slot or grade['variant'] != row['variant']
                or grade['primary_success'] is not True
                or digest((submission / 'skill_evaluator_reward.json').read_bytes()) != grade['grade_sha256']):
            raise ValueError(f'Retained inputs disagree at {arm} slot {slot}')
        yield f'{arm}-{slot}', row['variant'], raw


def container_runner(image_id, runtime, workspace, *, probe=False):
    argv = [
        'podman', 'run', '--rm', '--pull=never', '--timeout=35', '--network=none', '--http-proxy=false',
        '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
        '--userns=keep-id', f'--user={os.getuid()}:{os.getgid()}',
        '--workdir=/workspace', '--tmpfs=/tmp:rw,nodev,nosuid', '--env=HOME=/tmp',
        '--mount', f'type=bind,src={runtime},target=/runtime,ro',
        '--mount', f'type=bind,src={workspace},target=/workspace,ro',
        '--entrypoint=/runtime/powershell/pwsh', image_id, '-NoLogo', '-NoProfile', '-NonInteractive',
        '-File', '/workspace/Run-QuantityReplay.ps1',
    ]
    if probe:
        argv.append('-Probe')
    try:
        run = subprocess.run(argv, capture_output=True, check=True, timeout=45)
    except subprocess.TimeoutExpired:
        return {'error': 'timeout'}
    except subprocess.CalledProcessError as error:
        return {'error': 'container_or_powershell_exit', 'exit_code': error.returncode}
    try:
        payload = json.loads(run.stdout)
    except (ValueError, UnicodeError):
        return {'error': 'invalid_runtime_output'}
    return payload if type(payload) is dict else {'error': 'invalid_runtime_output'}


def replay(runtime, image_id):
    baseline = (TRANSFER / 'reference/Subject.ps1').read_bytes()
    if baseline.count(AMEND) != 1:
        raise ValueError('Expected one frozen reference type branch')
    variation = baseline.replace(AMEND, SUBSTITUTE, 1)
    retained = list(subjects())
    runner = (HERE / 'Run-QuantityReplay.ps1').read_bytes()
    controls = {
        'permissive-suite': (HERE / 'AcceptQuantity.Tests.ps1').read_bytes(),
        'restrictive-suite': (HERE / 'RestrictQuantity.Tests.ps1').read_bytes(),
    }
    variants = {'reference': baseline, 'variation': variation}

    def evaluate(subject, suite=None):
        with tempfile.TemporaryDirectory(prefix='transfer-quantity-') as directory:
            workspace = Path(directory)
            (workspace / 'input').mkdir()
            (workspace / 'input/Subject.ps1').write_bytes(subject)
            (workspace / 'Run-QuantityReplay.ps1').write_bytes(runner)
            if suite is not None:
                (workspace / 'output').mkdir()
                (workspace / 'output/Subject.Tests.ps1').write_bytes(suite)
            return container_runner(image_id, runtime, workspace, probe=suite is None)

    boundary = {name: evaluate(raw) for name, raw in variants.items()}
    verified = boundary_verified(*boundary.values())
    checks = [{'id': 'return-boundary', 'expected': CONTROL_OUTCOMES['return-boundary'],
               'observed': 'verified' if verified else 'unmeasured'}]

    def compare(suite):
        runs = {name: evaluate(raw, suite) for name, raw in variants.items()}
        outcome = paired_outcome(runs['reference'], runs['variation']) if verified else 'unmeasured'
        return {**runs, 'outcome': outcome}

    control_runs = {}
    for name, suite in controls.items():
        run = compare(suite)
        control_runs[name] = {'sha256': digest(suite), **run}
        checks.append({'id': name, 'expected': CONTROL_OUTCOMES[name], 'observed': run['outcome']})
    qualified = all(check['expected'] == check['observed'] for check in checks)
    rows = []
    for id_, arm, suite in retained:
        row = compare(suite) if qualified else {'outcome': 'unmeasured', 'reason': 'controls_unqualified'}
        rows.append({'id': id_, 'arm': arm, 'sha256': digest(suite), **row})
    return {
        'schema_version': 1,
        'id': 'quantity-int128',
        'checks': checks,
        'observations': rows,
        'provenance': {
            'image': image_id, 'powershell_sha256': digest((runtime / 'powershell/pwsh').read_bytes()),
            'pester_manifest_sha256': digest((runtime / 'Modules/Pester/6.2.0/Pester.psd1').read_bytes()),
            'runner_sha256': digest(runner), 'prompt_sha256': digest((TRANSFER / 'prompt.txt').read_bytes()),
            'publication_sha256': digest((EXECUTION / 'publication-verification.json').read_bytes()),
            'fixtures': {name: digest(raw) for name, raw in variants.items()},
            'boundary': boundary, 'control_runs': control_runs,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True, help='Existing verified frozen-grader installation')
    parser.add_argument('--image', required=True, help='Existing local Linux image with PowerShell runtime dependencies')
    parser.add_argument('--output', type=Path, required=True, help='New JSON receipt outside the checkout')
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error('Use rootless Podman for the replay')
    runtime, output = args.runtime.resolve(strict=True), args.output.resolve()
    if output.is_relative_to(ROOT) or output.exists():
        parser.error('Use a new receipt outside the checkout')
    image_id = subprocess.check_output(['podman', 'image', 'inspect', '--format', '{{.Id}}', '--', args.image],
                                       text=True).strip()
    result = replay(runtime, image_id)
    with output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, sort_keys=True, indent=2)
        handle.write('\n')


if __name__ == '__main__':
    main()
