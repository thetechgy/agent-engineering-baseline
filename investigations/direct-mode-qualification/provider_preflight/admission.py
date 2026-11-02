"""Native patch/command/denial evidence admission, never a numerical grader."""
import json,shlex,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aeb_direct.lifecycle import observe
from policy import Policy,Stop,MODEL,canonical,decode,digest,smoke

def admit(capture,requests,responses,audit,effects,nonce):
 native=observe(capture);actions=smoke(nonce)
 if len(requests)!=len(responses) or len(requests)!=6:raise Stop('provider-roundtrip-population')
 if any(r.get('model')!=MODEL for r in requests):raise Stop('outbound-model-drift')
 if '- provider-smoke:' not in json.dumps(requests[0]):raise Stop('skill-not-natively-advertised')
 policy=Policy(nonce,count_fee=0,fake=True);expected=[]
 reserved=[r['input_tokens'] for r in audit if r['phase']=='generation-reserved']
 if len(reserved)!=len(responses) or len([r for r in audit if r['phase']=='response-admitted'])!=len(responses) or any(r['phase']=='session-closed' for r in audit):raise Stop('relay-closure-or-reservation-population')
 for request,response,count in zip(requests,responses,reserved):
  policy.prepare(request);policy.reserve(count);expected.extend(policy.response(response))
 calls={};outputs={}
 for f in capture['frames']:
  if f.get('method')!='rawResponseItem/completed':continue
  p=f['params'];i=p['item'];kind=i['type']
  if kind not in ('function_call','custom_tool_call','function_call_output','custom_tool_call_output'):continue
  if p['threadId']!=capture['thread_id'] or p['turnId']!=capture['turn_id']:raise Stop('raw-call-scope')
  target=calls if kind in ('function_call','custom_tool_call') else outputs;key=i['call_id']
  if key in target or (target is outputs and key not in calls):raise Stop('raw-call-order-or-identity')
  target[key]=i
 if len(expected)!=5 or {i['call_id'] for i in expected}!=set(calls) or set(outputs)!=set(calls):raise Stop('native-original-inventory')
 for e in expected:
  i=calls[e['call_id']]
  for k in ('type','call_id','name','arguments' if e['type']=='function_call' else 'input'):
   if i.get(k)!=e.get(k):raise Stop('native-original-arguments')
 commands={i['id']:i for i in native['commands']};patches={i['id']:i for i in native['patches']}
 if set(commands)!={'smoke-read','smoke-failure','smoke-verify'} or set(patches)!={'smoke-patch'}:raise Stop('native-execution-population')
 for key,name,code in [('smoke-read','read',0),('smoke-failure','failure',7),('smoke-verify','verify',0)]:
  item=commands[key]
  if item['exitCode']!=code or item['cwd']!='/workspace' or shlex.split(item['command'])!=['/bin/sh','-lc',actions[name]]:raise Stop('native-command-outcome')
 if nonce not in commands['smoke-read']['aggregatedOutput'] or commands['smoke-verify']['aggregatedOutput']!=nonce+'\n':raise Stop('skill-read-or-recovery-verification')
 patch=patches['smoke-patch']
 if patch['status']!='completed' or len(patch['changes'])!=1 or patch['changes'][0]['path']!='/workspace/smoke.txt':raise Stop('native-patch-outcome')
 denial=outputs['smoke-denied']['output']
 if not isinstance(denial,str) or 'approval policy is Never' not in denial:raise Stop('approval-denial-unqualified')
 if effects!={'smoke_bytes':(nonce+'\n').encode().hex(),'forbidden_present':False,'collection':'paused-container-daemon-archive'}:raise Stop('independent-effects')
 return {'evidence_class':'fake-provider-native-compatibility-control','original_submissions':5,'native_commands':3,'native_patches':1,'denied_without_command_item':1,'native_skill_read':True,'nonzero_recovery':True,'independent_effects':True,'real_provider_compatibility':'unqualified-no-inference','grading':'not-invoked'}
