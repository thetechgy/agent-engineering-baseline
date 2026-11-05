"""Diagnostic-only loopback HTTP refusal; never forwards requests or stores content."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json, sys, time
from pathlib import Path
mode=sys.argv[1]
assert mode in ('http','idle')
path=Path('/tmp/provider-observation.json')
data={'mode':mode,'requests':[]}
def save():path.write_text(json.dumps(data))
class Refusal(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*args):pass
    def do_GET(self):
        self.send_response(404);self.send_header('Content-Length','0');self.end_headers()
    def do_POST(self):
        # Discard input; retain only counts/timing, never headers or request bodies.
        self.rfile.read(min(int(self.headers.get('Content-Length','0')),2_000_000))
        data['requests'].append({'method':'POST','path':self.path.split('?')[0],'at':time.time()});save()
        if mode=='http':
            self.send_response(503);self.send_header('Content-Length','0');self.end_headers()
        else:
            self.send_response(200);self.send_header('Content-Type','text/event-stream')
            self.send_header('Cache-Control','no-cache');self.end_headers();self.wfile.flush()
            time.sleep(75)
server=HTTPServer(('127.0.0.1',8765),Refusal)
save()
server.serve_forever()
