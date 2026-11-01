"""Match the pinned upstream Cargo/V8 ABI and checksum-first release helper."""
import hashlib
from pathlib import Path
import sys
import tomllib
import urllib.request

source, destination = map(Path, sys.argv[1:])
destination.mkdir(mode=0o700)
lock=tomllib.loads((source/'codex-rs/Cargo.lock').read_text())
entry=next(package for package in lock['package'] if package['name']=='v8')
assert entry['version']=='152.2.0'
assert entry['source'].endswith('#350c5a859a9b3c84ab8701b3ad51e3b7699b30c0')
target='x86_64-unknown-linux-gnu'
profile='ptrcomp_sandbox_release'
manifest=f'rusty_v8_{profile}_{target}.sha256'
archive=f'librusty_v8_{profile}_{target}.a.gz'
binding=f'src_binding_{profile}_{target}.rs'
base='https://github.com/openai/codex/releases/download/rusty-v8-v152.2.0/'
trusted=dict(line.split()[::-1] for line in
    (source/'third_party/v8/rusty_v8_152_2_0_release_manifests.sha256').read_text().splitlines())


def fetch(name, digest):
    request=urllib.request.Request(base+name)
    total=0
    hashed=hashlib.sha256()
    path=destination/name
    with urllib.request.urlopen(request, timeout=60) as response, path.open('xb') as output:
        assert response.url.startswith('https://')
        while block:=response.read(1024*1024):
            total+=len(block)
            assert total<512*1024*1024
            hashed.update(block)
            output.write(block)
    assert hashed.hexdigest()==digest, name


fetch(manifest,trusted[manifest])
entries=dict(line.split()[::-1] for line in (destination/manifest).read_text().splitlines())
assert set(entries)=={archive,binding}
for name,digest in entries.items():
    fetch(name,digest)
print('Verified pinned Codex V8 archive and target-matched Rust bindings')
