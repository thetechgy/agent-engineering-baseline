"""Transfer v2 policy appended to the staged native verifier."""
GRADER_VERSION = 'pester-transfer-batch-v2'
REFERENCE_NAMES = ('original', 'quantity-int128')


def assess_valid_references(references, mutants, minimum):
    # Use the existing completeness, failure-kind and mutation semantics.
    status, details = assess(references[0], mutants, minimum)
    if status in UNSCORED:
        return status, details
    second_status, second = assess(references[1], [], minimum)
    if second_status in UNSCORED:
        return second_status, second
    if any(run['failed'] != run['assertion_failures'] for run in references):
        return 'unsupported', {'code': 'reference_failure_kind'}
    if references[0]['total'] != references[1]['total']:
        return 'unsupported', {'code': 'reference_test_population'}

    passed = (details['reference_pass'], second['reference_pass'])
    details['valid_references'] = dict(zip(REFERENCE_NAMES, passed))
    details['reference_pass'] = int(all(passed))
    if not details['reference_pass']:
        details.update(mutants_detected=0, variant_detections=[0] * len(mutants),
                       variant_failure_kinds=[None] * len(mutants))
        status = 'failed'
    return status, details
