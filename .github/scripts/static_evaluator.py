"""The released Tier 1 producer identity and its owning runtime."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform

VERSION = '1.2.1'
PRODUCER = 'skillevaluator-1.2.1-static-v1'
REVISION = 'f7fcd35d79d0506fadbd79f2b3ff384c98bd10f3'
LOCK = '817d00c49588a09db6e47ce9295b1d5339642246dc529daa26c6ac949a21a942'
SOURCE = '607c05702f5e08f2cc2954a03e003002e98a97c40fe06cdd63a80e6e03079da2'
SCANNER_CONTRACT_SOURCE = 'debd689155e56cf3d4fc8c4a590c5643ef8395c53791aa020ee66923ff134806'
SCANNER_PATCH = '6873c37c0ca482b2222e2774700b6982302e74fccfb805192bd54b0447e860a9'
SEMGREP_LOCK = 'sha256:f34553471c8d6ad88e2139716a3e584de63b1dddecbe085c44a7a2a33db1199d'
VERSIONS = {'skillevaluator': VERSION, 'evaluator_revision': REVISION, 'python': '3.14.10',
            'harbor': '0.25.0', 'lock_sha256': LOCK, 'producer_profile': PRODUCER}
RETAINED = {'skillevaluator': '1.0.1', 'evaluator_revision': '914c15cb3f31562ccffdc9a7166002a87ed2ce1e',
            'python': '3.14.10', 'harbor': '0.25.0',
            'lock_sha256': 'c49a8340c7312a8396c34be64d0062e8a591f201202c890b7563265958e3f364',
            'producer_profile': 'skillevaluator-1.0.1-static-v1'}
STATIC_OWNERS = {entry['evaluator_revision']: entry for entry in (VERSIONS, RETAINED)}
STATIC_PRODUCERS = tuple(entry['producer_profile'] for entry in STATIC_OWNERS.values())
SOURCE_PINS = {
    VERSION: (SOURCE, SCANNER_CONTRACT_SOURCE),
    '1.0.1': ('7dd63bd0286d9cad9921c1739de193fd55ad407f67d1b6a8476e2fd32544920b',
              'd2e0773029fb335a44db0775c839cb7b1f3cb924e177522cc79f07518615922a'),
}


def validate_install(*, python=VERSIONS['python'], scanner_contracts=False, owner=VERSIONS):
    """Authenticate the installed release, interpreter and lock."""
    import skillevaluator

    version = owner['skillevaluator']
    if platform.python_version() != python or importlib.metadata.version('skillevaluator') != version:
        raise ValueError('Unexpected released evaluator environment')
    package = Path(skillevaluator.__file__).resolve().parent
    source = package.parent
    members = [path for path in package.rglob('*') if path.is_file() and '__pycache__' not in path.parts]
    if len(members) > 1000 or any(path.is_symlink() for path in members):
        raise ValueError('Unsafe static candidate implementation tree')
    files = {path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in members}
    digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    expected = SOURCE_PINS[version][int(scanner_contracts)]
    if digest != expected or hashlib.sha256((source.parent / 'uv.lock').read_bytes()).hexdigest() != owner['lock_sha256']:
        raise ValueError('Released evaluator implementation or lock differs')


def validate_owner(versions):
    """Authenticate the native producer and recorded versions."""
    owner = STATIC_OWNERS.get(versions.get('evaluator_revision'), {})
    if (not owner or any(versions.get(key) != value for key, value in owner.items())
            or importlib.metadata.version('harbor') != owner['harbor']):
        raise ValueError('Static producer requires its pinned owning runtime')
    validate_install(owner=owner, scanner_contracts=owner is VERSIONS)
    return {**owner, 'version': owner['skillevaluator']}


def is_owner():
    return importlib.metadata.version('skillevaluator') in SOURCE_PINS


def validate_captured_config(tree):
    from skillevaluator.tier3 import evals_config

    path = next(tree / 'evals' / name for name in evals_config.CONFIG_FILENAMES
                if (tree / 'evals' / name).exists())
    # The repository reader already enforces confinement, link and race checks.
    size = path.stat().st_size
    if size > evals_config.MAX_EVALS_CONFIG_BYTES:
        raise ValueError('Captured eval config exceeds the evaluator limit')
    try:
        raw = evals_config._parse_config_text(path.read_text(), path.path)
        if not isinstance(raw, dict):
            raise ValueError('Captured eval config requires a mapping')
        evals_config._validate_config(raw, path.path)
    except (evals_config.EvalsConfigError, UnicodeError) as error:
        raise ValueError('Captured eval config failed strict validation') from error
