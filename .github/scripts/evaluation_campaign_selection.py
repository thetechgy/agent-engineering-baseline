"""Reviewed campaign selection and producer/layout registration, never shell text."""
import argparse
import re
from pathlib import Path
import sys

from evaluation_campaign_core import require
from evaluation_runtime import ROOT
import skill_reports as reports

REGISTRY = '.github/evals/campaigns/selections.json'


def registry_path(identity):
    # Historical dispatch receipts bind every byte of the scored registry.
    if identity == 'case-observation':
        return ROOT / '.github/evals/campaigns/observation-selections.json'
    if identity == 'case-observation-1710':
        return ROOT / '.github/evals/campaigns/observation-1710-selections.json'
    return ROOT / REGISTRY


def selection(identity):
    registry = reports.read_json(registry_path(identity))
    require(registry['version'] == 1 and identity in registry['campaigns'], 'Unregistered campaign selection')
    return registry['campaigns'][identity]


def selected_task(identity):
    from evaluation_tasks import load
    identity = {"case-observation": "case-observation-1710",
                "case-observation-1691": "case-observation"}.get(identity, identity)
    row = selection(identity)
    task = load(ROOT / row['definition'])
    require(task.definition['id'] == identity, 'Selection/definition mismatch')
    return task


def registration(task):
    row = selection(task.definition['id'])
    require(row['definition'] == task.member, 'Selection/definition mismatch')
    return row


def owning_evaluator(task):
    if task.definition.get('type') == 'judge-only':
        import evaluator_profiles
        return evaluator_profiles.ACCOUNTING
    from evaluation_runtime import evaluator, read_profile
    return evaluator(read_profile(ROOT / task.definition['runtime_profile']))


def location(task, artifact, producer):
    """Only reviewed workflow/name/layout tuples; paths never come from inputs."""
    row = registration(task)
    matches = [p for p in row['producers'] if producer.get('path') == p['workflow']
               and artifact.get('name') == p['artifact'] + '-' + str(producer.get('run_attempt'))]
    require(len(matches) == 1, 'Unregistered preparation producer/layout')
    member = matches[0]['location']
    require(isinstance(member, str) and len(member) <= 256
            and re.fullmatch(r'(?:[a-z0-9-]+/)+evidence', member) is not None,
            'Unsafe registered preparation location')
    return member


def binding(task):
    from evaluation_campaign_protocol import digest
    return {'definition': task.member, 'definition_digest': digest(ROOT / task.member),
            'selection_digest': digest(registry_path(task.definition['id'])),
            **({'selected_skill': task.definition['skill'], 'selected_case': task.definition['source_case']} if getattr(task, "diagnostic_observation", False) else {})}


def main():
    from evaluation_campaign import main as campaign_main, no_credentials
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['qualify', 'prepare', 'check-preparation', 'authenticate', 'live', 'inspect'])
    parser.add_argument('--campaign', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--preparation', type=Path)
    parser.add_argument('--qualification', type=Path)
    parser.add_argument('--authentication-qualification', type=Path)
    parser.add_argument('--approval')
    parser.add_argument('--artifact')
    args = parser.parse_args()
    if args.action != 'live': no_credentials()
    task = selected_task(args.campaign)
    row = registration(task)
    definitions = row['controls'] if args.action == 'qualify' else [task.member]
    action, output = args.action, args.output.absolute()
    require(output.resolve() == output and not output.exists() and not output.is_relative_to(ROOT),
            'Use a new real persistent output outside checkout')
    if action == 'inspect':
        from evaluation_campaign_protocol import acquire
        require(args.artifact is not None, 'Preparation artifact ID required')
        args.preparation, metadata, producer, internal = acquire(output, args.artifact, task)
        reports.write_json(output/'inspection.json', {'campaign':args.campaign, **binding(task),
            'revision':__import__('evaluation_campaign_protocol').revision(), 'artifact':metadata['id'],
            'artifact_digest':metadata['digest'], 'producer_run':producer['id'],
            'preparation_location':internal, 'expires_at':metadata['expires_at'], 'inference':False})
        action, output = 'check-preparation', output/'consumption'
    if task.definition.get('type') == 'judge-only':
        from judge_calibration_campaign import entry
        args.action, args.output = action, output
        return entry(args, task)
    if task.diagnostic_observation and action == 'qualify':
        # The three native observations run during prepare, after exact live staging.
        reports.write_json(output/'qualification.json', {'complete': True, 'inference': False,
            'revision': __import__('evaluation_campaign_protocol').revision(), 'records': 0})
        return
    argv = [sys.argv[0], action, '--output', str(output)]
    for member in definitions: argv.extend(['--definition', str(ROOT / member)])
    for name in ('preparation', 'qualification', 'authentication_qualification', 'approval'):
        value = getattr(args, name)
        if value is not None: argv.extend(['--' + name.replace('_', '-'), str(value)])
    sys.argv = argv
    return campaign_main()


if __name__ == '__main__':
    main()
