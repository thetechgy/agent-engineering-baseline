"""Real Inspect sandbox lifecycle and stock SWE capture with a deterministic model."""
import ast,asyncio,json,pathlib,sys
from inspect_ai import Task,eval
from inspect_ai.dataset import Sample
from inspect_ai.solver import solver,chain
from inspect_ai.agent import as_solver
from inspect_ai.model import get_model,ModelOutput,ChatCompletionChoice,ChatMessageAssistant
from inspect_ai.tool import ToolCall
from inspect_ai.util import sandbox,store
from inspect_swe import codex_cli
root=pathlib.Path(sys.argv[1]);base=pathlib.Path(__file__).parent
mode=sys.argv[2] if len(sys.argv)>2 else 'normal'
script=next(ast.literal_eval(n.value) for n in ast.parse((base/'native_probe.py').read_text()).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SCRIPT' for t in n.targets))
@solver
def initialize():
 async def run(state,generate):
  s=sandbox()
  program='import json,os,pathlib; s=pathlib.Path("/proc/self/status").read_text(); print(json.dumps({"uid":os.geteuid(),"status":{k:next(x.split(":",1)[1].strip() for x in s.splitlines() if x.startswith(k+":")) for k in ["CapEff","Seccomp","NoNewPrivs"]},"interfaces":sorted(p.name for p in pathlib.Path("/sys/class/net").iterdir())}))'
  security=json.loads((await s.exec(['python','-c',program],user='agent',timeout=5,timeout_retry=False)).stdout)
  assert security=={'uid':1000,'status':{'CapEff':'0000000000000000','Seccomp':'2','NoNewPrivs':'1'},'interfaces':['lo']},security
  store().set('runtime_security',security)
  code=(base/'broker.py').read_bytes().hex()
  provision="import pathlib,os; p=pathlib.Path('/opt/operator-broker.py'); f=p.open('xb'); f.write(bytes.fromhex('"+code+"')); f.close(); os.chmod(p,0o644); assert p.stat().st_uid==0"
  assert (await s.exec(['python','-c',provision],user='root',timeout=5,timeout_retry=False)).success
  absent=await s.exec(['python','/opt/operator-broker.py','ready'],user='agent',timeout=5,timeout_retry=False)
  assert not absent.success,'missing broker passed readiness'
  if mode=='failure':assert (await s.exec(['mkdir','/opt/private'],user='root',timeout=5,timeout_retry=False)).success
  r=await s.exec(['python','/opt/operator-broker.py','init'],user='root',timeout=10,timeout_retry=False)
  if not r.success:raise RuntimeError(f'required initializer failed (exit {r.returncode})')
  ident=json.loads(r.stdout)['identity'];store().set('initializer_identity',ident)
  for cmd in [['cat','/opt/private/identity'],['cat','/opt/private/audit'],['python','/opt/broker.py','init'],['rm','/run/poc/broker.sock']]:
   assert not (await s.exec(cmd,user='agent',timeout=5,timeout_retry=False)).success
  assert json.loads((await s.exec(['python','/opt/broker.py','ready'],user='agent',timeout=5,timeout_retry=False)).stdout)['identity']==ident
  assert (await s.exec(['mkdir','-p','/home/agent/.codex'],user='agent',timeout_retry=False)).success
  if mode=='cancel':
   (root/'cancel-ready').write_text(ident)
   await asyncio.sleep(60)
  return state
 return run
@solver
def verify():
 async def run(state,generate):
  r=await sandbox().exec(['cat','/workspace/actual.txt'],user='agent',timeout=5,timeout_retry=False)
  assert r.success and r.stdout=='actual-modification\n'
  store().set('actual_patch_verified',True);return state
 return run
outputs=[ModelOutput(model='mockllm/model',choices=[ChatCompletionChoice(message=ChatMessageAssistant(content='',tool_calls=[ToolCall(id='script-1',function='exec',type='custom',arguments={'input':script})]))]),ModelOutput.from_content(model='mockllm/model',content='fixture finished')]
model=get_model('mockllm/model',custom_outputs=outputs)
compose=root/'inspect-compose.yaml';compose.write_text('services:\n  default:\n    image: architecture-poc:164\n    command: ["sleep", "infinity"]\n    user: agent\n    network_mode: none\n    cap_drop: [ALL]\n    security_opt: ["no-new-privileges:true"]\n    pids_limit: 128\n    mem_limit: 1g\n    cpus: 2\n    environment:\n      PATH: /opt/codex/bin:/usr/local/bin:/usr/bin:/bin\n')
agent=codex_cli(version='sandbox',model_config='gpt-5.6-sol',web_search='disabled',goals=False,auto_review=False,attempts=1,user='agent',cwd='/workspace',home_dir='/home/agent/.codex',network_access=False)
task=Task(dataset=[Sample(id='capture',input='Execute the fixed fixture script.')],solver=chain(initialize(),as_solver(agent),verify()),sandbox=('docker',str(compose)),name='architecture-inspect-'+mode,message_limit=40,time_limit=120)
logs=eval(task,model=model,log_dir=str(root/'evidence/inspect'),max_samples=1,max_tasks=1,max_subprocesses=2,retry_on_error=0)
if mode=='failure':
 assert logs[0].samples[0].error is not None
 assert 'required initializer failed (exit 1)' in logs[0].samples[0].error.message
 assert not logs[0].samples[0].store.get('actual_patch_verified')
 assert not any(e.event=='model' for e in logs[0].samples[0].events),'failed initialization reached agent'
 sys.exit(0)
assert logs[0].status=='success',str(logs[0].error)
assert logs[0].samples[0].store.get('actual_patch_verified') is True, 'sample did not reach verification'
assert logs[0].samples[0].error is None
print('Inspect stock Codex capture gate completed')
