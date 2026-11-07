"""Fixed qualification commands invoked only by the frozen CLI's stub tool call.

No secrets or input content are printed. The payload is a public grading control,
not protected reference material. All observations are independently checked by
the operator; missing or generic timeout evidence fails qualification.
"""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import struct


def rejected_write(path):
    try:
        with open(path, 'ab'):
            pass
    except PermissionError:
        return True
    return False


result = {}
status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
assert os.getuid() == 1000 and int(status['CapEff'].strip(), 16) == 0
assert status['NoNewPrivs'].strip() == '1' and status['Seccomp'].strip() == '2'
result['process'] = {'uid': 1000, 'cap_eff': 0, 'no_new_privs': 1, 'seccomp': 2}
paths = ('/tests', '/solution', '/opt/pester-runtime', '/var/run/docker.sock',
         '/opt/egress-sidecar', '/usr/local/bin/network-policy', '/host', '/root/.ssh')
for path in paths:
    assert not os.access(path, os.R_OK), path
result['protected_paths_unreadable'] = list(paths)
inputs = {p.relative_to('/workspace/input').as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in sorted(Path('/workspace/input').rglob('*')) if p.is_file()}
assert inputs and all(rejected_write(p) for p in Path('/workspace/input').rglob('*') if p.is_file())
assert rejected_write('/workspace/input/injected')
result['immutable_inputs'] = inputs
# These are real privilege operations, not missing-executable tests.
libc = ctypes.CDLL(None, use_errno=True)
assert libc.unshare(0x40000000) == -1 and ctypes.get_errno() == 1  # CLONE_NEWNET
assert libc.setuid(0) == -1 and ctypes.get_errno() == 1
with socket.socket() as s:
    try:
        s.setsockopt(socket.SOL_SOCKET, 36, 114514)  # SO_MARK: stock controller bypass mark
    except PermissionError:
        result['controller_mark_denied'] = True
    else:
        raise AssertionError('Agent acquired controller mark')
# A real nftables mutation request against the controller's shared network
# namespace must fail with EPERM; absence of a command-line nft tool is no proof.
with socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, 12) as netlink:
    netlink.settimeout(3)
    name = b'gost_egress\0'
    attribute = struct.pack('HH', 4 + len(name), 1) + name
    attribute += b'\0' * (-len(attribute) % 4)
    body = struct.pack('BBH', socket.AF_UNSPEC, 0, 0) + attribute
    netlink.sendto(struct.pack('IHHII', 16 + len(body), (10 << 8) | 2, 5, 1, 0) + body, (0, 0))
    reply = netlink.recv(4096)
    assert struct.unpack_from('H', reply, 4)[0] == 2 and struct.unpack_from('i', reply, 16)[0] == -1
result['nft_policy_mutation_denied'] = True
result['network_namespace_denied'] = True
result['setuid_denied'] = True
# Verify actual allowed route with no auth headers, then representative prohibited
# hostname and literal IP. Curl's generic timeout is explicitly inconclusive.
network = []
for url in ('https://api.openai.com/v1/models', 'https://example.com/', 'https://1.1.1.1/'):
    p = subprocess.run(['curl', '--noproxy', '*', '--silent', '--show-error', '--max-time', '15',
                        '--output', '/dev/null', '--write-out', '%{http_code}', url], capture_output=True, text=True)
    row = {'url': url, 'returncode': p.returncode, 'http_code': p.stdout, 'error': p.stderr[:512]}
    if 'api.openai.com' in url:
        assert p.returncode == 0 and p.stdout in ('401', '403'), row
    else:
        assert p.returncode in (35, 52, 56, 97) and p.stdout == '000', row
    network.append(row)
result['network'] = network
# Demonstrate the exposure explicitly without disclosing even the sentinel.
result['child_can_read_sentinel'] = os.environ.get('OPENAI_API_KEY') == 'pilot-not-a-credential'
assert result['child_can_read_sentinel']
result['config_writable'] = os.access(os.environ['CODEX_HOME'] + '/config.toml', os.W_OK)
assert result['config_writable']
Path('/home/agent/pilot-writable').write_text('container-owned')
Path('/logs/agent/pilot-writable').write_text('agent-owned')
result['home_and_logs_writable'] = True
print('PILOT_BOUNDARY ' + json.dumps(result, sort_keys=True), flush=True)
