"""Verify a released observer CLI against the existing non-forwarding provider."""
import argparse
import base64
from contextlib import contextmanager
import json
import os
from pathlib import Path
from queue import Empty, Queue
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
from threading import Thread
import time
from types import SimpleNamespace

import toml

from codex_pilot_contract import MODEL_CATALOG, ROOT, configuration, model_arguments
from evaluation_campaign import no_credentials, revision
from evaluation_campaign_core import require
from evaluation_codex import exec_trajectory
from harbor.agents.installed.codex import Codex
from qualify_codex_1691 import acquire
from skill_reports import read_json, write_json


PROFILE = ROOT / '.github/evals/codex-execution-1710.json'
ENDPOINT = 'http://127.0.0.1:8765/v1'
TEST_KEY = 'pilot-not-a-credential'


@contextmanager
def provider(root, scenario, commands):
    request = root / 'request.json'
    encoded = base64.b64encode(json.dumps(commands).encode()).decode()
    with socket.socket() as preflight:
        require(preflight.connect_ex(('127.0.0.1', 8765)) != 0, 'Fixture port already in use')
    with subprocess.Popen([sys.executable, '-I', ROOT / '.github/scripts/codex_pilot_stub.py',
                           request, scenario, 'Zml4dHVyZQ==', encoded], env={'PATH': os.defpath}) as server:
        try:
            for _ in range(100):
                require(server.poll() is None, 'Controlled endpoint exited')
                with socket.socket() as wait:
                    if wait.connect_ex(('127.0.0.1', 8765)) == 0:
                        break
                time.sleep(.05)
            else:
                raise ValueError('Controlled endpoint did not start')
            yield request
        finally:
            server.terminate()
            server.wait(timeout=5)
    require(server.poll() is not None, 'Controlled endpoint survived cleanup')


def config(root, runtime, *, named_workspace=False):
    home = root / 'home'
    home.mkdir()
    # Keep the existing observation model and feature choices. This fixture
    # exercises the CLI sandbox, in addition to the deployed external boundary.
    settings = configuration(ENDPOINT, runtime=runtime, catalog_path=ROOT / MODEL_CATALOG)
    if named_workspace:
        # Built-in workspace permissions also allow generic temporary-folder writes.
        # Keep the test independent of where the runner puts the two workspaces.
        settings.pop('sandbox_mode')
        settings['default_permissions'] = 'fixture-workspace'
        settings['permissions'] = {'fixture-workspace': {
            'extends': ':workspace', 'filesystem': {':slash_tmp': 'read', ':tmpdir': 'read'},
        }}
    else:
        settings['sandbox_mode'] = 'workspace-write'
    settings.update(analytics={'enabled': False})
    (home / 'config.toml').write_text(toml.dumps(settings))
    return {'PATH': os.defpath, 'HOME': str(home), 'CODEX_HOME': str(home), 'OPENAI_API_KEY': TEST_KEY}


def verify_requests(path, runtime, count):
    request = read_json(path)
    require(request['requests'] == count, 'Wrong number of requests')
    for row in request.get('request_observations', [request]):
        require(row['model'] == runtime['model'] and row['reasoning']['effort'] == runtime['reasoning_effort']
                and row['path'] == '/v1/responses' and row['authorization_matches_sentinel'],
                'Outgoing provider identity drift')
    return {'count': count, 'model': request['model'], 'effort': request['reasoning']['effort']}


def run_exec(binary, root, runtime, output, scenario):
    workspace = root / 'workspace'
    workspace.mkdir()
    environment = config(root, runtime)
    patch = {'tool': 'apply_patch', 'input': '*** Begin Patch\n*** Add File: edits.txt\n+fixture edit\n*** End Patch',
             'expect_failure': False}
    commands = ['printf fixture-command-ok', patch] if scenario == 'priced-success' else [':']
    argv = [binary, 'exec', '--strict-config', '--sandbox', 'workspace-write', '--skip-git-repo-check',
            '--cd', workspace, '--json', *model_arguments(runtime, runtime['model']), '--', 'Run fixture tools.']
    with provider(root, scenario, commands) as request:
        with output.open('w') as stream, subprocess.Popen(
                argv, env=environment, cwd=workspace, stdin=subprocess.DEVNULL, stdout=stream,
                stderr=subprocess.PIPE, text=True, start_new_session=True) as native:
            try:
                if scenario == 'interruption':
                    deadline = time.monotonic() + 35
                    while 'item.started' not in output.read_text() and native.poll() is None:
                        require(time.monotonic() < deadline, 'Interrupted tool did not start')
                        time.sleep(.05)
                    native.send_signal(signal.SIGINT)
                _, diagnostic = native.communicate(timeout=40)
            finally:
                if native.poll() is None:
                    os.killpg(native.pid, signal.SIGKILL)
                    native.wait(timeout=5)
        raw = output.read_text()
        events = [json.loads(line) for line in raw.splitlines()
                  if line != 'Reading additional input from stdin...']
        terminal = [event['usage'] for event in events if event['type'] == 'turn.completed']
        if scenario == 'interruption':
            require(any(e['type'] == 'item.started' for e in events) and not terminal
                    and native.returncode != 0, 'Interruption did not retain a partial turn')
            result = {'requests': verify_requests(request, runtime, 1), 'execution': 'interrupted',
                      'usage': None, 'returncode': native.returncode}
        else:
            require(native.returncode == 0, 'Native CLI exit: ' + diagnostic)
            require((workspace / 'edits.txt').read_text() == 'fixture edit\n', 'Native edit bytes differ')
            # Exercise the existing exec-JSON reader under its observation
            # grammar while preserving the actual released agent version.
            adapter = SimpleNamespace(profile=dict(runtime, id='codex-1691-observation-v1'),
                                      task=SimpleNamespace(diagnostic_observation=True),
                                      model_name=runtime['model'])
            adapter._convert_event_to_step = Codex._convert_event_to_step.__get__(adapter)
            trace = exec_trajectory(raw, adapter, diagnostics=diagnostic)
            require(trace.agent.version == runtime['cli'], 'Trajectory lost the released CLI version')
            actions = [call.function_name for step in trace.steps for call in step.tool_calls or []]
            require(actions == ['exec_command', 'file_change'], 'Native command or edit missing')
            counts, = terminal
            expect = {'input_tokens': 300, 'cached_input_tokens': 100,
                      'cache_write_input_tokens': 50, 'output_tokens': 30}
            require({key: counts.get(key) for key in expect} == expect, 'Cumulative provider usage differs')
            result = {'requests': verify_requests(request, runtime, 2), 'actions': actions, 'usage': expect}
    return dict(result, cleanup=True)


def working_directory(binary, root, runtime, output):
    before = root / 'before'
    after = root / 'after'
    before.mkdir()
    (after / '.git').mkdir(parents=True)
    protected = after / '.git/config'
    protected.write_text('original\n')
    command = ('printf ordinary > ordinary.txt; result=$?; '
               'if { printf changed > .git/config; } 2>/dev/null; then git=allowed; else git=denied; fi; '
               + 'if { printf old > ' + shlex.quote(str(before / 'old.txt'))
               + '; } 2>/dev/null; then old=allowed; else old=denied; fi; '
               'printf "cwd-policy:%s:%s:%s\\n" "$result" "$git" "$old"')
    environment = config(root, runtime, named_workspace=True)
    with provider(root, 'compatibility', [command]) as request, subprocess.Popen(
            [binary, 'app-server', '--strict-config'], cwd=before, env=environment,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1) as server:
        events = []
        next_id = 0

        messages = Queue()

        def receive():
            for line in server.stdout:
                messages.put(line)
            messages.put(None)

        reader = Thread(target=receive)
        reader.start()

        def read_for(matches):
            deadline = time.monotonic() + 40
            try:
                while time.monotonic() < deadline:
                    line = messages.get(timeout=max(deadline - time.monotonic(), .01))
                    require(line is not None, 'App server ended early')
                    event = json.loads(line)
                    events.append(event)
                    if matches(event):
                        return event
            except Empty:
                pass
            raise ValueError('Timed out waiting for app-server event')

        def rpc(method, params):
            nonlocal next_id
            next_id += 1
            server.stdin.write(json.dumps({'id': next_id, 'method': method, 'params': params}) + '\n')
            server.stdin.flush()
            response = read_for(lambda event: event.get('id') == next_id)
            require('result' in response, f'{method} failed: {response.get("error")}')
            return response['result']

        try:
            rpc('initialize', {'clientInfo': {'name': 'aeb-qualification', 'version': '1'},
                               'capabilities': {'experimentalApi': True}})
            server.stdin.write('{"method":"initialized"}\n')
            server.stdin.flush()
            thread = rpc('thread/start', {'cwd': str(before), 'permissions': 'fixture-workspace',
                                          'ephemeral': True, 'model': runtime['model']})
            identifier = thread['thread']['id']
            require(thread['activePermissionProfile']['id'] == 'fixture-workspace', 'Expected named workspace profile')
            rpc('thread/settings/update', {'threadId': identifier, 'cwd': str(after)})
            turn = rpc('turn/start', {'threadId': identifier, 'input': [{'type': 'text', 'text': 'Run the fixture.'}]})
            completed = read_for(lambda event: event.get('method') == 'turn/completed'
                                 and event.get('params', {}).get('turn', {}).get('id') == turn['turn']['id'])
            require(completed['params']['turn']['status'] == 'completed', 'Working-directory turn failed')
        finally:
            output.write_text(''.join(json.dumps(event) + '\n' for event in events))
            server.terminate()
            server.wait(timeout=5)
            reader.join(timeout=5)
        require((after / 'ordinary.txt').read_text() == 'ordinary' and protected.read_text() == 'original\n'
                and not (before / 'old.txt').exists(), 'Working-directory update changed filesystem permissions')
        return {'requests': verify_requests(request, runtime, 2), 'new_working_directory_write': True,
                'git_metadata_protected': True, 'previous_working_directory_protected': True, 'cleanup': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    no_credentials()
    output = args.output.resolve()
    output.mkdir()
    runtime = read_json(PROFILE)
    binary = acquire(runtime, output)
    for name, probe in (
        ('exec', lambda root, log: run_exec(binary, root, runtime, log, 'priced-success')),
        ('working-directory', lambda root, log: working_directory(binary, root, runtime, log)),
        ('interrupt', lambda root, log: run_exec(binary, root, runtime, log, 'interruption')),
    ):
        with tempfile.TemporaryDirectory(prefix='codex-1710-') as temp:
            receipt = probe(Path(temp), output / (name + '.jsonl'))
        write_json(output / (name + '.json'), {'revision': revision(), 'inference': False, **receipt})
        print(name + ' passed', flush=True)


if __name__ == '__main__':
    main()
