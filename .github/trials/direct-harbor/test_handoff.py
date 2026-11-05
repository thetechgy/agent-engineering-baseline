"""Focused credential-free contract tests, not live grading/activation evidence."""
import importlib.util,json,os,tempfile,unittest
from pathlib import Path
from artifact_state import observe,classify
import live,run

class HandoffTests(unittest.TestCase):
    def test_real_admission_reasons_preserve_acceptance(self):
        spec=importlib.util.spec_from_file_location('grader',run.ROOT/run.pilot.OVERLAY/'evals/grader.py')
        g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'candidate'
            self.assertEqual(g.read_candidate(p),(None,'missing'))
            p.write_bytes(b'\xff\xfe\x80');self.assertEqual(g.read_candidate(p),(None,'invalid_utf8'))
            self.assertEqual(observe(p)['size'],3);self.assertIsNotNone(observe(p)['sha256'])
            p.write_bytes(b'valid utf8');self.assertEqual(g.read_candidate(p),(b'valid utf8',None))
            link=Path(tmp)/'link';link.symlink_to(p);self.assertEqual(g.read_candidate(link),(None,'symlink'))
            hard=Path(tmp)/'hard';os.link(p,hard);self.assertEqual(g.read_candidate(p),(None,'hardlink'));hard.unlink()
            p.write_bytes(b'a'*(g.LIMIT+1));self.assertEqual(g.read_candidate(p),(None,'size'))
            p.unlink();p.mkdir();self.assertEqual(g.read_candidate(p),(None,'file_type'))
    def test_missing_failure_not_excluded_or_confused_with_transport(self):
        missing={'exists':False};present={'exists':True,'sha256':'fixture'}
        outcome={'classification':'invalid','admission_reason':'missing'}
        result=classify(missing,{'status':'failed'},missing,missing,outcome,environment_ok=True,completed=True)
        self.assertEqual(result['classification'],'missing_deliverable');self.assertTrue(result['task_completion_measured']);self.assertFalse(result['task_completed']);self.assertFalse(result['correctness_measured'])
        self.assertEqual(classify(present,{'status':'failed'},missing,missing,outcome,environment_ok=True,completed=True)['classification'],'collection_failure')
        self.assertEqual(classify(present,{'status':'ok'},present,missing,outcome,environment_ok=True,completed=True)['classification'],'transfer_failure')
        self.assertEqual(classify({}, {}, missing, missing,outcome,environment_ok=True,completed=True)['classification'],'missing_evidence')
        self.assertEqual(classify(missing,{},missing,missing,outcome,environment_ok=False,completed=True)['classification'],'missing_evidence')
    def test_rejected_vs_graded_and_unknown_hash(self):
        p={'exists':True,'sha256':'same'}
        result=classify(p,{'status':'ok'},p,p,{'classification':'invalid','admission_reason':'invalid_utf8'},environment_ok=True,completed=True)
        self.assertEqual(result['classification'],'rejected_output');self.assertFalse(result['correctness_measured'])
        for status in ('passed','failed'):
            r=classify(p,{'status':'ok'},p,p,{'classification':status},environment_ok=True,completed=True)
            self.assertEqual(r['classification'],'graded_'+status);self.assertTrue(r['correctness_measured'])
    def test_custom_events_are_bounded_and_never_retain_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'agent').mkdir()
            events=[{'type':'response_item','payload':{'type':'custom_tool_call','name':'exec_command','input':'cat powershell-pester-6/SKILL.md SENTINEL_SECRET'}},
                    {'type':'event_msg','payload':{'type':'exec_command_end','exit_code':1,'aggregated_output':'SENTINEL_SECRET'}},
                    {'type':'event_msg','payload':{'type':'task_complete','last_agent_message':'SENTINEL_SECRET'}}]
            (root/'agent/rollout-fixture.jsonl').write_text('\n'.join(json.dumps(x) for x in events))
            r=live.usage_and_activation(root);self.assertEqual(r['tool_calls'],1);self.assertEqual(r['exec_outcomes'],[{'exit_code':1,'output_retained':False}]);self.assertNotIn('SENTINEL_SECRET',json.dumps(r))
    def test_new_profile_and_paid_guard(self):
        self.assertEqual((live.MODEL,live.EFFORT,live.VERSION),('gpt-6.1-sol','high','0.166.0'))
        self.assertTrue(live.config()['features']['rollout_budget']['enforce_limit'])
        for variant in ('current','absent'):
            with self.assertRaisesRegex(RuntimeError,'Paid scheduling disabled'):live.live_attempt(Path('/unused'),variant)

if __name__=='__main__':unittest.main()
