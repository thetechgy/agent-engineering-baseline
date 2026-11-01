"""Real stock gRPC host controls. Canned callbacks; no provider inference."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import grpc
import code_mode_pb2 as p
import code_mode_pb2_grpc as g


def projection(message):
    from google.protobuf.json_format import MessageToDict
    return MessageToDict(message, preserving_proto_field_name=True)


async def trial(stub, label, source, truncation=None):
    request = p.OpenSessionRequest()
    request.cell_execution_limits.max_heap_size_bytes = 768 * 1024 * 1024
    if truncation is not None:
        request.output_truncation = truncation
    lease = stub.OpenSession(request)
    opened = await asyncio.wait_for(lease.read(), 10)
    session = opened.opened.session_id
    calls, events = [], []
    closed = asyncio.Event()
    async def read_events():
        while True:
            event = await lease.read()
            if event is grpc.aio.EOF:
                return
            events.append(projection(event))
            if event.HasField('cell_closed'):
                closed.set()
    subscription = stub.SubscribeToToolCalls(p.SubscribeToToolCallsRequest(session_id=session))
    async def read_calls():
        async for call in subscription:
            value = projection(call)
            value.pop('input_json', None)
            value['input_bytes'] = len(call.input_json)
            value['input_sha256'] = hashlib.sha256(call.input_json).hexdigest()
            calls.append(value)
            await stub.CompleteToolCall(p.CompleteToolCallRequest(
                session_id=session, invocation_id=call.invocation_id,
                succeeded=p.ToolCallSucceeded(output_json=b'{"ok":true}')))
    tasks = [asyncio.create_task(read_events()), asyncio.create_task(read_calls())]
    try:
        # RPC stream headers establish subscription registration before execution.
        await asyncio.wait_for(subscription.initial_metadata(), 10)
        outcomes = []
        execution = stub.Execute(p.ExecuteRequest(session_id=session, execution_id=label,
            tool_call_id='outer-'+label, source=source, yield_time_ms=1000,
            enabled_tools=[p.ToolDefinition(name='probe', tool_name=p.ToolName(name='probe'),
                kind=p.TOOL_KIND_FUNCTION, input_schema_json=b'{"type":"object"}')]))
        async for event in execution:
            outcomes.append(projection(event))
            if event.HasField('outcome') and event.outcome.HasField('yielded'):
                cell = event.outcome.cell_id
                for index in range(30):
                    result = await stub.Wait(p.WaitRequest(session_id=session, cell_id=cell,
                        wait_id=f'{label}-{index}', yield_time_ms=1000))
                    outcomes.append(projection(result))
                    if result.live_cell.HasField('completed'):
                        break
        print(label, 'outcomes', outcomes, 'events', events,
              'reader_errors', [str(t.exception()) for t in tasks if t.done() and not t.cancelled()], flush=True)
        await asyncio.wait_for(closed.wait(), 5)
        return dict(label=label, opened=projection(opened), calls=calls,
                    events=events, outcomes=outcomes)
    finally:
        await stub.CloseSession(p.CloseSessionRequest(session_id=session))
        subscription.cancel()
        lease.cancel()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def main(args):
    environment = {'PATH':'/usr/bin:/bin'}
    if os.environ.get('AEB_CALLBACK_JOURNAL'):
        environment['AEB_CALLBACK_JOURNAL'] = os.environ['AEB_CALLBACK_JOURNAL']
    host = subprocess.Popen([args.host, '--listen', 'grpc://127.0.0.1:0'],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            env=environment, text=True)
    try:
        endpoint = host.stdout.readline().strip()
        assert endpoint.startswith('http://127.0.0.1:'), endpoint
        async with grpc.aio.insecure_channel(endpoint[7:], options=[
            ('grpc.max_receive_message_length', 70*1024*1024)]) as channel:
            await asyncio.wait_for(channel.channel_ready(), 10)
            stub = g.CodeModeHostStub(channel)
            rows = []
            cases = [('empty', 'text("control-finished");'),
                     ('normal', 'await tools.probe({value:1});text("control-finished");'),
                     ('serialization-rejection', 'try {await tools.probe({value:1n});} catch (_) {} text("control-finished");'),
                     ('oversized-rejection', 'try {await tools.probe({value:"x".repeat(64*1024*1024)});} catch (_) {} text("control-finished");')]
            for label, source in cases:
                row = await trial(stub, label, source)
                rows.append(row)
                Path(args.out).write_text(json.dumps(dict(schema='stock-host-controls-v1',
                    evidence_class='real-host-scripted-no-provider', rows=rows), indent=2))
                print(label, len(row['calls']), row['events'], flush=True)
            assert len(rows[0]['calls']) == 0 and len(rows[1]['calls']) == 1
            assert len(rows[2]['calls']) == 0 and len(rows[3]['calls']) == 0
            for row in (rows[0], rows[2], rows[3]):
                assert row['events'][-1]['cell_closed'].get('final_tool_call_sequence', '0') == '0'
                assert 'control-finished' in json.dumps(row['outcomes'])
    finally:
        host.terminate()
        host.wait(timeout=10)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', required=True)
    parser.add_argument('--out', required=True)
    asyncio.run(main(parser.parse_args()))
