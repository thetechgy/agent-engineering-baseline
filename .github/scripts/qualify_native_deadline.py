#!/usr/bin/env python3
"""Exercise native Harbor cancellation with the pinned CLI and no inference."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

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
    for scenario in (('emitted',) if args.expect_broken else ('normal', 'emitted', 'empty', 'secondary')):
        def config(task, mode, control, runtime, present):
            value = original(task, mode, control, runtime, present)
            if scenario != 'normal':
                value.update(import_path='codex_pilot_deadline_fixture:DeadlineCodex', override_timeout_sec=45)
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
            require(row['native_exception'] == ('NonZeroAgentExitCodeError' if args.expect_broken else 'AgentTimeoutError'), 'Primary cause changed: ' + str(row))
            require(row['usage']['estimated_usd'] is None, 'Missing complete usage became a number')
        audit = reports.read_json(next((root / 'evidence/retained').rglob('pilot-runtime.json')))
        witness = audit['deadline_fixture_witness']
        require(witness and witness['events_emitted'] and witness['stderr_emitted'] and witness['submission_bytes'] == 461, 'Emission not observed before deadline')
        require(witness['submission_sha256'] == hashlib.sha256(load(campaign.ROOT / '.github/evals/campaigns/boolean-contract.json').payload('identity')).hexdigest(), 'Emission identity mismatch')
        require(witness['observed_elapsed_seconds'] < 45, 'Emission not observed before deadline')
        summary['emission_witness'] = witness
        summary['controls'].append({'scenario': scenario, 'native_exception': row.get('native_exception'),
            'cleanup': ledger['cleanup_complete'], 'ledger': str(root.relative_to(args.output) / 'evidence/attempt-ledger.json')})
        reports.write_json(args.output / 'qualification.json', summary)


if __name__ == '__main__': main()
