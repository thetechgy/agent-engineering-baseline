"""Required fake-upstream controls over real metering code; no provider connection."""
import copy,hashlib,http.client,http.server,json,os,tempfile,threading,time,unittest
from pathlib import Path
from policy import MODEL,CATALOG_SHA,Policy,Stop,canonical,digest
from relay import Relay,Upstream,read_secret
NONCE='a'*32
CATALOG=json.loads(Path(__file__).with_name('tool-catalog.json').read_text())
def request(n=1):return {'model':MODEL,'stream':True,'input':[{'type':'additional_tools','tools':CATALOG},{'type':'message','role':'user','content':str(n)}],'reasoning':{'effort':'low'}}
def wire(items=(),*,model=MODEL,status='completed',input_tokens=1000,output_tokens=100):
 response={'id':'fake','model':model,'status':status,'output':list(items),'usage':{'input_tokens':input_tokens,'output_tokens':output_tokens}}
 events=[{'type':'response.created','response':{'id':'fake'}},*[{'type':'response.output_item.done','item':i} for i in items],{'type':'response.completed','response':response}]
 return b''.join(b'data: '+canonical(e)+b'\n\n' for e in events)
class Fake:
 def __init__(self,scenario='normal'):self.paths=[];self.scenario=scenario
 def post(self,path,body,timeout):
  self.paths.append(path)
  if self.scenario=='transport':raise TimeoutError()
  if path.endswith('input_tokens'):return canonical({'object':'response.input_tokens','input_tokens':20000 if self.scenario=='input-cap' else 1000})
  return wire()
class Controls(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def relay(self,policy=None,fake=None):return Relay(policy or Policy(NONCE,count_fee=0,fake=True),fake or Fake(),'trial-token-'+'x'*32,self.root/'audit.jsonl')
 def test_exact_catalog_and_live_block(self):
  self.assertEqual(digest(CATALOG),CATALOG_SHA)
  with self.assertRaises(Stop):Upstream('never-read-real-key')
  with self.assertRaises(Stop):Policy(NONCE).prepare(request())
 def test_restart_and_ledger_substitution_fail_closed(self):
  r=self.relay()
  with self.assertRaises(Stop):self.relay()
  r.audit.unlink();r.audit.write_text('replacement');r.audit.chmod(0o600)
  with self.assertRaises(Stop):r.record('must-not-accept')
 def test_atomic_reservation_and_no_refund_after_failure(self):
  upstream=Fake('transport');r=self.relay(fake=upstream)
  with self.assertRaises(Stop):r.request(canonical(request()))
  with self.assertRaises(Stop):r.request(canonical(request(2)))
  self.assertEqual(upstream.paths,['/v1/responses/input_tokens']);self.assertIsNotNone(r.policy.closed)
 def test_eight_requests_and_replay(self):
  r=self.relay()
  for i in range(8):r.request(canonical(request(i)))
  self.assertEqual(r.policy.reserved,8*(5000+20480))
  with self.assertRaises(Stop) as e:r.request(canonical(request(9)))
  self.assertEqual(e.exception.category,'inconclusive-limit')
 def test_input_dollar_and_time_caps(self):
  for field,value in [('per_input',999),('max_input',999),('reserved',1000000),('deadline',0)]:
   p=Policy(NONCE,count_fee=1,fake=True);setattr(p,field,value)
   folder=self.root/field;folder.mkdir();r=Relay(p,Fake(),'trial-token-'+'x'*32,folder/'audit.jsonl')
   with self.assertRaises(Stop) as e:r.request(canonical(request()))
   self.assertEqual(e.exception.category,'inconclusive-limit')
 def test_generation_dollar_limit_never_forwards(self):
  p=Policy(NONCE,count_fee=0,fake=True);p.reserved=990000;r=self.relay(p)
  with self.assertRaises(Stop) as e:r.request(canonical(request()))
  self.assertEqual(e.exception.category,'inconclusive-limit');self.assertEqual(r.upstream.paths,['/v1/responses/input_tokens'])
 def test_zero_retries_and_usage_reserve_latch(self):
  p=Policy(NONCE,count_fee=3,fake=True);r=self.relay(p)
  r.request(canonical(request()));reserved=p.reserved
  with self.assertRaises(Stop):r.request(canonical(request()))
  self.assertEqual(p.reserved,reserved)
  rows=[json.loads(s) for s in (self.root/'audit.jsonl').read_text().splitlines()];previous='0'*64
  for index,row in enumerate(rows):
   self.assertEqual((row['sequence'],row['previous']),(index,previous));previous=hashlib.sha256(canonical(row)).hexdigest()
 def test_tool_patch_and_output_caps(self):
  for field in ('patch-escape','wrong-tool','duplicate','tools','output','missing-usage','stream-cut','model'):
   p=Policy(NONCE,count_fee=0,fake=True);p.last_count=1000
   a={'type':'custom_tool_call','name':'apply_patch','call_id':'patch','input':p.actions['patch']}
   data=wire([a])
   if field=='patch-escape':a['input']=a['input'].replace('/workspace/smoke.txt','/root/escape');data=wire([a])
   if field=='wrong-tool':a['name']='spawn_agent';data=wire([a])
   if field=='duplicate':data=wire([a,a])
   if field=='tools':p.max_tools=0
   if field=='output':data=wire([a],output_tokens=1025)
   if field=='missing-usage':data=wire([a],input_tokens=None)
   if field=='stream-cut':data=data[:data.rfind(b'data: ')]
   if field=='model':data=wire([a],model='gpt-6.1-sol')
   with self.subTest(field=field),self.assertRaises(Stop):p.response(data)
 def test_request_catalog_unknown_fields_and_framing(self):
  for mutate in ('model','catalog','unknown','tier','cache','duplicate'):
   p=Policy(NONCE,count_fee=0,fake=True);r=Relay(p,Fake(),'trial-token-'+'x'*32,self.root/(mutate+'.jsonl'));body=request()
   if mutate=='model':body['model']='gpt-6.1-sol'
   if mutate=='catalog':body['input'][0]['tools']=[]
   if mutate=='unknown':body['tools']=[{'type':'web_search'}]
   if mutate=='tier':body['service_tier']='priority'
   if mutate=='cache':body['input'][0]['prompt_cache_breakpoint']={'ttl':'12h'}
   raw=canonical(body) if mutate!='duplicate' else b'{"model":"a","model":"b"}'
   with self.subTest(mutate=mutate),self.assertRaises(Stop):r.request(raw)
 def test_http_auth_and_route_no_forward(self):
  r=self.relay();server=http.server.HTTPServer(('127.0.0.1',0),r.handler());thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=2);c.request('POST','/v1/responses',canonical(request()),{'Content-Type':'application/json'});response=c.getresponse();self.assertEqual(response.status,403);response.read();c.close()
   self.assertEqual(r.upstream.paths,[])
   c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=2);c.request('POST','http://attacker.invalid/v1/responses',canonical(request()),{'Content-Type':'application/json','Authorization':'Bearer '+r.token});response=c.getresponse();self.assertEqual(response.status,503);response.read();c.close();self.assertEqual(r.upstream.paths,[])
  finally:server.shutdown();thread.join();server.server_close()
 def test_credential_file_protection(self):
  p=self.root/'key';p.write_text('fake-provider-secret-'+'x'*32);p.chmod(0o600);self.assertEqual(read_secret(p),p.read_text())
  p.chmod(0o644)
  with self.assertRaises(Stop):read_secret(p)
if __name__=='__main__':unittest.main()
