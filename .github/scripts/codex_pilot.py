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

from codex_pilot_contract import PROFILE as P, ROOT, grader_bytes, runtime_installer_bytes
from codex_pilot_iteration import runner_bytes, PATH_LINK, CONTROLS as ITERATION_CONTROLS, control_payload
import evaluator_profiles as profiles
import pester_evaluations as pester
import skill_evidence as evidence
import skill_reports as reports

ARMS = ('with_skill', 'without_skill')
CONTROLS = {'classic': 'passed', 'weak': 'failed', 'missing': 'invalid',
            'boolean': 'passed', 'template': 'unsupported', 'parameter': 'unsupported',
            'failure': 'failed', **ITERATION_CONTROLS}


def sha(path):
    return hashlib.sha256(evidence.read_bytes(path)).hexdigest()


def resources():
    return {key: sorted(subprocess.check_output(cmd, text=True, timeout=15).split()) for key, cmd in (
        ('containers', ['docker', 'ps', '-aq']), ('networks', ['docker', 'network', 'ls', '-q']), ('volumes', ['docker', 'volume', 'ls', '-q']))}


def deploy(root, *, profile_id=None):
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
    reports.write_json(root / 'workspace-profile.json', {'id': profile_id or P['id'], 'mode': 'isolated',
        'deployment': 'APM install --only apm --target codex', 'apm': (ROOT / '.apm-version').read_text().strip(),
        'skills': [P['skill']], 'target_manifest': expected, 'personal_instructions': False,
        'mcp_servers': [], 'grader_reference_mutants_in_agent_workspace': False,
        'without_skill_difference': 'target skill directory and supporting files absent'})
    return deployed


def stage(root, *, controls=False, probe=False, replay=None, submissions=None, effectiveness=False):
    oracle = controls or replay is not None
    if replay is not None:
        from codex_pilot_replay import validate_retrospective, SUBMISSIONS
        validate_retrospective(replay)
        if controls or probe or set(submissions or {}) != set(ARMS) or any(
                hashlib.sha256(submissions[arm]).hexdigest() != SUBMISSIONS[arm] for arm in ARMS):
            raise ValueError('Replay mode or exact submission identity mismatch')
    from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks
    deployed = deploy(root, profile_id='pester-effectiveness-v3' if effectiveness else None)
    bundle = pester.stage(ROOT, root / 'bundle' / P['skill'])
    native = bundle / 'evals/harbor'
    if effectiveness:
        import codex_pilot_effectiveness as effective
        cases = effective.CASES
        fixtures = effective.fixtures()
    else:
        cases = (P['case'],)
    case = P['case']
    for task in native.iterdir():
        if task.is_dir() and task.name not in cases:
            shutil.rmtree(task)
    entries = {row['id']: row for row in pester.dataset(ROOT)}
    selected = [entries[name] for name in cases]
    if controls:
        selected = []
        cohort = fixtures if effectiveness else {case + '-' + name: {'case': case} for name in CONTROLS}
        for identity, fixture in cohort.items():
            source_case = fixture['case']
            target = native / identity
            shutil.copytree(native / source_case, target)
            config = target / 'task.toml'
            config.write_text(config.read_text().replace('entry_id = ' + json.dumps(source_case), 'entry_id = ' + json.dumps(target.name)))
            reports.write_json(target / 'tests/entry.json', {'id': target.name, 'grading_mode': 'custom_only'})
            selected.append({**entries[source_case], 'id': target.name})
        for name in cases:
            shutil.rmtree(native / name)
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
            for context in ('environment', 'tests'):
                (task / context / 'build/install-runtime.py').write_bytes(runtime_installer_bytes())
            source_case = fixtures[task.name]['case'] if effectiveness and controls else task.name if effectiveness else case
            (task / 'tests/Runner.ps1').write_bytes(effective.runner_bytes() if effectiveness else runner_bytes())
            (task / 'tests/verifier/grader.py').write_bytes(effective.grader_bytes() if effectiveness else grader_bytes())
            if effectiveness:
                (task / 'environment/input/EXECUTION-PROFILE.md').write_bytes(effective.execution_profile_bytes())
                shutil.rmtree(task / 'tests/case')
                for member, raw in effective.case_files(ROOT, source_case).items():
                    target = task / 'tests/case' / member
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(raw)
            (task / 'tests/docker-compose.yaml').write_text('services:\n  main:\n    network_mode: none\n')
            config = task / 'task.toml'
            config.write_text(config.read_text().replace('timeout_sec = 300.0', f'timeout_sec = {P["agent_seconds"]}.0')
                .replace('[agent]\n', '[agent]\nnetwork_mode = \"allowlist\"\nallowed_hosts = [\"api.openai.com\"]\n' if not oracle else '[agent]\n')
                .replace('network_mode = \"public\"', 'network_mode = \"allowlist\"\nallowed_hosts = [\"api.openai.com\"]' if not oracle else 'network_mode = \"public\"'))
            # A standard-path alias survives login-shell PATH reset. It changes
            # no executable bytes and is omitted only in the explicit baseline control.
            control = task.name.removeprefix(case + '-') if controls else None
            if control != 'path-before':
                with (task / 'environment/Dockerfile').open('a') as dockerfile:
                    dockerfile.write(PATH_LINK)
            if control == 'missing-runtime' or effectiveness and task.name.endswith('-missing-runtime'):
                with (task / 'tests/Dockerfile').open('a') as dockerfile:
                    dockerfile.write('RUN rm -- /opt/microsoft/powershell/7/pwsh\n')
            skill = task / 'environment/skills' / P['skill']
            if present:
                if pester.manifest(skill) != pester.manifest(deployed):
                    raise ValueError('Native staging differs from APM deployment')
            elif skill.exists():
                raise ValueError('Absent-arm skill contamination')
            if not oracle:
                from codex_pilot_runtime import prepare_cli
                prepare_cli(task)
            else:
                control = task.name.removeprefix(case + '-') if controls else 'retained-submission'
                fixture_dir = ROOT / pester.OVERLAY / 'support/qualification' / case
                good = (fixture_dir / 'classic.Tests.ps1').read_bytes()
                payload = {'classic': good, 'weak': (fixture_dir / 'weak.Tests.ps1').read_bytes(),
                    'boolean': good + b"\nDescribe 'Boolean assertions' { It 'supports true and false' { $true | Should -BeTrue; $false | Should -BeFalse } }\n",
                    'template': b"Describe 'reject <$(1)>' { It 'checks' { 1 | Should -Be 1 } }\n",
                    'parameter': b"Describe 'reject' { It 'checks' { 1 | Should -Be 2 -ErrorAction SilentlyContinue } }\n",
                    'failure': b"Describe 'failure' { It 'fails' { 1 | Should -Be 2 } }\n", 'missing': b''}
                payload = fixtures[task.name]['payload'] if effectiveness else submissions[arm] if replay is not None else payload[control] if control in payload else control_payload(control, good)
                solution = task / 'solution'; solution.mkdir()
                (solution / 'candidate').write_bytes(payload)
                path_check = path_probe_command(control) if control in ('path-before', 'path-after') else ''
                (solution / 'solve.sh').write_text('#!/bin/sh\nset -eu\ntest ! -e /tests\n' + path_check +
                    ('test ! -e /workspace/output/Subject.Tests.ps1\n' if control == 'missing' or effectiveness and task.name.endswith('-missing') else
                     'cp /solution/candidate /workspace/output/Subject.Tests.ps1\n' + producer_receipt_command() + '\n'))
        captured.extend(evidence.capture_custom_tasks(ROOT, P['skill'], tasks[arm], arm,
                        purpose=('skill_effectiveness_control' if controls else 'skill_effectiveness') if effectiveness else 'cli_pilot_replay' if replay is not None else 'cli_pilot_control' if controls else 'cli_pilot_probe' if probe else 'cli_pilot'))
    from codex_pilot_descriptors import retain_descriptors
    retain_descriptors(root / 'evidence', tasks, captured)
    return bundle, tasks, captured


def command(root, arm, *, controls=False, replay=False):
    oracle = controls or replay
    from skillevaluator.tier3.harbor.runner import build_harbor_run_command
    cmd = build_harbor_run_command(agent='oracle' if oracle else 'codex', env_mode='docker',
        dataset_path=root / 'tasks' / arm, job_name=f"{P['skill']}-codex-{'with' if arm == 'with_skill' else 'without'}",
        jobs_dir=root / 'jobs', n_attempts=1, n_concurrent=2, timeout_multiplier=1.0,
        model=None if oracle else P['model'], agent_import_path=None if oracle else 'codex_pilot_agent:PilotCodex')
    if not oracle:
        index = next(i for i, value in enumerate(cmd) if value.startswith('version='))
        cmd[index] = 'version=' + json.dumps(P['cli'])
        cmd[cmd.index('--env') + 1] = 'codex_pilot_environment:PilotEnvironment'
    cmd += ['--max-retries', '0']
    return cmd



def path_probe_command(control):
    # Constant commands in the actual agent login shell; no submitted code runs.
    code = ("import json,os,subprocess; from pathlib import Path; "
        "lookup=subprocess.run(['/bin/sh','-lc','command -v pwsh'],capture_output=True,text=True); "
        "absolute=subprocess.run(['/opt/microsoft/powershell/7/pwsh','-NoLogo','-NoProfile','-NonInteractive','-Command','$PSVersionTable.PSVersion.ToString()'],capture_output=True,text=True); "
        "v={'control':" + repr(control) + ", 'uid':os.geteuid(), 'login_shell_found':lookup.returncode==0, 'lookup_returncode':lookup.returncode, "
        "'resolved_path':lookup.stdout.strip(), 'absolute_returncode':absolute.returncode, 'powershell':absolute.stdout.strip()}; "
        "Path('/logs/agent/path-observation.json').write_text(json.dumps(v)); "
        "assert absolute.returncode==0 and absolute.stdout.strip()=='7.6.9'; "
        "assert (lookup.returncode==0)==" + repr(control == 'path-after') + "; "
        "assert lookup.returncode!=0 or lookup.stdout.strip()=='/usr/local/bin/pwsh'")
    import shlex
    return 'python3 -c ' + shlex.quote(code) + '\n'


def producer_receipt_command(output="/workspace/output/Subject.Tests.ps1", *, retain=False):
    code = ("import hashlib,json,stat; from pathlib import Path; p=Path(" + repr(output) + "); "
            "s=p.lstat() if p.exists() else None; "
            "v={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':s.st_size} "
            "if s and stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size<=65536 else None; "
            "Path('/logs/agent/pilot-produced-submission.json').write_text(json.dumps(v))")
    if retain:
        code += ("; target=Path('/logs/artifacts/submitted'); target.mkdir(parents=True,exist_ok=True); "
                 "(target/p.name).write_bytes(p.read_bytes()) if v else None")
    import shlex
    return 'python3 -c ' + shlex.quote(code)


def retain_probe_records(root, artifact):
    """Preserve available credential-free requests before qualification can fail."""
    from skillevaluator.utils.redaction import redact_sensitive_data
    records = []
    for arm in ARMS:
        job = root / 'jobs' / f"{P['skill']}-codex-{'with' if arm == 'with_skill' else 'without'}"
        for path in sorted(job.rglob('probe.json')):
            try:
                value = reports.read_json(path)
                if type(value) is not dict:
                    raise ValueError('Invalid probe record')
            except (ValueError, OSError):
                value = {'record_error': 'unreadable_probe_record'}
            records.append({**redact_sensitive_data(value), 'arm': arm,
                            'trial_member': path.relative_to(root / 'jobs').as_posix()})
    reports.write_json(artifact / 'cli-probes.json', records)
    return records


def validate_probe_requests(root, artifact, scenario):
    probes = retain_probe_records(root, artifact)
    counts = {arm: sum(p['arm'] == arm for p in probes) for arm in ARMS}
    missing = [arm for arm, count in counts.items() if count == 0]
    invalid = [arm for arm, count in counts.items() if count != 1]
    incomplete = bool(invalid or any('record_error' in p for p in probes))
    mismatches = []
    if not incomplete:
        for probe in probes:
            fields = []
            if probe.get('model') != P['model']:
                fields.append('model')
            if type(probe.get('reasoning')) is not dict or probe['reasoning'].get('effort') != 'high':
                fields.append('reasoning_effort')
            if type(probe.get('requests')) is not int or probe['requests'] != (1 if scenario == 'interruption' else 2):
                fields.append('request_count')
            if fields:
                mismatches.append({'arm': probe['arm'], 'fields': fields})
    status = {'complete': not incomplete and not mismatches, 'expected_arms': list(ARMS),
              'observed_counts': counts, 'missing_arms': missing,
              'reason': 'probe_missing_or_unreadable' if incomplete else 'observed_request_mismatch' if mismatches else 'matched',
              'request_mismatches': mismatches}
    reports.write_json(artifact / 'probe-validation.json', status)
    if incomplete:
        raise ValueError('CLI probe evidence incomplete; native acquisition/execution failures retained')
    if mismatches:
        raise ValueError('Observed CLI request contract mismatch; probe records retained')
    return probes


def retain(root, artifact, *, replay=False, controls=False, probe=False):
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
    reports.write_json(artifact / 'docker-observations.json', [reports.read_json(p) for p in sorted((root / 'jobs').rglob('docker-observation.json'))])
    reports.write_json(artifact / 'final-policy-audits.json', [reports.read_json(p) for p in sorted((root / 'jobs').rglob('pilot-final-policy.json'))])
    usage = []
    for path in sorted((root / 'jobs').rglob('result.json')):
        value = reports.read_json(path)
        if 'trial_name' not in value: continue
        from codex_pilot_runtime import usage_record
        usage.append(usage_record(value, probe=probe))
    if replay or controls:
        for row in usage:
            row['billing'] = ('credential-free oracle controls; no model inference or billing' if controls else
                              'credential-free retained-submission replay; no model inference')
    reports.write_json(artifact / 'usage.json', usage)
    reports.write_json(artifact / 'path-observations.json', [reports.read_json(p) for p in sorted((root / 'jobs').rglob('path-observation.json'))])
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


def collect(root, artifact, bundle, captured, *, controls=False, probe=False, replay=None, original_public=None, effectiveness=False, cohort=False):
    from skillevaluator.tier3.harbor.collector import collect_harbor_results
    ids = sorted({row['case_id'] for row in captured})
    raw = root / 'raw'; run = raw / 'results' / P['skill'] / ('retrospective-replay' if replay is not None else 'pilot-controls' if controls else 'cli-probe' if probe else 'live-pilot')
    collected = collect_harbor_results(P['skill'], ['codex'], run, root / 'jobs',
        expected_cases=len(ids), expected_case_ids=ids, expected_trials=None if cohort else len(ids),
        n_attempts=3 if cohort else 1, grading_mode="custom_only",
        agent_models={'codex': {'model': 'credential-free-oracle' if controls or replay is not None else P['model'], 'source': P['id']}})
    purpose = ('skill_effectiveness_control' if controls else 'skill_effectiveness') if effectiveness else 'cli_pilot_replay' if replay is not None else 'cli_pilot_control' if controls else 'cli_pilot_probe' if probe else 'cli_pilot'
    if cohort and probe: purpose = 'skill_effectiveness_probe'
    capture = evidence.custom_capture(ROOT, P['skill'], bundle, captured, purpose=purpose, attempts=3 if cohort else 1,
        agent='oracle' if controls or replay is not None else 'codex', retrospective=replay, execution_policy={'environment': 'docker',
        'concurrency': 1 if cohort else 2, 'timeout_multiplier': 1.0, 'stop_on_pass': False})
    reports.write_json(raw / evidence.CUSTOM_CAPTURE, capture)
    config = {'grading': {'mode': 'custom_only'}, 'judge': {'enabled': False},
        'provider': {'name': 'fixture' if controls or replay is not None else 'openai', 'model': 'credential-free-oracle' if controls or replay is not None else P['model']},
        'harbor': {'n_attempts': 3 if cohort else 1, 'stop_on_pass': False}}
    if controls or probe or replay is not None: config['qualification'] = {'producer': 'retained_submission_replay' if replay is not None else 'cli_probe' if probe else 'oracle', 'inference': False}
    reports.write_json(run / 'run_config.json', config)
    stages = reports.read_json(artifact / 'command-stages.json')
    status = 'complete' if len(stages) == (12 if cohort else 2) and all(s.get('returncode') == 0 for s in stages) else 'incomplete'
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
    report_inputs = [public, original_public] if replay is not None else [public]
    from evaluation_campaign_core import render
    captured_inputs = render(report_inputs, artifact)
    observations = [row for record in captured_inputs.records.values() if record['kind'] == 'behavioral' and (replay is None or record['custom']['purpose'] == 'cli_pilot_replay') for row in record['observations']]
    reports.write_json(artifact / 'outcomes.json', observations)
    if controls and effectiveness:
        from codex_pilot_effectiveness import fixtures
        expected = fixtures()
        rewards = list(run.rglob('reward.json'))
        if len(rewards) != 2 * len(expected): raise ValueError('Incomplete prospective control grading')
        for path in rewards:
            reward = reports.read_json(path)
            fixture = expected[reward['entry_id']]
            outcome = reward['details']['outcome']
            if outcome['classification'] != fixture['outcome']:
                raise ValueError('Unexpected prospective grade: ' + reward['entry_id'])
            if fixture['signature'] is not None and outcome.get('variant_detections') != fixture['signature']:
                raise ValueError('Wrong defect discrimination: ' + reward['entry_id'])
    elif controls:
        rewards = list(run.rglob('reward.json'))
        if len(rewards) != 2 * len(CONTROLS): raise ValueError('Incomplete control grading')
        for path in rewards:
            reward = reports.read_json(path)
            control = reward['entry_id'].removeprefix(P['case'] + '-')
            outcome = reward['details']['outcome']
            if outcome['classification'] != CONTROLS[control]: raise ValueError('Unexpected control grade: ' + control)
            expected_reason = {'template': 'test_name_template', 'parameter': 'command_parameter', 'missing': 'artifact'}.get(control)
            if expected_reason and outcome['code'] != expected_reason: raise ValueError('Specific admission reason lost')


def check_preparation(reference, artifact):
    """Consume authenticated same-revision preparation data before any live launch."""
    from codex_pilot_descriptors import compare_descriptors, verified_configurations
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    qualification = reference / 'pilot-report/evidence/qualification.json'
    value = reports.read_json(qualification)
    reports.require(value.get('complete') is True and value.get('inference') is False
                    and value.get('execution_policy') == P['execution_policy'], 'Incomplete preparation qualification')
    probe = reference / 'pilot-probe/evidence'
    phases = [(probe, False), (reference / 'pilot-controls/evidence', True)]
    phases += [(probe / 'cleanup-cases' / scenario, False) for scenario in ('command-failure', 'interruption')]
    for directory, controls in phases:
        ready = reports.read_json(directory / 'readiness.json')
        clean = reports.read_json(directory / 'cleanup.json')
        reports.require(ready.get('id') == P['id'] and ready.get('revision') == revision
                        and ready.get('complete') is True and ready.get('inference') is False
                        and ready.get('controls') is controls and ready.get('probe') is (not controls)
                        and clean.get('complete') is True and clean.get('unlaunched_arms') == [],
                        'Preparation source, readiness or cleanup mismatch')
        configurations = verified_configurations(directory)
        cases = {P['case'] + '-' + name for name in CONTROLS} if controls else {P['case']}
        reports.require(set(configurations) == {(arm, case) for arm in ARMS for case in cases},
                        'Preparation descriptor cohort mismatch')
        if not controls:
            compare_descriptors(probe, directory)
    retrospective = reference / 'pilot-retrospective/evidence'
    ready = reports.read_json(retrospective / 'readiness.json')
    clean = reports.read_json(retrospective / 'cleanup.json')
    checked = reports.read_json(retrospective / 'replay-check.json')
    from codex_pilot_replay import validate_retrospective, verify_retained_originals, REPLAY_PRODUCER, SUBMISSIONS
    verify_retained_originals(retrospective)
    validate_retrospective(checked.get('retrospective'))
    reports.require(ready.get('revision') == revision and ready.get('inference') is False
                    and ready.get('complete') is True and clean == {'complete': True, 'unlaunched_arms': []}
                    and checked.get('complete') is True and checked.get('inference') is False
                    and checked.get('originals_preserved') is True and checked.get('producer') == REPLAY_PRODUCER, 'Incomplete retrospective qualification')
    reports.require(set(verified_configurations(retrospective)) == {(arm, P['case']) for arm in ARMS},
                    'Retrospective descriptor cohort mismatch')
    retained = reports.read_json(retrospective / 'submissions.json')
    for row in retained:
        evidence.relative(row['member'])
        reports.require(row['member'].startswith('submissions/'), 'Retrospective submission outside retained evidence')
    actual = {('with_skill' if '/powershell-pester-6-codex-with/' in '/' + row['member'] else 'without_skill'): row for row in retained}
    reports.require(set(actual) == set(ARMS) and len(retained) == 2, 'Retrospective submission coverage mismatch')
    for arm, row in actual.items():
        reports.require(row['sha256'] == SUBMISSIONS[arm] and sha(retrospective / row['member']) == row['sha256'],
                        'Retrospective output bytes changed')
    comparison = compare_descriptors(probe, artifact)
    def members(directory):
        return {(row['arm'], row['case_id']): {
            'source_case_id': row['source_case_id'],
            'members': {name: digest for name, digest in row['members'].items() if name != 'task.toml'}}
            for row in reports.read_json(directory / 'staging.json')}
    reports.require(members(probe) == members(artifact), 'Non-descriptor preparation inputs changed')
    result = {**comparison, 'source_revision': revision, 'execution_policy': P['execution_policy'],
              'other_task_members_equal': True, 'credential_free_reference': True,
              'reference_descriptor_index_sha256': sha(probe / 'task-descriptors.json'),
              'reference_qualification_sha256': sha(qualification)}
    reports.write_json(artifact / 'preparation-check.json', result)
    return result


def run(root, *, controls=False, probe=False, preparation=None, replay=None, submissions=None, original_public=None, effectiveness=False):
    if not (controls or probe or replay is not None) and preparation is None:
        raise ValueError('Authenticated preparation evidence required before live execution')
    artifact = root / 'evidence'; artifact.mkdir(exist_ok=replay is not None)
    profiles.runtime(profiles.candidate_versions(), owning=True)
    if controls or probe or replay is not None:
        if any(os.environ.get(k) for k in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','NVIDIA_API_KEY')):
            raise ValueError('Credential-free preparation received credentials')
    before = resources(); stages = []; collected = False
    bundle, tasks, captured = stage(root, controls=controls, probe=probe, replay=replay, submissions=submissions, effectiveness=effectiveness)
    reports.write_json(artifact / 'staging.json', captured)
    shutil.copyfile(root / 'workspace-profile.json', artifact / 'workspace-profile.json')
    if probe: os.environ['AEB_PILOT_PROBE'] = '1'
    try:
        if not (controls or probe or replay is not None):
            check_preparation(preparation, artifact)
        for arm in ARMS:
            stage_record = {'arm': arm, 'stage': 'retained_submission_replay' if replay is not None else 'native_control' if controls else 'external_cli_probe' if probe else 'live_cli', 'status': 'running'}
            stages.append(stage_record); reports.write_json(artifact / 'command-stages.json', stages)
            environment = {k:v for k,v in os.environ.items() if not k.startswith(('CODEX_', 'ANTHROPIC_', 'NVIDIA_', 'SKILL_EVAL_'))}
            environment.update(PYTHONPATH=str(ROOT / '.github/scripts'), PYTHON_DOTENV_DISABLED='1', HARBOR_TELEMETRY='0')
            cmd = command(root, arm, controls=controls, replay=replay is not None)
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
            usage = retain(root, artifact, replay=replay is not None, controls=controls)
            if not probe and not controls and replay is None:
                audits = reports.read_json(artifact / 'runtime-audits.json')
                if code or len(audits) != ARMS.index(arm) + 1 or any(a.get('returncode') != 0 or a.get('cleanup') != 'complete' for a in audits):
                    raise RuntimeError('Infrastructure failure; remaining arm not launched')
                if resources() != before:
                    raise RuntimeError('Arm resource cleanup incomplete; remaining arm not launched')
                if any(row['estimated_usd'] is None for row in usage) or not usage:
                    raise RuntimeError('Usage unavailable; remaining allocation cannot be verified')
                if sum(row['estimated_usd'] for row in usage) >= P['stop_estimate_usd']:
                    raise RuntimeError('Spending stop threshold reached; remaining arm not launched')
        if replay is not None:
            from codex_pilot_replay import SUBMISSIONS
            retained = reports.read_json(artifact / 'submissions.json')
            expected = {arm: SUBMISSIONS[arm] for arm in ARMS}
            actual = {('with_skill' if '/powershell-pester-6-codex-with/' in '/' + r['member'] else 'without_skill'): r['sha256'] for r in retained}
            if len(retained) != 2 or actual != expected:
                raise ValueError('Replay output handoff differs from immutable originals')
        scenario = os.environ.get('AEB_PILOT_SCENARIO', 'success')
        if not probe or scenario == 'success':
            collect(root, artifact, bundle, captured, controls=controls, probe=probe, replay=replay, original_public=original_public, effectiveness=effectiveness)
            collected = True
        if probe:
            probes = validate_probe_requests(root, artifact, scenario)
            frozen_prompt = next(e['prompt'] for e in pester.dataset(ROOT) if e['id'] == P['case'])
            if any(frozen_prompt not in json.dumps(p['input']) for p in probes):
                raise ValueError('Post-upload actual task prompt mismatch')
            events = reports.read_json(artifact / 'tool-events.json')
            completed = [e['item'] for e in events if e['type'] == 'item.completed']
            audits = reports.read_json(artifact / 'runtime-audits.json')
            final_policies = reports.read_json(artifact / 'final-policy-audits.json')
            initial = {a['boundary_before']['agent_id']: a['boundary_before']['policy_sha256'] for a in audits}
            if len(final_policies) != 2 or any(initial.get(p['agent_id']) != p['policy_sha256'] for p in final_policies):
                raise ValueError('Post-agent policy was not retained through disposal')
            if len(audits) != 2 or any(a['cleanup'] != 'complete' for a in audits):
                raise ValueError('CLI cleanup audit incomplete')
            if scenario == 'success':
                if len(completed) != 2 or any(e.get('exit_code') != 0 or 'PILOT_BOUNDARY ' not in e.get('aggregated_output', '') for e in completed):
                    raise ValueError('Real externally contained CLI boundary probes incomplete')
                if any(a.get('returncode') != 0 or a.get('boundary_before', {}).get('policy_sha256') != a.get('boundary_after', {}).get('policy_sha256') for a in audits):
                    raise ValueError('CLI or policy changed')
                if len(reports.read_json(artifact / 'submissions.json')) != 2:
                    raise ValueError('CLI submission handoff incomplete')
                if any(len(p.get('late_cli_child', {}).get('network', [])) != 3 for p in final_policies):
                    raise ValueError('Post-agent real CLI child probe missing')
                boundary_probes = []
                for event in completed:
                    lines = event['aggregated_output'].splitlines()
                    line = next((v for v in lines if v.startswith('PILOT_BOUNDARY ')), None)
                    value = json.loads(line.removeprefix('PILOT_BOUNDARY '))
                    expected = pester.manifest(tasks['with_skill'][0] / 'environment/input')
                    if value.get('immutable_inputs') != expected:
                        raise ValueError('CLI did not read the frozen task inputs')
                    # Exact deployed supporting bytes in both registration locations;
                    # the other arm must contain no target skill files.
                    manifests = list(value.get('skill_files', {}).values())
                    expected_skill = reports.read_json(artifact / 'workspace-profile.json')['target_manifest']
                    if len(manifests) != 2 or not (all(m == expected_skill for m in manifests) or all(m == {} for m in manifests)):
                        raise ValueError('Actual CLI skill/supporting file exposure mismatch')
                    boundary_probes.append(value)
                if sorted(bool(p['skill_files']['/workspace/skills/powershell-pester-6']) for p in boundary_probes) != [False, True]:
                    raise ValueError('Actual CLI arm skill difference missing')
                reports.write_json(artifact / 'boundary-probes.json', boundary_probes)
                if sorted(a['skill_deployed'] for a in audits) != [False, True] or len({a['config_sha256'] for a in audits}) != 1 or len({a['prompt_sha256'] for a in audits}) != 1:
                    raise ValueError('Matched runtime/deployment contract incomplete')

            elif scenario == 'command-failure':
                if len(completed) != 2 or any(e.get('exit_code') != 23 for e in completed) or any(a.get('returncode') != 1 for a in audits):
                    raise ValueError('Command-failure control missing')
            elif any(a.get('returncode') != 124 for a in audits):
                raise ValueError('Interruption control missing')
    finally:
        if probe:
            retain_probe_records(root, artifact)
        if not probe and stages and not collected:
            try:
                collect(root, artifact, bundle, captured, controls=controls, replay=replay, original_public=original_public, effectiveness=effectiveness)
            except Exception as error:
                reports.write_json(artifact / 'collection-failure.json', {'stage': 'recovery', 'error': type(error).__name__})
        images = subprocess.check_output(['docker', 'image', 'ls', '--digests', '--no-trunc', '--format', '{{json .}}'], text=True, timeout=15)
        (artifact / 'image-identities.jsonl').write_text(images)
        clean = resources() == before
        reports.write_json(artifact / 'cleanup.json', {'complete': clean, 'unlaunched_arms': [arm for arm in ARMS if arm not in {s['arm'] for s in stages}]})
        if not clean: raise RuntimeError('Pilot resource cleanup incomplete')
    reports.write_json(artifact / 'readiness.json', {'id': P['id'], 'revision': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'inference': not (controls or probe or replay is not None), 'controls': controls, 'probe': probe, 'complete': True})


def consolidated(root):
    """One existing-renderer report for CLI qualification and native controls."""
    import skill_analysis as analysis
    import skill_report as report
    inputs = [root.parent / name / 'evidence/public' for name in ('pilot-probe', 'pilot-controls')]
    inputs += [root.parent / 'pilot-retrospective/evidence' / member for member in ('public', 'original-public')]
    inputs = [path for path in inputs if path.is_dir()]
    if not inputs:
        raise ValueError('No qualified public reporting inputs')
    value = analysis.validate_analysis(None, analysis.capture_inputs(inputs))
    reports.write_json(root / 'evidence/analysis/analysis.json', value)
    report.generate(inputs, root / 'evidence/analysis/analysis.json', root / 'evidence/consolidated')
    required = [root.parent / 'pilot-probe/evidence/readiness.json',
                root.parent / 'pilot-controls/evidence/readiness.json']
    required += [root.parent / 'pilot-probe' / name / 'evidence/readiness.json'
                 for name in ('command-failure', 'interruption')]
    required.append(root.parent / 'pilot-retrospective/evidence/replay-check.json')
    reports.write_json(root / 'evidence/qualification.json', {
        'execution_policy': P['execution_policy'], 'inference': False,
        'complete': all(path.is_file() and reports.read_json(path).get('complete') is True for path in required),
        'limitations': ['sentinel and non-forwarding stub, not provider authentication',
                        'agent credential and own-log exposure', 'DNS, ICMP and permitted-provider channels',
                        'deterministic fixture grade, not skill-effectiveness evidence']})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('controls','probe','live','report','check-preparation','effectiveness','cohort','check-cohort','qualify-cohort'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--approval', default='')
    parser.add_argument('--preparation', type=Path, help='Authenticated preparation artifact root')
    args=parser.parse_args()
    if args.action in ('cohort', 'check-cohort', 'qualify-cohort'):
        from codex_pilot_cohort import entry
        entry(args)
        return
    if args.action == 'live':
        revision = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        if args.approval != 'pilot-' + revision + '-usd10' or os.environ.get('GITHUB_RUN_ATTEMPT') != '1':
            parser.error('Exact-revision allocation and first workflow attempt required')
    if args.action in ('live', 'check-preparation') and args.preparation is None:
        parser.error('Authenticated preparation evidence required')
    if args.action == 'check-preparation' and any(os.environ.get(k) for k in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'NVIDIA_API_KEY')):
        parser.error('Credential-free preparation check received credentials')
    args.output.mkdir(parents=True, exist_ok=False)
    if args.action == 'report':
        consolidated(args.output)
        return
    if args.action == 'check-preparation':
        profiles.runtime(profiles.candidate_versions(), owning=True)
        _, _, captured = stage(args.output)
        artifact = args.output / 'evidence'
        reports.write_json(artifact / 'staging.json', captured)
        shutil.copyfile(args.output / 'workspace-profile.json', artifact / 'workspace-profile.json')
        check_preparation(args.preparation, artifact)
        return
    from qualify_evaluator_candidate import native_compose_config
    native_compose_config(ROOT)
    if args.action == 'effectiveness':
        from codex_pilot_effectiveness import prepare
        prepare(args.output)
        return
    run(args.output, controls=args.action=='controls', probe=args.action=='probe', preparation=args.preparation)
    if args.action == 'probe':
        for scenario in ('command-failure', 'interruption'):
            os.environ['AEB_PILOT_SCENARIO'] = scenario
            target = args.output / scenario; target.mkdir()
            run(target, probe=True)
            shutil.copytree(target / 'evidence', args.output / 'evidence/cleanup-cases' / scenario)


if __name__ == '__main__':
    main()
