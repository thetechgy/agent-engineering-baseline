"""Trial-local Harbor custom-agent extension; upstream files remain unchanged."""
import json
import shlex
import toml
from harbor.agents.installed.codex import Codex

class PinnedCodex(Codex):
    """Stock run/exec path; only pinned installation and unprivileged ownership."""
    async def install(self, environment):
        # The image contains the checksum-verified pin. Never fall back to an
        # installer with broader network/privilege requirements during a trial.
        from live import runtime_check
        import os
        from pathlib import Path
        await runtime_check(environment, os.environ['TRIAL_VARIANT'], Path(os.environ['TRIAL_PUBLIC_DIR']))
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
        import os
        from pathlib import Path
        (Path(os.environ['TRIAL_PUBLIC_DIR']) / 'effective-config.json').write_text(json.dumps(config, indent=2) + '\n')
        if remote_path != '/installed-agent/codex-home/config.toml':
            raise ValueError('Unexpected Codex configuration destination')
        await self.exec_as_agent(environment,
            'umask 077; printf %s ' + shlex.quote(toml.dumps(config)) + ' > ' + shlex.quote(remote_path))
