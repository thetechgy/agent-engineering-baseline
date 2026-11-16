"""Versioned, runtime-neutral read inventories from trusted task/deployment metadata.

No observed command or returned text can add an inventory member. This is bounded
provisioning/evidence validation, not a sandbox or filesystem attestation service.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat

SCHEMA = 'task-resources-v1'


def canonical(value, *, absolute):
    if not isinstance(value, str) or not value or '\x00' in value:
        raise ValueError('Invalid resource path')
    path = PurePosixPath(value)
    if path.is_absolute() != absolute or str(path) != value or '..' in path.parts:
        raise ValueError('Noncanonical resource path')
    if value in ('.', '/'):
        raise ValueError('Unbounded resource path')
    return value


def validate_inventory(value):
    if not isinstance(value, dict) or set(value) != {'schema', 'target', 'files', 'directories'} or value['schema'] != SCHEMA:
        raise ValueError('Unsupported resource inventory')
    target = value['target']
    if (not isinstance(target, dict) or set(target) != {'id', 'deployed'}
        or not isinstance(target['id'], str) or not re.fullmatch('[a-z0-9-]+', target['id'])
        or type(target['deployed']) is not bool):
        raise ValueError('Invalid target identity')
    if not isinstance(value['files'], list) or not 1 <= len(value['files']) <= 512:
        raise ValueError('Invalid resource population')
    paths = set(); sources = {}; target_sources = set()
    for row in value['files']:
        if not isinstance(row, dict) or set(row) != {'source', 'path', 'sha256', 'role', 'skill'}:
            raise ValueError('Invalid resource member')
        canonical(row['source'], absolute=False); canonical(row['path'], absolute=True)
        if (row['path'] in paths or not re.fullmatch('[0-9a-f]{64}', row['sha256'])
            or row['role'] not in ('input', 'target', 'discovery')):
            raise ValueError('Ambiguous resource member')
        if row['role'] == 'input':
            if row['skill'] is not None: raise ValueError('Input has skill identity')
        elif not isinstance(row['skill'], str) or not re.fullmatch('[a-z0-9-]+', row['skill']):
            raise ValueError('Invalid skill identity')
        if (row['role'] == 'target') != (row['skill'] == target['id']):
            raise ValueError('Inconsistent target role')
        binding = (row['sha256'], row['role'], row['skill'])
        if row['source'] in sources and sources[row['source']] != binding:
            raise ValueError('Inconsistent source binding')
        sources[row['source']] = binding; paths.add(row['path'])
        if row['role'] == 'target' and PurePosixPath(row['source']).name == 'SKILL.md':
            target_sources.add(row['source'])
    if len(target_sources) != int(target['deployed']):
        raise ValueError('Target deployment mismatch')
    directories = value['directories']
    if not isinstance(directories, list) or len(directories) > 128 or len(set(directories)) != len(directories):
        raise ValueError('Ambiguous discovery directories')
    for path in directories: canonical(path, absolute=True)
    return value


def inventory_bytes(value):
    validate_inventory(value)
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def regular_bytes(path):
    path = Path(path)
    if path.resolve(strict=True) != path.absolute():
        raise ValueError('Resource symlink or traversal')
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 8 * 1024 * 1024:
        raise ValueError('Resource is not a bounded single-link regular file')
    return path.read_bytes()


def target_bytes(native, inventory):
    """Select the one trusted target source, independently of directory order."""
    validate_inventory(inventory)
    rows = [r for r in inventory['files'] if r['role'] == 'target' and PurePosixPath(r['source']).name == 'SKILL.md']
    if not rows: return None
    row = rows[0]
    raw = regular_bytes(Path(native) / row['source'])
    if hashlib.sha256(raw).hexdigest() != row['sha256']:
        raise ValueError('Target source drift')
    return raw


def trace_observations_complete(trajectory):
    """Require a unique string observation per issued call before normalization.

    Normalizers can coerce missing content to an empty string. That conversion
    must not manufacture completed evidence. This accepts the existing ATIF
    call/result linkage across steps; it does not interpret agent commands.
    """
    if not isinstance(trajectory, dict) or not isinstance(trajectory.get('steps'), list): return False
    issued = []; observed = []
    for step in trajectory['steps']:
        if not isinstance(step, dict): return False
        calls = step.get('tool_calls', [])
        if not isinstance(calls, list): return False
        for call in calls:
            if not isinstance(call, dict) or not isinstance(call.get('tool_call_id'), str): return False
            issued.append(call['tool_call_id'])
        observation = step.get('observation') or {}
        if not isinstance(observation, dict) or not isinstance(observation.get('results', []), list): return False
        for result in observation.get('results', []):
            if (not isinstance(result, dict) or not isinstance(result.get('source_call_id'), str)
                or not isinstance(result.get('content'), str)): return False
            observed.append(result['source_call_id'])
    return bool(issued) and len(set(issued)) == len(issued) and sorted(issued) == sorted(observed)
