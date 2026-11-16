"""Build-time copies of a trusted inventory; called only by the runtime recipe."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluation_resources import regular_bytes, validate_inventory


def provision(inventory):
    validate_inventory(inventory)
    for row in inventory['files']:
        if row['role'] == 'input': continue
        # The runtime maps staged skill sources to workspace before this step.
        source = Path('/workspace/skills') / Path(row['source']).relative_to('environment/skills')
        raw = regular_bytes(source)
        if hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Provisioning source mismatch')
        destination = Path(row['path'])
        if destination != source:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() or destination.is_symlink():
                raise ValueError('Refusing existing resource destination')
            shutil.copyfile(source, destination)
        destination.chmod(0o444)
    # Freeze the selected directories; agent filesystem permissions remain in force.
    for value in sorted(inventory['directories'], key=len, reverse=True):
        path = Path(value)
        if path.exists() and any(path == Path(r['path']).parent for r in inventory['files'] if r['role'] != 'input'):
            path.chmod(0o555)


if __name__ == '__main__':
    provision(json.loads(regular_bytes(Path(sys.argv[1]))))
