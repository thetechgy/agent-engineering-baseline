"""Trial-local Harbor custom-agent extension; upstream files remain unchanged."""
import json
import shlex
import re
import toml
from harbor.agents.installed.codex import Codex

async def check_pin(environment):
    # Docker merges stderr into stdout; Codex can print a startup warning before
    # its version. Match the explicit version line, never the first output line.
    result = await environment.exec(command='/usr/local/bin/codex --version', user='agent', timeout_sec=30)
    versions = re.findall(r'^codex-cli ([0-9.]+)$', result.stdout or '', re.MULTILINE)
    from diagnostics import sanitize
    return {'stdout':sanitize(result.stdout),'stderr':sanitize(result.stderr),'cwd':'/workspace',
            'command':'/usr/local/bin/codex --version', 'user':'agent',
            'returncode':result.return_code, 'version':versions[0] if len(versions)==1 else None,
            'matched':result.return_code==0 and versions==['0.155.1']}

class PinnedCodex(Codex):
    """Stock run/exec path; only pinned installation and unprivileged ownership."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        import os
        from pathlib import Path
        from diagnostics import LaunchDiagnostics
        if os.environ.get('TRIAL_PUBLIC_DIR'):
            self.launch_diagnostics=LaunchDiagnostics(Path(os.environ['TRIAL_PUBLIC_DIR'])/'launch-diagnostics.json',
                tuple(os.environ.get(k,'') for k in ('OPENAI_API_KEY','CODEX_API_KEY')))
            self.logger.addHandler(self.launch_diagnostics)

    async def install(self, environment):
        # The image contains the checksum-verified pin. Never fall back to an
        # installer with broader network/privilege requirements during a trial.
        from live import runtime_check
        import os
        from pathlib import Path
        await runtime_check(environment, os.environ['TRIAL_VARIANT'], Path(os.environ['TRIAL_PUBLIC_DIR']))
        check = await check_pin(environment)
        (Path(os.environ['TRIAL_PUBLIC_DIR']) / 'installation.json').write_text(json.dumps(check, indent=2) + '\n')
        if not check['matched']:
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
