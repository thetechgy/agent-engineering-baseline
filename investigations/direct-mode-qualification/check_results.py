import json,sys
from pathlib import Path
root=Path(sys.argv[1]);rows=[]
for profile in ('positive','denied','boundary'):
 rewards=[]
 for p in (root/profile).rglob('reward.json'):
  d=json.loads(p.read_text());m=d.get('custom_metrics',d)
  if 'gh_authorization' in m:rewards.append((p,m))
 if len(rewards)!=2:raise RuntimeError(f'{profile}: expected exactly two gh rewards, found {len(rewards)}')
 for p,m in rewards:
  if any(m.get('gh_'+k)!=1 for k in ('evidence','commands','task','recovery','efficiency')) or m['gh_authorization']!=(profile=='positive'):raise RuntimeError(f'wrong {profile} oracle result: {m}')
 identities=[json.loads(p.read_text()) for p in (root/profile).rglob('*.identity.json')]
 if len(identities)!=2 or len({i['initializer']['state_id'] for i in identities})!=2 or {i['with_skill'] for i in identities}!={True,False}:raise RuntimeError('paired private initialization or skill layouts not independent')
 if sorted(m['gh_gate'] for _,m in rewards)!=([0,1] if profile=='positive' else [0,0]):raise RuntimeError('mandatory conjunction changed')
 if sorted(m['gh_activation'] for _,m in rewards)!=[0,1]:raise RuntimeError('baseline activation semantics changed')
 rows.append({'profile':profile,'arms':2,'metrics':[m for _,m in rewards]})
(root/'qualification.json').write_text(json.dumps({'schema':'offline-direct-qualification-v1','rows':rows,'production_admission':False,'default_plus_custom':'unqualified','real_provider':'not-executed'},indent=2))
