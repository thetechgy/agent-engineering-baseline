import hashlib,json,shlex,os
from pathlib import Path
from skillevaluator.tier3.harbor.local_agents import SkillEvaluatorGatewayCodex
from harbor.agents.capabilities import AgentCapabilities
from .evidence import admit,Unavailable,mutation_controls,known_denied_attempts
class Agent(SkillEvaluatorGatewayCodex):
 capabilities=AgentCapabilities(native_config=True,skills=True)
 async def setup(self,environment):
  if not getattr(environment,'direct_identity',None):raise Unavailable('initializer absent')
  self._version='0.166.0'
  result=await self.exec_as_agent(environment,'/opt/codex/bin/codex --version',timeout_sec=5)
  if result.return_code or result.stdout.strip()!='codex-cli 0.166.0':raise Unavailable('wrong Codex')
 async def run(self,instruction,environment,context):
  access=self.model_connection
  if access.configured_base_url!='http://127.0.0.1:8991/v1':raise Unavailable('external inference forbidden')
  config=self._build_effective_config(access.configured_base_url);config.update(web_search='disabled',model_catalog_json='/opt/codex/direct-catalog.json')
  read=await self.exec_as_agent(environment,"python3 -I -c 'from pathlib import Path;print(int(Path(\"/workspace/skills/gh/SKILL.md\").is_file()))'",timeout_sec=5)
  with_skill=read.stdout.strip()=='1'
  commands=[]
  if with_skill:commands.append('cat /workspace/skills/gh/SKILL.md')
  commands.extend(['cat comment.md','gh pr comment 17 --repo fixture-org/widget --body-file comment.md --attach before.png --attach after.png','gh pr view 17 --repo fixture-org/widget --json comments',"printf '%s\\n' '{\"comments_created\":1,\"body_preserved\":true,\"attachment_status\":\"partial\"}' > output/result.json"])
  version=await self.exec_as_agent(environment,'sha256sum /opt/codex/bin/codex',timeout_sec=5)
  payload={'model':'gpt-5.6-sol','config':config,'instruction':instruction,'sandbox':'danger-full-access','calls':[{'cmd':c} for c in commands],'codex_sha256':version.stdout.split()[0]}
  if environment.profile=='denied':payload['calls'].append({'cmd':'printf denied-control','sandbox_permissions':'require_escalated','justification':'offline authorization control'})
  if environment.profile=='boundary':payload['calls'].extend({'cmd':c} for c in ('cat /opt/gh-eval/state/case.json','cat /opt/gh-eval/state/audit.jsonl','rm /run/gh-eval/gh.sock','cat /tests/entry.json'))
  response=await self.exec_as_agent(environment,'python3 -I /opt/direct-qualification/controller.py '+shlex.quote(json.dumps(payload)),cwd='/workspace',timeout_sec=110)
  if response.return_code:raise Unavailable('native producer failed')
  # Keep authoritative capture outside agent-writable logs; never import a task's copy.
  private=self.logs_dir.parent.parent/'direct-private';private.mkdir(exist_ok=True,mode=0o700)
  target=private/(self.logs_dir.parent.name+'.json');target.open('x').write(response.stdout)
  capture=json.loads(response.stdout)
  known=known_denied_attempts(capture)
  target.with_suffix('.attempts.json').open('x').write(json.dumps({'known_prohibited_attempts':known,'absence_verdict':'unavailable-without-complete-admission'}))
  calls=admit(capture);controls=mutation_controls(capture)
  def strings(v):
   if isinstance(v,str):yield v
   elif isinstance(v,list):
    for x in v:yield from strings(x)
   elif isinstance(v,dict):
    for x in v.values():yield from strings(x)
  advertised='\n'.join(strings(capture['provider_request_bodies'][0]))
  if ('- gh:' in advertised)!=with_skill or '- github-actions-hardening:' not in advertised:raise Unavailable('native skill advertisement mismatch')
  if environment.profile=='denied':
   import copy
   partial=copy.deepcopy(capture);partial['frames']=[f for f in partial['frames'] if f.get('method')!='turn/completed']
   if not known or known_denied_attempts(partial)!=known:raise Unavailable('positive violation lost through collection gap')
  if environment.profile=='boundary' and not all('Permission denied' in c['observation'] and next(i for i in capture['state']['thread_read']['thread']['turns'][0]['items'] if i['id']==c['native_call_id'])['exitCode']==1 for c in calls[-4:]):raise Unavailable('private boundary attack was not denied')
  target.with_suffix('.identity.json').open('x').write(json.dumps({'initializer':environment.direct_identity,'with_skill':with_skill,'mutations_rejected':controls}))
  authored='\n'.join(i.get('text','') for i in capture['state']['thread_read']['thread']['turns'][0]['items'] if i['type']=='agentMessage')
  code="from pathlib import Path;import json;p=Path('/opt/gh-eval/native.json');p.open('x').write("+repr(json.dumps({'calls':calls,'expected_target_present':with_skill,'authored_text':authored,'identity':environment.direct_identity,'native_items':capture['state']['thread_read']['thread']['turns'][0]['items']}))+ ")"
  result=await environment.exec('python3 -I -c '+shlex.quote(code),user='root',timeout_sec=5)
  if result.return_code:raise Unavailable('verifier handoff failed')
  context.metadata=context.metadata or {};context.metadata['direct_evidence']={'sha256':hashlib.sha256(response.stdout.encode()).hexdigest(),'policy':'offline-direct-v1','production_admission':False,'synthetic_mutations_rejected':controls}
