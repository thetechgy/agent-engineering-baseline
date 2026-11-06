"""Retrospective-only observer of unchanged grader calls; no scoring replacement."""
import importlib.util,json
from pathlib import Path
spec=importlib.util.spec_from_file_location('qualified_grader','/tests/verifier/grader.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
original=g.invoke
variants=['reference',*[p.name for p in sorted(Path('/tests/case/mutants').glob('*.ps1'))]]
record={'admission':None,'runs':[]}

def observed(*args,**kwargs):
    value=original(*args,**kwargs)
    # Runner output is fixed protocol metadata only; never retain source/failure text.
    allowed={'status','code','version','powershell_version','total','passed','failed','skipped','not_run','inconclusive','failed_blocks','failed_containers','assertion_failures','admission_rule','admission_diagnostic','process_exit'}
    assert set(value)<=allowed
    if kwargs.get('admission'):record['admission']=value
    else:record['runs'].append({'variant':variants[len(record['runs'])],'result':value})
    return value

g.invoke=observed
try:g.main()
finally:
    path=Path('/logs/verifier/native-runs.json');path.write_text(json.dumps(record))
