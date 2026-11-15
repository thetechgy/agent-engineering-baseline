"""Captured scheduler states supplement native observations; they never grade work.

The raw scheduler witness is bound to the custom capture and authenticated by the
same producer/archive boundary as other campaign evidence. Public structural
validation alone is not producer authentication. Missing files prove no state.
"""
import copy
import re

from evaluation_campaign_core import require, schedule
import skill_reports as reports

MEMBER = 'campaign-scheduler.json'
POLICY = 'campaign-scheduler-v1'
FIELDS = ('position', 'case', 'trial', 'variant', 'arm', 'state', 'returncode', 'grading_present',
          'classification', 'native_exception', 'config_digest', 'task_checksum')


def state(row):
    if row['state'] == 'unlaunched': return 'unlaunched'
    if row['state'] == 'interrupted': return 'interrupted'
    if row['native_exception'] or row['returncode'] not in (None, 0) or row['state'] == 'failed':
        return 'launch_infrastructure_failed'
    if row['state'] == 'completed' and row['grading_present'] is True and row['classification'] in ('passed', 'failed'):
        return 'measured_task_' + row['classification']
    return 'launched_unscored'


def capture(task, ledger, staged):
    import skill_evidence as e
    from evaluation_campaign_protocol import digest, validate_receipt
    from evaluation_runtime import ROOT
    mode = ledger['mode']
    require(mode in ('live', 'experiment-probe'), 'Scheduler evidence requires registered protocol')
    if mode == 'live':
        import os
        validate_receipt(ledger['authorization'], os.environ['AEB_CAMPAIGN_APPROVAL'], task)
    else:
        require(ledger['authorization'] is None and ledger['inference'] is False, 'Probe acquired live authority')
    rows = []
    for row in ledger['entries']:
        arm = 'with_skill' if next(v['present'] for v in task.definition['variants'] if v['id'] == row['variant']) else 'without_skill'
        rows.append({**{k:row[k] for k in ('position', 'case', 'trial', 'variant', 'state')}, 'arm': arm,
            'returncode': row.get('returncode'), 'grading_present': row.get('grading_present'),
            'classification': row.get('outcome', {}).get('classification'), 'native_exception': row.get('native_exception'),
            'config_digest': 'sha256:' + row['config_sha256'] if row.get('config_sha256') else None,
            'task_checksum': row.get('task_checksum')})
    return {'schema': 1, 'campaign': task.definition['id'], 'revision': ledger['revision'],
        'definition_digest': digest(ROOT / task.member), 'mode': mode, 'inference': mode == 'live',
        'dispatch': (None if ledger['authorization'] is None else
            {**{k:ledger['authorization'][k] for k in ('artifact', 'artifact_digest', 'producer_run', 'revision',
                'protocol_digest', 'dispatch', 'run_id', 'allocation', 'first_dispatch', 'definition',
                'definition_digest', 'selection_digest', 'preparation_location')},
             'source_check': ledger['authorization']['authentication']}), 'state': ledger['state'],
        'stop_reason': ledger.get('stop_reason'), 'entries': rows,
        'staged_identity': e.identity(staged)}


def validate(value, task, *, staged=None, observations=None):
    import skill_evidence as e
    from evaluation_campaign_protocol import digest, protocol
    from evaluation_runtime import ROOT
    e.closed(value, ('schema', 'campaign', 'revision', 'definition_digest', 'mode', 'inference',
                     'dispatch', 'state', 'stop_reason', 'entries', 'staged_identity'))
    require(type(value['schema']) is int and value['schema'] == 1 and value['campaign'] == task.definition['id']
            and value['definition_digest'] == digest(ROOT / task.member), 'Scheduler definition mismatch')
    require(type(value['revision']) is str and re.fullmatch('[0-9a-f]{40}', value['revision']), 'Scheduler source identity missing')
    e.enum(value['mode'], ('live', 'experiment-probe')); e.boolean(value['inference'])
    require(value['inference'] == (value['mode'] == 'live'), 'Scheduler inference mismatch')
    e.enum(value['state'], ('running', 'completed', 'stopped', 'failed', 'interrupted'))
    e.optional(value['stop_reason'], e.token); e.sha(value['staged_identity'])
    if staged is not None: require(value['staged_identity'] == e.identity(staged), 'Scheduler staged population mismatch')
    receipt = value['dispatch']
    if value['mode'] == 'live':
        from evaluation_campaign_selection import binding, registration
        e.closed(receipt, ('artifact', 'artifact_digest', 'producer_run', 'revision', 'protocol_digest', 'dispatch',
                           'run_id', 'allocation', 'first_dispatch', 'definition', 'definition_digest',
                           'selection_digest', 'preparation_location', 'source_check'))
        require(type(receipt['producer_run']) is int and receipt['producer_run'] > 0, 'Scheduler producer missing')
        require(type(receipt) is dict and receipt.get('revision') == value['revision']
                and receipt.get('first_dispatch') is True and receipt.get('source_check') == 'github-api-producer-and-digest'
                and receipt.get('protocol_digest') == digest(ROOT / task.definition['protocol'])
                and all(receipt.get(k) == v for k,v in binding(task).items())
                and receipt.get('preparation_location') in {p['location'] for p in registration(task)['producers']},
                'Scheduler lacks matching authorization evidence')
        e.sha(receipt.get('artifact_digest')); e.token(receipt.get('run_id'))
        require(type(receipt.get('artifact')) is str and re.fullmatch('[1-9][0-9]*', receipt['artifact'])
                and type(receipt.get('dispatch')) is str and re.fullmatch('[A-Za-z0-9_-]{8,40}', receipt['dispatch'])
                and receipt.get('allocation') == f'campaign-{value["revision"]}-{value["campaign"]}-prep{receipt["artifact"]}-usd{protocol(task)["budget"]["planning_allocation_usd"]}-{receipt["dispatch"]}',
                'Scheduler allocation mismatch')
    else: require(receipt is None, 'Credential-free scheduler acquired authorization')
    expected = schedule(tuple(task.cases('live')), tuple(v['id'] for v in task.definition['variants']), task.definition['trials'])
    rows = value['entries']
    require(type(rows) is list and len(rows) == len(expected), 'Scheduler population mismatch')
    obs = None if observations is None else {(o['arm'], o['case_id'], o['attempt']): o for o in observations}
    for row, planned in zip(rows, expected):
        e.closed(row, FIELDS)
        require(all(type(row[k]) is type(v) and row[k] == v for k,v in planned.items()), 'Scheduler order or slot mismatch')
        arm = 'with_skill' if next(v['present'] for v in task.definition['variants'] if v['id'] == row['variant']) else 'without_skill'
        require(row['arm'] == arm, 'Scheduler arm mismatch')
        e.enum(row['state'], ('unlaunched', 'launching', 'completed', 'failed', 'interrupted'))
        require(row['returncode'] is None or type(row['returncode']) is int, 'Invalid launch return code')
        e.optional(row['grading_present'], e.boolean)
        e.optional(row['classification'], lambda x:e.enum(x, ('passed', 'failed', 'unsupported', 'timeout', 'infrastructure_error')))
        e.optional(row['native_exception'], e.token); e.optional(row['config_digest'], e.sha)
        require(row['task_checksum'] is None or re.fullmatch('[0-9a-f]{64}', row['task_checksum']), 'Invalid scheduler task identity')
        if staged is not None and row['task_checksum'] is not None:
            require(row['task_checksum'] == next(t['task_checksum'] for t in staged if t['arm'] == arm and t['case_id'] == row['case']),
                    'Scheduler task binding mismatch')
        if row['state'] == 'unlaunched':
            require(all(row[k] is None for k in FIELDS[6:]), 'Unlaunched slot has launch evidence')
        if obs is not None:
            found = obs.pop((arm, row['case'], row['trial']), None)
            require(not found or row['state'] != 'unlaunched', 'Native observation contradicts scheduler nonexecution')
            if state(row).startswith('measured_task_'):
                require(found is not None and found['custom']['outcome'] == row['classification'], 'Scheduler cannot invent measured task work')
    if obs is not None: require(not obs, 'Native observation outside scheduler population')
    return value


def arm_label(value, arm):
    labels = {state(row) for row in value['entries'] if row['arm'] == arm}
    if labels == {'unlaunched'}: return 'unlaunched'
    if 'launch_infrastructure_failed' in labels: return 'launch attempted; infrastructure failed'
    if 'interrupted' in labels: return 'interrupted'
    if 'measured_task_failed' in labels: return 'measured task failed'
    if labels == {'measured_task_passed'}: return 'measured task passed'
    return 'partially launched / unscored'
