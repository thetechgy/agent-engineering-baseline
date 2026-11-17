"""Versioned judge observations; no requests, credentials, grading or billing claims.

The exact same stdlib-only module is staged by the opt-in evaluator patch.
Token subsets are never added to their parent totals. Unknown usage stays unknown.
"""
from contextvars import ContextVar
from functools import wraps
import json
from pathlib import Path
from uuid import uuid4

VERSION = 'aeb-judge-accounting-v1'
TOKENS = ('input', 'output', 'total', 'cached_input',
          'reasoning_output', 'audio_input', 'audio_output',
          'accepted_prediction', 'rejected_prediction', 'cache_write_input')
_ACTIVE = ContextVar('judge_accounting', default=None)
_JUDGE = ContextVar('accounting_judge', default=None)
_LOGICAL = ContextVar('accounting_logical_attempt', default=None)
_ATTEMPT = ContextVar('accounting_model_attempt', default=None)
MAX_RECORDS = 256


def unknown():
    return {'status': 'missing', 'counters': dict.fromkeys(TOKENS)}


def usage(tokens, *, malformed=False):
    """Validate already mapped provider counters without estimating absent values."""
    values = {k: v if type(v) is int and 0 <= v <= 10**12 else None
              for k in TOKENS if (v := tokens.get(k)) is not None}
    bad = malformed or any(v is not None and (type(v) is not int or not 0 <= v <= 10**12)
                           for v in tokens.values())
    values = {k: values.get(k) for k in TOKENS}
    inconsistent = False
    a, b, total = (values[k] for k in TOKENS[:3])
    if None not in (a, b, total):
        inconsistent = a + b != total
    for child, parent in ((k, 'input' if k in ('cached_input', 'audio_input', 'cache_write_input') else 'output')
                          for k in TOKENS[3:]):
        if values[child] is not None and values[parent] is not None:
            inconsistent |= values[child] > values[parent]
    status = ('malformed' if bad else 'inconsistent' if inconsistent else
              'complete' if a is not None and b is not None else 'missing')
    return {'status': status, 'counters': values}


def start(path):
    value = {'version': VERSION, 'session': uuid4().hex, 'closed': False,
             'judgments': [], 'transports': [], 'retention_complete': True}
    token = _ACTIVE.set((Path(path), value))
    persist()
    return token


def persist():
    active = _ACTIVE.get()
    if active is None:
        return
    path, value = active
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + '.tmp')
        tmp.write_text(json.dumps(value, indent=2), encoding='utf-8')
        tmp.replace(path)
    except OSError:
        value['retention_complete'] = False


def finish():
    if _ACTIVE.get() is not None:
        _ACTIVE.get()[1]['closed'] = True
        persist()


def begin_judgment(metric, provider):
    active = _ACTIVE.get()
    if active is None:
        return _JUDGE.set(None)
    value = active[1]
    row = {'id': len(value['judgments']) + 1, 'metric': metric,
           'provider': provider, 'closed': False, 'model_attempts': 0, 'logical_attempts': 0, 'not_applicable': False}
    if len(value['judgments']) >= MAX_RECORDS:
        value['retention_complete'] = False
        row = None
    else:
        value['judgments'].append(row)
    persist()
    return _JUDGE.set(row)


def end_judgment(token, *, not_applicable=False):
    row = _JUDGE.get()
    if row is not None:
        row['closed'] = True
        row['not_applicable'] = not_applicable
    persist()
    _JUDGE.reset(token)


def logical_attempt(number):
    row = _JUDGE.get()
    if row is not None:
        row['logical_attempts'] += 1
    persist()
    return _LOGICAL.set(number)


def end_logical(token):
    _LOGICAL.reset(token)


def model_call(function):
    @wraps(function)
    def observed(*args, **kwargs):
        judge = _JUDGE.get()
        token = model_attempt(judge['model_attempts'] + 1 if judge is not None else 1)
        try:
            return function(*args, **kwargs)
        finally:
            end_attempt(token)
    return observed


def model_attempt(number):
    row = _JUDGE.get()
    if row is not None:
        row['model_attempts'] += 1
    persist()
    return _ATTEMPT.set(number)


def end_attempt(token):
    _ATTEMPT.reset(token)


def initiated(provider, model):
    active = _ACTIVE.get()
    judge = _JUDGE.get()
    if active is None or judge is None:
        return None
    value = active[1]
    if len(value['transports']) >= MAX_RECORDS:
        value['retention_complete'] = False
        persist()
        return None
    row = {'id': len(value['transports']) + 1, 'judgment': judge['id'],
           'model_attempt': _ATTEMPT.get(), 'logical_attempt': _LOGICAL.get(), 'provider': provider, 'model': model,
           'outcome': 'initiated', 'http_status': None, 'response_received': False,
           'usage': unknown()}
    value['transports'].append(row)
    persist()  # A hard interruption leaves an initiated record, never a completed zero.
    return row


def received(row, status, observation):
    if row is not None:
        row.update(outcome='http_response', http_status=status,
                   response_received=True, usage=observation)
        persist()


def failed(row, *, response_received=False, status=None):
    if row is not None:
        row.update(outcome='completion_unknown', response_received=response_received, http_status=status)
        persist()


def validate(value):
    """Closed and bounded public admission. Reject duplicate/replayed identities."""
    def require(ok):
        if not ok:
            raise ValueError('Invalid judge accounting')
    require(type(value) is dict and set(value) == {'version', 'session', 'closed', 'judgments', 'transports', 'retention_complete'})
    require(value['version'] == VERSION and type(value['session']) is str and len(value['session']) == 32
            and all(c in '0123456789abcdef' for c in value['session']))
    require(type(value['closed']) is bool and type(value['retention_complete']) is bool)
    for key in ('judgments', 'transports'):
        require(type(value[key]) is list and len(value[key]) <= MAX_RECORDS)
    judges = {}
    for n, row in enumerate(value['judgments'], 1):
        require(type(row) is dict and set(row) == {'id', 'metric', 'provider', 'closed', 'model_attempts', 'logical_attempts', 'not_applicable'})
        require(type(row['id']) is int and row['id'] == n and type(row['closed']) is bool
                and row['metric'] in ('accuracy', 'goal_accuracy', 'behavior_check')
                and row['provider'] in ('openai', 'openai-compatible', 'nv_build', 'anthropic', 'bedrock')
                and type(row['model_attempts']) is int and 0 <= row['model_attempts'] <= MAX_RECORDS
                and type(row['logical_attempts']) is int and 0 <= row['logical_attempts'] <= MAX_RECORDS
                and type(row['not_applicable']) is bool)
        judges[n] = row
    for n, row in enumerate(value['transports'], 1):
        require(type(row) is dict and set(row) == {'id', 'judgment', 'model_attempt', 'logical_attempt', 'provider', 'model',
                'outcome', 'http_status', 'response_received', 'usage'})
        require(type(row['id']) is int and row['id'] == n and type(row['judgment']) is int and row['judgment'] in judges)
        require(row['provider'] == judges[row['judgment']]['provider'] == 'openai')
        require(type(row['model']) is str and 0 < len(row['model']) <= 128
                and all(c.isalnum() or c in '-_./:' for c in row['model']))
        require(type(row['logical_attempt']) is int and 1 <= row['logical_attempt'] <= judges[row['judgment']]['logical_attempts'])
        require(type(row['model_attempt']) is int and 1 <= row['model_attempt'] <= judges[row['judgment']]['model_attempts'])
        require(row['outcome'] in ('initiated', 'http_response', 'completion_unknown') and type(row['response_received']) is bool)
        require(row['http_status'] is None or type(row['http_status']) is int and 100 <= row['http_status'] <= 599)
        require(row['outcome'] != 'http_response' or row['response_received'] and row['http_status'] is not None)
        u = row['usage']
        require(type(u) is dict and set(u) == {'status', 'counters'} and type(u['counters']) is dict and set(u['counters']) == set(TOKENS))
        require(u['status'] in ('complete', 'missing', 'malformed', 'inconsistent'))
        require(all(v is None or type(v) is int and 0 <= v <= 10**12 for v in u['counters'].values()))
        require(u['status'] == 'malformed' or usage(u['counters']) == u)
        require(row['outcome'] == 'http_response' or u == unknown())
    return value


def summarize(population):
    """One envelope per expected trial; None keeps absent trials in coverage."""
    seen = set()
    totals = dict.fromkeys(TOKENS, 0)
    coverage = dict.fromkeys(TOKENS, 0)
    result = {'version': VERSION, 'expected_trials': len(population), 'observed_trials': 0,
              'logical_judgments': 0, 'logical_attempts': 0, 'model_attempts': 0, 'http_attempts': 0, 'responses_received': 0,
              'usage_complete_responses': 0, 'completion_unknown': 0, 'complete': True}
    for envelope in population:
        if envelope is None:
            result['complete'] = False
            continue
        validate(envelope)
        if envelope['session'] in seen:
            raise ValueError('Duplicate judge accounting session')
        seen.add(envelope['session'])
        result['observed_trials'] += 1
        result['logical_judgments'] += len(envelope['judgments'])
        result['logical_attempts'] += sum(j['logical_attempts'] for j in envelope['judgments'])
        result['model_attempts'] += sum(j['model_attempts'] for j in envelope['judgments'])
        result['complete'] &= envelope['closed'] and envelope['retention_complete'] and all(j['closed'] and
            j['provider'] == 'openai' and ((j['not_applicable'] and j['model_attempts'] == 0) or
                j['model_attempts'] > 0 and {t['model_attempt'] for t in envelope['transports'] if t['judgment'] == j['id']} == set(range(1, j['model_attempts'] + 1)))
            for j in envelope['judgments'])
        for row in envelope['transports']:
            result['http_attempts'] += 1
            result['responses_received'] += int(row['response_received'])
            result['completion_unknown'] += int(row['outcome'] != 'http_response')
            u = row['usage']
            result['usage_complete_responses'] += int(u['status'] == 'complete')
            result['complete'] &= row['outcome'] == 'http_response' and u['status'] == 'complete'
            for k, v in u['counters'].items():
                if v is not None and u['status'] in ('complete', 'missing'):
                    totals[k] += v
                    coverage[k] += 1
    result['session_ids'] = sorted(seen)
    result['known_tokens'] = {k: totals[k] if coverage[k] else None for k in TOKENS}
    result['token_coverage'] = coverage
    result['cost_estimate_usd'] = None  # Requires separately identified prices; never provider billing.
    return result


def require_complete(summary, *, max_http_attempts):
    """Use at the existing scheduling checkpoint before admitting another unit."""
    if summary.get('version') != VERSION or summary.get('complete') is not True:
        raise ValueError('Stop: unknown judge accounting')
    if type(max_http_attempts) is not int or summary['http_attempts'] >= max_http_attempts:
        raise ValueError('Stop: judge transport allocation exhausted')
