"""Fetch the snapshot-selected packages from Debian's mirror, with snapshot hashes."""
import concurrent.futures
import hashlib
from pathlib import Path
import re
import shlex
import urllib.request


def fetch(line):
    uri, filename, size, digest = shlex.split(line)
    match = re.fullmatch(r'https://snapshot.debian.org/archive/(debian|debian-security)/20261103T000000Z/(pool/[^\s]+)', uri)
    if not match or Path(filename).name != filename or not re.fullmatch(r'SHA256:[0-9a-f]{64}', digest):
        raise ValueError('Unexpected snapshot package identity')
    url = 'https://deb.debian.org/' + match[1] + '/' + match[2]
    with urllib.request.urlopen(url, timeout=30) as response:
        data = response.read(int(size) + 1)
    if len(data) != int(size) or hashlib.sha256(data).hexdigest() != digest.removeprefix('SHA256:'):
        raise ValueError('Snapshot package digest mismatch: ' + filename)
    (Path('/var/cache/apt/archives') / filename).write_bytes(data)
    print('Verified snapshot package ' + filename, flush=True)


if __name__ == '__main__':
    lines = [s for s in Path('/tmp/apt-uris').read_text().splitlines() if s.startswith("'")]
    if not lines:
        raise ValueError('No snapshot package plan')
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch, lines))
