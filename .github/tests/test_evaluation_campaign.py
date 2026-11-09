"""Shared campaign contracts; native execution is qualified by the owning CI job."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))
import evaluation_campaign_core as core
import evaluation_runtime as runtime
from evaluation_tasks import load
import skill_evidence as evidence
import skill_reports as reports


class CampaignContracts(unittest.TestCase):
    def test_counterbalanced_schedule_supports_arbitrary_variants_and_preserves_historical_order(self):
        import codex_pilot_effectiveness as old
        rows = core.schedule(('one','two'), ('absent','current','revision'), 3)
        self.assertEqual(len(rows),18)
        self.assertEqual({(r['case'],r['variant'],r['trial']) for r in rows},
                         {(c,v,t) for c in ('one','two') for v in ('absent','current','revision') for t in (1,2,3)})
        self.assertEqual([r['variant'] for r in rows[:3]],['revision','absent','current'])
        # The historical protocol's exact twelve-slot order is frozen independently.
        self.assertEqual([(r['case'],r['arm']) for r in old.schedule()], [
            ('pester-003','with_skill'),('pester-003','without_skill'),('pester-004','without_skill'),('pester-004','with_skill'),
            ('pester-004','with_skill'),('pester-004','without_skill'),('pester-003','without_skill'),('pester-003','with_skill'),
            ('pester-003','with_skill'),('pester-003','without_skill'),('pester-004','without_skill'),('pester-004','with_skill')])
        for args in [((),('x','y'),1),(('x',),('y','y'),1),(('x',),('a','b'),True)]:
            with self.assertRaises(ValueError):core.schedule(*args)

    def test_durable_scheduler_keeps_partial_states_and_stops_without_replacement(self):
        def scenario(reason=None, error=None, cost=0, baseline=()):
            rows=[{**r,'state':'unlaunched'} for r in core.schedule(('x',),('left','right'),1)]
            ledger={'entries':rows};saved=[]
            def attempt(row,total):
                self.assertEqual(saved[-1]['entries'][row['position']-1]['state'],'launching')
                if error:raise error
                row.update(state='completed',usage={'estimated_usd':cost},outcome='failed')
                return reason
            try:
                core.drive(ledger,attempt,save=lambda:saved.append(copy.deepcopy(ledger)),resources=lambda:(),baseline=baseline,threshold=1)
            except BaseException:
                if error is None:raise
            return ledger
        for reason in ('unknown_usage','unsupported_grading','execution_infrastructure_failure','cleanup_failure'):
            result=scenario(reason)
            self.assertEqual(result['state'],'stopped');self.assertEqual(result['stop_reason'],reason)
            self.assertEqual([r['state'] for r in result['entries']],['completed','unlaunched'])
        result=scenario(cost=1);self.assertEqual(result['stop_reason'],'estimated_usage_threshold')
        result=scenario(error=KeyboardInterrupt());self.assertEqual(result['state'],'interrupted')
        self.assertEqual([r['state'] for r in result['entries']],['interrupted','unlaunched'])
        self.assertEqual(scenario()['state'],'completed') # Measured failures do not stop scheduling.

    def test_adapter_owns_model_validation_and_preserves_alternate_identities(self):
        # These are synthetic identity contracts, not compatibility probes.
        for agent,model,provider in [('claude-code','claude-fixture','anthropic-fixture'),('copilot','copilot-fixture','github-fixture')]:
            config={'id':'synthetic','adapter':agent,'cli':'synthetic-version','model':model,'provider':provider,'settings':{'effort':'fixture'}}
            with tempfile.TemporaryDirectory() as d:
                p=Path(d)/'profile.json';reports.write_json(p,config)
                def validate(value):
                    core.require(value['settings']=={'effort':'fixture'},'Unsupported model settings')
                    return copy.deepcopy(value)
                result=runtime.read_profile(p,{agent:validate})
                self.assertEqual(result,{'profile':config,'resolved':config})
                self.assertEqual(json.loads(json.dumps(result)),result)
                ledger={'runtime':copy.deepcopy(result),'entries':[{'state':'unlaunched'}]}
                def attempt(row,total):
                    row.update(state='completed',usage={'estimated_usd':0})
                core.drive(ledger,attempt,save=lambda:None,resources=lambda:(),baseline=(),threshold=1)
                self.assertEqual(json.loads(json.dumps(ledger))['runtime'],result)
                with self.assertRaisesRegex(ValueError,'Unsupported runtime adapter'):runtime.read_profile(p)
                config['settings']['effort']='unsupported';reports.write_json(p,config)
                with self.assertRaisesRegex(ValueError,'Unsupported model settings'):runtime.read_profile(p,{agent:validate})
        frozen=ROOT/'.github/evals/campaigns/codex-qualified.json'
        actual=runtime.read_profile(frozen)
        from codex_pilot_contract import PROFILE
        self.assertEqual(actual['resolved'],dict(PROFILE,agent='codex'))
        for key,value in [('model','arbitrary'),('inference_enabled',True),('capabilities',['all'])]:
            wrong={**actual['profile'],key:value}
            with self.assertRaises(ValueError):runtime.validate_codex(wrong)

    def test_both_tasks_have_frozen_original_prompts_independent_graders_and_metric_semantics(self):
        for filename in ('boolean-contract','gh-read'):
            task=load(ROOT/('.github/evals/campaigns/'+filename+'.json'))
            for mode in ('oracle','probe'):
                purpose='campaign-'+task.definition['id']+'-'+mode
                profile,definitions,_=evidence.custom_contract(task.definition['skill'],purpose=purpose)
                identities=evidence.custom_input_identities(ROOT,task.definition['skill'],purpose=purpose)
                self.assertTrue(all(profile[k]==v for k,v in identities.items()),(purpose,identities))
                self.assertEqual(profile['qualification_cases'],{k:task.definition['source_case'] for k in task.cases(mode)})
                self.assertEqual(evidence.custom_prepared_entries(ROOT,task.definition['skill'],list(task.cases(mode)),purpose), sorted(task.entries(mode),key=lambda r:r['id']))
                self.assertFalse(profile['runtime'].get('inference_enabled',False))
            if filename=='boolean-contract':
                candidate=task.candidate();self.assertEqual((ROOT/'.github/evals/pester-ceiling'/candidate['prompt']).read_text(),task.entry()['prompt']+'\n')
                self.assertEqual(set(task.controls()),{'identity','typed-classic','value-only','type-only','broken-discovery'})
                self.assertEqual(len([k for k in task.files() if k.startswith('mutants/')]),5)
            else:
                self.assertEqual(task.output,'result.json')
                self.assertEqual(task.commands('good'),task.original()['contract']['good_commands'])
                task.check('unauthorized',True,{'classification':'failed'},{'gh_task':1,'gh_authorization':0})
                with self.assertRaises(ValueError):task.check('unauthorized',True,{'classification':'failed'},{'gh_task':0,'gh_authorization':0})

    def test_metadata_inspection_does_not_import_native_runtime_backends(self):
        import builtins
        original=builtins.__import__
        def importing(name,*args,**kwargs):
            if name.startswith(('evaluation_codex','codex_pilot_environment','aeb_gh_fixture')):
                raise AssertionError('Metadata imported native backend: '+name)
            return original(name,*args,**kwargs)
        with patch('builtins.__import__',side_effect=importing), patch.object(runtime, 'adapter_for', side_effect=AssertionError('Metadata loaded execution adapter')):
            for filename in ('boolean-contract','gh-read'):
                task=load(ROOT/('.github/evals/campaigns/'+filename+'.json'))
                evidence.custom_input_identities(ROOT,task.definition['skill'],purpose='campaign-'+task.definition['id']+'-oracle')

    def test_historical_replay_does_not_require_matched_submitted_answers(self):
        rows=[{'case_id':'case','members':{'instruction.md':'same','solution/candidate':answer}} for answer in ('left','right')]
        staged=evidence.custom_staged_inputs(rows,'cli_pilot_replay')
        self.assertEqual(staged,[{'case_id':'case','instruction_digest':'same','agent_inputs':{}}])
        with self.assertRaisesRegex(ValueError,'With/without task input drift'):
            evidence.custom_staged_inputs(rows,'campaign-boolean-contract-v1-oracle')

    def test_gh_control_expectations_match_existing_offline_fixture_grader(self):
        import gh_evaluations as gh
        task=load(ROOT/'.github/evals/campaigns/gh-read.json')
        for control,fault in (('good',None),('wrong-repo','wrong-repo'),('unauthorized','unauthorized')):
            result=gh.replay_case(task.original(),fault=fault)
            metrics=result['custom_metrics']
            task.check(control,True,{'classification':'passed' if metrics['gh_gate'] else 'failed'},metrics)
        # Fixture replay supplies synthetic activation. Native CLI qualification
        # independently exercises discovery, command observations and the grader.

    def test_new_profiles_preserve_every_historical_profile_byte_value(self):
        # Canonical registry snapshot from merged base e2fabea; works in shallow
        # CI checkouts and never follows a moving remote tracking reference.
        import hashlib
        current=reports.read_json(ROOT/evidence.CUSTOM_REGISTRY)
        new={'pester-cli-pilot-retained-v7','pester-effectiveness-v7',
             'campaign-boolean-contract-v1-oracle','campaign-boolean-contract-v1-probe',
             'campaign-gh-read-v1-oracle','campaign-gh-read-v1-probe'}
        historical={k:v for k,v in current['profiles'].items() if k not in new}
        value={'profiles':historical,'active_profiles':current['active_profiles'],'metrics':current['metrics']}
        digest=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
        self.assertEqual(digest,'8abda5c8c49436edaaf2dd6a954720145c872cc9b5d6a4fe762beb584c92a118')




class NativeAdapterContracts(unittest.TestCase):
    @unittest.skipUnless(__import__('importlib.util',fromlist=['find_spec']).find_spec('aeb_gh_fixture') and __import__('importlib.metadata',fromlist=['version']).version('skillevaluator') == '0.8.0', 'Owning native backend required')
    def test_initializer_transport_creates_private_owned_files_and_refuses_replacement(self):
        import shlex
        import stat
        import subprocess
        from evaluation_codex import initializer_upload_command
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'approved.json'
            argv=shlex.split(initializer_upload_command(b'{"fixture":"digest"}', '/opt/aeb-gh/approved.json'))
            argv[-1]=str(target) # Existing component-probe convention: map only the container path.
            subprocess.run(argv,check=True,capture_output=True)
            self.assertEqual(target.read_bytes(),b'{"fixture":"digest"}')
            self.assertEqual(stat.S_IMODE(target.stat().st_mode),0o600)
            subprocess.run(argv,check=True,capture_output=True) # Repeated initialization preserves bytes.
            target.write_bytes(b'changed')
            self.assertNotEqual(subprocess.run(argv,capture_output=True).returncode,0)
            target.unlink();outside=Path(directory)/'outside';outside.write_bytes(b'unchanged');target.symlink_to(outside)
            self.assertNotEqual(subprocess.run(argv,capture_output=True).returncode,0)
            self.assertEqual(outside.read_bytes(),b'unchanged')
            with self.assertRaises(ValueError):initializer_upload_command(b'data','/workspace/output/result.json')

    @unittest.skipUnless(__import__('importlib.util',fromlist=['find_spec']).find_spec('aeb_gh_fixture') and __import__('importlib.metadata',fromlist=['version']).version('skillevaluator') == '0.8.0', 'Owning native backend required')
    def test_native_exec_bridge_keeps_completed_command_observations_and_rejects_ambiguity(self):
        from types import SimpleNamespace
        from evaluation_codex import exec_trajectory, failure_reason, MissingCodexObservation, UnsupportedCodexProtocol
        self.assertEqual(failure_reason('MissingCodexObservation'),'missing_native_observation')
        self.assertEqual(failure_reason('UnsupportedCodexProtocol'),'unsupported_runtime_protocol')
        self.assertEqual(failure_reason('RuntimeError'),'execution_infrastructure_failure')
        from harbor.agents.installed.codex import Codex
        from skillevaluator.tier3.eval_core.atif_helpers import get_all_tool_calls
        from codex_pilot_contract import PROFILE
        adapter=SimpleNamespace(profile=PROFILE, model_name=PROFILE['model'])
        adapter._convert_event_to_step=lambda event,index:Codex._convert_event_to_step(adapter,event,index)
        start={'type':'item.started','item':{'id':'native1','type':'command_execution','command':"/bin/sh -lc 'gh issue list --repo example/repo'"}}
        finish={'type':'item.completed','item':{**start['item'],'aggregated_output':'GH_FIXTURE_RECEIPT='+'a'*64+'\n','exit_code':0,'status':'completed'}}
        events=[{'type':'thread.started','thread_id':'synthetic-native-protocol'},start,finish,{'type':'turn.completed'}]
        def convert(values):return exec_trajectory('\n'.join(map(json.dumps,values)),adapter)
        trajectory=convert(events).model_dump(exclude_none=True)
        calls=get_all_tool_calls(trajectory)
        self.assertEqual(calls[0]['fn'],'exec_command')
        self.assertEqual(calls[0]['args'],{'command':'gh issue list --repo example/repo'})
        self.assertEqual(calls[0]['obs'],finish['item']['aggregated_output'].lower())
        self.assertNotIn('llm_call_count',trajectory['steps'][0])
        self.assertNotIn('final_metrics',trajectory)
        for values,error in [(events[:-2]+events[-1:],MissingCodexObservation),([events[0],finish,events[-1]],MissingCodexObservation),
                             ([*events[:2],start,*events[2:]],UnsupportedCodexProtocol),
                             ([*events[:3],finish,events[-1]],UnsupportedCodexProtocol)]:
            with self.assertRaises(error):convert(values)
        for changed in ['gh issue list','/bin/bash -lc gh']:
            values=copy.deepcopy(events)
            for index in (1,2):values[index]['item']['command']=changed
            with self.assertRaises(UnsupportedCodexProtocol):convert(values)
        values=copy.deepcopy(events);values[2]['item']['command']="/bin/sh -lc 'changed'"
        with self.assertRaises(UnsupportedCodexProtocol):convert(values)

    def test_report_staging_preserves_synthetic_alternate_runtime_and_model_identities(self):
        try:
            import skillevaluator
        except ImportError:self.skipTest('Existing reporting runtime required')
        for agent in ('claude-code','copilot'):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);raw=root/'raw';target=root/'retained'
                reports.write_json(raw/evidence.CUSTOM_CAPTURE,{'purpose':'campaign-synthetic-fixture'})
                member=Path('results/powershell-pester-6/synthetic')/agent/'with-skill/trials/fixture/result.json'
                value={'runtime':agent,'model':'synthetic-model','provider':'synthetic-provider'}
                reports.write_json(raw/member,value)
                profile={'campaign':{},'runtime':{'agent':agent}}
                with patch.object(evidence,'validate_custom_capture',return_value=(profile,{})), patch.object(reports,'benchmark_skill'), patch.object(reports,'capture_benchmark_custom'):
                    reports.benchmark_artifacts(ROOT,raw,'powershell-pester-6',target)
                self.assertEqual(reports.read_json(target/member),value)
                self.assertFalse((target/'results/powershell-pester-6/synthetic/codex').exists())


if __name__=='__main__':unittest.main()
