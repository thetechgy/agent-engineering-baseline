"""Actual Harbor Trial lifecycle through the inherited secure Docker backend."""
import asyncio, json, pathlib, subprocess, sys
from harbor.agents.base import BaseAgent
from harbor.models.trial.config import TrialConfig
from harbor.trial.trial import Trial
from skillevaluator.tier3.harbor.secure_docker_environment import SkillEvaluatorSecureDockerEnvironment

class TrustedEnvironment(SkillEvaluatorSecureDockerEnvironment):
 def __init__(self,*a,fail_init=False,**kw):
  super().__init__(*a,**kw);self.fail_init=fail_init
 async def start(self,force_build):
  await super().start(force_build)
  if self.fail_init:raise RuntimeError('injected required initializer failure')
  r=await self.exec('python /opt/broker.py init',user='root',timeout_sec=10)
  if r.return_code:raise RuntimeError('required initializer failed: '+r.stderr)
  self.initializer=json.loads(r.stdout)

class ProbeAgent(BaseAgent):
 @staticmethod
 def name():return 'architecture-probe'
 def version(self):return '1'
 async def setup(self,environment):
  assert (await environment.exec('id -u')).stdout.strip()=='1000'
  ready=await environment.exec('python /opt/broker.py ready',timeout_sec=5)
  assert ready.return_code==0
  assert json.loads(ready.stdout)['identity']==environment.initializer['identity']
  (self.logs_dir/'setup-order.json').write_text(json.dumps(environment.initializer))
 async def run(self,instruction,environment,context):
  for command in ['cat /opt/private/identity','cat /opt/private/audit','python /opt/broker.py init','rm /run/poc/broker.sock']:
   assert (await environment.exec(command,timeout_sec=5)).return_code!=0,command
  for op,expected in [('read',True),('mutate',True),('mutate',False),('private',False)]:
   r=await environment.exec('python /opt/broker.py '+op,timeout_sec=5)
   assert r.return_code==0 and json.loads(r.stdout)['allowed']==expected
  assert (await environment.exec('python /opt/probe.py',timeout_sec=90)).return_code==0
  for name in ['events.json','requests.json','stderr.txt','actual.txt']:
   await environment.download_file('/workspace/'+name,self.logs_dir/name)

async def main(root):
 out=root/'evidence';task=root/'task';env=task/'environment';env.mkdir(parents=True)
 (env/'Dockerfile').write_text('FROM architecture-poc:164\nUSER root\n')
 (env/'docker-compose.yaml').write_text('services:\n  main:\n    build: .\n    command: ["sleep", "infinity"]\n    network_mode: none\n    cap_drop: [ALL]\n    security_opt: ["no-new-privileges:true"]\n    pids_limit: 128\n')
 (task/'instruction.md').write_text('Execute the operator fixture.\n')
 (task/'task.toml').write_text('schema_version="1.3"\n[agent]\nuser="agent"\ntimeout_sec=100\n[verifier]\nuser="root"\ntimeout_sec=10\n[environment]\ncpus=2\nmemory_mb=1024\nstorage_mb=1024\nworkdir="/workspace"\nnetwork_mode="no-network"\n')
 (task/'tests').mkdir();(task/'tests/test.sh').write_text('#!/bin/sh\nmkdir -p /logs/verifier\nprintf 1 > /logs/verifier/reward.txt\n')
 (task/'tests/test.sh').chmod(0o755)
 rows=[]
 for arm,fail in [('with',False),('without',False),('init-failure',True)]:
  config=TrialConfig.model_validate({'task':{'path':str(task)},'trial_name':'architecture-'+arm,'trials_dir':str(out/'trials'),'agent':{'import_path':'harbor_gate:ProbeAgent'},'environment':{'import_path':'harbor_gate:TrustedEnvironment','kwargs':{'fail_init':fail}}})
  trial=await Trial.create(config);result=await trial.run()
  rows.append({'arm':arm,'result':result.model_dump(mode='json')})
  (out/'harbor-results.json').write_text(json.dumps(rows,indent=2))
  if not fail:assert result.exception_info is None,str(result.exception_info)
  else:assert result.exception_info is not None
 (out/'harbor-results.json').write_text(json.dumps(rows,indent=2))
 identities=[json.loads(p.read_text())['identity'] for p in out.glob('trials/*/agent/setup-order.json')]
 assert len(identities)==2 and len(set(identities))==2
 remaining=subprocess.check_output(['docker','ps','-aq','--filter','name=architecture-'],text=True).strip()
 assert not remaining,'trial containers remain'
 print('Harbor secure lifecycle gates passed')
if __name__=='__main__':asyncio.run(main(pathlib.Path(sys.argv[1])))
