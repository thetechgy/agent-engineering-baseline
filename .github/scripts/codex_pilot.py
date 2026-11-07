#!/usr/bin/env python3
"""One opt-in Codex pair using existing native staging, collection and reporting."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys

from codex_pilot_contract import PROFILE as P, ROOT, runner_bytes, grader_bytes
import evaluator_profiles as profiles
import pester_evaluations as pester
import skill_evidence as evidence
import skill_reports as reports

ARMS = ('with_skill', 'without_skill')
CONTROLS = {'classic': 'passed', 'weak': 'failed', 'missing': 'invalid',
            'boolean': 'passed', 'template': 'unsupported', 'parameter': 'unsupported',
            'failure': 'failed'}


def sha(path):
    return hashlib.sha256(evidence.read_bytes(path)).hexdigest()


def resources():
    return {key: sorted(subprocess.check_output(cmd, text=True, timeout=15).split()) for key, cmd in (
        ('containers', ['docker', 'ps', '-aq']), ('networks', ['docker', 'network', 'ls', '-q']))}


def deploy(root):
    """Native APM deployment of the isolated local-skill profile, then byte audit."""
    project = root / 'apm-project'
    project.mkdir()
    source = ROOT / '.apm/skills' / P['skill']
    shutil.copytree(source, project / '.apm/skills' / P['skill'], ignore=shutil.ignore_patterns('evals'))
    (project / 'apm.yml').write_text('name: codex-pilot-workspace\nversion: 1.0.0\ntarget: codex\nincludes:\n  - .apm/skills/powershell-pester-6/\n')
    apm = Path(os.environ['APM_EXECUTABLE']).resolve(strict=True)
    if re.search(r'CLI version ([0-9.]+)', subprocess.check_output([apm, '--version'], text=True)).group(1) != (ROOT / '.apm-version').read_text().strip():
        raise ValueError('APM version mismatch')
    clean = {k:v for k,v in os.environ.items() if k not in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'NVIDIA_API_KEY')}
    subprocess.run([apm, 'install', '--only', 'apm', '--target', 'codex'], cwd=project, env=clean, check=True, timeout=60)
    deployed = project / '.agents/skills' / P['skill']
    expected = {p.relative_to(source).as_posix(): sha(p) for p in reports.regular_tree(source)
                if p.relative_to(source).parts[0] != 'evals'}
    if pester.manifest(deployed) != expected:
        raise ValueError('APM deployment differs from current skill')
    reports.write_json(root / 'workspace-profile.json', {'id': P['id'], 'mode': 'isolated',
        'deployment': 'APM install --only apm --target codex', 'apm': (ROOT / '.apm-version').read_text().strip(),
        'skills': [P['skill']], 'target_manifest': expected, 'personal_instructions': False,
        'mcp_servers': [], 'grader_reference_mutants_in_agent_workspace': False,
        'without_skill_difference': 'target skill directory and supporting files absent'})
    return deployed


def stage(root, *, controls=False):
    from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks
    deployed = deploy(root)
    bundle = pester.stage(ROOT, root / 'bundle' / P['skill'])
    native = bundle / 'evals/harbor'
    case = P['case']
    for task in native.iterdir():
        if task.is_dir() and task.name != case:
            shutil.rmtree(task)
    entry = next(row for row in pester.dataset(ROOT) if row['id'] == case)
    selected = [entry]
    if controls:
        selected = []
        for control in CONTROLS:
            target = native / (case + '-' + control)
            shutil.copytree(native / case, target)
            config = target / 'task.toml'
            config.write_text(config.read_text().replace('entry_id = "pester-001"', 'entry_id = ' + json.dumps(target.name)))
            reports.write_json(target / 'tests/entry.json', {'id': target.name, 'grading_mode': 'custom_only'})
            selected.append({**entry, 'id': target.name})
        shutil.rmtree(native / case)
    reports.write_json(bundle / 'evals/evals.json', {'skill_name': P['skill'], 'evals': selected})
    (native / 'dataset.toml').write_text('[dataset]\nname = "nvidia/codex-compatibility-pilot"\n\n' +
        ''.join('[[tasks]]\nname = ' + json.dumps('nvidia/' + row['id']) + '\n\n' for row in selected))
    tasks = {}; captured = []
    for arm in ARMS:
        present = arm == 'with_skill'
        tasks[arm] = stage_native_harbor_tasks(bundle, root / 'tasks' / arm, with_skill=present, grading_mode='custom_only')
        if {task.name for task in tasks[arm]} != {e['id'] for e in selected}:
            raise ValueError('Pilot selection drift')
        for task in tasks[arm]:
            (task / 'tests/Runner.ps1').write_bytes(runner_bytes())
            (task / 'tests/verifier/grader.py').write_bytes(grader_bytes())
            (task / 'tests/docker-compose.yaml').write_text('services:\n  main:\n    network_mode: none\n')
            config = task / 'task.toml'
            config.write_text(config.read_text().replace('timeout_sec = 300.0', f'timeout_sec = {P["agent_seconds"]}.0'))
            skill = task / 'environment/skills' / P['skill']
            if present:
                if pester.manifest(skill) != pester.manifest(deployed):
                    raise ValueError('Native staging differs from APM deployment')
            elif skill.exists():
                raise ValueError('Absent-arm skill contamination')
            if not controls:
                # Verified artifacts are embedded before entering the protected job.
                with (task / 'environment/Dockerfile').open('a') as dockerfile:
                    dockerfile.write('RUN mkdir /opt/codex && curl --fail --location --silent --show-error '
                        '--proto "=https" --proto-redir "=https" '
                        'https://github.com/openai/codex/releases/download/rust-v0.167.0/codex-package-x86_64-unknown-linux-musl.tar.gz '
                        '-o /opt/codex.tar.gz && '
                        f"echo '{P['cli_archive_sha256']}  /opt/codex.tar.gz' | sha256sum -c --strict && "
                        'tar -xzf /opt/codex.tar.gz -C /opt/codex && '
                        f"echo '{P['cli_executable_sha256']}  /opt/codex/bin/codex' | sha256sum -c --strict && "
                        'rm /opt/codex.tar.gz\n')
            else:
                control = task.name.removeprefix(case + '-')
                fixtures = ROOT / pester.OVERLAY / 'support/qualification' / case
                good = (fixtures / 'classic.Tests.ps1').read_bytes()
                payload = {'classic': good, 'weak': (fixtures / 'weak.Tests.ps1').read_bytes(),
                    'boolean': good + b"\nDescribe 'Boolean assertions' { It 'supports true and false' { $true | Should -BeTrue; $false | Should -BeFalse } }\n",
                    'template': b"Describe 'reject <$(1)>' { It 'checks' { 1 | Should -Be 1 } }\n",
                    'parameter': b"Describe 'reject' { It 'checks' { 1 | Should -Be 2 -ErrorAction SilentlyContinue } }\n",
                    'failure': b"Describe 'failure' { It 'fails' { 1 | Should -Be 2 } }\n", 'missing': b''}[control]
                solution = task / 'solution'; solution.mkdir()
                (solution / 'candidate').write_bytes(payload)
                (solution / 'solve.sh').write_text('#!/bin/sh\nset -eu\ntest ! -e /tests\n' +
                    ('test ! -e /workspace/output/Subject.Tests.ps1\n' if control == 'missing' else
                     'cp /solution/candidate /workspace/output/Subject.Tests.ps1\n' + producer_receipt_command() + '\n'))
        captured.extend(evidence.capture_custom_tasks(ROOT, P['skill'], tasks[arm], arm,
                        purpose='cli_pilot_control' if controls else 'cli_pilot'))
    return bundle, tasks, captured


def command(root, arm, *, controls=False):
    from skillevaluator.tier3.harbor.runner import build_harbor_run_command
    cmd = build_harbor_run_command(agent='oracle' if controls else 'codex', env_mode='docker',
        dataset_path=root / 'tasks' / arm, job_name=f"{P['skill']}-codex-{'with' if arm == 'with_skill' else 'without'}",
        jobs_dir=root / 'jobs', n_attempts=1, n_concurrent=2, timeout_multiplier=1.0,
        model=None if controls else P['model'], agent_import_path=None if controls else 'codex_pilot_agent:PilotCodex')
    if not controls:
        index = next(i for i, value in enumerate(cmd) if value.startswith('version='))
        cmd[index] = 'version=' + json.dumps(P['cli'])
    cmd += ['--max-retries', '0']
    return cmd


def producer_receipt_command():
    code = ("import hashlib,json,stat; from pathlib import Path; p=Path('/workspace/output/Subject.Tests.ps1'); "
            "s=p.lstat() if p.exists() else None; "
            "v={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':s.st_size} "
            "if s and stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size<=65536 else None; "
            "Path('/logs/agent/pilot-produced-submission.json').write_text(json.dumps(v))")
    import shlex
    return 'python3 -c ' + shlex.quote(code)


def retain(root, artifact):
    """Retain exact safe submissions before collection/redaction/cleanup boundaries."""
    from skillevaluator.utils.redaction import redact_sensitive_text
    records = []
    for path in sorted((root / 'jobs').rglob('Subject.Tests.ps1')):
        if '/artifacts/' not in path.as_posix():
            continue
        raw = evidence.read_bytes(path)
        relative = path.relative_to(root / 'jobs')
        decoded = raw.decode('utf-8', errors='replace')
        if redact_sensitive_text(decoded) != decoded:
            raise ValueError('Submission requires protected retention; public upload refused')
        target = artifact / 'submissions' / relative
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
        if sha(path) != sha(target): raise ValueError('Submission handoff mismatch')
        trial = next(parent.parent for parent in path.parents if parent.name == 'artifacts')
        receipts = [reports.read_json(trial / d / n) for d,n in (('agent','pilot-produced-submission.json'), ('verifier','pilot-verified-submission.json'))]
        if any(r != {'sha256': sha(target), 'bytes': len(raw)} for r in receipts):
            raise ValueError('Producer/artifact/verifier handoff mismatch')
        records.append({'member': target.relative_to(artifact).as_posix(), 'sha256': sha(target), 'bytes': len(raw)})
    reports.write_json(artifact / 'submissions.json', records)
    audits = []
    for path in sorted((root / 'jobs').rglob('pilot-runtime.json')):
        audits.append({**reports.read_json(path), 'trial_member': path.relative_to(root / 'jobs').as_posix()})
    reports.write_json(artifact / 'runtime-audits.json', audits)
    usage = []
    for path in sorted((root / 'jobs').rglob('result.json')):
        value = reports.read_json(path)
        if 'trial_name' not in value: continue
        agent = value.get('agent_result') or {}
        counts = {key: agent.get(key) for key in ('n_input_tokens', 'n_cache_tokens', 'n_output_tokens')}
        valid = all(type(v) is int and v >= 0 for v in counts.values())
        cost = None
        if valid:
            i,c,o = counts.values()
            if c > i: raise ValueError('Contradictory provider usage')
            # Cumulative counts cannot identify per-request long-context billing.
            # Conservatively apply its premium once cumulative input exceeds 272K.
            prefill, sample = (2, 1.5) if i > 272000 else (1, 1)
            cost = (((i-c)*2+c*.1)*prefill+o*10*sample)/1_000_000
        usage.append({'trial': value['trial_name'], **counts, 'estimated_usd': cost,
                      'billing': 'provider-reported tokens; estimate, not invoice'})
    reports.write_json(artifact / 'usage.json', usage)
    events = []
    for path in sorted((root / 'jobs').rglob('codex.txt')):
        for line in evidence.read_bytes(path, limit=16*1024*1024).splitlines():
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if value.get('type') in ('item.started', 'item.completed') and value.get('item', {}).get('type') == 'command_execution':
                from skillevaluator.utils.redaction import redact_sensitive_data
                events.append({**redact_sensitive_data(value), 'trial_member': path.relative_to(root / 'jobs').as_posix()})
    reports.write_json(artifact / 'tool-events.json', events)
    return usage


def collect(root, artifact, bundle, captured, *, controls=False):
    from skillevaluator.tier3.harbor.collector import collect_harbor_results
    ids = sorted({row['case_id'] for row in captured})
    raw = root / 'raw'; run = raw / 'results' / P['skill'] / ('pilot-controls' if controls else 'live-pilot')
    collected = collect_harbor_results(P['skill'], ['codex'], run, root / 'jobs',
        expected_cases=len(ids), expected_case_ids=ids, expected_trials=len(ids),
        agent_models={'codex': {'model': 'credential-free-oracle' if controls else P['model'], 'source': P['id']}})
    purpose = 'cli_pilot_control' if controls else 'cli_pilot'
    capture = evidence.custom_capture(ROOT, P['skill'], bundle, captured, purpose=purpose, attempts=1,
        agent='oracle' if controls else 'codex', execution_policy={'environment': 'docker',
        'concurrency': 2, 'timeout_multiplier': 1.0, 'stop_on_pass': False})
    reports.write_json(raw / evidence.CUSTOM_CAPTURE, capture)
    config = {'grading': {'mode': 'custom_only'}, 'judge': {'enabled': False},
        'provider': {'name': 'fixture' if controls else 'openai', 'model': 'credential-free-oracle' if controls else P['model']},
        'harbor': {'n_attempts': 1, 'stop_on_pass': False}}
    if controls: config['qualification'] = {'producer': 'oracle', 'inference': False}
    reports.write_json(run / 'run_config.json', config)
    stages = reports.read_json(artifact / 'command-stages.json')
    status = 'complete' if len(stages) == 2 and all(s.get('returncode') == 0 for s in stages) else 'incomplete'
    reports.write_json(run / 'result.json', {**collected, 'diagnostic_only': True,
        'skill_name': P['skill'], 'report_status': status, 'run_config': config})
    grading = [{'trial_member': p.relative_to(run).as_posix(), 'entry_id': reports.read_json(p).get('entry_id'),
                'outcome': reports.read_json(p).get('details', {}).get('outcome', {})} for p in sorted(run.rglob('reward.json'))]
    reports.write_json(artifact / 'grading-outcomes.json', grading)
    native = artifact / 'native'
    reports.benchmark_artifacts(ROOT, raw, P['skill'], native)
    import skill_analysis as analysis
    import skill_report as report
    public = artifact / 'public'
    reports.public_benchmark(ROOT, native, P['skill'], 'confirmation', public)
    captured_inputs = analysis.capture_inputs([public])
    value = analysis.validate_analysis(None, captured_inputs)
    reports.write_json(artifact / 'analysis/analysis.json', value)
    report.generate([public], artifact / 'analysis/analysis.json', artifact / 'consolidated')
    observations = [row for record in captured_inputs.records.values() if record['kind'] == 'behavioral' for row in record['observations']]
    reports.write_json(artifact / 'outcomes.json', observations)
    if controls:
        rewards = list(run.rglob('reward.json'))
        if len(rewards) != 2 * len(CONTROLS): raise ValueError('Incomplete control grading')
        for path in rewards:
            reward = reports.read_json(path)
            control = reward['entry_id'].removeprefix(P['case'] + '-')
            outcome = reward['details']['outcome']
            if outcome['classification'] != CONTROLS[control]: raise ValueError('Unexpected control grade: ' + control)
            expected_reason = {'template': 'test_name_template', 'parameter': 'command_parameter', 'missing': 'artifact'}.get(control)
            if expected_reason and outcome['code'] != expected_reason: raise ValueError('Specific admission reason lost')


def run(root, *, controls=False, probe=False):
    artifact = root / 'evidence'; artifact.mkdir()
    profiles.runtime(profiles.candidate_versions(), owning=True)
    if controls or probe:
        if any(os.environ.get(k) for k in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','NVIDIA_API_KEY')):
            raise ValueError('Credential-free preparation received credentials')
    before = resources(); stages = []; collected = False
    bundle, tasks, captured = stage(root, controls=controls)
    reports.write_json(artifact / 'staging.json', captured)
    shutil.copyfile(root / 'workspace-profile.json', artifact / 'workspace-profile.json')
    if probe: os.environ['AEB_PILOT_PROBE'] = '1'
    try:
        for arm in ARMS:
            stage_record = {'arm': arm, 'stage': 'native_control' if controls else 'refusal_probe' if probe else 'live_cli', 'status': 'running'}
            stages.append(stage_record); reports.write_json(artifact / 'command-stages.json', stages)
            environment = {k:v for k,v in os.environ.items() if not k.startswith(('CODEX_', 'ANTHROPIC_', 'NVIDIA_', 'SKILL_EVAL_'))}
            environment.update(PYTHONPATH=str(ROOT / '.github/scripts'), PYTHON_DOTENV_DISABLED='1', HARBOR_TELEMETRY='0')
            cmd = command(root, arm, controls=controls)
            from qualify_evaluator_candidate import run_native
            with (root / 'command.log').open('w') as log:
                code = run_native(cmd, env=environment, log=log, timeout=1800 if controls else 1200)
            from harbor.models.task.task import Task
            expected_tasks = {r['case_id']: r['task_checksum'] for r in captured if r['arm'] == arm}
            if any(Task(t).checksum != expected_tasks[t.name] for t in tasks[arm]):
                raise ValueError('Task checksum changed across execution')
            stage_record.update(status='complete' if code == 0 else 'failed', returncode=code)
            from skillevaluator.utils.redaction import redact_sensitive_text
            diagnostic = redact_sensitive_text((root / 'command.log').read_text(errors='replace')[-32768:])
            diagnostic = diagnostic.replace(str(root), '<pilot>').replace(str(ROOT), '<checkout>')
            (artifact / (arm + '-diagnostics.txt')).write_text(diagnostic)
            reports.write_json(artifact / 'command-stages.json', stages)
            usage = retain(root, artifact)
            if not probe and not controls:
                if code: raise RuntimeError('Infrastructure failure; remaining arm not launched')
                if any(row['estimated_usd'] is None for row in usage) or not usage:
                    raise RuntimeError('Usage unavailable; remaining allocation cannot be verified')
                if sum(row['estimated_usd'] for row in usage) >= P['stop_estimate_usd']:
                    raise RuntimeError('Spending stop threshold reached; remaining arm not launched')
        if not probe:
            collect(root, artifact, bundle, captured, controls=controls)
            collected = True
        else:
            probes = [{**reports.read_json(p), 'trial_member': p.relative_to(root / 'jobs').as_posix()} for p in sorted((root / 'jobs').rglob('probe.json'))]
            if len(probes) != 2 or any(p['model'] != P['model'] or p['reasoning']['effort'] != 'high' or p['requests'] != 2 for p in probes):
                raise ValueError('Actual CLI request contract mismatch')
            frozen_prompt = next(e['prompt'] for e in pester.dataset(ROOT) if e['id'] == P['case'])
            if any(frozen_prompt not in json.dumps(p['input']) for p in probes):
                raise ValueError('Post-upload actual task prompt mismatch')
            reports.write_json(artifact / 'refusal-probes.json', probes)
            events = reports.read_json(artifact / 'tool-events.json')
            completed = [e['item'] for e in events if e['type'] == 'item.completed']
            if len(completed) != 2 or any(e.get('exit_code') != 0 or 'pilot-tool-event' not in e.get('aggregated_output', '') for e in completed):
                raise ValueError('Real sandboxed CLI tool-event collection incomplete')
    finally:
        if not probe and stages and not collected:
            try:
                collect(root, artifact, bundle, captured, controls=controls)
            except Exception as error:
                reports.write_json(artifact / 'collection-failure.json', {'stage': 'recovery', 'error': type(error).__name__})
        images = subprocess.check_output(['docker', 'image', 'ls', '--digests', '--no-trunc', '--format', '{{json .}}'], text=True, timeout=15)
        (artifact / 'image-identities.jsonl').write_text(images)
        clean = resources() == before
        reports.write_json(artifact / 'cleanup.json', {'complete': clean, 'unlaunched_arms': [arm for arm in ARMS if arm not in {s['arm'] for s in stages}]})
        if not clean: raise RuntimeError('Pilot resource cleanup incomplete')
    reports.write_json(artifact / 'readiness.json', {'id': P['id'], 'revision': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'inference': not (controls or probe), 'controls': controls, 'probe': probe, 'complete': True})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('controls','probe','live'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--approval', default='')
    args=parser.parse_args()
    if args.action == 'live':
        revision = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        if args.approval != 'pilot-' + revision + '-usd10' or os.environ.get('GITHUB_RUN_ATTEMPT') != '1':
            parser.error('Exact-revision allocation and first workflow attempt required')
    args.output.mkdir(parents=True, exist_ok=False)
    from qualify_evaluator_candidate import native_compose_config
    native_compose_config(ROOT)
    run(args.output, controls=args.action=='controls', probe=args.action=='probe')


if __name__ == '__main__':
    main()
