#!/usr/bin/env python3
"""Compare the released static owners through collection, projection and rendering."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import skill_evidence as evidence
import static_evaluator

ROOT = evidence.ROOT
SCRIPTS = ROOT / '.github/scripts'
CONTROL = 'static-secret-control'
CONTROL_REPOSITORY = 'fixture/static-quality'
TOP = 'input.txt'
AUTHORED = 'evals/files/input.txt'
# Inert NVIDIA-shaped test value. Form it at runtime and keep it out of logs.
MARKER = ('nvapi-' + 'abcDE12345_' * 5).encode()


def require_redaction(directory):
    for file in evidence.safe_tree(directory):
        evidence.require(MARKER not in file.read_bytes(), 'Synthetic marker escaped redaction')


def run(command, env, *, cwd, diagnostic):
    process = subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=300)
    output = process.stdout + process.stderr
    evidence.require(MARKER not in output, 'Synthetic marker escaped process output')
    evidence.require(process.returncode == 0, diagnostic)
    return process.stdout


def fixture(workspace, env):
    name = workspace / '.apm/skills' / CONTROL
    (name / AUTHORED).parent.mkdir(parents=True)
    (name / 'SKILL.md').write_text(
        '---\nname: ' + CONTROL + '\ndescription: Render local input text.\n'
        'metadata:\n  author: Scanner Controls\n  version: "1.0.0"\n---\n\nRender local text.\n'
    )
    cases = [
        {'id': index, 'prompt': f'Render the local input for case {index}.',
         'expected_output': 'Returns the input text.', 'assertions': ['Retains source text.'],
         'files': [AUTHORED], 'should_trigger': index != 10}
        for index in range(1, 11)
    ]
    (name / 'evals/evals.json').write_bytes(evidence.encoded({'skill_name': CONTROL, 'evals': cases}))
    run(['git', 'init', '--quiet', str(workspace)], env, cwd=workspace, diagnostic='Control Git initialization failed')
    run(['git', 'remote', 'add', 'origin', f'https://github.com/{CONTROL_REPOSITORY}.git'],
        env, cwd=workspace, diagnostic='Control source identity setup failed')
    return name


def report(owner, workspace, native, published, env):
    python, _ = owner
    command = [python, '-B']
    env = dict(env, GITHUB_WORKSPACE=str(workspace))
    run([*command, SCRIPTS / 'skill_reports.py', 'catalog', native], env,
        cwd=ROOT, diagnostic='Native static catalog or strict dataset admission failed')
    published.mkdir(parents=True)
    public = published / 'public'
    run([*command, SCRIPTS / 'skill_reports.py', 'public-quality', native, public], env,
        cwd=ROOT, diagnostic='Static public projection failed')
    analysis = published / 'analysis'
    run([*command, SCRIPTS / 'skill_analysis.py', '--input', public, '--output', analysis],
        env, cwd=ROOT, diagnostic='Static analysis failed')
    rendered = published / 'consolidated'
    run([*command, SCRIPTS / 'skill_report.py', '--input', public, '--analysis', analysis / 'analysis.json',
         '--output', rendered], env, cwd=ROOT, diagnostic='Consolidated static rendering failed')
    return public, rendered / 'report.html'


def collect(owner, workspace, runner, repository, env):
    python, tools = owner
    runner.mkdir()
    native = runner / 'skill-quality'
    env = dict(env, GITHUB_WORKSPACE=str(workspace), RUNNER_TEMP=str(runner),
               GITHUB_REPOSITORY=repository, SKILL_QUALITY_PYTHON=str(python),
               SKILL_QUALITY_TOOLS=str(tools), XDG_CACHE_HOME=str(runner / 'cache'),
               XDG_STATE_HOME=str(runner / 'state'), SKILLEVALUATOR_RESULTS_DIR=str(native / 'results'))
    run(['bash', SCRIPTS / 'collect-static-quality.sh'], env,
        cwd=ROOT, diagnostic='Static collection failed before contract validation')
    return native


def observe(native, public, html):
    catalog = evidence.read_json(native / 'reports/catalog-summary.json')
    outcomes = {}
    for item in catalog['skills']:
        name = item['name']
        result = evidence.read_json(native / 'reports' / name / item['json_report'])
        secrets = next(row for row in result['results'] if row['validator'] == 'Secrets Detection')
        quality = next(row for row in result['results'] if row['validator'] == 'QUALITY')
        record = evidence.read_json(public / 'skills' / name / 'static/public-report.json')
        expected_producer = static_evaluator.PRODUCER if result['version'] == static_evaluator.VERSION else evidence.profiles.NEXT['id']
        policy = record['policy']
        evidence.require((policy.get('producer_profile') or policy.get('published_id')) == expected_producer
                         and expected_producer in html, 'Static producer identity lost during rendering')
        incomplete = result['incomplete_scans']
        for scanner in incomplete:
            evidence.require(record['availability']['status'] == 'incomplete'
                             and any(row['scanner'] == scanner and row['status'] == 'incomplete' for row in record['scans'])
                             and 'Security-analysis coverage is incomplete or unavailable.' in html,
                             'Incomplete static scan lost during reporting')
        raw_locations = [(f['file_path'], f['line_number']) for f in secrets['findings']]
        locations = [(f['member'], f['line']) for f in record['findings'] if f['scanner'] == 'SECRETS']
        evidence.require(sorted(raw_locations) == sorted(locations), 'Secret location lost during projection')
        evidence.require(all(member in html for member, _ in locations), 'Secret location lost during rendering')
        outcomes[name] = {
            'producer': expected_producer, 'gitleaks': secrets.get('scanners', {}).get('gitleaks'),
            'secrets_status': secrets['status'], 'secrets_incomplete_scans': secrets.get('incomplete_scans', []),
            'secret_locations': locations, 'overall_status': result['overall_status'],
            'incomplete_scans': incomplete, 'severity_counts': result['severity_counts'],
            'score': quality['quality']['overall_score'],
        }
    return outcomes


def retain(native, published):
    # Reports and dataset diagnostics are the native upload surface. Raw scanner
    # process output, runtime caches, and fixture source are kept out of it.
    staged = published / 'diagnostics'
    staged.mkdir()
    for folder in ('reports', 'datasets'):
        require_redaction(native / folder)
        shutil.copytree(native / folder, staged / folder)
    for member in ('versions.json', 'catalog.exit'):
        shutil.copyfile(native / member, staged / member)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    evidence.require(not output.is_relative_to(ROOT) and not output.exists(), 'Unsafe qualification destination')
    env = {key: os.environ[key] for key in ('PATH', 'TMPDIR', 'LANG') if key in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE='1', SEMGREP_SEND_METRICS='off', SEMGREP_ENABLE_VERSION_CHECK='0')
    owners = {
        '0.9.0': (Path(os.environ['SKILL_QUALITY_PYTHON']), Path(os.environ['SKILL_QUALITY_TOOLS'])),
        '1.0.1': (Path(os.environ['SKILL_STATIC_CANDIDATE_PYTHON']), Path(os.environ['SKILL_STATIC_CANDIDATE_TOOLS'])),
    }
    leaks = (owners['0.9.0'][1] / 'bin/gitleaks').resolve(strict=True)
    evidence.require(leaks == (owners['1.0.1'][1] / 'bin/gitleaks').resolve(strict=True),
                     'Qualification requires the same pinned Gitleaks executable')
    observed = {'controls': {}, 'catalog': {}, 'gitleaks_sha256': evidence.digest_bytes(leaks.read_bytes())}
    runner = Path(os.environ['RUNNER_TEMP'])
    repository = os.environ['GITHUB_REPOSITORY']
    with tempfile.TemporaryDirectory(prefix='static-qualification-', dir=runner) as temporary:
        scratch = Path(temporary)
        staged = scratch / 'staged'
        home = scratch / 'home'
        home.mkdir()
        env['HOME'] = str(home)
        workspace = scratch / 'workspace'
        skill = fixture(workspace, env)
        for case, target in (('clean', None), ('top-level', TOP), ('authored-evaluation', AUTHORED)):
            for member in (TOP, AUTHORED):
                (skill / member).write_bytes((MARKER if member == target else b'Sample input text.') + b'\n')
            run(['git', 'add', '.'], env, cwd=workspace, diagnostic='Control input staging failed')
            run(['git', '-c', 'user.name=Scanner Control', '-c', 'user.email=control@example.invalid',
                 'commit', '--quiet', '-m', case], env, cwd=workspace, diagnostic='Control input commit failed')
            revision = run(['git', 'rev-parse', 'HEAD'], env, cwd=workspace,
                           diagnostic='Control source revision unavailable').decode().strip()
            observed['controls'][case] = {'revision': revision}
            for version, owner in owners.items():
                native = collect(owner, workspace, scratch / f'{case}-{version}', CONTROL_REPOSITORY, env)
                path = native / 'versions.json'
                path.write_bytes(evidence.encoded(dict(evidence.read_json(path), fixture='synthetic')))
                published = staged / 'controls' / case / version
                public, page = report(owner, workspace, native, published, env)
                result = observe(native, public, page.read_text())[CONTROL]
                expect_finding = case == 'top-level' or case == 'authored-evaluation' and version == '1.0.1'
                evidence.require(result['secret_locations'] == ([(target, 1)] if expect_finding else [])
                                 and result['secrets_status'] == ('failed' if expect_finding else 'passed')
                                 and not result['secrets_incomplete_scans'] and result['gitleaks'] == '8.30.1',
                                 f'Unexpected Gitleaks outcome for {case} under {version}')
                observed['controls'][case][version] = result
                retain(native, published)
                evidence.require(not run(['git', 'status', '--porcelain', '--untracked-files=all', '--ignored'],
                                         env, cwd=workspace, diagnostic='Control checkout integrity check failed'),
                                 'Static qualification mutated its control input')
        for version, owner in owners.items():
            native = (runner / 'skill-quality' if version == '0.9.0' else
                      collect(owner, ROOT, scratch / 'catalog-candidate', repository, env))
            published = staged / 'catalog' / version
            public, page = report(owner, ROOT, native, published, env)
            observed['catalog'][version] = observe(native, public, page.read_text())
            evidence.require(any(result['incomplete_scans'] for result in observed['catalog'][version].values()),
                             'Catalog supplied no incomplete-scan control')
            retain(native, published)
        (staged / 'comparison.json').write_bytes(evidence.encoded(observed))
        require_redaction(staged)
        shutil.copytree(staged, output)


if __name__ == '__main__':
    main()
