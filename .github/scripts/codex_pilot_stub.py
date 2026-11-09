"""Loopback-only non-forwarding qualification endpoint for the real CLI; no credentials or forwarding."""
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import sys

# The trusted host supplies this only at credential-free probe startup. Image
# bytes contain no qualification answer and there is no fallback payload.
if len(sys.argv) not in (4, 5):
    raise SystemExit('Probe fixture must be supplied at runtime')
fixture = sys.argv[3]
if not 0 < len(base64.b64decode(fixture, validate=True)) <= 65536:
    raise ValueError('Invalid probe fixture size')
commands = json.loads(base64.b64decode(sys.argv[4], validate=True)) if len(sys.argv) == 5 else None
if commands is not None and (not isinstance(commands, list) or not 0 < len(commands) <= 16 or any(not isinstance(c, str) or len(c) > 131072 for c in commands)):
    raise ValueError('Invalid probe commands')
record = Path(sys.argv[1])
scenario = sys.argv[2]


class Refuse(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        size = int(self.headers.get('Content-Length', '0'))
        if not 0 < size <= 4 * 1024 * 1024:
            self.send_error(413)
            return
        raw = self.rfile.read(size)
        body = json.loads(raw)
        # Save only nonsensitive frozen-request observations; discard auth headers.
        value = {'request_keys': sorted(body), 'tool_definitions': body.get('tools'), 'path': self.path, 'model': body.get('model'), 'reasoning': body.get('reasoning'),
                 'input_sha256': hashlib.sha256(json.dumps(body.get('input'), sort_keys=True).encode()).hexdigest(),
                 'input': body.get('input'), 'tools': [t.get('name', t.get('type')) for t in body.get('tools', [])],
                 'service_tier': body.get('service_tier'), 'stream': body.get('stream'),
                 'requests': (json.loads(record.read_text())['requests'] if record.exists() else 0) + 1}
        record.write_text(json.dumps(value, indent=2) + '\n')
        if value['requests'] == 1:
            command = {
                'success': f"python3 /opt/pilot/codex_pilot_probe.py && printf %s {fixture} | base64 -d > /workspace/output/Subject.Tests.ps1",
                'command-failure': "printf pilot-command-failure; exit 23",
                'interruption': "printf pilot-command-started; sleep 120",
            }[scenario]
            issued = commands if commands is not None and scenario == 'success' else [command]
            events = [
                {'type': 'response.created', 'response': {'id': 'pilot-fixture-1'}},
                *[{'type': 'response.output_item.done', 'item': {'type': 'custom_tool_call',
                    'call_id': 'pilot-tool-' + str(i), 'name': 'exec',
                    'input': 'text(await tools.exec_command(' + json.dumps({'cmd': cmd, 'max_output_tokens': 4096}) + '));'}}
                  for i, cmd in enumerate(issued)],
                {'type': 'response.completed', 'response': {'id': 'pilot-fixture-1',
                    'usage': {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0}}},
            ]
            payload = ''.join('event: '+event['type']+'\ndata: '+json.dumps(event)+'\n\n' for event in events).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if scenario == 'command-failure':
            payload = json.dumps({'error': {'message': 'Credential-free deliberate failure', 'type': 'invalid_request_error', 'code': 'pilot_failure'}}).encode()
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
        else:
            events = [
                {'type': 'response.created', 'response': {'id': 'pilot-fixture-2'}},
                {'type': 'response.output_item.done', 'item': {'id': 'pilot-final', 'type': 'message', 'role': 'assistant',
                 'content': [{'type': 'output_text', 'text': 'Credential-free qualification complete.'}]}},
                {'type': 'response.completed', 'response': {'id': 'pilot-fixture-2',
                 'usage': {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0}}},
            ]
            payload = ''.join('event: '+e['type']+'\ndata: '+json.dumps(e)+'\n\n' for e in events).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


HTTPServer(('127.0.0.1', 8765), Refuse).serve_forever()
