"""Operator-owned two-container observation boundary; no daemon in either trial."""
import argparse
import base64
import hashlib
import ipaddress
import json
from pathlib import Path
import subprocess
import time
import uuid


def run(*parts,timeout=100,check=True):
    result=subprocess.run(['docker',*parts],capture_output=True,text=True,timeout=timeout)
    if check:
        assert result.returncode==0,result.stderr[-3000:]
    return result


def inspect(name):
    return json.loads(run('inspect',name).stdout)[0]


def constraints(name):
    spec=inspect(name)
    assert not spec['Mounts'] and not spec['HostConfig']['Privileged']
    assert len(spec['NetworkSettings']['Networks'])==1
    assert 'ALL' in spec['HostConfig']['CapDrop']
    assert any('no-new-privileges' in value for value in spec['HostConfig']['SecurityOpt'])
    assert spec['HostConfig']['Memory']==2*1024**3
    code="import os,json,pathlib;d=dict(l.split(':',1) for l in pathlib.Path('/proc/self/status').read_text().splitlines() if ':' in l);print(json.dumps(dict(uid=os.getuid(),cap=d['CapEff'].strip(),nnp=d['NoNewPrivs'].strip(),seccomp=d['Seccomp'].strip(),ns={n:os.readlink('/proc/self/ns/'+n) for n in ['pid','net','mnt']})))"
    state=json.loads(run('exec',name,'python','-I','-c',code).stdout)
    assert state['uid']==1000 and int(state['cap'],16)==0 and state['nnp']=='1' and state['seccomp']=='2'
    return state


def main(args):
    args.out.mkdir()
    rows=[]
    profiles=('isolation',) if args.boundary_only else ('empty','denied','oversized','isolation')
    for profile in profiles:
        prefix='aeb-protected-'+uuid.uuid4().hex[:10]
        network,agent,helper,attacker=[prefix+suffix for suffix in ('-net','-agent','-helper','-attacker')]
        created=[]
        run('network','create','--internal',network)
        assert json.loads(run('network','inspect',network).stdout)[0]['Internal']
        try:
            common=['--network',network,'--cap-drop=ALL','--security-opt=no-new-privileges',
                    '--pids-limit=256','--memory=2g','--cpus=2']
            for name in (agent,attacker):
                run('run','-d','--name',name,*common,'aeb-cm:166')
                created.append(name)
            agent_ip=str(ipaddress.IPv4Address(inspect(agent)['NetworkSettings']['Networks'][network]['IPAddress']))
            attacker_ip=str(ipaddress.IPv4Address(inspect(attacker)['NetworkSettings']['Networks'][network]['IPAddress']))
            command=('python -m grpc_tools.protoc -I/opt/experiment/bindings --python_out=/workspace '
                     '--grpc_python_out=/workspace /opt/experiment/bindings/code_mode.proto; '
                     'exec python /opt/experiment/native.py --serve --host /workspace/patched-host '
                     '--catalog /opt/experiment/catalog.json --controller /opt/experiment/controller.py '
                     '--out /workspace/proxy.json --allowed-ip '+agent_ip)
            run('create','--name',helper,*common,'aeb-cm:166','sh','-ec',command)
            created.append(helper)
            run('cp',str(args.host),helper+':/workspace/patched-host')
            run('start',helper)
            deadline=time.monotonic()+15
            while run('exec',helper,'test','-f','/workspace/ready',check=False).returncode:
                assert time.monotonic()<deadline,run('logs',helper,check=False).stderr
                time.sleep(.1)
            helper_before=inspect(helper)
            helper_ip=str(ipaddress.IPv4Address(helper_before['NetworkSettings']['Networks'][network]['IPAddress']))
            before=json.loads(run('exec',helper,'cat','/workspace/gate.json').stdout)
            if args.boundary_only:
                run('exec',helper,'python','-I','-c',
                    'from pathlib import Path;Path("/workspace/callbacks.jsonl").write_text(\'{"operator_marker":true}\\n\')')
            states={name:constraints(name) for name in (agent,helper)}
            for kind in ('pid','net','mnt'):
                assert states[agent]['ns'][kind]!=states[helper]['ns'][kind]
            # Unauthorized peer has a real connection but cannot consume the seed slot.
            attack="import socket,sys;s=socket.create_connection((sys.argv[1],9000),timeout=3);s.settimeout(3);print(repr(s.recv(10)));s.close()"
            denied=run('exec',attacker,'python','-I','-c',attack,helper_ip,check=False)
            assert denied.returncode!=0 or denied.stdout.strip()=="b''"
            result=run('exec',agent,'python','/opt/experiment/worker.py',
                       'http://'+helper_ip+':9000',profile,str(before['backend_port']))
            capture=json.loads(result.stdout)
            gate=json.loads(run('exec',helper,'cat','/workspace/gate.json').stdout)
            assert gate['accepted']==[agent_ip] and gate['rejected']==[attacker_ip]
            assert not gate['producer_failed']
            assert gate['producer_sha256']==hashlib.sha256(args.host.read_bytes()).hexdigest()
            assert inspect(helper)['Id']==helper_before['Id'] and inspect(helper)['State']['Running']
            # No fresh connection is accepted after evaluated execution started.
            again=run('exec',agent,'python','-I','-c',
                      'import socket,sys;socket.create_connection((sys.argv[1],9000),timeout=1)',helper_ip,check=False)
            assert again.returncode!=0
            proxy=json.loads(run('exec',helper,'cat','/workspace/proxy.json').stdout)
            journal_text=run('exec',helper,'cat','/workspace/callbacks.jsonl').stdout
            assert 'FORGED-JOURNAL' not in journal_text
            journal=[json.loads(line) for line in journal_text.splitlines()]
            if args.boundary_only:
                assert journal==[{'operator_marker':True}]
            else:
                opens=[r for r in journal if r['stage']=='scope_open']
                closes=[r for r in journal if r['stage']=='scope_closed']
                entered=[r for r in journal if r['stage']=='callback_entered']
                assert len(opens)==len(closes)==1
                assert opens[0]['scope']==closes[0]['scope']
                assert closes[0]['callbacks']==len(entered)==(0 if profile=='empty' else 1)
            executions=[r['message'] for r in proxy if r.get('method')=='Execute' and r['direction']=='request']
            assert len(executions)==1
            if not args.boundary_only:
                assert executions[0]['tool_call_id']==opens[0]['outer']
            raw=[frame['params']['item'] for frame in capture['frames']
                 if frame.get('method')=='rawResponseItem/completed']
            submitted=[item for item in raw if item.get('type') in ('custom_tool_call','function_call')]
            assert len(submitted)==1 and submitted[0]['name']=='exec'
            assert submitted[0]['call_id']==executions[0]['tool_call_id']
            assert sum(r.get('method')=='OpenSession' and r['direction']=='request' for r in proxy)==1
            calls=[r['message'] for r in proxy if r.get('method')=='SubscribeToToolCalls' and r['direction']=='response']
            assert len(calls)==(1 if profile in ('denied','isolation') else 0)
            closed=[r['message']['cell_closed'] for r in proxy
                    if r.get('method')=='OpenSession' and r['direction']=='response'
                    and 'cell_closed' in r['message']]
            assert len(closed)==1
            assert closed[0]['execution_id']==executions[0]['execution_id']
            assert int(closed[0].get('final_tool_call_sequence',0))==len(calls)
            assert sorted(int(call['sequence']) for call in calls)==list(range(1,len(calls)+1))
            assert all(call['execution_id']==closed[0]['execution_id'] and
                       call['cell_id']==closed[0]['cell_id'] for call in calls)
            for call in calls:
                if not args.boundary_only:
                    queued=next(r for r in journal if r['stage']=='runtime_queued' and
                                r['runtime_tool_call_id']==call['runtime_tool_call_id'])
                    original=next(r for r in journal if r['stage']=='serialized' and
                                  r['scope']==queued['scope'] and r['callback']==queued['callback'])
                    assert original['arguments_complete'] and original['input_present']
                    assert original['arguments']==json.loads(base64.b64decode(call['input_json']))
                terminals=[r for r in proxy if r.get('method')=='CompleteToolCall' and
                           r['direction']=='request' and r['message']['invocation_id']==call['invocation_id']]
                assert len(terminals)==1
            if profile=='oversized':
                serialized=next(r for r in journal if r['stage']=='serialized')
                assert serialized['arguments_complete'] is False
            if profile=='denied':
                assert json.loads(base64.b64decode(calls[0]['input_json']))['sandbox_permissions']=='require_escalated'
            if profile=='isolation':
                assert run('exec',agent,'cat','/workspace/callbacks.jsonl').stdout=='FORGED-JOURNAL\n'
                items=[f['params']['item'] for f in capture['frames'] if f.get('method')=='item/completed'
                       and f['params']['item'].get('type')=='commandExecution']
                report=json.loads(items[0]['aggregatedOutput'].splitlines()[-1])
                assert report['uid']==1000
                assert not any(report[k] for k in ('observer_journal_readable','frontend_connectable',
                                                  'backend_connectable','foreign_endpoint_bindable'))
            payload=dict(profile=profile,capture=capture,proxy=proxy,journal=journal,gate=gate,
                         containers={name:inspect(name) for name in (agent,helper)},kernel_states=states)
            (args.out/(profile+'.json')).write_text(json.dumps(payload,indent=2))
            rows.append(dict(profile=profile,callback_population_observed=not args.boundary_only,
                original_arguments_complete=not args.boundary_only and profile!='oversized',
                security_grade='unavailable-no-production-oracle-integration'))
        finally:
            for name in reversed(created):
                run('rm','-f',name,check=False)
                assert not run('ps','-aq','--filter','name=^/'+name+'$').stdout.strip()
            run('network','rm',network)
    (args.out/'summary.json').write_text(json.dumps(dict(
        evidence_class=('actual-boundary-with-operator-marker' if args.boundary_only else
                        'actual-native-and-isolated-observer-containers'),rows=rows,
        cleanup_verified=True,scope='single seeded connection and one session per host instance'),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--host',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--boundary-only',action='store_true')
    main(parser.parse_args())
