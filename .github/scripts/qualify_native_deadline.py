#!/usr/bin/env python3
"""Exercise native Harbor cancellation with the pinned CLI and no inference."""
import argparse
import hashlib
import json
from pathlib import Path

import evaluation_campaign as campaign
import evaluation_codex as adapter
from evaluation_tasks import load
from qualify_evaluator_candidate import native_compose_config
from evaluation_campaign_core import require
import skill_reports as reports


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expect-broken', action='store_true')
    args = parser.parse_args()
    campaign.no_credentials()
    native_compose_config(campaign.ROOT)
    original = adapter.agent_config
    summary = {'revision': campaign.revision(), 'inference': False, 'expected_broken': args.expect_broken, 'controls': []}
    for scenario in (('emitted',) if args.expect_broken else ('normal', 'emitted', 'empty', 'secondary', 'cancelled')):
        def config(task, mode, control, runtime, present):
            value = original(task, mode, control, runtime, present)
            if scenario != 'normal':
                value.update(import_path='codex_pilot_deadline_fixture:DeadlineCodex', override_timeout_sec=90 if scenario == 'cancelled' else 45)
                value['kwargs']['deadline_fixture'] = scenario
            return value
        adapter.agent_config = config
        root = args.output / scenario
        try:
            campaign.run(root, load(campaign.ROOT / '.github/evals/campaigns/boolean-contract.json'), 'probe')
        except ValueError:
            if scenario == 'normal': raise
        ledger = reports.read_json(root / 'evidence/attempt-ledger.json')
        row = ledger['entries'][0]
        require(ledger['cleanup_complete'], 'Resources not disposed')
        if scenario != 'normal':
            require(all(r['state'] == 'unlaunched' for r in ledger['entries'][1:]), 'Operational failure did not stop scheduling')
            require(row['native_exception'] == ('NonZeroAgentExitCodeError' if args.expect_broken else 'CancelledError' if scenario == 'cancelled' else 'AgentTimeoutError'), 'Primary cause changed: ' + str(row))
            require(row['usage']['estimated_usd'] is None, 'Missing complete usage became a number')
        if scenario != 'normal' and not args.expect_broken:
            retained = root / 'evidence/retained'
            lifecycle = list(retained.rglob('pilot-lifecycle.json'))
            require(len(lifecycle) == 1, 'Missing lifecycle observation')
            stages = reports.read_json(lifecycle[0])['stages']
            require(stages[-1]['stage'] == 'disposal_complete', 'Final disposal unavailable')
            copies = list(retained.rglob('interrupted-submission.json'))
            if scenario == 'empty':
                require(not copies, 'Empty execution fabricated a submission')
            else:
                require(len(copies) == 1, 'Emitted submission was lost')
                receipt = reports.read_json(copies[0])
                output = copies[0].parent / 'interrupted-submission/Subject.Tests.ps1'
                require(output.read_bytes() == load(campaign.ROOT / '.github/evals/campaigns/boolean-contract.json').payload('identity'), 'Exact partial submission changed')
                require(receipt['sha256'] == hashlib.sha256(output.read_bytes()).hexdigest() and receipt['complete'] is False, 'Partial identity drift')
                raw = next(retained.rglob('codex.txt')).read_text()
                require('native-deadline-evidence' in raw and 'turn.completed' not in raw, 'Native events missing or fixture did not stall')
                usage = reports.read_json(next(retained.rglob('probe.json')))['simulated_response_usage']
                require(usage['complete'] is False and usage['input_tokens'] == 7, 'Simulated partial usage lost')
                if scenario == 'secondary':
                    require(any(v['stage'] == 'collection_failed' and v['member'] == 'codex-stderr.txt' for v in stages), 'Missing secondary collection failure')
                else:
                    diagnostics = next(retained.rglob('codex-stderr.txt')).read_text()
                    require('native-deadline-stderr' in diagnostics and 'fixture-redaction-sentinel' not in diagnostics, 'Diagnostic loss or redaction failure')
            require('report_failure' not in ledger, 'Partial report could not be reproduced')
            public = root / 'evidence/public'
            require(public.exists() and (root / 'evidence/consolidated/report.html').read_bytes() == (root / 'evidence/reproduced/report.html').read_bytes(), 'Report reproduction failed')
        if args.expect_broken:
            exception = next((root / 'evidence/native').rglob('exception.txt')).read_text()
            require('TimeoutError' in exception and 'NonZeroAgentExitCodeError' in exception and 'not running' in exception, 'Original chain was not reproduced')
            require(not list((root / 'evidence/retained').rglob('codex.txt')), 'Original evidence loss not reproduced')
        summary['controls'].append({'scenario': scenario, 'native_exception': row.get('native_exception'),
            'cleanup': ledger['cleanup_complete'], 'ledger': str(root.relative_to(args.output) / 'evidence/attempt-ledger.json')})
        reports.write_json(args.output / 'qualification.json', summary)


if __name__ == '__main__': main()
