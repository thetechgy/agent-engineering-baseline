"""Pilot-only Harbor Codex adapter. External Docker isolation; the released CLI inner sandbox is disabled."""
import asyncio
import base64
import time
import hashlib
import json
import os
from pathlib import Path
import shlex
import tomllib

from harbor.agents.installed.codex import Codex
from codex_pilot_contract import PROFILE, ROOT, configuration

BINARY = '/opt/codex/bin/codex'
HOME = '/home/agent/.codex-pilot'
OUTPUT = '/workspace/output/Subject.Tests.ps1'


class PilotCodex(Codex):
    """Reuse Harbor lifecycle/trajectory conversion, with an explicit safe launch."""

    profile = PROFILE
    skill = PROFILE['skill']
    output = OUTPUT
    retain_submission = False

    def fixture_payload(self):
        from skill_evidence import read_bytes
        if os.environ.get('AEB_COHORT_FIXTURE'):
            from codex_pilot_effectiveness import fixtures
            return fixtures()[os.environ['AEB_COHORT_FIXTURE']]['payload']
        return read_bytes(ROOT / '.github/evals' / self.skill / 'support/qualification' / self.profile['case'] / 'classic.Tests.ps1', limit=65536)

    def fixture_commands(self, payload):
        return [f"python3 /opt/pilot/codex_pilot_probe.py && printf %s {payload} | base64 -d > {self.output}"]

    async def probe_preflight(self, environment, env):
        pass

    def __init__(self, *args, **kwargs):
        kwargs['version'] = self.profile['cli']
        super().__init__(*args, **kwargs)

    async def install(self, environment):
        # Complete verified installation is baked into the agent image preapproval.
        await self.exec_as_agent(environment, command=(
            f"test \"$({BINARY} --version)\" = 'codex-cli {self.profile['cli']}' && "
            f"printf '%s  %s\\n' {self.profile['cli_executable_sha256']} {BINARY} | sha256sum -c --strict"))

    async def _upload_effective_config(self, environment, config, remote_path):
        # No CAP_CHOWN: create as the task user through the secure stdin transport.
        import toml
        payload = base64.b64encode(toml.dumps(config).encode()).decode()
        await self.exec_as_agent(environment, command=(
            f"umask 077; printf %s {shlex.quote(payload)} | base64 -d > {shlex.quote(remote_path)}"))

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
        environment.retain_on_interrupt(self.output)
        environment._stage('agent_started')
        try:
            return await self._run_codex(instruction, environment, context)
        except BaseException:
            self._execution_interrupted = True
            raise

    async def _run_codex(self, instruction, environment, context):
        if self.model_name != self.profile['model']:
            raise ValueError('Pilot model drift')
        probe = os.environ.get('AEB_PILOT_PROBE') == '1'
        if not probe and os.environ.get('OPENAI_BASE_URL'):
            raise ValueError('Pilot provider override refused')
        from codex_pilot_boundary import observe, connectivity_baseline
        # Harbor has already applied the agent phase policy. Verify it outside the
        # container before the first exec that could carry a future real key.
        boundary_before = await observe(environment)
        if probe:
            boundary_before['operator_positive_controls'] = connectivity_baseline()
        scenario = os.environ.get('AEB_PILOT_SCENARIO', 'success') if probe else 'live'
        logs = self.environment_logs_dir.as_posix()
        config = configuration('http://127.0.0.1:8765/v1' if probe else None)
        env = {'CODEX_HOME': HOME, 'OPENAI_API_KEY': 'pilot-not-a-credential' if probe else self.model_connection.api_key or ''}
        if not env['OPENAI_API_KEY']:
            raise ValueError('Protected provider key missing')
        await self.exec_as_agent(environment, command=f'mkdir -p {HOME} {logs}', env=env)
        await self._upload_effective_config(environment, config, HOME + '/config.toml')
        # Verify the real post-upload file, never just the configuration builder.
        result = await self.exec_as_agent(environment, command=f'cat {HOME}/config.toml')
        if tomllib.loads(result.stdout) != config:
            raise ValueError('Post-upload Codex configuration drift')
        config_hash = hashlib.sha256(result.stdout.encode()).hexdigest()
        register = self._build_register_skills_command() or ':'
        await self.exec_as_agent(environment, command=register)
        await self.exec_as_agent(environment, command=(
            'test "$(id -u)" = 1000 && test "$HOME" = /home/agent && '
            'test "$(pwd)" = /workspace && test ! -e /tests && '
            'test ! -e /solution && test ! -e /opt/pester-runtime && '
            'test -z "$(find /workspace/skills -type d -name evals -print -quit)"'))
        present = await environment.exec(user='agent', command=f'test -r "$HOME/.agents/skills/{self.skill}/SKILL.md"')
        if present.return_code == 0:
            await self.exec_as_agent(environment, command=f'diff -qr /workspace/skills/{self.skill} "$HOME/.agents/skills/{self.skill}"')
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        audit = {'adapter': self.profile['id'], 'cli': self.profile['cli'], 'model': self.profile['model'],
                 'reasoning_effort': 'high', 'provider': 'openai', 'probe': probe,
                 'cwd': '/workspace', 'output': self.output, 'sandbox': 'danger-full-access',
                 'execution_policy': self.profile['execution_policy'], 'scenario': scenario,
                 'boundary_before': boundary_before,
                 'config_sha256': config_hash, 'effective_config': config,
                 'prompt_sha256': hashlib.sha256(instruction.encode()).hexdigest(),
                 'skill_deployed': present.return_code == 0, 'cleanup': 'pending'}
        audit_path = self.logs_dir.parent / 'operator/pilot-runtime.json'
        audit_path.parent.mkdir(exist_ok=True)
        audit_path.write_text(json.dumps(audit, indent=2) + '\n')
        if probe:
            # Keep qualification answers on the trusted host, out of all images.
            # Only the credential-free probe receives this transient payload.
            raw = self.fixture_payload()
            payload = base64.b64encode(raw).decode()
            commands = base64.b64encode(json.dumps(self.fixture_commands(payload)).encode()).decode()
            await self.probe_preflight(environment, env)
            # Server has no network forwarding and never authenticates to a provider.
            await self.exec_as_agent(environment, command=(
                f'python3 /opt/pilot/codex_pilot_stub.py {logs}/probe.json {scenario} {shlex.quote(payload)} {shlex.quote(commands)} '
                f'>{logs}/stub.log 2>&1 & echo $! >{HOME}/stub.pid'))
        command = (f'{BINARY} exec --strict-config --sandbox danger-full-access --skip-git-repo-check '
                   f'--cd /workspace --model {self.profile["model"]} --json '
                   f'--output-last-message {logs}/last-message.txt -- {shlex.quote(instruction)} '
                   f'>{logs}/codex.txt 2>{logs}/codex-stderr.txt')
        if scenario == 'interruption':
            command = 'timeout --signal=INT --kill-after=5s 5s ' + command
        primary = None
        started = time.monotonic()
        try:
            result = await environment.exec(command=command, env=env, user='agent',
                                               timeout_sec=self.profile['agent_seconds'])
            audit['returncode'] = result.return_code
            audit['boundary_after'] = await observe(environment)
        except BaseException as error:
            primary = error
            self._execution_interrupted = True
            audit['execution_exception'] = type(error).__name__
            raise
        finally:
            audit['execution_elapsed_seconds'] = round(time.monotonic() - started, 3)
            # A contained workload cannot exec a receipt or scrub command. Its
            # remaining runtime home is removed by final container disposal.
            if environment._pilot_interrupted:
                audit['cleanup'] = 'pending_container_disposal'
            else:
                try:
                    from codex_pilot import producer_receipt_command
                    async with asyncio.timeout(30):
                        await self.exec_as_agent(environment, command=producer_receipt_command(self.output, retain=self.retain_submission))
                    async with asyncio.timeout(30):
                        await self.exec_as_agent(environment, command=(
                            f'if [ -f {HOME}/stub.pid ]; then kill "$(cat {HOME}/stub.pid)"; fi; '
                            f'rm -rf {HOME}; test ! -e {HOME}'))
                    audit['cleanup'] = 'complete'
                except BaseException as error:
                    audit['collection_or_cleanup_exception'] = type(error).__name__
                    if primary is None:
                        audit_path.write_text(json.dumps(audit, indent=2) + '\n')
                        raise
            audit_path.write_text(json.dumps(audit, indent=2) + '\n')
        if result.return_code != 0:
            self._execution_interrupted = True
            raise RuntimeError('Pilot Codex CLI exited unsuccessfully; original events retained')
