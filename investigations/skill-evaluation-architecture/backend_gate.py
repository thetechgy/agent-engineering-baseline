from skillevaluator.tier3.harbor.runner import build_harbor_run_command
from skillevaluator.tier3_environments import load_custom_backend
from skillevaluator.tier3.harbor.secure_docker_environment import SkillEvaluatorSecureDockerEnvironment
from harbor_gate import TrustedEnvironment
spec=load_custom_backend('architecture-poc')
assert spec.import_path=='harbor_gate:TrustedEnvironment'
assert issubclass(TrustedEnvironment,SkillEvaluatorSecureDockerEnvironment)
for name in ('exec','exec_with_sensitive_env','stop','service_exec','service_download_dir'):
 assert getattr(TrustedEnvironment,name) is getattr(SkillEvaluatorSecureDockerEnvironment,name),name
cmd=build_harbor_run_command(dataset_path='/nonexecuted',agent='codex',job_name='fixture',env_mode='architecture-poc')
assert cmd[cmd.index('--env')+1]=='harbor_gate:TrustedEnvironment'
print('Installed backend dispatch selects inherited secure environment')
