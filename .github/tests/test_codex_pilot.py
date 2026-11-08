"""Credential-free prospective contract and selection controls for the one-pair pilot."""
import importlib.util
import importlib.metadata
import json
import os
import shutil
import subprocess
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import AsyncMock, patch

CANDIDATE_RUNTIME = bool(importlib.util.find_spec('skillevaluator')) and importlib.metadata.version('skillevaluator') == '0.8.0'
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.github/scripts'))
from codex_pilot_contract import PROFILE, configuration
from codex_pilot_iteration import runner_bytes
import codex_pilot as pilot
import codex_pilot_descriptors as descriptors
import skill_reports as reports
import skill_evidence as evidence


class PilotContracts(unittest.TestCase):
    def test_external_config_preserves_model_provider_and_disables_retries(self):
        c=configuration()
        self.assertEqual((c['model'],c['model_reasoning_effort']),('gpt-6.1-sol','high'))
        self.assertEqual(c['sandbox_mode'],'danger-full-access')
        self.assertNotIn('sandbox_workspace_write',c)
        self.assertEqual(c['model_providers']['pilot']['base_url'],'https://api.openai.com/v1')
        self.assertEqual(c['model_providers']['pilot']['request_max_retries'],0)
        self.assertNotIn('rollout_budget',c['features'])
        probe=configuration('http://127.0.0.1:8765/v1')
        probe['model_providers']['pilot']['base_url']=c['model_providers']['pilot']['base_url']
        self.assertEqual(probe,c)

    def test_runner_correction_is_prospective_and_names_fixed_reasons(self):
        old=(ROOT/'.github/evals/powershell-pester-6/support/Runner.ps1').read_bytes()
        new=runner_bytes()
        self.assertNotEqual(old,new)
        self.assertNotIn(b"'Be', 'BeTrue', 'BeFalse'",old)
        self.assertIn(b"'Be', 'BeTrue', 'BeFalse'",new)
        self.assertIn(b"$__peResult.code = 'test_name_template'",new)
        self.assertIn(b"$__peResult.code = 'command_parameter'",new)
        self.assertIn(b"$__peText.Contains('<') -or $__peText.Contains('>')",new)

    def test_frozen_pilot_has_one_case_one_attempt_and_preserves_active_profile(self):
        self.assertEqual(PROFILE['case'],'pester-001')
        self.assertEqual(PROFILE['attempts_per_arm'],1)
        registry=evidence.custom_registry(ROOT)
        self.assertEqual(registry['active_profiles']['powershell-pester-6'],'pester-pilot-v3')
        profile,_,_=evidence.custom_contract('powershell-pester-6',ROOT,purpose='cli_pilot')
        self.assertEqual(set(profile['cases']),{'pester-001'})
        self.assertEqual(profile['runtime']['codex'],'0.167.0')
        identities=evidence.custom_input_identities(ROOT,'powershell-pester-6',purpose='cli_pilot')
        self.assertTrue(all(profile[k]==v for k,v in identities.items()))

    @unittest.skipUnless(CANDIDATE_RUNTIME,'Requires qualified 0.8.0 owning runtime')
    def test_native_command_has_no_retry_and_exact_runtime(self):
        with tempfile.TemporaryDirectory() as d:
            cmd=pilot.command(Path(d),'with_skill')
        self.assertEqual(cmd[cmd.index('--n-attempts')+1],'1')
        self.assertEqual(cmd[cmd.index('--max-retries')+1],'0')
        self.assertIn('version="0.167.0"',cmd)
        self.assertNotIn('version="0.155.1"',cmd)
        self.assertIn('codex_pilot_agent:PilotCodex',cmd)
        self.assertEqual(cmd[cmd.index('--model')+1],'gpt-6.1-sol')

    @unittest.skipUnless(shutil.which('pwsh'), 'Requires local PowerShell for admission')
    def test_actual_admission_boolean_and_template_controls(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            fixed=root/'Runner.ps1'; fixed.write_bytes(runner_bytes())
            original=ROOT/'.github/evals/powershell-pester-6/support/Runner.ps1'
            profile=ROOT/'.github/evals/powershell-pester-6/support/cases/pester-001/profile.json'
            cases={
                'boolean': ("Describe 'boolean' { It 'asserts' { $true | Should -BeTrue; $false | Should -BeFalse } }", 'admitted', 'ok'),
                'template': ("Describe 'reject <$(1)>' { It 'asserts' { 1 | Should -Be 1 } }", 'unsupported', 'test_name_template'),
                'parameter': ("Describe 'reject' { It 'asserts' { 1 | Should -Be 2 -ErrorAction SilentlyContinue } }", 'unsupported', 'command_parameter'),
                'dynamic': ("Describe 'reject' { It 'asserts' { & 'Get-Content' '/tests/case/profile.json' } }", 'unsupported', 'command_policy'),
            }
            for name,(text,status,code) in cases.items():
                candidate=root/(name+'.ps1');candidate.write_text(text)
                def invoke(runner):
                    result=subprocess.run(['pwsh','-NoLogo','-NoProfile','-NonInteractive','-File',str(runner),'-Candidate',str(candidate),'-Profile',str(profile),'-AdmissionOnly'],capture_output=True,text=True,check=True,timeout=20)
                    return json.loads(result.stdout)
                self.assertEqual(invoke(fixed),{'status':status,'code':code})
                if name=='boolean': self.assertEqual(invoke(original),{'status':'unsupported','code':'admission'})

    @unittest.skipUnless(os.environ.get('APM_EXECUTABLE') and CANDIDATE_RUNTIME, 'Requires verified APM and owning runtime')
    def test_actual_staging_capture_rejects_cohort_runner_and_attempt_drift(self):
        from harbor.models.task.task import Task
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for controls in (False, True):
                target=root/str(controls);target.mkdir()
                bundle,tasks,rows=pilot.stage(target,controls=controls)
                self.assertTrue((target/'evidence/task-descriptors.json').is_file(),
                                'Generated task descriptors must survive the artifact boundary')
                reports.write_json(target/'evidence/staging.json',rows)
                retained=descriptors.verified_configurations(target/'evidence')
                self.assertEqual(set(retained),{(r['arm'],r['case_id']) for r in rows})
                for arm_tasks in tasks.values():
                    for task in arm_tasks:
                        for context in ('environment', 'tests'):
                            self.assertEqual((task/context/'build/install-runtime.py').read_bytes(), pilot.runtime_installer_bytes())
                for row in rows:
                    retained_file=target/'evidence/task-descriptors'/row['arm']/(row['case_id']+'.toml')
                    original=next(t for t in tasks[row['arm']] if t.name==row['case_id'])/'task.toml'
                    self.assertEqual(retained_file.read_bytes(),original.read_bytes())
                purpose='cli_pilot_control' if controls else 'cli_pilot'
                self.assertEqual(len(rows),2 * len(pilot.CONTROLS) if controls else 2)
                if not controls:
                    for arm_tasks in tasks.values():
                        config = tomllib.loads((arm_tasks[0] / 'task.toml').read_text())
                        for phase in ('environment', 'agent'):
                            self.assertEqual(config[phase]['network_mode'], 'allowlist')
                            self.assertEqual(config[phase]['allowed_hosts'], ['api.openai.com'])
                        self.assertEqual(config['verifier']['environment']['network_mode'], 'no-network')
                capture=evidence.custom_capture(ROOT,PROFILE['skill'],bundle,rows,purpose=purpose,
                    attempts=1,agent='oracle' if controls else 'codex',execution_policy={
                    'environment':'docker','concurrency':2,'timeout_multiplier':1.0,'stop_on_pass':False})
                evidence.validate_custom_capture(capture,PROFILE['skill'],ROOT)
                self.assertEqual({Task(t).checksum for arm in tasks.values() for t in arm},{r['task_checksum'] for r in rows})
                capture['attempts']=2
                with self.assertRaisesRegex(ValueError,'attempts drift'):
                    evidence.validate_custom_capture(capture,PROFILE['skill'],ROOT)
                capture['attempts']=1
                capture['case_ids'].append('pester-002')
                with self.assertRaises(ValueError): evidence.validate_custom_capture(capture,PROFILE['skill'],ROOT)

    @unittest.skipUnless(os.environ.get('APM_EXECUTABLE') and CANDIDATE_RUNTIME, 'Requires verified APM and owning runtime')
    def test_live_and_probe_images_match_without_baked_qualification_solution(self):
        import base64
        from codex_pilot_replay import corpus
        _, _, submissions, _ = corpus()
        fixtures=[(ROOT/'.github/evals/powershell-pester-6/support/qualification/pester-001/classic.Tests.ps1').read_bytes(), *submissions.values()]
        forbidden=fixtures+[base64.b64encode(raw) for raw in fixtures]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);images=[]
            for probe in (False,True):
                target=root/str(probe);target.mkdir()
                _,tasks,_=pilot.stage(target,probe=probe)
                manifests={}
                for arm,arm_tasks in tasks.items():
                    environment=arm_tasks[0]/'environment'
                    for path in reports.regular_tree(environment):
                        raw=path.read_bytes()
                        if any(value in raw for value in forbidden):
                            self.fail('Qualification solution leaked into agent build context: '+path.relative_to(environment).as_posix())
                    manifests[arm]=pilot.pester.manifest(environment)
                images.append(manifests)
            self.assertEqual(images[0],images[1], 'Probe/live image bytes must stay identical')

    def test_probe_stub_has_no_default_qualification_payload(self):
        with tempfile.TemporaryDirectory() as d:
            record=Path(d)/'probe.json'
            for extra in ([],['not-valid-base64']):
                result=subprocess.run([sys.executable,'-B',str(ROOT/'.github/scripts/codex_pilot_stub.py'),
                    str(record),'success',*extra],capture_output=True,text=True,timeout=10)
                self.assertNotEqual(result.returncode,0)
                self.assertFalse(record.exists())

    @unittest.skipUnless(CANDIDATE_RUNTIME, 'Requires qualified owning runtime')
    def test_exec_json_usage_keeps_missing_unknown_and_rejects_invalid_counts(self):
        from codex_pilot_agent import PilotCodex
        from harbor.models.agent.context import AgentContext
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); context=AgentContext(); agent=SimpleNamespace(logs_dir=root)
            (root/'codex.txt').write_text('{"type":"turn.failed","error":{"message":"refused"}}\n')
            PilotCodex.populate_context_post_run(agent,context)
            self.assertIsNone(context.n_input_tokens)
            (root/'codex.txt').write_text(json.dumps({'type':'turn.completed','usage':{
                'input_tokens':100,'cached_input_tokens':20,'output_tokens':10}})+'\n')
            PilotCodex.populate_context_post_run(agent,context)
            self.assertEqual((context.n_input_tokens,context.n_cache_tokens,context.n_output_tokens),(100,20,10))
            (root/'codex.txt').write_text(json.dumps({'type':'turn.completed','usage':{
                'input_tokens':100,'cached_input_tokens':101,'output_tokens':10}})+'\n')
            with self.assertRaises(ValueError): PilotCodex.populate_context_post_run(agent,context)

    @unittest.skipUnless(CANDIDATE_RUNTIME, 'Requires qualified owning runtime')
    def test_exact_submission_handoff_rejects_changed_verifier_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);trial=root/'jobs/job/trial';artifact=root/'evidence';artifact.mkdir()
            path=trial/'artifacts/workspace/output/Subject.Tests.ps1';path.parent.mkdir(parents=True)
            path.write_bytes(b"Describe 'proof' { It 'checks' { 1 | Should -Be 1 } }\n")
            receipt={'sha256':pilot.sha(path),'bytes':path.stat().st_size}
            for directory,name in (('agent','pilot-produced-submission.json'),('verifier','pilot-verified-submission.json')):
                target=trial/directory/name;target.parent.mkdir(parents=True);target.write_text(json.dumps(receipt))
            pilot.retain(root,artifact)
            self.assertEqual(next((artifact/'submissions').rglob('Subject.Tests.ps1')).read_bytes(),path.read_bytes())
            (trial/'verifier/pilot-verified-submission.json').write_text(json.dumps({**receipt,'sha256':'0'*64}))
            with self.assertRaisesRegex(ValueError,'handoff mismatch'): pilot.retain(root,artifact)

    @unittest.skipUnless(importlib.util.find_spec('skillevaluator'), 'Requires pinned evidence runtime')
    def test_historical_public_record_cannot_claim_pilot_identity(self):
        from test_custom_metrics import synthetic_native
        with tempfile.TemporaryDirectory() as d:
            native,_=synthetic_native(Path(d),complete=True)
            public=json.loads(evidence.encoded(evidence.project(evidence.normalize_behavioral(native,PROFILE['skill']))))
            public['custom']['purpose']='cli_pilot'
            with self.assertRaisesRegex(ValueError,'Pilot profile/purpose mismatch'):
                evidence.validate_custom_evidence(public,public=True)


    @unittest.skipUnless(os.environ.get('APM_EXECUTABLE') and CANDIDATE_RUNTIME, 'Requires verified APM and owning runtime')
    def test_preparation_consumption_uses_actual_staging_and_rejects_changed_or_missing_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);reference=root/'reference';reference.mkdir()
            revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
            for phase,controls in (('pilot-probe',False),('pilot-controls',True)):
                target=reference/phase;target.mkdir()
                _,_,rows=pilot.stage(target,controls=controls,probe=not controls)
                artifact=target/'evidence'
                reports.write_json(artifact/'staging.json',rows)
                reports.write_json(artifact/'readiness.json',{'id':PROFILE['id'],'revision':revision,
                    'complete':True,'inference':False,'probe':not controls,'controls':controls})
                reports.write_json(artifact/'cleanup.json',{'complete':True,'unlaunched_arms':[]})
            from codex_pilot_replay import corpus, retrospective_metadata
            original, _, submissions, _ = corpus()
            replay=reference/'pilot-retrospective';replay.mkdir()
            _, _, rows=pilot.stage(replay,replay=retrospective_metadata(),submissions=submissions)
            artifact=replay/'evidence'
            reports.write_json(artifact/'staging.json',rows)
            reports.write_json(artifact/'readiness.json',{'revision':revision,'complete':True,'inference':False})
            reports.write_json(artifact/'cleanup.json',{'complete':True,'unlaunched_arms':[]})
            reports.write_json(artifact/'replay-check.json',{'complete':True,'inference':False,
                'originals_preserved':True,'retrospective':retrospective_metadata()})
            shutil.copytree(original,artifact/'original')
            retained=[]
            for arm, raw in submissions.items():
                member='submissions/powershell-pester-6-codex-'+('with' if arm=='with_skill' else 'without')+'/Subject.Tests.ps1'
                path=artifact/member;path.parent.mkdir(parents=True);path.write_bytes(raw)
                retained.append({'member':member,'sha256':pilot.sha(path)})
            reports.write_json(artifact/'submissions.json',retained)
            probe=reference/'pilot-probe/evidence'
            for scenario in ('command-failure','interruption'):
                shutil.copytree(probe,reference/scenario)
            for scenario in ('command-failure','interruption'):
                shutil.move(reference/scenario,probe/'cleanup-cases'/scenario)
            qualification=reference/'pilot-report/evidence/qualification.json'
            reports.write_json(qualification,{'complete':True,'inference':False,
                'execution_policy':PROFILE['execution_policy']})
            output=root/'fresh-consumption'
            with patch.object(sys,'argv',['pilot','check-preparation','--output',str(output),
                                          '--preparation',str(reference)]):
                pilot.main()
            artifact=output/'evidence'
            result=reports.read_json(artifact/'preparation-check.json')
            self.assertTrue(result['configurations_equal'] and result['other_task_members_equal'])
            self.assertEqual(result['source_revision'],revision)
            path=artifact/'task-descriptors/with_skill/pester-001.toml'
            original=path.read_bytes()
            changed=original.replace(b'timeout_sec = 600.0',b'timeout_sec = 601.0')
            self.assertNotEqual(original,changed)
            path.write_bytes(changed)
            staged=reports.read_json(artifact/'staging.json')
            row=next(r for r in staged if r['arm']=='with_skill')
            row['members']['task.toml']=descriptors.raw_digest(changed)
            row['task_checksum']=evidence.custom_task_checksum(row['members'])
            reports.write_json(artifact/'staging.json',staged)
            manifest=reports.read_json(artifact/'task-descriptors.json')
            entry=next(r for r in manifest['descriptors'] if r['arm']=='with_skill')
            entry.update(raw_sha256=descriptors.raw_digest(changed),
                parsed_sha256=descriptors.configuration_digest(changed),task_checksum=row['task_checksum'])
            reports.write_json(artifact/'task-descriptors.json',manifest)
            with self.assertRaisesRegex(ValueError,'Complete parsed task configurations differ'):
                pilot.check_preparation(reference,artifact)
            (probe/'task-descriptors/with_skill/pester-001.toml').unlink()
            with self.assertRaises(ValueError): pilot.check_preparation(reference,artifact)

    def test_live_requires_preparation_before_any_native_setup(self):
        with patch.object(pilot,'resources') as resources, patch.object(pilot,'stage') as stage:
            with self.assertRaisesRegex(ValueError,'preparation evidence required'):
                pilot.run(Path('unused'))
            resources.assert_not_called();stage.assert_not_called()
        with patch.dict(os.environ,{'OPENAI_API_KEY':'credential-free-negative-control'}), \
                patch.object(sys,'argv',['pilot','check-preparation','--output','unused','--preparation','unused']), \
                self.assertRaises(SystemExit):
            pilot.main()

    @unittest.skipUnless(CANDIDATE_RUNTIME, 'Requires qualified owning runtime')
    def test_released_harbor_mount_shape_and_independent_verifier(self):
        from harbor.trial.trial import _harbor_log_bind_mount, TaskOS
        from codex_pilot_environment import PilotEnvironment, SkillEvaluatorSecureDockerEnvironment
        mount = _harbor_log_bind_mount(source='/operator/agent', target='/logs/agent', os=TaskOS.LINUX)
        verifier = _harbor_log_bind_mount(source='/operator/verifier', target='/logs/verifier', os=TaskOS.LINUX)
        with patch.object(SkillEvaluatorSecureDockerEnvironment, '__init__', return_value=None) as parent:
            PilotEnvironment(mounts=[mount, verifier])
            self.assertEqual(parent.call_args.kwargs['mounts'], [])
            PilotEnvironment(mounts=[verifier])
            self.assertEqual(parent.call_args.kwargs['mounts'], [verifier])
            with self.assertRaisesRegex(ValueError, 'Unexpected pilot mount'):
                PilotEnvironment(mounts=[{'target': '/host'}])

    @unittest.skipUnless(CANDIDATE_RUNTIME, 'Requires qualified owning runtime')
    def test_failed_final_policy_observation_still_disposes_the_container(self):
        import asyncio
        from codex_pilot_environment import PilotEnvironment, SkillEvaluatorSecureDockerEnvironment
        agent = object.__new__(PilotEnvironment)
        agent._pilot_agent = True
        cleanup = AsyncMock()
        with patch('codex_pilot_boundary.observe', new=AsyncMock(side_effect=ValueError('unavailable'))), patch.object(SkillEvaluatorSecureDockerEnvironment, 'stop', new=cleanup):
            with self.assertRaisesRegex(ValueError, 'unavailable'):
                asyncio.run(agent.stop(True))
        cleanup.assert_awaited_once_with(True)

    @unittest.skipUnless(CANDIDATE_RUNTIME, 'Requires qualified owning runtime')
    def test_secret_delivery_uses_stdin_target_user_and_cancellation_cleanup(self):
        import asyncio
        from codex_pilot_environment import PilotEnvironment
        agent = object.__new__(PilotEnvironment)
        agent._pilot_agent = True
        agent._resolve_user = lambda value: value
        agent._merge_env = lambda value: value
        agent._output_callback = lambda: None
        agent._run_docker_compose_command = AsyncMock(return_value='result')
        value = asyncio.run(agent.exec('printf done', cwd='/workspace',
            env={'OPENAI_API_KEY': 'pilot-not-a-credential'}, user='agent'))
        self.assertEqual(value, 'result')
        args, kwargs = agent._run_docker_compose_command.call_args
        self.assertNotIn('pilot-not-a-credential', repr(args))
        self.assertIn(b'pilot-not-a-credential', kwargs['stdin_data'])
        self.assertEqual(args[0], ['exec', '-T', '-w', '/workspace', '-u', 'agent', 'main', 'sh', '-s'])
        self.assertTrue(kwargs['stop_main_on_interrupt'])
        self.assertIn('pilot-not-a-credential', kwargs['exact_secret_values'])

    def test_wrong_allocation_rejects_before_native_setup(self):
        with patch.object(sys,'argv',['pilot','live','--output','unused','--approval','wrong']), self.assertRaises(SystemExit):
            pilot.main()


class ProbeEvidence(unittest.TestCase):
    def record(self, root, arm, **changes):
        job = root / 'jobs' / ('powershell-pester-6-codex-with' if arm == 'with_skill' else 'powershell-pester-6-codex-without')
        target = job / 'trial/agent/probe.json'; target.parent.mkdir(parents=True)
        value = {'model': PROFILE['model'], 'reasoning': {'effort': 'high'}, 'requests': 2, **changes}
        target.write_text(json.dumps(value)); return target

    def test_missing_probe_preserves_available_sanitized_record_and_native_failure(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); artifact = root / 'evidence'
            self.record(root, 'without_skill', api_key='public-dummy-not-a-credential')
            failure = root / 'jobs/powershell-pester-6-codex-with/trial/exception.txt'
            failure.parent.mkdir(parents=True); failure.write_text('Runtime acquisition timeout: asset unresolved')
            with self.assertRaisesRegex(ValueError, 'evidence incomplete'):
                pilot.validate_probe_requests(root, artifact, 'success')
            values = reports.read_json(artifact / 'cli-probes.json')
            self.assertEqual(len(values), 1); self.assertEqual(values[0]['arm'], 'without_skill')
            self.assertEqual(values[0]['api_key'], '<redacted>')
            status = reports.read_json(artifact / 'probe-validation.json')
            self.assertFalse(status['complete']); self.assertEqual(status['missing_arms'], ['with_skill'])
            self.assertEqual(status['request_mismatches'], [])
            self.assertEqual(failure.read_text(), 'Runtime acquisition timeout: asset unresolved')

    def test_observed_request_mismatch_names_only_observed_fields(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); artifact = root / 'evidence'
            self.record(root, 'with_skill', model='different-model')
            self.record(root, 'without_skill')
            with self.assertRaisesRegex(ValueError, 'Observed CLI request'):
                pilot.validate_probe_requests(root, artifact, 'success')
            status = reports.read_json(artifact / 'probe-validation.json')
            self.assertEqual(status['missing_arms'], [])
            self.assertEqual(status['request_mismatches'], [{'arm': 'with_skill', 'fields': ['model']}])
            self.assertEqual(len(reports.read_json(artifact / 'cli-probes.json')), 2)

    def test_unreadable_probe_is_preserved_as_missing_evidence_not_field_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); artifact = root / 'evidence'
            self.record(root, 'with_skill').write_text('incomplete JSON')
            self.record(root, 'without_skill')
            with self.assertRaisesRegex(ValueError, 'evidence incomplete'):
                pilot.validate_probe_requests(root, artifact, 'success')
            status = reports.read_json(artifact / 'probe-validation.json')
            self.assertFalse(status['complete']); self.assertEqual(status['request_mismatches'], [])
            values = reports.read_json(artifact / 'cli-probes.json')
            self.assertEqual(values[0]['record_error'], 'unreadable_probe_record')


class DescriptorEvidence(unittest.TestCase):
    SAMPLE = b'''schema_version = "1.3"
[agent]
user = "agent"
network_mode = "allowlist"
allowed_hosts = ["api.openai.com"]
timeout_sec = 600.0
[environment]
cpus = 2
memory_mb = 2048
[environment.env]
BASH_ENV = ""
[verifier.environment]
network_mode = "no-network"
[metadata]
extra = {enabled = true, count = 1, ratio = 1.5}
order = ["a", "b"]
date = 2026-11-07
time = 12:00:00
datetime = 2026-11-07T12:00:00Z
'''

    def fixture(self, root, raw):
        task=root/'tasks/pester-001';task.mkdir(parents=True)
        (task/'task.toml').write_bytes(raw)
        row={'arm':'with_skill','case_id':'pester-001','members':{'task.toml':descriptors.raw_digest(raw)}}
        row['task_checksum']=evidence.custom_task_checksum(row['members'])
        artifact=root/'evidence'
        descriptors.retain_descriptors(artifact,{'with_skill':[task]},[row])
        reports.write_json(artifact/'staging.json',[row])
        return artifact

    def test_complete_toml_identity_ignores_presentation_and_preserves_types(self):
        reformatted=self.SAMPLE.replace(b'cpus = 2',b'cpus=0x2 # same integer').replace(
            b'user = "agent"',b"user='agent'").replace(b'600.0',b'6e2').replace(
            b'extra = {enabled = true, count = 1, ratio = 1.5}',
            b'extra={ratio=1.50,count=1,enabled=true}').replace(b'12:00:00Z',b'12:00:00+00:00')
        self.assertNotEqual(descriptors.raw_digest(self.SAMPLE),descriptors.raw_digest(reformatted))
        self.assertEqual(descriptors.configuration_digest(self.SAMPLE),descriptors.configuration_digest(reformatted))
        blocks=self.SAMPLE.split(b'\n[')
        reordered=blocks[0]+b'\n'+b''.join(b'['+block+b'\n' for block in reversed(blocks[1:]))
        self.assertEqual(descriptors.configuration_digest(self.SAMPLE),descriptors.configuration_digest(reordered))
        for a,b in ((b'value=1',b'value=1.0'),(b'value=true',b'value=1'),
                    (b'value=0.0',b'value=-0.0')):
            self.assertNotEqual(descriptors.configuration_digest(a),descriptors.configuration_digest(b))
        with self.assertRaises(ValueError): descriptors.configuration_digest(b'value=1\nvalue=2')

    @unittest.skipUnless(CANDIDATE_RUNTIME,'Requires qualified retention redactor')
    def test_compare_command_accepts_retained_formatting_only_difference(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);left=self.fixture(root/'left',self.SAMPLE)
            right=self.fixture(root/'right',self.SAMPLE.replace(b'cpus = 2',b'cpus=0x2 # presentation only'))
            result=subprocess.run([sys.executable,'-B',str(ROOT/'.github/scripts/codex_pilot_descriptors.py'),
                                   str(left),str(right)],capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout),{'algorithm':descriptors.ALGORITHM,
                'configurations_equal':True,'descriptors':1})

    @unittest.skipUnless(CANDIDATE_RUNTIME,'Requires qualified retention redactor')
    def test_complete_configuration_changes_are_rejected_with_valid_raw_evidence(self):
        changes=((b'user = "agent"',b'user = "root"'),
            (b'network_mode = "allowlist"',b'network_mode = "public"'),
            (b'allowed_hosts = ["api.openai.com"]',b'allowed_hosts = ["example.com"]'),
            (b'timeout_sec = 600.0',b'timeout_sec = 601.0'),
            (b'cpus = 2',b'cpus = 3'),(b'memory_mb = 2048',b'memory_mb = 4096'),
            (b'memory_mb = 2048\n',b''),
            (b'BASH_ENV = ""',b'BASH_ENV = "/changed"'),
            (b'network_mode = "no-network"',b'network_mode = "public"'),
            (b'enabled = true',b'enabled = false'),(b'count = 1',b'count = 1.0'),
            (b'ratio = 1.5',b'ratio = 1.6'),(b'order = ["a", "b"]',b'order = ["b", "a"]'),
            (b'date = 2026-11-07',b'date = 2026-11-08'),
            (b'time = 12:00:00',b'time = 12:00:01'),
            (b'datetime = 2026-11-07T12:00:00Z',b'datetime = 2026-11-07T12:00:01Z'),
            (b'[metadata]',b'[metadata]\nunknown = "new configuration field"'))
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);left=self.fixture(root/'left',self.SAMPLE)
            for i,(old,new) in enumerate(changes):
                with self.subTest(change=old):
                    right=self.fixture(root/str(i),self.SAMPLE.replace(old,new))
                    with self.assertRaisesRegex(ValueError,'Complete parsed task configurations differ'):
                        descriptors.compare_descriptors(left,right)

    @unittest.skipUnless(CANDIDATE_RUNTIME,'Requires qualified retention redactor')
    def test_missing_tampered_and_contradictory_descriptor_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);artifact=self.fixture(root/'valid',self.SAMPLE)
            path=artifact/'task-descriptors/with_skill/pester-001.toml'
            path.write_bytes(self.SAMPLE+b'\n# unrecorded raw-byte change\n')
            with self.assertRaisesRegex(ValueError,'Descriptor raw identity mismatch'):
                descriptors.verified_configurations(artifact)
            path.write_bytes(self.SAMPLE)
            manifest=reports.read_json(artifact/'task-descriptors.json')
            manifest['descriptors'][0]['parsed_sha256']='sha256:'+'0'*64
            reports.write_json(artifact/'task-descriptors.json',manifest)
            with self.assertRaisesRegex(ValueError,'Descriptor parsed identity mismatch'):
                descriptors.verified_configurations(artifact)
            manifest['descriptors'][0]['parsed_sha256']=descriptors.configuration_digest(self.SAMPLE)
            reports.write_json(artifact/'task-descriptors.json',manifest)
            descriptors.verified_configurations(artifact)
            missing=root/'older';missing.mkdir()
            result=subprocess.run([sys.executable,'-B',str(ROOT/'.github/scripts/codex_pilot_descriptors.py'),
                                   str(artifact),str(missing)],capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,1)
            self.assertIn('incomplete, inconsistent, or configuration differs',result.stderr)


if __name__=='__main__': unittest.main()
