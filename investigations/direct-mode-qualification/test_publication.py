"""Required producer/consumer metric parity and sensitive-name rejection."""
import json,runpy,sys
from pathlib import Path
from skillevaluator.tier3.harbor.metrics import extract_custom_metrics,custom_metric_name_is_publishable
root,evidence=map(Path,sys.argv[1:])
p=root/'src/skillevaluator/tier3/harbor/templates/custom_grader_runner.py'
after=runpy.run_path(str(p));source=p.read_text();before_source=source.replace('    if text == "gh_authorization":\n        return False\n','')
before={'__file__':str(p),'__name__':'publication_before_control'};exec(compile(before_source,str(p),'exec'),before)
metrics={f'gh_{name}':1.0 for name in ('evidence','activation','commands','task','recovery','authorization','efficiency','gate')}
if set(before['_extract_custom_metrics']({'custom_metrics':metrics}))!=set(metrics)-{'gh_authorization'}:raise RuntimeError('before control changed')
for value in (0.0,1.0):
 metrics['gh_authorization']=value
 published=after['_extract_custom_metrics']({'custom_metrics':metrics})
 if published!=metrics or extract_custom_metrics({'custom_metrics':published})!=metrics:raise RuntimeError('individual metric lost or changed')
unsafe=('authorization','gh_authorization_extra','gh_Authorization','gh_secret','api_key','private_key','ghs_'+'x'*36)
for name in unsafe:
 if not after['_metric_name_contains_sensitive_data'](name) or custom_metric_name_is_publishable(name):raise RuntimeError('sensitive metric name accepted')
for value in (2.0,float('nan'),'private-synthetic-data'):
 if 'gh_authorization' in after['_extract_custom_metrics']({'custom_metrics':{'gh_authorization':value}}):raise RuntimeError('non-score authorization value accepted')
(evidence/'publication-controls.json').write_text(json.dumps({'evidence_class':'synthetic-publication-controls','original_dropped':['gh_authorization'],'exact_name_preserved_for':[0.0,1.0],'sensitive_names_rejected':len(unsafe),'non_score_values_rejected':3},indent=2))
print('Exact numeric gh_authorization preserved by producer and consumer; sensitive names and non-scores rejected')
