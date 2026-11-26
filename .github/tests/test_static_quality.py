"""Static routing must not change retained native/review ownership or use PATH."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
ISOLATED_SCRIPTS = os.environ.get('STATIC_QUALITY_SCRIPTS')
sys.path.insert(0, ISOLATED_SCRIPTS or str(ROOT / '.github/scripts'))
import evaluator_profiles as profiles
import skill_evidence as evidence


class StaticQualityRoutingTests(unittest.TestCase):
    def test_active_scanner_runtime_matches_the_reviewed_semgrep_lock(self):
        import static_evaluator as owner

        lock = ROOT / '.github/requirements/semgrep.txt'
        self.assertEqual(owner.SEMGREP_LOCK, evidence.digest_bytes(lock.read_bytes()))
        self.assertEqual(evidence.SCANNER_RUNTIME_STATIC_CANDIDATE['semgrep_lock'], owner.SEMGREP_LOCK)
        self.assertEqual(evidence.SCANNER_RUNTIME_NEXT['semgrep_lock'], owner.SEMGREP_LOCK)
        self.assertNotEqual(evidence.SCANNER_2136_INITIAL_NEXT['semgrep_lock'], owner.SEMGREP_LOCK)

    def test_static_consumer_and_retained_native_boundary_have_explicit_separate_owners(self):
        jobs = yaml.safe_load((ROOT / '.github/workflows/validate.yml').read_text())['jobs']
        quality = jobs['skill-quality']
        contracts = jobs['ci-contracts']
        body = '\n'.join(step.get('run', '') for step in quality['steps'])
        setup = next(step for step in quality['steps'] if 'setup-static-evaluator.sh' in step.get('run', ''))
        self.assertEqual(setup['run'], 'bash .github/scripts/setup-static-evaluator.sh quality-static')
        self.assertNotIn('if', setup)
        comparison = next(step for step in quality['steps'] if 'qualify_static_evaluator.py' in step.get('run', ''))
        self.assertEqual(comparison['if'], "needs.plan.outputs.static_candidate == 'true'")
        baseline = 'setup-static-evaluator.sh quality-retained-101'
        self.assertIn(baseline, comparison['run'])
        self.assertEqual(body.count(baseline), 1)
        self.assertNotIn('SKILL_EVALUATOR_PYTHON', body)
        self.assertNotIn('gh_container_validation', body)
        for step in quality['steps']:
            if 'skill_reports.py' in step.get('run', '') and 'preflight' not in step['run']:
                self.assertIn('"$SKILL_QUALITY_PYTHON" -B "$STATIC_QUALITY_SCRIPTS/skill_reports.py"', step['run'])
        self.assertIn('bash "$STATIC_QUALITY_SCRIPTS/collect-static-quality.sh"', body)
        scanner_setup = 'bash .github/scripts/setup-static-evaluator.sh scanner-contracts'
        scanner, = [step for step in contracts['steps'] if step.get('run') == scanner_setup]
        self.assertFalse(any(step.get('run') == scanner_setup for step in quality['steps']))
        scanner_tests = next(step for step in contracts['steps'] if ' scanner-contracts' in step.get('run', '')
                             and 'test_evaluation_contracts.py' in step['run'])
        self.assertLess(contracts['steps'].index(scanner), contracts['steps'].index(scanner_tests))
        native = [step for job in jobs.values() for step in job.get('steps', [])
                  if 'gh_container_validation.py' in step.get('run', '')]
        self.assertEqual(len(native), 1)
        self.assertIn(native[0], contracts['steps'])
        self.assertIn('"$SKILL_NATIVE_BENCHMARK_CANDIDATE_PYTHON"', native[0]['run'])
        released_setup = next(step for step in contracts['steps']
                              if 'setup-static-evaluator.sh native-benchmark-candidate' in step.get('run', ''))
        self.assertLess(contracts['steps'].index(released_setup), contracts['steps'].index(native[0]))
        self.assertEqual(quality['permissions'], {'contents': 'read'})
        self.assertEqual(quality['if'], "needs.plan.outputs.quality == 'true'")

    def test_mismatched_owner_or_missing_provenance_refuses_before_collection(self):
        # Execute the production entry point using the opposite recorded owner.
        # A hostile PATH CLI must never be consulted, even after setup is absent.
        import importlib.metadata
        version = importlib.metadata.version('skillevaluator')
        opposite = (dict(python='3.13', skillevaluator='0.3.0', harbor='0.13.2',
                         evaluator_revision=profiles.HISTORICAL_REVISION)
                    if version == '0.9.0' else profiles.candidate_versions(profiles.NEXT))
        runtime = evidence.SCANNER_RUNTIME if version == '0.9.0' else evidence.SCANNER_RUNTIME_NEXT
        opposite.update(scanner_runtime=runtime, scanners=runtime['versions'],
                        skillspector_revision=runtime['skillspector_revision'])
        scripts = Path(ISOLATED_SCRIPTS or ROOT / '.github/scripts')
        for metadata in (None, {}, opposite):
            with self.subTest(metadata=metadata), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                tools = root / 'tools'; tools.mkdir()
                if metadata is not None:
                    (tools / 'versions.json').write_text(json.dumps(metadata))
                binary = root / 'bin'; binary.mkdir()
                marker = root / 'unexpected-cli'
                cli = binary / 'skillevaluator'
                cli.write_text('#!/bin/sh\ntouch "$CLI_MARKER"\nexit 0\n'); cli.chmod(0o700)
                result = subprocess.run(['bash', str(scripts / 'collect-static-quality.sh')],
                    env={'PATH': str(binary) + os.pathsep + os.defpath, 'CLI_MARKER': str(marker),
                         'SKILL_QUALITY_PYTHON': sys.executable, 'SKILL_QUALITY_TOOLS': str(tools),
                         'GITHUB_WORKSPACE': str(ROOT), 'RUNNER_TEMP': str(root / 'runner'),
                         'TMPDIR': os.environ.get('TMPDIR', temporary), 'PYTHONDONTWRITEBYTECODE': '1'},
                    capture_output=True, timeout=30)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(marker.exists())
                self.assertFalse((root / 'runner/skill-quality').exists())


    @unittest.skipUnless(ISOLATED_SCRIPTS, 'Requires isolated static reporting tools')
    def test_pages_history_admits_the_static_producer(self):
        import skill_history as history
        import static_evaluator as owner
        from test_skill_analysis import static_control
        from test_skill_pages import prov

        at = '2026-11-20T00:00:00Z'
        runtimes = (evidence.SCANNER_2136_INITIAL_STATIC, evidence.SCANNER_RUNTIME_STATIC_CANDIDATE)
        for runtime in runtimes:
            with self.subTest(lock=runtime['semgrep_lock']):
                pins = owner.STATIC_OWNERS[runtime['evaluator_revision']]
                record = static_control()
                record['policy'] = evidence.make_policy(
                    {key: pins[key] for key in ('evaluator_revision', 'harbor', 'python')},
                    judge={'model': None, 'provider': None, 'enabled': False},
                    provenance='runtime_recorded', published=pins['producer_profile'])
                record['scanner_runtime'] = runtime
                versions = dict(owner.VERSIONS, scanner_runtime=runtime, scanners=runtime['versions'],
                                skillspector_revision=runtime['skillspector_revision'])
                if pins is owner.VERSIONS:
                    self.assertEqual(evidence.validate_runtime_versions(versions)['version'], owner.VERSION)
                else:
                    with self.assertRaisesRegex(ValueError, 'Missing static candidate scanner provenance'):
                        evidence.validate_runtime_versions(versions)
                snapshot = history.empty(at)
                observation = history.observation(record, 'quality', prov(record['source']['revision']), at)
                history.add(snapshot, observation)
                retained = history.retain(snapshot, at)['observations']
                self.assertEqual(len(retained), 1)
                self.assertEqual(retained[0]['record']['policy']['published_id'], pins['producer_profile'])
                self.assertEqual(retained[0]['record_id'], evidence.identity(record))
                observation['record']['kind'] = 'behavioral'
                with self.assertRaisesRegex(ValueError, 'Static producer policy requires static evidence'):
                    history.validate(snapshot)

        active = evidence.SCANNER_RUNTIME_STATIC_CANDIDATE
        for invalid in (evidence.SCANNER_2136_INITIAL_NEXT, dict(active, semgrep_lock='sha256:' + 'a' * 64)):
            with self.subTest(lock=invalid['semgrep_lock']):
                record['scanner_runtime'] = invalid
                with self.assertRaisesRegex(ValueError, 'scanner runtime|Scanner adapter'):
                    evidence.validate_public(record)
