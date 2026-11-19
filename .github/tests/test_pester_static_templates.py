"""Qualification of bounded title expansion through the composed Pester runner."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from evaluation_campaign import purpose
from evaluation_campaign_protocol import frozen
from evaluation_campaign_selection import selected_task
from evaluation_runtime import ROOT
from evaluation_tasks import load
from pester_admission import runner_bytes
from pester_static_templates import template_runner_bytes
from test_codex_effectiveness import prospective_grader
import skill_evidence as evidence

PWSH = os.environ.get('CI_PWSH') or shutil.which('pwsh')
TRANSFER = '.github/evals/pester-return-contract/transfer'


class StaticTemplates(unittest.TestCase):
    @unittest.skipUnless(PWSH, 'PowerShell parser required')
    def test_static_layouts_and_adjacent_unsupported_forms(self):
        allowed = [
            "It 'case <FLaG>' -ForEach @{ Flag = 1 } { 1 | Should-Be 1 }",
            "It -Name 'case <Label2>' -TestCases @(@{ Label2 = 'a' }, @{ 'Label2' = 'b' }) { 1 | Should-Be 1 }",
            "Context 'case <Batch>' -ForEach @(\n@{ Batch = 1; Extra = 2 }\n@{ BATCH = 3 }\n) { It 'checks' { 1 | Should-Be 1 } }",
        ]
        unsupported = [
            ("It 'case <Flag>' -ForEach @(@{ Flag = 1 }, @{ Other = 2 }) {}", 'test_name_template'),
            ("It 'case <Flag>' -ForEach @(@{ Flag = 1 }, 2) {}", 'test_name_template'),
            ("It 'case <Flag>' -ForEach $rows {}", 'test_name_template'),
            ("It 'case <Flag>' -ForEach @{ Flag = 1 } -TestCases @{ Flag = 2 } {}", 'test_name_template'),
            ("Describe 'case <Flag>' { It 'child' -ForEach @{ Flag = 1 } {} }", 'test_name_template'),
            ("It 'case <Flag.Count>' -ForEach @{ Flag = @(1) } {}", 'test_name_template'),
            ("It 'case <script:Flag>' -ForEach @{ Flag = 1 } {}", 'test_name_template'),
            ("It 'case <Flag.ToString()>' -ForEach @{ Flag = 1 } {}", 'test_name_template'),
            ("It 'case <Error>' -ForEach @{ Error = 1 } {}", 'test_name_template'),
            ("It 'case <Flag>' -ForEach @{ Flag = (Get-Variable Flag) } {}", 'command_policy'),
            ('It "case $title" -ForEach @{ Flag = 1 } {}', 'test_name_template'),
        ]
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            runner = directory / 'Runner.ps1'
            candidate = directory / 'Subject.Tests.ps1'
            command = [PWSH, '-NoProfile', '-NonInteractive', '-File', str(runner), '-Candidate', str(candidate),
                       '-Profile', str(ROOT / TRANSFER / 'profile.json'), '-AdmissionOnly']

            def admit(raw, content):
                runner.write_bytes(raw)
                candidate.write_text(content, encoding='utf-8')
                result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=20)
                return json.loads(result.stdout)

            old, new = runner_bytes(), template_runner_bytes()
            for payload in allowed:
                with self.subTest(payload=payload):
                    self.assertEqual(admit(old,payload), {'status':'unsupported','code':'test_name_template'})
                    self.assertEqual(admit(new,payload), {'status':'admitted','code':'ok'})
            for payload, code in unsupported:
                with self.subTest(payload=payload):
                    self.assertEqual(admit(new,payload), {'status':'unsupported','code':code})

    def test_registered_pairs_preserve_independent_grading_and_scientific_criteria(self):
        tasks = []
        for variant in ('current','candidate'):
            identifier = f'pester-return-transfer-{variant}'
            task = selected_task(identifier+'-v6')
            old = load(ROOT/f'.github/evals/campaigns/{identifier}-v3.json')
            before = old.expected_members('pester-transfer-batch-v1','with_skill')
            after = task.expected_members('pester-transfer-batch-v1','with_skill')
            self.assertEqual(before.keys(), after.keys())
            self.assertEqual({k for k in before if before[k] != after[k]},
                             {'tests/Runner.ps1','environment/input/EXECUTION-PROFILE.md'})
            self.assertEqual(sum(k.startswith('tests/case/mutants/') for k in after), 5)
            proposal = frozen(task)
            self.assertEqual([row['variant'] for row in proposal['schedule']],
                             [variant,'absent','absent',variant,variant,'absent'])
            criteria = proposal['protocol']['decision_criteria']
            self.assertEqual(criteria['sha256'], hashlib.sha256((ROOT/criteria['path']).read_bytes()).hexdigest())
            for mode in ('live','experiment-probe'):
                profile, _, _ = evidence.custom_contract(task.definition['skill'], purpose=purpose(task,mode))
                self.assertTrue(all(profile[k] == v for k,v in proposal['source_identities'][mode].items()))
            tasks.append(after)
        self.assertEqual(tasks[0], tasks[1])

    def test_historical_registry_is_byte_equivalent_after_projecting_successors(self):
        registry = json.loads((ROOT / evidence.CUSTOM_REGISTRY).read_bytes())
        registry['profiles'] = {key: row for key, row in registry['profiles'].items() if '-source-v28-' not in key and '-source-v27-' not in key and '-source-v26-' not in key and key not in ('pester-effectiveness-v30', 'pester-cli-pilot-retained-v18', 'pester-effectiveness-v31', 'pester-cli-pilot-retained-v19')}
        raw = json.dumps(registry, sort_keys=True, separators=(',', ':')).encode()
        self.assertEqual(len(registry['profiles']), 874)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         'b89ade070c95a056590f5651798ac0858d4e7fa4c698abc51f64bf02914fb991')

    def test_nonmeasured_states_are_not_task_failures(self):
        from evaluation_campaign_protocol import stop_reason
        base = {'cleanup':True,'returncode':0,'grading_present':True,'usage':{'estimated_usd':0.01}}
        self.assertIsNone(stop_reason(dict(base,outcome={'classification':'failed'})))
        for row, reason in [
            (dict(base, grading_present=False), 'missing_grading_evidence'),
            (dict(base, returncode=1), 'execution_infrastructure_failure'),
            (dict(base, outcome={'classification':'unsupported'}), 'unsupported_grading'),
            (dict(base, outcome={'classification':'infrastructure_error'}), 'verifier_failure'),
        ]:
            self.assertEqual(stop_reason(row),reason)
        self.assertEqual(prospective_grader().assess({'status':'invalid','code':'artifact'},[]),
                         ('invalid',{'code':'artifact'}))
