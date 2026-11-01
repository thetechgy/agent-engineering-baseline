"""Real transport/producer controls; this does not qualify the loopback proxy."""
import argparse
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import grpc
import code_mode_pb2 as p
import code_mode_pb2_grpc as g
from stock import projection


def start(binary, port=0):
    process = subprocess.Popen([binary, '--listen', f'grpc://127.0.0.1:{port}'],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        env={'PATH':'/usr/bin:/bin'})
    endpoint = process.stdout.readline().strip()
    assert endpoint.startswith('http://127.0.0.1:')
    return process, endpoint[7:]


async def main(args):
    process, endpoint = start(args.host)
    rows = []
    try:
        async with grpc.aio.insecure_channel(endpoint) as channel:
            stub = g.CodeModeHostStub(channel)
            for value in [None, 1, 2]:
                request = p.OpenSessionRequest()
                if value is not None:
                    request.output_truncation = value
                lease = stub.OpenSession(request)
                opened = await asyncio.wait_for(lease.read(), 10)
                rows.append(dict(test='truncation-negotiation', requested=value,
                    response=projection(opened),
                    selected_present=opened.opened.HasField('output_truncation')))
                # Stock 0.166.0 declares fields but retains client truncation.
                assert not opened.opened.HasField('output_truncation')
                await stub.CloseSession(p.CloseSessionRequest(session_id=opened.opened.session_id))
                lease.cancel()
            lease = stub.OpenSession(p.OpenSessionRequest())
            opened = await asyncio.wait_for(lease.read(), 10)
            old_session = opened.opened.session_id
            # A separate OS client, supplied the session ID, can close it.
            child_code = (
                'import grpc,code_mode_pb2 as p,code_mode_pb2_grpc as g,sys;'
                'g.CodeModeHostStub(grpc.insecure_channel(sys.argv[1])).CloseSession('
                'p.CloseSessionRequest(session_id=sys.argv[2]),timeout=5)')
            child = await asyncio.create_subprocess_exec(sys.executable, '-c', child_code,
                endpoint, old_session, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            out, err = await child.communicate()
            assert child.returncode == 0, err.decode()
            rows.append(dict(test='separate-client-close', accepted=True,
                limit='session identifier supplied to attacker; protocol identity is not authentication'))
            lease.cancel()
            lease = stub.OpenSession(p.OpenSessionRequest())
            opened = await asyncio.wait_for(lease.read(), 10)
            old_session = opened.opened.session_id
            old_pid = process.pid
            process.terminate()
            process.wait(timeout=10)
            try:
                await lease.read()
            except grpc.aio.AioRpcError as error:
                rows.append(dict(test='transport-interruption', code=error.code().name,
                                 security_admission='unavailable'))
            process, same_endpoint = start(args.host, int(endpoint.rsplit(':',1)[1]))
            assert same_endpoint == endpoint and process.pid != old_pid
            # The existing URL transport may reconnect to a different producer.
            lease2 = stub.OpenSession(p.OpenSessionRequest(), wait_for_ready=True, timeout=10)
            replacement = await lease2.read()
            rows.append(dict(test='same-endpoint-producer-replacement', old_pid=old_pid,
                new_pid=process.pid, new_session=replacement.opened.session_id,
                security_admission='unavailable-producer-generation-changed'))
            assert replacement.opened.session_id != old_session
            lease2.cancel()
        Path(args.out).write_text(json.dumps(dict(evidence_class='actual-host-and-separate-client',
            producer_authenticity='not-qualified', rows=rows), indent=2))
    finally:
        process.terminate()
        process.wait(timeout=10)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--host',required=True)
    parser.add_argument('--out',required=True)
    asyncio.run(main(parser.parse_args()))
