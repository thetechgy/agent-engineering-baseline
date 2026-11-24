"""The released Tier 1 producer identity and its owning runtime."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform

VERSION = '1.0.1'
PRODUCER = 'skillevaluator-1.0.1-static-v1'
REVISION = '914c15cb3f31562ccffdc9a7166002a87ed2ce1e'
LOCK = 'c49a8340c7312a8396c34be64d0062e8a591f201202c890b7563265958e3f364'
SOURCE = '7dd63bd0286d9cad9921c1739de193fd55ad407f67d1b6a8476e2fd32544920b'
SEMGREP_LOCK = 'sha256:f34553471c8d6ad88e2139716a3e584de63b1dddecbe085c44a7a2a33db1199d'
VERSIONS = {'skillevaluator': VERSION, 'evaluator_revision': REVISION, 'python': '3.14.10',
            'harbor': '0.25.0', 'lock_sha256': LOCK, 'producer_profile': PRODUCER}


def validate_install():
    """Authenticate the installed release, interpreter and lock."""
    import skillevaluator

    if (platform.python_version() != VERSIONS['python']
            or importlib.metadata.version('skillevaluator') != VERSION):
        raise ValueError('Unexpected released evaluator environment')
    package = Path(skillevaluator.__file__).resolve().parent
    source = package.parent
    members = [path for path in package.rglob('*') if path.is_file() and '__pycache__' not in path.parts]
    if len(members) > 1000 or any(path.is_symlink() for path in members):
        raise ValueError('Unsafe static candidate implementation tree')
    files = {path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in members}
    digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if digest != SOURCE or hashlib.sha256((source.parent / 'uv.lock').read_bytes()).hexdigest() != LOCK:
        raise ValueError('Released evaluator implementation or lock differs')


def validate_owner(versions):
    """Authenticate the native producer and recorded versions."""
    validate_install()
    if (any(versions.get(key) != value for key, value in VERSIONS.items())
            or importlib.metadata.version('harbor') != VERSIONS['harbor']):
        raise ValueError('Static producer requires its pinned owning runtime')
    return {**VERSIONS, 'version': VERSION}


def is_owner():
    return importlib.metadata.version('skillevaluator') == VERSION


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
