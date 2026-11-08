"""Real-parser controls for the versioned subset; candidate code never executes here."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))
import codex_pilot_iteration as iteration
from codex_pilot_contract import runner_bytes as legacy_runner_bytes


@unittest.skipUnless(shutil.which('pwsh'), 'PowerShell parser required')
class IterationAdmission(unittest.TestCase):
    def admission(self, text, *, legacy=False):
        with tempfile.TemporaryDirectory(prefix='iteration-admission-') as directory:
            root = Path(directory)
            runner = root / 'Runner.ps1'
            runner.write_bytes(legacy_runner_bytes() if legacy else iteration.runner_bytes())
            candidate = root / 'Subject.Tests.ps1'; candidate.write_text(text)
            env = {'PATH': os.environ['PATH'], 'HOME': directory, 'TMPDIR': os.environ.get('TMPDIR', directory),
                   'POWERSHELL_TELEMETRY_OPTOUT': '1', 'DOTNET_EnableDiagnostics': '0'}
            result = subprocess.run([shutil.which('pwsh'), '-NoLogo', '-NoProfile', '-NonInteractive',
                '-File', str(runner), '-Candidate', str(candidate), '-Profile',
                str(ROOT / '.github/evals/powershell-pester-6/support/cases/pester-001/profile.json'),
                '-AdmissionOnly'], text=True, capture_output=True, env=env, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr[-1000:])
            return json.loads(result.stdout)

    def test_plain_loop_rejects_before_and_admits_after(self):
        text = "Describe 'iteration' { It 'counts' { for ($n=0; $n -lt 3; $n++) { $n | Should -Be $n } } }"
        self.assertEqual(self.admission(text, legacy=True), {'status': 'unsupported', 'code': 'ast_kind'})
        self.assertEqual(self.admission(text), {'status': 'admitted', 'code': 'ok'})

    def test_exact_retained_submissions_reject_before_and_admit_after(self):
        from codex_pilot_replay import corpus
        _, _, submissions, _ = corpus()
        for arm, raw in submissions.items():
            with self.subTest(arm=arm):
                self.assertEqual(self.admission(raw.decode(), legacy=True), {'status': 'unsupported', 'code': 'ast_kind'})
                self.assertEqual(self.admission(raw.decode()), {'status': 'admitted', 'code': 'ok'})

    def test_all_increment_forms_and_writable_scopes(self):
        for scope in ('', 'local:', 'private:', 'script:'):
            for operation in ('$%sn++', '++$%sn', '$%sn--', '--$%sn'):
                with self.subTest(scope=scope, operation=operation):
                    text = "Describe x { It y { $%sn=1; %s; $%sn | Should-Be $%sn } }" % (scope, operation % scope, scope, scope)
                    self.assertEqual(self.admission(text)['status'], 'admitted')

    def test_int64_aliases_reject_before_and_admit_after(self):
        for typename in ('long', 'int64', 'LONG'):
            text = "Describe x { It y { $value=[%s]123; Should-HaveType -Actual $value -Expected ([%s]) } }" % (typename, typename)
            with self.subTest(typename=typename):
                self.assertEqual(self.admission(text, legacy=True)['status'], 'unsupported')
                self.assertEqual(self.admission(text)['status'], 'admitted')
        self.assertEqual(self.admission("Describe x { It y { $value=[System.IO.File]; 1 | Should-Be 1 } }")['status'], 'unsupported')

    def test_independent_native_payload_admission(self):
        good = (ROOT / '.github/evals/powershell-pester-6/support/qualification/pester-001/classic.Tests.ps1').read_bytes()
        for name, expected in iteration.CONTROLS.items():
            with self.subTest(name=name):
                value = self.admission(iteration.control_payload(name, good).decode())
                self.assertEqual(value['status'], 'unsupported' if expected == 'unsupported' else 'admitted')

    def test_every_loop_component_is_inspected(self):
        forbidden = ("Get-Content '/tests/grader.py'", "Invoke-Expression '1'", "& 'Get-ActivePort'",
                     "[System.IO.File]::ReadAllText('/tests/grader.py')")
        for operation in forbidden:
            candidates = (
                f'for ($n=({operation}); $n -lt 1; $n++) {{ 1 | Should-Be 1 }}',
                f'for ($n=0; ({operation}); $n++) {{ 1 | Should-Be 1 }}',
                f'for ($n=0; $n -lt 1; {operation}) {{ $n=1 }}',
                f'for ($n=0; $n -lt 1; $n++) {{ {operation} }}')
            for component, statement in zip(('initializer', 'condition', 'iterator', 'body'), candidates):
                with self.subTest(operation=operation, component=component):
                    self.assertEqual(self.admission('Describe x { It y { ' + statement + ' } }')['status'], 'unsupported')

    def test_protected_mutation_targets_rejected(self):
        protected = ('PSScriptRoot', 'true', 'false', 'null', 'PID', 'ErrorActionPreference', 'PSHOME',
                     'PROFILE', 'PSDefaultParameterValues', '__peResult', '____Pester', 'env:PATH', 'global:n',
                     'function:n', 'variable:n', 'alias:n', 'script:PSScriptRoot', 'local:true', 'private:__peResult')
        for name in protected:
            for operator in ('++', '--'):
                with self.subTest(name=name, operator=operator):
                    text = 'Describe x { It y { for ($n=0; $n -lt 1; $' + name + operator + ') { $n=1 } } }'
                    self.assertEqual(self.admission(text)['status'], 'unsupported')

    def test_member_index_cast_and_parenthesized_mutations_rejected(self):
        for target in ('$value.Port', '$value[0]', '($value)', '([int]$value)'):
            for expression in (target + '++', '--' + target):
                with self.subTest(expression=expression):
                    result = self.admission('Describe x { It y { $value=@(1); ' + expression + ' } }')
                    self.assertIn(result['status'], ('unsupported', 'invalid'))
        for expression in ('$value.Port = 2', '$value[0] += 1', '$PSScriptRoot = 1'):
            self.assertEqual(self.admission('Describe x { It y { ' + expression + ' } }')['status'], 'unsupported')

    def test_parse_failures_and_nonterminating_work_are_distinct(self):
        self.assertEqual(self.admission('for (')['status'], 'invalid')
        # Parsing is bounded and never executes this loop. Native qualification
        # separately verifies execution is classified timeout under unchanged limits.
        self.assertEqual(self.admission('Describe x { It y { for (;;) {} } }')['status'], 'admitted')

    def test_cast_of_increment_result_keeps_a_plain_variable_target(self):
        # PowerShell parses [int]$n++ as a cast of the increment result; the
        # increment operand itself is still the plain variable $n.
        self.assertEqual(self.admission('Describe x { It y { $n=1; [int]$n++ } }')['status'], 'admitted')
        self.assertEqual(self.admission('Describe x { It y { $n=1; ++[int]$n } }')['status'], 'unsupported')


if __name__ == '__main__':
    unittest.main()
