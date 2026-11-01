"""Exercise the actual build-failure branch and checker corruption rejection."""
import copy,importlib.util,subprocess,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[2]
s=(root/'investigations/code-mode-evidence/bootstrap.sh').read_text()
branch=s[s.index('if [ "$build_status" != 0 ]; then'):s.index('if [ "$build_status" = 0 ]; then')]
with tempfile.TemporaryDirectory() as td:
 Path(td,'evidence').mkdir()
 script='set -e\nroot='+repr(td)+'\nexperiment=unused\nbuild_status=7\ngit(){ :; };cp(){ :; };cmp(){ :; };timeout(){ return 1; };\n'+branch
 result=subprocess.run(['bash','-c',script])
 if result.returncode!=7:raise RuntimeError('failed build did not block qualification')
spec=importlib.util.spec_from_file_location('checker',root/'investigations/code-mode-evidence/results/verify_observation.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
import base64,json
journal=[{'stage':'scope_open','scope':1,'outer':'outer'}, {'stage':'callback_entered','scope':1,'callback':1,'tool_index':0}, {'stage':'serialized','scope':1,'callback':1,'arguments_complete':True,'input_present':True,'arguments':{'cmd':'pwd'}}, {'stage':'runtime_queued','scope':1,'callback':1,'runtime_tool_call_id':'tool-1'}, {'stage':'scope_closed','scope':1,'callbacks':1}]
def record(method,direction,message):return dict(method=method,direction=direction,message=message)
proxy=[record('OpenSession','response',{'opened':{'session_id':'session'}}),record('Execute','request',{'session_id':'session','execution_id':'execution','tool_call_id':'outer','enabled_tools':[{'tool_name':{'name':'exec_command'},'kind':'TOOL_KIND_FUNCTION'}]}),record('SubscribeToToolCalls','request',{'session_id':'session'}),record('SubscribeToToolCalls','response',{'session_id':'session','execution_id':'execution','cell_id':'cell','sequence':'1','runtime_tool_call_id':'tool-1','invocation_id':'invocation','tool_name':{'name':'exec_command'},'tool_kind':'TOOL_KIND_FUNCTION','input_json':base64.b64encode(json.dumps({'cmd':'pwd'}).encode()).decode()}),record('CompleteToolCall','request',{'session_id':'session','invocation_id':'invocation'}),record('CompleteToolCall','response',{}),record('OpenSession','response',{'cell_closed':{'execution_id':'execution','cell_id':'cell','final_tool_call_sequence':'1'}})]
payload={'journal':journal,'proxy':proxy,'gate':{'producer_sha256':'binary','producer_failed':False,'accepted':['agent'],'rejected':['attacker']},'capture':{'status':'completed','frames':[{'method':'rawResponseItem/completed','params':{'item':{'type':'function_call','call_id':'outer'}}}]}}
if not m.protected(payload,'binary')['arguments_complete']:raise RuntimeError('positive checker control failed')
for label in ('foreign-session','foreign-completion-session','wrong-tool','missing-ack'):
 p=copy.deepcopy(payload)
 if label=='foreign-session':p['proxy'][3]['message']['session_id']='foreign'
 elif label=='foreign-completion-session':p['proxy'][4]['message']['session_id']='foreign'
 elif label=='wrong-tool':p['proxy'][3]['message']['tool_name']={'name':'foreign'}
 else:p['proxy'].pop(5)
 if m.protected(p,'binary')['arguments_complete']:raise RuntimeError('checker accepted '+label)
print('actual build-failure branch blocked; four synthetic correlation corruptions rejected')
