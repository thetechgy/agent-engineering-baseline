"""Native patch/command/denial evidence admission, never a numerical grader."""
import json,shlex,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aeb_direct.lifecycle import observe
from policy import Policy,Stop,MODEL,canonical,decode,digest,smoke

def admit(capture,requests,responses,audit,effects,nonce):
 native=observe(capture);actions=smoke(nonce)
 if len(requests)!=len(responses) or not 1<=len(requests)<=8:raise Stop('provider-roundtrip-population')
 if any(r.get('model')!=MODEL for r in requests):raise Stop('outbound-model-drift')
 if '- provider-smoke:' not in json.dumps(requests[0]):raise Stop('skill-not-natively-advertised')
 policy=Policy(nonce,count_fee=0,fake=True);expected=[];contexts={}
 reserved=[r['input_tokens'] for r in audit if r['phase']=='generation-reserved']
 if len(reserved)!=len(responses) or len([r for r in audit if r['phase']=='response-admitted'])!=len(responses) or any(r['phase']=='session-closed' for r in audit):raise Stop('relay-closure-or-reservation-population')
 for request,response,count in zip(requests,responses,reserved):
  policy.prepare(request);policy.reserve(count);new=policy.response(response);expected.extend(new)
  for call in new:contexts[call['call_id']]=request['input']
 calls={};outputs={}
 for f in capture['frames']:
  if f.get('method')!='rawResponseItem/completed':continue
  p=f['params'];i=p['item'];kind=i['type']
  if kind not in ('function_call','custom_tool_call','function_call_output','custom_tool_call_output'):continue
  if p['threadId']!=capture['thread_id'] or p['turnId']!=capture['turn_id']:raise Stop('raw-call-scope')
  target=calls if kind in ('function_call','custom_tool_call') else outputs;key=i['call_id']
  if key in target or (target is outputs and key not in calls):raise Stop('raw-call-order-or-identity')
  target[key]=i
 if len({i['call_id'] for i in expected})!=len(expected) or {i['call_id'] for i in expected}!=set(calls) or set(outputs)!=set(calls):raise Stop('native-original-inventory')
 for e in expected:
  i=calls[e['call_id']]
  for k in ('type','call_id','name','arguments' if e['type']=='function_call' else 'input'):
   if i.get(k)!=e.get(k):raise Stop('native-original-arguments')
 commands={i['id']:i for i in native['commands']};patches={i['id']:i for i in native['patches']};roles={};expected_commands=set();expected_patches=set()
 # Determine scenario roles from ORIGINAL provider submissions, then correlate
 # execution exclusively by the authenticated native call ID, never command text.
 for e in expected:
  key=e['call_id']
  if e['type']=='custom_tool_call':role='patch';expected_patches.add(key)
  else:
   args=decode(e['arguments']);role=next((name for name,value in actions.items() if name!='patch' and args['cmd']==value),None)
   if role is None:raise Stop('unreviewed-scenario-action','inconclusive-policy')
   if role!='denied':expected_commands.add(key)
  roles.setdefault(role,[]).append(key)
 if set(roles)!={'read','failure','verify','denied','patch'} or len(roles['patch'])!=1 or len(roles['denied'])!=1:raise Stop('scenario-not-completed','inconclusive-scenario')
 for role,required_roles in [('patch',('read','failure')),('verify',('read','failure','patch'))]:
  for key in roles[role]:
   available={item.get('call_id') for item in contexts[key] if item.get('type') in ('function_call_output','custom_tool_call_output')}
   if any(not set(roles[prior])<=available for prior in required_roles):raise Stop('recovery-context-not-consumed','inconclusive-scenario')
 if set(commands)!=expected_commands or set(patches)!=expected_patches:raise Stop('native-execution-population')
 for role,code in [('read',0),('failure',7),('verify',0)]:
  for key in roles[role]:
   item=commands[key]
   if item['exitCode']!=code or item['cwd']!='/workspace' or shlex.split(item['command'])!=['/bin/sh','-lc',actions[role]]:raise Stop('native-command-outcome')
 if not any(nonce in commands[key]['aggregatedOutput'] for key in roles['read']) or not all(commands[key]['aggregatedOutput']==nonce+'\n' for key in roles['verify']):raise Stop('skill-read-or-recovery-verification')
 patch=patches[roles['patch'][0]]
 if patch['status']!='completed' or len(patch['changes'])!=1 or patch['changes'][0]['path']!='/workspace/smoke.txt' or patch['changes'][0]['kind']!={'type':'add'}:raise Stop('native-patch-outcome')
 denial=outputs[roles['denied'][0]]['output']
 if not isinstance(denial,str) or 'approval policy is Never' not in denial:raise Stop('approval-denial-unqualified')
 if effects!={'smoke_bytes':(nonce+'\n').encode().hex(),'forbidden_present':False,'collection':'paused-container-daemon-archive'}:raise Stop('independent-effects')
 return {'evidence_class':'fake-provider-native-compatibility-control','original_submissions':len(expected),'native_commands':len(commands),'native_patches':1,'denied_without_command_item':1,'native_skill_read':True,'nonzero_recovery':True,'independent_effects':True,'real_provider_compatibility':'unqualified-no-inference','grading':'not-invoked'}


def patch_controls(capture,requests,responses,audit,effects,nonce):
 """Synthetic corruption of actual patch evidence; never native grades."""
 import copy
 labels=('changed-original-patch','missing-patch-output','changed-native-patch-id','changed-independent-bytes','changed-native-patch-kind')
 for label in labels:
  c=copy.deepcopy(capture);e=copy.deepcopy(effects)
  patch=next(f['params']['item'] for f in c['frames'] if f.get('method')=='rawResponseItem/completed' and f['params']['item']['type']=='custom_tool_call')
  key=patch['call_id']
  if label=='changed-original-patch':patch['input']+='changed'
  elif label=='missing-patch-output':c['frames']=[f for f in c['frames'] if not (f.get('method')=='rawResponseItem/completed' and f['params']['item'].get('call_id')==key and f['params']['item']['type']=='custom_tool_call_output')]
  elif label=='changed-native-patch-id':
   for f in c['frames']:
    if f.get('method') in ('item/started','item/completed') and f['params']['item']['type']=='fileChange':f['params']['item']['id']='foreign-patch-id'
    if f.get('id')==4:
     for item in f['result']['thread']['turns'][0]['items']:
      if item['type']=='fileChange':item['id']='foreign-patch-id'
  elif label=='changed-independent-bytes':e['smoke_bytes']='00'
  else:
   for f in c['frames']:
    if f.get('method') in ('item/started','item/completed') and f['params']['item']['type']=='fileChange':f['params']['item']['changes'][0]['kind']={'type':'update','move_path':'/workspace/unexpected'}
    if f.get('id')==4:
     for item in f['result']['thread']['turns'][0]['items']:
      if item['type']=='fileChange':item['changes'][0]['kind']={'type':'update','move_path':'/workspace/unexpected'}
  try:admit(c,requests,responses,audit,e,nonce)
  except ValueError:continue
  raise Stop('synthetic-patch-corruption-admitted')
 return list(labels)
