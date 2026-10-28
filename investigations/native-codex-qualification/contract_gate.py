"""Real native protocol coverage, kept separate from item-lifecycle coverage."""
import argparse,json,pathlib,subprocess,uuid
from aeb_native_qualification.evidence import observe,admit,Unavailable,ADMISSION_BLOCKER

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--engine',choices=('docker','podman'),default='docker');ap.add_argument('--out',type=pathlib.Path,required=True);args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    rows=[]
    profiles=[('normal',{}),('denied-inner',{'mode':'escalated-inner'}),('metadata-normal',{'tool_metadata':True}),('metadata-denied',{'tool_metadata':True,'mode':'escalated-inner'}),('host-disabled',{'disable_code_mode_host':True}),('unadvertised-direct',{'direct':True,'keep_code_mode_host':True})]
    def run(*parts):return subprocess.run([args.engine,*parts],capture_output=True,text=True,timeout=65)
    for label,payload in profiles:
        name='aeb-contract-'+uuid.uuid4().hex[:12]
        result=run('run','-d','--name',name,'--network=none','--cap-drop=ALL','--security-opt=no-new-privileges','--pids-limit=128','--memory=1g','--cpus=2','aeb-native-qualification:164','sleep','infinity');assert result.returncode==0,result.stderr
        try:
            spec=json.loads(run('inspect',name).stdout)[0];assert spec['Mounts']==[] and spec['HostConfig']['NetworkMode']=='none' and not spec['HostConfig']['Privileged']
            result=run('exec','--user','agent',name,'python3','-I','/opt/qualification/native_controller.py',json.dumps(payload));assert result.returncode==0,result.stderr
            capture=json.loads(result.stdout);(args.out/(label+'.json')).write_text(json.dumps(capture,indent=2))
            observation=observe(capture)
            raw=[f['params']['item'] for f in capture['frames'] if f.get('method')=='rawResponseItem/completed']
            tools={t['name'] for namespace in capture['tool_catalog'] for t in namespace.get('tools',[])}
            calls=[i for i in raw if i['type'] in ('function_call','custom_tool_call')]
            assert len(calls)==1
            advertised=calls[0]['name'] in tools
            if label=='unadvertised-direct':
                assert not advertised and observation['commands'][0]['id']==calls[0]['call_id']
            else:assert advertised and calls[0]['name']=='exec'
            if label=='host-disabled':
                assert not observation['commands'] and any('code-mode host is disabled' in json.dumps(i) for i in raw if i['type']=='custom_tool_call_output')
            elif 'denied' in label:
                assert not observation['commands'] and not observation['patches']
                assert any('approval policy is Never' in json.dumps(i) for i in raw if i['type']=='custom_tool_call_output')
            elif label!='unadvertised-direct':assert len(observation['commands'])==5 and len(observation['patches'])==1
            assert all('arguments' not in item for item in observation['commands'])
            try:admit(capture)
            except Unavailable as e:assert str(e)==ADMISSION_BLOCKER
            else:raise AssertionError('unsupported argument coverage admitted')
            rows.append({'profile':label,'native_item_population_complete':True,'scripted_call_advertised':advertised,'command_items':len(observation['commands']),'patch_items':len(observation['patches']),'security_grade_available':False,'admission':'unavailable','reason':ADMISSION_BLOCKER})
        finally:
            assert run('rm','-f',name).returncode==0
            assert not run('ps','-aq','--filter','name='+name).stdout.strip()
    (args.out/'summary.json').write_text(json.dumps({'evidence_class':'actual-container-and-native-protocol','rows':rows,'cleanup_verified':True,'qualification':'blocked-public-submission-contract'},indent=2))
    print(json.dumps(rows))

if __name__=='__main__':main()
