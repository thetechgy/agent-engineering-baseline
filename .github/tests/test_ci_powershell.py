"""Offline tests of stable-only runtime acquisition through the CI entry point."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile


SPEC = importlib.util.spec_from_file_location(
    "ci_powershell", Path(__file__).resolve().parents[1] / "scripts/install_ci_powershell.py")
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


def release(system="Linux", version="7.6.6"):
    name = (f"PowerShell-{version}-win-x64.zip" if system == "Windows"
            else f"powershell-{version}-linux-x64.tar.gz")
    return {"tag_name": f"v{version}", "draft": False, "prerelease": False,
            "assets": [{"name": asset, "browser_download_url": f"{runtime.RELEASE_BASE}v{version}/{asset}"}
                       for asset in (name, "hashes.sha256")]}


class CIPowerShellTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_selects_only_exact_official_assets_for_both_hosts(self):
        for system in ("Linux", "Windows"):
            version, name, urls = runtime.select_assets(release(system), system)
            self.assertEqual(version, "7.6.6")
            self.assertEqual(set(urls), {name, "hashes.sha256"})

    def test_rejects_prerelease_draft_and_malformed_metadata(self):
        for change in ({"prerelease": True}, {"draft": True}, {"tag_name": "v7.7.0-preview.1"},
                       {"tag_name": "v7.7.0-rc.1"}, {"tag_name": "v7.7.0-beta.1"},
                       {"tag_name": "v7.6.6\nCI_PWSH=other"}, {"prerelease": None}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                runtime.select_assets({**release(), **change}, "Linux")

    def test_rejects_missing_duplicate_or_relocated_assets(self):
        for mode in ("missing", "duplicate", "relocated"):
            data = release()
            if mode == "missing":
                data["assets"].pop()
            elif mode == "duplicate":
                data["assets"].append(data["assets"][0])
            else:
                data["assets"][0]["browser_download_url"] = "https://example.invalid/runtime"
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                runtime.select_assets(data, "Linux")

    def test_installs_and_executes_verified_linux_fixture_without_ambient_pwsh(self):
        executable, version = self.install_fixture()
        self.assertEqual(version, "7.6.6")
        self.assertEqual(executable, self.root / "installed/pwsh")
        self.assertEqual(subprocess.check_output([str(executable)], text=True).strip(), version)

    def install_fixture(self, *, reported="7.6.6", checksum="valid"):
        data = release()
        archive = self.root / "fixture.tar.gz"
        content = f"#!/bin/sh\nprintf '%s\\n' '{reported}'\n".encode()
        with tarfile.open(archive, "w:gz") as bundle:
            member = tarfile.TarInfo("pwsh")
            member.size = len(content)
            bundle.addfile(member, io.BytesIO(content))
        name = data["assets"][0]["name"]
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        sums = f"{digest}  {name}\n"
        if checksum == "wrong":
            sums = f"{'0' * 64}  {name}\n"
        elif checksum == "duplicate":
            sums *= 2
        elif checksum == "missing":
            sums = ""

        def download(url, destination):
            if url == runtime.RELEASE_API:
                destination.write_text(json.dumps(data))
            elif url.endswith("/hashes.sha256"):
                destination.write_text(sums)
            else:
                destination.write_bytes(archive.read_bytes())

        with patch.object(runtime, "download", side_effect=download), \
                patch.object(runtime.platform, "machine", return_value="x86_64"):
            return runtime.install(self.root / "installed", "Linux")

    def test_bad_hash_metadata_never_extracts_or_executes_runtime(self):
        for mode in ("wrong", "duplicate", "missing"):
            with self.subTest(mode=mode), patch.object(runtime, "extract_archive") as extract, \
                    patch.object(runtime.subprocess, "run") as run, self.assertRaises(ValueError):
                self.install_fixture(checksum=mode)
            extract.assert_not_called()
            run.assert_not_called()
            self.assertFalse((self.root / "installed").exists())

    def test_accepts_official_utf16_and_utf8_bom_checksum_files(self):
        archive = self.root / "runtime.zip"
        archive.write_bytes(b"verified archive fixture")
        sums = self.root / "hashes.sha256"
        digest = hashlib.sha256(archive.read_bytes()).hexdigest().upper()
        for encoding in ("utf-16", "utf-8-sig"):
            with self.subTest(encoding=encoding):
                sums.write_text(f"{digest}  {archive.name}\n", encoding=encoding)
                runtime.verify_archive(archive, sums)

    def test_runtime_version_mismatch_leaves_no_installed_runtime(self):
        with self.assertRaisesRegex(ValueError, "version does not match"):
            self.install_fixture(reported="7.7.0-preview.1")
        self.assertFalse((self.root / "installed").exists())

    def test_existing_destination_is_preserved_without_network_access(self):
        destination = self.root / "installed"
        destination.mkdir()
        sentinel = destination / "keep"
        sentinel.write_text("unrelated")
        with patch.object(runtime, "download") as download, self.assertRaises(ValueError):
            runtime.install(destination, "Linux")
        download.assert_not_called()
        self.assertEqual(sentinel.read_text(), "unrelated")

    def test_windows_zip_rejects_traversal_and_case_collisions(self):
        for names in (("../pwsh.exe",), ("C:/pwsh.exe",), ("pwsh.exe", "PWSH.EXE")):
            archive = self.root / "runtime.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                for name in names:
                    bundle.writestr(name, "untrusted")
            with self.subTest(names=names), self.assertRaises(ValueError):
                runtime.extract_archive(archive, self.root / "extracted", "Windows")
        self.assertFalse((self.root / "extracted").exists())

    def test_windows_zip_extracts_runtime_and_supporting_files(self):
        archive = self.root / "runtime.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("pwsh.exe", "fixture executable")
            bundle.writestr("Modules/fixture.psd1", "fixture module")
        destination = self.root / "extracted"
        runtime.extract_archive(archive, destination, "Windows")
        self.assertEqual((destination / "pwsh.exe").read_text(), "fixture executable")
        self.assertTrue((destination / "Modules/fixture.psd1").is_file())

    def test_platform_jobs_use_verified_runtime_and_latest_host_labels(self):
        import yaml
        workflow = Path(__file__).resolve().parents[1] / "workflows/validate.yml"
        jobs = yaml.safe_load(workflow.read_text())["jobs"]
        self.assertNotIn("macos", jobs)
        for name, host in (("linux", "ubuntu-latest"), ("windows-powershell", "windows-latest")):
            job = jobs[name]
            self.assertEqual(job["runs-on"], host)
            acquisition = next(i for i, step in enumerate(job["steps"])
                               if "install_ci_powershell.py" in step.get("run", ""))
            for index, step in enumerate(job["steps"]):
                if "Install-Module" in step.get("run", "") or "Invoke-Validation.ps1" in step.get("run", ""):
                    self.assertGreater(index, acquisition)
                    self.assertIn("& $env:CI_PWSH", step["run"])
                self.assertNotEqual(step.get("shell"), "powershell")
