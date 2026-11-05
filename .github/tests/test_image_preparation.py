"""Pinned owning-runtime package preparation; mocked lifecycle, real staging."""

import asyncio
import hashlib
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
                patch.object(p, 'observed_environment', side_effect=lambda base, _entry: base), \
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
                patch.object(p, 'observed_environment', side_effect=lambda base, _entry: base), \
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

    def test_launcher_forwards_verified_compose_identity_into_isolated_preparation(self):
        import qualify_evaluator_candidate as harness
        p = self.preparation
        plugin = self.output / 'compose'
        directory = plugin / 'cli-plugins'; directory.mkdir(parents=True)
        binary = directory / 'docker-compose'; binary.write_bytes(b'reviewed-fixture')
        project = self.output / 'project'
        scripts = project / '.github/scripts'; scripts.mkdir(parents=True)
        (scripts / 'setup-compose.sh').write_text('compose_sha256=' + hashlib.sha256(binary.read_bytes()).hexdigest() + '\n')
        verified = []
        validate = harness.native_compose_config
        def admit(_project):
            verified.append(validate(project))
        async def inspect(root, artifact, suite, arm, shard, runtime):
            self.assertEqual(runtime, RUNTIME)
            self.assertEqual(os.environ['DOCKER_CONFIG'], str(plugin))
            self.assertEqual(os.environ['COMPOSE_PLUGIN_ROOT'], str(plugin))
            self.assertEqual(Path(os.environ['HOME']).parent, root)
            self.assertNotIn('AGENT_REPLACEMENT_COMMAND', os.environ)
            return {'status': 'prepared', 'teardown': 'complete'}
        env = harness.preparation_environment({'PATH': os.environ['PATH'], 'AGENT_REPLACEMENT_COMMAND': 'untrusted'},
                                               str(plugin), self.output)
        with patch.dict(os.environ, env, clear=True), patch.object(harness, 'native_compose_config', side_effect=admit), \
                patch.object(p, 'prepare', side_effect=inspect):
            p.main(self.output / 'admission.json', runtime=RUNTIME)
        self.assertEqual(verified, [str(plugin)])

    def test_command_diagnostics_preserve_hardened_dispatch_without_raw_arguments(self):
        calls = []
        marker = object()
        class Hardened:
            async def _run_docker_compose_command(self, command, *args, **kwargs):
                calls.append((command, args, kwargs))
                return marker
            async def _run_trusted_docker_command(self, command):
                calls.append(command)
                return marker
        entry = {}
        environment = self.preparation.observed_environment(Hardened, entry)()
        async def run():
            self.assertIs(await environment._run_docker_compose_command(['build', 'PRIVATE_PAYLOAD'],
                False, timeout_sec=9, env_overrides={'PRIVATE_KEY': 'PRIVATE_VALUE'}), marker)
            self.assertIs(await environment._run_trusted_docker_command(['PRIVATE_COMMAND']), marker)
        asyncio.run(run())
        self.assertEqual(calls[0], (['build', 'PRIVATE_PAYLOAD'], (False,),
            {'timeout_sec': 9, 'env_overrides': {'PRIVATE_KEY': 'PRIVATE_VALUE'}}))
        self.assertEqual(calls[1], ['PRIVATE_COMMAND'])
        self.assertEqual([(e['kind'], e['operation'], e['status']) for e in entry['commands']],
                         [('compose', 'build', 'complete'), ('docker', 'other', 'complete')])
        self.assertNotIn('PRIVATE', json.dumps(entry))
        async def overflow():
            for _ in range(40):
                await environment._run_trusted_docker_command(['PRIVATE_COMMAND'])
        asyncio.run(overflow())
        self.assertEqual(len(entry['commands']), 32)
        self.assertTrue(entry['commands_truncated'])
        self.assertNotIn('PRIVATE', json.dumps(entry))

    def test_timed_out_command_retains_phase_and_propagates_cancellation(self):
        class Hardened:
            async def _run_docker_compose_command(self, command):
                await asyncio.Future()
        entry = {}
        environment = self.preparation.observed_environment(Hardened, entry)()
        async def run():
            with self.assertRaises(TimeoutError):
                await asyncio.wait_for(environment._run_docker_compose_command(['build']), timeout=0.01)
        asyncio.run(run())
        self.assertEqual(entry['commands'][0]['operation'], 'build')
        self.assertEqual(entry['commands'][0]['status'], 'cancelled')
        self.assertGreater(entry['commands'][0]['elapsed_sec'], 0)

    def test_candidate_build_progress_is_bounded_and_chains_the_original_callback(self):
        calls = []
        marker = object()
        async def original(text, stream):
            calls.append((text, stream))
        class Hardened:
            async def _run_docker_compose_command(self, command, check=True, on_output=None):
                self.command = command
                await on_output('RUN apt-get install PRIVATE_PAYLOAD\nsnapshot.debian.org 50', 'stdout')
                await on_output('3 Service Unavailable PRIVATE_VALUE\n', 'stdout')
                return marker
        entry = {}
        environment = self.preparation.observed_environment(Hardened, entry)()
        result = asyncio.run(environment._run_docker_compose_command(['build'], False, original))
        self.assertIs(result, marker)
        self.assertEqual(environment.command, ['build'])
        self.assertEqual(len(calls), 2)
        self.assertEqual(entry['commands'][0]['build_progress'],
                         {'stage': 'package_install', 'debian_snapshot': True, 'http_503': True})
        self.assertNotIn('PRIVATE', json.dumps(entry))
        self.assertNotIn('snapshot.debian.org', json.dumps(entry))

    def test_build_deadline_retries_only_after_complete_cleanup_and_never_after_integrity_failure(self):
        p = self.preparation
        for fault in ('none', 'cleanup', 'integrity'):
            with self.subTest(fault=fault):
                events, instances = [], []
                class Hardened:
                    def __init__(self, **kwargs):
                        self.number = len(instances) + 1
                        instances.append(self)
                    async def start(self, force_build):
                        events.append(('start', self.number))
                        await self._run_docker_compose_command(['build'])
                    async def _run_docker_compose_command(self, command, on_output=None):
                        if self.number == 1:
                            if fault == 'integrity':
                                await on_output('Hash Sum mismatch PRIVATE_DATA', 'stdout')
                            await asyncio.Future()
                    async def stop(self, delete):
                        self.assert_delete = delete
                        events.append(('stop', self.number))
                        if fault == 'cleanup':
                            raise OSError('controlled teardown failure')
                    async def exec(self, command, **kwargs):
                        return SimpleNamespace(return_code=0, stdout='7.6.9\n6.2.0\n')
                    async def setup(self):
                        raise AssertionError('Preparation must never enter agent setup')
                artifact = self.output / (fault + '.json')
                with patch.object(p, 'staged_task', return_value=self.task), \
                        patch.object(p, 'SkillEvaluatorSecureDockerEnvironment', Hardened), \
                        patch.object(p, 'BUILD_ATTEMPT_SECONDS', 0.02), \
                        patch.object(p.asyncio, 'sleep', new_callable=AsyncMock), \
                        patch.object(p.subprocess, 'check_output', return_value=''):
                    if fault == 'none':
                        result = asyncio.run(p.prepare(self.output, artifact, runtime=RUNTIME))
                        self.assertEqual(result['status'], 'prepared')
                        self.assertEqual(events, [('start', 1), ('stop', 1), ('start', 2), ('stop', 2)])
                        self.assertEqual(result['attempts'][0]['code'], 'build_timeout')
                        self.assertEqual(result['attempts'][0]['commands'][0]['status'], 'timed_out')
                    else:
                        with self.assertRaises((TimeoutError, OSError)):
                            asyncio.run(p.prepare(self.output, artifact, runtime=RUNTIME))
                        self.assertEqual(len(instances), 1)
                        self.assertEqual(json.loads(artifact.read_text())['status'], 'infrastructure_error')
                self.assertNotIn('PRIVATE_DATA', artifact.read_text())
