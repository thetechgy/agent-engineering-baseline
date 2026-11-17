"""Bounded root-only process diagnostic; never used by an agent or initializer.

Observe the unchanged pinned fingerprint immediately after Popen and later on
that same live child. This does not retry a task, broker initialization or grade.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


INITIALIZER = 'b702b81adbd6f0c8dc4c840eb0a9d06810f766e3703bdb5814c32cc3ea9cb47c'


def observe(result):
    source = Path('/opt/aeb-gh/initialize.py')
    if os.geteuid() != 0 or hashlib.sha256(source.read_bytes()).hexdigest() != INITIALIZER:
        raise RuntimeError('Unmatched root initializer diagnostic')
    spec = importlib.util.spec_from_file_location('pinned_initializer', source)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    result.update(schema=1,initializer=INITIALIZER,python=sys.version.split()[0],
        observations=128,immediate_passes=0,rejections=[],children_reaped=0)
    # Separate private copies prevent socket/audit interference with the real broker.
    with tempfile.TemporaryDirectory(prefix='spawn-probe-',dir='/opt/aeb-gh') as directory:
        state = Path(directory); endpoint = state/'broker.sock'
        for name in ('fixture.py','case.json'):
            shutil.copyfile(Path('/opt/gh-eval/state')/name,state/name)
            (state/name).chmod(0o600)
        (state/'audit.jsonl').write_text(''); (state/'audit.jsonl').chmod(0o600)
        module.STATE = state; module.SOCKET = endpoint
        for index in range(result['observations']):
            process = subprocess.Popen([sys.executable,'-I',str(state/'fixture.py'),'--serve',str(state),str(endpoint)],
                env={'PATH':'/usr/local/bin:/usr/bin:/bin','LANG':'C.UTF-8'},stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            try:
                try:
                    module.fingerprint(process.pid)
                    result['immediate_passes'] += 1
                except RuntimeError as error:
                    frame = error.__traceback__
                    while frame and frame.tb_frame.f_code.co_name != 'fingerprint': frame = frame.tb_next
                    if frame is None: raise
                    command = frame.tb_frame.f_locals.get('command')
                    row = {'index':index, 'error':type(error).__name__, 'line':frame.tb_lineno,
                        'argv_count':None if command is None else len(command),
                        'child_live':process.poll() is None, 'later_verified':False}
                    result['rejections'].append(row)
                    deadline = time.monotonic()+0.2
                    while process.poll() is None and time.monotonic()<deadline:
                        try:
                            start = module.fingerprint(process.pid)
                            row.update(later_verified=True,start=start); break
                        except RuntimeError:
                            time.sleep(0.001)
                    if not row['later_verified']: raise RuntimeError('Persistent child identity failure') from error
            finally:
                if process.poll() is None: process.terminate()
                process.wait(timeout=2)
                result['children_reaped'] += 1
                if endpoint.exists(): endpoint.unlink()
    if result['children_reaped'] != result['observations']: raise RuntimeError('Incomplete diagnostic cleanup')
    return result


if __name__ == '__main__':
    result = {}
    try:
        observe(result); result['status']='complete'
    except BaseException as error:
        result.update(status='failed',error=type(error).__name__)
        print(json.dumps(result,sort_keys=True)); raise SystemExit(1)
    print(json.dumps(result,sort_keys=True))
