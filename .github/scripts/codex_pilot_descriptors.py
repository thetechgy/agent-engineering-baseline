"""Retain exact pilot descriptors and compare their complete parsed configurations."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import struct
import tomllib

import skill_evidence as evidence
import skill_reports as reports

ALGORITHM = 'sha256-typed-toml-v1'
ARMS = ('with_skill', 'without_skill')


def raw_digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def configuration_digest(raw):
    """Ignore TOML presentation only; retain every key, scalar type and array order."""
    def typed(value):
        kind = type(value)
        if kind is dict:
            return ['table', [[key, typed(value[key])] for key in sorted(value)]]
        if kind is list:
            return ['array', [typed(item) for item in value]]
        if kind is float:
            return ['float64', struct.pack('!d', value).hex()]
        if kind in (datetime.datetime, datetime.date, datetime.time):
            return [kind.__name__, value.isoformat()]
        if kind in (str, bool, int):
            return [kind.__name__, value]
        raise ValueError('Unsupported parsed TOML value')
    value = typed(tomllib.loads(raw.decode('utf-8')))
    canonical = json.dumps(value, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode()
    return raw_digest(ALGORITHM.encode() + b'\0' + canonical)


def retain_descriptors(artifact, tasks, captured):
    """Snapshot before execution, binding exact bytes to the native staging capture."""
    from skillevaluator.utils.redaction import redact_sensitive_text
    expected = {(row['arm'], row['case_id']): row for row in captured}
    reports.require(len(expected) == len(captured), 'Duplicate staged descriptor')
    rows = []
    for arm, arm_tasks in sorted(tasks.items()):
        evidence.enum(arm, ARMS)
        for task in sorted(arm_tasks):
            case = task.name
            evidence.token(case)
            reports.require((arm, case) in expected, 'Uncaptured task descriptor')
            raw = evidence.read_bytes(task / 'task.toml', limit=65536)
            digest = raw_digest(raw)
            reports.require(digest == expected[arm, case]['members']['task.toml'], 'Descriptor changed after staging')
            text = raw.decode('utf-8')
            reports.require(redact_sensitive_text(text) == text, 'Descriptor requires protected retention; public upload refused')
            parsed_digest = configuration_digest(raw)
            member = f'task-descriptors/{arm}/{case}.toml'
            target = artifact / member
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            rows.append({'arm': arm, 'case_id': case, 'member': member,
                         'raw_sha256': digest, 'parsed_sha256': parsed_digest,
                         'task_checksum': expected[arm, case]['task_checksum']})
    reports.require({(r['arm'], r['case_id']) for r in rows} == set(expected)
                    and len(rows) == len(expected), 'Incomplete descriptor retention')
    reports.write_json(artifact / 'task-descriptors.json', {'algorithm': ALGORITHM, 'descriptors': rows})


def verified_configurations(artifact):
    """Verify retained bodies and both identities; missing older evidence fails closed."""
    manifest = reports.read_json(artifact / 'task-descriptors.json')
    evidence.closed(manifest, ('algorithm', 'descriptors'))
    reports.require(manifest['algorithm'] == ALGORITHM, 'Unknown descriptor identity algorithm')
    rows = manifest['descriptors']
    reports.require(type(rows) is list and 0 < len(rows) <= evidence.MAX_CASES, 'Invalid descriptor inventory')
    staged = reports.read_json(artifact / 'staging.json')
    reports.require(type(staged) is list and len(staged) == len(rows), 'Descriptor staging inventory mismatch')
    expected = {(row['arm'], row['case_id']): row for row in staged}
    reports.require(len(expected) == len(staged), 'Duplicate staged descriptor')
    reports.require(all(evidence.custom_task_checksum(row['members']) == row['task_checksum'] for row in staged),
                    'Native descriptor staging checksum mismatch')
    configurations = {}
    for row in rows:
        evidence.closed(row, ('arm', 'case_id', 'member', 'raw_sha256', 'parsed_sha256', 'task_checksum'))
        evidence.enum(row['arm'], ARMS)
        evidence.token(row['case_id'])
        key = row['arm'], row['case_id']
        reports.require(key in expected and key not in configurations, 'Unexpected or duplicate descriptor')
        member = f'task-descriptors/{key[0]}/{key[1]}.toml'
        reports.require(row['member'] == member, 'Invalid descriptor member')
        raw = evidence.read_bytes(artifact / member, limit=65536)
        reports.require(raw_digest(raw) == row['raw_sha256'] == expected[key]['members']['task.toml']
                        and row['task_checksum'] == expected[key]['task_checksum'], 'Descriptor raw identity mismatch')
        digest = configuration_digest(raw)
        reports.require(digest == row['parsed_sha256'], 'Descriptor parsed identity mismatch')
        configurations[key] = digest
    return configurations


def compare_descriptors(reference, candidate):
    left = verified_configurations(reference)
    right = verified_configurations(candidate)
    reports.require(left == right, 'Complete parsed task configurations differ')
    return {'algorithm': ALGORITHM, 'configurations_equal': True, 'descriptors': len(left)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path, help='Authenticated reference evidence directory')
    parser.add_argument('candidate', type=Path, help='Authenticated candidate evidence directory')
    args = parser.parse_args()
    try:
        result = compare_descriptors(args.reference, args.candidate)
    except (ValueError, OSError, KeyError, TypeError):
        parser.exit(1, 'Descriptor evidence is incomplete, inconsistent, or configuration differs.\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
