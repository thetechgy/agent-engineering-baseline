"""Twenty controlled infrastructure trials; never a model skill-effectiveness claim."""
import asyncio,json,pathlib,subprocess,sys
from harbor.models.trial.config import TrialConfig
from harbor.trial.trial import Trial

async def main(root):
 out=root/'evidence/paired';out.mkdir(parents=True);sem=asyncio.Semaphore(2)
 cases=['activation','negative-control','task-failure','missing','contradictory']
 async def one(case,arm,attempt):
  async with sem:
   name=f'paired-{case}-{arm}-{attempt}';task=root/name;env=task/'environment';env.mkdir(parents=True)
   docker='FROM architecture-poc:164\nUSER root\nRUN mkdir -p /workspace/skills/competing && printf "common fixture\\n" > /workspace/skills/competing/SKILL.md\n'
   if arm=='with':docker+='RUN mkdir -p /workspace/skills/probe && printf "synthetic skill fixture\\n" > /workspace/skills/probe/SKILL.md\n'
   (env/'Dockerfile').write_text(docker)
   (env/'docker-compose.yaml').write_text('services:\n  main:\n    build: .\n    command: ["sleep", "infinity"]\n    network_mode: none\n    cap_drop: [ALL]\n    security_opt: ["no-new-privileges:true"]\n    pids_limit: 128\n')
   (task/'instruction.md').write_text('Execute the controlled infrastructure fixture.\n')
   (task/'task.toml').write_text('schema_version="1.3"\n[agent]\nuser="agent"\ntimeout_sec=100\n[verifier]\nuser="root"\ntimeout_sec=10\n[environment]\ncpus=2\nmemory_mb=1024\nstorage_mb=1024\nworkdir="/workspace"\nnetwork_mode="no-network"\n')
   (task/'tests').mkdir(mode=0o755);(task/'tests').chmod(0o755)
   expected='different expected artifact' if case=='task-failure' else 'actual-modification'
   verifier=task/'tests/test.sh'
   verifier.write_text('#!/bin/sh\nmkdir -p /logs/verifier\nif [ "$(cat /workspace/actual.txt)" = "'+expected+'" ]; then printf 1; else printf 0; fi > /logs/verifier/reward.txt\n');verifier.chmod(0o755)
   config=TrialConfig.model_validate({'task':{'path':str(task)},'trial_name':name,'trials_dir':str(out),'agent':{'import_path':'harbor_gate:ProbeAgent','kwargs':{'skill_probe':case!='negative-control','evidence_fault':case if case in ('missing','contradictory') else None}},'environment':{'import_path':'harbor_gate:TrustedEnvironment'}})
   trial=await Trial.create(config);r=await trial.run();invalid=case in ('missing','contradictory')
   assert (r.exception_info is not None)==invalid,(name,r.exception_info)
   if invalid:
    assert r.verifier_result is None
    row={'case':case,'arm':arm,'attempt':attempt,'status':'unavailable','score':None,'activation_observed':None}
   else:
    rewards=r.verifier_result.rewards;score=next(iter(rewards.values()));assert score==(0 if case=='task-failure' else 1),(name,rewards)
    binding=json.loads((out/name/'agent/fixture-binding.json').read_text())
    active=binding['admission']['activation_observed'];assert active==(arm=='with' and case!='negative-control')
    row={'case':case,'arm':arm,'attempt':attempt,'status':'failed' if score==0 else 'passed','score':score,'activation_observed':active,'initializer_identity':json.loads((out/name/'agent/setup-order.json').read_text())['identity']}
   return row
 rows=await asyncio.gather(*(one(c,a,n) for c in cases for a in ('with','without') for n in (1,2)))
 assert len(rows)==20
 identities=[json.loads(p.read_text())['identity'] for p in out.glob('*/agent/setup-order.json')]
 assert len(identities)==20 and len(set(identities))==20
 assert not subprocess.check_output(['docker','ps','-aq','--filter','name=paired-'],text=True).strip()
 (root/'evidence/paired-summary.json').write_text(json.dumps({'policy':'synthetic-infrastructure-v1','rows':rows,'aggregate':'withheld: intentionally incomplete required evidence','independent_states':len(set(identities))},indent=2))
 print('Twenty paired infrastructure trials passed expected classifications')
if __name__=='__main__':asyncio.run(main(pathlib.Path(sys.argv[1])))
