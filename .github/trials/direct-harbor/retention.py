"""Publish only the explicitly authorized deliverable, unchanged; never execute it."""
import base64,hashlib,json,os,re,stat,sys
from pathlib import Path
from urllib.parse import quote
from artifact_state import OUTPUT,LIMIT,observe

NAME=Path(OUTPUT).name
ROOT=Path(__file__).resolve().parents[3]
IDENTITY=('allocation_id','reservation_id','attempt','variant','commit','run_id')

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')

def protected_contents():
    support=ROOT/'.github/evals/powershell-pester-6/support'
    paths=list((support/'qualification').rglob('*'))
    paths += [p for p in (support/'cases').rglob('*') if 'reference' in p.parts or 'mutants' in p.parts]
    return [p.read_bytes() for p in paths if p.is_file()]

def check_content(data,secrets,protected):
    try:text=data.decode('utf-8')
    except UnicodeDecodeError:return 'unscannable_utf8'
    for secret in secrets:
        if not secret:continue
        raw=secret.encode()
        if any(v in data for v in (raw,base64.b64encode(raw),raw.hex().encode(),quote(secret,safe='').encode())):
            return 'credential_value'
    if re.search(r'(?i)(?:sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|authorization\s*[:=]\s*[\x22\x27]?\s*(?:bearer|basic)\s+\S+)',text):
        return 'credential_pattern'
    if 'PESTER_VERIFIER_ONLY_' in text:return 'protected_evidence_marker'
    normalized=re.sub(rb'\s+',b'',data)
    for content in protected:
        normalized_protected=re.sub(rb'\s+',b'',content)
        if len(normalized_protected)>=32 and normalized_protected in normalized:return 'protected_fixture_content'
    return None

def stage(source,bundle,identity,*,secrets=(),protected=(),observations=None,kind='agent_submission'):
    """Closed publication boundary; a rejected submission can still be retained safely."""
    observation=observe(source)
    result={'status':'blocked','source':OUTPUT,'kind':kind,'identity':identity,'source_metadata':observation,
            'exact_bytes':False,'artifact_url':None,'publication_verified':False}
    if observation['exists'] is False:return dict(result,status='missing',reason='no_declared_deliverable')
    if observation['type']!='file' or observation.get('links')!=1 or not observation['sha256']:
        return dict(result,reason='unsafe_or_unreadable_file')
    fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);data=os.read(fd,LIMIT+1);after=os.fstat(fd)
    finally:os.close(fd)
    digest=hashlib.sha256(data).hexdigest()
    if not stat.S_ISREG(before.st_mode) or before!=after or len(data)>LIMIT or digest!=observation['sha256']:
        return dict(result,reason='source_changed_or_excessive')
    hashes={name:value.get('sha256') for name,value in (observations or {}).items()}
    if any(value and value!=digest for value in hashes.values()):return dict(result,reason='boundary_hash_mismatch')
    reason=check_content(data,secrets,protected)
    if reason:return dict(result,reason=reason)
    assert not bundle.exists(), 'No overwrite or implicit republication'
    bundle.mkdir(parents=True)
    with (bundle/NAME).open('xb') as stream:stream.write(data)
    metadata={'kind':kind,'identity':identity,'declared_output':OUTPUT,'sha256':digest,'size':len(data),
              'boundary_sha256':hashes,'checks':{'regular_single_link':True,'credential_scan':'passed','protected_content_scan':'passed'},
              'content_policy':'Exact declared bytes only. Bounded credential and protected-content checks are not a general DLP proof.'}
    write(bundle/'metadata.json',metadata)
    return dict(result,status='ready',reason=None,sha256=digest,size=len(data),exact_bytes=True)

def verify_download(bundle,download,identity):
    assert {p.name for p in download.iterdir()}=={NAME,'metadata.json'}, 'Unexpected downloaded members'
    original=json.loads((bundle/'metadata.json').read_text())
    metadata=json.loads((download/'metadata.json').read_text())
    assert metadata==original and metadata['identity']==identity, 'Identity or metadata mismatch'
    state=observe(download/NAME)
    assert state['type']=='file' and state['links']==1 and state['size']==metadata['size'] and state['sha256']==metadata['sha256'], 'Downloaded bytes differ'
    assert (bundle/NAME).read_bytes()==(download/NAME).read_bytes(), 'Exact-byte mismatch'
    return metadata

def publish(root,variant,download,artifact_id):
    path=root/'public'/variant/'attempt.json';record=json.loads(path.read_text())
    retention=record['submission_retention']
    assert retention['status']=='ready'
    identity=retention['identity']
    try:
        assert str(identity['run_id'])==os.environ['GITHUB_RUN_ID'] and identity['commit']==os.environ['GITHUB_SHA']
        assert re.fullmatch(r'[0-9]+',artifact_id)
        verify_download(root/'submissions'/variant,download,identity)
        retention.update(status='published_verified',publication_verified=True,artifact_id=artifact_id,
            artifact_url='https://github.com/thetechgy/agent-engineering-baseline/actions/runs/'+str(identity['run_id'])+'/artifacts/'+artifact_id)
    except Exception:
        retention.update(status='publication_failed',publication_verified=False,reason='download_or_identity_verification_failed')
        raise
    finally:write(path,record)

def fixture(root):
    assert not any(os.environ.get(k) for k in ('OPENAI_API_KEY','CODEX_API_KEY'))
    source=root/'producer'/NAME;source.parent.mkdir(parents=True)
    source.write_bytes(b"# Synthetic retention fixture; never executed.\r\nDescribe 'byte preservation' { }\r\n")
    identity={'allocation_id':'credential-free-retention','reservation_id':'none','attempt':None,'variant':'fixture',
              'commit':os.environ['GITHUB_SHA'],'run_id':os.environ['GITHUB_RUN_ID']}
    result=stage(source,root/'bundle',identity,protected=protected_contents(),kind='credential_free_retention_fixture')
    assert result['status']=='ready'
    write(root/'proof.json',result)

def fixture_verify(root,download):
    proof=json.loads((root/'proof.json').read_text())
    verify_download(root/'bundle',download,proof['identity'])
    proof.update(status='published_verified',publication_verified=True,paid_attempt=False,inference=False)
    write(root/'proof.json',proof)
    print(json.dumps(proof))

if __name__=='__main__':
    mode=sys.argv[1];root=Path(sys.argv[2])
    if mode=='fixture':fixture(root)
    elif mode=='fixture-verify':fixture_verify(root,Path(sys.argv[3]))
    elif mode=='publish':publish(root,sys.argv[3],Path(sys.argv[4]),sys.argv[5])
    else:raise ValueError('Unknown retention mode')
