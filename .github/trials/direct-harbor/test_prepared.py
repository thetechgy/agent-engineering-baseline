"""Focused credential-free transport fixtures; images are exercised in Actions."""
import hashlib,io,json,os,tarfile,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import prepared
WHO={'repository':'thetechgy/agent-engineering-baseline','branch':'refs/heads/trial/direct-harbor','commit':'a'*40,'run_id':'1','allocation_id':'fixture'}

def bundle(root,unsafe=False):
    root.mkdir();(root/'images.tar').write_bytes(b'synthetic Docker archive; never loaded by this test')
    data=b'unchanged UTF8 task bytes\r\n';name='../escape' if unsafe else 'tasks/current/instruction.md'
    with tarfile.open(root/'inputs.tar','w') as archive:
        info=tarfile.TarInfo(name);info.size=len(data);archive.addfile(info,io.BytesIO(data))
    manifest={'schema':3,'kernel_probe_reference':prepared.PROBE_REFERENCE,'experiment':prepared.experiment(),'expires_at':(prepared.datetime.now(prepared.timezone.utc)+prepared.timedelta(days=7)).isoformat(),'identity':WHO,'images':{k:'sha256:'+'1'*64 for k in prepared.TAGS+[prepared.PROBE_TAG,'harbor-prebuilt:harbor-docker-egress-control-sidecar--fixture']},
        'credentials':False,'running_containers':False,'authenticated_homes':False,
        'members':{name:{'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)}},
        'archives':{k:{'sha256':prepared.digest(root/k),'size':(root/k).stat().st_size} for k in ('images.tar','inputs.tar')}}
    prepared.write(root/'manifest.json',manifest);return prepared.digest(root/'manifest.json')

class PreparedTests(unittest.TestCase):
    def test_exact_archive_identity_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'bundle';sha=bundle(root)
            self.assertEqual(prepared.verify(root,sha,WHO)['identity'],WHO)
            with self.assertRaises(AssertionError):prepared.verify(root,'0'*64,WHO)
            with self.assertRaises(AssertionError):prepared.verify(root,sha,{**WHO,'run_id':'old'})
            (root/'images.tar').write_bytes(b'changed')
            with self.assertRaises(AssertionError):prepared.verify(root,sha,WHO)
    def test_traversal_rejected_even_with_matching_archive_digest(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'bundle';sha=bundle(root,True)
            with self.assertRaises(AssertionError):prepared.verify(root,sha,WHO)
    def test_changed_experiment_and_expired_images_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'bundle';sha=bundle(root)
            with patch.object(prepared,'experiment',return_value={'changed':True}):
                with self.assertRaisesRegex(AssertionError,'experiment inputs changed'):prepared.verify(root,sha,WHO)
            value=json.loads((root/'manifest.json').read_text());value['expires_at']='2020-01-01T00:00:00+00:00'
            prepared.write(root/'manifest.json',value)
            with self.assertRaisesRegex(AssertionError,'expired'):prepared.verify(root,prepared.digest(root/'manifest.json'),WHO)

    def test_report_and_allocation_metadata_do_not_change_experiment(self):
        original=prepared.experiment()
        read=Path.read_text
        def changed(path,*args,**kwargs):
            value=read(path,*args,**kwargs)
            if path.name=='launch.json':
                data=json.loads(value);data['allocation']={'id':'new-unarmed-allocation'};data['phase']='report'
                return json.dumps(data)
            return value
        with patch.object(Path,'read_text',changed):self.assertEqual(original,prepared.experiment())

    def test_cross_run_admission_rejects_changed_producer_or_artifact(self):
        source={'run_id':123,'commit':'a'*40,'artifact_id':456,'name':'prepared-images','artifact_digest':'sha256:'+'b'*64}
        run={'repository':{'full_name':prepared.REPOSITORY},'head_repository':{'full_name':prepared.REPOSITORY},
             'head_branch':'trial/direct-harbor','event':'push','run_attempt':1,'path':'.github/workflows/direct-harbor-trial.yml',
             'head_sha':source['commit'],'status':'completed','conclusion':'success'}
        artifact={'workflow_run':{'id':123,'head_sha':source['commit']},'name':source['name'],'expired':False,
                  'digest':source['artifact_digest'],'expires_at':'2099-01-01T00:00:00Z'}
        def check(r,a):
            with patch.object(prepared,'api',side_effect=[r,a]),patch.object(prepared.subprocess,'run'):
                return prepared.admit_source(source)
        self.assertEqual(check(run,artifact),artifact)
        for key,value in [('head_branch','main'),('event','pull_request'),('run_attempt',2),('head_sha','c'*40),('conclusion','failure')]:
            with self.assertRaises(AssertionError):check({**run,key:value},artifact)
        for key,value in [('name','unrelated'),('expired',True),('digest','sha256:'+'0'*64),('expires_at','2020-01-01T00:00:00Z')]:
            with self.assertRaises(AssertionError):check(run,{**artifact,key:value})
        with self.assertRaises(AssertionError):check({**run,'head_repository':{'full_name':'other/repo'}},artifact)

    def test_paths_relocate_without_changing_native_task_checksum(self):
        import shutil
        import run as trial
        from harbor.models.task.task import Task
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);native,_=trial.stage(root/'original',admission_diagnostics=True)
            source=native/'pester-002';destination=root/'other-runner/tasks/current'
            shutil.copytree(source,destination)
            self.assertEqual(Task(source).checksum,Task(destination).checksum)
            self.assertEqual(prepared.files(source),prepared.files(destination))
    def test_authenticated_environment_and_auth_files_are_excluded(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'NONSECRET_SENTINEL'}):
            with self.assertRaises(AssertionError):prepared.no_credentials()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'auth.json').write_text('{}')
            with self.assertRaises(AssertionError):prepared.files(root)

if __name__=='__main__':unittest.main()
