"""Trial-local Harbor custom-agent extension; upstream files remain unchanged."""
import json
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

    async def _upload_effective_config(self, environment, config, remote_path):
        (self.logs_dir / 'effective-config.json').write_text(json.dumps(config, indent=2) + '\n')
        await super()._upload_effective_config(environment, config, remote_path)
