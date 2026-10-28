"""Conservative admission of the exact native scripted probe, with poison controls."""
import collections,copy,json,pathlib,sys

def admit(events):
 starts={};ends={};turn_complete=False
 for e in events:
  p=e.get('params',{});m=e.get('method');item=p.get('item',{})
  if m=='turn/completed':
   if p['turn']['status']!='completed':raise ValueError('turn incomplete')
   turn_complete=True
  if m in ('item/started','item/completed') and item.get('type') not in ('userMessage','agentMessage','reasoning','plan','commandExecution','fileChange'):raise ValueError('unsupported native item coverage')
  if m not in ('item/started','item/completed') or item.get('type') not in ('commandExecution','fileChange'):continue
  key=(p['threadId'],p['turnId'],item['id']);target=starts if m=='item/started' else ends
  if key in target and target[key]!=item:raise ValueError('contradictory native identity')
  target[key]=item
 if not turn_complete or set(starts)!=set(ends):raise ValueError('incomplete execution population')
 cmds=[i for i in ends.values() if i['type']=='commandExecution']
 patches=[i for i in ends.values() if i['type']=='fileChange']
 allowed_optional={"/bin/sh -lc 'python /opt/broker.py read'","/bin/sh -lc 'cat /workspace/skills/probe/SKILL.md'"}
 optional=[i for i in cmds if '/opt/broker.py read' in i['command'] or 'cat /workspace/skills/probe/SKILL.md' in i['command']]
 if any(i['command'] not in allowed_optional for i in optional):raise ValueError('unauthorized fixture command')
 if len(optional)>2:raise ValueError('duplicate fixture controls')
 cmds=[i for i in cmds if i not in optional]
 if any(i.get('exitCode') not in (0,1) or i.get('status')!=('failed' if i.get('exitCode')==1 else 'completed') for i in optional):raise ValueError('fixture read incomplete')
 expected_commands=collections.Counter(["/bin/sh -lc 'printf parallel-one'","/bin/sh -lc 'printf parallel-two'","/bin/sh -lc 'printf identical'","/bin/sh -lc 'printf identical'","/bin/sh -lc 'exit 7'"])
 if collections.Counter(i['command'] for i in cmds)!=expected_commands:raise ValueError('unauthorized fixture command')
 if len(cmds)!=5 or len(patches)!=1:raise ValueError('unexpected fixture population')
 if sorted(i.get('exitCode') for i in cmds)!=[0,0,0,0,7]:raise ValueError('missing exit evidence')
 if any(i['status']!=('failed' if i['exitCode']==7 else 'completed') for i in cmds):raise ValueError('contradictory exit status')
 if patches[0]['status']!='completed':raise ValueError('patch not completed')
 return {'commands':len(cmds)+len(optional),'patches':len(patches),'complete':True,'activation_observed':any('cat /workspace/skills/probe/SKILL.md' in i['command'] and i['exitCode']==0 for i in optional)}

def check(path):
 events=json.loads(path.read_text());result=admit(events)
 variants={
 'missing_completion':[e for e in events if e.get('method')!='turn/completed'],
 'missing_result':copy.deepcopy(events),
 'contradictory_identity':copy.deepcopy(events),
 'unrecognized_tool':copy.deepcopy(events),
 'unauthorized_command':copy.deepcopy(events),
 }
 idx=next(i for i,e in enumerate(events) if e.get('method')=='item/completed' and e['params']['item']['type']=='commandExecution')
 del variants['missing_result'][idx]
 bad=copy.deepcopy(events[idx]);bad['params']['item']['exitCode']=99;variants['contradictory_identity'].append(bad)
 unknown=copy.deepcopy(events[idx]);unknown['params']['item']['type']='unknownExecutionTool';variants['unrecognized_tool'].append(unknown)
 variants['unauthorized_command'][idx]['params']['item']['command']="/bin/sh -lc 'unexpected-action'"
 for name,variant in variants.items():
  try:admit(variant)
  except ValueError:result[name]='rejected'
  else:raise AssertionError(name)
 print(json.dumps(result));return result
if __name__=='__main__':check(pathlib.Path(sys.argv[1]))
