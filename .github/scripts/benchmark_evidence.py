"""Versioned benchmark admission shared by recovery, reports and history.

This is an extension of the existing captured evidence contract. It does not
select an execution runtime, grade tasks, publish history or invoke a judge.
"""
import copy

import evaluator_profiles as profiles


def profile(value):
    return profiles.benchmark_profile(value)


def metadata(value):
    import skill_evidence as e
    e.closed(value, ('profile', 'origin', 'judgments'))
    p = profile(value['profile'])
    e.require(value['origin'] == p['origin'] and value['judgments'] in p['judgments'],
              'Unsupported behavioral evidence origin')
    return p


def capture(meta, data, native_rows, status, recovery, aggregates):
    """Attach only interpreted captured native observations to the existing witness."""
    import skill_evidence as e
    from evaluator_090 import interpret
    p = metadata(meta)
    e.require(data['policy'].get('producer_profile') == p['producer'], 'Behavioral producer mismatch')
    rows = []
    for obs, reward, trial in native_rows:
        threshold = data['policy']['attempts']['pass_threshold']
        e.require(threshold is not None, 'Native verdict threshold required')
        row = interpret(reward, trial, threshold)
        if obs['score'] is not None:
            e.require(obs['score'] == row['quality']['overall'] and (obs['rubric_pass'] is None or obs['rubric_pass'] == row['quality']['passed']),
                      'Native released verdict disagreement')
        if 'security_evidence' in obs:
            row['security_evidence'] = copy.deepcopy(obs['security_evidence'])
        if p.get('accounting'):
            row['judge_accounting'] = trial['_judge_accounting']
        rows.append({'observation_id': obs['id'], **row})
    value = {**meta, 'policy_id': e.identity([p, data['policy']['id']]),
             'native_status': status, 'recovery': recovery, 'observations': rows, 'native_dimensions':aggregates}
    if p.get('accounting'):
        value['judge_accounting'] = accounting_summary(value, data)
    value['populations'] = populations(value, data)
    return value


def populations(value, data):
    import skill_evidence as e
    by_id = {o['id']:o for o in data['observations']}
    output = {}
    for arm in data['arms']:
        rows = [r for r in value['observations'] if by_id[r['observation_id']]['arm'] == arm['name']]
        output[arm['name']] = {}
        for name in profiles.benchmark_profile('behavioral-090-offline-v1')['dimensions']:
            counts = {key: sum(r['dimensions'][name]['status'] == key for r in rows)
                      for key in ('observed', 'not_applicable', 'unavailable')}
            expected = arm['coverage']['expected_attempts']
            output[arm['name']][name] = {**counts, 'expected': expected,
                'absent': None if expected is None else expected - len(rows)}
    return output


def validate(value, data):
    """Closed data-only validation; the normalizer witness binds native semantics."""
    import skill_evidence as e
    e.closed(value, ('profile', 'origin', 'judgments', 'policy_id', 'native_status', 'recovery', 'observations', 'populations', 'native_dimensions') + (('judge_accounting',) if 'judge_accounting' in value else ()))
    p = metadata({k:value[k] for k in ('profile', 'origin', 'judgments')})
    e.require(data['kind'] == 'behavioral' and data['schema_version'] == 1
              and data['policy'].get('producer_profile') == p['producer']
              and data['policy']['scoring_policy'] == p['scoring']
              and data['policy']['fields']['grading'] == p['grading'], 'Behavioral producer or grading mismatch')
    e.require(value['policy_id'] == e.identity([p, data['policy']['id']]), 'Behavioral policy mismatch')
    e.enum(value['native_status'], ('complete', 'incomplete')); e.boolean(value['recovery'])
    e.require(type(value['observations']) is list and len(value['observations']) == len(data['observations']), 'Behavioral population mismatch')
    observations = {o['id']:o for o in data['observations']}
    ids = set(observations); seen = set()
    metrics = ('security', 'skill_execution', 'skill_efficiency', 'accuracy', 'goal_accuracy', 'behavior_check')
    for row in value['observations']:
        e.closed(row, ('observation_id', 'outcome', 'metrics', 'dimensions', 'quality') +
                 (('security_evidence',) if 'security_evidence' in row else ()) +
                 (('judge_accounting',) if p.get('accounting') else ()))
        e.require(row['observation_id'] in ids and row['observation_id'] not in seen, 'Behavioral observation mismatch')
        seen.add(row['observation_id'])
        e.enum(row['outcome'], ('passed', 'failed', 'unsupported', 'judgment_unavailable', 'runtime_failure', 'collection_incomplete'))
        for container, names in ((row['metrics'], metrics), (row['dimensions'], p['dimensions'])):
            e.closed(container, names)
            for name, item in container.items():
                e.closed(item, ('status', 'value'))
                e.enum(item['status'], ('observed', 'not_applicable', 'unavailable'))
                e.optional(item['value'], e.number)
                e.require((item['value'] is not None) == (item['status'] == 'observed'), 'Missingness became a score')
                e.require(name != 'security' or item['status'] != 'not_applicable', 'Security cannot be N/A')
        if value['judgments'] == 'unavailable':
            e.require(all(row['metrics'][k]['status'] != 'observed' for k in ('accuracy', 'goal_accuracy', 'behavior_check')), 'Unavailable judgment acquired values')
        q = row['quality']; e.closed(q, ('overall', 'passed', 'correct_answer', 'security_clean', 'required_failure'))
        e.optional(q['overall'], e.number)
        for key in ('passed', 'correct_answer', 'security_clean'): e.optional(q[key], e.boolean)
        e.optional(q['required_failure'], lambda v:e.enum(v, ('wrong_answer', 'security')))
        e.require((q['overall'] is not None) == (q['passed'] is not None), 'Unavailable verdict became negative')
        e.require(row['outcome'] == ('passed' if q['passed'] else 'failed') if q['passed'] is not None
                  else row['outcome'] in ('unsupported', 'judgment_unavailable', 'runtime_failure', 'collection_incomplete'), 'Verdict contradiction')
        if 'security_evidence' in row:
            e.unscored_security.validate_security(row['security_evidence'])
            original = observations[row['observation_id']]
            e.require(row['security_evidence'] == original.get('security_evidence'), 'Security support mismatch')
    e.closed(value['native_dimensions'], ('with_skill', 'without_skill'))
    for arm, dimensions in value['native_dimensions'].items():
        e.require(type(dimensions) is dict and set(dimensions) <= set(p['dimensions']), 'Unknown native dimensions')
        for observed in dimensions.values(): e.number(observed)
        condition = next(a for a in data['arms'] if a['name'] == arm)
        e.require(not dimensions or condition['execution_status'] == 'succeeded', 'Failed arm acquired native aggregates')
    if p.get('accounting'):
        e.require(value.get('judge_accounting') == accounting_summary(value, data), 'Judge accounting totals differ')
    else:
        e.require('judge_accounting' not in value, 'Historical accounting meaning changed')
    e.require(value['populations'] == populations(value, data), 'Behavioral denominators differ')
    # These are fixture observations, never legacy headline quality measurements.
    e.require(not data['metrics'] and all(o['score'] is None for o in data['observations']), 'Fixture acquired production metrics')
    e.reports.public_strings(value)


def history_admission(data):
    """Pure eligibility simulation; never writes a ledger or returns live approval."""
    import skill_evidence as e
    e.validate_public(data)
    value = data.get('benchmark')
    e.require(value is not None, 'Versioned behavioral policy required')
    reasons = ['offline_policy_not_enabled_for_production', value['origin']]
    if value['judgments'] == 'simulated': reasons.append('simulated_judgments')
    if value['recovery']: reasons.append('recovered')
    if value['native_status'] != 'complete' or data['availability']['status'] != 'complete': reasons.append('incomplete')
    conditions = comparison_identity(data)
    def unknown(value):
        if isinstance(value, dict): return any(unknown(v) for v in value.values())
        if isinstance(value, list): return any(unknown(v) for v in value)
        return value is None or value == 'unknown'
    if unknown(conditions): reasons.append('identity_missing')
    return {'eligible': False, 'series': e.identity(conditions), 'reasons': reasons}


def comparison_identity(data):
    """A series binds policy, cohort, grading and both deployment conditions."""
    import skill_evidence as e
    value = data['benchmark']
    return {'profile': value['policy_id'], 'origin': value['origin'], 'judgments': value['judgments'],
            'task': data['source']['skill_id'], **data['dataset'],
            'policy': data['policy']['id'], 'deployment': [a['condition'] for a in data['arms']]}


def report(workspace, root, name, mode, destination, selected=None):
    import skill_evidence as e
    import skill_reports as r
    native = e.normalize_behavioral(root, name, selected, workspace, native_layout=True)
    public = e.project(native)
    e.require('benchmark' in public, 'Versioned behavioral profile required')
    e.safe_path(destination.parent, directory=True)
    e.require(destination.resolve() == destination.absolute() and not destination.is_relative_to(workspace), 'External benchmark report required')
    destination.mkdir(exist_ok=False)
    r.public_benchmark(workspace, root, name, mode, destination / 'public', selected)
    r.write_json(destination / 'admission.json', history_admission(public))
    return public


def accounting_summary(value, data):
    import judge_accounting as accounting
    import skill_evidence as e
    population = []
    for row in value['observations']:
        item = row['judge_accounting']
        e.closed(item, ('status', 'evidence'))
        e.enum(item['status'], ('observed', 'absent', 'invalid'))
        e.require((item['evidence'] is not None) == (item['status'] == 'observed'), 'Accounting missingness mismatch')
        population.append(item['evidence'])
    expected = sum(a['coverage']['expected_attempts'] or 0 for a in data['arms'])
    e.require(expected >= len(population), 'Accounting population exceeds trials')
    return accounting.summarize(population + [None] * (expected - len(population)))
