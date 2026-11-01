"""Bounded native producer attacks, scoped to the actual command item."""
import json
from pathlib import Path
import sys

root=Path(sys.argv[1])
capture=json.loads((root/'producer.json').read_text())
rows=[]
for row in capture['rows'][3:]:
    label=row['label']
    native=row['capture']
    if label.startswith('direct-effect-'):
        assert row['verified_effect']['exists']==(label=='direct-effect-allowed')
        rows.append(dict(profile=label,result='scoped-effect-verified'))
        continue
    if label=='direct-kill-producer':
        assert native['status']=='unavailable'
        rows.append(dict(profile=label, result='unavailable-as-required'))
        continue
    items=[frame['params']['item'] for frame in native['frames']
           if frame.get('method')=='item/completed'
           and frame['params']['item'].get('type')=='commandExecution']
    assert not any(item['id']=='forged-native-id' for item in items)
    assert len(items)==1
    output=items[0].get('aggregatedOutput','')
    if not output or 'No permissions to create a new namespace' in output:
        rows.append(dict(profile=label,result='unsupported-runtime'))
        continue
    report=json.loads(output.splitlines()[-1])
    assert report['uid']==1000
    if label=='direct-fd-inject':
        assert len(report['checks'])==6
        assert not any(check['injected'] for check in report['checks'] if check['fd'] in ('0','1'))
    elif label=='direct-ptrace':
        assert all(check['result']==-1 for check in report['checks'])
    elif label=='direct-proc-mem':
        assert all(not check['memory_opened'] and check['pidfd_getfd']==-1 for check in report['checks'])
    else:
        assert label=='direct-forged-output'
    rows.append(dict(profile=label,result='tested-attack-blocked'))
(root/'producer-summary.json').write_text(json.dumps(dict(rows=rows,
    scope='bounded socketpair producer tests; no external proxy authenticity claim'),indent=2))
