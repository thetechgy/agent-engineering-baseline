"""One native trial inside the evaluated container; observer lives elsewhere."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from controller_adapter import adapt

endpoint,profile,backend_port=sys.argv[1:]
with tempfile.TemporaryDirectory(prefix='protected-native-') as td:
    root=Path(td)
    controller=root/'controller.py'
    controller.write_text(adapt('/opt/experiment/controller.py'))
    args=dict(cmd='printf submission-probe',workdir='/workspace',
              sandbox_permissions='require_escalated',justification='offline contract control',login=False)
    scripts={
        'empty':'text("control-finished");',
        'denied':'try {await tools.exec_command('+json.dumps(args)+');} catch (_) {} text("control-finished");',
        'oversized':'try {await tools.exec_command({cmd:"x".repeat(64*1024*1024)});} catch (_) {} text("control-finished");',
        'isolation':'text((await tools.exec_command({cmd:'+json.dumps(
            'python3 -I /opt/experiment/isolation_probe.py '+endpoint.split('//')[1].split(':')[0]+' '+backend_port)+'})).output);',
        'interrupted':'text(await tools.exec_command({cmd:"sleep 20"}));',
    }
    binary=Path('/opt/experiment/codex-x86_64-unknown-linux-musl')
    payload=dict(codex=str(binary),codex_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
        endpoint=endpoint,home=str(root),workspace='/workspace',
        sandbox='danger-full-access' if profile in ('isolation','interrupted') else 'read-only',
        script=scripts[profile])
    result=subprocess.run([sys.executable,'-I',str(controller),json.dumps(payload)],
        env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':str(root)},
        capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stderr[-2000:]
    capture=json.loads(result.stdout)
    print(json.dumps(capture))
