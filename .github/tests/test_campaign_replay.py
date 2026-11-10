"""Immutable source and current-only replay contracts, not another model attempt."""
import copy
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.github/scripts'))
import codex_pilot_replay as replay
import evaluation_campaign as campaign
from evaluation_tasks import load
import skill_evidence as evidence
import skill_reports as reports


class RetainedCampaign(unittest.TestCase):
    def task(self):return load(ROOT/'.github/evals/campaigns/boolean-retained-v1.json')

    def test_source_is_exact_and_original_unmeasured_record_stays_unchanged(self):
        root,manifest,original=replay.campaign_corpus()
        self.assertEqual(manifest['source']['run'],42695478931)
        self.assertEqual(len((root/'Subject.Tests.ps1').read_bytes()),471)
        self.assertEqual(hashlib.sha256((root/'Subject.Tests.ps1').read_bytes()).hexdigest(),'3215b6097fa3e5f592989f2b8f4523207e28ebd4893cc7d11437b19189795981')
        self.assertTrue(all(m['value'] is None for o in original['observations'] for m in o['custom']['measurements']))
        self.assertEqual([a['coverage']['expected_attempts'] for a in original['arms']],[3,3])
        self.assertEqual([a['coverage']['scored_attempts'] for a in original['arms']],[0,0])
        with tempfile.TemporaryDirectory() as d:
            workspace=Path(d);target=workspace/replay.CAMPAIGN_CORPUS;shutil.copytree(root,target)
            replay.campaign_corpus(workspace)
            (target/'Subject.Tests.ps1').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'bytes changed'):replay.campaign_corpus(workspace)

    def test_retrospective_is_distinct_no_inference_and_exactly_one_source_arm(self):
        task=self.task();purpose=campaign.purpose(task,'replay')
        self.assertEqual(task.cases('replay'),{'pester-004':'retained'})
        self.assertEqual(task.definition['attempt_limit'],1)
        self.assertNotIn('protocol',task.definition)
        profile,_,_=evidence.custom_contract(task.definition['skill'],purpose=purpose)
        self.assertTrue(evidence.oracle_purpose(purpose))
        meta=replay.campaign_retrospective(profile,adapter_revision='a'*40)
        self.assertEqual(set(meta['submission_digests']),{'with_skill'})
        self.assertIs(meta['new_inference'],False)
        replay.validate_campaign_retrospective(meta,profile)
        for key,value in [('source_slot',2),('source_run',1),('new_inference',True),('corrected_adapter_sha256','sha256:'+'0'*64)]:
            with self.assertRaises(ValueError):replay.validate_campaign_retrospective({**meta,key:value},profile)
        good={'qualification':{'producer':'retained_submission_replay','inference':False},'harbor':{'n_attempts':1,'stop_on_pass':False}}
        evidence.validate_custom_execution_config(purpose,good,1)
        with self.assertRaises(ValueError):evidence.validate_custom_execution_config(purpose,{'qualification':{'producer':'live','inference':True}},1)

    def test_candidate_and_all_frozen_grading_members_match_executed_revision(self):
        task=self.task();root,_,_=replay.campaign_corpus();staging=reports.read_json(root/'staging.json')
        old=next(r['members'] for r in staging if r['arm']=='with_skill')
        for member,raw in task.expected_members('pester-004','with_skill').items():
            self.assertEqual(evidence.digest_bytes(raw),old[member],member)
        self.assertEqual(task.payload('retained'),(root/'Subject.Tests.ps1').read_bytes())
        self.assertEqual(len([key for key in task.files() if key.startswith('mutants/')]),5)
        self.assertIn('mutants/integer-result.ps1',task.files())

    def test_report_labels_replay_and_requires_exact_original_pair(self):
        import skill_analysis as analysis
        task=self.task();purpose=campaign.purpose(task,'replay');profile,_,_=evidence.custom_contract(task.definition['skill'],purpose=purpose)
        meta=replay.campaign_retrospective(profile,adapter_revision='a'*40)
        original=replay.campaign_corpus()[2]
        row={'custom':{'purpose':purpose,'retrospective':meta},'observations':[]}
        replay.validate_campaign_pair(row,original)
        self.assertTrue(analysis.pilot_record(row))
        self.assertIn('Retrospective',analysis.coverage_label({'behavioral_results':[row]}))
        changed=copy.deepcopy(original);changed['observations'][0]['custom']['measurements'][0]['value']=0
        with self.assertRaises(ValueError):replay.validate_campaign_pair(row,changed)
        with self.assertRaises(ValueError):replay.validate_campaign_pair({**row,'observations':[{'arm':'without_skill'}]},original)


if __name__=='__main__':unittest.main()
