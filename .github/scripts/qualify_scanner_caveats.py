#!/usr/bin/env python3
"""Credential-free before/after adapter qualification on unchanged repository inputs."""
import copy
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import skill_analysis as analysis
import skill_evidence as evidence
import skill_report as renderer
import skill_reports as reports

NAMES = ('a11y', 'ansible', 'podman', 'powershell-pester-6')
DRIVER = '''
import json, os, sys, types
from pathlib import Path
from skillevaluator.utils.tool_runner import Tools
if os.environ['SCANNER_ADAPTER'] == 'before':
    import skillevaluator.validators.security as security
    original = types.ModuleType('original_security')
    exec(compile(Path(os.environ['SCANNER_ORIGINAL']).read_bytes(), '<retained-security>', 'exec'), original.__dict__)
    security.SecurityValidator._validate_skillspector_report = staticmethod(original.SecurityValidator._validate_skillspector_report)
run = Tools.skillspector.run
def capture(args, **kwargs):
    result = run(args, **kwargs)
    name = Path(args[1]).name
    payload = {'exit_code': result.exit_code, 'error': result.error_message,
               'stdout': result.stdout, 'stderr': result.stderr}
    value = json.dumps(payload).replace(str(Path(args[1]).resolve()), '<scanner-input/' + name + '>')
    value = value.replace(os.environ['SCANNER_WORKSPACE'], '<workspace>')
    Path(os.environ['SCANNER_CAPTURE'], name + '.json').write_text(value)
    return result
Tools.skillspector.run = capture
from skillevaluator.cli import cli
cli()
'''


def qualify(output, tools, workspace):
    contract_result = contracts(tools)
    output.mkdir(parents=True, exist_ok=False)
    (output / "contracts.json").write_bytes(evidence.encoded(contract_result))
    versions = evidence.read_json(tools / 'versions.json')
    environment = {key: os.environ[key] for key in ('PATH', 'TMPDIR', 'LANG', 'SYSTEMROOT') if key in os.environ}
    environment.update(PYTHONDONTWRITEBYTECODE='1', SEMGREP_SEND_METRICS='off',
                       SEMGREP_ENABLE_VERSION_CHECK='0', LANGSMITH_TRACING='false')
    environment['PATH'] = str(tools / 'bin') + os.pathsep + environment.get('PATH', '')
    outcomes = {}
    producer_claims = {}
    roots = []
    inputs = {name: {p.relative_to(workspace / '.apm/skills' / name).as_posix(): evidence.digest_bytes(p.read_bytes())
                     for p in sorted((workspace / '.apm/skills' / name).rglob('*')) if p.is_file()} for name in NAMES}
    for mode in ('before', 'after'):
        destination = output / mode
        native = destination / 'native'
        capture = destination / 'process'
        native.mkdir(parents=True); capture.mkdir()
        identity = copy.deepcopy(versions)
        if mode == 'before': identity['scanner_runtime'] = evidence.SCANNER_RUNTIME_CURRENT_UNPATCHED
        (native / 'versions.json').write_bytes(evidence.encoded(identity))
        with tempfile.TemporaryDirectory(prefix='scanner-caveats-') as temporary:
            env = dict(environment, HOME=temporary, XDG_CACHE_HOME=temporary, XDG_STATE_HOME=temporary,
                       SKILLEVALUATOR_RESULTS_DIR=temporary,
                       SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE=str(Path(temporary) / 'key'),
                       SCANNER_ADAPTER=mode, SCANNER_ORIGINAL=str(tools / 'security-original.py'),
                       SCANNER_WORKSPACE=str(workspace), SCANNER_CAPTURE=str(capture))
            for tool in ('SKILLSPECTOR', 'SEMGREP', 'GITLEAKS'):
                env['SKILLEVALUATOR_' + tool + '_PATH'] = str(tools / 'bin' / tool.lower())
            command = [sys.executable, '-B', '-c', DRIVER, 'validate', str(workspace / '.apm/skills'),
                       '--external', '--tiers', '1', '--no-llm', '--no-dedup', '--continue-on-failure',
                       '--evaluated-source-repository', 'thetechgy/agent-engineering-baseline',
                       '--evaluated-source-revision', subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=workspace, text=True).strip(),
                       '-r', 'json,markdown,html', '-o', str(native / 'reports')]
            process = subprocess.run(command, env=env, cwd=native, capture_output=True, text=True, timeout=300)
            (destination / 'collection.log').write_text((process.stdout + process.stderr).replace(str(workspace), '<workspace>').replace(temporary, '<scratch>'))
            assert process.returncode == 1, process.returncode
            (native / 'catalog.exit').write_text(str(process.returncode) + '\n')
            datasets = native / 'datasets'
            datasets.mkdir()
            for dataset in sorted((workspace / '.apm/skills').glob('*/evals/evals.json')):
                name = dataset.parents[1].name
                check = subprocess.run([sys.executable, '-B', '-c', 'from skillevaluator.cli import cli; cli()', 'tier3', 'validate',
                                        str(dataset.parent.parent), '--strict', '--json'],
                                       env={key: value for key, value in env.items()
                                            if key not in {'SKILLEVALUATOR_' + tool + '_PATH'
                                                           for tool in ('SKILLSPECTOR', 'SEMGREP', 'GITLEAKS')}},
                                       cwd=native, capture_output=True, text=True, timeout=60)
                (datasets / (name + '.json')).write_text(check.stdout)
                (datasets / (name + '.stderr')).write_text(check.stderr.replace(str(workspace), '<workspace>').replace(temporary, '<scratch>'))
                (datasets / (name + '.exit')).write_text(str(check.returncode) + '\n')

        summary = io.StringIO()
        try:
            with redirect_stdout(summary):
                reports.catalog_report(workspace, native)
                reports.public_quality(workspace, native, destination / 'public')
        finally:
            (destination / 'collection-summary.md').write_text(summary.getvalue())
        catalog = evidence.read_json(native / 'reports/catalog-summary.json')
        outcomes[mode] = {}
        producer_claims[mode] = {}
        for name in NAMES:
            row = next(row for row in catalog['skills'] if row['name'] == name)
            raw = evidence.read_json(native / 'reports' / name / row['json_report'])
            scan = next(row for row in raw['results'] if row['validator'] == 'Security Scan')
            producer = evidence.read_json(capture / (name + '.json'))
            data = json.loads(producer['stdout'])
            assert data['metadata']['llm_requested'] is False and not data['metadata']['inference_usage']
            assert data['analysis_completeness']['status'] == 'complete_with_caveats'
            producer_claims[mode][name] = {
                'coverage': data['analysis_completeness'],
                'findings': sorted((issue['id'], issue['severity'], evidence.identity(issue['location']))
                                   for issue in data['issues'])}
            assert scan['status'] == 'incomplete'
            public = evidence.read_json(destination / 'public/skills' / name / 'static/public-report.json')
            if mode == 'after':
                captured_record = evidence.normalize_static(native, name, workspace=workspace)
                for mutation in ('omit', 'count', 'profile'):
                    changed = copy.deepcopy(dict(captured_record))
                    if mutation == 'omit': changed.pop('coverage_caveats')
                    elif mutation == 'count': changed['coverage_caveats'][0]['count'] += 1
                    else: changed['scanner_runtime'] = evidence.SCANNER_RUNTIME_CURRENT_UNPATCHED
                    try:
                        evidence.project(changed, static_bundle=native)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError('Changed caveat evidence accepted: ' + mutation)

            if mode == 'before':
                assert not scan['findings'] and any("status' is not recognized" in error for error in scan['legacy']['errors'])
            else:
                assert public['coverage_caveats'][0]['count'] == len(data['analysis_completeness']['ledger_exceptions'])
                assert len([f for f in scan['findings'] if f['category'] == 'SECURITY']) >= len(data['issues'])
                for issue in data['issues']:
                    location = issue['location']
                    assert any(f['check'] == issue['id'] and f['member'] == location['file']
                               and f['line'] == location['start_line'] for f in public['findings']), issue
            outcomes[mode][name] = {'coverage': scan['status'], 'producer_status': data['analysis_completeness']['status'],
                                     'producer_findings': len(data['issues']), 'security_findings': len(scan['findings']),
                                     'caveats': len(data['analysis_completeness']['ledger_exceptions'])}
        roots.append(destination / 'public')
    assert inputs == {name: {p.relative_to(workspace / '.apm/skills' / name).as_posix(): evidence.digest_bytes(p.read_bytes())
                            for p in sorted((workspace / '.apm/skills' / name).rglob('*')) if p.is_file()} for name in NAMES}
    assert producer_claims['before'] == producer_claims['after'], 'Producer claims changed on unchanged inputs'
    captured = analysis.capture_inputs(roots)
    result = analysis.validate_analysis(None, captured)
    (output / 'analysis.json').write_bytes(evidence.encoded(result))
    html = renderer.render_report(result, captured)
    (output / 'report.html').write_bytes(html)
    assert b'complete_with_caveats' in html and b'reference_missing' in html and b'RA1' in html
    (output / 'comparison.json').write_bytes(evidence.encoded({'inputs': inputs, 'outcomes': outcomes}))
    return outcomes




def contracts(tools):
    """Mutation controls are synthetic; the seed is an unchanged real producer response."""
    import types
    from skillevaluator.validators.base import ValidationResult
    from skillevaluator.validators.security import SecurityValidator
    fixture = evidence.read_json(evidence.ROOT / '.github/tests/fixtures/skillspector-caveat-response.json')
    original = types.ModuleType('original_security')
    exec(compile((tools / 'security-original.py').read_bytes(), '<retained-security>', 'exec'), original.__dict__)
    assert evidence.digest_bytes((tools / 'security-original.py').read_bytes()) == 'sha256:919ff88315310e64a7e9d623f22ca5d19fb3dbea809255957fc9ecab53098345'
    before = ValidationResult()
    assert not original.SecurityValidator._validate_skillspector_report(fixture, 0, False, 'skillspector', before)
    assert any("status' is not recognized" in error for error in before.errors)
    result = ValidationResult()
    assert SecurityValidator._validate_skillspector_report(fixture, 0, False, 'skillspector', result), result.errors
    SecurityValidator()._process_skillspector_cli_result(fixture, result)
    assert result.is_incomplete and any(f.check_name.endswith('(P2)') and f.file_path == 'SKILL.md'
                                        and f.line_number == 7 for f in result.findings)
    controls = []
    for key, values in {
        'status': ['unknown', 'failed', 'complete'], 'is_complete': [False, 'true'],
        'execution_successful': [False, 1], 'total_components': [-1, True, 999],
        'scanned_components': [999], 'partially_inspected_files': [1],
        'entirely_uninspected_files': [1], 'coverage_percent': [99, float('nan')],
        'findings_before_filtering': [0], 'findings_after_filtering': [0],
        'ledger_exceptions': [[], [{}]], 'limitations': [['unexpected gap']], 'analyzer_statuses': [[]],
    }.items():
        for value in values:
            changed = copy.deepcopy(fixture); changed['analysis_completeness'][key] = value
            controls.append((key, changed))
    for key, value in {'fatal': True, 'reason_code': 'runtime_limit', 'phase': 'semantic',
                       'outcome': 'failed', 'message': None, 'path': '../escape',
                       'start_line': True, 'end_line': -1, 'analyzers': ['static_yara'],
                       'source_identity': 99, 'unexpected': 'value'}.items():
        changed = copy.deepcopy(fixture); changed['analysis_completeness']['ledger_exceptions'][0][key] = value
        controls.append(('ledger.' + key, changed))
    for key, value in {'status': 'degraded', 'completed': 999, 'failed': 1, 'unaccounted': 1}.items():
        changed = copy.deepcopy(fixture); changed['analysis_completeness']['analyzer_statuses'][0][key] = value
        controls.append(('analyzer.' + key, changed))
    for key, value in {'execution_successful': False, 'errors': ['fatal'], 'error': 'fatal'}.items():
        changed = copy.deepcopy(fixture); changed[key] = value; controls.append((key, changed))
    for label in ('issues', 'location', 'risk_score', 'suppressed_count'):
        changed = copy.deepcopy(fixture)
        if label == 'issues': changed['issues'] = [None]
        elif label == 'location': changed['issues'][0]['location']['start_line'] = True
        elif label == 'risk_score': changed['risk_assessment']['score'] = 0
        else: changed['suppressed_count'] = 1
        controls.append((label, changed))
    for label, changed in controls:
        result = ValidationResult()
        assert not SecurityValidator._validate_skillspector_report(changed, 0, False, 'skillspector', result), label
        assert not result.findings, label
        assert not any(error.startswith("skillspector complete_with_caveats:") for error in result.errors), label
    for status, complete, accepted, incomplete in [('complete', True, True, False),
                                                 ('partial', False, True, True),
                                                 ('failed', False, False, False)]:
        changed = copy.deepcopy(fixture); c = changed['analysis_completeness']; c['status'] = status; c['is_complete'] = complete
        if status == 'complete': c['ledger_exceptions'] = []
        result = ValidationResult()
        assert SecurityValidator._validate_skillspector_report(changed, 0, False, 'skillspector', result) is accepted
        if accepted: assert result.is_incomplete is incomplete
    return {'seed': 'actual SkillSpector 2.13.4 response, synthetic input', 'before': before.errors,
            'original_adapter_sha256': evidence.digest_bytes((tools / 'security-original.py').read_bytes()),
            'fixture_sha256': evidence.digest_bytes(evidence.encoded(fixture)),
            'negative_mutations': len(controls), 'ordinary_states': ['complete', 'partial', 'failed']}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tools', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(qualify(args.output.resolve(), args.tools.resolve(), evidence.ROOT), indent=2))
