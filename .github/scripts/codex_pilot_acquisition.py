"""Bounded pilot build transport, composed with the frozen runtime installer."""

from contextlib import contextmanager
import errno
import hashlib
import http.client
import json
import signal
import socket
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, build_opener


# Shared by both assets, including redirects, reads, hashes and retry backoff.
# Leave headroom in the existing 300-second observed Docker build limit.
ACQUISITION_SECONDS = 150
ATTEMPT_SECONDS = 60
ATTEMPTS = 3
BACKOFF_SECONDS = (2, 4)


class AcquisitionError(ValueError):
    def __init__(self, category):
        self.category = category
        super().__init__('Runtime acquisition failed: ' + category)


class HTTPSRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        if urlsplit(newurl).scheme != 'https':
            raise AcquisitionError('https_required')
        return super().redirect_request(request, fp, code, message, headers, newurl)


@contextmanager
def bounded_attempt(seconds):
    # The installer runs in the main thread of the Linux build process. A socket
    # inactivity timeout alone does not bound redirects, DNS or trickle reads.
    def expired(_signal, _frame):
        raise TimeoutError('Runtime acquisition deadline')
    started = time.monotonic()
    previous_handler = signal.signal(signal.SIGALRM, expired)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0]:
            signal.setitimer(signal.ITIMER_REAL,
                max(0.000001, previous_timer[0] - (time.monotonic() - started)), previous_timer[1])


def failure_category(error):
    if isinstance(error, AcquisitionError):
        return error.category, False
    if isinstance(error, HTTPError):
        error.close()
        return 'http_' + str(error.code), error.code in (408, 429, 500, 502, 503, 504)
    if isinstance(error, URLError):
        error = error.reason
    if isinstance(error, ssl.SSLCertVerificationError):
        return 'tls_verification', False
    if isinstance(error, TimeoutError):
        return 'timeout', True
    if isinstance(error, http.client.IncompleteRead):
        return 'partial_download', True
    if isinstance(error, socket.gaierror):
        return 'dns', error.errno == socket.EAI_AGAIN
    if isinstance(error, (ConnectionError, http.client.RemoteDisconnected, ssl.SSLEOFError)):
        return 'transport', True
    if isinstance(error, OSError) and error.errno in (
            errno.ETIMEDOUT, errno.ECONNRESET, errno.ECONNREFUSED, errno.ENETUNREACH, errno.EHOSTUNREACH):
        return 'transport', True
    return 'local_or_protocol', False


def acquisition_event(asset, attempt, status, started, received, category=None):
    # Deliberately no URL, redirect Location, exception text, headers or credentials.
    print('RUNTIME_ACQUISITION ' + json.dumps({
        'asset': asset, 'attempt': attempt, 'status': status,
        'elapsed_sec': round(time.monotonic() - started, 3),
        'bytes_received': received, 'category': category}, sort_keys=True), flush=True)


def acquire(url, expected, asset, archive, deadline):
    if asset not in ('powershell.tar.gz', 'pester.nupkg'):
        raise AcquisitionError('unknown_asset')
    if archive.exists() or archive.is_symlink():
        raise AcquisitionError('destination_exists')
    for attempt in range(1, ATTEMPTS + 1):
        started = time.monotonic()
        remaining = deadline - started
        if remaining <= 0:
            acquisition_event(asset, attempt - 1, 'not_started', started, 0, 'total_deadline')
            raise AcquisitionError('total_deadline')
        received = 0
        acquisition_event(asset, attempt, 'started', started, received)
        try:
            with bounded_attempt(min(ATTEMPT_SECONDS, remaining)):
                if urlsplit(url).scheme != 'https':
                    raise AcquisitionError('https_required')
                opener = build_opener(HTTPSRedirects())
                with opener.open(url, timeout=min(ATTEMPT_SECONDS, remaining)) as response:
                    if urlsplit(response.url).scheme != 'https':
                        raise AcquisitionError('https_required')
                    length = response.headers.get('Content-Length')
                    length = int(length) if length is not None else None
                    with archive.open('xb') as output:
                        while True:
                            try:
                                chunk = response.read1(64 * 1024)
                            except http.client.IncompleteRead as error:
                                received += len(error.partial)
                                raise
                            if not chunk:
                                break
                            output.write(chunk)
                            received += len(chunk)
                    if length is not None and received != length:
                        raise http.client.IncompleteRead(b'', length - received)
                with archive.open('rb') as content:
                    if hashlib.file_digest(content, 'sha256').hexdigest() != expected:
                        raise AcquisitionError('sha256_mismatch')
            acquisition_event(asset, attempt, 'verified', started, received)
            return
        except Exception as error:
            archive.unlink(missing_ok=True)
            category, transient = failure_category(error)
            acquisition_event(asset, attempt, 'failed', started, received, category)
            remaining = deadline - time.monotonic()
            if not transient or attempt == ATTEMPTS or remaining <= 0:
                raise AcquisitionError(category) from None
            time.sleep(min(BACKOFF_SECONDS[attempt - 1], remaining))


