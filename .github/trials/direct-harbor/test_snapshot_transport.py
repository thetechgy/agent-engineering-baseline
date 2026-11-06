"""Transport regression checks; signed APT verification is exercised in CI builds."""
import hashlib,importlib.util,io,json,tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('snapshot_transport',Path(__file__).with_name('prefetch-apt.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class SnapshotTransportTests(unittest.TestCase):
    def test_cached_and_remote_packages_have_identical_hash_bound_identity(self):
        suffix="/pool/main/a/a.deb' a.deb 8 SHA256:"+'1'*64
        remote="'https://snapshot.debian.org/archive/debian/20261103T000000Z"+suffix
        cached="'file:/var/lib/trial-snapshot/20261103T000000Z/debian"+suffix
        self.assertEqual(m.package_identity(remote),m.package_identity(cached))
        for value in (remote.replace('20261103','20261104'),cached.replace('debian/pool','other/pool'),remote.replace('a.deb 8','../a.deb 8')):
            with self.assertRaises(ValueError):m.package_identity(value)
    def test_transient_retries_bounded_and_hash_failure_not_retried(self):
        error=urllib.error.HTTPError('https://example.invalid',504,'fixture',{},None)
        with patch.object(m.urllib.request,'urlopen',side_effect=[error,error,io.BytesIO(b'bytes')]) as get,patch.object(m.time,'sleep'),patch('builtins.print'):
            self.assertEqual(m.download('https://example.invalid',8),b'bytes');self.assertEqual(get.call_count,3)
        with patch.object(m.urllib.request,'urlopen',side_effect=error) as get,patch.object(m.time,'sleep'),patch('builtins.print'):
            with self.assertRaises(urllib.error.HTTPError):m.download('https://example.invalid',8)
            self.assertEqual(get.call_count,3)
        with patch.object(m,'download',return_value=b'wrong') as get:
            with self.assertRaises(ValueError):m.checked('fixture',5,'0'*64)
            self.assertEqual(get.call_count,1)
    def test_local_bundle_missing_corrupt_and_incompatible_fail_without_network(self):
        payload=b'pinned synthetic index fixture'
        indexes={name:(len(payload),hashlib.sha256(payload).hexdigest(),entry[2]) for name,entry in m.INDEXES.items()}
        with tempfile.TemporaryDirectory() as temp,patch.object(m,'INDEXES',indexes),patch.object(m,'download',side_effect=AssertionError('network forbidden')):
            root=Path(temp);retained=root/'retained';retained.mkdir()
            for _,_,name in indexes.values():(retained/name).write_bytes(payload)
            bundle=root/'bundle';m.seed_bundle(retained,bundle,'a'*40)
            m.cache_indexes(bundle,root/'sources.list')
            first=bundle/next(iter(indexes));first.write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError,'snapshot_bundle_corrupt'):m.cache_indexes(bundle,root/'sources.list')
            first.unlink()
            with self.assertRaisesRegex(ValueError,'missing_or_extra'):m.validate_bundle(bundle)
            first.write_bytes(payload)
            manifest=bundle/'manifest.json';data=json.loads(manifest.read_text());data['snapshot']='other';manifest.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'incompatible'):m.validate_bundle(bundle)
            manifest.unlink()
            with self.assertRaisesRegex(ValueError,'snapshot_bundle_missing'):m.validate_bundle(bundle)

    def test_acquisition_keeps_completed_file_when_later_file_fails(self):
        payload=b'checked fixture';names=list(m.INDEXES)
        indexes={name:(len(payload),hashlib.sha256(payload).hexdigest(),entry[2]) for name,entry in m.INDEXES.items()}
        with tempfile.TemporaryDirectory() as temp,patch.object(m,'INDEXES',indexes),patch.object(m,'checked',side_effect=[payload,TimeoutError('fixture')]):
            root=Path(temp)/'bundle'
            with self.assertRaises(TimeoutError):m.seed_bundle(None,root,'a'*40)
            self.assertEqual((root/names[0]).read_bytes(),payload)
            self.assertFalse((root/'manifest.json').exists())

    def test_staging_retains_signatures_pins_and_runtime_source(self):
        import run as trial
        with tempfile.TemporaryDirectory() as temp:
            native,_=trial.stage(Path(temp)/'stage')
            for kind in ('environment','tests'):
                text=(native/'pester-002'/kind/'Dockerfile').read_text()
                self.assertIn('python3 /tmp/prefetch-apt.py indexes && rm -f',text)
                self.assertEqual(text.count('Dir::Etc::sourcelist=/tmp/trial-snapshot.list'),3)
                self.assertIn('https://snapshot.debian.org/archive/debian/20261103T000000Z/',text)
                self.assertIn('signed-by=/usr/share/keyrings/debian-archive-keyring.gpg',text)
                self.assertIn('Acquire::ForceHash=sha256',text)
                self.assertIn('--no-download install',text)
                self.assertNotIn('trusted=yes',text);self.assertNotIn('allow-unauthenticated',text)
                self.assertIn('/var/lib/trial-snapshot /tmp/trial-snapshot.list\n',text)
                first=text.index('apt-get -o Dir::Etc::sourcelist=')
                self.assertNotIn('rm -rf /var/lib/apt/lists/* /var/lib/trial-snapshot',text[:first])

if __name__=='__main__':unittest.main()
