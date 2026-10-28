"""Actual Harbor Trial lifecycle through the inherited secure Docker backend."""
import asyncio, contextlib, copy, hashlib, json, pathlib, shlex, subprocess, sys
from harbor.agents.base import BaseAgent
from harbor.models.trial.config import TrialConfig
from harbor.trial.trial import Trial
from skillevaluator.tier3.harbor.secure_docker_environment import SkillEvaluatorSecureDockerEnvironment

class TrustedEnvironment(SkillEvaluatorSecureDockerEnvironment):
 def __init__(self,*a,fail_init=False,**kw):
  super().__init__(*a,**kw);self.fail_init=fail_init
 async def start(self,force_build):
  await super().start(force_build)
  for module,target in [('broker.py','broker'),('native_probe.py','probe'),('start_native.py','start')]:
   source=pathlib.Path(__file__).with_name(module)
   remote='/opt/operator-'+target+'.py'
   expected=hashlib.sha256(source.read_bytes()).hexdigest()
   program="import pathlib,os,hashlib,stat; p=pathlib.Path('"+remote+"'); parent=p.parent.lstat(); assert parent.st_uid==0 and not parent.st_mode&0o022; f=p.open('xb'); f.write(bytes.fromhex('"+source.read_bytes().hex()+"')); f.close(); os.chmod(p,0o444); s=p.lstat(); assert s.st_uid==0 and s.st_nlink==1 and stat.S_ISREG(s.st_mode); print(hashlib.sha256(p.read_bytes()).hexdigest())"
   check=await self.exec('python -c '+shlex.quote(program),user='root',timeout_sec=5)
   assert check.return_code==0 and check.stdout.strip()==expected,'operator code substitution'
  absent=await self.exec('python /opt/operator-broker.py ready',user='agent',timeout_sec=5)
  assert absent.return_code!=0,'missing broker passed readiness'
  if self.fail_init:
   assert (await self.exec('mkdir /opt/private',user='root',timeout_sec=5)).return_code==0
  r=await self.exec('python /opt/operator-broker.py init',user='root',timeout_sec=10)
  if r.return_code:raise RuntimeError(f'required initializer failed (exit {r.return_code})')
  self.initializer=json.loads(r.stdout)

class ProbeAgent(BaseAgent):
 def __init__(self,*a,hold=False,evidence_fault=None,skill_probe=False,**kw):
  super().__init__(*a,**kw);self.hold=hold;self.evidence_fault=evidence_fault;self.skill_probe=skill_probe
 @staticmethod
 def name():return 'architecture-probe'
 def version(self):return '1'
 async def setup(self,environment):
  assert (await environment.exec('id -u')).stdout.strip()=='1000'
  r=await environment.exec("python -c 'import json,pathlib; s=pathlib.Path(\"/proc/self/status\").read_text(); print(json.dumps({\"capabilities\":next(x for x in s.splitlines() if x.startswith(\"CapEff:\")),\"seccomp\":next(x for x in s.splitlines() if x.startswith(\"Seccomp:\")),\"no_new_privs\":next(x for x in s.splitlines() if x.startswith(\"NoNewPrivs:\")),\"interfaces\":sorted(p.name for p in pathlib.Path(\"/sys/class/net\").iterdir())}))'")
  security=json.loads(r.stdout);assert security['capabilities'].endswith('0000000000000000') and security['seccomp'].endswith('2') and security['no_new_privs'].endswith('1') and security['interfaces']==['lo']
  (self.logs_dir/'security.json').write_text(json.dumps(security))
  ready=await environment.exec('python /opt/broker.py ready',timeout_sec=5)
  assert ready.return_code==0
  assert json.loads(ready.stdout)['identity']==environment.initializer['identity']
  self.component_receipts=[environment.initializer['receipt'],json.loads(ready.stdout)['receipt']]
  assert (await environment.exec('python /opt/operator-start.py',user='agent',timeout_sec=5)).return_code==0
  (self.logs_dir/'setup-order.json').write_text(json.dumps(environment.initializer))
 async def run(self,instruction,environment,context):
  if self.hold:
   await environment.exec('sleep 30',timeout_sec=35)
   return
  for command in ['cat /opt/private/identity','cat /opt/private/audit','python /opt/broker.py init','rm /run/poc/broker.sock']:
   assert (await environment.exec(command,timeout_sec=5)).return_code!=0,command
  for op,expected in [('read',True),('mutate',True),('mutate',False),('private',False)]:
   r=await environment.exec('python /opt/broker.py '+op,timeout_sec=5)
   assert r.return_code==0 and json.loads(r.stdout)['allowed']==expected
   self.component_receipts.append(json.loads(r.stdout)['receipt'])
  assert (await environment.exec('python /opt/operator-probe.py protected broker-probe'+(' skill-probe' if self.skill_probe else ''),user='root',timeout_sec=90)).return_code==0
  from evidence_gate import admit
  for name in ['events.json','wire.jsonl','requests.json','stderr.txt','actual.txt']:
   await environment.download_file(('/workspace/' if name=='actual.txt' else '/opt/native-capture/')+name,self.logs_dir/name)
  assert (await environment.exec('cat /opt/native-capture/events.json',user='agent',timeout_sec=5)).return_code!=0
  events=json.loads((self.logs_dir/'events.json').read_text())
  if self.evidence_fault=='missing':events=[e for e in events if e.get('method')!='turn/completed']
  if self.evidence_fault=='contradictory':
   bad=copy.deepcopy(next(e for e in events if e.get('method')=='item/completed' and e['params']['item']['type']=='commandExecution'));bad['params']['item']['exitCode']=99;events.append(bad)
  admission=admit(events)
  audit_result=await environment.exec('cat /opt/private/audit',user='root',timeout_sec=5)
  audit=[json.loads(line) for line in audit_result.stdout.splitlines()]
  native=next(e['params']['item'] for e in events if e.get('method')=='item/completed' and '/opt/broker.py read' in e.get('params',{}).get('item',{}).get('command',''))
  receipt=json.loads(native['aggregatedOutput'])['receipt']
  assert len(audit)==len(self.component_receipts)+1 and {r['receipt'] for r in audit}==set(self.component_receipts+[receipt]),'unbound broker audit'
  assert next(r for r in audit if r['receipt']==receipt)['op']=='read'
  (self.logs_dir/'fixture-binding.json').write_text(json.dumps({'native_item_id':native['id'],'receipt':receipt,'audit_population':len(audit),'admission':admission}))

async def main(root):
 out=root/'evidence';task=root/'task';env=task/'environment';env.mkdir(parents=True)
 (env/'Dockerfile').write_text('FROM architecture-poc:164\nUSER root\n')
 (env/'docker-compose.yaml').write_text('services:\n  main:\n    build: .\n    command: ["sleep", "infinity"]\n    network_mode: none\n    cap_drop: [ALL]\n    security_opt: ["no-new-privileges:true"]\n    pids_limit: 128\n')
 (task/'instruction.md').write_text('Execute the operator fixture.\n')
 (task/'task.toml').write_text('schema_version="1.3"\n[agent]\nuser="agent"\ntimeout_sec=100\n[verifier]\nuser="root"\ntimeout_sec=10\n[environment]\ncpus=2\nmemory_mb=1024\nstorage_mb=1024\nworkdir="/workspace"\nnetwork_mode="no-network"\n')
 (task/'tests').mkdir();(task/'tests/test.sh').write_text('#!/bin/sh\nmkdir -p /logs/verifier\nprintf 1 > /logs/verifier/reward.txt\n')
 (task/'tests').chmod(0o755)
 (task/'tests/test.sh').chmod(0o755)
 rows=[];sessions=[]
 for arm,fail in [('with',False),('without',False),('init-failure',True),('missing',False),('contradictory',False)]:
  config=TrialConfig.model_validate({'task':{'path':str(task)},'trial_name':'architecture-'+arm,'trials_dir':str(out/'trials'),'agent':{'import_path':'harbor_gate:ProbeAgent','kwargs':{'evidence_fault':arm if arm in ('missing','contradictory') else None}},'environment':{'import_path':'harbor_gate:TrustedEnvironment','kwargs':{'fail_init':fail}}})
  trial=await Trial.create(config);sessions.append(trial.agent_environment.session_id);result=await trial.run()
  rows.append({'arm':arm,'result':result.model_dump(mode='json')})
  (out/'harbor-results.json').write_text(json.dumps(rows,indent=2))
  if arm in ('with','without'):assert result.exception_info is None,str(result.exception_info)
  else:assert result.exception_info is not None
  if fail:assert result.exception_info.exception_type=='RuntimeError' and result.exception_info.exception_message=='required initializer failed (exit 1)'
  if fail:assert not (out/'trials'/('architecture-'+arm)/'agent/setup-order.json').exists(),'failed initialization reached agent setup'
  if arm in ('missing','contradictory'):
   assert result.verifier_result is None,'invalid evidence reached grader'
   expected='incomplete execution population' if arm=='missing' else 'contradictory native identity'
   assert result.exception_info.exception_type=='ValueError' and result.exception_info.exception_message==expected
 (out/'harbor-results.json').write_text(json.dumps(rows,indent=2))
 identities=[json.loads(p.read_text())['identity'] for p in [out/'trials'/('architecture-'+arm)/'agent/setup-order.json' for arm in ('with','without')]]
 assert len(identities)==2 and len(set(identities))==2
 config=TrialConfig.model_validate({'task':{'path':str(task)},'trial_name':'architecture-cancel','trials_dir':str(out/'trials'),'agent':{'import_path':'harbor_gate:ProbeAgent','kwargs':{'hold':True}},'environment':{'import_path':'harbor_gate:TrustedEnvironment'}})
 trial=await Trial.create(config);sessions.append(trial.agent_environment.session_id);work=asyncio.create_task(trial.run())
 for _ in range(900):
  if (out/'trials/architecture-cancel/agent/setup-order.json').exists():break
  if work.done():raise AssertionError('cancellation trial ended before setup')
  await asyncio.sleep(.1)
 else:raise TimeoutError('cancellation setup deadline')
 await asyncio.sleep(.5);work.cancel()
 with contextlib.suppress(asyncio.CancelledError):await asyncio.wait_for(work,20)
 remaining=subprocess.check_output(['docker','ps','-aq','--filter','name=architecture-'],text=True).strip()
 assert not remaining,'trial containers remain'
 from resource_audit import audit
 (out/'harbor-cleanup.json').write_text(json.dumps(audit(sessions)))
 print('Harbor secure lifecycle gates passed')
if __name__=='__main__':asyncio.run(main(pathlib.Path(sys.argv[1])))
