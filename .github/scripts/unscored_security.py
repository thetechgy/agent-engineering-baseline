"""Bounded projection of existing verifier findings, never a security verdict.

This source is also carried in the versioned evaluator patch. Keep the two
copies identical; the producer and data-only consumers share this contract.
"""
import hashlib
import json
import re

VERSION = 'aeb-unscored-security-v1'
MAX_FINDINGS = 64
MAX_TEXT = 2048
FIELDS = {'type', 'severity', 'message', 'evidence', 'source', 'score_impact'}
OPTIONAL = {'tool', 'target_skill_used_before'}
FINDING_TYPES = {'prompt_injection_attempt', 'secret_leak', 'secret_exposure', 'unsupported_tool_wrapper',
                 'destructive_command', 'unsupported_path_evidence', 'sensitive_path_access',
                 'network_exfiltration_risk', 'sensitive_file_write', 'refusal_observed'}
UNSCORED_TYPES = {'prompt_injection_attempt', 'unsupported_tool_wrapper', 'unsupported_path_evidence', 'refusal_observed'}
SOURCES = {'agent_tool_call', 'tool_observation', 'agent_response', 'user_prompt'}
ERRORS = {'missing', 'malformed', 'oversized', 'contradictory', 'sidecar_unavailable'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def finding_id(finding):
    return 'sha256:' + hashlib.sha256(json.dumps(
        {k: v for k, v in finding.items() if k != 'id'},
        sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def validate_finding(row, *, published=False):
    extra = {'id'} if published else set()
    require(type(row) is dict and FIELDS | extra <= set(row)
            and set(row) <= FIELDS | OPTIONAL | extra, 'malformed')
    for key in ('type', 'source'):
        require(type(row[key]) is str and re.fullmatch(r'[a-z][a-z0-9_]{0,63}', row[key]), 'malformed')
    require(row['severity'] in ('info', 'warning', 'critical'), 'malformed')
    require(row['type'] in FINDING_TYPES and row['source'] in SOURCES, 'malformed')
    require(type(row['score_impact']) is bool, 'malformed')
    require(row['score_impact'] is (row['type'] not in UNSCORED_TYPES), 'contradictory')
    for key in ('message', 'evidence', 'tool'):
        if key in row:
            require(type(row[key]) is str, 'malformed')
            require(len(row[key]) <= (128 if key == 'tool' else MAX_TEXT), 'oversized')
    if 'target_skill_used_before' in row:
        require(type(row['target_skill_used_before']) is bool, 'malformed')
    if published:
        require(row['id'] == finding_id(row), 'contradictory')


def validate_security(value):
    require(type(value) is dict and set(value) == {'findings', 'evidence_status', 'evidence_errors'}, 'malformed')
    rows = value['findings']; errors = value['evidence_errors']
    require(type(rows) is list and len(rows) <= MAX_FINDINGS, 'oversized')
    require(type(errors) is list and all(type(e) is str and e in ERRORS for e in errors)
            and errors == sorted(set(errors)), 'malformed')
    expected = ('partial' if rows else 'unavailable') if errors else 'retained'
    require(value['evidence_status'] == expected, 'contradictory')
    seen = set()
    for row in rows:
        validate_finding(row, published=True)
        require(row['id'] not in seen, 'contradictory')
        seen.add(row['id'])
    return value


def project_security(details, sanitize):
    """Retain fixed finding fields; reject malformed populations without a pass.

    Exact sanitized duplicates collapse by content identity. This identity names
    a finding record, not a tool call or a successful operation.
    """
    result = {'findings': [], 'evidence_status': 'unavailable', 'evidence_errors': []}
    try:
        security = details.get('security') if type(details) is dict else None
        require(type(security) is dict and 'findings' in security, 'missing')
        rows = security['findings']
        require(type(rows) is list, 'malformed')
        require(len(rows) <= MAX_FINDINGS, 'oversized')
        for row in rows:
            validate_finding(row)
        require(not (security.get('passed') is True and any(row['score_impact'] for row in rows)), 'contradictory')
        require(not (security.get('supported') is False and security.get('passed') is not None), 'contradictory')
        seen = set()
        for row in rows:
            safe = {k: sanitize(v) if type(v) is str else v for k, v in row.items()}
            safe['id'] = finding_id(safe)
            if safe['id'] not in seen:
                result['findings'].append(safe)
                seen.add(safe['id'])
    except ValueError as error:
        result['evidence_errors'] = [str(error) if str(error) in ERRORS else 'malformed']
    result['evidence_status'] = (('partial' if result['findings'] else 'unavailable')
                                 if result['evidence_errors'] else 'retained')
    return validate_security(result)


def merge_security(parts):
    rows = {}; errors = set()
    for part in parts:
        validate_security(part)
        errors.update(part['evidence_errors'])
        for row in part['findings']:
            rows.setdefault(row['id'], row)
    if len(rows) > MAX_FINDINGS:
        rows = {}; errors.add('oversized')
    if not parts:
        errors.add('missing')
    return validate_security({'findings': list(rows.values()), 'evidence_errors': sorted(errors),
        'evidence_status': ('partial' if rows else 'unavailable') if errors else 'retained'})
