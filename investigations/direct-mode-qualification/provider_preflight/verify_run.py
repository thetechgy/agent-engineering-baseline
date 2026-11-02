"""Independent bounded data reader. Uses trusted checkout code, never artifact code."""
import sys
sys.dont_write_bytecode=True
import hashlib,io,json,stat,subprocess,zipfile
from pathlib import Path,PurePosixPath
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from policy import decode,canonical,MODEL,CATALOG_SHA
from admission import admit,patch_controls

def main():
 run_id,out=sys.argv[1],Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True);repo='thetechgy/agent-engineering-baseline'
 checkout=HERE.parents[2];head=subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True).strip()
 def api(path):return subprocess.check_output(['gh','api',f'repos/{repo}/{path}'])
 run=decode(api('actions/runs/'+run_id))
 assert run['repository']['full_name']==repo and run['head_repository']['full_name']==repo and run['head_sha']==head
 assert run['event']=='push' and run['head_branch']=='experiment/direct-mode-qualification' and run['run_attempt']==1 and run['conclusion']=='success'
 assert run['actor']['login']=='thetechgy' and run['path']=='.github/workflows/experimental-direct-mode-qualification.yml'
 meta=decode(api(f'actions/runs/{run_id}/artifacts'));assert meta['total_count']==len(meta['artifacts'])==1
 a=meta['artifacts'][0];assert a['workflow_run']['id']==int(run_id) and a['workflow_run']['head_sha']==head and not a['expired']
 raw=api(f'actions/artifacts/{a["id"]}/zip');assert len(raw)==a['size_in_bytes'] and a['digest']=='sha256:'+hashlib.sha256(raw).hexdigest()
 (out/(run_id+'.zip')).write_bytes(raw);(out/(run_id+'-run.json')).write_bytes(canonical(run));(out/(run_id+'-artifacts.json')).write_bytes(canonical(meta))
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  entries=z.infolist();names=z.namelist();assert len(entries)<2048 and len(set(names))==len(names) and sum(e.file_size for e in entries)<32*1024*1024
  for e in entries:
   path=PurePosixPath(e.filename);assert not path.is_absolute() and '..' not in path.parts and '\\' not in e.filename and e.file_size<=8*1024*1024
   assert stat.S_IFMT(e.external_attr>>16) in (0,stat.S_IFREG,stat.S_IFDIR)
  def read(name):return decode(z.read(name))
  export=read('export.json');assert export['source']==head and export['run']==run_id and export['attempt']=='1'
  assert export['qualification']=='offline-qualified' and export['paired_qualification']=='offline-qualified' and export['provider_preflight']=='fake-qualified'
  q=read('qualification.json');assert len(q['rows'])==3 and q['production_admission'] is False and q['default_plus_custom']=='unqualified'
  pre=read('provider-preflight/preflight.json');assert pre['cleanup_verified'] is True and pre['inference_executed'] is False and pre['ready_for_inference'] is False
  scenarios={r['scenario']:r for r in pre['rows']};assert len(scenarios)==11
  prefix='provider-preflight/normal/'
  requests=[read(prefix+f'request-{i}.json') for i in range(1,7)];responses=[z.read(prefix+f'response-{i}.sse') for i in range(1,7)]
  audit=[decode(s) for s in z.read(prefix+'relay.jsonl').splitlines()];effects=read(prefix+'independent-effects.json');capture=read(prefix+'native.json')
  recomputed=admit(capture,requests,responses,audit,effects['effects'],effects['nonce']);assert recomputed['native_patches']==1 and recomputed['native_commands']==3
  assert len(patch_controls(capture,requests,responses,audit,effects['effects'],effects['nonce']))==4
  restart=read(prefix+'relay-restart.json');assert restart['original_pid']>0 and restart['replacement_running'] is False and restart['replacement_pid']==0 and restart['replacement_exit_code']!=0 and restart['ledger_sha256_before']==restart['ledger_sha256_after']
  consumed=[decode(s) for s in z.read(prefix+'upstream-consumption.jsonl').splitlines()];generated=[r for r in consumed if r['path']=='/v1/responses'];reserved=[r for r in audit if r['phase']=='generation-reserved']
  assert len(consumed)==12 and [r['body_sha256'] for r in generated]==[r['request_sha256'] for r in reserved]
  assert all(r['tool_catalog_sha256']==CATALOG_SHA and r['model']==MODEL and r['max_output_tokens']==1024 and r['service_tier']=='default' and r['cache_options']=={'ttl':'30m'} and r['expected_provider_authorization'] for r in generated)
  for scenario,row in scenarios.items():
   p='provider-preflight/'+scenario+'/'
   cleanup=read(p+'cleanup.json');assert cleanup=={'verified':True,'containers_removed':3,'networks_removed':2,'volumes_removed':1,'firewall_rules_removed':3}
   n=row['network'];assert n['relay'] is True and not any(n[k] for k in ('relay_wrong_port','fake_upstream','host_gateway','public_ip','external_dns','provider_key_present')) and (n['uid'],n['caps'],n['nnp'],n['seccomp'])==(1000,'0000000000000000','1','2')
   rows=[decode(s) for s in z.read(p+'relay.jsonl').splitlines()];previous='0'*64
   for index,r in enumerate(rows):
    assert (r['sequence'],r['previous'])==(index,previous) and r['reserved_micro_usd']<=1000000;previous=hashlib.sha256(canonical(r)).hexdigest()
   if scenario=='watchdog':
    fired=read(p+'watchdog-fired.json');assert fired['reason']=='command-time-limit' and fired['active_ids']==['smoke-sleep'] and fired['elapsed_seconds']>=.5 and fired['container_running_after_stop'] is False
    assert row['classification']=='inconclusive-limit'
   elif scenario!='normal':
    assert not any(r['phase']=='response-admitted' for r in rows) and len([r for r in rows if r['phase']=='authenticated-client-request'])==1
    assert not any(f.get('method')=='item/started' and f.get('params',{}).get('item',{}).get('type') in ('commandExecution','fileChange') for f in read(p+'native.json')['frames'])
  result={'schema':'independent-provider-preflight-verification-v1','source':head,'run_id':int(run_id),'attempt':1,'artifact_id':a['id'],'artifact_digest':a['digest'],'members':len(entries),'bytes_uncompressed':sum(e.file_size for e in entries),'native_fake_scenarios':len(scenarios),'native_patch_corruptions_rejected':4,'exact_catalog_sha256':CATALOG_SHA,'independent_upstream_consumption':True,'ledger_chains_and_cleanup_verified':True,'real_inference_executed':False,'ready_for_inference':False,'live_blockers':pre['live_blockers']}
  (out/'PREFLIGHT_VERIFICATION.json').write_bytes(canonical(result));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
