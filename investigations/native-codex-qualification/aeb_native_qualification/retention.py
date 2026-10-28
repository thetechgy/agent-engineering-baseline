"""Exclusive publication into an agent-writable log mount; no host symlink writes."""
import hashlib,os,pathlib,tempfile

def retain(logs_dir,name,raw):
    if name not in ('qualification-setup.json','native-capture.json'):
        raise ValueError('unsupported retained evidence name')
    data=raw.encode();digest=hashlib.sha256(data).hexdigest()
    # This private host copy is outside every agent bind mount. This experimental
    # path is returned only to the trusted caller, never to evaluated processes.
    fd,path=tempfile.mkstemp(prefix='aeb-native-private-',suffix='.json')
    with os.fdopen(fd,'wb') as file:file.write(data)
    directory=os.open(logs_dir,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory)
        with os.fdopen(fd,'wb') as file:file.write(data)
    finally:os.close(directory)
    return {'sha256':digest,'size':len(data),'private_host_copy':str(pathlib.Path(path))}
