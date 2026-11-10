"""Pinned exec protocol fixtures; native apply_patch qualification is hosted."""
import copy
import hashlib
from importlib.metadata import version, PackageNotFoundError
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.github/scripts'))
try: OWNING=version('harbor')=='0.24.0'
except PackageNotFoundError: OWNING=False


@unittest.skipUnless(OWNING,'Pinned Harbor representation required')
class ExecEvents(unittest.TestCase):
    def setUp(self):
        from harbor.agents.installed.codex import Codex
        from codex_pilot_contract import PROFILE
        self.adapter=SimpleNamespace(profile=PROFILE,model_name=PROFILE['model'])
        self.adapter._convert_event_to_step=lambda event,index:Codex._convert_event_to_step(self.adapter,event,index)

    def parse(self,events):
        from evaluation_codex import exec_trajectory
        return exec_trajectory('\n'.join(map(json.dumps,events)),self.adapter)

    def edit(self,status='completed',identity='edit',kind='add'):
        return {'id':identity,'type':'file_change','changes':[{'path':'/workspace/output/result.txt','kind':kind}],'status':status}

    def stream(self,*events):
        return [{'type':'thread.started','thread_id':'fixture'},*events,{'type':'turn.completed'}]

    def test_retained_failure_structure_now_preserves_native_action_and_raw_link(self):
        from evaluation_codex import exec_trajectory
        path=ROOT/'.github/tests/fixtures/codex-events/retained-file-change.jsonl'
        raw=path.read_text();trajectory=exec_trajectory(raw,self.adapter)
        original=[json.loads(line) for line in raw.splitlines()]
        edits=[step for step in trajectory.steps if step.tool_calls and step.tool_calls[0].function_name=='file_change']
        self.assertEqual(len(edits),1);edit=edits[0];call=edit.tool_calls[0]
        expected=next(e['item'] for e in original if e['type']=='item.completed' and e.get('item',{}).get('type')=='file_change')
        self.assertEqual(call.tool_call_id,expected['id'])
        self.assertEqual(call.arguments,{'changes':expected['changes']})
        self.assertEqual(json.loads(edit.observation.results[0].content),expected)
        self.assertEqual(edit.extra['status'],expected['status'])
        self.assertNotIn('command',call.arguments)
        self.assertNotIn('exit_code',edit.extra['tool_metadata'])
        self.assertIsNone(edit.llm_call_count)
        self.assertEqual(trajectory.extra['raw_trace']['sha256'],'sha256:'+hashlib.sha256(raw.encode()).hexdigest())
        for line in edit.extra['tool_metadata']['raw_event_lines']:
            self.assertEqual(original[line-1]['item']['id'],expected['id'])
        self.assertEqual(len([s for s in trajectory.steps if s.tool_calls and s.tool_calls[0].function_name=='exec_command']),6)

    def test_file_changes_preserve_success_failure_paths_operations_and_completion_only(self):
        for status in ('completed','failed'):
            for kind in ('add','update','delete'):
                for paired in (True,False):
                    with self.subTest(status=status,kind=kind,paired=paired):
                        item=self.edit(status,kind=kind)
                        values=([{'type':'item.started','item':{**item,'status':'in_progress'}}] if paired else [])
                        values.append({'type':'item.completed','item':item})
                        step=self.parse(self.stream(*values)).steps[0]
                        self.assertEqual(step.tool_calls[0].arguments['changes'],item['changes'])
                        self.assertEqual(step.extra['status'],status)
                        self.assertEqual(step.extra['tool_metadata']['lifecycle'],'started/completed' if paired else 'completion-only')
                        self.assertEqual(json.loads(step.observation.results[0].content),item)

    def test_bad_incomplete_duplicate_and_changed_file_lifecycles_fail_closed(self):
        from evaluation_codex import MissingCodexObservation,UnsupportedCodexProtocol
        item=self.edit();start={'type':'item.started','item':{**item,'status':'in_progress'}};end={'type':'item.completed','item':item}
        for events,error in [([start],MissingCodexObservation),([start,start,end],UnsupportedCodexProtocol),
                             ([end,end],UnsupportedCodexProtocol),([start,{**end,'item':self.edit(kind='delete')}],UnsupportedCodexProtocol),
                             ([{**end,'item':{**item,'status':'in_progress'}}],MissingCodexObservation),
                             ([{'type':'item.updated','item':item}],UnsupportedCodexProtocol)]:
            with self.assertRaises(error):self.parse(self.stream(*events))
        for item in [dict(item,id=''),dict(item,changes='path'),dict(item,changes=[{'path':'x','kind':'rename'}]),
                     dict(item,changes=[{'path':'x','kind':'add','contents':'not in exec schema'}]),dict(item,patch='invented')]:
            with self.assertRaises(UnsupportedCodexProtocol):self.parse(self.stream({'type':'item.completed','item':item}))

    def test_reasoning_plan_and_nonfatal_errors_are_information_not_actions(self):
        plan={'id':'plan','type':'todo_list','items':[{'text':'work','completed':False}]}
        events=self.stream({'type':'item.completed','item':{'id':'warning','type':'error','message':'another non-fatal warning'}},
            {'type':'item.completed','item':{'id':'reason','type':'reasoning','text':'native summary'}},
            {'type':'item.started','item':plan},{'type':'item.updated','item':plan},{'type':'item.completed','item':plan},
            {'type':'item.completed','item':self.edit()})
        trajectory=self.parse(events)
        self.assertEqual(trajectory.steps[0].reasoning_content,'native summary')
        self.assertEqual(trajectory.steps[0].message,'')
        self.assertEqual(len([s for s in trajectory.steps if s.tool_calls]),1)
        self.assertIn('another non-fatal warning',trajectory.notes)
        info=trajectory.extra['informational_events']
        self.assertEqual(len([e for e in info if e['event'].get('item',{}).get('type')=='todo_list']),3)
        self.assertFalse(next(e for e in info if e['event']['type']=='item.completed' and e['event'].get('item',{}).get('type')=='todo_list')['event']['item']['items'][0]['completed'])

    def test_terminal_failures_are_distinct_and_unknown_action_forms_still_reject(self):
        from evaluation_codex import CodexRuntimeError,UnsupportedCodexProtocol
        from evaluation_runtime import failure_reason
        self.assertEqual(failure_reason('CodexRuntimeError'),'execution_infrastructure_failure')
        for event in ({'type':'error','message':'fatal'},{'type':'turn.failed','error':{'message':'failed'}}):
            with self.assertRaises(CodexRuntimeError):self.parse(self.stream(event))
        for kind in ('mcp_tool_call','collab_tool_call','web_search','unknown'):
            with self.assertRaises(UnsupportedCodexProtocol):self.parse(self.stream({'type':'item.completed','item':{'id':'x','type':kind}}))
        with self.assertRaises(UnsupportedCodexProtocol):self.parse(self.stream({'type':'item.completed','item':self.edit()})+[{'type':'turn.completed'}])

    def test_command_updates_keep_final_observations_and_require_observed_start(self):
        from evaluation_codex import MissingCodexObservation
        item={'id':'command','type':'command_execution','command':"/bin/sh -lc 'echo data'",'status':'in_progress','aggregated_output':''}
        update={**item,'aggregated_output':'partial'};end={**item,'aggregated_output':'observed failure','exit_code':23,'status':'failed'}
        trajectory=self.parse(self.stream({'type':'item.started','item':item},{'type':'item.updated','item':update},{'type':'item.completed','item':end}))
        step=trajectory.steps[0]
        self.assertEqual(step.tool_calls[0].function_name,'exec_command')
        self.assertEqual(step.observation.results[0].content,'observed failure')
        self.assertEqual(step.extra['tool_metadata']['exit_code'],23)
        self.assertEqual(len(step.extra['tool_metadata']['raw_event_lines']),3)
        with self.assertRaises(MissingCodexObservation):self.parse(self.stream({'type':'item.completed','item':end}))

    def test_separate_diagnostics_are_retained_without_relaxing_json_event_admission(self):
        from evaluation_codex import exec_trajectory,UnsupportedCodexProtocol
        events=self.stream({'type':'item.completed','item':self.edit('failed')})
        raw='\n'.join(map(json.dumps,events))
        diagnostics='ERROR codex_core::tools::router: error=Exit code: 1\nWall time: 0 seconds\nOutput:\nFailed to write file /workspace/output/result.txt\n'
        trajectory=exec_trajectory(raw,self.adapter,diagnostics=diagnostics)
        self.assertEqual(trajectory.extra['diagnostic_trace'],{'member':'agent/codex-stderr.txt',
            'sha256':'sha256:'+hashlib.sha256(diagnostics.encode()).hexdigest()})
        self.assertEqual(trajectory.extra['raw_trace']['sha256'],'sha256:'+hashlib.sha256(raw.encode()).hexdigest())
        self.assertEqual(len(trajectory.steps),1)
        self.assertEqual(trajectory.steps[0].extra['status'],'failed')
        # Mixed diagnostic text still fails. The runtime must separate the real
        # channels rather than teaching the parser to skip arbitrary output.
        with self.assertRaises(UnsupportedCodexProtocol):
            exec_trajectory(raw+'\n'+diagnostics,self.adapter,diagnostics='')

    def test_missing_diagnostic_stream_is_missing_essential_runtime_evidence(self):
        import tempfile
        from evaluation_codex import CampaignCodex,MissingCodexObservation
        with tempfile.TemporaryDirectory() as directory:
            adapter=object.__new__(CampaignCodex);adapter.logs_dir=Path(directory)
            (adapter.logs_dir/'codex.txt').write_text(json.dumps({'type':'turn.completed','usage':{
                'input_tokens':0,'cached_input_tokens':0,'output_tokens':0}})+'\n')
            with self.assertRaisesRegex(MissingCodexObservation,'diagnostic stream'):
                adapter.populate_context_post_run(SimpleNamespace())

    def test_native_file_change_cannot_bypass_gh_command_authorization(self):
        from skillevaluator.tier3.eval_core.atif_helpers import get_all_tool_calls
        from gh_evaluations import module
        grader=module(ROOT/'.github/evals/gh/evals/grader.py','gh_file_change_policy')
        trajectory=self.parse(self.stream({'type':'item.completed','item':self.edit()})).model_dump(exclude_none=True)
        calls=get_all_tool_calls(trajectory)
        self.assertEqual(calls[0]['fn'],'file_change')
        actual=[{'action':call['fn'],'action_input':call['args'],'observation':call['obs']} for call in calls]
        self.assertFalse(grader.authorized_calls({'allowed_reads':[]},actual,[],None,Path('/workspace')))

    def test_probe_requests_real_freeform_patch_and_keeps_gh_command_transport(self):
        from evaluation_codex import native_file_edit_operations
        from evaluation_tasks import load
        values=native_file_edit_operations('/workspace/output/result.txt','data\n')
        operations=[v for v in values if isinstance(v,dict)]
        self.assertIn('test ! -e /workspace/input/',values[-1])
        self.assertEqual([x['tool'] for x in operations],['apply_patch']*5)
        self.assertEqual([x['expect_failure'] for x in operations],[False]*4+[True])
        self.assertIn('*** Add File:',operations[0]['input'])
        self.assertIn('*** Update File:',operations[2]['input'])
        self.assertIn('*** Delete File:',operations[3]['input'])
        self.assertTrue(load(ROOT/'.github/evals/campaigns/boolean-contract.json').native_file_edit_probe)
        self.assertFalse(load(ROOT/'.github/evals/campaigns/gh-read.json').native_file_edit_probe)


if __name__=='__main__':unittest.main()
