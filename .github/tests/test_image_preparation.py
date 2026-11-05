"""Pinned owning-runtime package preparation; mocked lifecycle, real staging."""

import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))
RUNTIME = os.environ.get('IMAGE_PREPARATION_RUNTIME',
                         'candidate' if os.environ.get('CANDIDATE_EVIDENCE_CHILD') == '1' else '')


@unittest.skipUnless(RUNTIME in ('candidate', 'retained'), 'explicit owning-runtime qualification only')
class ImagePreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import prepare_candidate_images as preparation
        cls.preparation = preparation
        cls.temporary = tempfile.TemporaryDirectory(prefix='image-runtime-controls-')
        cls.root = Path(cls.temporary.name)
        cls.task = preparation.staged_task(cls.root / 'source', runtime=RUNTIME)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='image-preparation-case-')
        self.addCleanup(self.scratch.cleanup)
        self.output = Path(self.scratch.name)

    def environment(self, failure=None):
        return SimpleNamespace(start=AsyncMock(side_effect=failure), stop=AsyncMock(), setup=AsyncMock(),
            exec=AsyncMock(return_value=SimpleNamespace(return_code=0, stdout='7.6.9\n6.2.0\n')))

    def test_preparation_uses_exact_owning_pair_and_original_staged_bytes(self):
        p = self.preparation
        env = self.environment()
        with patch.object(p, 'staged_task', return_value=self.task), \
                patch.object(p, 'SkillEvaluatorSecureDockerEnvironment', return_value=env), \
                patch.object(p.subprocess, 'check_output', return_value=''):
            result = asyncio.run(p.prepare(self.output, self.output / 'status.json', runtime=RUNTIME))
        self.assertEqual(result['runtime'], p.RUNTIMES[RUNTIME])
        self.assertEqual(result['status'], 'prepared')
        self.assertEqual(result['qualification_context'], 'cache_prepared')
        self.assertEqual(result['teardown'], 'complete')
        env.exec.assert_awaited_once_with(p.RUNTIME_COMMAND, user='root', timeout_sec=20)
        env.setup.assert_not_awaited()

    def test_wrong_runtime_rejects_before_staging_or_docker(self):
        p = self.preparation
        other = 'retained' if RUNTIME == 'candidate' else 'candidate'
        artifact = self.output / 'status.json'
        with patch.object(p, 'staged_task') as stage, patch.object(p, 'SkillEvaluatorSecureDockerEnvironment') as create:
            with self.assertRaisesRegex(RuntimeError, 'Unqualified'):
                asyncio.run(p.prepare(self.output, artifact, runtime=other))
        stage.assert_not_called(); create.assert_not_called()
        self.assertEqual(json.loads(artifact.read_text())['status'], 'infrastructure_error')

    def test_transient_retries_wait_and_use_new_fully_torn_down_environments(self):
        p = self.preparation
        message = ('Docker compose command failed: E: Failed to fetch https://snapshot.debian.org/pkg '
                   '503 No healthy backends\napt-get failed: exit code: 100')
        environments = [self.environment(RuntimeError(message)), self.environment(RuntimeError(message)), self.environment()]
        with patch.object(p, 'staged_task', return_value=self.task), \
                patch.object(p, 'SkillEvaluatorSecureDockerEnvironment', side_effect=environments) as create, \
                patch.object(p.subprocess, 'check_output', return_value=''), \
                patch.object(p.asyncio, 'sleep', new_callable=AsyncMock) as sleep:
            result = asyncio.run(p.prepare(self.output, self.output / 'status.json', runtime=RUNTIME))
        self.assertEqual(create.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.await_args_list], [30, 60])
        self.assertEqual([a['status'] for a in result['attempts']], ['infrastructure_error', 'infrastructure_error', 'prepared'])
        for env in environments:
            env.start.assert_awaited_once_with(force_build=True)
            env.stop.assert_awaited_once_with(delete=True)
            env.setup.assert_not_awaited()
        self.assertTrue(all(a['teardown'] == 'complete' for a in result['attempts']))
