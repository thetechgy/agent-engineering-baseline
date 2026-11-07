"""Reviewed gh fixture commands through real Harbor oracle trials and collection."""
import copy
import json
import os
from pathlib import Path
import subprocess
import signal
import tempfile
import time

import gh_candidate
import gh_evaluations as gh
import skill_evidence as evidence
import skill_reports as reports
from aeb_gh_fixture.manifest import write_manifest
from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks
from skillevaluator.tier3.harbor.collector import collect_harbor_results
from skillevaluator.tier3.harbor.runner import build_harbor_run_command
from pester_container_validation import _qualify_reporting

ROOT = evidence.ROOT
CONTROLS = {'gh-001': 'wrong-repo', 'gh-002': 'unsupported',
            'gh-003': 'missing-trace', 'gh-014': 'unauthorized'}
# The oracle executes the reviewed commands. Its trajectory records the actual
# command/observation linkage; no model output or replay record is substituted.
SOLUTION = r'''
import json, os, shlex, subprocess
from pathlib import Path
assert os.getuid() == 1000
assert not Path('/tests').exists()
payload = json.loads(Path('/solution/candidate').read_text())
payload['present'] = Path('/workspace/skills/gh').exists()
steps = []
def observed(command):
    result = subprocess.run(command, shell=True, cwd='/workspace', capture_output=True, text=True, timeout=35)
    identity = str(len(steps))
    steps.append({'source': 'agent', 'tool_calls': [{'tool_call_id': identity,
        'function_name': 'exec_command', 'arguments': {'cmd': command}}],
        'observation': {'results': [{'source_call_id': identity, 'content': result.stdout + result.stderr}]}})
if payload['present'] and payload['expected_skill']:
    observed('cat /workspace/skills/gh/SKILL.md')
elif not payload['present']:
    assert not Path('/workspace/skills/gh').exists()
for argv in payload['commands']:
    issued = ['gh', *argv]
    if argv[:2] == ['run', 'watch']: issued = ['timeout', '30s', *issued]
    observed(shlex.join(issued))
if not payload['commands']: observed('git status --porcelain')
observed("printf '%s\\n' " + shlex.quote(json.dumps(payload['expected'])) + ' > output/result.json')
if payload['control'] == 'unsupported':
    index = int(payload['present'] and bool(payload['expected_skill']))
    call = steps[index]['tool_calls'][0]
    call.update(function_name='exec', arguments={'input': 'await tools.exec_command(dynamic);'})
if payload['control'] == 'missing-trace': steps = []
Path('/logs/agent/trajectory.json').write_text(json.dumps({'steps': steps}))
'''


def prepare(root):
    bundle = gh_candidate.stage(ROOT, root / 'bundle/gh', fixture=True)
    fixtures = {entry['id']: entry for entry in gh.dataset(ROOT)}
    rows = []; arms = {}
    for present in (True, False):
        arm = 'with_skill' if present else 'without_skill'
        tasks = stage_native_harbor_tasks(bundle, root / 'tasks' / arm, with_skill=present,
            grading_mode='custom_only', workspace_mode='group', workspace_skill_paths=[bundle.parent / gh.COMPETING])
        if len(tasks) != 24: raise RuntimeError('Incomplete gh native cohort')
        for task in tasks:
            entry = fixtures[task.name]; control = CONTROLS.get(task.name, 'good')
            commands = copy.deepcopy(entry['contract']['good_commands'])
            if control == 'wrong-repo':
                commands[0] = [value.replace('fixture-org/widget', 'fixture-fork/other').replace('owner=fixture-org', 'owner=fixture-fork') for value in commands[0]]
            elif control == 'unauthorized':
                commands.append(['api', 'repos/fixture-org/widget/issues/12', '--method', 'POST'])
            solution = task / 'solution'; solution.mkdir()
            reports.write_json(solution / 'candidate', {'expected_skill': entry.get('expected_skill'),
                'commands': commands, 'expected': entry['contract']['expected'], 'control': control})
            (solution / 'solve.py').write_text(SOLUTION)
            (solution / 'solve.sh').write_text('#!/bin/sh\nset -eu\nexec python3 -I /solution/solve.py\n')
            # Invoke the same standalone custom grader; no remote standard grader.
            (task / 'tests/test.sh').write_text('#!/bin/sh\nset -eu\nexec python3 -I /tests/grader.py\n')
        rows.extend(evidence.capture_custom_tasks(ROOT, 'gh', tasks, arm, purpose='oracle_qualification'))
        arms[arm] = tasks
    manifest = write_manifest(root / 'operator', [t for tasks in arms.values() for t in tasks],
                              staged_roots=[root / 'tasks', root / 'bundle'])
    return bundle, fixtures, rows, arms, manifest


def main(artifact):
    from aeb_gh_fixture.backend import require_runtime
    require_runtime()
    from evaluator_profiles import runtime, candidate_versions
    runtime(candidate_versions(), owning=True)
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    if any(os.environ.get(k) for k in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'NVIDIA_API_KEY')):
        raise RuntimeError('Provider credentials forbidden')
    artifact = Path(artifact)
    with tempfile.TemporaryDirectory(prefix='gh-oracle-', dir=os.environ.get('RUNNER_TEMP')) as temporary:
        root = Path(temporary)
        os.environ['SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE'] = str(root / 'key')
        bundle, fixtures, rows, arms, manifest = prepare(root)
        jobs = root / 'jobs'; stages = []
        before = {kind: subprocess.check_output(command, text=True).split() for kind, command in (
            ('containers', ['docker', 'ps', '-aq']), ('networks', ['docker', 'network', 'ls', '-q']))}
        try:
            for arm, tasks in arms.items():
                command = build_harbor_run_command(agent='oracle', env_mode='aeb-gh-fixture',
                    dataset_path=tasks[0].parent, job_name='gh-codex-' + ('with' if arm == 'with_skill' else 'without'),
                    jobs_dir=jobs, n_attempts=1, n_concurrent=2, timeout_multiplier=1.0)
                started = time.monotonic(); event = {'arm': arm, 'stage': 'native_oracle', 'status': 'running'}
                stages.append(event)
                artifact.mkdir(parents=True, exist_ok=True)
                reports.write_json(artifact / 'command-stages.json', stages)
                from qualify_evaluator_candidate import run_native
                with (root / 'native-command.log').open('w') as log:
                    code = run_native(command, env={**os.environ, 'AEB_GH_MANIFEST': str(manifest),
                        'PYTHON_DOTENV_DISABLED': '1'}, log=log, timeout=2400)
                event.update(status='complete' if code == 0 else 'infrastructure_error' if code == 124 else 'failed',
                    returncode=code, elapsed_sec=round(time.monotonic() - started, 3))
                reports.write_json(artifact / 'command-stages.json', stages)
                if code:
                    from skillevaluator.utils.redaction import redact_sensitive_text
                    diagnostic = redact_sensitive_text((root / 'native-command.log').read_text(errors='replace')[-32768:])
                    diagnostic = diagnostic.replace(str(root), '<native>').replace(str(ROOT), '<checkout>')
                    (artifact / 'command-diagnostics.txt').write_text(diagnostic)
                    raise RuntimeError('Native gh oracle command failed')
            native = root / 'native'; run = native / 'results/gh/native-oracle'
            collected = collect_harbor_results('gh', ['codex'], run, jobs, expected_cases=24,
                expected_case_ids=list(fixtures), expected_trials=24,
                agent_models={'codex': {'model': 'credential-free-oracle', 'source': 'qualification'}})
            config = {'grading': {'mode': 'custom_only'}, 'judge': {'enabled': False},
                      'qualification': {'producer': 'oracle', 'inference': False}}
            reports.write_json(run / 'run_config.json', config)
            reports.write_json(run / 'result.json', {**collected, 'skill_name': 'gh',
                'report_status': 'incomplete', 'diagnostic_only': True, 'qualification': True})
            numeric = evidence.capture_custom_numeric_fields(ROOT, 'gh', jobs, root, rows, purpose='oracle_qualification')
            reports.write_json(native / evidence.CUSTOM_CAPTURE, evidence.custom_capture(ROOT, 'gh', bundle, rows,
                purpose='oracle_qualification', attempts=1, agent='oracle',
                execution_policy={'environment': 'aeb-gh-fixture', 'concurrency': 2, 'timeout_multiplier': 1.0, 'stop_on_pass': False},
                numeric_excerpts=numeric))
            # Check prospective expectations against actual native sidecars.
            outcomes = []
            for arm in ('with-skill', 'without-skill'):
                paths = list((run / 'codex' / arm / 'trials').glob('*/reward.json'))
                if len(paths) != 24: raise RuntimeError('Incomplete collected gh arm')
                for path in paths:
                    reward = reports.read_json(path); case = reward['entry_id']; metrics = reward.get('custom_metrics', {})
                    status = reward.get('details', {}).get('outcome', {}).get('classification')
                    if case in ('gh-002', 'gh-003'):
                        expected_status = 'unsupported' if case == 'gh-002' else 'unknown'
                        if status != expected_status or metrics or reward.get('evaluation_status') != 'failed':
                            raise RuntimeError('Missing/unsupported evidence acquired a score')
                    elif case == 'gh-001':
                        if metrics.get('gh_task') != 0: raise RuntimeError('Broken gh work passed')
                    elif case == 'gh-014':
                        if metrics.get('gh_task') != 1 or metrics.get('gh_authorization') != 0:
                            raise RuntimeError('Unauthorized gh work lost separate correctness')
                    elif any(metrics.get('gh_' + key) != 1 for key in ('task', 'evidence', 'authorization', 'commands', 'recovery', 'efficiency')):
                        raise RuntimeError('Correct native gh fixture failed')
                    outcomes.append({'case': case, 'arm': arm, 'outcome': status, 'control': CONTROLS.get(case, 'good')})
            reports.benchmark_artifacts(ROOT, native, 'gh', artifact / 'native')
            _qualify_reporting(root, artifact / 'native', candidate=True, name='gh')
            reports.write_json(artifact / 'qualification.json', {'success': True, 'inference': False,
                'producer': 'oracle', 'expected': 48, 'outcomes': outcomes,
                'versions': __import__('evaluator_profiles').candidate_versions()})
        finally:
            after = {kind: subprocess.check_output(command, text=True).split() for kind, command in (
                ('containers', ['docker', 'ps', '-aq']), ('networks', ['docker', 'network', 'ls', '-q']))}
            clean = all(set(before[k]) == set(after[k]) for k in before)
            artifact.mkdir(parents=True, exist_ok=True)
            reports.write_json(artifact / 'cleanup.json', {'complete': clean})
            if not clean: raise RuntimeError('Native gh cleanup incomplete')
