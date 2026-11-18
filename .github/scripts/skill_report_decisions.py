#!/usr/bin/env python3
"""Open the consolidated report with evidence-backed reviewer decisions."""

from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
import skill_report as report

analysis = report.analysis
evidence = report.evidence
require = evidence.require
OVERVIEW_START = b'<section class="overview" aria-labelledby="overview">'
SUPPLEMENT_LIMIT = 64 * 1024
DECISION_CSS = """
.review-decisions{margin:0 0 1.5rem}
.review-decisions>h2{margin:0 0 .75rem}
.decision-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,26rem),1fr));gap:1rem}
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


def replay_observations(spec, receipt):
    """Count only qualified observations and reconcile them with the planned cohort."""
    evidence.closed(spec, ('id', 'member', 'expected', 'controls', 'population', 'variation', 'gap', 'contract'))
    evidence.token(spec['id'])
    evidence.sha(spec['population'])
    expected = spec['expected']
    require(type(expected) is int and 0 < expected <= 256, 'Invalid replay population')
    controls = spec['controls']
    require(type(controls) is dict and 0 < len(controls) <= 16, 'Invalid replay controls')
    for control, outcome in controls.items():
        evidence.token(control)
        evidence.enum(outcome, ('verified', 'accepted', 'rejected'))

    counts = dict(accepted=0, rejected=0, unmeasured=expected)
    if receipt is None:
        return counts, 'Replay receipt missing.'
    evidence.closed(receipt, ('schema_version', 'id', 'checks', 'observations', 'provenance'))
    require(type(receipt['schema_version']) is int and receipt['schema_version'] == 1
            and receipt['id'] == spec['id']
            and receipt['provenance']['publication_sha256'] == spec['population'], 'Replay identity mismatch')
    checks = {}
    for check in receipt['checks']:
        evidence.closed(check, ('id', 'expected', 'observed'))
        identity = check['id']
        require(identity in controls and identity not in checks and check['expected'] == controls[identity],
                'Replay controls disagree with the reviewed plan')
        evidence.enum(check['observed'], ('verified', 'accepted', 'rejected', 'unmeasured'))
        checks[identity] = check['observed']
    unqualified = [name for name, value in controls.items() if checks.get(name) != value]
    rows = receipt['observations']
    require(type(rows) is list and len(rows) <= expected, 'Unexpected replay population')
    identities = set()
    for row in rows:
        evidence.token(row['id'])
        evidence.sha(row['sha256'])
        require(row['id'] not in identities, 'Duplicate replay observation')
        evidence.enum(row['outcome'], counts)
        identities.add(row['id'])
        if not unqualified and row['outcome'] != 'unmeasured':
            counts[row['outcome']] += 1
            counts['unmeasured'] -= 1
    if unqualified:
        return counts, 'Unqualified controls: ' + ', '.join(unqualified) + '.'
    if counts['unmeasured']:
        return counts, 'A qualified result is missing for ' + report.count(counts['unmeasured'], 'saved submission') + '.'
    if counts['accepted'] and counts['rejected']:
        return counts, 'The saved suites gave mixed results.'
    return counts, None


def replay_finding(spec, receipt):
    counts, unresolved = replay_observations(spec, receipt)
    variation = label(spec['variation'])
    if unresolved:
        heading = 'Unresolved · Neither yet'
        finding = report.safe(unresolved)
        action = ('Inspect the acceptance and rejection split before changing coverage.'
                  if not counts['unmeasured'] else 'Complete the missing replay evidence before changing coverage.')
        change = 'A qualified result for every saved submission with consistent outcomes would resolve the finding.'
    elif counts['rejected']:
        heading = 'Confirmed · Evaluator coverage gap'
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
             '<p class="finding-result"><strong>' + count_line + '</strong></p>',
             '<p><strong>Next step</strong> · ' + action + '</p>',
             '<p><strong>What would change it</strong> · ' + change + '</p>']
    if receipt is not None:
        target = report.anchor('replay', spec['id'])
        controls = [[label(row['id']), label(row['expected']), label(row['observed'])] for row in receipt['checks']]
        observations = [[label(row['id']), label(row['outcome'])] for row in receipt['observations']]
        parts.append(f'<p><a href="#{target}">Replay evidence</a> · ' + source_link(spec['contract']) + '</p>'
                     f'<details><summary>Replay controls, runs and provenance</summary><div id="{target}">' +
                     report.table('Diagnostic controls', ('Control', 'Expected', 'Observed'), controls) +
                     report.table('Receipt observations · subject to control qualification', ('Submission', 'Outcome'), observations) +
                     report.disclosure('Exact replay receipt', receipt) + '</div></details>')
    return ''.join(parts)


def decision_section(manifest, result, records, receipts, replays):
    evidence.closed(manifest, ('schema_version', 'receipts', 'decisions'))
    require(type(manifest['schema_version']) is int and manifest['schema_version'] == 1, 'Decision schema')
    cards = manifest['decisions']
    require(type(cards) is list and 0 < len(cards) <= 16, 'Decision count')
    runs = {run['record_id']: run for skill in result['skills'] for run in skill['behavioral_results']}
    summaries = {}
    parts = ['<section class="review-decisions" aria-labelledby="review-decisions">'
             '<h2 id="review-decisions">Skill improvement findings</h2><div class="decision-cards">']
    for card in cards:
        extra = ('replay',) if 'replay' in card else ('next', 'reconsider')
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
            parts.append('<article class="decision-card replay-card">' + heading +
                         replay_finding(replay, replays.get(replay['id'])) +
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
    summary = ('<p class="lead">Matched-case results and diagnostic replays are reported above in their own units. '
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
    replays = {}
    for path in replay_paths:
        receipt = evidence.parse_json(read(path, SUPPLEMENT_LIMIT), limit=SUPPLEMENT_LIMIT)
        identity = receipt['id']
        require(identity not in replays and any(b['id'] == identity for b in bindings), 'Unknown or duplicate replay')
        evidence.reports.public_strings(receipt)
        replays[identity] = receipt
    for binding in bindings:
        evidence.relative(binding['member'])
        path = decisions_path.parent / binding['member']
        if binding['id'] not in replays and path.exists():
            receipt = evidence.parse_json(read(path, SUPPLEMENT_LIMIT), limit=SUPPLEMENT_LIMIT)
            evidence.reports.public_strings(receipt)
            replays[binding['id']] = receipt
    guard = evidence.input_guard(directories, states, members, budget)
    guard()

    page = report.render_report(result, captured)
    section, summaries = decision_section(manifest, result, captured.records, receipts, replays)
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
