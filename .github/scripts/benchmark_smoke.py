"""Prepare and authenticate the single protected Podman compatibility smoke."""

import argparse
import os
import re
import subprocess
from pathlib import Path
import signal
import time

from benchmark_native import native_versions, validate_runtime
from benchmark_podman import CODEX_PROFILE, SMOKE_CASE, compose_teardown_complete, configure_openai_task, scope, stage_task
from skill_orchestration import BENCHMARK, REPOSITORY, git, read_artifact
import skill_pages as pages
from skill_reports import outputs, read_json, require, summary, write_json

MODE = 'candidate-smoke'
BRANCH = 'qualify/skillevaluator-101-retirement'
JOB_NAMES = {'with_skill': 'podman-codex-with', 'without_skill': 'podman-codex-without'}
PROVIDER_CREDENTIALS = (
    'OPENAI_API_KEY', 'CODEX_API_KEY', 'CODEX_AUTH_JSON_PATH', 'CODEX_FORCE_AUTH_JSON',
    'ANTHROPIC_API_KEY', 'NVIDIA_API_KEY', 'SKILL_EVAL_LLM_API_KEY',
)
PROVIDER_POLICY = {
    'provider': 'openai',
    'host': 'api.openai.com',
    'preflight': False,
    'judge_transport_retries': 0,
    'judge_policy': 'strict',
    'agent_seconds_per_arm': 300,
    'inference_seconds': 900,
    'max_observed_agent_tokens_before_next_arm': 120_000,
}


def estimate_cost(*, baseline_only=False):
    profile = read_json(CODEX_PROFILE)
    prices = profile['prices_per_million']
    # The first live arm recorded about 249,000 input tokens including cache reads.
    planned = ({'input_tokens': 300_000, 'output_tokens': 120_000} if baseline_only
               else {'input_tokens': 400_000, 'output_tokens': 240_000})
    return {**planned, 'basis': 'standard_short_context_uncached',
            'usd': round((planned['input_tokens'] * prices['input'] +
                          planned['output_tokens'] * prices['output']) / 1_000_000, 2)}



def reviewed_scope(workspace, env, inputs):
    require(env['GITHUB_REPOSITORY'] == REPOSITORY
            and env['GITHUB_EVENT_NAME'] == 'workflow_dispatch'
            and env['GITHUB_REF'] == 'refs/heads/' + BRANCH
            and env['GITHUB_RUN_ATTEMPT'] == '1', 'Candidate smoke requires an initial manual feature dispatch')
    revision = pages.sha(env['GITHUB_SHA'])
    require(inputs['skill'] == 'podman' and inputs['mode'] == MODE
            and inputs.get('expected_revision') == revision
            and not any(inputs.get(key) for key in ('request_id', 'planner_run_id', 'planner_attempt')),
            'Candidate dispatch does not match its reviewed scope')
    require(git(workspace, 'rev-parse', 'HEAD').decode().strip() == revision
            and not git(workspace, 'status', '--porcelain=v1', '--untracked-files=all', '--ignored'),
            'Candidate checkout differs from the dispatched revision')
    arms = inputs.get('candidate_smoke_arms') or 'paired'
    require(arms in ('paired', 'without-skill'), 'Unknown candidate arm selection')
    selected = scope(workspace, revision, released=True)
    baseline_only = arms == 'without-skill'
    if baseline_only:
        selected.update(arms=['without_skill'], planned_trials=1)
    return {'schema_version': 2, 'kind': 'podman_101_compatibility', 'run_id': pages.number(int(env['GITHUB_RUN_ID'])),
            'attempt': 1, 'scope': selected, 'provider_policy': PROVIDER_POLICY, 'runtime': native_versions(),
            'cost_estimate': estimate_cost(baseline_only=baseline_only)}


def artifact_name(record):
    return f'podman-101-compatibility-context-{record["run_id"]}-{record["attempt"]}'


def guard(api, expected):
    run_id, attempt = expected['run_id'], expected['attempt']
    revision = expected['scope']['revision']
    run = api.get(f'actions/runs/{run_id}/attempts/{attempt}')
    require(run['id'] == run_id and run['run_attempt'] == attempt
            and run['repository']['full_name'] == run['head_repository']['full_name'] == REPOSITORY
            and run['head_branch'] == BRANCH and run['head_sha'] == revision
            and run['event'] == 'workflow_dispatch' and run['path'] == BENCHMARK,
            'Candidate run identity mismatch')
    workflow = api.get('actions/workflows/benchmark-skills.yml')
    require(workflow['id'] == run['workflow_id'] and workflow['path'] == BENCHMARK,
            'Candidate workflow identity mismatch')
    require(read_artifact(api, run, artifact_name(expected)) == expected, 'Candidate preapproval scope mismatch')
    require(api.get('git/ref/heads/' + BRANCH)['object']['sha'] == revision,
            'Candidate branch changed after preapproval')


def prepare(workspace, stage, expected):
    from qualify_codex_1691 import acquire

    owner = validate_runtime()
    require(owner == expected['runtime'], 'Candidate preparation runtime differs from the reviewed scope')
    selected = expected['scope']
    stage.mkdir(mode=0o700, parents=True, exist_ok=False)
    assets = stage / 'archive'
    assets.mkdir()
    profile = read_json(CODEX_PROFILE)
    acquire(profile, assets)
    task_checksums = {}
    for arm in selected['arms']:
        task = stage_task(workspace / '.apm/skills/podman', stage / arm, case=SMOKE_CASE,
                          with_skill=arm == 'with_skill')
        native = configure_openai_task(task, assets, profile)
        task_checksums[arm] = native.checksum
        require(native.config.agent.timeout_sec == PROVIDER_POLICY['agent_seconds_per_arm'],
                'Candidate agent execution timeout changed')
    return {'scope': expected, 'runtime': owner, 'codex': read_json(assets / 'integrity.json'),
            'tasks': task_checksums}


def trial_receipt(job, *, arm, selected, receipt):
    paths = list(job.glob('*/result.json'))
    require(len(paths) == 1, 'Expected one native trial in the selected arm')
    path = paths[0]
    result = read_json(path)
    require(result['exception_info'] is None and result['finished_at']
            and result['agent_info']['version'] == selected['agent']['cli'], 'Native trial failed')
    usage = result.get('agent_result') or {}
    counts = {key: usage.get(key) for key in ('n_input_tokens', 'n_output_tokens', 'n_cache_tokens')}
    require(all(type(counts[key]) is int and counts[key] >= 0 for key in ('n_input_tokens', 'n_output_tokens')),
            'Native usage unavailable')
    require(counts['n_cache_tokens'] is None
            or type(counts['n_cache_tokens']) is int and counts['n_cache_tokens'] >= 0, 'Invalid cache token usage')
    receipt['agent_usage'] = counts
    reward = read_json(path.parent / 'verifier/skill_evaluator_reward.json')
    require(reward['entry_id'] == selected['case'] and reward['has_skill'] is (arm == 'with_skill')
            and reward['judge_contract'] == 'skill-evaluator-judges-v2'
            and reward['score_policy'] == 'skill-evaluator-dimension-mean-v1', 'Native reward identity mismatch')
    judges = {}
    for metric in ('accuracy', 'behavior_check', 'goal_accuracy'):
        detail = reward['details'][metric]
        require(detail['judge_model_used'] == selected['verifier']['model']
                and detail['judge_reasoning_effort'] is None and detail['judge_fallback_used'] is False
                and type(detail['score']) in (int, float) and 0 <= detail['score'] <= 1,
                'Missing or changed judge observation')
        judges[metric] = detail['score']
    receipt.update(state='complete', judge_scores=judges)


def collect_candidate(stage, jobs, selected):
    from skillevaluator.tier3.harbor.collector import collect_harbor_results

    baseline_only = selected['arms'] == ['without_skill']
    collected = collect_harbor_results(
        'podman', ['codex'], stage / 'collected', jobs, expected_cases=1,
        expected_case_ids=[selected['case']], expected_trials=1, n_attempts=1,
        skip_with_skill=baseline_only,
        agent_models={'codex': {'model': selected['agent']['model'], 'source': 'explicit'}},
    )
    agent = collected['agents']['codex']
    conditions = agent['conditions']
    require(set(conditions) == set(JOB_NAMES) and all(
        conditions[arm]['execution_status'] == 'succeeded'
        and conditions[arm]['scored_attempts'] == conditions[arm]['expected_attempts'] == 1
        for arm in selected['arms']
    ), 'Released collector lost a candidate arm')
    if baseline_only:
        skipped = conditions['with_skill']
        require(skipped['execution_status'] == 'skipped' and skipped['scored_attempts'] == 0
                and not agent.get('lift'), 'Baseline-only collection acquired a comparison')


def execute(stage, expected, output, key):
    from skillevaluator.tier3.harbor.runner import (
        _HarborRunCancellation, _run_bounded_harbor_process, build_harbor_run_command,
    )

    # Only the selected provider key enters the Harbor process. All checked-in
    # and retained records refer to the key by placeholder.
    owner = validate_runtime()
    require(owner == expected['runtime'], 'Protected candidate runtime differs from the reviewed scope')
    env = {name: os.environ[name] for name in ('PATH', 'TMPDIR', 'DOCKER_CONFIG', 'COMPOSE_PLUGIN_ROOT')
           if name in os.environ}
    home = stage / 'operator-home'
    home.mkdir(mode=0o700)
    env.update(HOME=str(home), OPENAI_API_KEY=key, PYTHON_DOTENV_DISABLED='1', PYTHONDONTWRITEBYTECODE='1',
               LITELLM_LOCAL_MODEL_COST_MAP='True')
    selected = expected['scope']
    settings = {
        'SKILL_EVAL_LLM_PROVIDER': 'openai', 'LLM_JUDGE_MODEL': selected['verifier']['model'],
        'LLM_JUDGE_FALLBACK_MODELS': '', 'LLM_JUDGE_RETRY_POLICY': PROVIDER_POLICY['judge_policy'],
        'SKILL_EVAL_LLM_MAX_RETRIES': str(PROVIDER_POLICY['judge_transport_retries']),
    }
    env.update(settings)
    judge = {name: '$' + '{' + name + '}' for name in settings}
    judge['SKILL_EVAL_LLM_API_KEY'] = '$' + '{OPENAI_API_KEY}'
    cancellation = _HarborRunCancellation()
    old = {kind: signal.signal(kind, lambda *_: cancellation.requested.set()) for kind in (signal.SIGTERM, signal.SIGINT)}
    deadline = time.monotonic() + PROVIDER_POLICY['inference_seconds']
    evidence = {'context': expected, 'runtime': owner, 'history_eligible': False, 'status': 'incomplete', 'arms': {}}
    jobs = stage / 'jobs'
    try:
        for arm in selected['arms']:
            receipt = {'state': 'started', 'agent_usage': None}
            evidence['arms'][arm] = receipt
            write_json(output, evidence)
            task = stage / arm / 'tasks'
            job_name = JOB_NAMES[arm]
            command = build_harbor_run_command(dataset_path=task, job_name=job_name, jobs_dir=jobs, agent='codex',
                env_mode='aeb-benchmark-docker', n_attempts=1, n_concurrent=1,
                model=selected['agent']['model'], verifier_env=judge)
            remaining = deadline - time.monotonic() - 30
            require(remaining > 0, 'Candidate deadline exhausted')
            process = _run_bounded_harbor_process(command, env=env, cwd=stage, stdin_text=None,
                timeout_seconds=remaining, max_output_bytes=8 * 1024 * 1024, diagnostic_tail_chars=1024,
                secret_values={key}, cancellation=cancellation)
            require(process.returncode == 0 and not process.output_exceeded, 'Native launcher failed')
            job = jobs / job_name
            trial_receipt(job, arm=arm, selected=selected, receipt=receipt)
            trial, = job.glob('*/result.json')
            project = trial.parent.name.lower() + '__env'
            receipt['teardown_complete'] = compose_teardown_complete(project)
            require(receipt['teardown_complete'], 'Native trial left Compose resources')
            if arm == 'with_skill':
                used = receipt['agent_usage']
                if (used['n_input_tokens'] + used['n_output_tokens']
                        > PROVIDER_POLICY['max_observed_agent_tokens_before_next_arm']):
                    evidence['stop_reason'] = 'second_arm_token_threshold'
                    raise ValueError('First-arm agent tokens exceeded the second-arm threshold')
        collect_candidate(stage, jobs, selected)
        evidence['status'] = 'complete'
    except Exception as error:
        category = type(error).__name__
        evidence['failure'] = category if category in (
            'KeyError', 'OSError', 'RuntimeError', 'ValueError', '_HarborRunCancelledError',
            '_HarborRunTimeoutError', 'TimeoutExpired') else 'Exception'
        raise
    finally:
        for kind, handler in old.items():
            signal.signal(kind, handler)
        write_json(output, evidence)


def cleanup(stage, expected, output):
    evidence = read_json(output) if output.is_file() else {
        'context': expected, 'history_eligible': False, 'status': 'incomplete', 'arms': {},
    }
    evidence['teardown'] = 'incomplete'
    try:
        require(evidence['context'] == expected, 'Diagnostic scope changed')
        subprocess.run(['docker', 'info', '--format', '{{.ServerVersion}}'], stdout=subprocess.DEVNULL,
                       timeout=10, check=True)
        for arm in expected['scope']['arms']:
            environment = stage / arm / 'tasks' / SMOKE_CASE / 'environment'
            for trial in (stage / 'jobs' / JOB_NAMES[arm]).glob(SMOKE_CASE + '__*'):
                require(trial.is_dir() and not trial.is_symlink()
                        and re.fullmatch(r'1__[A-Za-z0-9]{1,32}', trial.name), 'Unexpected trial recording path')
                project = trial.name.lower() + '__env'
                selector = 'label=com.docker.compose.project=' + project
                containers = subprocess.check_output(
                    ['docker', 'container', 'ls', '--all', '--quiet', '--filter', selector], text=True, timeout=10).split()
                for container in containers:
                    owner = subprocess.check_output(['docker', 'container', 'inspect', '--format',
                        '{{index .Config.Labels "com.docker.compose.project.working_dir"}}', container],
                        text=True, timeout=10).strip()
                    require(owner == str(environment), 'Compose resource does not belong to the staged task')
                    subprocess.run(['docker', 'container', 'rm', '--force', container], stdout=subprocess.DEVNULL,
                                   timeout=15, check=True)
                networks = subprocess.check_output(
                    ['docker', 'network', 'ls', '--quiet', '--filter', selector], text=True, timeout=10).split()
                for network in networks:
                    subprocess.run(['docker', 'network', 'rm', network], stdout=subprocess.DEVNULL,
                                   timeout=15, check=True)
                require(compose_teardown_complete(project), 'Candidate cleanup could not be confirmed')
        evidence['teardown'] = 'complete'
    except Exception:
        evidence['status'] = 'incomplete'
        raise
    finally:
        write_json(output, evidence)



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('context', 'prepare', 'guard', 'run', 'cleanup'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stage', type=Path)
    parser.add_argument('--preparation', type=Path)
    parser.add_argument('--authorization', type=Path)
    args = parser.parse_args()
    workspace = Path.cwd().resolve()
    require(args.output.is_absolute() and args.output.resolve() == args.output
            and not args.output.is_relative_to(workspace) and (args.command == 'cleanup' or not args.output.exists()),
            'Use a fresh operational record outside the checkout')
    env = os.environ
    present = {key for key in PROVIDER_CREDENTIALS if env.get(key)}
    if args.command == 'run':
        require(present == {'OPENAI_API_KEY'}, 'The protected OpenAI credential is required')
    else:
        require(not present, 'Candidate authorization and setup run without inference credentials')
    value = reviewed_scope(workspace, env, read_json(Path(env['GITHUB_EVENT_PATH']))['inputs'])
    if args.command == 'context':
        selected = value['scope']
        cost = value['cost_estimate']
        arms = ', '.join(selected['arms'])
        summary(['## Candidate compatibility smoke', '',
                 f'Revision {selected["revision"]}. Podman case {selected["case"]}. One trial in each selected arm ({arms}).',
                 f'Runtime {value["runtime"]["producer_profile"]}. Patch SHA-256 {value["runtime"]["patch_sha256"]}.',
                 'Codex 0.171.0 uses gpt-6.2-sol at High. The default verifier uses gpt-6.2-sol with reasoning omitted.',
                 'The protected evaluation has a 15-minute deadline. Judge transport retries are disabled.',
                 *(['The second arm requires recorded first-arm usage within the declared threshold.']
                   if selected['planned_trials'] == 2 else []),
                 f'Estimated cost is ${cost["usd"]:.2f} at the standard short-context rates '
                 f'for {cost["input_tokens"]:,} input and {cost["output_tokens"]:,} output tokens. Billing varies.',
                 'The operational receipt is outside canonical history.'])
    if args.command in ('prepare', 'guard', 'run', 'cleanup'):
        require(args.stage.is_absolute() and args.stage.resolve() == args.stage
                and not args.stage.is_relative_to(workspace), 'Use a confined candidate staging path')
    if args.command == 'cleanup':
        cleanup(args.stage, value, args.output)
        return
    if args.command == 'prepare':
        write_json(args.output, prepare(workspace, args.stage, value))
        return
    if args.command == 'guard':
        guard(pages.GitHub(), value)
    if args.command in ('guard', 'run'):
        from harbor.models.task.task import Task

        preparation = read_json(args.preparation)
        require(preparation['scope'] == value and preparation['runtime'] == value['runtime'] == validate_runtime(),
                'Prepared scope or runtime changed')
        for arm in value['scope']['arms']:
            staged, = (args.stage / arm / 'tasks').iterdir()
            require(not staged.is_symlink() and Task(staged).checksum == preparation['tasks'][arm],
                    'Staged candidate task changed')
    if args.command == 'run':
        require(read_json(args.authorization) == value, 'Final approval scope changed')
        execute(args.stage, value, args.output, env['OPENAI_API_KEY'])
        return
    write_json(args.output, value)
    outputs(execute='true')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Podman compatibility step failed. Inspect the bounded operational receipt.')
