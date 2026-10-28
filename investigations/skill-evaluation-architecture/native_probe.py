"""Real Codex/App Server probe; canned loopback SSE, no inference or credentials."""
import http.server, json, os, pathlib, queue, subprocess, threading, time
PROTECTED='protected' in __import__('sys').argv
ROOT=pathlib.Path('/workspace')
OUTPUT=pathlib.Path('/opt/native-capture') if PROTECTED else ROOT
if PROTECTED: OUTPUT.mkdir(mode=0o700)
else: pathlib.Path('/home/agent/.codex').mkdir(exist_ok=True)
SCRIPT='''const a = await Promise.all([tools.exec_command({cmd:"printf parallel-one"}), tools.exec_command({cmd:"printf parallel-two"})]); for (const r of a) text(r.output); text((await tools.exec_command({cmd:"printf identical"})).output); text((await tools.exec_command({cmd:"printf identical"})).output); text(await tools.apply_patch("*** Begin Patch\\n*** Add File: /workspace/actual.txt\\n+actual-modification\\n*** End Patch")); text((await tools.exec_command({cmd:"exit 7"})).output); text("reported-only: never executed ghost-command");'''
if len(__import__('sys').argv)>1 and __import__('sys').argv[1]=='interrupt':
 SCRIPT='text(await tools.exec_command({cmd:"sleep 20",yield_time_ms:1000})); await new Promise(r=>setTimeout(r,20000));'
if len(__import__('sys').argv)>1 and __import__('sys').argv[1]=='decline':
 SCRIPT='text(await tools.exec_command({cmd:"touch /tmp/poc-declined",sandbox_permissions:"require_escalated",justification:"Synthetic denial control"}));'
requests=[]
class Server(http.server.BaseHTTPRequestHandler):
 def log_message(self,*a): pass
 def do_POST(self):
  data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  requests.append(data)
  n=len(requests)
  events=[{'type':'response.created','response':{'id':f'resp-{n}'}}]
  if n==1: events.append({'type':'response.output_item.done','item':{'type':'custom_tool_call','call_id':'script-1','name':'exec','input':SCRIPT}})
  else: events.append({'type':'response.output_item.done','item':{'type':'message','id':'answer','role':'assistant','content':[{'type':'output_text','text':'fixture finished'}]}})
  events.append({'type':'response.completed','response':{'id':f'resp-{n}','usage':{'input_tokens':0,'output_tokens':0,'total_tokens':0}}})
  body=''.join('event: '+e['type']+'\ndata: '+json.dumps(e)+'\n\n' for e in events).encode()
  self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
server=http.server.ThreadingHTTPServer(('127.0.0.1',8765),Server)
threading.Thread(target=server.serve_forever,daemon=True).start()
config=['model_provider="fixture"','model_providers.fixture.name="fixture"','model_providers.fixture.base_url="http://127.0.0.1:8765/v1"','model_providers.fixture.wire_api="responses"','model_providers.fixture.requires_openai_auth=false','model_providers.fixture.supports_websockets=false','web_search="disabled"']
cmd=['/opt/codex/bin/codex']
for c in config:cmd+=['-c',c]
cmd+=['app-server']
proc=None
ws=None
if PROTECTED:
 from websockets.sync.client import connect
 for attempt in range(50):
  try:ws=connect('ws://127.0.0.1:8766');break
  except OSError:time.sleep(.1)
 else:raise RuntimeError('native WebSocket readiness failed')
else: proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env={'PATH':'/opt/codex/bin:/usr/local/bin:/usr/bin:/bin','HOME':'/home/agent','CODEX_HOME':'/home/agent/.codex'},cwd=ROOT)
q=queue.Queue(); events=[]; raw_frames=[]
def read():
 try:
  for line in (iter(ws.recv,None) if PROTECTED else proc.stdout):
   raw_frames.append(line)
   if sum(map(len,raw_frames))>8*1024*1024:raise ValueError('native capture budget')
   try:q.put(json.loads(line))
   except ValueError:q.put({'malformed':True})
 except Exception as error:q.put({'transport_error':type(error).__name__})
 finally:q.put({'eof':True})
threading.Thread(target=read,daemon=True).start()
def write(obj):
 line=json.dumps(obj)
 if PROTECTED:ws.send(line)
 else:proc.stdin.write(line+'\n');proc.stdin.flush()
def send(i,method,params):write({'id':i,'method':method,'params':params})
def until(predicate,seconds=65):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  e=q.get(timeout=max(.1,end-time.monotonic()));events.append(e)
  if e.get('eof') or e.get('transport_error') or e.get('malformed'): raise RuntimeError('native transport incomplete')
  if e.get('method')=='item/commandExecution/requestApproval':
   write({'id':e['id'],'result':{'decision':'decline'}})
  if predicate(e):return e
 raise TimeoutError()
try:
 send(1,'initialize',{'clientInfo':{'name':'qualification_fixture','version':'1'},'capabilities':{'experimentalApi':True}})
 init=until(lambda e:e.get('id')==1)
 write({'method':'initialized'})
 send(2,'thread/start',{'model':'gpt-5.6-sol','modelProvider':'fixture','cwd':str(ROOT),'approvalPolicy':('on-request' if 'decline' in __import__('sys').argv else 'never'),'sandbox':('read-only' if 'decline' in __import__('sys').argv else 'danger-full-access'),'ephemeral':True})
 thread=until(lambda e:e.get('id')==2)
 if 'error' in thread:raise RuntimeError(str(thread))
 send(3,'turn/start',{'threadId':thread['result']['thread']['id'],'input':[{'type':'text','text':'Execute the fixed fixture script.'}]})
 if 'interrupt' in __import__('sys').argv:
  until(lambda e:e.get('method')=='item/started' and e.get('params',{}).get('item',{}).get('type')=='commandExecution')
  send(4,'turn/interrupt',{'threadId':thread['result']['thread']['id'],'turnId':next(e['params']['turnId'] for e in reversed(events) if e.get('method')=='item/started')})
 until(lambda e:e.get('method')=='turn/completed')
finally:
 if PROTECTED:ws.close()
 else:
  proc.terminate()
  try:proc.wait(timeout=5)
  except subprocess.TimeoutExpired:proc.kill();proc.wait()
 server.shutdown()
 (OUTPUT/'wire.jsonl').write_text('\n'.join(raw_frames))
 (OUTPUT/'events.json').write_text(json.dumps(events,indent=2))
 (OUTPUT/'requests.json').write_text(json.dumps(requests,indent=2))
 (OUTPUT/'stderr.txt').write_text('WebSocket connection closed; server lifecycle owned by container' if PROTECTED else proc.stderr.read())
print(json.dumps({'requests':len(requests),'native_items':[e['params']['item'] for e in events if e.get('method')=='item/completed'],'actual_file':(ROOT/'actual.txt').exists(),'declined_file_exists':pathlib.Path('/tmp/poc-declined').exists()}))
