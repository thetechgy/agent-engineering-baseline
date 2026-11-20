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
sys.path.insert(0, str(ROOT / '.github/scripts'))
import evaluator_profiles as profiles
import skill_evidence as evidence


class StaticQualityRoutingTests(unittest.TestCase):
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
        for selector in ('quality-next', 'quality-candidate'):
            self.assertIn('setup-skillevaluator.sh ' + selector, comparison['run'])
            self.assertEqual(body.count('setup-skillevaluator.sh ' + selector), 1)
        self.assertNotIn('SKILL_EVALUATOR_PYTHON', body)
        self.assertNotIn('gh_container_validation', body)
        for step in quality['steps']:
            if 'skill_reports.py' in step.get('run', '') and 'preflight' not in step['run']:
                self.assertIn('"$SKILL_QUALITY_PYTHON" -B "$STATIC_QUALITY_SCRIPTS/skill_reports.py"', step['run'])
        self.assertIn('bash "$STATIC_QUALITY_SCRIPTS/collect-static-quality.sh"', body)
        publisher = yaml.safe_load((ROOT / '.github/workflows/publish-skill-report.yml').read_text())['jobs']
        prepare = '\n'.join(step.get('run', '') for step in publisher['prepare']['steps'])
        self.assertIn('static_quality_ci.py tools', prepare)
        self.assertIn('"$SKILL_NEXT_PYTHON" -B "$STATIC_QUALITY_SCRIPTS/skill_pages.py" prepare', prepare)
        commit = '\n'.join(step.get('run', '') for step in publisher['commit']['steps'])
        self.assertIn('python3 .github/scripts/skill_pages.py commit', commit)
        setup = next(step for step in contracts['steps'] if 'setup-skillevaluator' in step.get('run', ''))
        self.assertEqual(setup['run'], 'bash .github/scripts/setup-skillevaluator.sh quality')
        native = [step for job in jobs.values() for step in job.get('steps', [])
                  if 'gh_container_validation.py' in step.get('run', '')]
        self.assertEqual(len(native), 1)
        self.assertIn(native[0], contracts['steps'])
        self.assertIn('"$SKILL_EVALUATOR_PYTHON"', native[0]['run'])
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
        scripts = Path(os.environ.get('STATIC_QUALITY_SCRIPTS', ROOT / '.github/scripts'))
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
