"""Task-parameterized use of the qualified Codex adapter; inference requires the shared exact authorization gate."""
import base64
import json
import os
import shlex
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from codex_pilot_agent import PilotCodex
from codex_pilot_environment import PilotEnvironment
from evaluation_campaign_core import require
from evaluation_runtime import ROOT, read_profile, failure_reason


class MissingCodexObservation(ValueError):
    pass


class UnsupportedCodexProtocol(ValueError):
    pass


class CodexRuntimeError(ValueError):
    """A recognized terminal failure, distinct from an unsupported event."""


def exec_trajectory(raw, adapter):
    """Read pinned 0.167 exec events as data; never execute recorded actions.

    File-change items contain paths/operations/status, not patch contents or
    shell output. Completion-only edits are emitted by the released processor.
    Every normalized action links to its exact raw trace and event line(s).
    """
    from harbor.agents.installed.codex import Agent, Trajectory
    pending = {}; completed = set(); steps = []; notes = []; informational = []
    session = None; turns = 0; actions = 0; terminal = False
    trace = {'member':'agent/codex.txt', 'sha256':'sha256:' + hashlib.sha256(raw.encode()).hexdigest()}

    def identity(item):
        value = item.get('id')
        if not isinstance(value, str) or not value or value in completed:
            raise UnsupportedCodexProtocol('Ambiguous native item identity')
        return value

    def begin(item, line):
        key = identity(item)
        if key in pending:
            raise UnsupportedCodexProtocol('Duplicate native item start')
        pending[key] = {'item':item, 'lines':[line]}

    def finish(item, line, *, terminal_only=False):
        key = identity(item)
        previous = pending.pop(key, None)
        if previous is None and not terminal_only:
            raise MissingCodexObservation('Unobserved native item start')
        if previous and previous['item']['type'] != item['type']:
            raise UnsupportedCodexProtocol('Native item type changed')
        completed.add(key)
        return previous, {'protocol':'codex-0.167-exec-json', 'native_item_id':key,
            'native_item_type':item['type'], 'raw_trace':trace,
            'raw_event_lines':[*previous['lines'],line] if previous else [line],
            'lifecycle':'started/completed' if previous else 'completion-only'}

    def changes(item):
        value = item.get('changes')
        if not isinstance(value, list) or any(not isinstance(c, dict) or set(c) != {'path','kind'}
                or not isinstance(c['path'], str) or not c['path'] or '\x00' in c['path']
                or c['kind'] not in ('add','delete','update') for c in value):
            raise UnsupportedCodexProtocol('Invalid native file changes')
        return sorted((c['path'],c['kind']) for c in value)

    for line_number, line in enumerate(raw.splitlines(), 1):
        if line == 'Reading additional input from stdin...':
            notes.append(line); continue
        try: event = json.loads(line)
        except ValueError as error:
            raise UnsupportedCodexProtocol('Non-JSON native observation') from error
        if not isinstance(event, dict):
            raise UnsupportedCodexProtocol('Invalid native event')
        kind = event.get('type')
        if terminal:
            raise UnsupportedCodexProtocol('Native event after terminal turn')
        if kind == 'thread.started':
            if session is not None or not isinstance(event.get('thread_id'), str) or not event['thread_id']:
                raise UnsupportedCodexProtocol('Ambiguous native thread')
            session = event['thread_id']; continue
        if kind == 'turn.started':
            informational.append({'line':line_number, 'event':event}); continue
        if kind in ('error','turn.failed'):
            value = event if kind == 'error' else event.get('error')
            if not isinstance(value, dict) or not isinstance(value.get('message'), str):
                raise UnsupportedCodexProtocol('Malformed native terminal error')
            raise CodexRuntimeError('Codex terminal failure at raw line ' + str(line_number) + ': ' + kind)
        if kind == 'turn.completed':
            turns += 1; terminal = True
            informational.append({'line':line_number, 'event':event}); continue
        item = event.get('item')
        if not isinstance(item, dict):
            raise UnsupportedCodexProtocol('Invalid native item')
        item_type = item.get('type')
        if item_type in ('agent_message','reasoning','error') and kind == 'item.completed':
            key = identity(item)
            if key in pending:
                raise UnsupportedCodexProtocol('Informational item conflicts with native action')
            field = 'message' if item_type == 'error' else 'text'
            if not isinstance(item.get(field), str):
                raise MissingCodexObservation('Missing native informational content')
            completed.add(key)
            metadata = {'native_item_id':key, 'native_item_type':item_type,
                        'raw_trace':trace, 'raw_event_lines':[line_number]}
            if item_type == 'error':
                # The released schema defines item/error as non-fatal. Keep every
                # warning, not just one recognized message prefix.
                notes.append(item['message']); informational.append({'line':line_number, 'event':event}); continue
            normalized = {'kind':'message', 'role':'assistant', 'text':item['text'] if item_type == 'agent_message' else '',
                          'reasoning':item['text'] if item_type == 'reasoning' else None, 'extra':metadata}
        elif item_type == 'todo_list' and kind in ('item.started','item.updated','item.completed'):
            key = identity(item); values = item.get('items')
            if not isinstance(values, list) or any(not isinstance(v, dict) or set(v) != {'text','completed'}
                    or not isinstance(v['text'], str) or type(v['completed']) is not bool for v in values):
                raise UnsupportedCodexProtocol('Invalid native plan')
            if kind == 'item.started': begin(item,line_number)
            elif kind == 'item.updated':
                if key not in pending or pending[key]['item']['type'] != item_type:
                    raise MissingCodexObservation('Unobserved native plan start')
                pending[key]['lines'].append(line_number)
            else: finish(item,line_number)
            informational.append({'line':line_number, 'event':event}); continue
        elif item_type == 'command_execution' and kind in ('item.started','item.updated','item.completed'):
            key = identity(item); command = item.get('command')
            if not isinstance(command, str):
                raise UnsupportedCodexProtocol('Invalid native command')
            if kind == 'item.started': begin(item,line_number); continue
            if key not in pending:
                raise MissingCodexObservation('Unobserved native command start')
            if pending[key]['item'].get('command') != command:
                raise UnsupportedCodexProtocol('Native command identity changed')
            if kind == 'item.updated':
                if item.get('status') != 'in_progress' or not isinstance(item.get('aggregated_output'), str) or item.get('exit_code') is not None:
                    raise UnsupportedCodexProtocol('Invalid native command update')
                pending[key]['lines'].append(line_number); continue
            if not isinstance(item.get('aggregated_output'), str) or type(item.get('exit_code')) is not int or item.get('status') not in ('completed','failed'):
                raise MissingCodexObservation('Incomplete native command result')
            _, metadata = finish(item,line_number)
            try: wrapper = shlex.split(command)
            except ValueError as error:
                raise UnsupportedCodexProtocol('Invalid native shell wrapper') from error
            if len(wrapper) != 3 or wrapper[:2] != ['/bin/sh','-lc']:
                raise UnsupportedCodexProtocol('Unsupported native shell wrapper')
            metadata.update(native_command=command, exit_code=item['exit_code'])
            normalized = {'kind':'tool_call', 'call_id':key, 'tool_name':'exec_command',
                'arguments':{'command':wrapper[2]}, 'output':item['aggregated_output'],
                'status':item['status'], 'metadata':metadata}
            actions += 1
        elif item_type == 'file_change' and kind in ('item.started','item.completed'):
            key = identity(item); operation_identity = changes(item)
            if set(item) != {'id','type','changes','status'}:
                raise UnsupportedCodexProtocol('Unknown native file-change fields')
            if kind == 'item.started':
                if item['status'] != 'in_progress':
                    raise UnsupportedCodexProtocol('Invalid native file-change start')
                begin(item,line_number); continue
            if item['status'] not in ('completed','failed'):
                raise MissingCodexObservation('Nonterminal native file change')
            previous, metadata = finish(item,line_number,terminal_only=True)
            if previous and changes(previous['item']) != operation_identity:
                raise UnsupportedCodexProtocol('Native file-change identity changed')
            # Use the native action name and native terminal payload. No shell
            # command, patch body, exit code or fabricated success text is added.
            normalized = {'kind':'tool_call', 'call_id':key, 'tool_name':'file_change',
                'arguments':{'changes':item['changes']}, 'output':json.dumps(item,ensure_ascii=False,sort_keys=True),
                'status':item['status'], 'metadata':metadata}
            actions += 1
        else:
            raise UnsupportedCodexProtocol('Unsupported native event: ' + str(kind) + '/' + str(item_type))
        step = adapter._convert_event_to_step(normalized, len(steps)+1)
        steps.append(step.model_copy(update={'llm_call_count':None}))
    if pending or turns != 1 or not session or not actions:
        raise MissingCodexObservation('Incomplete native trajectory')
    return Trajectory(schema_version='ATIF-v1.7', session_id=session,
        agent=Agent(name='codex',version=adapter.profile['cli'],model_name=adapter.model_name),
        steps=steps, notes='\n'.join(notes) or None,
        extra={'source':'codex-0.167-exec-json','inference':getattr(adapter,'live',False),
               'raw_trace':trace,'informational_events':informational})


class CampaignCodex(PilotCodex):
    retain_submission = True

    def __init__(self, *args, campaign_definition, control, present, live=False, **kwargs):
        from evaluation_tasks import load
        self.task = load(ROOT / campaign_definition)
        self.control = control
        self.expected_present = present
        self.profile = read_profile(ROOT / self.task.definition['runtime_profile'])['resolved']
        self.skill = self.task.definition['skill']
        self.output = '/workspace/output/' + self.task.output
        self.live = live
        if live:
            from evaluation_campaign_protocol import runtime_gate
            runtime_gate(self.task)
            require(control is None and 'protocol' in self.task.definition, 'Live control payload refused')
        else:
            require(os.environ.get('AEB_PILOT_PROBE') == '1', 'Campaign inference is disabled')
        super().__init__(*args, **kwargs)

    def populate_context_post_run(self, context):
        super().populate_context_post_run(context) # Keep qualified usage semantics.
        from skill_evidence import read_bytes
        if self.logs_dir.resolve() != self.logs_dir.absolute():
            raise MissingCodexObservation('Unsafe native log directory')
        path = self.logs_dir / 'codex.txt'
        if not path.exists():
            raise MissingCodexObservation('Missing native log')
        raw = read_bytes(path, limit=16*1024*1024).decode()
        fault = os.environ.get('AEB_CAMPAIGN_OBSERVATION_FIXTURE')
        if fault:
            require(not self.live and os.environ.get('AEB_PILOT_PROBE') == '1', 'Live observation injection refused')
            record = {'fixture':fault, 'native_sha256':hashlib.sha256(raw.encode()).hexdigest()}
            (self.logs_dir / 'observation-injection.json').write_text(json.dumps(record))
            if fault == 'unsupported-runtime': raw += '\n' + json.dumps({'type':'unsupported.synthetic.control'})
            elif fault == 'missing-evidence': raw = '\n'.join(line for line in raw.splitlines() if '"turn.completed"' not in line)
            else: raise ValueError('Unknown observation fixture')
        trajectory = exec_trajectory(raw, self)
        if not self.live and self.task.native_file_edit_probe:
            edits = [step for step in trajectory.steps if step.tool_calls
                     and step.tool_calls[0].function_name == 'file_change']
            checks = [step for step in trajectory.steps if step.tool_calls and step.tool_calls[0].function_name=='exec_command'
                      and step.tool_calls[0].arguments == {'command':FILE_EDIT_CHECK}]
            require(len(checks)==1 and checks[0].extra['tool_metadata']['exit_code']==0
                    and checks[0].observation.results[0].content.strip()=='native-file-edit-controls-ok',
                    'Native edit failure/cleanup observation missing')
            statuses = [step.extra['status'] for step in edits]
            kinds = {change['kind'] for step in edits for change in step.tool_calls[0].arguments['changes']}
            require(statuses == ['completed'] * 4 + ['failed'] and kinds == {'add','update','delete'},
                    'Native file-edit probe did not exercise success/failure and all operations')
            (self.logs_dir / 'native-file-edit-probe.json').write_text(json.dumps({
                'raw_trace':trajectory.extra['raw_trace'], 'statuses':statuses, 'operations':sorted(kinds),
                'native_item_ids':[step.tool_calls[0].tool_call_id for step in edits],
                'inference':False, 'source':'real pinned CLI native apply_patch'},indent=2)+'\n')
        # Replacing the directory entry never follows a preexisting target link.
        with tempfile.NamedTemporaryFile(mode='w', dir=self.logs_dir, delete=False) as stream:
            temporary = Path(stream.name)
            try:
                stream.write(trajectory.model_dump_json(exclude_none=True)); stream.flush(); os.fsync(stream.fileno())
                os.fchmod(stream.fileno(), 0o644) # Harbor copies logs back; the capability-dropped verifier must read them.
                os.replace(temporary, self.logs_dir / 'trajectory.json')
            finally:
                temporary.unlink(missing_ok=True)

    def fixture_payload(self):
        require(not self.live, 'Fixture payload unavailable in live mode')
        control = os.environ.get('AEB_CAMPAIGN_CONTROL', self.control)
        return self.task.payload(control)

    def fixture_commands(self, payload):
        control = os.environ.get('AEB_CAMPAIGN_CONTROL', self.control)
        if self.task.probe_origin == 'operator':
            return self.task.probe_commands(control, payload, self.expected_present)
        read = ['cat /home/agent/.agents/skills/' + self.skill + '/SKILL.md'] if self.expected_present else []
        commands = ['python3 /opt/pilot/codex_pilot_probe.py ' + self.skill, *read]
        if not self.task.native_file_edit_probe:
            return [*commands, *self.task.probe_commands(control, payload, self.expected_present)]
        return [*commands, *native_file_edit_operations(self.output, base64.b64decode(payload).decode())]

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


FILE_EDIT_CHECK = "test ! -e /workspace/input/.native-edit-must-remain-absent && test ! -e /workspace/output/.native-edit-probe && printf '%s\\n' native-file-edit-controls-ok"


def native_file_edit_operations(output, content):
    """Host-only fixture instructions for real code-mode apply_patch calls.

    The failed add targets the already read-only public input directory. Nothing
    changes its permissions, and a successful protected write fails qualification.
    """
    def add(path, text):
        return '*** Begin Patch\n*** Add File: ' + path + '\n' + ''.join('+'+line+'\n' for line in text.splitlines()) + '*** End Patch'
    auxiliary = '/workspace/output/.native-edit-probe'
    patches = [add(output,content), add(auxiliary,'before\n'),
        '*** Begin Patch\n*** Update File: '+auxiliary+'\n@@\n-before\n+after\n*** End Patch',
        '*** Begin Patch\n*** Delete File: '+auxiliary+'\n*** End Patch',
        add('/workspace/input/.native-edit-must-remain-absent','must not be written\n')]
    return [*[{'tool':'apply_patch','input':patch,'expect_failure':index == 4} for index,patch in enumerate(patches)], FILE_EDIT_CHECK]


# Harbor public environment import hook composes the two existing lifecycle hooks:
# trusted gh startup before any agent work, then the qualified external CLI boundary.
from aeb_gh_fixture.backend import TrustedGhEnvironment


def initializer_upload_command(raw, target):
    require(target in ('/opt/aeb-gh/initialize.py', '/opt/aeb-gh/approved.json') and len(raw) <= 65536,
            'Unapproved gh initializer transport')
    # Docker cp can retain the operator uid. Write as the existing root user
    # instead; no capabilities, ownership changes or wider permissions are added.
    source = r"""import base64, os, stat, sys
raw = base64.b64decode(sys.argv[1], validate=True)
path = sys.argv[2]
try:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
except FileExistsError:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        assert stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o600
        assert stream.read(65537) == raw
else:
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
"""
    return 'python3 -I -c ' + shlex.quote(source) + ' ' + shlex.quote(base64.b64encode(raw).decode()) + ' ' + shlex.quote(target)


VERIFIER_UPLOAD_SCRIPT = r"""import base64, json, os, re, stat, sys
from pathlib import Path
payload = sys.stdin.buffer.read(16*1024*1024 + 1)
assert len(payload) <= 16*1024*1024
files = json.loads(payload)
assert isinstance(files, dict) and 0 < len(files) <= 1000
base = Path('/tests')
assert base.resolve() == base.absolute() and not base.is_symlink()
base.mkdir(mode=0o700, exist_ok=True)
base.chmod(0o700)
assert base.stat().st_uid == os.geteuid()
for name, encoded in files.items():
    assert isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*', name)
    assert not any(part in ('.', '..') for part in Path(name).parts)
    raw = base64.b64decode(encoded, validate=True)
    target = base / name
    for directory in reversed(target.parent.relative_to(base).parents):
        parent = base / directory
        assert not parent.is_symlink()
        parent.mkdir(mode=0o700, exist_ok=True)
    assert not target.parent.is_symlink()
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    assert target.parent.resolve() == target.parent.absolute()
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            assert stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o600
            assert stream.read(len(raw)+1) == raw
    else:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
"""


class CampaignGhEnvironment(PilotEnvironment, TrustedGhEnvironment):
    async def upload_dir(self, source_dir, target_dir):
        if str(target_dir) != '/tests':
            return await super().upload_dir(source_dir, target_dir)
        import skill_reports as reports
        from skill_evidence import read_bytes
        source = Path(source_dir).absolute()
        require(source == self.environment_dir.parent / 'tests', 'Unapproved verifier source')
        files = {p.relative_to(source).as_posix():base64.b64encode(read_bytes(p, limit=8*1024*1024)).decode()
                 for p in reports.regular_tree(source)}
        payload = json.dumps(files).encode()
        require(len(payload) <= 16*1024*1024, 'Verifier transport limit')
        result = await self._run_docker_compose_command(
            ['exec', '-T', '-u', 'root', 'main', 'python3', '-I', '-c', VERIFIER_UPLOAD_SCRIPT],
            check=False, stdin_data=payload, timeout_sec=30)
        require(result.return_code == 0, 'Cannot transport private verifier files')

    async def upload_file(self, source_path, target_path):
        if target_path not in ('/opt/aeb-gh/initialize.py', '/opt/aeb-gh/approved.json'):
            return await super().upload_file(source_path, target_path)
        from aeb_gh_fixture.manifest import regular
        raw = regular(Path(source_path).absolute())
        result = await self.exec(user='root', command=initializer_upload_command(raw, target_path))
        require(result.return_code == 0, 'Cannot transport approved gh initializer')

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
    if mode in ('probe', 'experiment-probe', 'live'):
        text = text.replace('network_mode = "public"', 'network_mode = "allowlist"\nallowed_hosts = ["api.openai.com"]')
    config.write_text(text)
    if mode in ('probe', 'experiment-probe', 'live'):
        from codex_pilot_runtime import prepare_cli
        (native / 'environment/build').mkdir(exist_ok=True)
        # Reuse the already-qualified curl package version and snapshot. The gh
        # fixture image has no curl; the Pester image already satisfies this pin.
        with (native / 'environment/Dockerfile').open('a') as stream:
            stream.write('RUN command -v curl >/dev/null || (apt-get update --error-on=any -o Acquire::Retries=3 -o Acquire::https::Timeout=30 && apt-get install -y --no-install-recommends curl=8.14.1-2+deb13u7 && rm -rf /var/lib/apt/lists/*)\n')
        prepare_cli(native)


def agent_config(task, mode, control, runtime, present):
    if mode in ('oracle','replay'):
        return {'name': 'oracle'}
    return {'import_path': 'evaluation_codex:CampaignCodex', 'model_name': runtime['model'],
            'kwargs': {'campaign_definition': task.member, 'control': control, 'present': present, **({'live': True} if mode == 'live' else {})}}


def submission_path(trial, output):
    from harbor.models.task.artifacts import source_host_path
    return source_host_path(trial / 'artifacts', '/logs/artifacts') / 'submitted' / output


def native_observation(trial, native, present, row, rows, *, output, live=False):
    import skill_reports as reports
    audits = list(trial.rglob('pilot-runtime.json'))
    require(len(audits) == 1, 'Missing runtime observation')
    audit = reports.read_json(audits[0]); row['runtime_observation'] = audit
    from codex_pilot_contract import configuration
    require(audit['cleanup'] == 'complete' and audit['boundary_before']['policy_sha256'] == audit['boundary_after']['policy_sha256']
        and audit['effective_config'] == configuration(None if live else 'http://127.0.0.1:8765/v1')
        and audit['prompt_sha256'] == hashlib.sha256((native / 'instruction.md').read_bytes()).hexdigest()
        and audit['skill_deployed'] == present, 'Runtime identity or cleanup drift')
    finals = list(trial.rglob('pilot-final-policy.json'))
    require(len(finals) == 1 and reports.read_json(finals[0])['policy_sha256'] == audit['boundary_before']['policy_sha256'],
            'Missing final policy or identity drift')
    if not live:
        probes = list(trial.rglob('probe.json'))
        require(len(probes) == 1, 'Missing non-forwarding request observation')
        probe = reports.read_json(probes[0])
        from codex_pilot_contract import PROFILE
        require(probe.get('model') == PROFILE['model'] and probe.get('reasoning', {}).get('effort') == PROFILE['reasoning_effort']
                and probe.get('requests') == 2, 'Observed CLI model/request drift')
    from skill_evidence import read_bytes
    submitted = read_bytes(submission_path(trial, output), limit=65536)
    receipts = list(trial.rglob('pilot-produced-submission.json'))
    require(len(receipts) == 1, 'Missing submitted artifact receipt')
    receipt = reports.read_json(receipts[0])
    require(receipt == {'sha256':hashlib.sha256(submitted).hexdigest(), 'bytes':len(submitted)},
            'Retained submission differs from native produced artifact')
    from skillevaluator.utils.redaction import redact_sensitive_text
    require(redact_sensitive_text(submitted.decode()) == submitted.decode(), 'Submission needs protected retention')
    row['submission'] = dict(receipt, file=output)
    row['skill_access'] = skill_access(trial, present, native)
    row['agent_id'] = audit['boundary_before']['agent_id']
    require(not any(r is not row and r.get('agent_id') == row['agent_id'] for r in rows), 'Reused agent environment')


def manifest(directory):
    import skill_reports as reports
    return {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in reports.regular_tree(directory)}


def usage(trial, mode):
    import skill_reports as reports
    from codex_pilot_runtime import usage_record
    if mode in ('oracle','replay'):
        return {'estimated_usd': 0, 'billing': 'oracle fixture; no model inference or billing',
                'n_input_tokens': None, 'n_cache_tokens': None, 'n_output_tokens': None}
    if not (trial / 'result.json').exists():
        return {'estimated_usd': None, 'billing': 'missing native usage'}
    return usage_record(reports.read_json(trial / 'result.json'), probe=mode != 'live')


def validate_members(members, mode):
    if mode not in ('probe', 'experiment-probe', 'live'):
        return
    for filename in ('codex_pilot_stub.py', 'codex_pilot_probe.py'):
        digest = 'sha256:' + hashlib.sha256((ROOT / '.github/scripts' / filename).read_bytes()).hexdigest()
        require(members.get('environment/build/' + filename) == digest, 'Unapproved staged runtime helper')



RETAINED_MEMBERS = ('pilot-runtime.json', 'pilot-final-policy.json', 'docker-observation.json',
                    'probe.json', 'native-file-edit-probe.json', 'observation-injection.json', 'codex.txt', 'trajectory.json', 'task-boundary.json', 'pilot-produced-submission.json')


def skill_access(trial, present, native):
    """Successful full SKILL.md output is access evidence only; absence is unknown.

    This conservative observation does not infer activation from command text.
    Other read forms or truncated outputs can remain unobserved.
    """
    import skill_reports as reports
    trajectories = list(trial.rglob('trajectory.json'))
    require(len(trajectories) == 1, 'Missing native trajectory')
    value = reports.read_json(trajectories[0])
    skill = next((p for p in (native / 'environment/skills').glob('*/SKILL.md')), None)
    expected = skill.read_text().strip() if present and skill else None
    logs = list(trial.rglob('codex.txt'))
    require(len(logs) == 1, 'Missing native access observation')
    events = []
    for line in logs[0].read_text().splitlines():
        try: events.append(json.loads(line))
        except ValueError: continue
    observed = bool(expected and any(event.get('type') == 'item.completed'
        and event.get('item', {}).get('type') == 'command_execution'
        and event['item'].get('exit_code') == 0
        and expected in event['item'].get('aggregated_output', '') for event in events))
    return {'successful_full_read': True if observed else None, 'deployed': present,
            'interpretation': 'access only; no task quality or benefit implied'}


def fixture_environment(task, fixture, row):
    control = task.fixture_control(fixture, row)
    result = {'AEB_CAMPAIGN_CONTROL':control, 'AEB_PILOT_SCENARIO':'interruption' if fixture == 'interruption' else 'success'}
    if fixture in ('missing-evidence', 'unsupported-runtime'):
        result['AEB_CAMPAIGN_OBSERVATION_FIXTURE'] = fixture
    return result
