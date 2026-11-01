import hashlib,importlib.resources,json,shlex,tempfile,os,stat
from pathlib import Path
from skillevaluator.tier3.harbor.secure_docker_environment import SkillEvaluatorSecureDockerEnvironment
class Environment(SkillEvaluatorSecureDockerEnvironment):
 def __init__(self,*args,profile='positive',**kwargs):
  if profile not in ('positive','denied','boundary'):raise ValueError('unknown qualification profile')
  self.profile=profile
  self._operator_overlay=tempfile.TemporaryDirectory(prefix='aeb-direct-overlay-')
  overlay=Path(self._operator_overlay.name)/'containment.json'
  overlay.write_text(json.dumps({'services':{'main':{'network_mode':'none','cap_drop':['ALL'],'security_opt':['no-new-privileges:true'],'pids_limit':256,'healthcheck':{'test':['CMD','python3','-I','-c','import os;os.kill(1,0)'],'interval':'1s','timeout':'2s','retries':5}}}}))
  if kwargs.get('extra_docker_compose'):raise ValueError('unqualified operator overlay')
  kwargs['extra_docker_compose']=[str(overlay)]
  super().__init__(*args,**kwargs)
 async def upload_dir(self,source_dir,target_dir):
  # Narrow Linux verifier ownership adapter over the inherited hardened runner.
  # Compose cp defaults to preserving host UIDs, unusable for cap-drop=ALL root.
  if target_dir!='/tests':return await super().upload_dir(source_dir,target_dir)
  source=Path(source_dir)
  if source.absolute()!=source.resolve() or source!=self.environment_dir.parent/'tests':raise RuntimeError('unexpected verifier source')
  entries=[source,*source.rglob('*')]
  if len(entries)>256:raise RuntimeError('verifier member limit')
  manifest={};total=0
  for entry in entries:
   meta=entry.lstat()
   if meta.st_uid!=os.getuid() or not (stat.S_ISREG(meta.st_mode) or stat.S_ISDIR(meta.st_mode)):raise RuntimeError('unsafe verifier source')
   if stat.S_ISREG(meta.st_mode):
    if meta.st_nlink!=1:raise RuntimeError('linked verifier source')
    total+=meta.st_size
    if total>8*1024*1024:raise RuntimeError('verifier byte limit')
    manifest[str(entry.relative_to(source))]=hashlib.sha256(entry.read_bytes()).hexdigest()
  if total>8*1024*1024:raise RuntimeError('verifier byte limit')
  await self._run_docker_compose_command(['cp','--archive=false',str(source)+'/.','main:/tests'],check=True)
  code="from pathlib import Path;import stat,hashlib,json;p=Path('/tests');entries=[p,*p.rglob('*')];print(json.dumps({'metadata':[(str(x),x.lstat().st_uid,oct(x.lstat().st_mode&0o777),x.lstat().st_nlink) for x in entries]}),flush=True);assert all(x.lstat().st_uid==0 and (stat.S_ISDIR(x.lstat().st_mode) or (stat.S_ISREG(x.lstat().st_mode) and x.lstat().st_nlink==1)) for x in entries);[x.chmod(x.lstat().st_mode&0o700) for x in entries];print(json.dumps({str(x.relative_to(p)):hashlib.sha256(x.read_bytes()).hexdigest() for x in entries if x.is_file()}))"
  result=await self.exec('python3 -I -c '+shlex.quote(code),user='root',timeout_sec=10)
  if result.return_code or json.loads(result.stdout.splitlines()[-1])!=manifest:raise RuntimeError('verifier transfer identity or bytes changed: '+repr((result.return_code,result.stdout,result.stderr)))
 async def start(self,force_build):
  await super().start(force_build)
  protect="from pathlib import Path;import stat;p=Path('/tests');p.mkdir(exist_ok=True);m=p.lstat();assert stat.S_ISDIR(m.st_mode) and m.st_uid==0;p.chmod(0o700)"
  result=await self.exec('python3 -I -c '+shlex.quote(protect),user='root',timeout_sec=5)
  if result.return_code:raise RuntimeError('private verifier directory unavailable')
  for name in ('controller.py','initialize.py'):
   raw=importlib.resources.files('aeb_direct').joinpath(name).read_bytes()
   code="from pathlib import Path;import os,stat,hashlib;p=Path('/opt/direct-qualification');p.mkdir(exist_ok=True);s=p.lstat();assert s.st_uid==0 and not s.st_mode&0o022;f=p/"+repr(name)+";f.open('xb').write(bytes.fromhex('"+raw.hex()+"'));f.chmod(0o444);assert f.lstat().st_uid==0 and f.lstat().st_nlink==1;print(hashlib.sha256(f.read_bytes()).hexdigest())"
   result=await self.exec('python3 -I -c '+shlex.quote(code),user='root',timeout_sec=10)
   if result.return_code or result.stdout.strip()!=hashlib.sha256(raw).hexdigest():raise RuntimeError('operator helper substitution')
  check="import os,pathlib,json;d=dict(x.split(':',1) for x in pathlib.Path('/proc/self/status').read_text().splitlines() if ':' in x);print(json.dumps([os.getuid(),d['CapEff'].strip(),d['NoNewPrivs'].strip(),d['Seccomp'].strip(),sorted(p.name for p in pathlib.Path('/sys/class/net').iterdir())]))"
  security=await self.exec('python3 -I -c '+shlex.quote(check),user='agent',timeout_sec=5)
  if security.return_code or json.loads(security.stdout)!=[1000,'0000000000000000','1','2',['lo']]:raise RuntimeError('runtime isolation mismatch')
  permissions="from pathlib import Path;import stat,json;p=Path('/workspace/skills');entries=[p,*p.rglob('*')];print(json.dumps({'metadata':[(str(x),x.lstat().st_uid,oct(x.lstat().st_mode&0o777),x.lstat().st_nlink) for x in entries]}),flush=True);assert all(x.lstat().st_uid==0 and (stat.S_ISREG(x.lstat().st_mode) or stat.S_ISDIR(x.lstat().st_mode)) for x in entries);[(x.chmod((x.lstat().st_mode&0o777)|(0o555 if x.is_dir() else 0o444))) for x in entries]"
  result=await self.exec('python3 -I -c '+shlex.quote(permissions),user='root',timeout_sec=5)
  if result.return_code:raise RuntimeError('public skill projection permissions unavailable')
  result=await self.exec('python3 -I /opt/direct-qualification/initialize.py',user='root',timeout_sec=10)
  if result.return_code:raise RuntimeError('required initializer failed')
  self.direct_identity=json.loads(result.stdout)
