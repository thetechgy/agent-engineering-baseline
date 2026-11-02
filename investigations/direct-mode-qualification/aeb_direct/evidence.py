"""Strict Direct capture admission. Caller must authenticate the controller separately."""
import json,shlex,re
from .lifecycle import observe
class Unavailable(ValueError): pass
def require(ok,why):
    if not ok: raise Unavailable(why)
def admit(c):
    native=observe(c)
    native_commands={i['id']:i for i in native['commands']}
    advertised={t['name'] for group in c['tool_catalog'] for t in group.get('tools',[])}
    require('exec_command' in advertised and 'apply_patch' in advertised and 'exec' not in advertised,'wrong direct catalog')
    require(all(r.get('model')=='gpt-5.6-sol' for r in c['provider_request_bodies']),'wrong provider model route')
    require(c.get('status')=='completed' and c.get('channel')=='socketpair','incomplete capture')
    require(c.get('controller_dumpable')==0 and int(c.get('yama_ptrace_scope','0'))>=1,'unprotected producer')
    require(c.get('shutdown_by_operator') and c.get('producer_exit') in (0,-15) and c.get('state',{}).get('transport_eof'),'producer continuity lost')
    tid,turn=c['thread_id'],c['turn_id'];calls={};outputs={};done=False;rpc={}
    for f in c['frames']:
        q=f.get('params',{});m=f.get('method')
        if 'id' in f and m is None:
            require(f['id'] not in rpc and 'result' in f and 'error' not in f,'RPC contradiction');rpc[f['id']]=f['result']
        if m=='turn/completed':
            require(not done and q['threadId']==tid and q['turn']['id']==turn and q['turn']['status']=='completed','terminal scope mismatch');done=True
        if m=='error': raise Unavailable('native error')
        if m=='rawResponseItem/completed':
            require(not done and q['threadId']==tid and q['turnId']==turn,'foreign or late raw item')
            i=q['item'];kind=i['type']
            require(kind not in ('custom_tool_call','custom_tool_call_output'),'unexpected tool surface')
            if kind not in ('function_call','function_call_output'):continue
            key=i['call_id'];target=calls if kind=='function_call' else outputs
            require(key not in target,'duplicate call identity')
            if kind=='function_call_output':require(key in calls,'outcome precedes submission')
            target[key]=i
    require(done and set(rpc)=={1,2,3,4,5} and rpc[5]=={},'incomplete native closure')
    require(rpc[2]['thread']['id']==tid and rpc[3]['turn']['id']==turn,'launch mismatch')
    require(rpc[4]['thread']['id']==tid and len(rpc[4]['thread']['turns'])==1 and rpc[4]['thread']['turns'][0]['id']==turn and rpc[4]['thread']['turns'][0]['status']=='completed','snapshot mismatch')
    require(set(calls)==set(outputs),'missing tool outcome')
    expected=c['provider_submissions']
    require(len(expected)==len(calls) and len({i['call_id'] for i in expected})==len(expected),'provider inventory mismatch')
    result=[];executed=set()
    require(not native['patches'],'unsubmitted native patch')
    for e in expected:
        i=calls[e['call_id']];require(all(i[k]==e[k] for k in ('call_id','name','arguments')),'original arguments mismatch')
        require(i['name']=='exec_command','unqualified direct tool')
        def unique(pairs):
            d={}
            for k,v in pairs:
                require(k not in d,'duplicate argument key');d[k]=v
            return d
        args=json.loads(i['arguments'],object_pairs_hook=unique);require(isinstance(args,dict),'non-object arguments')
        output=outputs[e['call_id']]['output'];require(isinstance(output,str),'unsupported output')
        require(not re.search(r'Warning: truncated output|…[0-9]+ tokens truncated…|\.\.\. [0-9]+ bytes omitted \.\.\.',output),'incomplete output')
        require('Process running with session ID' not in output.partition('\nOutput:\n')[0],'unclosed command process')
        if args.get('sandbox_permissions')=='require_escalated':
            require('approval policy is Never' in output and e['call_id'] not in native_commands,'denial outcome not qualified')
        else:
            require(e['call_id'] in native_commands and native_commands[e['call_id']]['status'] in ('completed','failed'),'execution correlation missing or interrupted')
            item=native_commands[e['call_id']]
            require(shlex.split(item['command'])==['/bin/sh','-lc',args['cmd']] and item['cwd']=='/workspace','native executed arguments changed')
            executed.add(e['call_id'])
        result.append({'action':'exec_command','action_input':args,'observation':output,'native_call_id':e['call_id']})
    require(set(native_commands)==executed,'unsubmitted native execution')
    return result


def mutation_controls(c):
    """Synthetic corruption of a real capture; never fed to an oracle."""
    import copy
    labels=('missing-output','foreign-turn','changed-arguments','duplicate-call','missing-terminal','producer-loss','output-before-call','changed-native-command','unsubmitted-native-command','incomplete-output')
    for label in labels:
        d=copy.deepcopy(c)
        frames=d['frames']
        raw=[f for f in frames if f.get('method')=='rawResponseItem/completed' and f['params']['item']['type']=='function_call']
        if label=='missing-output':d['frames']=[f for f in frames if not (f.get('method')=='rawResponseItem/completed' and f['params']['item']['type']=='function_call_output')]
        elif label=='foreign-turn':raw[0]['params']['turnId']='foreign'
        elif label=='changed-arguments':raw[0]['params']['item']['arguments']='{}'
        elif label=='duplicate-call':frames.insert(frames.index(raw[0]),copy.deepcopy(raw[0]))
        elif label=='missing-terminal':d['frames']=[f for f in frames if f.get('method')!='turn/completed']
        elif label=='producer-loss':d['shutdown_by_operator']=False
        elif label=='output-before-call':
            outcome=next(f for f in frames if f.get('method')=='rawResponseItem/completed' and f['params']['item']['type']=='function_call_output');frames.remove(outcome);frames.insert(frames.index(raw[0]),outcome)
        elif label=='changed-native-command':
            for f in frames:
                if f.get('method') in ('item/started','item/completed') and f['params']['item']['type']=='commandExecution':f['params']['item']['command']='changed-native-command'
                if f.get('id')==4:
                    for item in f['result']['thread']['turns'][0]['items']:
                        if item['type']=='commandExecution':item['command']='changed-native-command'
        elif label=='unsubmitted-native-command':
            terminal=next(f for f in frames if f.get('method')=='turn/completed')
            for method in ('item/started','item/completed'):
                extra=copy.deepcopy(next(f for f in frames if f.get('method')==method and f['params']['item']['type']=='commandExecution'))
                extra['params']['item']['id']='unsubmitted-native-id';frames.insert(frames.index(terminal),extra)
            snapshot=next(f for f in frames if f.get('id')==4)['result']['thread']['turns'][0]['items']
            extra=copy.deepcopy(next(i for i in snapshot if i['type']=='commandExecution'));extra['id']='unsubmitted-native-id';snapshot.append(extra)
        else:
            output=next(f for f in frames if f.get('method')=='rawResponseItem/completed' and f['params']['item']['type']=='function_call_output')['params']['item'];output['output']+='\nWarning: truncated output (original token count: 99999)'
        try:admit(d)
        except (ValueError,KeyError):continue
        raise RuntimeError('false admission: '+label)
    return list(labels)


def known_denied_attempts(c):
    """Retain positive attempted-action facts even when full admission is unavailable.

    The trusted controller/provider ledger is a prerequisite. Absence here is
    deliberately not an authorization verdict.
    """
    ledger={e['call_id']:e for e in c.get('provider_submissions',[])}
    found=[]
    for f in c.get('frames',[]):
        q=f.get('params',{});i=q.get('item',{});e=ledger.get(i.get('call_id'))
        if f.get('method')!='rawResponseItem/completed' or i.get('type')!='function_call' or not e:continue
        if q.get('threadId')!=c.get('thread_id') or q.get('turnId')!=c.get('turn_id'):continue
        if not all(i.get(k)==e.get(k) for k in ('name','arguments')):continue
        try:a=json.loads(i['arguments'])
        except (ValueError,TypeError):continue
        if isinstance(a,dict) and a.get('sandbox_permissions')=='require_escalated':found.append(i['call_id'])
    return found
