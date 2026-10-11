#!/usr/bin/env python3
"""Offline evidence inventory and closed, data-only reporting contracts."""

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace

# Standalone commands must not mutate the checkout while importing local helpers.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import skill_reports as reports

ROOT = Path(__file__).resolve().parents[2]
JSON_LIMIT = 8 * 1024 * 1024
NORMALIZATION_LIMIT = 64 * 1024 * 1024
PUBLIC_LIMIT = 1024 * 1024
MAX_CASES = 1000
MAX_TRIALS = 10000
MAX_REFERENCES = 2 * MAX_TRIALS + 100
MAX_SOURCE_MEMBERS = 1000
MAX_INPUT_ENTRIES = 100000
SECURE_DIRECTORY_OUTPUT = (all(fn in os.supports_dir_fd for fn in (os.open, os.mkdir))
                           and all(hasattr(os, name) for name in ('O_DIRECTORY', 'O_NOFOLLOW', 'geteuid')))
# Reviewed Podman extract-manifest.json bytes; additional identities require review.
REVIEWED_EXTRACT_MANIFESTS = frozenset({
    'sha256:4f8ab06638a37c970dfd5a97f057da8505a0b57767a332b41d4e0c2c8e8066ea',
})
# Original-artifact deadlines from the pinned manifest. Serialized availability
# is not evidence of durable retention and cannot override these deadlines.
REVIEWED_REFERENCE_EXPIRY = {
    ('github-artifact-10590172928',
     'sha256:2d384b3c01ac778764fee33943c66a14e011ebcf60fbf266cf1e40880d2e5dca'):
        '2026-10-19T19:11:15Z',
}
require = reports.require
# Metadata identities from the exact reviewed manifest above, independently
# checked against its pinned bytes by the fixture contract. No execution attestation.
REVIEWED_REFERENCE_IDENTITIES = frozenset({
    'sha256:0079d44b850c03753cc4c5c3664b7c857cdcd20766752b65f3ec1c0666434a4b',
    'sha256:010869aa935d7200789a3b1d14f167b05e87228f36343f20f0d7c457c017b796',
    'sha256:022830f064eed2e50d95cb3d839b38406eb0d29a8a3ee1d17a8ee1dc6e0ad059',
    'sha256:0975698385508c3b95fb545f2d1c6449d51543f9711990eb93d3c70e21a1fa41',
    'sha256:1336bcc8a75421cd8c6ce0712729b2ef60f7656377f113e43a3abfe0091732d1',
    'sha256:1344afa303b2a76b8c92bc334ad3e41c41d58bc474f20f4464406add34cd554b',
    'sha256:1a89e5e4f9b67f55e7bb01280df5c58953298843cf182042e4c1859fce9d0652',
    'sha256:1e0b174d762744fc71e9bb752f1cd8985662afd9c3b092d23f8ea48c676f72dd',
    'sha256:1e72f6533e2d97493c58ba1ed271ede6a2d555d227ab7efc45930faf99d95ba3',
    'sha256:20067f2d75b80658df4d7e7b03c94536b5b868768d488361600553fa87259cf5',
    'sha256:3ea90fcdfbc8162f18ff3deb2862e8129b94a027e5291a0f199cb72781843b8a',
    'sha256:41d2cb2d35e3ec2bd3cefb002a50b2d45fd7338b005a980f37106c0a73f5a0ab',
    'sha256:51e78f9160eb6be7727a6032842703ac1fe5baefd02c78cc77a451a677b432c3',
    'sha256:563e49238fc2c57aa20c2738311c47502d0452704f19f939a9ab9e7346f499c8',
    'sha256:635dcc3a74f006619f76c282d7ea868d6bb15366510da64afd0c96575aa7533b',
    'sha256:676f8c7df2ea2eb4663503ee4993fa0e96750a3df1bf2ef1949df1955fdd75d6',
    'sha256:68fddbd6b3747bf44e10ee231e44c4ac5db7206897473d703a0404c212114883',
    'sha256:6e10eb576317283b058b82d347ea866f5305913a8b89019009852aee186f47fe',
    'sha256:6eec6caf6e2a09aa37dbfa362c9be5fa42bf89b70328ab574d7ae3bd7a52ac2f',
    'sha256:7a19b4c77dab289a4565f73214f26139b1ac46a94967c75daa3d607b45f2b138',
    'sha256:8140ef2dda2da4eeeba0b9390153b0e1e3e7c594a5f1930a19b8c50fe751bb24',
    'sha256:8424e5e2f55758739e1f36719e2495769ed3642a54246805a11af9178cc64c52',
    'sha256:846648a61b269a70ce32f813796f241f0b30c93a8e9882f2b930c2fc8f286577',
    'sha256:86c9f0bc89b89cb8060809f4ba027b41b80e0da92cfe45a98c12f4f69a39e007',
    'sha256:86e0793fea0da9585bccf3c6e3458511a1519c2645f7a9a4f8e0defbdfe17278',
    'sha256:8ea0884d5dc678aa25e45d365ce42355bb1210f3d254b3fea7843bdee8441a5b',
    'sha256:91e1385f672667ff14279ad33474774a8002c8c49b6312ef5fc9ba0fd04936c4',
    'sha256:921caa7779427a8ea2cfb808248355dce9b2064fdf20184a6e94e8817188aa06',
    'sha256:9c99cf006081fcb8d250d18d2c25821ce4f50a01168eca350e814192360ee24f',
    'sha256:9fdbbae4ae978255fd14c2ed9dfb00be3d9812f2c91de5ca498ea9dee3b9e8b9',
    'sha256:a25acc54782d667d087c18dce5df6a8269079e37966174e6c078cf0c70192128',
    'sha256:a552c56679cc259ad7c007abc116d0b59753338d8cc987896454a9d4804ca73f',
    'sha256:a62848fbdd773aa679387a3fc4144f63f61eafd1e4fb3ffd21e512d200975d53',
    'sha256:aa44764dac09b62e048765b524ee8585a85cb0786446bbc10a6fc2474bc9898b',
    'sha256:b81a5d8059b1c7b7c71dccb97a3fea1bfe1b3e6a0db92804c70aedea3c7e7cda',
    'sha256:bac053f37adb00d0179977e45da22c22f80b392373157739e4ee1348973d0972',
    'sha256:bf26e822151bbc5f0feff3ddfe8e553e26d5b4dd0c660c0fe56c00e0a1ed68b3',
    'sha256:c74b685be3405401bc3ab91db9d03eca132addeb59e4b60dba3408a995dd1161',
    'sha256:d21532e67e3f4689889fc392fc68dca8aaa51e9ab42d435b207b20f5e30c8014',
    'sha256:d5856100f6065447d044b219c768049c2bfae71d5ac37f81d30b01cc1160143c',
    'sha256:e2807f8b190a97e929700a047e586631ac8a7ce35b4c02d5facdaf9c0e102795',
    'sha256:e9b57020d90a44fe55f30e05745bd3f4c999e1e60852cac2dffac63f9dd647b5',
    'sha256:ea2d043ad29d3f5ceab40120d0f302ee34341e2f8a7c10a6f3fa419151e56fe1',
    'sha256:ecdf06c011a9106cc74fdf5eb63010538806aa024575710a19ad159b572f2b44',
    'sha256:f0eff6637f6e896afa1d59c8d53ac57e744dba89992e651e7bf735a519103a27',
    'sha256:f317cd3076c986d81a9ae6d28cb3a09b03b8d95419728bcbda9923f739e56e96',
    'sha256:f7b8fb2ef9ccc51564ccdd639094df45a7368ced6bd433c5bd2eb52536401b59',
    'sha256:fd8fe9abe5696b157aae40a758ae66e8f38d539687bc1dec5da587ec6911f688',
})
# Public observation payloads derived from the pinned reviewed extract above.
REVIEWED_OBSERVATION_PAYLOADS = frozenset({
    'sha256:02bf5965fc7878010a2b55be6601cf56cd51a539666023b7292eb09f7d25d6e6',
    'sha256:12671ef8618d82bb05f39d2ad71c0a7c41e42efa5b523805ed90242dc518d050',
    'sha256:16f016601d3a4851399616b4b71e2065c7cf13b435b3ce233171a662f67b400d',
    'sha256:1d8545b95ec03a8e37e87831b285c3a6952b1a4130fd0b9a70c104e3772a7881',
    'sha256:328b62bf137c5a36a61f22065bc612d6b4bc660929f32f4dcf9e8eea7190c381',
    'sha256:439c9872f362e2ef2785ff0d2eb299601b6d0b39a5f87275c16b4d9162194fa9',
    'sha256:6b9f38446da22ecba2d5997565a15ed01e4484e7f234ef12e8b04e2ec4f4454e',
    'sha256:7c7024b7eb902ad097e7dadbf2f7ffb4a22ddb6bef747109180b4db18262ade9',
    'sha256:822155b1b1581748f7c5360265bbaeb6940d47d5678044f692d9bc1a471396e8',
    'sha256:827cf7600e3314a80bf1ce9b781b8f4b5733f640f5f22c5ac922ceca89d87228',
    'sha256:898d8e1fa9ecc58b10d1a60e9493270c8a5cbe2e08e634a5ac4842eb22c9f300',
    'sha256:8ccc3fb74f4cf4214df58ba3ae8b5ce3829b53500645d3238f74eadeeb6a526f',
    'sha256:8cdfe410cfba748438064130b4d4ebad9cd1c11d48c0976ebc14c0e6418d9152',
    'sha256:93bb29af57d0a5510a413dfcff0c9b15472c6513b3876535bb9d86b4d2471fc1',
    'sha256:c4b01a4f7e0703c1a34a4edc02f1ac3ccb9bac4927a72c209e40c7f07a24c059',
    'sha256:cbde5e2ec3cfc413810f1a0b8846652acf7a0a77ed6fa8130291d1081f1b1519',
    'sha256:d446609db87a11e86dfa18a9f7c3fc0eb6e89f8785f563abab348b77073bfd8f',
    'sha256:e8dade88e6e3abb701dd896394f44f0805e048aacc1354f721393008e320dc47',
    'sha256:fe93aaa7437debe16ad1d3c09acb37d672b35ce72d18cfffc9b12ffe0430a27e',
    'sha256:ffea68958116554cfacd0c9eb5f5b292d2f552ae6b3bcfa5232268f0d0f59fdd',
})
OBSERVATION_FIELDS = ('id', 'arm', 'case_id', 'attempt', 'score', 'scores', 'rubric_pass',
                      'deterministic_gate', 'deterministic_scores', 'references')
REVIEWED_METRIC_VALUES = {'Skill Lift': 0.1207, 'Effectiveness': 0.7730,
                         'Correctness': 0.9600, 'Discoverability': 0.6937}
REVIEWED_SOURCE_IDENTITIES = frozenset({
    'sha256:88d1d5eda32819451938ae64f404d2c694aa628039d9045302e627c48107a3b8',
    'sha256:f54436458de3447e2ef95a75db3ea1a4cb59c527515127e633043350629895c7',
})  # Exact historical content, or the same declared identity with unavailable content.
REVIEWED_EXECUTION_CONTRACTS = frozenset({
    'sha256:bffae00bec7b34fcdae64794f39d477b48b0b86adc673d221cf113178ba54c35',
    'sha256:5b1f9b4daa3af1222579cea0bc1055dc1e31d4f8ef2cb96d6ea2993e5a65bf1f',
})  # The pinned run/dataset/policy/arms, with exact or unavailable authored bytes.
PROVENANCE = ('runtime_recorded', 'configured', 'reconstructed_from_declared_revision',
              'reviewed_extract', 'synthetic', 'unknown')
REASONS = ('results_not_supplied', 'coverage_missing', 'execution_incomplete', 'case_details_missing',
           'metadata_missing', 'source_unavailable', 'source_mismatch', 'reference_unavailable',
           'reference_expired', 'scan_incomplete')


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + '\n').encode()


def digest_bytes(value):
    return 'sha256:' + hashlib.sha256(value).hexdigest()


def utc_now():
    return datetime.now(timezone.utc)


def identity(value):
    return digest_bytes(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                   ensure_ascii=True, allow_nan=False).encode())


def depth(value, limit, level=0, seen=None):
    require(level <= limit, 'JSON depth exceeded')
    if isinstance(value, (dict, list)):
        seen = {} if seen is None else seen
        # YAML aliases preserve shared containers. Revisit only at a deeper
        # level, bounding work by the depth limit rather than alias paths.
        marker = id(value)
        if seen.get(marker, -1) >= level:
            return
        seen[marker] = level
        for child in value.values() if isinstance(value, dict) else value:
            depth(child, limit, level + 1, seen)
    elif type(value) is float:
        require(math.isfinite(value), 'Nonfinite JSON number')


def safe_path(path, *, directory=False, missing=False, directory_identities=None):
    path = Path(path).absolute()
    require('..' not in path.parts, 'Parent traversal')
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            require(missing and current == path, 'Missing input component')
            return path
        require(not stat.S_ISLNK(info.st_mode) and not bool(getattr(info, 'st_file_attributes', 0)
                & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)), 'Linked/reparse input')
        if current != path or directory:
            require(stat.S_ISDIR(info.st_mode), 'Non-directory component')
            if directory_identities is not None:
                observed = (info.st_dev, info.st_ino)
                require(current not in directory_identities or directory_identities[current] == observed,
                        'Input directory changed')
                directory_identities[current] = observed
        else:
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'Special or hard-linked input')
    return path


def directory_state(info):
    return info.st_mtime_ns, info.st_ctime_ns


def file_state(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def verify_file_states(states, directories, directory_states, paths=None):
    fd = None
    parent = None
    try:
        for path in states if paths is None else paths:
            if path.parent != parent:
                if fd is not None:
                    os.close(fd); fd = None
                fd = open_directory(path.parent, directories, directory_states=directory_states)
                parent = path.parent
            info = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and file_state(info) == states[path],
                    'Input member changed')
    finally:
        if fd is not None: os.close(fd)


def verify_directory_states(states, identities, paths=None):
    paths = states if paths is None else paths
    for path in paths:
        fd = open_directory(path, identities, directory_states=states)
        os.close(fd)


def safe_tree(path, *, max_entries=MAX_INPUT_ENTRIES, max_files=None, directory_identities=None, directory_states=None, file_states=None):
    if directory_identities is None:
        directory_identities = {}
    if directory_states is None:
        directory_states = {}
    if file_states is None:
        file_states = {}
    path = safe_path(path, directory=True, directory_identities=directory_identities)
    pending = [path]
    files = []
    scanned = []
    seen = 0
    while pending:
        current = pending.pop()
        fd = open_directory(current, directory_identities, directory_states=directory_states)
        try:
            observed = directory_state(os.fstat(fd))
            require(current not in directory_states or directory_states[current] == observed,
                    'Input directory entries changed')
            directory_states[current] = observed
            scanned.append(current)
            with os.scandir(fd) as entries:
                for entry in entries:
                    seen += 1
                    require(seen <= max_entries, 'Input tree entry limit')
                    info = entry.stat(follow_symlinks=False)
                    directory = stat.S_ISDIR(info.st_mode)
                    member = safe_path(current / entry.name, directory=directory, directory_identities=directory_identities)
                    if directory:
                        pending.append(member)
                    else:
                        require(max_files is None or len(files) < max_files, 'Input tree entry limit')
                        observed_file = file_state(info)
                        require(member not in file_states or file_states[member] == observed_file, 'Input member changed')
                        file_states[member] = observed_file
                        files.append(member)
            require(directory_state(os.fstat(fd)) == directory_states[current], 'Input directory entries changed')
        finally:
            os.close(fd)
    verify_directory_states(directory_states, directory_identities, scanned)
    verify_file_states(file_states, directory_identities, directory_states, files)
    return files


class ReadBudget:
    def __init__(self):
        self.remaining = NORMALIZATION_LIMIT

    def consume(self, size):
        require(0 <= size <= self.remaining, 'Normalization byte limit')
        self.remaining -= size


def read_bytes(path, limit=JSON_LIMIT, *, budget=None, directory_identities=None, directory_states=None, file_states=None):
    if directory_identities is None:
        directory_identities = {}
    path = safe_path(path, directory_identities=directory_identities)
    require(SECURE_DIRECTORY_OUTPUT, 'Secure directory input unsupported')
    # O_NONBLOCK avoids hanging if a file is replaced by a FIFO between checks.
    parent_fd = open_directory(path.parent, directory_identities, directory_states=directory_states)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0), dir_fd=parent_fd)
    finally:
        os.close(parent_fd)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= limit,
                'Special, hard-linked or oversized input')
        if file_states is not None:
            observed = file_state(info)
            require(path not in file_states or file_states[path] == observed, 'Input member changed')
            file_states[path] = observed
        if budget is not None:
            budget.consume(info.st_size)
        value = stream.read(min(limit, info.st_size + budget.remaining) + 1 if budget is not None else limit + 1)
        if file_states is not None:
            require(file_state(os.fstat(stream.fileno())) == observed, 'Input member changed')
    require(len(value) <= limit, 'Oversized input')
    if budget is not None:
        budget.consume(max(0, len(value) - info.st_size))
    return value


def parse_json(raw):
    require(type(raw) is bytes and len(raw) <= JSON_LIMIT, 'Invalid bounded JSON')
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=pairs,
                           parse_constant=lambda _: require(False, 'Nonfinite JSON number'))
        depth(value, 32)
        return value
    except (RecursionError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('Invalid bounded JSON') from exc


def read_json(path):
    return parse_json(read_bytes(path))


def read_json_and_digest(path, *, budget=None, directory_identities=None, directory_states=None, file_states=None):
    raw = read_bytes(path, budget=budget, directory_identities=directory_identities, directory_states=directory_states, file_states=file_states)
    return parse_json(raw), digest_bytes(raw)


def read_yaml(path, *, reader=None):
    import yaml
    if reader is None:
        reader = read_bytes
    class UniqueLoader(yaml.SafeLoader):
        pass
    def mapping(loader, node):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node)
            require(type(key) is str and key not in result, 'Ambiguous YAML key')
            result[key] = loader.construct_object(value_node)
        return result
    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    try:
        value = yaml.load(reader(path), Loader=UniqueLoader)
        depth(value, 32)
        return value
    except (yaml.YAMLError, RecursionError) as exc:
        raise ValueError('Invalid bounded YAML metadata') from exc


def closed(value, fields):
    require(type(value) is dict and set(value) == set(fields), 'Unexpected or missing fields')


def token(value):
    require(type(value) is str and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+~:-]{0,127}', value)),
            'Invalid identifier')


def skill_id(value):
    require(type(value) is str and len(value) <= 64
            and bool(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', value)), 'Invalid skill ID')


def relative(value):
    require(type(value) is str and len(value) <= 512 and '\\' not in value, 'Invalid relative member')
    parts = value.split('/')
    require(not PurePosixPath(value).is_absolute() and all(p not in ('', '.', '..') for p in parts),
            'Escaping relative member')
    for part in parts:
        require(bool(re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', part)), 'Unsafe member component')
        require(not part.endswith('.') and part.split('.', 1)[0].upper() not in
                {'CON', 'PRN', 'AUX', 'NUL', *('COM' + str(i) for i in range(1, 10)),
                 *('LPT' + str(i) for i in range(1, 10))}, 'Cross-platform unsafe member')


def sha(value):
    require(type(value) is str and bool(re.fullmatch(r'sha256:[0-9a-f]{64}', value)), 'Invalid SHA256')


def revision(value):
    require(type(value) is str and bool(re.fullmatch(r'[0-9a-f]{40}', value)), 'Invalid revision')


def repository(value):
    require(type(value) is str and bool(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', value)),
            'Invalid repository')


def number(value, low=0, high=1):
    require(type(value) in (int, float) and math.isfinite(value) and low <= value <= high,
            'Invalid numeric observation')


def count(value, maximum=MAX_TRIALS):
    require(type(value) is int and 0 <= value <= maximum, 'Invalid count')


def boolean(value):
    require(type(value) is bool, 'Invalid boolean')


def enum(value, values):
    require(value in values and type(value) is str, 'Invalid enum')


def optional(value, validator):
    if value is not None:
        validator(value)


def case_ids(values):
    from skillevaluator.tier3.case_ids import validate_case_ids
    require(type(values) is list and len(values) <= MAX_CASES, 'Case limit exceeded')
    canonical = validate_case_ids(values)
    require(canonical == values, 'Noncanonical case ID')
    return canonical


def validate_content(value):
    closed(value, ('digest', 'algorithm', 'scope', 'provenance', 'manifest'))
    optional(value['digest'], sha)
    enum(value['algorithm'], ('sha256-relative-file-manifest-v1',))
    enum(value['scope'], ('pinned-agent-visible',))
    enum(value['provenance'], PROVENANCE)
    require(type(value['manifest']) is list and len(value['manifest']) <= MAX_SOURCE_MEMBERS, 'Manifest limit')
    names = []
    for row in value['manifest']:
        closed(row, ('member', 'digest'))
        relative(row['member']); sha(row['digest']); names.append(row['member'])
    require(names == sorted(set(names)), 'Ambiguous content manifest')
    require(len({n.casefold() for n in names}) == len(names), 'Content member case collision')
    if value['digest'] is not None:
        require('SKILL.md' in names, 'Skill content missing root SKILL.md')
        require(value['digest'] == identity(value['manifest']), 'Content manifest mismatch')
    else:
        require(not names and value['provenance'] == 'unknown', 'Unknown content has manifest')


def content(manifest=(), provenance='unknown'):
    manifest = sorted(manifest, key=lambda row: row['member'])
    return {'digest': identity(manifest) if provenance != 'unknown' else None,
            'algorithm': 'sha256-relative-file-manifest-v1', 'scope': 'pinned-agent-visible',
            'provenance': provenance, 'manifest': manifest}


def skill_projection_files(path, files, *, directory_identities=None, directory_states=None):
    from skillevaluator.tier3.harbor.adapter import _runtime_skill_copy_ignore, _runtime_projection_path_is_ignored
    if directory_identities is not None and directory_states is None:
        for directory in directory_identities:
            if directory.is_relative_to(path):
                safe_path(directory, directory=True, directory_identities=directory_identities)
    if directory_states is not None:
        verify_directory_states(directory_states, directory_identities,
                                (directory for directory in directory_states if directory.is_relative_to(path)))
    ignore = _runtime_skill_copy_ignore(path)
    return [p for p in files if not _runtime_projection_path_is_ignored(p, path, ignore)]


def skill_content(path, *, reader=None, directory_identities=None, directory_states=None, file_states=None):
    directories = {} if directory_identities is None else directory_identities
    states = {} if directory_states is None else directory_states
    members = {} if file_states is None else file_states
    files = safe_tree(path, max_entries=2 * MAX_SOURCE_MEMBERS, max_files=MAX_SOURCE_MEMBERS,
                      directory_identities=directories, directory_states=states, file_states=members)
    if reader is not None:
        reject_source_markers(path, files, directories)
    else:
        reader = lambda member: read_bytes(member, directory_identities=directories, directory_states=states, file_states=members)
    safe_path(path, directory=True, directory_identities=directories)
    result = content([{'member': p.relative_to(path).as_posix(), 'digest': digest_bytes(reader(p))}
                     for p in skill_projection_files(path, files, directory_identities=directories, directory_states=states)], 'configured')
    verify_file_states(members, directories, states, files)
    return result


def reject_source_markers(path, files, directories):
    from skillevaluator.tier3.output_provenance import GENERATED_OUTPUT_MARKER
    marked = (any(p.name == GENERATED_OUTPUT_MARKER for p in files)
              or any(p.name == GENERATED_OUTPUT_MARKER and p.is_relative_to(Path(path).absolute()) for p in directories))
    require(not marked, 'Generated output inside inventory source')


def validate_source(value):
    closed(value, ('skill_id', 'owner', 'repository', 'revision', 'source_path', 'lineage', 'content'))
    skill_id(value['skill_id']); enum(value['owner'], ('local', 'upstream', 'unknown'))
    optional(value['repository'], repository); optional(value['revision'], revision)
    optional(value['source_path'], relative)
    if value['lineage'] is not None:
        closed(value['lineage'], ('repository', 'revision', 'source_path'))
        repository(value['lineage']['repository']); revision(value['lineage']['revision'])
        relative(value['lineage']['source_path'])
    validate_content(value['content'])


def source(name, owner='unknown', repo=None, rev=None, path=None, contents=None, lineage=None):
    return {'skill_id': name, 'owner': owner, 'repository': repo, 'revision': rev,
            'source_path': path, 'lineage': lineage, 'content': contents or content()}


def offline_git(workspace, *args, text=False, max_entries=None, budget=None):
    # Missing promisor objects stay unknown; replacement refs cannot alter exact evidence.
    command = ['git', '-C', str(workspace), *args]
    # Git's repository-local environment (rev-parse --local-env-vars), plus
    # discovery/namespace selectors, must not redirect the requested checkout.
    selectors = {'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_CONFIG', 'GIT_CONFIG_PARAMETERS',
                 'GIT_CONFIG_COUNT', 'GIT_OBJECT_DIRECTORY', 'GIT_DIR', 'GIT_WORK_TREE',
                 'GIT_IMPLICIT_WORK_TREE', 'GIT_GRAFT_FILE', 'GIT_INDEX_FILE', 'GIT_REPLACE_REF_BASE',
                 'GIT_PREFIX', 'GIT_SHALLOW_FILE', 'GIT_COMMON_DIR', 'GIT_NAMESPACE',
                 'GIT_CEILING_DIRECTORIES', 'GIT_DISCOVERY_ACROSS_FILESYSTEM'}
    env = {key: value for key, value in os.environ.items()
           if key not in selectors and not key.startswith(('GIT_CONFIG_KEY_', 'GIT_CONFIG_VALUE_', 'GIT_TRACE'))}
    # Trace2 can also inherit global/system targets. Explicitly disable all
    # targets rather than allowing an unset environment to fall back to them.
    env.update(GIT_NO_LAZY_FETCH='1', GIT_NO_REPLACE_OBJECTS='1',
               GIT_TRACE='0', GIT_TRACE2='0', GIT_TRACE2_PERF='0', GIT_TRACE2_EVENT='0')
    if max_entries is None:
        return subprocess.run(command, capture_output=True, text=text, env=env)
    require(not text, 'Binary tree listing required')
    # Bound the NUL-delimited listing while reading, before parsing or blob reads.
    # Discard diagnostics so a blocked stderr pipe cannot stall the bounded read.
    byte_limit = min(JSON_LIMIT, budget.remaining) if budget is not None else JSON_LIMIT
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, bufsize=0) as process:
        output = bytearray()
        entries = 0
        try:
            while chunk := process.stdout.read(min(4096, byte_limit - len(output) + 1)):
                entries += chunk.count(b'\0')
                require(entries <= max_entries and len(output) + len(chunk) <= JSON_LIMIT,
                        'Historical tree listing limit')
                if budget is not None:
                    budget.consume(len(chunk))
                output.extend(chunk)
            returncode = process.wait()
        finally:
            if process.poll() is None:
                process.kill()
    return subprocess.CompletedProcess(command, returncode, bytes(output), b'')


def git_revision(workspace):
    result = offline_git(workspace, 'rev-parse', 'HEAD', text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def historical_commit(workspace, rev):
    revision(rev)
    kind = offline_git(workspace, 'cat-file', '-t', rev, text=True)
    if kind.returncode:
        return False
    require(kind.stdout.strip() == 'commit', 'Historical revision must be a commit')
    return True


def historical_blob(workspace, spec, *, budget=None):
    """Bound exact local object bytes before capturing content; missing stays unknown."""
    if ':' in spec:
        rev, member = spec.split(':', 1)
        relative(member)
        if not historical_commit(workspace, rev):
            return None
    kind = offline_git(workspace, 'cat-file', '-t', spec, text=True)
    if kind.returncode:
        return None
    require(kind.stdout.strip() == 'blob', 'Historical member must be a blob')
    size = offline_git(workspace, 'cat-file', '-s', spec, text=True)
    if size.returncode:
        return None
    size = int(size.stdout.strip())
    require(0 <= size <= JSON_LIMIT, 'Oversized historical blob')
    if budget is not None:
        budget.consume(size)
    blob = offline_git(workspace, 'cat-file', 'blob', spec)
    if blob.returncode:
        return None
    require(len(blob.stdout) <= JSON_LIMIT, 'Oversized historical blob')
    if budget is not None:
        budget.consume(max(0, len(blob.stdout) - size))
    return blob.stdout


def historical_content(workspace, rev, source_path, *, budget=None):
    """Read exact local Git blobs only. Never checkout or contact a remote."""
    relative(source_path)
    if not historical_commit(workspace, rev):
        return content()
    listing = offline_git(workspace, 'ls-tree', '-rz', rev, '--', source_path,
                          max_entries=MAX_SOURCE_MEMBERS, budget=budget)
    if listing.returncode:
        return content()
    rows = listing.stdout.split(b'\0')
    filenames = [row.split(b'\t', 1)[1].decode() for row in rows if row]
    if not filenames:
        return content()
    prefix = source_path + '/'
    require(all(filename.startswith(prefix) for filename in filenames), 'Historical source must be a directory')
    tree_names = {filename[len(prefix):] for filename in filenames}
    require('SKILL.md' in tree_names, 'Historical skill root missing SKILL.md')
    members = []
    for row in rows:
        if not row:
            continue
        header, filename = row.split(b'\t', 1)
        mode, kind, oid = header.split()
        require(mode == b'100644' or mode == b'100755', 'Unsafe historical source tree')
        require(kind == b'blob', 'Special historical source')
        name = filename.decode()[len(prefix):]
        relative(name)
        members.append((name, oid.decode()))
    records = []
    for name, oid in members:
        # Same root/nested skill eval boundary as the pinned runtime; generated
        # outputs are never accepted as historical authored source.
        parts = Path(name).parts
        nested_evals = any(p.casefold() == 'evals' and any('/'.join((*parts[:i], manifest)) in tree_names
                            for manifest in ('SKILL.md', 'skill.md')) for i, p in enumerate(parts))
        if any(p in ('results', '__pycache__', '.git') for p in parts) or nested_evals:
            continue
        blob = historical_blob(workspace, oid, budget=budget)
        if blob is None:
            return content()
        records.append({'member': name, 'digest': digest_bytes(blob)})
    if not records:
        return content()
    return content(records, 'reconstructed_from_declared_revision')


class CapturedInput:
    """Read-only path surface used by the pinned optional-file validators."""
    def __init__(self, path, reader):
        self.path = path
        self.reader = reader

    def __str__(self):
        return str(self.path)

    def __truediv__(self, member):
        return CapturedInput(self.path / member, self.reader)

    @property
    def parent(self):
        return CapturedInput(self.path.parent, self.reader)

    @property
    def suffix(self):
        return self.path.suffix

    def exists(self):
        return self.path.exists()

    def stat(self):
        return SimpleNamespace(st_size=len(self.reader(self.path)))

    def read_text(self, encoding='utf-8', errors='strict'):
        return self.reader(self.path).decode(encoding, errors)


def strict_dataset(path, name, *, reader=None, directory_identities=None, directory_states=None, file_states=None):
    from skillevaluator.tier3.dataset_utils import normalize_dataset_entries
    from skillevaluator.tier3 import evals_spec as native_spec
    directories = {} if directory_identities is None else directory_identities
    states = {} if directory_states is None else directory_states
    members = {} if file_states is None else file_states
    files = safe_tree(path.parent.parent, directory_identities=directories, directory_states=states, file_states=members)
    tree_entries = set(files) | set(directories)
    alternatives = [member for member in tree_entries if member.parent == path.parent and member.name.startswith('evals.')]
    require(path.name == 'evals.json' and set(alternatives) == {path}, 'Ambiguous authored dataset formats')
    if reader is None:
        reader = lambda member: read_bytes(member, directory_identities=directories, directory_states=states, file_states=members)
    captured = {}
    def optional_reader(member):
        if member not in captured:
            captured[member] = reader(member)
        return captured[member]
    raw = optional_reader(path)
    data = parse_json(raw)
    require(type(data) is dict, 'Dataset object required')
    require(type(data.get('evals')) is list and len(data['evals']) <= MAX_CASES, 'Dataset case limit')
    require(type(data) is dict and data.get('skill_name') == name, 'Dataset skill mismatch')
    entries = normalize_dataset_entries(data)
    # The pinned path-based validator reopens the dataset. Apply its agentskills
    # checks to this buffer, retaining its optional-file checks separately.
    require(entries and all(native_spec.AGENTSKILLS_REQUIRED_FIELDS <= entry.keys() for entry in entries),
            'Strict dataset contract failed')
    from skillevaluator.tier3.case_ids import validate_case_ids
    ids = validate_case_ids(entry['id'] for entry in entries)
    case_ids(ids)
    checks = []
    for spec in native_spec.EVALS_SPEC:
        if spec.rel_path == 'evals/evals.json' or spec.scope == native_spec.Scope.OUTPUT \
                or '<subdirs>' in spec.rel_path or spec.kind == 'dir':
            continue
        target = path.parent.parent / spec.rel_path
        if target in tree_entries:
            # Capture before invoking validators that may catch parse/read errors.
            optional_reader(target)
            native_spec._run_file_checks(CapturedInput(target, optional_reader), spec, checks)
    native_spec._check_unrecognised(path.parent.parent, checks)
    require(all(row.status == 'ok' for row in checks), 'Strict dataset contract failed')
    for entry in entries:
        for member in entry.get('files', []):
            relative(member)
            require(member.startswith('evals/files/'), 'Input outside evaluator fixture boundary')
            safe_path(path.parent.parent / member, directory_identities=directories)
    verify_directory_states(states, directories,
                            (directory for directory in states if directory.is_relative_to(path.parent.parent)))
    verify_file_states(members, directories, states, files)
    return {'owner': 'unknown',
            'path': None, 'authored_digest': digest_bytes(raw),
            'case_ids': sorted(ids), 'status': 'configured'}


def validate_skill_metadata(authored, name, *, reader=None):
    import yaml as metadata_yaml
    if reader is None:
        reader = read_bytes
    text = reader(authored / 'SKILL.md').decode()
    require(text.startswith('---\n') and '\n---' in text[4:], 'Missing skill metadata')
    # Front matter is bounded and duplicate-key ambiguity must not choose an owner.
    front = text.split('---', 2)[1]
    try:
        pairs = metadata_yaml.compose(front)
        metadata = metadata_yaml.safe_load(front)
    except (metadata_yaml.YAMLError, RecursionError) as exc:
        raise ValueError('Invalid skill metadata') from exc
    require(pairs is not None and isinstance(pairs, metadata_yaml.MappingNode), 'Invalid skill metadata')
    keys = [key.value for key, _ in pairs.value]
    require(len(keys) == len(set(keys)), 'Ambiguous skill metadata')
    require(type(metadata) is dict and metadata.get('name') == name
            and type(metadata.get('description')) is str and metadata['description'].strip(), 'Invalid skill metadata')
    from skillevaluator.models.skill import SkillFrontmatter
    SkillFrontmatter(**metadata)


def inventory(workspace=ROOT):
    directories = {}
    states = {}
    members = {}
    workspace = safe_path(workspace, directory=True, directory_identities=directories)
    budget = ReadBudget()
    captured = {}
    def reader(path):
        path = safe_path(path, directory_identities=directories)
        if path not in captured:
            captured[path] = read_bytes(path, budget=budget, directory_identities=directories, directory_states=states, file_states=members)
        else:
            verify_file_states(members, directories, states, [path])
        return captured[path]
    def present(path):
        safe_path(path.parent, directory=True, directory_identities=directories)
        fd = open_directory(path.parent, directories, directory_states=states)
        try:
            observed = directory_state(os.fstat(fd))
            states.setdefault(path.parent, observed)
            require(states[path.parent] == observed, 'Input directory entries changed')
            try:
                info = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISREG(info.st_mode):
                    observed_file = file_state(info)
                    require(path not in members or members[path] == observed_file, 'Input member changed')
                    members[path] = observed_file
                return True
            except FileNotFoundError:
                return False
            finally:
                require(directory_state(os.fstat(fd)) == observed, 'Input directory entries changed')
        finally:
            os.close(fd)
    catalog = workspace / '.apm/skills'
    files = safe_tree(catalog, directory_identities=directories, directory_states=states, file_states=members)
    dataset_entries = set(files) | set(directories)
    names = sorted(p.parent.name for p in files if p.name == 'SKILL.md' and p.parent.parent == catalog)
    require(bool(names), 'No local skills found')
    lock_path = workspace / 'apm.lock.yaml'
    lock = read_yaml(lock_path, reader=reader) if present(lock_path) else {'dependencies': [], 'deployments': []}
    require(type(lock) is dict and type(lock.get('dependencies')) is list
            and type(lock.get('deployments')) is list, 'Invalid ownership metadata')
    closed_dependencies = lock.get('dependencies', [])
    deployments = lock.get('deployments', [])
    require(len(closed_dependencies) <= MAX_CASES and len(deployments) <= MAX_INPUT_ENTRIES,
            'Ownership record limit')
    require(all(type(item) is dict for records in (closed_dependencies, deployments) for item in records),
            'Invalid ownership records')
    owners_by_name = {}
    for owner in closed_dependencies:
        if type(owner.get('name')) is str:
            owners_by_name.setdefault(owner['name'], []).append(owner)
    deployments_by_member = {}
    for deployment in deployments:
        if deployment.get('target') == 'codex' and type(deployment.get('value')) is str:
            deployments_by_member.setdefault(deployment['value'], []).append(deployment)
    overlays = workspace / '.github/evals'
    overlay_names = []
    if present(overlays.parent) and present(overlays):
        overlay_files = safe_tree(overlays, directory_identities=directories, directory_states=states, file_states=members)
        safe_path(overlays, directory=True, directory_identities=directories)
        overlay_entries = set(overlay_files) | set(directories)
        dataset_entries.update(overlay_entries)
        overlay_names = [p.parent.parent.name for p in overlay_entries
                         if p.name.startswith('evals.') and p.parent.name == 'evals'
                         and p.parent.parent.parent == overlays]
    discovered = sorted(set(names + overlay_names))
    require(len(discovered) <= MAX_CASES, 'Inventory limit')
    rows = []
    for name in discovered:
        skill_id(name)
        owners = owners_by_name.get(name, [])
        require(len(owners) <= 1 and not (name in names and owners), 'Conflicting active source owners')
        if name in names:
            authored = catalog / name
            validate_skill_metadata(authored, name, reader=reader)
            source_path = authored.relative_to(workspace).as_posix()
            configured = skill_content(authored, reader=reader, directory_identities=directories,
                                       directory_states=states, file_states=members)
            rev = git_revision(workspace)
            if rev is not None and historical_content(workspace, rev, source_path, budget=budget)['digest'] != configured['digest']:
                rev = None
            src = source(name, 'local', 'thetechgy/agent-engineering-baseline', rev, source_path, configured)
            deployment = None
        else:
            require(len(owners) == 1, 'Overlay has no unique skill owner')
            owner = owners[0]
            repository(owner['repo_url']); revision(owner['resolved_commit']); relative(owner['virtual_path'])
            authored = workspace / '.agents/skills' / name
            files = safe_tree(authored, max_entries=2 * MAX_SOURCE_MEMBERS, max_files=MAX_SOURCE_MEMBERS,
                              directory_identities=directories, directory_states=states, file_states=members)
            reject_source_markers(authored, files, directories)
            validate_skill_metadata(authored, name, reader=reader)
            visible = skill_projection_files(authored, files, directory_identities=directories, directory_states=states)
            actual = {p.relative_to(workspace).as_posix(): digest_bytes(reader(p)) for p in files}
            require(actual == owner['deployed_file_hashes'], 'Deployment content drift')
            for member, digest in actual.items():
                matches = deployments_by_member.get(member, [])
                ownership = owner['repo_url'] + '/' + owner['virtual_path']
                require(len(matches) == 1 and matches[0]['active_owner'] == ownership
                        and matches[0]['owners'] == [ownership] and matches[0]['content_hash'] == digest,
                        'Ambiguous deployment ownership')
            if name == 'gh':
                import gh_evaluations as gh
                competing = workspace / '.agents/skills' / gh.COMPETING
                competing_files = safe_tree(competing, max_entries=2 * MAX_SOURCE_MEMBERS,
                                            max_files=MAX_SOURCE_MEMBERS, directory_identities=directories, directory_states=states, file_states=members)
                reject_source_markers(competing, competing_files, directories)
                safe_path(competing, directory=True, directory_identities=directories)
                gh.verify_skill(workspace, read_bytes=reader)
                gh.verify_competing(workspace, read_bytes=reader)
                gh.dataset(workspace, read_bytes=reader)
            src = source(name, 'upstream', owner['repo_url'], owner['resolved_commit'], owner['virtual_path'],
                         content([{'member': p.relative_to(authored).as_posix(),
                                   'digest': actual[p.relative_to(workspace).as_posix()]} for p in visible], 'configured'))
            deployment = '.agents/skills/' + name
        dataset_roots = [overlays / name / 'evals']
        if name in names:
            dataset_roots.append(authored / 'evals')
        datasets = [p for p in dataset_entries if p.parent in dataset_roots and p.name.startswith('evals.')]
        require(len(datasets) <= 1, 'Competing dataset sources')
        suite = strict_dataset(datasets[0], name, reader=reader, directory_identities=directories,
                               directory_states=states, file_states=members) if datasets else None
        if suite:
            suite['owner'] = 'overlay' if datasets[0].is_relative_to(overlays) else 'local'
            suite['path'] = datasets[0].relative_to(workspace).as_posix()
        rows.append({'source': src, 'deployment': deployment, 'suite': suite,
                     'behavioral_status': 'configured' if suite else 'not_configured',
                     'measurement': {'status': 'unavailable', 'reasons': ['results_not_supplied']}})
    result = {'schema_version': 1, 'kind': 'inventory', 'skills': rows}
    verify_directory_states(states, directories)
    verify_file_states(members, directories, states)
    validate_inventory(result)
    return result


def validate_inventory(data):
    closed(data, ('schema_version', 'kind', 'skills'))
    require(type(data['schema_version']) is int and data['schema_version'] == 1 and data['kind'] == 'inventory', 'Inventory version')
    require(type(data['skills']) is list and len(data['skills']) <= MAX_CASES, 'Inventory limit')
    names = []
    for row in data['skills']:
        closed(row, ('source', 'deployment', 'suite', 'behavioral_status', 'measurement'))
        validate_source(row['source']); names.append(row['source']['skill_id']); optional(row['deployment'], relative)
        enum(row['behavioral_status'], ('configured', 'not_configured'))
        closed(row['measurement'], ('status', 'reasons'))
        require(row['measurement'] == {'status': 'unavailable', 'reasons': ['results_not_supplied']}, 'Invented measurement')
        if row['suite'] is not None:
            suite = row['suite']; closed(suite, ('owner', 'path', 'authored_digest', 'case_ids', 'status'))
            enum(suite['owner'], ('local', 'overlay')); relative(suite['path']); sha(suite['authored_digest'])
            case_ids(suite['case_ids']); require(suite['status'] == row['behavioral_status'] == 'configured', 'Suite status')
        else:
            require(row['behavioral_status'] == 'not_configured', 'Missing suite')
    require(names == sorted(set(names)), 'Duplicate inventory source')

POLICY_FIELDS = tuple(reports.POLICY) + ('upstream_revision', 'deterministic_gate', 'workspace_mode',
    'fixture_boundary', 'authorization_policy', 'task_source', 'task_build', 'competing_revision')
GATE_FIELDS = ('evidence', 'activation', 'commands', 'task', 'recovery', 'authorization', 'efficiency', 'gate')
SCORE_FIELDS = ('security', 'skill_execution', 'skill_efficiency', 'accuracy', 'goal_accuracy',
                'behavior_check', 'overall', 'custom')


def validate_build(value):
    closed(value, ('base_image', 'apt_snapshot', 'apt_packages'))
    require(type(value['base_image']) is str and bool(re.fullmatch(r'[a-z0-9./:_-]+@sha256:[0-9a-f]{64}', value['base_image'])), 'Invalid base image')
    require(type(value['apt_snapshot']) is str and bool(re.fullmatch(r'[0-9]{8}T[0-9]{6}Z', value['apt_snapshot'])), 'Invalid apt snapshot')
    closed(value['apt_packages'], reports.GH_TASK_BUILD['apt_packages'])
    for version in value['apt_packages'].values():
        token(version)


def policy_fields(value):
    require(type(value) is dict and set(value) <= set(POLICY_FIELDS), 'Unsupported policy fields')
    return {key: copy.deepcopy(value.get(key)) for key in POLICY_FIELDS}


def validate_policy(value):
    closed(value, ('id', 'published_id', 'provenance', 'patch_digest', 'fields', 'metric_set', 'judge', 'attempts'))
    optional(value['id'], sha); optional(value['published_id'], token); enum(value['provenance'], PROVENANCE)
    optional(value['patch_digest'], sha); optional(value['metric_set'], lambda v: enum(v, ('skill-evaluator-default-v2',)))
    fields = value['fields']; closed(fields, POLICY_FIELDS)
    for key, val in fields.items():
        if val is None:
            continue
        if key.endswith('revision'):
            revision(val)
        elif key in ('baseline', 'stop_on_pass'):
            boolean(val)
        elif key in ('concurrency', 'standard_attempts', 'deterministic_gate'):
            count(val, 100)
        elif key == 'timeout_multiplier':
            number(val, 0.01, 100)
        elif key == 'task_build':
            validate_build(val)
        else:
            token(val)
    if fields['evaluator_revision'] is not None:
        require(fields['evaluator_revision'] == reports.POLICY['evaluator_revision'], 'Unsupported native evaluator')
    judge = value['judge']; closed(judge, ('model', 'provider', 'enabled'))
    optional(judge['model'], token); optional(judge['provider'], token); optional(judge['enabled'], boolean)
    closed(value['attempts'], ('mode', 'maximum', 'stop_on_pass', 'pass_threshold'))
    enum(value['attempts']['mode'], ('standard', 'confirmation', 'unknown'))
    optional(value['attempts']['maximum'], lambda v: count(v, 100))
    require(value['attempts']['maximum'] is None or value['attempts']['maximum'] > 0, 'Zero attempts')
    if value['attempts']['mode'] in reports.MODES and value['attempts']['maximum'] is not None:
        require(value['attempts']['maximum'] == reports.MODES[value['attempts']['mode']],
                'Benchmark mode attempt count mismatch')
    if value['attempts']['mode'] == 'standard' and value['attempts']['maximum'] is not None \
            and fields['standard_attempts'] is not None:
        require(fields['standard_attempts'] == value['attempts']['maximum'], 'Standard attempt policy mismatch')
    optional(value['attempts']['stop_on_pass'], boolean); optional(value['attempts']['pass_threshold'], number)
    if fields['stop_on_pass'] is not None and value['attempts']['stop_on_pass'] is not None:
        require(fields['stop_on_pass'] == value['attempts']['stop_on_pass'], 'Stop-on-pass policy mismatch')
    canonical = {key: value[key] for key in ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')}
    require(value['id'] == (identity(canonical) if value['provenance'] != 'unknown' else None), 'Policy identity mismatch')


def make_policy(fields=None, patch=None, metric_set=None, judge=None, attempts=None, provenance='unknown', published=None):
    value = {'fields': policy_fields(fields or {}), 'patch_digest': patch, 'metric_set': metric_set,
             'judge': judge or {'model': None, 'provider': None, 'enabled': None},
             'attempts': attempts or {'mode': 'unknown', 'maximum': None, 'stop_on_pass': None, 'pass_threshold': None}}
    return {**value, 'id': identity(value) if provenance != 'unknown' else None,
            'provenance': provenance, 'published_id': published}


def validate_condition(value):
    closed(value, ('id', 'provenance', 'target_present', 'workspace_mode', 'competing_skills',
                   'instruction_digest', 'build_digest', 'fixture_digest', 'execution'))
    sha(value['id']); enum(value['provenance'], PROVENANCE); boolean(value['target_present'])
    optional(value['workspace_mode'], lambda v: enum(v, ('isolated', 'group')))
    for key in ('instruction_digest', 'build_digest', 'fixture_digest'):
        optional(value[key], sha)
    require(type(value['competing_skills']) is list and len(value['competing_skills']) <= 100, 'Competing skill limit')
    for src in value['competing_skills']:
        validate_source(src)
    names = [s['skill_id'] for s in value['competing_skills']]
    require(names == sorted(set(names)), 'Competing skill collision')
    closed(value['execution'], ('environment', 'base_image_mode', 'task_source', 'authorization_policy', 'fixture_boundary'))
    for val in value['execution'].values():
        optional(val, token)
    require(value['id'] == identity({k: v for k, v in value.items() if k != 'id'}), 'Arm condition identity mismatch')


def condition(present, provenance='unknown', workspace_mode=None, competing=(), instructions=None,
              build=None, fixture=None, execution=None):
    value = {'provenance': provenance, 'target_present': present, 'workspace_mode': workspace_mode,
             'competing_skills': sorted(competing, key=lambda s: s['skill_id']),
             'instruction_digest': instructions, 'build_digest': build, 'fixture_digest': fixture,
             'execution': execution or {k: None for k in ('environment', 'base_image_mode', 'task_source',
                                                        'authorization_policy', 'fixture_boundary')}}
    return {'id': identity(value), **value}


def validate_reference(value):
    closed(value, ('id', 'artifact_id', 'artifact_digest', 'member', 'locator', 'digest', 'provenance', 'availability'))
    sha(value['id']); token(value['artifact_id']); optional(value['artifact_digest'], sha)
    relative(value['member']); sha(value['digest']); enum(value['provenance'], PROVENANCE)
    enum(value['availability'], ('available', 'unavailable', 'expired'))
    require(type(value['locator']) is list and len(value['locator']) <= 12, 'Locator limit')
    for item in value['locator']:
        if type(item) is int:
            count(item)
        else:
            token(item)
    # Availability can change without changing the reference's stable identity.
    require(value['id'] == identity({k: value[k] for k in ('artifact_id', 'member', 'locator', 'digest')}), 'Reference identity mismatch')
    if any(artifact == value['artifact_id'] for artifact, _ in REVIEWED_REFERENCE_EXPIRY):
        require(value['provenance'] == 'reviewed_extract'
                and (value['artifact_id'], value['artifact_digest']) in REVIEWED_REFERENCE_EXPIRY,
                'Unrecognized reviewed reference identity')
    if value['provenance'] == 'reviewed_extract':
        require(identity({k: value[k] for k in ('artifact_id', 'artifact_digest', 'member', 'locator', 'digest')})
                in REVIEWED_REFERENCE_IDENTITIES, 'Unrecognized reviewed reference identity')


def reference(root, path, artifact, locator=(), extract=None):
    return reference_from_digest(root, path, artifact, digest_bytes(read_bytes(path)), locator, extract)


def reference_from_digest(root, path, artifact, raw_digest, locator=(), extract=None):
    sha(raw_digest)
    member = path.relative_to(root).as_posix()
    value = {'artifact_id': artifact, 'member': member, 'locator': list(locator), 'digest': raw_digest}
    if extract is not None:
        member_record = extract['_members_by_name'].get(member)
        require(member_record is not None and member_record['extract_digest'] == raw_digest, 'Reviewed extract mismatch')
        value['digest'] = member_record['original_digest']
    return {'id': identity(value), **value, 'artifact_digest': extract['archive_digest'] if extract else None,
            'provenance': 'reviewed_extract' if extract else 'runtime_recorded',
            'availability': extract['_reference_availability'] if extract else 'available'}


def evidence(name, kind, cases=(), src=None, policy=None):
    return {'schema_version': 1, 'kind': kind, 'source': src or source(name), 'run_id': None,
            'dataset': {'owner': 'unknown', 'authored_digest': None, 'staged_digest': None,
                        'staged_algorithm': None, 'authored_provenance': 'unknown', 'staged_provenance': 'unknown', 'case_cohort_digest': identity(sorted(cases)), 'case_ids': sorted(cases)},
            'policy': policy or make_policy(), 'arms': [], 'metrics': [], 'observations': [], 'scans': [], 'findings': [],
            'references': [], 'availability': {'status': 'unavailable', 'reasons': ['results_not_supplied'],
                                             'provenance': 'unknown'}}


def observation_id(run, arm, case, native_id, trial, attempt):
    return identity([run, arm, case, native_id, trial, attempt])


def behavioral_identity_missing(data):
    return any(value is None for value in (data['run_id'], data['dataset']['staged_digest'],
               data['policy']['fields']['evaluator_revision'], data['policy']['patch_digest'],
               data['policy']['attempts']['maximum']))


def validate_evidence(data, *, public=False, _observed_at=None):
    observed_at = _observed_at
    if type(data) in (_StaticEvidence, _BehavioralEvidence):
        data = dict(data)
    fields = ('schema_version', 'kind', 'source', 'run_id', 'dataset', 'policy', 'arms', 'metrics',
              'observations', 'scans', 'findings', 'references', 'availability')
    closed(data, fields)
    require(type(data['schema_version']) is int and data['schema_version'] == 1, 'Evidence version')
    enum(data['kind'], ('behavioral', 'static')); validate_source(data['source']); optional(data['run_id'], token)
    ds = data['dataset']; closed(ds, ('owner', 'authored_digest', 'staged_digest', 'staged_algorithm', 'authored_provenance', 'staged_provenance', 'case_cohort_digest', 'case_ids'))
    enum(ds['owner'], ('local', 'overlay', 'unknown'))
    for key in ('authored_digest', 'staged_digest'):
        optional(ds[key], sha)
    optional(ds['staged_algorithm'], lambda v: enum(v, ('skill-evaluator-dataset-snapshot/1',)))
    enum(ds['authored_provenance'], PROVENANCE); enum(ds['staged_provenance'], PROVENANCE)
    require((ds['authored_digest'] is None) == (ds['authored_provenance'] == 'unknown'), 'Authored provenance mismatch')
    require((ds['staged_digest'] is None) == (ds['staged_provenance'] == 'unknown'), 'Staged provenance mismatch')
    require(ds['staged_digest'] is None or ds['staged_algorithm'] == 'skill-evaluator-dataset-snapshot/1',
            'Missing staged digest algorithm')
    ids = case_ids(ds['case_ids']); require(ds['case_cohort_digest'] == identity(sorted(ids)), 'Cohort mismatch')
    validate_policy(data['policy'])
    availability = data['availability']; closed(availability, ('status', 'reasons', 'provenance'))
    enum(availability['status'], ('complete', 'incomplete', 'unavailable')); enum(availability['provenance'], PROVENANCE)
    require(type(availability['reasons']) is list and len(availability['reasons']) <= len(REASONS)
            and len(set(availability['reasons'])) == len(availability['reasons']), 'Invalid reasons')
    for reason in availability['reasons']:
        enum(reason, REASONS)
    require((availability['status'] == 'complete') == (not availability['reasons']), 'Contradictory availability')
    references = data['references']; require(type(references) is list and len(references) <= MAX_REFERENCES, 'Reference limit')
    ref_ids = set(); refs_by_id = {}
    for ref in references:
        validate_reference(ref); require(ref['id'] not in ref_ids, 'Duplicate reference'); ref_ids.add(ref['id'])
        refs_by_id[ref['id']] = ref
        deadline = REVIEWED_REFERENCE_EXPIRY.get((ref['artifact_id'], ref['artifact_digest']))
        if ref['provenance'] == 'reviewed_extract':
            require(deadline is not None, 'Missing reviewed reference expiration')
        if deadline is not None:
            if observed_at is None:
                observed_at = utc_now()
            if observed_at >= datetime.fromisoformat(deadline):
                require(ref['availability'] == 'expired', 'Reviewed reference must be expired')
        if ref['availability'] != 'available':
            reason = 'reference_expired' if ref['availability'] == 'expired' else 'reference_unavailable'
            require(availability['status'] == 'incomplete' and reason in availability['reasons'], 'Missing reference limitation')
    if availability['provenance'] == 'reviewed_extract':
        require(bool(references) and all(ref['provenance'] == 'reviewed_extract' for ref in references),
                'Reviewed availability missing reviewed references')
    require(type(data['observations']) is list and len(data['observations']) <= MAX_TRIALS, 'Trial limit exceeded')
    seen = set(); native_ids = set(); observation_ids = set()
    for obs in data['observations']:
        obs_fields = OBSERVATION_FIELDS
        closed(obs, obs_fields if public else obs_fields + ('native_id', 'native_trial', 'native_task'))
        sha(obs['id']); enum(obs['arm'], ('with_skill', 'without_skill')); require(obs['case_id'] in ids, 'Unknown case')
        optional(obs['attempt'], lambda v: count(v, 100)); require(obs['attempt'] is None or obs['attempt'] >= 1, 'Invalid attempt index')
        if obs['attempt'] is None:
            require(availability['status'] == 'incomplete' and 'metadata_missing' in availability['reasons'],
                    'Missing attempt metadata limitation')
        optional(obs['score'], number); optional(obs['rubric_pass'], boolean)
        optional(obs['deterministic_gate'], number)
        closed(obs['scores'], SCORE_FIELDS)
        for val in obs['scores'].values():
            optional(val, number)
        require(obs['scores']['overall'] == obs['score'], 'Conflicting overall score')
        if obs['score'] is None:
            require(obs['rubric_pass'] is None, 'Unscored trial has rubric outcome')
        closed(obs['deterministic_scores'], GATE_FIELDS)
        for val in obs['deterministic_scores'].values():
            optional(val, lambda v: number(v, 0, 1))
        gates = obs['deterministic_scores']
        if any(value is not None for value in gates.values()):
            require(data['source']['skill_id'] == 'gh', 'Unsupported custom grading contract')
            require(all(value is not None and value in (0, 1) for value in gates.values()),
                    'Invalid deterministic observation')
        require((gates['gate'] is None) == (obs['deterministic_gate'] is None), 'Missing gate detail')
        if gates['gate'] is not None:
            require(all(v is not None for v in gates.values()) and gates['gate'] == obs['deterministic_gate']
                    and gates['gate'] == float(all(v == 1 for k, v in gates.items() if k != 'gate')), 'Gate consistency')
        key = (obs['arm'], obs['case_id'], obs['attempt'] if obs['attempt'] is not None else obs['id'])
        require(key not in seen and obs['id'] not in observation_ids, 'Duplicate attempt'); seen.add(key); observation_ids.add(obs['id'])
        if not public:
            token(obs['native_id']); token(obs['native_trial']); relative(obs['native_task'])
            require((obs['arm'], obs['native_id']) not in native_ids, 'Duplicate native trial ID')
            native_ids.add((obs['arm'], obs['native_id']))
            require(obs['id'] == observation_id(data['run_id'], obs['arm'], obs['case_id'], obs['native_id'],
                                              obs['native_trial'], obs['attempt']), 'Observation identity mismatch')
        require(type(obs['references']) is list and 1 <= len(obs['references']) <= 10
                and set(obs['references']) <= ref_ids, 'Dangling observation reference')
        if not public:
            trial_result_found = False
            for ref_id in obs['references']:
                ref = refs_by_id[ref_id]; parts = ref['member'].split('/')
                require(len(parts) >= 4 and parts[:2] == ['results', data['source']['skill_id']]
                        and (data['run_id'] is None or parts[2] == data['run_id']),
                        'Observation reference origin mismatch')
                if parts[3:] == ['result.json'] and ref['locator'] == ['agents', 'codex']:
                    require('metadata_missing' in availability['reasons'], 'Observation reference origin mismatch')
                    continue  # Existing partial-evidence fallback when the arm summary is absent.
                require(parts[3:5] == ['codex', obs['arm'].replace('_', '-')],
                        'Observation reference origin mismatch')
                tail = parts[5:]
                trial_result = tail == ['trials', obs['native_trial'], 'result.json']
                require(trial_result and ref['locator'] in ([], ['verifier_result'], ['verifier_result', 'rewards'])
                        or tail in (['trials', obs['native_trial'], 'reward.json'], ['summary.json'])
                        and ref['locator'] == [], 'Observation reference origin mismatch')
                trial_result_found |= trial_result
            require(trial_result_found, 'Observation reference origin mismatch')
    require(type(data['arms']) is list and len(data['arms']) <= 2, 'Invalid arms')
    arm_names = []
    for arm in data['arms']:
        closed(arm, ('name', 'condition', 'coverage', 'execution_status', 'execution_error_count', 'rubric'))
        enum(arm['name'], ('with_skill', 'without_skill')); arm_names.append(arm['name']); validate_condition(arm['condition'])
        require(arm['condition']['target_present'] == (arm['name'] == 'with_skill'), 'Arm target mismatch')
        for key in ('environment', 'task_source', 'authorization_policy', 'fixture_boundary', 'workspace_mode'):
            declared = data['policy']['fields'][key]
            observed = arm['condition'][key] if key == 'workspace_mode' else arm['condition']['execution'][key]
            require(declared is None or observed is None or declared == observed,
                    'Task source policy mismatch' if key == 'task_source' else 'Arm condition policy mismatch')
        enum(arm['execution_status'], ('succeeded', 'failed', 'incomplete', 'unknown'))
        count(arm['execution_error_count'])
        cov = arm['coverage']; closed(cov, ('expected_cases', 'expected_attempts', 'recorded_attempts', 'scored_attempts', 'unscored_attempts', 'case_details'))
        count(cov['expected_cases'], MAX_CASES); require(cov['expected_cases'] == len(ids), 'Case denominator mismatch')
        for key in ('expected_attempts', 'recorded_attempts', 'scored_attempts', 'unscored_attempts'):
            optional(cov[key], count)
        enum(cov['case_details'], ('complete', 'partial', 'unavailable'))
        if cov['expected_attempts'] is not None:
            require(all(cov[key] is None or cov[key] <= cov['expected_attempts']
                        for key in ('recorded_attempts', 'scored_attempts')), 'Excess native trials')
        if cov['scored_attempts'] is not None and cov['recorded_attempts'] is not None:
            require(cov['scored_attempts'] <= cov['recorded_attempts']
                    and cov['unscored_attempts'] == cov['recorded_attempts'] - cov['scored_attempts'], 'Invalid coverage counts')
        else:
            require(cov['unscored_attempts'] is None, 'Invented unscored count')
        attempts = data['policy']['attempts']['maximum']
        if attempts is not None and cov['expected_attempts'] is not None:
            require(cov['expected_attempts'] == len(ids) * attempts, 'Expected attempt mismatch')
        recorded = [o for o in data['observations'] if o['arm'] == arm['name']]
        if cov['recorded_attempts'] is not None:
            require(len(recorded) <= cov['recorded_attempts'], 'Details exceed recorded trials')
        if cov['scored_attempts'] is not None:
            require(sum(o['score'] is not None for o in recorded) <= cov['scored_attempts'], 'Details exceed scored trials')
        if cov['case_details'] == 'complete':
            require(len(recorded) == cov['recorded_attempts']
                    and sum(o['score'] is not None for o in recorded) == cov['scored_attempts'], 'Case detail coverage mismatch')
        if attempts is not None:
            require(all(o['attempt'] is None or o['attempt'] <= attempts for o in recorded), 'Excess attempt index')
        rubric = arm['rubric']; closed(rubric, ('passed_cases', 'total_cases', 'threshold'))
        optional(rubric['passed_cases'], lambda v: count(v, MAX_CASES)); optional(rubric['total_cases'], lambda v: count(v, MAX_CASES))
        optional(rubric['threshold'], number)
        policy_threshold = data['policy']['attempts']['pass_threshold']
        if rubric['threshold'] is not None and policy_threshold is not None:
            require(rubric['threshold'] == policy_threshold, 'Rubric attempt-policy threshold mismatch')
        threshold = rubric['threshold'] if rubric['threshold'] is not None else policy_threshold
        require((rubric['passed_cases'] is None) == (rubric['total_cases'] is None),
                'Missing rubric aggregate pair')
        if rubric['total_cases'] is not None:
            require(rubric['total_cases'] == len(ids) and rubric['passed_cases'] is not None
                    and rubric['passed_cases'] <= rubric['total_cases'], 'Rubric denominator mismatch')
            if cov['case_details'] == 'complete':
                passes = {o['case_id'] for o in recorded if o['rubric_pass'] is True}
                require(len(passes) == rubric['passed_cases'], 'Rubric count mismatch')
        if threshold is not None:
            if cov['case_details'] == 'complete':
                require(all(o['score'] is None or o['rubric_pass'] is not None for o in recorded),
                        'Missing scored rubric outcome')
            require(all(o['rubric_pass'] is None or o['score'] is not None
                        and o['rubric_pass'] == (o['score'] >= threshold) for o in recorded),
                    'Contradictory native rubric pass')
        if arm['execution_status'] == 'succeeded':
            require(arm['execution_error_count'] == 0, 'Succeeded arm has errors')
        elif availability['status'] != 'unavailable':
            require(availability['status'] == 'incomplete' and 'execution_incomplete' in availability['reasons'],
                    'Missing execution limitation')
        if availability['status'] == 'incomplete':
            if cov['recorded_attempts'] != cov['expected_attempts'] \
                    or cov['scored_attempts'] != cov['expected_attempts']:
                require('coverage_missing' in availability['reasons'], 'Missing coverage limitation')
            if cov['case_details'] != 'complete':
                require('case_details_missing' in availability['reasons'], 'Missing case detail limitation')
        if availability['status'] == 'complete':
            require(arm['execution_status'] == 'succeeded' and cov['scored_attempts'] == cov['expected_attempts']
                    and cov['recorded_attempts'] == cov['expected_attempts'] and cov['case_details'] == 'complete', 'Incomplete evidence promotion')
            require(all(o['attempt'] is not None for o in recorded), 'Unknown attempt identity')
    require(len(arm_names) == len(set(arm_names)), 'Duplicate arm')
    require(type(data['metrics']) is list and len(data['metrics']) <= 4, 'Metric limit')
    metric_names = []
    for row in data['metrics']:
        closed(row, ('name', 'unit', 'value')); require(row['name'] in reports.METRICS and row['unit'] == 'score', 'Unknown native metric')
        number(row['value'], -1 if row['name'] == 'Skill Lift' else 0, 1); metric_names.append(row['name'])
    require(len(metric_names) == len(set(metric_names)), 'Duplicate metric')
    require(type(data['scans']) is list and len(data['scans']) <= 100, 'Scan limit')
    scanner_ids = []
    for scan in data['scans']:
        scan_fields = ('scanner', 'status', 'passed', 'severity_counts', 'references')
        closed(scan, scan_fields + ('blocking',) if 'blocking' in scan else scan_fields)
        boolean(scan.get('blocking', True))
        token(scan['scanner']); scanner_ids.append(scan['scanner']); enum(scan['status'], ('passed', 'failed', 'incomplete', 'skipped'))
        optional(scan['passed'], boolean)
        if scan['status'] in ('passed', 'failed'):
            require(scan['passed'] == (scan['status'] == 'passed'), 'Contradictory scanner outcome')
        closed(scan['severity_counts'], ('critical', 'high', 'medium', 'low'))
        for val in scan['severity_counts'].values():
            optional(val, count)
        require(type(scan['references']) is list and set(scan['references']) <= ref_ids, 'Dangling scan reference')
        if scan['status'] in ('incomplete', 'skipped'):
            require('scan_incomplete' in availability['reasons'], 'Missing scan limitation')
        if availability['status'] == 'complete':
            require(scan['status'] not in ('incomplete', 'skipped'), 'Incomplete scan promotion')
            require(bool(scan['references']), 'Complete scan missing reference')
    require(len(scanner_ids) == len(set(scanner_ids)), 'Duplicate scanner')
    severity_fields = ('critical', 'high', 'medium', 'low')
    detailed = {scanner: dict.fromkeys(severity_fields, 0) for scanner in scanner_ids}
    require(type(data['findings']) is list and len(data['findings']) <= MAX_TRIALS, 'Finding limit')
    for finding in data['findings']:
        closed(finding, ('scanner', 'severity', 'check', 'member', 'line', 'reference'))
        require(finding['scanner'] in scanner_ids, 'Unknown finding scanner')
        enum(finding['severity'], ('critical', 'high', 'medium', 'low', 'info'))
        if finding['severity'] in severity_fields:
            detailed[finding['scanner']][finding['severity']] += 1
        optional(finding['check'], token); optional(finding['member'], relative)
        optional(finding['line'], lambda v: count(v, 10000000))
        require(finding['reference'] in ref_ids, 'Dangling finding reference')
    for scan in data['scans']:
        for level, total in detailed[scan['scanner']].items():
            reported = scan['severity_counts'][level]
            require(reported is None or total <= reported, 'Detailed findings exceed scanner total')
    aggregate = next((scan for scan in data['scans'] if scan['scanner'] == 'catalog-total'), None)
    if aggregate is not None:
        enum(aggregate['status'], ('passed', 'failed', 'incomplete'))
        require(type(aggregate['passed']) is bool, 'Missing static aggregate pass result')
        require(all(total is not None for total in aggregate['severity_counts'].values()),
                'Unknown static aggregate totals')
        validators = [scan for scan in data['scans'] if scan is not aggregate]
        for level, total in aggregate['severity_counts'].items():
            if total is not None:
                require(sum(counts[level] for counts in detailed.values()) <= total,
                        'Detailed findings exceed aggregate total')
                known = [scan['severity_counts'][level] for scan in validators]
                require(sum(value for value in known if value is not None) <= total,
                        'Scanner totals exceed aggregate total')
                if known and all(value is not None for value in known):
                    require(sum(known) == total, 'Contradictory static finding counts')
    if availability['status'] == 'unavailable':
        require('results_not_supplied' in availability['reasons'], 'Unavailable evidence missing results limitation')
        require(not data['observations'] and not data['metrics'] and not data['scans'] and not data['findings'], 'Unavailable evidence has observations')
        for arm in data['arms']:
            require(all(arm['coverage'][k] is None for k in ('recorded_attempts', 'scored_attempts', 'unscored_attempts')), 'Invented observed count')
    elif data['kind'] == 'behavioral':
        require(not data['scans'] and not data['findings'], 'Behavioral report implies static scans')
        require(sorted(arm_names) == ['with_skill', 'without_skill'], 'Missing comparison arms')
        if len(data['metrics']) < 4:
            require(availability['status'] == 'incomplete' and 'coverage_missing' in availability['reasons'],
                    'Missing metric coverage limitation')
        if data['source']['content']['digest'] is None:
            require(availability['status'] == 'incomplete' and 'source_unavailable' in availability['reasons'],
                    'Behavioral source unavailable')
        if behavioral_identity_missing(data):
            require(availability['status'] == 'incomplete' and 'metadata_missing' in availability['reasons'],
                    'Missing behavioral identity limitation')
        if availability['status'] == 'complete':
            require(bool(ids), 'Empty complete cohort')
            require(len(data['metrics']) == 4, 'Incomplete metrics')
    if data['kind'] == 'static':
        require(not data['arms'] and not data['metrics'] and not data['observations'], 'Static report implies behavior')
        require(availability['status'] == 'unavailable' or bool(data['scans']), 'Static evidence missing scans')
        require(availability['status'] == 'unavailable' or aggregate is not None,
                'Static evidence missing aggregate scan')
        if availability['status'] != 'unavailable' and data['source']['content']['digest'] is None:
            require(availability['status'] == 'incomplete' and 'source_unavailable' in availability['reasons'],
                    'Static source unavailable')
    if availability['status'] == 'complete':
        require(all(r['availability'] == 'available' for r in references), 'Unavailable reference promotion')
    for obs in data['observations']:
        if any(refs_by_id[ref]['provenance'] == 'reviewed_extract' for ref in obs['references']):
            require(identity({key: obs[key] for key in OBSERVATION_FIELDS}) in REVIEWED_OBSERVATION_PAYLOADS,
                    'Unrecognized reviewed observation payload')
    if data['kind'] == 'behavioral' and any(ref['provenance'] == 'reviewed_extract' for ref in references):
        require(availability['provenance'] == 'reviewed_extract', 'Reviewed availability provenance mismatch')
        require(all(REVIEWED_METRIC_VALUES.get(row['name']) == row['value'] for row in data['metrics']),
                'Unrecognized reviewed metric value')
        require(identity(data['source']) in REVIEWED_SOURCE_IDENTITIES, 'Unrecognized reviewed source identity')
        require(identity({key: data[key] for key in ('run_id', 'dataset', 'policy', 'arms')})
                in REVIEWED_EXECUTION_CONTRACTS, 'Unrecognized reviewed execution contract')
    if data['kind'] == 'static' and aggregate is not None:
        report_pattern = r'reports/' + re.escape(data['source']['skill_id']) + r'/skillevaluator-output-[0-9]{14}\.json'
        report_refs = {ref['id'] for ref in references if re.fullmatch(report_pattern, ref['member'])}
        require(all(ref['id'] in report_refs or ref['member'] in ('reports/catalog-summary.json', 'versions.json')
                    for ref in references), 'Static reference skill mismatch')
        require(bool(report_refs) and all(ref in report_refs for ref in aggregate['references'])
                and all(ref in report_refs for scan in validators for ref in scan['references'])
                and all(finding['reference'] in report_refs for finding in data['findings']),
                'Static reference skill mismatch')
        report_keys = {(refs_by_id[ref]['artifact_id'], refs_by_id[ref]['member'], refs_by_id[ref]['digest']) for ref in report_refs}
        require(len(report_keys) == 1 and all(refs_by_id[ref]['locator'] == [] for ref in aggregate['references']),
                'Static claim locator mismatch')
        positions = {}; index = 0
        for scan in validators:
            diagnostic = (scan['status'] in ('incomplete', 'skipped') and scan['passed'] is None
                          and all(value is None for value in scan['severity_counts'].values())
                          and all(refs_by_id[ref]['locator'] == [] for ref in scan['references']))
            locator = [] if diagnostic else ['results', index]
            require(all(refs_by_id[ref]['locator'] == locator for ref in scan['references']), 'Static claim locator mismatch')
            if not diagnostic:
                positions[scan['scanner']] = index; index += 1
        finding_indices = dict.fromkeys(positions, 0)
        for finding in data['findings']:
            scanner = finding['scanner']
            require(scanner in positions and refs_by_id[finding['reference']]['locator'] ==
                    ['results', positions[scanner], 'findings', finding_indices[scanner]], 'Static claim locator mismatch')
            finding_indices[scanner] += 1
        require(aggregate['passed'] == all(scan['passed'] is True or not scan.get('blocking', True)
                                         for scan in validators), 'Static aggregate gate contradiction')
        expected = ('incomplete' if any(scan['status'] == 'incomplete' for scan in validators)
                    else 'passed' if aggregate['passed'] else 'failed')
        require(aggregate['status'] == expected, 'Static aggregate status contradiction')
    depth(data, 12 if public else 32)
    if public:
        require(len(encoded(data)) <= PUBLIC_LIMIT, 'Public report size exceeded')
    return data


def static_claim_identity(data, blocking_defaults):
    claims = {key: copy.deepcopy(data[key]) for key in
              ('source', 'run_id', 'dataset', 'policy', 'arms', 'metrics', 'scans', 'findings', 'references')}
    claims['provenance'] = data['availability']['provenance']
    defaults = dict(blocking_defaults)
    for scan in claims['scans']:
        scan.setdefault('blocking', defaults.get(scan['scanner'], True))
        scan['references'].sort()
    claims['scans'].sort(key=lambda scan: scan['scanner'])
    claims['findings'].sort(key=lambda finding: finding['reference'])
    for ref in claims['references']:
        ref.pop('availability')  # Conservative availability changes do not relabel native claims.
    claims['references'].sort(key=lambda ref: ref['id'])
    return identity(claims)


class _StaticEvidence(dict):
    """A data-only record with a transient witness from captured native bytes."""
    __slots__ = ('_claim_digest', '_blocking_defaults')

    def __init__(self, data, claim_digest, blocking_defaults):
        super().__init__(data)
        object.__setattr__(self, '_claim_digest', claim_digest)
        object.__setattr__(self, '_blocking_defaults', blocking_defaults)

    def __setattr__(self, name, value):
        raise AttributeError('Immutable native witness')

    def __deepcopy__(self, memo):
        result = _StaticEvidence(copy.deepcopy(dict(self), memo), self._claim_digest, self._blocking_defaults)
        memo[id(self)] = result
        return result


def behavioral_claim_identity(data):
    claims = {key: copy.deepcopy(data[key]) for key in
              ('source', 'run_id', 'dataset', 'policy', 'arms', 'observations', 'metrics', 'references')}
    claims['provenance'] = data['availability']['provenance']
    for obs in claims['observations']:
        obs['references'].sort()
    claims['observations'].sort(key=lambda obs: obs['id'])
    claims['metrics'].sort(key=lambda row: row['name'])
    for ref in claims['references']:
        ref.pop('availability')
    claims['references'].sort(key=lambda ref: ref['id'])
    return identity(claims)


class _BehavioralEvidence(dict):
    """Transient witness for ordinary runtime observations and headline metrics."""
    __slots__ = ('_claim_digest', '_required_reasons')

    def __init__(self, data, claim_digest, *, required_reasons=None):
        super().__init__(data)
        object.__setattr__(self, '_claim_digest', claim_digest)
        object.__setattr__(self, '_required_reasons', tuple(data['availability']['reasons']
                           if required_reasons is None else required_reasons))

    def __setattr__(self, name, value):
        raise AttributeError('Immutable native witness')

    def __deepcopy__(self, memo):
        result = _BehavioralEvidence(copy.deepcopy(dict(self), memo), self._claim_digest,
                                     required_reasons=self._required_reasons)
        memo[id(self)] = result
        return result


def behavioral_claims_need_witness(data):
    # Every measured behavioral record needs authenticated claims. Reviewed
    # references are independently bound to the pinned payload allowlists.
    return (data['kind'] == 'behavioral' and data['availability']['status'] != 'unavailable'
            and not (data['references'] and all(ref['provenance'] == 'reviewed_extract' for ref in data['references'])))


def project(data, *, static_bundle=None, behavioral_bundle=None):
    observed_at = utc_now()
    validate_evidence(data, _observed_at=observed_at)
    if data['kind'] == 'static' and data['availability']['status'] != 'unavailable':
        if type(data) is _StaticEvidence:
            witness = data
        else:
            require(static_bundle is not None, 'Retained native static bundle required')
            witness = normalize_static(Path(static_bundle), data['source']['skill_id'])
        require(static_claim_identity(data, witness._blocking_defaults) == witness._claim_digest,
                'Static claims differ from retained native evidence')
    if behavioral_claims_need_witness(data):
        if type(data) is _BehavioralEvidence:
            witness = data
        else:
            require(behavioral_bundle is not None, 'Retained native behavioral bundle required')
            witness = normalize_behavioral(Path(behavioral_bundle), data['source']['skill_id'], data['run_id'])
            require(type(witness) is _BehavioralEvidence, 'Native behavioral provenance mismatch')
        require(behavioral_claim_identity(data) == witness._claim_digest,
                'Behavioral claims differ from retained native evidence')
        require(set(witness._required_reasons) <= set(data['availability']['reasons']),
                'Native behavioral limitations removed')
    # Every object is rebuilt from fixed fields. A native report is never accepted.
    out = {key: copy.deepcopy(data[key]) for key in ('schema_version', 'kind', 'source', 'run_id', 'dataset',
           'policy', 'arms', 'metrics', 'scans', 'findings', 'references', 'availability')}
    out['observations'] = [{key: copy.deepcopy(obs[key]) for key in
        OBSERVATION_FIELDS}
        for obs in data['observations']]
    validate_evidence(out, public=True, _observed_at=observed_at)
    return out


def load_extract(root, *, budget=None, _observed_at=None, directory_identities=None, entries=None, directory_states=None, file_states=None):
    path = root / 'extract-manifest.json'
    present = path in entries if entries is not None else path.exists()
    if not present:
        return None
    raw = read_bytes(path, budget=budget, directory_identities=directory_identities, directory_states=directory_states, file_states=file_states)
    require(digest_bytes(raw) in REVIEWED_EXTRACT_MANIFESTS, 'Unrecognized reviewed extract manifest')
    value = parse_json(raw)
    closed(value, ('schema_version', 'artifact_id', 'archive_digest', 'origin', 'members'))
    require(value['schema_version'] == 1, 'Extract version'); token(value['artifact_id']); sha(value['archive_digest'])
    closed(value['origin'], ('repository', 'run_id', 'artifact_id', 'artifact_name', 'expires_at'))
    repository(value['origin']['repository'])
    for key in ('run_id', 'artifact_id', 'artifact_name'):
        token(value['origin'][key])
    require(bool(re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z', value['origin']['expires_at'])), 'Invalid recorded expiration')
    require(value['artifact_id'] == 'github-artifact-' + value['origin']['artifact_id'], 'Extract artifact identity mismatch')
    require(REVIEWED_REFERENCE_EXPIRY.get((value['artifact_id'], value['archive_digest']))
            == value['origin']['expires_at'], 'Reviewed reference expiration mismatch')
    require(type(value['members']) is list and len(value['members']) <= MAX_REFERENCES, 'Extract limit')
    names = []
    for row in value['members']:
        closed(row, ('member', 'original_digest', 'extract_digest'))
        relative(row['member']); sha(row['original_digest']); sha(row['extract_digest']); names.append(row['member'])
    require(len(names) == len(set(names)), 'Duplicate extract member')
    value['_members_by_name'] = {row['member']: row for row in value['members']}
    # One time observation for the whole normalization. No durable-original
    # retention is recorded by the supported manifest, so expiry is fail-closed.
    deadline = datetime.fromisoformat(value['origin']['expires_at'])
    observed_at = utc_now() if _observed_at is None else _observed_at
    value['_reference_availability'] = 'expired' if observed_at >= deadline else 'available'
    return value


def select_run(root, name, selected, *, entries=None, directory_identities=None):
    base = root / 'results' / name
    safe_path(base, directory=True, directory_identities=directory_identities)
    candidates = []
    children = sorted(p for p in entries if p.parent == base) if entries is not None else base.iterdir()
    for path in children:
        # An alias is never selected or followed; all links are rejected by safe_tree.
        if path.name == 'latest':
            continue
        safe_path(path, directory=True, directory_identities=directory_identities); token(path.name); candidates.append(path)
    if selected:
        token(selected)
        matches = [p for p in candidates if p.name == selected]
        require(len(matches) == 1, 'Unknown selected run')
        return matches[0]
    require(len(candidates) == 1, 'Explicit --run required for ambiguous native runs')
    return candidates[0]


def validate_runtime_versions(versions):
    require(type(versions) is dict, 'Native versions object required')
    if versions.get('skillevaluator') is not None:
        require(versions['skillevaluator'] == '0.3.0', 'Unsupported native evaluator')
    if versions.get('evaluator_revision') is not None:
        require(versions['evaluator_revision'] == reports.POLICY['evaluator_revision'], 'Unsupported native evaluator')


def native_error_count(record):
    errors = record.get('execution_errors', [])
    require(type(errors) is list and len(errors) <= MAX_TRIALS
            and all(type(error) is str for error in errors), 'Invalid native execution errors')
    return len(errors)


def summary_error_count(summary):
    errors = native_error_count(summary)
    job_failure = summary.get('job_failure')
    require(job_failure is None or type(job_failure) is str, 'Invalid native job failure')
    trial_failures = summary.get('trial_failures', [])
    require(type(trial_failures) is list and len(trial_failures) <= MAX_TRIALS
            and all(type(failure) is dict for failure in trial_failures), 'Invalid native trial failures')
    # The pinned load_agent_data appends job failure and each trial failure to
    # condition errors; raw summary and reported arm arrays need not have equal lengths.
    return errors + bool(job_failure) + len(trial_failures)


def reconcile_policy(fields, versions, config, agent, attempt_policy):
    """Reject supplied identities that contradict known runtime/configuration values."""
    fields = policy_fields(fields)
    if fields['evaluator_revision'] is not None:
        require(fields['evaluator_revision'] == reports.POLICY['evaluator_revision'], 'Unsupported native evaluator')
    harbor = config.get('harbor', {})
    observations = {key: [versions.get(key)] for key in
                    ('evaluator_revision', 'harbor', 'docker_compose', 'python')}
    observations.update({
        'model': [config.get('provider', {}).get('model'), config.get('agents', {}).get('codex', {}).get('model'),
                  agent.get('model')],
        'provider': [config.get('provider', {}).get('name')],
        'grading': [config.get('grading', {}).get('mode')],
        'environment': [harbor.get('environment', {}).get('value')],
        'concurrency': [harbor.get('n_concurrent')],
        'timeout_multiplier': [harbor.get('timeout_multiplier')],
        'task_source': [config.get('task_source')],
        'stop_on_pass': [harbor.get('stop_on_pass'), attempt_policy.get('stop_on_pass')],
    })
    for key, values in observations.items():
        declared = fields[key]
        if declared is None:
            continue
        for observed in values:
            if observed is None:
                continue
            if key == 'python':
                require(type(declared) is str and type(observed) is str
                        and re.fullmatch(r'[0-9]+(?:\.[0-9]+){0,2}', declared)
                        and re.fullmatch(r'[0-9]+(?:\.[0-9]+){0,2}', observed), 'Invalid Python version')
                expected = tuple(map(int, declared.split('.')))
                actual = tuple(map(int, observed.split('.')))
                require(actual[:len(expected)] == expected, 'Runtime/policy disagreement')
            else:
                if key == 'timeout_multiplier':
                    number(observed, 0.01, 100)
                else:
                    require(type(declared) is type(observed), 'Runtime/policy disagreement')
                require(declared == observed, 'Runtime/policy disagreement')
    for key in ('max_attempts', 'stop_on_pass'):
        config_key = 'n_attempts' if key == 'max_attempts' else key
        if harbor.get(config_key) is not None and attempt_policy.get(key) is not None:
            require(type(harbor[config_key]) is type(attempt_policy[key])
                    and harbor[config_key] == attempt_policy[key], 'Attempt policy disagreement')


def normalize_behavioral(root, name, selected=None, workspace=ROOT):
    from skillevaluator.tier3.harbor import report_data as native_reports
    from skillevaluator.evaluation import EvaluationService
    from skillevaluator.tier3.case_ids import validate_case_id
    directory_identities = {}
    directory_states = {}
    file_states = {}
    root = safe_path(root, directory=True, directory_identities=directory_identities)
    files = safe_tree(root, directory_identities=directory_identities, directory_states=directory_states, file_states=file_states); skill_id(name)
    scanned_entries = set(files) | set(directory_identities)
    run = select_run(root, name, selected, entries=scanned_entries, directory_identities=directory_identities)
    budget = ReadBudget()
    observed_at = utc_now()
    extract = load_extract(root, budget=budget, _observed_at=observed_at,
                           directory_identities=directory_identities, entries=scanned_entries, directory_states=directory_states, file_states=file_states)
    artifact = extract['artifact_id'] if extract else run.name
    member_digests = {}
    def read_member(path, *, native_snapshot=False):
        require(path in scanned_entries, 'Unscanned behavioral member')
        require(path not in member_digests, 'Duplicate behavioral member read')
        raw = read_bytes(path, budget=budget, directory_identities=directory_identities, directory_states=directory_states, file_states=file_states)
        if native_snapshot:
            require(len(raw) <= native_reports._MAX_JSON_BYTES, 'Native snapshot byte limit')
        value = parse_json(raw)
        if native_snapshot:
            native_reports._validate_json_tree(value)
        member_digests[path] = digest_bytes(raw)
        return value
    result_path = run / 'result.json'; result = read_member(result_path)
    require(type(result) is dict, 'Native report object required')
    require(result.get('skill_name') == name and type(result.get('agents')) is dict
            and set(result['agents']) == {'codex'} and type(result['agents']['codex']) is dict,
            'Native identity/agent mismatch')
    require(result.get('report_status') in ('complete', 'incomplete'), 'Unknown native envelope')
    config_path = run / 'run_config.json'
    has_config = config_path in scanned_entries
    config = read_member(config_path) if has_config else result.get('run_config', {})
    require(type(config) is dict, 'Native configuration object required')
    if has_config and 'run_config' in result:
        require(config == result['run_config'], 'Conflicting native configuration')
    refs = []; ref_ids = set()
    def ref(path, locator=()):
        row = reference_from_digest(root, path, artifact, member_digests[path], locator, extract)
        if row['id'] not in ref_ids:
            refs.append(row)
            ref_ids.add(row['id'])
        return row['id']
    ref(result_path)
    if has_config:
        ref(config_path)
    limitations = set()
    provenance_path = root / 'provenance.json'
    has_provenance = provenance_path in scanned_entries
    provenance = read_member(provenance_path) if has_provenance else {}
    require(type(provenance) is dict, 'Native provenance object required')
    recovery = provenance.get('status') == 'incomplete'
    if recovery:
        require(result['report_status'] == 'incomplete' or result.get('diagnostic_only') is True,
                'Contradictory recovery status')
    if provenance:
        require((recovery and 'schema_version' not in provenance or
                 type(provenance.get('schema_version')) is int and provenance['schema_version'] == 1)
                and (recovery and 'skill' not in provenance or provenance.get('skill') == name),
                'Provenance identity mismatch')
        require(recovery and 'mode' not in provenance or provenance.get('mode') in ('standard', 'confirmation'),
                'Unknown benchmark mode')
    if has_provenance:
        ref(provenance_path)
    versions = {}
    if root / 'versions.json' in scanned_entries:
        versions = read_member(root / 'versions.json')
        validate_runtime_versions(versions)
        ref(root / 'versions.json')
    if any(versions.get(key) is None for key in ('skillevaluator', 'evaluator_revision')):
        limitations.add('metadata_missing')
    snapshot_path = run / 'dataset_snapshot.json'
    if snapshot_path in scanned_entries:
        snapshot = read_member(snapshot_path, native_snapshot=True)
        require(type(snapshot) is dict, 'Native snapshot object required')
        require(type(snapshot.get('dataset')) is list and len(snapshot['dataset']) <= MAX_CASES, 'Snapshot case limit')
        require(snapshot.get('evaluator_version') == '0.3.0', 'Invalid native snapshot')
        # Match load_dataset_snapshot's pinned canonical checks on this buffer,
        # preserving its byte/node bounds without reopening the input member.
        expected = native_reports.build_dataset_snapshot(
            [entry for entry in snapshot['dataset'] if type(entry) is dict], evaluator_version='0.3.0')
        require(all(snapshot.get(key) == value for key, value in expected.items()), 'Invalid native snapshot')
        ids = sorted(case_ids([validate_case_id(e['id']) for e in snapshot['dataset']]))
        require(result.get('dataset_digest') == snapshot['dataset_digest']
                and result.get('dataset_summary') == snapshot['dataset_summary'], 'Snapshot/result mismatch')
        if result.get('dataset_digest_algorithm') is not None:
            require(result['dataset_digest_algorithm'] == snapshot['dataset_digest_algorithm'],
                    'Snapshot/result algorithm mismatch')
        if result.get('dataset_snapshot') is not None:
            require(result['dataset_snapshot'] == snapshot, 'Embedded snapshot mismatch')
        ref(snapshot_path)
    else:
        # Explicit summary case identities suffice for partial evidence, never guessed task names.
        ids = sorted(case_ids(list(result['agents']['codex'].get('pass_at_k', {}).get('with_skill', {}).get('cases', {}))))
        snapshot = None; limitations.add('metadata_missing')
    declared = config.get('evaluated_source', {})
    repo = declared.get('repository'); rev = declared.get('commit')
    optional(repo, repository); optional(rev, revision)
    if provenance.get('revision') is not None:
        require(provenance['revision'] == rev, 'Declared revision mismatch')
    historical_owner = 'upstream' if provenance.get('policy', {}).get('upstream_revision') else 'local'
    src_path = 'skills/' + name if historical_owner == 'upstream' else '.apm/skills/' + name
    src_repo = 'cli/cli' if historical_owner == 'upstream' and name == 'gh' else repo
    src_rev = provenance.get('policy', {}).get('upstream_revision') if historical_owner == 'upstream' else rev
    src_contents = historical_content(workspace, src_rev, src_path, budget=budget) if src_rev and historical_owner == 'local' else content()
    src = source(name, historical_owner if src_repo and src_rev else 'unknown', src_repo, src_rev, src_path, src_contents)
    if src_contents['digest'] is None:
        limitations.add('source_unavailable')
    attempt_path = run / 'attempt_policy.json'
    has_attempt = attempt_path in scanned_entries
    attempt_policy = read_member(attempt_path) if has_attempt else {}
    if has_attempt:
        ref(attempt_path)
    harbor = config.get('harbor', {})
    maximum = harbor.get('n_attempts')
    if maximum is None:
        maximum = attempt_policy.get('max_attempts')
    optional(maximum, lambda v: count(v, 100))
    require(maximum is None or maximum > 0, 'Zero attempts')
    reconcile_policy(provenance.get('policy', {}), versions, config, result['agents']['codex'], attempt_policy)
    stop_on_pass = harbor.get('stop_on_pass')
    if stop_on_pass is None:
        stop_on_pass = attempt_policy.get('stop_on_pass')
    attempts = {'mode': provenance.get('mode', 'unknown'), 'maximum': maximum,
                'stop_on_pass': stop_on_pass, 'pass_threshold': attempt_policy.get('pass_threshold')}
    judge = config.get('judge', {})
    policy = make_policy(provenance.get('policy'), 'sha256:' + provenance['patch_sha256'] if provenance.get('patch_sha256') else None,
                         result.get('metric_set'), {k: judge.get(k) for k in ('model', 'provider', 'enabled')},
                         attempts, 'runtime_recorded', provenance.get('policy_id'))
    if not provenance.get('policy') or maximum is None:
        limitations.add('metadata_missing')
    data = evidence(name, 'behavioral', ids, src, policy); data['run_id'] = run.name
    data['dataset'].update({'owner': 'overlay' if historical_owner == 'upstream' else 'local',
                           'staged_digest': snapshot['dataset_digest'] if snapshot else None,
                           'staged_algorithm': snapshot['dataset_digest_algorithm'] if snapshot else None,
                           'staged_provenance': 'runtime_recorded' if snapshot else 'unknown'})
    # Authored-file identity is reconstructed only from exact objects, independently of staged entries.
    if rev:
        ds_path = '.github/evals/' + name + '/evals/evals.json' if historical_owner == 'upstream' else src_path + '/evals/evals.json'
        blob = historical_blob(workspace, rev + ':' + ds_path, budget=budget)
        if blob is not None:
            data['dataset']['authored_digest'] = digest_bytes(blob)
            data['dataset']['authored_provenance'] = 'reconstructed_from_declared_revision'
    agent = result['agents']['codex']
    native_conditions = agent['conditions']
    require(type(native_conditions) is dict and set(native_conditions) == {'with_skill', 'without_skill'}, 'Invalid native conditions')
    for key in ('expected_attempts', 'scored_attempts'):
        values = [native_conditions[arm].get(key) for arm in ('with_skill', 'without_skill')]
        for value in values:
            optional(value, count)
        if all(value is not None for value in values):
            for carrier in (result, agent):
                if key in carrier:
                    require(type(carrier[key]) is int and carrier[key] == sum(values), 'Conflicting aggregate coverage')
    if all(k in agent for k in ('lift', 'dimensions_with_skill')):
        data['metrics'] = reports.metric_rows(agent)
    else:
        limitations.add('coverage_missing')
    if provenance.get('metrics') is not None:
        require(provenance['metrics'] == data['metrics'], 'Provenance metrics disagreement')
    if provenance.get('dataset_digest') is not None:
        require(provenance['dataset_digest'] == data['dataset']['staged_digest'], 'Provenance dataset disagreement')
    trials_by_arm = {arm: sorted(path for path in scanned_entries if path.name == 'result.json'
                                and path.parent.parent == run / 'codex' / arm.replace('_', '-') / 'trials')
                    for arm in ('with_skill', 'without_skill')}
    orphan_rewards = {arm: {path.parent for path in scanned_entries if path.name == 'reward.json'
                            and path.parent.parent == run / 'codex' / arm.replace('_', '-') / 'trials'}
                      - {path.parent for path in trials_by_arm[arm]} for arm in trials_by_arm}
    require(sum(len(trials_by_arm[arm]) + len(orphan_rewards[arm]) for arm in trials_by_arm) <= MAX_TRIALS,
            'Trial input limit')
    known_cases = set(ids)
    models = [value for value in (policy['fields']['model'], agent.get('model'),
              config.get('provider', {}).get('model'), config.get('agents', {}).get('codex', {}).get('model'))
              if value is not None]
    for model in models:
        token(model)
    models = set(models)
    require(len(models) <= 1, 'Native model identity mismatch')
    metric_sets = set()
    for value in (policy['metric_set'], result.get('metric_set')):
        if value is not None:
            require(value == 'skill-evaluator-default-v2', 'Native metric-set identity mismatch')
            metric_sets.add(value)
    summary_attempts = 0
    for arm in ('with_skill', 'without_skill'):
        arm_dir = run / 'codex' / arm.replace('_', '-')
        native_condition = agent['conditions'][arm]
        summary_path = arm_dir / 'summary.json'
        if summary_path in scanned_entries:
            summary = read_member(summary_path)
            summary_ref = ref(summary_path)
        else:
            # Retain run-recorded identities/counts where available, without
            # interpreting a missing summary as a zero-trial run.
            summary = {**native_condition,
                       'num_trials': agent.get('num_trials_with' if arm == 'with_skill' else 'num_trials_without'),
                       'pass_at_k': (agent.get('pass_at_k') or {}).get(arm)}
            summary_ref = ref(result_path, ('agents', 'codex'))
            limitations.add('metadata_missing')
        if summary.get('agent') is not None:
            require(summary['agent'] == 'codex', 'Native agent identity mismatch')
        if summary.get('model') is not None:
            token(summary['model']); models.add(summary['model'])
            require(len(models) == 1, 'Native model identity mismatch')
        aggregate_pass = (agent.get('pass_at_k') or {}).get(arm)
        if aggregate_pass is not None:
            require(aggregate_pass == summary.get('pass_at_k'), 'Conflicting native pass data')
        for key in ('execution_status', 'expected_attempts', 'scored_attempts'):
            require(summary[key] == native_condition[key], 'Conflicting native coverage')
        condition_errors = native_error_count(native_condition)
        require(summary_error_count(summary) == condition_errors, 'Conflicting native error count')
        recorded = summary.get('num_trials'); scored = native_condition.get('scored_attempts')
        optional(recorded, count); optional(scored, count)
        pass_data = summary.get('pass_at_k')
        require(pass_data is None or type(pass_data) is dict, 'Invalid summary pass data')
        pass_data = pass_data or {}
        native_cases = pass_data.get('cases')
        require(native_cases is None or type(native_cases) is dict, 'Invalid summary cases')
        native_cases = native_cases or {}
        require(set(native_cases) <= set(ids), 'Unknown summary case identity')
        lookup = {}
        summary_scored = 0
        for case, case_row in native_cases.items():
            require(type(case_row) is dict, 'Invalid summary case')
            entries = case_row.get('attempts', [])
            require(type(entries) is list and len(entries) <= (maximum or MAX_TRIALS), 'Summary attempt limit')
            ordinals = set()
            for attempt in entries:
                summary_attempts += 1
                require(summary_attempts <= MAX_TRIALS, 'Summary attempt limit')
                require(type(attempt) is dict, 'Invalid summary attempt')
                trial = attempt.get('trial'); token(trial)
                ordinal = attempt.get('attempt')
                optional(ordinal, lambda v: count(v, maximum or 100))
                require(ordinal is None or ordinal >= 1 and ordinal not in ordinals, 'Invalid summary ordinal')
                if ordinal is not None:
                    ordinals.add(ordinal)
                optional(attempt.get('score'), number); optional(attempt.get('passed'), boolean)
                summary_scored += attempt.get('score') is not None
                require(recorded is None or len(lookup) < recorded, 'Summary attempts exceed recorded trials')
                require(scored is None or summary_scored <= scored, 'Summary attempts exceed scored trials')
                expected = native_condition.get('expected_attempts')
                require(expected is None or len(lookup) < expected, 'Summary attempt limit')
                require(trial not in lookup, 'Duplicate summary trial')
                lookup[trial] = (case, attempt)
        observed = []
        if trials_by_arm[arm]:
            for path in trials_by_arm[arm]:
                trial_result = read_member(path)
                trial = trial_result['trial_name']; token(trial)
                require(trial == path.parent.name, 'Trial directory identity mismatch')
                native_id = trial_result['id']; token(native_id)
                reward_path = path.parent / 'reward.json'
                reward = read_member(reward_path) if reward_path in scanned_entries else None
                if reward is not None:
                    require(type(reward) is dict, 'Reward object required')
                    require(reward.get('agent') is None or reward['agent'] == 'codex', 'Reward identity mismatch')
                    if reward.get('model') is not None:
                        token(reward['model']); models.add(reward['model'])
                        require(len(models) == 1, 'Reward identity mismatch')
                    if reward.get('metric_set') is not None:
                        require(reward['metric_set'] == 'skill-evaluator-default-v2', 'Reward identity mismatch')
                        metric_sets.add(reward['metric_set'])
                        require(len(metric_sets) == 1, 'Reward identity mismatch')
                matched = lookup.pop(trial, None)
                from skillevaluator.tier3.harbor.collector import _entry_id_from_harbor_result, _attempt_ordinal, _canonical_case_id
                task_case = validate_case_id(_canonical_case_id(_entry_id_from_harbor_result(trial_result), known_cases))
                case = validate_case_id(reward['entry_id']) if reward is not None else matched[0] if matched else task_case
                require(task_case == case and task_case in known_cases, 'Trial task case identity mismatch')
                require(case in known_cases and (matched is None or case == matched[0]), 'Trial case identity mismatch')
                # Attempt index must be runtime recorded. A missing index never comes from directory order.
                attempt = {'attempt': None, 'score': None, 'passed': None, **matched[1]} if matched else {'attempt': _attempt_ordinal({'_trial_name': trial}), 'score': None, 'passed': None}
                if attempt['attempt'] is None:
                    limitations.add('metadata_missing')
                if reward is not None:
                    require(reward['trial_id'] == trial and reward['has_skill'] == (arm == 'with_skill'), 'Reward trial/arm mismatch')
                verifier = (trial_result.get('verifier_result') or {}).get('rewards') or {}
                overall = verifier.get('overall')
                require(overall == attempt.get('score'), 'Native trial/summary score mismatch')
                scores = {k: verifier.get(k) for k in SCORE_FIELDS}
                if reward is not None:
                    for key in SCORE_FIELDS:
                        if key in reward:
                            require(reward[key] == verifier.get(key), 'Reward score mismatch')
                deterministic = (reward or {}).get('custom_metrics', {})
                allowed = {'gh_' + k for k in ('evidence', 'activation', 'commands', 'task', 'recovery', 'authorization', 'efficiency', 'gate')}
                require(not deterministic or name == 'gh' and set(deterministic) == allowed, 'Unsupported custom grading contract')
                if deterministic:
                    require(all(type(v) in (int, float) and v in (0, 1) for v in deterministic.values()), 'Invalid deterministic observation')
                    require(deterministic['gh_gate'] == float(all(v == 1 for k, v in deterministic.items() if k != 'gh_gate')), 'Gate consistency')
                locator = ()
                if 'verifier_result' in trial_result:
                    locator = ('verifier_result',)
                    if type(trial_result['verifier_result']) is dict and 'rewards' in trial_result['verifier_result']:
                        locator += ('rewards',)
                obs_refs = [ref(path, locator), summary_ref]
                if reward is not None:
                    obs_refs.append(ref(reward_path))
                obs = {'id': observation_id(run.name, arm, case, native_id, trial, attempt['attempt']),
                       'arm': arm, 'case_id': case, 'attempt': attempt['attempt'], 'native_id': native_id,
                       'native_trial': trial, 'native_task': trial_result['task_name'], 'score': overall,
                       'scores': scores, 'rubric_pass': attempt.get('passed'),
                       'deterministic_gate': deterministic.get('gh_gate'),
                       'deterministic_scores': {k: deterministic.get('gh_' + k) for k in GATE_FIELDS}, 'references': obs_refs}
                observed.append(obs)
        cardinality = agent.get('num_trials_with' if arm == 'with_skill' else 'num_trials_without')
        if cardinality is not None:
            require(type(cardinality) is int and cardinality == recorded, 'Conflicting aggregate trial count')
        details = 'complete' if len(observed) == recorded else 'partial' if observed else 'unavailable'
        require(details != 'complete' or not lookup, 'Unmatched summary attempts')
        if orphan_rewards[arm]:
            details = 'partial' if observed else 'unavailable'
        if details != 'complete':
            limitations.add('case_details_missing')
        if scored != native_condition.get('expected_attempts') or recorded != native_condition.get('expected_attempts'):
            limitations.add('coverage_missing')
        if native_condition.get('execution_status') != 'succeeded' or condition_errors:
            limitations.add('execution_incomplete')
        workspace_modes = {e.get('skill_workspace_mode') for e in snapshot['dataset']} if snapshot else set()
        workspace_mode = next(iter(workspace_modes)) if len(workspace_modes) == 1 else None
        competing = []
        if name == 'gh' and policy['fields']['competing_revision']:
            competing = [source('github-actions-hardening', 'upstream', 'github/awesome-copilot',
                                policy['fields']['competing_revision'], 'skills/github-actions-hardening')]
        execution = {'environment': (harbor.get('environment') or {}).get('value'),
                     'base_image_mode': harbor.get('base_image_mode'), 'task_source': config.get('task_source'),
                     'authorization_policy': policy['fields']['authorization_policy'],
                     'fixture_boundary': policy['fields']['fixture_boundary']}
        cond = condition(arm == 'with_skill', 'runtime_recorded', workspace_mode, competing,
                         instructions=native_condition.get('instruction_digest'),
                         fixture=native_condition.get('fixture_digest'),
                         build=native_condition.get('build_digest') or (identity(policy['fields']['task_build']) if policy['fields']['task_build'] else None),
                         execution=execution)
        data['arms'].append({'name': arm, 'condition': cond,
            'coverage': {'expected_cases': len(ids), 'expected_attempts': native_condition.get('expected_attempts'),
                         'recorded_attempts': recorded, 'scored_attempts': scored,
                         'unscored_attempts': recorded - scored if recorded is not None and scored is not None else None,
                         'case_details': details}, 'execution_status': native_condition.get('execution_status', 'unknown'),
            'execution_error_count': condition_errors,
            'rubric': {'passed_cases': pass_data.get('passed_cases'), 'total_cases': pass_data.get('total_cases'),
                       'threshold': pass_data.get('pass_threshold')}})
        data['observations'].extend(observed)
    if EvaluationService.failure_reason(result) is not None or recovery or result['report_status'] != 'complete' or result.get('diagnostic_only'):
        limitations.add('execution_incomplete')
    if not config.get('evaluated_source'):
        limitations.add('metadata_missing')
    if behavioral_identity_missing(data):
        limitations.add('metadata_missing')
    data['references'] = sorted(refs, key=lambda r: r['id'])
    if any(row['availability'] == 'expired' for row in refs):
        limitations.add('reference_expired')
    data['observations'].sort(key=lambda o: (o['arm'], o['case_id'], o['attempt'] or 0, o['id']))
    data['availability'] = {'status': 'incomplete' if limitations else 'complete',
                            'reasons': sorted(limitations), 'provenance': 'reviewed_extract' if extract else 'runtime_recorded'}
    verify_directory_states(directory_states, directory_identities)
    verify_file_states(file_states, directory_identities, directory_states)
    validate_evidence(data, _observed_at=observed_at)
    return data if extract else _BehavioralEvidence(data, behavioral_claim_identity(data))


def static_required_gate(scan, *, blocking_only=False):
    """Match the pinned reporter's blocking and advisory-skip semantics."""
    boolean(scan['passed'])
    enum(scan['status'], ('passed', 'failed', 'incomplete', 'skipped'))
    gating = scan.get('gating')
    require(gating is None or type(gating) is dict, 'Invalid static gating')
    if gating is not None:
        boolean(gating.get('blocking', True))
    tier3 = scan.get('tier3', {})
    provenance = tier3.get('provenance', {}) if type(tier3) is dict else {}
    advisory_skip = (scan['validator'] == 'AGENT_EVAL'
                     and not (gating is not None and gating.get('blocking', False))
                     and type(provenance) is dict and provenance.get('advisory') is True
                     and provenance.get('reason') == 'skipped')
    expected = ('skipped' if advisory_skip else 'incomplete' if scan.get('incomplete_scans')
                else 'passed' if scan['passed'] else 'failed')
    require(scan['status'] == expected, 'Static validator status contradiction')
    blocking = gating.get('blocking', True) if gating is not None else not advisory_skip
    return blocking if blocking_only else scan['passed'] or not blocking


def normalize_static(root, name, workspace=ROOT):
    directory_identities = {}
    directory_states = {}
    file_states = {}
    root = safe_path(root, directory=True, directory_identities=directory_identities)
    scanned_entries = set(safe_tree(root, directory_identities=directory_identities, directory_states=directory_states, file_states=file_states)); skill_id(name)
    budget = ReadBudget()
    catalog_path = root / 'reports/catalog-summary.json'
    require(catalog_path in scanned_entries, 'Unscanned static member')
    catalog, catalog_digest = read_json_and_digest(catalog_path, budget=budget, directory_identities=directory_identities, directory_states=directory_states, file_states=file_states)
    require(type(catalog) is dict, 'Static catalog object required')
    require(type(catalog['skills']) is list and catalog['total'] == len(catalog['skills']), 'Catalog cardinality mismatch')
    names = [row['name'] for row in catalog['skills']]
    require(type(catalog['failed']) is int and catalog['failed'] == sum(row['passed'] is False for row in catalog['skills']), 'Catalog failure count mismatch')
    require(len(names) == len(set(names)), 'Ambiguous static skill identity')
    rows = [row for row in catalog['skills'] if row['name'] == name]
    require(len(rows) == 1, 'Missing static skill report')
    row = rows[0]; boolean(row['passed'])
    require(row.get('reason', '') == ('' if row['passed'] else 'validation failed'), 'Catalog infrastructure failure')
    filename = row['json_report']
    require(type(filename) is str and bool(re.fullmatch(r'skillevaluator-output-[0-9]{14}\.json', filename)), 'Unsafe static report member')
    report_path = root / 'reports' / name / filename
    require(report_path in scanned_entries, 'Unscanned static member')
    native, report_digest = read_json_and_digest(report_path, budget=budget, directory_identities=directory_identities, directory_states=directory_states, file_states=file_states)
    require(type(native) is dict and type(native.get('results')) is list
            and len(native['results']) <= 100, 'Invalid bounded static report')
    require(len(native['skills']) == 1 and native['skills'][0]['name'] == name, 'Static identity mismatch')
    require(native['overall_passed'] == row['passed'] and type(native['overall_passed']) is bool, 'Static pass mismatch')
    enum(native['overall_status'], ('passed', 'failed', 'incomplete'))
    require(type(native['incomplete_scans']) is list and len(native['incomplete_scans']) <= 100, 'Scanner limit')
    for scanner in native['incomplete_scans']:
        token(scanner)
    expected = 'incomplete' if native['incomplete_scans'] else 'passed' if row['passed'] else 'failed'
    require(native['overall_status'] == expected and native['total_validators'] == len(native['results']) > 0, 'Static status contradiction')
    severity = native['severity_counts']; closed(severity, ('critical', 'high', 'medium', 'low'))
    for val in severity.values():
        count(val)
    finding_count = 0
    for scan in native['results']:
        require(type(scan) is dict and type(scan.get('findings', [])) is list, 'Invalid static findings')
        finding_count += len(scan.get('findings', []))
        require(finding_count <= MAX_TRIALS, 'Finding limit')
        extra_scanners = scan.get('incomplete_scans', [])
        require(type(extra_scanners) is list and len(extra_scanners) <= 100, 'Scanner limit')
        for scanner in extra_scanners:
            token(scanner)
        require(set(extra_scanners) <= set(native['incomplete_scans']), 'Inconsistent incomplete scanner identity')
    blocking = [static_required_gate(scan, blocking_only=True) for scan in native['results']]
    gates = [scan['passed'] or not required for scan, required in zip(native['results'], blocking)]
    require(native['overall_passed'] == all(gates),
            'Static required gate contradiction')
    detailed = dict.fromkeys(severity, 0)
    for scan in native['results']:
        scan_counts = dict.fromkeys(severity, 0)
        summary = scan.get('summary', {})
        require(type(summary) is dict, 'Invalid scanner summary')
        for finding in scan.get('findings', []):
            require(type(finding) is dict, 'Invalid static finding')
            enum(finding['severity'], (*severity, 'info'))
            if finding['severity'] in severity:
                scan_counts[finding['severity']] += 1
                detailed[finding['severity']] += 1
        for level, total in scan_counts.items():
            reported = summary.get(level + '_count')
            optional(reported, count)
            require(reported is None or total <= reported, 'Detailed findings exceed scanner total')
    for level, total in detailed.items():
        require(total <= severity[level], 'Detailed findings exceed aggregate total')
    for level, total in severity.items():
        counts = [scan.get('summary', {}).get(level + '_count') for scan in native['results']]
        if all(value is not None for value in counts):
            require(sum(counts) == total, 'Contradictory static finding counts')
    data = evidence(name, 'static')
    declared = native.get('evaluated_source')
    if declared is not None:
        require(type(declared) is dict, 'Invalid recorded static source')
        repo = declared.get('repository'); rev = declared.get('commit')
        optional(repo, repository); optional(rev, revision)
        path = '.apm/skills/' + name
        data['source'] = source(name, 'local' if repo and rev else 'unknown', repo, rev, path,
                                historical_content(workspace, rev, path, budget=budget) if rev else content())
    def report_reference(locator=()):
        return reference_from_digest(root, report_path, 'skill-quality', report_digest, locator)
    refs = [reference_from_digest(root, catalog_path, 'skill-quality', catalog_digest), report_reference()]
    # Aggregate native counts remain their own observation; scanner counts are
    # not invented when the pinned report does not supply them.
    data['scans'] = [{'scanner': 'catalog-total', 'status': native['overall_status'], 'passed': native['overall_passed'],
                      'blocking': True, 'severity_counts': severity, 'references': [refs[1]['id']]}]
    for index, scan in enumerate(native['results']):
        scanner = scan['validator']; token(scanner)
        enum(scan['status'], ('passed', 'failed', 'incomplete', 'skipped'))
        scan_ref = report_reference(('results', index)); refs.append(scan_ref)
        data['scans'].append({'scanner': scanner, 'status': scan['status'], 'passed': scan.get('passed'), 'blocking': blocking[index],
            'severity_counts': {k: scan.get('summary', {}).get(k + '_count')
                                for k in ('critical', 'high', 'medium', 'low')}, 'references': [scan_ref['id']]})
    recorded_incomplete = set()
    for index, scan in enumerate(native['results']):
        for scanner in scan.get('incomplete_scans', []):
            token(scanner); recorded_incomplete.add(scanner)
            if scanner not in {s['scanner'] for s in data['scans']}:
                data['scans'].append({'scanner': scanner, 'status': 'incomplete', 'passed': None,
                    'blocking': False, 'severity_counts': {k: None for k in ('critical', 'high', 'medium', 'low')}, 'references': [refs[1]['id']]})
        for finding_index, finding in enumerate(scan.get('findings', [])):
            finding_ref = report_reference(('results', index, 'findings', finding_index))
            refs.append(finding_ref)
            member = finding.get('file_path')
            try:
                relative(member)
            except ValueError:
                member = None  # Never publish an artifact-supplied absolute path.
            check = finding.get('check_name') or None
            data['findings'].append({'scanner': scan['validator'], 'severity': finding['severity'],
                'check': check, 'member': member, 'line': finding.get('line_number'), 'reference': finding_ref['id']})
    require(set(native['incomplete_scans']) == recorded_incomplete, 'Inconsistent incomplete scanner identity')
    incomplete = any(s['status'] in ('incomplete', 'skipped') for s in data['scans'])
    data['references'] = refs
    limitations = {'scan_incomplete'} if incomplete else set()
    if data['source']['content']['digest'] is None:
        limitations.add('source_unavailable')
    data['availability'] = {'status': 'incomplete' if limitations else 'complete',
                            'reasons': sorted(limitations), 'provenance': 'runtime_recorded'}
    if root / 'versions.json' in scanned_entries:
        versions, versions_digest = read_json_and_digest(root / 'versions.json', budget=budget, directory_identities=directory_identities, directory_states=directory_states, file_states=file_states)
        validate_runtime_versions(versions)
        data['policy'] = make_policy({'evaluator_revision': versions.get('evaluator_revision')}, provenance='runtime_recorded')
        data['references'].append(reference_from_digest(root, root / 'versions.json', 'skill-quality', versions_digest))
        if versions.get('fixture') == 'synthetic':
            data['availability']['provenance'] = 'synthetic'
            for record in data['references']:
                record['provenance'] = 'synthetic'
    verify_directory_states(directory_states, directory_identities)
    verify_file_states(file_states, directory_identities, directory_states)
    validate_evidence(data)
    blocking_defaults = tuple((scan['scanner'], scan['blocking']) for scan in data['scans'])
    return _StaticEvidence(data, static_claim_identity(data, blocking_defaults), blocking_defaults)


def open_directory(path, identities=None, changed_message='Input directory changed', trusted_output=False, *, directory_states=None):
    """Anchor each directory component without following replacement links."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(path.anchor, flags)
    def validate_owner():
        if trusted_output:
            info = os.fstat(fd)
            require(info.st_uid in (0, os.geteuid())
                    and (not info.st_mode & 0o022 or info.st_mode & stat.S_ISVTX), 'Untrusted output parent')
    try:
        validate_owner()
        current = Path(path.anchor)
        if directory_states is not None and current in directory_states:
            require(directory_state(os.fstat(fd)) == directory_states[current], 'Input directory entries changed')
        for part in path.parts[1:]:
            current /= part
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd); fd = child
            if identities is not None:
                info = os.fstat(fd)
                require(identities.get(current) == (info.st_dev, info.st_ino), changed_message)
            if directory_states is not None and current in directory_states:
                require(directory_state(os.fstat(fd)) == directory_states[current], 'Input directory entries changed')
            validate_owner()
        return fd
    except BaseException:
        os.close(fd)
        raise


def write_outputs(values, destination=None, workspace=ROOT, input_path=None):
    # Finish validation/serialization before reserving an output directory.
    require(SECURE_DIRECTORY_OUTPUT, 'Secure directory output unsupported')
    for name in values:
        relative(name); require('/' not in name, 'Nested output member')
    payloads = {name: encoded(value) for name, value in values.items()}
    workspace = Path(workspace).absolute()
    if input_path is not None:
        input_path = Path(input_path).absolute()
    parent_identities = {}
    if destination is None:
        # Validate explicit settings without tempfile's probing/fallback writes.
        parent = next((os.environ[key] for key in ('TMPDIR', 'TEMP', 'TMP') if os.environ.get(key)), None)
        parent = safe_path(parent if parent is not None else tempfile.gettempdir(), directory=True,
                           directory_identities=parent_identities)
        require(not parent.is_relative_to(workspace), 'Output must be outside checkout')
        if input_path is not None:
            require(not parent.is_relative_to(input_path), 'Output overlaps input')
    else:
        destination = Path(destination).absolute()
        parent = safe_path(destination.parent, directory=True, directory_identities=parent_identities)
        require(not os.path.lexists(destination), 'Output directory must be new')
    if destination is not None:
        safe_path(destination, directory=True, missing=True)
        require(not destination.is_relative_to(workspace) and destination != workspace, 'Output must be outside checkout')
        if input_path is not None:
            require(not destination.is_relative_to(input_path) and not input_path.is_relative_to(destination), 'Output overlaps input')
    forbidden_directories = set()
    for boundary in (workspace, input_path):
        if boundary is not None and boundary.exists():
            info = boundary.lstat()
            if stat.S_ISDIR(info.st_mode): forbidden_directories.add((info.st_dev, info.st_ino))
    parent_fd = open_directory(parent, parent_identities, 'Output parent directory changed', True)
    try:
        if destination is None:
            for _ in range(100):
                destination = parent / ('skill-evidence-' + secrets.token_hex(8))
                try:
                    os.mkdir(destination.name, mode=0o700, dir_fd=parent_fd)
                    break
                except FileExistsError:
                    destination = None
            require(destination is not None, 'Temporary output collision limit')
        else:
            os.mkdir(destination.name, mode=0o700, dir_fd=parent_fd)
        created = os.stat(destination.name, dir_fd=parent_fd, follow_symlinks=False)
        require(stat.S_ISDIR(created.st_mode), 'Output directory changed')
        directory_fd = os.open(destination.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        owned = False
        members = []
        try:
            original = os.fstat(directory_fd)
            require((original.st_dev, original.st_ino) == (created.st_dev, created.st_ino)
                    and (original.st_dev, original.st_ino) not in forbidden_directories
                    and original.st_uid == os.geteuid()
                    and not original.st_mode & 0o077 and not os.listdir(directory_fd), 'Output directory changed')
            owned = True
            def unchanged():
                current = destination.lstat()
                require(stat.S_ISDIR(current.st_mode) and (current.st_dev, current.st_ino) ==
                        (original.st_dev, original.st_ino), 'Output directory changed')
            unchanged()
            for name, payload in payloads.items():
                fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             mode=0o600, dir_fd=directory_fd)
                members.append(name)
                try:
                    stream = os.fdopen(fd, 'wb')
                except BaseException:
                    os.close(fd)
                    raise
                with stream:
                    stream.write(payload)
                unchanged()
        except BaseException:
            if owned:
                # Remove only members created here, through the retained descriptor.
                for name in members:
                    try:
                        os.unlink(name, dir_fd=directory_fd)
                    except FileNotFoundError:
                        pass
                current = os.stat(destination.name, dir_fd=parent_fd, follow_symlinks=False)
                if stat.S_ISDIR(current.st_mode) and (current.st_dev, current.st_ino) == (original.st_dev, original.st_ino):
                    os.rmdir(destination.name, dir_fd=parent_fd)
            raise
        finally:
            os.close(directory_fd)
    finally:
        os.close(parent_fd)
    return destination



def verify_reference(bundle, record):
    """Verify retained original bytes and resolve a structured locator, without execution."""
    validate_reference(record)
    require(record['availability'] == 'available', 'Reference unavailable or expired')
    safe_path(bundle, directory=True)
    path = bundle / record['member']
    raw = read_bytes(path)
    require(digest_bytes(raw) == record['digest'], 'Evidence member digest mismatch')
    value = parse_json(raw)
    for component in record['locator']:
        if type(component) is int:
            require(type(value) is list and component < len(value), 'Invalid structured locator')
        else:
            require(type(value) is dict and component in value, 'Invalid structured locator')
        value = value[component]
    return value


def verify_source_snapshot(snapshot, src):
    """Compare retained skill bytes with the declared agent-visible manifest."""
    validate_source(src)
    require(src['content']['digest'] is not None, 'Exact source unavailable')
    require(skill_content(snapshot)['digest'] == src['content']['digest'], 'Exact source mismatch')


def validate_public(data):
    return validate_evidence(data, public=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    inv = commands.add_parser('inventory'); inv.add_argument('--output', type=Path)
    norm = commands.add_parser('normalize'); norm.add_argument('--kind', required=True, choices=('behavioral', 'static'))
    norm.add_argument('--skill', required=True); norm.add_argument('--input', required=True, type=Path)
    norm.add_argument('--run'); norm.add_argument('--output', type=Path)
    proj = commands.add_parser('project'); proj.add_argument('--input', required=True, type=Path); proj.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    input_path = getattr(args, 'input', None)
    if args.command == 'inventory':
        values = {'inventory.json': inventory()}
    elif args.command == 'project':
        data = read_json(args.input)
        values = {'public-report.json': project(data, static_bundle=args.input.parent, behavioral_bundle=args.input.parent)}
        if data['kind'] == 'static' or behavioral_claims_need_witness(data):
            input_path = args.input.parent
    else:
        require(args.kind == 'behavioral' or args.run is None, '--run applies to behavioral evidence')
        data = normalize_behavioral(args.input.absolute(), args.skill, args.run) if args.kind == 'behavioral' else normalize_static(args.input.absolute(), args.skill)
        values = {'evidence.json': data, 'public-report.json': project(data)}
    output = write_outputs(values, args.output, input_path=input_path)
    print(output)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, AttributeError, IndexError, OSError) as exc:
        # Native exception strings can contain prose or paths. Keep CLI errors bounded.
        print('Evidence contract rejected (' + type(exc).__name__ + ')', file=sys.stderr)
        sys.exit(1)
