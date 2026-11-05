"""Bounded, content-free metadata for one declared artifact; not a grader."""
import hashlib,json,os,stat,sys
from pathlib import Path

OUTPUT='/workspace/output/Subject.Tests.ps1'
LIMIT=64*1024

def observe(path):
    path=Path(path)
    value={'exists':None,'type':None,'size':None,'uid':None,'gid':None,'mode':None,'sha256':None}
    try:
        info=path.lstat()
        value.update(exists=True,size=info.st_size,uid=info.st_uid,gid=info.st_gid,mode=oct(stat.S_IMODE(info.st_mode)),links=info.st_nlink)
        value['type']=('symlink' if stat.S_ISLNK(info.st_mode) else 'file' if stat.S_ISREG(info.st_mode) else 'directory' if stat.S_ISDIR(info.st_mode) else 'special')
        if value['type']=='file' and info.st_size<=LIMIT and all(not p.is_symlink() for p in path.parents):
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            try:
                data=os.read(fd,LIMIT+1)
                if len(data)<=LIMIT:value['sha256']=hashlib.sha256(data).hexdigest()
            finally:os.close(fd)
    except FileNotFoundError:value.update(exists=False,observation='missing')
    except PermissionError:value['observation']='permission_denied'
    except OSError:value['observation']='io_error'
    return value

def classify(agent,collection,host,verifier,outcome,*,environment_ok,completed):
    """Keep task completion, transport, admission and mutation denominators distinct."""
    result={'classification':'missing_evidence','task_completion_measured':False,'task_completed':None,'correctness_measured':False}
    transferred=(collection.get('status')=='ok' and host.get('sha256') is not None and host.get('sha256')==verifier.get('sha256'))
    # The caller supplies completed, Harbor-valid grades independently of agent status.
    if transferred and outcome.get('classification') in ('passed','failed'):
        return dict(result,classification='graded_'+outcome['classification'],task_completion_measured=True,task_completed=True,correctness_measured=True)
    if outcome.get('classification')=='unsupported':
        return dict(result,classification='unsupported_submission')
    if not environment_ok or not completed:return result
    if agent.get('exists') is False and host.get('exists') is False and verifier.get('exists') is False and outcome.get('admission_reason')=='missing':
        return dict(result,classification='missing_deliverable',task_completion_measured=True,task_completed=False)
    if agent.get('exists') is True and (collection.get('status') in ('failed','skipped') or (collection.get('status')=='ok' and host.get('exists') is False)):
        return dict(result,classification='collection_failure')
    if collection.get('status')=='ok' and host.get('exists') is True:
        if verifier.get('exists') is not True or (host.get('sha256') and host['sha256']!=verifier.get('sha256')):
            return dict(result,classification='transfer_failure')
        if outcome.get('classification')=='invalid' and outcome.get('admission_reason') not in (None,'missing'):
            return dict(result,classification='rejected_output',task_completion_measured=True,task_completed=False)
    return result

if __name__=='__main__':
    destination=Path(sys.argv[2]);destination.parent.mkdir(parents=True,exist_ok=True)
    value={'artifact':observe(sys.argv[1]),'observer_uid':os.getuid(),'observer_gid':os.getgid(),'cwd':os.getcwd()}
    temporary=destination.with_suffix('.tmp');temporary.write_text(json.dumps(value));temporary.replace(destination)
