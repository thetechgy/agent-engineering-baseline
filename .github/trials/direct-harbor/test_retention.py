"""Synthetic publication controls, never task grades or inference."""
import json,os,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import retention as r

IDENTITY={'allocation_id':'fixture','reservation_id':'fixture/current/7','attempt':7,'variant':'current','commit':'abc','run_id':'123'}
class RetentionTests(unittest.TestCase):
    def test_exact_bytes_identity_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source';data=b"# synthetic\r\nDescribe 'byte check' { }\r\n";source.write_bytes(data)
            result=r.stage(source,root/'bundle',IDENTITY)
            self.assertEqual(result['status'],'ready')
            shutil.copytree(root/'bundle',root/'download')
            self.assertEqual(r.verify_download(root/'bundle',root/'download',IDENTITY)['sha256'],result['sha256'])
            with self.assertRaises(AssertionError):r.verify_download(root/'bundle',root/'download',{**IDENTITY,'reservation_id':'wrong'})
            (root/'download'/r.NAME).write_bytes(data.replace(b'\r\n',b'\n'))
            with self.assertRaises(AssertionError):r.verify_download(root/'bundle',root/'download',IDENTITY)
    def test_missing_unsafe_sensitive_and_protected_never_staged(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source';bundle=root/'bundle'
            self.assertEqual(r.stage(source,bundle,IDENTITY)['status'],'missing')
            secret='SENTINEL_NOT_A_CREDENTIAL_123456789'
            protected=b"# synthetic protected fixture content only\nDescribe 'protected' {}"
            for data,reason in [(secret.encode(),'credential_value'),(r.base64.b64encode(secret.encode()),'credential_value'),(b'Authorization: Bearer abc','credential_pattern'),(protected,'protected_fixture_content'),(b'PESTER_VERIFIER_ONLY_x','protected_evidence_marker'),(b'\xff','unscannable_utf8')]:
                source.write_bytes(data);result=r.stage(source,bundle,IDENTITY,secrets=[secret],protected=[protected])
                self.assertEqual(result['reason'],reason);self.assertFalse(bundle.exists());self.assertNotIn(secret,json.dumps(result))
            source.unlink();source.symlink_to('missing')
            self.assertEqual(r.stage(source,bundle,IDENTITY)['status'],'blocked')
            source.unlink();source.write_bytes(b'safe');os.link(source,root/'hardlink')
            self.assertEqual(r.stage(source,bundle,IDENTITY)['status'],'blocked')
    def test_hash_binding_and_failure_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'GITHUB_SHA':'abc','GITHUB_RUN_ID':'123'}):
            root=Path(temp);source=root/'source';source.write_bytes(b'# synthetic safe bytes')
            self.assertEqual(r.stage(source,root/'unused',IDENTITY,observations={'host':{'sha256':'wrong'}})['reason'],'boundary_hash_mismatch')
            result=r.stage(source,root/'submissions/current',IDENTITY)
            r.write(root/'public/current/attempt.json',{'submission_retention':result})
            shutil.copytree(root/'submissions/current',root/'download')
            (root/'download'/r.NAME).write_bytes(b'changed')
            with self.assertRaises(AssertionError):r.publish(root,'current',root/'download','456')
            self.assertEqual(json.loads((root/'public/current/attempt.json').read_text())['submission_retention']['status'],'publication_failed')

if __name__=='__main__':unittest.main()
