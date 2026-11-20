"""Codex deployment destinations and recipe for the opt-in resource contract."""
import hashlib
from pathlib import Path
import shlex

from evaluation_resources import SCHEMA, inventory_bytes, regular_bytes, validate_inventory

NATIVE_SKILLS = '/home/agent/.agents/skills'


def inventory(target, present, selections, inputs, *, native_skills=NATIVE_SKILLS):
    """Selections are task-owned exact files; layout is runtime-owned metadata."""
    files = []; directories = {'/workspace', '/workspace/input', '/workspace/output', '/workspace/skills', native_skills}
    for skill, members in selections.items():
        if skill == target and not present: continue
        for name, raw in members.items():
            for root in ('/workspace/skills', native_skills):
                path = root + '/' + skill + '/' + name
                directories.add(str(Path(path).parent))
                files.append({'source': 'environment/skills/' + skill + '/' + name, 'path': path,
                    'sha256': hashlib.sha256(raw).hexdigest(), 'role': 'target' if skill == target else 'discovery', 'skill': skill})
    for path, (source, raw) in inputs.items():
        files.append({'source': source, 'path': path, 'sha256': hashlib.sha256(raw).hexdigest(), 'role': 'input', 'skill': None})
    result = {'schema': SCHEMA, 'target': {'id': target, 'deployed': present},
              'files': sorted(files, key=lambda r: r['path']), 'directories': sorted(directories)}
    return validate_inventory(result)


def stage(native, resources, *, scripts):
    """Called from trusted task staging, before manifest capture/native execution."""
    for row in resources['files']:
        raw = regular_bytes(native / row['source'])
        if hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Staged resource differs from selected task input')
    (native / 'environment/resource-inventory.json').write_bytes(inventory_bytes(resources))
    build = native / 'environment/resource-build'; build.mkdir(exist_ok=True)
    for name in ('evaluation_resources.py', 'evaluation_resource_provision.py'):
        (build / name).write_bytes(regular_bytes(scripts / name))
    with (native / 'environment/Dockerfile').open('a') as stream:
        stream.write('COPY input/PERMISSIONS.md /workspace/AGENTS.md\n'
            'COPY resource-build/ /opt/aeb-resources/\n'
            'COPY resource-inventory.json /opt/aeb-resources/inventory.json\n'
            'RUN python3 -I /opt/aeb-resources/evaluation_resource_provision.py /opt/aeb-resources/inventory.json\n')

        # Upstream notices accompany installed skills. They are distribution
        # metadata, outside the task's agent-readable resource inventory.
        deployed = {row['skill'] for row in resources['files'] if row['role'] != 'input'}
        for skill in sorted(deployed | {resources['target']['id']}):
            source = Path('skills') / skill / 'LICENSE'
            if skill in deployed and regular_bytes(native / 'environment' / source) != regular_bytes(scripts.parents[1] / '.agents' / source):
                raise ValueError('Staged license differs from deployment')
            workspace = shlex.quote('/workspace/skills/' + skill)
            destination = shlex.quote(f'{NATIVE_SKILLS}/{skill}/LICENSE')
            # Both arms get the same recipe. An absent target stays absent.
            stream.write(f'RUN if test -d {workspace}; then '
                         f'install -m 0444 {workspace}/LICENSE {destination}; fi\n')


def registration_command(resources):
    """The successor uses root-provisioned copies, rather than overwriting them."""
    validate_inventory(resources)
    paths = sorted({r['path'] for r in resources['files'] if r['role'] != 'input'})
    return ' && '.join('test -r ' + shlex.quote(p) + ' && test ! -L ' + shlex.quote(p) for p in paths)
