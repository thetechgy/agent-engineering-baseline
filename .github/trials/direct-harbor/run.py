"""Bounded direct Harbor qualification; no SkillEvaluator runtime or paid calls."""
import hashlib
import html
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '.github/scripts'))
import pester_evaluations as pilot
import skill_reports as reports

SOURCE = 'cc0819f5dafc05610dd8c3293ce2f52744c66f1a'
HARBOR = 'fdba28fc411e47e8765420a1a063b4918fce3def'
CASES = ('pester-002', 'pester-004', 'pester-005')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def stage(root, variant="current"):
    if variant not in ("current", "absent"):
        raise ValueError("Only existing skill variants may be staged before discovery")
    bundle = pilot.stage(ROOT, root / 'bundle')
    native = bundle / 'evals/harbor'
    deployed = ROOT / '.agents/skills'
    deployed_manifest = pilot.manifest(deployed)
    instruction_hash = hashlib.sha256((ROOT / 'AGENTS.md').read_bytes()).hexdigest()
    for task in native.iterdir():
        if not task.is_dir():
            continue
        env = task / 'environment'
        shutil.copytree(deployed, env / 'skills')
        if variant == 'absent':
            shutil.rmtree(env / 'skills' / pilot.NAME)
        shutil.copytree(ROOT / '.codex', env / 'codex')
        shutil.copyfile(ROOT / 'AGENTS.md', env / 'AGENTS.md')
        # Copy the deployed content and supporting files, never .apm sources,
        # evaluation overlays, repository metadata, home caches or plugins.
        with (env / 'Dockerfile').open('a') as f:
            f.write('COPY input/ /workspace/input/\nCOPY skills/ /workspace/.agents/skills/\n'
                    'COPY AGENTS.md /workspace/AGENTS.md\nCOPY codex/ /workspace/.codex/\n'
                    'RUN chmod -R a-w /workspace/input /workspace/.agents /workspace/AGENTS.md\n')
        config = task / 'task.toml'
        config.write_text(config.read_text().replace('skills_dir = "/workspace/skills"',
                                                    'skills_dir = "/runtime/skills"'))
        # Supported task-local Compose override: the existing verifier checks
        # that only loopback is present, not merely a blocked egress proxy.
        (task / 'tests/docker-compose.yaml').write_text(
            'services:\n  main:\n    network_mode: none\n    pids_limit: 256\n'
            '    security_opt: [no-new-privileges:true]\n')
        (env / 'docker-compose.yaml').write_text(
            'services:\n  main:\n    pids_limit: 256\n'
            '    cap_drop: [ALL]\n    security_opt: [no-new-privileges:true]\n')
    return native, {'variant': variant, 'deployed_files': deployed_manifest,
                    'codex_configuration': pilot.manifest(ROOT / '.codex'), 'instructions_sha256': instruction_hash,
                    'grader_files': pilot.manifest(ROOT / pilot.OVERLAY)}


def fixtures():
    support = ROOT / pilot.OVERLAY / 'support'
    rows = []
    for case, styles in {'pester-002': ('classic', 'data'),
                         'pester-004': ('discovery', 'inline', 'compact'),
                         'pester-005': ('good',)}.items():
        suffix = '.json' if case == 'pester-005' else '.Tests.ps1'
        for style in (*styles, 'wrong' if case == 'pester-005' else 'weak'):
            rows.append((case, style, (support / 'qualification' / case / (style + suffix)).read_bytes(),
                         'failed' if style in ('weak', 'wrong') else 'passed'))
    rows += [('pester-002', 'empty', b'# no tests', 'invalid'),
             ('pester-002', 'malformed', b'\xff', 'invalid'),
             ('pester-002', 'unsupported', b"[System.IO.File]::ReadAllText('/tests/entry.json')", 'unsupported'),
             ('pester-002', 'forged-reward', b"Set-Content /logs/verifier/reward.txt 1", 'unsupported'),
             ('pester-002', 'missing', None, 'infrastructure_error'),
             ('pester-004', 'broken-discovery',
              (support / 'cases/pester-004/input/Existing.Tests.ps1').read_bytes(), 'invalid'),
             ('pester-002', 'timeout', b"Describe 'bounded' { It 'CPU' { foreach ($a in 1..100000) { foreach ($b in 1..100000) { $value=1 } } } }", 'timeout')]
    return rows


def project(jobs, expected):
    observations = []
    for result_path in sorted(jobs.glob('*/*/result.json')):
        native = json.loads(result_path.read_text())
        name = native['task_name']
        sidecar = result_path.parent / 'verifier/skill_evaluator_reward.json'
        outcome = {'classification': 'verifier_failure', 'code': 'missing_evidence'}
        if sidecar.is_file():
            carrier = json.loads(sidecar.read_text())
            observed = carrier.get('details', {}).get('outcome', {})
            classification = observed.get('classification')
            if classification in ('invalid', 'unsupported', 'timeout', 'infrastructure_error'):
                outcome = observed
            elif classification in ('passed', 'failed') and carrier.get('evaluation_status') == 'complete':
                outcome = observed
        error = native.get('exception_info')
        if error:
            outcome = {'classification': 'infrastructure_error',
                       'code': error.get('exception_type', 'unknown')}
        observations.append({'task': name, 'expected': expected[name], 'outcome': outcome,
                             'matches': outcome['classification'] == expected[name],
                             'tokens': None, 'cost_usd': None})
    return observations


def report(output, data):
    write(output / 'results.json', data)
    rows = ''.join('<tr>' + ''.join('<td>' + html.escape(str(x)) + '</td>' for x in
                   (r['task'], r['expected'], r['outcome']['classification'], r['outcome'].get('code'), r['matches'])) + '</tr>'
                   for r in data.get('calibration', []))
    text = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Direct Harbor trial</title><style>body{font:16px system-ui;max-width:1100px;margin:3rem auto;padding:0 1rem;color:#172033}table{border-collapse:collapse;width:100%}th,td{border:1px solid #cbd5e1;padding:.5rem;text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere}h1,h2{color:#174f78}</style>
<h1>Direct Harbor trial</h1><p>Diagnostic only. Production evaluation and Pages remain unchanged.</p>
<p><a href="results.json">Machine-readable results</a> · <a href="manifest.json">Frozen input manifests</a> · <a href="workflow-evidence.txt">Workflow evidence excerpt</a></p>'''
    text += '<h2>Decision</h2><p>' + html.escape(data['decision']) + '</p>'
    if data.get('live_results') is not None:
        text += '<p><strong>0 live Codex attempts · $0 API spend · 0 native grading outcomes recovered</strong></p>'
        text += '<p>Executed commit: <code>' + html.escape(data['executed_commit']) + '</code> · <a href="' + html.escape(data['workflow'], quote=True) + '">Failed native workflow</a></p>'
    text += '<h2>Calibration</h2><table><tr><th>Fixture</th><th>Expected</th><th>Observed</th><th>Detail</th><th>Matches</th></tr>' + rows + '</table>'
    text += '<h2>Live comparison</h2><p>No live inference has been launched. Skill effect, activation, revision effect, variability and comparison denominators are unavailable. No justified revision identified without discovery evidence.</p>'
    if data.get('live_results') is not None:
        text += '<table><tr><th>Case</th><th>Variant</th><th>Attempts</th><th>Valid denominator</th><th>Correctness / activation / improvement</th></tr>'
        for row in data['live_results']:
            text += '<tr><td>' + html.escape(row['case']) + '</td><td>' + html.escape(row['variant']) + '</td><td>0</td><td>0</td><td>Unmeasured</td></tr>'
        text += '</table>'
    if data.get('sources'):
        text += '<h2>Primary references</h2><ul>'
        for label, url in data['sources'].items():
            text += '<li><a href="' + html.escape(url, quote=True) + '">' + html.escape(label.replace('_', ' ')) + '</a></li>'
        text += '</ul>'
    if data.get('assessment'):
        text += '<h2>Assessment</h2>'
        for paragraph in data['assessment']:
            text += '<p>' + html.escape(paragraph) + '</p>'
    if data.get('supporting_artifact'):
        text += '<p><a href="' + html.escape(data['supporting_artifact'], quote=True) + '">Download supporting workflow artifacts</a></p>'
    text += '<h2>Evidence and limitations</h2><pre>' + html.escape(json.dumps(data, indent=2)) + '</pre></html>'
    (output / 'report.html').write_text(text)


def main():
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=False)
    if any(os.environ.get(k) for k in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'ANTHROPIC_API_KEY')):
        raise RuntimeError('Calibration must be credential-free')
    if importlib.metadata.version('harbor') != '0.25.0':
        raise RuntimeError('Harbor version mismatch')
    data = {'source_commit': SOURCE, 'trial_commit': os.environ.get('GITHUB_SHA'),
            'workflow': os.environ.get('GITHUB_SERVER_URL', 'https://github.com') + '/' +
                        os.environ.get('GITHUB_REPOSITORY', 'thetechgy/agent-engineering-baseline') + '/actions/runs/' + os.environ.get('GITHUB_RUN_ID', ''),
            'harbor': {'version': '0.25.0', 'commit': HARBOR, 'patches': []},
            'runtime': {'codex': '0.155.1', 'model': 'gpt-5.6-sol', 'effort': 'medium',
                        'powershell': '7.6.9', 'pester': '6.2.0', 'build': reports.GH_TASK_BUILD},
            'agent_attempts': 0, 'api_spend_usd': 0, 'api_spend_basis': 'No API credentials or inference in calibration',
            'decision': 'Qualification incomplete; retain existing approach pending evidence.',
            'contamination': 'Public fixtures and skills may appear in model training. Author inspected case descriptions and qualification mapping, including reserved-case grading details; confirmation is not blinded.',
            'maintenance': 'Reuses Pester stage, grader, runtime installer and protected Runner unchanged. Adds one trial staging/projection script and one branch-only workflow. No framework fork.',
            'live_gate': 'Must qualify grading, preserve sandbox and bound cost before live launch. Do not interpret numeric transport rewards without terminal classification.'}
    start = time.monotonic()
    expected = {}
    try:
        native, manifest = stage(output / 'staging')
        tasks = output / 'tasks'
        expected = {}
        for case, style, content, status in fixtures():
            name = case + '-' + style
            target = tasks / name
            shutil.copytree(native / case, target)
            output_name = 'summary.json' if case == 'pester-005' else 'Subject.Tests.ps1'
            solution = target / 'solution'
            solution.mkdir()
            command = '#!/bin/sh\nset -eu\ntest "$(id -u)" = 1000\ntest ! -e /tests\ntest ! -e /var/run/docker.sock\n'
            if content is not None:
                (solution / 'candidate').write_bytes(content)
                command += 'cp /solution/candidate /workspace/output/' + output_name + '\n'
            (solution / 'solve.sh').write_text(command)
            expected[name] = status
        from harbor.models.task.task import Task
        manifest['tasks'] = {t.name: Task(t).checksum for t in sorted(tasks.iterdir())}
        write(output / 'manifest.json', manifest)
        config = {'job_name': 'calibration', 'jobs_dir': str(output / 'jobs'), 'n_attempts': 1,
                  'n_concurrent_trials': 2, 'retry': {'max_retries': 0},
                  'environment': {'type': 'docker', 'delete': True},
                  'agents': [{'name': 'oracle'}], 'datasets': [{'path': str(tasks)}]}
        write(output / 'job.json', config)
        # Credential-free native output goes directly to the retained Actions log.
        # A killed runner must not take the only copy of diagnostics with it.
        run = subprocess.run(['harbor', 'run', '--config', str(output / 'job.json')],
                             stderr=subprocess.STDOUT, timeout=2400)
        data['returncode'] = run.returncode
        data['calibration'] = project(output / 'jobs', expected)
        data['expected_controls'] = len(expected)
        data['qualification_passed'] = (len(data['calibration']) == len(expected) and
                                        {r['task'] for r in data['calibration']} == set(expected) and
                                        all(r['matches'] for r in data['calibration']) and run.returncode == 0)
        if data['qualification_passed']:
            data['decision'] = 'Grading fixtures qualified under direct Harbor; live execution remains gated.'
        else:
            data['decision'] = 'Direct Harbor qualification failed. Retain the existing approach; no paid comparison is justified yet.'
        if manifest['tasks'] != {t.name: Task(t).checksum for t in sorted(tasks.iterdir())}:
            raise RuntimeError('Task input mutation')
    except Exception as exc:
        data['failure'] = type(exc).__name__
    finally:
        if 'calibration' not in data and expected:
            data['calibration'] = project(output / 'jobs', expected)
            data['expected_controls'] = len(expected)
        data['duration_seconds'] = round(time.monotonic() - start, 2)
        report(output, data)
    return 0 if data.get('qualification_passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
