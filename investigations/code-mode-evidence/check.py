"""Assertions over operator captures, never producer code."""
import base64
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
summary = {}
for version in (166, 165):
    stock = json.loads((root/f'stock-{version}.json').read_text())
    native = json.loads((root/f'native-{version}.json').read_text())
    assert [len(row['calls']) for row in stock['rows'][:6]] == [0, 1, 0, 0, 1, 1]
    assert len(stock['rows'])==7 and len(stock['rows'][6]['calls']) in (0,1)
    empty, denied, direct = native['rows'][:3]
    assert all(row['capture']['status']=='completed' for row in native['rows'])
    calls = [r['message'] for r in denied['grpc'] if r['method']=='SubscribeToToolCalls' and r['direction']=='response']
    assert len(calls)==1
    arguments = json.loads(base64.b64decode(calls[0]['input_json']))
    assert arguments['sandbox_permissions']=='require_escalated'
    assert not [r for r in empty['grpc'] if r['method']=='SubscribeToToolCalls' and r['direction']=='response']
    for row in (empty, denied):
        assert not [f for f in row['capture']['frames'] if f.get('method')=='item/completed' and f.get('params',{}).get('item',{}).get('type')=='commandExecution']
    advertised = {t['name'] for group in direct['capture']['tool_catalog'] for t in group.get('tools',[])}
    assert 'exec_command' in advertised and 'exec' not in advertised
    raw = [f['params']['item'] for f in direct['capture']['frames'] if f.get('method')=='rawResponseItem/completed']
    assert any(r['type']=='function_call' and json.loads(r['arguments'])['sandbox_permissions']=='require_escalated' for r in raw)
    assert any('approval policy is Never' in json.dumps(r) for r in raw)
    uncaught=next(row for row in native['rows'] if row['label']=='uncaught-denied')
    original=[r['message'] for r in uncaught['grpc']
        if r['method']=='SubscribeToToolCalls' and r['direction']=='response']
    assert len(original)==1
    assert json.loads(base64.b64decode(original[0]['input_json']))==dict(
        cmd='printf denied-escalation',sandbox_permissions='require_escalated',
        justification='denied request qualification')
    assert any('approval policy is Never' in json.dumps(r) for r in uncaught['grpc'])
    summary[str(version)] = dict(stock_full_submission_contract='failed',
        denied_escalation_visible_over_grpc=True, direct_runtime_feasible=True,
        real_provider_compatibility='unavailable-no-inference', producer_authenticity='unqualified')
(root/'summary.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary))
