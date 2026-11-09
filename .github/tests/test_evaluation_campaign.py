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



if __name__=='__main__':unittest.main()
