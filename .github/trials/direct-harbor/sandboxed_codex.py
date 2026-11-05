"""Trial-local Harbor custom-agent extension; upstream files remain unchanged."""
import json
import shlex
import toml
from harbor.agents.installed.codex import Codex

BYPASS = '--dangerously-bypass-approvals-and-sandbox '
REPLACEMENT = '--sandbox workspace-write -c approval_policy=never '


def sandbox_command(command):
    if 'codex exec ' not in command or command.count(BYPASS) != 1:
        raise ValueError('Pinned Codex launch shape changed')
    return command.replace(BYPASS, REPLACEMENT, 1)


class SandboxedCodex(Codex):
    """Use Harbor's import_path custom-agent API, retaining its native CLI adapter."""
    async def exec_as_agent(self, environment, command, env=None, cwd=None, timeout_sec=None):
        if 'codex exec ' in command:
            command = sandbox_command(command)
            # This contains only the public task and fixed flags, never env/auth values.
            (self.logs_dir / 'effective-command.txt').write_text(command + '\n')
        return await super().exec_as_agent(environment, command, env=env, cwd=cwd, timeout_sec=timeout_sec)

    async def install(self, environment):
        # The image contains the checksum-verified pin. Never fall back to an
        # installer with broader network/privilege requirements during a trial.
        if not await self._installed_codex_satisfies_version(environment):
            raise RuntimeError('Preinstalled Codex version mismatch')

    async def _ensure_agent_owned_dir(self, environment, path):
        # Build-time ownership avoids root chown under cap_drop=ALL.
        if str(path) != '/installed-agent/codex-home':
            raise ValueError('Unexpected Codex home')
        await self.exec_as_agent(environment,
            'test "$(id -u)" = 1000 && test "$(id -g)" = 1000 && '
            'test "$(stat -c %u /installed-agent/codex-home)" = 1000 && '
            'test "$(stat -c %a /installed-agent/codex-home)" = 700')
        return '1000', '1000'

    async def _upload_effective_config(self, environment, config, remote_path):
        (self.logs_dir / 'effective-config.json').write_text(json.dumps(config, indent=2) + '\n')
        if remote_path != '/installed-agent/codex-home/config.toml':
            raise ValueError('Unexpected Codex configuration destination')
        await self.exec_as_agent(environment,
            'umask 077; printf %s ' + shlex.quote(toml.dumps(config)) + ' > ' + shlex.quote(remote_path))
