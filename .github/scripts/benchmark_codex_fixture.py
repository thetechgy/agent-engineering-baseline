"""Non-forwarding Responses fixture for the direct-tool native benchmark."""
import base64
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import sys
import time


SENTINEL = 'pilot-not-a-credential'
TOOL_ROUTE = 'functions.exec_command'
MODEL = 'gpt-6.2-sol'


def observe_request(path, authorization, body):
    declarations = {
        tool['name']: tool['type']
        for item in body['input']
        if item.get('type') == 'additional_tools' and item.get('role') == 'developer'
        for namespace in item['tools']
        if namespace.get('type') == 'namespace' and namespace.get('name') == 'functions'
        for tool in namespace['tools']
    }
    if (path != '/v1/responses' or authorization != 'Bearer ' + SENTINEL
            or body['model'] != MODEL or body['reasoning']['effort'] != 'high'
            or declarations.get('exec_command') != 'function' or declarations.get('apply_patch') != 'custom'
            or 'exec' in declarations):
        raise ValueError('Direct Codex request policy differs')
    return {'path': path, 'authorization_matches_sentinel': True, 'model': MODEL,
            'reasoning': {'effort': 'high'}, 'native_tool_route': TOOL_ROUTE}


def tool_items(commands):
    for index, operation in enumerate(commands):
        identity = {'call_id': f'benchmark-tool-{index}', 'namespace': 'functions'}
        if isinstance(operation, str) and 0 < len(operation) <= 131072:
            yield {**identity, 'type': 'function_call', 'name': 'exec_command',
                   'arguments': json.dumps({'cmd': operation, 'max_output_tokens': 4096})}
        elif (type(operation) is dict and set(operation) == {'tool', 'input', 'expect_failure'}
              and operation['tool'] == 'apply_patch' and operation['expect_failure'] is False
              and isinstance(operation['input'], str) and 0 < len(operation['input']) <= 131072):
            yield {**identity, 'type': 'custom_tool_call', 'name': 'apply_patch', 'input': operation['input']}
        else:
            raise ValueError('Invalid direct benchmark fixture operation')


def serve(record, scenario, commands):
    if scenario not in ('benchmark-priced', 'native-deadline') or type(commands) is not list or not 0 < len(commands) <= 16:
        raise ValueError('Invalid native benchmark fixture')
    tools = list(tool_items(commands))
    requests = []

    class Fixture(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4 * 1024 * 1024 or len(requests) >= 2:
                    raise ValueError('Unexpected direct benchmark request')
                observation = observe_request(self.path, self.headers.get('Authorization'), json.loads(self.rfile.read(length)))
            except (KeyError, TypeError, ValueError):
                self.send_error(400, 'Invalid direct benchmark request')
                return
            requests.append(observation)
            count = len(requests)
            record.write_text(json.dumps({**observation, 'requests': count, 'request_observations': requests}) + '\n')
            if scenario == 'native-deadline' and count == 2:
                time.sleep(120)
                return
            if count == 1:
                items = tools
                input_tokens, cached_tokens, output_tokens = (7, 0, 3) if scenario == 'native-deadline' else (100, 40, 10)
            else:
                items = [{'type': 'message', 'id': 'benchmark-final', 'role': 'assistant',
                          'content': [{'type': 'output_text', 'text': 'Credential-free qualification complete.'}]}]
                input_tokens, cached_tokens, output_tokens = (200, 60, 20)
            response = {'id': f'benchmark-fixture-{count}'}
            usage = {'input_tokens': input_tokens, 'input_tokens_details': {'cached_tokens': cached_tokens},
                     'output_tokens': output_tokens, 'total_tokens': input_tokens + output_tokens}
            events = [{'type': 'response.created', 'response': response},
                      *({'type': 'response.output_item.done', 'item': item} for item in items),
                      {'type': 'response.completed', 'response': {**response, 'usage': usage}}]
            payload = ''.join('event: ' + event['type'] + '\ndata: ' + json.dumps(event) + '\n\n'
                              for event in events).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    with HTTPServer(('127.0.0.1', 8765), Fixture) as server:
        server.serve_forever()


if __name__ == '__main__':
    output, scenario, _, payload = sys.argv[1:]
    serve(Path(output), scenario, json.loads(base64.b64decode(payload, validate=True)))
