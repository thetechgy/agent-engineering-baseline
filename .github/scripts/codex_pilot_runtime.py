"""Pinned Codex image preparation shared by historical and campaign entry points."""
import shutil
from codex_pilot_contract import ROOT, PROFILE as P


def prepare_cli(task):
    (task / 'environment/docker-compose.yaml').write_text(
        'services:\n  main:\n    cap_drop: [ALL]\n    security_opt: [no-new-privileges:true]\n    pids_limit: 256\n')
    for name in ('codex_pilot_stub.py', 'codex_pilot_probe.py'):
        shutil.copyfile(ROOT / '.github/scripts' / name, task / 'environment/build' / name)
    # Verified artifacts are embedded before entering the protected job.
    with (task / 'environment/Dockerfile').open('a') as dockerfile:
        dockerfile.write('RUN mkdir /opt/codex && curl --fail --location --silent --show-error '
            '--proto "=https" --proto-redir "=https" '
            'https://github.com/openai/codex/releases/download/rust-v0.167.0/codex-package-x86_64-unknown-linux-musl.tar.gz '
            '-o /opt/codex.tar.gz && '
            f"echo '{P['cli_archive_sha256']}  /opt/codex.tar.gz' | sha256sum -c --strict && "
            'tar -xzf /opt/codex.tar.gz -C /opt/codex && '
            f"echo '{P['cli_executable_sha256']}  /opt/codex/bin/codex' | sha256sum -c --strict && "
            'rm /opt/codex.tar.gz\n'
            'COPY build/codex_pilot_stub.py build/codex_pilot_probe.py /opt/pilot/\n'
            'RUN mkdir -p /logs/agent /logs/verifier /logs/artifacts /installed-agent && chmod 777 /logs/agent /logs/artifacts && chmod 700 /logs/verifier && '
            'chmod -R a-w /workspace/input /opt/codex /opt/pilot && '
            'chmod 755 /home/agent && mkdir -p /home/agent/.codex-pilot && '
            'chown agent:agent /home/agent/.codex-pilot && chmod 700 /home/agent/.codex-pilot\n'
            'USER agent\n')


def usage_record(value, *, probe=False):
    import os
    agent = value.get('agent_result') or {}
    counts = {key: agent.get(key) for key in ('n_input_tokens', 'n_cache_tokens', 'n_output_tokens')}
    valid = all(type(v) is int and v >= 0 for v in counts.values())
    cost = None
    if valid:
        i,c,o = counts.values()
        if c > i: raise ValueError('Contradictory provider usage')
        # Cumulative counts cannot identify per-request long-context billing.
        # Conservatively apply its premium once cumulative input exceeds 272K.
        prefill, sample = (2, 1.5) if i > 272000 else (1, 1)
        cost = (((i-c)*2+c*.1)*prefill+o*10*sample)/1_000_000
    complete = (agent.get('metadata') or {}).get('execution_complete', True)
    return {'trial': value['trial_name'], 'completeness': 'complete_turn' if valid and complete else 'partial' if valid else 'unavailable',
            'provenance': 'codex-0.167-exec-json' if valid else None, **counts, 'estimated_usd': cost if complete else None,
            **({'observed_estimated_usd': cost} if not complete else {}),
            'billing': 'stub protocol; no model usage or billing' if probe or os.environ.get('AEB_PILOT_PROBE') == '1' else 'provider-reported tokens; estimate, not invoice'}
