"""Protected stock App Server transport; the host owns all enforcement deadlines."""
import ctypes,hashlib,json,os,queue,socket,stat,subprocess,sys,threading,time
from pathlib import Path
if ctypes.CDLL(None,use_errno=True).prctl(4,0,0,0,0)!=0:raise RuntimeError('non-dumpable controller required')
sys.path.insert(0,str(Path(__file__).resolve().parent))
from policy import MODEL,Stop,canonical,decode
payload=decode(sys.stdin.buffer.readline(65537))
exe=Path('/opt/codex/bin/codex');m=exe.lstat()
if not stat.S_ISREG(m.st_mode) or m.st_uid!=0 or m.st_mode&0o022 or hashlib.sha256(exe.read_bytes()).hexdigest()!=payload['codex_sha256']:raise Stop('official-runtime-substitution')
provider={'name':'metered','base_url':payload['relay_url'],'wire_api':'responses','env_key':'AEB_RELAY_TOKEN','requires_openai_auth':False,'request_max_retries':0,'stream_max_retries':0,'supports_websockets':False,'stream_idle_timeout_ms':15000}
if not payload['relay_url'].startswith('http://') or not payload['relay_url'].endswith(':8991/v1'):raise Stop('invalid-private-relay')
settings={'model_provider':'metered','model_providers':{'metered':provider},'model_catalog_json':'/opt/codex/direct-catalog.json','model_reasoning_effort':'low','service_tier':'default','web_search':'disabled'}
cmd=[str(exe)]
def flatten(prefix,value):
 if isinstance(value,dict):
  for k,v in value.items():yield from flatten(prefix+'.'+k,v)
 else:yield prefix,value
for key,value in settings.items():
 for name,v in flatten(key,value):cmd+=['-c',name+'='+json.dumps(v)]
cmd+=['app-server','--listen','stdio://']
Path('/home/agent/.codex').mkdir(exist_ok=True)
env={'PATH':'/opt/codex/bin:/usr/local/bin:/usr/bin:/bin','HOME':'/home/agent','CODEX_HOME':'/home/agent/.codex','AEB_RELAY_TOKEN':payload['trial_token']}
a,b=socket.socketpair();p=subprocess.Popen(cmd,stdin=b,stdout=b,stderr=subprocess.PIPE,env=env,cwd='/workspace',text=True,close_fds=True);b.close()
native_in=a.makefile('w');native_out=a.makefile('r');frames=[];pending=queue.Queue(maxsize=4096);errors=[];state={};err=[]
def emit(value):print(json.dumps(value),flush=True)
def reader():
 total=0
 try:
  for line in native_out:
   total+=len(line.encode())
   if total>8*1024*1024 or len(line)>1024*1024:raise Stop('native-capture-cap')
   frame=decode(line);frames.append(frame);emit({'frame':frame});pending.put(frame,timeout=1)
 except Exception:errors.append('native-parse-or-cap-failure')
 finally:state['transport_eof']=True;pending.put({'eof':True})
def stderr():
 for chunk in iter(lambda:p.stderr.read(4096),''):
  err.append(chunk)
  if sum(map(len,err))>65536:p.kill();break
r=threading.Thread(target=reader,daemon=True);e=threading.Thread(target=stderr,daemon=True);r.start();e.start()
def rpc(i,method,params):native_in.write(json.dumps({'id':i,'method':method,'params':params})+'\n');native_in.flush()
def wait(test):
 while True:
  value=pending.get(timeout=310)
  if value.get('eof'):raise Stop('early-producer-exit')
  if test(value):return value
status='unavailable';thread=turn=None;error=None
try:
 rpc(1,'initialize',{'clientInfo':{'name':'aeb_provider_preflight','version':'1'},'capabilities':{'experimentalApi':True}})
 if 'result' not in wait(lambda f:f.get('id')==1):raise Stop('initialize-error')
 native_in.write('{"method":"initialized"}\n');native_in.flush()
 rpc(5,'skills/extraRoots/set',{'extraRoots':['/skills']})
 if wait(lambda f:f.get('id')==5).get('result')!={}:raise Stop('native-skill-root-registration')
 rpc(2,'thread/start',{'model':MODEL,'modelProvider':'metered','cwd':'/workspace','approvalPolicy':'never','sandbox':'danger-full-access','experimentalRawEvents':True})
 thread=wait(lambda f:f.get('id')==2)['result']['thread']['id']
 rpc(3,'turn/start',{'threadId':thread,'input':[{'type':'text','text':'Use the native provider-smoke skill. Perform its local compatibility check, including failure recovery, apply_patch, verification and the harmless escalation denial. Do not use network tools or delegation.'}]})
 turn=wait(lambda f:f.get('id')==3)['result']['turn']['id']
 terminal=wait(lambda f:f.get('method')=='turn/completed')
 if terminal['params']['threadId']!=thread or terminal['params']['turn']['id']!=turn or terminal['params']['turn']['status']!='completed':raise Stop('turn-not-complete')
 rpc(4,'thread/read',{'threadId':thread,'includeTurns':True});state['thread_read']=wait(lambda f:f.get('id')==4)['result'];status='completed'
except Exception as failure:error=type(failure).__name__
finally:
 owned=p.poll() is None
 if owned:p.terminate()
 try:p.wait(timeout=3)
 except subprocess.TimeoutExpired:p.kill();p.wait()
 r.join(2);e.join(2)
 if errors or r.is_alive() or e.is_alive():status='unavailable';error='native-transport-failure'
 capture={'schema':'native-capture-v1','channel':'socketpair','status':status,'error':error,'frames':frames,'thread_id':thread,'turn_id':turn,'state':state,'shutdown_by_operator':owned,'producer_exit':p.returncode,'controller_dumpable':ctypes.CDLL(None).prctl(3,0,0,0,0),'yama_ptrace_scope':Path('/proc/sys/kernel/yama/ptrace_scope').read_text().strip()}
 emit({'capture':capture})
