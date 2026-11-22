"""Pinned Codex image preparation shared by historical and campaign entry points."""
import shutil
from codex_pilot_contract import ROOT, PROFILE as P
from evaluation_runtime import CODEX_OBSERVATION_PROFILES


def prepare_cli(task, runtime=None):
    selected = P if runtime is None else runtime
    (task / 'environment/docker-compose.yaml').write_text(
        'services:\n  main:\n    cap_drop: [ALL]\n    security_opt: [no-new-privileges:true]\n    pids_limit: 256\n')
    for name in ('codex_pilot_stub.py', 'codex_pilot_probe.py'):
        shutil.copyfile(ROOT / '.github/scripts' / name, task / 'environment/build' / name)
    # Verified artifacts are embedded before entering the protected job.
    with (task / 'environment/Dockerfile').open('a') as dockerfile:
        dockerfile.write('RUN mkdir /opt/codex && curl --fail --location --silent --show-error '
            '--proto "=https" --proto-redir "=https" '
            + ('--connect-timeout 10 --max-time 180 --retry 1 --retry-max-time 190 ' if selected['cli'] in ('0.155.1', '0.169.1', '0.171.0') else '') +
            f'https://github.com/openai/codex/releases/download/rust-v{selected["cli"]}/codex-package-x86_64-unknown-linux-musl.tar.gz '
            '-o /opt/codex.tar.gz && '
            f"echo '{selected['cli_archive_sha256']}  /opt/codex.tar.gz' | sha256sum -c --strict && "
            'tar -xzf /opt/codex.tar.gz -C /opt/codex && '
            f"echo '{selected['cli_executable_sha256']}  /opt/codex/bin/codex' | sha256sum -c --strict && "
            + ''.join(f"echo '{digest}  /opt/codex/{member}' | sha256sum -c --strict && "
                    for member, digest in (selected['helper_sha256'].items() if selected['cli'] in ('0.155.1', '0.169.1', '0.171.0') else ())) +
            'rm /opt/codex.tar.gz\n'
            'COPY build/codex_pilot_stub.py build/codex_pilot_probe.py /opt/pilot/\n'
            'RUN mkdir -p /logs/agent /logs/verifier /logs/artifacts /installed-agent && chmod 777 /logs/agent /logs/artifacts && chmod 700 /logs/verifier && '
            'chmod -R a-w /workspace/input /opt/codex /opt/pilot && '
            'chmod 755 /home/agent && mkdir -p /home/agent/.codex-pilot && '
            'chown agent:agent /home/agent/.codex-pilot && chmod 700 /home/agent/.codex-pilot\n'
            'USER agent\n')


def usage_source(runtime):
    version = runtime['cli']
    return 'codex-0.167-exec-json' if version.startswith('0.167.') else f'codex-{version}-exec-json'


def usage_record(value, *, probe=False, runtime=None):
    import os
    selected = P if runtime is None else runtime
    prices = selected['prices_per_million']
    agent = value.get('agent_result') or {}
    counts = {key: agent.get(key) for key in ('n_input_tokens', 'n_cache_tokens', 'n_output_tokens')}
    metadata = agent.get('metadata') or {}
    candidate = selected['cli'] in ('0.169.1', '0.171.0')
    write_key = ('cache_write_input_count' if selected['id'] in CODEX_OBSERVATION_PROFILES
                 else 'n_cache_write_input_tokens')
    writes = metadata.get(write_key) if candidate else 0
    if candidate:
        counts['n_cache_write_input_tokens'] = writes
    valid = all(type(v) is int and v >= 0 for v in counts.values())
    cost = None
    if valid:
        i, c, o = (counts[k] for k in ('n_input_tokens', 'n_cache_tokens', 'n_output_tokens'))
        if c + writes > i: raise ValueError('Contradictory provider usage')
        # Cumulative counts cannot identify per-request long-context billing.
        # Conservatively apply its premium once cumulative input exceeds 272K.
        prefill, sample = (2, 1.5) if i > 272000 else (1, 1)
        input_cost = (i - c - writes) * prices['input'] + c * prices['cached_input']
        if 'cache_write_12h' in prices and not candidate:
            input_cost = (i - c) * prices['cache_write_12h'] + c * prices['cached_input']
        if candidate:
            input_cost += writes * prices['cache_write_30m']
        cost = (input_cost * prefill + o * prices['output'] * sample) / 1_000_000
    complete = metadata.get('execution_complete', True)
    return {'trial': value['trial_name'], 'completeness': 'complete_turn' if valid and complete else 'partial' if valid else 'unavailable',
            'provenance': usage_source(selected) if valid else None, **counts, 'estimated_usd': cost if complete else None,
            **({'observed_estimated_usd': cost} if not complete else {}),
            **({'estimate_basis': 'standard rates; 30-minute cache write assumption; long-context upper bound from cumulative input'
                if valid else None} if candidate else
               {'estimate_basis': 'unclassified input at 12-hour cache-write rate; cumulative long-context upper bound'}
               if 'cache_write_12h' in prices and valid else {}),
            'billing': 'stub protocol; no model usage or billing' if probe or os.environ.get('AEB_PILOT_PROBE') == '1' else 'provider-reported tokens; estimate, not invoice'}
