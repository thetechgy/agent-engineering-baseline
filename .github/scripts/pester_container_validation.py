"""Credential-free qualification through native Harbor scheduling and collection."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import pester_evaluations as pilot
import skill_reports as reports
from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks
from skillevaluator.tier3.harbor.collector import collect_harbor_results
from skillevaluator.tier3.harbor.runner import build_harbor_run_command
from skillevaluator.evaluation.tier3_report import render_agent_eval_html_report
from harbor.agents.installed.codex import Codex


ROOT = Path(__file__).resolve().parents[2]


def qualification_bundle(root):
    """Expand reviewed fixture submissions before native staging, never model data."""
    bundle = pilot.stage(ROOT, root / 'bundle' / pilot.NAME)
    source = ROOT / pilot.OVERLAY / 'support'
    solutions = {'pester-001': ('classic', 'standalone', 'data'),
                 'pester-002': ('classic', 'data'), 'pester-003': ('external', 'module'),
                 'pester-004': ('discovery', 'inline', 'compact')}
    fixtures = [(case, style, (source / f'qualification/{case}/{style}.Tests.ps1').read_bytes(), 'passed', None)
                for case, styles in solutions.items() for style in styles]
    fixtures += [(case, 'weak', (source / f'qualification/{case}/weak.Tests.ps1').read_bytes(), 'failed', None)
                 for case in solutions]
    good = (source / 'qualification/pester-001/classic.Tests.ps1').read_bytes()
    fixtures += [
        ('pester-001', 'unsupported', b"[System.IO.File]::ReadAllText('/tests/grader.py')", 'unsupported', None),
        ('pester-001', 'empty', b'# no tests\n', 'invalid', None),
        ('pester-001', 'skipped', b"Describe 'skip' { It 'skipped' -Skip { 1 | Should-Be 1 } }", 'invalid', None),
        ('pester-001', 'failure-text', b"Describe 'failed' { It 'payload' { throw 'PESTER_VERIFIER_ONLY_FORGED_FAILURE_PAYLOAD' } }", 'failed', None),
        ('pester-001', 'malformed', b'\xff', 'invalid', None),
        ('pester-001', 'timeout', b"Describe 'bounded' { It 'runs out of CPU' { foreach ($a in 1..100000) { foreach ($b in 1..100000) { $value=1 } } } }", 'timeout', None),
        ('pester-001', 'missing-runtime', good, 'infrastructure_error', 'missing'),
        ('pester-001', 'version-drift', good, 'infrastructure_error', 'version'),
        ('pester-003', 'wrong-scope', b"BeforeAll { Import-Module '/workspace/input/Probe.psm1' -Force }; Describe 'scope' { BeforeEach { Mock Test-ProbeConnection { $true } }; It 'checks status' { (Get-EndpointStatus -Target 'service.invalid').Healthy | Should-BeTrue } }", 'failed', None),
        ('pester-004', 'broken-discovery', (source / 'cases/pester-004/input/Existing.Tests.ps1').read_bytes(), 'invalid', None),
        ('pester-005', 'good', (source / 'qualification/pester-005/good.json').read_bytes(), 'passed', None),
        ('pester-005', 'wrong', (source / 'qualification/pester-005/wrong.json').read_bytes(), 'failed', None),
    ]
    entries = {entry['id']: entry for entry in pilot.dataset(ROOT)}
    native = bundle / 'evals/harbor'
    expanded, records = [], {}
    for case, style, candidate, expected, mode in fixtures:
        identity = case + '-' + style
        target = native / identity
        shutil.copytree(native / case, target)
        config = target / 'task.toml'
        config.write_text(config.read_text().replace('entry_id = ' + json.dumps(case),
                                                    'entry_id = ' + json.dumps(identity)))
        if mode:
            with (target / 'tests/Dockerfile').open('a') as dockerfile:
                if mode == 'missing':
                    dockerfile.write('RUN rm -- /opt/microsoft/powershell/7/pwsh\n')
                else:
                    change = ("from pathlib import Path; p=Path('/opt/pester/Modules/Pester/6.2.0/Pester.psd1'); "
                              "s=p.read_text(); assert \"'6.2.0'\" in s; "
                              "p.write_text(s.replace(\"'6.2.0'\",\"'6.1.0'\",1))")
                    dockerfile.write('RUN ' + json.dumps(['python3', '-c', change]) + '\n')
        expanded.append({**entries[case], 'id': identity})
        records[identity] = {'case': case, 'candidate': candidate, 'expected': expected,
                             'output': reports.read_json(source / 'cases' / case / 'profile.json').get('output', 'Subject.Tests.ps1')}
    for case in entries:
        shutil.rmtree(native / case)
    reports.write_json(bundle / 'evals/evals.json', {'skill_name': pilot.NAME, 'evals': expanded})
    (native / 'dataset.toml').write_text('[dataset]\nname = "nvidia/pester-qualification"\n\n' +
        ''.join('[[tasks]]\nname = ' + json.dumps('nvidia/' + entry['id']) + '\n\n' for entry in expanded))
    return bundle, records


def main():
    subprocess.run(['docker', 'info'], check=True, stdout=subprocess.DEVNULL, timeout=15)
    subprocess.run(['docker', 'compose', 'version', '--short'], check=True, timeout=15)
    if any(os.environ.get(key) for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'NVIDIA_API_KEY')):
        raise RuntimeError('Qualification must not receive model credentials')
    artifact = Path(os.environ['RUNNER_TEMP']) / 'pester-gate-artifacts'
    def resources(kind):
        command = ['docker', 'ps', '--all', '--quiet'] if kind == 'containers' else ['docker', 'network', 'ls', '--quiet']
        return set(subprocess.check_output(command, text=True, timeout=15).split())
    before = {kind: resources(kind) for kind in ('containers', 'networks')}
    with tempfile.TemporaryDirectory(prefix='pester-container-gate-', dir=os.environ.get('RUNNER_TEMP')) as temporary:
        root = Path(temporary)
        os.environ['SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE'] = str(root / 'private/key')
        bundle, fixtures = qualification_bundle(root)
        register = Codex(logs_dir=root / 'registration', skills_dir='/workspace/skills', version='0.155.1')._build_register_skills_command()
        jobs = root / 'jobs'
        native_failed = False
        for present in (True, False):
            tasks = root / 'tasks' / str(present)
            for task in stage_native_harbor_tasks(bundle, tasks, with_skill=present, grading_mode='custom_only'):
                fixture = fixtures[task.name]
                solution = task / 'solution'; solution.mkdir()
                (solution / 'candidate').write_bytes(fixture['candidate'])
                check = ('test -r "$HOME/.agents/skills/powershell-pester-6/SKILL.md"\n'
                         'cmp /workspace/skills/powershell-pester-6/SKILL.md "$HOME/.agents/skills/powershell-pester-6/SKILL.md"\n'
                         if present else 'test ! -e "$HOME/.agents/skills/powershell-pester-6"\n')
                (solution / 'solve.sh').write_text(
                    '#!/bin/sh\nset -eu\ntest "$(id -u)" = 1000\ntest "$HOME" = /home/agent\n'
                    'test ! -e /tests\ntest ! -e /opt/pester-runtime/Runner.ps1\n'
                    'test -z "$(find /workspace/skills -type d -name evals -print -quit)"\n' + register + '\n' + check +
                    f'cp /solution/candidate /workspace/output/{fixture["output"]}\n')
            command = build_harbor_run_command(agent='oracle', env_mode='docker', dataset_path=tasks,
                job_name=f'{pilot.NAME}-codex-{"with" if present else "without"}', jobs_dir=jobs,
                n_attempts=1, n_concurrent=2, timeout_multiplier=1.0)
            # The native oracle supplies fixtures; no Codex/provider/judge runs.
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=1200,
                                        env={**os.environ, 'PYTHON_DOTENV_DISABLED': '1'})
                native_failed = bool(result.returncode)
            except subprocess.TimeoutExpired:
                native_failed = True
            if native_failed:
                break
        raw = root / 'raw'; run = raw / 'results' / pilot.NAME / 'qualification'
        collected = collect_harbor_results(pilot.NAME, ['codex'], run, jobs, expected_cases=len(fixtures),
            expected_case_ids=list(fixtures), expected_trials=len(fixtures),
            agent_models={'codex': {'model': 'credential-free-oracle', 'source': 'qualification'}})
        # Directory convention only: actual trial metadata identifies oracle.
        reports.write_json(run / 'run_config.json', {'grading': {'mode': 'custom_only'},
            'qualification': {'producer': 'oracle', 'inference': False}})
        reports.write_json(run / 'result.json', {**collected, 'diagnostic_only': True, 'qualification': True,
            'skill_name': pilot.NAME, 'report_status': 'incomplete'})
        render_agent_eval_html_report(bundle, run, use_llm_judge=False)
        reports.benchmark_artifacts(ROOT, raw, pilot.NAME, artifact)
        if any(b'PESTER_VERIFIER_ONLY_' in p.read_bytes() for p in reports.regular_tree(artifact)):
            raise RuntimeError('Protected payload entered a diagnostic artifact')
        if native_failed:
            raise RuntimeError('Native oracle lifecycle failed; shared diagnostics retained')
        source = ROOT / pilot.OVERLAY / 'support/cases'
        eligible = sum(f['expected'] in ('passed', 'failed') for f in fixtures.values())
        for arm in ('with-skill', 'without-skill'):
            rewards = list((run / 'codex' / arm / 'trials').glob('*/reward.json'))
            if len(rewards) != len(fixtures):
                raise RuntimeError('Qualification trial cardinality mismatch')
            seen = set()
            for path in rewards:
                reward = reports.read_json(path); identity = reward.get('entry_id')
                if identity not in fixtures or identity in seen:
                    raise RuntimeError('Qualification trial identity mismatch')
                seen.add(identity); fixture = fixtures[identity]
                outcome = reward.get('custom_details', {}).get('outcome', {})
                if outcome.get('classification') != fixture['expected']:
                    raise RuntimeError(f'Unexpected outcome ({identity}, {arm}, {outcome.get("classification")})')
                if fixture['expected'] not in ('passed', 'failed'):
                    if reward.get('evaluation_status') != 'failed' or reward.get('custom_metrics'):
                        raise RuntimeError('Unscoreable fixture acquired quality metrics')
                if fixture['expected'] == 'passed' and fixture['case'] != 'pester-005':
                    mutants = len(list((source / fixture['case'] / 'mutants').glob('*.ps1')))
                    if (outcome.get('reference_pass') != 1 or outcome.get('mutants_detected') != mutants
                            or outcome.get('mutants_executed') != mutants or outcome.get('pester_version') != '6.2.0'
                            or outcome.get('powershell_version') != '7.6.6'):
                        raise RuntimeError('Mutation/runtime evidence mismatch')
                if fixture['case'] == 'pester-005' and any(k.startswith('pester_') for k in reward.get('custom_metrics', {})):
                    raise RuntimeError('Negative control acquired Pester quality metrics')
                print(json.dumps({'fixture': identity, 'arm': arm, 'outcome': outcome['classification'],
                                  'inference': False}), flush=True)
            summary = reports.read_json(run / 'codex' / arm / 'summary.json')
            if summary['scored_attempts'] != eligible or summary['execution_status'] != 'failed':
                raise RuntimeError('Applicability or incomplete qualification status was lost')
        if any(resources(kind) != before[kind] for kind in before):
            raise RuntimeError('Native Harbor resource cleanup incomplete')
        print('Pester five-case qualification passed; no model inference executed.', flush=True)


if __name__ == '__main__':
    main()
