"""Fixed smoke pair; only the authorized declared deliverable may be published."""
import asyncio, hashlib, importlib.metadata, json, os, shlex, shutil, subprocess, sys, time, uuid
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
        features={'rollout_budget':False})
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

def validate_prior_results(previous, allocation=None):
    if previous.get('grading_smoke_qualified') is not True:
        raise RuntimeError('Independent grading controls are not qualified')
    if allocation is not None and previous.get('agent_attempts') != allocation['prior_campaign_attempts']:
        raise RuntimeError('Report and authorized allocation disagree on prior campaign attempts')


def stage_admission_checks(task):
    shutil.copyfile(Path(__file__).with_name('admission_checks.py'), task/'tests/admission_checks.py')
    shutil.copytree(trial.ROOT/trial.pilot.OVERLAY/'support/qualification/pester-002', task/'tests/admission-fixtures')
    with (task/'tests/Dockerfile').open('a') as build:
        build.write('COPY admission_checks.py /tests/admission_checks.py\nCOPY admission-fixtures/ /tests/admission-fixtures/\n')


def admission_preflight(image, destination):
    """Small real-parser controls in the built verifier, before any credentialed step."""
    assert not any(os.environ.get(k) for k in ('OPENAI_API_KEY','CODEX_API_KEY','CODEX_AUTH_JSON_PATH','CODEX_FORCE_AUTH_JSON')), 'Credential-free admission preflight required'
    name = 'pester-admission-' + uuid.uuid4().hex
    result = {'kind': 'admission_parser_checks', 'passed': False, 'code': 'probe_incomplete',
              'inference': False, 'candidate_execution': False}
    try:
        process = subprocess.run([
            'docker', 'run', '--rm', '--name', name, '--network', 'none',
            '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=128m',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
            '--cpus', '2', '--memory', '2g', '--pids-limit', '256',
            '--entrypoint', 'python3', image, '-I', '/tests/admission_checks.py',
            '--runner', '/tests/Runner.ps1', '--profile', '/tests/case/profile.json',
            '--fixtures', '/tests/admission-fixtures'], capture_output=True, timeout=120)
        observed = json.loads(process.stdout) if len(process.stdout) <= 32768 else None
        if (type(observed) is not dict or observed.get('kind') != 'admission_parser_checks'
                or observed.get('inference') is not False or observed.get('candidate_execution') is not False
                or type(observed.get('passed')) is not bool
                or type(observed.get('controls')) is not list or len(observed['controls']) != 4
                or any(type(c) is not dict for c in observed['controls'])
                or [c.get('control') for c in observed.get('controls',[]) if isinstance(c,dict)] !=
                    ['classic','weak','unsupported_command','unexpected_runner_error']
                or any(type(c.get('passed')) is not bool for c in observed['controls'])
                or observed['passed'] != all(c['passed'] for c in observed['controls'])):
            raise ValueError('probe protocol')
        result = observed
        if process.returncode or result.get('passed') is not True:
            result = dict(result, passed=False, code='probe_failed')
    except (OSError, ValueError, subprocess.TimeoutExpired):
        result = dict(result, passed=False, code='probe_execution')
    finally:
        # Named disposable container only; no host mounts or API credentials.
        try:
            removed = subprocess.run(['docker', 'rm', '--force', name], capture_output=True, timeout=20)
            if removed.returncode and b'No such container' not in removed.stderr:
                result = dict(result, passed=False, code='probe_cleanup')
        except (OSError, subprocess.TimeoutExpired):
            result = dict(result, passed=False, code='probe_cleanup')
        trial.write(destination, result)
    if result.get('passed') is not True:
        raise RuntimeError('Credential-free admission preflight failed; inspect admission-preflight.json')
    return result


def check_task(task, variant, output, root, diagnostic=False):
    from harbor.models.task.task import Task
    from harbor.models.trial.paths import TrialPaths
    from harbor.environments.docker.docker import DockerEnvironment
    async def check():
        t=Task(task)
        environment=DockerEnvironment(environment_dir=t.paths.environment_dir,environment_name='pester-002',
            session_id='live-preflight-'+variant,trial_paths=TrialPaths(root/('preflight-'+variant)),
            task_env_config=t.config.environment,network_policy=t.config.environment.resolve_baseline())
        try:
            await environment.start(force_build=False)
            await runtime_check(environment,variant,output)
            if not diagnostic:
                from pinned_codex import inspect_budget_feature
                uploaded=await environment.exec(command='umask 077; printf %s '+shlex.quote(toml.dumps(config()))+' > /installed-agent/codex-home/config.toml',user='agent',timeout_sec=30)
                assert uploaded.return_code==0
                trial.write(output/'budget-preflight.json',await inspect_budget_feature(environment))
        finally:
            await environment.stop(delete=True)
    asyncio.run(check())

def prepare(root, diagnostic=False, infrastructure=False, retained=None):
    from harbor.models.task.task import Task
    assert not os.environ.get('OPENAI_API_KEY'), 'Credential-free preparation required'
    assert importlib.metadata.version('harbor')=='0.25.0'
    root.mkdir(parents=True,exist_ok=False)
    public=root/'public';public.mkdir()
    previous=json.loads((trial.ROOT/'.github/trials/direct-harbor/results/results.json').read_text())
    allocation = None
    if infrastructure:
        from handoff import no_credentials
        no_credentials()
    if not diagnostic and not infrastructure:
        from allocation import active
        allocation = active()
        retention_proof=json.loads(Path(__file__).with_name("results").joinpath("retention-validation.json").read_text())
        assert retention_proof["publication_verified"] and retention_proof["local_download_verified"]
        assert retention_proof["paid_attempt"] is False and retention_proof["inference"] is False
    validate_prior_results(previous, allocation)
    from prepared import snapshot_module
    snapshot = Path(os.environ['TRIAL_SNAPSHOT_BUNDLE'])
    snapshot_module().validate_bundle(snapshot)
    trial.write(public/'snapshot-bundle.json', {'manifest_sha256': hashlib.sha256((snapshot/'manifest.json').read_bytes()).hexdigest(), 'manifest': snapshot_module().validate_bundle(snapshot), 'index_downloads': 0})
    launch = json.loads(Path(__file__).with_name('launch.json').read_text())
    admission_diagnostics = launch.get('admission_diagnostics', False)
    for variant in (('current',) if diagnostic else ('current','absent')):
        output=public/variant;output.mkdir()
        native,manifest=trial.stage(root/variant,variant,admission_diagnostics=admission_diagnostics)
        task=native/'pester-002';cfg=toml.load(task/'task.toml')
        if not diagnostic:
            stage_admission_checks(task)
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
            if variant=='absent' and folder=='tests':
                first_task=Path(json.loads((root/'current-task.json').read_text())['path'])
                assert trial.pilot.manifest(first_task/'tests')==trial.pilot.manifest(task/'tests'), 'Verifier contexts differ'
            elif retained is not None:
                from prepared import refresh_image
                refresh_image(task,variant,folder,tag,retained,root)
            else:
                snapshot_copy=task/folder/'build/snapshot'
                shutil.copytree(snapshot,snapshot_copy)
                try:
                    subprocess.run(['docker','build','--progress=plain','-t',tag,str(task/folder)],check=True,timeout=600)
                finally:
                    shutil.rmtree(snapshot_copy)
            (cfg['environment'] if folder=='environment' else cfg['verifier']['environment'])['docker_image']=tag
        if not diagnostic and variant == 'current':
            admission_preflight('direct-harbor-verifier:live', public/'admission-preflight.json')
        (task/'task.toml').write_text(toml.dumps(cfg))
        manifest.update(task_checksum=Task(task).checksum,effective_skills=expected_files(variant),effective_codex_config=config())
        trial.write(output/'manifest.json',manifest)
        check_task(task, variant, output, root, diagnostic)
        trial.write(root/(variant+'-task.json'),{'path':str(task)})
        trial.write(output/'preparation.json',{'stage':'preflight_passed','paid_inference_permitted':False})
        print('External preflight passed: '+variant,flush=True)
    assert {k:v for k,v in expected_files('current').items() if not k.startswith(TARGET+'/')}==expected_files('absent')
    if not diagnostic:
        current=json.loads((public/'current/manifest.json').read_text());absent=json.loads((public/'absent/manifest.json').read_text())
        for key in ('instructions_sha256','codex_configuration','grader_files','effective_codex_config'):
            assert current[key]==absent[key], 'Unmatched arm configuration: '+key
        removed=sorted(set(current['effective_skills'])-set(absent['effective_skills']))
        assert len(removed)==3 and all(k.startswith(TARGET+'/') for k in removed)
        trial.write(public/'comparison-manifest.json',{'matched':True,'removed_target_files':removed,
            'profile':PROFILE['id'],'shared_config':config(),'instructions_sha256':current['instructions_sha256']})
    trial.write(public/'preflight.json',{'passed':True,'commit':os.environ.get('GITHUB_SHA'),'paid_inference_permitted':False,'live_eligible_after_approval':not (diagnostic or infrastructure),'network_mode':'none' if diagnostic else 'allowlist','remote_tools_disabled':True})

def usage_and_activation(native_dir):
    totals=None;activation=set();completion=False;calls=0;event_types={};tool_names={};outcomes=[];completion_shape=None;tool_errors={'runtime_tool_error':0,'permission_denied':0,'missing_path':0}
    rollouts=sorted((native_dir/'agent').glob('**/rollout-*.jsonl')); malformed=0; last_token_line=None; terminal_line=None
    for p in rollouts:
        for index,line in enumerate(p.read_text().splitlines()):
            try:event=json.loads(line)
            except ValueError:
                malformed+=1;continue
            payload=event.get('payload',{})
            event_type=payload.get('type')
            known={'function_call','custom_tool_call','function_call_output','custom_tool_call_output','exec_command_end','task_complete','turn_complete','token_count'}
            label=event_type if event_type in known else 'other'
            event_types[label]=event_types.get(label,0)+1
            if event.get('type')=='event_msg' and payload.get('type')=='token_count':
                value=(payload.get('info') or {}).get('total_token_usage')
                if value:last_token_line=index
                if value:totals={k:(value.get(k) if type(value.get(k)) is int and value[k]>=0 else None) for k in ('input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens','cache_write_input_tokens','total_tokens')}
            if event.get('type')=='response_item' and payload.get('type') in ('function_call','custom_tool_call'):
                calls+=1
                name=payload.get('name')
                safe_name=name if name in ('exec_command','write_stdin','apply_patch','functions.exec','shell','shell_command','read_file','update_plan') else 'other'
                tool_names[safe_name]=tool_names.get(safe_name,0)+1
                arguments=payload.get('arguments' if payload['type']=='function_call' else 'input','')
                for name in expected_files('current'):
                    if name.startswith(TARGET+'/') and name in str(arguments):activation.add(name)
            if event_type in ('function_call_output','custom_tool_call_output','exec_command_end'):
                observed=str(payload.get('output',payload.get('aggregated_output',''))).lower()
                if ('codex-exec-server' in observed or 'codex-code-mode-host' in observed) and any(x in observed for x in ('no such file','failed to start','permission denied')):
                    tool_errors['runtime_tool_error']+=1
                if 'permission denied' in observed:tool_errors['permission_denied']+=1
                if 'no such file or directory' in observed:tool_errors['missing_path']+=1
            if event.get('type')=='event_msg' and event_type=='exec_command_end':
                outcomes.append({'exit_code':payload.get('exit_code') if type(payload.get('exit_code')) is int else None,'output_retained':False})
            if event.get('type')=='event_msg' and event_type in ('task_complete','turn_complete'):
                completion=True;terminal_line=index
                message=payload.get('last_agent_message')
                completion_shape={'message_present':isinstance(message,str),'message_characters':len(message) if isinstance(message,str) else None,'content_retained':False}
    return {'session_evidence':{'rollout_files':len(rollouts),'malformed_lines':malformed,'usage_before_terminal':last_token_line is not None and terminal_line is not None and last_token_line<terminal_line},'total_usage':totals,'skill_file_access_attempts':sorted(activation),'tool_calls':calls,'completion_event':completion,'event_type_counts':event_types,'tool_name_counts':tool_names,'exec_outcomes':outcomes[:100],'completion_shape':completion_shape,'tool_error_flags':tool_errors,'evidence_limit':'File-access attempts do not prove successful reads, instruction following or correctness.'}

def usage_estimate(usage):
    if not isinstance(usage,dict):return None
    keys=('input_tokens','cached_input_tokens','cache_write_input_tokens','output_tokens','reasoning_output_tokens','total_tokens')
    if any(type(usage.get(k)) is not int or usage[k]<0 for k in keys):return None
    if usage['cached_input_tokens']+usage['cache_write_input_tokens']>usage['input_tokens']:return None
    if usage['reasoning_output_tokens']>usage['output_tokens']:return None
    if usage['total_tokens']!=usage['input_tokens']+usage['output_tokens']:return None
    # Cache reads/writes are input subsets; reasoning is an output subset.
    return trial.conservative_usage_cost({'input_including_cache':usage['input_tokens'],
        'cached_input':usage['cached_input_tokens'],'output':usage['output_tokens']},
        input_rate=PROFILE['pricing']['conservative_all_input_per_million'],
        output_rate=PROFILE['pricing']['conservative_output_per_million'])

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
    from allocation import active,ATTEMPTS,ID,receipt_path,gate
    a=active()
    assert not (root/'public/allocation/closed.json').exists(), 'Allocation already closed'
    receipt=json.loads(receipt_path(root,variant).read_text())
    assert receipt['run_id']==os.environ['GITHUB_RUN_ID'] and receipt['commit']==os.environ['GITHUB_SHA']
    assert receipt['attempt']==ATTEMPTS[variant] and receipt['allocation_id']==ID and receipt['reservation_id']==a['reservation_ids'][variant]
    assert not os.environ.get('TRIAL_DIAGNOSTIC') and not os.environ.get('TRIAL_PROVIDER_PROBE')
    assert os.environ.get('OPENAI_API_KEY') and variant in ('current','absent')
    assert json.loads((root/'public/preflight.json').read_text())['passed']
    output=root/'public'/variant
    assert not (output/'attempt.json').exists(), 'No implicit retry'
    if variant=='absent':
        first=json.loads((root/'public/current/attempt.json').read_text())
        assert gate(first,a)['allowed'], 'Unreliable first outcome or insufficient spending reserve'
    task=Path(json.loads((root/(variant+'-task.json')).read_text())['path'])
    manifest=json.loads((output/'manifest.json').read_text());assert Task(task).checksum==manifest['task_checksum']
    record={'allocation_id':ID,'reservation_id':receipt['reservation_id'],'attempt':ATTEMPTS[variant],'variant':variant,'reserved':True,'credentialed_launch_started':False,'rollout_present':False,
            'result_extraction_succeeded':False,'execution_completed':False,'usage_estimate_usd':None,
            'projection':[],'commit':os.environ.get('GITHUB_SHA')}
    with (output/'attempt.json').open('x') as f:json.dump(record,f,indent=2)
    cfg={'job_name':variant,'jobs_dir':str(root/'jobs'),'n_attempts':1,'n_concurrent_trials':1,
        'retry':{'max_retries':0},'environment':{'type':'docker','delete':True},
        'agents':[{'import_path':'pinned_codex:PinnedCodex','model_name':MODEL,'extra_allowed_hosts':['api.openai.com'],
          'kwargs':{'version':VERSION,'reasoning_effort':EFFORT,'web_search':'disabled','config':config()}}],
        'tasks':[{'path':str(task)}]}
    trial.write(root/(variant+'-job.json'),cfg)
    env=os.environ.copy();env.update(PYTHONPATH=str(Path(__file__).parent),TRIAL_VARIANT=variant,TRIAL_PUBLIC_DIR=str(output))
    started=time.monotonic()
    try:
        record['credentialed_launch_started']=True
        trial.write(output/'attempt.json',record)
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
        from accounting import terminal_events,assess
        record['usage_estimate_usd']=usage_estimate(details['total_usage'])
        terminal_path=native/'agent/codex.txt'
        record['native_terminal']=terminal_events(terminal_path.read_text()) if terminal_path.is_file() else []
        record.update(assess(row,details,record['native_terminal'],record['usage_estimate_usd']))
        record['execution_completed']=record['execution_assessment']['outcome']=='completed'
        record['native_pricing_estimate_usd']=row['cost_usd']
        record['api_bill_usd']=None
        trial.write(output/'attempt.json',record)
        record['handoff']=collect(native,row,completed=record['execution_assessment']['interpretable'],environment_ok=record['execution_assessment']['interpretable'])
        from retention import stage,protected_contents,OUTPUT
        identity={k:receipt[k] for k in ('allocation_id','reservation_id','attempt','variant','commit','run_id')}
        record['submission_retention']=stage(native/'artifacts'/OUTPUT.lstrip('/'),root/'submissions'/variant,identity,
            secrets=[os.environ.get(k,'') for k in ('OPENAI_API_KEY','CODEX_API_KEY','GITHUB_TOKEN','GH_TOKEN','ACTIONS_RUNTIME_TOKEN')],
            protected=protected_contents(),observations={'producer':record['handoff']['agent_observation'].get('artifact',{}),'host':record['handoff']['host_artifact'],'verifier':record['handoff']['verifier_observation'].get('artifact',{})})
        trial.write(output/'attempt.json',record)
        assert Task(task).checksum==manifest['task_checksum'], 'Frozen task changed'
        record['result_extraction_succeeded']=True
    except Exception as exc:
        record['extraction_exception']={'type':type(exc).__name__,'message':sanitize(str(exc),(os.environ.get('OPENAI_API_KEY',''),))}
    finally:
        # Inspect/stop only this disposable runner's trial containers, never export inspect env.
        for label,tag in (('agent','direct-harbor-agent:'+variant),('verifier','direct-harbor-verifier:live')):
            try:
                remaining=subprocess.check_output(['docker','ps','--all','--filter','label=com.docker.compose.service=main','--filter','ancestor='+tag,'--quiet'],text=True,timeout=30).split()
                record[label+'_container_removed']=not remaining
                if remaining:
                    assert all(__import__('re').fullmatch('[0-9a-f]{12,64}',x) for x in remaining)
                    subprocess.run(['docker','rm','--force',*remaining],check=True,timeout=30,stdout=subprocess.DEVNULL)
                    record[label+'_forced_cleanup']=True
                    record['result_extraction_succeeded']=False
            except Exception as exc:
                record[label+'_container_removed']=None
                record['disposal_exception']=sanitize(str(exc),(os.environ.get('OPENAI_API_KEY',''),))
                record['result_extraction_succeeded']=False
        record['second_arm_gate']=gate(record,a,require_publication=False)
        record['duration_seconds']=round(time.monotonic()-started,3);trial.write(output/'attempt.json',record)
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'],'a') as f:
                print('retention_ready='+str(record.get('submission_retention',{}).get('status')=='ready').lower(),file=f)
        print(json.dumps({k:record.get(k) for k in ('attempt','variant','rollout_present','execution_completed','result_extraction_succeeded','usage_estimate_usd','second_arm_gate')}),flush=True)
    if variant=='current':return 0 if record['second_arm_gate']['allowed'] else 1
    completed_gate=gate(record,{**a,'second_attempt_reserve_usd':0,'headroom_usd':0},require_publication=False)
    return 0 if completed_gate['allowed'] else 1

if __name__=='__main__':
    mode=sys.argv[1];root=Path(sys.argv[2]).resolve()
    if mode=='diagnostic-prepare':
        try:prepare(root,diagnostic=True)
        except Exception as exc:
            from diagnostics import sanitize
            trial.write(root/'public/preparation-failure.json',{'type':type(exc).__name__,'message':sanitize(str(exc)),'paid_inference_permitted':False})
            raise
    elif mode=='diagnostic':raise SystemExit(diagnostic(root,sys.argv[3]))
    elif mode in ('prepare','infrastructure-prepare'):
        try:prepare(root,infrastructure=mode=='infrastructure-prepare')
        except Exception as exc:
            from diagnostics import sanitize
            trial.write(root/'public/preparation-failure.json',{'stage':'image_preparation','type':type(exc).__name__,'message':sanitize(str(exc)),'paid_inference_permitted':False})
            raise
    elif mode in ('current','absent'):raise SystemExit(live_attempt(root,mode))
    else:raise ValueError('Unknown trial mode')
