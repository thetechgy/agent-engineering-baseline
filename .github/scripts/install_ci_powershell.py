"""Acquire the latest stable PowerShell for disposable GitHub-hosted CI jobs."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
from urllib.request import Request, urlopen
import zipfile


RELEASE_API = "https://api.github.com/repos/PowerShell/PowerShell/releases/latest"
RELEASE_BASE = "https://github.com/PowerShell/PowerShell/releases/download/"


def download(url, destination):
    request = Request(url, headers={"User-Agent": "baseline-powershell-ci"})
    with urlopen(request, timeout=60) as response:
        if not response.url.startswith("https://"):
            raise ValueError("PowerShell downloads must use HTTPS")
        with destination.open("xb") as output:
            shutil.copyfileobj(response, output)


def select_assets(release, system):
    tag = release.get("tag_name", "")
    if (release.get("draft") is not False or release.get("prerelease") is not False
            or re.fullmatch(r"v[1-9][0-9]*\.[0-9]+\.[0-9]+", tag) is None):
        raise ValueError("Latest PowerShell release must be a published stable version")
    version = tag[1:]
    if system == "Windows":
        archive = f"PowerShell-{version}-win-x64.zip"
    elif system == "Linux":
        archive = f"powershell-{version}-linux-x64.tar.gz"
    else:
        raise ValueError(f"Unsupported CI operating system: {system}")
    urls = {}
    for name in (archive, "hashes.sha256"):
        matches = [asset for asset in release.get("assets", []) if asset.get("name") == name]
        expected = f"{RELEASE_BASE}{tag}/{name}"
        if len(matches) != 1 or matches[0].get("browser_download_url") != expected:
            raise ValueError(f"Missing, duplicate, or unexpected release asset: {name}")
        urls[name] = expected
    return version, archive, urls


def verify_archive(archive, checksums):
    matches = []
    content = checksums.read_bytes()
    # PowerShell releases include Windows-generated UTF-16 checksum files.
    encoding = "utf-16" if content.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    for line in content.decode(encoding).splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]{64})[ \t]+\*?(\S+)", line)
        if match and match[2] == archive.name:
            matches.append(match[1].lower())
    if len(matches) != 1:
        raise ValueError("Expected exactly one SHA256 entry for the PowerShell archive")
    with archive.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    if digest != matches[0]:
        raise ValueError("PowerShell archive SHA256 mismatch")


def extract_archive(archive, destination, system):
    if system == "Windows":
        with zipfile.ZipFile(archive) as bundle:
            seen = set()
            for entry in bundle.infolist():
                name = entry.filename.replace("\\", "/")
                parts = name.rstrip("/").split("/")
                if (not name or name.startswith("/") or ":" in name
                        or any(part in ("", ".", "..") for part in parts)
                        or name.casefold() in seen
                        or stat.S_ISLNK(entry.external_attr >> 16)):
                    raise ValueError("Unsafe PowerShell ZIP member")
                seen.add(name.casefold())
            bundle.extractall(destination)
    else:
        with tarfile.open(archive, "r:gz") as bundle:
            bundle.extractall(destination, filter="data")


def install(destination, system):
    if platform.machine().lower() not in ("x86_64", "amd64"):
        raise ValueError("PowerShell CI acquisition requires an x64 runner")
    destination = destination.absolute()
    if os.path.lexists(destination):
        raise ValueError("PowerShell CI destination must not already exist")
    with tempfile.TemporaryDirectory(prefix="ci-powershell-", dir=destination.parent) as temporary:
        staging = Path(temporary)
        metadata = staging / "release.json"
        download(RELEASE_API, metadata)
        version, name, urls = select_assets(json.loads(metadata.read_text(encoding="utf-8")), system)
        archive, checksums = staging / name, staging / "hashes.sha256"
        download(urls[name], archive)
        download(urls["hashes.sha256"], checksums)
        verify_archive(archive, checksums)
        extracted = staging / "runtime"
        extracted.mkdir()
        extract_archive(archive, extracted, system)
        executable = extracted / ("pwsh.exe" if system == "Windows" else "pwsh")
        if executable.is_symlink() or not executable.is_file():
            raise ValueError("PowerShell archive has no regular runtime executable")
        if system == "Linux":
            executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
        result = subprocess.run(
            [str(executable), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command",
             "$PSVersionTable.PSVersion.ToString()"],
            capture_output=True, text=True, check=True, timeout=30,
        )
        if result.stdout.strip() != version:
            raise ValueError("PowerShell executable version does not match the stable release")
        extracted.rename(destination)
    return destination / executable.name, version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--github-env", required=True, type=Path)
    args = parser.parse_args()
    if any(character in str(args.destination) for character in "\r\n"):
        parser.error("Destination must fit on one environment-file line")
    executable, version = install(args.destination, platform.system())
    with args.github_env.open("a", encoding="utf-8") as output:
        output.write(f"CI_PWSH={executable}\n")
    print(f"CI host: {platform.system()} {platform.release()} {platform.machine()}")
    print(f"Verified latest stable PowerShell {version}: {executable}")


if __name__ == "__main__":
    main()
