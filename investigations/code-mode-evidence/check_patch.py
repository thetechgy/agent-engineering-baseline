"""Check journal callback coverage without promoting it to trusted scoring."""
import json
from pathlib import Path
import sys

root=Path(sys.argv[1])
raw=(root/'callbacks.jsonl').read_bytes()
assert len(raw)<9*1024*1024
records=[json.loads(line) for line in raw.splitlines()]
scopes={}
for record in records:
    scopes.setdefault(record['scope'], []).append(record)
assert len(scopes)==4
result={}
for entries in scopes.values():
    opened=entries[0]
    assert opened['stage']=='scope_open'
    assert entries[-1]['stage']=='scope_closed'
    entered=[e for e in entries if e['stage']=='callback_entered']
    assert entries[-1]['callbacks']==len(entered)
    assert [e['callback'] for e in entered]==list(range(1,len(entered)+1))
    result[opened['outer']]=dict(callbacks=len(entered),
        serialized=[e['arguments_complete'] for e in entries if e['stage']=='serialized'])
assert result['outer-empty']['callbacks']==0
assert result['outer-normal']==dict(callbacks=1,serialized=[True])
assert result['outer-serialization-rejection']==dict(callbacks=1,serialized=[])
assert result['outer-oversized-rejection']==dict(callbacks=1,serialized=[False])
(root/'patch-summary.json').write_text(json.dumps(dict(
    callback_coverage=result, argument_incompleteness_preserved=True,
    security_admission='unavailable-not-qualified-for-production'),indent=2))
