"""Operator-only initializer and identity-bound, audit-neutral active readiness."""
import importlib.util,json,os,socket,stat,struct,time
from pathlib import Path
root=Path('/opt/gh-eval');state=root/'state';sock=Path('/run/gh-eval/gh.sock')
if os.geteuid()!=0: raise RuntimeError('root initializer required')
spec=importlib.util.spec_from_file_location('trusted_setup',root/'setup.py');setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)
setup.setup(Path('/workspace'),root/'source',install=True,private=state)
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
identity={'pid':pid,'start':start,'socket_inode':info.st_ino,'socket_device':info.st_dev,'peer_uid':peer[1],'state_inode':state.stat().st_ino}
(root/'ready.json').write_text(json.dumps(identity));print(json.dumps(identity))
