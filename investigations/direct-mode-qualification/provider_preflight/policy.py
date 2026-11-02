"""One-session compatibility policy; separate from every evaluation/grading policy."""
import hashlib,json,re,time
from pathlib import Path
MODEL='gpt-5.6-sol'
CATALOG_SHA='3261a6c98fca558d3ce6561bcfd3924357c1f7e04c8e376a7132891ae635f369'
class Stop(ValueError):
 def __init__(self,reason,category='unavailable-evidence'):
  self.reason,self.category=reason,category;super().__init__(reason)
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def decode(raw):
 def unique(pairs):
  result={}
  for k,v in pairs:
   if k in result:raise Stop('duplicate-json-key')
   result[k]=v
  return result
 try:return json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(Stop('non-finite-json')))
 except (UnicodeError,json.JSONDecodeError) as e:raise Stop('invalid-json') from e

def catalog(request):
 return [tool for item in request.get('input',[]) if item.get('type')=='additional_tools' for tool in item.get('tools',[])]
def smoke(nonce):
 if not re.fullmatch('[0-9a-f]{32}',nonce):raise Stop('invalid-nonce')
 return {
  'read':'cat /skills/provider-smoke/SKILL.md',
  'failure':"printf 'failure-marker\\n'; exit 7",
  'verify':'cat /workspace/smoke.txt',
  'denied':"printf forbidden > /workspace/forbidden",
  'patch':'*** Begin Patch\n*** Add File: /workspace/smoke.txt\n+'+nonce+'\n*** End Patch\n',
 }
class Policy:
 def __init__(self,nonce,*,count_fee=None,clock=time.monotonic,fake=False):
  self.actions=smoke(nonce);self.clock=clock;self.start=clock();self.deadline=300
  self.max_requests=8;self.max_input=128000;self.per_input=16000;self.output=1024;self.max_tools=16
  self.count_fee=count_fee;self.fake=fake;self.extra_commands=set()
  self.reserved=0;self.inputs=0;self.requests=0;self.tools=0;self.ids=set();self.request_hashes=set();self.closed=None
 def stop(self,reason,category='unavailable-evidence'):
  self.closed=(reason,category);raise Stop(reason,category)
 def check(self):
  if self.closed:raise Stop(*self.closed)
  if self.clock()-self.start>=self.deadline:self.stop('session-time-limit','inconclusive-limit')
 def prepare(self,request):
  self.check()
  if self.requests>=self.max_requests:self.stop('request-limit','inconclusive-limit')
  if self.count_fee is None:self.stop('unverified-count-endpoint-price','preflight-blocked')
  allowed={'model','stream','input','tool_choice','parallel_tool_calls','reasoning','store','include','prompt_cache_key','text','client_metadata','max_output_tokens','service_tier'}
  if set(request)-allowed:self.stop('unsupported-request-field')
  if request.get('model')!=MODEL or request.get('stream') is not True:self.stop('model-or-wire-route')
  if digest(catalog(request))!=CATALOG_SHA:self.stop('tool-catalog-drift')
  if request.get('reasoning',{}).get('effort')!='low':self.stop('reasoning-drift')
  if request.get('service_tier','default')!='default':self.stop('service-tier-drift')
  if request.get('max_output_tokens',self.output)!=self.output:self.stop('output-cap-substitution')
  if len(canonical(request))>256*1024:self.stop('request-byte-limit','inconclusive-limit')
  key=digest(request)
  if key in self.request_hashes:self.stop('request-replay')
  if not isinstance(self.count_fee,int) or isinstance(self.count_fee,bool) or self.count_fee<0:self.stop('invalid-count-price','preflight-blocked')
  if self.reserved+self.count_fee>1000000:self.stop('dollar-limit','inconclusive-limit')
  self.reserved+=self.count_fee;self.requests+=1;self.request_hashes.add(key)
  outbound=dict(request,max_output_tokens=self.output,service_tier='default',prompt_cache_options={'ttl':'30m'})
  # Caller fields cannot select extended retention or explicit hidden breakpoints.
  def inspect(v):
   if isinstance(v,dict):
    if any(k.startswith('prompt_cache_') and k!='prompt_cache_key' for k in v):self.stop('unreviewed-cache-control')
    for x in v.values():inspect(x)
   elif isinstance(v,list):
    for x in v:inspect(x)
  inspect(request)
  return outbound
 def reserve(self,count):
  self.check()
  if not isinstance(count,int) or isinstance(count,bool) or count<1:self.stop('invalid-input-token-count')
  if count>self.per_input or self.inputs+count>self.max_input:self.stop('input-token-limit','inconclusive-limit')
  # micro-USD: all input at 30m cache-write price, all output incl reasoning.
  maximum=count*5+self.output*20
  if self.reserved+maximum>1000000:self.stop('dollar-limit','inconclusive-limit')
  self.reserved+=maximum;self.inputs+=count;self.last_count=count
  return maximum
 def tool(self,item):
  self.check();kind=item.get('type');name=item.get('name');key=item.get('call_id')
  if not isinstance(key,str) or not key or key in self.ids:self.stop('tool-identity')
  if self.tools>=self.max_tools:self.stop('tool-limit','inconclusive-limit')
  if (name=='apply_patch' and kind!='custom_tool_call') or (name=='exec_command' and kind!='function_call'):self.stop('advertised-tool-kind-mismatch','provider-protocol-error')
  if kind=='custom_tool_call' and name=='apply_patch':
   if item.get('input') not in (self.actions['patch'],self.actions['patch'].rstrip('\n')):self.stop('patch-outside-smoke-policy','inconclusive-policy')
  elif kind=='function_call' and name=='exec_command':
   args=decode(item.get('arguments',''))
   allowed={'cmd','workdir','sandbox_permissions','justification','max_output_tokens','yield_time_ms','login','shell','tty'}
   if not isinstance(args,dict) or set(args)-allowed:self.stop('unreviewed-command-argument','inconclusive-policy')
   if args.get('cmd') not in set(self.actions.values())-{self.actions['patch']}|self.extra_commands:self.stop('command-outside-smoke-policy','inconclusive-policy')
   if args.get('workdir','/workspace')!='/workspace' or args.get('shell','/bin/sh')!='/bin/sh' or args.get('tty',False) is not False:self.stop('command-context','inconclusive-policy')
   if args.get('sandbox_permissions','use_default')!='use_default' and not (args.get('sandbox_permissions')=='require_escalated' and args['cmd']==self.actions['denied']):self.stop('unexpected-escalation','inconclusive-policy')
   if args['cmd']==self.actions['denied'] and args.get('sandbox_permissions')!='require_escalated':self.stop('unprotected-denial-scenario','inconclusive-policy')
  else:self.stop('tool-outside-allowlist','inconclusive-policy')
  self.ids.add(key);self.tools+=1
 def response(self,wire):
  self.check()
  if len(wire)>4*1024*1024:self.stop('response-byte-limit','inconclusive-limit')
  items=[];terminal=None;response_id=None
  for block in wire.decode('utf-8').replace('\r\n','\n').split('\n\n'):
   if not block.strip():continue
   lines=[line[6:] for line in block.splitlines() if line.startswith('data: ')]
   if len(lines)!=1:self.stop('invalid-event-frame')
   if lines[0]=='[DONE]':continue
   event=decode(lines[0]);kind=event.get('type','')
   if terminal is not None:self.stop('event-after-terminal')
   if not kind.startswith('response.') or kind in ('response.failed','response.error'):self.stop('provider-error','provider-error')
   if kind=='response.created':
    if response_id is not None:self.stop('duplicate-response')
    response_id=event['response']['id']
   if kind=='response.output_item.done':items.append(event['item'])
   if kind in ('response.completed','response.incomplete'):
    terminal=event['response']
    if kind=='response.incomplete':self.stop('provider-output-limit' if terminal.get('incomplete_details',{}).get('reason')=='max_output_tokens' else 'provider-incomplete','inconclusive-limit' if terminal.get('incomplete_details',{}).get('reason')=='max_output_tokens' else 'unavailable-evidence')
  if terminal is None:self.stop('incomplete-provider-stream')
  if terminal.get('id')!=response_id or terminal.get('model')!=MODEL or terminal.get('status')!='completed':self.stop('response-model-or-scope')
  if terminal.get('output')!=items:self.stop('response-item-population')
  usage=terminal.get('usage',{});i=usage.get('input_tokens');o=usage.get('output_tokens')
  if any(not isinstance(v,int) or isinstance(v,bool) or v<0 for v in (i,o)):self.stop('missing-provider-usage')
  if usage.get('total_tokens')!=i+o or isinstance(usage.get('total_tokens'),bool):self.stop('inconsistent-provider-usage')
  if i>self.last_count or o>self.output:self.stop('provider-exceeded-reservation')
  calls=[]
  for item in items:
   if item.get('type') in ('function_call','custom_tool_call'):self.tool(item);calls.append(item)
   elif item.get('type') not in ('message','reasoning'):self.stop('unreviewed-provider-item')
  return calls
