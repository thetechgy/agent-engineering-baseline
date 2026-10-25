#!/usr/bin/env python3
"""Bounded metadata discovery and a data-only, default-branch issue publisher.

No dependency installation, upstream code execution, or pin updates. Python 3.11+.
"""

import argparse
import ast
import base64
import hashlib
import html
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import tomllib
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = "thetechgy/agent-engineering-baseline"
CONFIG = ".github/dependency-freshness.json"
API = "https://api.github.com/"
SEMGREP_PYPI = "https://pypi.org/pypi/semgrep/json"
ISSUE_MARKER = "<!-- dependency-freshness:v1 -->"
ALERT_MARKER = "<!-- dependency-freshness-alert:"
BOT = "github-actions[bot]"
VERSION = r"[0-9]+\.[0-9]+\.[0-9]+"
SHA = r"[0-9a-f]{40}"
GHSA = r"GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}"
MAX_BYTES = 4 * 1024 * 1024
MAX_REPORT = 256 * 1024
MAX_BODY = 60 * 1024


class DiscoveryError(Exception):
    """Safe, host-authored diagnostic code; never a raw HTTP/error body."""


def require(condition, code="invalid_metadata"):
    if not condition:
        raise DiscoveryError(code)


def full(pattern, value):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def stable(value):
    require(full(VERSION, value), "unsupported_version")
    return tuple(map(int, value.split(".")))


def plain(value, limit=400):
    require(isinstance(value, str), "invalid_text")
    value = "".join(" " if unicodedata.category(c).startswith("C") else c for c in value)
    return " ".join(value.split())[:limit]


def escape(value):
    value = html.escape(plain(str(value), 8000), quote=True).replace("@", "&#64;")
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", value)


def read(root, path):
    relative = Path(path)
    require(not relative.is_absolute() and ".." not in relative.parts, "unsafe_source")
    target = root
    for part in relative.parts:
        target = target / part
        require(not target.is_symlink(), "linked_source")
    require(target.is_file() and target.stat().st_size <= MAX_BYTES, "missing_source")
    try:
        return target.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise DiscoveryError("unreadable_source") from error


def load_config(root):
    data = json.loads(read(root, CONFIG))
    require(data["schema_version"] == 1 and isinstance(data["dependencies"], list), "invalid_config")
    ids = [item["id"] for item in data["dependencies"]]
    require(len(ids) == len(set(ids)) and 1 <= len(ids) <= 30, "invalid_config")
    for item in data["dependencies"]:
        require(full(r"[a-z0-9-]+", item["id"]) and full(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", item["repo"]), "invalid_config")
        require(item.get("release_source", "github") == "github" or
                (item["id"] == "semgrep" and item["release_source"] == "pypi"), "invalid_release_source")
    return data["dependencies"]


def literal(source, symbol):
    nodes = [node for node in ast.parse(source).body if isinstance(node, ast.Assign)
             and any(isinstance(target, ast.Name) and target.id == symbol for target in node.targets)]
    require(len(nodes) == 1, "missing_or_duplicate_pin")
    try:
        return ast.literal_eval(nodes[0].value), nodes[0].lineno
    except (ValueError, TypeError) as error:
        raise DiscoveryError("nonliteral_pin") from error


def extract(root, item):
    values, sources = {}, []
    for selector in item["sources"]:
        source = read(root, selector["path"])
        if "symbol" in selector:
            value, line = literal(source, selector["symbol"])
            if selector["key"]:
                require(isinstance(value, dict) and selector["key"] in value, "missing_pin")
                value = value[selector["key"]]
            matches = [({selector["field"]: value}, line)]
        else:
            found = list(re.finditer(selector["pattern"], source, re.MULTILINE))
            require(len(found) == selector["count"], "missing_or_duplicate_pin")
            matches = [(match.groupdict(), source.count("\n", 0, match.start()) + 1) for match in found]
        for fields, line in matches:
            sources.append({"path": selector["path"], "line": line})
            for field, value in fields.items():
                require(field in {"version", "revision"} and isinstance(value, str), "invalid_pin")
                values.setdefault(field, set()).add(value)
    require(all(len(found) == 1 for found in values.values()), "contradictory_pins")
    pin = {key: next(iter(values[key])) if key in values else None for key in ("version", "revision")}
    if pin["version"] is not None:
        stable(pin["version"])
    if pin["revision"] is not None:
        require(full(SHA, pin["revision"]), "invalid_revision")
    require(any(pin.values()), "missing_pin")
    pin["value"] = pin["version"] or pin["revision"]
    return pin, sorted(sources, key=lambda s: (s["path"], s["line"]))


def apm_entries(root):
    """Read only the generated lock's top-level dependency records, not YAML generally."""
    lock = read(root, "apm.lock.yaml").split("\ndeployments:", 1)[0]
    entries = {}
    for block in re.split(r"(?m)^- repo_url: ", lock)[1:]:
        repo = block.splitlines()[0]
        fields = {}
        for key in ("name", "resolved_commit", "resolved_ref", "virtual_path"):
            matches = re.findall(rf"(?m)^  {key}: (\S+)$", block)
            require(len(matches) == 1, "invalid_apm_lock")
            fields[key] = matches[0]
        require(fields["name"] not in entries and full(SHA, fields["resolved_commit"]), "invalid_apm_lock")
        entries[fields["name"]] = {**fields, "repo": repo}
    return entries


def row(item, pin, sources, errors=None):
    return {"id": item["id"], "label": item["label"], "repo": item.get("repo"),
            "pin": pin, "sources": sources,
            "policy": {key: item.get(key) for key in ("owner", "hold", "group", "validation")},
            "upstream": {"status": "not_checked", "version": None, "revision": None},
            "freshness": "unverified" if errors else "not_checked",
            "security": {"status": "not_checked", "advisories": []}, "signals": [], "errors": errors or []}


def inventory(root):
    definitions, rows = load_config(root), []
    for item in definitions:
        try:
            pin, sources = extract(root, item)
            rows.append(row(item, pin, sources))
        except (DiscoveryError, OSError, SyntaxError, KeyError) as error:
            code = str(error) if isinstance(error, DiscoveryError) else "invalid_source"
            rows.append(row(item, {"version": None, "revision": None, "value": "Unknown"}, [], [code]))
    # Reconcile source refs with the lock and retain independent held skill ownership.
    try:
        locked = apm_entries(root)
        manifest = read(root, "apm.yml")
        refs = re.findall(r"(?m)^\s*- ([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/([^#\s]+)#([^\s]+)$", manifest)
        require(len(refs) == len(locked), "apm_inventory_mismatch")
        for repo, path, ref in refs:
            name = path.rsplit("/", 1)[-1]
            entry = locked.get(name, {})
            require(entry.get("repo") == repo and entry.get("virtual_path") == path
                    and entry.get("resolved_ref") == ref, "apm_inventory_mismatch")
            if full(SHA, ref):
                require(entry["resolved_commit"] == ref, "apm_inventory_mismatch")
                existing = next((r for r in rows if r["id"] == name), None)
                require(existing and existing["pin"]["revision"] == ref, "unregistered_apm_hold")
            else:
                item = dict(id=f"apm-{name}", label=f"APM skill: {name}", repo=repo,
                            owner="Weekly reviewed APM updater", hold=None, group="APM branch dependencies",
                            validation="Review the existing updater's resolved commits and generated diff; this report does not duplicate branch-head polling.")
                rows.append(row(item, {"version": None, "revision": entry["resolved_commit"], "value": entry["resolved_commit"]},
                                [{"path": "apm.yml", "line": 1}, {"path": "apm.lock.yaml", "line": 1}]))
    except (DiscoveryError, OSError, KeyError) as error:
        rows.append(row(dict(id="apm-inventory", label="APM dependency inventory", owner="Weekly reviewed APM updater"),
                        {"version": None, "revision": None, "value": "Unknown"}, [],
                        [str(error) if isinstance(error, DiscoveryError) else "invalid_apm_inventory"]))
    actions = {}
    for path in sorted((root / ".github/workflows").glob("*.y*ml")):
        source = read(root, path.relative_to(root).as_posix())
        for match in re.finditer(r"(?m)^\s*uses: ([A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+)@([^\s]+)", source):
            action, revision = match.groups()
            actions.setdefault(action, []).append((revision, path.relative_to(root).as_posix(), source.count("\n", 0, match.start()) + 1))
    require(bool(actions), "missing_actions")
    for action, matches in sorted(actions.items()):
        revisions = {m[0] for m in matches}
        valid = len(revisions) == 1 and all(full(SHA, value) for value in revisions)
        item = dict(id="action-" + action.lower().replace("/", "-"), label=f"Action: {action}",
                    owner="Dependabot routine GitHub Actions version updates", hold=None, group="GitHub Actions",
                    validation="Review the Dependabot PR, action permissions and exact-SHA CI; synchronize the external-action allowlist when required.")
        pin = next(iter(revisions)) if valid else "Unknown"
        rows.append(row(item, {"version": None, "revision": pin if valid else None, "value": pin},
                        [{"path": path, "line": line} for _, path, line in matches], [] if valid else ["contradictory_action_pins"]))
    for id, label, symbol, keys, note in (
        ("task-build", "Container and Debian snapshot", "GH_TASK_BUILD", None,
         "Intentional reproducibility constraints; review image, signed snapshot and direct package pins together. No OS package monitoring or image vulnerability scanning here."),
        ("runtime-selectors", "Evaluation runtime and fixture selectors", "POLICY", ("python", "model", "provider"),
         "Evaluation policy selectors and captured gh fixture contract, not installed CLI/Python patch versions or a model-release freshness assessment."),
    ):
        value, line = literal(read(root, ".github/scripts/skill_reports.py"), symbol)
        if keys:
            value = {key: value[key] for key in keys}
            fixture_path = ".github/scripts/gh_evaluations.py"
            fixture_source = read(root, fixture_path)
            matches = list(re.finditer(r'"cli_contract": "([^"]+)"', fixture_source))
            require(len(matches) == 1, "missing_or_duplicate_fixture_contract")
            stable(matches[0][1])
            value["gh_cli_fixture_contract"] = matches[0][1]
        item = dict(id=id, label=label, owner="Maintainer evaluation qualification", hold=note,
                    group="Evaluation reproducibility", validation=note)
        rows.append(row(item, {"version": None, "revision": None, "value": json.dumps(value, sort_keys=True)},
                        [{"path": ".github/scripts/skill_reports.py", "line": line}]))
        if keys:
            rows[-1]["sources"].append({"path": fixture_path, "line": fixture_source.count("\n", 0, matches[0].start()) + 1})
    # Configuration declares routine version coverage, not the independent security setting.
    dependabot = read(root, ".github/dependabot.yml")
    mechanisms = {"dependabot_routine_ecosystems": sorted(re.findall(r"package-ecosystem:\s*([a-z-]+)", dependabot)),
                  "dependabot_python_security_updates": "Observed in PR #77; not proof of routine Python version-update configuration or current settings.",
                  "upstream_frozen_locks": "Evaluator and SkillSpector own remaining transitive packages; no individual transitive polling.",
                  "hosted_tools": "Latest stable CI PowerShell acquisition and ambient hosted-runner tools are runtime/provider-owned; installed versions are not inferred here."}
    return definitions, sorted(rows, key=lambda r: r["id"]), mechanisms


class SameOrigin(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        origin = SEMGREP_PYPI if request is not None and request.full_url == SEMGREP_PYPI else API
        require(newurl == origin if origin == SEMGREP_PYPI else newurl.startswith(origin), "unsafe_redirect")
        return super().redirect_request(request, response, code, message, headers, newurl)


class GitHub:
    def __init__(self, token=None):
        self.token = token
        self.cache = {}
        self.failed = {}
        self.requests = 0
        self.started = time.monotonic()
        self.opener = build_opener(SameOrigin())

    def request(self, path, *, public=False, method="GET", data=None):
        require(isinstance(path, str) and not path.startswith("/") and ":" not in path, "unsafe_api_path")
        return self._json_request(API + path, public=public, method=method, data=data)

    def semgrep_metadata(self):
        """The sole package-registry lookup; never carries GitHub credentials."""
        return self._json_request(SEMGREP_PYPI, public=True)

    def _json_request(self, url, *, public=False, method="GET", data=None):
        require(url.startswith(API) or (url == SEMGREP_PYPI and public and method == "GET" and data is None),
                "unsafe_api_path")
        key = (url, public)
        if method == "GET" and key in self.cache:
            return self.cache[key]
        if method == "GET" and key in self.failed:
            raise DiscoveryError(self.failed[key])
        require(self.requests < 100 and time.monotonic() - self.started < 180, "request_budget_exceeded")
        headers = {"Accept": "application/json", "User-Agent": "baseline-dependency-freshness"}
        if url.startswith(API):
            headers.update({"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
        if self.token and not public:
            headers["Authorization"] = f"Bearer {self.token}"
        payload = None if data is None else json.dumps(data).encode()
        if payload is not None:
            headers["Content-Type"] = "application/json"
        self.requests += 1
        try:
            with self.opener.open(Request(url, headers=headers, data=payload, method=method), timeout=10) as response:
                raw = response.read(MAX_BYTES + 1)
                require(len(raw) <= MAX_BYTES, "oversized_response")
                result = json.loads(raw)
        except HTTPError as error:
            error.close()
            if method == "GET":
                self.failed[key] = f"http_{error.code}"
            raise DiscoveryError(f"http_{error.code}") from error
        except (TimeoutError, socket.timeout) as error:
            if method == "GET":
                self.failed[key] = "timeout"
            raise DiscoveryError("timeout") from error
        except (URLError, OSError, UnicodeError, ValueError) as error:
            if method == "GET":
                self.failed[key] = "invalid_or_unavailable_response"
            raise DiscoveryError("invalid_or_unavailable_response") from error
        except DiscoveryError as error:
            if method == "GET":
                self.failed[key] = str(error)
            raise
        if method == "GET":
            self.cache[key] = result
        return result

    def pages(self, path, *, public=False):
        result = []
        for page in range(1, 4):
            separator = "&" if "?" in path else "?"
            values = self.request(f"{path}{separator}per_page=100&page={page}", public=public)
            require(isinstance(values, list) and len(values) <= 100, "invalid_collection")
            result.extend(values)
            if len(values) < 100:
                return result
        raise DiscoveryError("pagination_limit")


def query(**values):
    return urlencode(values)


def released(api, item, current):
    data = api.request(f"repos/{item['repo']}/releases/latest")
    require(isinstance(data, dict) and data.get("draft") is False and data.get("prerelease") is False, "invalid_stable_release")
    prefix = item.get("tag_prefix", "v")
    tag = data.get("tag_name")
    require(full(re.escape(prefix) + VERSION, tag), "unsupported_release_tag")
    version = tag[len(prefix):]
    stable(version)
    if current["revision"] and current["version"]:
        tag_commit = api.request(f"repos/{item['repo']}/commits/{quote(prefix + current['version'], safe='')}")
        require(tag_commit.get("sha") == current["revision"], "pin_tag_mismatch")
    body = data.get("body") or ""
    if item.get("release_source") == "pypi":
        github_version = version
        version = semgrep_version(api.semgrep_metadata())
        # Notes describe the GitHub release, which can lag the PyPI package.
        require(isinstance(body, str), "invalid_release_notes")
        body = ("\n".join(f"GitHub {tag}: {line}" for line in body.splitlines())
                if stable(current["version"]) < stable(github_version) <= stable(version) else "")
    return {"status": "verified", "version": version, "revision": None}, body


def semgrep_version(data):
    """Validate Semgrep's published stable inventory without fetching artifacts."""
    require(isinstance(data, dict) and isinstance(data.get("info"), dict)
            and data["info"].get("name") == "semgrep", "invalid_pypi_identity")
    version = data["info"].get("version")
    stable(version)
    releases = data.get("releases")
    require(isinstance(releases, dict) and 0 < len(releases) <= 2000, "invalid_pypi_releases")
    available = []
    for candidate, files in releases.items():
        require(isinstance(files, list) and len(files) <= 100, "invalid_pypi_files")
        if not full(VERSION, candidate):
            continue  # Prereleases and other unsupported version forms are not stable candidates.
        for artifact in files:
            require(isinstance(artifact, dict) and type(artifact.get("yanked")) is bool
                    and isinstance(artifact.get("digests"), dict)
                    and full(r"[0-9a-f]{64}", artifact["digests"].get("sha256")), "invalid_pypi_artifact")
            filename = artifact.get("filename")
            require(isinstance(filename, str) and
                    ((filename.startswith(f"semgrep-{candidate}-") and filename.endswith(".whl"))
                     or filename == f"semgrep-{candidate}.tar.gz"), "invalid_pypi_artifact")
        if any(not artifact["yanked"] for artifact in files):
            available.append(candidate)
    require(available and version == max(available, key=stable), "inconsistent_pypi_latest")
    require(isinstance(data.get("urls"), list) and data["urls"] == releases[version], "inconsistent_pypi_files")
    return version


def skill_tree(api, item, ref):
    values = api.request(f"repos/{item['repo']}/contents/{item['path']}?{query(ref=ref)}")
    require(isinstance(values, list) and len(values) <= 100, "invalid_skill_tree")
    entries = []
    for value in values:
        require(value.get("type") in {"file", "dir"} and full(SHA, value.get("sha")), "invalid_skill_tree")
        entries.append((value["path"], value["type"], value["sha"]))
    require(entries, "missing_skill_tree")
    return hashlib.sha256(json.dumps(sorted(entries)).encode()).hexdigest()


def signals(body):
    require(isinstance(body, str) and len(body) <= MAX_BYTES, "invalid_release_notes")
    found = []
    patterns = (("security", r"\bsecurity\b|GHSA-|CVE-"),
                ("breaking", r"\bbreaking\b|\bdeprecated\b|\bremoved interfaces?\b"),
                ("evaluation", r"\bscor(?:e|es|ing)\b|\bgrader|\bHarbor\b|\bevidence\b|\bschema\b|\bruntime"))
    for kind, pattern in patterns:
        lines = body.splitlines()
        for index, line in enumerate(lines):
            if re.search(pattern, line, re.IGNORECASE):
                text = line
                if line.lstrip().startswith("#") or len(plain(line)) < 90:
                    following = next((v for v in lines[index + 1:] if v.strip() and not v.lstrip().startswith("#")), "")
                    text += " " + following
                found.append({"kind": kind, "text": plain(text, 240)})
                break
    return found


def package_matches(left, right):
    def normalized(package):
        name = package.get("name", "")
        if package.get("ecosystem") == "pip":
            name = re.sub(r"[-_.]+", "-", name).lower()
        return package.get("ecosystem"), name
    return normalized(left) == normalized(right)


def advisory_record(data, source, identity):
    require(isinstance(data, dict) and full(GHSA, data.get("ghsa_id")), "invalid_advisory")
    require(data.get("severity") in {"low", "medium", "high", "critical", "unknown", None}, "invalid_advisory")
    vulnerabilities = data.get("vulnerabilities")
    require(isinstance(vulnerabilities, list) and len(vulnerabilities) <= 30, "invalid_advisory")
    packages = []
    for vulnerability in vulnerabilities:
        package = vulnerability.get("package")
        require(isinstance(package, dict), "invalid_advisory")
        if identity and not package_matches(package, identity):
            continue
        packages.append({"ecosystem": plain(package.get("ecosystem") or "", 60),
                         "name": plain(package.get("name") or "", 120),
                         "affected": plain(vulnerability.get("vulnerable_version_range") or "Unknown", 200),
                         "fixed": plain(vulnerability.get("first_patched_version") or vulnerability.get("patched_versions") or "Unknown", 200)})
    if not packages:
        return None
    return {"id": data["ghsa_id"], "source": source, "severity": data.get("severity") or "unknown",
            "summary": plain(data.get("summary") or "No summary", 240), "packages": packages,
            "applicability": "unknown", "evidence": ("Publisher metadata" if source == "publisher" else "GitHub-reviewed metadata")
            + "; version applicability not established."}


def advisories(api, item, pin):
    records, errors = [], []
    try:
        for value in api.pages(f"repos/{item['repo']}/security-advisories?state=published", public=True):
            if value.get("withdrawn_at") is None:
                record = advisory_record(value, "publisher", item.get("package"))
                if record:
                    records.append(record)
    except (DiscoveryError, KeyError, TypeError, AttributeError) as error:
        errors.append("publisher_advisories:" + (str(error) if isinstance(error, DiscoveryError) else "invalid_metadata"))
    package = item.get("package")
    if package and pin["version"]:
        try:
            all_values = api.pages("advisories?" + query(ecosystem=package["ecosystem"], affects=package["name"]))
            reviewed = []
            for value in all_values:
                if value.get("withdrawn_at") is None:
                    record = advisory_record(value, "github_reviewed", package)
                    if record:
                        reviewed.append(record)
                        records.append(record)
            matches = api.pages("advisories?" + query(ecosystem=package["ecosystem"], affects=package["name"] + "@" + pin["version"])) if all_values else []
            matched = {v["ghsa_id"] for v in matches if v.get("withdrawn_at") is None}
            for record in reviewed:
                if record["id"] in matched:
                    record["applicability"] = "potentially_affected" if item.get("modified") else "confirmed_version_match"
                    record["evidence"] = ("GitHub package@version match for " + package["name"] + "@" + pin["version"]
                                          + "; platform, configuration and exploitability require review."
                                          + (" Locally modified evaluator; build applicability remains unqualified." if item.get("modified") else ""))
                else:
                    record["applicability"] = "not_matched"
                    record["evidence"] = "Not returned by the complete GitHub affected-version query; not a comprehensive safety assessment."
            # A positive result missing from the package-wide response cannot be silently dropped.
            require(matched <= {r["id"] for r in records if r["source"] == "github_reviewed"}, "inconsistent_advisory_queries")
        except (DiscoveryError, KeyError, TypeError, AttributeError) as error:
            errors.append("reviewed_advisories:" + (str(error) if isinstance(error, DiscoveryError) else "invalid_metadata"))
    return {"status": "partial" if errors else "checked", "advisories": sorted(records, key=lambda r: (r["id"], r["source"]))}, errors


def freshness(pin, upstream):
    if upstream["status"] != "verified":
        return "unverified" if upstream["status"] == "unverified" else "not_checked"
    if "content_changed" in upstream:
        version_behind = False
        if pin["version"] is not None and upstream["version"] is not None:
            require(stable(pin["version"]) <= stable(upstream["version"]), "pin_ahead_of_latest_release")
            version_behind = stable(pin["version"]) < stable(upstream["version"])
        return "update_available" if upstream["content_changed"] or version_behind else "current"
    require(pin["version"] is not None and upstream["version"] is not None, "missing_version")
    installed, latest = stable(pin["version"]), stable(upstream["version"])
    require(installed <= latest, "pin_ahead_of_latest_release")
    return "update_available" if installed < latest else "current"


def collect(root, api, revision):
    definitions, rows, mechanisms = inventory(root)
    by_id = {item["id"]: item for item in definitions}
    lock = None
    for result in rows:
        item = by_id.get(result["id"])
        if item is None or result["errors"]:
            continue
        try:
            if item.get("lock_package"):
                evaluator = next(r for r in rows if r["id"] == "skillevaluator")
                require(full(SHA, evaluator["pin"]["revision"]), "missing_evaluator_pin")
                if lock is None:
                    data = api.request(f"repos/NVIDIA/SkillEvaluator/contents/uv.lock?ref={evaluator['pin']['revision']}")
                    require(data.get("encoding") == "base64" and isinstance(data.get("content"), str), "invalid_frozen_lock")
                    lock = tomllib.loads(base64.b64decode(data["content"], validate=False).decode())
                versions = [p["version"] for p in lock["package"] if p.get("name") == item["lock_package"]]
                require(versions == [result["pin"]["version"]], "frozen_lock_mismatch")
            if item.get("kind") == "skill":
                upstream = {"status": "verified", "version": None, "revision": None}
                ref = item.get("ref")
                if not ref:
                    upstream, _ = released(api, item, result["pin"])
                    ref = item["tag_prefix"] + upstream["version"]
                commit = api.request(f"repos/{item['repo']}/commits/{quote(ref, safe='')}")
                require(full(SHA, commit.get("sha")), "invalid_skill_revision")
                before = skill_tree(api, item, result["pin"]["revision"])
                after = skill_tree(api, item, commit["sha"])
                upstream.update(revision=commit["sha"], content_changed=before != after, content_digest=after, ref=ref)
                result["upstream"] = upstream
            else:
                result["upstream"], body = released(api, item, result["pin"])
                result["signals"] = signals(body)
            result["freshness"] = freshness(result["pin"], result["upstream"])
        except (DiscoveryError, ValueError, KeyError, TypeError, AttributeError) as error:
            result["upstream"] = {"status": "unverified", "version": None, "revision": None}
            result["freshness"] = "unverified"
            result["errors"].append("release:" + (str(error) if isinstance(error, DiscoveryError) else "invalid_metadata"))
        if item.get("kind") != "skill":
            result["security"], errors = advisories(api, item, result["pin"])
            result["errors"].extend(errors)
    return {"schema_version": 1, "repository": REPOSITORY, "source_revision": revision,
            "complete": not any(r["errors"] for r in rows), "mechanisms": mechanisms, "dependencies": rows}


def release_url(item, upstream):
    if item.get("release_source") == "pypi":
        version = upstream.get("version")
        return "https://pypi.org/project/semgrep/" + (version + "/" if version else "")
    ref = upstream.get("ref") or (item.get("tag_prefix", "v") + upstream["version"] if upstream.get("version") else None)
    if not ref:
        return f"https://github.com/{item['repo']}/releases"
    suffix = "tree/" if item.get("kind") == "skill" else "releases/tag/"
    return f"https://github.com/{item['repo']}/{suffix}{quote(ref, safe='')}"


def risk_events(report):
    """Stable evidence keys, independent of timestamps, patch churn and lookup gaps."""
    events = {}
    for result in report["dependencies"]:
        pin = result["pin"]["version"] or result["pin"]["revision"]
        if pin is None:
            continue
        for advisory in result["security"]["advisories"]:
            if advisory["applicability"] in {"confirmed_version_match", "potentially_affected"}:
                value = {k: advisory[k] for k in ("id", "severity", "packages", "applicability")}
                identity = [result["id"], pin, value]
                key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
                events[key] = f"{result['label']}: {advisory['id']} ({advisory['severity']}; {advisory['applicability']})"
        confirmed = {a["id"] for a in result["security"]["advisories"]
                     if a["applicability"] in {"confirmed_version_match", "potentially_affected"}}
        for signal in result["signals"] if result["freshness"] == "update_available" else []:
            if signal["kind"] not in {"security", "breaking"}:
                continue
            # Prefer advisory IDs over release versions so the same fix does not alert every patch.
            ids = sorted(set(re.findall(GHSA + r"|CVE-[0-9]{4}-[0-9]+", signal["text"], re.IGNORECASE)))
            if signal["kind"] == "security" and ids and set(ids) <= confirmed:
                continue  # Existing advisory evidence owns this security notification.
            identity = [result["id"], pin, signal["kind"], ids or signal["text"]]
            key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
            events[key] = f"{result['label']}: upstream {signal['kind']} signal; review applicability"
        if result["freshness"] == "update_available" and result["pin"]["version"] and result["upstream"].get("version"):
            before, after = stable(pin), stable(result["upstream"]["version"])
            line = (after[0], after[1] if after[0] == 0 else None)
            if before[0] != after[0] or (after[0] == 0 and before[1] != after[1]):
                key = hashlib.sha256(json.dumps([result["id"], pin, "compatibility-line", line]).encode()).hexdigest()
                events[key] = f"{result['label']}: new compatibility line; qualification required, breaking behavior not established"
            if not result["policy"]["hold"]:
                key = hashlib.sha256(json.dumps([result["id"], pin, "outdated-direct-pin"]).encode()).hexdigest()
                events[key] = f"{result['label']}: direct pin is behind a stable release; review required"
    return events


def render(report, definitions):
    by_id = {item["id"]: item for item in definitions}
    lines = ["# Dependency freshness", "", ISSUE_MARKER, "",
             "This snapshot changes only with meaningful findings. Check [workflow health](https://github.com/" + REPOSITORY + "/actions/workflows/dependency-freshness.yml) for collection failures and recent observations.", "",
             "**Discovery: " + ("complete for the configured checks." if report["complete"] else "INCOMPLETE. Unknown fields and failed sources remain visible; successful findings are retained.") + "**", "",
             "Freshness, management policy, and advisory evidence are independent. A newer stable release is not an upgrade approval. No matching advisory is not proof of safety.", ""]
    priorities = []
    for result in report["dependencies"]:
        matches = [a for a in result["security"]["advisories"] if a["applicability"] in {"confirmed_version_match", "potentially_affected"}]
        security_signal = result["freshness"] == "update_available" and any(s["kind"] == "security" for s in result["signals"])
        if matches or security_signal:
            evidence = ", ".join(sorted({a["id"] for a in matches})) or "upstream release-note security signal; affected-version applicability unverified"
            priorities.append("- " + escape(result["label"] + ": " + evidence) + ". Prioritize a separate focused security review; retain qualification requirements.")
    if priorities:
        lines += ["## Priority review", "", *priorities, ""]
    lines += ["| Dependency | Pinned | Latest stable / content | Freshness | Management policy |",
              "| --- | --- | --- | --- | --- |"]
    for result in report["dependencies"]:
        upstream = result["upstream"]
        latest = upstream.get("version") or ("Changed" if upstream.get("content_changed") else "Unchanged" if "content_changed" in upstream else "Unknown / not checked")
        management = result["policy"]["owner"] or "Unknown"
        if result["policy"]["hold"]:
            management += "; intentional hold"
        lines.append("| " + " | ".join(escape(v) for v in (result["label"], result["pin"]["value"], latest,
                                                              result["freshness"].replace("_", " "), management)) + " |")
    lines += ["", "## Evidence and next actions", ""]
    for result in report["dependencies"]:
        lines += ["### " + escape(result["label"]), ""]
        if result["policy"]["group"]:
            lines += ["Group: " + escape(result["policy"]["group"]) + ".", ""]
        if result["policy"]["hold"]:
            lines += ["Hold: " + escape(result["policy"]["hold"]), ""]
        source_links = [f"[{escape(path)}](https://github.com/{REPOSITORY}/blob/main/{quote(path, safe='/')})"
                        for path in sorted({s["path"] for s in result["sources"]})]
        if source_links:
            lines += ["Pin sources: " + ", ".join(source_links) + ".", ""]
        item = by_id.get(result["id"])
        if item:
            pypi = item.get("release_source") == "pypi"
            reference = ("[PyPI version availability](" if pypi else "[Upstream release/content](") + release_url(item, result["upstream"]) + ")."
            if pypi:
                reference += f" [GitHub release notes and tags](https://github.com/{item['repo']}/releases) are a separate source and may lag PyPI."
            elif result["upstream"]["status"] == "verified":
                reference += f" [Full comparison](https://github.com/{item['repo']}/compare/"
                reference += quote(result["pin"]["revision"] or item.get("tag_prefix", "v") + result["pin"]["version"], safe='')
                reference += "..." + quote(result["upstream"].get("ref") or item.get("tag_prefix", "v") + result["upstream"]["version"], safe='') + ")."
            lines += [reference, ""]
        if "content_digest" in result["upstream"]:
            lines += ["Upstream skill-directory fingerprint: " + result["upstream"]["content_digest"] + ". "
                      + ("Content differs from the held revision." if result["upstream"]["content_changed"] else "Content matches the held revision."), ""]
        for signal in result["signals"]:
            lines += ["- Upstream " + escape(signal["kind"]) + " signal (untrusted excerpt; applicability unverified): " + escape(signal["text"])]
        if result["signals"]:
            lines.append("")
        security = result["security"]
        if security["status"] != "not_checked":
            lines += ["Advisory lookup: " + escape(security["status"]) + ". Checked public publisher/GitHub-reviewed sources only; no transitive, OS or comprehensive vulnerability coverage.", ""]
            if not security["advisories"]:
                lines += ["No advisory records identified in successful queries. Failed queries remain unknown.", ""]
        for advisory in security["advisories"]:
            advisory_url = (f"https://github.com/advisories/{advisory['id']}" if advisory["source"] == "github_reviewed"
                            else f"https://github.com/{result['repo']}/security/advisories/{advisory['id']}")
            lines += [f"- [{advisory['id']}]({advisory_url}): " + escape(advisory["summary"]) + "; source=" + escape(advisory["source"])
                      + "; severity=" + escape(advisory["severity"]) + "; " + escape(advisory["applicability"]) + ". " + escape(advisory["evidence"])]
            for package in advisory["packages"]:
                lines += ["  - " + escape(package["ecosystem"] + ":" + package["name"]) + "; affected=" + escape(package["affected"]) + "; fixed=" + escape(package["fixed"])]
        if security["advisories"]:
            lines.append("")
        if result["errors"]:
            lines += ["Unknown/failed sources: " + ", ".join(escape(code) for code in result["errors"]) + ".", ""]
        action = ("Restore failed lookups; conclusions for those sources remain unknown. " if result["errors"] else "")
        if any(a["applicability"] == "confirmed_version_match" for a in security["advisories"]):
            action += "Prioritize a separate focused security remediation review. "
        if result["freshness"] == "current" and not result["errors"] and not result["signals"]:
            action += "No freshness-driven upgrade identified. "
        lines += ["Next action: " + escape(action + (result["policy"]["validation"] or "Investigate missing inventory coverage.")), ""]
    lines += ["## Existing mechanisms", ""]
    lines += ["- " + escape(key + ": " + (", ".join(value) if isinstance(value, list) else value)) for key, value in sorted(report["mechanisms"].items())]
    lines += ["", "Release-note excerpts cover selected signals, not every intervening change. Review the complete upstream comparison. Historical evaluation identities and pins remain unchanged.", ""]
    body = "\n".join(lines)
    require(len(body.encode()) <= MAX_BODY, "issue_body_limit")
    return body


def validate_report(report, root, revision):
    """Publisher validates data independently, using its trusted current inventory."""
    require(isinstance(report, dict) and set(report) == {"schema_version", "repository", "source_revision", "complete", "mechanisms", "dependencies"}, "invalid_report")
    require(report["schema_version"] == 1 and report["repository"] == REPOSITORY and report["source_revision"] == revision
            and full(SHA, revision) and type(report["complete"]) is bool, "report_revision_mismatch")
    definitions, expected, mechanisms = inventory(root)
    by_id = {item["id"]: item for item in definitions}
    rows = report["dependencies"]
    require(isinstance(rows, list) and len(rows) == len(expected) and report["mechanisms"] == mechanisms, "inventory_mismatch")
    for result, original in zip(rows, expected):
        require(isinstance(result, dict) and set(result) == set(original), "invalid_row")
        for key in ("id", "label", "repo", "pin", "sources", "policy"):
            require(result[key] == original[key], "inventory_mismatch")
        upstream = result["upstream"]
        require(isinstance(upstream, dict) and set(upstream) <= {"status", "version", "revision", "content_changed", "content_digest", "ref"}, "invalid_upstream")
        require({"status", "version", "revision"} <= set(upstream) and upstream["status"] in {"verified", "unverified", "not_checked"}, "invalid_upstream")
        require((upstream["revision"] is None or ("content_changed" in upstream and full(SHA, upstream["revision"])))
                and (upstream["version"] is None or full(VERSION, upstream["version"])), "invalid_upstream")
        if "content_changed" in upstream:
            require(type(upstream["content_changed"]) is bool and full(r"[0-9a-f]{64}", upstream.get("content_digest"))
                    and full(r"[A-Za-z0-9_.-]+", upstream.get("ref")), "invalid_upstream")
        require(isinstance(result["errors"], list) and len(result["errors"]) <= 8
                and all(full(r"[a-z0-9_:]+", error) for error in result["errors"]), "invalid_errors")
        require(set(original["errors"]) <= set(result["errors"]), "missing_inventory_error")
        require(result["freshness"] == ("unverified" if original["errors"] else freshness(result["pin"], upstream)), "invalid_freshness")
        require(not (upstream["status"] == "unverified" and not result["errors"]), "hidden_failure")
        item = by_id.get(result["id"])
        if item and not original["errors"]:
            require(upstream["status"] != "not_checked", "missing_release_assessment")
        security = result["security"]
        require(isinstance(security, dict) and set(security) == {"status", "advisories"}
                and security["status"] in {"checked", "partial", "not_checked"} and isinstance(security["advisories"], list)
                and len(security["advisories"]) <= 100, "invalid_security")
        require(not (security["status"] == "partial" and not result["errors"]), "hidden_failure")
        if item and not original["errors"] and item.get("kind") != "skill":
            require(security["status"] != "not_checked", "missing_advisory_assessment")
        for advisory in security["advisories"]:
            require(isinstance(advisory, dict) and set(advisory) == {"id", "source", "severity", "summary", "packages", "applicability", "evidence"}
                    and full(GHSA, advisory["id"]) and advisory["source"] in {"publisher", "github_reviewed"}
                    and advisory["severity"] in {"low", "medium", "high", "critical", "unknown"}
                    and advisory["applicability"] in {"unknown", "not_matched", "confirmed_version_match", "potentially_affected"}, "invalid_advisory")
            require(all(isinstance(advisory[k], str) and len(advisory[k]) <= 500 for k in ("summary", "evidence")), "invalid_advisory")
            require(isinstance(advisory["packages"], list) and 1 <= len(advisory["packages"]) <= 30, "invalid_advisory")
            for package in advisory["packages"]:
                require(isinstance(package, dict) and set(package) == {"name", "ecosystem", "affected", "fixed"}
                        and all(isinstance(v, str) and len(v) <= 200 for v in package.values()), "invalid_advisory")
            if advisory["applicability"] in {"confirmed_version_match", "potentially_affected", "not_matched"}:
                require(advisory["source"] == "github_reviewed" and item and item.get("package")
                        and result["pin"]["version"] is not None
                        and all(package_matches(p, item["package"]) for p in advisory["packages"]), "invalid_advisory_match")
        require(isinstance(result["signals"], list) and len(result["signals"]) <= 3, "invalid_signals")
        for signal in result["signals"]:
            require(isinstance(signal, dict) and set(signal) == {"kind", "text"}
                    and signal["kind"] in {"security", "breaking", "evaluation"}
                    and isinstance(signal["text"], str) and len(signal["text"]) <= 240, "invalid_signals")
    require(report["complete"] == (not any(r["errors"] for r in rows)), "hidden_failure")
    render(report, definitions)
    return definitions


def publish(report, root, api, revision):
    definitions = validate_report(report, root, revision)
    metadata = api.request(f"repos/{REPOSITORY}")
    require(metadata.get("default_branch") == "main" and os.environ.get("GITHUB_REF") == "refs/heads/main"
            and os.environ.get("GITHUB_EVENT_NAME") in {"schedule", "workflow_dispatch"}, "publication_not_authorized")
    head = api.request(f"repos/{REPOSITORY}/branches/main")
    require(head.get("commit", {}).get("sha") == revision, "superseded_snapshot")
    base = f"repos/{REPOSITORY}/issues"
    candidates = [issue for issue in api.pages(base + "?state=all&creator=" + BOT)
                  if "pull_request" not in issue and issue.get("user", {}).get("login") == BOT
                  and ISSUE_MARKER in (issue.get("body") or "")]
    require(len(candidates) <= 1, "ambiguous_tracking_issue")
    body = render(report, definitions)
    if not candidates:
        # No automatic retry. A later run lists issues again before considering creation.
        issue = api.request(base, method="POST", data={"title": "Dependency freshness and upgrade review", "body": body})
    else:
        issue = candidates[0]
    require(type(issue.get("number")) is int and issue.get("state") == "open", "closed_or_invalid_tracking_issue")
    number = issue["number"]
    events = risk_events(report)
    seen = set()
    for comment in api.pages(f"{base}/{number}/comments"):
        if comment.get("user", {}).get("login") == BOT:
            seen.update(re.findall(re.escape(ALERT_MARKER) + r"([0-9a-f]{64}) -->", comment.get("body") or ""))
    novel = {key: value for key, value in events.items() if key not in seen}
    if novel:
        notice = "Material dependency findings changed. Review the tracking issue's evidence and qualification requirements.\n\n"
        notice += "\n".join("- " + escape(value) + "\n" + ALERT_MARKER + key + " -->" for key, value in sorted(novel.items()))
        require(len(notice.encode()) <= MAX_BODY, "notification_limit")
        # Comment first. If its response is lost, the next run reconciles markers;
        # if the body update fails, an existing notification is not emitted again.
        api.request(f"{base}/{number}/comments", method="POST", data={"body": notice})
    changed = issue.get("body") != body
    if changed:
        api.request(f"{base}/{number}", method="PATCH", data={"body": body})
    return {"issue": number, "body_changed": changed, "new_notifications": len(novel)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inventory", "check", "publish"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    revision = os.environ.get("GITHUB_SHA") or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    require(full(SHA, revision), "invalid_revision")
    if args.command == "publish":
        require(args.report is not None and args.report.is_file() and not args.report.is_symlink()
                and args.report.stat().st_size <= MAX_REPORT, "invalid_report_file")
        require(os.environ.get("GH_TOKEN"), "missing_publisher_token")
        result = publish(json.loads(args.report.read_text()), ROOT, GitHub(os.environ["GH_TOKEN"]), revision)
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as stream:
                stream.write(f"[Dependency tracking issue](https://github.com/{REPOSITORY}/issues/{result['issue']})\n")
        print(json.dumps(result, sort_keys=True))
        return 0
    if args.command == "inventory":
        _, rows, mechanisms = inventory(ROOT)
        print(json.dumps({"dependencies": rows, "mechanisms": mechanisms}, indent=2, sort_keys=True))
        return int(any(r["errors"] for r in rows))
    require(args.output is not None and not args.output.exists(), "output_must_be_new")
    require(not args.output.resolve().is_relative_to(ROOT), "output_must_be_outside_checkout")
    api = GitHub(os.environ.get("GH_TOKEN"))
    report = collect(ROOT, api, revision)
    definitions = validate_report(report, ROOT, revision)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    require(len(encoded.encode()) <= MAX_REPORT, "report_limit")
    body = render(report, definitions)
    args.output.mkdir(parents=True)
    (args.output / "report.json").write_text(encoded, encoding="utf-8")
    (args.output / "report.md").write_text(body, encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write(body)
    print(json.dumps({"complete": report["complete"], "requests": api.requests,
                      "elapsed_seconds": round(time.monotonic() - api.started, 3), "report_bytes": len(encoded.encode())}, sort_keys=True))
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (DiscoveryError, OSError, ValueError, KeyError, TypeError) as error:
        print("Dependency freshness failed: " + (str(error) if isinstance(error, DiscoveryError) else "invalid_or_unavailable_data"), file=sys.stderr)
        sys.exit(2)
