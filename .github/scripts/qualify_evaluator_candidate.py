#!/usr/bin/env python3
"""Opt-in, inference-free evidence qualification; never select production pins."""

import argparse
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import os
import re
import stat
from pathlib import Path
import subprocess
import sys
import tarfile


REVISION = 'f878f99a9cd4a85dd04043feb43e5bd6a777f64b'
PINS = {'aeb-gh-fixture': '1.0.0', 'skillevaluator': '0.7.2', 'harbor': '0.24.0', 'openai': '2.44.0',
        'pydantic': '2.13.4', 'pydantic-core': '2.46.4',
        'typing-inspection': '0.4.2', 'litellm': '1.93.2'}
CHILD = '''
import json, os, sys, unittest
from pathlib import Path
network = []
def offline(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo'):
        network.append(event)
        raise PermissionError('Candidate qualification forbids network access')
sys.addaudithook(offline)
source, project, result_path = map(Path, sys.argv[1:])
sys.path[:0] = [str(source / 'src'), str(project / '.github/tests'), str(project / '.github/scripts')]
import skillevaluator
assert Path(skillevaluator.__file__).resolve().is_relative_to(source.resolve())
suite = unittest.defaultTestLoader.loadTestsFromNames([
    'test_grading_evidence.GradingEvidenceTests',
    'test_pester_evaluations.NativeStagingTests.test_native_runner_collector_and_report_do_not_score_unsupported_zero',
    'test_evaluator_candidate.CandidateEvidenceTests',
    'test_gh_initializer.InitializerTests',
])
result = unittest.TextTestRunner(verbosity=2).run(suite)
payload = dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
               skipped=len(result.skipped), network_attempts=network,
               success=result.wasSuccessful() and not network,
               failure_names=[test.id() for test, _ in result.failures + result.errors])
result_path.write_text(json.dumps(payload, indent=2) + '\\n')
raise SystemExit(0 if payload['success'] else 1)
'''


def native_compose_config(project):
    """Pass only setup-compose's hash-verified, credential-free plugin directory."""
    root = Path(os.environ.get('COMPOSE_PLUGIN_ROOT', ''))
    def require(condition):
        if not condition:
            raise ValueError('Reviewed Compose plugin required')
    require(root.is_absolute() and root.resolve() == root and not root.is_symlink()
            and os.environ.get('DOCKER_CONFIG') == str(root))
    require(root.is_dir() and {p.name for p in root.iterdir()} == {'cli-plugins'})
    directory = root / 'cli-plugins'
    require(not directory.is_symlink() and directory.is_dir()
            and {p.name for p in directory.iterdir()} == {'docker-compose'})
    binary = directory / 'docker-compose'
    info = binary.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 128 * 1024 * 1024)
    pins = re.findall(r'^compose_sha256=([0-9a-f]{64})$', (project / '.github/scripts/setup-compose.sh').read_text(), re.M)
    require(len(pins) == 1 and hashlib.sha256(binary.read_bytes()).hexdigest() == pins[0])
    return str(root)


def run_native(command, *, env, log):
    """Allow bounded teardown before forcibly ending a hung no-inference child."""
    with subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT) as process:
        try:
            return process.wait(timeout=2600)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            return 124
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Clean checkout of the exact candidate revision')
    parser.add_argument('--output', type=Path, required=True, help='New persistent evidence directory outside both checkouts')
    parser.add_argument('--unpatched', action='store_true', help='Measure failing-before controls against pristine source')
    parser.add_argument('--native-gh', action='store_true', help='Qualify all 24 gh cases in both arms using the trusted backend, without inference')
    parser.add_argument('--gh-arm', choices=('with_skill', 'without_skill'), help='Bound native gh qualification to one arm; adoption requires both')
    parser.add_argument('--adoption', action='store_true', help='Run available native gates and report every remaining adoption blocker; never promote implicitly')
    parser.add_argument('--native-pester', action='store_true', help='After the evidence controls, qualify native Pester packaging without inference')
    args = parser.parse_args()
    if args.adoption and args.gh_arm:
        parser.error('Adoption requires both native gh arms')
    if args.adoption:
        args.native_gh = args.native_pester = True
    if (args.native_pester or args.native_gh) and args.unpatched:
        parser.error('Native qualification requires the reviewed evidence patch')
    project = Path(__file__).resolve().parents[2]
    compose_error = False
    try:
        compose_config = native_compose_config(project) if args.native_pester or args.native_gh else None
    except (OSError, ValueError):
        compose_config = None
        compose_error = True
    source, output = args.source.resolve(strict=True), args.output.absolute()
    if output.resolve() != output or output.exists() or any(output.is_relative_to(root) for root in (project, source)):
        parser.error('Output must be a new resolved directory outside both checkouts')
    if sys.version_info[:2] != (3, 13):
        parser.error('Run with the candidate frozen Python 3.13 environment')
    versions = {name: importlib.metadata.version(name) for name in PINS}
    if versions != PINS:
        parser.error('Candidate frozen dependency versions do not match')
    backend = Path(importlib.util.find_spec('aeb_gh_fixture').origin).parent
    authored = project / '.github/evaluator-backends/aeb_gh_fixture'
    actual = {p.name: p.read_bytes() for p in backend.glob('*.py')}
    expected = {p.name: p.read_bytes() for p in authored.glob('*.py')}
    if actual != expected:
        parser.error('Installed backend differs from the reviewed source; rebuild using setup candidate')

    def git(*arguments):
        return subprocess.check_output(['git', '-C', str(source), *arguments])
    if git('rev-parse', 'HEAD').decode().strip() != REVISION:
        parser.error('Candidate source revision does not match')
    if git('diff', 'HEAD', '--', 'src', 'pyproject.toml', 'uv.lock') or git('ls-files', '--others', '--exclude-standard', '--', 'src'):
        parser.error('Candidate source or lock has local changes')
    patch = project / '.github/patches/skillevaluator-v0.7.2-evidence.patch'
    patch_bytes = patch.read_bytes()
    archive = git('archive', '--format=tar', 'HEAD', 'src')
    if len(archive) > 64 * 1024 * 1024:
        parser.error('Candidate source archive exceeds the qualification bound')
    with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
        members = bundle.getmembers()
        if len(members) > 10000 or any(not (m.isdir() or m.isfile()) for m in members):
            parser.error('Candidate source contains unsupported archive members')
        if any((m.name != 'src' and not m.name.startswith('src/')) or '..' in Path(m.name).parts for m in members):
            parser.error('Candidate source archive has an unsafe path')
        output.mkdir(mode=0o700, parents=True)
        snapshot = output / 'source'
        snapshot.mkdir()
        bundle.extractall(snapshot, filter='data')
    if not args.unpatched:
        subprocess.run(['git', 'apply', '--check', str(patch)], cwd=snapshot, check=True)
        subprocess.run(['git', 'apply', str(patch)], cwd=snapshot, check=True)
    home = output / 'empty-home'
    home.mkdir(mode=0o700)
    env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'HOME': str(home),
           'TMPDIR': os.environ.get('TMPDIR', '/tmp'), 'PYTHON_DOTENV_DISABLED': '1',
           'PYTHONDONTWRITEBYTECODE': '1', 'GRADING_PATCH_CHILD': '1', 'CANDIDATE_EVIDENCE_CHILD': '1',
           'SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE': str(output / 'provenance.key')}
    metadata = {'source_revision': REVISION, 'versions': versions, 'patched': not args.unpatched,
                'patch_sha256': hashlib.sha256(patch_bytes).hexdigest(),
                'lock_sha256': hashlib.sha256(git('show', 'HEAD:uv.lock')).hexdigest(),
                'control_sha256': {name: hashlib.sha256((project / '.github/tests' / name).read_bytes()).hexdigest()
                                   for name in ('test_grading_evidence.py', 'test_pester_evaluations.py',
                                                'test_evaluator_candidate.py', 'test_gh_initializer.py')},
                'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'production_pins_changed': False, 'inference': False, 'diagnostic_only': True,
                'backend_sources': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((project / '.github/evaluator-backends/aeb_gh_fixture').glob('*.py'))},
                'gh_harness_sha256': hashlib.sha256((project / '.github/scripts/gh_initializer_validation.py').read_bytes()).hexdigest(),
                'gh_staging_sha256': hashlib.sha256((project / '.github/scripts/gh_candidate.py').read_bytes()).hexdigest(),
                'backend_builder_sha256': hashlib.sha256((project / '.github/evaluator-backends/build_wheel.py').read_bytes()).hexdigest(),
                'native_harness_sha256': hashlib.sha256((project / '.github/scripts/pester_container_validation.py').read_bytes()).hexdigest()}
    (output / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    with (output / 'qualification.log').open('w') as log:
        try:
            process = subprocess.run([sys.executable, '-I', '-B', '-c', CHILD, str(snapshot), str(project), str(output / 'result.json')],
                                     env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180)
            returncode = process.returncode
        except subprocess.TimeoutExpired:
            returncode = 124
    if not (output / 'result.json').exists():
        (output / 'result.json').write_text(json.dumps({'success': False, 'error': 'Control process did not produce a terminal result'}) + '\n')
    metadata['returncode'] = returncode
    (output / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    if compose_error:
        metadata['native_prerequisite'] = 'reviewed_compose_unavailable'
        metadata['returncode'] = returncode = returncode or 2
        (output / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    if returncode == 0 and args.native_gh:
        native_env = {**env, 'DOCKER_CONFIG': compose_config, 'RUNNER_TEMP': str(output),
                      'PATH': str(Path(sys.executable).parent) + os.pathsep + env['PATH']}
        launcher = ('import sys; sys.path[:0] = sys.argv[1:3]; '
                    'from gh_initializer_validation import main; main(sys.argv[3], sys.argv[4] or None)')
        with (output / 'native-gh.log').open('w') as log:
            try:
                returncode = run_native([sys.executable, '-I', '-B', '-c', launcher, str(snapshot / 'src'),
                    str(project / '.github/scripts'), str(output / 'native-gh.json'), args.gh_arm or ''], env=native_env,
                    log=log)
            except subprocess.TimeoutExpired:
                returncode = 124
        metadata['returncode'] = returncode
        metadata['native_gh'] = {'success': returncode == 0, 'returncode': returncode, 'diagnostic_only': True}
        (output / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    if returncode == 0 and args.native_pester:
        native_env = {**env, 'DOCKER_CONFIG': compose_config, 'PYTHONPATH': str(snapshot / 'src'), 'RUNNER_TEMP': str(output),
                      'PATH': str(Path(sys.executable).parent) + os.pathsep + env['PATH']}
        launcher = ('import sys; sys.path[:0] = sys.argv[1:3]; '
                    'from pester_container_validation import main; '
                    'main(candidate=True, artifact=sys.argv[3])')
        with (output / 'native-pester.log').open('w') as log:
            try:
                returncode = run_native([sys.executable, '-I', '-B', '-c', launcher, str(snapshot / 'src'),
                    str(project / '.github/scripts'), str(output / 'native-pester')], env=native_env,
                    log=log)
            except subprocess.TimeoutExpired:
                returncode = 124
        metadata['returncode'] = returncode
        metadata['native_pester'] = {'success': returncode == 0, 'returncode': returncode, 'diagnostic_only': True}
        (output / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    if args.adoption:
        # No green verdict while required migration boundaries lack evidence.
        blockers = ['podman_standard_collection_recovery', 'codex_setup_only_installed_version',
                    'dual_runtime_reporting_and_public_replay', 'historical_original_tooling_replay',
                    'new_profiles_provenance_and_publisher_admission', 'upstream_differential_selection']
        if not metadata.get('native_gh', {}).get('success'):
            blockers.append('native_gh_48_outcomes')
        if not metadata.get('native_pester', {}).get('success'):
            blockers.append('candidate_pester_52_outcomes')
        metadata['adoption'] = {'ready': False, 'blockers': blockers, 'inference': False}
        metadata['returncode'] = returncode = returncode or 1
        (output / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps({**metadata, 'result': json.loads((output / 'result.json').read_text())}))
    return returncode


if __name__ == '__main__':
    raise SystemExit(main())
