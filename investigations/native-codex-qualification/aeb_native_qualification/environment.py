"""Required operator profile over the unmodified secure environment implementation."""
import hashlib
import importlib.resources
import json
import shlex
from harbor.models.task.config import NetworkMode,NetworkPolicy
from skillevaluator.tier3.harbor.secure_docker_environment import SkillEvaluatorSecureDockerEnvironment

class SecureNativeEnvironment(SkillEvaluatorSecureDockerEnvironment):
    def __init__(self,*args,profile=None,**kwargs):
        if profile!='producer-smoke':raise ValueError('required operator profile missing or unsupported')
        kwargs['network_policy']=NetworkPolicy(network_mode=NetworkMode.NO_NETWORK)
        super().__init__(*args,**kwargs);self.qualification_profile=None
    async def start(self,force_build):
        await super().start(force_build)
        for name in ('native_controller.py','attack.py'):
            raw=importlib.resources.files('aeb_native_qualification').joinpath('helpers',name).read_bytes()
            expected=hashlib.sha256(raw).hexdigest()
            code="import pathlib,os,stat,hashlib; d=pathlib.Path('/opt/qualification'); d.mkdir(exist_ok=True); s=d.lstat(); assert s.st_uid==0 and stat.S_ISDIR(s.st_mode) and not s.st_mode&0o022; d.chmod(0o755); p=d/'"+name+"'; f=p.open('xb'); f.write(bytes.fromhex('"+raw.hex()+"')); f.close(); p.chmod(0o444); s=p.lstat(); assert s.st_uid==0 and stat.S_ISREG(s.st_mode) and s.st_nlink==1; print(hashlib.sha256(p.read_bytes()).hexdigest())"
            r=await self.exec('python3 -I -c '+shlex.quote(code),user='root',timeout_sec=5)
            if r.return_code or (r.stdout or '').strip()!=expected:raise RuntimeError('operator helper provisioning failed')
        r=await self.exec("python3 -I -c 'import os,json,pathlib; s=pathlib.Path(\"/proc/self/status\").read_text(); print(json.dumps({\"uid\":os.getuid(),\"interfaces\":[p.name for p in pathlib.Path(\"/sys/class/net\").iterdir()],\"status\":{k:next(l.split(\":\",1)[1].strip() for l in s.splitlines() if l.startswith(k+\":\")) for k in [\"CapEff\",\"Seccomp\",\"NoNewPrivs\"]}}))'",user='agent',timeout_sec=5)
        security=json.loads(r.stdout)
        if security!={'uid':1000,'interfaces':['lo'],'status':{'CapEff':'0000000000000000','Seccomp':'2','NoNewPrivs':'1'}}:raise RuntimeError('runtime isolation mismatch')
        self.qualification_profile={'name':'producer-smoke','security':security}
