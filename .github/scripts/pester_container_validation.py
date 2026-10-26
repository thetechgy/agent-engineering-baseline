"""Credential-free feasibility gate using native Harbor's oracle and verifier."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import pester_evaluations as pilot
import skill_reports as reports
from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks
from skillevaluator.tier3.harbor.collector import collect_harbor_results
from skillevaluator.tier3.harbor.runner import build_harbor_run_command
from skillevaluator.evaluation.tier3_report import render_agent_eval_html_report
from harbor.agents.installed.codex import Codex


ROOT = Path(__file__).resolve().parents[2]


def main():
    subprocess.run(['docker', 'info'], check=True, stdout=subprocess.DEVNULL, timeout=15)
    subprocess.run(['docker', 'compose', 'version', '--short'], check=True, timeout=15)
    if any(os.environ.get(key) for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'NVIDIA_API_KEY')):
        raise RuntimeError('Qualification must not receive model credentials')
    artifact_root = Path(os.environ['RUNNER_TEMP']) / 'pester-gate-artifacts'
    artifact_root.mkdir(exist_ok=False)
    def resources(kind):
        command = ['docker', 'ps', '--all', '--quiet'] if kind == 'containers' else ['docker', 'network', 'ls', '--quiet']
        return set(subprocess.check_output(command, text=True, timeout=15).split())
    before = {kind: resources(kind) for kind in ('containers', 'networks')}
    with tempfile.TemporaryDirectory(prefix='pester-container-gate-', dir=os.environ.get('RUNNER_TEMP')) as temporary:
        root = Path(temporary)
        os.environ['SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE'] = str(root / 'private/key')
        bundle = pilot.stage(ROOT, root / 'bundle' / pilot.NAME)
        source = ROOT / pilot.OVERLAY / 'support'
        register = Codex(logs_dir=root / 'codex-registration', skills_dir='/workspace/skills', version='0.155.1')._build_register_skills_command()
        fixtures = [(style, (source / f'qualification/pester-001/{style}.Tests.ps1').read_text(), 'passed')
                    for style in ('classic', 'standalone', 'data', 'weak')]
        fixtures[-1] = (*fixtures[-1][:2], 'failed')
        fixtures += [
            ('unsupported', "[System.IO.File]::ReadAllText('/tests/grader.py')", 'unsupported'),
            ('empty', '# no tests\n', 'invalid'),
            ('skipped', "Describe 'skip' { It 'skipped' -Skip { 1 | Should-Be 1 } }", 'invalid'),
            ('failure-text', "Describe 'failed' { It 'payload' { throw 'PESTER_VERIFIER_ONLY_FORGED_FAILURE_PAYLOAD' } }", 'failed'),
        ]
        for label, candidate, expected in fixtures:
            jobs = root / 'jobs' / label
            native_failed = False
            for present in (True, False):
                tasks = root / 'tasks' / f'{label}-{present}'
                task, = stage_native_harbor_tasks(bundle, tasks, with_skill=present, grading_mode='custom_only')
                solution = task / 'solution'; solution.mkdir()
                (solution / 'candidate.Tests.ps1').write_text(candidate)
                check_skill = ('test -r "$HOME/.agents/skills/powershell-pester-6/SKILL.md"\n'
                               'cmp /workspace/skills/powershell-pester-6/SKILL.md "$HOME/.agents/skills/powershell-pester-6/SKILL.md"\n'
                               if present else 'test ! -e "$HOME/.agents/skills/powershell-pester-6"\n')
                (solution / 'solve.sh').write_text(
                    '#!/bin/sh\nset -eu\ntest "$(id -u)" = 1000\n'
                    'test "$HOME" = /home/agent\ntest ! -e /tests\n'
                    'test ! -e /opt/pester-runtime/Runner.ps1\n'
                    'test -z "$(find /workspace/skills -type d -name evals -print -quit)"\n'
                    + register + '\n' + check_skill +
                    'cp /solution/candidate.Tests.ps1 /workspace/output/Subject.Tests.ps1\n')
                command = build_harbor_run_command(
                    agent='oracle', env_mode='docker', dataset_path=tasks,
                    job_name=f'{pilot.NAME}-codex-{"with" if present else "without"}',
                    jobs_dir=jobs, n_attempts=1, n_concurrent=1, timeout_multiplier=1.0)
                # Native oracle writes a supplied fixture. It never installs or
                # invokes Codex, an API provider, or a model judge.
                result = subprocess.run(command, capture_output=True, text=True, timeout=1200,
                                        env={**os.environ, 'PYTHON_DOTENV_DISABLED': '1'})
                if result.returncode:
                    native_failed = True
                    break  # Collect actual failure diagnostics before rejecting.
            raw = root / 'raw' / label
            run = raw / 'results' / pilot.NAME / 'qualification'
            collected = collect_harbor_results(
                skill_name=pilot.NAME, agents=['codex'], output_dir=run, jobs_dir=jobs,
                expected_cases=1, expected_case_ids=['pester-001'], expected_trials=1,
                agent_models={'codex': {'model': 'credential-free-oracle', 'source': 'qualification'}})
            # The collector directory convention is codex; retained native
            # trial metadata still identifies oracle. This is not model data.
            reports.write_json(run / 'run_config.json', {'grading': {'mode': 'custom_only'},
                               'qualification': {'producer': 'oracle', 'inference': False}})
            reports.write_json(run / 'result.json', {**collected, 'diagnostic_only': True,
                               'qualification': True, 'skill_name': pilot.NAME, 'report_status': 'incomplete'})
            render_agent_eval_html_report(bundle, run, use_llm_judge=False)
            # Retain only the normal shared allowlisted/redacted output, also on
            # negative outcomes. Task/build contexts and raw jobs are not uploaded.
            artifact = artifact_root / label
            reports.benchmark_artifacts(ROOT, raw, pilot.NAME, artifact)
            for member in reports.regular_tree(artifact):
                if b'PESTER_VERIFIER_ONLY_' in member.read_bytes():
                    raise RuntimeError('Protected payload entered a diagnostic artifact')
            if native_failed:
                raise RuntimeError(f'Native oracle lifecycle failed ({label}); shared diagnostics retained')
            for arm in ('with-skill', 'without-skill'):
                rewards = list((run / 'codex' / arm / 'trials').glob('*/reward.json'))
                if len(rewards) != 1:
                    raise RuntimeError('Qualification trial cardinality mismatch')
                reward = reports.read_json(rewards[0])
                outcome = reward.get('custom_details', {}).get('outcome', {})
                if outcome.get('classification') != expected:
                    raise RuntimeError(f'Unexpected qualification outcome ({label}, {arm}, {outcome.get("classification")})')
                if expected in ('unsupported', 'invalid'):
                    summary = reports.read_json(run / 'codex' / arm / 'summary.json')
                    if summary['scored_attempts'] or summary['overall_score'] is not None:
                        raise RuntimeError('Unscoreable candidate was scored')
            if any(resources(kind) != before[kind] for kind in before):
                raise RuntimeError('Native Harbor resource cleanup incomplete')
            print(json.dumps({'qualification': label, 'outcome': expected, 'arms': 2,
                              'artifact_containment': 'passed', 'inference': False}), flush=True)
        # Native Harbor deletes trial containers by default. A disposable hosted
        # runner owns build cache/images; nothing is installed on a workstation.
        print('Pester feasibility gate passed; no model inference executed.', flush=True)


if __name__ == '__main__':
    main()
