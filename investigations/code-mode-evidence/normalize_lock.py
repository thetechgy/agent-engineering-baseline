"""Normalize release stamping only; preserve every external dependency byte."""
import hashlib
import json
from pathlib import Path
import sys
import tomllib

root=Path(sys.argv[1])/'codex-rs'
destination=Path(sys.argv[2])
manifest=tomllib.loads((root/'Cargo.toml').read_text())
assert manifest['workspace']['package']['version']=='0.166.0'
members={}
patterns=manifest['workspace']['members']+[
    'message-history','windows-sandbox-rs','core/tests/common',
    'chatgpt','app-server/tests/common']
for pattern in patterns:
    for path in root.glob(pattern+'/Cargo.toml'):
        package=tomllib.loads(path.read_text()).get('package',{})
        if package.get('version')=={'workspace':True}:
            members[package['name']]=path
path=root/'Cargo.lock'
original=path.read_bytes()
before=tomllib.loads(original.decode())
changed=[]
blocks=original.decode().split('[[package]]')
for index in range(1,len(blocks)):
    package=tomllib.loads('[[package]]'+blocks[index])['package'][0]
    if package.get('source') is None and package['name'] in members:
        assert package['version']=='0.0.0',package['name']
        assert blocks[index].count('version = "0.0.0"')==1
        blocks[index]=blocks[index].replace('version = "0.0.0"','version = "0.166.0"',1)
        changed.append(package['name'])
assert len(changed)==170
normalized='[[package]]'.join(blocks).encode()
after=tomllib.loads(normalized.decode())
expected=json.loads(json.dumps(before))
for package in expected['package']:
    if package['name'] in changed and package.get('source') is None:
        package['version']='0.166.0'
assert after==expected
assert [p for p in before['package'] if 'source' in p]==[p for p in after['package'] if 'source' in p]
path.write_bytes(normalized)
destination.write_text(json.dumps(dict(schema='release-workspace-stamp-v1',
    original_sha256=hashlib.sha256(original).hexdigest(),
    normalized_sha256=hashlib.sha256(normalized).hexdigest(),
    workspace_packages=changed, external_dependencies_changed=False),indent=2))
