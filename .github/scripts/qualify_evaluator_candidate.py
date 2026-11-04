#!/usr/bin/env python3
"""Opt-in, inference-free evidence qualification; never select production pins."""

import argparse
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile


REVISION = 'f878f99a9cd4a85dd04043feb43e5bd6a777f64b'
PINS = {'skillevaluator': '0.7.2', 'harbor': '0.24.0', 'openai': '2.44.0',
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
])
result = unittest.TextTestRunner(verbosity=2).run(suite)
payload = dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
               skipped=len(result.skipped), network_attempts=network,
               success=result.wasSuccessful() and not network,
               failure_names=[test.id() for test, _ in result.failures + result.errors])
result_path.write_text(json.dumps(payload, indent=2) + '\\n')
raise SystemExit(0 if payload['success'] else 1)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Clean checkout of the exact candidate revision')
    parser.add_argument('--output', type=Path, required=True, help='New persistent evidence directory outside both checkouts')
    parser.add_argument('--unpatched', action='store_true', help='Measure failing-before controls against pristine source')
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[2]
    source, output = args.source.resolve(strict=True), args.output.absolute()
    if output.resolve() != output or output.exists() or any(output.is_relative_to(root) for root in (project, source)):
        parser.error('Output must be a new resolved directory outside both checkouts')
    if sys.version_info[:2] != (3, 13):
        parser.error('Run with the candidate frozen Python 3.13 environment')
    versions = {name: importlib.metadata.version(name) for name in PINS}
    if versions != PINS:
        parser.error('Candidate frozen dependency versions do not match')
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
                                                'test_evaluator_candidate.py')},
                'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'production_pins_changed': False}
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
    print(json.dumps({**metadata, 'result': json.loads((output / 'result.json').read_text())}))
    return returncode


if __name__ == '__main__':
    raise SystemExit(main())
