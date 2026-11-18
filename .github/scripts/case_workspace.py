"""Trusted operator probe. Run with isolated Python and supply the baseline on stdin."""
import base64
import hashlib
import json
import os
import re
import stat
import sys

MAX_FILES = 256
MAX_FILE = 128 * 1024
MAX_TREE = 4 * 1024 * 1024
MAX_CHANGED = 128 * 1024


def compare(root, baseline):
    rootfd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        return walk(rootfd, baseline)
    finally:
        os.close(rootfd)


def walk(rootfd, baseline):
    inventory = {}
    changes = []
    visited = retained = 0

    def scan(fd, relative):
        nonlocal visited, retained
        before = os.fstat(fd)
        with os.scandir(fd) as entries:
            for entry in entries:
                inspect(fd, relative, entry.name)
        after = os.fstat(fd)
        if before.st_ctime_ns != after.st_ctime_ns or before.st_mtime_ns != after.st_mtime_ns:
            raise ValueError("unstable_directory")

    def inspect(fd, relative, name):
        nonlocal visited, retained
        path = name if not relative else relative + "/" + name
        if (len(inventory) >= MAX_FILES or len(path) > 256 or
                not re.fullmatch(r"[a-zA-Z0-9._-]{1,96}", name)):
            raise ValueError("unsupported_path")
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        mode = stat.S_IMODE(info.st_mode)
        data = None
        if stat.S_ISDIR(info.st_mode):
            item = {"type": "directory", "mode": mode}
        elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
            if info.st_size > MAX_FILE or visited + info.st_size > MAX_TREE:
                raise ValueError("scan_limit")
            child = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=fd)
            with os.fdopen(child, "rb") as stream:
                actual = os.fstat(child)
                if not os.path.samestat(info, actual) or not stat.S_ISREG(actual.st_mode):
                    raise ValueError("unstable_file")
                data = stream.read(MAX_FILE + 1)
                end = os.fstat(child)
            if (len(data) != info.st_size or end.st_ctime_ns != info.st_ctime_ns or
                    end.st_mtime_ns != info.st_mtime_ns):
                raise ValueError("unstable_file")
            visited += len(data)
            item = {"type": "file", "mode": mode, "sha256": hashlib.sha256(data).hexdigest()}
        else:
            raise ValueError("unsupported_member")
        inventory[path] = item
        if baseline is not None and baseline.get(path) != item:
            row = {"path": path, "change": "modified" if path in baseline else "added", **item}
            if data is not None:
                retained += len(data)
                if retained > MAX_CHANGED:
                    raise ValueError("change_limit")
                row["data"] = base64.b64encode(data).decode("ascii")
            changes.append(row)
        if item["type"] == "directory":
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            try:
                if not os.path.samestat(info, os.fstat(child)):
                    raise ValueError("unstable_directory")
                scan(child, path)
            finally:
                os.close(child)
    scan(rootfd, "")
    if baseline is None:
        return {"baseline": inventory}
    changes.extend({"path": path, "change": "deleted"} for path in baseline.keys() - inventory.keys())
    return {"changes": sorted(changes, key=lambda row: row["path"])}


if __name__ == "__main__":
    try:
        baseline = json.load(sys.stdin)
    except (OSError, ValueError):
        sys.exit(os.EX_DATAERR)
    try:
        result = compare("/workspace", baseline)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    except (OSError, ValueError, UnicodeError):
        sys.exit(1)
