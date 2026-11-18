"""Verify fixture receipts and reproduce the existing consolidated public report."""
import hashlib
import json
from math import isclose
from pathlib import Path
import sys

from evaluation_campaign import no_credentials, revision
from evaluation_campaign_core import require
from skill_report import generate
from skill_reports import read_json


def verify(retained, output):
    no_credentials()
    probe = read_json(retained / 'cli-probe/qualification.json')
    root = retained / 'codex-qualification'
    evidence = root / 'gh-codex-1691/probe/evidence'
    ledger = read_json(evidence / 'attempt-ledger.json')
    require(probe['revision'] == ledger['revision'] == revision()
            and ledger['inference'] is False and probe['inference'] is False,
            'Qualification revision or inference identity drift')
    require(ledger['state'] == 'completed' and ledger['cleanup_complete']
            and read_json(evidence / 'cleanup.json') == {'complete': True, 'unlaunched_positions': []},
            'Incomplete native campaign')
    rows = ledger['entries']
    require(len(rows) == 4 and len({r['agent_id'] for r in rows}) == 4, 'Wrong native trial population')
    for row in rows:
        present = row['variant'] == 'current'
        allowed = row['case'] == 'gh-014-good'
        require(row['state'] == 'completed' and row['cleanup'] and row['grading_present']
                and row['outcome']['classification'] == ('passed' if allowed and present else 'failed'),
                'Wrong native control outcome')
        metrics = row['custom_metrics']
        require((metrics['gh_task'], metrics['gh_authorization'], metrics['gh_activation']) ==
                (1, int(allowed), int(present)), 'Correctness, authorization or activation drift')
        require(row['skill_access']['successful_full_read'] is (True if present else None),
                'Unexpected full skill read observation')
        usage = row['usage']
        require((usage['n_input_tokens'], usage['n_cache_tokens'], usage['n_cache_write_input_tokens'],
                 usage['n_output_tokens']) == (300, 100, 50, 30)
                and usage['completeness'] == 'complete_turn' and isclose(usage['estimated_usd'], .000735),
                'Non-forwarding fixture usage drift')
        native = evidence / 'retained' / row['native_trial'].removeprefix('jobs/')
        observed = list(native.rglob('probe.json'))
        require(len(observed) == 1, 'Missing request observation')
        request = read_json(observed[0])
        require(request['requests'] == len(request['request_observations']) == 2
                and all(r['model'] == 'gpt-6.2-sol' and r['reasoning']['effort'] == 'high'
                        and r['authorization_matches_sentinel'] is True and r['path'] == '/v1/responses'
                        for r in request['request_observations']),
                'Native CLI request identity drift')
        trajectory = read_json(next(native.rglob('trajectory.json')))
        require(trajectory['agent']['version'] == '0.169.1'
                and any(step.get('tool_calls') for step in trajectory['steps']),
                'Missing normalized native tool observation')
        submissions = [path for path in native.rglob(row['submission']['file']) if 'submitted' in path.parts]
        require(len(submissions) == 1, 'Missing retained output handoff')
        submitted = submissions[0].read_bytes()
        require(len(submitted) == row['submission']['bytes']
                and hashlib.sha256(submitted).hexdigest() == row['submission']['sha256'],
                'Retained output handoff differs from native submission')
        receipts = list(native.rglob('pilot-produced-submission.json'))
        require(len(receipts) == 1 and read_json(receipts[0]) == {
            'bytes': row['submission']['bytes'], 'sha256': row['submission']['sha256']},
            'Native submission receipt drift')
    original = root / 'report'
    generate([evidence / 'public'], original / 'analysis/analysis.json', output)
    require((output / 'report.html').read_bytes() == (original / 'consolidated/report.html').read_bytes(),
            'Fresh-runner consolidated report drift')
    print(json.dumps({'revision': revision(), 'controls': len(rows), 'report_reproduced': True, 'inference': False}))


if __name__ == '__main__':
    verify(Path(sys.argv[1]), Path(sys.argv[2]))
