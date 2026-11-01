import hashlib,importlib.resources,json,shlex,tempfile
from pathlib import Path
from skillevaluator.tier3.harbor.secure_docker_environment import SkillEvaluatorSecureDockerEnvironment
class Environment(SkillEvaluatorSecureDockerEnvironment):
 def __init__(self,*args,profile='positive',**kwargs):
  if profile not in ('positive','denied','boundary'):raise ValueError('unknown qualification profile')
  self.profile=profile
  self._operator_overlay=tempfile.TemporaryDirectory(prefix='aeb-direct-overlay-')
  overlay=Path(self._operator_overlay.name)/'containment.json'
  overlay.write_text(json.dumps({'services':{'main':{'network_mode':'none','cap_drop':['ALL'],'security_opt':['no-new-privileges:true'],'pids_limit':256}}}))
  if kwargs.get('extra_docker_compose'):raise ValueError('unqualified operator overlay')
  kwargs['extra_docker_compose']=[str(overlay)]
  super().__init__(*args,**kwargs)
 async def start(self,force_build):
  await super().start(force_build)
  for name in ('controller.py','initialize.py'):
   raw=importlib.resources.files('aeb_direct').joinpath(name).read_bytes()
   code="from pathlib import Path;import os,stat,hashlib;p=Path('/opt/direct-qualification');p.mkdir(exist_ok=True);s=p.lstat();assert s.st_uid==0 and not s.st_mode&0o022;f=p/"+repr(name)+";f.open('xb').write(bytes.fromhex('"+raw.hex()+"'));f.chmod(0o444);assert f.lstat().st_uid==0 and f.lstat().st_nlink==1;print(hashlib.sha256(f.read_bytes()).hexdigest())"
   result=await self.exec('python3 -I -c '+shlex.quote(code),user='root',timeout_sec=10)
   if result.return_code or result.stdout.strip()!=hashlib.sha256(raw).hexdigest():raise RuntimeError('operator helper substitution')
  check="import os,pathlib,json;d=dict(x.split(':',1) for x in pathlib.Path('/proc/self/status').read_text().splitlines() if ':' in x);print(json.dumps([os.getuid(),d['CapEff'].strip(),d['NoNewPrivs'].strip(),d['Seccomp'].strip(),sorted(p.name for p in pathlib.Path('/sys/class/net').iterdir())]))"
  security=await self.exec('python3 -I -c '+shlex.quote(check),user='agent',timeout_sec=5)
  if security.return_code or json.loads(security.stdout)!=[1000,'0000000000000000','1','2',['lo']]:raise RuntimeError('runtime isolation mismatch')
  result=await self.exec('python3 -I /opt/direct-qualification/initialize.py',user='root',timeout_sec=10)
  if result.return_code:raise RuntimeError('required initializer failed')
  self.direct_identity=json.loads(result.stdout)
