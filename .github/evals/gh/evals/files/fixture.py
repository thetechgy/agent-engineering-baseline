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


class GraphQLSubsetError(ValueError):
    pass


class UnsupportedGraphQL(GraphQLSubsetError):
    pass


class UnauthorizedGraphQL(UnsupportedGraphQL):
    pass


# A closed schema for the two read-only selections modeled by this fixture.
# Not a general GraphQL parser: aliases, fragments, directives, lists and defaults
# remain unsupported. Bounds and whole-input consumption are part of the contract.
GRAPHQL_FIELDS = {
    "Query": {"repository": ("Repository", {"owner": "String!", "name": "String!"})},
    "Repository": {"pullRequest": ("PullRequest", {"number": "Int!"}), "issues": ("Issues", {})},
    "PullRequest": {"reviewThreads": ("Threads", {"first": "Int", "after": "String"})},
    "Threads": {"nodes": ("Thread", {}), "pageInfo": ("PageInfo", {})},
    "Thread": {"id": (None, {}), "isResolved": (None, {}), "comments": ("Comments", {"first": "Int"})},
    "Comments": {"nodes": ("Comment", {})},
    "Comment": {"body": (None, {})},
    "PageInfo": {"hasNextPage": (None, {}), "endCursor": (None, {})},
    "Issues": {"totalCount": (None, {})},
}


class GraphQLSubset:
    """Tokenize and validate a bounded modeled operation, without executing code."""

    token = re.compile(r'[ \t\r\n,\ufeff]+|\#[^\r\n]*|[A-Za-z_][A-Za-z_0-9]*|-?(?:0|[1-9][0-9]*)|'
                       r'"(?:[^"\\\x00-\x1f]|\\["\\/bfnrt]|\\u[0-9A-Fa-f]{4})*"|\.\.\.|[!$():{}@\[\]=]')

    def __init__(self, query, fields):
        try:
            size = len(query.encode("utf-8"))
        except UnicodeError:
            raise GraphQLSubsetError("invalid query Unicode") from None
        if not query or size > 16384:
            raise GraphQLSubsetError("query limit")
        self.tokens = []
        position = 0
        while position < len(query):
            matched = self.token.match(query, position)
            if not matched:
                raise GraphQLSubsetError("unsupported query token")
            value = matched[0]
            if not value[0].isspace() and value[0] not in ",\ufeff#":
                self.tokens.append(value)
            position = matched.end()
        if len(self.tokens) > 512:
            raise GraphQLSubsetError("token limit")
        self.index = 0
        self.fields = fields
        self.variables = {}
        self.used = set()
        if self.peek() in ("mutation", "subscription"):
            raise UnauthorizedGraphQL("write or subscription operation")
        if self.peek() == "fragment":
            raise UnsupportedGraphQL("unsupported operation")
        if self.peek() == "query":
            self.take()
            if self.peek() not in ("(", "{"):
                self.name()  # Optional operation name.
            if self.peek() == "(":
                self.take()
                while self.peek() != ")":
                    self.take("$")
                    name = self.name()
                    self.take(":")
                    if self.peek() == "[":
                        raise UnsupportedGraphQL("list types unsupported")
                    kind = self.name()
                    if self.peek() == "!":
                        kind += self.take()
                    if name in self.variables:
                        raise GraphQLSubsetError("repeated variable definition")
                    if kind not in ("String", "String!", "Int", "Int!") or self.peek() == "=":
                        raise UnsupportedGraphQL("unsupported variable definition")
                    self.variables[name] = kind
                if not self.variables:
                    raise GraphQLSubsetError("empty variable definitions")
                self.take(")")
        if self.peek() == "@":
            raise UnsupportedGraphQL("directives unsupported")
        self.selection = self.select("Query", 0)
        if self.index != len(self.tokens) or self.used != set(self.variables):
            raise GraphQLSubsetError("trailing input or unused variable")

    def peek(self):
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def take(self, expected=None):
        value = self.peek()
        if value is None or expected is not None and value != expected:
            raise GraphQLSubsetError("incomplete or invalid query")
        self.index += 1
        return value

    def name(self):
        value = self.take()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", value):
            raise GraphQLSubsetError("invalid name")
        return value

    def value(self, expected):
        variable = None
        if self.peek() == "$":
            self.take()
            variable = self.name()
            declared = self.variables.get(variable)
            if declared not in (expected, expected + "!"):
                raise GraphQLSubsetError("undefined or incompatible variable")
            self.used.add(variable)
            value = self.fields.get(variable)
            if value is None and not expected.endswith("!") and not declared.endswith("!"):
                return None, variable
        else:
            if self.peek() == "[":
                raise UnsupportedGraphQL("list values unsupported")
            token = self.take()
            if token == "null" and not expected.endswith("!"):
                return None, None
            value = json.loads(token) if token.startswith('"') else token
        if expected.rstrip("!") == "Int":
            if variable is not None:
                if type(value) is not int:
                    raise GraphQLSubsetError("invalid integer variable")
            elif token.startswith('"') or not re.fullmatch(r"-?(?:0|[1-9][0-9]*)", value):
                raise GraphQLSubsetError("invalid integer argument")
            if len(str(value)) > 11:
                raise GraphQLSubsetError("integer argument limit")
            value = int(value)
            if not -(2**31) <= value < 2**31:
                raise GraphQLSubsetError("integer argument limit")
        elif not isinstance(value, str) or variable is None and not token.startswith('"'):
            raise GraphQLSubsetError("invalid string argument")
        return value, variable

    def select(self, kind, depth):
        if depth > 8:
            raise GraphQLSubsetError("selection depth limit")
        self.take("{")
        selections = {}
        while self.peek() != "}":
            if self.peek() in ("...", "@"):
                raise UnsupportedGraphQL("fragments and directives unsupported")
            name = self.name()
            if self.peek() == ":":
                raise UnsupportedGraphQL("aliases unsupported")
            if name not in GRAPHQL_FIELDS[kind] or name in selections:
                raise UnsupportedGraphQL("unsupported or repeated field")
            child, definitions = GRAPHQL_FIELDS[kind][name]
            args = {}
            if self.peek() == "(":
                self.take()
                while self.peek() != ")":
                    argument = self.name()
                    self.take(":")
                    if argument not in definitions or argument in args:
                        raise GraphQLSubsetError("unsupported or repeated argument")
                    args[argument] = self.value(definitions[argument])
                if not args:
                    raise GraphQLSubsetError("empty arguments")
                self.take(")")
            if {key for key, value in definitions.items() if value.endswith("!")} - args.keys():
                raise GraphQLSubsetError("required argument missing")
            if "first" in definitions and args.get("first", (None, None))[0] != 100:
                raise UnsupportedGraphQL("unsupported page size")
            if self.peek() == "@":
                raise UnsupportedGraphQL("directives unsupported")
            selections[name] = (args, self.select(child, depth + 1) if child else None)
        if not selections:
            raise GraphQLSubsetError("empty selection")
        self.take("}")
        return selections

    def at(self, *path):
        selection = self.selection
        for name in path:
            if selection is None or name not in selection:
                return None
            args, selection = selection[name]
        return args, selection

    def project(self, data, selection=None):
        selection = self.selection if selection is None else selection
        if isinstance(data, list):
            return [self.project(item, selection) for item in data]
        if data is None:
            return None
        return {name: self.project(data[name], children) if children else data[name]
                for name, (_, children) in selection.items()}


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
    if "--slurp" in opts and (pos[:1] != ["api"] or "--paginate" not in opts or "--jq" in opts):
        return {**result, "stderr": "--slurp requires --paginate and cannot be combined with --jq"}
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
            if name in fields:
                return {**result, "stderr": "duplicate API field"}
            if key == "--field":
                if value in ("true", "false", "null"):
                    value = json.loads(value)
                elif re.fullmatch(r"-?(?:0|[1-9][0-9]*)", value):
                    if len(value) > 11:
                        return {**result, "stderr": "integer field limit"}
                    value = int(value)
            fields[name] = value
    query = fields.get("query", "")
    parsed_query = None
    if pos[:2] == ["api", "graphql"]:
        repo = f"{fields.get('owner', '')}/{fields.get('name', '')}"
        if not isinstance(query, str):
            return result
        try:
            parsed_query = GraphQLSubset(query, fields)
        except UnauthorizedGraphQL:
            return {**result, "route": "unauthorized", "repo": repo}
        except UnsupportedGraphQL:
            return {**result, "repo": repo}
        except GraphQLSubsetError:
            if repo not in {route["match"].get("repo") for route in case["routes"] if route["match"]["pos"] == pos}:
                return {**result, "repo": repo}
            return {
                **result,
                "route": "malformed",
                "repo": repo,
                "stderr": "GraphQL: invalid modeled query",
            }
        repository = parsed_query.at("repository")[0]
        repo = "/".join(repository[key][0] for key in ("owner", "name"))
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
            - ({"--jq", "--slurp"} if pos[:1] == ["api"] else {"--jq"})
        ):
            continue
        paths = {
            "reviewThreads": ("repository", "pullRequest", "reviewThreads"),
            "isResolved": ("repository", "pullRequest", "reviewThreads", "nodes", "isResolved"),
            "pageInfo": ("repository", "pullRequest", "reviewThreads", "pageInfo"),
            "hasNextPage": ("repository", "pullRequest", "reviewThreads", "pageInfo", "hasNextPage"),
            "endCursor": ("repository", "pullRequest", "reviewThreads", "pageInfo", "endCursor"),
            "issues": ("repository", "issues"), "totalCount": ("repository", "issues", "totalCount"),
        }
        if any(parsed_query is None or parsed_query.at(*paths[word]) is None for word in match.get("query", [])):
            continue
        if "reviewThreads" in match.get("query", []):
            if parsed_query.at("repository", "pullRequest")[0]["number"][0] != 17:
                continue
        if "--paginate" in opts and pos[:2] == ["api", "graphql"]:
            connection = parsed_query.at("repository", "pullRequest", "reviewThreads")
            if (connection is None or connection[0].get("after") != (None, "endCursor")
                or parsed_query.variables.get("endCursor") != "String"
                or parsed_query.at(*paths["hasNextPage"]) is None or parsed_query.at(*paths["endCursor"]) is None):
                continue
        if parsed_query is not None:
            if [repository[key][0] for key in ("owner", "name")] != [match["fields"][key] for key in ("owner", "name")]:
                continue
            connection = parsed_query.at("repository", "pullRequest", "reviewThreads")
            if connection is not None and connection[0].get("after", (None, None))[0] is not None:
                continue  # Manual cursor requests are intentionally not modeled.
        if any((repository.get(key, (None, None))[0] if parsed_query is not None else fields.get(key)) != val
               for key, val in match.get("fields", {}).items()):
            continue
        if match.get("body") is not None and body != match["body"]:
            continue
        count = sum(row["route"] == route["id"] for row in history)
        responses = route["responses"]
        response = responses[min(count, len(responses) - 1)]
        response = dict(response)
        if parsed_query is not None and response.get("exit_code", 0) == 0:
            try:
                pages = [json.loads(page) for page in response["stdout"].splitlines()]
                pages = [{"data": parsed_query.project(page["data"])} for page in pages]
            except (KeyError, TypeError, ValueError):
                return result  # Selections not represented by this case remain unsupported.
            response["stdout"] = json.dumps(pages) if "--slurp" in opts else "\n".join(json.dumps(page) for page in pages)
        elif "--slurp" in opts and response.get("exit_code", 0) == 0:
            try:
                response["stdout"] = json.dumps([json.loads(page) for page in response["stdout"].splitlines()])
            except ValueError:
                return result
        if "--jq" in opts and response.get("exit_code", 0) == 0:
            # Real jq evaluates filtering only; never shells or forwards a request.
            filtered = subprocess.run(
                ["jq", "-c", "-r", opts["--jq"][-1]],
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
