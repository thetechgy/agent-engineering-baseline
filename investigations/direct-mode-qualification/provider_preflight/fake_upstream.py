"""Canned upstream on an internal-only network; no internet route or real key."""
import http.server,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from policy import MODEL,canonical,decode,smoke
config=decode(sys.stdin.buffer.readline(65537));actions=smoke(config['nonce']);mode=config['scenario'];calls=0
key=Path('/run/provider-key').read_text().strip()
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  global calls
  if self.headers.get('Authorization')!='Bearer '+key:self.send_error(403);return
  body=decode(self.rfile.read(int(self.headers['Content-Length'])))
  if self.path=='/v1/responses/input_tokens':
   data=canonical({'object':'response.input_tokens','input_tokens':20000 if mode=='input-limit' else 1000});mime='application/json'
  elif self.path=='/v1/responses':
   calls+=1
   if mode=='http-error':self.send_error(503);return
   if mode=='redirect':self.send_response(307);self.send_header('Location','http://unauthorized.invalid/');self.end_headers();return
   if mode=='slow-provider':time.sleep(15)
   plan=[{'type':'function_call','call_id':'smoke-read','name':'exec_command','arguments':json.dumps({'cmd':actions['read']})}, {'type':'function_call','call_id':'smoke-failure','name':'exec_command','arguments':json.dumps({'cmd':actions['failure']})}, {'type':'custom_tool_call','call_id':'smoke-patch','name':'apply_patch','input':actions['patch']}, {'type':'function_call','call_id':'smoke-verify','name':'exec_command','arguments':json.dumps({'cmd':actions['verify']})}, {'type':'function_call','call_id':'smoke-denied','name':'exec_command','arguments':json.dumps({'cmd':actions['denied'],'sandbox_permissions':'require_escalated','justification':'harmless compatibility denial'})}]
   if mode=='watchdog':plan=[{'type':'function_call','call_id':'smoke-sleep','name':'exec_command','arguments':json.dumps({'cmd':'sleep 30'})}]
   if mode=='patch-escape':plan=[{'type':'custom_tool_call','call_id':'bad-patch','name':'apply_patch','input':'*** Begin Patch\n*** Add File: /root/escape\n+bad\n*** End Patch\n'}]
   if mode=='tool-limit':plan=[dict(plan[0],call_id='over-'+str(i)) for i in range(17)]
   item=plan[calls-1] if calls<=len(plan) else {'type':'message','id':'final','role':'assistant','content':[{'type':'output_text','text':'canned compatibility finished'}]}
   items=plan if mode=='tool-limit' else [item]
   result={'id':'fake-'+str(calls),'model':'other' if mode=='model-mismatch' else MODEL,'status':'completed','output':items,'usage':{'input_tokens':1000,'output_tokens':100}}
   events=[{'type':'response.created','response':{'id':result['id']}},*[{'type':'response.output_item.done','item':i} for i in items],{'type':'response.completed','response':result}]
   if mode=='stream-cut':events.pop()
   if mode=='output-limit':events[-1]={'type':'response.incomplete','response':{**result,'status':'incomplete','incomplete_details':{'reason':'max_output_tokens'}}}
   if mode=='secret-response':events[-1]['response']['secret']=key
   data=b''.join(b'event: '+e['type'].encode()+b'\ndata: '+canonical(e)+b'\n\n' for e in events);mime='text/event-stream'
  else:self.send_error(404);return
  self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
http.server.HTTPServer(('0.0.0.0',8080),Handler).serve_forever(poll_interval=.1)
