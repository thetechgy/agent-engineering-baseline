"""Native execution admission, independent of grader judgments and model proposals."""
class Unavailable(ValueError):
    pass

def require(value,reason):
    if not value:raise Unavailable(reason)

def admit(capture):
    require(capture.get('schema')=='native-capture-v1','unknown capture schema')
    require(capture.get('channel')=='socketpair','unqualified capture transport')
    require(capture.get('controller_dumpable')==0,'controller memory protection absent')
    require(int(capture.get('yama_ptrace_scope','0'))>=1,'same-UID memory boundary unavailable')
    require(capture.get('status')=='completed','capture incomplete')
    require(capture.get('shutdown_by_operator') is True,'producer ended unexpectedly')
    require(capture.get('producer_exit') in (0,-15),'producer shutdown failed')
    tid,turn=capture['thread_id'],capture['turn_id'];require(tid and turn,'missing execution scope')
    starts={};ends={};done=False;responses={}
    allowed={'userMessage','agentMessage','reasoning','plan','commandExecution','fileChange'}
    for event in capture['frames']:
        if 'id' in event and 'method' not in event:
            require(event['id'] not in responses,'duplicate RPC response')
            require('result' in event and 'error' not in event,'RPC failure')
            responses[event['id']]=event['result']
        method=event.get('method');p=event.get('params',{})
        if method=='error':raise Unavailable('native error')
        if method=='turn/completed':
            require(not done and p.get('threadId')==tid and p.get('turn',{}).get('id')==turn,'contradictory terminal scope')
            require(p['turn']['status']=='completed','turn incomplete');done=True
        if method in ('item/started','item/completed'):
            require(not done,'item after terminal completion')
            require(p.get('threadId')==tid and p.get('turnId')==turn,'foreign execution scope')
            item=p['item'];require(item['type'] in allowed,'unsupported native item')
            target=starts if method=='item/started' else ends
            require(item['id'] not in target,'duplicate native lifecycle identity')
            if method=='item/completed':
                require(item['id'] in starts,'completion without submission')
                before=starts[item['id']];require(before['type']==item['type'],'native kind changed')
                for key in ('command','cwd','changes'):
                    if key in item:require(item[key]==before.get(key),'native operation changed')
            target[item['id']]=item
    require(done and set(starts)==set(ends),'incomplete native item population')
    require(set(responses)=={1,2,3,4},'incomplete RPC population')
    require(responses[2]['thread']['id']==tid and responses[3]['turn']['id']==turn,'unbound launch response')
    snapshot=responses[4]['thread'];require(snapshot['id']==tid and len(snapshot['turns'])==1,'snapshot scope changed')
    terminal=snapshot['turns'][0];require(terminal['id']==turn and terminal['status']=='completed','snapshot incomplete')
    items=terminal['items'];require(len({i['id'] for i in items})==len(items),'duplicate snapshot identity')
    require({i['id']:i for i in items}==ends,'live/snapshot population disagreement')
    commands=[];patches=[]
    for item in ends.values():
        if item['type']=='commandExecution':
            status=item['status'];code=item.get('exitCode')
            require(status in ('completed','failed','declined','interrupted'),'unknown execution state')
            if status in ('completed','failed'):
                require(isinstance(code,int) and not isinstance(code,bool),'missing execution exit')
                require((code==0)==(status=='completed'),'contradictory exit status')
                require(item.get('processId') is not None,'execution start unknown')
            else:require(code is None,'non-execution has exit status')
            commands.append(item)
        elif item['type']=='fileChange':
            require(item['status'] in ('completed','failed','declined'),'unknown file outcome');patches.append(item)
    return {'scope':{'thread_id':tid,'turn_id':turn},'commands':commands,'patches':patches,'complete':True}
