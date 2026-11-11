#!/usr/bin/env python3
"""Run the existing two-arm native probe, retaining its failure as evidence."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    if any(os.environ.get(k) for k in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'NVIDIA_API_KEY')):
        raise ValueError('Credential-free qualification required')
    args.output.mkdir(parents=True)
    # Import the selected source unchanged; instrumentation observes resolver
    # shape only. No probes, DNS settings, network policy or fixture are replaced.
    sys.path.insert(0, str(args.source / '.github/scripts'))
    import codex_pilot as pilot
    from qualify_evaluator_candidate import native_compose_config
    native_compose_config(args.source)
    identity = {'revision': subprocess.check_output(['git','rev-parse','HEAD'], cwd=args.source, text=True).strip(),
        'python': sys.version, 'packages': {n: importlib.metadata.version(n) for n in ('harbor','skillevaluator')},
        'inference': False, 'instrumentation': 'none; unchanged existing native probe',
        'runner_image': {k: os.environ.get(k) for k in ('ImageOS','ImageVersion')},
        'sources': {n: hashlib.sha256((args.source / '.github/scripts' / n).read_bytes()).hexdigest()
            for n in ('codex_pilot.py','codex_pilot_agent.py','codex_pilot_environment.py','codex_pilot_probe.py','skill_evidence.py')},
        'docker_version': subprocess.check_output(['docker','version','--format','{{.Server.Version}}'], text=True).strip(),
        'compose_version': subprocess.check_output(['docker','compose','version','--short'], text=True).strip()}
    import harbor.environments.docker.docker as docker
    context = docker.DockerEnvironment._EGRESS_CONTROL_SIDECAR_CONTEXT_PATH
    identity['sidecar_sources'] = {str(p.relative_to(context)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(context.rglob('*')) if p.is_file()}
    (args.output / 'native').mkdir()
    try:
        pilot.run(args.output / 'native', probe=True)
        identity['complete'] = True
    except Exception as error:
        identity.update(complete=False, exception=type(error).__name__, message=str(error))
    (args.output / 'qualification.json').write_text(json.dumps(identity, indent=2)+'\n')
    if not (args.output / 'native/evidence/cleanup.json').is_file():
        raise ValueError('Native run did not reach cleanup evidence')
    if json.loads((args.output / 'native/evidence/cleanup.json').read_text())['complete'] is not True:
        raise ValueError('Native resources not disposed')
    if args.require_complete and not identity['complete']:
        raise ValueError('CLI observation readiness unavailable: ' + identity['message'])


if __name__ == '__main__':
    main()
