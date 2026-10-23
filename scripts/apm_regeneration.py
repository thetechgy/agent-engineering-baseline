#!/usr/bin/env python3
"""Regenerate tracked APM outputs without installation-local state in the checkout."""

import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
from urllib.parse import urlsplit


OUTPUTS = {
    "apm.lock.yaml", "AGENTS.md", ".github/copilot-instructions.md",
    ".github/mcp.json", ".codex/config.toml",
}
GIT_PATH_ENV = {
    "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE", "GIT_PREFIX",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_QUARANTINE_PATH",
}


def git_environment(environment=None):
    return {key: value for key, value in (os.environ if environment is None else environment).items()
            if key not in GIT_PATH_ENV}


def generated(path):
    return path in OUTPUTS or path.startswith(".agents/skills/")


def run(arguments, root, **kwargs):
    if arguments[0] == "git":
        kwargs["env"] = git_environment(kwargs.get("env"))
    return subprocess.run(arguments, cwd=root, check=True, **kwargs)


def git(root, *arguments):
    return run(["git", *arguments], root, stdout=subprocess.PIPE).stdout


def safe_path(root, name):
    parts = PurePosixPath(name).parts
    if not parts or PurePosixPath(name).is_absolute() or any(p in {"..", ".git"} for p in parts):
        raise RuntimeError("Unsafe regeneration path")
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise RuntimeError("Linked regeneration paths are not supported")
    return path


def inventory(root):
    names = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").split(b"\0")
    files = {}
    for value in names:
        if not value:
            continue
        name = os.fsdecode(value)
        path = safe_path(root, name)
        if path.is_file():
            files[name] = (hashlib.sha256(path.read_bytes()).digest(), bool(path.stat().st_mode & 0o111))
        elif path.exists():
            raise RuntimeError("Non-file regeneration input")
    return files


def snapshot(source, destination):
    # No shared Git metadata, hooks, credentials, receipts, modules or untracked
    # user files. Overlay current tracked bytes, including staged additions.
    git(source, "clone", "--quiet", "--local", "--no-hardlinks", "--no-checkout", str(source), str(destination))
    origin = git(source, "remote", "get-url", "origin").decode().strip()
    url = urlsplit(origin)
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise RuntimeError("Regeneration requires a credential-free HTTPS origin")
    git(destination, "remote", "set-url", "origin", origin)
    entries = git(source, "ls-files", "--stage", "-z")
    for entry in entries.split(b"\0"):
        if not entry:
            continue
        header, value = entry.split(b"\t", 1)
        mode, _, stage = header.split()
        if mode not in {b"100644", b"100755"} or stage != b"0":
            raise RuntimeError("Regeneration requires regular tracked files without conflicts")
        name = os.fsdecode(value)
        original = safe_path(source, name)
        if name.startswith(".agents/skills/") or not original.exists():
            continue
        target = safe_path(destination, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, target)
    git(destination, "read-tree", "--empty")
    run(["git", "update-index", "-z", "--index-info"], destination, input=entries)


def native_checks(apm, root, refresh, environment=None):
    environment = dict(os.environ if environment is None else environment)

    def apm_run(*arguments):
        run([str(apm), *arguments], root, env=environment)

    if refresh:
        apm_run("update", "--yes")
        # The reviewed 0.34 updater skips executable assets without this pass.
        apm_run("install", "--trust-bin")
    lock = (root / "apm.lock.yaml").read_bytes()
    apm_run("install", "--frozen", "--trust-bin")
    apm_run("compile", "--target", "codex,copilot", "--validate")
    apm_run("compile", "--target", "codex,copilot")
    if not refresh:
        # Keep the native full audit in a PTY: replay has no --trust-bin flag.
        environment["APM_EXECUTABLE"] = str(apm)
        run(["script", "-q", "-e", "-c", 'exec "$APM_EXECUTABLE" audit --ci', "/dev/null"],
            root, env=environment)
        apm_run("pack", "--dry-run")
        apm_run("install", "--frozen", "--trust-bin")
        run(["script", "-q", "-e", "-c", 'exec "$APM_EXECUTABLE" audit --ci', "/dev/null"],
            root, env=environment)
        smoke = run(["bash", "./.agents/skills/msgraph/scripts/run.sh", "openapi-search",
                     "--query", "users", "--limit", "1"], root, env=environment, stdout=subprocess.PIPE).stdout
        if not smoke.strip():
            raise RuntimeError("Offline msgraph launcher/index smoke test failed")
    if (root / "apm.lock.yaml").read_bytes() != lock:
        raise RuntimeError("Frozen regeneration changed lockfile bytes")


def publish(source, scratch, before, after):
    changed = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    if inventory(source) != before:
        raise RuntimeError("Checkout changed during regeneration; nothing was published")
    for name in changed:
        target = safe_path(source, name)
        if target.exists() and not target.is_file():
            raise RuntimeError("APM output collides with a non-file caller path")
    backups = {name: (safe_path(source, name).read_bytes(), safe_path(source, name).stat().st_mode) if name in before else None for name in changed}
    try:
        for name in changed:
            target = safe_path(source, name)
            if name in after:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(safe_path(scratch, name), target)
            else:
                target.unlink()
    except BaseException:
        for name, content in backups.items():
            target = safe_path(source, name)
            if content is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(content[0])
                target.chmod(content[1])
        raise


def regenerate(source, apm, mode):
    source, apm = source.resolve(), apm.resolve()
    if not apm.is_file():
        raise RuntimeError("The absolute APM executable must exist")
    before = inventory(source)
    if mode == "refresh":
        clean = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", *sorted(OUTPUTS), ".agents/skills"],
                               cwd=source, env=git_environment(), check=False)
        if clean.returncode:
            raise RuntimeError("Refresh requires unchanged generated outputs")
    tracked = {os.fsdecode(name) for name in git(source, "ls-files", "-z").split(b"\0") if name}
    with tempfile.TemporaryDirectory(prefix="baseline-regeneration-") as directory:
        scratch = Path(directory) / "repository"
        snapshot(source, scratch)
        # Untracked caller files are never inputs or publication targets.
        expected = {name: digest for name, digest in before.items() if name in tracked}
        # APM 0.35 writes receipts under Path.home(), not just the deployment
        # root. Isolate child-process settings and cache as well as the checkout.
        home = Path(directory) / "home"
        home.mkdir()
        environment = {**git_environment(), "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"),
                       "XDG_CACHE_HOME": str(home / ".cache"), "TMPDIR": directory}
        environment.pop("APM_HOME", None)
        native_checks(apm, scratch, mode == "refresh", environment)
        if inventory(source) != before:
            raise RuntimeError("Checkout changed during regeneration; nothing was published")
        after = inventory(scratch)
        changed = sorted(name for name in expected.keys() | after.keys()
                         if expected.get(name) != after.get(name))
        unexpected = [name for name in changed if not generated(name)]
        if unexpected:
            raise RuntimeError("APM changed non-output paths: " + ", ".join(unexpected))
        if mode == "validate" and changed:
            raise RuntimeError("APM regeneration differs from checkout: " + ", ".join(changed))
        if mode == "refresh":
            collisions = set(changed) & (before.keys() - tracked)
            if collisions:
                raise RuntimeError("APM output collides with untracked caller files")
            # Preserve unrelated untracked files while publishing only checked outputs.
            publish(source, scratch, before, {**after, **{n: h for n, h in before.items() if n not in tracked}})
    print("APM isolated regeneration passed (" + mode + ").")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--apm", type=Path, required=True)
    parser.add_argument("--mode", choices=("validate", "refresh"), default="validate")
    arguments = parser.parse_args()
    if not arguments.apm.is_absolute():
        parser.error("--apm must be an absolute executable path")
    try:
        regenerate(arguments.repository, arguments.apm, arguments.mode)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, "APM isolated regeneration failed: " + str(error) + "\n")


if __name__ == "__main__":
    main()
