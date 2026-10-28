"""One supervised native stdio session. Operator code; no model inference in qualification."""
import ctypes
import os
if ctypes.CDLL(None, use_errno=True).prctl(4, 0, 0, 0, 0) != 0:
    raise OSError(ctypes.get_errno(), 'PR_SET_DUMPABLE failed')
import http.server
import hashlib
import stat
import json
import pathlib
import queue
import subprocess
import socket
import sys
import threading
import time

payload=json.loads(sys.argv[1]); mode=payload.get('mode','normal')
frames=[]; requests=[]; state={}; pending=queue.Queue(); byte_count=0
base_script='''const a=await Promise.all([tools.exec_command({cmd:"printf parallel-one"}),tools.exec_command({cmd:"printf parallel-two"})]);for(const r of a)text(r.output);text((await tools.exec_command({cmd:"printf identical"})).output);text((await tools.exec_command({cmd:"printf identical"})).output);text(await tools.apply_patch("*** Begin Patch\\n*** Add File: /workspace/actual.txt\\n+actual-modification\\n*** End Patch"));text((await tools.exec_command({cmd:"exit 7"})).output);text("reported-only ghost-operation");'''
class Provider(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        size=int(self.headers['Content-Length']);assert size<2*1024*1024
        request=json.loads(self.rfile.read(size));requests.append(request)
        n=len(requests)
        script=payload.get('script',base_script)
        if mode!='normal':
            command='python3 -I /opt/qualification/attack.py '+mode+' '+str(os.getpid())+' '+str(state['producer_pid'])
            script='text((await tools.exec_command({cmd:'+json.dumps(command)+'})).output);'+(base_script if mode in ('fd-inject','ptrace','proc-mem','forged-output') else '')
        items=[{'type':'response.created','response':{'id':f'fixture-{n}'}}]
        if n==1:items.append({'type':'response.output_item.done','item':{'type':'custom_tool_call','call_id':'script-1','name':'exec','input':script}})
        else:items.append({'type':'response.output_item.done','item':{'type':'message','id':'answer','role':'assistant','content':[{'type':'output_text','text':'scripted fixture finished'}]}})
        items.append({'type':'response.completed','response':{'id':f'fixture-{n}','usage':{'input_tokens':0,'output_tokens':0,'total_tokens':0}}})
        wire=''.join('event: '+i['type']+'\ndata: '+json.dumps(i)+'\n\n' for i in items).encode()
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(wire)));self.end_headers();self.wfile.write(wire)

server=http.server.ThreadingHTTPServer(('127.0.0.1',8991),Provider)
threading.Thread(target=server.serve_forever,daemon=True).start()
settings=payload.get('config',{'model_provider':'fixture','model_providers':{'fixture':{'name':'fixture','base_url':'http://127.0.0.1:8991/v1','wire_api':'responses','requires_openai_auth':False}},'web_search':'disabled'})
# Configuration comes from the provider wrapper in integration tests; reject external routes.
provider=settings['model_providers'][settings['model_provider']]
assert provider['base_url']=='http://127.0.0.1:8991/v1'
executable=pathlib.Path('/opt/codex/bin/codex'); info=executable.lstat()
assert stat.S_ISREG(info.st_mode) and info.st_uid==0 and not info.st_mode&0o022
assert hashlib.sha256(executable.read_bytes()).hexdigest()=='b93f6811d3f653f0fb83be4050d857fb9abbb111dfa2ce160563327daff7f306'
cmd=[str(executable)]
for key,value in settings.items():
    # TOML supports inline tables; JSON object syntax does not. Flatten leaf settings.
    def flatten(prefix,v):
        if isinstance(v,dict):
            for k,x in v.items():yield from flatten(prefix+'.'+k,x)
        else:yield prefix,v
    for name,v in flatten(key,value):cmd.extend(['-c',name+'='+json.dumps(v)])
cmd+=['app-server','--listen','stdio://']
home='/home/agent/.codex';pathlib.Path(home).mkdir(exist_ok=True)
env={'PATH':'/opt/codex/bin:/usr/local/bin:/usr/bin:/bin','HOME':'/home/agent','CODEX_HOME':home}
if os.environ.get('OPENAI_API_KEY'):env['OPENAI_API_KEY']=os.environ['OPENAI_API_KEY']
channel=payload.get('channel','socketpair')
parent_socket=None
if channel=='socketpair':
    parent_socket,child_socket=socket.socketpair(socket.AF_UNIX,socket.SOCK_STREAM)
    p=subprocess.Popen(cmd,stdin=child_socket,stdout=child_socket,stderr=subprocess.PIPE,text=True,env=env,cwd='/workspace',close_fds=True)
    child_socket.close()
    native_in=parent_socket.makefile('w');native_out=parent_socket.makefile('r')
elif channel=='pipe':
    p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env,cwd='/workspace',close_fds=True)
    native_in,native_out=p.stdin,p.stdout
else:raise ValueError('unsupported channel')
state['producer_pid']=p.pid
errors=[]
def reader():
    global byte_count
    try:
        for line in native_out:
            byte_count+=len(line.encode());assert byte_count<8*1024*1024
            frame=json.loads(line);frames.append(frame);pending.put(frame)
    except Exception as e:errors.append(type(e).__name__)
    finally:pending.put({'transport_eof':True})
stderr=[]
def read_error():
    for block in iter(lambda:p.stderr.read(4096),''):
        stderr.append(block)
        if sum(map(len,stderr))>1024*1024:p.kill();break
threading.Thread(target=reader,daemon=True).start();threading.Thread(target=read_error,daemon=True).start()
def write(value):native_in.write(json.dumps(value)+'\n');native_in.flush()
def rpc(n,method,params):write({'id':n,'method':method,'params':params})
def wait(predicate,timeout=30):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        event=pending.get(timeout=max(.01,deadline-time.monotonic()))
        if event.get('transport_eof'):raise RuntimeError('producer terminated before scoped completion')
        if predicate(event):return event
    raise TimeoutError('native deadline')
status='unavailable';error=None;thread_id=None;turn_id=None
try:
    rpc(1,'initialize',{'clientInfo':{'name':'aeb_qualification','version':'1'},'capabilities':{'experimentalApi':True}})
    response=wait(lambda e:e.get('id')==1);assert 'result' in response
    write({'method':'initialized'})
    rpc(2,'thread/start',{'model':payload.get('model','gpt-5.6-sol'),'modelProvider':settings['model_provider'],'cwd':'/workspace','approvalPolicy':'never','sandbox':payload.get('sandbox','danger-full-access'),'ephemeral':False})
    response=wait(lambda e:e.get('id')==2);thread_id=response['result']['thread']['id']
    rpc(3,'turn/start',{'threadId':thread_id,'input':[{'type':'text','text':payload.get('instruction','Execute the supplied scripted fixture.')} ]})
    response=wait(lambda e:e.get('id')==3);turn_id=response['result']['turn']['id']
    event=wait(lambda e:e.get('method')=='turn/completed' and e.get('params',{}).get('threadId')==thread_id and e.get('params',{}).get('turn',{}).get('id')==turn_id,timeout=15)
    assert event['params']['turn']['status']=='completed'
    # Require the same live producer to return the authoritative scoped turn population.
    rpc(4,'thread/read',{'threadId':thread_id,'includeTurns':True})
    response=wait(lambda e:e.get('id')==4);assert 'result' in response
    state['thread_read']=response['result']
    status='completed'
except Exception as e:error=type(e).__name__+': '+str(e)
finally:
    shutdown_by_operator=p.poll() is None
    if shutdown_by_operator:p.terminate()
    try:p.wait(timeout=5)
    except subprocess.TimeoutExpired:p.kill();p.wait()
    server.shutdown()
    if errors:status='unavailable';error='native transport parse/size failure'
    result={'schema':'native-capture-v1','channel':channel,'status':status,'error':error,'controller_pid':os.getpid(),'producer_pid':p.pid,'shutdown_by_operator':shutdown_by_operator,'producer_exit':p.returncode,'thread_id':thread_id,'turn_id':turn_id,'frames':frames,'state':state,'provider_requests':len(requests),'stderr':''.join(stderr),'controller_dumpable':ctypes.CDLL(None).prctl(3,0,0,0,0),'yama_ptrace_scope':pathlib.Path('/proc/sys/kernel/yama/ptrace_scope').read_text().strip()}
    print(json.dumps(result),flush=True)
# This exit describes capture delivery, not execution success; the host admits the envelope.
sys.exit(0)
