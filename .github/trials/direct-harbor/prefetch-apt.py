"""Cache the fixed signed snapshot indexes, then fetch hash-selected packages.

APT still authenticates InRelease and validates index/package hashes. Local index
transport avoids repeated CDN negotiation; it does not create a rolling source.
"""
import concurrent.futures,hashlib,json,re,shlex,sys,time,urllib.error,urllib.request
from pathlib import Path

SNAPSHOT='20261103T000000Z'
CACHE=Path('/var/lib/trial-snapshot')/SNAPSHOT
RELEASES={
    'debian':('trixie','0584fba32e13e0ab8285fb16c27adea1ec03a73669c18702821094fd6ca86675'),
    'debian-security':('trixie-security','01590ffbf20362d6138369dbf543ee42d3d8ec62589d31cfb93a085afcad4f3c'),
}

def download(url,limit):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url,timeout=30) as response:data=response.read(limit+1)
            if len(data)>limit:raise ValueError('Snapshot response exceeds declared bound')
            return data
        except (urllib.error.URLError,TimeoutError) as exc:
            if isinstance(exc,urllib.error.HTTPError) and exc.code not in (429,500,502,503,504):raise
            if attempt==2:raise
            print('Transient snapshot transport failure; bounded retry '+str(attempt+2)+'/3',flush=True)
            time.sleep(2**attempt)

def checked(url,size,sha256):
    data=download(url,size)
    if len(data)!=size or hashlib.sha256(data).hexdigest()!=sha256:
        raise ValueError('Snapshot content identity mismatch')
    return data

# Identities copied from the reviewed snapshot-recovery.json, never learned on fetch.
INDEXES={
    'debian/dists/trixie/InRelease': (140421, RELEASES['debian'][1], 'InRelease'),
    'debian/dists/trixie/main/binary-amd64/Packages.xz': (9678380, '7778d3e3f303b7ddb8ce0fe7c8d57473a076c6bf2e8f241f75421d2396352498', 'main_binary-amd64_Packages.xz'),
    'debian-security/dists/trixie-security/InRelease': (43409, RELEASES['debian-security'][1], 'security_InRelease'),
    'debian-security/dists/trixie-security/main/binary-amd64/Packages.xz': (297148, '38ca814a70dea1f035fd078c08b15b9a93f23b9605f3115a7791f30e62a6bf27', 'security_main_binary-amd64_Packages.xz'),
}

def index_entries():
    return {name: {'size':size, 'sha256':sha, 'url':'https://snapshot.debian.org/archive/'+name.split('/',1)[0]+'/'+SNAPSHOT+'/'+name.split('/',1)[1]}
            for name,(size,sha,_) in INDEXES.items()}

def validate_bundle(root):
    if not (root/'manifest.json').is_file():raise ValueError('snapshot_bundle_missing: manifest.json')
    manifest=json.loads((root/'manifest.json').read_text())
    if (manifest.get('schema')!=1 or manifest.get('snapshot')!=SNAPSHOT or manifest.get('files')!=index_entries()
            or not re.fullmatch('[a-f0-9]{40}',manifest.get('source_commit',''))):
        raise ValueError('snapshot_bundle_incompatible')
    names=set()
    for path in root.rglob('*'):
        if path.is_symlink():raise ValueError('snapshot_bundle_unsafe_member')
        if path.is_file():names.add(path.relative_to(root).as_posix())
    if names!=set(INDEXES)|{'manifest.json'}:raise ValueError('snapshot_bundle_missing_or_extra_member')
    for name,(size,sha,_) in INDEXES.items():
        path=root/name
        if path.stat().st_nlink!=1 or path.stat().st_size!=size or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
            raise ValueError('snapshot_bundle_corrupt: '+index_entries()[name]['url'])
    return manifest

def seed_bundle(retained,root,commit):
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('Invalid source commit')
    root.mkdir(parents=True,exist_ok=True)
    for name,(size,sha,old_name) in INDEXES.items():
        destination=root/name
        if destination.exists():data=destination.read_bytes()
        elif retained is not None:data=(retained/old_name).read_bytes()
        else:data=checked(index_entries()[name]['url'],size,sha)
        if len(data)!=size or hashlib.sha256(data).hexdigest()!=sha:raise ValueError('snapshot_bundle_corrupt: '+name)
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(data)  # Keep each success even if a later acquisition fails.
    (root/'manifest.json').write_text(json.dumps({'schema':1,'snapshot':SNAPSHOT,'source_commit':commit,'files':index_entries()},indent=2)+'\n')
    return validate_bundle(root)

def cache_indexes(root=CACHE,sources=Path('/tmp/trial-snapshot.list')):
    validate_bundle(root)  # Deliberately no network fallback in the image build.
    lines=[]
    for archive,(suite,release_hash) in RELEASES.items():
        lines.append('deb [check-valid-until=no signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] file:'+str(root/archive)+' '+suite+' main')
        print('Verified retained '+archive+' indexes; APT signature verification follows',flush=True)
    sources.write_text('\n'.join(lines)+'\n')

def package_identity(line):
    uri,filename,size,digest=shlex.split(line)
    remote=re.fullmatch(r'https://snapshot.debian.org/archive/(debian|debian-security)/'+SNAPSHOT+r'/(pool/[^\s]+)',uri)
    cached=re.fullmatch(r'file:'+re.escape(str(CACHE))+r'/(debian|debian-security)/(pool/[^\s]+)',uri)
    match=remote or cached
    if not match or Path(filename).name!=filename or not re.fullmatch(r'SHA256:[0-9a-f]{64}',digest):
        raise ValueError('Unexpected snapshot package identity')
    size=int(size)
    if not 0<size<256*1024**2:raise ValueError('Invalid package size')
    url='https://deb.debian.org/'+match[1]+'/'+match[2]
    return url,filename,size,digest.removeprefix('SHA256:')

def fetch(line):
    url,filename,size,digest=package_identity(line)
    try:data=checked(url,size,digest)
    except Exception as exc:
        print(json.dumps({'stage':'package_download','url':url,'failure_type':type(exc).__name__,'http_status':getattr(exc,'code',None)}),flush=True)
        raise
    (Path('/var/cache/apt/archives')/filename).write_bytes(data)
    print('Verified snapshot package '+filename,flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['indexes']:cache_indexes()
    elif sys.argv[1:2]==['validate']:print(json.dumps(validate_bundle(Path(sys.argv[2]))))
    elif sys.argv[1:2]==['seed']:seed_bundle(Path(sys.argv[2]) if sys.argv[2]!='-' else None,Path(sys.argv[3]),sys.argv[4])
    else:
        if sys.argv[1:]:raise ValueError('Unexpected transport mode')
        lines=[s for s in Path('/tmp/apt-uris').read_text().splitlines() if s.startswith("'")]
        if not lines:raise ValueError('No snapshot package plan')
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(fetch,lines))
