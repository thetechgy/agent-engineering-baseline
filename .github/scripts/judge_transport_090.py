"""Qualification-only OpenAI HTTP boundary for the pinned 0.9 verifier.

No forwarding, credentials, production registration, or live mode. The upstream
request builder still sees the official endpoint, including its native token key.
Only HTTPS transport is replaced by an in-process loopback HTTP responder.
"""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
import signal
import threading
import time
import urllib.request
from unittest.mock import patch

URL = 'https://api.openai.com/v1/chat/completions'
MODEL = 'gpt-5.6-sol'
SENTINEL = 'fixture-not-a-provider-credential'
SETTINGS = {
    'SKILL_EVAL_LLM_PROVIDER': 'openai', 'LLM_JUDGE_MODEL': MODEL,
    'SKILL_EVAL_LLM_API_KEY': SENTINEL, 'SKILL_EVAL_LLM_BASE_URL': 'https://api.openai.com/v1',
    'LLM_JUDGE_RETRY_POLICY': 'strict', 'LLM_JUDGE_FALLBACK_POLICY': 'replace',
    'LLM_JUDGE_FALLBACK_MODELS': '', 'SKILL_EVAL_LLM_MAX_RETRIES': '1',
    'SKILL_EVAL_LLM_RETRY_BASE_DELAY': '0.001', 'SKILL_EVAL_LLM_RETRY_MAX_DELAY': '0.01',
    'SKILL_EVAL_LLM_JUDGE_BUDGET_SEC': '1',
}


def reply_for(payload):
    prompt = payload['messages'][0]['content']
    if 'EXPECTED BEHAVIORS:' in prompt:
        count = int(re.search(r'"results" must hold exactly (\d+) entries', prompt)[1])
        return {'results': [{'step': n, 'passed': True, 'reason': 'Transport fixture'}
                            for n in range(1, count + 1)], 'summary': 'Transport fixture'}
    if '"criteria" object' in prompt:
        return {'criteria': dict.fromkeys(('ACTION_CORRECT', 'FACTUALLY_ACCURATE', 'TASK_ADDRESSED',
                                          'ACTIONABLE', 'FORMAT_FOLLOWED'), True), 'reason': 'Transport fixture'}
    return {'achieved': True, 'user_goal': 'Fixture', 'end_state': 'Fixture', 'reason': 'Transport fixture'}


class Responder:
    def __init__(self):
        self.requests = []
        self.scenario = 'valid'
        self.metric_counts = {}

    def respond(self, payload):
        response = reply_for(payload)
        metric = 'accuracy' if 'criteria' in response else 'behavior_check' if 'results' in response else 'goal_accuracy'
        ordinal = self.metric_counts.get(metric, 0) + 1
        self.metric_counts[metric] = ordinal
        scenario = self.scenario
        row = {'scenario': scenario, 'metric': metric, 'ordinal': ordinal, 'payload': payload,
               'url': URL, 'sentinel_authenticated': True}
        self.requests.append(row)
        status = 200
        if scenario == 'unknown_behavior':
            response['results'][0]['passed'] = None
        if scenario == 'interrupt':
            os.kill(os.getpid(), signal.SIGINT)
            time.sleep(0.1)
        if scenario == 'timeout':
            time.sleep(1.1)
        if scenario in ('wrong_shape', 'legacy_format_retry') and (scenario == 'wrong_shape' or ordinal == 1):
            response = {'score': 1}
        if scenario == 'partial' and metric == 'goal_accuracy' or scenario in ('provider_error', 'error_usage'):
            status, response = 400, {'error': {'message': 'Fixture provider error', 'type': 'invalid_request_error'}}
        if scenario == 'refusal':
            body = {'choices': [{'message': {'refusal': 'Fixture refusal'}, 'finish_reason': 'stop'}]}
        elif scenario in ('schema_fallback', 'retry_exhausted_schema') and ordinal == 1 and 'response_format' in payload:
            status, response = 400, {'error': {'message': 'response_format json_schema is not supported', 'param': 'response_format'}}
            body = response
        elif scenario in ('transient_retry', 'retry_exhausted_schema') and (ordinal == 1 or scenario == 'retry_exhausted_schema'):
            status, body = 503, {'error': {'message': 'Fixture unavailable'}}
        elif status != 200:
            body = response
        elif scenario == 'wrong_envelope':
            body = {'output': []}
        else:
            body = {'choices': [{'message': {'content': json.dumps(response)}, 'finish_reason': 'stop'}]}
        if status == 200 and scenario != 'missing_usage' or scenario == 'error_usage':
            body['usage'] = {'prompt_tokens': 19, 'completion_tokens': 7, 'total_tokens': 26,
                             'prompt_tokens_details': {'cached_tokens': 5},
                             'completion_tokens_details': {'reasoning_tokens': 3,
                                 'accepted_prediction_tokens': 2, 'rejected_prediction_tokens': 0}}
            if scenario == 'malformed_usage':
                body['usage']['prompt_tokens'] = 'nineteen'
            if scenario == 'inconsistent_usage':
                body['usage']['total_tokens'] = 999
        row.update(status=status, supplied_usage=body.get('usage'), response=body)
        return status, json.dumps(body).encode()

    @contextmanager
    def boundary(self):
        responder = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                # Observe a redirect follow independently of the client's ledger.
                responder.requests.append({'scenario': responder.scenario, 'metric': 'redirect_follow',
                    'method': 'GET', 'payload': {}, 'url': URL, 'status': 400,
                    'sentinel_authenticated': self.headers.get('Authorization') == 'Bearer ' + SENTINEL})
                body = b'{"error":{"message":"Unexpected redirect follow"}}'
                self.send_response(400)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                assert self.path == '/v1/chat/completions'
                assert self.headers.get('Authorization') == 'Bearer ' + SENTINEL
                length = int(self.headers['Content-Length'])
                assert 0 < length < 1_000_000
                status, body = responder.respond(json.loads(self.rfile.read(length)))
                try:
                    self.send_response(status)
                    if responder.scenario == 'redirect':
                        self.send_header('Location', f'http://127.0.0.1:{server.server_port}/redirect-probe')
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        local_url = f'http://127.0.0.1:{server.server_port}/v1/chat/completions'
        local = urllib.request.build_opener(urllib.request.ProxyHandler({}))

        class LocalHTTPS(urllib.request.HTTPSHandler):
            def https_open(self, request):
                assert request.full_url == URL, 'Unexpected provider destination'
                assert request.get_method() == 'POST'
                assert request.get_header('Authorization') == 'Bearer ' + SENTINEL
                return local.open(urllib.request.Request(local_url, data=request.data, headers=dict(request.headers)),
                                  timeout=request.timeout)

        previous = urllib.request._opener
        urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({}), LocalHTTPS()))
        try:
            yield server.server_port
        finally:
            urllib.request.install_opener(previous)
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    @contextmanager
    def case(self, verifier, scenario, **overrides):
        self.scenario = scenario
        self.metric_counts = {}
        # Cache lifetime is one verifier process in production; each fixture trial
        # here uses the same imported module, so explicitly reproduce that lifetime.
        verifier._SCHEMA_UNSUPPORTED_TARGETS.clear()
        with patch.dict(os.environ, {**SETTINGS, **overrides}):
            yield
