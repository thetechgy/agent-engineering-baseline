"""Bounded Docker tar reader and unconditional diagnostics; never extract image files."""
import hashlib,io,json,os,selectors,subprocess,tarfile,time,uuid
from pathlib import Path,PurePosixPath
from diagnostics import sanitize

ARCHIVE_LIMIT=64*1024**2
STDERR_LIMIT=8192

class DockerFailure(RuntimeError):pass

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2)+'\n');temporary.replace(path)

class DockerOperations:
    def __init__(self,path):
        self.path=path;self.data={'operations':[],'primary_failure':None,'cleanup_failures':[]};self.save()
    def save(self):write(self.path,self.data)
    def run(self,stage,args,*,timeout=30,limit=1024**2,cleanup=False):
        entry={'stage':stage,'command':[sanitize(a) for a in args],'exit_status':None,'stderr':'','stderr_truncated':False,'failure':None}
        self.data['operations'].append(entry);self.save();out=bytearray();err=bytearray();process=None;reason=None
        try:
            process=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            with selectors.DefaultSelector() as poll:
                poll.register(process.stdout,selectors.EVENT_READ,'stdout');poll.register(process.stderr,selectors.EVENT_READ,'stderr')
                until=time.monotonic()+timeout
                while poll.get_map():
                    if time.monotonic()>=until:raise TimeoutError('Docker operation timed out')
                    for key,_ in poll.select(min(0.2,max(0,until-time.monotonic()))):
                        chunk=os.read(key.fileobj.fileno(),65536)
                        if not chunk:poll.unregister(key.fileobj);continue
                        if key.data=='stdout':
                            if len(out)+len(chunk)>limit:raise ValueError('Docker stdout exceeded bounded limit')
                            out.extend(chunk)
                        else:
                            remaining=STDERR_LIMIT-len(err);err.extend(chunk[:remaining])
                            if len(chunk)>remaining:entry['stderr_truncated']=True
                process.wait(timeout=max(0.1,until-time.monotonic()))
        except Exception as exc:
            reason={'type':type(exc).__name__,'message':sanitize(str(exc))}
        finally:
            if process is not None:
                if process.poll() is None:process.kill()
                process.wait(timeout=5);entry['exit_status']=process.returncode
                process.stdout.close();process.stderr.close()
            entry['stderr']=sanitize(err.decode('utf-8','replace'))
            entry['stdout_bytes']=len(out)
            if reason or entry['exit_status']!=0:
                entry['failure']=reason or {'type':'nonzero_exit','message':'Docker operation failed'}
                if cleanup:self.data['cleanup_failures'].append(dict(entry))
                elif self.data['primary_failure'] is None:self.data['primary_failure']=dict(entry)
            self.save()
        if entry['failure']:raise DockerFailure(stage+': '+entry['failure']['type'])
        return bytes(out)

def read_archive(data,source,expected,*,exact=True,readonly=False):
    if len(data)>ARCHIVE_LIMIT:raise ValueError('archive_size_limit')
    prefix=PurePosixPath(source).name;files={};modes={};names=set();total=0
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:') as archive:
        for member in archive:
            path=PurePosixPath(member.name)
            if member.name.startswith('/') or '\\' in member.name or '..' in path.parts or not path.parts or path.parts[0]!=prefix:
                raise ValueError('unsafe_archive_path')
            canonical=path.as_posix()
            if canonical in names or len(names)>=3000:raise ValueError('duplicate_or_excess_archive_members')
            names.add(canonical)
            if not (member.isfile() or member.isdir()):raise ValueError('unsupported_archive_member_type')
            if readonly and member.mode&0o222:raise ValueError('writable_input_permission')
            relative=PurePosixPath(*path.parts[1:]).as_posix();modes[relative]=member.mode&0o7777
            if member.isdir():continue
            if relative=='.' or member.size<0 or member.size>16*1024**2:raise ValueError('invalid_file_size')
            total+=member.size
            if total>32*1024**2:raise ValueError('content_size_limit')
            stream=archive.extractfile(member);content=stream.read(member.size+1)
            if len(content)!=member.size:raise ValueError('truncated_file')
            files[relative]={'sha256':hashlib.sha256(content).hexdigest(),'size':len(content)}
    if exact and set(files)!=set(expected):raise ValueError('content_members_mismatch')
    for name,identity in expected.items():
        if files.get(name)!=identity:raise ValueError('content_identity_mismatch: '+name)
    return {'verified_files':expected,'archive_files':len(files),'permissions':modes,'tar_bytes':len(data),'filesystem_extraction':False}

def inspect_image(image,source,expected,destination,*,exact=True,readonly=False,inject_cleanup_failure=False):
    """Create a stopped, network-free container, read its tar stream, always remove it."""
    record={'passed':False,'image':image,'source':source,'primary_failure':None,'cleanup_failures':[],'container_removed':False}
    operations=DockerOperations(destination.with_name(destination.stem+'-docker.json'))
    name='image-content-'+uuid.uuid4().hex;created=False;failure=None
    try:
        operations.run('inspection_create',['docker','create','--name',name,'--network','none','--cap-drop','ALL','--security-opt','no-new-privileges:true','--entrypoint','/bin/true',image]);created=True
        raw=operations.run('content_tar_export',['docker','cp',name+':'+source,'-'],limit=ARCHIVE_LIMIT)
        record['content']=read_archive(raw,source,expected,exact=exact,readonly=readonly)
        record['passed']=True
    except Exception as exc:
        failure=exc;record['primary_failure']=operations.data['primary_failure'] or {'stage':'content_validation','type':type(exc).__name__,'message':sanitize(str(exc))}
    finally:
        if created:
            try:
                if inject_cleanup_failure:
                    operations.run('injected_cleanup',['docker','rm','--intentionally-invalid-option',name],cleanup=True)
                operations.run('inspection_remove',['docker','rm','--force',name],cleanup=True);record['container_removed']=True
            except Exception as exc:
                if failure is None:failure=exc
                # Recover only this known disposable container; preserve the cleanup failure.
                try:
                    operations.run('inspection_remove_recovery',['docker','rm','--force',name],cleanup=True);record['container_removed']=True
                except Exception:pass
        record['cleanup_failures']=operations.data['cleanup_failures']
        record['passed']=record['passed'] and record['container_removed'] and not record['cleanup_failures']
        write(destination,record)
    if failure:raise failure
    if not record['passed']:raise DockerFailure('Inspection cleanup unconfirmed')
    return record
