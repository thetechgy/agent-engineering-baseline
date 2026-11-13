"""Fixed-cohort scheduling/accounting/trust boundaries. Hosted native fixtures own readiness."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))
import codex_pilot as pilot
import codex_pilot_cohort as cohort
import codex_pilot_dispatch as dispatch
import codex_pilot_effectiveness as effect
import skill_reports as reports


class Boundaries(unittest.TestCase):
    def test_accounting_is_once_per_launch_and_blocks_unknown_nonfinite_and_negative(self):
        rows = [{**r, 'state':'unlaunched'} for r in effect.schedule()]
        self.assertEqual(cohort.accounting(rows), 0)
        for i in range(2): rows[i].update(state='completed', usage={'estimated_usd': 5})
        self.assertEqual(cohort.accounting(rows), 10)
        for value in (None, float('nan'), float('inf'), -1, True):
            rows[1]['usage']['estimated_usd'] = value
            with self.assertRaises(ValueError): cohort.accounting(rows)

    def test_decimal_threshold_is_not_bypassed_by_binary_float_addition(self):
        rows=[{'state':'completed','usage':{'estimated_usd':9.0}}]+[
            {'state':'completed','usage':{'estimated_usd':.1}} for _ in range(10)]
        self.assertEqual(cohort.accounting(rows),10.0)
        self.assertGreaterEqual(cohort.accounting(rows),10)

    def test_same_dispatch_is_claimed_once_even_after_output_deletion(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,RUNNER_TEMP=d,GITHUB_ACTIONS='true'):
            root=Path(d)/'cohort-live';receipt={'allocation':'one-cohort'}
            cohort.claim_dispatch(root,receipt)
            with self.assertRaises(FileExistsError): cohort.claim_dispatch(root,receipt)
            with self.assertRaises(ValueError): cohort.claim_dispatch(Path(d)/'another-output',receipt)

    def test_measured_failure_and_unavailable_conditions_remain_distinct(self):
        audit = [{'cleanup':'complete', 'boundary_after': {'policy_sha256':'x'}}]
        def reason(outcome, usage=0, clean=True, code=0, audits=audit):
            return cohort.stop_reason({}, [{'estimated_usd':usage}], clean, code=code, audits=audits,
                                      grades=[{'classification':outcome}])
        self.assertIsNone(reason('passed')); self.assertIsNone(reason('failed'))
        self.assertEqual(reason('unsupported'), 'unsupported_grading')
        self.assertEqual(reason('timeout'), 'verifier_failure')
        self.assertEqual(reason('infrastructure_error'), 'verifier_failure')
        self.assertEqual(reason('invalid'), 'missing_usable_evidence')
        self.assertEqual(reason('passed', usage=None), 'unknown_usage')
        self.assertEqual(reason('passed', clean=False), 'cleanup_failure')
        self.assertEqual(reason('passed', code=124), 'execution_infrastructure_failure')

    def test_missing_malformed_or_wrong_boundary_never_admits_a_failed_task(self):
        boundary = {key: 'a' * 64 for key in (
            'agent_id', 'controller_id', 'agent_image', 'controller_image', 'policy_sha256')}
        audit = {'boundary_before': copy.deepcopy(boundary), 'boundary_after': copy.deepcopy(boundary)}
        self.assertIsNone(cohort.boundary_stop([audit], [boundary]))
        for audits, finals in (([], [boundary]), ([audit, audit], [boundary]), ([audit], []), ([audit], [boundary, boundary])):
            self.assertEqual(cohort.boundary_stop(audits, finals), 'missing_security_evidence')
        for field in ('boundary_before', 'boundary_after'):
            for bad in (None, {}, [], {'policy_sha256': 'x'}):
                value = copy.deepcopy(audit); value[field] = bad
                self.assertEqual(cohort.boundary_stop([value], [boundary]), 'missing_security_evidence')
        for field in boundary:
            for member in ('boundary_after', 'final'):
                value = copy.deepcopy(audit); final = copy.deepcopy(boundary)
                (value[member] if member != 'final' else final)[field] = 'b' * 64
                self.assertEqual(cohort.boundary_stop([value], [final]), 'security_or_identity_drift')

    def test_exact_allocation_rejects_old_pair_stale_code_and_workflow_rerun(self):
        source = 'a'*40; artifact='123'; nonce='one_dispatch'
        expected=f'cohort-{source}-{cohort.PROTOCOL}-prep{artifact}-usd15-{nonce}'
        with patch.dict(os.environ, GITHUB_RUN_ATTEMPT='1', GITHUB_EVENT_NAME='workflow_dispatch'):
            cohort.allocation(expected, source, artifact, nonce)
            for wrong in ('pilot-'+source+'-usd10', expected.replace(source,'b'*40), expected.replace('usd15','usd10')):
                with self.assertRaises(ValueError): cohort.allocation(wrong, source, artifact, nonce)
        with patch.dict(os.environ, GITHUB_RUN_ATTEMPT='2', GITHUB_EVENT_NAME='workflow_dispatch'):
            with self.assertRaises(ValueError): cohort.allocation(expected, source, artifact, nonce)

    def test_second_dispatch_cannot_reuse_even_a_failed_allocation(self):
        allocation='approved';runs=[{'id':10,'display_title':'Codex cohort approved','run_attempt':1,'event':'workflow_dispatch'},
                                   {'id':11,'display_title':'Codex cohort approved','run_attempt':1,'event':'workflow_dispatch'}]
        dispatch.first_dispatch(runs, allocation, '10')
        with self.assertRaises(ValueError): dispatch.first_dispatch(runs, allocation, '11')
        runs[0]['run_attempt']=2
        with self.assertRaises(ValueError): dispatch.first_dispatch(runs, allocation, '10')

    def test_actual_trial_config_has_one_case_no_multi_attempt_loop_or_context_reuse(self):
        try:
            import importlib.metadata
            if importlib.metadata.version('harbor') != '0.24.0': self.skipTest('Pinned native runtime required')
        except importlib.metadata.PackageNotFoundError: self.skipTest('Pinned native runtime required')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);paths=[]
            for row in effect.schedule():
                config, trial=cohort.launch_config(root,row,root/'tasks'/row['arm']/row['case'])
                value=reports.read_json(config);paths.append(trial)
                self.assertEqual(value['task']['path'],str(root/'tasks'/row['arm']/row['case']))
                self.assertEqual(value['agent']['import_path'],'codex_pilot_agent:PilotCodex')
                self.assertEqual(value['environment']['import_path'],'codex_pilot_environment:PilotEnvironment')
                self.assertIsNone(value['source_trial'])
                self.assertEqual(value['timeout_multiplier'],1)
                self.assertNotIn('n_attempts',value)
                self.assertEqual(value['agent']['kwargs'],{'version':'0.167.0','reasoning_effort':'high'})
            self.assertEqual(len(set(paths)),12)

    @unittest.skipUnless(os.environ.get('APM_EXECUTABLE') and __import__('shutil').which('docker'), 'Native Docker/APM metadata transport')
    def test_native_equal_metadata_case_switches_bind_actual_verifier_inputs(self):
        import hashlib
        import importlib.metadata
        import shutil
        if importlib.metadata.version('skillevaluator') != '0.8.0': self.skipTest('Owning pinned runtime required')
        from qualify_evaluator_candidate import run_native, native_compose_config
        from harbor.models.task.task import Task
        cohort.no_credentials()
        reviewed = Path(native_compose_config(ROOT))
        root = Path(os.environ['RUNNER_TEMP']) / 'verifier-metadata-diagnostic'
        root.mkdir(exist_ok=False)
        # Own a separate copy of the already-verified plugin. Docker may create
        # client state; the following preparation still needs its fresh config.
        config_root = root / 'compose'; (config_root / 'cli-plugins').mkdir(parents=True)
        plugin = config_root / 'cli-plugins/docker-compose'
        shutil.copyfile(reviewed / 'cli-plugins/docker-compose', plugin); plugin.chmod(0o755)
        with patch.dict(os.environ, DOCKER_CONFIG=str(config_root), COMPOSE_PLUGIN_ROOT=str(config_root)):
            native_compose_config(ROOT)
            _, tasks, captured = cohort.staged(root)
            expected = {(r['arm'], r['case_id']): r for r in captured}
            stamp = 1_700_000_000_000_000_000
            for arm, arm_tasks in tasks.items():
                for task in arm_tasks:
                    # Include copied metadata too: fresh mtimes must not be the fix.
                    for metadata in (task / 'tests').rglob('*.json'):
                        os.utime(metadata, ns=(stamp, stamp))
                    self.assertEqual(Task(task).checksum, expected[arm, task.name]['task_checksum'])
            baseline = pilot.resources()
            sequence = [('pester-003', 'without_skill'), ('pester-004', 'without_skill'),
                        ('pester-003', 'without_skill'), ('pester-004', 'with_skill')]
            for position, (case, arm) in enumerate(sequence, 1):
                row = {'position': position, 'trial': position, 'case': case, 'arm': arm}
                task = next(t for t in tasks[arm] if t.name == case)
                target, trial = cohort.launch_config(root, row, task)
                config = reports.read_json(target)
                config['trial_name'] = config['trial_name'].replace('cohort-', 'metadata-', 1)
                trial = trial.parent / config['trial_name']; reports.write_json(target, config)
                environment = {k:v for k,v in os.environ.items() if not k.startswith(('CODEX_', 'ANTHROPIC_', 'NVIDIA_', 'SKILL_EVAL_', 'AEB_'))
                               and k not in ('GH_TOKEN', 'GITHUB_TOKEN', 'OPENAI_BASE_URL')}
                environment.update(PYTHONPATH=str(ROOT / '.github/scripts'), PYTHON_DOTENV_DISABLED='1', HARBOR_TELEMETRY='0',
                    AEB_PILOT_PROBE='1', AEB_COHORT_FIXTURE=case + ('-external' if case == 'pester-003' else '-explicit'),
                    AEB_PILOT_SCENARIO='success')
                with (root / 'launches' / f'{position:02}.log').open('w') as log:
                    code = run_native([str(Path(sys.executable).parent / 'harbor'), 'trials', 'start', '--config', str(target)],
                                      env=environment, log=log, timeout=1200)
                clean = pilot.resources() == baseline
                self.assertTrue(clean, 'Metadata diagnostic cleanup failed; stop')
                self.assertEqual(code, 0)
                observation = reports.read_json(trial / 'operator/pilot-verifier-observation.json')
                expected_files = {'/' + k: v.removeprefix('sha256:') for k,v in expected[arm, case]['members'].items()
                                  if k.startswith(('tests/case/', 'tests/verifier/')) or k in ('tests/entry.json', 'tests/test.sh', 'tests/Runner.ps1')}
                actual_files = {k:v['sha256'] for k,v in observation['observation']['files'].items() if k.startswith('/tests/')}
                reward = reports.read_json(trial / 'verifier/skill_evaluator_reward.json')
                entry = task / 'tests/entry.json'
                native = reports.read_json(trial / 'result.json')
                print(json.dumps({'source_revision': cohort.revision(), 'position': position, 'case': case, 'arm': arm,
                    'host_entry': {'sha256': hashlib.sha256(entry.read_bytes()).hexdigest(), 'bytes': entry.stat().st_size,
                                   'mtime_ns': entry.stat().st_mtime_ns, 'json': reports.read_json(entry)},
                    'trial': {k: native[k] for k in ('id', 'trial_name', 'task_name', 'task_checksum')},
                    'produced_submission': reports.read_json(trial / 'agent/pilot-produced-submission.json'),
                    'verified_submission': reports.read_json(trial / 'verifier/pilot-verified-submission.json'),
                    'host_metadata_files': {p.relative_to(task).as_posix(): {'sha256': pilot.sha(p),
                        'bytes': p.stat().st_size, 'mtime_ns': p.stat().st_mtime_ns} for p in (task / 'tests').rglob('*.json')},
                    'verifier_dockerfile_sha256': pilot.sha(task / 'tests/Dockerfile'),
                    'expected_files': expected_files, 'verifier': observation, 'reward_entry': reward.get('entry_id'),
                    'cleanup_complete': clean}), flush=True)
                # Compare all actual protected inputs, not just the result number
                # or a correct host-side case file. Stop immediately on mismatch.
                self.assertEqual(actual_files, expected_files)
                self.assertEqual(reward['entry_id'], case)

    def test_archive_rejects_wrong_digest_and_path_traversal(self):
        import hashlib
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);archive=root/'a.zip'
            with zipfile.ZipFile(archive,'w') as z: z.writestr('../escape','not executable')
            metadata={'size_in_bytes':archive.stat().st_size,'digest':'sha256:'+hashlib.sha256(archive.read_bytes()).hexdigest()}
            with self.assertRaises(ValueError): dispatch.extract(archive,root/'out',metadata)
            metadata['digest']='sha256:'+'0'*64
            with self.assertRaises(ValueError): dispatch.extract(archive,root/'out2',metadata)
            self.assertFalse((root/'escape').exists())

    def test_preparation_rejects_wrong_protocol_and_identity_before_native_launch(self):
        # The real hosted consumer covers full successful consumption. These are
        # deliberately wrong data, rejected before credentials or any trial.
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);reference=root/'ref';staging=root/'stage'
            reports.write_json(reference/'frozen-proposal.json',{'qualified_revision':'0'*40,'protocol':{'id':'wrong'}})
            reports.write_json(reference/'qualification.json',{'complete':True,'inference':False,'revision':'0'*40})
            with patch.object(cohort.profiles,'runtime'), self.assertRaises(ValueError): cohort.check(reference,staging)
            reports.write_json(reference/'qualification.json',{'complete':False})
            with patch.object(cohort.profiles,'runtime'), self.assertRaises(ValueError): cohort.check(reference,staging)

    def test_existing_retention_keeps_cached_input_separate_and_unknown_usage_unknown(self):
        try:
            import importlib.metadata
            if importlib.metadata.version('skillevaluator') != '0.8.0': self.skipTest('Owning runtime required')
        except importlib.metadata.PackageNotFoundError: self.skipTest('Owning runtime required')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);artifact=root/'evidence';artifact.mkdir()
            path=root/'jobs/trial/result.json'
            reports.write_json(path,{'trial_name':'one','agent_result':{'n_input_tokens':100000,'n_cache_tokens':20000,'n_output_tokens':30000}})
            usage=pilot.retain(root,artifact,probe=True)
            self.assertAlmostEqual(usage[0]['estimated_usd'],.462)
            self.assertEqual(usage[0]['n_cache_tokens'],20000)
            reports.write_json(path,{'trial_name':'one','agent_result':{'n_input_tokens':100000,'n_output_tokens':30000}})
            self.assertIsNone(pilot.retain(root,artifact,probe=True)[0]['estimated_usd'])
            reports.write_json(path,{'trial_name':'one','agent_result':{'n_input_tokens':1,'n_cache_tokens':2,'n_output_tokens':0}})
            with self.assertRaises(ValueError): pilot.retain(root,artifact,probe=True)

    def test_existing_output_claim_prevents_relaunch_without_touching_runtime(self):
        with tempfile.TemporaryDirectory() as d, patch.object(cohort,'staged') as staging:
            with self.assertRaises(FileExistsError): cohort.execute(Path(d),Path(d)/'missing',fixture='complete')
            staging.assert_not_called()

    def test_cohort_probe_is_separate_from_live_effectiveness_in_public_reporting(self):
        import skill_analysis as analysis
        record={'custom':{'purpose':'skill_effectiveness_probe'},'policy':{}}
        self.assertIn('Credential-free', analysis.coverage_label({'behavioral_results':[record]}))
        record['custom']['purpose']='skill_effectiveness'
        self.assertIn('Prospective exploratory',analysis.coverage_label({'behavioral_results':[record]}))


if __name__ == '__main__': unittest.main()
