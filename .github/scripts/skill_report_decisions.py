#!/usr/bin/env python3
"""Open the consolidated report with evidence-backed reviewer decisions."""

import importlib.util
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
import skill_report as report
from quantity_replay_evidence import (
    CONTROL_OUTCOMES, PUBLICATION_MEMBER, boundary_verified, paired_outcome, submission_roster,
)

analysis = report.analysis
evidence = report.evidence
require = evidence.require
OVERVIEW_START = b'<section class="overview" aria-labelledby="overview">'
SUPPLEMENT_LIMIT = 64 * 1024
QUALIFICATION_VALIDATORS = {
    'pester-transfer-batch-v2': '.github/evals/pester-return-contract/grader-v2/verify_qualification.py',
}
DECISION_CSS = """
.review-decisions{margin:0 0 1.5rem}
.review-decisions>h2{margin:0 0 .75rem}
.decision-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,23rem),1fr));gap:1rem}
.decision-card{min-width:0;background:var(--surface);border:1px solid var(--line);border-radius:.4rem;
padding:.85rem 1rem}
.decision-card h3{margin:0;font-size:1.15rem}
.decision-card p{margin:.5rem 0;line-height:1.45}
.decision-card .table-scroll{margin:.6rem 0}
.decision-card th,.decision-card td{padding:.35rem .5rem}
.decision-card caption{margin-bottom:.25rem}
.decision-card .finding-result{font-variant-numeric:tabular-nums}
@media(min-width:50rem){header{display:grid;grid-template-columns:minmax(0,1fr) auto;
align-items:baseline;column-gap:1rem}
header .eyebrow{grid-column:1/-1;margin:.2rem 0}
.decision-cards:has(>.replay-card):has(>:nth-child(2):last-child){grid-template-columns:minmax(0,1.45fr) minmax(0,1fr)}}
""".strip()
GITHUB_EVIDENCE = re.compile(
    r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/'
    r'(?:blob/[0-9a-f]{40}/[A-Za-z0-9_./-]+(?:#L[0-9]+(?:-L[0-9]+)?)?'
    r'|actions/runs/[0-9]+(?:/artifacts/[0-9]+)?)'
)


def label(value):
    require(type(value) is str and 0 < len(value) <= 400 and value.isprintable() and value.strip() == value,
            'Invalid decision text')
    return report.safe(value)


def source_link(source):
    evidence.closed(source, ('label', 'url'))
    href = source['url']
    require(type(href) is str and len(href) <= 512 and GITHUB_EVIDENCE.fullmatch(href)
            and not {'..', '.'}.intersection(href.split('/')), 'Invalid decision evidence link')
    return f'<a href="{report.safe(href)}">{label(source["label"])}</a>'


def cited_text(item):
    evidence.closed(item, ('text', 'source'))
    return label(item['text']) + ' ' + source_link(item['source'])


def live_witness(record):
    witness = record.get('custom', {}).get('scheduler', {}).get('witness', {})
    return witness if witness.get('mode') == 'live' else {}


def public_pair(record, run, metric):
    """Select a binary endpoint from one admitted, complete live custom cohort."""
    require(record['kind'] == 'behavioral' and record['schema_version'] == 2, 'Custom behavioral record required')
    if metric is not None:
        require(any(d['id'] == metric for d in record['custom']['definitions']), 'Unknown decision metric')
    if live_witness(record).get('state') != 'completed' or not run['custom']['complete_paired_population']:
        return None
    values = {arm: [] for arm in report.ARM}
    for observation in record['observations']:
        custom = observation['custom']
        if metric is None:
            value = custom['outcome'] == 'passed'
        else:
            value = next((m['value'] for m in custom['measurements']
                          if m['metric_id'] == metric and m['status'] == 'measured'), None)
            if value not in (0, 1):
                return None
        values[observation['arm']].append(value)
    return [(sum(arm), len(arm)) for arm in values.values()]


def receipt_pair(receipt, metric):
    """Select a binary endpoint from a retained single-pair execution receipt."""
    verification = receipt.get('verification', {})
    if (verification.get('complete') is not True or verification.get('ledger_state') != 'completed'
            or verification.get('workflow_conclusion') != 'success'
            or verification.get('stop_reason', 'missing') is not None
            or verification.get('report_failure', 'missing') is not None
            or verification.get('verifier_reward_receipts') != 2):
        return None
    rows = verification.get('rows', [])
    if len(rows) != 2 or [row.get('variant') for row in rows] != ['current', 'absent']:
        return None
    values = []
    for row in rows:
        if (row.get('state') != 'completed' or type(row.get('returncode')) is not int or row['returncode'] != 0
                or row.get('grading_present') is not True or row.get('native_exception', 'missing') is not None
                or row.get('outcome', {}).get('classification') not in evidence.CUSTOM_MEASURED):
            return None
        value = row.get('custom_metrics', {}).get(metric)
        if type(value) not in (int, float) or value not in (0, 1):
            return None
        values.append((int(value), 1))
    return values


def recorded_pair_outcome(runs):
    if type(runs) is not dict:
        return 'unmeasured'
    outcome = paired_outcome(runs.get('reference'), runs.get('variation'))
    return outcome if outcome == runs.get('outcome') else 'unmeasured'


def replay_observations(spec, receipt, population):
    """Count only qualified observations and reconcile them with the planned cohort."""
    evidence.closed(spec, ('id', 'member', 'expected', 'controls', 'population', 'variation', 'gap', 'contract'))
    evidence.token(spec['id'])
    evidence.sha(spec['population'])
    publication_digest, roster = population
    expected = len(roster)
    require(spec['population'] == publication_digest and type(spec['expected']) is int
            and spec['expected'] == expected, 'Replay population binding mismatch')
    controls = spec['controls']
    require(controls == CONTROL_OUTCOMES, 'Invalid replay controls')

    counts = dict(accepted=0, rejected=0, unmeasured=expected)
    if receipt is None:
        return counts, 'Replay receipt missing.', {}, {}
    evidence.closed(receipt, ('schema_version', 'id', 'checks', 'observations', 'provenance'))
    provenance = receipt['provenance']
    require(type(receipt['schema_version']) is int and receipt['schema_version'] == 1
            and receipt['id'] == spec['id']
            and type(provenance) is dict
            and provenance.get('publication_sha256') == publication_digest, 'Replay identity mismatch')
    recorded_checks = {}
    for check in receipt['checks']:
        evidence.closed(check, ('id', 'expected', 'observed'))
        identity = check['id']
        require(identity in controls and identity not in recorded_checks and check['expected'] == controls[identity],
                'Replay controls disagree with the reviewed plan')
        evidence.enum(check['observed'], ('verified', 'accepted', 'rejected', 'unmeasured'))
        recorded_checks[identity] = check['observed']

    boundary = provenance.get('boundary')
    control_runs = provenance.get('control_runs')
    verified = type(boundary) is dict and boundary_verified(boundary.get('reference'), boundary.get('variation'))
    checks = {'return-boundary': 'verified' if verified else 'unmeasured'}
    for name in ('permissive-suite', 'restrictive-suite'):
        runs = control_runs.get(name) if type(control_runs) is dict else None
        checks[name] = recorded_pair_outcome(runs)
    for name, outcome in checks.items():
        if recorded_checks.get(name) != outcome:
            checks[name] = 'unmeasured'
    unqualified = [name for name, value in controls.items() if checks.get(name) != value]
    rows = receipt['observations']
    require(type(rows) is list and len(rows) <= expected, 'Unexpected replay population')
    submitted = {}
    for row in rows:
        identity = row['id']
        evidence.token(identity)
        evidence.sha(row['sha256'])
        require(identity not in submitted, 'Duplicate replay observation')
        evidence.enum(row['outcome'], counts)
        submitted[identity] = row
    observations = {}
    for identity, (_, _, arm, digest) in roster.items():
        row = submitted.get(identity)
        matches = row is not None and (row.get('arm'), row['sha256']) == (arm, digest)
        outcome = recorded_pair_outcome(row) if matches and not unqualified else 'unmeasured'
        observations[identity] = outcome
        if outcome != 'unmeasured':
            counts[outcome] += 1
            counts['unmeasured'] -= 1
    unresolved = None
    if unqualified:
        unresolved = 'Unqualified controls: ' + ', '.join(unqualified) + '.'
    elif counts['unmeasured']:
        unresolved = 'A qualified result is missing for ' + report.count(counts['unmeasured'], 'saved submission') + '.'
    elif counts['accepted'] and counts['rejected']:
        unresolved = 'The saved suites gave mixed results.'
    return counts, unresolved, checks, observations


def replay_finding(spec, receipt, admitted, *, coverage_verified=False):
    counts, unresolved, checks, outcomes = admitted
    coverage_verified = coverage_verified and not unresolved and bool(counts['rejected'])
    variation = label(spec['variation'])
    if unresolved:
        heading = 'Unresolved · Neither yet'
        finding = report.safe(unresolved)
        action = ('Inspect the acceptance and rejection split before changing coverage.'
                  if not counts['unmeasured'] else 'Complete the missing replay evidence before changing coverage.')
        change = 'A qualified result for every saved submission with consistent outcomes would resolve the finding.'
    elif counts['rejected']:
        heading = ('Historical finding · Valid output rejected' if coverage_verified
                   else 'Confirmed · Evaluator coverage gap')
        finding = 'The saved suites rejected a valid ' + variation + '. ' + label(spec['gap'])
        action = 'Add a ' + variation + ' to the evaluator’s valid-reference coverage.'
        change = 'If a qualified reproduction accepts the variant across the saved set, retire this finding.'
    else:
        heading = 'Disproved · Neither'
        finding = 'The saved suites accepted the valid ' + variation + '.'
        action = 'Retire this finding.'
        change = 'A reproducible rejection with qualifying controls would reopen the finding.'
    count_line = ' · '.join(f'{count} {status}' for status, count in counts.items())
    parts = ['<p class="lead"><strong>' + heading + '</strong></p><p>' + finding + '</p>',
             '<p class="finding-result"><strong>' + count_line + '</strong></p>']
    if not coverage_verified:
        parts.extend(['<p><strong>Next step</strong> · ' + action + '</p>',
                      '<p><strong>What would change it</strong> · ' + change + '</p>'])
    if receipt is not None:
        target = report.anchor('replay', spec['id'])
        controls = [[label(name), label(spec['controls'][name]), label(outcome)] for name, outcome in checks.items()]
        observations = [[label(identity), label(outcome)] for identity, outcome in outcomes.items()]
        parts.append(f'<p><a href="#{target}">Replay evidence</a> · ' + source_link(spec['contract']) + '</p>'
                     f'<details><summary>Replay controls, runs and provenance</summary><div id="{target}">' +
                     report.table('Diagnostic controls', ('Control', 'Expected', 'Observed'), controls) +
                     report.table('Replay observation outcomes', ('Submission', 'Outcome'), observations) +
                     report.disclosure('Exact replay receipt', receipt) + '</div></details>')
    return ''.join(parts)


def qualification_status(spec, receipt, replay_pair, *, replay_complete):
    """Render the task-owned verifier's admission of the native evidence."""
    evidence.closed(spec, ('id', 'member'))
    version = spec['id']
    require(version in QUALIFICATION_VALIDATORS, 'Unknown qualification evidence contract')
    if receipt is None or replay_pair is None:
        return False, '<p><strong>Evaluator status</strong> · Qualification receipt or historical replay missing.</p>'
    replay, replay_digest = replay_pair
    evidence.closed(receipt, ('schema_version', 'id', 'historical_replay', 'member_digests',
                              'provenance', 'controls', 'observations'))
    require(type(receipt['schema_version']) is int and receipt['schema_version'] == 1
            and receipt['id'] == version, 'Qualification identity mismatch')
    if receipt['historical_replay'] != replay_digest:
        return False, '<p><strong>Evaluator status</strong> · Qualification covers a different replay.</p>'

    if not replay_complete:
        return False, '<p><strong>Evaluator status</strong> · Historical replay qualification incomplete.</p>'

    validator_spec = importlib.util.spec_from_file_location(
        '_task_qualification', evidence.ROOT / QUALIFICATION_VALIDATORS[version])
    validator = importlib.util.module_from_spec(validator_spec)
    validator_spec.loader.exec_module(validator)
    observed = validator.verify(receipt, replay)
    verified = observed['verified']
    state = 'Coverage added and verified' if verified else 'Coverage qualification incomplete'
    parts = ['<p class="lead"><strong>Evaluator status · ' + state + '</strong> · ' + label(version) + '</p>',
             '<p class="finding-result">Native regrade · ' +
             ' · '.join(f'{count} {name}' for name, count in observed['counts'].items()) + '</p>',
             '<p>This regrade measures evaluator behavior on saved submissions.</p>']
    target = report.anchor('qualification', version)
    controls = [[label(name), label(status), 'Met' if passed else 'Unqualified']
                for name, status, passed in observed['controls']]
    parts.append(f'<p><a href="#{target}">Native qualification evidence</a></p>'
                 f'<details><summary>Native controls, grades and provenance</summary><div id="{target}">' +
                 report.table('Native controls', ('Control', 'Grade', 'Expected behavior'), controls) +
                 report.disclosure('Exact native qualification receipt', receipt) + '</div></details>')
    return verified, ''.join(parts)


def observation_card(card, receipt, workspace):
    """Admit the retained evidence for one human-reviewed, ungraded observation."""
    evidence.closed(card, ('skill', 'case', 'decision', 'attribution', 'notes', 'logs', 'reconsider', 'observation'))
    evidence.skill_id(card['skill'])
    evidence.token(card['case'])
    decision = label(card['decision'])
    expected = card['observation']['changed_paths']
    require(type(expected) is int and expected >= 0, 'Invalid reviewed workspace change count')
    require(type(card['notes']) is list and len(card['notes']) <= 4, 'Decision notes')
    require(type(card['logs']) is list and 0 < len(card['logs']) <= 4, 'Decision log links')
    links = ' · '.join(source_link(item) for item in [card['attribution'], *card['logs']])
    history = ''.join('<p>' + cited_text(note) + '</p>' for note in card['notes'])
    reconsider = cited_text(card['reconsider'])
    runtime_label = ''
    if receipt is not None:
        evidence.closed(receipt, ('schema_version', 'source', 'runtime', 'observation', 'answer', 'trace'))
        require(type(receipt['schema_version']) is int and receipt['schema_version'] == 1, 'Observation schema')
        source = receipt['source']
        evidence.closed(source, ('run_id', 'revision', 'artifact_id', 'artifact_sha256'))
        evidence.revision(source['revision'])
        evidence.sha(source['artifact_sha256'])
        require(all(type(source[key]) is int and source[key] > 0 for key in ('run_id', 'artifact_id')),
                'Invalid observation source')
        require(card['attribution']['url'].endswith(f"/actions/runs/{source['run_id']}/artifacts/{source['artifact_id']}"),
                'Observation artifact link mismatch')
        recorded = receipt['observation']
        evidence.closed(recorded, ('skill', 'case', 'arm', 'execution', 'quality', 'evidence', 'cleanup', 'model_judge_calls'))
        require((recorded['skill'], recorded['case'], recorded['arm']) == (card['skill'], card['case'], 'current')
                and recorded['quality'] == 'ungraded', 'Observation skill, case or grading mismatch')
        runtime = receipt['runtime']
        evidence.closed(runtime, ('agent', 'cli', 'model', 'reasoning_effort'))
        runtime_label = label(runtime['agent']) + ' ' + ' / '.join(
            label(runtime[key]) for key in ('cli', 'model', 'reasoning_effort'))
        answer, trace = receipt['answer'], receipt['trace']
        evidence.closed(trace, ('source_sha256', 'terminal_event', 'final_message_sha256', 'actions'))
        evidence.sha(trace['source_sha256'])
        evidence.sha(trace['final_message_sha256'])
        require(type(trace['actions']) is list and all(type(action) is dict and action for action in trace['actions']),
                'Invalid retained action trace')
        complete = (recorded['execution'] == 'completed' and recorded['evidence'] == 'complete'
                    and recorded['cleanup'] is True and type(recorded['model_judge_calls']) is int
                    and recorded['model_judge_calls'] == 0 and type(answer) is str and bool(answer.strip())
                    and evidence.digest_bytes(answer.encode('utf-8')) == trace['final_message_sha256']
                    and trace['terminal_event'] == 'turn.completed')
    else:
        complete = False

    changes = None
    if workspace is not None and workspace.get('status') == 'complete':
        evidence.closed(workspace, ('status', 'root', 'changes', 'baseline_input_files', 'baseline_sha256'))
        evidence.sha('sha256:' + workspace['baseline_sha256'])
        changes = workspace['changes']
        require(type(changes) is list and all(type(change) is dict for change in changes), 'Invalid workspace changes')
    workspace_reviewed = changes is not None and len(changes) == expected
    complete = complete and workspace_reviewed
    heading = '<h3>' + label(card['skill']) + '</h3><p class="muted">Case ' + report.code(card['case']) + '</p>'
    if complete:
        finding = ('<p class="lead"><strong>' + decision + '</strong></p>'
                   '<p>One human-reviewed, current-skill observation · ' + runtime_label + '. Skill benefit remains unmeasured.</p>')
    else:
        missing = ('Completed workspace comparison unavailable for this decision.' if not workspace_reviewed
                   else 'Retained final answer or completed action trace unavailable.')
        finding = '<p class="lead"><strong>Decision pending complete evidence</strong></p><p>' + missing + '</p>'
    details = report.disclosure('Retained answer, action trace and workspace evidence',
                                {'receipt': receipt, 'workspace': workspace}) if receipt or workspace else ''
    reopen = '<p>' + reconsider + '</p>' if complete else ''
    return ('<article class="decision-card">' + heading + finding + reopen + '<p>' + links + '</p>' + details +
            ('<details><summary>Historical context</summary>' + history + '</details>' if history else '') + '</article>')


def bound_observation_member(base, binding, read):
    evidence.closed(binding, ('member', 'sha256'))
    evidence.relative(binding['member'])
    evidence.sha(binding['sha256'])
    path = base / binding['member']
    if not path.exists():
        return None
    raw = read(path, SUPPLEMENT_LIMIT)
    require(evidence.digest_bytes(raw) == binding['sha256'], 'Observation member digest mismatch')
    value = evidence.parse_json(raw, limit=SUPPLEMENT_LIMIT)
    require(type(value) is dict, 'Invalid observation member')
    evidence.reports.public_strings(value)
    return value


def decision_section(manifest, result, records, receipts, replays, population, qualifications, observations):
    evidence.closed(manifest, ('schema_version', 'receipts', 'decisions'))
    require(type(manifest['schema_version']) is int and manifest['schema_version'] == 1, 'Decision schema')
    cards = manifest['decisions']
    require(type(cards) is list and 0 < len(cards) <= 16, 'Decision count')
    runs = {run['record_id']: run for skill in result['skills'] for run in skill['behavioral_results']}
    summaries = {}
    parts = ['<section class="review-decisions" aria-labelledby="review-decisions">'
             '<h2 id="review-decisions">Skill improvement findings</h2><div class="decision-cards">']
    for card in cards:
        if 'observation' in card:
            parts.append(observation_card(card, *observations[card['skill'], card['case']]))
            continue
        extra = ('replay',) if 'replay' in card else ('next', 'reconsider')
        if 'qualification' in card:
            require('replay' in card, 'Qualification requires a historical replay')
            extra += ('qualification',)
        evidence.closed(card, ('skill', 'case', 'decision', 'attribution', 'caption', 'rows', 'notes', 'logs') + extra)
        evidence.skill_id(card['skill'])
        evidence.token(card['case'])
        heading = '<h3>' + label(card['skill']) + '</h3>'
        attribution = source_link(card['attribution'])
        decision = label(card['decision'])
        require(type(card['notes']) is list and len(card['notes']) <= 4, 'Decision notes')
        notes = [cited_text(note) for note in card['notes']]
        replay = card.get('replay')
        require(type(card['logs']) is list and 0 < len(card['logs']) <= 4, 'Decision log links')
        logs = ' · '.join(source_link(log) for log in card['logs'])
        require(type(card['rows']) is list and 0 < len(card['rows']) <= 8, 'Decision row count')
        rows = []
        complete = True
        for row in card['rows']:
            evidence.closed(row, ('label', 'source', 'metric'))
            sid = row['source']
            evidence.sha(sid)
            evidence.optional(row['metric'], evidence.token)
            label(row['label'])
            if sid in receipts:
                receipt, binding = receipts[sid]
                require((binding['skill'], binding['case']) == (card['skill'], card['case']),
                        'Decision receipt skill or case mismatch')
                cells = receipt_pair(receipt, row['metric'])
                support = source_link({'label': row['label'], 'url': binding['scoring']})
            else:
                require(sid in runs, 'Decision source missing from report')
                record = records[sid]
                require(record['source']['skill_id'] == card['skill'] and record['dataset']['case_ids'] == [card['case']],
                        'Decision source skill or case mismatch')
                cells = public_pair(record, runs[sid], row['metric'])
                support = report.link('record', (sid,), row['label'])
            if cells is None:
                complete = False
                rows.append([support, 'Unknown', 'Unknown'])
            else:
                rows.append([support, *(report.outcome(passed) if total == 1 else f'{passed}/{total}'
                                        for passed, total in cells)])
        summaries[card['skill']] = card['caption'] if complete else 'Incomplete matched evidence'
        display_decision = decision if complete else 'Decision pending complete evidence'
        scores = report.table(card['caption'], ('Result', 'With skill', 'Matched absent'), rows)
        if replay is not None:
            historical = replays.get(replay['id'])
            historical_receipt = historical[0] if historical else None
            admitted = replay_observations(replay, historical_receipt, population)
            verified, qualification_html = False, ''
            if 'qualification' in card:
                qualification = card['qualification']
                verified, qualification_html = qualification_status(
                    qualification, qualifications.get(qualification['id']), historical,
                    replay_complete=admitted[0]['unmeasured'] == 0)
            parts.append('<article class="decision-card replay-card">' + heading +
                         replay_finding(replay, historical_receipt, admitted, coverage_verified=verified) +
                         qualification_html +
                         '<p><strong>Transfer decision</strong> · ' + display_decision + ' ' + attribution + '</p>' +
                         '<details><summary>Frozen transfer checks and logs</summary>' + scores +
                         ''.join('<p>' + note + '</p>' for note in notes) + '<p>' + logs + '</p></details>')
        else:
            parts.append('<article class="decision-card">' + heading + '<p class="muted">' +
                         report.code(card['case']) + ' · ' + attribution + '</p><p class="lead"><strong>' +
                         display_decision + '</strong></p>' + scores)
            if complete:
                parts.extend('<p>' + note + '</p>' for note in notes)
                parts.append('<p><strong>Next step</strong> · ' + cited_text(card['next']) + '</p>' +
                             '<p><strong>What would change it</strong> · ' + cited_text(card['reconsider']) + '</p>')
            parts.append('<p>' + logs + '</p>')
        parts.append('</article>')
    parts.append('</div></section>')
    return ''.join(parts).encode('utf-8'), summaries


def replace_once(page, original, replacement):
    require(page.count(original) == 1, 'Consolidated report template changed')
    return page.replace(original, replacement, 1)


def scope_coverage(page, result, records, summaries):
    # The frozen analysis retains standard-score eligibility and original findings.
    # Matched custom evidence has its own decision criteria in this presentation.
    context_only = {'supply_two_intended_runs', 'supply_model_backed_public_report'}
    view = {**result, 'findings': [f for f in result['findings']
                                 if f['skill'] not in summaries or f['next_step'] not in context_only]}
    summary = report.executive_summary(view, records)
    start = summary.index('</p>') + len('</p>')
    summary = ('<p class="lead">Matched results, diagnostic replays and human-reviewed observations appear above in their own units. '
               'Configured coverage and standard-score comparisons are shown below.</p>' + summary[start:])
    summary = replace_once(summary, 'Mandatory gates · Among recorded observations:',
                           'Mandatory gates in analyzed bundles · Recorded observations:')
    summary = summary.replace('No recorded gate outcomes supplied.',
                              'No gate observations in the analyzed bundles. Attached receipts appear in their case cards.')
    page = replace_once(page, report.executive_summary(result, records).encode(), summary.encode())
    review = report.review_first(view, records, {})
    for skill in result['skills']:
        name = skill['skill']
        if name not in summaries:
            continue
        coverage = report.safe(report.coverage_label(skill))
        scoped = label(summaries[name])
        cell = report.link('skill', (name,), name) + '</th><td>'
        review = replace_once(review, cell + coverage, cell + scoped)
        marker = f'<section class="skill" id="{report.anchor("skill", name)}">'.encode()
        start = page.index(marker)
        end = page.index(b'</section>', start)
        details = page[start:end].decode()
        details = replace_once(details, '<p>' + coverage + '</p>', '<p>' + scoped + '</p>')
        details = details.replace(
            '<p class="notice"><strong>Unmeasured.</strong> No supplied model-backed measurement. '
            'Configuration and offline fixture replay do not establish skill benefit or harm.</p>', '')
        if not skill['comparisons']:
            details = details.replace(report.comparisons(skill),
                '<h3>Cross-run comparisons</h3><p>Standard-score comparison unavailable for these inputs. '
                'See the matched-case outcomes above.</p>')
        page = page[:start] + details.encode() + page[end:]
    return replace_once(page, report.review_first(result, records, {}).encode(), review.encode())


def add_decisions(page, section, result, records, summaries):
    css = report.CSS + '\n' + DECISION_CSS
    page = replace_once(page, report.asset_hash(report.CSS).encode(), report.asset_hash(css).encode())
    page = replace_once(page, ('<style>' + report.CSS + '</style>').encode(), ('<style>' + css + '</style>').encode())
    # The base overview uses producer-profile presence for its synthetic banner.
    # A live scheduler witness can coexist with that diagnostic producer label.
    flagged = {rid: r for rid, r in records.items() if r['kind'] == 'behavioral'
               and 'producer_profile' in r['policy'] and not analysis.pilot_record(r)}
    live_custom = {rid for rid, r in flagged.items()
                   if live_witness(r) and r['policy']['fields']['grading'] == 'custom_only'}
    if live_custom and live_custom == flagged.keys():
        page, count = re.subn(rb'<p class="safety"><strong>Synthetic candidate qualification\.</strong>[^<]*</p>',
            b'<p class="notice">Live diagnostic records retain custom outcomes. '
            b'The overview below counts standard measurements.</p>', page)
        require(count == 1, 'Consolidated report diagnostic notice changed')
    for rid in sorted(live_custom):
        marker = f'<article class="run" id="{report.anchor("record", rid)}">'.encode()
        start = page.index(marker)
        end = page.index(b'</article>', start)
        run = page[start:end]
        run, count = re.subn(rb'<p class="safety"><strong>Synthetic candidate qualification;.*?</p>',
            b'<p class="notice">Live Codex execution with custom grading. Standard judge scores are unavailable.</p>', run)
        require(count == 1, 'Consolidated report run notice changed')
        run = run.replace(b'Measurement: <strong>Unmeasured', b'Standard scoring: <strong>Unavailable')
        run = run.replace(b'Raw upstream standard values \xc2\xb7 synthetic transport only',
                          b'Raw upstream standard values \xc2\xb7 custom-only mode')
        page = page[:start] + run + page[end:]
    page = scope_coverage(page, result, records, summaries)
    return replace_once(page, OVERVIEW_START, section + OVERVIEW_START)


def generate(inputs, saved_analysis, decisions_path, output=None, *, replay_paths=()):
    captured = analysis.capture_inputs(inputs)
    directories = {}; states = {}; members = {}
    budget = evidence.ReadBudget()

    def read(path, limit):
        path = evidence.safe_path(path, directory_identities=directories)
        return evidence.read_bytes(path, limit=limit, budget=budget, directory_identities=directories,
                                   directory_states=states, file_states=members)

    result = evidence.parse_json(read(saved_analysis, analysis.JSON_LIMIT), limit=analysis.JSON_LIMIT)
    manifest = evidence.parse_json(read(decisions_path, SUPPLEMENT_LIMIT), limit=SUPPLEMENT_LIMIT)
    evidence.reports.public_strings(manifest)
    registrations = manifest['receipts']
    require(type(registrations) is list and len(registrations) <= 8, 'Decision receipt count')
    receipts = {}
    for item in registrations:
        evidence.closed(item, ('member', 'sha256', 'skill', 'case', 'scoring'))
        evidence.relative(item['member'])
        raw = read(decisions_path.parent / item['member'], SUPPLEMENT_LIMIT)
        digest = evidence.digest_bytes(raw)
        require(digest == item['sha256'] and digest not in receipts, 'Decision receipt identity mismatch')
        receipts[digest] = (evidence.parse_json(raw, limit=SUPPLEMENT_LIMIT), item)
    bindings = [card['replay'] for card in manifest['decisions'] if 'replay' in card]
    population = None
    if bindings:
        raw = read(evidence.ROOT / PUBLICATION_MEMBER, SUPPLEMENT_LIMIT)
        population = (evidence.digest_bytes(raw), submission_roster(evidence.parse_json(raw, limit=SUPPLEMENT_LIMIT)))
    replays = {}
    for path in replay_paths:
        raw = read(path, SUPPLEMENT_LIMIT)
        receipt = evidence.parse_json(raw, limit=SUPPLEMENT_LIMIT)
        identity = receipt['id']
        require(identity not in replays and any(b['id'] == identity for b in bindings), 'Unknown or duplicate replay')
        evidence.reports.public_strings(receipt)
        replays[identity] = receipt, evidence.digest_bytes(raw)
    for binding in bindings:
        evidence.relative(binding['member'])
        path = decisions_path.parent / binding['member']
        if binding['id'] not in replays and path.exists():
            raw = read(path, SUPPLEMENT_LIMIT)
            receipt = evidence.parse_json(raw, limit=SUPPLEMENT_LIMIT)
            evidence.reports.public_strings(receipt)
            replays[binding['id']] = receipt, evidence.digest_bytes(raw)
    qualifications = {}
    for card in manifest['decisions']:
        if 'qualification' not in card:
            continue
        binding = card['qualification']
        evidence.relative(binding['member'])
        path = decisions_path.parent / binding['member']
        if path.exists():
            receipt = evidence.parse_json(read(path, SUPPLEMENT_LIMIT), limit=SUPPLEMENT_LIMIT)
            evidence.reports.public_strings(receipt)
            qualifications[binding['id']] = receipt
    observations = {}
    for card in manifest['decisions']:
        if 'observation' not in card:
            continue
        spec = card['observation']
        evidence.closed(spec, ('receipt', 'workspace', 'changed_paths'))
        key = card['skill'], card['case']
        require(key not in observations, 'Duplicate observation decision')
        observations[key] = tuple(bound_observation_member(decisions_path.parent, spec[role], read)
                                  for role in ('receipt', 'workspace'))
    guard = evidence.input_guard(directories, states, members, budget)
    guard()

    page = report.render_report(result, captured)
    section, summaries = decision_section(
        manifest, result, captured.records, receipts, replays, population, qualifications, observations)
    page = add_decisions(page, section, result, captured.records, summaries)
    require(len(page) <= report.HTML_LIMIT, 'HTML report size exceeded')
    return evidence.write_outputs({}, output, input_paths=(*captured.roots, saved_analysis.parent, decisions_path.parent,
                                                          *(path.parent for path in replay_paths)),
                                  input_guards=(*captured.guards, guard, lambda: analysis.check_capture(captured)),
                                  rendered={'report.html': page})


def main(argv=None):
    parser = report.PrivateParser(description=__doc__)
    parser.add_argument('--input', type=Path, action='append', required=True, help='Validated public bundle, repeatable')
    parser.add_argument('--analysis', type=Path, required=True, help='Saved analysis.json for exactly these bundles')
    parser.add_argument('--decisions', type=Path, required=True, help='Reviewer decisions and source bindings')
    parser.add_argument('--replay', type=Path, action='append', default=[], help='Replacement diagnostic receipt, repeatable')
    parser.add_argument('--output', type=Path, help='New private directory outside checkout and inputs')
    args = parser.parse_args(argv)
    try:
        print(generate(args.input, args.analysis, args.decisions, args.output, replay_paths=args.replay))
    except (*report.CONTRACT_ERRORS, AttributeError):
        parser.exit(1, 'Decision report inputs rejected. No HTML report is ready.\n')


if __name__ == '__main__':
    main()
