#!/usr/bin/env python3
"""Offline gh command model. Never imports a network client or forwards commands."""

import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
import sys
import socketserver

ALIASES = {
    "-R": "--repo",
    "-L": "--limit",
    "-q": "--jq",
    "-X": "--method",
    "-f": "--raw-field",
    "-F": "--field",
    "-b": "--body",
    "-Fbody": "--body-file",
}
VALUES = {
    "--repo",
    "--limit",
    "--jq",
    "--method",
    "--raw-field",
    "--field",
    "--json",
    "--body",
    "--body-file",
    "--attach",
    "--author",
    "--app",
    "--search",
    "--branch",
    "--workflow",
    "--commit",
    "--interval",
    "--hostname",
    "--state",
}
FLAGS = {
    "--paginate",
    "--slurp",
    "--comments",
    "--log-failed",
    "--exit-status",
    "--watch",
    "--help",
}


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def parse(argv):
    positional, options = [], {}
    i = 0
    while i < len(argv):
        token = argv[i]
        key, sep, value = token.partition("=")
        key = (
            "--body-file"
            if key == "-F" and argv[:2] in (["pr", "comment"], ["issue", "comment"])
            else ALIASES.get(key, key)
        )
        if key in VALUES:
            if not sep:
                i += 1
                if i == len(argv):
                    raise ValueError("missing flag argument")
                value = argv[i]
            options.setdefault(key, []).append(value)
        elif key in FLAGS or key == "--version":
            if sep:
                raise ValueError("unsupported flag value")
            options[key] = [True]
        elif token.startswith("-"):
            raise ValueError("unknown flag")
        else:
            positional.append(token)
        i += 1
    return positional, options


def dispatch(case, argv, history, body=None):
    """Pure transition used by executable and independent verifier replay."""
    result = {
        "route": "unsupported",
        "exit_code": 2,
        "stdout": "",
        "stderr": "unsupported fixture command",
        "mutation": None,
        "repo": None,
    }
    try:
        pos, opts = parse(argv)
    except ValueError as error:
        return {**result, "stderr": str(error)}
    if pos == [] and "--version" in opts:
        return {
            **result,
            "route": "version",
            "exit_code": 0,
            "stdout": "gh version 2.102.0 (fixture)",
            "stderr": "",
        }
    if "--help" in opts:
        key = " ".join(pos[:1] if pos[:1] == ["api"] else pos[:2])
        if key in case.get("help", {}):
            return {
                **result,
                "route": "help",
                "exit_code": 0,
                "stdout": case["help"][key],
                "stderr": "",
            }
    repo = opts.get("--repo", [None])[-1]
    if pos[:1] == ["api"] and len(pos) > 1 and pos[1].startswith("repos/"):
        repo = "/".join(pos[1].split("/")[1:3])
    fields = {}
    for key in ("--field", "--raw-field"):
        for item in opts.get(key, []):
            name, sep, value = item.partition("=")
            if not sep:
                return result
            fields[name] = value
    query = fields.get("query", "")
    if pos[:2] == ["api", "graphql"]:
        repo = f"{fields.get('owner', '')}/{fields.get('name', '')}"
        if "mutation" in query:
            return {**result, "route": "unauthorized", "repo": repo}
        if query.count("{") != query.count("}"):
            return {
                **result,
                "route": "malformed",
                "repo": repo,
                "stderr": "GraphQL: Expected RCURLY, actual EOF",
            }
    if pos[:1] == ["api"] and pos[1:2] != ["graphql"]:
        method = opts.get("--method", ["POST" if fields else "GET"])[-1]
        if method != "GET":
            return {
                **result,
                "route": "unauthorized",
                "repo": repo,
                "stderr": "fixture rejected non-GET REST request",
            }
    result["repo"] = repo
    for route in case["routes"]:
        match = route["match"]
        if pos != match["pos"]:
            continue
        if match.get("repo") and repo != match["repo"]:
            continue

        def equivalent(key, left, right):
            if key == "--json" and left and right:
                return set(left[-1].split(",")) == set(right[-1].split(","))
            if key in ("--field", "--raw-field") and left and right:
                return sorted(
                    re.sub(r"\s+", "", v) if v.startswith("query=") else v for v in left
                ) == sorted(
                    re.sub(r"\s+", "", v) if v.startswith("query=") else v
                    for v in right
                )
            return left == right

        if any(
            not equivalent(key, opts.get(key), val)
            for key, val in match.get("options", {}).items()
        ):
            continue
        if (
            set(opts)
            - set(match.get("options", {}))
            - set(match.get("allow", []))
            - {"--jq"}
        ):
            continue
        if any(word not in query for word in match.get("query", [])):
            continue
        if "reviewThreads" in match.get("query", []):
            number = re.search(
                r"pullRequest\s*\(\s*number\s*:\s*(\d+|\$[A-Za-z]+)", query
            )
            if (
                not number
                or (
                    fields.get(number[1][1:])
                    if number[1].startswith("$")
                    else number[1]
                )
                != "17"
            ):
                continue
        if "--paginate" in opts and pos[:2] == ["api", "graphql"]:
            if not all(
                token in query
                for token in ("$endCursor", "after:", "hasNextPage", "endCursor")
            ):
                continue
        if any(fields.get(key) != val for key, val in match.get("fields", {}).items()):
            continue
        if match.get("body") is not None and body != match["body"]:
            continue
        count = sum(row["route"] == route["id"] for row in history)
        responses = route["responses"]
        response = responses[min(count, len(responses) - 1)]
        response = dict(response)
        if "--jq" in opts and response.get("exit_code", 0) == 0:
            # Real jq evaluates filtering only; never shells or forwards a request.
            filtered = subprocess.run(
                ["jq", "-r", opts["--jq"][-1]],
                input=response["stdout"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if filtered.returncode:
                return {**result, "stderr": "unsupported or invalid JSON filter"}
            response["stdout"] = filtered.stdout.rstrip("\n")
        return {
            **result,
            **response,
            "route": route["id"],
            "stderr": response.get("stderr", ""),
            "exit_code": response.get("exit_code", 0),
        }
    return result


def read_regular(path):
    if path.resolve() != path.absolute() or not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("linked or special fixture input")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("oversized fixture input")
    return path.read_text()


def serve(root, socket_path):
    case = json.loads(read_regular(root / "case.json"))
    audit = root / "audit.jsonl"

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.connection.settimeout(5)
            try:
                request = json.loads(self.rfile.readline(65537))
                argv, body = request["argv"], request["body"]
                if (not isinstance(argv, list) or len(argv) > 100
                    or not all(isinstance(arg, str) for arg in argv)
                    or (body is not None and not isinstance(body, str))):
                    raise ValueError("invalid broker request")
                history = [json.loads(line) for line in read_regular(audit).splitlines()]
                result = dispatch(case, argv, history, body)
                row = {
                    **result, "argv": argv, "body": body, "sequence": len(history),
                    "previous": digest(history[-1]) if history else digest(case),
                }
                with audit.open("a") as stream:
                    stream.write(json.dumps(row, sort_keys=True) + "\n")
                self.wfile.write(json.dumps({**result, "receipt": digest(row)}).encode() + b"\n")
            except (OSError, ValueError, KeyError, TypeError):
                self.wfile.write(b'{"error":"invalid broker request"}\n')

    # A single-threaded server serializes transitions and owns the only audit writer.
    with socketserver.UnixStreamServer(str(socket_path), Handler) as server:
        socket_path.chmod(0o666)
        server.serve_forever()


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "--serve":
        sys.exit("private broker invocation required")
    serve(Path(sys.argv[2]), Path(sys.argv[3]))
