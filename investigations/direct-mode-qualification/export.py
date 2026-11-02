"""Bounded data-only export; never publish build contexts, executables or keys."""
import json,os,stat,sys
from pathlib import Path
root=Path(sys.argv[1]);source=root/'evidence';target=root/'public-evidence';target.mkdir()
selected=[];total=0
for p in source.rglob('*'):
 if p.suffix not in ('.json','.jsonl','.log','.txt','.sse'):continue
 st=p.lstat()
 if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1:raise RuntimeError('unsafe export member')
 if st.st_size>8*1024*1024:raise RuntimeError('oversized diagnostic member')
 total+=st.st_size;selected.append(p)
 if len(selected)>=2048 or total>=32*1024*1024:raise RuntimeError('diagnostic export budget')
for p in selected:
 q=target/p.relative_to(source);q.parent.mkdir(parents=True,exist_ok=True);q.open('xb').write(p.read_bytes())
(target/'export.json').write_text(json.dumps({'source':os.environ.get('GITHUB_SHA'),'run':os.environ.get('GITHUB_RUN_ID'),'attempt':os.environ.get('GITHUB_RUN_ATTEMPT'),'members':len(selected),'bytes':total,'production_admission':False,'qualification':'offline-qualified' if (source/'qualification.json').is_file() and (source/'provider-preflight/preflight.json').is_file() else 'unavailable-required-gates-incomplete','paired_qualification':'offline-qualified' if (source/'qualification.json').is_file() else 'unavailable','provider_preflight':'fake-qualified' if (source/'provider-preflight/preflight.json').is_file() else 'unavailable','error_rewards':'retained raw; never admitted as scores'}))
