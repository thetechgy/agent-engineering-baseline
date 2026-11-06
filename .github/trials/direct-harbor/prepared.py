"""One-run handoff of credential-free Docker images and immutable pester-002 inputs.

Only docker save/load and a bounded data archive; no running containers or homes.
The caller supplies the manifest digest from the successful preparation job output.
"""
import hashlib,json,os,re,shutil,subprocess,sys,tarfile
from pathlib import Path
import allocation

TAGS=['direct-harbor-agent:current','direct-harbor-agent:absent','direct-harbor-verifier:live']
FILES={'images.tar','inputs.tar','manifest.json'}

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n')

def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def identity():
    allocation.active()
    return {'repository':os.environ['GITHUB_REPOSITORY'],'branch':os.environ['GITHUB_REF'],
            'commit':os.environ['GITHUB_SHA'],'run_id':os.environ['GITHUB_RUN_ID'],'allocation_id':allocation.ID}

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
    images={tag:image_id(tag) for tag in TAGS+sidecars}
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
    manifest={'identity':who,'images':images,'tasks':tasks,'members':members,
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
    assert all(manifest[k] is False for k in ('credentials','running_containers','authenticated_homes'))
    assert all(k in manifest['images'] for k in TAGS) and len(manifest['images'])==4
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
    no_credentials();manifest=verify(bundle,expected,identity());root.mkdir(parents=True,exist_ok=False)
    subprocess.run(['docker','image','load','--input',str(bundle/'images.tar')],check=True,timeout=240)
    assert {tag:image_id(tag) for tag in manifest['images']}==manifest['images'], 'Loaded image identity mismatch'
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
    write(root/'public/prepared-transfer.json',{'verified':True,'identity':manifest['identity'],'manifest_sha256':expected,
        'images':manifest['images'],'task_checksums':manifest['tasks'],'fresh_image_load':True,'snapshot_rebuild':False,
        'root_paths_relocated':True,'note':'Only built images were transferred; Harbor creates fresh containers, homes and sessions.'})
    print('Prepared image IDs, archive hashes, task checksums and relocated paths verified; no rebuild.')

if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='export':export(Path(sys.argv[2]).resolve(),Path(sys.argv[3]).resolve())
    elif mode=='verify':
        no_credentials();m=verify(Path(sys.argv[2]),sys.argv[3],identity())
        write(Path(sys.argv[4]),{'verified':True,'identity':m['identity'],'manifest_sha256':sys.argv[3],'images':m['images'],'tasks':m['tasks'],'credential_free':True})
    elif mode=='restore':restore(Path(sys.argv[2]),Path(sys.argv[3]),sys.argv[4],Path(sys.argv[5]) if len(sys.argv)>5 else None)
    else:raise ValueError('Unknown prepared handoff mode')
