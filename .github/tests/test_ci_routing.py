"""Production routing, complete Git comparisons, and fail-closed result controls."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('ci_routing', ROOT / '.github/scripts/ci_routing.py')
routing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routing)


class SelectionTests(unittest.TestCase):
    def selected(self, *paths):
        return {k for k, v in routing.select(list(paths)).items() if v}

    def test_docs_keep_required_platform_jobs_but_no_native_work(self):
        self.assertEqual(self.selected('docs/operator.md', 'CONTRIBUTING.md', '.github/evals/EVALUATION-PLAN.md'), set())

    def test_skill_support_is_not_documentation(self):
        self.assertEqual(self.selected('.apm/skills/podman/references/quadlet.md'), {'contracts', 'quality'})
        self.assertEqual(self.selected('.apm/skills/gh/scripts/helper.py'), {'contracts', 'quality', 'evaluator'})
        self.assertIn('legacy', self.selected('.apm/skills/powershell-pester-6/references/execution.md'))

    def test_shared_dependencies_and_unknown_inputs_select_broadly(self):
        for path in ('apm.yml', 'apm.lock.yaml', '.apm/instructions/safety.instructions.md',
                     '.github/scripts/evaluation_codex.py', '.github/scripts/evaluation_campaign_core.py',
                     '.github/scripts/skill_evidence.py', '.github/scripts/skill_report.py',
                     '.github/locks/evaluator.lock',
                     '.github/workflows/validate.yml', '.github/scripts/ci_routing.py',
                     'new-dependency.json', '../unsafe', '/absolute'):
            with self.subTest(path=path):
                self.assertEqual(self.selected(path), set(routing.FLAGS))

    def test_task_owned_and_workflow_boundaries(self):
        self.assertEqual(self.selected('.github/evals/powershell-pester-6/evals/grader.py'), routing.PESTER)
        self.assertEqual(self.selected('.github/evals/pester-admission-v1/controls/good.Tests.ps1'), routing.PESTER)
        self.assertEqual(self.selected('.github/evals/gh/evals/files/setup.py'), routing.GH)
        self.assertEqual(self.selected('.github/workflows/current-evaluator.yml'), {'contracts', 'evaluator'})
        self.assertEqual(self.selected('.github/workflows/evaluation-campaign.yml'), {'contracts'})
        self.assertEqual(self.selected('.github/scripts/qualify_scanners.py'), {'contracts', 'quality'})

    def test_main_keeps_the_existing_production_population(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'outputs'
            subprocess.run(['python3', '-B', str(ROOT / '.github/scripts/ci_routing.py'), 'plan'], check=True,
                env={**os.environ, 'GITHUB_EVENT_NAME': 'push', 'GITHUB_OUTPUT': str(output)}, capture_output=True)
            values = dict(line.split('=') for line in output.read_text().splitlines())
            self.assertEqual({key for key, value in values.items() if value == 'true'}, {'contracts', 'quality', 'pester'})

    def test_monitoring_is_contract_only(self):
        self.assertEqual(self.selected('.github/scripts/dependency_freshness.py'), {'contracts'})
        self.assertEqual(self.selected('README.md'), {'contracts'})

    def test_empty_or_incomplete_evidence_never_selects_nothing(self):
        self.assertTrue(all(routing.select([], complete=True).values()))
        self.assertTrue(all(routing.select(['README.md'], complete=False).values()))
        for event in ({}, {'pull_request': {'base': {'sha': 'malformed'}}}):
            self.assertFalse(routing.changes(event, 'pull_request')[1])
        self.assertFalse(routing.changes({}, 'push')[1])

    def test_large_rename_and_deleted_diff_through_real_git(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL).decode().strip()
            git('init', '-q'); git('config', 'user.email', 'fixture@example.invalid'); git('config', 'user.name', 'Fixture')
            (root / 'old.txt').write_text('same bytes')
            (root / 'deleted.py').write_text('deleted')
            git('add', '.'); git('commit', '-qm', 'base'); base = git('rev-parse', 'HEAD')
            (root / 'old.txt').rename(root / 'renamed.txt'); (root / 'deleted.py').unlink()
            for i in range(350):
                (root / f'file-{i}.md').write_text('large diff')
            git('add', '.'); git('commit', '-qm', 'head'); head = git('rev-parse', 'HEAD')
            # A later base-branch change is outside the PR's three-dot diff.
            git('checkout', '-q', '--detach', base)
            (root / 'base-only.txt').write_text('not a PR change')
            git('add', '.'); git('commit', '-qm', 'base advance'); advanced = git('rev-parse', 'HEAD')
            event = {'pull_request': {'base': {'sha': advanced}, 'head': {'sha': head}}}
            with patch.object(routing, 'ROOT', root):
                paths, complete, reason = routing.changes(event, 'pull_request')
                self.assertTrue(complete, reason)
                self.assertEqual(len(paths), 353)
                self.assertTrue({'old.txt', 'renamed.txt', 'deleted.py'} <= set(paths))
                self.assertNotIn('base-only.txt', paths)
                with patch.object(routing, 'git', return_value=b'incomplete'):
                    self.assertFalse(routing.changes(event, 'pull_request')[1])
                event['pull_request']['base']['sha'] = '0' * 40
                self.assertFalse(routing.changes(event, 'pull_request')[1])


class GateTests(unittest.TestCase):
    def needs(self, selected):
        outputs = {flag: str(selected).lower() for flag in routing.FLAGS}
        return {'plan': {'result': 'success', 'outputs': outputs},
                'linux': {'result': 'success'}, 'windows-powershell': {'result': 'success'},
                **{job: {'result': 'success' if selected else 'skipped'} for job in routing.JOBS.values()}}

    def test_skips_and_selected_success_are_distinct(self):
        self.assertIn('not selected', routing.gate(self.needs(False)))
        self.assertIn('selected', routing.gate(self.needs(True)))

    def test_every_selected_failure_cancellation_skip_and_missing_result_rejects(self):
        for job in (*routing.JOBS.values(), 'linux', 'windows-powershell'):
            for status in ('failure', 'cancelled', 'skipped', 'in_progress', None):
                with self.subTest(job=job, status=status):
                    needs = self.needs(True)
                    needs[job] = {} if status is None else {'result': status}
                    with self.assertRaises(ValueError): routing.gate(needs)

    def test_planner_failure_missing_outputs_and_unexpected_execution_reject(self):
        needs = self.needs(False)
        for status in ('failure', 'cancelled', 'skipped', None):
            bad = copy.deepcopy(needs); bad['plan']['result'] = status
            with self.assertRaises(ValueError): routing.gate(bad)
        for value in ('', 'TRUE', 'null', None):
            bad = copy.deepcopy(needs); bad['plan']['outputs']['legacy'] = value
            with self.assertRaises(ValueError): routing.gate(bad)
        needs['codex-pilot']['result'] = 'success'
        with self.assertRaises(ValueError): routing.gate(needs)

    def test_actual_gate_process_cannot_pass_selected_failure(self):
        needs = self.needs(True); needs['codex-pilot']['result'] = 'failure'
        result = subprocess.run(['python3', '-B', str(ROOT / '.github/scripts/ci_routing.py'), 'gate'],
                                env={**os.environ, 'CI_NEEDS': json.dumps(needs)}, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('codex-pilot: expected success, received failure', result.stderr)

    def test_actual_plan_process_uses_fixed_outputs_and_falls_back_broadly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); event = root / 'event.json'; event.write_text('{}')
            output = root / 'outputs'
            subprocess.run(['python3', '-B', str(ROOT / '.github/scripts/ci_routing.py'), 'plan'], check=True,
                env={**os.environ, 'GITHUB_EVENT_NAME': 'pull_request', 'GITHUB_EVENT_PATH': str(event),
                     'GITHUB_OUTPUT': str(output)}, capture_output=True)
            self.assertEqual(output.read_text(), ''.join(f'{flag}=true\n' for flag in routing.FLAGS))


if __name__ == '__main__':
    unittest.main()
