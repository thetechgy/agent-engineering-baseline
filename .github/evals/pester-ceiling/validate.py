"""Bounded exploratory controls using the existing pinned Pester runner.

Local component evidence only, not native cohort admission or historical rescoring.
Optional retained submissions must come from the authenticated live archive.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SUPPORT = ROOT / '.github/evals/powershell-pester-6/support'
CASE = SUPPORT / 'cases/pester-004'


def classify(result):
    if result.get('status') != 'executed' or any(result.get(k) != 0 for k in (
        'skipped', 'not_run', 'inconclusive', 'failed_blocks', 'failed_containers'
    )) or result.get('total', 0) <= 0:
        return 'unavailable'
    if result['failed'] == 0 and result['passed'] == result['total']:
        return 'pass'
    if result['failed'] > 0 and result['assertion_failures'] == result['failed']:
        return 'assertion'
    return 'unavailable'


def run(payload, subject, manifest):
    # Only the known project-root literal changes in reviewed copies; originals stay intact.
    with tempfile.TemporaryDirectory(prefix='pester-ceiling-') as directory:
        workspace = Path(directory)
        (workspace / 'input').mkdir()
        (workspace / 'output').mkdir()
        (workspace / 'input/Subject.ps1').write_bytes(subject)
        candidate = workspace / 'output/Subject.Tests.ps1'
        candidate.write_bytes(payload.replace(b'/workspace', os.fsencode(directory)))
        command = [shutil.which('pwsh'), '-NoLogo', '-NoProfile', '-File', str(SUPPORT / 'Runner.ps1'),
                   '-Candidate', str(candidate), '-Profile', str(CASE / 'profile.json'),
                   '-Workspace', directory, '-PesterManifest', str(manifest)]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=40, check=True)
        result = json.loads(completed.stdout.strip().splitlines()[-1])
        return {'classification': classify(result), 'execution': result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pester-manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--retained-evidence', type=Path)
    args = parser.parse_args()
    if any(os.environ.get(k) for k in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'NVIDIA_API_KEY')):
        raise ValueError('Credential-free validation received model credentials')
    if args.output.exists():
        raise ValueError('Use a new evidence filename')
    subjects = {'reference': (CASE / 'reference/Subject.ps1').read_bytes()}
    subjects.update({p.stem: p.read_bytes() for p in sorted((CASE / 'mutants').glob('*.ps1'))})
    subjects['integer-result'] = (HERE / 'candidate/integer-result.ps1').read_bytes()
    controls = {name: (HERE / f'candidate/{name}.Tests.ps1').read_bytes()
                for name in ('identity', 'typed-classic', 'type-only')}
    controls['value-only'] = (SUPPORT / 'qualification/pester-004/inline.Tests.ps1').read_bytes()
    controls['broken-discovery'] = (CASE / 'input/Existing.Tests.ps1').read_bytes()
    rows = []
    for name, payload in controls.items():
        for variant, subject in subjects.items():
            expected = ('unavailable' if name == 'broken-discovery' else
                        'pass' if variant == 'reference' or
                        (name == 'type-only' and variant != 'integer-result') or
                        (name == 'value-only' and variant == 'integer-result') else 'assertion')
            observed = run(payload, subject, args.pester_manifest)
            rows.append({'control': name, 'variant': variant, 'expected': expected, **observed})
    diagnostic = []
    if args.retained_evidence:
        for receipt in json.loads((args.retained_evidence / 'submissions.json').read_text()):
            member = Path(receipt['member'])
            if member.is_absolute() or '..' in member.parts or member.parts[0] != 'submissions':
                raise ValueError('Unsafe submission member')
            if 'pester-004' not in member.as_posix():
                continue
            path = args.retained_evidence / member
            if any(p.is_symlink() for p in [path, *path.parents]):
                raise ValueError('Linked submission member')
            payload = path.read_bytes()
            if len(payload) != receipt['bytes'] or hashlib.sha256(payload).hexdigest() != receipt['sha256']:
                raise ValueError('Submission receipt mismatch')
            for variant in ('reference', 'integer-result'):
                diagnostic.append({'submission': receipt, 'variant': variant,
                                   **run(payload, subjects[variant], args.pester_manifest)})
    inputs = [SUPPORT / 'Runner.ps1', CASE / 'profile.json', Path(__file__), args.pester_manifest]
    identities = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    result = {'purpose': 'exploratory output-informed component checks; no historical grades changed',
              'inference': False, 'input_sha256': identities,
              'subject_sha256': {k: hashlib.sha256(v).hexdigest() for k, v in subjects.items()},
              'control_sha256': {k: hashlib.sha256(v).hexdigest() for k, v in controls.items()},
              'controls': rows, 'retained_diagnostic': diagnostic,
              'controls_match': all(r['classification'] == r['expected'] for r in rows)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(f"{len(rows)} control executions; {len(diagnostic)} exploratory submission executions")
    if not result['controls_match']:
        raise SystemExit('Unexpected control outcome; inspect retained evidence')


if __name__ == '__main__':
    main()
