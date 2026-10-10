#!/usr/bin/env python3
"""Public CLI transport. Response definitions and audit state stay in the broker."""

import json
import os
from pathlib import Path
import socket
import stat
import sys


def main():
    argv = sys.argv[1:]
    body = None
    # Send only explicitly supplied comment text; never ask the broker to open a path.
    for index, token in enumerate(argv):
        if token in ("--body-file", "-F") and argv[:2] in (
            ["pr", "comment"], ["issue", "comment"]
        ):
            path = Path(argv[index + 1]).absolute()
            if path.resolve() != path or not stat.S_ISREG(path.lstat().st_mode):
                raise ValueError("unsafe comment body file")
            if path.stat().st_size > 65536:
                raise ValueError("oversized comment body")
            body = path.read_text()
        elif token == "--body" or token == "-b":
            body = argv[index + 1]
        elif token.startswith("--body="):
            body = token.partition("=")[2]
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(5)
        connection.connect(os.environ.get("GH_FIXTURE_SOCKET", "/run/gh-eval/gh.sock"))
        connection.sendall(json.dumps({"argv": argv, "body": body}).encode() + b"\n")
        with connection.makefile("rb") as stream:
            result = json.loads(stream.readline(2 * 1024 * 1024))
    print(result["stdout"], end="\n" if result["stdout"] else "")
    print(result["stderr"], file=sys.stderr, end="\n" if result["stderr"] else "")
    print("GH_FIXTURE_RECEIPT=" + result["receipt"], file=sys.stderr)
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
