"""Exact successor selection, frozen decision and native deployment; no inference."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))
from evaluation_campaign import purpose, stage
from evaluation_campaign_protocol import frozen
from evaluation_campaign_selection import selected_task
import skill_evidence as evidence
import skill_reports as reports

BASE = ROOT / '.github/evals/pester-transfer-decision'


class TransferDecision(unittest.TestCase):
    def test_freeze_and_historical_profiles_are_preserved(self):
        freeze = reports.read_json(BASE / 'freeze.json')
        self.assertEqual(freeze['proposed_attempts'], 12)
        self.assertEqual(freeze['authorized_live_attempts'], 0)
        for member, digest in freeze['files'].items():
            self.assertEqual(hashlib.sha256((ROOT / member).read_bytes()).hexdigest(), digest, member)
        registry = reports.read_json(ROOT / '.github/evals/custom-metrics.json')
        for key, digest in reports.read_json(BASE / freeze['historical_profiles']).items():
            raw = json.dumps(registry['profiles'][key], sort_keys=True, separators=(',', ':')).encode()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), digest, key)

    def test_successors_change_only_registered_admission_and_keep_two_matched_pairs(self):
        shared = []
        for variant in ('current', 'candidate'):
            task = selected_task('pester-return-transfer-' + variant + '-v5')
            proposal = frozen(task)
            self.assertEqual([r['variant'] for r in proposal['schedule']],
                             [variant, 'absent', 'absent', variant, variant, 'absent'])
            self.assertEqual(proposal['protocol']['budget']['planning_allocation_usd'], 8)
            self.assertEqual(proposal['protocol']['budget']['stop_estimate_usd'], 5)
            self.assertEqual(proposal['protocol']['budget']['overshoot_reserve_usd'], 3)
            criteria = proposal['protocol']['decision_criteria']
            self.assertEqual(criteria['sha256'], hashlib.sha256((ROOT / criteria['path']).read_bytes()).hexdigest())
            old = reports.read_json(ROOT / task.member.replace('-v5.json', '-v3.json'))
            changed = {k for k in task.definition if task.definition[k] != old.get(k)}
            self.assertEqual(changed, {'id', 'protocol', 'admission_policy', 'control_set'})
            self.assertEqual(task.definition['admission_policy'], 'pester-collection-numeric-v1')
            from evaluation_tasks import load
            previous = load(ROOT / task.member.replace('-v5.json', '-v3.json'))
            before = previous.expected_members(task.definition['source_case'], 'with_skill')
            after = task.expected_members(task.definition['source_case'], 'with_skill')
            self.assertEqual({k for k in after if after[k] != before[k]},
                             {'tests/Runner.ps1', 'environment/input/EXECUTION-PROFILE.md'})
            for mode in ('live', 'experiment-probe'):
                profile, _, _ = evidence.custom_contract(task.definition['skill'], purpose=purpose(task, mode))
                self.assertTrue(all(profile[k] == v for k, v in proposal['source_identities'][mode].items()))
            shared.append(after)
        self.assertEqual(shared[0], shared[1])

    def test_control_population_uses_contract_cases_with_the_qualified_policy(self):
        from evaluation_tasks import load
        for variant in ('current', 'candidate'):
            previous = load(ROOT / ('.github/evals/campaigns/pester-return-transfer-' + variant + '-controls-v4.json'))
            self.assertGreater(len(previous.cases('oracle')) * 2, previous.definition['attempt_limit'])
            selected = load(ROOT / ('.github/evals/campaigns/pester-return-transfer-' + variant + '-controls-v5.json'))
            self.assertEqual(len(selected.cases('oracle')) * 2, selected.definition['attempt_limit'])
            self.assertEqual(set(selected.controls()), {'good', 'good-loop', 'value-only', 'overrestricted', 'invalid'})
            for mode in ('oracle', 'probe'):
                profile, _, _ = evidence.custom_contract(selected.definition['skill'], purpose=purpose(selected, mode))
                self.assertEqual(profile['qualification_cases'], {case:selected.definition['source_case'] for case in selected.cases(mode)})
            selected.definition['control_set'] = 'unreviewed'
            with self.assertRaisesRegex(ValueError, 'Unknown batch control set'):
                selected.controls()

    @unittest.skipUnless(os.environ.get('APM_EXECUTABLE'), 'Pinned APM required for native deployment')
    def test_production_staging_keeps_exact_current_candidate_and_absent_deployments(self):
        shared = []
        for variant in ('current', 'candidate'):
            task = selected_task('pester-return-transfer-' + variant + '-v5')
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                _, _, captured, _ = stage(root, task, 'live')
                self.assertEqual(len(captured), 2)
                for row in captured:
                    task.validate_members(row['members'], row['case_id'], row['arm'])
                present = next(row['members'] for row in captured if row['arm'] == 'with_skill')
                absent = next(row['members'] for row in captured if row['arm'] == 'without_skill')
                prefix = 'environment/skills/powershell-pester-6/'
                self.assertEqual(len([k for k in present if k.startswith(prefix)]), 3)
                self.assertFalse(any(k.startswith(prefix) for k in absent))
                shared.append({k:v for k,v in present.items() if not k.startswith(prefix)})
        self.assertEqual(shared[0], shared[1])
