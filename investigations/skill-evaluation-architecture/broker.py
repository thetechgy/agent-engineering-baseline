"""Non-sensitive root-owned broker approximation. Never opens caller-selected paths."""
import json, os, pathlib, socket, subprocess, sys, time, uuid
PRIVATE=pathlib.Path('/opt/private'); SOCKET='/run/poc/broker.sock'
def client(op):
 with socket.socket(socket.AF_UNIX) as s:
  s.connect(SOCKET);s.sendall(json.dumps({'op':op}).encode());return json.loads(s.recv(4096))
if sys.argv[1]=='init':
 if os.geteuid()!=0:raise PermissionError('initializer requires root')
 PRIVATE.mkdir(mode=0o700);(PRIVATE/'identity').write_text(uuid.uuid4().hex);(PRIVATE/'audit').write_text('')
 pathlib.Path('/run/poc').mkdir(mode=0o755)
 subprocess.Popen([sys.executable,__file__,'serve'],env={'PATH':'/usr/bin:/usr/local/bin:/bin'},stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
 for _ in range(50):
  try:
   r=client('ready');assert r['identity']==(PRIVATE/'identity').read_text();print(json.dumps(r));break
  except (OSError,ValueError):time.sleep(.1)
 else:raise RuntimeError('active readiness failed')
elif sys.argv[1]=='serve':
 ident=(PRIVATE/'identity').read_text();mutated=False
 with socket.socket(socket.AF_UNIX) as s:
  s.bind(SOCKET);os.chmod(SOCKET,0o666);s.listen()
  while True:
   c,_=s.accept()
   with c:
    op=json.loads(c.recv(4096))['op'];allowed=op in ('ready','read') or op=='mutate' and not mutated
    if op=='mutate' and allowed:mutated=True
    r={'identity':ident,'allowed':allowed,'receipt':uuid.uuid4().hex}
    with (PRIVATE/'audit').open('a') as f:f.write(json.dumps({'op':op,**r})+'\n')
    c.sendall(json.dumps(r).encode())
else:print(json.dumps(client(sys.argv[1])))
