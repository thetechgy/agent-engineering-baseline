"""Independent corruptions of a successful native capture; require exact admission stops."""
import copy
from admission import admit
from policy import Stop,digest,canonical
import hashlib

def admission_controls(capture,requests,responses,audit,effects,nonce,case=None):
 admit(capture,requests,responses,audit,effects,nonce)
 cases={
  'retained-request':'retained-request-hash',
  'outbound-request':'outbound-request-hash',
  'observed-response':'retained-response-hash',
  'admitted-response':'retained-response-hash',
  'context-type':'recovery-context-output-mismatch',
  'context-id':'recovery-context-not-consumed',
  'context-bytes':'recovery-context-output-mismatch',
  'late-submission':'raw-call-after-terminal',
  'late-output':'raw-call-after-terminal',
 }
 if case is not None:cases={case:cases[case]}
 for label,reason in cases.items():
  c,q,s,a=copy.deepcopy((capture,requests,responses,audit))
  if label=='retained-request':q[0]['client_metadata']={'corrupted':True}
  elif label=='outbound-request':next(r for r in a if r['phase']=='generation-reserved')['request_sha256']='0'*64
  elif label in ('observed-response','admitted-response'):
   phase='provider-response-observed' if label=='observed-response' else 'response-admitted'
   next(r for r in a if r['phase']==phase)['response_sha256']='0'*64
  elif label.startswith('context-'):
   # Alter the failure result supplied to the patch-generating request. Rebind
   # its hashes so each test reaches the recovery comparison independently.
   patch_id=next(f['params']['item']['call_id'] for f in c['frames'] if f.get('method')=='rawResponseItem/completed' and f['params']['item']['type']=='custom_tool_call')
   from policy import Policy
   p=Policy(nonce,count_fee=0,fake=True)
   for index,request in enumerate(q):
    p.last_count=[r for r in a if r['phase']=='generation-reserved'][index]['input_tokens']
    calls=p.response(s[index])
    if any(x['call_id']==patch_id for x in calls):break
   item=next(x for x in q[index]['input'] if x.get('type')=='function_call_output' and 'failure-marker' in str(x.get('output')))
   if label=='context-type':item['type']='custom_tool_call_output'
   elif label=='context-id':item['call_id']='foreign-call'
   else:item['output']+=' '
   [r for r in a if r['phase']=='count-reserved'][index]['request_sha256']=digest(q[index])
   outbound=dict(q[index],max_output_tokens=1024,service_tier='default',prompt_cache_options={'ttl':'30m'})
   [r for r in a if r['phase']=='generation-reserved'][index]['request_sha256']=digest(outbound)
  else:
   kinds=('function_call','custom_tool_call') if label=='late-submission' else ('function_call_output','custom_tool_call_output')
   frame=next(f for f in c['frames'] if f.get('method')=='rawResponseItem/completed' and f['params']['item']['type'] in kinds)
   c['frames'].remove(frame)
   if label=='late-submission':
    outcome=next(f for f in c['frames'] if f.get('method')=='rawResponseItem/completed' and f['params']['item'].get('call_id')==frame['params']['item']['call_id'] and f['params']['item']['type'] in ('function_call_output','custom_tool_call_output'))
    c['frames'].remove(outcome);c['frames'].extend([frame,outcome])
   else:c['frames'].append(frame)
  # Keep the chain valid; corruption must fail on the intended admission rule.
  previous='0'*64
  for row in a:
   row['previous']=previous;previous=hashlib.sha256(canonical(row)).hexdigest()
  try:admit(c,q,s,a,effects,nonce)
  except Stop as error:
   expected_category='inconclusive-scenario' if reason=='recovery-context-not-consumed' else 'unavailable-evidence'
   if (error.reason,error.category)!=(reason,expected_category):raise AssertionError((label,error.reason,error.category)) from error
  else:raise AssertionError('corruption admitted: '+label)
 return list(cases)
