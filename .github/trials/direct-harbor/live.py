"""Fixed direct-Harbor smoke pair. Raw agent work and logs are never published."""
import asyncio, hashlib, importlib.metadata, json, os, shlex, shutil, subprocess, sys, time
from pathlib import Path
import toml
import run as trial
TARGET = 'powershell-pester-6'
PROFILE=json.loads(Path(__file__).with_name('runtime-profile.json').read_text())
MODEL=PROFILE['model']
EFFORT=PROFILE['reasoning_effort']
VERSION=PROFILE['codex_version']

def config():
    value = toml.load(trial.ROOT / '.codex/config.toml')
    for server in value.get('mcp_servers', {}).values():
        server['enabled'] = False
    value.update(web_search='disabled', service_tier='default', model_reasoning_effort=EFFORT,
        forced_login_method='api', projects={'/workspace': {'trust_level': 'trusted'}},
        model_provider='trial_openai',
        model_providers={'trial_openai': {'name':'OpenAI', 'base_url':'https://api.openai.com/v1',
            'wire_api':'responses', 'requires_openai_auth':True, 'request_max_retries':0,
            'stream_max_retries':0, 'stream_idle_timeout_ms':60000,
            'supports_websockets':True,'supports_standalone_web_search':True,
            'http_headers':{'version':VERSION},
            'env_http_headers':{'OpenAI-Organization':'OPENAI_ORGANIZATION','OpenAI-Project':'OPENAI_PROJECT'}}},
        features={'rollout_budget': {'enabled':True, 'limit_tokens':30000, 'enforce_limit':True,
            'reminder_at_remaining_tokens':[5000], 'sampling_token_weight':5.0, 'prefill_token_weight':1.0}})
    return value

def expected_files(variant):
    values = trial.pilot.manifest(trial.ROOT / '.agents/skills')
    return {k:v for k,v in values.items() if variant=='current' or not k.startswith(TARGET+'/')}

async def runtime_check(environment, variant, output, expected_version=None):
    offline=os.environ.get('TRIAL_DIAGNOSTIC')=='1'
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
    if offline:
        program=program.replace("assert network['api.openai.com'] is not None, 'model endpoint unreachable'", "assert all(v is None for v in network.values()), 'offline diagnostic endpoint reachable'")
    result = await environment.exec(command='python3 -c '+shlex.quote(program), user='agent', timeout_sec=75)
    if result.return_code:
        raise RuntimeError('External preflight failed: '+(result.stderr or '')[-1200:])
    observed=json.loads(result.stdout)
    from pinned_codex import check_pin
    output.mkdir(parents=True,exist_ok=True)
    pin=await check_pin(environment,version=expected_version)
    trial.write(output/'installation.json',pin)
    assert pin['matched'], 'Pinned unprivileged Codex version check failed'
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
    assert (host['NetworkMode']=='none' if offline else host['NetworkMode'].startswith('container:')) and host.get('PidMode','')!='host'
    assert not any('unconfined' in s for s in host.get('SecurityOpt',[]))
    mounts=[m['Destination'] for m in inspected['Mounts']]
    assert all(p in ['/logs/agent','/logs/artifacts'] for p in mounts), 'unexpected host mount'
    observed.update(image=inspected['Image'],mount_destinations=mounts,resources={'cpus':2,'memory_mb':2048,'pids':256},variant=variant)
    trial.write(output/'boundary.json',observed)
    return observed

def prepare(root, diagnostic=False):
    from harbor.models.task.task import Task
    from harbor.models.trial.paths import TrialPaths
    from harbor.environments.docker.docker import DockerEnvironment
    assert not os.environ.get('OPENAI_API_KEY'), 'Credential-free preparation required'
    assert importlib.metadata.version('harbor')=='0.25.0'
    root.mkdir(parents=True,exist_ok=False)
    public=root/'public';public.mkdir()
    previous=json.loads((trial.ROOT/'.github/trials/direct-harbor/results/results.json').read_text())
    assert previous['grading_smoke_qualified'] and previous['agent_attempts']==4 and previous['api_spend_usd'] is None
    if not diagnostic:
        assert json.loads((trial.ROOT/'.github/trials/direct-harbor/launch.json').read_text())['paid_execution_enabled'] is True
    for variant in (('current',) if diagnostic else ('current','absent')):
        output=public/variant;output.mkdir()
        native,manifest=trial.stage(root/variant,variant)
        task=native/'pester-002';cfg=toml.load(task/'task.toml')
        if diagnostic:
            shutil.copyfile(Path(__file__).with_name('refusal_fixture.py'),task/'environment/refusal_fixture.py')
            shutil.copyfile(task/'instruction.md',task/'environment/task-instruction.txt')
            with (task/'environment/Dockerfile').open('a') as build:build.write('COPY refusal_fixture.py /opt/refusal_fixture.py\nCOPY task-instruction.txt /opt/trial-task-instruction.txt\n')
            cfg['artifacts'].append('/tmp/provider-observation.json')
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
        if diagnostic:compose.write_text(compose.read_text().replace('    user: "1000:1000"', '    user: "1000:1000"\n    network_mode: none'))
        trial.write(output/'preparation.json',{'stage':'building_pinned_image','paid_inference_permitted':False})
        for folder,tag in ([('environment','direct-harbor-agent:'+variant)] + ([] if diagnostic else [('tests','direct-harbor-verifier:live')])):
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
    trial.write(public/'preflight.json',{'passed':True,'commit':os.environ.get('GITHUB_SHA'),'paid_inference_permitted':not diagnostic,'network_mode':'none' if diagnostic else 'allowlist','remote_tools_disabled':True})

def usage_and_activation(native_dir):
    totals=None;activation=set();completion=False;calls=0;event_types={};tool_names={};outcomes=[];completion_shape=None
    for p in sorted((native_dir/'agent').glob('**/rollout-*.jsonl')):
        for line in p.read_text().splitlines():
            try:event=json.loads(line)
            except ValueError:continue
            payload=event.get('payload',{})
            event_type=payload.get('type')
            known={'function_call','custom_tool_call','function_call_output','custom_tool_call_output','exec_command_end','task_complete','turn_complete','token_count'}
            label=event_type if event_type in known else 'other'
            event_types[label]=event_types.get(label,0)+1
            if event.get('type')=='event_msg' and payload.get('type')=='token_count':
                value=(payload.get('info') or {}).get('total_token_usage')
                if value:totals={k:(value.get(k) if type(value.get(k)) is int and value[k]>=0 else None) for k in ('input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens','cache_write_input_tokens','total_tokens')}
            if event.get('type')=='response_item' and payload.get('type') in ('function_call','custom_tool_call'):
                calls+=1
                name=payload.get('name')
                safe_name=name if name in ('exec_command','write_stdin','apply_patch','functions.exec','shell','shell_command','read_file','update_plan') else 'other'
                tool_names[safe_name]=tool_names.get(safe_name,0)+1
                arguments=payload.get('arguments' if payload['type']=='function_call' else 'input','')
                for name in expected_files('current'):
                    if name.startswith(TARGET+'/') and name in str(arguments):activation.add(name)
            if event.get('type')=='event_msg' and event_type=='exec_command_end':
                outcomes.append({'exit_code':payload.get('exit_code') if type(payload.get('exit_code')) is int else None,'output_retained':False})
            if event.get('type')=='event_msg' and event_type in ('task_complete','turn_complete'):
                completion=True
                message=payload.get('last_agent_message')
                completion_shape={'message_present':isinstance(message,str),'message_characters':len(message) if isinstance(message,str) else None,'content_retained':False}
    return {'total_usage':totals,'skill_file_access_attempts':sorted(activation),'tool_calls':calls,'completion_event':completion,'event_type_counts':event_types,'tool_name_counts':tool_names,'exec_outcomes':outcomes[:100],'completion_shape':completion_shape,'evidence_limit':'File-access attempts do not prove successful reads, instruction following or correctness.'}

def can_schedule(previous, accept_unknown_cost=False):
    if previous.get('execution_completed',previous.get('usage_complete')) is not True:return False
    cost=previous.get('usage_estimate_usd')
    return accept_unknown_cost if cost is None else cost+1.32<4

def diagnostic(root, mode):
    from harbor.models.task.task import Task
    from diagnostics import SENTINEL, sanitized_exception, sanitize
    assert not any(os.environ.get(k) for k in ('OPENAI_API_KEY','CODEX_API_KEY','CODEX_AUTH_JSON_PATH','CODEX_FORCE_AUTH_JSON')), 'No real authentication permitted'
    assert os.environ.get('TRIAL_DIAGNOSTIC')=='1'
    assert mode in ('historical','http','idle')
    output=root/'public'/mode;output.mkdir(parents=True,exist_ok=False)
    task=Path(json.loads((root/'current-task.json').read_text())['path'])
    before=Task(task).checksum
    settings=(json.loads((trial.ROOT/'.github/trials/direct-harbor/results/live-evidence.json').read_text())['effective_config_current'] if mode=='historical' else config())
    cfg={'job_name':mode,'jobs_dir':str(root/'jobs'),'n_attempts':1,'n_concurrent_trials':1,
        'retry':{'max_retries':0},'environment':{'type':'docker','delete':True},'verifier':{'disable':True},
        'agents':[{'import_path':'pinned_codex:PinnedCodex','model_name':MODEL,'extra_allowed_hosts':['api.openai.com'],
            'kwargs':{'version':VERSION,'reasoning_effort':EFFORT,'web_search':'disabled','config':settings}}],
        'tasks':[{'path':str(task)}]}
    if mode!='historical':cfg['agents'][0]['base_url']='http://127.0.0.1:8765/v1'
    trial.write(root/(mode+'-job.json'),cfg)
    environment=os.environ.copy();environment.update(PYTHONPATH=str(Path(__file__).parent),
        TRIAL_VARIANT='current',TRIAL_PUBLIC_DIR=str(output),OPENAI_API_KEY=SENTINEL,TRIAL_PROVIDER_PROBE=mode)
    record={'mode':mode,'kind':'credential_free_launch_diagnostic','paid_attempt':False,'measured_task_outcome':False,
        'result_extraction_succeeded':False,'launch_succeeded':False,'rollout_present':False,
        'commit':os.environ.get('GITHUB_SHA')}
    started=time.monotonic()
    try:
        with (root/(mode+'-private-native.log')).open('w') as log:
            completed=subprocess.run(['harbor','run','--config',str(root/(mode+'-job.json'))],env=environment,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        record['harbor_returncode']=completed.returncode
        row=next(r for r in trial.project(root/'jobs',{}) if r['native_result'].startswith('jobs/'+mode+'/'))
        row['exceptions']=[sanitized_exception(e) for e in row['exceptions']]
        record['native_result']=row
        record['rollout_present']=bool(list((root/'jobs'/mode).glob('**/rollout-*.jsonl')))
        observations=list((root/'jobs'/mode).glob('**/provider-observation.json'))
        if observations:record['provider_observation']=json.loads(observations[0].read_text())
        assert Task(task).checksum==before, 'Frozen task changed'
        record['result_extraction_succeeded']=True
        record['launch_succeeded']=row['failure_cause'] is None and not row['exceptions']
    except Exception as exc:
        record['extraction_exception']={'type':type(exc).__name__,'message':sanitize(str(exc))}
    finally:
        record['duration_seconds']=round(time.monotonic()-started,3)
        trial.write(output/'diagnostic.json',record)
        print(json.dumps(record),flush=True)
    return 0 if record['launch_succeeded'] else 1

def live_attempt(root,variant):
    from harbor.models.task.task import Task
    from diagnostics import sanitized_exception, sanitize
    launch=json.loads((trial.ROOT/'.github/trials/direct-harbor/launch.json').read_text())
    raise RuntimeError('Paid scheduling disabled for this credential-free handoff pass')
    assert launch['paid_execution_enabled'] is True and launch['paid_attempts_used']==2
    assert launch['accept_unknown_cost_for_testing'] is True
    assert not os.environ.get('TRIAL_DIAGNOSTIC') and not os.environ.get('TRIAL_PROVIDER_PROBE')
    assert os.environ.get('OPENAI_API_KEY') and variant in ('current','absent')
    assert json.loads((root/'public/preflight.json').read_text())['passed']
    output=root/'public'/variant
    assert not (output/'attempt.json').exists(), 'No implicit retry'
    if variant=='absent':
        first=json.loads((root/'public/current/attempt.json').read_text())
        assert first['result_extraction_succeeded'] and can_schedule(first,accept_unknown_cost=launch['accept_unknown_cost_for_testing']), 'Execution incomplete or operational reserve reached'
    task=Path(json.loads((root/(variant+'-task.json')).read_text())['path'])
    manifest=json.loads((output/'manifest.json').read_text());assert Task(task).checksum==manifest['task_checksum']
    record={'attempt':3 if variant=='current' else 4,'variant':variant,'reserved':True,'rollout_present':False,
            'result_extraction_succeeded':False,'execution_completed':False,'usage_estimate_usd':None,
            'projection':[],'commit':os.environ.get('GITHUB_SHA')}
    trial.write(output/'attempt.json',record)
    cfg={'job_name':variant,'jobs_dir':str(root/'jobs'),'n_attempts':1,'n_concurrent_trials':1,
        'retry':{'max_retries':0},'environment':{'type':'docker','delete':True},
        'agents':[{'import_path':'pinned_codex:PinnedCodex','model_name':MODEL,'extra_allowed_hosts':['api.openai.com'],
          'kwargs':{'version':VERSION,'reasoning_effort':EFFORT,'web_search':'disabled','config':config()}}],
        'tasks':[{'path':str(task)}]}
    trial.write(root/(variant+'-job.json'),cfg)
    env=os.environ.copy();env.update(PYTHONPATH=str(Path(__file__).parent),TRIAL_VARIANT=variant,TRIAL_PUBLIC_DIR=str(output))
    started=time.monotonic()
    try:
        with (root/(variant+'-private.log')).open('w') as log:
            completed=subprocess.run(['harbor','run','--config',str(root/(variant+'-job.json'))],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1000)
        record['harbor_returncode']=completed.returncode
        row=next(r for r in trial.project(root/'jobs',{}) if r['native_result'].startswith('jobs/'+variant+'/'))
        native=root/Path(row['native_result']).parent
        row['exceptions']=[sanitized_exception(e) for e in row['exceptions']]
        row.pop('expected',None);row.pop('matches',None);record['projection']=[row]
        from handoff import collect
        details=usage_and_activation(native);record['usage_and_activation']=details
        record['rollout_present']=bool(list((native/'agent').glob('**/rollout-*.jsonl')))
        record['execution_completed']=details['completion_event'] and row['failure_cause'] is None
        record['handoff']=collect(native,row,completed=record['execution_completed'])
        record['usage_complete']=record['execution_completed'] and details['total_usage'] is not None
        if details['total_usage']:
            usage=details['total_usage'];record['usage_estimate_usd']=trial.conservative_usage_cost({'input_including_cache':usage.get('input_tokens'),'cached_input':usage.get('cached_input_tokens'),'output':usage.get('output_tokens')},input_rate=PROFILE['pricing']['conservative_all_input_per_million'],output_rate=PROFILE['pricing']['conservative_output_per_million'])
        artifact=native/'artifacts/workspace/output/Subject.Tests.ps1'
        if artifact.is_file():record['submitted_artifact']={'bytes':artifact.stat().st_size,'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest()}
        assert Task(task).checksum==manifest['task_checksum'], 'Frozen task changed'
        remaining=subprocess.check_output(['docker','ps','--all','--filter','label=com.docker.compose.service=main','--filter','ancestor=direct-harbor-agent:'+variant,'--quiet'],text=True).strip()
        record['agent_container_removed']=not remaining
        assert not remaining, 'Agent container disposal incomplete'
        record['result_extraction_succeeded']=True
    except Exception as exc:
        record['extraction_exception']={'type':type(exc).__name__,'message':sanitize(str(exc),(os.environ.get('OPENAI_API_KEY',''),))}
    finally:
        record['duration_seconds']=round(time.monotonic()-started,3);trial.write(output/'attempt.json',record)
        print(json.dumps({k:record.get(k) for k in ('attempt','variant','rollout_present','execution_completed','result_extraction_succeeded','usage_estimate_usd')}),flush=True)
    return 0 if record['result_extraction_succeeded'] and record['execution_completed'] else 1

if __name__=='__main__':
    mode=sys.argv[1];root=Path(sys.argv[2]).resolve()
    if mode=='diagnostic-prepare':
        try:prepare(root,diagnostic=True)
        except Exception as exc:
            from diagnostics import sanitize
            trial.write(root/'public/preparation-failure.json',{'type':type(exc).__name__,'message':sanitize(str(exc)),'paid_inference_permitted':False})
            raise
    elif mode=='diagnostic':raise SystemExit(diagnostic(root,sys.argv[3]))
    elif mode=='prepare':prepare(root)
    elif mode in ('current','absent'):raise SystemExit(live_attempt(root,mode))
    else:raise ValueError('Paid execution disabled; only credential-free diagnostics are allowed')
