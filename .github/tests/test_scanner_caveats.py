"""Run adapter controls in the quality evaluator, preserving the historical review runtime."""
import os
from pathlib import Path
import subprocess
import unittest


class ScannerCaveatTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('SKILL_EVALUATION_KIND') == 'quality', 'Requires quality setup')
    def test_retained_adapter_compatibility_contracts(self):
        python = os.environ['SKILL_EVALUATOR_PYTHON']
        tools = Path(python).parents[3]
        root = Path(__file__).resolve().parents[2]
        script = 'import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); from qualify_scanner_caveats import contracts; print(contracts(Path(sys.argv[2])))'
        result = subprocess.run([python, '-B', '-c', script, str(root / '.github/scripts'), str(tools)],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
