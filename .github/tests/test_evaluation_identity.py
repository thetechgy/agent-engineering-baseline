"""Git-backed execution identity and compatibility controls."""
import copy
from pathlib import Path
import subprocess
import tempfile
import unittest

import evaluation_identity as bindings
import skill_evidence as evidence


class ExecutionBindingTests(unittest.TestCase):
    def git(self, workspace, *arguments):
        return subprocess.check_output(
            ['git', '-C', str(workspace), '-c', 'user.name=Fixture',
             '-c', 'user.email=fixture@example.invalid', *arguments],
            stderr=subprocess.PIPE, text=True).strip()

    def revise(self, workspace, message):
        self.git(workspace, 'add', '.github')
        self.git(workspace, 'commit', '-m', message)
        return self.git(workspace, 'rev-parse', 'HEAD')

    def test_source_only_revision_reuses_grading_and_preserves_offline_replay(self):
        purpose = 'skill_effectiveness_control'
        profile = {'id': bindings.EFFECTIVENESS, 'skill_id': 'powershell-pester-6',
                   'grading': 'custom_only', 'runtime': {'codex': '0.167.0'}}
        contract = evidence.identity(bindings.grading_definition(profile))
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            self.git(workspace, 'init')
            self.git(workspace, 'remote', 'add', 'origin', 'https://github.com/example/fixture.git')
            config = workspace / bindings.REGISTRY
            config.parent.mkdir(parents=True)
            config.write_text('{"version": 1, "retained_source_revisions": []}\n')
            source = workspace / '.github/scripts/shared.py'
            source.parent.mkdir()
            source.write_text('revision = 1\n')
            first = self.revise(workspace, 'Register reusable grading')
            original = bindings.execution_binding(workspace, profile, purpose, contract)
            self.assertEqual(original['revision'], first)
            source.write_text('revision = 2\n')
            with self.assertRaisesRegex(ValueError, 'committed tree'):
                bindings.execution_binding(workspace, profile, purpose, contract)
            second = self.revise(workspace, 'Change shared source only')
            latest = bindings.execution_binding(workspace, profile, purpose, contract)
            self.assertEqual(self.git(workspace, 'diff', '--numstat', first, second),
                             '1\t1\t.github/scripts/shared.py')
            self.assertEqual(latest['grading'], original['grading'])
            self.assertNotEqual(evidence.identity(latest), evidence.identity(original))
            self.assertEqual(bindings.execution_binding(workspace, profile, purpose, contract, recorded=original),
                             original)

            for key in ('tree', 'profile', 'purpose', 'grading', 'policy', 'replay_adapter'):
                with self.subTest(key=key):
                    forged = {**original, key: 'forged'}
                    with self.assertRaisesRegex(ValueError, 'Execution binding mismatch'):
                        bindings.execution_binding(workspace, profile, purpose, contract, recorded=forged)
            wrong_runtime = copy.deepcopy(profile)
            wrong_runtime['runtime']['codex'] = '0.172.0'
            with self.assertRaisesRegex(ValueError, 'Execution binding mismatch'):
                bindings.execution_binding(workspace, wrong_runtime, purpose, contract, recorded=original)

            unrelated = self.git(workspace, 'commit-tree', 'HEAD^{tree}', '-m', 'Unreviewed tree')
            forged = {**latest, 'revision': unrelated}
            # A modified worktree cannot add a trusted archive pin.
            config.write_text(f'{{"version": 1, "retained_source_revisions": ["{unrelated}"]}}\n')
            with self.assertRaisesRegex(ValueError, 'outside reviewed history'):
                bindings.execution_binding(workspace, profile, purpose, contract, recorded=forged)
