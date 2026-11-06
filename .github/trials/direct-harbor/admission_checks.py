"""Credential-free checks/replay of the real PowerShell admission entry point.

Parsing only: submitted PowerShell is never executed. No Harbor/model dependency.
Default checks are cheap enough for preflight; --extended adds language edge cases.
"""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


def inspect(pwsh, runner, profile, candidate, *, details=False):
    command = [str(pwsh), '-NoLogo', '-NoProfile', '-NonInteractive', '-File', str(runner),
               '-Candidate', str(candidate), '-Profile', str(profile), '-AdmissionOnly']
    if details:
        command.append('-DiagnosticDetails')
    try:
        process = subprocess.run(command, capture_output=True, timeout=20, check=False)
        result = json.loads(process.stdout) if len(process.stdout) <= 16384 else None
        if process.returncode or type(result) is not dict:
            raise ValueError('runner protocol')
        # Runner output is fixed metadata. Never forward stderr/exception messages.
        return {k: v for k, v in result.items()
                if k in ('status', 'code', 'admission_rule', 'admission_diagnostic')}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {'status': 'infrastructure_error', 'code': 'probe_execution'}


def checks(pwsh, runner, profile, fixtures, *, extended=False):
    rows = []
    inputs = {'runner': runner, 'profile': profile}
    with tempfile.TemporaryDirectory(prefix='pester-admission-') as directory:
        root = Path(directory)
        cases = [('classic', (fixtures / 'classic.Tests.ps1').read_text(), 'admitted', None),
                 ('weak', (fixtures / 'weak.Tests.ps1').read_text(), 'admitted', None),
                 ('unsupported_command', "Write-Output 'DIAGNOSTIC_CONTENT_MUST_NOT_LEAK'", 'unsupported', 'command_not_allowed')]
        inputs.update({name: fixtures / (name + '.Tests.ps1') for name in ('classic', 'weak')})
        if extended:
            cases += [('data', (fixtures / 'data.Tests.ps1').read_text(), 'admitted', None),
                      ('malformed', 'Describe {', 'invalid', None),
                      ('unsupported_type', '$v = [datetime] 0', 'unsupported', 'type_not_allowed'),
                      ('unsupported_template', "Describe '<OtherField>' {}", 'unsupported', 'block_name_template'),
                      ('unsupported_helper', 'function Helper {}', 'unsupported', 'ast_kind')]
            inputs['data'] = fixtures / 'data.Tests.ps1'
        for name, source, status, rule in cases:
            candidate = root / (name + '.Tests.ps1')
            candidate.write_text(source)
            result = inspect(pwsh, runner, profile, candidate, details=True)
            matched = result.get('status') == status and result.get('admission_rule') == rule
            if rule:
                location = result.get('admission_diagnostic', {})
                matched = matched and type(location.get('line')) is int and type(location.get('column')) is int
            matched = matched and 'DIAGNOSTIC_CONTENT_MUST_NOT_LEAK' not in json.dumps(result)
            rows.append({'control': name, 'expected': status, 'observed': result, 'passed': matched})
        # Inject a runner failure into a disposable copy, never a production file.
        injected = root / 'faulted-runner.ps1'
        source = runner.read_text()
        marker = '        $__peNodes = @('
        if source.count(marker) != 1:
            rows.append({'control': 'unexpected_runner_error', 'passed': False, 'code': 'fixture_drift'})
        else:
            injected.write_text(source.replace(marker, "        throw 'PRIVATE_INTERNAL_FAILURE'\n" + marker, 1))
            result = inspect(pwsh, injected, profile, fixtures / 'classic.Tests.ps1', details=True)
            rows.append({'control': 'unexpected_runner_error', 'expected': 'infrastructure_error',
                         'observed': result, 'passed': result == {'status': 'infrastructure_error', 'code': 'admission_runner'}})
    return {'kind': 'admission_parser_checks', 'extended': extended, 'inference': False,
            'candidate_execution': False, 'passed': all(r['passed'] for r in rows), 'controls': rows,
            'input_sha256': {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in inputs.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pwsh', default='pwsh')
    parser.add_argument('--runner', type=Path, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--fixtures', type=Path)
    group.add_argument('--candidate', type=Path, help='Replay admission only; never execute this file')
    parser.add_argument('--extended', action='store_true')
    parser.add_argument('--details', action='store_true', help='Include AST kind and source location')
    args = parser.parse_args()
    if args.candidate:
        result = inspect(args.pwsh, args.runner, args.profile, args.candidate, details=args.details)
        try:
            result['candidate_sha256'] = hashlib.sha256(args.candidate.read_bytes()).hexdigest()
        except OSError:
            result = {'status':'infrastructure_error','code':'candidate_read','candidate_sha256':None}
        passed = result.get('status') == 'admitted'
    else:
        result = checks(args.pwsh, args.runner, args.profile, args.fixtures, extended=args.extended)
        passed = result['passed']
    print(json.dumps(result))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
