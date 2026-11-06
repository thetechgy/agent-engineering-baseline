"""Cache the fixed signed snapshot indexes, then fetch hash-selected packages.

APT still authenticates InRelease and validates index/package hashes. Local index
transport avoids repeated CDN negotiation; it does not create a rolling source.
"""
import concurrent.futures,hashlib,re,shlex,sys,time,urllib.error,urllib.request
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

def cache_indexes(root=CACHE,sources=Path('/tmp/trial-snapshot.list')):
    lines=[]
    for archive,(suite,release_hash) in RELEASES.items():
        base='https://snapshot.debian.org/archive/'+archive+'/'+SNAPSHOT+'/dists/'+suite+'/'
        release=download(base+'InRelease',256*1024)
        if hashlib.sha256(release).hexdigest()!=release_hash:raise ValueError('Pinned InRelease bytes changed')
        relative='main/binary-amd64/Packages.xz'
        entries=[line.split() for line in release.decode().split('SHA256:\n',1)[1].splitlines() if line.endswith(' '+relative)]
        if len(entries)!=1:raise ValueError('Missing unique compressed-index identity')
        digest,size,_=entries[0];size=int(size)
        if not re.fullmatch('[a-f0-9]{64}',digest) or not 0<size<32*1024**2:raise ValueError('Invalid index identity')
        data=checked(base+relative,size,digest)
        destination=root/archive/'dists'/suite;destination.mkdir(parents=True,exist_ok=True)
        (destination/'InRelease').write_bytes(release)
        index=destination/relative;index.parent.mkdir(parents=True,exist_ok=True);index.write_bytes(data)
        lines.append('deb [check-valid-until=no signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] file:'+str(root/archive)+' '+suite+' main')
        print('Cached '+archive+' InRelease '+release_hash+' and Packages.xz '+digest+'; APT signature verification follows',flush=True)
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
    data=checked(url,size,digest)
    (Path('/var/cache/apt/archives')/filename).write_bytes(data)
    print('Verified snapshot package '+filename,flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['indexes']:cache_indexes()
    else:
        if sys.argv[1:]:raise ValueError('Unexpected transport mode')
        lines=[s for s in Path('/tmp/apt-uris').read_text().splitlines() if s.startswith("'")]
        if not lines:raise ValueError('No snapshot package plan')
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(fetch,lines))
