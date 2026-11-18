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


def verify_preparation(reference, output):
    """Audit the admitted shared campaign and repeat fixture auth on its archive members."""
    import tempfile
    from campaign_authentication_qualification import run_case
    from evaluation_campaign_protocol import digest
    from evaluation_campaign_selection import selected_task
    from skill_reports import write_json

    no_credentials()
    task = selected_task('gh-codex-1691-live')
    frozen = read_json(reference / 'frozen-proposal.json')
    scenarios = reference.parent / 'scenarios'
    evidence = scenarios / 'complete/evidence'
    ledger = read_json(evidence / 'attempt-ledger.json')
    require(ledger['revision'] == frozen['revision'] == revision()
            and ledger['mode'] == 'experiment-probe' and not ledger['inference']
            and ledger['state'] == 'completed' and ledger['cleanup_complete']
            and read_json(evidence / 'cleanup.json') == {'complete': True, 'unlaunched_positions': []},
            'Incomplete exact-source scheduler fixture')
    rows = ledger['entries']
    require(len(rows) == 2 and [row['variant'] for row in rows] == ['current', 'absent']
            and len({row['agent_id'] for row in rows}) == 2, 'Native pair order or environment drift')
    for row in rows:
        present = row['variant'] == 'current'
        native = evidence / 'retained' / row['native_trial'].removeprefix('jobs/')
        control = task.fixture_control('complete', row)
        require(row['case'] == 'gh-014' and row['state'] == 'completed' and row['cleanup']
                and row['grading_present'] and row['skill_access']['deployed'] is present
                and row['skill_access']['successful_full_read'] is (True if present else None),
                'Native submission, cleanup or target access missing')
        task.check(control, present, row['outcome'], row['custom_metrics'])
        reward = read_json(next(native.rglob('skill_evaluator_reward.json')))
        require(reward['custom_metrics'] == row['custom_metrics']
                and reward['details']['outcome'] == row['outcome'], 'Independent verifier handoff drift')
        submitted = [path for path in native.rglob(task.output) if 'submitted' in path.parts]
        require(len(submitted) == 1 and submitted[0].read_bytes() == task.payload(control),
                'Retained submission bytes differ from fixture output')
        receipt = {'sha256': digest(submitted[0]).removeprefix('sha256:'), 'bytes': submitted[0].stat().st_size}
        require(read_json(next(native.rglob('pilot-produced-submission.json'))) == receipt
                and row['submission'] == {**receipt, 'file': task.output}, 'Producer submission handoff drift')
        request = read_json(next(native.rglob('probe.json')))
        require(request['requests'] == len(request['request_observations']) == 2
                and all(r['model'] == 'gpt-6.2-sol' and r['reasoning']['effort'] == 'high'
                        and r['authorization_matches_sentinel'] is True and r['path'] == '/v1/responses'
                        for r in request['request_observations']), 'Stub request identity drift')
        usage = row['usage']
        require(tuple(usage[key] for key in ('n_input_tokens', 'n_cache_tokens', 'n_cache_write_input_tokens',
                                             'n_output_tokens')) == (300, 100, 50, 30)
                and usage['completeness'] == 'complete_turn' and isclose(usage['estimated_usd'], .000735),
                'Cache-write accounting missing from the campaign')
    public = read_json(next((evidence / 'public').rglob('public-report.json')))
    require(len(public['observations']) == 2
            and all(obs['custom']['usage']['cache_write_input_count'] == 50 for obs in public['observations'])
            and 'Cache-write tokens' in (reference / 'consolidated/report.html').read_text(),
            'Cache-write accounting was dropped by public reporting')
    refusal = read_json(scenarios / 'provider-refusal/evidence/attempt-ledger.json')
    receipt = read_json(reference / 'scheduler-qualification.json')['scenarios']['provider-refusal']['provider']
    require(refusal['cleanup_complete'] and refusal['stop_reason'] == 'execution_infrastructure_failure'
            and [row['state'] for row in refusal['entries']] == ['failed', 'unlaunched']
            and refusal['entries'][0]['usage']['estimated_usd'] is None
            and receipt['requests'] == 1 and receipt['cli_returncode'] != 0,
            'Provider refusal did not stop with unknown cost and no second launch')
    missing = scenarios / 'unknown-usage/evidence'
    missing_ledger = read_json(missing / 'attempt-ledger.json')
    first, second = missing_ledger['entries']
    missing_native = missing / 'retained' / first['native_trial'].removeprefix('jobs/')
    missing_request = read_json(next(missing_native.rglob('probe.json')))
    require(missing_ledger['cleanup_complete'] and missing_ledger['stop_reason'] == 'unknown_usage'
            and first['state'] == 'failed' and first['grading_present'] and first['cleanup']
            and first['usage']['completeness'] == 'unavailable' and first['usage']['estimated_usd'] is None
            and 'observation_injection' not in first and second['state'] == 'unlaunched'
            and missing_request['provider_usage_supplied'] is False and missing_request['requests'] == 2,
            'Native missing usage was priced or allowed another launch')
    with tempfile.TemporaryDirectory(prefix='codex-1691-preparation-auth-') as directory:
        result = run_case(Path(directory) / 'actual-preparation', task, 'accepted', preparation=reference)
        require(result['receipt_present'], 'Actual preparation did not reach the receipt validator')
    write_json(output, {'revision': revision(), 'complete': True, 'inference': False,
                        'fixture_authentication': True, 'fixture_receipts_retained': False,
                        'paired_slots': len(rows), 'refusal_requests': receipt['requests'],
                        'native_missing_usage_stop': True,
                        'reproduced_report_digest': digest(reference / 'consolidated/report.html')})


if __name__ == '__main__':
    if sys.argv[1] == 'preparation':
        verify_preparation(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        verify(Path(sys.argv[1]), Path(sys.argv[2]))
