"""Native App Server agent; inherits provider routing and secure credential dispatch."""
import json
import shlex
from skillevaluator.tier3.harbor.local_agents import SkillEvaluatorGatewayCodex
from .evidence import admit,Unavailable
from .retention import retain
from harbor.agents.capabilities import AgentCapabilities

class NativeCodex(SkillEvaluatorGatewayCodex):
    capabilities=AgentCapabilities(native_config=True,skills=True)
    async def install(self,environment):
        result=await self.exec_as_agent(environment,'/opt/codex/bin/codex --version',timeout_sec=5)
        if result.return_code or (result.stdout or '').strip()!='codex-cli 0.164.0':raise RuntimeError('pinned Codex unavailable')
        self._version='0.164.0'
    async def setup(self,environment):
        if not getattr(environment,'qualification_profile',None):raise RuntimeError('required trusted initialization absent')
        if self.mcp_servers or self._load or self._resume:raise RuntimeError('unqualified runtime feature')
        await self.install(environment)
        skills_command=self._build_register_skills_command()
        if skills_command:await self.exec_as_agent(environment,skills_command,timeout_sec=5)
        retain(self.logs_dir,'qualification-setup.json',json.dumps(environment.qualification_profile))
    async def run(self,instruction,environment,context):
        access=self.model_connection
        if access.configured_base_url!='http://127.0.0.1:8991/v1':raise RuntimeError('qualification forbids external provider')
        config=self._build_effective_config(access.configured_base_url)
        config['web_search']='disabled'
        payload={'model':self.model_name,'config':config,'instruction':instruction,'sandbox':environment.qualification_profile['codex_sandbox']}
        env={'OPENAI_API_KEY':access.api_key or '', 'OPENAI_BASE_URL':access.configured_base_url}
        result=await self.exec_as_agent(environment,'python3 -I /opt/qualification/native_controller.py '+shlex.quote(json.dumps(payload)),env=env,cwd='/workspace',timeout_sec=50)
        raw=result.stdout or ''
        retained=retain(self.logs_dir,'native-capture.json',raw)
        context.metadata=context.metadata or {}
        context.metadata['native_evidence']={k:v for k,v in retained.items() if k!='private_host_copy'}
        if result.return_code:raise Unavailable('native producer/capture failed')
        admit(json.loads(raw))
