"""Qualification rules for the quantity-int128 native replay."""

from pathlib import Path
import re

PUBLICATION_MEMBER = Path('docs/evaluations/pester-transfer-decision/execution-v6/publication-verification.json')
CONTROL_OUTCOMES = {
    'return-boundary': 'verified',
    'permissive-suite': 'accepted',
    'restrictive-suite': 'rejected',
}
CASES = (-2, 0, 3, 8, 9)


def submission_roster(publication):
    """Return the frozen slots in publication order, keyed by replay ID."""
    planned = {(campaign, slot) for campaign in ('current', 'candidate') for slot in range(1, 7)}
    rows = publication['submissions']
    if type(rows) is not list or len(rows) != len(planned):
        raise ValueError('Retained transfer population differs from the frozen receipt')
    roster = {}
    for row in rows:
        campaign, slot, variant, digest = (row[key] for key in ('campaign', 'slot', 'variant', 'submission_sha256'))
        if (type(campaign) is not str or type(slot) is not int or (campaign, slot) not in planned
                or variant not in (campaign, 'absent') or type(digest) is not str
                or not re.fullmatch(r'[0-9a-f]{64}', digest)):
            raise ValueError('Invalid retained transfer submission')
        planned.remove((campaign, slot))
        roster[f'{campaign}-{slot}'] = (campaign, slot, variant, 'sha256:' + digest)
    return roster


def run_outcome(run):
    count_fields = ('total', 'passed', 'failed', 'assertion_failures', 'skipped', 'not_run',
                    'inconclusive', 'failed_blocks', 'failed_containers')
    if (type(run) is not dict or 'error' in run
            or run.get('powershell') != '7.6.9' or run.get('pester') != '6.2.0'
            or any(type(run.get(key)) is not int or run[key] < 0 for key in count_fields)
            or any(run[key] for key in ('skipped', 'not_run', 'inconclusive', 'failed_blocks', 'failed_containers'))
            or run['total'] <= 0 or run['passed'] + run['failed'] != run['total']
            or run['failed'] != run['assertion_failures']):
        return 'unmeasured'
    return 'rejected' if run['failed'] else 'accepted'


def paired_outcome(reference, variation):
    """Measure a variation against a passing reference with equal coverage."""
    outcome = run_outcome(variation)
    if outcome == 'unmeasured' or run_outcome(reference) != 'accepted' or reference['total'] != variation['total']:
        return 'unmeasured'
    return outcome


def boundary_verified(reference, variation):
    for run, quantity_type in ((reference, 'System.Int64'), (variation, 'System.Int128')):
        if type(run) is not dict or 'error' in run or run.get('int128_is_numeric') is not True:
            return False
        rows = run.get('boundary')
        if type(rows) is not list or len(rows) != len(CASES):
            return False
        for requested, row in zip(CASES, rows, strict=True):
            expected = {
                'requested': requested, 'returned': 1, 'object_type': 'System.Management.Automation.PSCustomObject',
                'properties': ['Enabled', 'Quantity'], 'enabled': requested > 0,
                'quantity': str(max(0, min(8, requested))),
                'quantity_type': quantity_type if requested == 3 else 'System.Int32',
            }
            if row != expected or any(type(row[key]) is not type(value) for key, value in expected.items()):
                return False
    return True
