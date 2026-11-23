#!/usr/bin/env python3
"""Isolated static quality setup and authored-input evidence for CI."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import qualify_static_evaluator as qualification
import skill_evidence as evidence
import static_evaluator

ROOT = evidence.ROOT
HISTORY_PATCH = ROOT / '.github/scripts/static-quality-history.patch'


def write_versions(tools):
    runtime = dict(evidence.SCANNER_RUNTIME_CURRENT_UNPATCHED,
                   evaluator_revision=static_evaluator.REVISION, semgrep_lock=static_evaluator.SEMGREP_LOCK)
    versions = dict(static_evaluator.VERSIONS, scanners=runtime['versions'],
                    skillspector_revision=runtime['skillspector_revision'], scanner_runtime=runtime)
    static_evaluator.validate_owner(versions)
    for package, owner in (('semgrep', 'semgrep'), ('skillspector', 'skillspector'),
                           ('bandit', 'evaluator'), ('pip-audit', 'evaluator')):
        installed = evidence.read_json(tools / 'dependencies' / (owner + '.json'))
        evidence.require(any(row['name'] == package and row['version'] == versions['scanners'][package]
                             for row in installed), 'Unexpected static dependency version: ' + package)
    leaks = subprocess.check_output([tools / 'bin/gitleaks', 'version'], text=True, timeout=30)
    evidence.require(leaks.strip() == versions['scanners']['gitleaks'], 'Unexpected Gitleaks version')
    for key, path in (('skillspector_lock', tools / 'skillspector/uv.lock'),
                      ('semgrep_lock', ROOT / '.github/requirements/semgrep.txt')):
        evidence.require(evidence.digest_bytes(path.read_bytes()) == runtime[key], 'Unexpected scanner lock: ' + key)
    (tools / 'versions.json').write_bytes(evidence.encoded(versions))


def authored_input(scripts, output, runner):
    env = {key: os.environ[key] for key in ('PATH', 'TMPDIR', 'LANG') if key in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE='1', SEMGREP_SEND_METRICS='off', SEMGREP_ENABLE_VERSION_CHECK='0')
    owner = tuple(Path(os.environ[key]) for key in ('SKILL_QUALITY_PYTHON', 'SKILL_QUALITY_TOOLS'))
    versions = evidence.read_json(owner[1] / 'versions.json')
    with tempfile.TemporaryDirectory(prefix='static-authored-input-', dir=runner) as temporary:
        scratch = Path(temporary)
        workspace = scratch / 'workspace'
        home = scratch / 'home'
        home.mkdir()
        env['HOME'] = str(home)
        skill = qualification.fixture(workspace, env)
        (skill / qualification.AUTHORED).write_bytes(qualification.MARKER + b'\n')
        qualification.run(['git', 'add', '.'], env, cwd=workspace, diagnostic='Control input staging failed')
        qualification.run(['git', '-c', 'user.name=Scanner Control', '-c', 'user.email=control@example.invalid',
                           'commit', '--quiet', '-m', 'Authored evaluation input'], env, cwd=workspace,
                          diagnostic='Control input commit failed')
        native = qualification.collect(scripts, owner, workspace, scratch / 'native',
                                       qualification.CONTROL_REPOSITORY, env)
        (native / 'versions.json').write_bytes(evidence.encoded(dict(versions, fixture='synthetic')))
        staged = scratch / 'published'
        public, page = qualification.report(scripts, owner, workspace, native, staged, env)
        html = page.read_text()
        result = qualification.observe(native, public, html)[qualification.CONTROL]
        candidate = versions['skillevaluator'] == static_evaluator.VERSION
        expected = [(qualification.AUTHORED, 1)] if candidate else []
        evidence.require(result['secret_locations'] == expected
                         and result['secrets_status'] == ('failed' if candidate else 'passed')
                         and not result['secrets_incomplete_scans'] and result['gitleaks'] == '8.30.1',
                         'Unexpected authored-input Gitleaks outcome')
        if candidate:
            evidence.require(qualification.AUTHORED + ':1' in html, 'Rendered authored-input line missing')
        evidence.require(not qualification.run(['git', 'status', '--porcelain', '--untracked-files=all', '--ignored'],
                                               env, cwd=workspace, diagnostic='Control source integrity check failed'),
                         'Static control mutated its input')
        qualification.retain(native, staged)
        (staged / 'receipt.json').write_bytes(evidence.encoded(result))
        qualification.require_redaction(staged)
        shutil.copytree(staged, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('tools')
    commands.add_parser('versions').add_argument('--tools', required=True, type=Path)
    commands.add_parser('authored-input').add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.command == 'versions':
        write_versions(args.tools)
        return
    runner = Path(os.environ['RUNNER_TEMP']).resolve(strict=True)
    evidence.require(not runner.is_relative_to(ROOT), 'Static tooling must be outside the checkout')
    if args.command == 'tools':
        env = os.environ.copy()
        scripts = qualification.reporting_tools(runner, env)
        qualification.run(['git', 'apply', HISTORY_PATCH], env, cwd=scripts.parents[1],
                          diagnostic='Could not install static history compatibility')
        print(scripts)
    else:
        authored_input(runner / 'reporting-tools/.github/scripts', args.output, runner)


if __name__ == '__main__':
    main()
