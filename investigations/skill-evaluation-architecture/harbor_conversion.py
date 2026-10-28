"""Pinned Harbor ACP converter replay from real native observations."""
import json,pathlib,sys,tempfile
from harbor.agents.installed.acp import AcpAgent
p=json.loads(pathlib.Path(sys.argv[1]).read_text())
with tempfile.TemporaryDirectory() as tmp:
 agent=AcpAgent(logs_dir=pathlib.Path(tmp),registry_entry={'id':'fixture','name':'fixture','version':'1','description':'synthetic','distribution':{'local':{'cmd':'/nonexecuted'}}})
 trajectory=agent._convert_events_to_trajectory(summary={'instruction':'fixture'},events=p['events'])
 data=trajectory.model_dump(mode='json',exclude_none=True)
 pathlib.Path(sys.argv[2]).write_text(json.dumps(data,indent=2))
 print(json.dumps({'native_terminal_statuses':p['terminalStates'],'steps':len(data['steps']),'tool_calls':sum(len(s.get('tool_calls',[])) for s in data['steps']),'terminal_status_preserved':any('status' in s for s in data['steps'])}))
