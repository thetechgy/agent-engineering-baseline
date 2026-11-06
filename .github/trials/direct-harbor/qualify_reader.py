"""Small real-Docker qualification; no Harbor, task candidate or model credentials."""
import hashlib,io,json,os,shutil,sys,tarfile,uuid
from pathlib import Path
from image_contents import DockerOperations,inspect_image,read_archive,write
IMAGE='alpine:3.23.4@sha256:5b10f432ef3da1b8d4c7eb6c487f2f5a8f096bc91145e68878dd4a5019afde11'

def main(root):
    assert not any(os.environ.get(k) for k in ('OPENAI_API_KEY','CODEX_API_KEY','CODEX_AUTH_JSON_PATH','CODEX_FORCE_AUTH_JSON'))
    root.mkdir(parents=True,exist_ok=False);public=root/'public';public.mkdir();ops=DockerOperations(public/'fixture-docker.json')
    tag='direct-harbor-reader-fixture:'+uuid.uuid4().hex;record={'passed':False,'inference':False,'controls':[],'fixture_removed':False}
    context=root/'context';context.mkdir();(context/'Dockerfile').write_text('FROM '+IMAGE+'\nRUN mkdir -p /fixture/input/nested && printf expected > /fixture/input/README.md && printf second > /fixture/input/nested/data.txt && chmod -R a-w /fixture/input\n')
    expected={name:{'sha256':hashlib.sha256(value).hexdigest(),'size':len(value)} for name,value in [('README.md',b'expected'),('nested/data.txt',b'second')]}
    try:
        ops.run('fixture_pull',['docker','pull',IMAGE],timeout=120)
        ops.run('fixture_build',['docker','build','--network=none','--pull=false','-t',tag,str(context)],timeout=120)
        controls=[('readonly_success','/fixture/input',expected,False,None),('missing_source','/fixture/missing',expected,False,'content_tar_export'),('missing_content','/fixture/input',{**expected,'missing.txt':expected['README.md']},False,'content_validation'),('changed_content','/fixture/input',{**expected,'README.md':{'size':8,'sha256':'0'*64}},False,'content_validation'),('primary_and_cleanup_failure','/fixture/missing',expected,True,'content_tar_export')]
        for label,source,wanted,inject,error_stage in controls:
            destination=public/(label+'.json')
            try:inspect_image(tag,source,wanted,destination,readonly=True,inject_cleanup_failure=inject)
            except Exception:
                if error_stage is None:raise
            value=json.loads(destination.read_text());assert value['container_removed']
            if error_stage:
                assert not value['passed'] and value['primary_failure']['stage']==error_stage
                if error_stage=='content_tar_export':assert value['primary_failure']['exit_status']!=0 and value['primary_failure']['stderr']
            else:assert value['passed'] and value['content']['filesystem_extraction'] is False
            assert bool(value['cleanup_failures'])==inject
            record['controls'].append({'control':label,'expected_outcome_matched':True,'container_removed':True,'primary_failure':value['primary_failure'],'cleanup_failures':value['cleanup_failures']})
        # Exercise archive-policy rejection independently of Docker's normal archive producer.
        for label,name,kind,mode in [('traversal','input/../escape',tarfile.REGTYPE,0o444),('symlink','input/link',tarfile.SYMTYPE,0o444),('writable','input/a',tarfile.REGTYPE,0o644)]:
            buffer=io.BytesIO()
            with tarfile.open(fileobj=buffer,mode='w') as archive:
                member=tarfile.TarInfo(name);member.type=kind;member.mode=mode;member.size=0;member.linkname='target' if kind==tarfile.SYMTYPE else '';archive.addfile(member)
            try:read_archive(buffer.getvalue(),'/fixture/input',{},readonly=True)
            except ValueError:record['controls'].append({'control':label,'expected_outcome_matched':True})
            else:raise AssertionError(label+' unexpectedly accepted')
        # Attempt the previous approach, retaining its exact native diagnostic.
        name='reader-legacy-'+uuid.uuid4().hex;created=False
        try:
            ops.run('legacy_create',['docker','create','--name',name,'--network','none','--entrypoint','/bin/true',tag]);created=True
            try:
                ops.run('legacy_directory_copy',['docker','cp',name+':/fixture/input',str(root/'legacy-copy')])
                record['legacy_directory_copy']='succeeded; historical failure not reproduced'
            except Exception:
                record['legacy_directory_copy']='failed; bounded Docker diagnostic retained; historical cause still cannot be proven'
        finally:
            if created:ops.run('legacy_remove',['docker','rm','--force',name],cleanup=True)
        record['passed']=True
    except Exception as exc:
        from diagnostics import sanitize
        record['failure']={'type':type(exc).__name__,'message':sanitize(str(exc))}
    finally:
        try:
            record['remaining_containers']=ops.run('fixture_disposal_audit',['docker','ps','--all','--filter','ancestor='+tag,'--quiet']).decode().split()
            record['passed']=record['passed'] and not record['remaining_containers']
        except Exception:record['passed']=False
        try:ops.run('fixture_image_remove',['docker','image','rm','--force',tag],cleanup=True);record['fixture_removed']=True
        except Exception:record['passed']=False
        write(public/'reader-qualification.json',record)
    print(json.dumps(record));return 0 if record['passed'] else 1
if __name__=='__main__':raise SystemExit(main(Path(sys.argv[1]).resolve()))
