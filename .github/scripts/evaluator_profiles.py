"""Producer identities are independent of artifact schema and scoring policy.

The candidate is diagnostic-only; historical evidence retains its original policy.
"""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

CANDIDATE = json.loads((Path(__file__).resolve().parents[1] / 'evals/evaluator-candidate.json').read_text())
HISTORICAL_REVISION = 'ac0a04905100acdafc6c95829311a9739c340ff6'


def by_revision(revision):
    if revision == HISTORICAL_REVISION:
        return {'revision': revision, 'version': '0.3.0', 'harbor': '0.13.2', 'python': '3.13',
                'scoring': 'skill-evaluator-metric-mean-v1'}
    if revision == CANDIDATE['revision']:
        return CANDIDATE
    raise ValueError('Unsupported native evaluator')


def runtime(versions, *, owning=False):
    revision = versions.get('evaluator_revision')
    if revision is None and versions.get('skillevaluator') in (None, '0.3.0'):
        revision = HISTORICAL_REVISION
    profile = by_revision(revision)
    for key, expected in (('skillevaluator', profile['version']), ('harbor', profile['harbor'])):
        if versions.get(key) is not None and versions[key] != expected:
            raise ValueError('Contradictory producer identity')
    if profile is CANDIDATE:
        expected = {'skillevaluator': profile['version'], 'evaluator_revision': profile['revision'],
                    'harbor': profile['harbor'], 'python': profile['python'],
                    'lock_sha256': profile['lock_sha256'], 'patch_sha256': profile['patch_sha256']}
        if any(versions.get(key) != value for key, value in expected.items()):
            raise ValueError('Incomplete or contradictory candidate provenance')
    if owning:
        if importlib.metadata.version('skillevaluator') != profile['version']:
            raise ValueError('Use the producer owning runtime for native normalization')
        if profile is CANDIDATE and ('.'.join(map(str,sys.version_info[:3])) != profile['python'] or
                any(importlib.metadata.version(k) != v for k,v in profile['dependencies'].items())):
            raise ValueError('Candidate owning dependencies differ')
        if profile is CANDIDATE:
            import skillevaluator
            package = Path(skillevaluator.__file__).resolve().parent
            source = package.parents[1]
            members = [f for f in package.rglob('*') if f.is_file() and '__pycache__' not in f.parts]
            if len(members) > 2000 or any(f.is_symlink() for f in members):
                raise ValueError('Unsafe candidate implementation tree')
            files = {f.relative_to(source / 'src').as_posix(): hashlib.sha256(f.read_bytes()).hexdigest() for f in members}
            digest = 'sha256:' + hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            if digest != profile['source_tree_digest'] or hashlib.sha256((source / 'uv.lock').read_bytes()).hexdigest() != profile['lock_sha256']:
                raise ValueError('Candidate implementation or lock differs')
    return profile


def candidate_versions():
    p = CANDIDATE
    return {'skillevaluator': p['version'], 'evaluator_revision': p['revision'], 'harbor': p['harbor'],
            'python': p['python'], 'lock_sha256': p['lock_sha256'], 'patch_sha256': p['patch_sha256']}
