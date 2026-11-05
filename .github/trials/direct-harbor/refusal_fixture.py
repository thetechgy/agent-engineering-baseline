"""Diagnostic-only loopback HTTP refusal; never forwards requests or stores content."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import hashlib, json, sys, time
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
        # Parse only fixed configuration observations; discard headers/body immediately.
        body=self.rfile.read(min(int(self.headers.get('Content-Length','0')),2_000_000))
        request=json.loads(body)
        prompt=Path('/opt/trial-task-instruction.txt').read_text().strip()
        def strings(value):
            if isinstance(value,str):yield value
            elif isinstance(value,list):
                for item in value:yield from strings(item)
            elif isinstance(value,dict):
                for item in value.values():yield from strings(item)
        input_text='\n'.join(strings(request.get('input',[])))
        observed={'method':'POST','path':self.path.split('?')[0],'at':time.time(),
            'model_matches_profile':request.get('model')=='gpt-6.1-sol',
            'reasoning_high':request.get('reasoning',{}).get('effort')=='high',
            'api_bearer_sentinel_used':self.headers.get('Authorization')=='Bearer NONSECRET-DIRECT-HARBOR-DIAGNOSTIC-ONLY',
            'task_prompt_present':prompt in input_text,'output_path_present':'output/Subject.Tests.ps1' in input_text,
            'task_prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest()}
        data['requests'].append(observed);save()
        if mode=='http':
            self.send_response(503);self.send_header('Content-Length','0');self.end_headers()
        else:
            self.send_response(200);self.send_header('Content-Type','text/event-stream')
            self.send_header('Cache-Control','no-cache');self.end_headers();self.wfile.flush()
            time.sleep(75)
server=HTTPServer(('127.0.0.1',8765),Refusal)
save()
server.serve_forever()
