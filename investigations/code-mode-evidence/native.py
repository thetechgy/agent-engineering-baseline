"""Actual App Server via an experimental inline gRPC recorder.

Loopback endpoints are deliberately NOT admitted as authenticated evidence.
This probe establishes protocol feasibility before security qualification.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import grpc
import code_mode_pb2 as p
import code_mode_pb2_grpc as g
from google.protobuf.json_format import MessageToDict


async def main(args):
    host = subprocess.Popen([args.host, '--listen', 'grpc://127.0.0.1:0'],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            env={'PATH':'/usr/bin:/bin'}, text=True)
    records = []
    endpoint = host.stdout.readline().strip()[7:]
    channel = grpc.aio.insecure_channel(endpoint)
    stub = g.CodeModeHostStub(channel)
    server = grpc.aio.server()
    def record(method, direction, value):
        records.append(dict(method=method, direction=direction,
                            message=MessageToDict(value, preserving_proto_field_name=True)))
    handlers = {}
    for method in p.DESCRIPTOR.services_by_name['CodeModeHost'].methods:
        def factory(method):
            name = method.name
            async def unary(request, context):
                record(name, 'request', request)
                try:
                    value = await getattr(stub, name)(request)
                except grpc.aio.AioRpcError as error:
                    await context.abort(error.code(), error.details())
                record(name, 'response', value)
                return value
            async def stream(request, context):
                record(name, 'request', request)
                upstream = getattr(stub, name)(request)
                try:
                    await upstream.initial_metadata()
                    await context.send_initial_metadata(())
                    async for value in upstream:
                        record(name, 'response', value)
                        yield value
                except grpc.aio.AioRpcError as error:
                    await context.abort(error.code(), error.details())
                finally:
                    upstream.cancel()
            handler = grpc.unary_stream_rpc_method_handler if method.server_streaming else grpc.unary_unary_rpc_method_handler
            return handler(stream if method.server_streaming else unary,
                request_deserializer=getattr(p, method.input_type.name).FromString,
                response_serializer=getattr(p, method.output_type.name).SerializeToString)
        handlers[method.name] = factory(method)
    server.add_generic_rpc_handlers([grpc.method_handlers_generic_handler(
        'codex.code_mode.v1.CodeModeHost', handlers)])
    port = server.add_insecure_port('127.0.0.1:0')
    await server.start()
    try:
        original = Path(args.controller).read_text()
        original = original.replace("executable=pathlib.Path('/opt/codex/bin/codex')", "executable=pathlib.Path(payload['codex'])")
        original = original.replace("info.st_uid==0 and ", "")
        original = original.replace("=='b93f6811d3f653f0fb83be4050d857fb9abbb111dfa2ce160563327daff7f306'", "==payload['codex_sha256']")
        original = original.replace("cmd+=['app-server','--listen','stdio://']", "cmd+=['app-server','--listen','stdio://','--code-mode-host',payload['endpoint']]")
        original = original.replace("home='/home/agent/.codex'", "home=payload['home']")
        original = original.replace("'HOME':'/home/agent'", "'HOME':payload['home']")
        original = original.replace("cwd='/workspace'", "cwd=payload['workspace']")
        # Actual provider wrapper is unchanged apart from isolated paths/runtime.
        with tempfile.TemporaryDirectory(prefix='cm-native-') as td:
            root = Path(td)
            controller = root/'controller.py'
            controller.write_text(original)
            output = []
            for label in ['empty', 'denied', 'direct-denied']:
                home = root/label
                home.mkdir()
                arguments = dict(cmd='printf submission-probe', workdir=str(home),
                    sandbox_permissions='require_escalated', justification='offline contract control', login=False)
                payload = dict(codex=args.codex, codex_sha256=hashlib.sha256(Path(args.codex).read_bytes()).hexdigest(),
                    home=str(home), workspace=str(home), endpoint=f'http://127.0.0.1:{port}', sandbox='read-only')
                script = ('try {await tools.exec_command('+json.dumps(arguments)+');} catch (_) {} ' if label=='denied' else '')+'text("control-finished");'
                payload['script'] = script
                if label=='direct-denied':
                    catalog = json.loads(Path(args.catalog).read_text())
                    catalog['models'] = [m for m in catalog['models'] if m['slug']=='gpt-5.6-sol']
                    catalog['models'][0]['tool_mode'] = 'direct'
                    catalog_path = root/'catalog.json'
                    catalog_path.write_text(json.dumps(catalog))
                    payload.update(direct=True, keep_code_mode_host=True, escalated=True)
                    payload['config'] = dict(model_catalog_json=str(catalog_path), model_provider='fixture',
                        model_providers={'fixture':dict(name='fixture', base_url='http://127.0.0.1:8991/v1',
                            wire_api='responses', requires_openai_auth=False)}, web_search='disabled')
                start = len(records)
                process = await asyncio.create_subprocess_exec(sys.executable, '-I', str(controller), json.dumps(payload),
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                    env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':str(home)})
                stdout, stderr = await asyncio.wait_for(process.communicate(), 60)
                assert process.returncode==0, stderr.decode()[-2000:]
                capture = json.loads(stdout)
                output.append(dict(label=label, capture=capture, grpc=records[start:]))
                print(label, capture['status'], len(records)-start, flush=True)
            Path(args.out).write_text(json.dumps(dict(schema='native-grpc-controls-v1',
                security_admission='unavailable-unqualified-loopback-producer', rows=output), indent=2))
    finally:
        await server.stop(0)
        await channel.close()
        host.terminate()
        host.wait(timeout=10)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ['host','codex','catalog','controller','out']:
        parser.add_argument('--'+name, required=True)
    asyncio.run(main(parser.parse_args()))
