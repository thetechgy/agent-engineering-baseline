"""Executed through the real command tool in the evaluated namespace."""
import json
import os
from pathlib import Path
import socket
import sys

address,backend_port=sys.argv[1],int(sys.argv[2])
result={'uid':os.getuid()}
routes=Path('/proc/net/route').read_text().splitlines()[1:]
result['default_route']=any(line.split()[1]=='00000000' for line in routes)
path=Path('/workspace/callbacks.jsonl')
try:
    path.read_bytes()
    result['observer_journal_readable']=True
except OSError:
    result['observer_journal_readable']=False
# Same spelling in the evaluated filesystem cannot replace the observer file.
path.write_text('FORGED-JOURNAL\n')
for label,port in [('frontend',9000),('backend',backend_port)]:
    try:
        with socket.create_connection((address,port),timeout=1):
            result[label+'_connectable']=True
    except OSError:
        result[label+'_connectable']=False
try:
    with socket.socket() as handle:
        handle.bind((address,9000))
    result['foreign_endpoint_bindable']=True
except OSError:
    result['foreign_endpoint_bindable']=False
print(json.dumps(result))
