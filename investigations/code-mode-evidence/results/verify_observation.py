"""Offline experimental census checks; trusted operator captures, never grades.

Run after verify_archives.py. Producer provenance is a separate prerequisite;
this validates retained contents, not an arbitrary caller's authenticity claim.
"""
import base64
import copy
import json
from pathlib import Path
import sys
import zipfile


def census(records, outer):
    try:
        assert records[0]['stage']=='scope_open' and records[-1]['stage']=='scope_closed'
        assert sum(r['stage']=='scope_open' for r in records)==1
        assert sum(r['stage']=='scope_closed' for r in records)==1
        assert records[0]['outer']==outer
        assert all(r['scope']==records[0]['scope'] for r in records)
        entered=[r for r in records if r['stage']=='callback_entered']
        assert [r['callback'] for r in entered]==list(range(1,len(entered)+1))
        assert records[-1]['callbacks']==len(entered)
        phases={}
        serialized=[]
        for record in records:
            stage=record['stage']
            assert stage in {'scope_open','callback_entered','serialized','runtime_queued','scope_closed'}
            if stage=='callback_entered':
                assert record['callback'] not in phases
                phases[record['callback']]=[stage]
            if stage in ('serialized','runtime_queued'):
                callback=record['callback']
                expected=['callback_entered'] if stage=='serialized' else ['callback_entered','serialized']
                assert phases[callback]==expected
                phases[callback].append(stage)
                if stage=='serialized':
                    assert type(record['arguments_complete']) is bool
                    assert type(record['input_present']) is bool
                    serialized.append(record)
        # A callback with no serialized result still belongs to the census.
        arguments_complete=(len(serialized)==len(entered)
                            and all(r['arguments_complete'] for r in serialized))
        queued=[r['runtime_tool_call_id'] for r in records if r['stage']=='runtime_queued']
        assert len(queued)==len(set(queued))
        return dict(callback_inventory_complete=True,arguments_complete=arguments_complete,
                    callback_count=len(entered))
    except (AssertionError,KeyError,TypeError,IndexError):
        return dict(callback_inventory_complete=False,arguments_complete=False,callback_count=None)


def protected(payload, expected_binary):
    try:
        assert payload['gate']['producer_sha256']==expected_binary
        assert not payload['gate']['producer_failed']
        assert not payload['gate'].get('operator_transport_cut',False)
        assert len(payload['gate']['accepted'])==len(payload['gate']['rejected'])==1
        assert payload['capture']['status']=='completed'
        proxy=payload['proxy']
        assert not any(r.get('observer_loss') or r.get('retained') is False for r in proxy)
        executes=[r['message'] for r in proxy if r['method']=='Execute' and r['direction']=='request']
        assert len(executes)==1
        execution=executes[0]
        submitted=[f['params']['item'] for f in payload['capture']['frames']
                   if f.get('method')=='rawResponseItem/completed'
                   and f['params']['item'].get('type') in ('custom_tool_call','function_call')]
        assert len(submitted)==1 and submitted[0]['call_id']==execution['tool_call_id']
        result=census(payload['journal'],execution['tool_call_id'])
        assert result['callback_inventory_complete']
        closed=[r['message']['cell_closed'] for r in proxy if r['method']=='OpenSession'
                and r['direction']=='response' and 'cell_closed' in r['message']]
        assert len(closed)==1 and closed[0]['execution_id']==execution['execution_id']
        calls=[r['message'] for r in proxy if r['method']=='SubscribeToToolCalls' and r['direction']=='response']
        assert sorted(int(c['sequence']) for c in calls)==list(range(1,int(closed[0].get('final_tool_call_sequence',0))+1))
        for call in calls:
            assert call['execution_id']==closed[0]['execution_id'] and call['cell_id']==closed[0]['cell_id']
            identified=next(r for r in payload['journal'] if r['stage']=='runtime_queued'
                            and r['runtime_tool_call_id']==call['runtime_tool_call_id'])
            serialized=next(r for r in payload['journal'] if r['stage']=='serialized'
                            and r['callback']==identified['callback'])
            assert serialized['arguments_complete'] and serialized['input_present']
            assert serialized['arguments']==json.loads(base64.b64decode(call['input_json']))
            assert sum(r['method']=='CompleteToolCall' and r['direction']=='request'
                       and r['message']['invocation_id']==call['invocation_id'] for r in proxy)==1
        return dict(**result,forwarded_sequence_complete=True,
                    production_security_admission='unavailable-no-production-integration')
    except (AssertionError,KeyError,TypeError,IndexError,StopIteration,ValueError):
        return dict(callback_inventory_complete=False,arguments_complete=False,
                    forwarded_sequence_complete=False,
                    production_security_admission='unavailable')


def main(path):
    with zipfile.ZipFile(path) as archive:
        entries=archive.infolist()
        assert len(entries)<100 and sum(e.file_size for e in entries)<16*1024*1024
        assert len({e.filename for e in entries})==len(entries)
        def read(name): return json.loads(archive.read(name))
        expected=archive.read('patch-binary.sha256').decode().split()[0]
        rows={profile:protected(read('protected/'+profile+'.json'),expected)
              for profile in ('empty','denied','oversized','isolation')}
        assert all(row['callback_inventory_complete'] for row in rows.values())
        assert [rows[p]['arguments_complete'] for p in rows]==[True,True,False,True]
        normal=read('protected/denied.json')
        controls=[]
        for label in ('missing-closure','missing-entry','wrong-outer','wrong-producer','observer-loss','incomplete-arguments'):
            mutated=copy.deepcopy(normal)
            if label=='missing-closure': mutated['journal'].pop()
            elif label=='missing-entry': mutated['journal']=[r for r in mutated['journal'] if r['stage']!='callback_entered']
            elif label=='wrong-outer': mutated['journal'][0]['outer']='unrelated'
            elif label=='wrong-producer': mutated['gate']['producer_sha256']='0'*64
            elif label=='observer-loss': mutated['proxy'].append(dict(observer_loss=True))
            else: next(r for r in mutated['journal'] if r['stage']=='serialized')['arguments_complete']=False
            decision=protected(mutated,expected)
            assert not (decision['callback_inventory_complete'] and decision['arguments_complete'])
            controls.append(label)
        interrupted=[json.loads(line) for line in archive.read('protected/interrupted-callbacks.jsonl').splitlines()]
        assert not census(interrupted,interrupted[0]['outer'])['callback_inventory_complete']
        transport=read('protected/transport-gate.json')
        assert transport['operator_transport_cut'] and transport['transport_closed'] and not transport['producer_failed']
        replacement=read('protected/replacement.json')
        assert replacement['original_container']!=replacement['replacement_container']
        assert replacement['admission']=='unavailable-producer-instance-changed'
        print(json.dumps(dict(schema='offline-observation-check-v1',rows=rows,
            synthetic_mutation_controls=controls,actual_missing_closure_rejected=True,
            actual_transport_and_replacement_fenced=True,producer_authentication='separate-operator-prerequisite'),indent=2))


if __name__=='__main__': main(Path(sys.argv[1]))
