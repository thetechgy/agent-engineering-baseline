#!/usr/bin/env python3
"""Bounded, offline descriptive analysis of validated public evidence bundles."""

import argparse
import copy
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import skill_evidence as evidence

require = evidence.require
SCHEMA_VERSION = 1
METHOD = 'bounded-descriptive-skill-analysis/1'
MAX_INPUTS = 32
MAX_REPORTS = 128
MAX_SKILLS = 1000
MAX_ENTRIES = 100000
MAX_COMPARISONS = 16
JSON_LIMIT = 64 * 1024 * 1024
MARKDOWN_LIMIT = 1024 * 1024
# Validated native numbers are binary floats in [-1, 1] or integers. This
# precision retains the smallest float contribution even beside a score of 1,
# through at most 100 planned attempts and subsequent differences of means.
DECIMAL_PRECISION = 400
SIGNIFICANT_GROUP_LIMIT = 8
# Shared across the entire Markdown summary, not renewed for each record.
STATIC_DETAIL_PREVIEW_LIMIT = 100
SEVERITIES = ('critical', 'high', 'medium', 'low')


NEXT_STEPS = {
    'complete_scans_and_reproject': 'Inspect available evidence and identify the scan limitation. Regenerate evidence after resolving or better characterizing it; rerunning alone may not resolve a tooling limitation.',
    'inspect_original_scanner_evidence': 'Inspect the original scanner finding and its applicability.',
    'inspect_original_case_evidence': 'Inspect both arms of the case, including attempts and grader evidence.',
    'inspect_gate_evidence': 'Inspect the mandatory gate evidence before treating the result as acceptable.',
    'complete_execution_and_reproject': 'Complete missing execution evidence, then regenerate public evidence.',
    'retain_or_reacquire_exact_evidence': 'Retain or reacquire the exact identified evidence; keep availability unchanged until verified.',
    'supply_at_most_16_skill_pairs': 'Supply at most 16 intended skill pairs in a separate analysis invocation.',
    'verify_benchmark_identities': 'Verify source, dataset, policy and execution identities before comparing runs.',
    'inspect_original_run_evidence': 'Inspect original run evidence under the recorded benchmark conditions.',
    'supply_two_intended_runs': 'Supply exactly two intended measured runs per skill to the existing analyzer.',
    'supply_model_backed_public_report': 'Supply a validated model-backed public report when an evaluation is authorized.',
}
FINDING_LABELS = {
    'custom_unavailable': 'Unavailable deterministic evaluation',
    'custom_measured_failure': 'Reported deterministic measurement warrants investigation',
    'case_regression': 'Lower with-skill case score', 'failed_gate': 'Failed mandatory gate',
    'failed_static_checks': 'Native required check not passed', 'incomplete_scans': 'Incomplete static scans',
    'incomplete_execution': 'Incomplete execution evidence', 'unavailable_support': 'Original support unavailable',
    'comparison_limit': 'Comparison invocation limit', 'comparison_limitation': 'Comparison unavailable or limited',
    'configured_unmeasured': 'Configured suite without measurement',
    'run_metric_regression': 'Lower metric in right-hand run', 'run_case_regression': 'Lower case score in right-hand run',
}


def coverage_label(skill):
    purposes = {run['custom']['purpose'] for run in skill['behavioral_results'] if 'custom' in run}
    if purposes:
        return ' · '.join(('Oracle qualification' if purpose == 'oracle_qualification' else 'Model-backed custom evidence')
                          for purpose in sorted(purposes))
    if any(run['measured'] for run in skill['behavioral_results']):
        return 'Measured results'
    if any(config['suite'] is not None for config in skill['configurations']) or skill['behavioral_results']:
        return 'Configured; results not supplied'
    if skill['configurations']:
        return 'No configured suite'
    return 'Configuration not supplied'


FINDING_PREVIEW_LIMIT = 5


def ordered_findings(findings):
    """Presentation order only; serialized analysis and identities are unchanged."""
    order = {'mandatory': 0, 'investigate': 1, 'context': 2}
    return sorted(findings, key=lambda f: (order[f['importance']], f['kind'], f['id']))


def finding_observation(item):
    observed = item['observed']
    facts = [item['skill'] or 'Report scope']
    if item['case_ids']:
        facts.append('cases ' + ', '.join(item['case_ids']))
    for key, label in (('with_minus_without', 'with minus without'), ('right_minus_left', 'right minus left')):
        if key in observed:
            facts.append(label + ' ' + signed(observed[key]))
    for key, label in (('scanners', 'scanners'), ('components', 'failed gate components'), ('metric_ids', 'metrics')):
        if observed.get(key):
            facts.append(label + ': ' + ', '.join(observed[key]))
    if 'classification' in observed:
        facts.append('recorded outcome: ' + observed['classification'])
    return '; '.join(facts)


def finding_qualifier(item):
    return item['uncertainty'].replace('_', ' ')


def render_finding(item, *, exact=False):
    lines = [f"- **{FINDING_LABELS[item['kind']]}**: {finding_observation(item)}.",
             f"  Evidence limit: {finding_qualifier(item)}. Next: {NEXT_STEPS[item['next_step']]}"]
    if exact:
        lines += ['', '<details><summary>Exact finding and evidence identities</summary>', '',
                  f"Finding `{item['id']}`; importance `{item['importance']}`; uncertainty `{item['uncertainty']}`; next step `{item['next_step']}`."]
        for key in ('record_ids', 'case_ids', 'observation_ids', 'reference_ids'):
            lines.append(key + ': ' + (', '.join('`' + value + '`' for value in item[key]) or 'none'))
        lines += ['', '</details>', '']
    return lines


def static_record(record_id, record):
    return {'record_id': record_id, 'run_id': record['run_id'], 'source': compact_source(record['source']),
            'availability': copy.deepcopy(record['availability']), 'scans': copy.deepcopy(record['scans']),
            'detailed_findings': copy.deepcopy(record['findings'])}


def static_groups(runs):
    """Display roll-ups only; every finding and its containing record stay distinct."""
    groups = {}
    for run in runs:
        for item in run['detailed_findings']:
            if item['severity'] not in ('critical', 'high'):
                continue
            key = (item['severity'], item['scanner'], item['check'],
                   None if item['check'] is not None else (run['record_id'], item['reference']))
            groups.setdefault(key, []).append((run, item))
    return [(key, sorted(items, key=lambda pair: (pair[0]['source']['skill_id'], pair[0]['record_id'], pair[1]['reference'])))
            for key, items in sorted(groups.items(), key=lambda pair:
                (SEVERITIES.index(pair[0][0]), pair[0][1], pair[0][2] or '', pair[0][3] or ('', '')))]


def static_totals(runs, scanner='catalog-total'):
    """Sum authoritative counts once per skill; never combine repeated snapshots."""
    names = [run['source']['skill_id'] for run in runs]
    if not runs or len(names) != len(set(names)):
        return None
    scans = [next((s for s in run['scans'] if s['scanner'] == scanner), None) for run in runs]
    return {level: sum(s['severity_counts'][level] for s in scans)
            if all(s is not None and s['severity_counts'][level] is not None for s in scans) else None
            for level in SEVERITIES}



def static_count_label(runs):
    totals = static_totals(runs)
    if not runs:
        return 'Not supplied'
    if totals is None:
        return 'Totals withheld: no single snapshot per skill'
    return ' · '.join((str(totals[level]) if totals[level] is not None else 'unknown') + ' ' + level
                      for level in SEVERITIES)


def static_guidance(scanner, check):
    if (scanner, check) == ('SCHEMA', 'author_missing'):
        return ('Author metadata is optional under the Agent Skills specification. This evaluator flag alone '
                'does not establish a defect or justify a metadata change; inspect the evaluator requirement and repository policy.')
    return {
        'SECURITY': 'Inspect exact source context and applicability, including prohibitions and examples; the flag is not a confirmed vulnerability.',
        'PII': 'Privately inspect the flagged source and classification; do not reproduce potentially sensitive content.',
        'SCHEMA': 'Inspect the named evaluator requirement and repository policy before deciding whether a change is warranted.',
        'QUALITY': 'Inspect the reported heuristic; it does not measure task success, token consumption or execution efficiency.',
    }.get(scanner, 'Inspect the original evaluator finding and source context before deciding whether a change is warranted.')


def static_overview(runs):
    states = [next((s['status'] for s in run['scans'] if s['scanner'] == 'catalog-total'), 'unavailable') for run in runs]
    lines = [f"{len(runs)} static records supplied: " + ' · '.join(
        f'{states.count(state)} {state}' for state in ('passed', 'failed', 'incomplete', 'unavailable')) + ' native assessments.']
    for scanner, label in (('catalog-total', 'All evaluator findings'), ('SECURITY', 'SECURITY subset (not additional findings)')):
        totals = static_totals(runs, scanner)
        lines.append(label + ': ' + ('totals withheld; no single snapshot per skill is established.' if totals is None else
            ' · '.join(f"{totals[level] if totals[level] is not None else 'unknown'} {level}" for level in SEVERITIES) +
            (f" ({sum(totals.values())} total)." if all(value is not None for value in totals.values()) else '.')))
    totals = static_totals(runs)
    detail = {level: sum(item['severity'] == level for run in runs for item in run['detailed_findings']) for level in SEVERITIES}
    if totals is not None and any(totals[level] is None or totals[level] > detail[level] for level in SEVERITIES):
        lines.append('Structured detail records: ' + ' · '.join(f'{detail[level]} {level}' for level in SEVERITIES) +
                     ('. Native totals are unavailable; details do not establish total findings.' if any(value is None for value in totals.values()) else
                      '. Some native findings have no structured public detail; inspect the original reports.'))
    security = [next((s['status'] for s in run['scans'] if s['scanner'] == 'SECURITY'), 'unavailable') for run in runs]
    lines.append('SECURITY coverage: ' + ' · '.join((
        f"{security.count('incomplete')} incomplete", f"{security.count('skipped')} skipped",
        f"{security.count('unavailable')} unavailable",
        f"{sum(s in ('passed', 'failed') for s in security)} with no incompleteness reported")) +
        '.')
    return lines


def render_static_summary(runs, *, heading='Static quality and coverage'):
    """Markdown over already validated static projections; no scanner prose or new findings."""
    lines = ['### ' + heading, '',
             'Scanner severity is not confirmed engineering significance. Findings remain advisory in quality CI.', '',
             *[part for line in static_overview(runs) for part in (line, '')],
             '#### Significant evaluator flags · applicability unresolved', '']
    if not runs or any(not any(s['scanner'] == 'SECURITY' and s['status'] in ('passed', 'failed') for s in run['scans']) for run in runs):
        lines[2:2] = ['**Security-analysis coverage is incomplete or unavailable.**', '']
    groups = static_groups(runs)
    if not groups:
        lines.append('No detailed critical/high flags supplied. Native counts and evidence gaps above remain authoritative.')
    for key, items in groups[:SIGNIFICANT_GROUP_LIMIT]:
        level, scanner, check, _ = key
        names = sorted({run['source']['skill_id'] for run, _ in items})
        skills = ', '.join(f'`{name}`' for name in names[:6]) + (f' (+{len(names) - 6} more)' if len(names) > 6 else '')
        run, item = items[0]
        lines.extend([f"- **{level.upper()} · `{scanner}` / `{check or 'rule-unavailable'}`** — {len(items)} " +
            ('finding' if len(items) == 1 else 'findings') + f"; skills: {skills}.",
            '  Next: ' + static_guidance(scanner, check), '',
            '<details><summary>Exact representative evidence</summary>', '',
            f"Skill `{run['source']['skill_id']}`; record `{run['record_id']}`; reference `{item['reference']}`.",
            '', '</details>', ''])
    omitted = groups[SIGNIFICANT_GROUP_LIMIT:]
    if omitted:
        lines.extend(['', 'Additional groups omitted from this preview: ' + '; '.join(
            f"{sum(key[0] == level for key, _ in omitted)} {level} groups / "
            f"{sum(len(items) for key, items in omitted if key[0] == level)} findings" for level in ('critical', 'high')) + '.'])
    lines.extend(['', 'Groups count retained finding records, not raw scanner occurrence spans. '
                  'Every individual finding remains in the detailed evidence; no false-positive classification is inferred.'])
    lines.extend(['', '<details><summary>Evidence limits · static interpretation</summary>', '', 'SECURITY denotes this pipeline\'s SkillSpector integration. Partial scans may retain valid findings; '
                  'zero findings and no incompleteness reported do not prove exhaustive inspection or behavioral benefit. '
                  'Detailed coverage reasons and separate scanner process outcomes are not retained by this native-report path.', '', '</details>'])
    return lines


@dataclass(frozen=True)
class ValidatedRecords:
    """Captured originals required for semantic validation; paths never serialize."""
    records: dict
    manifests: list
    roots: tuple = ()
    guards: tuple = ()


def measured(record):
    return record['kind'] == 'behavioral' and bool(record['metrics'] or record['observations'] or
        any((arm['coverage']['recorded_attempts'] or 0) > 0 for arm in record['arms']))


def check_records(records):
    """Revalidate each record and reconcile semantic claims without choosing a revision."""
    require(type(records) is dict, 'Invalid captured record index')
    names = set()
    claims = {}
    reports = 0
    for record_id, record in records.items():
        require(record_id == evidence.identity(record), 'Record semantic identity mismatch')
        if record.get('kind') == 'inventory':
            evidence.validate_inventory(record)
            names.update(row['source']['skill_id'] for row in record['skills'])
        else:
            evidence.validate_public(record)
            reports += 1
            name = record['source']['skill_id']
            names.add(name)
            if record['kind'] == 'behavioral':
                # Unmeasured configurations with no run are snapshots, not run claims.
                key = ('behavioral', name, record['run_id']) if measured(record) or record['run_id'] else None
            else:
                originals = {(ref['artifact_id'], ref['member']) for ref in record['references']
                             if ref['member'].startswith('reports/' + name + '/')}
                key = ('static', name, tuple(sorted(originals))) if originals else None
            if key is not None:
                require(key not in claims, 'Conflicting public report claims')
                claims[key] = record_id
        evidence.reports.public_strings(record)
    require(reports <= MAX_REPORTS, 'Analysis report limit')
    require(len(names) <= MAX_SKILLS, 'Analysis skill limit')


def check_capture(captured):
    require(type(captured) is ValidatedRecords, 'Captured public records required')
    check_records(captured.records)
    require(type(captured.manifests) is list and 0 < len(captured.manifests) <= MAX_INPUTS,
            'Analysis provenance manifest limit')
    manifest_ids = []; retained = set()
    for manifest in captured.manifests:
        evidence.closed(manifest, ('id', 'members'))
        evidence.sha(manifest['id'])
        entries = manifest['members']
        require(type(entries) is list and 0 < len(entries) <= MAX_REPORTS + 1, 'Analysis provenance member limit')
        names = []
        for entry in entries:
            evidence.closed(entry, ('member', 'raw_digest', 'record_id'))
            evidence.relative(entry['member']); evidence.sha(entry['raw_digest']); evidence.sha(entry['record_id'])
            require(entry['record_id'] in captured.records, 'Dangling provenance record')
            retained.add(entry['record_id']); names.append(entry['member'])
        require(names == sorted(set(names)), 'Ambiguous provenance members')
        require(manifest['id'] == evidence.identity(entries), 'Provenance manifest identity mismatch')
        manifest_ids.append(manifest['id'])
    require(manifest_ids == sorted(set(manifest_ids)), 'Ambiguous provenance manifests')
    require(retained == set(captured.records), 'Provenance record coverage mismatch')


def capture_inputs(paths):
    require(0 < len(paths) <= MAX_INPUTS, 'Analysis input root limit')
    directories = {}; states = {}; members = {}
    budget = evidence.ReadBudget()
    roots = tuple(sorted({evidence.safe_path(path, directory=True, directory_identities=directories)
                          for path in paths}))
    # Overlapping roots otherwise cause double capture and ambiguous relative manifests.
    require(not any(a != b and a.is_relative_to(b) for a in roots for b in roots),
            'Overlapping input roots')
    records = {}; manifests = {}
    scanned = 0
    observed_at = evidence.utc_now()
    for root in roots:
        files = evidence.safe_tree(root, max_entries=MAX_ENTRIES - scanned,
            directory_identities=directories, directory_states=states, file_states=members)
        scanned += len(files) + sum(path != root and path.is_relative_to(root) for path in states)
        require(scanned <= MAX_ENTRIES, 'Analysis aggregate entry limit')
        relative_files = {path.relative_to(root).as_posix(): path for path in files}
        flat = 'inventory.json' in relative_files
        inv_name = 'inventory.json' if flat else 'inventory/inventory.json'
        require(inv_name in relative_files, 'Public inventory required')
        entries = []
        bundle_records = []
        for member, path in sorted(relative_files.items()):
            evidence.relative(member)
            raw = evidence.read_bytes(path, budget=budget, directory_identities=directories,
                directory_states=states, file_states=members)
            record = evidence.parse_json(raw)
            if member == inv_name:
                evidence.validate_inventory(record)
            else:
                evidence.validate_evidence(record, public=True, _observed_at=observed_at)
                name = record['source']['skill_id']
                kind = record['kind']
                tail = 'static' if kind == 'static' else 'behavioral/' + str(record['run_id'])
                expected = 'public-report.json' if flat else f'skills/{name}/{tail}/public-report.json'
                require(member == expected, 'Unexpected public artifact member')
                if not flat and kind == 'behavioral':
                    require(record['run_id'] is not None, 'Artifact run identity required')
            evidence.reports.public_strings(record)
            record_id = evidence.identity(record)
            records.setdefault(record_id, record)
            bundle_records.append(record)
            entries.append({'member': member, 'raw_digest': evidence.digest_bytes(raw), 'record_id': record_id})
            require(sum(value['kind'] != 'inventory' for value in records.values()) <= MAX_REPORTS,
                    'Analysis report limit')
        inv = next(value for value in bundle_records if value['kind'] == 'inventory')
        names = {row['source']['skill_id'] for row in inv['skills']}
        require(all(value['kind'] == 'inventory' or value['source']['skill_id'] in names
                    for value in bundle_records), 'Report absent from accompanying inventory')
        # Reject unexpected empty directories as well as unexpected files.
        allowed_dirs = {root / Path(member).parent for member in relative_files}
        allowed_dirs |= {parent for path in allowed_dirs.copy() for parent in path.parents
                         if parent.is_relative_to(root)}
        require(all(path in allowed_dirs or path == root for path in states if path.is_relative_to(root)),
                'Unexpected public artifact directory')
        manifest = {'id': evidence.identity(entries), 'members': entries}
        manifests.setdefault(manifest['id'], manifest)
    guard = evidence.input_guard(directories, states, members, budget)
    guard()
    captured = ValidatedRecords(records, sorted(manifests.values(), key=lambda value: value['id']), roots, (guard,))
    check_capture(captured)
    return captured


def compact_source(source):
    return {**{key: copy.deepcopy(source[key]) for key in
               ('skill_id', 'owner', 'repository', 'revision', 'source_path', 'lineage')},
            'content_digest': source['content']['digest'],
            'content_provenance': source['content']['provenance']}


def compact_condition(condition):
    return {**{key: copy.deepcopy(value) for key, value in condition.items() if key != 'competing_skills'},
            'competing_skills': [compact_source(value) for value in condition['competing_skills']]}


def quantity(value):
    """Keep the direction before four-place display rounding (decimal arithmetic only)."""
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        context.rounding = ROUND_HALF_EVEN
        display = format(value, '.4f')
    return {'value': str(value), 'display': display,
            'direction': 'negative' if value < 0 else 'positive' if value > 0 else 'zero'}


def difference(right, left):
    if right is None or left is None:
        return None
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        context.rounding = ROUND_HALF_EVEN
        return quantity(Decimal(right['value']) - Decimal(left['value']))


def case_index(record):
    index = {case: {'with_skill': [], 'without_skill': []} for case in record['dataset']['case_ids']}
    for observation in record['observations']:
        index[observation['case_id']][observation['arm']].append(observation)
    for arms in index.values():
        for observations in arms.values():
            observations.sort(key=lambda obs: (obs['attempt'] or 0, obs['id']))
    return index


def analyze_cases(record, index):
    maximum = record['policy']['attempts']['maximum']
    stop = record['policy']['attempts']['stop_on_pass']
    rows = []
    for case, arms in sorted(index.items()):
        means = {}; links = {}; reasons = set()
        for arm, observations in arms.items():
            links[arm] = [obs['id'] for obs in observations]
            if maximum is None:
                reasons.add('attempt_maximum_unknown'); means[arm] = None
            elif maximum > 1 and stop is not False:
                reasons.add('adaptive_or_unknown_stopping'); means[arm] = None
            elif [obs['attempt'] for obs in observations] != list(range(1, maximum + 1)):
                reasons.add('planned_attempts_missing'); means[arm] = None
            elif any(obs['score'] is None for obs in observations):
                reasons.add('scores_missing'); means[arm] = None
            else:
                with localcontext() as context:
                    context.prec = DECIMAL_PRECISION
                    context.rounding = ROUND_HALF_EVEN
                    means[arm] = quantity(sum((Decimal(str(obs['score'])) for obs in observations), Decimal(0))
                                          / Decimal(maximum))
        rows.append({'case_id': case, 'arm_means': means, 'observation_ids': links,
                     'reference_ids': sorted({ref for observations in arms.values() for obs in observations
                                              for ref in obs['references']}),
                     'with_minus_without': difference(means['with_skill'], means['without_skill']),
                     'unavailable_reasons': sorted(reasons)})
    return rows


def complete_custom_population(record):
    maximum = record['policy']['attempts']['maximum']
    if record['custom']['agent_version'] is None: return False
    if maximum is None or record['policy']['attempts']['stop_on_pass'] is not False:
        return False
    for arms in case_index(record).values():
        for rows in arms.values():
            if [row['attempt'] for row in rows] != list(range(1, maximum + 1)):
                return False
            if any(row['custom']['outcome'] not in evidence.CUSTOM_MEASURED for row in rows):
                return False
    return bool(record['dataset']['case_ids']) and all(arm['execution_status'] == 'succeeded'
        and arm['coverage']['recorded_attempts'] == arm['coverage']['expected_attempts']
        and arm['coverage']['case_details'] == 'complete'
        and arm['execution_error_count'] == 0 for arm in record['arms'])


def analyze_custom(record):
    custom = record['custom']; maximum = record['policy']['attempts']['maximum']
    complete = complete_custom_population(record)
    rows = []; outcomes = {}
    for arm in ('with_skill', 'without_skill'):
        observed = [obs for obs in record['observations'] if obs['arm'] == arm]
        outcomes[arm] = {kind: sum(obs['custom']['outcome'] == kind for obs in observed) for kind in evidence.CUSTOM_OUTCOMES}
        outcomes[arm]['missing'] = len(record['dataset']['case_ids']) * maximum - len(observed)
    for definition in custom['definitions']:
        native = definition['native_name']
        populations = {}; means = {}
        applicable_cases = [case['case_id'] for case in custom['cases'] if native in case['metrics']]
        for arm in ('with_skill', 'without_skill'):
            observations = [obs for obs in record['observations'] if obs['arm'] == arm]
            measurements = [measurement for obs in observations for measurement in obs['custom']['measurements']
                            if measurement['metric_id'] == definition['id']]
            measured = [m for m in measurements if m['status'] == 'measured']
            expected = len(applicable_cases) * maximum
            populations[arm] = {'expected_applicable': expected, 'measured': len(measured),
                'unavailable_or_missing': expected - len(measured),
                'recorded_nonapplicable': sum(m['applicability'] == 'not_applicable' for m in measurements)}
            with localcontext() as ctx:
                ctx.prec = DECIMAL_PRECISION
                means[arm] = quantity(sum((Decimal(str(m['value'])) for m in measured), Decimal(0)) / Decimal(expected)) \
                    if complete and expected and len(measured) == expected else None
        # Activation and the conjunction are policy/routing evidence. Preserve
        # their numbers without translating their difference into task benefit.
        rows.append({'native_name': native, 'definition': copy.deepcopy(definition), 'coverage': populations,
            'arm_means': means, 'with_minus_without': difference(means['with_skill'], means['without_skill']),
            'interpretation': 'routing_or_gate_not_task_correctness' if definition['competency'] in ('activation_routing', 'fixture_gate')
                              else 'descriptive_reported_measurement_only',
            'unavailable_reason': None if complete and applicable_cases else 'not_applicable' if not applicable_cases else 'incomplete_required_population'})
    return {'purpose': custom['purpose'], 'agent': custom['agent'], 'outcomes': outcomes,
            'complete_paired_population': complete, 'metrics': rows,
            'assurance': {'structural_validation': 'passed', 'native_consistency': 'producer_reported_at_admission',
                          'native_revalidation_here': 'not_performed', 'producer_authentication': 'not_established',
                          'execution_authentication': 'not_established'},
            'cross_run_policy': 'disabled_pending_qualification', 'history_policy': 'custom_metrics_not_admitted'}


def behavioral_result(record_id, record, cases):
    observations = record['observations']
    gate_observations = observations
    if record['schema_version'] == 2:
        mandatory = any(definition['role'] == 'mandatory_with_skill_gate' for definition in record['custom']['definitions'])
        gate_observations = [obs for obs in observations if obs['arm'] == 'with_skill'] if mandatory else []
    failed = [{'observation_id': obs['id'], 'case_id': obs['case_id'], 'arm': obs['arm'],
               'components': sorted(key for key, value in obs['deterministic_scores'].items()
                                    if key != 'gate' and value == 0),
               'reference_ids': obs['references']} for obs in gate_observations if obs['deterministic_gate'] == 0]
    return {**({'custom': analyze_custom(record)} if record['schema_version'] == 2 else {}),
            'record_id': record_id, 'run_id': record['run_id'], 'measured': measured(record),
            'source': compact_source(record['source']),
            'dataset': {key: copy.deepcopy(value) for key, value in record['dataset'].items() if key != 'case_ids'},
            'policy': copy.deepcopy(record['policy']), 'native_metrics': copy.deepcopy(record['metrics']),
            'arms': [{**{key: copy.deepcopy(value) for key, value in arm.items() if key != 'condition'},
                      'condition': compact_condition(arm['condition'])} for arm in record['arms']],
            'availability': copy.deepcopy(record['availability']),
            'case_summary': {'matched_cases': sum(row['with_minus_without'] is not None for row in cases),
                             'cohort_cases': len(cases), 'scored_observations': sum(obs['score'] is not None for obs in observations),
                             'method': 'descriptive_arm_means_with_minus_without', 'cases': cases},
            'gates': {'failed': failed,
                      'passed_observations': sum(obs['deterministic_gate'] == 1 for obs in gate_observations),
                      'unknown_observations': sum(obs['deterministic_gate'] is None for obs in gate_observations)}}


def source_compatible(left, right):
    """A target revision may change. An ownership conversion needs exact recorded lineage."""
    def origin(source):
        if source['owner'] == 'unknown' or source['repository'] is None or source['source_path'] is None:
            return None
        return source['owner'], source['repository'], source['source_path']
    a, b = origin(left), origin(right)
    if a is None or b is None:
        return False
    if a == b:
        return True
    # Lineage names an exact origin revision; matching skill names cannot supply it.
    for converted, original in ((left, right), (right, left)):
        lineage = converted['lineage']
        if lineage is not None and original['revision'] is not None and lineage == {
                key: original[key] for key in ('repository', 'revision', 'source_path')}:
            return True
    return left['lineage'] is not None and left['lineage'] == right['lineage']


def condition_identity(record):
    """Index conditions once, using explicit default/custom applicability rules."""
    policy = record['policy']; fields = policy['fields']
    essential = {'run.identity_known': True if record['run_id'] is not None else None,
                 **{'dataset.' + key: record['dataset'][key] for key in
                    ('authored_digest', 'staged_digest', 'staged_algorithm', 'case_cohort_digest')},
                 'policy.patch_digest': policy['patch_digest'], 'policy.metric_set': policy['metric_set'],
                 **{'policy.' + key: fields[key] for key in ('evaluator_revision', 'grading', 'model', 'provider')},
                 **{'attempts.' + key: value for key, value in policy['attempts'].items()},
                 'judge.enabled': policy['judge']['enabled']}
    if policy['judge']['enabled'] is not False:
        essential.update({'judge.' + key: policy['judge'][key] for key in ('model', 'provider')})
    supplementary = {'dataset.owner': record['dataset']['owner']}
    default_fields = set(evidence.reports.POLICY) - {'evaluator_revision', 'grading', 'model', 'provider'}
    supplementary.update({'policy.' + key: fields[key] for key in sorted(default_fields)})
    supplementary['policy.workspace_mode'] = fields['workspace_mode']
    grading = fields['grading']
    custom_grading = grading != 'default' or record['source']['skill_id'] == 'gh'
    if custom_grading:
        # v1 has no dedicated custom-grader content identity. Never substitute a
        # grading label, patch hash or the target revision for that missing carrier.
        essential['custom_grader.identity'] = None
        supplementary.update({'policy.' + key: fields[key] for key in
                              ('deterministic_gate', 'fixture_boundary', 'authorization_policy',
                               'task_source', 'task_build', 'competing_revision')})
    else:
        # Default grading does not require gh-only carriers. If a producer
        # supplies additional benchmark conditions, still compare those claims.
        supplementary.update({'policy.' + key: fields[key] for key in
                              ('deterministic_gate', 'fixture_boundary', 'authorization_policy',
                               'task_source', 'task_build', 'competing_revision') if fields[key] is not None})
    for arm in record['arms']:
        condition = arm['condition']; prefix = arm['name'] + '.'
        for key in ('workspace_mode', 'instruction_digest', 'build_digest', 'fixture_digest'):
            supplementary[prefix + key] = condition[key]
        for key, value in condition['execution'].items():
            # Default staging does not apply gh's broker/authorization contract.
            if custom_grading or key in ('environment', 'base_image_mode') or value is not None:
                supplementary[prefix + key] = value
        supplementary[prefix + 'condition_identity_known'] = (
            True if condition['provenance'] != 'unknown' else None)
        supplementary[prefix + 'competitors'] = [compact_source(src) for src in condition['competing_skills']]
        # Null competitor identity is unknown, even if lists match.
        for src in condition['competing_skills']:
            supplementary[prefix + 'competitor.' + src['skill_id']] = (
                evidence.identity(src) if all(src[key] is not None for key in ('repository', 'revision', 'source_path'))
                and src['owner'] != 'unknown' and src['content']['digest'] is not None else None)
        supplementary[prefix + 'rubric_threshold'] = arm['rubric']['threshold']
    return essential, supplementary


def complete_numeric(record):
    if record['schema_version'] == 2 and record['policy']['fields']['grading'] == 'custom_only':
        return complete_custom_population(record)
    return bool(record['dataset']['case_ids']) and len(record['metrics']) == 4 and len(record['arms']) == 2 and all(
        obs['attempt'] is not None and obs['score'] is not None for obs in record['observations']) and all(
        arm['execution_status'] == 'succeeded' and arm['coverage']['case_details'] == 'complete'
        and arm['coverage']['expected_attempts'] is not None
        and arm['coverage']['scored_attempts'] == arm['coverage']['recorded_attempts'] == arm['coverage']['expected_attempts']
        for arm in record['arms'])


def classify(left, right, left_conditions, right_conditions):
    incompatible = []; exploratory = []
    if not source_compatible(left['source'], right['source']):
        incompatible.append('source_origin_or_lineage_unknown_or_conflicting')
    for group, a, b in zip(('essential', 'supplementary'), left_conditions, right_conditions):
        for key in sorted(set(a) | set(b)):
            x, y = a.get(key), b.get(key)
            unknown = x is None or y is None or x == 'unknown' or y == 'unknown'
            if unknown:
                (incompatible if group == 'essential' else exploratory).append('unknown:' + key)
            elif x != y:
                incompatible.append('changed:' + key)
    if not complete_numeric(left) or not complete_numeric(right):
        exploratory.append('incomplete_numeric_execution')
    if left['source']['content']['digest'] is None or right['source']['content']['digest'] is None:
        exploratory.append('target_content_unknown')
    classification = ('incompatible_or_unknown' if incompatible else 'exploratory' if exploratory
                      else 'directly_comparable')
    return classification, sorted(set(incompatible + exploratory))


def cross_run(left_id, right_id, records, results, conditions):
    left, right = records[left_id], records[right_id]
    classification, reasons = classify(left, right, conditions[left_id], conditions[right_id])
    if left['schema_version'] == 2 or right['schema_version'] == 2:
        classification, reasons = 'custom_comparison_deferred', ['custom_cross_run_not_qualified']
    direct = classification == 'directly_comparable'
    a = {row['case_id']: row for row in results[left_id]['case_summary']['cases']}
    b = {row['case_id']: row for row in results[right_id]['case_summary']['cases']}
    common = sorted(a.keys() & b.keys())
    require(len(common) <= evidence.MAX_CASES, 'Comparison case join limit')
    rows = []
    for case in common:
        rows.append({'case_id': case,
                     'left_arm_means': a[case]['arm_means'], 'right_arm_means': b[case]['arm_means'],
                     'left_observation_ids': a[case]['observation_ids'], 'right_observation_ids': b[case]['observation_ids'],
                     'right_minus_left': {arm: difference(b[case]['arm_means'][arm], a[case]['arm_means'][arm])
                                          if direct else None for arm in ('with_skill', 'without_skill')}})
    am = {row['name']: row['value'] for row in left['metrics']}
    bm = {row['name']: row['value'] for row in right['metrics']}
    names = () if (left['schema_version'] == 2 or right['schema_version'] == 2) and not am and not bm else evidence.reports.METRICS
    metrics = [{'name': name, 'left': am.get(name), 'right': bm.get(name),
                'right_minus_left': difference(quantity(Decimal(str(bm[name]))), quantity(Decimal(str(am[name]))))
                if direct and name in am and name in bm else None} for name in names]
    subject = {'left_record_id': left_id, 'right_record_id': right_id}
    return {'id': evidence.identity(subject), **subject, 'classification': classification, 'reasons': reasons,
            'scope': 'two_supplied_runs_right_minus_left_descriptive_only',
            'native_metrics': metrics, 'matched_case_ids': common, 'cases': rows}


def finding(kind, skill, records=(), cases=(), observations=(), references=(), *, observed,
            uncertainty, importance, next_step):
    value = {'kind': kind, 'skill': skill, 'record_ids': sorted(set(records)), 'case_ids': sorted(set(cases)),
             'observation_ids': sorted(set(observations)), 'reference_ids': sorted(set(references)),
             'observed': observed, 'uncertainty': uncertainty, 'importance': importance, 'next_step': next_step}
    return {'id': evidence.identity(value), **value}


def build_analysis(captured):
    """Pure bounded projection. Original records remain the authority for all claims."""
    records = captured.records
    configurations = {}; static = {}; behavioral = {}; conditions = {}; findings = []
    names = set()
    record_index = []
    for record_id, record in sorted(records.items()):
        inventory = record['kind'] == 'inventory'
        name = None if inventory else record['source']['skill_id']
        record_index.append({'id': record_id, 'kind': record['kind'], 'skill': name,
                             'run_id': None if inventory else record['run_id']})
        if inventory:
            for row in record['skills']:
                name = row['source']['skill_id']; names.add(name)
                suite = row['suite']
                context = {'id': evidence.identity(row), 'source': compact_source(row['source']),
                           'suite': None if suite is None else {**{key: value for key, value in suite.items()
                                                                 if key != 'case_ids'}, 'case_count': len(suite['case_ids'])},
                           'behavioral_status': row['behavioral_status'], 'inventory_record_ids': []}
                configs = configurations.setdefault(name, {})
                configs.setdefault(context['id'], context)['inventory_record_ids'].append(record_id)
            continue
        names.add(name)
        if record['kind'] == 'static':
            result = static_record(record_id, record)
            static.setdefault(name, []).append(result)
            incomplete = [scan for scan in record['scans'] if scan['status'] in ('incomplete', 'skipped')]
            if incomplete:
                findings.append(finding('incomplete_scans', name, [record_id],
                    references=[ref for scan in incomplete for ref in scan['references']],
                    observed={'scanners': [scan['scanner'] for scan in incomplete]}, uncertainty='scanner_coverage_incomplete',
                    importance='investigate', next_step='complete_scans_and_reproject'))
            failed = [scan for scan in record['scans'] if scan['scanner'] != 'catalog-total'
                      and scan.get('blocking', True) and scan['passed'] is False]
            if failed:
                findings.append(finding('failed_static_checks', name, [record_id],
                    references=[ref for scan in failed for ref in scan['references']],
                    observed={'scanners': [scan['scanner'] for scan in failed]}, uncertainty='recorded_static_outcome',
                    importance='mandatory', next_step='inspect_original_scanner_evidence'))
        else:
            cases = analyze_cases(record, case_index(record))
            if record['schema_version'] == 2 and record['policy']['fields']['grading'] == 'custom_only':
                for case in cases: case['unavailable_reasons'] = ['standard_judge_not_collected']
            conditions[record_id] = condition_identity(record)
            result = behavioral_result(record_id, record, cases)
            behavioral.setdefault(name, []).append(result)
            if record['schema_version'] == 2:
                for obs in record['observations']:
                    if obs['custom']['outcome'] in ('invalid', 'unsupported', 'timeout', 'infrastructure_error', 'interrupted', 'unknown'):
                        findings.append(finding('custom_unavailable', name, [record_id], [obs['case_id']], [obs['id']], obs['custom']['references'],
                            observed={'classification': obs['custom']['outcome']}, uncertainty='reported_unscoreable_outcome',
                            importance='investigate', next_step='inspect_original_case_evidence'))
                    failed_metrics = [m['metric_id'] for m in obs['custom']['measurements'] if m['status'] == 'measured' and m['value'] < 1
                        and next(d for d in record['custom']['definitions'] if d['id'] == m['metric_id'])['competency']
                        not in ('activation_routing', 'fixture_gate')]
                    if failed_metrics:
                        findings.append(finding('custom_measured_failure', name, [record_id], [obs['case_id']], [obs['id']], obs['custom']['references'],
                            observed={'metric_ids': failed_metrics, 'arm': obs['arm']}, uncertainty='reported_measurement_not_instruction_causality',
                            importance='investigate', next_step='inspect_original_case_evidence'))
            for row in cases:
                delta = row['with_minus_without']
                if delta is not None and delta['direction'] == 'negative':
                    findings.append(finding('case_regression', name, [record_id], [row['case_id']],
                        [obs for links in row['observation_ids'].values() for obs in links], row['reference_ids'],
                        observed={'with_minus_without': delta}, uncertainty='descriptive_only_no_trial_pairing',
                        importance='investigate', next_step='inspect_original_case_evidence'))
            for failure in result['gates']['failed']:
                findings.append(finding('failed_gate', name, [record_id], [failure['case_id']],
                    [failure['observation_id']], failure['reference_ids'], observed={'components': failure['components'], 'gate': 0},
                    uncertainty='recorded_deterministic_outcome', importance='mandatory', next_step='inspect_gate_evidence'))
            if record['availability']['status'] != 'unavailable' and not complete_numeric(record):
                findings.append(finding('incomplete_execution', name, [record_id],
                    observed={'arms': [{key: arm[key] for key in ('name', 'execution_status', 'coverage')}
                                       for arm in record['arms']]}, uncertainty='numeric_coverage_incomplete',
                    importance='investigate', next_step='complete_execution_and_reproject'))
        unavailable = [ref for ref in record['references'] if ref['availability'] != 'available']
        if unavailable or 'source_unavailable' in record['availability']['reasons']:
            findings.append(finding('unavailable_support', name, [record_id], references=[ref['id'] for ref in unavailable],
                observed={'unavailable_references': len(unavailable), 'source_content_known': record['source']['content']['digest'] is not None},
                uncertainty='original_support_unavailable', importance='context', next_step='retain_or_reacquire_exact_evidence'))
    by_id = {row['record_id']: row for values in behavioral.values() for row in values}
    eligible = {name: sorted(row['record_id'] for row in values if row['measured']) for name, values in behavioral.items()}
    pairs = sum(len(ids) == 2 for ids in eligible.values())
    global_limit = pairs > MAX_COMPARISONS
    if global_limit:
        findings.append(finding('comparison_limit', None, observed={'eligible_pairs': pairs, 'maximum': MAX_COMPARISONS},
            uncertainty='invocation_comparison_limit_exceeded', importance='context', next_step='supply_at_most_16_skill_pairs'))
    skills = []
    for name in sorted(names):
        ids = eligible.get(name, [])
        status = ('comparison_limit_exceeded' if len(ids) > 2 else 'insufficient_run_evidence' if len(ids) < 2
                  else 'invocation_comparison_limit_exceeded' if global_limit else 'compared')
        comparisons = []
        if status == 'compared':
            comparison = cross_run(*ids, records, by_id, conditions)
            comparisons.append(comparison)
            if comparison['classification'] != 'directly_comparable':
                findings.append(finding('comparison_limitation', name, ids,
                    observed={'classification': comparison['classification'], 'reasons': comparison['reasons']},
                    uncertainty='controlled_comparison_unsupported', importance='context', next_step='verify_benchmark_identities'))
            else:
                for metric in comparison['native_metrics']:
                    delta = metric['right_minus_left']
                    if delta is not None and delta['direction'] == 'negative':
                        findings.append(finding('run_metric_regression', name, ids,
                            observed={'metric': metric['name'], 'right_minus_left': delta},
                            uncertainty='descriptive_only_no_chronology', importance='investigate', next_step='inspect_original_run_evidence'))
                for case in comparison['cases']:
                    for arm, delta in case['right_minus_left'].items():
                        if delta is not None and delta['direction'] == 'negative':
                            findings.append(finding('run_case_regression', name, ids, [case['case_id']],
                                [obs for side in ('left_observation_ids', 'right_observation_ids') for obs in case[side][arm]],
                                observed={'arm': arm, 'right_minus_left': delta},
                                uncertainty='descriptive_only_no_chronology', importance='investigate', next_step='inspect_original_case_evidence'))
        else:
            findings.append(finding('comparison_limitation', name, ids,
                observed={'status': status, 'measured_runs': len(ids)}, uncertainty='supplied_inputs_only', importance='context',
                next_step='supply_two_intended_runs' if len(ids) != 2 else 'supply_at_most_16_skill_pairs'))
        configs = sorted(configurations.get(name, {}).values(), key=lambda row: row['id'])
        configured = [config for config in configs if config['suite'] is not None]
        if configured and not ids:
            findings.append(finding('configured_unmeasured', name,
                [record_id for config in configured for record_id in config['inventory_record_ids']],
                observed={'configured_case_counts': sorted({config['suite']['case_count'] for config in configured})},
                uncertainty='no_measurement_in_supplied_inputs', importance='context', next_step='supply_model_backed_public_report'))
        skills.append({'skill': name, 'configurations': configs, 'static_results': static.get(name, []),
                       'behavioral_results': behavioral.get(name, []), 'comparison_status': status,
                       'comparisons': comparisons})
    has_custom = any(record.get('schema_version') == 2 and record.get('kind') == 'behavioral' for record in records.values())
    return {'schema_version': 2 if has_custom else SCHEMA_VERSION,
            'method_version': 'bounded-descriptive-skill-analysis/2' if has_custom else METHOD,
            'input_provenance': copy.deepcopy(captured.manifests), 'record_index': record_index, 'skills': skills,
            'comparison_scope': {'eligible_pairs': pairs, 'maximum_pairs': MAX_COMPARISONS,
                                 'performed_pairs': 0 if global_limit else pairs,
                                 'limitations': ['supplied_inputs_only', 'no_chronology', 'no_causal_or_statistical_claims']},
            'findings': sorted(findings, key=lambda row: row['id'])}


def validate_analysis(result, validated_records):
    """Recompute from public originals; None constructs the authoritative validated projection.

    Construction inside this boundary lets the CLI calculate its bounded pairs
    once. A supplied saved result is always checked by independent recomputation.
    """
    check_capture(validated_records)
    expected = build_analysis(validated_records) if result is None else None
    if result is None:
        result = expected
    evidence.closed(result, ('schema_version', 'method_version', 'input_provenance', 'record_index',
                            'skills', 'comparison_scope', 'findings'))
    evidence.depth(result, 20)
    payload = evidence.encoded(result)
    require(len(payload) <= JSON_LIMIT, 'Analysis JSON size exceeded')
    if expected is None:
        expected = build_analysis(validated_records)
    # Canonical bytes also reject extra/missing fields at every nested level,
    # wrong native numeric types, links, quantities, gates and classifications.
    require(payload == evidence.encoded(expected), 'Analysis differs from captured public evidence')
    evidence.reports.public_strings(result)
    return result


def signed(quantity_value):
    return ('+' if quantity_value['direction'] == 'positive' else '') + quantity_value['display']


def render_summary(result):
    """Fixed templates over validated analysis; no raw prose, timestamps, or paths."""
    remaining_static_details = STATIC_DETAIL_PREVIEW_LIMIT
    findings = ordered_findings(result['findings'])
    runs = [run for skill in result['skills'] for run in skill['behavioral_results']]
    static_runs = [run for skill in result['skills'] for run in skill['static_results']]
    lines = ['# Offline skill analysis', '',
             'Descriptive evidence from supplied public bundles only. Static findings, mandatory gates and measurement coverage have separate scopes.', '',
             '| Evidence scope | Supplied status |', '| --- | --- |',
             f"| Skills | {len(result['skills'])} represented |",
             f"| Mandatory gates · recorded observations | {sum(len(r['gates']['failed']) for r in runs)} failed; "
             f"{sum(r['gates']['passed_observations'] for r in runs)} passed; {sum(r['gates']['unknown_observations'] for r in runs)} unknown |",
             f"| Static findings · advisory | {static_count_label(static_runs)} |",
             f"| Investigation records | {len(findings)} |",
             f"| Skills with measured results | {sum(any(r['measured'] for r in skill['behavioral_results']) for skill in result['skills'])} |", '',
             'Unknown gates are not passes. Missing execution coverage is excluded from recorded counts.', '',
             '## Review first', '',
             'Native required-check failures describe evaluator policy, not CI blockers.', '',
             f"{len(findings)} investigation records; showing {min(len(findings), FINDING_PREVIEW_LIMIT)}. "
             f"{max(0, len(findings) - FINDING_PREVIEW_LIMIT)} additional records in the complete list below.", '']
    for item in findings[:FINDING_PREVIEW_LIMIT]:
        lines.extend(render_finding(item))
    if not findings:
        lines += ['No deterministic investigation findings in the supplied evidence. This does not establish readiness.', '']
    lines += ['', '<details><summary>All deterministic investigations and exact evidence</summary>', '']
    for item in findings:
        lines.extend(render_finding(item, exact=True))
    lines += ['', '</details>', '']
    lines.extend(render_static_summary(static_runs) + [''])
    lines += ['## Skills and coverage', '']
    for skill in result['skills']:
        lines.extend([f"### `{skill['skill']}`", '', coverage_label(skill), '',
                      '<details><summary>Results and supporting evidence</summary>', ''])
        for config in skill['configurations']:
            count = config['suite']['case_count'] if config['suite'] else 0
            lines.append(f"Configuration `{config['id']}`: {count} configured cases; {config['behavioral_status']}.")
        if not any(run['measured'] for run in skill['behavioral_results']):
            lines.extend(['No supplied model-backed measurement.', ''])
        for run in skill['behavioral_results']:
            lines.extend([f"Run `{run['run_id']}`; evidence {run['availability']['status']}; "
                          f"limitations: {', '.join(run['availability']['reasons']) or 'none recorded'}.", '',
                          '<details><summary>Exact record identity</summary>', '', f"`{run['record_id']}`", '', '</details>', ''])
            if 'custom' in run:
                custom = run['custom']
                lines.append(f"- Purpose `{custom['purpose']}`; agent `{custom['agent']}`; complete paired population: {custom['complete_paired_population']}.")
                lines.append('- Structural validation passed; native consistency is producer reported at admission. Producer and execution authentication are not established.')
                lines += ['', '| Reported custom outcome | With skill | Without skill |', '| --- | --- | --- |']
                for kind in (*evidence.CUSTOM_OUTCOMES, 'missing'):
                    lines.append(f"| {kind} | {custom['outcomes']['with_skill'][kind]} | {custom['outcomes']['without_skill'][kind]} |")
                lines.append('')
                for metric in custom['metrics']:
                    definition = metric['definition']
                    lines.append(f"- **{definition['title']}** (`{definition['id']}`)")
                    for arm, coverage in metric['coverage'].items():
                        mean = metric['arm_means'][arm]
                        lines.append(f"  - `{arm}`: applicable {coverage['expected_applicable']}, measured {coverage['measured']}, unavailable/missing {coverage['unavailable_or_missing']}, recorded nonapplicable {coverage['recorded_nonapplicable']}; mean {mean['display'] if mean else 'unavailable'}.")
                    delta = metric['with_minus_without']
                    lines.append(f"  - With-minus-without: {signed(delta) if delta else 'unavailable'}; {metric['unavailable_reason'] or metric['interpretation']}.")
                    lines += ['', '<details><summary>Metric definition and interpretation</summary>', '',
                              f"{definition['definition']} Competency `{definition['competency']}`; unit `{definition['unit']}`. {metric['interpretation']}.",
                              '', '</details>', '']
                lines.append('- Activation and fixture-gate baseline zeros are routing/policy evidence, not worse task correctness. Oracle qualification is not a model-backed skill-benefit measurement.')
            for metric in run['native_metrics']:
                value = quantity(Decimal(str(metric['value'])))
                lines.append(f"- Native {metric['name']}: {signed(value) if metric['name'] == 'Skill Lift' else value['display']}.")
            cases = run['case_summary']
            lines.append(f"- {cases['matched_cases']} matched cases; {cases['scored_observations']} scored trials; {cases['cohort_cases']} cohort cases.")
            for arm in run['arms']:
                cov = arm['coverage']; rubric = arm['rubric']
                lines.append(f"- `{arm['name']}`: execution {arm['execution_status']}; rubric case passes "
                             f"{rubric['passed_cases']}/{rubric['total_cases']}; attempts expected/recorded/scored/unscored "
                             f"{cov['expected_attempts']}/{cov['recorded_attempts']}/{cov['scored_attempts']}/{cov['unscored_attempts']}.")
            gates = run['gates']
            lines.append(f"- Deterministic gates: {len(gates['failed'])} failed, {gates['passed_observations']} passed, {gates['unknown_observations']} unknown observations.")
            for gate in gates['failed']:
                lines.append(f"- **Mandatory gate failure**: case `{gate['case_id']}`, observation `{gate['observation_id']}`; components {', '.join(gate['components'])}.")
            for case in cases['cases']:
                delta = case['with_minus_without']
                if delta is not None and delta['direction'] == 'negative':
                    lines.append(f"- Case `{case['case_id']}` regression: {signed(delta)} with-minus-without (descriptive).")
            limitations = run['availability']['reasons']
            lines.extend([f"- Supporting evidence: {run['availability']['status']}; limitations: {', '.join(limitations) or 'none recorded'}.", ''])
        lines += ['', '<details><summary>All scanner outcomes and native counts</summary>', '']
        for static in skill['static_results']:
            lines.append(f"Static record `{static['record_id']}`; support {static['availability']['status']}.")
            for scan in static['scans']:
                counts = ', '.join(f"{key}={scan['severity_counts'][key]}" for key in ('critical', 'high', 'medium', 'low'))
                lines.append(f"- Scanner `{scan['scanner']}`: {scan['status']}; required by native evaluator {scan.get('blocking', True)}; counts {counts}.")
            lines.extend([f"- {len(static['detailed_findings'])} detailed findings retained separately; aggregate and scanner counts are not added.", ''])
            preview = static['detailed_findings'][:remaining_static_details]
            remaining_static_details -= len(preview)
            omitted = len(static['detailed_findings']) - len(preview)
            lines.extend([f"Detail preview: {len(preview)} shown; {omitted} omitted "
                          f"(at most {STATIC_DETAIL_PREVIEW_LIMIT} detail rows across this summary). "
                          "The complete list is in [analysis.json](analysis.json), "
                          "`skills[].static_results[].detailed_findings`, under the record identity above.", ''])
            for finding in preview:
                lines.append(f"- `{finding['scanner']}` / `{finding['check']}`: {finding['severity']}; reference `{finding['reference']}`.")
        lines += ['', '</details>', '', '<details><summary>Cross-run comparison status and evidence</summary>', '']
        lines.append(f"Cross-run comparison: {skill['comparison_status']}.")
        for comparison in skill['comparisons']:
            lines.extend([f"- `{comparison['classification']}`: left `{comparison['left_record_id']}`, right `{comparison['right_record_id']}`.",
                          f"- Reasons: {', '.join(comparison['reasons']) or 'recorded conditions match'}."])
            for metric in comparison['native_metrics']:
                delta = metric['right_minus_left']
                lines.append(f"- {metric['name']}: left {metric['left']}, right {metric['right']}; right-minus-left {signed(delta) if delta else 'unsupported'}.")
        lines += ['', '</details>', '', '</details>', '']
    lines += ['## Source details', '', '<details><summary>Evidence limits and measure interpretation</summary>', '',
              'No chronology, statistical significance, repeatability, causal inference, production readiness, or cross-suite rankings are established.',
              'Skill Lift is a native difference on the evaluator score scale. Effectiveness, Correctness and Discoverability are native rubric dimensions. '
              'Derived case means never reconstruct native lift.', '', '</details>']
    lines.extend(['', 'Independent semantic validation requires these exact public records. Expert investigation also',
                  'requires the appropriate original trial/scanner evidence and exact source content; unavailable',
                  'or expired references cannot supply discarded bytes. Reference expiry preserves completed scores.', ''])
    payload = '\n'.join(lines).encode('utf-8')
    require(len(payload) <= MARKDOWN_LIMIT, 'Analysis Markdown size exceeded')
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    captured = capture_inputs(args.input)
    result = validate_analysis(None, captured)
    markdown = render_summary(result)
    destination = evidence.write_outputs({'analysis.json': result}, args.output, input_paths=captured.roots,
                                         input_guards=captured.guards, rendered={'summary.md': markdown})
    print(destination)
    return destination


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, TypeError, KeyError, IndexError, OverflowError, RecursionError):
        print('Analysis contract rejected; no publication is ready.', file=sys.stderr)
        sys.exit(1)
