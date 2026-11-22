"""Measure the released Codex process against the existing loopback fixture."""
import argparse
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

from codex_pilot_contract import ROOT, configuration, model_arguments
from codex_pilot_runtime import usage_record
from evaluation_campaign import no_credentials, revision
from evaluation_campaign_core import require
from evaluation_runtime import read_profile
import skill_reports as reports


SELECTOR = ROOT / '.github/evals/campaigns/codex-1691.json'


def acquire(runtime, destination):
    archive = destination / 'codex.tar.gz'
    subprocess.run(['curl', '--fail', '--silent', '--show-error', '--location',
        '--proto', '=https', '--proto-redir', '=https', '--connect-timeout', '10',
        '--max-time', '180', '--output', str(archive),
        runtime['release_url'].replace('/tag/', '/download/') + '/codex-package-x86_64-unknown-linux-musl.tar.gz'], check=True)
    check_digest(archive, runtime['cli_archive_sha256'])
    members = {'bin/codex': runtime['cli_executable_sha256'], **runtime['helper_sha256']}
    subprocess.run(['tar', '-xzf', str(archive), '-C', str(destination), *members], check=True)
    for name, digest in members.items():
        check_digest(destination / name, digest)
    binary = destination / 'bin/codex'
    version = subprocess.check_output([binary, '--version'], text=True).strip()
    require(version == 'codex-cli ' + runtime['cli'], 'Unexpected CLI version')
    reports.write_json(destination / 'integrity.json',
        {'version': version, 'archive_sha256': runtime['cli_archive_sha256'], 'verified_members': members})
    return binary


def check_digest(path, expected):
    from hashlib import file_digest
    require(path.is_file() and not path.is_symlink(), 'Invalid release asset member')
    with path.open('rb') as stream:
        require(file_digest(stream, 'sha256').hexdigest() == expected, 'Release asset digest mismatch')


def probe(runtime, binary, root, scenario, *, selected_model=None):
    import toml
    root.mkdir()
    home = root / 'home'
    home.mkdir(mode=0o700)
    config = configuration('http://127.0.0.1:8765/v1', runtime=runtime)
    config['sandbox_mode'] = 'read-only'
    (home / 'config.toml').write_text(toml.dumps(config))
    observed = root / 'request.json'
    command = base64.b64encode(json.dumps(['printf fixture-tool-ok']).encode()).decode()
    with socket.socket() as preflight:
        require(preflight.connect_ex(('127.0.0.1', 8765)) != 0, 'Fixture port already in use')
    with subprocess.Popen([sys.executable, ROOT / '.github/scripts/codex_pilot_stub.py',
                          observed, scenario, 'Zml4dHVyZQ==', command]) as server:
        try:
            for _ in range(100):
                require(server.poll() is None, 'Fixture process exited')
                try:
                    with urllib.request.urlopen('http://127.0.0.1:8765/', timeout=.2):
                        pass
                except urllib.error.HTTPError as error:
                    require(error.code == 501, 'Unexpected fixture readiness response')
                    break
                except urllib.error.URLError:
                    time.sleep(.05)
            else:
                raise ValueError('Fixture did not start')
            process = subprocess.run([binary, 'exec', '--strict-config', '--sandbox', 'read-only',
                '--skip-git-repo-check', '--cd', root, '--json', *model_arguments(runtime, runtime['model'] if selected_model is None else selected_model),
                '--', 'Print the fixture result.'],
                env={'PATH': os.defpath, 'HOME': str(home), 'CODEX_HOME': str(home),
                     'OPENAI_API_KEY': 'pilot-not-a-credential'},
                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=45)
        finally:
            server.terminate()
            server.wait(timeout=5)
    (root / 'events.jsonl').write_text(process.stdout)
    (root / 'stderr.txt').write_text(process.stderr)
    request = reports.read_json(observed)
    require(request['model'] == runtime['model'] and request['reasoning']['effort'] == 'high'
            and request['path'] == '/v1/responses' and request['authorization_matches_sentinel'],
            'Fixture request identity drift')
    events = [json.loads(line) for line in process.stdout.splitlines() if line != 'Reading additional input from stdin...']
    final = [event['usage'] for event in events if event['type'] == 'turn.completed']
    if scenario == 'provider-refusal':
        require(process.returncode != 0 and request['requests'] == 1 and not final
                and any(event['type'] == 'turn.failed' for event in events), 'Wrong refusal behavior')
    else:
        require(process.returncode == 0 and request['requests'] == 2 and len(final) == 1,
                'Compatibility probe failed')
    return {'model': request['model'], 'reasoning_effort': request['reasoning']['effort'],
            'request_count': request['requests'], 'requests': request.get('request_observations'),
            'request_keys': request['request_keys'],
            'tools': request['tools'], 'service_tier': request['service_tier'],
            'exit': process.returncode, 'usage': final[0] if final else None,
            'event_types': sorted({e['type'] + ('/' + e['item']['type'] if 'item' in e else '') for e in events}),
            'command': next((e['item'] for e in events if e.get('type') == 'item.completed'
                             and e['item']['type'] == 'command_execution'), None),
            'fixture_stopped': server.poll() is not None}


def check_pricing(runtime):
    from math import isclose
    checks = {}
    for label, count, expected in (('short', 300, .000735), ('boundary', 272000, .544135),
                                   ('cumulative_long_upper_bound', 272001, 1.088124)):
        record = usage_record({'trial_name': label, 'agent_result': {
            'n_input_tokens': count, 'n_cache_tokens': 100, 'n_output_tokens': 30,
            'metadata': {'n_cache_write_input_tokens': 50}}}, probe=True, runtime=runtime)
        require(isclose(record['estimated_usd'], expected), 'Pricing check failed: ' + label)
        checks[label] = record
    unavailable = usage_record({'trial_name': 'missing', 'agent_result': {'n_input_tokens': 300}},
                               probe=True, runtime=runtime)
    require(unavailable['estimated_usd'] is None, 'Missing usage was priced')
    return {**checks, 'missing': unavailable}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    no_credentials()
    root = args.output.resolve()
    root.mkdir()
    runtime = read_profile(SELECTOR)['resolved']
    binary = acquire(runtime, root)
    summary = {'revision': revision(), 'inference': False,
               'compatibility': probe(read_profile(ROOT / '.github/evals/campaigns/codex-090-sol62.json')['resolved'],
                                      binary, root / 'compatibility', 'compatibility'),
               'refusal': probe(runtime, binary, root / 'refusal', 'provider-refusal'),
               'pricing_checks': check_pricing(runtime)}
    reports.write_json(root / 'qualification.json', summary)


if __name__ == '__main__':
    main()
