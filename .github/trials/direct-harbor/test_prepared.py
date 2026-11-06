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
    manifest={'identity':WHO,'images':{k:'sha256:'+'1'*64 for k in prepared.TAGS+['harbor-prebuilt:harbor-docker-egress-control-sidecar--fixture']},
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
