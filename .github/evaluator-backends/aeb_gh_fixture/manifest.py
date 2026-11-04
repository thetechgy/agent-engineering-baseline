"""Bound native task approval to an operator-held, content-addressed manifest."""

import hashlib
import json
import os
from pathlib import Path
import re
import stat

MAX_BYTES = 8 * 1024 * 1024


def require(value):
    if not value:
        raise ValueError("Unapproved gh initialization inputs")


def regular(path):
    path = Path(path)
    require(path.is_absolute() and path.resolve(strict=True) == path)
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= MAX_BYTES)
    # O_NOFOLLOW closes replacement-by-link between inspection and open.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    def identity(value):
        return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns, value.st_mode, value.st_nlink)
    with os.fdopen(fd, "rb") as stream:
        require(identity(os.fstat(stream.fileno())) == identity(info))
        raw = stream.read(MAX_BYTES + 1)
        require(len(raw) <= MAX_BYTES and identity(os.fstat(stream.fileno())) == identity(info))
    return raw


def digest(path):
    return hashlib.sha256(regular(Path(path).absolute())).hexdigest()


def tree(root):
    root = Path(root).absolute()
    require(root.resolve(strict=True) == root and root.is_dir())
    result = {}
    total = 0
    count = 0
    pending = [root]
    while pending:
        directory = pending.pop()
        for path in sorted(directory.iterdir()):
            count += 1
            info = path.lstat()
            mode = info.st_mode
            total += info.st_size if stat.S_ISREG(mode) else 0
            require(count <= 4096 and total <= 64 * 1024 * 1024)
            require(not path.is_symlink())
            if stat.S_ISDIR(mode):
                pending.append(path)
            else:
                result[path.relative_to(root).as_posix()] = digest(path)
    return dict(sorted(result.items()))


def task_identity(task):
    from harbor.models.task.task import Task
    from skillevaluator.tier3.harbor.adapter import _task_environment_context_hash
    members = tree(task)
    native = Task(task)
    entry = json.loads(regular(task / "tests/entry.json"))
    require(type(entry.get("has_skill")) is bool)
    case = entry["id"]
    require(isinstance(case, str) and re.fullmatch(r"gh-[0-9]{3}(?:-[a-z-]+)?", case))
    require(native.name == case)
    private = task / "environment/private"
    return {"case": case, "arm": "with_skill" if entry["has_skill"] else "without_skill",
            "checksum": native.checksum,
            "context": _task_environment_context_hash(task / "environment"),
            "members": members,
            "private": {"case.json": digest(private / "cases" / (case + ".json")),
                        **{name: digest(private / name) for name in ("fixture.py", "setup.py", "client.py")}}}


def payload_digest():
    return digest(Path(__file__).absolute().with_name("initialize.py"))


def write_manifest(directory, tasks, *, staged_roots):
    directory = Path(directory).absolute()
    require(directory.resolve() == directory and not directory.exists())
    require(all(not directory.is_relative_to(Path(root).resolve()) for root in staged_roots))
    require(0 < len(tasks) <= 48)
    identities = [task_identity(Path(task).absolute()) for task in tasks]
    rows = {row["case"] + "__" + row["arm"]: row for row in identities}
    require(len(rows) == len(tasks))
    directory.mkdir(mode=0o700, parents=True)
    raw = json.dumps({"schema": 1, "payload": payload_digest(), "tasks": rows}, sort_keys=True, separators=(",", ":")).encode()
    require(len(raw) <= MAX_BYTES)
    path = directory / ("manifest-" + hashlib.sha256(raw).hexdigest() + ".json")
    with path.open("xb") as stream:
        stream.write(raw)
    path.chmod(0o600)
    return path


def load_manifest(path):
    path = Path(path)
    raw = regular(path)
    require(path.name == "manifest-" + hashlib.sha256(raw).hexdigest() + ".json")
    for target in (path, path.parent):
        info = target.lstat()
        require(info.st_uid == os.geteuid() and not stat.S_IMODE(info.st_mode) & 0o077)
    data = json.loads(raw)
    require(set(data) == {"schema", "payload", "tasks"} and type(data["schema"]) is int and data["schema"] == 1)
    require(data["payload"] == payload_digest() and type(data["tasks"]) is dict and 0 < len(data["tasks"]) <= 48)
    for key, row in data["tasks"].items():
        require(type(row) is dict and set(row) == {"case", "arm", "checksum", "context", "members", "private"})
        require(isinstance(row["case"], str) and re.fullmatch(r"gh-[0-9]{3}(?:-[a-z-]+)?", row["case"]))
        require(row["arm"] in ("with_skill", "without_skill") and key == row["case"] + "__" + row["arm"])
        require(type(row["members"]) is dict and 0 < len(row["members"]) <= 4096)
        require(type(row["private"]) is dict and set(row["private"]) == {"case.json", "fixture.py", "setup.py", "client.py"})
        require(all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
                    for value in (row["checksum"], row["context"], *row["members"].values(), *row["private"].values())))
    return data, hashlib.sha256(raw).hexdigest()


def approve(path, task):
    path, task = Path(path), Path(task).absolute()
    require(not path.is_relative_to(task))
    data, seal = load_manifest(path)
    row = task_identity(task)
    require(data["tasks"].get(row["case"] + "__" + row["arm"]) == row)
    return row, seal


def prerequisites(environment_kwargs):
    from . import MANIFEST_ENV
    try:
        require(not environment_kwargs)
        # Content identity is portable to the CLI's private staging directory;
        # actual task checksums are revalidated at environment startup.
        load_manifest(Path(os.environ.get(MANIFEST_ENV, "")))
    except (OSError, ValueError, KeyError, TypeError):
        return ["Reviewed operator gh initialization manifest required"]
    return []
