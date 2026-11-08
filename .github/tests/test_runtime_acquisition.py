"""Real local HTTPS failures through the build installer; never model/provider calls."""
import contextlib
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import shutil
import signal
import ssl
import subprocess
import tarfile
import tempfile
import threading
import time
import sys
import types
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))
from codex_pilot_contract import runtime_installer_bytes


def installer():
    value = types.ModuleType('runtime_installer')
    exec(compile(runtime_installer_bytes(), '<staged install-runtime.py>', 'exec'), value.__dict__)
    return value


@unittest.skipUnless(hasattr(signal, 'setitimer') and shutil.which('openssl'), 'Linux build signal timer and OpenSSL required')
class AcquisitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='aeb-runtime-tls-')
        cls.root = Path(cls.temporary.name)
        cls.cert, cls.key = cls.root / 'cert.pem', cls.root / 'key.pem'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                        '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1',
                        '-keyout', str(cls.key), '-out', str(cls.cert)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        owner = cls
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                path = urlsplit(self.path).path
                with owner.lock:
                    owner.calls.append(path)
                    plans = owner.plans[path]
                    kind, data = plans.pop(0) if len(plans) > 1 else plans[0]
                try:
                    if kind == 'redirect':
                        self.send_response(302)
                        self.send_header('Location', data)
                        self.end_headers()
                        return
                    if kind == 'timeout':
                        time.sleep(0.7)
                    elif kind == 'delay':
                        time.sleep(0.2)
                    self.send_response(kind if type(kind) is int else 200)
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    if kind == 'partial':
                        self.wfile.write(data[:4]); self.wfile.flush()
                        self.close_connection = True
                    elif kind == 'trickle':
                        for byte in data:
                            self.wfile.write(bytes([byte])); self.wfile.flush(); time.sleep(0.08)
                    else:
                        self.wfile.write(data)
                except (BrokenPipeError, ConnectionError, ssl.SSLError):
                    pass
        class Server(ThreadingHTTPServer):
            daemon_threads = True
            def handle_error(self, *_args):
                pass
        cls.lock = threading.Lock()
        cls.plans, cls.calls = {}, []
        cls.server = Server(('127.0.0.1', 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cls.cert, cls.key)
        cls.server.socket = context.wrap_socket(cls.server.socket, server_side=True)
        cls.url = 'https://localhost:' + str(cls.server.server_port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()
        cls.temporary.cleanup()

    def setUp(self):
        self.module = installer()
        self.directory = tempfile.TemporaryDirectory(prefix='aeb-runtime-case-')
        self.addCleanup(self.directory.cleanup)
        self.destination = Path(self.directory.name) / 'download'
        with self.lock:
            type(self).plans, type(self).calls = {}, []
        self.trust = patch.dict(os.environ, {'SSL_CERT_FILE': str(self.cert)})
        self.trust.start(); self.addCleanup(self.trust.stop)
        for name, value in (('ATTEMPT_SECONDS', 0.25), ('BACKOFF_SECONDS', (0.01, 0.02))):
            control = patch.object(self.module, name, value)
            control.start(); self.addCleanup(control.stop)
        self.log = io.StringIO()

    def acquire(self, data, *, budget=2, expected=None, path='/asset'):
        with contextlib.redirect_stdout(self.log):
            self.module.acquire(self.url + path, expected or hashlib.sha256(data).hexdigest(),
                                'powershell.tar.gz', self.destination, time.monotonic() + budget)

    def events(self):
        return [json.loads(line.removeprefix('RUNTIME_ACQUISITION ')) for line in self.log.getvalue().splitlines()]

    def test_recovers_timeout_and_service_failure_after_signed_redirect(self):
        data = b'approved fixture archive'
        self.plans.update({'/redirect': [('redirect', self.url + '/asset?signature=DO_NOT_LOG')],
                           '/asset': [('timeout', data), (503, b'unavailable'), (200, data)]})
        self.acquire(data, path='/redirect?credential=DO_NOT_LOG')
        self.assertEqual(self.destination.read_bytes(), data)
        events = self.events()
        self.assertEqual([r['category'] for r in events if r['status'] == 'failed'], ['timeout', 'http_503'])
        self.assertEqual(events[-1]['attempt'], 3)
        self.assertEqual(events[-1]['status'], 'verified')
        self.assertEqual(events[-1]['bytes_received'], len(data))
        self.assertNotIn('DO_NOT_LOG', self.log.getvalue())
        self.assertNotIn('https://', self.log.getvalue())
        self.assertTrue(all(set(r) == {'asset', 'attempt', 'status', 'elapsed_sec', 'bytes_received', 'category'} for r in events))

    def test_partial_file_is_removed_before_retry_and_never_appended(self):
        data = b'correct complete fixture payload'
        self.plans['/asset'] = [('partial', data), (200, data)]
        self.acquire(data)
        self.assertEqual(self.destination.read_bytes(), data)
        failure = next(r for r in self.events() if r['status'] == 'failed')
        self.assertEqual((failure['category'], failure['bytes_received']), ('partial_download', 4))
        self.assertEqual(self.events()[-1]['attempt'], 2)

    def test_exhausted_retry_bound_removes_partial_file(self):
        self.plans['/asset'] = [('partial', b'incomplete archive')]
        with self.assertRaises(self.module.AcquisitionError):
            self.acquire(b'incomplete archive')
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(len([r for r in self.events() if r['status'] == 'started']), 3)
        self.assertFalse(self.destination.exists())

    def test_global_deadline_bounds_trickle_reads_and_all_retries(self):
        self.plans['/asset'] = [('trickle', b'long trickling fixture body')]
        started = time.monotonic()
        with self.assertRaises(self.module.AcquisitionError):
            self.acquire(b'long trickling fixture body', budget=0.4)
        self.assertLess(time.monotonic() - started, 1.3)
        self.assertLessEqual(len(self.calls), 3)
        self.assertFalse(self.destination.exists())
        self.assertTrue(any(r['bytes_received'] > 0 for r in self.events()))

    def test_installer_budget_is_shared_across_both_assets(self):
        first, second = b'first pinned asset', b'second pinned asset'
        self.plans.update({'/powershell': [('delay', first)], '/pester': [('timeout', second)]})
        inputs = ((self.url + '/powershell', hashlib.sha256(first).hexdigest(), 'powershell.tar.gz'),
                  (self.url + '/pester', hashlib.sha256(second).hexdigest(), 'pester.nupkg'))
        root = Path(self.directory.name); started = time.monotonic()
        with patch.object(self.module, 'ACQUISITION_SECONDS', 0.45), \
                patch.object(self.module, 'ATTEMPT_SECONDS', 1), \
                contextlib.redirect_stdout(self.log), self.assertRaises(self.module.AcquisitionError):
            self.module.main(inputs=inputs, runtime=root / 'powershell', module=root / 'Pester')
        self.assertLess(time.monotonic() - started, 1.3)
        self.assertEqual(self.calls, ['/powershell', '/pester'])
        self.assertEqual(self.events()[-1]['asset'], 'pester.nupkg')
        self.assertFalse((root / 'powershell').exists())

    def test_checksum_failure_is_terminal_and_cannot_be_retried(self):
        self.plans['/asset'] = [(200, b'changed archive'), (200, b'approved archive')]
        with self.assertRaisesRegex(self.module.AcquisitionError, 'sha256_mismatch'):
            self.acquire(b'approved archive')
        self.assertEqual(len(self.calls), 1)
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.events()[-1]['category'], 'sha256_mismatch')

    def test_https_downgrade_and_permanent_service_errors_do_not_retry(self):
        self.plans['/asset'] = [('redirect', 'http://127.0.0.1/DO_NOT_LOG')]
        with self.assertRaisesRegex(self.module.AcquisitionError, 'https_required'):
            self.acquire(b'fixture')
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn('DO_NOT_LOG', self.log.getvalue())
        self.calls.clear(); self.plans['/asset'] = [(404, b'not found')]
        with self.assertRaisesRegex(self.module.AcquisitionError, 'http_404'):
            self.acquire(b'fixture')
        self.assertEqual(len(self.calls), 1)

    def test_certificate_validation_remains_required(self):
        trust = Path('/etc/ssl/certs/ca-certificates.crt')
        if not trust.is_file():
            self.skipTest('System trust store unavailable')
        self.plans['/asset'] = [(200, b'fixture')]
        with patch.dict(os.environ, {'SSL_CERT_FILE': str(trust)}), \
                self.assertRaisesRegex(self.module.AcquisitionError, 'tls_verification'):
            self.acquire(b'fixture')
        self.assertEqual(len(self.calls), 0)
        self.assertEqual(len([r for r in self.events() if r['status'] == 'started']), 1)

    def test_real_installer_extracts_both_verified_fixtures_and_invokes_runtime_check(self):
        tar = io.BytesIO()
        with tarfile.open(fileobj=tar, mode='w:gz') as archive:
            script = b'#!/bin/sh\nprintf "%s\\n" "$@" > "$RUNTIME_INSTALL_TEST_LOG"\n'
            entry = tarfile.TarInfo('pwsh'); entry.size = len(script)
            archive.addfile(entry, io.BytesIO(script))
        bundle = io.BytesIO()
        with zipfile.ZipFile(bundle, 'w') as archive:
            archive.writestr('Pester.psd1', 'approved fixture module')
        powershell, pester = tar.getvalue(), bundle.getvalue()
        self.plans.update({'/powershell': [(503, b'unavailable'), (200, powershell)], '/pester': [(200, pester)]})
        inputs = ((self.url + '/powershell', hashlib.sha256(powershell).hexdigest(), 'powershell.tar.gz'),
                  (self.url + '/pester', hashlib.sha256(pester).hexdigest(), 'pester.nupkg'))
        root = Path(self.directory.name)
        with patch.object(self.module, 'ACQUISITION_SECONDS', 2), \
                patch.dict(os.environ, {'RUNTIME_INSTALL_TEST_LOG': str(root / 'runtime-call')}), \
                contextlib.redirect_stdout(self.log):
            self.module.main(inputs=inputs, runtime=root / 'powershell', module=root / 'Pester')
        self.assertEqual((root / 'Pester/Pester.psd1').read_text(), 'approved fixture module')
        command = (root / 'runtime-call').read_text()
        self.assertIn("7.6.9", command); self.assertIn('-RequiredVersion 6.2.0', command)
        self.assertEqual({r['asset'] for r in self.events() if r['status'] == 'verified'}, {'powershell.tar.gz', 'pester.nupkg'})
        self.assertEqual(self.module.INPUTS, installer().INPUTS)
        self.assertEqual(installer().ACQUISITION_SECONDS, 150)
        self.assertEqual(installer().ATTEMPTS, 3)


if __name__ == '__main__':
    unittest.main()
