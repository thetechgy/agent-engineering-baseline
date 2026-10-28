"""Read only bounded synthetic evidence; never import or execute artifact content."""
import collections,hashlib,json,pathlib,shutil,stat,sys,zipfile
archive,metadata,run_metadata,dest,report=map(pathlib.Path,sys.argv[1:])
meta=json.loads(metadata.read_text())['artifacts'][0];run=json.loads(run_metadata.read_text())
assert run['conclusion']=='success' and run['event']=='push' and run['head_branch']=='experiment/skill-evaluation-architecture'
assert 'sha256:'+hashlib.sha256(archive.read_bytes()).hexdigest()==meta['digest']
with zipfile.ZipFile(archive) as z:
 members=z.infolist();assert len(members)<1024 and sum(m.file_size for m in members)<16*1024*1024
 assert len({m.filename for m in members})==len(members)
 for m in members:
  p=pathlib.PurePosixPath(m.filename);assert not p.is_absolute() and '..' not in p.parts and '\\' not in m.filename and not stat.S_ISLNK(m.external_attr>>16)
 z.extractall(dest)
load=lambda p:json.loads((dest/p).read_text())
outcomes=load('outcomes.json');assert set(outcomes.values())=={0}
paired=load('paired-summary.json');counts=dict(collections.Counter(r['status'] for r in paired['rows']))
assert counts=={'passed':8,'failed':4,'unavailable':8} and paired['independent_states']==20
ids=[json.loads(p.read_text())['identity'] for p in dest.glob('paired/*/agent/setup-order.json')];assert len(ids)==20 and len(set(ids))==20
for p in dest.glob('paired/*/agent/setup-order.json'):assert json.loads(p.read_text())['cwd_import_isolated']
cleanup={}
for name,n in [('harbor-cleanup.json',6),('paired-cleanup.json',20)]:
 rows=load(name);assert len(rows)==n and all(r[k]==0 for r in rows for k in ['container','network','volume','image']);cleanup[name]=rows
harbor=load('harbor-results.json');failure=next(r['result'] for r in harbor if r['arm']=='init-failure')
assert failure['exception_info']['exception_type']=='RuntimeError' and failure['exception_info']['exception_message']=='required initializer failed (exit 1)' and failure['verifier_result'] is None
assert not (dest/'trials/architecture-init-failure/agent/setup-order.json').exists()
for r in harbor:
 if r['arm'] in ('missing','contradictory'):
  assert r['result']['verifier_result'] is None
  assert r['result']['exception_info']['exception_type']=='ValueError'
bindings=[]
for p in dest.glob('paired/*/agent/fixture-binding.json'):
 b=json.loads(p.read_text());assert b['audit_population']==7 and b['admission']['complete'];bindings.append(b)
assert len(bindings)==12
inspect=[]
expected_security={'uid':1000,'status':{'CapEff':'0000000000000000','Seccomp':'2','NoNewPrivs':'1'},'interfaces':['lo']}
for p in sorted((dest/'inspect').glob('*.eval')):
 with zipfile.ZipFile(p) as log:
  assert len(log.infolist())<1024 and sum(m.file_size for m in log.infolist())<16*1024*1024
  samples=[json.loads(log.read(n)) for n in log.namelist() if n.startswith('samples/') and n.endswith('.json')]
  assert len(samples)==1;s=samples[0];assert s['store']['runtime_security']==expected_security
  events=dict(collections.Counter(e.get('event') for e in s['events']));mode=next(m for m in ('normal','failure','cancel') if '-'+m+'_' in p.name)
  if mode=='normal':assert s['store']['actual_patch_verified'] is True and s.get('error') is None and events['model']==2 and s['store']['initializer_cwd_poison_rejected']
  else:
   assert s.get('error') is not None and not s['store'].get('actual_patch_verified') and 'model' not in events
   if mode=='failure':assert 'required initializer failed (exit 1)' in s['error']['message']
  inspect.append({'mode':mode,'store':s['store'],'error_message':s['error']['message'] if s.get('error') else None,'event_counts':events,'log_file':p.name})
assert {i['mode'] for i in inspect}=={'normal','failure','cancel'}
summary={'schema':'architecture-poc-qualification-v1','evidence_class':'actual-framework-container-lifecycle-with-scripted-inference-free-provider','run_id':run['id'],'run_attempt':run['run_attempt'],'code_revision':run['head_sha'],'artifact':{k:meta[k] for k in ['id','name','digest','size_in_bytes','expires_at']},'archive_members':len(members),'uncompressed_bytes':sum(m.file_size for m in members),'outcomes':outcomes,'focused_outcomes':[{'arm':r['arm'],'exception_type':r['result']['exception_info']['exception_type'] if r['result']['exception_info'] else None,'exception_message':r['result']['exception_info']['exception_message'] if r['result']['exception_info'] else None,'verifier_ran':r['result']['verifier_result'] is not None} for r in harbor],'paired':paired,'all_initializer_identities':ids,'cleanup':cleanup,'inspect':inspect,'paired_native_broker_bindings':bindings,'fault_injection':'missing/contradictory controls mutate admission input in memory; original native capture retained','production_qualification':'not-qualified','paid_inference':False}
report.mkdir(exist_ok=True);(report/'qualification.json').write_text(json.dumps(summary,indent=2)+'\n');example=report/'native-example';example.mkdir(exist_ok=True)
for name in ['events.json','wire.jsonl','fixture-binding.json','actual.txt','security.json','setup-order.json']:
 shutil.copyfile(dest/'trials/architecture-with/agent'/name,example/name)
print(json.dumps({'digest_verified':meta['digest'],'members':len(members),'bytes':summary['uncompressed_bytes'],'outcomes':outcomes,'paired':counts,'states':len(set(ids)),'cleanup_projects':26,'inspect_modes':[i['mode'] for i in inspect]},indent=2))
