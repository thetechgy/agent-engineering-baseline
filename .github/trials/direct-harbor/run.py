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


def stage(root, variant="current", *, historical_runtime=False, admission_diagnostics=False):
    if type(admission_diagnostics) is not bool:
        raise ValueError('admission_diagnostics must be a boolean')
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
            if context == env:
                # The pinned standalone Codex archive has no bundled bwrap.
                text = text.replace('ripgrep=14.1.1-1+b4', 'ripgrep=14.1.1-1+b4 bubblewrap=0.12.0-1~deb13u1')
            # The immutable signed snapshot's compressed index is available even
            # when the by-hash/plain route returns 503. Apt still verifies hashes.
            text = text.replace('apt-get update --error-on=any', 'apt-get update --error-on=any -o Acquire::By-Hash=false -o Acquire::CompressionTypes::Order::=xz -o Acquire::https::No-Cache=true')
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
            image_tail = ('COPY input/ /workspace/input/\nCOPY skills/ /workspace/.agents/skills/\n'
                    'COPY AGENTS.md /workspace/AGENTS.md\nCOPY codex/ /workspace/.codex/\n'
                    'RUN mkdir -p /outside /home/agent/.codex /installed-agent/codex-home && chown agent:agent /outside /home/agent/.codex /installed-agent/codex-home && chmod 700 /installed-agent/codex-home\n'
                    'RUN curl -fsSL https://github.com/openai/codex/releases/download/rust-v0.155.1/codex-x86_64-unknown-linux-musl.tar.gz -o /tmp/codex.tgz && '
                    "echo 'a0ef8b2debc3bf747e07b1a039354de31300ac0dcc2276498ba281470b5d9115  /tmp/codex.tgz' | sha256sum -c - && "
                    'tar -xzf /tmp/codex.tgz -C /usr/local/bin && mv /usr/local/bin/codex-x86_64-unknown-linux-musl /usr/local/bin/codex && rm /tmp/codex.tgz && codex --version\n'
                    'RUN chmod -R a-w /workspace/input /workspace/.agents /workspace/AGENTS.md\n')
            if not historical_runtime:
                profile=json.loads(Path(__file__).with_name('runtime-profile.json').read_text())
                begin=image_tail.index('RUN curl -fsSL ')
                finish=image_tail.index('RUN chmod -R a-w ',begin)
                image_tail=image_tail[:begin]+('RUN curl -fsSL '+profile['archive_url']+' -o /tmp/codex.tgz && '
                    "echo '"+profile['archive_sha256']+"  /tmp/codex.tgz' | sha256sum -c - && "
                    'mkdir -p /opt/codex && tar -xzf /tmp/codex.tgz -C /opt/codex && '
                    'ln -s /opt/codex/bin/codex /usr/local/bin/codex && rm /tmp/codex.tgz && codex --version\n')+image_tail[finish:]
            f.write(image_tail)
        # Supported collection hook: metadata only, before normal Harbor collection.
        shutil.copyfile(Path(__file__).with_name('artifact_state.py'),env/'artifact_state.py')
        shutil.copyfile(Path(__file__).with_name('artifact_state.py'),task/'tests/artifact_state.py')
        with (env/'Dockerfile').open('a') as f:
            f.write('COPY artifact_state.py /opt/trial-artifact-state.py\nRUN chmod 555 /opt/trial-artifact-state.py\n')
        with (task/'tests/Dockerfile').open('a') as f:
            f.write('COPY artifact_state.py /tests/artifact_state.py\n')
        entry=task/'tests/test.sh'
        entry.write_text(entry.read_text().replace('exec python3 -I /tests/verifier/grader.py',
            'python3 -I /tests/artifact_state.py /workspace/output/Subject.Tests.ps1 /logs/verifier/artifact-transfer.json\nexec python3 -I /tests/verifier/grader.py'))
        config = task / 'task.toml'
        config.write_text(config.read_text().replace('skills_dir = "/workspace/skills"',
                                                    'skills_dir = "/runtime/skills"'))
        if admission_diagnostics:
            with config.open('a') as stream:
                stream.write('\n[verifier.env]\nPESTER_ADMISSION_DIAGNOSTICS = "1"\n')
        with config.open('a') as f:
            f.write('\n[[verifier.collect]]\ncommand = "python3 /opt/trial-artifact-state.py /workspace/output/Subject.Tests.ps1 /logs/artifacts/agent-artifact.json"\nuser = "agent"\ntimeout_sec = 15\n')
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
            'native_agent_exit_code': (result_path.parent / 'agent/exit-code.txt').read_text().strip()
                if (result_path.parent / 'agent/exit-code.txt').is_file() else None,
            'native_rewards': native.verifier_result.rewards if native.verifier_result else None,
            'tokens': {'input_including_cache': n_input, 'cached_input': n_cache, 'output': n_output},
            'cost_usd': cost,
            'timing': {key: getattr(native, key).model_dump(mode='json') if getattr(native, key) else None
                       for key in ('agent_execution', 'verifier')},
            'native_result': result_path.relative_to(jobs.parent).as_posix(),
        })
    return observations


def conservative_usage_cost(tokens, input_rate=20, output_rate=30):
    """Operational estimate, not provider billing or an enforced dollar cap.

    Charge ALL input (including cached input) at $20/M and output at $30/M:
    long-context prices plus the maximum 12-hour cache-write premium. Cache observations
    remain intact; absence of usage is never substituted with a measured zero.
    """
    total, cached, output = (tokens.get(k) for k in ('input_including_cache', 'cached_input', 'output'))
    if any(type(v) is not int or v < 0 for v in (total, output)):
        return None
    if cached is not None and (type(cached) is not int or not 0 <= cached <= total):
        return None
    return (total * input_rate + output * output_rate) / 1_000_000


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
    """The campaign's single report; packaging is never a qualification result."""
    write(output / 'results.json', data)
    def esc(value):
        return html.escape("Unknown" if value is None else str(value))
    def table(headers, rows):
        return ('<table><thead><tr>' + ''.join('<th scope="col">'+esc(v)+'</th>' for v in headers)
                + '</tr></thead><tbody>' + ''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in rows)
                + '</tbody></table>')
    text = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">\n<title>Direct Harbor recovery trial</title><style>body{font:16px system-ui;max-width:1100px;margin:3rem auto;padding:0 1rem;color:#172033}table{border-collapse:collapse;width:100%;margin:1rem 0}th,td{border:1px solid #cbd5e1;padding:.5rem;text-align:left;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}h1,h2{color:#174f78}a{color:#145f91}</style>\n<h1>Direct Harbor recovery trial</h1><p>Bounded experimental trial. Production evaluation and Pages remain unchanged.</p>\n<p><a href="results.json" download>Download machine-readable results</a> · <a href="manifest.json">Frozen input manifests</a> · <a href="workflow-evidence.txt">Workflow evidence excerpts</a></p>'
    text += '<h2>Decision</h2><p>' + esc(data['decision']) + '</p>'
    text += '<p>' + esc(data['summary']) + '</p>'
    if data.get('admission_validation'):
        validation=data['admission_validation']
        text += '<h2>Credential-free admission diagnostic validation</h2><p>Passed: '+esc(validation['passed'])+'. No model inference. These are deterministic verifier controls, not new skill-evaluation attempts. Historical attempt six remains unexplained.</p><p><a href="admission-validation.json">Docker control evidence and input identity</a></p>'
        rows=[]
        for control in validation['controls']:
            outcome=control.get('outcome',{});reason=outcome.get('admission_rule') or outcome.get('code')
            diagnostic=outcome.get('admission_diagnostic')
            if diagnostic:reason += ' ('+diagnostic['ast_kind']+' at '+str(diagnostic['line'])+':'+str(diagnostic['column'])+')'
            rows.append((control['control'],outcome.get('classification'),reason,outcome.get('reference_pass'),outcome.get('mutants_detected'),control['passed']))
        text += table(('Control','Classification','Diagnostic reason','Reference pass','Defects detected','Expected outcome matched'),rows)
    if data.get('live_allocation'):
        allocation=data['live_allocation'];rows=allocation['rows']
        text += '<h2>New live allocation: '+esc(allocation['profile'])+'</h2><p><a href="allocation-evidence.json">Sanitized launch, deployment, handoff and usage evidence</a></p>'
        labels={'graded_passed':'Graded success','graded_failed':'Graded failure','missing_deliverable':'Deliverable missing (task failure)',
                'missing_after_budget_exhaustion':'No deliverable before token-budget exhaustion','rejected_output':'Deliverable rejected','missing_evidence':'Evidence incomplete','not_scheduled':'Not scheduled',
                'collection_failure':'Collection failure','transfer_failure':'Transfer failure','unsupported_submission':'Unsupported submission'}
        def agent_seconds(row):
            from datetime import datetime
            timing=(row.get('timing') or {}).get('agent_execution') or {}
            if timing.get('started_at') and timing.get('finished_at'):
                return round((datetime.fromisoformat(timing['finished_at'])-datetime.fromisoformat(timing['started_at'])).total_seconds(),3)
            return None
        def admission_label(row):
            label = str(row.get('admission') or 'Unknown')
            diagnostic = row.get('admission_diagnostic') or {}
            if diagnostic:
                label += ' (' + str(diagnostic.get('ast_kind')) + ' at ' + str(diagnostic.get('line')) + ':' + str(diagnostic.get('column')) + ')'
            return label
        text += table(('Arm / attempt','Execution / session completed','Task outcome','Artifact transfer / admission','Reference / defects','Skill-file access attempts','Agent / total seconds'),
            [(r['variant']+' / '+str(r['attempt']),(r['execution_outcome']+' / '+str(r['session_completed'])) if r['scheduled'] else 'Not run',labels.get(r['outcome'],r['outcome']),
              ('Hashes matched' if r['handoff']=='hash_matched' else 'No source file' if r['handoff']=='no_source' else 'Unconfirmed')+' / '+admission_label(r),
              (('Pass' if r['reference_pass']==1 else 'Fail')+' / '+str(r['mutants_detected'])+'/'+str(r['mutants_executed'])) if r['valid_grade'] else 'Not measured',
              ', '.join(r['skill_file_access_attempts']) if r['skill_file_access_attempts'] else ('None observed' if r['skill_file_access_attempts']==[] else 'Unknown'),
              (str(agent_seconds(r))+' / '+str(r['duration_seconds'])) if r['scheduled'] else 'Not run') for r in rows])
        text += table(('Arm','Total input','Cached input','Cache-write input','Total output','Reasoning output','Conservative USD estimate','Native pricing estimate'),
            [(r['variant'],*( (r['usage'] or {}).get(k) for k in ('input_tokens','cached_input_tokens','cache_write_input_tokens','output_tokens','reasoning_output_tokens')),r['conservative_estimate_usd'],r['native_pricing_estimate_usd']) for r in rows])
        text += '<p>'+esc(allocation['usage_note'])+'</p>'
        if allocation.get('admission_preflight'):
            checks = allocation['admission_preflight']
            text += '<p>Credential-free admission checks: '+esc('passed' if checks.get('passed') else 'failed')+'. These check parsing and diagnostic classification; they do not establish task correctness or skill effectiveness.</p>'
        text += table(('Arm','Accounting coverage','Billing certainty'),[(r['variant'],(r.get('accounting_assessment') or {}).get('coverage','Unknown'),'Unknown') for r in rows])
        for note in allocation.get('reviewed_notes',[])+allocation['limits']:text += '<p>'+esc(note)+'</p>'
        text += '<p>Allocation closed; paid scheduling disabled. Consumed campaign slots: '+esc(allocation['closure']['reserved_slots_consumed'])+'.</p>'
    if data.get('live_allocation_history'):
        text += '<h2>Earlier closed allocations</h2><p>Historical settings and outcomes are preserved; they are not matched arms of the current comparison. Full metadata remains in allocation-evidence.json.</p>'
        text += table(('Allocation','Consumed campaign attempts','Historical outcomes','Observed usage estimate USD'),[(a['id'],a['closure']['reserved_slots_consumed'],[(r['variant'],r['execution_outcome'],r['outcome']) for r in a['rows']],a.get('observed_usage_conservative_estimate_usd')) for a in data['live_allocation_history']])
    if data.get('handoff_pass'):
        handoff=data['handoff_pass']
        text += '<h2>Prior credential-free artifact handoff and runtime checks</h2><p>'+esc(handoff['summary'])+'</p>'
        text += '<p><a href="handoff-evidence.json">Native handoff metadata and runtime compatibility evidence</a></p>'
        text += table(('Deterministic control','Expected','Observed handoff','Verifier','Control matched'),
            [(kind,{'good':'Reference pass and 2/2 defects','missing':'Missing submission','rejected':'Transferred then invalid UTF-8'}[kind],
              (row or {}).get('classification',{}).get('classification'),(row or {}).get('native_result',{}).get('outcome'),(row or {}).get('passed')) for kind,row in handoff['controls'].items()])
        text += '<p>Future profile: '+esc(handoff['profile'])+'. Model inference in this pass: none.</p>'
        for paragraph in handoff['notes']:text += '<p>'+esc(paragraph)+'</p>'
    if data.get('launch_repair'):
        repair=data['launch_repair']
        text += '<h2>Credential-free launch repair</h2><p>'+esc(repair['summary'])+'</p>'
        text += '<p><a href="launch-repair.json">Sanitized launch diagnostics and provider checks</a></p>'
        text += table(('Probe','CLI startup','Outcome','Requests to local fixture','Stream wait seconds'),
                      [(r['probe'],r['startup'],r['outcome'],r.get('requests'),r.get('stream_wait_seconds')) for r in repair['observations']])
        for paragraph in repair['notes']:
            text += '<p>'+esc(paragraph)+'</p>'
    text += '<h2>Native credential-free controls</h2>'
    text += table(('Case / submission', 'Expected', 'Verifier observation', 'Reference pass', 'Defects detected', 'Harbor failure cause', 'Valid measured grade'),
                  [(r['task'], r['expected'], r['outcome']['classification'] + ': ' + str(r['outcome'].get('code', '')),
                    r['outcome'].get('reference_pass'), str(r['outcome'].get('mutants_detected')) + '/' + str(r['outcome'].get('mutants_executed')),
                    r.get('failure_cause') or 'None', r.get('measured', False)) for r in data['calibration']])
    text += '<p>' + esc(data['calibration_note']) + '</p><ul>'
    for row in data['calibration']:
        for label, path in row.get('evidence', {}).items():
            text += '<li><a href="' + html.escape(path, quote=True) + '">' + esc(row['task'] + ': ' + label) + '</a></li>'
    text += '</ul>'
    text += '<h2>Historical live Codex pair</h2>'
    text += table(('Case', 'Variant', 'Task execution', 'Valid denominator', 'Reference', 'Defects detected', 'Activation evidence'),
                  [(r['case'],r['variant'],r.get('execution'),r['valid_denominator'],r['correctness'],r['mutation_detection'],r['activation']) for r in data['live_results']])
    text += '<p>' + esc(data['live_note']) + '</p>'
    if data.get('live_evidence'):
        text += '<p><a href="live-evidence.json">Reviewed live attempt, deployment and usage metadata</a></p>'
        text += table(('Variant', 'Input tokens (including cache)', 'Cached input tokens', 'Output tokens', 'Conservative USD estimate'),
                      [(r['variant'],r.get('input_tokens'),r.get('cached_input_tokens'),r.get('output_tokens'),r.get('estimate_usd')) for r in data.get('usage_rows',[])])
    text += '<h2>Campaign usage</h2><p>' + esc(data['spending_note']) + '</p>'
    text += '<h2>Sandbox and deployment boundary</h2>'
    for paragraph in data['boundary_assessment']:
        text += '<p>' + esc(paragraph) + '</p>'
    text += '<h2>Execution and supporting artifacts</h2><ul>'
    for entry in data['recovery_runs']:
        text += '<li><a href="' + html.escape(entry['url'], quote=True) + '">' + esc(entry['label']) + '</a> — ' + esc(entry['summary'])
        for artifact in entry.get('artifacts', []):
            text += ' · <a href="' + html.escape(artifact['url'], quote=True) + '">' + esc(artifact['name']) + '</a>'
        text += '</li>'
    text += '</ul><h2>History</h2><p>' + esc(data['history_note']) + '</p>'
    text += '<h2>Maintenance and remaining evidence</h2>'
    for paragraph in data['assessment']:
        text += '<p>' + esc(paragraph) + '</p>'
    text += '<h2>Primary references</h2><ul>'
    for label, url in data['sources'].items():
        text += '<li><a href="' + html.escape(url, quote=True) + '">' + esc(label.replace('_', ' ')) + '</a></li>'
    text += '</ul><details><summary>Complete machine-readable evidence</summary><pre>' + esc(json.dumps(data, indent=2)) + '</pre></details></html>'
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
        (solution / 'solve.sh').chmod(0o755)
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
