"""Three deterministic producers through native Harbor collection and verification."""
import asyncio,hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
import toml
import run as trial
from artifact_state import OUTPUT,observe,classify

KINDS=('good','missing','rejected')
def no_credentials():
    assert not any(os.environ.get(k) for k in ('OPENAI_API_KEY','CODEX_API_KEY','CODEX_AUTH_JSON_PATH','CODEX_FORCE_AUTH_JSON')), 'Credential-free diagnostics only'
    launch=json.loads(Path(__file__).with_name('launch.json').read_text())
    assert launch['paid_execution_enabled'] is False and launch['paid_attempts_used']==4 and launch['scheduling_stopped'] is True

def prepare(root):
    from harbor.models.task.task import Task
    no_credentials();root.mkdir(parents=True,exist_ok=False)
    native,manifest=trial.stage(root/'stage',historical_runtime=True)
    task=native/'pester-002';cfg=toml.load(task/'task.toml')
    cfg['environment'].update(network_mode='allowlist',allowed_hosts=['api.openai.com'])
    cfg['agent']['timeout_sec']=60
    compose=task/'environment/docker-compose.yaml'
    compose.write_text(compose.read_text()+'''    user: "1000:1000"
  harbor-docker-egress-control-sidecar:
    cap_drop: [ALL]
    security_opt: [no-new-privileges:true]
    pids_limit: 128
    mem_limit: 256m
    cpus: 0.5
''')
    for folder,tag in [('environment','direct-harbor-agent:handoff'),('tests','direct-harbor-verifier:handoff')]:
        subprocess.run(['docker','build','--progress=plain','-t',tag,str(task/folder)],check=True,timeout=600)
        (cfg['environment'] if folder=='environment' else cfg['verifier']['environment'])['docker_image']=tag
    (task/'task.toml').write_text(toml.dumps(cfg))
    from harbor.models.trial.paths import TrialPaths
    from harbor.environments.docker.docker import DockerEnvironment
    from live import runtime_check
    async def check():
        obj=Task(task)
        environment=DockerEnvironment(environment_dir=obj.paths.environment_dir,environment_name='pester-002',session_id='handoff-preflight',trial_paths=TrialPaths(root/'preflight'),task_env_config=obj.config.environment,network_policy=obj.config.environment.resolve_baseline())
        try:
            await environment.start(force_build=False)
            await runtime_check(environment,'current',root/'public/preflight',expected_version='0.155.1')
        finally:await environment.stop(delete=True)
    asyncio.run(check())
    manifest.update(task_checksum=Task(task).checksum,instruction_sha256=hashlib.sha256((task/'instruction.md').read_bytes()).hexdigest(),
        image_ids={tag:subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',tag],text=True).strip() for tag in ('direct-harbor-agent:handoff','direct-harbor-verifier:handoff')},
        runtime_profile='historical 0.155.1 installed, never invoked by these producers')
    trial.write(root/'public/manifest.json',manifest);trial.write(root/'task.json',{'path':str(task)})

def collect(native, row):
    entries=json.loads((native/'artifacts/manifest.json').read_text())
    entry=next((x for x in entries if x['source']==OUTPUT),{})
    producer_path=native/'artifacts/logs/artifacts/agent-artifact.json'
    transfer_path=native/'verifier/artifact-transfer.json'
    producer=json.loads(producer_path.read_text()) if producer_path.is_file() else {}
    verifier=json.loads(transfer_path.read_text()) if transfer_path.is_file() else {}
    host=observe(native/'artifacts'/OUTPUT.lstrip('/'))
    result={'native_collection_manifest':entries,'agent_observation':producer,'host_artifact':host,'verifier_observation':verifier,
        'classification':classify(producer.get('artifact',{}),entry,host,verifier.get('artifact',{}),row['outcome'],environment_ok=row['failure_cause'] is None,completed=row['failure_cause'] is None),
        'upload_status':'hash_matched' if host.get('sha256') and host['sha256']==verifier.get('artifact',{}).get('sha256') else 'no_source' if host.get('exists') is False and verifier.get('artifact',{}).get('exists') is False else 'unconfirmed'}
    return result

def control(root,kind):
    from harbor.models.task.task import Task
    no_credentials();assert kind in KINDS
    output=root/'public'/kind;output.mkdir(parents=True,exist_ok=False)
    record={'kind':'deterministic_handoff_control','control':kind,'paid_attempt':False,'codex_task_execution':False,'passed':False,'commit':os.environ.get('GITHUB_SHA')}
    trial.write(output/'control.json',record)
    task=root/'tasks'/('pester-002-'+kind)
    shutil.copytree(Path(json.loads((root/'task.json').read_text())['path']),task)
    solution=task/'solution';solution.mkdir()
    script='#!/bin/sh\nset -eu\ntest "$(id -u)" = 1000\ntest "$(id -g)" = 1000\ntest "$PWD" = /workspace\ntest ! -e /tests\ntest ! -e /var/run/docker.sock\ntest ! -e /workspace/output/Subject.Tests.ps1\n'
    if kind=='good':
        shutil.copyfile(trial.ROOT/trial.pilot.OVERLAY/'support/qualification/pester-002/classic.Tests.ps1',solution/'candidate')
        script+='cp /solution/candidate /workspace/output/Subject.Tests.ps1\n'
    elif kind=='rejected':script+="python3 -c \"from pathlib import Path; Path('/workspace/output/Subject.Tests.ps1').write_bytes(bytes([255,254,128]))\"\n"
    (solution/'solve.sh').write_text(script);(solution/'solve.sh').chmod(0o755)
    before=Task(task).checksum
    cfg={'job_name':kind,'jobs_dir':str(root/'jobs'),'n_attempts':1,'n_concurrent_trials':1,'retry':{'max_retries':0},'environment':{'type':'docker','delete':True},'agents':[{'name':'oracle'}],'tasks':[{'path':str(task)}]}
    trial.write(root/(kind+'-job.json'),cfg)
    try:
        with (root/(kind+'-private.log')).open('w') as log:
            completed=subprocess.run(['harbor','run','--config',str(root/(kind+'-job.json'))],stdout=log,stderr=subprocess.STDOUT,timeout=420)
        row=next(r for r in trial.project(root/'jobs',{}) if r['native_result'].startswith('jobs/'+kind+'/'))
        row.pop('expected',None);row.pop('matches',None)
        record.update(native_result=row,harbor_returncode=completed.returncode,task_checksum=before)
        record.update(collect(root/Path(row['native_result']).parent,row))
        assert completed.returncode==0 and row['failure_cause'] is None and Task(task).checksum==before
        expected={'good':'graded_passed','missing':'missing_deliverable','rejected':'rejected_output'}[kind]
        assert record['classification']['classification']==expected, record['classification']
        if kind=='good':assert row['outcome']['reference_pass']==1 and row['outcome']['mutants_detected']==2 and row['measured']
        else:assert not row['measured'] and row['outcome']['admission_reason']==('missing' if kind=='missing' else 'invalid_utf8')
        if kind!='missing':assert record['upload_status']=='hash_matched' and record['agent_observation']['artifact']['sha256']==record['host_artifact']['sha256']
        assert record['agent_observation']['observer_uid']==1000
        record['passed']=True
    except Exception as exc:
        from diagnostics import sanitize
        record['diagnostic_failure']={'type':type(exc).__name__,'message':sanitize(str(exc))}
    finally:
        trial.write(output/'control.json',record);print(json.dumps(record),flush=True)
    return 0 if record['passed'] else 1

if __name__=='__main__':
    root=Path(sys.argv[2]).resolve()
    if sys.argv[1]=='prepare':prepare(root)
    else:raise SystemExit(control(root,sys.argv[1]))
