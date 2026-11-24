#!/usr/bin/env python3
"""Credential-free released verifier/collector → benchmark evidence qualification.

Uses existing setup candidate-next. Fixed judge responses exercise transport and
released verdict semantics; they never measure provider or skill effectiveness.
"""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import json
from itertools import product
import os
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / '.github/scripts'), str(ROOT / '.github/tests')]
import benchmark_evidence as benchmark
import evaluator_profiles as profiles
import skill_evidence as evidence
import skill_reports as reports


def fixture(output, scenario, *, judge_context=None, producer=profiles.NEXT, mode='standard',
            metadata=None, codex='0.155.1', model=None, accuracy_factor=1.0, workspace=ROOT):
    model = model or (reports.POLICY['model'] if judge_context else 'gpt-5.6-sol')
    attempts = reports.MODES[mode]
    from harbor.models.job.result import JobResult, JobStats
    from harbor.models.task.task import Task
    from harbor.models.trial.result import TrialResult, ExceptionInfo
    from skillevaluator.tier3.harbor import adapter
    from skillevaluator.tier3.harbor.collector import collect_harbor_results
    from skillevaluator.tier3.harbor.report_data import build_dataset_snapshot
    from skillevaluator.tier3.harbor.templates import eval as verifier
    now = datetime(2026, 11, 15, tzinfo=timezone.utc)
    skill = workspace / '.apm/skills/podman'
    native = output / 'native'; run = native / 'results/podman' / scenario
    jobs = run / '_harbor-jobs'
    for present in (True, False):
        tasks = adapter.generate_harbor_tasks(skill, output / 'tasks' / str(present), with_skill=present,
            base_image='', custom_dockerfile_mode='disabled')
        job = jobs / ('podman-codex-with' if present else 'podman-codex-without')
        trials = []
        for index, (task, attempt) in enumerate(product(tasks, range(1, attempts + 1)), 1):
            case = str(reports.read_json(task / 'tests/entry.json')['id'])
            name = f'skillevaluator-{case}__attempt{attempt:03d}'
            trial = job / name; target = trial / 'verifier'; target.mkdir(parents=True)
            unsupported = scenario == 'unavailable' and case == '5'
            command = 'cat /workspace/skills/podman/SKILL.md' if present and case != '8' else 'printf fixture'
            if case == '3': command = 'cat /etc/shadow'
            call = {'tool_call_id': 'fixture', 'function_name': 'exec_command', 'arguments': {'cmd': command}}
            if unsupported:
                call = {'tool_call_id': 'fixture', 'function_name': 'exec',
                        'arguments': {'input': 'await tools.exec_command(dynamic);'}}
            content = 'Authorization: Bearer sk-' + 'abcdefgh12345678' if unsupported else 'fixture'
            trajectory = {'steps': [{'source': 'agent', 'tool_calls': [call],
                'observation': {'results': [{'source_call_id': 'fixture', 'content': content}]}},
                {'source': 'agent', 'message': 'Simulated answer; no model executed.'}]}
            trace = trial / 'agent/trajectory.json'; reports.write_json(trace, trajectory)
            score = 0.0 if case == '2' else 1.0
            unavailable = scenario == 'unavailable' and case == '4'
            paths = {'ATIF_PATH': trace, 'ENTRY_PATH': task / 'tests/entry.json', 'REWARD_JSON': target / 'reward.json',
                'REWARD_TXT': target / 'reward.txt', 'SKILL_EVALUATOR_REWARD_JSON': target / 'skill_evaluator_reward.json'}
            response = {'score': score, 'reason': 'Simulated judge fixture'}
            goal_response = {'score': None, 'error': 'Simulated judgment unavailable'} if unavailable else response
            with ExitStack() as stack:
                stack.enter_context(patch.multiple(verifier, **paths))
                stack.enter_context(patch.dict(os.environ, {'HARBOR_ATIF_PATH':str(trace)}))
                if judge_context is None:
                    for function, reply in (('judge_accuracy', {**response, 'score': score * accuracy_factor}),
                                            ('judge_goal_accuracy', goal_response),
                                            ('judge_behavior_check', response)):
                        stack.enter_context(patch.object(verifier, function, return_value=reply))
                else:
                    stack.enter_context(judge_context(verifier, case))
                try:
                    verifier.main()
                except SystemExit as error:
                    reports.require(error.code in (0, 1), 'Unexpected verifier exit')
            numeric = reports.read_json(target / 'reward.json')
            rich = reports.read_json(target / 'skill_evaluator_reward.json')
            failed = rich.get('evaluation_status') == 'failed'
            result = TrialResult.model_validate({'id': UUID(int=index + (100 if present else 0)),
                'task_name':'nvidia/skillevaluator-' + case, 'trial_name':name, 'trial_uri':trial.as_uri(),
                'task_id':{'path':str(task)}, 'task_checksum':Task(task).checksum,
                'config':{'task':{'path':str(task)}, 'trial_name':name},
                'agent_info':{'name':'codex', 'version':codex, 'model_info':{'name':model}},
                'agent_result':{'n_input_tokens':0, 'n_output_tokens':0, 'n_cache_tokens':0},
                'verifier_result':{'rewards':numeric}, 'started_at':now, 'finished_at':now,
                'exception_info': {'exception_type':'VerifierError', 'exception_message':'Simulated unavailable evidence',
                                   'exception_traceback':'Fixture verifier error', 'occurred_at':now} if failed else None})
            if scenario == 'unavailable' and case == '6':
                for member in target.iterdir(): member.unlink()
                result = result.model_copy(update={'verifier_result':None,
                    'exception_info': ExceptionInfo(
                        exception_type='AgentExecutionError', exception_message='Fixture CLI exited 23',
                        exception_traceback='Fixture primary runtime failure', occurred_at=now)})
            (trial / 'result.json').write_text(result.model_dump_json(indent=2))
            trials.append(result)
        job_result = JobResult(id=UUID(int=1000 + int(present)), started_at=now, updated_at=now, finished_at=now,
            n_total_trials=len(trials), stats=JobStats.from_trial_results(trials, n_total_trials=len(trials)), trial_results=trials)
        (job / 'result.json').write_text(job_result.model_dump_json(indent=2))
    meta = metadata if metadata is not None else {'profile':('behavioral-090-accounting-v1' if producer is profiles.ACCOUNTING else 'behavioral-090-offline-v1'), 'origin':'credential_free_fixture', 'judgments':'simulated'}
    reports.write_json(native / 'versions.json', profiles.candidate_versions(producer))
    policy = {**reports.POLICY, 'model':model, 'codex':codex, 'evaluator_revision':producer['revision'], 'harbor':producer['harbor'],
              'python':producer['python']}
    reports.write_json(native / 'provenance.json', {'schema_version':1, 'skill':'podman', 'mode':mode,
        'policy':policy, 'patch_sha256':producer['patch_sha256'], 'benchmark':meta})
    config = {'grading':{'mode':'default'}, 'judge':{'enabled':False},
              'provider':{'name':'openai', 'model':model},
              'harbor':{'environment':{'value':'docker'}, 'n_attempts':attempts, 'n_concurrent':2,
                        'stop_on_pass':False, 'timeout_multiplier':2.0},
              'evaluated_source':{'repository':'thetechgy/agent-engineering-baseline', 'commit':evidence.git_revision(workspace)}}
    reports.write_json(run / 'run_config.json', config)
    snapshot = build_dataset_snapshot(reports.read_json(skill / 'evals/evals.json')['evals'], evaluator_version=producer['version'])
    reports.write_json(run / 'dataset_snapshot.json', snapshot)
    reports.write_json(run / 'attempt_policy.json', {'max_attempts':attempts, 'stop_on_pass':False, 'pass_threshold':0.5})
    if scenario == 'interrupted':
        job_path = jobs / 'podman-codex-with/result.json'
        original = JobResult.model_validate_json(job_path.read_text())
        retained = [t for t in original.trial_results if t.trial_name != 'skillevaluator-1__attempt001']
        partial = original.model_copy(update={'finished_at':None, 'trial_results':retained,
            'stats':JobStats.from_trial_results(retained, n_total_trials=original.n_total_trials)})
        job_path.write_text(partial.model_dump_json(indent=2))
        (jobs / 'podman-codex-with/skillevaluator-1__attempt001/result.json').unlink()
        reports.recover_benchmark(workspace, native, 'podman', mode, 'cancelled', evidence_profile=meta['profile'])
        collected = reports.read_json(run / 'result.json')
    else:
        collected = collect_harbor_results('podman', ['codex'], run, jobs, expected_cases=10,
            expected_case_ids=[str(i) for i in range(1,11)], expected_trials=10 * attempts, n_attempts=attempts,
            agent_models={'codex':{'model':model, 'source':'fixture'}})
    reports.write_json(run / 'result.json', {**collected, 'skill_name':'podman',
        'report_status':'complete' if scenario == 'complete' else 'incomplete',
        'diagnostic_only':True, 'run_config':config,
        'dataset_digest':snapshot['dataset_digest'], 'dataset_summary':snapshot['dataset_summary'],
        'metric_set':'skill-evaluator-default-v2', 'score_policy':producer['scoring']})
    return native


def worker(output):
    network = []
    def offline(event, args):
        if event.startswith('socket.') or event == 'http.client.connect':
            network.append(event)
            raise RuntimeError('Behavioral qualification forbids network')
    sys.addaudithook(offline)
    profiles.runtime(profiles.candidate_versions(profiles.NEXT), owning=True)
    from qualify_current_evaluator import render
    records = []; receipts = {}
    for scenario in ('complete', 'unavailable', 'interrupted'):
        root = output / scenario
        native = fixture(root, scenario)
        sanitized = root / 'sanitized'
        reports.benchmark_artifacts(ROOT, native, 'podman', sanitized)
        public = benchmark.report(ROOT, sanitized, 'podman', 'standard', root / 'admitted')
        records.append(public)
        receipts[scenario] = benchmark.history_admission(public)
    render(records, output / 'reporting')
    import unittest
    os.environ['BENCHMARK_090_EVIDENCE'] = str(output)
    tests = unittest.defaultTestLoader.loadTestsFromName('test_benchmark_evidence')
    result = unittest.TextTestRunner(verbosity=2).run(tests)
    reports.require(result.wasSuccessful(), 'Versioned behavioral admission controls failed')
    reports.require(not network, 'Qualification attempted network access')
    reports.write_json(output / 'receipt.json', {'profile':profiles.benchmark_profile('behavioral-090-offline-v1')['id'],
        'producer_revision':evidence.git_revision(ROOT), 'versions':profiles.candidate_versions(profiles.NEXT),
        'sources':{member:evidence.digest_bytes((ROOT / member).read_bytes()) for member in (
            '.github/scripts/qualify_benchmark_evidence.py', '.github/scripts/benchmark_evidence.py',
            '.github/scripts/evaluator_090.py', '.github/scripts/evaluator_profiles.py',
            '.github/scripts/skill_evidence.py', '.github/scripts/skill_reports.py',
            '.github/scripts/skill_analysis.py', '.github/scripts/skill_report.py',
            '.github/scripts/skill_history.py', '.github/scripts/skill_pages.py',
            '.github/evals/benchmark-090.json')},
        'inference':False, 'judges':'simulated', 'network_attempts':network, 'history':receipts})
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.output); return
    output = args.output.absolute()
    reports.require(output.resolve() == output and not output.is_relative_to(ROOT) and not output.exists(),
                    'Fresh external qualification destination required')
    output.mkdir(parents=True)
    home = output / 'empty-home'; home.mkdir()
    env = {k:os.environ[k] for k in ('PATH', 'TMPDIR', 'LANG') if k in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTHON_DOTENV_DISABLED='1', LITELLM_LOCAL_MODEL_COST_MAP='True',
        HOME=str(home), USERPROFILE=str(home), XDG_CACHE_HOME=str(output / 'cache'),
        XDG_STATE_HOME=str(output / 'state'), SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE=str(output / 'fixture-provenance.key'))
    subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '--worker', '--output', str(output)],
                   env=env, check=True, timeout=300)


if __name__ == '__main__':
    main()
