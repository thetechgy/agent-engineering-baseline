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
from controller_adapter import adapt


def atomic_json(path,value):
    path=Path(path)
    temporary=path.with_name(path.name+'.next')
    temporary.write_text(json.dumps(value))
    temporary.replace(path)


async def protected_gate(args, backend_port, host):
    """One operator-seeded connection; no listener remains for evaluated code."""
    state=dict(schema='operator-gate-v1',allowed_ip=args.allowed_ip,accepted=[],
               rejected=[],producer_pid=host.pid,
               producer_sha256=hashlib.sha256(Path(args.host).read_bytes()).hexdigest(),
               backend_port=backend_port,producer_failed=False,transport_closed=False)
    state_path=Path('/workspace/gate.json')
    def save():
        atomic_json(state_path,state)
    active=[]
    async def connect(reader,writer):
        peer=writer.get_extra_info('peername')[0]
        if peer!=args.allowed_ip or state['accepted']:
            state['rejected'].append(peer)
            save()
            writer.close()
            await writer.wait_closed()
            return
        state['accepted'].append(peer)
        listener.close()
        await listener.wait_closed()
        save()
        upstream_reader,upstream_writer=await asyncio.open_connection('127.0.0.1',backend_port)
        active.extend([writer,upstream_writer])
        async def copy(source,destination):
            while data:=await source.read(65536):
                destination.write(data)
                await destination.drain()
        tasks=[asyncio.create_task(copy(reader,upstream_writer)),
               asyncio.create_task(copy(upstream_reader,writer))]
        try:
            await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks: task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
            writer.close()
            upstream_writer.close()
            state['transport_closed']=True
            save()
    listener=await asyncio.start_server(connect,'0.0.0.0',9000)
    save()
    Path('/workspace/ready').write_text('ready')
    state['producer_exit']=await asyncio.to_thread(host.wait)
    state['producer_failed']=True
    save()
    listener.close()
    for writer in active: writer.close()


async def main(args):
    environment={'PATH':'/usr/bin:/bin'}
    if args.serve:
        environment['AEB_CALLBACK_JOURNAL']='/workspace/callbacks.jsonl'
    host = subprocess.Popen([args.host, '--listen', 'grpc://127.0.0.1:0'],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            env=environment, text=True)
    records = []
    recorded_bytes = 0
    endpoint = host.stdout.readline().strip()[7:]
    limits=[('grpc.max_receive_message_length',64*1024*1024),
            ('grpc.max_send_message_length',64*1024*1024)]
    channel = grpc.aio.insecure_channel(endpoint, options=limits)
    stub = g.CodeModeHostStub(channel)
    server = grpc.aio.server(options=limits)
    def record(method, direction, value):
        nonlocal recorded_bytes
        if len(records)>=4096 or recorded_bytes+value.ByteSize()*2+200>4*1024*1024:
            if not records or records[-1].get('observer_loss') is not True:
                records.append(dict(observer_loss=True, reason='record-count-limit'))
            if args.serve: atomic_json(args.out,records)
            return
        recorded_bytes += value.ByteSize()*2+200
        if value.ByteSize()>256*1024:
            records.append(dict(method=method,direction=direction,
                arguments_complete=False, retained=False, serialized_bytes=value.ByteSize(),
                sha256=hashlib.sha256(value.SerializeToString()).hexdigest()))
            if args.serve: atomic_json(args.out,records)
            return
        records.append(dict(method=method, direction=direction,
                            message=MessageToDict(value, preserving_proto_field_name=True)))
        if args.serve: atomic_json(args.out,records)
    handlers = {}
    for method in p.DESCRIPTOR.services_by_name['CodeModeHost'].methods:
        assert not method.client_streaming
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
        if args.serve:
            await protected_gate(args,port,host)
            return
        original = adapt(args.controller)
        original = original.replace("arguments={'cmd':'printf direct-native'}",
            "arguments=payload.get('direct_arguments',{'cmd':'printf direct-native'})\n"
            "            if payload.get('direct_attack'):\n"
            "                arguments={'cmd':'python3 -I /opt/experiment/attack.py '+payload['direct_attack']+' '+str(os.getpid())+' '+str(state['producer_pid'])}")
        # Actual provider wrapper is unchanged apart from isolated paths/runtime.
        with tempfile.TemporaryDirectory(prefix='cm-native-') as td:
            root = Path(td)
            controller = root/'controller.py'
            controller.write_text(original)
            output = []
            labels = ['empty', 'denied', 'direct-denied', 'uncaught-denied']
            if args.attacks:
                labels += ['direct-'+mode for mode in (
                    'fd-inject','ptrace','proc-mem','forged-output','kill-producer')]
                labels += ['direct-effect-allowed','direct-effect-denied']
            for label in labels:
                home = root/label
                home.mkdir()
                arguments = dict(cmd='printf submission-probe', workdir=str(home),
                    sandbox_permissions='require_escalated', justification='offline contract control', login=False)
                payload = dict(codex=args.codex, codex_sha256=hashlib.sha256(Path(args.codex).read_bytes()).hexdigest(),
                    home=str(home), workspace=str(home), endpoint=f'http://127.0.0.1:{port}', sandbox='read-only')
                script = ('try {await tools.exec_command('+json.dumps(arguments)+');} catch (_) {} ' if label=='denied' else '')+'text("control-finished");'
                payload['script'] = script
                if label=='uncaught-denied':
                    payload['mode']='escalated-inner'
                if label.startswith('direct-'):
                    catalog = json.loads(Path(args.catalog).read_text())
                    catalog['models'] = [m for m in catalog['models'] if m['slug']=='gpt-5.6-sol']
                    catalog['models'][0]['tool_mode'] = 'direct'
                    catalog_path = root/'catalog.json'
                    catalog_path.write_text(json.dumps(catalog))
                    payload.update(direct=True, keep_code_mode_host=True,
                        escalated=label in ('direct-denied','direct-effect-denied'))
                    if label.startswith('direct-effect-'):
                        payload.update(direct_arguments={'cmd':'printf effect-marker > '+str(home/'effect.txt')},
                                       sandbox='danger-full-access')
                    elif label!='direct-denied':
                        payload.update(direct_attack=label.removeprefix('direct-'), sandbox='danger-full-access')
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
                effect = None
                if label.startswith('direct-effect-'):
                    marker=home/'effect.txt'
                    effect=dict(scope='fixture effect.txt only', exists=marker.exists(),
                                content_matches=marker.exists() and marker.read_text()=='effect-marker')
                    assert effect['exists']==(label=='direct-effect-allowed')
                    if effect['exists']:
                        assert effect['content_matches']
                catalog_bytes = (catalog_path.read_bytes() if label.startswith('direct-')
                                 else Path(args.catalog).read_bytes())
                output.append(dict(label=label, capture=capture, grpc=records[start:], verified_effect=effect,
                    conditions=dict(model='gpt-5.6-sol', codex_sha256=payload['codex_sha256'],
                        catalog_sha256=hashlib.sha256(catalog_bytes).hexdigest(),
                        profile=('gpt-5.6-sol-direct-catalog-v1' if label.startswith('direct-')
                                 else 'gpt-5.6-sol-stock-code-mode-v1'),
                        provider='canned-responses-no-inference')))
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
    parser.add_argument('--attacks', action='store_true')
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--allowed-ip')
    asyncio.run(main(parser.parse_args()))
