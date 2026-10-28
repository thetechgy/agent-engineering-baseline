"""Conservative admission of the exact native scripted probe, with poison controls."""
import copy,json,pathlib,sys

def admit(events):
 starts={};ends={};turn_complete=False
 for e in events:
  p=e.get('params',{});m=e.get('method');item=p.get('item',{})
  if m=='turn/completed':
   if p['turn']['status']!='completed':raise ValueError('turn incomplete')
   turn_complete=True
  if m not in ('item/started','item/completed') or item.get('type') not in ('commandExecution','fileChange'):continue
  key=(p['threadId'],p['turnId'],item['id']);target=starts if m=='item/started' else ends
  if key in target and target[key]!=item:raise ValueError('contradictory native identity')
  target[key]=item
 if not turn_complete or set(starts)!=set(ends):raise ValueError('incomplete execution population')
 cmds=[i for i in ends.values() if i['type']=='commandExecution']
 patches=[i for i in ends.values() if i['type']=='fileChange']
 if len(cmds)!=5 or len(patches)!=1:raise ValueError('unexpected fixture population')
 if sorted(i.get('exitCode') for i in cmds)!=[0,0,0,0,7]:raise ValueError('missing exit evidence')
 if any(i['status']!=('failed' if i['exitCode']==7 else 'completed') for i in cmds):raise ValueError('contradictory exit status')
 if patches[0]['status']!='completed':raise ValueError('patch not completed')
 return {'commands':len(cmds),'patches':len(patches),'complete':True}

def check(path):
 events=json.loads(path.read_text());result=admit(events)
 variants={
 'missing_completion':[e for e in events if e.get('method')!='turn/completed'],
 'missing_result':copy.deepcopy(events),
 'contradictory_identity':copy.deepcopy(events),
 }
 idx=next(i for i,e in enumerate(events) if e.get('method')=='item/completed' and e['params']['item']['type']=='commandExecution')
 del variants['missing_result'][idx]
 bad=copy.deepcopy(events[idx]);bad['params']['item']['exitCode']=99;variants['contradictory_identity'].append(bad)
 for name,variant in variants.items():
  try:admit(variant)
  except ValueError:result[name]='rejected'
  else:raise AssertionError(name)
 print(json.dumps(result));return result
if __name__=='__main__':check(pathlib.Path(sys.argv[1]))
