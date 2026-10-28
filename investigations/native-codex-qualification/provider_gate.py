"""Exercise upstream provider dispatch/config, without any provider request."""
import json,pathlib,tempfile
from skillevaluator.provider_config import ProviderConfig
from skillevaluator.tier3.harbor.runner import _agent_import_path
from skillevaluator.tier3.harbor.local_agents import SkillEvaluatorGatewayCodex
from aeb_native_qualification.agent import NativeCodex
from aeb_native_qualification.environment import SecureNativeEnvironment
from skillevaluator.tier3.harbor.secure_docker_environment import SkillEvaluatorSecureDockerEnvironment

def check():
    provider=ProviderConfig(provider='openai-compatible',model='fixture/gpt-5.6-sol',api_key='qualification-sentinel-not-a-real-key',base_url='http://127.0.0.1:8991/v1',litellm_model='openai/gpt-5.6-sol')
    try:_agent_import_path(provider,'codex','architecture-poc')
    except ValueError as e:assert 'must subclass it' in str(e)
    else:raise AssertionError('unrelated agent bypassed provider wrapper')
    selected=_agent_import_path(provider,'codex','aeb-native');assert selected=='aeb_native_qualification.agent:NativeCodex'
    assert issubclass(NativeCodex,SkillEvaluatorGatewayCodex)
    assert NativeCodex.exec_as_agent is SkillEvaluatorGatewayCodex.exec_as_agent
    for name in ('exec','exec_with_sensitive_env','stop','service_exec','service_download_dir'):
        assert getattr(SecureNativeEnvironment,name) is getattr(SkillEvaluatorSecureDockerEnvironment,name)
    with tempfile.TemporaryDirectory() as path:
        agent=NativeCodex(logs_dir=pathlib.Path(path),model_name=provider.model)
        config=agent._build_effective_config(provider.base_url)
        route=config['model_providers'][config['model_provider']]
        assert route['base_url']==provider.base_url and route['env_key']=='OPENAI_API_KEY' and route['wire_api']=='responses'
        assert agent.model_name==provider.model
    return {'evidence_class':'actual-upstream-dispatch-and-config-functions','bad_wrapper':'rejected','required_wrapper':'inherited','config_routing':'preserved','secure_execution_methods':'inherited','actual_cli':'separate gate required'}
if __name__=='__main__':print(json.dumps(check(),indent=2))
