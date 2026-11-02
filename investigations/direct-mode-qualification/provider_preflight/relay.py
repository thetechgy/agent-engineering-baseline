"""Operator-only relay: buffered admission, no redirects/proxies/retries or arbitrary routes."""
import re,ipaddress,hashlib,hmac,http.client,http.server,json,os,socket,stat,sys,threading,time
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parent))
from policy import MODEL,Policy,Stop,canonical,decode,digest

class Upstream:
 def __init__(self,key,*,fake_origin=None,approval=None):
  self.key=key;self.fake_origin=fake_origin
  if fake_origin:
   parsed=urlsplit(fake_origin)
   if parsed.scheme!='http' or parsed.path or parsed.username or parsed.query or parsed.fragment:raise Stop('invalid-fake-origin')
   if not parsed.hostname or not ipaddress.ip_address(parsed.hostname).is_private or not key.startswith('fake-provider-key-'):raise Stop('fake-route-or-key')
   self.host,self.port=parsed.hostname,parsed.port
  else:
   if not approval or approval.get('inference_authorized') is not True or approval.get('max_micro_usd')!=1000000 or approval.get('model')!=MODEL or approval.get('count_fee_verified') is not True or approval.get('account_model_access_verified') is not True or approval.get('account_pricing_verified') is not True or approval.get('input_micro_usd_per_token')!=5 or approval.get('output_micro_usd_per_token')!=20 or approval.get('cache_ttl')!='30m':raise Stop('separate-authorization-and-billing-required','preflight-blocked')
   fee=approval.get('count_fee_micro_usd')
   if not isinstance(fee,int) or isinstance(fee,bool) or not 0<=fee<=24520 or approval.get('count_fee_covers_request_bytes')!=262144:raise Stop('unverified-count-fee-bound','preflight-blocked')
   if not isinstance(approval.get('reviewed_source'),str) or len(approval['reviewed_source'])!=40 or not isinstance(approval.get('billing_evidence_sha256'),str) or len(approval['billing_evidence_sha256'])!=64 or not 0<approval.get('expires_unix',0)-time.time()<=86400 or not 0<=time.time()-approval.get('pricing_checked_unix',0)<=3600:raise Stop('invalid-or-stale-authorization-record','preflight-blocked')
   self.host,self.port='api.openai.com',443
 def post(self,path,body,timeout):
  if path not in ('/v1/responses','/v1/responses/input_tokens'):raise Stop('upstream-path')
  cls=http.client.HTTPConnection if self.fake_origin else http.client.HTTPSConnection
  conn=cls(self.host,self.port,timeout=timeout)
  try:
   conn.request('POST',path,body=canonical(body),headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})
   response=conn.getresponse()
   if response.status!=200:
    details={'http_status':response.status}
    try:
     error=decode(response.read(8193)).get('error',{})
     for name in ('type','code','param'):
      value=error.get(name)
      if isinstance(value,str) and re.fullmatch(r'[a-z0-9_.\[\]]{1,128}',value) and 'secret' not in value and 'authorization' not in value:details[name]=value
    except Exception:pass
    stopped=Stop('upstream-http-'+str(response.status),'provider-error');stopped.provider_details=details;raise stopped
   data=response.read(4*1024*1024+1)
   if len(data)>4*1024*1024:raise Stop('upstream-response-cap','inconclusive-limit')
   if self.key.encode() in data:raise Stop('credential-in-provider-response','security-block')
   return data
  finally:conn.close()
class Relay:
 def __init__(self,policy,upstream,token,audit):
  self.policy,self.upstream,self.token=policy,upstream,token;self.audit=Path(audit);self.lock=threading.Lock();self.audit_lock=threading.Lock();self.previous='0'*64;self.sequence=0;self.submissions=[]
  try:fd=os.open(self.audit,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
  except OSError:raise Stop('refusing-existing-or-unsafe-relay-ledger') from None
  m=os.fstat(fd);self.audit_identity=(m.st_dev,m.st_ino);self.audit_fd=fd
  self.record('session-open',model=MODEL)
 def __del__(self):
  fd=getattr(self,'audit_fd',None)
  if fd is not None:
   os.close(fd);self.audit_fd=None
 def record(self,phase,**fields):
  with self.audit_lock:
   row={'sequence':self.sequence,'previous':self.previous,'phase':phase,'reserved_micro_usd':self.policy.reserved,**fields}
   raw=canonical(row);fd=os.open(self.audit,os.O_WRONLY|os.O_APPEND|os.O_NOFOLLOW)
   m=os.fstat(fd)
   if (m.st_dev,m.st_ino)!=self.audit_identity or m.st_uid!=os.getuid() or m.st_nlink!=1 or m.st_mode&0o077:os.close(fd);raise Stop('relay-ledger-substitution')
   with os.fdopen(fd,'ab') as f:f.write(raw+b'\n');f.flush();os.fsync(f.fileno())
   self.previous=hashlib.sha256(raw).hexdigest();self.sequence+=1
 def request(self,body):
  if not self.lock.acquire(blocking=False):
   self.policy.closed=('concurrent-or-retried-request','unavailable-evidence');raise Stop(*self.policy.closed)
  try:
   self.record('authenticated-client-request',body_sha256=hashlib.sha256(body).hexdigest())
   original=decode(body);outbound=self.policy.prepare(original)
   fd=os.open(self.audit.parent/('request-'+str(self.policy.requests)+'.json'),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
   with os.fdopen(fd,'wb') as stream:stream.write(canonical(original))
   self.record('count-reserved',request_sha256=digest(original))
   count_body={k:v for k,v in outbound.items() if k in ('model','input','tools','instructions','reasoning','text','tool_choice')}
   count=decode(self.upstream.post('/v1/responses/input_tokens',count_body,self.remaining()))
   if count.get('object')!='response.input_tokens':raise Stop('token-count-response')
   value=count.get('input_tokens');self.policy.reserve(value);self.policy.last_count=value
   self.record('generation-reserved',input_tokens=value,request_sha256=digest(outbound))
   wire=self.upstream.post('/v1/responses',outbound,self.remaining())
   path=self.audit.parent/('response-'+str(self.policy.requests)+'.sse')
   fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
   with os.fdopen(fd,'wb') as stream:stream.write(wire)
   self.record('provider-response-observed',response_sha256=hashlib.sha256(wire).hexdigest())
   calls=self.policy.response(wire)
   self.submissions.extend(calls)
   self.record('response-admitted',response_sha256=hashlib.sha256(wire).hexdigest(),call_ids=[c['call_id'] for c in calls],tools_total=self.policy.tools)
   return wire
  except Exception as error:
   e=error if isinstance(error,Stop) else Stop('relay-transport-or-parse-failure')
   self.policy.closed=(e.reason,e.category);self.record('session-closed',reason=e.reason,category=e.category,provider_details=getattr(e,'provider_details',None))
   raise e from None
  finally:self.lock.release()
 def remaining(self):
  self.policy.check();return max(.01,min(10,self.policy.deadline-(self.policy.clock()-self.policy.start)))
 def handler(self):
  relay=self
  class Handler(http.server.BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def setup(self):
    super().setup();self.connection.settimeout(5)
   def do_GET(self):self.send_error(405)
   def do_POST(self):
    self.connection.settimeout(5)
    if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+relay.token):
     self.send_response(403);self.end_headers();return
    try:
     if self.path!='/v1/responses' or self.headers.get('Transfer-Encoding') or self.headers.get('Content-Type')!='application/json':raise Stop('client-route-or-framing')
     lengths=self.headers.get_all('Content-Length',[])
     if len(lengths)!=1 or not lengths[0].isdigit():raise Stop('request-framing')
     size=int(lengths[0])
     if not 0<size<=256*1024:raise Stop('request-byte-limit','inconclusive-limit')
     body=self.rfile.read(size)
     if len(body)!=size:raise Stop('short-request')
     wire=relay.request(body)
     self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(wire)));self.end_headers();self.wfile.write(wire)
    except Exception as error:
     e=error if isinstance(error,Stop) else Stop('client-transport-failure')
     if not relay.policy.closed:
      relay.policy.closed=(e.reason,e.category);relay.record('session-closed',reason=e.reason,category=e.category)
     # Do not echo upstream errors, headers, request content or secrets.
     wire=canonical({'error':{'message':e.category+': '+e.reason,'type':'preflight_stopped'}})
     self.send_response(503);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(wire)));self.end_headers();self.wfile.write(wire)
  return Handler

def read_secret(path):
 p=Path(path);m=p.lstat()
 if not stat.S_ISREG(m.st_mode) or m.st_nlink!=1 or m.st_uid!=os.getuid() or m.st_mode&0o077 or m.st_size>512:raise Stop('credential-file-protection')
 value=p.read_text().strip()
 if len(value)<24 or not value.isascii() or any(c.isspace() for c in value):raise Stop('credential-shape')
 return value
if __name__=='__main__':
 config=decode(sys.stdin.buffer.readline(65537));mode=config['mode']
 if mode not in ('fake','live'):raise Stop('unreviewed-relay-mode')
 approval=config.get('authorization')
 # Check authorization BEFORE reading any real provider credential.
 if mode=='live':Upstream('',approval=approval)
 policy=Policy(config['nonce'],count_fee=config.get('count_fee_micro_usd'),fake=mode=='fake')
 if mode=='live' and (policy.count_fee is None or policy.count_fee!=approval.get('count_fee_micro_usd')):raise Stop('unverified-count-fee','preflight-blocked')
 key=read_secret('/run/provider-key');token=read_secret('/run/trial-token')
 if mode=='fake':policy.extra_commands=set(config.get('extra_commands',[]))
 relay=Relay(policy,Upstream(key,fake_origin=config.get('fake_origin') if mode=='fake' else None,approval=approval),token,'/evidence/relay.jsonl')
 server=http.server.HTTPServer(('0.0.0.0',8991),relay.handler());server.daemon_threads=True
 server.serve_forever(poll_interval=.1)
