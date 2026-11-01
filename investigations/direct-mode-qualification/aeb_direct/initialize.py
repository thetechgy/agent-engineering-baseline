"""Operator-only initializer and identity-bound, audit-neutral active readiness."""
import importlib.util,json,os,socket,stat,struct,time,uuid,hashlib,tempfile
from pathlib import Path
root=Path('/opt/gh-eval');state=root/'state';sock=Path('/run/gh-eval/gh.sock')
if os.geteuid()!=0: raise RuntimeError('root initializer required')

# Reviewed production fixture bytes; verify before executing root-owned setup.
EXPECTED={'setup.py': '01a285a4a5fafb9aba80337295edc22836ff2e9dae508460e07a341a87c09556', 'fixture.py': '4d3da7a0dbc1481963e68d1577fe10e95bf72a844cec3e8f58ff94de52a554fe', 'client.py': '3255b7628edd43233d39c5ef8e2e88a06fc059c418502f5aa737fa31d50e791d', 'cases/gh-010-partial.json': '2f5280b2d18cdf5cf196550f681710aa27ad1de790320e7a6e4d60dfee07e8c2'}
for name,digest in EXPECTED.items():
 p=root/'source'/name;m=p.lstat()
 if not stat.S_ISREG(m.st_mode) or m.st_uid!=0 or m.st_nlink!=1 or m.st_mode&0o022 or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:raise RuntimeError('fixture source substitution')
if hashlib.sha256((root/'setup.py').read_bytes()).hexdigest()!=EXPECTED['setup.py']:raise RuntimeError('initializer source substitution')
spec=importlib.util.spec_from_file_location('trusted_setup',root/'setup.py');setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)
if sock.exists() or sock.is_symlink():raise RuntimeError('refusing existing broker socket')
# Public workspace/client provisioning happened at image build. Runtime private
# state is new and operator-owned; no chown capability or audit reset is needed.
with tempfile.TemporaryDirectory(prefix='initializer-',dir=root) as td:
 setup.setup(Path(td),root/'source',private=state)
broker=setup.start_broker(state,sock)
pid=broker.pid;start=Path(f'/proc/{pid}/stat').read_text().split()[21]
info=sock.lstat()
if not stat.S_ISSOCK(info.st_mode) or info.st_uid!=0:raise RuntimeError('wrong socket owner/type')
with socket.socket(socket.AF_UNIX) as c:
 c.settimeout(2);c.connect(str(sock));peer=struct.unpack('3i',c.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
 if peer[0]!=pid or peer[1]!=0:raise RuntimeError('wrong broker peer')
 c.sendall(b'{}\n')
 if c.recv(1024)!=b'{"error":"invalid broker request"}\n':raise RuntimeError('broker readiness failed')
if Path(f'/proc/{pid}/stat').read_text().split()[21]!=start or sock.lstat().st_ino!=info.st_ino or (state/'audit.jsonl').read_bytes():raise RuntimeError('readiness identity/audit changed')
identity={'state_id':uuid.uuid4().hex,'pid':pid,'start':start,'socket_inode':info.st_ino,'socket_device':info.st_dev,'peer_uid':peer[1],'state_inode':state.stat().st_ino}
(root/'ready.json').write_text(json.dumps(identity));print(json.dumps(identity))
