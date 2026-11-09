"""Task-parameterized use of the qualified Codex adapter; inference is refused."""
import base64
import json
import os
import shlex
import hashlib
from pathlib import Path
import re
import shutil
import subprocess

from codex_pilot_agent import PilotCodex
from codex_pilot_environment import PilotEnvironment
from evaluation_campaign_core import require
from evaluation_runtime import ROOT, read_profile


class CampaignCodex(PilotCodex):
    def __init__(self, *args, campaign_definition, control, present, **kwargs):
        from evaluation_tasks import load
        self.task = load(ROOT / campaign_definition)
        self.control = control
        self.expected_present = present
        self.profile = read_profile(ROOT / self.task.definition['runtime_profile'])['resolved']
        self.skill = self.task.definition['skill']
        self.output = '/workspace/output/' + self.task.output
        require(os.environ.get('AEB_PILOT_PROBE') == '1', 'Campaign inference is disabled')
        super().__init__(*args, **kwargs)

    def fixture_payload(self):
        return self.task.payload(self.control)

    def fixture_commands(self, payload):
        if self.task.probe_origin == 'operator':
            return self.task.probe_commands(self.control, payload, self.expected_present)
        return ['python3 /opt/pilot/codex_pilot_probe.py ' + self.skill, *self.task.probe_commands(self.control, payload, self.expected_present)]

    async def probe_preflight(self, environment, env):
        if self.task.probe_origin == 'operator':
            await self.exec_as_agent(environment, command='python3 /opt/pilot/codex_pilot_probe.py ' + self.skill, env=env)
        for path in self.task.protected_paths:
            present = await environment.exec(user='root', command='test -f ' + shlex.quote(path))
            denied = await environment.exec(user='agent', command='test ! -r ' + shlex.quote(path))
            require(present.return_code == denied.return_code == 0, 'Task protected-path boundary failed')
        if self.task.protected_paths:
            target = self.logs_dir.parent / 'operator/task-boundary.json'
            target.write_text(json.dumps({'origin': 'operator', 'present_and_unreadable': list(self.task.protected_paths)}))


# Harbor public environment import hook composes the two existing lifecycle hooks:
# trusted gh startup before any agent work, then the qualified external CLI boundary.
from aeb_gh_fixture.backend import TrustedGhEnvironment


class CampaignGhEnvironment(PilotEnvironment, TrustedGhEnvironment):
    pass

def deploy(root, definition):
    """Native APM owns skill discovery/deployment; compare all supporting bytes."""
    import skill_reports as reports
    skill = definition['skill']
    source = ROOT / definition['source']
    require(source.resolve() == source and source.is_dir() and source.is_relative_to(ROOT), 'Unsafe skill source')
    project = root / 'apm-project'; project.mkdir()
    shutil.copytree(source, project / '.apm/skills' / skill, ignore=shutil.ignore_patterns('evals'))
    (project / 'apm.yml').write_text('name: evaluation-workspace\nversion: 1.0.0\ntarget: codex\nincludes:\n  - .apm/skills/' + skill + '/\n')
    apm = Path(os.environ['APM_EXECUTABLE']).resolve(strict=True)
    version = re.search(r'CLI version ([0-9.]+)', subprocess.check_output([apm, '--version'], text=True)).group(1)
    require(version == (ROOT / '.apm-version').read_text().strip(), 'APM version mismatch')
    clean = {k:v for k,v in os.environ.items() if not re.search('TOKEN|SECRET|API_KEY|PASSWORD', k)}
    subprocess.run([apm, 'install', '--only', 'apm', '--target', 'codex'], cwd=project, env=clean, check=True, timeout=60)
    deployed = project / '.agents/skills' / skill
    expected = {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in reports.regular_tree(source) if p.relative_to(source).parts[0] != 'evals'}
    require(manifest(deployed) == expected, 'APM deployment differs from source')
    reports.write_json(root / 'deployment.json', {'apm': version, 'adapter': 'codex', 'skill': skill, 'manifest': expected,
        'personal_instructions': False, 'mcp_servers': [], 'mode': 'isolated'})
    return deployed


def resources():
    from codex_pilot import resources as docker_resources
    return docker_resources()


def prepare_task(native, mode, runtime):
    config = native / 'task.toml'
    text = config.read_text().replace('timeout_sec = 300.0', f'timeout_sec = {runtime["agent_seconds"]}.0').replace('memory_mb = 4096', f'memory_mb = {runtime["memory_mb"]}')
    if mode == 'probe':
        text = text.replace('network_mode = "public"', 'network_mode = "allowlist"\nallowed_hosts = ["api.openai.com"]')
    config.write_text(text)
    if mode == 'probe':
        from codex_pilot_runtime import prepare_cli
        (native / 'environment/build').mkdir(exist_ok=True)
        # Reuse the already-qualified curl package version and snapshot. The gh
        # fixture image has no curl; the Pester image already satisfies this pin.
        with (native / 'environment/Dockerfile').open('a') as stream:
            stream.write('RUN command -v curl >/dev/null || (apt-get update --error-on=any -o Acquire::Retries=3 -o Acquire::https::Timeout=30 && apt-get install -y --no-install-recommends curl=8.14.1-2+deb13u7 && rm -rf /var/lib/apt/lists/*)\n')
        prepare_cli(native)


def agent_config(task, mode, control, runtime, present):
    if mode == 'oracle':
        return {'name': 'oracle'}
    return {'import_path': 'evaluation_codex:CampaignCodex', 'model_name': runtime['model'],
            'kwargs': {'campaign_definition': task.member, 'control': control, 'present': present}}


def native_observation(trial, native, present, row, rows):
    import skill_reports as reports
    audits = list(trial.rglob('pilot-runtime.json'))
    require(len(audits) == 1, 'Missing runtime observation')
    audit = reports.read_json(audits[0]); row['runtime_observation'] = audit
    from codex_pilot_contract import configuration
    require(audit['cleanup'] == 'complete' and audit['boundary_before']['policy_sha256'] == audit['boundary_after']['policy_sha256']
        and audit['effective_config'] == configuration('http://127.0.0.1:8765/v1')
        and audit['prompt_sha256'] == hashlib.sha256((native / 'instruction.md').read_bytes()).hexdigest()
        and audit['skill_deployed'] == present, 'Runtime identity or cleanup drift')
    probes = list(trial.rglob('probe.json'))
    require(len(probes) == 1, 'Missing non-forwarding request observation')
    probe = reports.read_json(probes[0])
    from codex_pilot_contract import PROFILE
    require(probe.get('model') == PROFILE['model'] and probe.get('reasoning', {}).get('effort') == PROFILE['reasoning_effort']
            and probe.get('requests') == 2, 'Observed CLI model/request drift')
    row['agent_id'] = audit['boundary_before']['agent_id']
    require(not any(r is not row and r.get('agent_id') == row['agent_id'] for r in rows), 'Reused agent environment')


def manifest(directory):
    import skill_reports as reports
    return {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in reports.regular_tree(directory)}


def usage(trial, mode):
    import skill_reports as reports
    from codex_pilot_runtime import usage_record
    if mode == 'oracle':
        return {'estimated_usd': 0, 'billing': 'oracle fixture; no model inference or billing',
                'n_input_tokens': None, 'n_cache_tokens': None, 'n_output_tokens': None}
    if not (trial / 'result.json').exists():
        return {'estimated_usd': None, 'billing': 'missing native usage'}
    return usage_record(reports.read_json(trial / 'result.json'), probe=True)


def validate_members(members, mode):
    if mode != 'probe':
        return
    for filename in ('codex_pilot_stub.py', 'codex_pilot_probe.py'):
        digest = 'sha256:' + hashlib.sha256((ROOT / '.github/scripts' / filename).read_bytes()).hexdigest()
        require(members.get('environment/build/' + filename) == digest, 'Unapproved staged runtime helper')



RETAINED_MEMBERS = ('pilot-runtime.json', 'pilot-final-policy.json', 'docker-observation.json',
                    'probe.json', 'codex.txt', 'trajectory.json', 'task-boundary.json')
