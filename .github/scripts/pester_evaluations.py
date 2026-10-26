"""Pester fixture preparation only; native Harbor owns execution and collection."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import skill_reports as reports

NAME = 'powershell-pester-6'
OVERLAY = Path('.github/evals') / NAME
EXTRA_PACKAGES = {'libicu76': '76.1-4', 'curl': '8.14.1-2+deb13u5', 'ripgrep': '14.1.1-1+b4'}


def manifest(root):
    files = reports.regular_tree(root)
    reports.require(all(p.stat().st_nlink == 1 for p in files), 'Hard-linked evaluation input')
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def dataset(workspace):
    manifest(workspace / OVERLAY)
    data = reports.read_json(workspace / OVERLAY / 'evals/evals.json')
    reports.require(data['skill_name'] == NAME, 'Overlay identity mismatch')
    ids = [e['id'] for e in data['evals']]
    reports.require(ids and len(ids) == len(set(ids)), 'Invalid case identities')
    for entry in data['evals']:
        reports.require(entry['id'].startswith('pester-') and '/' not in entry['id']
                        and 'files' not in entry, 'Invalid overlay task inputs')
    return data['evals']


def dockerfile(*, verifier=False):
    build = reports.GH_TASK_BUILD
    packages = {**build['apt_packages'], **EXTRA_PACKAGES}
    sources = [f'deb [check-valid-until=no signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] '
               f'https://snapshot.debian.org/archive/{archive}/{build["apt_snapshot"]}/ {suite} main'
               for archive, suite in [('debian', 'trixie'), ('debian-security', 'trixie-security')]]
    apt = ' '.join(f'{key}={value}' for key, value in packages.items())
    lines = [f'FROM {build["base_image"]}',
             "RUN rm -f /etc/apt/sources.list.d/* && rm -rf /var/lib/apt/lists/* && "
             "printf '%s\\n' " + ' '.join("'" + source + "'" for source in sources) +
             ' > /etc/apt/sources.list && apt-get update --error-on=any && '
             f'apt-get install -y --no-install-recommends {apt} && rm -rf /var/lib/apt/lists/*',
             'COPY build/install-runtime.py /tmp/install-runtime.py',
             'RUN python3 -I /tmp/install-runtime.py && rm /tmp/install-runtime.py',
             'RUN useradd --create-home --uid 1000 agent && useradd --uid 53001 --no-create-home runner && '
             'mkdir -p /workspace/input /workspace/output && chown agent:agent /workspace/output',
             'ENV PSModulePath=/opt/pester/Modules',
             'ENV HOME=/home/agent',
             'ENV PATH=/opt/microsoft/powershell/7:/usr/local/bin:/usr/bin:/bin',
             'WORKDIR /workspace']
    if verifier:
        lines += ['COPY . /tests/', 'RUN chmod 700 /tests && chown root:root /workspace/output']
    return '\n'.join(lines) + '\n'


def stage(workspace, destination):
    source = reports.local_skill(workspace, NAME)
    before = manifest(source)
    reports.require(before == manifest(workspace / '.agents/skills' / NAME), 'Deployed local skill drift')
    entries = dataset(workspace)
    destination = destination.absolute()
    reports.require(destination.resolve() == destination and not destination.exists()
                    and not destination.is_relative_to(workspace), 'Unsafe evaluation bundle destination')
    destination.mkdir(parents=True)
    # Own a minimal repository boundary: no enclosing checkout, instructions,
    # remote, dependency cache, credentials, or overlay can enter repo context.
    subprocess.run(['git', 'init', '--quiet', '--template=', str(destination)], check=True,
                   env={k: v for k, v in os.environ.items() if not k.startswith('GIT_')})
    for relative in before:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, target)
    root = workspace / OVERLAY
    support = root / 'support'
    (destination / 'evals').mkdir()
    for filename in ('evals.json', 'config.yml'):
        shutil.copyfile(root / 'evals' / filename, destination / 'evals' / filename)
    native = destination / 'evals/harbor'
    native.mkdir()
    lines = ['[dataset]', 'name = "nvidia/pester-pilot"', '']
    for entry in entries:
        case = support / 'cases' / entry['id']
        task = native / entry['id']
        env = task / 'environment'
        tests = task / 'tests'
        env.mkdir(parents=True)
        tests.mkdir()
        shutil.copytree(case / 'input', env / 'input')
        shutil.copyfile(support / 'EXECUTION-PROFILE.md', env / 'input/EXECUTION-PROFILE.md')
        for context in (env, tests):
            (context / 'build').mkdir()
            shutil.copyfile(support / 'install-runtime.py', context / 'build/install-runtime.py')
        shutil.copyfile(root / 'evals/grader.py', tests / 'grader.py')
        shutil.copyfile(support / 'Runner.ps1', tests / 'Runner.ps1')
        (tests / 'case').mkdir()
        for filename in ('profile.json',):
            shutil.copyfile(case / filename, tests / 'case' / filename)
        for directory in ('reference', 'mutants'):
            shutil.copytree(case / directory, tests / 'case' / directory)
        (env / 'Dockerfile').write_text(dockerfile())
        (tests / 'Dockerfile').write_text(dockerfile(verifier=True))
        (task / 'instruction.md').write_text(entry['prompt'] + '\n')
        (task / 'task.toml').write_text(
            'schema_version = "1.3"\nartifacts = ["/workspace/output/Subject.Tests.ps1"]\n'
            '[metadata]\nentry_id = ' + json.dumps(entry['id']) + '\n'
            '[agent]\nuser = "agent"\ntimeout_sec = 300.0\n'
            '[verifier]\nuser = "root"\nenvironment_mode = "separate"\ntimeout_sec = 240.0\n'
            '[verifier.environment]\nnetwork_mode = "no-network"\ncpus = 2\nmemory_mb = 2048\n'
            '[environment]\nnetwork_mode = "public"\ncpus = 2\nmemory_mb = 2048\n'
            'workdir = "/workspace"\nskills_dir = "/workspace/skills"\n')
        lines += ['[[tasks]]', 'name = ' + json.dumps('nvidia/' + entry['id']), '']
    (native / 'dataset.toml').write_text('\n'.join(lines))
    reports.require(manifest(source) == before, 'Source changed during preparation')
    return destination
