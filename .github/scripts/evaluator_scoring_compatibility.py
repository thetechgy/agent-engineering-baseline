"""Offline score-preservation gate. Controlled inputs are never measurements."""

import itertools
import json
import math
import os
from pathlib import Path
import subprocess

METRICS = ('security', 'skill_execution', 'skill_efficiency', 'accuracy', 'goal_accuracy', 'behavior_check')
PINS = {
    '0.3.0': {'harbor': '0.13.2', 'openai': '2.44.0', 'pydantic': '2.13.4'},
    '0.7.2': {'harbor': '0.24.0', 'openai': '2.44.0', 'pydantic': '2.13.4'},
}
REVISIONS = {'0.3.0': 'ac0a04905100acdafc6c95829311a9739c340ff6',
             '0.7.2': 'f878f99a9cd4a85dd04043feb43e5bd6a777f64b'}
LOCKS = {'0.3.0': '00c604509f7aeb055d6eac6cc866190086562a2a8295ae471589266a9d8f1983',
         '0.7.2': '532efd6d79caf262d5264a10c45dd100c2c038decfac7e6e965a940e915a8908'}
# Exact public source bytes, including the reviewed candidate compatibility patch.
# The retained reporting and benchmark recipes have the same scoring helper.
SOURCES = {
    '0.3.0': {
        'tier3/harbor/metrics.py': ('373995c404325031a836561c2b7bd392772c344778bac029f04e9e24f67f4f07',),
        'constants.py': ('a857894a882b84d1605617f39ab197568139fd65e320218d48268c1028b449f5',),
        'tier3/harbor/templates/eval.py': ('6e9d0abb7ea1336f4a44c73b5891b539f73e862f553f8db50c73d2f4ad609c65',
                                         'de1863fe690c4da5f1be5a09cd2339ad12acdcd04376e7f3a3cbf3a31d365b68'),
    },
    '0.7.2': {
        'tier3/harbor/metrics.py': ('2ba8557e7431af7b8d296debdd52b2f048177e575e9f8c6bfd9c89935879f72a',),
        'constants.py': ('1054880653647dcda6660cd1421972f2431f795fcc91cc9880267ab912626b1a',),
        'tier3/harbor/templates/eval.py': ('a49e8b9b9d23671e3681fbad4e1072fd7dfa8254ef713291814dc411fad42f79',),
    },
}
LIMIT = 64 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def vectors():
    binary = [dict(zip(METRICS, values)) for values in itertools.product((0, 1), repeat=len(METRICS))]
    fractional = [dict.fromkeys(METRICS, value) for value in (0.25, 0.5, 0.75)]
    fractional += [{key: 0.5 if key == selected else 1 for key in METRICS} for selected in METRICS]
    return binary + fractional


PROBE = ('PINS = ' + repr(PINS) + '\nLOCKS = ' + repr(LOCKS) + '\nSOURCES = ' + repr(SOURCES)
         + '\nMETRICS = ' + repr(METRICS) + r'''
import sys, json, hashlib, itertools, importlib.metadata
from pathlib import Path
network = []
def offline(event, args):
    if event.startswith('socket.'):
        network.append(event)
        raise PermissionError('Score probe forbids network access')
    if event in ('subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn', 'os.spawn', 'os.fork', 'os.forkpty', 'pty.spawn'):
        raise PermissionError('Score probe forbids process execution')
sys.addaudithook(offline)
try:
    version, source, lock = sys.argv[1:]
    assert sys.version_info[:2] == (3, 13)
    observed = {key: importlib.metadata.version(key) for key in ('skillevaluator', *PINS[version])}
    assert observed == {'skillevaluator': version, **PINS[version]}
    if source:
        source = Path(source).resolve(strict=True)
        sys.path.insert(0, str(source / 'src'))
    import skillevaluator
    package = Path(skillevaluator.__file__).resolve().parent
    if source:
        assert package.is_relative_to(source / 'src')
    lock = Path(lock) if lock else package.parents[1] / 'uv.lock'
    assert lock.is_file() and not lock.is_symlink() and lock.stat().st_size <= 2 * 1024 * 1024
    lock_digest = hashlib.sha256(lock.read_bytes()).hexdigest()
    assert lock_digest == LOCKS[version]
    sources = {}
    for member, expected in SOURCES[version].items():
        path = package / member
        assert path.is_file() and not path.is_symlink() and path.stat().st_size <= 1024 * 1024
        sources[member] = hashlib.sha256(path.read_bytes()).hexdigest()
        assert sources[member] in expected
    from skillevaluator.tier3.harbor import metrics
    assert tuple(metrics.DEFAULT_METRICS) == METRICS
    inputs = [dict(zip(METRICS, row)) for row in itertools.product((0, 1), repeat=len(METRICS))]
    inputs += [dict.fromkeys(METRICS, value) for value in (0.25, 0.5, 0.75)]
    inputs += [{key: 0.5 if key == selected else 1 for key in METRICS} for selected in METRICS]
    scores = [round(metrics.overall_score(row), 4) for row in inputs]
    assert not network
    response = {'schema': 1, 'runtime': observed,
        'python': '.'.join(map(str, sys.version_info[:3])), 'lock_sha256': lock_digest,
        'sources': sources, 'metrics': list(metrics.DEFAULT_METRICS), 'definition': metrics.score_definition(),
        'native_score_policy': getattr(metrics, 'DEFAULT_SCORE_POLICY', None), 'scores': scores,
        'network_attempts': network, 'inference': False, 'remote_judges': False}
    raw = json.dumps(response, allow_nan=False, sort_keys=True).encode()
    assert len(raw) <= 64 * 1024
    sys.stdout.buffer.write(raw)
except Exception:
    sys.exit(1)
''')


def validate_probe(value, version):
    require(type(value) is dict and set(value) == {'schema', 'runtime', 'python', 'lock_sha256', 'sources',
        'metrics', 'definition', 'native_score_policy', 'scores', 'network_attempts', 'inference', 'remote_judges'},
        'Invalid score probe schema')
    require(type(value['schema']) is int and value['schema'] == 1 and
            value['runtime'] == {'skillevaluator': version, **PINS[version]}, 'Score probe runtime mismatch')
    require(type(value['python']) is str and value['python'].startswith('3.13.'), 'Score probe Python mismatch')
    require(value['lock_sha256'] == LOCKS[version], 'Score probe lock mismatch')
    require(type(value['sources']) is dict and set(value['sources']) == set(SOURCES[version]) and
            all(value['sources'][key] in expected for key, expected in SOURCES[version].items()), 'Score probe source mismatch')
    require(value['metrics'] == list(METRICS), 'Score probe metric contract mismatch')
    require(type(value['definition']) is str and 0 < len(value['definition']) <= 512, 'Score definition limit')
    require(value['native_score_policy'] is None if version == '0.3.0' else
            value['native_score_policy'] == 'skill-evaluator-dimension-mean-v1', 'Unknown native score policy')
    require(value['network_attempts'] == [] and value['inference'] is False and value['remote_judges'] is False,
            'Score probe activity rejected')
    require(type(value['scores']) is list and len(value['scores']) == len(vectors()) and
            all(type(score) in (int, float) and 0 <= score <= 1 and math.isfinite(score) for score in value['scores']),
            'Score probe coverage or numeric mismatch')
    return value


def probe(executable, version, *, source=None, lock=None):
    require(version in PINS, 'Unsupported scoring runtime')
    executable = Path(executable)
    require(executable.is_absolute() and executable.is_file(), 'Pinned score probe interpreter required')
    result = subprocess.run([str(executable), '-I', '-B', '-c', PROBE, version,
        str(source) if source else '', str(lock) if lock else ''],
        env={'PATH': os.defpath, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHON_DOTENV_DISABLED': '1',
             'LITELLM_LOCAL_MODEL_COST_MAP': 'True'},
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30, check=False)
    require(result.returncode == 0 and len(result.stdout) <= LIMIT, 'Pinned native score probe rejected')
    def reject_constant(value):
        raise ValueError('Invalid score probe constant')
    value = json.loads(result.stdout, parse_constant=reject_constant)
    return validate_probe(value, version)


def compare(retained, candidate):
    validate_probe(retained, '0.3.0'); validate_probe(candidate, '0.7.2')
    differences = [{'case': index, 'metrics': row, 'retained': old, 'candidate': new}
        for index, (row, old, new) in enumerate(zip(vectors(), retained['scores'], candidate['scores'])) if old != new]
    return {'schema': 1, 'status': 'incompatible' if differences else 'compatible',
        'code': 'standard_score_policy_changed' if differences else 'standard_scores_preserved',
        'fixture_only': True, 'inference': False, 'remote_judges': False,
        'revisions': REVISIONS, 'probes': {'retained': retained, 'candidate': candidate},
        'vectors': len(vectors()), 'differences': differences}


def qualify(candidate_python, candidate_source, candidate_lock, retained_python):
    """Missing tooling and probe failures never fall back or manufacture evidence."""
    if not retained_python or not Path(retained_python).is_absolute():
        return {'schema': 1, 'status': 'unqualified', 'code': 'retained_evaluator_python_required',
                'fixture_only': True, 'inference': False, 'remote_judges': False}
    try:
        retained = probe(retained_python, '0.3.0')
        candidate = probe(candidate_python, '0.7.2', source=candidate_source, lock=candidate_lock)
        return compare(retained, candidate)
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired):
        return {'schema': 1, 'status': 'unqualified', 'code': 'native_score_probe_rejected',
                'fixture_only': True, 'inference': False, 'remote_judges': False}
