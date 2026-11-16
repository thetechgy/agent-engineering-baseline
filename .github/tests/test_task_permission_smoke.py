"""Credential-free successor integration through shared preparation boundaries."""
import copy
from importlib.metadata import version, PackageNotFoundError
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))
import evaluation_campaign as campaign
import evaluation_campaign_core as core
import evaluation_campaign_protocol as protocol
import evaluation_campaign_selection as selection
from evaluation_tasks import load
import skill_evidence as evidence
import skill_reports as reports


def task():
    return selection.selected_task('gh-task-permission-v2')


class PermissionSmoke(unittest.TestCase):
    def test_registered_live_population_preserves_qualification_and_inputs(self):
        owner = task()
        original = load(ROOT / '.github/evals/campaigns/gh-task-permission-v2.json')
        frozen = protocol.frozen(owner)
        self.assertEqual(frozen['schedule'], [
            {'position': 1, 'case': 'gh-014', 'trial': 1, 'variant': 'current'},
            {'position': 2, 'case': 'gh-014', 'trial': 1, 'variant': 'absent'}])
        self.assertEqual(owner.entry(), original.entry())
        self.assertEqual(owner.grader(), original.grader())
        for present in (True, False):
            self.assertEqual(owner.resource_contract(present), original.resource_contract(present))
        self.assertEqual(original.definition['attempt_limit'], 36)
        self.assertNotIn('protocol', original.definition)
        self.assertEqual(selection.registration(owner)['controls'], [original.member])
        self.assertEqual(selection.registration(owner)['producers'][0]['location'], 'preparation/evidence')
        self.assertEqual(frozen['runtime']['resolved']['cli'], '0.155.1')
        self.assertEqual(frozen['runtime']['resolved']['model'], 'gpt-5.6-sol')
        self.assertEqual(frozen['runtime']['resolved']['reasoning_effort'], 'high')
        self.assertEqual(frozen['protocol']['grading'], {
            'mode': 'custom_only', 'agent_attempts': 2, 'verifier_runs': 2, 'model_judge_calls': 0,
            'judgments': 'deterministic; no model judgments', 'production_history': False})
        for mode in ('live', 'experiment-probe'):
            identity = campaign.purpose(owner, mode)
            profile = evidence.custom_contract('gh', purpose=identity)[0]
            self.assertEqual(profile['campaign']['definition'], owner.member)
            self.assertEqual(profile['campaign']['mode'], mode)
            self.assertEqual(profile['campaign']['policy_fields'], owner.public_policy_fields())
            self.assertEqual(profile['campaign']['scheduler'], 'campaign-scheduler-v1')
            self.assertTrue(all(profile[k] == v for k,v in frozen['source_identities'][mode].items()))
        self.assertNotEqual(campaign.purpose(owner, 'experiment-probe'), campaign.purpose(original, 'probe'))

    @unittest.skipUnless(__import__('importlib.util', fromlist=['find_spec']).find_spec('skillevaluator'), 'Owning task runtime required')
    def test_unsuffixed_live_verifier_binds_both_resource_inventories(self):
        owner = task()
        for present in (True, False):
            entry = owner.verifier_entry('gh-014', present)
            self.assertEqual(entry['id'], 'gh-014')
            self.assertEqual(entry['contract']['resources'], owner.resource_contract(present))
            self.assertEqual(entry['has_skill'], present)
            self.assertEqual(entry['grading_mode'], 'custom_only')
            members = owner.expected_members('gh-014', 'with_skill' if present else 'without_skill')
            self.assertEqual(json.loads(members['tests/entry.json']), entry)
            self.assertEqual(json.loads(members['environment/resource-inventory.json']), entry['contract']['resources'])

    def test_manifest_capability_survives_adapter_rename(self):
        owner = task()
        self.assertNotEqual(owner.definition['adapter'], 'gh-fixture')
        self.assertTrue(owner.trusted_launch_metadata)
        self.assertTrue(load(ROOT / '.github/evals/campaigns/gh-runtime-090-v1.json').trusted_launch_metadata)
        self.assertFalse(load(ROOT / '.github/evals/campaigns/boolean-effectiveness-v1.json').trusted_launch_metadata)

    def test_shared_two_slot_stops_and_measured_failure_continuation(self):
        owner = task()
        valid = {'cleanup': True, 'returncode': 0, 'grading_present': True,
                 'outcome': {'classification': 'failed'}, 'usage': {'estimated_usd': 0.1}}
        changes = [({}, None), ({'cleanup': False}, 'cleanup_failure'),
            ({'grading_present': False}, 'missing_grading_evidence'),
            ({'outcome': {'classification': 'unsupported'}}, 'unsupported_grading'),
            ({'outcome': {'classification': 'unknown'}}, 'missing_usable_evidence'),
            ({'outcome': {'classification': 'infrastructure_error'}}, 'verifier_failure'),
            ({'usage': {'estimated_usd': None}}, 'unknown_usage'),
            ({'native_exception': 'MissingCodexObservation'}, 'missing_native_observation')]
        for change, expected in changes:
            with self.subTest(expected=expected):
                ledger = {'entries': [{**r, 'state': 'unlaunched'} for r in protocol.frozen(owner)['schedule']]}
                snapshots = []
                def attempt(row, total):
                    row.update(copy.deepcopy({**valid, **change}), state='completed')
                    return protocol.stop_reason(row)
                core.drive(ledger, attempt, save=lambda: snapshots.append(copy.deepcopy(ledger)),
                           resources=lambda: (), baseline=(), threshold=3)
                self.assertEqual(ledger.get('stop_reason'), expected)
                self.assertEqual([r['state'] for r in ledger['entries']],
                                 ['completed', 'completed' if expected is None else 'unlaunched'])
                self.assertEqual(snapshots[1]['entries'][0]['state'], 'launching')
        self.assertEqual(owner.fixture_control('complete', {'position': 1}), 'unauthorized')
        self.assertEqual(owner.fixture_control('complete', {'position': 2}), 'good')
        self.assertEqual(owner.fixture_control('unsupported-grading', {'position': 1}), 'unsupported-command')
        self.assertIn('verifier-failure', protocol.scenarios(owner))
        self.assertIn('cleanup-failure', protocol.scenarios(owner))

    def test_authenticated_admission_uses_complete_preparation_not_oracle_subtree(self):
        from test_campaign_selection import SelectionContracts
        helper = SelectionContracts()
        owner = task()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def scenarios(files):
                files['scheduler-qualification.json']['scenarios'] = {name:{} for name in protocol.scenarios(owner)}
            archive, artifact, producer = helper.archive(root, owner, mutate=scenarios, producer_index=0)
            reference, internal = protocol.admit(archive, root/'downloaded', artifact, producer, owner)
            self.assertEqual(internal, 'preparation/evidence')
            self.assertEqual(reports.read_json(reference/'frozen-proposal.json'), protocol.frozen(owner))
            for key, value in [('path', '.github/workflows/current-evaluator.yml'), ('head_sha', '0'*40), ('run_attempt', 2)]:
                with self.assertRaises(ValueError):
                    protocol.authenticate_metadata(artifact, {**producer, key:value}, protocol.revision(),
                                                   __import__('codex_pilot_dispatch').REPO_ID, 40000000, task=owner)
            archive.write_bytes(archive.read_bytes() + b'tampered')
            with self.assertRaisesRegex(ValueError, 'digest mismatch'):
                protocol.admit(archive, root/'tampered', artifact, producer, owner)

    def test_real_live_constructor_and_consumers_for_successor(self):
        try: owning = version('skillevaluator') == '0.9.0' and version('harbor') == '0.25.0'
        except PackageNotFoundError: owning = False
        if not owning or not os.environ.get('APM_EXECUTABLE'):
            self.skipTest('Pinned 0.9 owner and APM required; hosted preparation exercises this path')
        from evaluation_launch_qualification import qualify, validate
        owner = task()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); campaign.stage(root, owner, 'live')
            result = qualify(root/'construction', owner, root/'evidence')
            valid = [r for r in result['records'] if r['case'] == 'valid']
            self.assertEqual({r['variant'] for r in valid}, {'current','absent'})
            self.assertTrue(all(r.get('resource_digest') and r.get('manifest_digest') for r in valid))
            self.assertFalse(result['allocation_claimed'])
            for case in ('missing-manifest','wrong-manifest-population','missing-inventory','tampered-inventory','wrong-inventory'):
                self.assertEqual(len([r for r in result['records'] if r['case'] == case and r.get('variant')]), 2)
                altered = copy.deepcopy(result)
                altered['records'] = [r for r in altered['records'] if r['case'] != case]
                with self.assertRaises(ValueError): validate(altered, owner)


if __name__ == '__main__':
    unittest.main()
