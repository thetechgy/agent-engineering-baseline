"""Admit measured transfer v2 grades and evaluate the native controls."""

VERSION = 'pester-transfer-batch-v2'
REFERENCE_NAMES = ('original', 'quantity-int128')
OUTCOMES = ('passed', 'failed', 'unmeasured')
CONTROLS = ('contract-correct', 'type-restrictive', 'missing-reference')


def native_observation(row):
    native = row.get('native', {})
    reward = native.get('reward', {})
    sidecar = native.get('sidecar', {})
    detail = sidecar.get('details', {}).get('outcome', {})
    metrics = reward.get('custom_metrics')
    if (native.get('handoff', {}).get('sha256') != row['sha256'].removeprefix('sha256:')
            or reward.get('entry_id') != VERSION or sidecar.get('entry_id') != VERSION
            or reward.get('details') != sidecar.get('details') or detail.get('grader_version') != VERSION):
        return 'unmeasured', {}
    classification = detail.get('classification')
    if (classification not in ('passed', 'failed') or sidecar.get('evaluation_status') != 'complete'):
        return 'unmeasured', detail if metrics is None and sidecar.get('evaluation_status') == 'failed' else {}

    references = detail.get('valid_references', {})
    detections = detail.get('variant_detections', [])
    if (references.keys() != set(REFERENCE_NAMES)
            or any(type(value) is not int or value not in (0, 1) for value in references.values())
            or len(detections) != 5 or any(type(value) is not int or value not in (0, 1) for value in detections)
            or detail.get('mutants_executed') != len(detections)
            or detail.get('mutants_detected') != sum(detections)
            or detail.get('powershell_version') != '7.6.9' or detail.get('pester_version') != '6.2.0'
            or detail.get('code') != 'evaluated'):
        return 'unmeasured', {}
    accepted = all(references.values())
    primary = accepted and all(detections)
    if (detail.get('reference_pass') != int(accepted) or (not accepted and any(detections))
            or classification != ('passed' if primary else 'failed')
            or metrics != {'pester_reference_pass': float(accepted),
                           'pester_mutation_detection': sum(detections) / len(detections),
                           'pester_test_quality': float(primary)}):
        return 'unmeasured', {}
    return classification, detail


def verify(receipt, replay):
    """Return presentation counts from the exact historical population and verifier records."""
    def index(rows):
        if type(rows) is not list or len(rows) > 256:
            raise ValueError('Invalid qualification cohort')
        indexed = {row['id']: row for row in rows}
        if len(indexed) != len(rows):
            raise ValueError('Duplicate qualification observation')
        return indexed

    controls = index(receipt['controls'])
    if set(controls) - set(CONTROLS):
        raise ValueError('Unknown qualification control')
    native_controls = {key: native_observation(controls[key]) if key in controls else ('unmeasured', {})
                       for key in CONTROLS}
    correct_status, correct = native_controls['contract-correct']
    restrictive_status, restrictive = native_controls['type-restrictive']
    missing_status, missing = native_controls['missing-reference']
    checks = {
        'contract-correct': (correct_status == 'passed' and correct.get('valid_references') ==
                             {'original': 1, 'quantity-int128': 1} and correct.get('mutants_detected') == 5),
        'type-restrictive': (restrictive_status == 'failed' and restrictive.get('valid_references') ==
                             {'original': 1, 'quantity-int128': 0}),
        'missing-reference': (missing_status == 'unmeasured' and missing.get('classification') ==
                              'infrastructure_error' and missing.get('code') == 'verifier'),
    }

    history = index(replay['observations'])
    observations = index(receipt['observations'])
    members = receipt['member_digests']
    fixtures = replay['provenance']['fixtures']
    if (members.get('tests/case/reference/Subject.ps1') != fixtures['reference']
            or members.get('tests/case/reference/Quantity.Int128.ps1') != fixtures['variation']
            or any(key not in history or row['sha256'] != history[key]['sha256']
                   for key, row in observations.items())):
        raise ValueError('Qualification fixture or submission identity mismatch')
    counts = dict.fromkeys(OUTCOMES, 0)
    counts['unmeasured'] = len(history) - len(observations)
    for row in observations.values():
        counts[native_observation(row)[0]] += 1
    return {
        'verified': bool(history) and all(checks.values()) and not counts['unmeasured'],
        'controls': [(key, native_controls[key][0], checks[key]) for key in CONTROLS],
        'counts': counts,
    }
