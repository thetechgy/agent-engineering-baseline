"""Fixed direct-Harbor smoke pair. Raw agent work and logs are never published."""
import asyncio, hashlib, importlib.metadata, json, os, shlex, shutil, subprocess, sys, time
from pathlib import Path
import toml
import run as trial
TARGET = 'powershell-pester-6'
MODEL = 'gpt-5.6-sol'

def config():
    value = toml.load(trial.ROOT / '.codex/config.toml')
    for server in value.get('mcp_servers', {}).values():
        server['enabled'] = False
    value.update(web_search='disabled', service_tier='default', model_reasoning_effort='medium',
        forced_login_method='api', projects={'/workspace': {'trust_level': 'trusted'}},
        model_providers={'openai': {'name':'OpenAI', 'base_url':'https://api.openai.com/v1',
            'wire_api':'responses', 'requires_openai_auth':True, 'request_max_retries':0,
            'stream_max_retries':0, 'stream_idle_timeout_ms':60000}},
        features={'rollout_budget': {'enabled':True, 'limit_tokens':30000,
            'reminder_at_remaining_tokens':[5000], 'sampling_token_weight':5.0, 'prefill_token_weight':1.0}})
    return value

def expected_files(variant):
    values = trial.pilot.manifest(trial.ROOT / '.agents/skills')
    return {k:v for k,v in values.items() if variant=='current' or not k.startswith(TARGET+'/')}

async def runtime_check(environment, variant, output):
    program = r'''
import hashlib,json,os,pathlib,urllib.request,urllib.error
P=pathlib.Path
status=P('/proc/self/status').read_text()
assert os.getuid()==os.getgid()==1000, 'agent uid/gid'
assert 'CapEff:\t0000000000000000' in status and 'NoNewPrivs:\t1' in status and 'Seccomp:\t2' in status, 'process protections'
for p in ['/tests','/solution','/workspace/.apm','/workspace/.git','/workspace/.github','/var/run/docker.sock','/run/docker.sock','/home/runner/work']:
 assert not P(p).exists(), 'protected input or host path exposed: '+p
assert not any(k in os.environ for k in ['GITHUB_TOKEN','GH_TOKEN','ACTIONS_RUNTIME_TOKEN','AWS_ACCESS_KEY_ID']), 'unrelated credential name'
P('/workspace/output/preflight').write_text('ok'); P('/workspace/output/preflight').unlink()
def manifest(root):
 return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in P(root).rglob('*') if p.is_file()}
copies=[]
for root,dirs,files in os.walk('/',followlinks=False):
 dirs[:]=[d for d in dirs if str(P(root)/d) not in ['/proc','/sys','/dev','/logs']]
 if P(root).name=='powershell-pester-6':copies.append(root)
assert not list(P('/installed-agent/codex-home').glob('sessions/**/*')), 'reused sessions'
assert not P('/installed-agent/codex-home/auth.json').exists(), 'reused authentication'
network={}
for host in ['api.openai.com','github.com','raw.githubusercontent.com','learn.microsoft.com','169.254.169.254']:
 try:
  with urllib.request.urlopen('https://'+host+'/',timeout=8) as r:code=r.status
 except urllib.error.HTTPError as e:code=e.code
 except (OSError,urllib.error.URLError,TimeoutError):code=None
 network[host]=code
assert network['api.openai.com'] is not None, 'model endpoint unreachable'
assert all(v is None for k,v in network.items() if k!='api.openai.com'), 'unapproved HTTPS endpoint reachable'
print(json.dumps({'skills':manifest('/workspace/.agents/skills'),'instructions_sha256':hashlib.sha256(P('/workspace/AGENTS.md').read_bytes()).hexdigest(),'codex_files':manifest('/workspace/.codex'),'target_copies':copies,'network':network,'uid':os.getuid(),'capabilities':0,'no_new_privileges':True,'seccomp_filter':True,'workspace_writable':True,'fresh_session':True}))
'''
    result = await environment.exec(command='python3 -c '+shlex.quote(program), user='agent', timeout_sec=75)
    if result.return_code:
        raise RuntimeError('External preflight failed: '+(result.stderr or '')[-1200:])
    observed=json.loads(result.stdout)
    assert observed['skills']==expected_files(variant), 'Deployed skill manifest mismatch'
    assert observed['target_copies']==(['/workspace/.agents/skills/'+TARGET] if variant=='current' else []), 'Target copies mismatch'
    assert observed['codex_files']==trial.pilot.manifest(trial.ROOT/'.codex'), 'APM config mismatch'
    assert observed['instructions_sha256']==hashlib.sha256((trial.ROOT/'AGENTS.md').read_bytes()).hexdigest()
    ids=subprocess.check_output(['docker','ps','--filter','label=com.docker.compose.service=main',
        '--filter','ancestor='+environment.task_env_config.docker_image,'--quiet'],text=True).split()
    assert len(ids)==1, 'Expected one main service for this pinned agent image'
    inspected=json.loads(subprocess.check_output(['docker','inspect',ids[0]],text=True))[0]
    host=inspected['HostConfig']
    fields={k:host.get(k) for k in ('Privileged','CapDrop','CapAdd','PidsLimit','Memory','NanoCpus','NetworkMode','PidMode','SecurityOpt')}
    trial.write(output/'container-policy.json',fields)
    assert not host['Privileged'] and 'ALL' in [v.upper() for v in host['CapDrop']] and not host.get('CapAdd'), 'Agent capability policy mismatch'
    assert host['PidsLimit']==256 and host['Memory']==2147483648 and host['NanoCpus']==2000000000
    assert host['NetworkMode'].startswith('container:') and host.get('PidMode','')!='host'
    assert not any('unconfined' in s for s in host.get('SecurityOpt',[]))
    mounts=[m['Destination'] for m in inspected['Mounts']]
    assert all(p in ['/logs/agent','/logs/artifacts'] for p in mounts), 'unexpected host mount'
    observed.update(image=inspected['Image'],mount_destinations=mounts,resources={'cpus':2,'memory_mb':2048,'pids':256},variant=variant)
    trial.write(output/'boundary.json',observed)
    return observed

def prepare(root):
    from harbor.models.task.task import Task
    from harbor.models.trial.paths import TrialPaths
    from harbor.environments.docker.docker import DockerEnvironment
    assert not os.environ.get('OPENAI_API_KEY'), 'Credential-free preparation required'
    assert importlib.metadata.version('harbor')=='0.25.0'
    root.mkdir(parents=True,exist_ok=False)
    public=root/'public';public.mkdir()
    previous=json.loads((trial.ROOT/'.github/trials/direct-harbor/results/results.json').read_text())
    assert previous['grading_smoke_qualified'] and previous['agent_attempts']==0 and previous['api_spend_usd']==0
    for variant in ('current','absent'):
        output=public/variant;output.mkdir()
        native,manifest=trial.stage(root/variant,variant)
        task=native/'pester-002';cfg=toml.load(task/'task.toml')
        cfg['agent']['timeout_sec']=600
        cfg['environment'].update(network_mode='allowlist',allowed_hosts=['api.openai.com'])
        compose=task/'environment/docker-compose.yaml'
        compose.write_text(compose.read_text()+'''    user: "1000:1000"
  harbor-docker-egress-control-sidecar:
    cap_drop: [ALL]
    security_opt: [no-new-privileges:true]
    pids_limit: 128
    mem_limit: 256m
    cpus: 0.5
''')
        for folder,tag in [('environment','direct-harbor-agent:'+variant),('tests','direct-harbor-verifier:live')]:
            subprocess.run(['docker','build','--progress=plain','-t',tag,str(task/folder)],check=True,timeout=600)
            (cfg['environment'] if folder=='environment' else cfg['verifier']['environment'])['docker_image']=tag
        (task/'task.toml').write_text(toml.dumps(cfg))
        manifest.update(task_checksum=Task(task).checksum,effective_skills=expected_files(variant),effective_codex_config=config())
        trial.write(output/'manifest.json',manifest)
        async def check():
            t=Task(task)
            environment=DockerEnvironment(environment_dir=t.paths.environment_dir,environment_name='pester-002',
                session_id='live-preflight-'+variant,trial_paths=TrialPaths(root/('preflight-'+variant)),
                task_env_config=t.config.environment,network_policy=t.config.environment.resolve_baseline())
            try:
                await environment.start(force_build=False)
                await runtime_check(environment,variant,output)
            finally:
                await environment.stop(delete=True)
        asyncio.run(check())
        trial.write(root/(variant+'-task.json'),{'path':str(task)})
        print('External preflight passed: '+variant,flush=True)
    assert {k:v for k,v in expected_files('current').items() if not k.startswith(TARGET+'/')}==expected_files('absent')
    trial.write(public/'preflight.json',{'passed':True,'commit':os.environ.get('GITHUB_SHA'),'api_calls':0,'network_allowlist':['api.openai.com'],'remote_tools_disabled':True})

def usage_and_activation(native_dir):
    totals=None;activation=set();completion=False;calls=0
    for p in sorted((native_dir/'agent').glob('**/rollout-*.jsonl')):
        for line in p.read_text().splitlines():
            try:event=json.loads(line)
            except ValueError:continue
            payload=event.get('payload',{})
            if event.get('type')=='event_msg' and payload.get('type')=='token_count':
                value=(payload.get('info') or {}).get('total_token_usage')
                if value:totals={k:(value.get(k) if type(value.get(k)) is int and value[k]>=0 else None) for k in ('input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens','cache_write_input_tokens','total_tokens')}
            if event.get('type')=='response_item' and payload.get('type')=='function_call':
                calls+=1
                for name in expected_files('current'):
                    if name.startswith(TARGET+'/') and name in str(payload.get('arguments','')):activation.add(name)
            if event.get('type')=='event_msg' and payload.get('type') in ('task_complete','turn_complete'):completion=True
    return {'total_usage':totals,'skill_file_access_attempts':sorted(activation),'tool_calls':calls,'completion_event':completion}

def can_schedule(previous):
    cost=previous.get('usage_estimate_usd')
    return previous.get('usage_complete') is True and cost is not None and cost+1.32<4

def attempt(root,variant):
    from harbor.models.task.task import Task
    public=root/'public';output=public/variant
    assert os.environ.get('OPENAI_API_KEY'), 'Existing protected credential required'
    assert json.loads((public/'preflight.json').read_text())['passed']
    launch=json.loads((trial.ROOT/'.github/trials/direct-harbor/launch.json').read_text())
    assert launch['paid_attempts_used']==0 and launch['recovery_live_attempt_limit']==4
    if variant=='absent':
        first=json.loads((public/'current/attempt.json').read_text())
        assert can_schedule(first), 'Incomplete usage or scheduling reserve reached'
    number=1 if variant=='current' else 2
    assert number<=4 and number<=36
    assert not (output/'attempt.json').exists(), 'No implicit retry'
    task=Path(json.loads((root/(variant+'-task.json')).read_text())['path'])
    manifest=json.loads((output/'manifest.json').read_text())
    assert Task(task).checksum==manifest['task_checksum']
    record={'attempt':number,'variant':variant,'reserved':True,'codex_executed':False,'usage_estimate_usd':None,'projection':[],'commit':os.environ.get('GITHUB_SHA')}
    trial.write(output/'attempt.json',record)
    cfg={'job_name':variant,'jobs_dir':str(root/'jobs'),'n_attempts':1,'n_concurrent_trials':1,
        'retry':{'max_retries':0},'environment':{'type':'docker','delete':True},
        'agents':[{'import_path':'pinned_codex:PinnedCodex','model_name':MODEL,'extra_allowed_hosts':['api.openai.com'],
            'kwargs':{'version':'0.155.1','reasoning_effort':'medium','web_search':'disabled','config':config()}}],
        'tasks':[{'path':str(task)}]}
    trial.write(root/(variant+'-job.json'),cfg)
    environment=os.environ.copy();environment.update(PYTHONPATH=str(Path(__file__).parent),TRIAL_VARIANT=variant,TRIAL_PUBLIC_DIR=str(output))
    started=time.monotonic()
    try:
        with (root/(variant+'-private.log')).open('w') as log:
            completed=subprocess.run(['harbor','run','--config',str(root/(variant+'-job.json'))],env=environment,stdout=log,stderr=subprocess.STDOUT,timeout=1000)
        record['harbor_returncode']=completed.returncode
        row=next(r for r in trial.project(root/'jobs',{}) if r['native_result'].startswith('jobs/'+variant+'/'))
        native_dir=root/Path(row['native_result']).parent
        details=usage_and_activation(native_dir)
        record['codex_executed']=any((native_dir/'agent').glob('**/rollout-*.jsonl'))
        row['exceptions']=[{k:e[k] for k in ('exception_type','occurred_at')} for e in row['exceptions']]
        row.pop('expected',None);row.pop('matches',None)
        record['projection']=[row];record['usage_and_activation']=details
        record['usage_complete']=details['completion_event'] and row['failure_cause'] is None
        totals=details['total_usage']
        if totals:
            tokens={'input_including_cache':totals.get('input_tokens'),'cached_input':totals.get('cached_input_tokens'),'output':totals.get('output_tokens')}
            record['usage_estimate_usd']=trial.conservative_usage_cost(tokens)
        artifact=native_dir/'artifacts/workspace/output/Subject.Tests.ps1'
        if artifact.is_file():record['submitted_artifact']={'bytes':artifact.stat().st_size,'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest()}
        assert Task(task).checksum==manifest['task_checksum'], 'Frozen input mutation'
        record['integration_valid']=True
    except Exception as exc:
        record['integration_valid']=False;record['integration_failure_type']=type(exc).__name__
    finally:
        record['duration_seconds']=round(time.monotonic()-started,2)
        trial.write(output/'attempt.json',record)
        print(json.dumps({k:record.get(k) for k in ('attempt','variant','codex_executed','usage_estimate_usd','integration_valid')}),flush=True)
    return 0 if record.get('integration_valid') and record.get('usage_complete') and record['usage_estimate_usd'] is not None else 1

if __name__=='__main__':
    mode=sys.argv[1];root=Path(sys.argv[2]).resolve()
    if mode=='prepare':
        try:prepare(root)
        except Exception as exc:
            trial.write(root/'public/preflight.json',{'passed':False,'failure_type':type(exc).__name__,'message':str(exc)[-1600:],'api_calls':0})
            raise
    elif mode in ('current','absent'):raise SystemExit(attempt(root,mode))
    else:raise ValueError('Unsupported fixed phase')

