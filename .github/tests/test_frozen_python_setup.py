"""Frozen interpreter metadata must be verified before uv consumes it."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class FrozenPythonSetup(unittest.TestCase):
    def test_failed_or_changed_catalog_never_reaches_interpreter_installation(self):
        script = ROOT / '.github/scripts/setup-skillevaluator.sh'
        version = re.search(r"^test .*uv --version.* = '([^']+)'$", script.read_text(), re.M)[1]
        for mode in ('changed', 'unavailable'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                commands = root / 'bin'; commands.mkdir()
                marker = root / 'unexpected-uv-call'
                uv = commands / 'uv'
                uv.write_text('#!/bin/sh\nif [ "$1" = --version ]; then\n'
                              f"  printf 'uv {version}\\n'; exit 0\nfi\n"
                              'touch "$UNEXPECTED_UV_CALL"\nexit 99\n')
                curl = commands / 'curl'
                curl.write_text('#!/bin/sh\n' + ('exit 22\n' if mode == 'unavailable' else
                    'while [ "$#" -gt 0 ]; do\n'
                    '  if [ "$1" = --output ]; then shift; output=$1; fi\n'
                    '  shift\ndone\nprintf "{}\\n" > "$output"\n'))
                for command in (uv, curl):
                    command.chmod(0o700)
                environment = {'PATH': str(commands) + os.pathsep + os.defpath,
                    'RUNNER_TEMP': str(root / 'tools'), 'GITHUB_WORKSPACE': str(ROOT),
                    'GITHUB_ENV': str(root / 'github-env'), 'GITHUB_PATH': str(root / 'github-path'),
                    'UNEXPECTED_UV_CALL': str(marker)}
                result = subprocess.run(['bash', str(script), 'candidate-current'],
                    env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(marker.exists(), 'Unverified metadata reached uv installation')
                self.assertFalse((root / 'tools/current-evaluator').exists())
                self.assertFalse((root / 'github-env').exists())
