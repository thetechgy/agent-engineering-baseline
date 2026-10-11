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
import stat
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skill_reports as reports

ROOT = Path(__file__).resolve().parents[2]
JSON_LIMIT = 8 * 1024 * 1024
PUBLIC_LIMIT = 1024 * 1024
MAX_CASES = 1000
MAX_TRIALS = 10000
MAX_SOURCE_MEMBERS = 1000
MAX_INPUT_ENTRIES = 100000
# Reviewed Podman extract-manifest.json bytes; additional identities require review.
REVIEWED_EXTRACT_MANIFESTS = frozenset({
    'sha256:4f8ab06638a37c970dfd5a97f057da8505a0b57767a332b41d4e0c2c8e8066ea',
})
require = reports.require
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


def depth(value, limit, level=0):
    require(level <= limit, 'JSON depth exceeded')
    if isinstance(value, dict):
        for child in value.values():
            depth(child, limit, level + 1)
    elif isinstance(value, list):
        for child in value:
            depth(child, limit, level + 1)
    elif type(value) is float:
        require(math.isfinite(value), 'Nonfinite JSON number')


def safe_path(path, *, directory=False, missing=False):
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
        else:
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'Special or hard-linked input')
    return path


def safe_tree(path, *, max_entries=MAX_INPUT_ENTRIES, max_files=None):
    path = safe_path(path, directory=True)
    pending = [path]
    files = []
    seen = 0
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                seen += 1
                require(seen <= max_entries, 'Input tree entry limit')
                directory = stat.S_ISDIR(entry.stat(follow_symlinks=False).st_mode)
                member = safe_path(entry.path, directory=directory)
                if directory:
                    pending.append(member)
                else:
                    require(max_files is None or len(files) < max_files, 'Input tree entry limit')
                    files.append(member)
    return files


def read_bytes(path, limit=JSON_LIMIT):
    path = safe_path(path)
    # O_NONBLOCK avoids hanging if a file is replaced by a FIFO between checks.
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= limit,
                'Special, hard-linked or oversized input')
        value = stream.read(limit + 1)
    require(len(value) <= limit, 'Oversized input')
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


def read_json_and_digest(path):
    raw = read_bytes(path)
    return parse_json(raw), digest_bytes(raw)


def read_yaml(path):
    import yaml
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
        value = yaml.load(read_bytes(path), Loader=UniqueLoader)
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
        require(value['digest'] == identity(value['manifest']), 'Content manifest mismatch')
    else:
        require(not names and value['provenance'] == 'unknown', 'Unknown content has manifest')


def content(manifest=(), provenance='unknown'):
    manifest = sorted(manifest, key=lambda row: row['member'])
    return {'digest': identity(manifest) if provenance != 'unknown' else None,
            'algorithm': 'sha256-relative-file-manifest-v1', 'scope': 'pinned-agent-visible',
            'provenance': provenance, 'manifest': manifest}


def skill_content(path):
    from skillevaluator.tier3.harbor.adapter import _runtime_skill_copy_ignore, _runtime_projection_path_is_ignored
    files = safe_tree(path, max_entries=2 * MAX_SOURCE_MEMBERS, max_files=MAX_SOURCE_MEMBERS)
    ignore = _runtime_skill_copy_ignore(path)
    return content([{'member': p.relative_to(path).as_posix(), 'digest': digest_bytes(read_bytes(p))}
                    for p in files if not _runtime_projection_path_is_ignored(p, path, ignore)], 'configured')


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


def offline_git(workspace, *args, text=False, max_entries=None):
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
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env) as process:
        output = bytearray()
        entries = 0
        try:
            while chunk := process.stdout.read(4096):
                entries += chunk.count(b'\0')
                require(entries <= max_entries and len(output) + len(chunk) <= JSON_LIMIT,
                        'Historical tree listing limit')
                output.extend(chunk)
            returncode = process.wait()
        finally:
            if process.poll() is None:
                process.kill()
    return subprocess.CompletedProcess(command, returncode, bytes(output), b'')


def git_revision(workspace):
    result = offline_git(workspace, 'rev-parse', 'HEAD', text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def historical_blob(workspace, spec):
    """Bound exact local object bytes before capturing content; missing stays unknown."""
    size = offline_git(workspace, 'cat-file', '-s', spec, text=True)
    if size.returncode:
        return None
    require(0 <= int(size.stdout.strip()) <= JSON_LIMIT, 'Oversized historical blob')
    blob = offline_git(workspace, 'cat-file', 'blob', spec)
    if blob.returncode:
        return None
    require(len(blob.stdout) <= JSON_LIMIT, 'Oversized historical blob')
    return blob.stdout


def historical_content(workspace, rev, source_path):
    """Read exact local Git blobs only. Never checkout or contact a remote."""
    revision(rev); relative(source_path)
    listing = offline_git(workspace, 'ls-tree', '-rz', rev, '--', source_path, max_entries=MAX_SOURCE_MEMBERS)
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
        blob = historical_blob(workspace, oid)
        if blob is None:
            return content()
        records.append({'member': name, 'digest': digest_bytes(blob)})
    if not records:
        return content()
    return content(records, 'reconstructed_from_declared_revision')


def strict_dataset(path, name):
    from skillevaluator.tier3.dataset_utils import normalize_dataset_entries
    from skillevaluator.tier3.evals_spec import validate_skillevaluators
    safe_tree(path.parent.parent)
    alternatives = list(path.parent.glob('evals.*'))
    require(path.name == 'evals.json' and set(alternatives) == {path}, 'Ambiguous authored dataset formats')
    data = read_json(path)
    require(type(data) is dict, 'Dataset object required')
    require(type(data.get('evals')) is list and len(data['evals']) <= MAX_CASES, 'Dataset case limit')
    require(type(data) is dict and data.get('skill_name') == name, 'Dataset skill mismatch')
    checks = validate_skillevaluators(path.parent.parent)
    require(checks and all(row.status == 'ok' for row in checks), 'Strict dataset contract failed')
    entries = normalize_dataset_entries(data)
    from skillevaluator.tier3.case_ids import validate_case_ids
    ids = validate_case_ids(entry['id'] for entry in entries)
    case_ids(ids)
    for entry in entries:
        for member in entry.get('files', []):
            relative(member)
            require(member.startswith('evals/files/'), 'Input outside evaluator fixture boundary')
            safe_path(path.parent.parent / member)
    return {'owner': 'unknown',
            'path': None, 'authored_digest': digest_bytes(read_bytes(path)),
            'case_ids': sorted(ids), 'status': 'configured'}


def validate_skill_metadata(authored, name):
    import yaml as metadata_yaml
    text = read_bytes(authored / 'SKILL.md').decode()
    require(text.startswith('---\n') and '\n---' in text[4:], 'Missing skill metadata')
    # Front matter is bounded and duplicate-key ambiguity must not choose an owner.
    front = text.split('---', 2)[1]
    pairs = metadata_yaml.compose(front)
    require(pairs is not None and isinstance(pairs, metadata_yaml.MappingNode), 'Invalid skill metadata')
    keys = [key.value for key, _ in pairs.value]
    require(len(keys) == len(set(keys)), 'Ambiguous skill metadata')
    metadata = metadata_yaml.safe_load(front)
    require(type(metadata) is dict and metadata.get('name') == name
            and type(metadata.get('description')) is str and metadata['description'].strip(), 'Invalid skill metadata')
    from skillevaluator.models.skill import SkillFrontmatter
    SkillFrontmatter(**metadata)


def inventory(workspace=ROOT):
    workspace = safe_path(workspace, directory=True)
    catalog = workspace / '.apm/skills'
    files = safe_tree(catalog)
    names = sorted(p.parent.name for p in files if p.name == 'SKILL.md' and p.parent.parent == catalog)
    require(bool(names), 'No local skills found')
    lock_path = workspace / 'apm.lock.yaml'
    lock = read_yaml(lock_path) if lock_path.exists() else {'dependencies': [], 'deployments': []}
    require(type(lock) is dict and type(lock.get('dependencies')) is list
            and type(lock.get('deployments')) is list, 'Invalid ownership metadata')
    closed_dependencies = lock.get('dependencies', [])
    deployments = lock.get('deployments', [])
    require(all(type(item) is dict for item in closed_dependencies + deployments), 'Invalid ownership records')
    overlays = workspace / '.github/evals'
    overlay_names = []
    if overlays.exists():
        safe_tree(overlays)
        overlay_names = [p.parent.parent.name for p in overlays.glob('*/evals/evals.*')]
    rows = []
    for name in sorted(set(names + overlay_names)):
        skill_id(name)
        owners = [d for d in closed_dependencies if d.get('name') == name]
        require(len(owners) <= 1 and not (name in names and owners), 'Conflicting active source owners')
        if name in names:
            authored = catalog / name
            validate_skill_metadata(authored, name)
            src = source(name, 'local', 'thetechgy/agent-engineering-baseline', git_revision(workspace),
                         authored.relative_to(workspace).as_posix(), skill_content(authored))
            deployment = None
        else:
            require(len(owners) == 1, 'Overlay has no unique skill owner')
            owner = owners[0]
            repository(owner['repo_url']); revision(owner['resolved_commit']); relative(owner['virtual_path'])
            authored = workspace / '.agents/skills' / name
            files = safe_tree(authored, max_entries=2 * MAX_SOURCE_MEMBERS, max_files=MAX_SOURCE_MEMBERS)
            validate_skill_metadata(authored, name)
            actual = {p.relative_to(workspace).as_posix(): digest_bytes(read_bytes(p)) for p in files}
            require(actual == owner['deployed_file_hashes'], 'Deployment content drift')
            for member, digest in actual.items():
                matches = [d for d in deployments if d.get('value') == member and d.get('target') == 'codex']
                ownership = owner['repo_url'] + '/' + owner['virtual_path']
                require(len(matches) == 1 and matches[0]['active_owner'] == ownership
                        and matches[0]['owners'] == [ownership] and matches[0]['content_hash'] == digest,
                        'Ambiguous deployment ownership')
            if name == 'gh':
                import gh_evaluations as gh
                gh.verify_skill(workspace); gh.verify_competing(workspace); gh.dataset(workspace)
            src = source(name, 'upstream', owner['repo_url'], owner['resolved_commit'], owner['virtual_path'],
                         skill_content(authored))
            deployment = '.agents/skills/' + name
        dataset_roots = [overlays / name / 'evals']
        if name in names:
            dataset_roots.append(authored / 'evals')
        datasets = [p for directory in dataset_roots for p in directory.glob('evals.*')]
        require(len(datasets) <= 1, 'Competing dataset sources')
        suite = strict_dataset(datasets[0], name) if datasets else None
        if suite:
            suite['owner'] = 'overlay' if datasets[0].is_relative_to(overlays) else 'local'
            suite['path'] = datasets[0].relative_to(workspace).as_posix()
        rows.append({'source': src, 'deployment': deployment, 'suite': suite,
                     'behavioral_status': 'configured' if suite else 'not_configured',
                     'measurement': {'status': 'unavailable', 'reasons': ['results_not_supplied']}})
    result = {'schema_version': 1, 'kind': 'inventory', 'skills': rows}
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
    judge = value['judge']; closed(judge, ('model', 'provider', 'enabled'))
    optional(judge['model'], token); optional(judge['provider'], token); optional(judge['enabled'], boolean)
    closed(value['attempts'], ('mode', 'maximum', 'stop_on_pass', 'pass_threshold'))
    enum(value['attempts']['mode'], ('standard', 'confirmation', 'unknown'))
    optional(value['attempts']['maximum'], lambda v: count(v, 100))
    if value['attempts']['mode'] in reports.MODES and value['attempts']['maximum'] is not None:
        require(value['attempts']['maximum'] == reports.MODES[value['attempts']['mode']],
                'Benchmark mode attempt count mismatch')
    optional(value['attempts']['stop_on_pass'], boolean); optional(value['attempts']['pass_threshold'], number)
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


def reference(root, path, artifact, locator=(), extract=None):
    return reference_from_digest(root, path, artifact, digest_bytes(read_bytes(path)), locator, extract)


def reference_from_digest(root, path, artifact, raw_digest, locator=(), extract=None):
    sha(raw_digest)
    member = path.relative_to(root).as_posix()
    value = {'artifact_id': artifact, 'member': member, 'locator': list(locator), 'digest': raw_digest}
    if extract is not None:
        member_record = next((row for row in extract['members'] if row['member'] == member), None)
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


def validate_evidence(data, *, public=False):
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
    ids = case_ids(ds['case_ids']); require(ds['case_cohort_digest'] == identity(sorted(ids)), 'Cohort mismatch')
    validate_policy(data['policy'])
    availability = data['availability']; closed(availability, ('status', 'reasons', 'provenance'))
    enum(availability['status'], ('complete', 'incomplete', 'unavailable')); enum(availability['provenance'], PROVENANCE)
    require(type(availability['reasons']) is list and len(availability['reasons']) <= len(REASONS)
            and len(set(availability['reasons'])) == len(availability['reasons']), 'Invalid reasons')
    for reason in availability['reasons']:
        enum(reason, REASONS)
    require((availability['status'] == 'complete') == (not availability['reasons']), 'Contradictory availability')
    references = data['references']; require(type(references) is list and len(references) <= MAX_TRIALS + 100, 'Reference limit')
    ref_ids = set()
    for ref in references:
        validate_reference(ref); require(ref['id'] not in ref_ids, 'Duplicate reference'); ref_ids.add(ref['id'])
        if ref['availability'] != 'available':
            reason = 'reference_expired' if ref['availability'] == 'expired' else 'reference_unavailable'
            require(availability['status'] == 'incomplete' and reason in availability['reasons'], 'Missing reference limitation')
    require(type(data['observations']) is list and len(data['observations']) <= MAX_TRIALS, 'Trial limit exceeded')
    seen = set(); native_ids = set(); observation_ids = set()
    for obs in data['observations']:
        obs_fields = ('id', 'arm', 'case_id', 'attempt', 'score', 'scores', 'rubric_pass', 'deterministic_gate', 'deterministic_scores', 'references')
        closed(obs, obs_fields if public else obs_fields + ('native_id', 'native_trial', 'native_task'))
        sha(obs['id']); enum(obs['arm'], ('with_skill', 'without_skill')); require(obs['case_id'] in ids, 'Unknown case')
        optional(obs['attempt'], lambda v: count(v, 100)); require(obs['attempt'] is None or obs['attempt'] >= 1, 'Invalid attempt index')
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
    require(type(data['arms']) is list and len(data['arms']) <= 2, 'Invalid arms')
    arm_names = []
    for arm in data['arms']:
        closed(arm, ('name', 'condition', 'coverage', 'execution_status', 'execution_error_count', 'rubric'))
        enum(arm['name'], ('with_skill', 'without_skill')); arm_names.append(arm['name']); validate_condition(arm['condition'])
        require(arm['condition']['target_present'] == (arm['name'] == 'with_skill'), 'Arm target mismatch')
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
        if rubric['total_cases'] is not None:
            require(rubric['total_cases'] == len(ids) and rubric['passed_cases'] is not None
                    and rubric['passed_cases'] <= rubric['total_cases'], 'Rubric denominator mismatch')
            if cov['case_details'] == 'complete':
                passes = {o['case_id'] for o in recorded if o['rubric_pass'] is True}
                require(len(passes) == rubric['passed_cases'], 'Rubric count mismatch')
        if rubric['threshold'] is not None:
            require(all(o['rubric_pass'] is None or o['score'] is not None
                        and o['rubric_pass'] == (o['score'] >= rubric['threshold']) for o in recorded),
                    'Contradictory native rubric pass')
        if arm['execution_status'] == 'succeeded':
            require(arm['execution_error_count'] == 0, 'Succeeded arm has errors')
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
        closed(scan, ('scanner', 'status', 'passed', 'severity_counts', 'references'))
        token(scan['scanner']); scanner_ids.append(scan['scanner']); enum(scan['status'], ('passed', 'failed', 'incomplete', 'skipped'))
        optional(scan['passed'], boolean)
        if scan['status'] in ('passed', 'failed'):
            require(scan['passed'] == (scan['status'] == 'passed'), 'Contradictory scanner outcome')
        closed(scan['severity_counts'], ('critical', 'high', 'medium', 'low'))
        for val in scan['severity_counts'].values():
            optional(val, count)
        require(type(scan['references']) is list and set(scan['references']) <= ref_ids, 'Dangling scan reference')
        if availability['status'] == 'complete':
            require(scan['status'] not in ('incomplete', 'skipped'), 'Incomplete scan promotion')
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
        require(not data['observations'] and not data['metrics'] and not data['scans'] and not data['findings'], 'Unavailable evidence has observations')
        for arm in data['arms']:
            require(all(arm['coverage'][k] is None for k in ('recorded_attempts', 'scored_attempts', 'unscored_attempts')), 'Invented observed count')
    elif data['kind'] == 'behavioral':
        require(sorted(arm_names) == ['with_skill', 'without_skill'], 'Missing comparison arms')
        if availability['status'] == 'complete':
            require(len(data['metrics']) == 4 and data['run_id'] is not None, 'Incomplete metrics')
            require(data['source']['content']['digest'] is not None and ds['staged_digest'] is not None
                    and data['policy']['fields']['evaluator_revision'] is not None
                    and data['policy']['patch_digest'] is not None
                    and data['policy']['attempts']['maximum'] is not None, 'Missing identity metadata')
    if data['kind'] == 'static':
        require(not data['arms'] and not data['metrics'] and not data['observations'], 'Static report implies behavior')
        require(availability['status'] == 'unavailable' or bool(data['scans']), 'Static evidence missing scans')
        if availability['status'] != 'unavailable' and data['source']['content']['digest'] is None:
            require(availability['status'] == 'incomplete' and 'source_unavailable' in availability['reasons'],
                    'Static source unavailable')
    if availability['status'] == 'complete':
        require(all(r['availability'] == 'available' for r in references), 'Unavailable reference promotion')
    depth(data, 12 if public else 32)
    if public:
        require(len(encoded(data)) <= PUBLIC_LIMIT, 'Public report size exceeded')
    return data


def project(data):
    validate_evidence(data)
    # Every object is rebuilt from fixed fields. A native report is never accepted.
    out = {key: copy.deepcopy(data[key]) for key in ('schema_version', 'kind', 'source', 'run_id', 'dataset',
           'policy', 'arms', 'metrics', 'scans', 'findings', 'references', 'availability')}
    out['observations'] = [{key: copy.deepcopy(obs[key]) for key in
        ('id', 'arm', 'case_id', 'attempt', 'score', 'scores', 'rubric_pass', 'deterministic_gate', 'deterministic_scores', 'references')}
        for obs in data['observations']]
    validate_evidence(out, public=True)
    return out


def load_extract(root):
    path = root / 'extract-manifest.json'
    if not path.exists():
        return None
    raw = read_bytes(path)
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
    require(type(value['members']) is list and len(value['members']) <= MAX_TRIALS + 100, 'Extract limit')
    names = []
    for row in value['members']:
        closed(row, ('member', 'original_digest', 'extract_digest'))
        relative(row['member']); sha(row['original_digest']); sha(row['extract_digest']); names.append(row['member'])
    require(len(names) == len(set(names)), 'Duplicate extract member')
    # One time observation for the whole normalization. No durable-original
    # retention is recorded by the supported manifest, so expiry is fail-closed.
    deadline = datetime.fromisoformat(value['origin']['expires_at'])
    value['_reference_availability'] = 'expired' if utc_now() >= deadline else 'available'
    return value


def select_run(root, name, selected):
    base = root / 'results' / name
    safe_path(base, directory=True)
    candidates = []
    for path in base.iterdir():
        # An alias is never selected or followed; all links are rejected by safe_tree.
        if path.name == 'latest':
            continue
        safe_path(path, directory=True); token(path.name); candidates.append(path)
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
    safe_tree(root); skill_id(name)
    run = select_run(root, name, selected)
    extract = load_extract(root)
    artifact = extract['artifact_id'] if extract else run.name
    member_digests = {}
    def read_member(path, *, native_snapshot=False):
        require(path not in member_digests, 'Duplicate behavioral member read')
        raw = read_bytes(path)
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
    has_config = config_path.exists()
    config = read_member(config_path) if has_config else result.get('run_config', {})
    require(type(config) is dict, 'Native configuration object required')
    if has_config and 'run_config' in result:
        require(config == result['run_config'], 'Conflicting native configuration')
    refs = []
    def ref(path, locator=()):
        row = reference_from_digest(root, path, artifact, member_digests[path], locator, extract)
        if row['id'] not in {r['id'] for r in refs}:
            refs.append(row)
        return row['id']
    ref(result_path)
    if has_config:
        ref(config_path)
    limitations = set()
    provenance_path = root / 'provenance.json'
    has_provenance = provenance_path.exists()
    provenance = read_member(provenance_path) if has_provenance else {}
    require(type(provenance) is dict, 'Native provenance object required')
    recovery = provenance.get('status') == 'incomplete'
    if recovery:
        require(result['report_status'] == 'incomplete' or result.get('diagnostic_only') is True,
                'Contradictory recovery status')
    elif provenance:
        require(provenance.get('schema_version') == 1 and provenance.get('skill') == name, 'Provenance identity mismatch')
        require(provenance.get('mode') in ('standard', 'confirmation'), 'Unknown benchmark mode')
    if has_provenance:
        ref(provenance_path)
    versions = {}
    if (root / 'versions.json').exists():
        versions = read_member(root / 'versions.json')
        validate_runtime_versions(versions)
        ref(root / 'versions.json')
    if any(versions.get(key) is None for key in ('skillevaluator', 'evaluator_revision')):
        limitations.add('metadata_missing')
    snapshot_path = run / 'dataset_snapshot.json'
    if snapshot_path.exists():
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
    src_contents = historical_content(workspace, src_rev, src_path) if src_rev and historical_owner == 'local' else content()
    src = source(name, historical_owner if src_repo and src_rev else 'unknown', src_repo, src_rev, src_path, src_contents)
    if src_contents['digest'] is None:
        limitations.add('source_unavailable')
    attempt_path = run / 'attempt_policy.json'
    has_attempt = attempt_path.exists()
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
        blob = historical_blob(workspace, rev + ':' + ds_path)
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
    for arm in ('with_skill', 'without_skill'):
        arm_dir = run / 'codex' / arm.replace('_', '-')
        native_condition = agent['conditions'][arm]
        summary_path = arm_dir / 'summary.json'
        if summary_path.exists():
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
        for key in ('execution_status', 'expected_attempts', 'scored_attempts'):
            require(summary[key] == native_condition[key], 'Conflicting native coverage')
        require(bool(summary.get('execution_errors')) == bool(native_condition.get('execution_errors')), 'Conflicting native errors')
        pass_data = summary.get('pass_at_k') or {}
        native_cases = pass_data.get('cases') or {}
        require(set(native_cases) <= set(ids), 'Unknown summary case identity')
        lookup = {}
        for case, case_row in native_cases.items():
            for attempt in case_row.get('attempts', []):
                trial = attempt['trial']; token(trial)
                require(trial not in lookup, 'Duplicate summary trial')
                lookup[trial] = (case, attempt)
        observed = []
        trial_root = arm_dir / 'trials'
        if trial_root.exists():
            trial_paths = sorted(trial_root.glob('*/result.json'))
            require(len(trial_paths) <= MAX_TRIALS, 'Trial input limit')
            for path in trial_paths:
                trial_result = read_member(path)
                trial = trial_result['trial_name']; token(trial)
                require(trial == path.parent.name, 'Trial directory identity mismatch')
                native_id = trial_result['id']; token(native_id)
                reward_path = path.parent / 'reward.json'
                reward = read_member(reward_path) if reward_path.exists() else None
                matched = lookup.get(trial)
                from skillevaluator.tier3.harbor.collector import _entry_id_from_harbor_result, _attempt_ordinal, _canonical_case_id
                case = validate_case_id(reward['entry_id']) if reward is not None else matched[0] if matched else validate_case_id(
                    _canonical_case_id(_entry_id_from_harbor_result(trial_result), set(ids)))
                require(case in ids and (matched is None or case == matched[0]), 'Trial case identity mismatch')
                # Attempt index must be runtime recorded. A missing index never comes from directory order.
                attempt = matched[1] if matched else {'attempt': _attempt_ordinal({'_trial_name': trial}), 'score': None, 'passed': None}
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
                        if key in reward and key in verifier:
                            require(reward[key] == verifier[key], 'Reward score mismatch')
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
        recorded = summary.get('num_trials'); scored = native_condition.get('scored_attempts')
        optional(recorded, count); optional(scored, count)
        cardinality = agent.get('num_trials_with' if arm == 'with_skill' else 'num_trials_without')
        if cardinality is not None:
            require(type(cardinality) is int and cardinality == recorded, 'Conflicting aggregate trial count')
        details = 'complete' if len(observed) == recorded else 'partial' if observed else 'unavailable'
        if details != 'complete':
            limitations.add('case_details_missing')
        if scored != native_condition.get('expected_attempts') or recorded != native_condition.get('expected_attempts'):
            limitations.add('coverage_missing')
        if native_condition.get('execution_status') != 'succeeded' or native_condition.get('execution_errors'):
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
            'execution_error_count': len(native_condition.get('execution_errors') or []),
            'rubric': {'passed_cases': pass_data.get('passed_cases'), 'total_cases': pass_data.get('total_cases'),
                       'threshold': pass_data.get('pass_threshold')}})
        data['observations'].extend(observed)
    if EvaluationService.failure_reason(result) is not None or recovery or result['report_status'] != 'complete' or result.get('diagnostic_only'):
        limitations.add('execution_incomplete')
    if not config.get('evaluated_source'):
        limitations.add('metadata_missing')
    data['references'] = sorted(refs, key=lambda r: r['id'])
    if any(row['availability'] == 'expired' for row in refs):
        limitations.add('reference_expired')
    data['observations'].sort(key=lambda o: (o['arm'], o['case_id'], o['attempt'] or 0, o['id']))
    data['availability'] = {'status': 'incomplete' if limitations else 'complete',
                            'reasons': sorted(limitations), 'provenance': 'reviewed_extract' if extract else 'runtime_recorded'}
    validate_evidence(data)
    return data


def static_required_gate(scan):
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
    return scan['passed'] or (not gating.get('blocking', True) if gating is not None else advisory_skip)


def normalize_static(root, name, workspace=ROOT):
    safe_tree(root); skill_id(name)
    catalog_path = root / 'reports/catalog-summary.json'; catalog, catalog_digest = read_json_and_digest(catalog_path)
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
    report_path = root / 'reports' / name / filename; native, report_digest = read_json_and_digest(report_path)
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
    gates = [static_required_gate(scan) for scan in native['results']]
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
                                historical_content(workspace, rev, path) if rev else content())
    def report_reference(locator=()):
        return reference_from_digest(root, report_path, 'skill-quality', report_digest, locator)
    refs = [reference_from_digest(root, catalog_path, 'skill-quality', catalog_digest), report_reference()]
    # Aggregate native counts remain their own observation; scanner counts are
    # not invented when the pinned report does not supply them.
    data['scans'] = [{'scanner': 'catalog-total', 'status': native['overall_status'], 'passed': native['overall_passed'],
                      'severity_counts': severity, 'references': [refs[1]['id']]}]
    for index, scan in enumerate(native['results']):
        scanner = scan['validator']; token(scanner)
        enum(scan['status'], ('passed', 'failed', 'incomplete', 'skipped'))
        scan_ref = report_reference(('results', index)); refs.append(scan_ref)
        data['scans'].append({'scanner': scanner, 'status': scan['status'], 'passed': scan.get('passed'),
            'severity_counts': {k: scan.get('summary', {}).get(k + '_count')
                                for k in ('critical', 'high', 'medium', 'low')}, 'references': [scan_ref['id']]})
    recorded_incomplete = set()
    for index, scan in enumerate(native['results']):
        for scanner in scan.get('incomplete_scans', []):
            token(scanner); recorded_incomplete.add(scanner)
            if scanner not in {s['scanner'] for s in data['scans']}:
                data['scans'].append({'scanner': scanner, 'status': 'incomplete', 'passed': None,
                    'severity_counts': {k: None for k in ('critical', 'high', 'medium', 'low')}, 'references': [refs[1]['id']]})
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
    if (root / 'versions.json').exists():
        versions, versions_digest = read_json_and_digest(root / 'versions.json')
        validate_runtime_versions(versions)
        data['policy'] = make_policy({'evaluator_revision': versions.get('evaluator_revision')}, provenance='runtime_recorded')
        data['references'].append(reference_from_digest(root, root / 'versions.json', 'skill-quality', versions_digest))
        if versions.get('fixture') == 'synthetic':
            data['availability']['provenance'] = 'synthetic'
            for record in data['references']:
                record['provenance'] = 'synthetic'
    validate_evidence(data)
    return data


def write_outputs(values, destination=None, workspace=ROOT, input_path=None):
    # Finish validation/serialization before reserving an output directory.
    payloads = {name: encoded(value) for name, value in values.items()}
    workspace = Path(workspace).absolute()
    if input_path is not None:
        input_path = Path(input_path).absolute()
    if destination is None:
        # Validate explicit settings without tempfile's probing/fallback writes.
        parent = next((os.environ[key] for key in ('TMPDIR', 'TEMP', 'TMP') if os.environ.get(key)), None)
        parent = safe_path(parent if parent is not None else tempfile.gettempdir(), directory=True)
        require(not parent.is_relative_to(workspace), 'Output must be outside checkout')
        if input_path is not None:
            require(not parent.is_relative_to(input_path), 'Output overlaps input')
        destination = Path(tempfile.mkdtemp(prefix='skill-evidence-', dir=parent))
    else:
        destination = Path(destination).absolute()
        safe_path(destination.parent, directory=True)
        require(not os.path.lexists(destination), 'Output directory must be new')
    safe_path(destination, directory=True, missing=True)
    require(not destination.is_relative_to(workspace) and destination != workspace, 'Output must be outside checkout')
    if input_path is not None:
        require(not destination.is_relative_to(input_path) and not input_path.is_relative_to(destination), 'Output overlaps input')
    if not destination.exists():
        destination.mkdir(mode=0o700)
    for name, payload in payloads.items():
        with (destination / name).open('xb') as stream:
            stream.write(payload)
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
    if args.command == 'inventory':
        values = {'inventory.json': inventory()}
    elif args.command == 'project':
        values = {'public-report.json': project(read_json(args.input))}
    else:
        require(args.kind == 'behavioral' or args.run is None, '--run applies to behavioral evidence')
        data = normalize_behavioral(args.input.absolute(), args.skill, args.run) if args.kind == 'behavioral' else normalize_static(args.input.absolute(), args.skill)
        values = {'evidence.json': data, 'public-report.json': project(data)}
    output = write_outputs(values, args.output, input_path=getattr(args, 'input', None))
    print(output)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, AttributeError, IndexError, OSError) as exc:
        # Native exception strings can contain prose or paths. Keep CLI errors bounded.
        print('Evidence contract rejected (' + type(exc).__name__ + ')', file=sys.stderr)
        sys.exit(1)
