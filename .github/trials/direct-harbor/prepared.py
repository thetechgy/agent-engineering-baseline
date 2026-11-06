"""Input-bound handoff of credential-free Docker images and immutable pester-002 inputs.

Only docker save/load and a bounded data archive; no running containers or homes.
The caller supplies the manifest digest from the successful preparation job output.
"""
import ast,hashlib,importlib.util,json,os,re,shutil,subprocess,sys,tarfile,zipfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
import allocation

TAGS=['direct-harbor-agent:current','direct-harbor-agent:absent','direct-harbor-verifier:live']
PROBE_REFERENCE='alpine:3.23.4@sha256:5b10f432ef3da1b8d4c7eb6c487f2f5a8f096bc91145e68878dd4a5019afde11'
PROBE_TAG='direct-harbor-kernel-probe:0.25.0'
FILES={'images.tar','inputs.tar','manifest.json'}

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n')

def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

HERE=Path(__file__).resolve().parent
REPOSITORY='thetechgy/agent-engineering-baseline'
BRANCH='refs/heads/trial/direct-harbor'

def snapshot_module():
    spec=importlib.util.spec_from_file_location('snapshot_transport',HERE/'prefetch-apt.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def identity():
    assert os.environ['GITHUB_REPOSITORY']==REPOSITORY and os.environ['GITHUB_REF']==BRANCH
    assert os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_RUN_ATTEMPT']=='1'
    launch=json.loads((HERE/'launch.json').read_text())
    if launch['phase']=='live-pair':
        allocation.active();allocation_id=allocation.ID
    else:
        assert launch['phase']=='preparation' and launch['scheduling_stopped'] and not launch['paid_execution_enabled']
        allocation_id=None
    return {'repository':REPOSITORY,'branch':BRANCH,'commit':os.environ['GITHUB_SHA'],
            'run_id':os.environ['GITHUB_RUN_ID'],'run_attempt':1,'allocation_id':allocation_id}

def experiment():
    """Bind actual build/deployment inputs, excluding reports and allocation metadata."""
    import run as trial
    roots=['.agents/skills','.codex','.github/evals/powershell-pester-6']
    inputs={}
    for relative in roots:
        inputs.update({relative+'/'+name:entry for name,entry in files(trial.ROOT/relative).items()})
    for relative in ['AGENTS.md','.github/scripts/pester_evaluations.py','.github/scripts/setup-compose.sh']:
        path=trial.ROOT/relative;inputs[relative]={'sha256':digest(path),'size':path.stat().st_size}
    # run.py also renders the report: bind its staging function, not report prose.
    stage=next(n for n in ast.parse((HERE/'run.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='stage')
    inputs['trial.stage']=ast.dump(stage,include_attributes=False)
    for name in ('live.py','pinned_codex.py','artifact_state.py','admission_checks.py','prefetch-apt.py','runtime-profile.json'):
        inputs[name]=digest(HERE/name)
    inputs['GH_TASK_BUILD']=trial.reports.GH_TASK_BUILD
    inputs['harbor_commit']=trial.HARBOR
    inputs['admission_diagnostics']=json.loads((HERE/'launch.json').read_text()).get('admission_diagnostics',False)
    return {'sha256':hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest(),'inputs':inputs}

def api(path):
    return json.loads(subprocess.check_output(['gh','api','repos/'+REPOSITORY+'/'+path],text=True))

def admit_source(source, *, require_success=True):
    """Check producer provenance before downloading or loading anything from another run."""
    run=api('actions/runs/'+str(source['run_id']))
    assert run['repository']['full_name']==REPOSITORY and run['head_repository']['full_name']==REPOSITORY
    assert run['head_branch']=='trial/direct-harbor' and run['event']=='push' and run['run_attempt']==1
    assert run['path']=='.github/workflows/direct-harbor-trial.yml' and run['head_sha']==source['commit']
    assert run['status']=='completed'
    if require_success:assert run['conclusion']=='success'
    subprocess.run(['git','merge-base','--is-ancestor',source['commit'],'HEAD'],check=True)
    artifact=api('actions/artifacts/'+str(source['artifact_id']))
    assert artifact['workflow_run']['id']==source['run_id'] and artifact['workflow_run']['head_sha']==source['commit']
    assert artifact['name']==source['name'] and not artifact['expired']
    assert artifact['digest']==source['artifact_digest']
    assert datetime.fromisoformat(artifact['expires_at'].replace('Z','+00:00'))>datetime.now(timezone.utc)
    return artifact

def download_artifact(source,bundle, *, members=FILES, limit=20*1024**3, require_success=True):
    metadata=admit_source(source,require_success=require_success)
    assert 0<metadata['size_in_bytes']<=limit
    archive=bundle.with_suffix('.zip');bundle.mkdir(parents=True,exist_ok=False)
    with archive.open('wb') as stream:
        subprocess.run(['gh','api','repos/'+REPOSITORY+'/actions/artifacts/'+str(source['artifact_id'])+'/zip'],stdout=stream,check=True,timeout=600)
    assert digest(archive)=='%s'%source['artifact_digest'].removeprefix('sha256:'), 'Artifact transport digest mismatch'
    with zipfile.ZipFile(archive) as zipped:
        entries=zipped.infolist()
        assert {e.filename for e in entries}==members and len(entries)==len(members)
        assert sum(e.file_size for e in entries)<=limit
        for entry in entries:
            with zipped.open(entry) as src,(bundle/entry.filename).open('wb') as dst:shutil.copyfileobj(src,dst)
    archive.unlink()
    return metadata

def producer_identity():
    source=json.loads((HERE/'preparation.json').read_text()).get('prepared_source')
    if source is None:return identity()
    return {'repository':REPOSITORY,'branch':BRANCH,'commit':source['commit'],'run_id':str(source['run_id']),'run_attempt':1,'allocation_id':None}

def no_credentials():
    assert not any(os.environ.get(k) for k in ('OPENAI_API_KEY','CODEX_API_KEY','CODEX_AUTH_JSON_PATH','CODEX_FORCE_AUTH_JSON'))

def image_id(tag):
    value=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',tag],text=True).strip()
    assert re.fullmatch('sha256:[a-f0-9]{64}',value)
    return value

def files(root):
    result={}
    for path in sorted(root.rglob('*')):
        assert not path.is_symlink()
        if path.is_file():
            assert path.stat().st_nlink==1
            assert path.name not in ('auth.json','.env') and 'sessions' not in path.parts
            result[path.relative_to(root).as_posix()]={'sha256':digest(path),'size':path.stat().st_size}
        else:assert path.is_dir()
    return result

def export(root,bundle):
    no_credentials();who=identity();assert json.loads((root/'public/preflight.json').read_text())['passed']
    # A successful probe must have removed its environments before packaging images.
    assert not subprocess.check_output(['docker','ps','--all','--filter','label=com.docker.compose.service=main','--quiet'],text=True).strip()
    bundle.mkdir(parents=True,exist_ok=False)
    tags=subprocess.check_output(['docker','image','ls','--format','{{.Repository}}:{{.Tag}}'],text=True).splitlines()
    sidecars=[t for t in tags if t.startswith('harbor-prebuilt:harbor-docker-egress-control-sidecar-')]
    assert len(sidecars)==1, 'Expected the pinned Harbor content-addressed egress image'
    # Stock Harbor has already used this digest-pinned auxiliary during preflight.
    probe_id=image_id(PROBE_REFERENCE)
    subprocess.run(['docker','image','tag',PROBE_REFERENCE,PROBE_TAG],check=True)
    assert image_id(PROBE_TAG)==probe_id
    images={tag:image_id(tag) for tag in TAGS+sidecars+[PROBE_TAG]}
    payload=bundle.parent/'prepared-inputs';payload.mkdir(exist_ok=False)
    tasks={}
    from harbor.models.task.task import Task
    for variant in ('current','absent'):
        task=Path(json.loads((root/(variant+'-task.json')).read_text())['path'])
        assert task.is_relative_to(root) and task.name=='pester-002'
        shutil.copytree(task,payload/'tasks'/variant)
        tasks[variant]={'path':'tasks/'+variant,'checksum':Task(task).checksum}
        assert Task(payload/'tasks'/variant).checksum==tasks[variant]['checksum']
    # This directory exists before any credentialed launch and contains metadata only.
    for source in sorted((root/'public').rglob('*')):
        if source.is_file():
            assert source.suffix=='.json' and not source.is_symlink()
            destination=payload/'public'/source.relative_to(root/'public');destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,destination)
    members=files(payload)
    with tarfile.open(bundle/'inputs.tar','w') as archive:
        for name in members:archive.add(payload/name,arcname=name,recursive=False)
    subprocess.run(['docker','image','save','--output',str(bundle/'images.tar'),*images],check=True,timeout=240)
    manifest={'schema':3,'kernel_probe_reference':PROBE_REFERENCE,'experiment':experiment(),'created_at':datetime.now(timezone.utc).isoformat(),'expires_at':(datetime.now(timezone.utc)+timedelta(days=7)).isoformat(),'snapshot_bundle':json.loads((root/'public/snapshot-bundle.json').read_text()),'identity':who,'images':images,'tasks':tasks,'members':members,
        'archives':{name:{'sha256':digest(bundle/name),'size':(bundle/name).stat().st_size} for name in ('images.tar','inputs.tar')},
        'credentials':False,'running_containers':False,'authenticated_homes':False,
        'contents':'Prepared images and public repository task/verifier inputs only; separate from the report and agent-visible inputs.'}
    write(bundle/'manifest.json',manifest)
    value=digest(bundle/'manifest.json')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as output:print('manifest_sha256='+value,file=output)
    write(root/'public/prepared-manifest.json',manifest)
    print(json.dumps({'prepared_manifest_sha256':value,'images':images,'task_checksums':tasks}))

def verify(bundle,expected,who):
    assert re.fullmatch('[a-f0-9]{64}',expected)
    assert {p.name for p in bundle.iterdir()}==FILES
    assert all(p.is_file() and not p.is_symlink() for p in bundle.iterdir())
    assert digest(bundle/'manifest.json')==expected, 'Preparation manifest digest mismatch'
    manifest=json.loads((bundle/'manifest.json').read_text())
    assert manifest['identity']==who, 'Wrong repository, branch, commit, run or allocation'
    assert manifest['schema']==3 and manifest['kernel_probe_reference']==PROBE_REFERENCE and manifest['experiment']==experiment(), 'Prepared experiment inputs changed'
    assert datetime.fromisoformat(manifest['expires_at'])>datetime.now(timezone.utc), 'Prepared images expired'
    assert all(manifest[k] is False for k in ('credentials','running_containers','authenticated_homes'))
    assert all(k in manifest['images'] for k in TAGS+[PROBE_TAG]) and len(manifest['images'])==5
    for name,entry in manifest['archives'].items():
        assert name in ('images.tar','inputs.tar')
        assert 0<entry['size']<=16*1024**3
        assert (bundle/name).stat().st_size==entry['size'] and digest(bundle/name)==entry['sha256']
    assert set(manifest['archives'])=={'images.tar','inputs.tar'}
    with tarfile.open(bundle/'inputs.tar') as archive:
        entries=archive.getmembers()
        assert len(entries)==len(manifest['members'])<3000
        assert sum(x.size for x in entries)<64*1024**2
        assert len({x.name for x in entries})==len(entries)
        for item in entries:
            path=Path(item.name)
            assert item.isfile() and not path.is_absolute() and '..' not in path.parts
            assert item.name in manifest['members'] and path.parts[0] in ('tasks','public')
            assert path.name not in ('auth.json','.env') and 'sessions' not in path.parts
            data=archive.extractfile(item).read()
            assert {'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)}==manifest['members'][item.name]
    return manifest

def restore(bundle,root,expected,proof_path=None):
    no_credentials();consumer=identity();manifest=verify(bundle,expected,producer_identity());root.mkdir(parents=True,exist_ok=False)
    subprocess.run(['docker','image','load','--input',str(bundle/'images.tar')],check=True,timeout=240)
    assert {tag:image_id(tag) for tag in manifest['images']}==manifest['images'], 'Loaded image identity mismatch'
    # Classic Docker archives omit RepoDigests. Re-establish only the stock pinned
    # reference, never a moving tag; downloaded layers (if any) remain digest checked.
    probe=subprocess.run(['docker','image','inspect',PROBE_REFERENCE],capture_output=True)
    refreshed=probe.returncode!=0
    if refreshed:subprocess.run(['docker','image','pull',PROBE_REFERENCE],check=True,timeout=120)
    assert image_id(PROBE_REFERENCE)==manifest['images'][PROBE_TAG], 'Kernel probe identity mismatch'
    with tarfile.open(bundle/'inputs.tar') as archive:archive.extractall(root,filter='data')
    assert files(root)==manifest['members']
    from harbor.models.task.task import Task
    for variant,entry in manifest['tasks'].items():
        assert variant in ('current','absent') and entry['path']=='tasks/'+variant
        task=root/entry['path'];assert Task(task).checksum==entry['checksum']
        assert json.loads((root/'public'/variant/'manifest.json').read_text())['task_checksum']==entry['checksum']
        write(root/(variant+'-task.json'),{'path':str(task.resolve())})
    if proof_path is not None:
        proof=json.loads(proof_path.read_text())
        assert proof['verified'] and proof['identity']==manifest['identity'] and proof['manifest_sha256']==expected
        write(root/'public/prepared-download.json',proof)
    write(root/'public/prepared-manifest.json',manifest)
    write(root/'public/prepared-transfer.json',{'verified':True,'identity':consumer,'source_identity':manifest['identity'],'manifest_sha256':expected,
        'images':manifest['images'],'task_checksums':manifest['tasks'],'fresh_image_load':True,'snapshot_rebuild':False,
        'root_paths_relocated':True,'kernel_probe_registry_refresh':refreshed,'kernel_probe_reference':PROBE_REFERENCE,'note':'Only built images were transferred; Harbor creates fresh containers, homes and sessions.'})
    print('Prepared image IDs, archive hashes, task checksums and relocated paths verified; no rebuild.')

def reuse_preflight(root):
    """Check the restored runtime before approval/reservation; reuse native qualification."""
    no_credentials();consumer=identity()
    transfer=json.loads((root/'public/prepared-transfer.json').read_text())
    assert transfer['verified'] and transfer['identity']==consumer
    record={'passed':False,'identity':consumer,'manifest_sha256':transfer['manifest_sha256'],
            'inference':False,'image_rebuilds':0,'snapshot_index_downloads':0}
    import live
    try:
        inventory=sorted(subprocess.check_output(['docker','image','ls','--no-trunc','--quiet'],text=True).splitlines())
        for variant in ('current','absent'):
            task=Path(json.loads((root/(variant+'-task.json')).read_text())['path'])
            live.check_task(task,variant,root/'public/reuse'/variant,root)
        assert inventory==sorted(subprocess.check_output(['docker','image','ls','--no-trunc','--quiet'],text=True).splitlines()), 'Unexpected image creation or pull'
        assert {tag:image_id(tag) for tag in transfer['images']}==transfer['images']
        record['image_inventory_unchanged']=True
        record['remaining_containers']={tag:subprocess.check_output(['docker','ps','--all','--filter','ancestor='+tag,'--quiet'],text=True).splitlines() for tag in transfer['images']}
        assert not any(record['remaining_containers'].values()), 'Preflight disposal unconfirmed'
        record['container_disposal_verified']=True
        record['passed']=True
    except Exception as exc:
        from diagnostics import sanitize
        record['failure']={'type':type(exc).__name__,'message':sanitize(str(exc))}
        raise
    finally:write(root/'public/reuse-preflight.json',record)


def acquire_dependency(root):
    no_credentials();identity()
    config=json.loads((HERE/'preparation.json').read_text());seed=config['dependency_seed']
    source=config.get('dependency_source')
    if source:
        assert source['name']=='snapshot-dependencies'
        # Exact pinned bytes remain usable even if a later image build failed.
        download_artifact(source,root,members={seed['asset']},limit=12*1024**2,require_success=False)
    else:
        root.mkdir(parents=True,exist_ok=False)
        subprocess.run(['gh','release','download',seed['tag'],'--repo',REPOSITORY,'--pattern',seed['asset'],'--dir',str(root)],check=True,timeout=120)
    archive=root/seed['asset']
    assert archive.stat().st_size<12*1024**2 and digest(archive)==seed['archive_sha256'], 'snapshot_seed_transport_digest'
    target=root/'indexes';target.mkdir()
    with zipfile.ZipFile(archive) as zipped:
        entries=zipped.infolist();expected=set(snapshot_module().INDEXES)|{'manifest.json'}
        assert {e.filename for e in entries}==expected and len(entries)==len(expected), 'snapshot_seed_members'
        assert sum(e.file_size for e in entries)<12*1024**2
        for entry in entries:
            destination=target/entry.filename;destination.parent.mkdir(parents=True,exist_ok=True)
            with zipped.open(entry) as src,destination.open('wb') as dst:shutil.copyfileobj(src,dst)
    assert digest(target/'manifest.json')==seed['manifest_sha256'], 'snapshot_seed_manifest_digest'
    manifest=snapshot_module().validate_bundle(target)
    assert manifest['source_commit']==seed['source_commit']
    print(json.dumps({'snapshot_manifest_sha256':seed['manifest_sha256'],'source_commit':manifest['source_commit'],'index_downloads':0}))


def qualify(bundle,root,expected):
    """A separate hosted job must start with none of the retained images present."""
    no_credentials();identity()
    manifest=verify(bundle,expected,producer_identity())
    for tag in manifest['images']:
        assert subprocess.run(['docker','image','inspect',tag],capture_output=True).returncode!=0, 'Runner already has a prepared image'
    restore(bundle,root,expected)
    record={'passed':False,'inference':False,'image_rebuilds':0,'snapshot_index_downloads':0,
            'fresh_runner_initial_images_absent':True,'source_identity':manifest['identity'],
            'consumer_identity':identity(),'images':manifest['images'],'controls':[],
            'task_checksums':manifest['tasks'],'experiment':manifest['experiment']['sha256'],
            'kernel_probe_registry_refresh':json.loads((root/'public/prepared-transfer.json').read_text())['kernel_probe_registry_refresh']}
    # Harbor's unmodified start(force_build=False) uses the already-loaded sidecar.
    # All retained identities must exist before Harbor's supported prebuilt path starts.
    import live,admission_validation
    try:
        inventory=subprocess.check_output(['docker','image','ls','--no-trunc','--quiet'],text=True).splitlines()
        record['image_inventory_before']=sorted(inventory)
        for variant in ('current','absent'):
            task=Path(json.loads((root/(variant+'-task.json')).read_text())['path'])
            live.check_task(task,variant,root/'public/fresh'/variant,root)
        record['image_inventory_after']=sorted(subprocess.check_output(['docker','image','ls','--no-trunc','--quiet'],text=True).splitlines())
        assert sorted(inventory)==record['image_inventory_after'], 'Unexpected image creation or pull'
        record['image_inventory_unchanged']=True
        record['parser']=live.admission_preflight(TAGS[2],root/'public/fresh/admission-preflight.json')
        admission_validation.IMAGE=TAGS[2]
        record['controls']=[admission_validation.control(root/'fresh-controls',kind) for kind in ('good','weak','unsupported','runner_error')]
        assert all(c['passed'] for c in record['controls'])
        assert {tag:image_id(tag) for tag in manifest['images']}==manifest['images']
        record['remaining_containers']={tag:subprocess.check_output(['docker','ps','--all','--filter','ancestor='+tag,'--quiet'],text=True).splitlines() for tag in manifest['images']}
        record['container_disposal_verified']=not any(record['remaining_containers'].values())
        assert record['container_disposal_verified']
        record['passed']=True
    except Exception as exc:
        from diagnostics import sanitize
        record['failure']={'type':type(exc).__name__,'message':sanitize(str(exc))}
        raise
    finally:write(root/'public/fresh-qualification.json',record)

if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='export':export(Path(sys.argv[2]).resolve(),Path(sys.argv[3]).resolve())
    elif mode=='verify':
        no_credentials();m=verify(Path(sys.argv[2]),sys.argv[3],producer_identity())
        write(Path(sys.argv[4]),{'verified':True,'identity':m['identity'],'manifest_sha256':sys.argv[3],'images':m['images'],'tasks':m['tasks'],'credential_free':True})
    elif mode=='restore':restore(Path(sys.argv[2]),Path(sys.argv[3]),sys.argv[4],Path(sys.argv[5]) if len(sys.argv)>5 else None)
    elif mode=='preflight':reuse_preflight(Path(sys.argv[2]))
    elif mode=='dependency':acquire_dependency(Path(sys.argv[2]))
    elif mode=='qualify':qualify(Path(sys.argv[2]),Path(sys.argv[3]),sys.argv[4])
    elif mode=='reuse':
        no_credentials();identity()
        source=json.loads((HERE/'preparation.json').read_text())['prepared_source']
        download_artifact(source,Path(sys.argv[2]))
        verify(Path(sys.argv[2]),source['manifest_sha256'],producer_identity())
        with open(os.environ['GITHUB_OUTPUT'],'a') as out:print('manifest_sha256='+source['manifest_sha256'],file=out)
    else:raise ValueError('Unknown prepared handoff mode')
