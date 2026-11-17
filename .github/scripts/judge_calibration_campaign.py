"""Judge-only callbacks for the registered campaign, scheduler and artifact path.

No agent staging, runtime, variants or native cleanup witnesses are synthesized.
Provider prompts, response parsing, retries and accounting belong to the pinned
evaluator. Only the existing OpenAI strict/replace route is supported.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import time

import evaluation_campaign_core as core
import evaluation_campaign_protocol as shared
from evaluation_runtime import ROOT
import evaluator_profiles as profiles
import judge_accounting as accounting
import judge_calibration_inputs as inputs
import skill_reports as reports

SCENARIOS = ('complete', 'schema-fallback', 'retry', 'retry-exhaustion', 'unknown-retry', 'refusal', 'malformed',
             'missing-usage', 'malformed-usage', 'contradictory-usage', 'timeout', 'interruption',
             'request-stop', 'usage-stop', 'cost-stop', 'cache-cost-stop', 'deadline-stop', 'retention-failure')


def settings(task, key):
    p = shared.protocol(task)['request']
    return {'SKILL_EVAL_LLM_PROVIDER': p['provider'], 'LLM_JUDGE_MODEL': p['model'],
            'SKILL_EVAL_LLM_API_KEY': key, 'SKILL_EVAL_LLM_BASE_URL': p['endpoint'].removesuffix('/chat/completions'),
            'LLM_JUDGE_RETRY_POLICY': p['retry_policy'], 'LLM_JUDGE_FALLBACK_POLICY': p['fallback_policy'],
            'LLM_JUDGE_FALLBACK_MODELS': '', 'SKILL_EVAL_LLM_MAX_RETRIES': str(p['transport_retries']),
            'SKILL_EVAL_LLM_JUDGE_BUDGET_SEC': str(p['judge_seconds'])}


@contextmanager
def configured(values):
    """Restore the caller's environment; never inherit provider overrides."""
    previous = dict(os.environ)
    for key in tuple(os.environ):
        if key.startswith(('SKILL_EVAL_', 'LLM_JUDGE_', 'OPENAI_', 'ANTHROPIC_', 'NVIDIA_')):
            del os.environ[key]
    os.environ.update(values)
    try:
        yield
    finally:
        os.environ.clear(); os.environ.update(previous)


def transport_estimate(transports, task):
    """Conservative scheduling estimate; missing cache detail stays missing."""
    prices = shared.protocol(task)['budget']['prices_per_million']
    total = 0.0
    for transport in transports:
        usage = transport['usage']
        if transport['outcome'] != 'http_response' or usage['status'] != 'complete':
            return None
        tokens = usage['counters']
        a, b = tokens['input'], tokens['output']
        cached = tokens['cached_input'] or 0
        writes = tokens['cache_write_input']
        writes = a - cached if writes is None else writes
        if cached + writes > a:
            return None  # Read/write cache subsets cannot price the same input twice.
        total += ((a - cached - writes) * prices['input'] + cached * prices['cached_input']
                  + writes * prices['cache_write_input'] + b * prices['output']) / 1_000_000
    return total


def estimate(envelope, task):
    return transport_estimate(envelope['transports'], task) if accounting.summarize([envelope])['complete'] else None


def summary(rows):
    return accounting.summarize([r.get('accounting') for r in rows if r['state'] != 'unlaunched'])


def run(root, task, *, live=False, preparation=None, fixture=None):
    """One serial callback per retained record through the existing drive loop."""
    from skillevaluator.tier3.harbor.templates import eval as verifier
    profiles.runtime(profiles.candidate_versions(profiles.ACCOUNTING), owning=True)
    p = shared.protocol(task)
    authority = None
    if live:
        authority = shared.runtime_gate(task)
        core.require(preparation is not None, 'Approved preparation required')
        check(preparation, root.parent / 'judge-consumption', task)
    else:
        from evaluation_campaign import no_credentials
        no_credentials()
        core.require(fixture is not None, 'Credential-free transport required')
    root.mkdir(parents=True, exist_ok=False)
    if live:
        shared.claim(root, authority)
    rows = [{**r, 'state': 'unlaunched'} for r in shared.frozen(task)['schedule']]
    ledger = {'version': 1, 'type': 'judge-only', 'revision': shared.revision(),
              'origin': 'live_provider' if live else 'credential_free_fixture',
              'scenario': fixture.name if fixture else 'calibration',
              'inference': live, 'paid_authority': False, 'authorization': authority,
              'frozen': shared.frozen(task), 'entries': rows, 'agent_runtime': None,
              'agent_cleanup': None, 'state': 'preparing', 'resource_disposal': False}
    started = time.monotonic()
    limits = {'http': p['max_http_attempts'], 'tokens': p['max_reported_tokens'], 'cost': p['budget']['stop_estimate_usd'],
              'seconds': p['deadline_seconds'], **(fixture.limits if fixture else {})}
    ledger['execution_bounds'] = limits
    ledger['fixture_settings'] = fixture.settings if fixture else None
    def save():
        path = root / 'attempt-ledger.json'
        temporary = path.with_suffix('.pending')
        with temporary.open('w') as stream:
            json.dump(ledger, stream, indent=2, allow_nan=False); stream.write('\n')
            stream.flush(); os.fsync(stream.fileno())
        temporary.replace(path)
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)

    def stop(reason):
        ledger.setdefault('stop_reason', reason)
        raise ValueError(reason)

    def eligible(active=None):
        if ledger['frozen'] != shared.frozen(task):
            stop('judge_source_drift')
        if live:
            now = shared.datetime.now(shared.timezone.utc)
            if any(now >= shared.datetime.fromisoformat(expiry.replace('Z', '+00:00'))
                   for expiry in (p['authorization_expires_at'], authority['artifact_expires_at'])):
                stop('preparation_expired')
        for completed in rows:
            if 'accounting' not in completed:
                continue
            retained = root / 'records' / completed['case']
            try:
                if (reports.read_json(retained / 'judge_accounting.json') != completed['accounting']
                    or reports.read_json(retained / 'judgments.json') != completed['results']
                    or shared.digest(retained / 'judge_attempts.json') != completed['diagnostics_digest']):
                    stop('evidence_retention_failure')
            except (OSError, ValueError):
                stop('evidence_retention_failure')
        envelopes = [r['accounting'] for r in rows if 'accounting' in r]
        previous = accounting.summarize(envelopes)
        if not previous['complete']:
            stop('unknown_judge_accounting')
        transports = [t for e in envelopes for t in e['transports']]
        if active is not None:
            if not active['retention_complete']:
                stop('evidence_retention_failure')
            if any(t['outcome'] != 'http_response' or t['usage']['status'] != 'complete' for t in active['transports']):
                stop('unknown_judge_accounting')
            transports += active['transports']
        if len(transports) >= limits['http']:
            stop('judge_request_limit')
        known_cost = transport_estimate(transports, task)
        if known_cost is None:
            stop('unknown_judge_cost')
        if known_cost >= limits['cost']:
            stop('estimated_usage_threshold')
        if sum((t['usage']['counters']['input'] or 0) + (t['usage']['counters']['output'] or 0) for t in transports) >= limits['tokens']:
            stop('judge_usage_limit')
        if time.monotonic() - started >= limits['seconds']:
            stop('judge_deadline')

    original_read = verifier._accounted_read
    original_reward = verifier.SKILL_EVALUATOR_REWARD_JSON
    original_alarm = signal.getsignal(signal.SIGALRM)
    def bounded_read(request, timeout):
        core.require(request.full_url == p['request']['endpoint']
                and getattr(request, '_aeb_provider', None) == 'openai'
                and request._aeb_model == p['request']['model'], 'Unsupported judge transport')
        active = verifier._accounting._ACTIVE.get()
        core.require(active is not None, 'Missing accounting before HTTP request')
        eligible(active[1])
        judge = verifier._accounting._JUDGE.get()
        core.require(judge is not None, 'Missing logical judgment before HTTP request')
        if sum(t['judgment'] == judge['id'] for t in active[1]['transports']) >= p['request']['max_requests_per_judgment']:
            stop('judge_request_limit')
        payload = json.loads(request.data)
        core.require(payload['model'] == p['request']['model'] and payload['stream'] is False
                     and payload['max_completion_tokens'] == p['request']['max_completion_tokens']
                     and 'reasoning_effort' not in payload and 'temperature' not in payload,
                     'Judge request settings drift')
        return original_read(request, min(timeout, max(0.001, limits['seconds'] - (time.monotonic() - started))))

    def attempt(row, total):
        core.require(ledger['frozen'] == shared.frozen(task), 'Source drift before judge record')
        record = inputs.records(task)[row['position'] - 1]
        record_root = root / 'records' / record['id']
        record_root.mkdir(parents=True)
        verifier.SKILL_EVALUATOR_REWARD_JSON = record_root / 'reward.json'
        verifier._SCHEMA_UNSUPPORTED_TARGETS.clear()
        token = verifier._accounting.start(record_root / 'judge_accounting.json')
        attempts = []
        evidence_token = verifier._ACTIVE_JUDGE_EVIDENCE.set(attempts)
        deadline_token = verifier._ACTIVE_JUDGE_DEADLINE.set(started + limits['seconds'])
        results = {dimension: {'score': None, 'status': 'not_applicable',
                              'reason': 'Frozen applicability; this dimension has no intended reference'}
                   for dimension in inputs.DIMENSIONS if dimension != record['dimension']}
        try:
            if fixture:
                fixture.before_record(verifier, row)
            for dimension in inputs.DIMENSIONS:
                applicable = record['dimension'] == dimension
                if dimension == 'behavior_check':
                    args = (record['question'] + '\n' + record['submission'], record['expected_behavior'] if applicable else [])
                else:
                    args = (record['question'], record['reference'] if applicable else '', record['submission'])
                results[dimension] = verifier._call_required_judge(dimension, getattr(verifier, 'judge_' + dimension),
                                                                *args, allow_not_applicable=not applicable)
                if applicable and results[dimension].get('score') is None:
                    ledger.setdefault('stop_reason', 'judge_unavailable')
                    break
        except BaseException as error:
            ledger.setdefault('stop_reason', 'interrupted' if isinstance(error, KeyboardInterrupt) else 'judge_infrastructure_failure')
            row['primary_failure'] = type(error).__name__
            raise
        finally:
            verifier._accounting.finish()
            verifier._accounting._ACTIVE.reset(token)
            verifier._ACTIVE_JUDGE_EVIDENCE.reset(evidence_token)
            verifier._ACTIVE_JUDGE_DEADLINE.reset(deadline_token)
            row.update(results=results, state='completed' if not ledger.get('stop_reason') else 'failed')
            row['accounting'] = reports.read_json(record_root / 'judge_accounting.json')
            observation = accounting.summarize([row['accounting']])
            row['usage'] = {'estimated_usd': estimate(row['accounting'], task)}
            row['accounting_summary'] = observation
            reports.write_json(record_root / 'judge_attempts.json', {'attempts': attempts})
            reports.write_json(record_root / 'judgments.json', results)
            row['diagnostics_digest'] = shared.digest(record_root / 'judge_attempts.json')
        if not observation['complete']:
            ledger.setdefault('stop_reason', 'unknown_judge_accounting')
        if row['usage']['estimated_usd'] is None:
            ledger.setdefault('stop_reason', 'unknown_judge_cost')
        if fixture:
            fixture.after_record(row)
        return ledger.get('stop_reason')

    key = os.environ.get('OPENAI_API_KEY', '') if live else 'fixture-not-a-provider-credential'
    if live:
        core.require(key, 'Protected provider credential required')
    values = settings(task, key)
    if fixture:
        values.update(fixture.settings)
    try:
        with configured(values):
            verifier._accounted_read = bounded_read
            core.drive(ledger, attempt, save=save, resources=lambda: signal.getsignal(signal.SIGALRM),
                       baseline=original_alarm, threshold=limits['cost'],
                       before_attempt=lambda row: eligible())
    except BaseException as error:
        ledger.setdefault('stop_reason', 'interrupted' if isinstance(error, KeyboardInterrupt) else 'evidence_or_infrastructure_failure')
        ledger.setdefault('primary_failure', type(error).__name__)
        # Keep the first failure; report/retention failures are additional evidence.
    finally:
        verifier._accounted_read = original_read
        verifier.SKILL_EVALUATOR_REWARD_JSON = original_reward
        ledger['resource_disposal'] = (signal.getsignal(signal.SIGALRM) == original_alarm
                                      and signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0))
        ledger['accounting_summary'] = summary(rows)
        save()
    return ledger


def admit_run(root, task):
    """Data-only judge admission without an agent TrialResult or history score."""
    value = reports.read_json(root / 'attempt-ledger.json')
    core.require(value['version'] == 1 and value['type'] == 'judge-only'
                 and value['frozen'] == shared.frozen(task) and value['revision'] == shared.revision()
                 and value['agent_runtime'] is value['agent_cleanup'] is None
                 and value['paid_authority'] is False, 'Judge report identity drift')
    core.require((value['origin'] == 'credential_free_fixture' and value['inference'] is False and value['authorization'] is None)
                 or (value['origin'] == 'live_provider' and value['inference'] is True and type(value['authorization']) is dict),
                 'Judge evidence origin mismatch')
    scheduled = shared.frozen(task)['schedule']
    core.require(len(value['entries']) == len(scheduled), 'Judge report population drift')
    for row, expected in zip(value['entries'], scheduled, strict=True):
        core.require(all(row[k] == v for k, v in expected.items()), 'Judge schedule drift')
        core.require(row['state'] in ('unlaunched', 'completed', 'failed', 'interrupted', 'launching'), 'Invalid record state')
        if 'accounting' in row:
            native = reports.read_json(root / 'records' / row['case'] / 'judge_accounting.json')
            core.require(row['accounting'] == native and accounting.summarize([native]) == row['accounting_summary']
                    and row['results'] == reports.read_json(root / 'records' / row['case'] / 'judgments.json'),
                    'Judge retained evidence drift')
            core.require(row['diagnostics_digest'] == shared.digest(root / 'records' / row['case'] / 'judge_attempts.json'),
                         'Judge diagnostics missing or changed')
            core.require(row['usage'] == {'estimated_usd': estimate(native, task)}, 'Judge cost estimate drift')
    core.require(value['accounting_summary'] == summary(value['entries']), 'Judge accounting total drift')
    return value


def render(roots, destination, task):
    """Use the consolidated renderer and tables; no fake behavioral populations."""
    import skill_analysis as analysis
    import skill_report as report
    admitted = [admit_run(root, task) for root in roots]
    core.require(len({value['origin'] for value in admitted}) == 1, 'Fixture and live judgments cannot be pooled')
    public = destination / 'public'
    reports.write_json(public / 'inventory.json', {'schema_version': 1, 'kind': 'inventory', 'skills': []})
    captured = analysis.capture_inputs([public])
    result = analysis.build_analysis(captured)
    html = report.render_report(result, captured)
    status = ('Live calibration UNRUN. Fixture observations do not measure judge accuracy or skill benefit.'
              if admitted[0]['inference'] is False else 'Bounded calibration results; no general judge-accuracy or skill-benefit claim.')
    section = '<section><h2>Judge-only calibration</h2><p>' + status + ' Agent runtime, arms and cleanup: inapplicable. Request limits and reserves are not billing caps.</p>'
    corpus = reports.read_json(ROOT / task.definition['corpus'])
    section += report.table('Frozen calibration references (outside provider inputs)',
                            ['Record', 'Intended judgment', 'Reference label', 'Basis', 'Independent evidence', 'Limits'],
                            [[report.safe(item[k]) for k in ('id', 'judgment', 'expected', 'label_basis', 'reference', 'ambiguity')]
                             for item in corpus['items']])
    section += '<p>Reference disagreements are calibration results, never a reason to retry. False passes on known-broken work block authoritative use pending investigation. Unsupported binary conclusions and unavailable judgments stay outside scored agreement. Preserve independent executable checks and human review; seven controls cannot establish general accuracy.</p>'
    frozen = shared.frozen(task)
    section += report.table('Source and declared execution bounds', ['Identity', 'Value'],
        [[report.safe(k), report.safe(str(v))] for k,v in {
            'revision': frozen['revision'], 'producer': frozen['evaluator']['id'],
            'patch': frozen['evaluator']['patch_sha256'],
            'corpus': frozen['source_identities']['live'][task.definition['corpus']],
            'rubric inputs': frozen['source_identities']['live'][task.definition['rubric']],
            'request settings': json.dumps(frozen['protocol']['request'], sort_keys=True),
            'maximum records / applicable judgments / HTTP requests': '7 / 7 / 14',
            'scheduling threshold / reserve USD': '2 / 10',
            'CI cost': 'separate; unavailable here',
            'cost estimate': 'reported cache writes use the write rate; unreported writes conservatively price uncached input at that rate; not billing',
            'qualification timing': 'shortened judge deadline/backoff; full production-duration behavior unmeasured'
        }.items()])
    population = []; details = []
    for root, value in zip(roots, admitted, strict=True):
        rows = value['entries']; a = value['accounting_summary']
        name = value['scenario']
        population.append([name, value['origin'], len(rows), sum(r['state'] != 'unlaunched' for r in rows),
                           sum(r['state'] == 'completed' for r in rows), sum(r['state'] == 'unlaunched' for r in rows),
                           a['logical_judgments'], sum(not j['not_applicable'] for r in rows for j in r.get('accounting', {}).get('judgments', [])),
                           sum(j['not_applicable'] for r in rows for j in r.get('accounting', {}).get('judgments', [])),
                           a['model_attempts'], a['http_attempts'], a['responses_received'],
                           a['usage_complete_responses'], a['complete'], value.get('stop_reason', 'none'), value['resource_disposal']])
        for row in rows:
            details.append([name, row['case'], row['state'], json.dumps(row.get('results', {}), sort_keys=True),
                            json.dumps(row.get('accounting_summary', {}), sort_keys=True),
                            json.dumps(row.get('usage')), 'records/' + row['case']])
    section += report.table('Population, accounting and stops', ['Scenario', 'Origin', 'Expected records', 'Launched', 'Completed', 'Unlaunched', 'Dimensions evaluated', 'Applicable judgments', 'Inapplicable dimensions', 'Model attempts', 'HTTP attempts', 'Responses', 'Complete usage', 'Accounting complete', 'Stop reason', 'Resources disposed'],
                            [[report.safe(str(v)) for v in row] for row in population])
    section += report.table('Judgments and retained evidence', ['Scenario', 'Record', 'State', 'Dimensions and verdicts', 'Accounting', 'Estimated USD', 'Evidence'],
                            [[report.safe(str(v)) for v in row] for row in details]) + '</section>'
    html = html.replace(b'</main>', section.encode() + b'</main>')
    core.require(len(html) <= report.HTML_LIMIT, 'Judge consolidated report size exceeded')
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'report.html').write_bytes(html)
    reports.write_json(destination / 'admission.json', {'complete': True, 'inference': admitted[0]['inference'],
                       'revision': shared.revision(), 'runs': [shared.digest(r / 'attempt-ledger.json') for r in roots]})
    return html


def check(reference, output, task):
    profiles.runtime(profiles.candidate_versions(profiles.ACCOUNTING), owning=True)
    core.require(reports.read_json(reference / 'frozen-proposal.json') == shared.frozen(task), 'Preparation/source/protocol/runtime drift')
    from campaign_authentication_qualification import validate
    validate(reports.read_json(reference / 'authentication-qualification.json'), task)
    core.require(reports.read_json(reference / 'preparation.json') == {'complete': True, 'inference': False,
        'revision': shared.revision(), 'protocol_digest': shared.digest(ROOT / task.definition['protocol']),
        'authorized_live_attempts': 0}, 'Incomplete preparation')
    proof = reports.read_json(reference / 'scheduler-qualification.json')
    core.require(proof['complete'] is True and proof['revision'] == shared.revision()
                 and proof['inference'] is False and set(proof['scenarios']) == set(SCENARIOS), 'Incomplete judge qualification')
    authentication = reports.read_json(reference / 'authentication-consumption.json')
    core.require(authentication == {'complete': True, 'inference': False, 'fixture_only': True,
        'revision': shared.revision(), 'entry_point': '.github/scripts/evaluation_campaign_selection.py authenticate',
        'actual_preparation': True, 'live_authority': False}, 'Actual preparation authentication not qualified')
    roots = [reference.parent / 'scenarios' / name / 'evidence' for name in SCENARIOS]
    html = render(roots, output / 'evidence/reproduced', task)
    core.require(html == (reference / 'consolidated/report.html').read_bytes(), 'Consumed judge report reproduction failed')
    reports.write_json(output / 'evidence/preparation-check.json', {'complete': True, 'inference': False,
        'revision': shared.revision(), 'report_digest': shared.digest(reference / 'consolidated/report.html'),
        'agent_runtime': None, 'agent_cleanup': None})
    return True


def entry(args, task):
    from evaluation_campaign import no_credentials
    if args.action != 'live':
        no_credentials()
    if args.action == 'authenticate':
        return shared.authenticate(args.output, args.approval, task)
    if args.action == 'check-preparation':
        core.require(args.preparation is not None, 'Preparation required')
        return check(args.preparation, args.output, task)
    if args.action in ('qualify', 'prepare'):
        from judge_calibration_qualification import qualify, prepare
        return qualify(args.output, task) if args.action == 'qualify' else prepare(args.output, task, args.qualification, args.authentication_qualification)
    core.require(args.action == 'live' and args.approval == os.environ.get('AEB_CAMPAIGN_APPROVAL'), 'Exact approved allocation required')
    result = run(args.output, task, live=True, preparation=args.preparation)
    render([args.output], args.output / 'consolidated', task)
    core.require(result['state'] == 'completed' and result['resource_disposal'], 'Calibration stopped; no continuation authorized')
    return result
