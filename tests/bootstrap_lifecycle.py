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
    # Native APM hashes Markdown with LF. Use identical fixture bytes on both hosts.
    path.write_text(value, encoding="utf-8", newline="\n")


def package(path, name, dependencies=None, includes=None):
    data = {"name": name, "version": "1.0.0", "targets": ["codex", "copilot"]}
    if dependencies:
        data["dependencies"] = dependencies
    if includes is not None:
        data["includes"] = includes
    # JSON is a YAML subset accepted by the native APM manifest reader.
    write(path / "apm.yml", json.dumps(data))


def skill(path, name, marker, *, directory=".apm/skills"):
    write(path / directory / name / "SKILL.md",
          f"---\nname: {name}\ndescription: Isolated bootstrap lifecycle fixture\n---\n# {marker}\n")


def instructions(path, marker):
    write(path / ".apm/instructions/personal.instructions.md",
          f"---\ndescription: Shared lifecycle fixture\n---\n# Shared guidance: {marker}\n")
    write(path / "baseline-review.instructions.md",
          '---\ndescription: Repository-only fixture\napplyTo: "**"\n---\n# REPOSITORY_ONLY_REVIEW\n')


def locked_dependencies(path):
    """Inspect only native fixture lock rows; never resolve or rewrite locks."""
    text = path.read_text(encoding="utf-8")
    rows = {}
    for match in re.finditer(r"(?ms)^- repo_url: ([^\r\n]+)\r?\n(.*?)(?=^- repo_url:|^[a-z_]+:|\Z)", text):
        repo, body = match.groups()
        commit = re.search(r"(?m)^  resolved_commit: ([0-9a-f]{40})\r?$", body)
        virtual = re.search(r"(?m)^  virtual_path: ([^\r\n]+)$", body)
        identity = f"{repo}/{virtual[1]}" if virtual else repo
        if commit:
            if identity in rows:
                raise AssertionError(f"Duplicate native lock row for {identity}")
            rows[identity] = (commit[1], body)
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
    def __init__(self, root, apm, global_scope, bootstrap=None, *, extra_repos=()):
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
        for name in ("baseline", "graph", "unrelated", *extra_repos):
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

    def run(self, args, cwd=None, success=True, timeout=120):
        process = subprocess.Popen([str(a) for a in args], cwd=cwd or self.project,
                                   env=self.env, text=True, encoding="utf-8", errors="replace",
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   start_new_session=os.name != "nt")
        try:
            output, _ = process.communicate(timeout=timeout)
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
            raise AssertionError(f"Native command timed out after {timeout} seconds; owned process tree stopped.\n{output}") from None
        if success is None:
            return process.returncode, output
        if (process.returncode == 0) != success:
            raise AssertionError(f"Command failed contract ({process.returncode}): {args}\n{output}")
        return output

    def native(self, *args, success=True):
        return self.run([self.apm, *args, *self.scope], success=success)

    def install(self, ref, update=False, timeout=120, *, success=True):
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
                        return self.run([os.environ.get("CI_PWSH", "pwsh"), "-NoProfile", "-File",
                                         source / "invoke.ps1", "Global" if self.global_scope else "Repo"],
                                        success=success, timeout=timeout)
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
                return self.run(["bash", source / "scripts/bootstrap.sh",
                                 "--global" if self.global_scope else "--repo"],
                                success=success, timeout=timeout)
        else:
            self.native("install", *(["--update"] if update else []), "--target", "codex,copilot",
                        "--trust-bin", "--trust-transitive-mcp", ref)
            self.native("compile", *([] if self.global_scope else ["--target", "codex,copilot"]))

    def commit(self, name, marker):
        path = self.repos[name]
        skill(path, name, marker)
        if name == "baseline":
            instructions(path, marker)
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
        files += self.config_paths() + self.instruction_paths()
        return {str(p): digest(p) for p in files}

    def config_paths(self):
        return [self.deploy / ".codex/config.toml", self.deploy /
                (".copilot/mcp-config.json" if self.global_scope else ".mcp.json")]

    def instruction_paths(self):
        # These are APM outputs. Local Copilot CLI 1.0.103 discovery selected
        # the modular user instruction; it did not select the user AGENTS.md.
        names = ([".codex/AGENTS.md", ".copilot/AGENTS.md",
                  ".copilot/instructions/personal.instructions.md"] if self.global_scope else
                 ["AGENTS.md", ".github/instructions/personal.instructions.md"])
        return [self.deploy / name for name in names]

    def instruction_delivery(self, marker):
        for path in self.instruction_paths():
            text = path.read_text(encoding="utf-8")
            check(f"# Shared guidance: {marker}" in text,
                  f"{path.relative_to(self.deploy)} delivers the selected shared instruction")
            check("REPOSITORY_ONLY_REVIEW" not in text,
                  f"{path.relative_to(self.deploy)} excludes repository-only review guidance")

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
        }, includes=[".apm/instructions/personal.instructions.md", ".apm/skills/baseline/"])
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
        self.instruction_delivery("baseline-a")
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
        check(before == self.content(), "unchanged reinstall preserves manifest, lock, skills, instructions, executables and MCP bytes")
        self.instruction_delivery("baseline-a")
        self.functionality("graph-b")
        # A specific reviewed baseline ref is distinct from a subtree refresh.
        self.install(self.url("baseline") + ".git#" + baseline_b)
        self.instruction_delivery("baseline-b")
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
        self.instruction_delivery("baseline-b")
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

        # The upstream branch already points at C. A baseline pinned to A
        # still installs A; selecting a new baseline pinned to B adopts B.
        for revision, marker in ((graph_a, "graph-a"), (graph_b, "graph-b")):
            package(self.repos["baseline"], "baseline", {
                "apm": [self.url("graph") + ".git#" + revision], "mcp": [LEARN],
            })
            pinned = self.commit("baseline", "pin-" + marker)
            self.install(self.url("baseline") + ".git#" + pinned)
            check(self.pins()["bootstrap-fixture/graph"] == revision,
                  f"{label}: deliberate {marker} pin installed while upstream remained at C")
            script = self.deploy / ".agents/skills/graph/scripts/bin/probe.py"
            reviewed = self.run(["git", "rev-parse", revision + ":.apm/skills/graph/scripts/bin/probe.py"],
                                self.repos["graph"])
            check(self.run(["git", "hash-object", "--no-filters", script]) == reviewed
                  and self.run([sys.executable, script]).strip() == marker,
                  f"{label}: deployed executable matches selected fixture pin")


def instruction_regeneration(root, apm):
    """Exercise the production helper with native APM and no external dependencies."""
    scenario = Scenario(root, apm, False)
    source = scenario.project
    scenario.run(["git", "init", "--quiet"], source)
    scenario.run(["git", "remote", "add", "origin", "https://git.example.invalid/regeneration.git"], source)
    package(source, "instructions", includes=[".apm/instructions/personal.instructions.md"])
    instructions(source, "original")
    scenario.native("install", "--target", "codex,copilot", "--trust-bin")
    scenario.native("compile", "--target", "codex,copilot")
    scenario.run(["git", "add", "."], source)
    scenario.run(["git", "commit", "--message", "Original native instruction outputs"], source)
    instructions(source, "updated")
    authored = (source / ".apm/instructions/personal.instructions.md").read_bytes()
    helper = [sys.executable, REPOSITORY / "scripts/apm_regeneration.py",
              "--repository", source, "--apm", apm, "--mode", "refresh"]
    scenario.run(helper)
    for path in scenario.instruction_paths():
        check("# Shared guidance: updated" in path.read_text(encoding="utf-8"),
              f"native regeneration publishes the updated {path.relative_to(source)}")
    check((source / ".apm/instructions/personal.instructions.md").read_bytes() == authored,
          "native regeneration preserves the authored instruction")
    check("REPOSITORY_ONLY_REVIEW" in (source / "AGENTS.md").read_text(encoding="utf-8"),
          "local compilation retains repository-only review guidance")
    # The helper deliberately requires clean generated files for another refresh.
    scenario.run(["git", "add", "."], source)
    scenario.run(["git", "commit", "--message", "Regenerated instruction outputs"], source)
    paths = [source / "apm.lock.yaml", *scenario.instruction_paths()]
    before = [path.read_bytes() for path in paths]
    scenario.run(helper)
    check([path.read_bytes() for path in paths] == before,
          "repeated native instruction regeneration retains lock and output bytes")


MSGRAPH = "merill/msgraph/skills/msgraph"
MSGRAPH_BIN = ".agents/skills/msgraph/scripts/bin/"
GIT_COMMIT = "github/awesome-copilot/skills/git-commit"
FORMER_BRANCH_IMPORTS = (
    "addyosmani/agent-skills/skills/code-simplification",
    "github/awesome-copilot/skills/dependabot",
    "github/awesome-copilot/skills/github-actions-hardening",
    "github/awesome-copilot/skills/microsoft-code-reference",
)
# Authentic older msgraph snapshot. All six binaries differ from the reviewed set.
LEGACY_MSGRAPH = "eb081bf8628d0c9669dc20e681d5eb9623dea9b0"


def file_hashes(body):
    deployed = re.search(r"(?ms)^  deployed_file_hashes:\n(.*?)(?=^  \S|\Z)", body)
    if deployed is None:
        return {}
    return dict(re.findall(r"(?m)^    ([^:\r\n]+): sha256:([0-9a-f]{64})$", deployed[1]))


def verify_imports(scenario, expected, stage):
    rows = locked_dependencies(scenario.metadata / "apm.lock.yaml")
    for identity, (commit, reviewed) in expected.items():
        actual, body = rows[identity]
        check(actual == commit and f"  resolved_ref: {commit}" in body.splitlines(),
              f"{stage}: {identity} resolved and locked to {actual}")
        directory = scenario.deploy / ".agents/skills" / identity.rsplit("/", 1)[1]
        installed = {path.relative_to(scenario.deploy).as_posix(): digest(path)
                     for path in directory.rglob("*") if path.is_file()}
        check(installed == reviewed == file_hashes(body),
              f"{stage}: {identity} matches {len(reviewed)} reviewed lock hashes and deployed files")


def seed_legacy_imports(scenario, mirrors, old_ref, expected, scope):
    package(scenario.repos["unrelated"], "unrelated")
    scenario.commit("unrelated", "unrelated package")
    scenario.install(scenario.url("unrelated") + ".git#main")
    # Route only the legacy install to controlled branch heads. Destination
    # declarations, files and lock rows are created by native APM.
    slots = int(scenario.env["GIT_CONFIG_COUNT"])
    index = slots
    for repo, (mirror, _) in mirrors.items():
        for suffix in (".git", ""):
            scenario.env[f"GIT_CONFIG_KEY_{index}"] = f"url.{mirror.as_uri()}.insteadOf"
            scenario.env[f"GIT_CONFIG_VALUE_{index}"] = f"https://github.com/{repo}{suffix}"
            index += 1
    scenario.env["GIT_CONFIG_COUNT"] = str(index)
    scenario.install(old_ref, timeout=600)
    scenario.env["GIT_CONFIG_COUNT"] = str(slots)
    rows = locked_dependencies(scenario.metadata / "apm.lock.yaml")
    for identity in (*FORMER_BRANCH_IMPORTS, MSGRAPH):
        repo, _, name = identity.partition("/skills/")
        legacy_commit, body = rows[identity]
        check(legacy_commit == mirrors[repo][1] and "  resolved_ref: main" in body.splitlines()
              and legacy_commit != expected[identity][0],
              f"{scope} legacy #main: {identity} installed from a different commit")
        paths = ([path for path in expected[identity][1] if path.startswith(MSGRAPH_BIN)]
                 if identity == MSGRAPH else [f".agents/skills/{name}/SKILL.md"])
        legacy_hashes = file_hashes(body)
        check(all(digest(scenario.deploy / path) == legacy_hashes[path] != expected[identity][1][path]
                  for path in paths), f"{scope} legacy #main: {identity} deployed different bytes")


def unrelated_state(scenario):
    row = locked_dependencies(scenario.metadata / "apm.lock.yaml")["bootstrap-fixture/unrelated"]
    return row, digest(scenario.deploy / ".agents/skills/unrelated/SKILL.md")


def destination_hashes(scenario):
    paths = [scenario.deploy / "AGENTS.md"]
    directories = [scenario.deploy / name for name in (".agents", ".codex", ".copilot", ".github")]
    directories.append(scenario.metadata / "apm_modules")
    for directory in directories:
        paths.extend(directory.rglob("*"))
    return {path.relative_to(scenario.deploy).as_posix(): digest(path) for path in paths if path.is_file()}


def lock_handling(scenario, case):
    scope = "user" if scenario.global_scope else "repository"
    stage = f"{scope} {case}"
    graph = scenario.repos["graph"]
    skill_path = ".apm/skills/graph"
    identity = f"bootstrap-fixture/graph/{skill_path}"
    dependency = {"git": scenario.url("graph") + ".git", "path": skill_path}
    reviewed_commit = scenario.commit("graph", "reviewed-a")
    reviewed = {f".agents/skills/graph/{path.relative_to(graph / skill_path).as_posix()}": digest(path)
                for path in (graph / skill_path).rglob("*") if path.is_file()}
    other_commit = scenario.commit("graph", "other-b")
    check(reviewed_commit != other_commit and digest(graph / skill_path / "scripts/bin/probe.py") !=
          reviewed[".agents/skills/graph/scripts/bin/probe.py"],
          f"{stage}: A and B are distinct commits with distinct executables")

    def publish(name, revision):
        package(scenario.repos[name], name, {"apm": [{**dependency, "ref": revision}]})
        commit = scenario.commit(name, name)
        return scenario.url(name) + ".git#" + commit

    baseline = publish("baseline", reviewed_commit)
    package(scenario.repos["unrelated"], "unrelated")
    scenario.commit("unrelated", "unrelated")
    scenario.install(scenario.url("unrelated") + ".git#main")
    scenario.install(baseline)
    verify_imports(scenario, {identity: (reviewed_commit, reviewed)}, f"{stage} seed")
    independent = unrelated_state(scenario)
    lock = scenario.metadata / "apm.lock.yaml"
    manifest = scenario.metadata / "apm.yml"
    if case == "contradictory lock":
        # Keep the requested ref and all other fields from the native row.
        # A different resolved_ref would only replay the migration case.
        original = lock.read_bytes()
        field = f"  resolved_commit: {reviewed_commit}".encode()
        check(original.count(field) == 1, f"{stage}: exactly one native commit field to change")
        lock.write_bytes(original.replace(field, f"  resolved_commit: {other_commit}".encode()))
        commit, body = locked_dependencies(lock)[identity]
        declared = json.loads((scenario.repos["baseline"] / "apm.yml").read_text(encoding="utf-8"))
        check(declared["dependencies"]["apm"] == [{**dependency, "ref": reviewed_commit}]
              and f"  resolved_ref: {reviewed_commit}" in body.splitlines() and commit == other_commit,
              f"{stage}: manifest requests {reviewed_commit}, destination records {commit} for the same ref and skill")
        incoming = baseline
    else:
        incoming = publish("conflict", other_commit)
        declared = json.loads((scenario.repos["conflict"] / "apm.yml").read_text(encoding="utf-8"))
        check(declared["dependencies"]["apm"] == [{**dependency, "ref": other_commit}],
              f"{stage}: incoming package requests {other_commit} for the installed skill at {reviewed_commit}")

    old_lock, old_manifest, old_files = lock.read_bytes(), manifest.read_bytes(), destination_hashes(scenario)
    status, output = scenario.install(incoming, success=None)
    new_lock = lock.read_bytes() if lock.exists() else None
    new_files = destination_hashes(scenario)
    rows = locked_dependencies(lock) if lock.exists() else {}
    selected = rows.get(identity, (None, ""))[0]
    print(f"{stage}: exit={status}, resolved={selected}, "
          f"lock unchanged={new_lock == old_lock}, destination files unchanged={new_files == old_files}", flush=True)
    check((rows.get("bootstrap-fixture/unrelated"), new_files.get(".agents/skills/unrelated/SKILL.md"))
          == independent, f"{stage}: unrelated lock record and deployed bytes preserved")
    if case == "contradictory lock" and status == 0:
        check(selected == reviewed_commit, f"{stage}: successful reinstall selected the reviewed pin")
        verify_imports(scenario, {identity: (reviewed_commit, reviewed)}, f"{stage} reconciled")
        return

    diagnostic = " ".join(output.lower().split())
    if case == "shared dependency conflict":
        visible = ("incompatible immutable requirements" in diagnostic and identity in diagnostic
                   and reviewed_commit in diagnostic and other_commit in diagnostic)
    else:
        visible = (re.search(r"contradict|mismatch|incompatible|conflict", diagnostic)
                   and (identity in diagnostic or "lock" in diagnostic))
    if status == 0 or not visible:
        raise AssertionError(f"{stage}: expected a visible refusal (exit={status})\n{output}")
    print(f"{stage}: bootstrap reported {case}", flush=True)
    check(new_lock == old_lock, f"{stage}: refusal preserves the destination lock")
    check(manifest.exists() and manifest.read_bytes() == old_manifest,
          f"{stage}: refusal preserves the destination manifest")
    changed = sorted(path for path in old_files.keys() | new_files.keys()
                     if old_files.get(path) != new_files.get(path))
    if changed:
        raise AssertionError(f"{stage}: files changed after refusal: {', '.join(changed)}")
    print(f"{stage}: refusal preserved modules and deployed files", flush=True)


def reviewed_imports(root, apm, bootstrap):
    rows = locked_dependencies(REPOSITORY / "apm.lock.yaml")
    imports = {identity: (commit, file_hashes(body)) for identity, (commit, body) in rows.items()}
    manifest = (REPOSITORY / "apm.yml").read_text(encoding="utf-8")
    declarations = re.findall(r"(?m)^    - ([^#\s]+)#(\S+)$", manifest)
    check(dict(declarations) == {identity: commit for identity, (commit, _) in imports.items()}
          and len(declarations) == len(imports) and all(hashes for _, hashes in imports.values()),
          "every imported skill declares the exact commit and has hashes in the reviewed lock")
    check(all(imports[identity][0] != imports[GIT_COMMIT][0]
              for identity in FORMER_BRANCH_IMPORTS if identity.startswith("github/awesome-copilot/")),
          "git-commit shares an upstream repository with three skills at a different revision")
    platforms = ("darwin_amd64", "darwin_arm64", "linux_amd64", "linux_arm64",
                 "windows_amd64.exe", "windows_arm64.exe")
    check({path for path in imports[MSGRAPH][1] if path.startswith(MSGRAPH_BIN)} ==
          {MSGRAPH_BIN + "msgraph_" + platform for platform in platforms},
          "reviewed lock contains all six msgraph platform executable hashes")

    producer = Scenario(root / "producer", apm, False)
    msgraph = root / "legacy-msgraph.git"
    producer.run(["git", "init", "--bare", "--initial-branch=main", msgraph])
    producer.run(["git", "fetch", "--no-tags", "https://github.com/merill/msgraph.git",
                  LEGACY_MSGRAPH + ":refs/heads/main"], msgraph, timeout=600)
    mirrors = {"merill/msgraph": (msgraph, LEGACY_MSGRAPH)}
    # Use small Git repositories for moved branches so these controls remain
    # deterministic even if today's upstream skill still matches the pin.
    for repo in ("addyosmani/agent-skills", "github/awesome-copilot"):
        mirror = root / repo.rsplit("/", 1)[1]
        producer.run(["git", "init", "--initial-branch=main", mirror])
        for identity in FORMER_BRANCH_IMPORTS:
            if identity.startswith(repo + "/"):
                skill(mirror, identity.rsplit("/", 1)[1], "Legacy branch content", directory="skills")
        producer.run(["git", "add", "skills"], mirror)
        producer.run(["git", "commit", "--message", "Moved upstream branches"], mirror)
        mirrors[repo] = (mirror, producer.run(["git", "rev-parse", "HEAD"], mirror).strip())
    baseline = producer.repos["baseline"]
    package(baseline, "baseline", {"apm": [identity + "#main" for identity in (*FORMER_BRANCH_IMPORTS, MSGRAPH)]})
    old = producer.commit("baseline", "Legacy branch declarations")
    # Publish the candidate's actual manifest, lock, and authored package
    # contents to local Git. Other dependencies follow their normal APM paths.
    shutil.copytree(REPOSITORY / ".apm", baseline / ".apm", dirs_exist_ok=True)
    for name in ("apm.yml", "apm.lock.yaml", "LICENSE"):
        shutil.copy2(REPOSITORY / name, baseline / name)
    producer.run(["git", "add", "."], baseline)
    producer.run(["git", "commit", "--message", "Reviewed skill declarations"], baseline)
    selected = producer.run(["git", "rev-parse", "HEAD"], baseline).strip()
    for user in (False, True):
        scope = "user" if user else "repository"
        for migration in (True, False):
            stage = "migration" if migration else "fresh"
            # Release the real Git caches between independent installations.
            with tempfile.TemporaryDirectory(dir=root, prefix=stage[0]) as directory:
                scenario = Scenario(Path(directory), apm, user, bootstrap)
                scenario.run(["git", "pull", "--ff-only", baseline, "main"], scenario.repos["baseline"])
                ref = scenario.url("baseline") + ".git#"
                if migration:
                    seed_legacy_imports(scenario, mirrors, ref + old, imports, scope)
                    record = unrelated_state(scenario)
                # A cold full manifest hydrates every upstream skill, including cli/cli.
                scenario.install(ref + selected, timeout=600)
                verify_imports(scenario, imports, f"{scope} {stage}")
                if migration:
                    check(unrelated_state(scenario) == record,
                          f"{scope} migration preserves unrelated lock record and deployed bytes")
                else:
                    scenario.install(ref + selected, timeout=600)
                    verify_imports(scenario, imports, f"{scope} ordinary reinstall")
                    scripts = scenario.deploy / ".agents/skills/msgraph/scripts"
                    args = ([os.environ.get("CI_PWSH", "pwsh"), "-NoProfile", "-File", scripts / "run.ps1"]
                            if os.name == "nt" else ["bash", scripts / "run.sh"])
                    output = scenario.run([*args, "openapi-search", "--query", "users", "--limit", "1"])
                    check(bool(output.strip()), f"{scope}: actual reviewed msgraph offline launcher succeeds")


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
        failures = []
        for user in (False, True):
            for case in ("contradictory lock", "shared dependency conflict"):
                with tempfile.TemporaryDirectory(dir=root, prefix=case[0]) as destination:
                    scenario = Scenario(Path(destination), apm, user, bootstrap, extra_repos=("conflict",))
                    try:
                        lock_handling(scenario, case)
                    except AssertionError as error:
                        failures.append(str(error))
        for scope in (False, True):
            Scenario(root / ("user" if scope else "repo"), apm, scope, bootstrap).exercise()
        instruction_regeneration(root / "instructions", apm)
        reviewed_imports(root / "imports", apm, bootstrap)
        if failures:
            raise AssertionError("\n".join(failures))
    print(f"Native APM lifecycle: {CHECKS} checks passed.")


if __name__ == "__main__":
    main()
