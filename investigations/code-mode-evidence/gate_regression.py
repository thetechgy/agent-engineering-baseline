"""Actual asyncio listener regression, separate from protocol qualification."""
import asyncio
import json
import platform


async def probe(wait_inside_handler):
    handlers=[]
    async def serve(reader,writer):
        handlers.append(asyncio.current_task())
        try:
            listener.close()
            if wait_inside_handler:
                await listener.wait_closed()
            writer.write(b'forwarded')
            await writer.drain()
        finally:
            writer.close()
    listener=await asyncio.start_server(serve,'127.0.0.1',0)
    port=listener.sockets[0].getsockname()[1]
    reader,writer=await asyncio.open_connection('127.0.0.1',port)
    try:
        try:
            result=(await asyncio.wait_for(reader.read(),1)).decode()
        except TimeoutError:
            result='blocked'
    finally:
        writer.close()
        await writer.wait_closed()
        for task in handlers: task.cancel()
        await asyncio.gather(*handlers,return_exceptions=True)
        listener.close()
        await listener.wait_closed()
    return result


async def main():
    before,after=await probe(True),await probe(False)
    assert before=='blocked' and after=='forwarded',(before,after)
    print(json.dumps(dict(evidence_class='real-loopback-primitive',python=platform.python_version(),
                         before=before,after=after)))


asyncio.run(main())
