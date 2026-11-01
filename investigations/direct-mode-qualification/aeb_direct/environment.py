import hashlib,importlib.resources,json,shlex
from skillevaluator.tier3.harbor.secure_docker_environment import SkillEvaluatorSecureDockerEnvironment
class Environment(SkillEvaluatorSecureDockerEnvironment):
 def __init__(self,*args,profile='positive',**kwargs):
  if profile not in ('positive','denied'):raise ValueError('unknown qualification profile')
  self.profile=profile;super().__init__(*args,**kwargs)
 async def start(self,force_build):
  await super().start(force_build)
  for name in ('controller.py','initialize.py'):
   raw=importlib.resources.files('aeb_direct').joinpath(name).read_bytes()
   code="from pathlib import Path;import os,stat,hashlib;p=Path('/opt/direct-qualification');p.mkdir(exist_ok=True);s=p.lstat();assert s.st_uid==0 and not s.st_mode&0o022;f=p/"+repr(name)+";f.open('xb').write(bytes.fromhex('"+raw.hex()+"'));f.chmod(0o444);assert f.lstat().st_uid==0 and f.lstat().st_nlink==1;print(hashlib.sha256(f.read_bytes()).hexdigest())"
   result=await self.exec('python3 -I -c '+shlex.quote(code),user='root',timeout_sec=10)
   if result.return_code or result.stdout.strip()!=hashlib.sha256(raw).hexdigest():raise RuntimeError('operator helper substitution')
  result=await self.exec('python3 -I /opt/direct-qualification/initialize.py',user='root',timeout_sec=10)
  if result.return_code:raise RuntimeError('required initializer failed')
  self.direct_identity=json.loads(result.stdout)
