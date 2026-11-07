"""Pilot-only Harbor Codex adapter. Uses the released CLI with its sandbox enabled."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import tempfile
import tomllib

from harbor.agents.installed.codex import Codex
from codex_pilot_contract import PROFILE, configuration

BINARY = '/opt/codex/bin/codex'
HOME = '/home/agent/.codex-pilot'
OUTPUT = '/workspace/output/Subject.Tests.ps1'


class PilotCodex(Codex):
    """Reuse Harbor lifecycle/trajectory conversion, with an explicit safe launch."""

    def __init__(self, *args, **kwargs):
        kwargs['version'] = PROFILE['cli']
        super().__init__(*args, **kwargs)

    async def install(self, environment):
        # Complete verified installation is baked into the agent image preapproval.
        await self.exec_as_agent(environment, command=(
            f"test \"$({BINARY} --version)\" = 'codex-cli {PROFILE['cli']}' && "
            f"printf '%s  %s\\n' {PROFILE['cli_executable_sha256']} {BINARY} | sha256sum -c --strict"))

    def populate_context_post_run(self, context):
        # 0.167's durable store differs from Harbor 0.24's old JSONL reader.
        # The released exec JSON protocol supplies final cumulative usage.
        path = self.logs_dir / 'codex.txt'
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 16*1024*1024:
            return
        events = []
        for line in path.read_text().splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                continue
        completed = [e['usage'] for e in events if e.get('type') == 'turn.completed']
        if len(completed) != 1:
            return  # No fallback zero for interrupted or unobserved usage.
        usage = completed[0]
        keys = ('input_tokens', 'cached_input_tokens', 'output_tokens')
        if not all(type(usage.get(k)) is int and usage[k] >= 0 for k in keys):
            raise ValueError('Invalid CLI usage protocol')
        if usage['cached_input_tokens'] > usage['input_tokens']:
            raise ValueError('Contradictory CLI usage')
        context.n_input_tokens = usage['input_tokens']
        context.n_cache_tokens = usage['cached_input_tokens']
        context.n_output_tokens = usage['output_tokens']
        context.metadata = {'usage_source': 'codex-0.167-exec-json', 'billing_verified': False}

    async def run(self, instruction, environment, context):
        if self.model_name != PROFILE['model']:
            raise ValueError('Pilot model drift')
        probe = os.environ.get('AEB_PILOT_PROBE') == '1'
        if not probe and os.environ.get('OPENAI_BASE_URL'):
            raise ValueError('Pilot provider override refused')
        logs = self.environment_logs_dir.as_posix()
        config = configuration('http://127.0.0.1:8765/v1' if probe else None)
        env = {'CODEX_HOME': HOME, 'OPENAI_API_KEY': 'pilot-not-a-credential' if probe else self.model_connection.api_key or ''}
        if not env['OPENAI_API_KEY']:
            raise ValueError('Protected provider key missing')
        await self.exec_as_agent(environment, command=f'mkdir -p {HOME} {logs}', env=env)
        await self._upload_effective_config(environment, config, HOME + '/config.toml')
        # Verify the real post-upload file, never just the configuration builder.
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'effective.toml'
            await environment.download_file(HOME + '/config.toml', target)
            if tomllib.loads(target.read_text()) != config:
                raise ValueError('Post-upload Codex configuration drift')
            config_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        register = self._build_register_skills_command() or ':'
        await self.exec_as_agent(environment, command=register)
        await self.exec_as_agent(environment, command=(
            'test "$(id -u)" = 1000 && test "$HOME" = /home/agent && '
            'test "$(pwd)" = /workspace && test ! -e /tests && '
            'test ! -e /solution && test ! -e /opt/pester-runtime && test ! -e /home/agent/pilot-deny && '
            'test -z "$(find /workspace/skills -type d -name evals -print -quit)"'))
        present = await environment.exec(user='agent', command='test -r "$HOME/.agents/skills/powershell-pester-6/SKILL.md"')
        if present.return_code == 0:
            await self.exec_as_agent(environment, command='diff -qr /workspace/skills/powershell-pester-6 "$HOME/.agents/skills/powershell-pester-6"')
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        audit = {'adapter': PROFILE['id'], 'cli': PROFILE['cli'], 'model': PROFILE['model'],
                 'reasoning_effort': 'high', 'provider': 'openai', 'probe': probe,
                 'cwd': '/workspace', 'output': OUTPUT, 'sandbox': 'workspace-write',
                 'config_sha256': config_hash, 'effective_config': config,
                 'prompt_sha256': hashlib.sha256(instruction.encode()).hexdigest(),
                 'skill_deployed': present.return_code == 0, 'cleanup': 'pending'}
        (self.logs_dir / 'pilot-runtime.json').write_text(json.dumps(audit, indent=2) + '\n')
        if probe:
            # Server has no network forwarding and never authenticates to a provider.
            server = Path(__file__).with_name('codex_pilot_stub.py')
            await environment.upload_file(server, HOME + '/stub.py')
            await self.exec_as_agent(environment, command=f'python3 {HOME}/stub.py {logs}/probe.json >{logs}/stub.log 2>&1 & echo $! >{HOME}/stub.pid')
        command = (f'{BINARY} exec --strict-config --sandbox workspace-write --skip-git-repo-check '
                   f'--cd /workspace --model {PROFILE["model"]} --json '
                   f'--output-last-message {logs}/last-message.txt -- {shlex.quote(instruction)} '
                   f'>{logs}/codex.txt 2>&1')
        try:
            result = await environment.exec(command=command, env=env, user='agent',
                                               timeout_sec=PROFILE['agent_seconds'])
            audit['returncode'] = result.return_code
        finally:
            # Keep exact native events before removing the runtime home/credentials.
            try:
                from codex_pilot import producer_receipt_command
                await self.exec_as_agent(environment, command=producer_receipt_command())
                await self.exec_as_agent(environment, command=(
                    f'if [ -d {HOME}/sessions ]; then cp -R {HOME}/sessions {logs}/sessions; fi; '
                    f'if [ -f {HOME}/stub.pid ]; then kill "$(cat {HOME}/stub.pid)"; fi; '
                    f'rm -rf {HOME}; test ! -e {HOME}'))
                audit['cleanup'] = 'complete'
            finally:
                (self.logs_dir / 'pilot-runtime.json').write_text(json.dumps(audit, indent=2) + '\n')
