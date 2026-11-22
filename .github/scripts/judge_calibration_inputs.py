"""Frozen calibration inputs and applicability; no provider IO or orchestration.

Labels and acceptance metadata remain in the corpus, outside provider inputs.
The released evaluator owns all prompts, schemas and scoring.
"""
from dataclasses import dataclass
import json

from evaluation_campaign_core import require
from evaluation_runtime import ROOT
import evaluator_profiles as profiles
import skill_reports as reports

DIMENSIONS = ('accuracy', 'goal_accuracy', 'behavior_check')
MEMBER = '.github/evals/campaigns/judge-calibration-090-v1.json'


@dataclass
class Calibration:
    definition: dict
    member: str


def load(path, definition):
    active_member = '.github/evals/campaigns/judge-calibration-090-v1-sol62.json'
    require(path in (ROOT / MEMBER, ROOT / active_member) and path.resolve() == path,
            'Unregistered judge campaign definition')
    require(definition == reports.read_json(path)
            and definition['id'] == path.stem
            and definition['adapter'] == 'standard-judge-090'
            and definition['authorized_live_attempts'] == 0
            and set(definition) == {'id', 'type', 'adapter', 'corpus', 'rubric',
                                   'runtime_profile', 'protocol', 'authorized_live_attempts'},
            'Unsupported judge campaign')
    for field in ('corpus', 'rubric', 'runtime_profile', 'protocol'):
        target = ROOT / definition[field]
        require(target.resolve() == target and target.is_relative_to(ROOT), 'Unsafe judge input')
    task = Calibration(definition, path.relative_to(ROOT).as_posix())
    protocol(task)
    return task


def records(task):
    from qualify_standard_judges import corpus
    require(task.definition['corpus'] == '.github/evals/judge-calibration-090/corpus.json', 'Unsupported corpus')
    frozen = corpus()
    rubric = reports.read_json(ROOT / task.definition['rubric'])
    require(rubric['version'] == 1 and len(frozen['items']) == len(rubric['records']) == 7,
            'Frozen calibration population drift')
    rows = []
    for item, rule in zip(frozen['items'], rubric['records'], strict=True):
        require(item['id'] == rule['id'] and set(rule) == {'id', 'dimension', 'reference'}
                and rule['dimension'] == item['judgment'].split(':')[0]
                and rule['dimension'] in DIMENSIONS, 'Frozen applicability drift')
        if item['id'] == 'control-01':
            native = reports.read_json(ROOT / '.github/evals/gh/evals/evals.json')
            expected = next(r for r in native['evals'] if r['id'] == 'gh-014')['contract']['expected']
            require(json.loads(rule['reference']) == expected, 'Factual reference differs from frozen native answer')
        else:
            require(rule['reference'] is None, 'Unfrozen reference input')
        # Explicit projection: never pass item/reference/expected/ambiguity/sources.
        rows.append({'id': item['id'], 'dimension': rule['dimension'],
                     'question': item['question'], 'submission': item['submission'],
                     'reference': rule['reference'], 'expected_behavior': item['expected_behavior']})
    return rows


def applicable(record, dimension):
    return (dimension == record['dimension'] and
            bool(record['expected_behavior'] if dimension == 'behavior_check' else record['reference']))


def protocol(task):
    value = reports.read_json(ROOT / task.definition['protocol'])
    request = value['request']
    require(value['id'] == task.definition['id'] and value['definition'] == task.member
            and value['type'] == 'judge-only' and value['version'] == 1
            and value['authorized_live_attempts'] == 0
            and value['attempt_slots'] == len(records(task)) == 7
            and value['logical_judgments'] == sum(applicable(r, r['dimension']) for r in records(task)) == 6
            and value['inapplicable_dimensions'] == 15 and value['max_http_attempts'] == 12
            and value['concurrency'] == value['passes'] == 1
            and value['automatic_retries'] == value['replacements'] == 0
            and value['agent_runtime'] is value['agent_cleanup'] is value['variants'] is None,
            'Unsupported judge protocol')
    current = task.member != MEMBER
    require(request == {'provider': 'openai', 'model': reports.POLICY['model'] if current else 'gpt-5.6-sol',
                'endpoint': 'https://api.openai.com/v1/chat/completions',
                'follow_redirects': False,
                'retry_policy': 'strict', 'fallback_policy': 'replace', 'fallback_models': [],
                'transport_retries': 1, 'max_requests_per_judgment': 2, 'max_completion_tokens': 32768,
                'reasoning_effort': 'medium' if current else None, 'temperature': None, 'stream': False, 'judge_seconds': 180},
            'Unsupported judge provider/request profile')
    require(reports.read_json(ROOT / task.definition['runtime_profile']) == profiles.ACCOUNTING,
            'Judge accounting owner drift')
    require(type(value['deadline_seconds']) is int and 0 < value['deadline_seconds'] <= 1260
            and type(value['max_reported_tokens']) is int and 0 < value['max_reported_tokens'] <= 1000000
            and value['budget']['stop_estimate_usd'] > 0
            and value['budget']['billing_limit_enforced'] is False, 'Unbounded judge protocol')
    return value


def frozen(task):
    from evaluation_campaign_protocol import revision, digest
    from evaluation_campaign_selection import binding
    inputs = records(task)
    files = [task.member, task.definition['corpus'], task.definition['rubric'], task.definition['protocol'],
             task.definition['runtime_profile'], '.github/evals/judge-calibration-090/README.md',
             '.github/patches/skillevaluator-v0.9.0-accounting-v1.patch', '.github/locks/evaluator-0.9.lock']
    files += ['.github/scripts/' + name for name in (
        'judge_calibration_inputs.py', 'judge_calibration_campaign.py', 'judge_calibration_qualification.py',
        'judge_accounting.py', 'judge_transport_090.py', 'evaluation_campaign_core.py', 'evaluation_campaign_protocol.py',
        'evaluation_campaign_selection.py', 'evaluation_tasks.py', 'campaign_authentication_qualification.py',
        'setup-campaign-authentication.sh', 'skill_report.py', 'skill_analysis.py', 'codex_pilot_dispatch.py')]
    files += ['.github/workflows/evaluation-campaign.yml']
    identities = {name: digest(ROOT / name) for name in files}
    return {'revision': revision(), **binding(task), 'definition': task.definition,
            'protocol': protocol(task), 'protocol_digest': digest(ROOT / task.definition['protocol']),
            'evaluator': profiles.ACCOUNTING, 'authorized_live_attempts': 0,
            'source_identities': {'live': identities}, 'inputs': inputs,
            'schedule': [{'position': n, 'case': row['id'], 'trial': 1, 'variant': None}
                         for n, row in enumerate(inputs, 1)],
            'agent_runtime': None, 'agent_cleanup': None}
