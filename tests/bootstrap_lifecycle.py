#!/usr/bin/env python3
"""Real, hash-pinned APM lifecycle fixtures; no production bootstrap dependency.

Exercise production bootstrap scripts against a reviewed release archive and
local Git repositories, then apply the exact documented native update command.
All agent settings and dependency state belong to disposable child homes.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from urllib.request import urlopen


REPOSITORY = Path(__file__).resolve().parents[1]
TOOLS = ["microsoft_docs_search", "microsoft_docs_fetch", "microsoft_code_sample_search"]
LEARN = {
    "name": "microsoft-learn", "registry": False, "transport": "http",
    "url": "https://learn.microsoft.com/api/mcp", "tools": TOOLS, "enabled_tools": TOOLS,
}
CHECKS = 0


def check(condition, message):
    global CHECKS
    if not condition:
        raise AssertionError(message)
    CHECKS += 1
    print(f"ok - {message}", flush=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def package(path, name, dependencies=None):
    data = {"name": name, "version": "1.0.0", "targets": ["codex", "copilot"]}
    if dependencies:
        data["dependencies"] = dependencies
    # JSON is a YAML subset accepted by the native APM manifest reader.
    write(path / "apm.yml", json.dumps(data))


def skill(path, name, marker):
    write(path / ".apm/skills" / name / "SKILL.md",
          f"---\nname: {name}\ndescription: Isolated bootstrap lifecycle fixture\n---\n# {marker}\n")


def locked_dependencies(path):
    """Inspect only native fixture lock rows; never resolve or rewrite locks."""
    text = path.read_text(encoding="utf-8")
    rows = {}
    for match in re.finditer(r"(?ms)^- repo_url: ([^\r\n]+)\r?\n(.*?)(?=^- repo_url:|^[a-z_]+:|\Z)", text):
        repo, body = match.groups()
        commit = re.search(r"(?m)^  resolved_commit: ([0-9a-f]{40})\r?$", body)
        if commit:
            rows[repo] = (commit.group(1), body)
    return rows


def prepare_bootstrap(root, member, checksums):
    """Reuse authentic reviewed archive bytes for every production-wrapper run."""
    version = (REPOSITORY / ".apm-version").read_text().strip()
    archive_name = member.split("/", 1)[0] + (".zip" if os.name == "nt" else ".tar.gz")
    archive = root / "mirror" / f"v{version}" / archive_name
    archive.parent.mkdir(parents=True)
    with urlopen(f"https://github.com/microsoft/apm/releases/download/v{version}/{archive_name}",
                 timeout=60) as response, archive.open("wb") as output:
        shutil.copyfileobj(response, output)
    check(digest(archive) == checksums[archive_name], "wrapper fixture archive matches reviewed hash")
    source = root / "source"
    (source / "scripts").mkdir(parents=True)
    for name in (".apm-version", ".apm-checksums", "scripts/bootstrap.sh", "scripts/Bootstrap-Baseline.ps1"):
        shutil.copy2(REPOSITORY / name, source / name)
    if os.name == "nt":
        # Match the existing Windows acquisition fixture boundary: only the
        # downloader is replaced. Hashing, extraction, promotion, dispatch and
        # real APM operations all run. Restore the test user's PATH as the
        # existing Windows bootstrap fixtures do; agent config stays isolated.
        write(source / "invoke.ps1", r'''param([string]$Scope)
$ErrorActionPreference = 'Stop'
function Invoke-WebRequest {
    param([string]$Uri, [string]$OutFile)
    if ($Uri -cne $env:BOOTSTRAP_FIXTURE_URL) { throw "Unexpected fixture download: $Uri" }
    Copy-Item -LiteralPath $env:BOOTSTRAP_FIXTURE_ARCHIVE -Destination $OutFile
}
$previous = [Environment]::GetEnvironmentVariable('Path', 'User')
try { & "$PSScriptRoot/scripts/Bootstrap-Baseline.ps1" -Scope $Scope -Confirm:$false }
finally { [Environment]::SetEnvironmentVariable('Path', $previous, 'User') }
''')
    return source, archive


class Scenario:
    def __init__(self, root, apm, global_scope, bootstrap=None):
        self.root, self.apm, self.global_scope = root, apm, global_scope
        self.bootstrap = bootstrap
        self.home, self.project = root / "home", root / "project"
        self.home.mkdir(parents=True)
        self.project.mkdir()
        # Do not inherit credentials, APM overrides, git hooks/config, or agent
        # profiles. Preserve Windows process essentials, not user settings.
        keys = {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "LANG",
                "OS", "PROCESSOR_ARCHITECTURE", "PROCESSOR_ARCHITEW6432"}
        self.env = {k: v for k, v in os.environ.items() if k.upper() in keys}
        self.env.update({
            "HOME": str(self.home), "USERPROFILE": str(self.home),
            "APPDATA": str(self.home / "AppData/Roaming"),
            "LOCALAPPDATA": str(self.home / "AppData/Local"),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_CACHE_HOME": str(self.home / ".cache"),
            "GH_CONFIG_DIR": str(self.home / ".config/gh"),
            "TMPDIR": str(root), "TMP": str(root), "TEMP": str(root),
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0", "VERSION": (REPOSITORY / ".apm-version").read_text().strip(),
            "GIT_AUTHOR_NAME": "Fixture", "GIT_COMMITTER_NAME": "Fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            "APM_NON_INTERACTIVE": "1",
        })
        self.deploy = self.home if global_scope else self.project
        self.metadata = self.home / ".apm" if global_scope else self.project
        self.scope = ["--global"] if global_scope else []
        self.repos = {}
        slots = []
        for name in ("baseline", "graph", "unrelated"):
            path = root / name
            path.mkdir()
            self.run(["git", "init", "--initial-branch=main"], path)
            self.repos[name] = path
            for suffix in (".git", ""):
                slots.append((f"url.{path.as_uri()}.insteadOf", self.url(name) + suffix))
        self.env["GIT_CONFIG_COUNT"] = str(len(slots))
        for index, (key, value) in enumerate(slots):
            self.env[f"GIT_CONFIG_KEY_{index}"] = key
            self.env[f"GIT_CONFIG_VALUE_{index}"] = value

    @staticmethod
    def url(name):
        # Generic Git transport avoids GitHub API discovery; the exact
        # process-local rewrite routes every fixture acquisition to local Git.
        return f"https://git.example.invalid/bootstrap-fixture/{name}"

    def run(self, args, cwd=None, success=True):
        process = subprocess.Popen([str(a) for a in args], cwd=cwd or self.project,
                                   env=self.env, text=True, encoding="utf-8", errors="replace",
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   start_new_session=os.name != "nt")
        try:
            output, _ = process.communicate(timeout=120)
        except subprocess.TimeoutExpired:
            # Native Git hydration can outlive its APM parent. Terminate only
            # this test-owned process tree before removing its temporary home.
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, timeout=30)
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            output, _ = process.communicate()
            raise AssertionError(f"Native command timed out after 120 seconds; owned process tree stopped.\n{output}") from None
        if (process.returncode == 0) != success:
            raise AssertionError(f"Command failed contract ({process.returncode}): {args}\n{output}")
        return output

    def native(self, *args, success=True):
        return self.run([self.apm, *args, *self.scope], success=success)

    def install(self, ref, update=False):
        if self.bootstrap and not update:
            source, archive = self.bootstrap
            self.env["BASELINE_PACKAGE_REF"] = ref
            self.env["APM_INSTALL_DIR"] = str(self.root / "cli/bin")
            if os.name == "nt":
                self.env["APM_RELEASE_BASE_URL"] = "https://mirror.example.invalid/apm"
                self.env["BOOTSTRAP_FIXTURE_ARCHIVE"] = str(archive)
                self.env["BOOTSTRAP_FIXTURE_URL"] = (
                    f"https://mirror.example.invalid/apm/v{self.env['VERSION']}/{archive.name}")
                import winreg
                # The parent restores the exact registry value even when the
                # child times out and cannot execute its PowerShell finally.
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                                    winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as key:
                    try:
                        previous_path = winreg.QueryValueEx(key, "Path")
                    except FileNotFoundError:
                        previous_path = None
                    try:
                        self.run([os.environ.get("CI_PWSH", "pwsh"), "-NoProfile", "-File",
                                  source / "invoke.ps1", "Global" if self.global_scope else "Repo"])
                    finally:
                        if previous_path is not None:
                            winreg.SetValueEx(key, "Path", 0, previous_path[1], previous_path[0])
                        else:
                            try:
                                winreg.DeleteValue(key, "Path")
                            except FileNotFoundError:
                                pass
            else:
                self.env["APM_RELEASE_BASE_URL"] = archive.parent.parent.as_uri()
                self.run(["bash", source / "scripts/bootstrap.sh",
                          "--global" if self.global_scope else "--repo"])
        else:
            self.native("install", *(["--update"] if update else []), "--target", "codex,copilot",
                        "--trust-bin", "--trust-transitive-mcp", ref)
            self.native("compile", *([] if self.global_scope else ["--target", "codex,copilot"]))

    def commit(self, name, marker):
        path = self.repos[name]
        skill(path, name, marker)
        if name == "graph":
            scripts = path / ".apm/skills/graph/scripts"
            write(scripts / "bin/probe.py", f"print({marker!r})\n")
            write(scripts / "run.py", "import pathlib,subprocess,sys\n"
                  "subprocess.run([sys.executable,str(pathlib.Path(__file__).parent/'bin/probe.py')],check=True)\n")
        self.run(["git", "add", "."], path)
        self.run(["git", "commit", "--message", marker], path)
        return self.run(["git", "rev-parse", "HEAD"], path).strip()

    def pins(self):
        return {name: row[0] for name, row in locked_dependencies(self.metadata / "apm.lock.yaml").items()}

    def content(self):
        # Compare installed bytes, not cache and local receipt timestamps.
        files = [self.metadata / "apm.yml", self.metadata / "apm.lock.yaml"]
        files += [p for p in (self.deploy / ".agents").rglob("*") if p.is_file()]
        files += self.config_paths()
        return {str(p): digest(p) for p in files}

    def config_paths(self):
        return [self.deploy / ".codex/config.toml", self.deploy /
                (".copilot/mcp-config.json" if self.global_scope else ".github/mcp.json")]

    def functionality(self, marker):
        codex, copilot = self.config_paths()
        native = json.loads(copilot.read_text(encoding="utf-8"))["mcpServers"]
        check(native["microsoft-learn"]["url"] == LEARN["url"], "Copilot Learn endpoint retained")
        check(native["microsoft-learn"]["type"] == "http", "Copilot Learn transport retained")
        check(native["microsoft-learn"]["tools"] == TOOLS and
              native["microsoft-learn"]["enabled_tools"] == TOOLS, "Copilot Learn allowlists retained")
        text = codex.read_text(encoding="utf-8")
        block = re.search(r"(?ms)^\[mcp_servers\.microsoft-learn\]\r?\n(.*?)(?=^\[|\Z)", text)
        check(block is not None and f'url = "{LEARN["url"]}"' in block[1], "Codex Learn endpoint retained")
        tools = re.search(r"(?m)^enabled_tools = (\[[^\r\n]*\])", block[1])
        check(tools is not None and json.loads(tools[1]) == TOOLS, "Codex Learn allowlist retained")
        output = self.run([sys.executable, self.deploy / ".agents/skills/graph/scripts/run.py"])
        check(output.strip() == marker, "bundled executable fixture remains functional")
        check(native["foreign"]["url"] == "https://example.invalid/foreign", "foreign MCP entry preserved")
        check('model = "fixture-model"' in text, "foreign Codex setting preserved")

    def exercise(self):
        label = "user" if self.global_scope else "repository"
        print(f"Native APM {label} scope", flush=True)
        package(self.repos["graph"], "graph")
        graph_a = self.commit("graph", "graph-a")
        package(self.repos["unrelated"], "unrelated")
        unrelated_a = self.commit("unrelated", "unrelated-a")
        package(self.repos["baseline"], "baseline", {
            "apm": [self.url("graph") + ".git#main"], "mcp": [LEARN],
        })
        # Deliberately older source-package lock: fresh consumers must not
        # mistake this for a reviewed transitive replay guarantee.
        write(self.repos["baseline"] / "apm.lock.yaml", json.dumps({
            "lockfile_version": "1", "dependencies": [{"repo_url": "bootstrap-fixture/graph",
            "host": "git.example.invalid", "resolved_ref": "main", "resolved_commit": graph_a}],
        }))
        baseline_a = self.commit("baseline", "baseline-a")
        graph_b = self.commit("graph", "graph-b")
        codex, copilot = self.config_paths()
        write(codex, 'model = "fixture-model"\n')
        write(copilot, json.dumps({"mcpServers": {"foreign": {
            "type": "http", "url": "https://example.invalid/foreign", "tools": ["read"],
        }}}))
        ref = self.url("baseline") + ".git#main"
        self.install(ref)
        check(self.pins()["bootstrap-fixture/baseline"] == baseline_a, "fresh baseline commit recorded")
        check(self.pins()["bootstrap-fixture/graph"] == graph_b, "fresh install resolves branches rather than source package lock")
        self.install(self.url("unrelated") + ".git#main")
        before = self.content()
        unrelated_skill = self.deploy / ".agents/skills/unrelated/SKILL.md"
        unrelated_state = (locked_dependencies(self.metadata / "apm.lock.yaml")["bootstrap-fixture/unrelated"],
                           digest(unrelated_skill))
        graph_c = self.commit("graph", "graph-c")
        self.commit("unrelated", "unrelated-b")
        baseline_b = self.commit("baseline", "baseline-b")
        self.install(ref)
        check(before == self.content(), "unchanged reinstall preserves manifest, lock, skills, executables and MCP bytes")
        self.functionality("graph-b")
        # A specific reviewed baseline ref is distinct from a subtree refresh.
        self.install(self.url("baseline") + ".git#" + baseline_b)
        pins = self.pins()
        check(pins["bootstrap-fixture/baseline"] == baseline_b, "changed immutable baseline ref adopted")
        check(pins["bootstrap-fixture/graph"] == graph_b, "baseline ref change retains matching child lock")
        check(pins["bootstrap-fixture/unrelated"] == unrelated_a, "baseline ref change retains unrelated lock")
        # This is exactly the documented explicit update command, including
        # trust flags needed for bin/ assets in a noninteractive invocation.
        self.install(self.url("baseline") + ".git#" + baseline_b, update=True)
        pins = self.pins()
        check(pins["bootstrap-fixture/baseline"] == baseline_b, "explicit subtree refresh retains selected baseline SHA")
        check(pins["bootstrap-fixture/graph"] == graph_c, "explicit refresh advances branch-tracking child")
        check(pins["bootstrap-fixture/unrelated"] == unrelated_a, "explicit refresh retains unrelated package commit")
        check(unrelated_state == (
            locked_dependencies(self.metadata / "apm.lock.yaml")["bootstrap-fixture/unrelated"],
            digest(unrelated_skill)), "explicit refresh preserves unrelated lock record and deployed bytes")
        self.functionality("graph-c")
        lock = self.metadata / "apm.lock.yaml"
        good = lock.read_bytes()
        for bad in (b"dependencies: [broken", b"dependencies: false\n",
                    b"<<<<<<< HEAD\na\n=======\nb\n>>>>>>> branch\n"):
            lock.write_bytes(bad)
            self.native("install", "--target", "codex,copilot", "--trust-bin", "--trust-transitive-mcp",
                        self.url("baseline") + ".git#" + baseline_b, success=False)
            check(lock.read_bytes() == bad, "invalid lock rejected without replacement")
            lock.write_bytes(good)
        # Missing metadata is ordinary resolution, not a frozen guarantee.
        manifest_before = (self.metadata / "apm.yml").read_bytes()
        lock.unlink()
        self.install(self.url("baseline") + ".git#" + baseline_b)
        check(self.pins()["bootstrap-fixture/graph"] == graph_c, "missing lock resolved natively")
        check("bootstrap-fixture/unrelated" not in self.pins(),
              "missing lock does not reconstruct unrelated lock entries")
        check(digest(unrelated_skill) == unrelated_state[1],
              "missing lock leaves unrelated deployed skill intact")
        check((self.metadata / "apm.yml").read_bytes() == manifest_before,
              "missing lock leaves dependency declarations byte-identical")


def reviewed_msgraph(root, apm):
    """Run the actual reviewed platform binary, never a branch-tip executable."""
    scenario = Scenario(root, apm, False)
    rows = locked_dependencies(REPOSITORY / "apm.lock.yaml")
    commit, body = rows["merill/msgraph"]
    scenario.native("install", "--target", "codex,copilot", "--trust-bin",
                    f"merill/msgraph/skills/msgraph#{commit}")
    platform = "windows_amd64.exe" if os.name == "nt" else (
        "linux_arm64" if os.uname().machine in {"aarch64", "arm64"} else "linux_amd64")
    member = f".agents/skills/msgraph/scripts/bin/msgraph_{platform}"
    expected = re.search(re.escape(member) + r": sha256:([0-9a-f]{64})", body)
    check(expected is not None and digest(scenario.project / member) == expected[1],
          "actual msgraph executable matches reviewed lock hash before execution")
    if os.name == "nt":
        args = [os.environ.get("CI_PWSH", "pwsh"), "-NoProfile", "-File", scenario.project / ".agents/skills/msgraph/scripts/run.ps1"]
    else:
        args = ["bash", scenario.project / ".agents/skills/msgraph/scripts/run.sh"]
    output = scenario.run([*args, "openapi-search", "--query", "users", "--limit", "1"])
    check(bool(output.strip()), "actual reviewed msgraph offline launcher succeeds")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apm", required=True, type=Path)
    args = parser.parse_args()
    apm = args.apm.resolve(strict=True)
    member = ("apm-windows-x86_64/apm.exe" if os.name == "nt" else
              "apm-linux-arm64/apm" if os.uname().machine in {"aarch64", "arm64"} else "apm-linux-x86_64/apm")
    expected = dict(line.split()[::-1] for line in (REPOSITORY / ".apm-checksums").read_text().splitlines())
    check(digest(apm) == expected[member], "APM executable matches reviewed hash before execution")
    with tempfile.TemporaryDirectory(prefix="apm-lifecycle-") as directory:
        root = Path(directory).resolve()
        bootstrap = prepare_bootstrap(root, member, expected)
        for scope in (False, True):
            Scenario(root / ("user" if scope else "repo"), apm, scope, bootstrap).exercise()
        reviewed_msgraph(root / "reviewed-msgraph", apm)
    print(f"Native APM lifecycle: {CHECKS} checks passed.")


if __name__ == "__main__":
    main()
