"""Actual container/producer attacks; no mocked transport or inferred operation identity."""
import argparse,copy,json,pathlib,subprocess,uuid
from aeb_native_qualification.evidence import observe,Unavailable

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--engine',choices=('docker','podman'),default='docker');ap.add_argument('--out',type=pathlib.Path,required=True);args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    rows=[]
    def run(*parts,timeout=65):return subprocess.run([args.engine,*parts],capture_output=True,text=True,timeout=timeout)
    for mode in ('pipe-control','normal','fd-inject','ptrace','proc-mem','forged-output','kill-producer','kill-controller','stop-producer','workspace-normal','workspace-fd-inject'):
        name='aeb-producer-'+uuid.uuid4().hex[:12]
        r=run('run','-d','--name',name,'--network=none','--cap-drop=ALL','--security-opt=no-new-privileges','--pids-limit=128','--memory=1g','--cpus=2','aeb-native-qualification:164','sleep','infinity');assert r.returncode==0,r.stderr
        try:
            spec=json.loads(run('inspect',name).stdout)[0];assert spec['HostConfig']['NetworkMode']=='none' and spec['HostConfig']['Privileged'] is False and spec['Mounts']==[]
            if args.engine=='docker':assert 'ALL' in spec['HostConfig']['CapDrop']
            assert any('no-new-privileges' in s for s in spec['HostConfig']['SecurityOpt'])
            check="import os,pathlib; assert os.getuid()==1000; s=pathlib.Path('/proc/self/status').read_text(); d={l.split(':',1)[0]:l.split(':',1)[1].strip() for l in s.splitlines() if ':' in l}; assert all(int(d[k],16)==0 for k in ['CapInh','CapPrm','CapEff','CapBnd','CapAmb']); assert d['Seccomp']=='2' and d['NoNewPrivs']=='1'; assert sorted(p.name for p in pathlib.Path('/sys/class/net').iterdir())==['lo']; assert not pathlib.Path('/var/run/docker.sock').exists()"
            security=run('exec','--user','agent',name,'python3','-I','-c',check);assert security.returncode==0,security.stderr
            r=run('exec','--user','agent',name,'python3','-I','/opt/qualification/native_controller.py',json.dumps({'mode':('fd-inject' if mode=='pipe-control' else mode.removeprefix('workspace-')),'channel':('pipe' if mode=='pipe-control' else 'socketpair'),'sandbox':('workspace-write' if mode.startswith('workspace-') else 'danger-full-access')}))
            (args.out/(mode+'.stdout')).write_text(r.stdout);(args.out/(mode+'.stderr')).write_text(r.stderr)
            capture=json.loads(r.stdout) if r.returncode==0 else None
            accepted=False;reason=None
            if capture:
                try:admitted=observe(capture);accepted=True
                except Unavailable as e:reason=str(e)
            if mode=='pipe-control':
                assert not accepted and reason=='unqualified capture transport'
                injected=next(e['params']['item']['aggregatedOutput'] for e in capture['frames'] if e.get('method')=='item/completed' and '/opt/qualification/attack.py' in e.get('params',{}).get('item',{}).get('command',''))
                assert any(c['injected'] and c['fd'] in ('0','1') for c in json.loads(injected.splitlines()[-1])['checks'])
            elif mode.startswith('workspace-') and run('exec','--user','agent',name,'test','-f','/workspace/actual.txt').returncode!=0:
                failed=[i for i in admitted['commands'] if i['status']=='failed']
                assert failed and all('bwrap: No permissions to create a new namespace' in i['aggregatedOutput'] for i in failed)
                rows.append({'mode':mode,'exit_code':r.returncode,'item_population_observed':accepted,'runtime_qualified':False,'classification':'unsupported-runtime','reason':'default runtime blocks inner user namespace; outer protections retained'})
                (args.out/'producer-summary.json').write_text(json.dumps({'evidence_class':'actual-container-and-native-producer','rows':rows,'cleanup_verified':False},indent=2))
                continue
            elif mode in ('normal','fd-inject','ptrace','proc-mem','forged-output','workspace-normal','workspace-fd-inject'):
                assert accepted,(mode,reason,r.stderr)
                assert run('exec','--user','agent',name,'cat','/workspace/actual.txt').stdout=='actual-modification\n'
                if mode not in ('normal','workspace-normal'):
                    attacked=next(i for i in admitted['commands'] if '/opt/qualification/attack.py' in i['command'])
                    output=attacked['aggregatedOutput'];report=json.loads(output.splitlines()[-1]);assert report['uid']==1000
                    if mode in ('fd-inject','workspace-fd-inject'):assert len(report['checks'])==6 and not any(c['injected'] for c in report['checks'] if c['fd'] in ('0','1'))
                    if mode=='ptrace':assert len(report['checks'])==2 and all(c['result']==-1 for c in report['checks'])
                    if mode=='proc-mem':assert len(report['checks'])==2 and all(not c['memory_opened'] and c['pidfd_getfd']==-1 for c in report['checks'])
                    if mode=='forged-output':assert not any(i['id']=='forged-native-id' for i in admitted['commands'])
            else:assert not accepted,(mode,'interruption admitted')
            row={'mode':mode,'exit_code':r.returncode,'item_population_observed':accepted,'reason':reason,'classification':('rejected-injection-control' if mode=='pipe-control' else 'available' if accepted else 'unavailable')};rows.append(row)
            if mode=='normal':
                variants={}
                for variant in ('foreign-terminal','foreign-item','missing-result','snapshot-conflict','late-item','missing-eof'):
                    value=copy.deepcopy(capture)
                    if variant=='foreign-terminal':next(e for e in value['frames'] if e.get('method')=='turn/completed')['params']['turn']['id']='foreign'
                    if variant=='foreign-item':next(e for e in value['frames'] if e.get('method')=='item/started')['params']['turnId']='foreign'
                    if variant=='missing-result':value['frames'].pop(next(i for i,e in enumerate(value['frames']) if e.get('method')=='item/completed'))
                    if variant=='snapshot-conflict':next(e for e in value['frames'] if e.get('id')==4)['result']['thread']['turns'][0]['items'].pop()
                    if variant=='missing-eof':value['state']['transport_eof']=False
                    if variant=='late-item':value['frames'].append(next(e for e in value['frames'] if e.get('method')=='item/started'))
                    try:observe(value)
                    except Unavailable as e:variants[variant]=str(e)
                    else:raise AssertionError(variant)
                (args.out/'synthetic-controls.json').write_text(json.dumps(variants,indent=2))
        finally:
            assert run('rm','-f',name).returncode==0
            assert not run('ps','-aq','--filter','name='+name).stdout.strip()
        (args.out/'producer-summary.json').write_text(json.dumps({'evidence_class':'actual-container-and-native-producer','rows':rows,'cleanup_verified':True},indent=2))
    (args.out/'producer-summary.json').write_text(json.dumps({'evidence_class':'actual-container-and-native-producer','rows':rows,'cleanup_verified':True},indent=2))
    print(json.dumps(rows))
if __name__=='__main__':main()
