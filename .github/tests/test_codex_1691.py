"""Check opt-in admission and frozen compatibility accounting."""
import hashlib
import json
import unittest

from codex_pilot_contract import configuration
from evaluation_campaign import purpose
import evaluation_campaign_protocol as protocol
from evaluation_campaign_selection import owning_evaluator, selected_task
from evaluation_runtime import ROOT, read_profile, evaluator
from evaluation_tasks import load
from qualify_codex_1691 import SELECTOR, check_pricing
import evaluator_profiles
import skill_evidence


class Codex1691Tests(unittest.TestCase):
    def test_candidate_uses_existing_gh_contract_and_has_no_live_capability(self):
        task = load(ROOT / '.github/evals/campaigns/gh-codex-1691.json')
        held = load(ROOT / '.github/evals/campaigns/gh-task-permission-v2.json')
        runtime = read_profile(SELECTOR)
        self.assertEqual((runtime['resolved']['cli'], runtime['resolved']['model'], runtime['resolved']['reasoning_effort']),
                         ('0.169.1', 'gpt-6.2-sol', 'high'))
        self.assertEqual(runtime['profile']['capabilities'], ['non-forwarding-cli-probe'])
        self.assertFalse(runtime['profile']['inference_enabled'])
        self.assertIs(evaluator(runtime), evaluator_profiles.NEXT)
        self.assertEqual(task.entry(), held.entry())
        self.assertEqual(task.cases('probe'), held.cases('probe'))
        self.assertEqual(task.resource_contract(True), held.resource_contract(True))
        self.assertEqual(task.resource_contract(False), held.resource_contract(False))
        with self.assertRaisesRegex(ValueError, 'cannot enable inference'):
            task.cases('live')
        config = configuration('http://127.0.0.1:8765/v1', runtime=runtime['resolved'])
        self.assertFalse(config['agents']['enabled'])
        self.assertFalse(config['features']['multi_agent_v2'])

    def test_live_opt_in_reuses_frozen_cli_and_permission_task(self):
        task = selected_task('gh-codex-1691-live')
        live = read_profile(ROOT / task.definition['runtime_profile'])
        fixture = read_profile(SELECTOR)
        self.assertNotEqual(live['profile']['id'], fixture['profile']['id'])
        self.assertEqual({**live['resolved'], 'id': fixture['resolved']['id']}, fixture['resolved'])
        self.assertEqual(configuration(runtime=live['resolved']), configuration(runtime=fixture['resolved']))
        self.assertEqual(configuration(runtime=live['resolved'])['model_providers']['pilot']['base_url'],
                         'https://api.openai.com/v1')
        self.assertIs(owning_evaluator(task), evaluator_profiles.NEXT)
        held = selected_task('gh-task-permission-v2')
        self.assertEqual(task.entry(), held.entry())
        self.assertEqual(task.grader(), held.grader())
        self.assertEqual(task.cases('live'), held.cases('live'))
        self.assertEqual(task.definition['variants'], held.definition['variants'])
        self.assertEqual(protocol.protocol(task)['grading'], protocol.protocol(held)['grading'])
        self.assertIn('provider-refusal', protocol.scenarios(task))
        fixture_task = load(ROOT / '.github/evals/campaigns/gh-codex-1691.json')
        with self.assertRaisesRegex(ValueError, 'cannot authorize inference'):
            protocol.protocol(fixture_task)

    def test_registry_projects_exact_main_and_candidate_matches_shared_evidence_owner(self):
        registry = skill_evidence.custom_registry(ROOT)
        original = {**registry, 'profiles': {
            key: row for key, row in registry['profiles'].items()
            if '-source-v28-' not in key and key not in ('pester-effectiveness-v31', 'pester-cli-pilot-retained-v19')
            and '-source-v27-' not in key and key not in ('pester-effectiveness-v30', 'pester-cli-pilot-retained-v18')}}
        self.assertEqual(hashlib.sha256(json.dumps(original, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                         '6528c9bf763bec8056c8cfd57273cab9a2caf875d52584852496e34725b3252e')
        task = load(ROOT / '.github/evals/campaigns/gh-codex-1691.json')
        identity = purpose(task, 'probe')
        manifest = skill_evidence.custom_source_manifest(ROOT, 'gh', purpose=identity)
        self.assertEqual(skill_evidence.identity(manifest), registry['profiles'][identity]['runtime_digest'])

    def test_opt_in_report_accepts_only_numeric_cache_writes_and_preserves_unknown(self):
        trial = {'agent_result': {'n_input_tokens': 100, 'n_cache_tokens': 30,
                                  'metadata': {'cache_write_input_count': 50}}}
        self.assertNotIn('cache_write_input_count', skill_evidence.custom_usage(trial))
        self.assertEqual(skill_evidence.custom_usage(trial, cache_writes=True)['cache_write_input_count'], 50)
        trial['agent_result']['metadata'].clear()
        self.assertIsNone(skill_evidence.custom_usage(trial, cache_writes=True)['cache_write_input_count'])
        for invalid in (71, True, 'invalid'):
            trial['agent_result']['metadata']['cache_write_input_count'] = invalid
            with self.assertRaises(ValueError):
                skill_evidence.custom_usage(trial, cache_writes=True)

    def test_pricing_applies_cache_reads_writes_and_only_available_context_evidence(self):
        prices = check_pricing(read_profile(SELECTOR)['resolved'])
        self.assertEqual(prices['short']['estimated_usd'], .000735)
        self.assertEqual(prices['boundary']['estimated_usd'], .544135)
        self.assertEqual(prices['cumulative_long_upper_bound']['estimated_usd'], 1.088124)
        self.assertIsNone(prices['missing']['estimated_usd'])
