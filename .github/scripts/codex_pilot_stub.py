"""Loopback-only refusal endpoint for the real CLI; no credentials or forwarding."""
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import sys

record = Path(sys.argv[1])


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
            code = 'text(await tools.exec_command({cmd: "if (printf denied > /home/agent/pilot-deny) 2>/dev/null; then exit 91; fi; printf pilot-tool-event", max_output_tokens: 100}));'
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
        payload = json.dumps({'error': {'message': 'Credential-free pilot refusal', 'type': 'invalid_request_error', 'code': 'pilot_refusal'}}).encode()
        self.send_response(400)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


HTTPServer(('127.0.0.1', 8765), Refuse).serve_forever()
