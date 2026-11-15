"""Interpret the released 0.9 producer; no execution, task grading or fallback.

The native helpers, not repository thresholds, own score, N/A and verdict rules.
Only the already qualified offline-v3 producer may use this interpretation.
"""
import json
from pathlib import Path
import evaluator_profiles as profiles

PROFILE = json.loads((Path(__file__).resolve().parents[1] / 'evals/benchmark-090.json').read_text())


def interpret(reward, trial, threshold):
    from skillevaluator.tier3.harbor import metrics
    from skillevaluator.tier3.attempt_verdict import attempt_verdict
    from skill_reports import require
    require(metrics.DIMENSION_DEFINITIONS == PROFILE['dimensions'],
            'Released dimension contract differs')
    missing_reward = reward is None
    reward = reward or {}
    failed = reward.get('evaluation_status') in ('failed', 'error')
    errors = reward.get('evaluation_errors') or {}
    require(type(errors) is dict, 'Invalid evaluation errors')
    unsupported = bool({'evidence', 'execution_evidence'} & errors.keys())
    runtime_failed = (missing_reward or trial.get('exception_info') is not None) and not failed
    # A failed judge/unsupported diagnostic's transport zero is never a score.
    available = not failed and not runtime_failed
    retained = diagnostic_observations(reward, trial) if failed else {}
    values = {}
    skipped = []
    for name in metrics.DEFAULT_METRICS:
        na = metrics.metric_is_not_applicable(reward, name) if available else False
        value = metrics.metric_value(reward, name) if available else retained.get(name)
        if na: skipped.append(name)
        values[name] = {'status': 'not_applicable' if na else 'observed' if value is not None else 'unavailable',
                        'value': value}
    overall = metrics.overall_score(reward) if available else None
    if overall is not None:
        require(reward.get('score_policy') == PROFILE['scoring'], 'Unversioned native score')
        require(reward.get('overall') == overall, 'Native overall disagreement')
        verdict = attempt_verdict(overall, threshold, reward=reward)
        quality = {'overall': overall, 'passed': verdict.passed,
                   'correct_answer': verdict.correct_answer, 'security_clean': verdict.security_clean,
                   'required_failure': verdict.required_failure}
    else:
        quality = dict.fromkeys(('overall', 'passed', 'correct_answer', 'security_clean', 'required_failure'))
    dimensions = metrics.dimension_scores({k:v['value'] for k,v in values.items() if v['status'] == 'observed'}, skipped)
    return {'outcome': 'unsupported' if unsupported else 'judgment_unavailable' if failed else
            'runtime_failure' if runtime_failed else 'passed' if quality['passed'] is True else
            'failed' if quality['passed'] is False else 'judgment_unavailable',
            'metrics': values, 'dimensions': {name: {'status': 'observed', 'value': row['score']}
                if name in dimensions and (row := dimensions[name]) else
                {'status': 'not_applicable' if metrics.dimension_is_not_applicable(name, skipped) else 'unavailable', 'value': None}
                for name in PROFILE['dimensions']},
            'quality': quality}


def diagnostic_observations(reward, trial):
    """The released verifier keeps other valid scores when a judge fails.

    Its overall zero remains transport data. Unsupported evidence has no scores.
    This extension does not change the historical unscored diagnostic contract.
    """
    from skill_reports import require
    from skillevaluator.tier3.harbor.metrics import score_value, DEFAULT_METRICS
    raw = (trial.get('verifier_result') or {}).get('rewards') or {}
    errors = reward.get('evaluation_errors') or {}
    require(type(raw) is dict and type(errors) is dict, 'Invalid native diagnostic values')
    if not raw or set(raw) == {'overall'} and type(raw['overall']) in (int, float) and raw['overall'] == 0.0:
        return {}
    observed = set(raw) - {'overall'}
    require(bool(errors) and set(errors) <= {'accuracy', 'goal_accuracy', 'behavior_check'}
            and observed <= set(DEFAULT_METRICS) and not observed.intersection(errors)
            and raw.get('overall') == 0.0
            and all(score_value(v) is not None for v in raw.values()), 'Unscored diagnostic acquired measurements')
    return {k:v for k,v in raw.items() if k != 'overall'}

def validate_native_aggregates(agent, rows, ids):
    """Reconcile complete arm aggregates with the released N/A-aware helpers."""
    import skill_evidence as e
    from skillevaluator.tier3.harbor import metrics
    from skillevaluator.tier3.harbor.collector import _compute_lift
    rewards = {}
    aggregates = {}
    for arm in ('with_skill', 'without_skill'):
        population = [reward for obs, reward, _ in rows if obs['arm'] == arm and reward is not None
                      and reward.get('evaluation_status') not in ('failed', 'error')]
        rewards[arm] = population
        condition = agent['conditions'][arm]
        if condition['execution_status'] != 'succeeded': continue
        e.require(len(population) == condition['expected_attempts'] == condition['scored_attempts'], 'Incomplete native benchmark arm')
        means, metric_set, _ = metrics.average_metrics(population)
        e.require(metric_set == PROFILE['metric_set'] and agent[arm] == means, 'Native benchmark aggregate mismatch')
        skipped = metrics.not_applicable_metrics(population)
        aggregates[arm] = {name:row['score'] for name,row in agent['dimensions_' + arm].items()}
        e.require(agent['not_applicable_metrics'][arm] == skipped and
                  agent['dimensions_' + arm] == metrics.dimension_scores(means, skipped), 'Native applicability mismatch')
    if all(agent['conditions'][arm]['execution_status'] == 'succeeded' for arm in rewards):
        expected = _compute_lift(agent['with_skill'], agent['without_skill'],
            with_rewards=rewards['with_skill'], without_rewards=rewards['without_skill'], expected_case_ids=ids)
        e.require(agent['lift'] == expected, 'Native benchmark lift mismatch')
    return {arm:aggregates.get(arm, {}) for arm in ('with_skill', 'without_skill')}
