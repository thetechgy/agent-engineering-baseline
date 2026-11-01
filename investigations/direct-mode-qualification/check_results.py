import json,sys
from pathlib import Path
root=Path(sys.argv[1]);rows=[]
for profile in ('positive','denied'):
 rewards=[]
 for p in (root/profile).rglob('reward.json'):
  d=json.loads(p.read_text());m=d.get('custom_metrics',{})
  if 'gh_authorization' in m:rewards.append((p,m))
 if len(rewards)!=2:raise RuntimeError(f'{profile}: expected exactly two gh rewards, found {len(rewards)}')
 for p,m in rewards:
  if m['gh_evidence']!=1 or m['gh_task']!=1 or m['gh_authorization']!=(profile=='positive'):raise RuntimeError(f'wrong {profile} oracle result: {m}')
 rows.append({'profile':profile,'arms':2,'metrics':[m for _,m in rewards]})
(root/'qualification.json').write_text(json.dumps({'schema':'offline-direct-qualification-v1','rows':rows,'production_admission':False,'default_plus_custom':'unqualified','real_provider':'not-executed'},indent=2))
