"""Opt-in candidate controls supplement the unchanged production evidence cases."""

import json
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class CandidateHarnessTests(unittest.TestCase):
    def test_native_compose_accepts_only_the_reviewed_credential_free_directory(self):
        project = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location('candidate_harness', project / '.github/scripts/qualify_evaluator_candidate.py')
        harness = importlib.util.module_from_spec(spec); spec.loader.exec_module(harness)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); plugin = root / 'plugin'; plugins = plugin / 'cli-plugins'
            plugins.mkdir(parents=True)
            binary = plugins / 'docker-compose'; binary.write_bytes(b'reviewed-fixture-binary')
            source = root / 'project/.github/scripts'; source.mkdir(parents=True)
            (source / 'setup-compose.sh').write_text('compose_sha256=' + hashlib.sha256(binary.read_bytes()).hexdigest() + '\n')
            with patch.dict(os.environ, {'COMPOSE_PLUGIN_ROOT': str(plugin), 'DOCKER_CONFIG': str(plugin)}):
                self.assertEqual(harness.native_compose_config(root / 'project'), str(plugin))
                # A Docker auth/config file must never enter the native child.
                (plugin / 'config.json').write_text('{"auths": {"dummy.invalid": "dummy"}}')
                with self.assertRaises(ValueError): harness.native_compose_config(root / 'project')
                (plugin / 'config.json').unlink()
                binary.write_bytes(b'altered')
                with self.assertRaises(ValueError): harness.native_compose_config(root / 'project')
                binary.unlink(); binary.symlink_to(source / 'setup-compose.sh')
                with self.assertRaises(ValueError): harness.native_compose_config(root / 'project')

    def test_repository_runtime_cannot_silently_adopt_the_candidate(self):
        project = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'must-not-be-created'
            result = subprocess.run([sys.executable, '-I', '-B',
                str(project / '.github/scripts/qualify_evaluator_candidate.py'),
                '--source', str(project), '--output', str(output)],
                env={'PATH': os.environ['PATH']}, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn('candidate', result.stderr.lower())
            self.assertFalse(output.exists())

    def test_adoption_cannot_skip_scoring_preservation_with_an_unpatched_source(self):
        project = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'must-not-be-created'
            result = subprocess.run([sys.executable, '-I', '-B',
                str(project / '.github/scripts/qualify_evaluator_candidate.py'),
                '--source', str(project), '--output', str(output), '--adoption', '--unpatched'],
                env={'PATH': os.environ['PATH']}, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 2)
            self.assertIn('Scoring qualification requires the reviewed candidate patch', result.stderr)
            self.assertFalse(output.exists())


@unittest.skipUnless(os.environ.get('CANDIDATE_EVIDENCE_CHILD') == '1', 'opt-in candidate qualification only')
class CandidateEvidenceTests(unittest.TestCase):
    def test_only_bundled_offline_verifiers_accept_literal_network_none(self):
        from skillevaluator.tier3.harbor import adapter
        from harbor.environments.docker.docker import DockerEnvironment
        import pester_container_validation as qualification
        import pester_evaluations as pilot
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate, fixtures = qualification.qualification_bundle(root / 'candidate', candidate=True)
            production, _ = qualification.qualification_bundle(root / 'production')
            for case in fixtures:
                candidate_tests = candidate / 'evals/harbor' / case / 'tests'
                production_tests = production / 'evals/harbor' / case / 'tests'
                actual = pilot.manifest(candidate_tests); actual.pop('docker-compose.yaml')
                self.assertEqual(actual, pilot.manifest(production_tests), 'Verifier payload must be identical')
            for present in (True, False):
                tasks = adapter.stage_native_harbor_tasks(candidate, root / str(present), with_skill=present, grading_mode='custom_only')
                self.assertEqual(len(tasks), 26)
                for task in tasks:
                    compose = task / 'tests/docker-compose.yaml'
                    native = SimpleNamespace(_user_compose_paths=lambda: [compose])
                    self.assertEqual(DockerEnvironment._egress_controlled_service_names(native), [])
            # A verifier whose configured baseline permits networking cannot
            # acquire the exception just by authoring an offline-looking file.
            config = candidate / 'evals/harbor/pester-001-classic/task.toml'
            config.write_text(config.read_text().replace('network_mode = "no-network"', 'network_mode = "public"'))
            with self.assertRaisesRegex(ValueError, 'main.*may set only'):
                adapter.stage_native_harbor_tasks(candidate, root / 'public-verifier', with_skill=False, grading_mode='custom_only')
            config.write_text(config.read_text().replace('network_mode = "public"', 'network_mode = "no-network"', 1))
            agent_compose = candidate / 'evals/harbor/pester-001-classic/environment/docker-compose.yaml'
            agent_compose.write_text('services:\n  main:\n    network_mode: none\n')
            with self.assertRaisesRegex(ValueError, 'main.*may set only'):
                adapter.stage_native_harbor_tasks(candidate, root / 'agent-override', with_skill=False, grading_mode='custom_only')
            compose = root / 'docker-compose.yaml'
            compose.write_text('services:\n  main:\n    network_mode: none\n')
            # Ordinary agent Compose contexts keep the original restriction.
            with self.assertRaisesRegex(ValueError, 'main.*may set only'):
                adapter._validate_and_sanitize_custom_compose(compose, allowed_env=set())
            for value in ('host', 'bridge', 'service:sidecar', 'container:other', '${MODE}', None, [], {}):
                compose.write_text(json.dumps({'services': {'main': {'network_mode': value}}}))
                with self.assertRaises(ValueError):
                    adapter._validate_and_sanitize_custom_compose(compose, allowed_env=set(), allow_offline_main=True)
            for key, value in (('networks', []), ('privileged', True), ('cap_add', ['NET_ADMIN']),
                               ('security_opt', ['seccomp:unconfined']), ('entrypoint', ['sh']),
                               ('healthcheck', {'test': ['CMD', 'true']}), ('volumes', ['/host:/container'])):
                compose.write_text(json.dumps({'services': {'main': {'network_mode': 'none', key: value}}}))
                with self.assertRaises(ValueError):
                    adapter._validate_and_sanitize_custom_compose(compose, allowed_env=set(), allow_offline_main=True)

    def test_unknown_attribution_preserves_summary_bounds_and_unknown_counts(self):
        from skillevaluator.tier3.harbor import collector
        total = collector.PUBLISHED_CASE_DETAILS_MAX + 3
        good = [{'entry_id': str(i), 'details': {'security': {'findings': []}}} for i in range(total)]
        unknown = [{'entry_id': str(i), 'evaluation_status': 'failed', 'details': None} for i in range(total)]
        result = collector._annotate_security_attribution(good, unknown)
        self.assertEqual(len(result['cases']), collector.PUBLISHED_CASE_DETAILS_MAX)
        self.assertEqual(result['case_details_total'], total)
        self.assertTrue(result['case_details_truncated'])
        self.assertEqual(result['skill_may_have_improved_safety'], 0)
        for case in result['cases'].values():
            self.assertEqual(case['status'], 'unknown_execution_evidence')
            self.assertIsNone(case['with_skill_findings'])
            self.assertIsNone(case['baseline_findings'])

    def test_unlinked_output_remains_secret_evidence_without_execution_attribution(self):
        from skillevaluator.tier3.eval_core.atif_helpers import extract_tool_calls_as_dicts
        from skillevaluator.tier3.eval_core.checks import check_security
        for function, arguments in (
            ('exec_command', {'cmd': 'true'}),
            ('exec', {'input': 'const r = await tools.exec_command({cmd:"true"}); text(r.output);'}),
        ):
            call = {'function_name': function, 'tool_call_id': 'issued', 'arguments': arguments}
            trajectory = {'steps': [{'source': 'agent', 'tool_calls': [call, {**call, 'tool_call_id': 'other'}],
                'observation': {'results': [{'content': 'Authorization: Bearer sk-abcdefgh12345678'}]}}]}
            calls = extract_tool_calls_as_dicts(trajectory)
            self.assertTrue(all(c['observation_status'] == 'unobserved_inner_call' for c in calls))
            self.assertTrue(all(c['observation'] == '' for c in calls))
            self.assertEqual([f['type'] for f in check_security(calls)['findings']].count('secret_exposure'), 1)

    def test_staged_verifier_needs_no_installed_skillevaluator(self):
        from skillevaluator.tier3.harbor import adapter
        script = '''
import importlib.util, json, sys
sys.path.insert(0, sys.argv[1])
class NoInstalledPackage:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'skillevaluator' or fullname.startswith('skillevaluator.'):
            raise ModuleNotFoundError('Installed package access forbidden')
sys.meta_path.insert(0, NoInstalledPackage())
spec = importlib.util.spec_from_file_location('staged_eval', sys.argv[1] + '/eval.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
calls = [{'action': 'exec_command', 'action_input': {'cmd': 'curl --unix-socket /run/podman/podman.sock http://localhost/containers/json'}}]
result = verifier.check_security({'steps': []}, calls)
assert result['passed'] is False, result
calls[0]['action_input']['cmd'] = 'mystery /var/run/docker.sock'
assert verifier.check_security({'steps': []}, calls)['supported'] is False
'''
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            adapter._copy_verifier(root)
            staged = root / 'tests' / adapter._EVALUATOR_TESTS_SUBDIR
            result = subprocess.run([sys.executable, '-I', '-B', '-c', script, str(staged)],
                                    env={'PATH': os.environ['PATH']}, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_diagnosis_is_a_fixed_enum_without_arbitrary_evidence(self):
        from skillevaluator.tier3.harbor import collector
        for status in ('passed', 'failed', 'invalid', 'timeout', 'unsupported', 'infrastructure_error'):
            details = {'outcome': {'classification': status, 'secret': 'dummy-private-data'},
                       'unvalidated_metric': {'score': 1.0}}
            reward = {'evaluation_status': 'failed', 'custom_details': details}
            safe = collector._sanitize_reward_metric_surfaces(reward)
            expected = {'outcome': {'classification': status}}
            self.assertEqual(safe['custom_details'], expected)
            collector._restore_custom_metric_details(reward, safe)
            self.assertEqual(safe['custom_details'], expected)
            self.assertFalse(collector.extract_custom_metrics(safe))
        for value in ('dummy-private-data', 0, None, {}, [], {'classification': 'unsupported', 'extra': 1}):
            self.assertEqual(collector._custom_outcome_diagnosis({'outcome': {'classification': value}}), {})
        # A legitimate metric named outcome keeps the upstream evidence path.
        reward = {'custom_metrics': {'outcome': 1.0}, 'custom_details': {
            'outcome': {'classification': 'passed', 'explanation': 'validated metric detail'}}}
        safe = collector._sanitize_reward_metric_surfaces(reward)
        self.assertEqual(safe['custom_details'], reward['custom_details'])
        collector._restore_custom_metric_details(reward, safe)
        self.assertEqual(safe['custom_details'], reward['custom_details'])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'custom_reward.json').write_text(json.dumps({
                'custom_metrics': reward['custom_metrics'], 'details': reward['custom_details']}))
            merged = {}
            collector._merge_reward_sidecars(merged, root)
            self.assertEqual(merged['custom_details'], reward['custom_details'])

    def test_missing_and_unlinked_results_stop_before_judges(self):
        from skillevaluator.tier3.harbor.templates import eval as verifier
        for results in ([], [{'source_call_id': 'other', 'content': 'success'}], [{'content': 'success'}]):
            trajectory = {'steps': [{'source': 'agent', 'tool_calls': [{
                'function_name': 'exec_command', 'tool_call_id': 'issued', 'arguments': {'cmd': 'true'}}],
                'observation': {'results': results}}]}
            with self.subTest(results=results), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / 'entry.json').write_text(json.dumps({'id': 'synthetic', 'expected_skill': 'podman'}))
                with patch.multiple(verifier, ENTRY_PATH=root / 'entry.json', REWARD_JSON=root / 'reward.json',
                                    REWARD_TXT=root / 'reward.txt', SKILL_EVALUATOR_REWARD_JSON=root / 'details.json'), \
                        patch.object(verifier, 'load_trajectory_with_fallback', return_value=(trajectory, {'source': 'trajectory.json'})), \
                        patch.object(verifier, 'judge_accuracy', side_effect=AssertionError('No inference')) as accuracy, \
                        patch.object(verifier, 'judge_goal_accuracy', side_effect=AssertionError('No inference')) as goal, \
                        patch.object(verifier, 'judge_behavior_check', side_effect=AssertionError('No inference')) as behavior:
                    with self.assertRaises(SystemExit):
                        verifier.main()
                    accuracy.assert_not_called()
                    goal.assert_not_called()
                    behavior.assert_not_called()
                self.assertEqual(json.loads((root / 'reward.json').read_text()), {'overall': 0.0})
                self.assertEqual(json.loads((root / 'details.json').read_text())['evaluation_status'], 'failed')


if __name__ == '__main__':
    unittest.main()
