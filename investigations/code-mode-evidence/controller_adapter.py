"""Adapt only the pinned operator fixture; never patch Codex."""
from pathlib import Path


def adapt(path):
    source=Path(path).read_text()
    pairs=[
        ("executable=pathlib.Path('/opt/codex/bin/codex')", "executable=pathlib.Path(payload['codex'])"),
        ("info.st_uid==0 and ", ""),
        ("=='b93f6811d3f653f0fb83be4050d857fb9abbb111dfa2ce160563327daff7f306'", "==payload['codex_sha256']"),
        ("cmd+=['app-server','--listen','stdio://']", "cmd+=['app-server','--listen','stdio://','--code-mode-host',payload['endpoint']]"),
        ("home='/home/agent/.codex'", "home=payload['home']"),
        ("'HOME':'/home/agent'", "'HOME':payload['home']"),
        ("cwd='/workspace'", "cwd=payload['workspace']"),
    ]
    for old,new in pairs:
        assert old in source
        source=source.replace(old,new)
    return source
