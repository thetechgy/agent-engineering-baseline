"""Compact publisher-derived observations; never an alternative grader or native witness."""
from collections import defaultdict
from datetime import datetime, timedelta
import copy
from decimal import Decimal
import re

import skill_analysis as analysis
import skill_evidence as evidence

VERSION = 1
LIMIT = 16 * 1024 * 1024
SNAPSHOT_LIMIT = 64 * 1024
CLASSES = ('standard', 'quality', 'diagnostic')
FIELDS = ('schema_version', 'kind', 'source', 'run_id', 'dataset', 'policy', 'arms', 'metrics', 'availability', 'scans')


def timestamp(value):
    evidence.require(type(value) is str and re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ', value), 'Invalid history timestamp')
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def empty(at):
    timestamp(at)
    return {'schema_version': VERSION, 'retained_at': at, 'observations': [], 'protected': []}


def observation(record, slot, provenance, at, execution=None):
    """Caller must first authenticate producer and validate the original public bundle."""
    evidence.validate_public(record)
    core = {key: copy.deepcopy(record[key]) for key in FIELDS}
    # Reference IDs remain provenance locators, not claims of retained possession.
    category = 'quality' if slot == 'quality' else 'standard' if slot.startswith('standard--') else 'diagnostic'
    subject = [provenance['repository'], slot, record['source']['skill_id'],
               record['run_id'] if category == 'standard' else [provenance['run_id'], provenance['attempt']],
               record['source']['content']['digest'], record['policy']['id'], record['dataset']['staged_digest']]
    return {'id': evidence.identity(subject), 'class': category, 'slot': slot,
            'provenance': copy.deepcopy(provenance), 'record_id': evidence.identity(record),
            'record_digest': evidence.digest_bytes(evidence.encoded(record)), 'admitted_at': at,
            'execution': execution or {'started_at': None, 'completed_at': None},
            'record': core, 'numeric_complete': analysis.complete_numeric(record) if category == 'standard' and record['schema_version'] == 1 else False,
            'finding_counts': {level: sum(f['severity'] == level for f in record['findings'])
                               for level in analysis.SEVERITIES}}


def validate(value):
    from skill_pages import validate_provenance, SLOT
    evidence.closed(value, ('schema_version', 'retained_at', 'observations', 'protected'))
    evidence.require(type(value['schema_version']) is int and value['schema_version'] == VERSION, 'History version')
    timestamp(value['retained_at'])
    evidence.require(type(value['observations']) is list and len(evidence.encoded(value)) <= LIMIT, 'History size limit')
    seen = set()
    for item in value['observations']:
        evidence.closed(item, ('id', 'class', 'slot', 'provenance', 'record_id', 'record_digest', 'admitted_at', 'execution', 'record', 'numeric_complete', 'finding_counts'))
        for key in ('id', 'record_id', 'record_digest'): evidence.sha(item[key])
        evidence.require(item['id'] not in seen, 'Duplicate history observation'); seen.add(item['id'])
        evidence.require(len(evidence.encoded(item)) <= SNAPSHOT_LIMIT, 'Snapshot size limit')
        evidence.enum(item['class'], CLASSES); evidence.require(SLOT.fullmatch(item['slot']), 'History slot')
        expected = 'quality' if item['slot'] == 'quality' else 'standard' if item['slot'].startswith('standard--') else 'diagnostic'
        evidence.require(item['class'] == expected, 'History class mismatch')
        validate_provenance(item['provenance']); timestamp(item['admitted_at'])
        evidence.require(timestamp(date(item)) <= timestamp(value['retained_at']), 'Future historical observation')
        evidence.closed(item['execution'], ('started_at', 'completed_at'))
        for val in item['execution'].values():
            if val is not None: timestamp(val)
        a = item['execution']['started_at']
        b = item['execution']['completed_at']
        evidence.require(a is None or b is None or timestamp(a) <= timestamp(b), 'History execution order')
        r=item['record']; evidence.closed(r, FIELDS)
        evidence.validate_source(r['source']); evidence.validate_policy(r['policy'], custom_only=r['policy']['fields']['grading']=='custom_only')
        evidence.enum(r['kind'], ('static','behavioral')); evidence.boolean(item['numeric_complete'])
        evidence.require(type(r['schema_version']) is int and r['schema_version'] in (1,2), 'History source schema')
        evidence.optional(r['run_id'], evidence.token)
        ds=r['dataset']
        evidence.closed(ds, ('owner','authored_digest','staged_digest','staged_algorithm','case_cohort_digest','case_ids','authored_provenance','staged_provenance'))
        evidence.enum(ds['owner'], ('local','overlay','unknown'))
        for key in ('authored_digest','staged_digest','case_cohort_digest'): evidence.optional(ds[key], evidence.sha)
        evidence.optional(ds['staged_algorithm'], lambda v: evidence.enum(v, ('skill-evaluator-dataset-snapshot/1', 'sha256-staged-task-inputs-v1')))
        for key in ('authored_provenance','staged_provenance'): evidence.enum(ds[key], evidence.PROVENANCE)
        ids=evidence.case_ids(ds['case_ids'])
        evidence.require(ds['case_cohort_digest']==evidence.identity(sorted(ids)), 'History cohort mismatch')
        evidence.closed(r['availability'], ('status','provenance','reasons'))
        evidence.enum(r['availability']['status'], ('complete','incomplete','unavailable'))
        evidence.enum(r['availability']['provenance'], evidence.PROVENANCE)
        evidence.require(type(r['availability']['reasons']) is list, 'History limitations')
        for reason in r['availability']['reasons']: evidence.enum(reason, evidence.REASONS)
        evidence.require(type(r['arms']) is list and len(r['arms'])<=2, 'History arm limit')
        for arm in r['arms']:
            evidence.validate_condition(arm['condition'])
            evidence.enum(arm['name'], ('with_skill','without_skill'))
            evidence.enum(arm['execution_status'], ('succeeded','failed','incomplete','unknown'))
            evidence.closed(arm['coverage'], ('case_details','expected_attempts','expected_cases','recorded_attempts','scored_attempts','unscored_attempts'))
            for key,n in arm['coverage'].items():
                if key!='case_details': evidence.optional(n,evidence.count)
            evidence.enum(arm['coverage']['case_details'], ('complete','partial','unavailable'))
        evidence.require(type(r['scans']) is list and len(r['scans'])<=100, 'History scanner limit')
        for scan in r['scans']:
            evidence.token(scan['scanner']); evidence.enum(scan['status'], ('passed','failed','incomplete','skipped','unavailable'))
            evidence.closed(scan['severity_counts'], analysis.SEVERITIES)
            for n in scan['severity_counts'].values(): evidence.optional(n,evidence.count)
        subject=[item['provenance']['repository'], item['slot'], r['source']['skill_id'],
                 r['run_id'] if expected=='standard' else [item['provenance']['run_id'],item['provenance']['attempt']],
                 r['source']['content']['digest'],r['policy']['id'],ds['staged_digest']]
        evidence.require(item['id']==evidence.identity(subject), 'History identity mismatch')
        evidence.require((r['kind']=='static') == (expected=='quality'), 'History kind mismatch')
        evidence.require(type(r['metrics']) is list and len(r['metrics']) <= 4, 'History metric limit')
        names=[]
        for m in r['metrics']:
            evidence.closed(m, ('name','value','unit')); evidence.enum(m['name'], tuple(evidence.reports.METRICS)); names.append(m['name'])
            evidence.require(m['unit']=='score', 'History metric unit'); evidence.number(m['value'], -1 if m['name']=='Skill Lift' else 0, 1)
        evidence.require(len(names)==len(set(names)), 'Duplicate history metric')
        evidence.require(not item['numeric_complete'] or (expected=='standard' and r['schema_version']==1 and len(names)==4 and len(r['arms'])==2 and all(
            a['execution_status']=='succeeded' and a['coverage']['case_details']=='complete' and a['coverage']['expected_attempts'] is not None
            and a['coverage']['scored_attempts']==a['coverage']['recorded_attempts']==a['coverage']['expected_attempts'] for a in r['arms'])), 'History completeness mismatch')
        evidence.closed(item['finding_counts'], analysis.SEVERITIES)
        for n in item['finding_counts'].values(): evidence.count(n)
        evidence.reports.public_strings(item)
    evidence.require(type(value['protected']) is list and len(value['protected'])==len(set(value['protected'])) and set(value['protected']) <= seen, 'Invalid protected baselines')
    return value


def add(value, item):
    for previous in value['observations']:
        same_attempt = (previous['slot'], previous['record']['source']['skill_id'], previous['provenance']['run_id'], previous['provenance']['attempt']) == (item['slot'], item['record']['source']['skill_id'], item['provenance']['run_id'], item['provenance']['attempt'])
        same_native = item['class'] == previous['class'] == 'standard' and (previous['slot'], previous['record']['run_id']) == (item['slot'], item['record']['run_id'])
        if same_attempt or same_native:
            evidence.require(previous['record_digest'] == item['record_digest'], 'Conflicting historical producer identity')
            return
    old = next((r for r in value['observations'] if r['id']==item['id']), None)
    if old:
        evidence.require(old['record_digest']==item['record_digest'], 'Conflicting historical measurement')
        return
    value['observations'].append(item)


def retain(value, at, baselines=()):
    timestamp(at); groups=defaultdict(list)
    for item in value['observations']:
        groups[(item['record']['source']['skill_id'],item['class'])].append(item)
    kept=[]; protected_ids=[]; cutoff=timestamp(at)-timedelta(days=90)
    for rows in groups.values():
        protected=[r for r in rows if (r['provenance']['run_id'],r['provenance']['attempt']) in baselines and r['class']=='standard']
        evidence.require(len(protected)<=2, 'Protected baseline limit')
        protected_ids.extend(r['id'] for r in protected)
        recent=[r for r in rows if r not in protected and timestamp(date(r))>=cutoff]
        kept.extend(protected+sorted(recent,key=lambda r:(date(r),r['id']),reverse=True)[:30])
    value.update(retained_at=at, protected=sorted(protected_ids), observations=sorted(kept,key=lambda r:(date(r),r['id'])))
    return validate(value)


def date(item):
    return item['execution']['completed_at'] or item['admitted_at']


def facts(item):
    r=item['record']
    return {'source':r['source'], 'conditions':analysis.condition_identity(r), 'complete_numeric':item['numeric_complete']}


def compare(left, right):
    a,b=left['record'],right['record']
    if a['schema_version']==2 or b['schema_version']==2:
        return 'custom_comparison_deferred', ['custom_cross_run_not_qualified'], {}
    classification,reasons=analysis.classify_facts(facts(left),facts(right))
    eligible=all(r['class']=='standard' and r['execution']['completed_at'] for r in (left,right))
    ordered=eligible and timestamp(left['execution']['completed_at'])<timestamp(right['execution']['completed_at'])
    if not ordered: return 'exploratory', ['chronology_or_purpose_unavailable'], {}
    if classification!='directly_comparable': return classification,reasons,{}
    am={m['name']:m['value'] for m in a['metrics']}; bm={m['name']:m['value'] for m in b['metrics']}
    return classification,reasons,{name:analysis.difference(analysis.quantity(Decimal(str(bm[name]))),analysis.quantity(Decimal(str(am[name])))) for name in am.keys() & bm.keys()}
