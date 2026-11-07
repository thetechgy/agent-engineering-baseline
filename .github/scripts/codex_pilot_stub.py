"""Loopback-only non-forwarding qualification endpoint for the real CLI; no credentials or forwarding."""
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import sys

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
                'success': "python3 /opt/pilot/codex_pilot_probe.py && printf %s QmVmb3JlQWxsIHsgLiAnL3dvcmtzcGFjZS9pbnB1dC9TdWJqZWN0LnBzMScgfQpEZXNjcmliZSAnR2V0LUFjdGl2ZVBvcnQnIHsKICAgIEl0ICdlbWl0cyBub3RoaW5nIGZvciBlbXB0eSBpbnB1dCcgewogICAgICAgIEAoR2V0LUFjdGl2ZVBvcnQgLUVuZHBvaW50IEAoKSkgfCBTaG91bGQgLUhhdmVDb3VudCAwCiAgICB9CiAgICBJdCAnZW1pdHMgYW4gaW50ZWdlciBmb3Igb25lIGVuYWJsZWQgZW5kcG9pbnQnIHsKICAgICAgICAkYWN0dWFsID0gQChHZXQtQWN0aXZlUG9ydCAtRW5kcG9pbnQgQChbcHNjdXN0b21vYmplY3RdQHsgUG9ydCA9IDQ0MzsgRW5hYmxlZCA9ICR0cnVlIH0pKQogICAgICAgICRhY3R1YWwgfCBTaG91bGQgLUhhdmVDb3VudCAxCiAgICAgICAgJGFjdHVhbFswXSB8IFNob3VsZCAtQmUgNDQzCiAgICAgICAgJGFjdHVhbFswXSB8IFNob3VsZCAtQmVPZlR5cGUgKFtpbnRdKQogICAgfQogICAgSXQgJ2ZpbHRlcnMgZGlzYWJsZWQgZW5kcG9pbnRzIGFuZCByZW1vdmVzIGR1cGxpY2F0ZXMnIHsKICAgICAgICAkYWN0dWFsID0gQChHZXQtQWN0aXZlUG9ydCAtRW5kcG9pbnQgQCgKICAgICAgICAgICAgW3BzY3VzdG9tb2JqZWN0XUB7IFBvcnQgPSA0NDM7IEVuYWJsZWQgPSAkdHJ1ZSB9CiAgICAgICAgICAgIFtwc2N1c3RvbW9iamVjdF1AeyBQb3J0ID0gODA7IEVuYWJsZWQgPSAkdHJ1ZSB9CiAgICAgICAgICAgIFtwc2N1c3RvbW9iamVjdF1AeyBQb3J0ID0gMjI7IEVuYWJsZWQgPSAkZmFsc2UgfQogICAgICAgICAgICBbcHNjdXN0b21vYmplY3RdQHsgUG9ydCA9IDgwOyBFbmFibGVkID0gJHRydWUgfQogICAgICAgICkpCiAgICAgICAgJGFjdHVhbCB8IFNob3VsZCAtSGF2ZUNvdW50IDIKICAgICAgICAkYWN0dWFsWzBdIHwgU2hvdWxkIC1CZSA4MAogICAgICAgICRhY3R1YWxbMV0gfCBTaG91bGQgLUJlIDQ0MwogICAgICAgIGZvcmVhY2ggKCRwb3J0IGluICRhY3R1YWwpIHsgJHBvcnQgfCBTaG91bGQgLUJlT2ZUeXBlIChbaW50XSkgfQogICAgfQp9Cg== | base64 -d > /workspace/output/Subject.Tests.ps1",
                'command-failure': "printf pilot-command-failure; exit 23",
                'interruption': "printf pilot-command-started; sleep 120",
            }[scenario]
            code = 'text(await tools.exec_command(' + json.dumps({'cmd': command, 'max_output_tokens': 4096}) + '));'
            events = [
                {'type': 'response.created', 'response': {'id': 'pilot-fixture-1'}},
                {'type': 'response.output_item.done', 'item': {'type': 'custom_tool_call',
                    'call_id': 'pilot-tool-1', 'name': 'exec', 'input': code}},
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
