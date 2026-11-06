"""Trial-local Harbor custom-agent extension; upstream files remain unchanged."""
import json
import shlex
import re
import toml
from harbor.agents.installed.codex import Codex

async def check_pin(environment, version=None):
    # Docker merges stderr into stdout; Codex can print a startup warning before
    # its version. Match the explicit version line, never the first output line.
    result = await environment.exec(command='/usr/local/bin/codex --version', user='agent', timeout_sec=30)
    versions = re.findall(r'^codex-cli ([0-9.]+)$', result.stdout or '', re.MULTILINE)
    from diagnostics import sanitize
    return {'stdout':sanitize(result.stdout),'stderr':sanitize(result.stderr),'cwd':'/workspace',
            'command':'/usr/local/bin/codex --version', 'user':'agent',
            'returncode':result.return_code, 'version':versions[0] if len(versions)==1 else None,
            'matched':result.return_code==0 and versions==[version or json.loads(__import__('pathlib').Path(__file__).with_name('runtime-profile.json').read_text())['codex_version']]}

async def inspect_budget_feature(environment):
    result=await environment.exec(command='CODEX_HOME=/installed-agent/codex-home codex features list',user='agent',timeout_sec=30)
    matches=re.findall(r'^rollout_budget\s+.+?\s+(true|false)\s*$',result.stdout or '',re.MULTILINE)
    assert result.return_code==0 and matches==['false'], 'Supplemental rollout-budget feature must be fully disabled'
    return {'command':'CODEX_HOME=/installed-agent/codex-home codex features list','user':'agent','exit_status':result.return_code,'rollout_budget_enabled':False,'inference':False,'reminders_enabled':False}

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
        package=await environment.exec(command='test -x /opt/codex/bin/codex-code-mode-host && test -x /opt/codex/bin/codex-exec-server && test -x /opt/codex/codex-path/rg && test -d /opt/codex/codex-resources && cat /opt/codex/codex-package.json',user='agent',timeout_sec=30)
        if package.return_code:raise RuntimeError('Pinned package layout incomplete')
        check['package']=json.loads(package.stdout)
        assert check['package']['version']=='0.166.0' and check['package']['entrypoint']=='bin/codex'
        (Path(os.environ['TRIAL_PUBLIC_DIR'])/'installation.json').write_text(json.dumps(check,indent=2)+'\n')
        probe=os.environ.get('TRIAL_PROVIDER_PROBE')
        if os.environ.get('TRIAL_DIAGNOSTIC')=='1' and probe in ('http','idle'):
            result=await environment.exec(command='nohup python3 /opt/refusal_fixture.py '+probe+' </dev/null >/tmp/refusal-fixture.log 2>&1 &',user='agent')
            if result.return_code:raise RuntimeError('Local refusal fixture failed to start')

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
        loaded=await self.exec_as_agent(environment,
            'CODEX_HOME=/installed-agent/codex-home codex app-server --strict-config --print-startup-config')
        parsed=next(json.loads(line) for line in loaded.stdout.splitlines() if line.startswith('{') and 'appServerVersion' in line)
        observed={'version':parsed['appServerVersion'],'allowed_login_methods':parsed['configRequirements']['requirements']['allowedLoginMethods'],'exit_status':loaded.return_code}
        observed['budget_feature']=await inspect_budget_feature(environment)
        (Path(os.environ['TRIAL_PUBLIC_DIR'])/'configuration-load.json').write_text(json.dumps(observed,indent=2)+'\n')
