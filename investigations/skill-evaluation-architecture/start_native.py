"""Start an unprivileged native server; no provider credentials or external listener."""
import os,pathlib,subprocess
assert os.geteuid()==1000
pathlib.Path('/home/agent/.codex').mkdir(exist_ok=True)
settings=['model_provider="fixture"','model_providers.fixture.name="fixture"','model_providers.fixture.base_url="http://127.0.0.1:8765/v1"','model_providers.fixture.wire_api="responses"','model_providers.fixture.requires_openai_auth=false','model_providers.fixture.supports_websockets=false','web_search="disabled"']
cmd=['/opt/codex/bin/codex']
for setting in settings:cmd+=['-c',setting]
cmd+=['app-server','--listen','ws://127.0.0.1:8766']
p=subprocess.Popen(cmd,env={'PATH':'/opt/codex/bin:/usr/local/bin:/usr/bin:/bin','HOME':'/home/agent','CODEX_HOME':'/home/agent/.codex'},stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
print(p.pid)
