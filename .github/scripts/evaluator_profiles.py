"""Producer identities are independent of artifact schema and scoring policy.

The candidate is diagnostic-only; historical evidence retains its original policy.
"""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

CANDIDATE = json.loads((Path(__file__).resolve().parents[1] / 'evals/evaluator-candidate.json').read_text())
NEXT = json.loads((Path(__file__).resolve().parents[1] / 'evals/evaluator-0.9.json').read_text())
RETAINED_NEXT = json.loads((Path(__file__).resolve().parents[1] / 'evals/evaluator-0.9-offline-v2.json').read_text())
ACCOUNTING = json.loads((Path(__file__).resolve().parents[1] / 'evals/evaluator-0.9-accounting-v1.json').read_text())
RETAINED_RELEASE_BENCHMARK = json.loads((Path(__file__).resolve().parents[1] / 'evals/evaluator-1.0.1-benchmark-candidate-v2.json').read_text())
RELEASE_BENCHMARK = json.loads((Path(__file__).resolve().parents[1] / 'evals/evaluator-1.0.1-benchmark-candidate-v3.json').read_text())
CANDIDATES = (CANDIDATE, NEXT, RETAINED_NEXT, ACCOUNTING, RELEASE_BENCHMARK, RETAINED_RELEASE_BENCHMARK)
BENCHMARK_ACCOUNTING = json.loads((Path(__file__).resolve().parents[1] / 'evals/benchmark-090-accounting-v1.json').read_text())


def candidate_revision(revision, *, producer_id=None, patch=None):
    return next((p for p in CANDIDATES if p['revision'] == revision
                 and (producer_id is None or p['id'] == producer_id)
                 and (patch is None or patch == 'sha256:' + p['patch_sha256'])), None)


def is_candidate(profile):
    return any(profile is p for p in CANDIDATES)


def by_version(version):
    if version in (None, '0.3.0'):
        return by_revision(HISTORICAL_REVISION)
    for profile in CANDIDATES:
        if profile['version'] == version:
            return profile
    raise ValueError('Unsupported native evaluator')


def owning_candidate():
    profile = by_version(importlib.metadata.version('skillevaluator'))
    if not is_candidate(profile):
        raise ValueError('Opt-in candidate owning runtime required')
    return profile


HISTORICAL_REVISION = 'ac0a04905100acdafc6c95829311a9739c340ff6'


def by_revision(revision):
    if revision == HISTORICAL_REVISION:
        return {'revision': revision, 'version': '0.3.0', 'harbor': '0.13.2', 'python': '3.13',
                'scoring': 'skill-evaluator-metric-mean-v1'}
    if candidate := candidate_revision(revision):
        return candidate
    raise ValueError('Unsupported native evaluator')


def runtime(versions, *, owning=False):
    if versions.get('skillevaluator') == RELEASE_BENCHMARK['version'] and 'producer_profile' in versions:
        from benchmark_native import NATIVE_PRODUCER, native_profile, native_versions

        if versions['producer_profile'] == NATIVE_PRODUCER:
            backend = next((p for p in (RELEASE_BENCHMARK, RETAINED_RELEASE_BENCHMARK)
                            if versions == native_versions(backend=p)), None)
            if backend is None:
                raise ValueError('Contradictory released benchmark runtime provenance')
            profile = native_profile(backend=backend)
            if owning:
                validate_install(profile)
            return profile
    by_version(versions.get('skillevaluator'))
    revision = versions.get('evaluator_revision')
    if revision is None and versions.get('skillevaluator') in (None, '0.3.0'):
        revision = HISTORICAL_REVISION
    profile = by_revision(revision)
    if is_candidate(profile):
        profile = next((p for p in CANDIDATES if p['revision'] == revision
                        and versions.get('codex_tool_surface') == p.get('codex_tool_surface')
                        and all(versions.get(key) == value for key, value in candidate_versions(p).items())), None)
        if profile is None:
            raise ValueError('Incomplete or contradictory candidate provenance')
    for key, expected in (('skillevaluator', profile['version']), ('harbor', profile['harbor'])):
        # Historical admission reconciles recorded Harbor metadata with its policy.
        # It did not require every retained report to use the current replay lock.
        if key == 'harbor' and not is_candidate(profile):
            continue
        if versions.get(key) is not None and versions[key] != expected:
            raise ValueError('Contradictory producer identity')
    if is_candidate(profile):
        expected = candidate_versions(profile)
        if any(versions.get(key) != value for key, value in expected.items()):
            raise ValueError('Incomplete or contradictory candidate provenance')
    if owning:
        validate_install(profile)
    return profile


def validate_install(profile):
    """Authenticate an installation against its separately selected producer pins."""
    if importlib.metadata.version('skillevaluator') != profile['version']:
        raise ValueError('Use the producer owning runtime for native normalization')
    if 'dependencies' in profile and ('.'.join(map(str,sys.version_info[:3])) != profile['python'] or
            any(importlib.metadata.version(k) != v for k,v in profile['dependencies'].items())):
        raise ValueError('Candidate owning dependencies differ')
    if profile.get('backend_source_digest'):
        backend = Path(importlib.metadata.distribution('aeb-gh-fixture').locate_file('aeb_gh_fixture'))
        members = list(backend.glob('*.py'))
        if len(members) > 20 or any(p.is_symlink() for p in members):
            raise ValueError('Unsafe candidate backend tree')
        files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in members}
        digest = 'sha256:' + hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if digest != profile['backend_source_digest']:
            raise ValueError('Candidate backend implementation differs')
        if surface := profile.get('codex_tool_surface'):
            catalog = backend / 'codex-catalog/models.json'
            if (catalog.parent.is_symlink() or catalog.is_symlink() or not catalog.is_file()
                    or hashlib.sha256(catalog.read_bytes()).hexdigest() != surface['catalog_sha256']):
                raise ValueError('Candidate Codex tool catalog differs')
    if 'source_tree_digest' in profile:
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


def candidate_versions(profile=None):
    p = CANDIDATE if profile is None else profile
    if not is_candidate(p):
        raise ValueError('Unsupported candidate profile')
    value = {'skillevaluator': p['version'], 'evaluator_revision': p['revision'], 'harbor': p['harbor'],
             'python': p['python'], 'lock_sha256': p['lock_sha256'], 'patch_sha256': p['patch_sha256']}
    if p.get('backend_source_digest'):
        value.update(backend_version=p['dependencies']['aeb-gh-fixture'],
                     backend_source_digest=p['backend_source_digest'], backend_wheel_sha256=p['backend_wheel_sha256'])
    if 'codex_tool_surface' in p:
        value['codex_tool_surface'] = p['codex_tool_surface'].copy()
    return value


def benchmark_profile(identifier):
    """Explicit offline evidence lookup, independent of execution selection."""
    from evaluator_090 import PROFILE
    if identifier == PROFILE['id']:
        return PROFILE
    if identifier == BENCHMARK_ACCOUNTING['id']:
        return BENCHMARK_ACCOUNTING
    raise ValueError('Unsupported behavioral evidence profile')
