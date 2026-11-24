"""Run the released isolated Podman benchmark with two non-forwarding responders."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import threading
import urllib.request

MODEL = 'gpt-6.2-sol'
JUDGE_URL = 'https://api.openai.com/v1/chat/completions'
SENTINEL = 'podman-judge-fixture-not-a-credential'
CASE = '5'


def judge_response(payload):
    prompt = payload['messages'][0]['content']
    if '"criteria" object' in prompt:
        return 'accuracy', {'criteria': {
            'ACTION_CORRECT': True, 'FACTUALLY_ACCURATE': True, 'TASK_ADDRESSED': True,
            'ACTIONABLE': True, 'FORMAT_FOLLOWED': False,
        }, 'reason': 'Fixed fixture'}
    if 'EXPECTED BEHAVIORS:' in prompt:
        count = int(re.search(r'"results" must hold exactly (\d+) entries', prompt)[1])
        return 'behavior_check', {'results': [{'step': step, 'passed': True, 'reason': 'Fixed fixture'}
                                               for step in range(1, count + 1)], 'summary': 'Fixed fixture'}
    return 'goal_accuracy', {'achieved': True, 'user_goal': 'Fixture', 'end_state': 'Fixture',
                             'reason': 'Fixed fixture'}


def verifier():
    """Keep synthetic judge credentials and request payloads inside the verifier."""
    requests = []

    class Judge(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            size = int(self.headers.get('Content-Length', '0'))
            if (self.path != '/v1/chat/completions' or not 0 < size <= 1_000_000
                    or self.headers.get('Authorization') != 'Bearer ' + SENTINEL):
                self.send_error(400)
                return
            payload = json.loads(self.rfile.read(size))
            metric, reply = judge_response(payload)
            expected = (payload.get('model') == MODEL and 'max_completion_tokens' in payload
                        and 'reasoning_effort' not in payload and 'temperature' not in payload)
            requests.append({'metric': metric, 'model': payload.get('model'),
                             'path': self.path, 'max_completion_tokens': 'max_completion_tokens' in payload,
                             'reasoning_present': 'reasoning_effort' in payload,
                             'temperature_present': 'temperature' in payload, 'request_policy_matches': expected})
            if not expected:
                self.send_error(400)
                return
            body = json.dumps({'choices': [{'message': {'content': json.dumps(reply)}, 'finish_reason': 'stop'}],
                               'usage': {'prompt_tokens': 19, 'completion_tokens': 7, 'total_tokens': 26}}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    with ThreadingHTTPServer(('127.0.0.1', 0), Judge) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        local_url = f'http://127.0.0.1:{server.server_port}/v1/chat/completions'
        local = urllib.request.build_opener(urllib.request.ProxyHandler({}))

        class FixtureHTTPS(urllib.request.HTTPSHandler):
            def https_open(self, request):
                if request.full_url != JUDGE_URL or request.get_method() != 'POST':
                    raise ValueError('Unexpected verifier endpoint')
                return local.open(urllib.request.Request(local_url, data=request.data, headers=dict(request.headers)),
                                  timeout=request.timeout)

        try:
            tests = Path(os.environ.get('HARBOR_TESTS_DIR', '/tests'))
            path = os.environ['PATH']
            os.environ.clear()
            os.environ.update(PATH=path, HARBOR_ATIF_PATH='/logs/agent/trajectory.json',
                              SKILL_EVAL_LLM_PROVIDER='openai', LLM_JUDGE_MODEL=MODEL,
                              SKILL_EVAL_LLM_API_KEY=SENTINEL, LLM_JUDGE_RETRY_POLICY='strict',
                              PYTHON_DOTENV_DISABLED='1')
            urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({}), FixtureHTTPS()))
            try:
                runpy.run_path(str(tests / 'skill_evaluator/eval.py'), run_name='__main__')
            except SystemExit as exit_status:
                result = exit_status.code
            else:
                result = 0
        finally:
            server.shutdown()
            thread.join()
    logs = Path('/logs/verifier')
    (logs / 'judge-requests.json').write_text(json.dumps(requests))
    shutil.copy2('/opt/reviewed/request.json', logs / 'codex-requests.json')
    return result


def run(root, present):
    from skillevaluator.tier3.harbor.adapter import generate_harbor_tasks
    from skillevaluator.tier3.harbor.runner import build_harbor_run_command

    from qualify_benchmark_101 import ROOT
    from qualify_benchmark_codex import add_offline_assets
    from skill_reports import POLICY, benchmark_options, read_json, require, write_json

    arm = 'with' if present else 'without'
    work = root / arm
    options = benchmark_options('podman')
    tasks = generate_harbor_tasks(ROOT / '.apm/skills/podman', work / 'generated', with_skill=present,
                                  workspace_mode=options['workspace_mode'], grading_mode=options['grading_mode'],
                                  custom_dockerfile_mode='disabled')
    selected, = (task for task in tasks if str(read_json(task / 'tests/entry.json')['id']) == CASE)
    staged = work / 'tasks'
    staged.mkdir()
    task = selected.rename(staged / selected.name)
    descriptor = task / 'task.toml'
    source = descriptor.read_text()
    require('network_mode = "public"' in source, 'Unexpected released default networking')
    require(source.count('[agent]') == 1, 'Unexpected released agent descriptor')
    descriptor.write_text(source.replace('network_mode = "public"', 'network_mode = "no-network"')
                          .replace('[agent]', '[agent]\nuser = "agent"'))
    image = task / 'environment'
    # The isolated default image does not carry npm. The normal Codex
    # installer provisions it, which this fixture replaces.
    with (image / 'Dockerfile').open('a') as build:
        build.write('\nRUN apt-get -o Acquire::Retries=3 update && '
                    'apt-get -o Acquire::Retries=3 install -y --no-install-recommends nodejs npm '
                    '&& rm -rf /var/lib/apt/lists/*\n'
                    'RUN useradd --create-home --uid 1000 agent && chown agent:agent /workspace/output\n')
    add_offline_assets(image)
    shutil.copy2(Path(__file__), image / 'reviewed/podman_fixture.py')
    verify = task / 'tests/test.sh'
    require(verify.read_text().splitlines()[-1] == 'python3 -I "${evaluator_dir}/eval.py"',
            'Released default verifier entry point changed')
    verify.write_text('#!/bin/sh\nexec python3 -I /opt/reviewed/podman_fixture.py --verify\n')
    verify.chmod(0o755)
    request = work / 'fixture.json'
    command = ('test -r /workspace/skills/podman/SKILL.md && head -n 8 /workspace/skills/podman/SKILL.md'
               if present else 'test ! -e /workspace/skills/podman/SKILL.md && printf baseline')
    write_json(request, {'scenario': 'benchmark-priced', 'commands': [command]})
    job_name = 'podman-codex-' + arm
    argv = build_harbor_run_command(dataset_path=staged, job_name=job_name, jobs_dir=root / 'jobs',
                                    agent='codex', model=MODEL, env_mode='aeb-benchmark-docker', n_concurrent=1)
    index = argv.index('--agent') + 1
    require(argv[index] == 'aeb_gh_fixture.benchmark_codex:BenchmarkCodex' and MODEL == POLICY['model']
            and 'reasoning_effort="high"' in argv, 'Unexpected isolated dispatch')
    argv[index] = 'qualify_benchmark_codex:OfflinePodmanCodex'
    env = dict(os.environ, PYTHONPATH=str(ROOT / '.github/scripts'), BENCHMARK_CODEX_FIXTURE=str(request))
    subprocess.run(argv, env=env, timeout=480, check=True)
    result_path, = (root / 'jobs' / job_name).glob('*/result.json')
    result = read_json(result_path)
    exception = result.get('exception_info')
    if exception is not None:
        category = exception['exception_type']
        raise ValueError(f'Podman native trial failed: {category}')
    trial = result_path.parent
    container = read_json(trial / 'fixture-container.json')['id']
    require(subprocess.run(['docker', 'container', 'inspect', container], capture_output=True).returncode != 0,
            'Podman trial container survived cleanup')
    verify_dir = trial / 'verifier'
    reward = read_json(verify_dir / 'skill_evaluator_reward.json')
    requests = read_json(verify_dir / 'judge-requests.json')
    codex = read_json(verify_dir / 'codex-requests.json')['request_observations']
    require(set(row['metric'] for row in requests) == {'accuracy', 'behavior_check', 'goal_accuracy'}
            and len(requests) == 3 and all(row['request_policy_matches'] for row in requests),
            'Unexpected default judge requests')
    require(len(codex) == 2 and all(row['model'] == MODEL and row['reasoning']['effort'] == 'high'
            and row['path'] == '/v1/responses' and row['authorization_matches_sentinel'] for row in codex),
            'Unexpected Codex requests')
    require(reward.get('accuracy') == 0.8 and result['agent_info']['version'] == POLICY['codex'],
            'Native accuracy or Codex identity changed')
    trajectory = read_json(trial / 'agent/trajectory.json')
    require(any(call.get('function_name') == 'exec_command' and command in str(call.get('arguments'))
                for step in trajectory['steps'] for call in step.get('tool_calls', [])),
            'Native command absent from collected trajectory')
    return {'codex_requests': len(codex), 'judge_requests': requests, 'accuracy': reward['accuracy'],
            'skill_execution': reward.get('skill_execution'), 'cleanup': True}


def main(output):
    from skillevaluator.tier3.harbor.collector import collect_harbor_results

    from qualify_benchmark_101 import ROOT, fixture_owner
    from skill_reports import require, write_json

    require(not any(os.getenv(key) for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'NVIDIA_API_KEY',
                'SKILL_EVAL_LLM_API_KEY', 'CODEX_AUTH_JSON_PATH', 'CODEX_FORCE_AUTH_JSON', 'CODEX_API_KEY')),
            'Native Podman fixture requires a credential-free environment')
    root = output.absolute()
    require(root.resolve() == root and not root.is_relative_to(ROOT), 'Unsafe native fixture output')
    root.mkdir(exist_ok=False)
    with fixture_owner() as versions:
        arms = {arm: run(root, present) for arm, present in (('with_skill', True), ('without_skill', False))}
        collected = collect_harbor_results('podman', ['codex'], root / 'collected', root / 'jobs', expected_cases=1,
            expected_case_ids=[CASE], expected_trials=1, n_attempts=1,
            agent_models={'codex': {'model': MODEL, 'source': 'fixture'}})
        conditions = collected['agents']['codex']['conditions']
        require(set(conditions) == set(arms) and all(c['execution_status'] == 'succeeded'
                and c['scored_attempts'] == c['expected_attempts'] == 1 for c in conditions.values()),
                'Native collector lost a Podman arm')
    write_json(root / 'qualification.json', {'runtime': versions, 'case': CASE, 'workspace_mode': 'isolated',
        'grading_mode': 'default', 'inference': False, 'arms': arms, 'collector': conditions})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    options = parser.add_mutually_exclusive_group(required=True)
    options.add_argument('--verify', action='store_true')
    options.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.verify:
        raise SystemExit(verifier())
    main(args.output)
