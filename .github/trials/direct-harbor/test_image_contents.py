"""Bound/error diagnostics use real processes; Docker behavior has its own CI fixture."""
import io,json,sys,tarfile,tempfile,unittest
from pathlib import Path
from image_contents import DockerOperations,DockerFailure,read_archive

class ReaderTests(unittest.TestCase):
    def test_timeout_launch_and_output_limits_are_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name,args,kwargs,kind in [('timeout',[sys.executable,'-c','import time;time.sleep(10)'],{'timeout':0.1},'TimeoutError'),('launch',['/nonexistent/trial-docker-fixture'],{},'FileNotFoundError'),('output',[sys.executable,'-c','print("a"*10000)'],{'limit':100},'ValueError')]:
                path=Path(tmp)/(name+'.json');ops=DockerOperations(path)
                with self.assertRaises(DockerFailure):ops.run(name,args,**kwargs)
                value=json.loads(path.read_text());self.assertEqual(value['primary_failure']['failure']['type'],kind)
                self.assertIsNone(value['operations'][0]['exit_status']) if name=='launch' else self.assertIsNotNone(value['operations'][0]['exit_status'])
    def test_cleanup_failure_does_not_replace_primary_and_stderr_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            ops=DockerOperations(Path(tmp)/'operations.json')
            for name,cleanup in [('primary',False),('cleanup',True)]:
                with self.assertRaises(DockerFailure):ops.run(name,[sys.executable,'-c','import sys;sys.stderr.write("x"*20000);sys.exit(3)'],cleanup=cleanup)
            self.assertEqual(ops.data['primary_failure']['stage'],'primary');self.assertEqual(len(ops.data['cleanup_failures']),1)
            self.assertLessEqual(len(ops.data['primary_failure']['stderr']),8192);self.assertTrue(ops.data['primary_failure']['stderr_truncated'])
    def test_duplicate_and_special_archive_members_are_rejected(self):
        for kind in (tarfile.LNKTYPE,tarfile.FIFOTYPE):
            data=io.BytesIO()
            with tarfile.open(fileobj=data,mode='w') as archive:
                member=tarfile.TarInfo('input/item');member.type=kind;member.linkname='input/other';archive.addfile(member)
            with self.assertRaisesRegex(ValueError,'member_type'):read_archive(data.getvalue(),'/input',{})
        data=io.BytesIO()
        with tarfile.open(fileobj=data,mode='w') as archive:
            for _ in range(2):archive.addfile(tarfile.TarInfo('input/same'))
        with self.assertRaisesRegex(ValueError,'duplicate'):read_archive(data.getvalue(),'/input',{})
if __name__=='__main__':unittest.main()
