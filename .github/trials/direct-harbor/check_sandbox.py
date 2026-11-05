"""Credential-free native Codex sandbox check in the exact agent image."""
import json
from pathlib import Path
import subprocess
import sys

output = Path(sys.argv[1]); output.mkdir(parents=True, exist_ok=True)
command = ['codex', 'sandbox', '-c', 'sandbox_mode="workspace-write"',
           '-c', 'approval_policy="never"', '-c', 'sandbox_workspace_write.network_access=false',
           '-c', 'sandbox_workspace_write.exclude_slash_tmp=true',
           '-c', 'sandbox_workspace_write.exclude_tmpdir_env_var=true', '--', 'python3', '-c',
           "import pathlib,socket; pathlib.Path('/workspace/output/sandbox-ok').write_text('ok'); "
           "exec(\"try:\\n pathlib.Path('/outside/inner-denied').write_text('bad')\\n raise AssertionError('outside write allowed')\\nexcept PermissionError: pass\\ntry:\\n socket.socket().connect(('127.0.0.1',9))\\n raise AssertionError('network allowed')\\nexcept PermissionError: pass\"); print('native sandbox restrictions verified')"]
# Environment is fresh, credential-free, unprivileged, with normal Docker seccomp.
# Outer file permissions alone allow /outside writes: prove that before testing Codex.
outer = "import os,pathlib,socket,subprocess,json; assert os.getuid()==1000; s=socket.socket(); s.close(); pathlib.Path('/outside/outer-ok').write_text('ok'); assert not pathlib.Path('/var/run/docker.sock').exists(); status=pathlib.Path('/proc/self/status').read_text(); assert 'CapEff:\\t0000000000000000' in status and 'NoNewPrivs:\\t1' in status; raise SystemExit(subprocess.call(" + repr(command) + "))"
argv = ['docker','run','--rm','--network','none','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--pids-limit','256','--cpus','2','--memory','2g','--user','1000:1000','--workdir','/workspace',
        '-e','CODEX_HOME=/home/agent/.codex','direct-harbor-agent:recovery','python3','-c',outer]
try:
    result = subprocess.run(argv, text=True, capture_output=True, timeout=60)
    data = {'qualified': result.returncode == 0, 'returncode': result.returncode,
            'command': command, 'stdout': result.stdout[-8000:], 'stderr': result.stderr[-8000:],
            'boundary': 'Codex native workspace-write plus unprivileged Docker, default seccomp, no-new-privileges, no extra capabilities or mounts'}
except subprocess.TimeoutExpired:
    data = {'qualified': False, 'failure': 'sandbox_check_timeout', 'command': command}
(output / 'sandbox.json').write_text(json.dumps(data, indent=2)+'\n')
print(json.dumps(data), flush=True)
raise SystemExit(0 if data['qualified'] else 1)
