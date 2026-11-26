#!/usr/bin/env python3
"""Qualify the released Harbor backend dispatch and matched gh-007 startup without inference."""

import argparse
import asyncio
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from unittest.mock import patch

from aeb_gh_fixture import MANIFEST_ENV, MODE
from aeb_gh_fixture.backend import TrustedGhEnvironment, require_runtime
from aeb_gh_fixture.manifest import approve, write_manifest
from harbor.environments.factory import EnvironmentFactory
from harbor.models.task.task import Task
from harbor.models.trial.paths import TrialPaths
from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks
from skillevaluator.tier3.harbor.runner import build_harbor_run_command

import gh_candidate
import gh_evaluations as gh
from gh_initializer_validation import docker, startup_attempt
import evaluator_profiles as profiles
import static_evaluator


async def check_containment(environment):
    agent = await environment.exec('id -u', user='agent', timeout_sec=5)
    if agent.return_code or agent.stdout.strip() != '1000':
        raise RuntimeError('Unexpected gh fixture agent identity')
    paths = ('/opt/gh-eval/state/case.json', '/opt/gh-eval/state/audit.jsonl', '/opt/aeb-gh/approved.json')
    for path in paths:
        root = await environment.exec(f'test -r {path}', user='root', timeout_sec=5)
        agent = await environment.exec(f'test ! -r {path} && test ! -w {path}', user='agent', timeout_sec=5)
        if root.return_code or agent.return_code:
            raise RuntimeError('gh resource containment check failed')
    return 'verified'


async def run_startup(task, paths, import_path, row, save):
    name = 'aeb-gh101-' + uuid.uuid4().hex[:16]
    native = Task(task)
    environment = EnvironmentFactory.create_environment_from_import_path(
        import_path, task / 'environment', name, name, paths, native.config.environment,
        mounts=[], network_policy=native.config.environment.resolve_baseline())
    if type(environment) is not TrustedGhEnvironment:
        raise RuntimeError('Unexpected Harbor environment implementation')
    environment.default_user = 'agent'

    def image():
        ids = docker('ps', '-aq', '--filter', 'label=com.docker.compose.project=' + name).split()
        if len(ids) != 1:
            raise RuntimeError('Unexpected gh startup container population')
        observed = json.loads(docker('inspect', '--format',
            '{"image":{{json .Image}},"healthy":{{json .State.Health.Status}}}', ids[0]))
        if observed['healthy'] != 'healthy' or not re.fullmatch(r'sha256:[0-9a-f]{64}', observed['image']):
            raise RuntimeError('Unexpected staged environment image or readiness')
        return observed

    def cleanup_check():
        for args in (('ps', '-aq'), ('network', 'ls', '-q')):
            if docker(*args, '--filter', 'label=com.docker.compose.project=' + name).strip():
                raise RuntimeError('gh startup resources survived teardown')

    def retain(value):
        row.update(value)
        save()

    await startup_attempt(environment, inspect_image=image, cleanup_check=cleanup_check,
                          retain=retain, check_containment=check_containment)


def qualify(output, *, stage_only):
    profiles.validate_install(profiles.CURRENT_RELEASE)
    require_runtime()
    output = output.absolute()
    if output.resolve() != output or output.is_relative_to(gh.ROOT) or output.exists():
        raise ValueError('Qualification requires a new receipt outside the checkout')
    if any(os.environ.get(key) for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'NVIDIA_API_KEY',
                                           'COPILOT_GITHUB_TOKEN', 'GITHUB_TOKEN', 'GH_TOKEN')):
        raise RuntimeError('Qualification requires a credential-free environment')
    if not stage_only and (not shutil.which('docker') or
                           docker('compose', 'version', '--short').strip() != gh.reports.POLICY['docker_compose']):
        raise RuntimeError('Qualification requires Docker and the pinned Compose')
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=gh.ROOT, text=True).strip()
    clean = not subprocess.check_output(['git', 'status', '--porcelain'], cwd=gh.ROOT, text=True)
    if os.environ.get('GITHUB_ACTIONS') == 'true' and (not clean or os.environ.get('GITHUB_SHA') != source):
        raise RuntimeError('Hosted startup requires the exact workflow revision')
    status = {'schema': 1, 'revision': source, 'inference': False, 'stage_only': stage_only,
              'worktree_clean': clean,
              'evaluator_revision': static_evaluator.REVISION, 'lock_sha256': static_evaluator.LOCK,
              'versions': {name: importlib.metadata.version(name) for name in
                           ('skillevaluator', 'harbor', 'aeb-gh-fixture')}, 'complete': False, 'attempts': []}
    with output.open('x') as stream:
        def save():
            stream.seek(0)
            json.dump(status, stream, sort_keys=True, indent=2)
            stream.write('\n')
            stream.truncate()
            stream.flush()
        save()
        with tempfile.TemporaryDirectory(prefix='gh101-') as temporary:
            root = Path(temporary)
            bundle = gh_candidate.stage(gh.ROOT, root / 'bundle/gh', ['gh-007'], fixture=True)
            tasks = {}
            for present, arm in ((True, 'with_skill'), (False, 'without_skill')):
                task, = stage_native_harbor_tasks(bundle, root / 'tasks' / arm, with_skill=present,
                    grading_mode='custom_only', workspace_mode='group',
                    workspace_skill_paths=[bundle.parent / gh.COMPETING])
                tasks[arm] = task
                native = Task(task)
                dockerfile = (task / 'environment/Dockerfile').read_text().splitlines()
                if ('ENTRYPOINT []' not in dockerfile or 'HEALTHCHECK NONE' not in dockerfile
                        or native.config.environment.healthcheck is not None):
                    raise RuntimeError('Released staging did not suppress authored startup')
            for arm, task in tasks.items():
                manifest = write_manifest(root / ('operator-' + arm), [task], staged_roots=[bundle, root / 'tasks'])
                identity, _ = approve(manifest, task)
                other = next(candidate for candidate in tasks.values() if candidate != task)
                try:
                    approve(manifest, other)
                except ValueError:
                    pass
                else:
                    raise RuntimeError('Operator manifest admitted the wrong arm')
                with patch.dict(os.environ, {MANIFEST_ENV: str(manifest)}):
                    command = build_harbor_run_command(dataset_path=task.parent, agent='codex',
                        job_name='gh101-startup', env_mode=MODE, disable_verification=True)
                    import_path = command[command.index('--env') + 1]
                    if import_path != 'aeb_gh_fixture.backend:TrustedGhEnvironment':
                        raise RuntimeError('Released evaluator did not select the trusted backend')
                    row = {key: identity[key] for key in ('case', 'arm', 'checksum', 'context')}
                    row.update(dispatch=import_path, cross_arm_rejected=True, status='staged')
                    status['attempts'].append(row)
                    save()
                    if not stage_only:
                        paths = TrialPaths(root / ('trial-' + arm))
                        paths.mkdir()
                        asyncio.run(run_startup(task, paths, import_path, row, save))
        status['complete'] = True
        save()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--stage-only', action='store_true')
    args = parser.parse_args()
    qualify(args.output, stage_only=args.stage_only)
