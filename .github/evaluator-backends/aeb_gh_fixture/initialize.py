"""Fixed root-only broker startup; no task-selected commands or audit resets."""

import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import struct
import subprocess
import sys
import time

STATE = Path("/opt/gh-eval/state")
SOCKET = Path("/run/gh-eval/gh.sock")
CONTROL = Path("/opt/aeb-gh")


def require(value):
    if not value:
        raise RuntimeError("gh broker initialization rejected")


def private(path, *, directory=False):
    require(path.resolve(strict=True) == path)
    info = path.lstat()
    require(info.st_uid == 0 and not info.st_mode & 0o022)
    require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
    return info


def fingerprint(pid):
    process = Path("/proc") / str(pid)
    private(process, directory=True)
    command = (process / "cmdline").read_bytes().split(b"\0")[:-1]
    require(len(command) == 6 and Path(os.fsdecode(command[0])).resolve() == Path(sys.executable).resolve())
    require(command[1:] == [b"-I", bytes(STATE / "fixture.py"), b"--serve", bytes(STATE), bytes(SOCKET)])
    status = (process / "status").read_text().splitlines()
    require(next(line for line in status if line.startswith("Uid:")).split()[1:] == ["0"] * 4)
    value = (process / "stat").read_text().rsplit(")", 1)[1].split()
    require(value[0] not in ("Z", "X"))
    return value[19]  # field 22, process start tick; PID reuse cannot satisfy readiness.


def probe(expected):
    private(SOCKET.parent, directory=True)
    info = SOCKET.lstat()
    require(stat.S_ISSOCK(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1)
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(1)
        connection.connect(str(SOCKET))
        pid, uid, _ = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
        require(uid == 0 and pid == expected["pid"] and fingerprint(pid) == expected["start"])
        # The fixed invalid envelope exercises the live request loop. It is
        # rejected before dispatch/audit, so readiness adds no grading operation.
        connection.sendall(b"{}\n")
        with connection.makefile("rb") as stream:
            response = stream.readline(129)
        require(len(response) <= 128 and json.loads(response) == {"error": "invalid broker request"})
    # No modeled request is dispatched; readiness never appends to the audit.
    return {"pid": pid, "start": expected["start"], "uid": uid, "socket_inode": info.st_ino}


def initialize():
    require(os.geteuid() == 0 and sys.argv[1:] == [])
    private(CONTROL, directory=True)
    private(STATE, directory=True)
    approved = json.loads((CONTROL / "approved.json").read_text())
    require(set(approved) == {"case.json", "fixture.py", "setup.py", "client.py"})
    for name, digest in approved.items():
        target = STATE / name
        info = private(target)
        require(info.st_size <= 8 * 1024 * 1024 and hashlib.sha256(target.read_bytes()).hexdigest() == digest)
    private(STATE / "audit.jsonl")
    record = CONTROL / "broker.json"
    if SOCKET.exists() or SOCKET.is_symlink() or record.exists() or record.is_symlink():
        private(record)
        identity = probe(json.loads(record.read_text()))
    else:
        SOCKET.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        private(SOCKET.parent, directory=True)
        process = subprocess.Popen([sys.executable, "-I", str(STATE / "fixture.py"), "--serve", str(STATE), str(SOCKET)],
            env={"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8"}, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            expected = {"pid": process.pid, "start": fingerprint(process.pid)}
            deadline = time.monotonic() + 25
            while True:
                require(process.poll() is None)
                if SOCKET.exists():
                    identity = probe(expected)
                    break
                require(time.monotonic() < deadline)
                time.sleep(0.02)
            with record.open("x") as stream:
                json.dump(identity, stream)
            record.chmod(0o600)
        except BaseException:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=2)
            raise
    print(json.dumps({"status": "ready", **identity}, sort_keys=True))


if __name__ == "__main__":
    initialize()
