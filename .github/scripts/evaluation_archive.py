"""Read legacy registry inputs as pinned data from the local Git object store."""
from functools import lru_cache
from pathlib import Path

INDEX = '.github/evals/legacy-registry-archive.json'


def configured(workspace):
    path = workspace / INDEX
    return path.exists() or path.is_symlink()


def archive_index(workspace):
    import skill_evidence as evidence

    index = evidence.read_json(workspace / INDEX)
    evidence.closed(index, ('version', 'revision', 'members', 'source_inputs'))
    evidence.require(type(index['version']) is int and index['version'] == 1
                     and type(index['members']) is dict and len(index['members']) == 20
                     and type(index['source_inputs']) is dict and len(index['source_inputs']) <= 32,
                     'Invalid legacy registry archive')
    evidence.revision(index['revision'])
    for member, digest in (*index['members'].items(), *index['source_inputs'].items()):
        evidence.relative(member)
        evidence.sha(digest)
    return index


@lru_cache(maxsize=32)
def verified_member(workspace, revision, member, expected):
    import skill_evidence as evidence

    raw = evidence.historical_blob(workspace, f'{revision}:{member}')
    evidence.require(raw is not None, 'Legacy registry archive unavailable in the local Git object store')
    evidence.require(evidence.digest_bytes(raw) == expected, 'Legacy registry archive digest mismatch')
    return raw


def read_member(workspace, member):
    from skill_evidence import ROOT, read_bytes, require

    workspace = Path(workspace).absolute()
    if configured(workspace):
        index = archive_index(workspace)
        require(member in index['members'], 'Unregistered legacy registry archive member')
        return verified_member(workspace, index['revision'], member, index['members'][member])
    # Explicit frozen workspaces still provide the original layout.
    require(workspace != ROOT, 'Legacy registry archive index missing')
    return read_bytes(workspace / member)


def read_json(workspace, member):
    from skill_evidence import parse_json

    return parse_json(read_member(workspace, member))
