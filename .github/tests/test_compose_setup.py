"""Exercise the real checksum-first installer with inert download fixtures."""

import hashlib
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / ".github/scripts/setup-compose.sh"


class ComposeSetupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.runtime = self.root / "runtime"
        self.runtime.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.github_env = self.root / "github-env"
        self.github_env.touch()
        self.marker = self.root / "executed"
        self.ready = self.root / "downloaded"
        source = SOURCE.read_text()
        self.version = re.search(r"^compose_version=(\S+)$", source, re.M)[1]
        self.payload = ("#!/bin/sh\n"
                        'printf "invoked\\n" >> "$COMPOSE_TEST_EXECUTED"\n'
                        'printf "%s\\n" "${COMPOSE_TEST_VERSION:-' + self.version + '}"\n').encode()
        self.fixture = self.root / "payload"
        self.fixture.write_bytes(self.payload)
        digest = hashlib.sha256(self.payload).hexdigest()
        self.script = self.root / "setup-compose.sh"
        self.script.write_text(re.sub(r"^compose_sha256=[0-9a-f]{64}$",
                                      "compose_sha256=" + digest, source, flags=re.M))
        self.executable("curl", """#!/usr/bin/env python3
import os, pathlib, sys, time
target = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])
target.write_bytes(pathlib.Path(os.environ['COMPOSE_TEST_PAYLOAD']).read_bytes())
assert target.stat().st_mode & 0o111 == 0
pathlib.Path(os.environ['COMPOSE_TEST_READY']).touch()
if os.environ.get('COMPOSE_TEST_DOWNLOAD') == 'wait': time.sleep(30)
sys.exit(22 if os.environ.get('COMPOSE_TEST_DOWNLOAD') == 'fail' else 0)
""")
        self.executable("docker", '#!/bin/sh\nexec "$DOCKER_CONFIG/cli-plugins/docker-compose" version --short\n')
        self.env = {**os.environ, "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
                    "RUNNER_TEMP": str(self.runtime), "GITHUB_WORKSPACE": str(ROOT),
                    "GITHUB_ENV": str(self.github_env), "COMPOSE_TEST_PAYLOAD": str(self.fixture),
                    "COMPOSE_TEST_EXECUTED": str(self.marker), "COMPOSE_TEST_READY": str(self.ready)}

    def executable(self, name, contents):
        path = self.bin / name
        path.write_text(contents)
        path.chmod(0o755)

    def invoke(self, *args, **environment):
        return subprocess.run(["bash", str(self.script), *args], env={**self.env, **environment},
                              capture_output=True, text=True, timeout=15)

    def assert_failed_cleanly(self, result):
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.runtime.iterdir()), [])
        self.assertEqual(self.github_env.read_text(), "")

    def test_verified_plugin_discovery_and_owned_cleanup(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        exported = dict(line.split("=", 1) for line in self.github_env.read_text().splitlines())
        self.assertEqual(exported["DOCKER_CONFIG"], exported["COMPOSE_PLUGIN_ROOT"])
        plugin = Path(exported["DOCKER_CONFIG"])
        self.assertEqual(plugin.stat().st_mode & 0o777, 0o700)
        self.assertEqual((plugin / "cli-plugins/docker-compose").read_bytes(), self.payload)
        self.assertEqual(self.marker.read_text().splitlines(), ["invoked", "invoked"])
        unrelated = self.runtime / "unrelated"
        unrelated.write_text("preserve")
        self.assertEqual(self.invoke("cleanup", **exported).returncode, 0)
        self.assertFalse(plugin.exists())
        self.assertEqual(unrelated.read_text(), "preserve")
        self.assertEqual(self.invoke("cleanup", **exported).returncode, 0)

    def test_wrong_checksum_never_executes_or_exports(self):
        self.fixture.write_bytes(self.payload + b"# corrupted\n")
        self.assert_failed_cleanly(self.invoke())
        self.assertFalse(self.marker.exists())

    def test_failed_download_never_executes_or_exports(self):
        self.assert_failed_cleanly(self.invoke(COMPOSE_TEST_DOWNLOAD="fail"))
        self.assertFalse(self.marker.exists())

    def test_wrong_runtime_version_removes_installation(self):
        self.assert_failed_cleanly(self.invoke(COMPOSE_TEST_VERSION="unexpected"))

    def test_interrupted_download_removes_partial_installation(self):
        process = subprocess.Popen(["bash", str(self.script)], env={**self.env, "COMPOSE_TEST_DOWNLOAD": "wait"},
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            deadline = time.monotonic() + 10
            while not self.ready.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(self.ready.exists())
            os.killpg(process.pid, signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=5)
            self.assert_failed_cleanly(subprocess.CompletedProcess([], process.returncode, stdout, stderr))
            self.assertFalse(self.marker.exists())
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()

    def test_linked_environment_file_and_cleanup_target_are_rejected(self):
        target = self.root / "unrelated"
        target.write_text("preserve")
        self.github_env.unlink()
        self.github_env.symlink_to(target)
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertEqual(target.read_text(), "preserve")
        linked = self.runtime / "compose-plugin.link"
        linked.symlink_to(self.root, target_is_directory=True)
        self.assertNotEqual(self.invoke("cleanup", COMPOSE_PLUGIN_ROOT=str(linked)).returncode, 0)
        self.assertEqual(target.read_text(), "preserve")

    def test_tool_directory_inside_checkout_is_rejected(self):
        self.assert_failed_cleanly(self.invoke(GITHUB_WORKSPACE=str(self.runtime)))
