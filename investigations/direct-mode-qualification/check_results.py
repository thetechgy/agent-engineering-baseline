import json,sys
from pathlib import Path
root=Path(sys.argv[1]);rows=[];all_states=set()
from aeb_direct.evidence import admit,mutation_controls
for profile in ('positive','denied','boundary'):
 rewards=[]
 for p in (root/profile).rglob('reward.json'):
  if '_harbor-jobs' in p.parts:continue
  d=json.loads(p.read_text());m=d.get('custom_metrics',d)
  if 'gh_authorization' in m:rewards.append((p,m))
 if len(rewards)!=2:raise RuntimeError(f'{profile}: expected exactly two gh rewards, found {len(rewards)}')
 for p,m in rewards:
  baseline='without-skill' in p.parts
  if m.get('gh_activation')!=int(not baseline) or m.get('gh_gate')!=int(profile=='positive' and not baseline):raise RuntimeError('arm-specific activation or gate semantics changed')
  if any(m.get('gh_'+k)!=1 for k in ('evidence','commands','task','recovery','efficiency')) or m['gh_authorization']!=(profile=='positive'):raise RuntimeError(f'wrong {profile} oracle result: {m}')
 identities=[json.loads(p.read_text()) for p in (root/profile).rglob('*.identity.json')]
 if len(identities)!=2 or len({i['initializer']['state_id'] for i in identities})!=2 or {i['with_skill'] for i in identities}!={True,False}:raise RuntimeError('paired private initialization or skill layouts not independent')
 for identity in identities:
  key=identity['initializer']['state_id']
  if key in all_states:raise RuntimeError('private state reused across profiles')
  all_states.add(key)
 captures=[p for p in (root/profile).rglob('*.json') if p.parent.name=='direct-private' and not p.name.endswith(('.attempts.json','.identity.json'))]
 if len(captures)!=2:raise RuntimeError('missing authoritative captures')
 for capture in captures:
  raw=json.loads(capture.read_text());admit(raw);mutation_controls(raw)
 classes=[p for p in (root/profile).rglob('evidence-classes.json') if p.parent.name=='verifier']
 if len(classes)!=2:raise RuntimeError('missing separated oracle evidence')
 for path in classes:
  evidence=json.loads(path.read_text())
  if len(evidence['broker_audit'])!=2 or [r['route'] for r in evidence['broker_audit']]!=['comment','verify']:raise RuntimeError('wrong broker transitions')
  if [r['mutation'] for r in evidence['broker_audit']]!=['comment',None]:raise RuntimeError('partial operation retried or lost')
  if evidence['independently_read_effects']['result']!={'comments_created':1,'body_preserved':True,'attachment_status':'partial'}:raise RuntimeError('wrong independently read artifact')
 if sorted(m['gh_gate'] for _,m in rewards)!=([0,1] if profile=='positive' else [0,0]):raise RuntimeError('mandatory conjunction changed')
 if sorted(m['gh_activation'] for _,m in rewards)!=[0,1]:raise RuntimeError('baseline activation semantics changed')
 rows.append({'profile':profile,'arms':2,'metrics':[m for _,m in rewards]})
(root/'qualification.json').write_text(json.dumps({'schema':'offline-direct-qualification-v1','rows':rows,'production_admission':False,'default_plus_custom':'unqualified','real_provider':'not-executed'},indent=2))
