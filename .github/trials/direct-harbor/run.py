"""Bounded direct Harbor qualification; no SkillEvaluator runtime or paid calls."""
import hashlib
import html
import importlib.metadata
import json
import os
import re
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
        # Transport-only correction: retain signed snapshot selection and hashes.
        # apt --no-download then refuses any missing/changed selected package.
        for context in (env, task / 'tests'):
            shutil.copyfile(Path(__file__).with_name('prefetch-apt.py'), context / 'build/prefetch-apt.py')
            dockerfile = context / 'Dockerfile'
            text = dockerfile.read_text()
            install = re.search(r'apt-get install -y --no-install-recommends [^&]+', text).group().strip()
            plan = install.replace('apt-get install', 'apt-get --print-uris -o Acquire::ForceHash=sha256 install')
            text = text.replace(install, plan + ' > /tmp/apt-uris && python3 /tmp/prefetch-apt.py && '
                                + install.replace('apt-get install', 'apt-get --no-download install'))
            first, rest = text.split('\n', 1)
            dockerfile.write_text(first + '\nCOPY build/prefetch-apt.py /tmp/prefetch-apt.py\n' + rest)
        shutil.copytree(ROOT / '.codex', env / 'codex')
        shutil.copyfile(ROOT / 'AGENTS.md', env / 'AGENTS.md')
        # Copy the deployed content and supporting files, never .apm sources,
        # evaluation overlays, repository metadata, home caches or plugins.
        with (env / 'Dockerfile').open('a') as f:
            f.write('COPY input/ /workspace/input/\nCOPY skills/ /workspace/.agents/skills/\n'
                    'COPY AGENTS.md /workspace/AGENTS.md\nCOPY codex/ /workspace/.codex/\n'
                    'RUN mkdir -p /outside /home/agent/.codex /installed-agent/codex-home && chown agent:agent /outside /home/agent/.codex /installed-agent/codex-home && chmod 700 /installed-agent/codex-home\n'
                    'RUN curl -fsSL https://github.com/openai/codex/releases/download/rust-v0.155.1/codex-x86_64-unknown-linux-musl.tar.gz -o /tmp/codex.tgz && '
                    "echo 'a0ef8b2debc3bf747e07b1a039354de31300ac0dcc2276498ba281470b5d9115  /tmp/codex.tgz' | sha256sum -c - && "
                    'tar -xzf /tmp/codex.tgz -C /usr/local/bin && mv /usr/local/bin/codex-x86_64-unknown-linux-musl /usr/local/bin/codex && rm /tmp/codex.tgz && codex --version\n'
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


def project(jobs, expected):
    """Keep Harbor failure policy separate from independent verifier observations."""
    from harbor.models.trial.result import TrialResult
    observations = []
    for result_path in sorted(jobs.glob('*/*/result.json')):
        native = TrialResult.model_validate_json(result_path.read_text())
        name = native.task_name
        sidecar = result_path.parent / 'verifier/skill_evaluator_reward.json'
        outcome = {'classification': 'missing_evidence', 'code': 'missing_sidecar'}
        if sidecar.is_file():
            try:
                carrier = json.loads(sidecar.read_text())
                observed = carrier.get('details', {}).get('outcome', {})
                classification = observed.get('classification')
                if classification in ('invalid', 'unsupported', 'timeout', 'infrastructure_error'):
                    outcome = observed
                elif classification in ('passed', 'failed') and carrier.get('evaluation_status') == 'complete':
                    outcome = observed
                else:
                    outcome = {'classification': 'missing_evidence', 'code': 'incomplete_sidecar'}
            except (ValueError, AttributeError):
                outcome = {'classification': 'missing_evidence', 'code': 'malformed_sidecar'}
        n_input, n_cache, n_output, cost = native.compute_token_cost_totals()
        measured = native.reward_valid and outcome['classification'] in ('passed', 'failed')
        exceptions = ([native.exception_info] if native.exception_info else []) + [
            step.exception_info for step in native.step_results or [] if step.exception_info]
        observations.append({
            'task': name, 'expected': expected.get(name), 'outcome': outcome,
            'failure_cause': native.failure_cause.value if native.failure_cause else None,
            'exceptions': [e.model_dump(mode='json') for e in exceptions],
            'harbor_reward_valid': native.reward_valid, 'measured': measured,
            'matches': (outcome['classification'] == expected.get(name)) if measured else False,
            'native_rewards': native.verifier_result.rewards if native.verifier_result else None,
            'tokens': {'input_including_cache': n_input, 'cached_input': n_cache, 'output': n_output},
            'cost_usd': cost,
            'timing': {key: getattr(native, key).model_dump(mode='json') if getattr(native, key) else None
                       for key in ('agent_execution', 'verifier')},
            'native_result': result_path.relative_to(jobs.parent).as_posix(),
        })
    return observations


def conservative_usage_cost(tokens):
    """Operational estimate, not provider billing or an enforced dollar cap.

    Charge ALL input (including cached input) at $10/M and output at $30/M:
    long-context prices plus the input cache-write premium. Cache observations
    remain intact; absence of usage is never substituted with a measured zero.
    """
    total, cached, output = (tokens.get(k) for k in ('input_including_cache', 'cached_input', 'output'))
    if any(type(v) is not int or v < 0 for v in (total, output)):
        return None
    if cached is not None and (type(cached) is not int or not 0 <= cached <= total):
        return None
    return (total * 10 + output * 30) / 1_000_000


def validate_control(rows, expected, before, after, returncode):
    """Success is assigned only after all post-run invariants have passed."""
    if before != after:
        raise RuntimeError('Task input mutation')
    if returncode or len(rows) != 1 or rows[0]['task'] != expected:
        raise RuntimeError('Incomplete control execution')
    row = rows[0]
    if not row['matches'] or row['failure_cause'] is not None:
        raise RuntimeError('Unexpected control outcome')


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


def control(kind, root):
    """One existing fixture per process; Actions checkpoints it before the next."""
    from harbor.models.task.task import Task
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    if any(os.environ.get(k) for k in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'ANTHROPIC_API_KEY')):
        raise RuntimeError('Controls must be credential-free')
    if importlib.metadata.version('harbor') != '0.25.0':
        raise RuntimeError('Harbor version mismatch')
    name = 'pester-002-' + kind
    expected = {name: 'passed' if kind == 'good' else 'failed'}
    data = {'control': kind, 'qualification_passed': False, 'calibration': [],
            'commit': os.environ.get('GITHUB_SHA'), 'workflow_run': os.environ.get('GITHUB_RUN_ID')}
    write(root / 'control.json', data)
    start = time.monotonic()
    try:
        native, manifest = stage(root / 'staging')
        task = root / 'tasks' / name
        shutil.copytree(native / 'pester-002', task)
        solution = task / 'solution'; solution.mkdir()
        style = 'classic' if kind == 'good' else 'weak'
        shutil.copyfile(ROOT / pilot.OVERLAY / 'support/qualification/pester-002' / (style + '.Tests.ps1'), solution / 'candidate')
        (solution / 'solve.sh').write_text('#!/bin/sh\nset -eu\ntest "$(id -u)" = 1000\ntest ! -e /tests\ntest ! -e /var/run/docker.sock\ncp /solution/candidate /workspace/output/Subject.Tests.ps1\n')
        # Build explicitly to expose Docker progress even if the runner shuts down.
        # Both controls use the same contexts, so the second uses local layers.
        for folder, image in [('environment', 'direct-harbor-agent:recovery'), ('tests', 'direct-harbor-verifier:recovery')]:
            subprocess.run(['docker', 'build', '--progress=plain', '-t', image, str(task / folder)], check=True, timeout=600)
            section = '[environment]' if folder == 'environment' else '[verifier.environment]'
            config = task / 'task.toml'
            config.write_text(config.read_text().replace(section, section + '\ndocker_image = "' + image + '"'))
        manifest['task_checksum'] = Task(task).checksum
        manifest['images'] = {image: subprocess.check_output(['docker', 'image', 'inspect', '--format', '{{.Id}}', image], text=True).strip()
                              for image in ('direct-harbor-agent:recovery', 'direct-harbor-verifier:recovery')}
        write(root / 'manifest.json', manifest)
        config = {'job_name': kind, 'jobs_dir': str(root / 'jobs'), 'n_attempts': 1,
                  'n_concurrent_trials': 1, 'retry': {'max_retries': 0},
                  'environment': {'type': 'docker', 'delete': True},
                  'agents': [{'name': 'oracle'}], 'tasks': [{'path': str(task)}]}
        write(root / 'job.json', config)
        run = subprocess.run(['harbor', 'run', '--config', str(root / 'job.json')], stderr=subprocess.STDOUT, timeout=480)
        data['returncode'] = run.returncode
        data['calibration'] = project(root / 'jobs', expected)
        validate_control(data['calibration'], name, manifest['task_checksum'], Task(task).checksum, run.returncode)
        data['qualification_passed'] = True
    except Exception as exc:
        data['qualification_passed'] = False
        data['integration_failure'] = {'type': type(exc).__name__, 'message': str(exc)[:1200]}
    finally:
        if not data['calibration']:
            try:
                data['calibration'] = project(root / 'jobs', expected)
            except Exception as exc:
                data['projection_failure'] = type(exc).__name__
                data['qualification_passed'] = False
        data['duration_seconds'] = round(time.monotonic() - start, 2)
        write(root / 'control.json', data)
        print(json.dumps(data), flush=True)
    return 0 if data['qualification_passed'] else 1


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('control', choices=('good', 'weak'))
    parser.add_argument('output')
    args = parser.parse_args()
    raise SystemExit(control(args.control, args.output))
