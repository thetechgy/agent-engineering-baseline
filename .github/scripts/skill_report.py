#!/usr/bin/env python3
"""Render one private offline HTML report from public bundles and saved analysis."""

import argparse
import base64
import hashlib
import html
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import skill_analysis as analysis
import skill_evidence as evidence

HTML_LIMIT = 64 * 1024 * 1024
METHOD = 'private-offline-skill-report/2'
CONTRACT_ERRORS = (ValueError, OSError, TypeError, KeyError, IndexError, OverflowError, RecursionError, UnicodeError)

# Fixed assets only. No evidence is interpolated into CSS, JavaScript or URLs.
CSS = """
:root{color-scheme:light;--bg:#f4f6f8;--surface:#fff;--text:#192b3a;
--muted:#455c6b;--line:#788995;--accent:#005a87;--alert:#963511}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){color-scheme:dark;
--bg:#111c26;--surface:#192b38;--text:#edf3f7;--muted:#bccbd6;
--line:#8293a0;--accent:#8ad6ff;--alert:#ffb591}}
:root[data-theme=dark]{color-scheme:dark;--bg:#111c26;--surface:#192b38;
--text:#edf3f7;--muted:#bccbd6;--line:#8293a0;--accent:#8ad6ff;--alert:#ffb591}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font:1rem/1.6 system-ui,sans-serif;overflow-wrap:anywhere}
header,main,footer{max-width:76rem;margin:auto;padding:1.5rem}
header{padding-top:3rem}h1{font-size:clamp(2rem,5vw,3rem);line-height:1.15}
h2{font-size:1.65rem;line-height:1.3}h3{font-size:1.25rem}
p{max-width:78ch}a{color:var(--accent);text-underline-offset:.18em}
a:focus-visible,summary:focus-visible,select:focus-visible,[tabindex]:focus-visible{
outline:3px solid var(--accent);outline-offset:4px}
.skip{position:absolute;top:-8rem;left:1rem;background:var(--surface);padding:1rem}
.skip:focus{top:1rem}.eyebrow{color:var(--muted);letter-spacing:.1em;font-size:.8rem}
.muted,caption{color:var(--muted)}.notice{border-left:4px solid var(--accent);padding-left:1rem}
section.skill,.overview{background:var(--surface);
border:1px solid var(--line);border-radius:.6rem;padding:1.5rem;margin-bottom:2rem}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,14rem),1fr));gap:1rem}
.card,.assessment{border:1px solid var(--line);border-radius:.3rem;padding:1rem;min-width:0}
.card strong{display:block;font-size:1.5rem}.badge{display:inline-block;border:1px solid currentColor;
border-radius:.25rem;padding:.15rem .5rem;font-size:.85rem}
nav ul{display:flex;flex-wrap:wrap;gap:.5rem 1.5rem;padding:0;list-style:none}
nav a,summary,select{min-height:2rem}nav a{display:inline-block;padding:.3rem 0}
details{border-top:1px solid var(--line);padding:.75rem 0}summary{cursor:pointer;font-weight:600}
pre,code{font-family:ui-monospace,monospace;font-size:.85em}pre{white-space:pre-wrap;
overflow-wrap:anywhere;background:var(--bg);padding:1rem;border-radius:.3rem}
.table-scroll{max-width:100%;overflow-x:auto;margin:1rem 0}
table{border-collapse:collapse;width:100%;font-size:.95rem}caption{text-align:left;margin-bottom:.5rem}
table.wide{min-width:48rem}
th,td{padding:.7rem;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}
thead th{background:var(--bg)}tbody th{font-weight:600}td p{margin:0}
.priorities{padding-left:1.5rem}.priorities>li{padding:.5rem 0}
.run{border-top:2px solid var(--line);margin-top:1.5rem;padding-top:.5rem}
label{display:inline-block;margin-right:.5rem}select{font:inherit;background:var(--surface);
color:var(--text);border:1px solid var(--line);padding:.4rem}
@media(max-width:40rem){header,main,footer{padding:1rem}section.skill,.overview{padding:1rem}}
@media print{body{background:white;color:black}details{break-inside:avoid}
header,main,footer{max-width:none}.theme,.skip{display:none}.table-scroll{overflow:visible}}
""".strip()

JS = """
const control = document.getElementById('theme');
document.getElementById('theme-control').hidden = false;
control.addEventListener('change', () => {
  if (control.value === 'system') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.setAttribute('data-theme', control.value);
});
""".strip()

NEXT_STEPS = {
    'complete_scans_and_reproject': 'Complete missing scans, then regenerate public evidence.',
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
    'case_regression': 'Lower with-skill case score', 'failed_gate': 'Failed mandatory gate',
    'failed_static_checks': 'Failed blocking static check', 'incomplete_scans': 'Incomplete static scans',
    'incomplete_execution': 'Incomplete execution evidence', 'unavailable_support': 'Original support unavailable',
    'comparison_limit': 'Comparison invocation limit', 'comparison_limitation': 'Comparison unavailable or limited',
    'configured_unmeasured': 'Configured suite without measurement',
    'run_metric_regression': 'Lower metric in right-hand run', 'run_case_regression': 'Lower case score in right-hand run',
}
COMPARISON_STATUS = {
    'insufficient_run_evidence': 'Fewer than two measured runs supplied; cross-run comparison is unavailable.',
    'comparison_limit_exceeded': 'More than two measured runs supplied; the analyzer does not select or order a pair.',
    'invocation_comparison_limit_exceeded': 'More than 16 eligible skill pairs supplied; comparisons are suppressed.',
    'compared': 'The analyzer evaluated the two supplied runs for compatibility.',
}
ARM = {'with_skill': 'With skill', 'without_skill': 'Without skill'}
LIMITATIONS = {
    'results_not_supplied': 'Results were not supplied', 'coverage_missing': 'Numeric coverage is incomplete',
    'execution_incomplete': 'Execution evidence is incomplete', 'case_details_missing': 'Case details are missing',
    'metadata_missing': 'Required identity or attempt metadata is missing', 'source_unavailable': 'Exact source content is unavailable',
    'source_mismatch': 'Source identity does not match', 'reference_unavailable': 'Original support is unavailable',
    'reference_expired': 'Original artifact references have expired', 'scan_incomplete': 'Static scan coverage is incomplete',
}


def safe(value):
    return html.escape(str(value), quote=True)


def text(value):
    if value is None:
        return 'Unknown / not supplied'
    if type(value) is bool:
        return 'Yes' if value else 'No'
    return safe(value)


def code(value):
    return '<code>' + text(value) + '</code>'


def limitations(availability):
    return '; '.join(safe(LIMITATIONS[r]) + ' (' + code(r) + ')' for r in availability['reasons']) or 'No schema-level limitation recorded'


def anchor(kind, *identities):
    # Scope shared observation/reference IDs by their containing record.
    return kind + '-' + evidence.identity(list(identities)).split(':')[1]


def link(kind, identities, label):
    return f'<a href="#{anchor(kind, *identities)}">{safe(label)}</a>'


def disclosure(label, value):
    return '<details><summary>' + safe(label) + '</summary><pre>' + safe(
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False)) + '</pre></details>'


def quantity(value):
    if value is None:
        return 'Unavailable'
    # Direction is retained even when four-place display rounds to zero.
    return code(analysis.signed(value)) + ' (' + safe(value['direction']) + ')'


def table(caption, headers, rows):
    cells = []
    for row in rows:
        cells.append('<tr><th scope="row">' + row[0] + '</th>' + ''.join(
            '<td>' + cell + '</td>' for cell in row[1:]) + '</tr>')
    width_class = ' class="wide"' if len(headers) > 4 else ''
    return '<div class="table-scroll" role="region" aria-label="' + safe(caption) + '" tabindex="0"><table' + width_class + '><caption>' + safe(
        caption) + '</caption><thead><tr>' + ''.join('<th scope="col">' + safe(h) + '</th>' for h in headers
        ) + '</tr></thead><tbody>' + ''.join(cells) + '</tbody></table></div>'


def support_links(finding, records):
    links = [link('record', (rid,), 'Record ' + rid) for rid in finding['record_ids']]
    for rid in finding['record_ids']:
        record = records[rid]
        for obs in record.get('observations', []):
            if obs['id'] in finding['observation_ids']:
                links.append(link('observation', (rid, obs['id']), 'Observation ' + obs['id']))
        for ref in record.get('references', []):
            if ref['id'] in finding['reference_ids']:
                links.append(link('reference', (rid, ref['id']), 'Reference ' + ref['id']))
    return '<ul>' + ''.join('<li>' + item + '</li>' for item in links) + '</ul>' if links else '<p>No record-level support links for this invocation limit.</p>'


def priorities(findings, records):
    if not findings:
        return '<p>No deterministic investigation findings in the supplied evidence. This does not establish production readiness.</p>'
    order = {'mandatory': 0, 'investigate': 1, 'context': 2}
    items = []
    for item in sorted(findings, key=lambda f: (order[f['importance']], f['kind'], f['id'])):
        label = {'mandatory': 'Mandatory outcome to inspect', 'investigate': 'Investigation', 'context': 'Evidence gap'}[item['importance']]
        observed = item['observed']
        facts = []
        if item['case_ids']:
            facts.append('Cases: ' + ', '.join(code(v) for v in item['case_ids']))
        if 'with_minus_without' in observed:
            facts.append('With minus without: ' + quantity(observed['with_minus_without']))
        if 'right_minus_left' in observed:
            facts.append('Right minus left: ' + quantity(observed['right_minus_left']))
        if observed.get('components'):
            facts.append('Failed gate components: ' + ', '.join(code(v) for v in observed['components']))
        if observed.get('scanners'):
            facts.append('Scanners: ' + ', '.join(code(v) for v in observed['scanners']))
        if 'unavailable_references' in observed:
            facts.append('Unavailable original references: ' + text(observed['unavailable_references']))
        items.append('<li><strong>' + safe(FINDING_LABELS[item['kind']]) + '</strong> <span class="badge">' + label +
            '</span><p>' + '; '.join(facts) + '</p><p>' + safe(NEXT_STEPS[item['next_step']]) + '</p><details><summary>Finding evidence and uncertainty</summary>' +
            '<p>Cases: ' + (', '.join(code(v) for v in item['case_ids']) or 'Run or configuration scope') + '</p>' +
            disclosure('Exact deterministic finding and next-step code', item) + support_links(item, records) + '</details></li>')
    return '<ol class="priorities">' + ''.join(items) + '</ol>'


def record_support(rid, record):
    parts = [disclosure('Source identity and content manifest', record['source']),
             disclosure('Record scope and availability', {k: record[k] for k in ('kind', 'run_id', 'availability')}),
             disclosure('Dataset identity', record['dataset']), disclosure('Policy identity', record['policy'])]
    if record['kind'] == 'behavioral':
        parts.append(disclosure('Arm conditions and coverage', record['arms']))
    observations = []
    for obs in record['observations']:
        refs = '<br>'.join(link('reference', (rid, ref), ref) for ref in obs['references'])
        observations.append([f'<span id="{anchor("observation", rid, obs["id"])}">' + code(obs['id']) + '</span>',
            safe(ARM[obs['arm']]), code(obs['case_id']), text(obs['attempt']), text(obs['score']), text(obs['rubric_pass']),
            text(obs['deterministic_gate']), disclosure('Native component scores and gate details', {
                'scores': obs['scores'], 'deterministic_scores': obs['deterministic_scores']}) + refs])
    if observations:
        parts.append(table('Observation identities and recorded outcomes',
            ('Observation', 'Arm', 'Case', 'Attempt', 'Overall score', 'Rubric pass', 'Mandatory gate', 'Components and references'), observations))
    parts.append('<p>Reference availability is recorded public availability, not verification of local possession. '
                 'Members and locators are inert identifiers; this report never retrieves or opens them.</p>')
    references = []
    for ref in record['references']:
        references.append([f'<span id="{anchor("reference", rid, ref["id"])}">' + code(ref['id']) + '</span>',
            text(ref['availability']), code(ref['member']), disclosure('Artifact, digest, locator and provenance', ref)])
    parts.append(table('Original support references', ('Reference identity', 'Availability', 'Original member', 'Provenance'), references)
                 if references else '<p>No original support references supplied.</p>')
    return '<details><summary>Source, policy, observations and original support</summary>' + ''.join(parts) + '</details>'


def behavioral(run, records):
    rid = run['record_id']; record = records[rid]
    parts = [f'<article class="run" id="{anchor("record", rid)}"><h3>Behavioral run: ' + text(run['run_id']) + '</h3>',
        '<p>Evidence: <strong>' + text(run['availability']['status']) + '</strong>. Measurement: <strong>' +
        ('Recorded' if run['measured'] else 'Unmeasured') + '</strong>. Record ' + code(rid) + '</p>',
        '<p>Evaluated source: ' + text(run['source']['owner']) + ' · ' + code(run['source']['repository']) +
        ' · revision ' + code(run['source']['revision']) + '.</p>',
        '<p>Limitations: ' + limitations(run['availability']) + '</p>']
    if run['native_metrics']:
        parts.append(table('Native evaluator metrics — score units, preserved as supplied', ('Metric', 'Native value', 'Scope'),
            [[safe(m['name']), text(m['value']), 'With minus without' if m['name'] == 'Skill Lift' else 'With-skill dimension']
             for m in run['native_metrics']]))
    else:
        parts.append('<p>Native metrics unavailable; no performance value is inferred.</p>')
    parts.append(table('Measured coverage by arm — unknown counts are not zero',
        ('Arm', 'Execution', 'Cases expected', 'Attempts expected', 'Recorded', 'Scored', 'Unscored', 'Rubric cases passed / total'),
        [[safe(ARM[a['name']]), text(a['execution_status']), text(a['coverage']['expected_cases']),
          text(a['coverage']['expected_attempts']), text(a['coverage']['recorded_attempts']),
          text(a['coverage']['scored_attempts']), text(a['coverage']['unscored_attempts']),
          text(a['rubric']['passed_cases']) + ' / ' + text(a['rubric']['total_cases'])] for a in run['arms']]))
    summary = run['case_summary']; gates = run['gates']
    parts.append('<p>' + text(summary['matched_cases']) + ' matched cases out of ' + text(summary['cohort_cases']) +
        '; ' + text(summary['scored_observations']) + ' scored observations. Mandatory gates: ' +
        text(len(gates['failed'])) + ' failed, ' + text(gates['passed_observations']) + ' passed, ' +
        text(gates['unknown_observations']) + ' unknown. Unknown gates do not count as passing.</p>')
    rows = []
    for case in summary['cases']:
        obs_links = '<br>'.join(link('observation', (rid, oid), ARM[arm] + ' observation ' + oid)
            for arm, ids in case['observation_ids'].items() for oid in ids)
        rows.append([code(case['case_id']), quantity(case['arm_means']['with_skill']),
            quantity(case['arm_means']['without_skill']), quantity(case['with_minus_without']),
            ', '.join(code(v) for v in case['unavailable_reasons']) or 'Complete planned scores',
            disclosure('Exact derived quantities and support identities', case) + obs_links])
    parts.append('<details><summary>All case scores and comparison coverage</summary><p>Descriptive arm means across complete planned attempts; '
        'with minus without. Attempts are not statistically paired. Missing or adaptive attempts suppress means. '
        'These case means do not reconstruct native Skill Lift.</p>' + table('Within-run case comparison',
        ('Case', 'With skill mean', 'Without skill mean', 'With minus without', 'Coverage limitations', 'Evidence'), rows) + '</details>')
    parts.extend([record_support(rid, record), '</article>'])
    return ''.join(parts)


def static_result(run, records):
    rid = run['record_id']
    parts = [f'<article class="run" id="{anchor("record", rid)}"><h3>Static checks</h3><p>Record ' + code(rid) +
        '; evidence ' + text(run['availability']['status']) + '. Static checks are not behavioral performance.</p>',
        '<p>Limitations: ' + limitations(run['availability']) + '</p>']
    parts.append(table('Scanner outcomes — counts can include findings without public detail',
        ('Scanner', 'State', 'Blocking', 'Passed', 'Critical / high / medium / low'),
        [[code(s['scanner']), text(s['status']), text(s.get('blocking', True)), text(s['passed']),
          ' / '.join(text(s['severity_counts'][k]) for k in ('critical', 'high', 'medium', 'low'))] for s in run['scans']]))
    parts.append('<details><summary>Structured static findings</summary>' + table('Public static finding details',
        ('Scanner / check', 'Severity', 'Member / line', 'Original reference'),
        [[code(f['scanner']) + ' / ' + code(f['check']), text(f['severity']), code(f['member']) + ' / ' + text(f['line']),
          link('reference', (rid, f['reference']), f['reference'])] for f in run['detailed_findings']]) + '</details>')
    parts.extend([record_support(rid, records[rid]), '</article>'])
    return ''.join(parts)


def comparisons(skill):
    parts = ['<h3>Cross-run comparisons</h3><p>' + safe(COMPARISON_STATUS[skill['comparison_status']]) + '</p>',
        '<p>Left and right follow semantic record identity order, not time. No chronology or trend is established. '
        'Direct compatibility means recorded conditions match; it does not establish causality, significance or repeatability.</p>']
    for pair in skill['comparisons']:
        parts.append('<details><summary>Comparison: ' + safe(pair['classification']) + '</summary><p>Comparison identity ' + code(pair['id']) +
            '</p><p>Left: ' + link('record', (pair['left_record_id'],), pair['left_record_id']) + '<br>Right: ' +
            link('record', (pair['right_record_id'],), pair['right_record_id']) + '</p>')
        parts.append('<p>Compatibility reasons: ' + (', '.join(code(r) for r in pair['reasons']) or 'No recorded mismatch') + '</p>')
        parts.append(table('Cross-run native metrics', ('Metric', 'Left', 'Right', 'Right minus left'),
            [[safe(m['name']), text(m['left']), text(m['right']), quantity(m['right_minus_left'])] for m in pair['native_metrics']]))
        parts.append(table('Cross-run cases — only analyzer-supported deltas',
            ('Case / arm', 'Left mean', 'Right mean', 'Right minus left'),
            [[code(c['case_id']) + ' / ' + safe(ARM[a]), quantity(c['left_arm_means'][a]), quantity(c['right_arm_means'][a]),
              quantity(c['right_minus_left'][a])] for c in pair['cases'] for a in ARM]))
        parts.append(disclosure('Exact comparison quantities and observation identities', pair) + '</details>')
    return ''.join(parts)


def asset_hash(value):
    return base64.b64encode(hashlib.sha256(value.encode('utf-8')).digest()).decode('ascii')


def interpretation(item):
    """Only independently validated attachments reach this inert presentation."""
    report = item['report']; judgment = report['judgment']; assessment = judgment['assessment']
    parts = ['<article class="run"><h3>Model interpretation · analyst report</h3>'
        '<p class="notice"><strong>Model-generated judgment requiring human review.</strong> '
        'Citation integrity does not establish semantic truth or an instruction defect. '
        'Recommendations and validation plans are proposals, not completed actions.</p><p>Bound record: ' +
        link('record', (item['record_id'],), item['record_id']) + '</p><p>Analyst disposition: <strong>' +
        text(assessment['disposition']) + '</strong> · ' + text(len(judgment['recommendations'])) +
        ' recommendations. Source owner: ' + text(report['provenance']['source_owner']) + '.</p>']
    for key, label in (('tested_benefit', 'Tested benefit · analyst interpretation'),
                       ('tested_harm', 'Tested harm · analyst interpretation'), ('uncertainty', 'Uncertainty')):
        parts.append('<p><strong>' + label + ':</strong> ' + text(assessment[key]) + '</p>')
    parts.append('<details><summary>Analyst reasoning, sufficiency and citations</summary><p>' +
        text(assessment['interpretation']) + '</p>' + disclosure('Assessment evidence and limitations', {
            'sufficiency': assessment['sufficiency'], 'citations': assessment['citations']}) +
        disclosure('Native suggestions and analyst dispositions', judgment['native_suggestions']) +
        disclosure('Unverified external assertions', judgment['unverified_external_assertions']) + '</details>')
    if not judgment['recommendations']:
        parts.append('<p>No recommendations supplied. This is not a clean bill of health or approval.</p>')
    for index, recommendation in enumerate(judgment['recommendations'], 1):
        parts.append('<details><summary>Recommendation ' + str(index) + ': ' + text(recommendation['category']) +
            ' · ' + text(recommendation['priority']) + '</summary>')
        for key in ('scope', 'justification', 'expected_benefit'):
            parts.append('<p><strong>' + safe(key.replace('_', ' ').capitalize()) + ':</strong> ' + text(recommendation[key]) + '</p>')
        parts.append(disclosure('Source targets, evidence, alternatives, risks and proposed validation',
            {k: v for k, v in recommendation.items() if k not in ('scope', 'justification', 'expected_benefit')}) + '</details>')
    parts.append(disclosure('Analyst provenance and original validation profile', {
        'profile': item['profile'], 'tooling_revision': item['tooling_revision'],
        'review_digest': item['review_digest'], 'markdown_digest': item['markdown_digest'],
        'provenance': report['provenance']}) + '<h4>Independent assessments · separately supplied</h4>'
        '<p>No authenticated human approval is established by this report. Authorship and independence are supplied '
        'attributions. Assessments are not aggregated and cannot change analyst qualification.</p>')
    if not item['assessments']:
        parts.append('<p>No independent assessments supplied for this analyst report.</p>')
    labels = {'independent_ai': 'Independent AI assessment (supplied)',
              'human_supplied': 'Human assessment (supplied; unauthenticated)', 'unknown': 'Assessment (author category unknown)'}
    for supplied in item['assessments']:
        score = ('Numeric score not assigned' if supplied['score'] is None else
                 'Supplied score: ' + text(supplied['score']) + ' / ' + text(supplied['maximum']))
        parts.append('<div class="assessment"><h5>' + labels[supplied['author_kind']] + '</h5><p>Attributed to ' +
            text(supplied['attribution']) + '. Supplied verdict: <strong>' + text(supplied['verdict']) +
            '</strong>. ' + score + '.</p><details><summary>Assessment reasoning, rubric and provenance</summary>')
        if supplied['dimensions'] is not None:
            parts.append(table('Supplied assessment dimensions — arithmetic checked, substantive judgments attributed',
                ('Dimension', 'Score', 'Assessor rationale'), [[text(name.replace('_', ' ')), text(row['score']),
                    text(row['rationale'])] for name, row in supplied['dimensions'].items()]))
        parts.append(disclosure('Supplied assessment limitations', supplied['limitations']))
        if supplied['narrative'] is not None:
            parts.append('<details><summary>Original assessment narrative · inert text</summary><pre>' +
                         safe(supplied['narrative']) + '</pre></details>')
        if supplied['rubric'] is not None:
            parts.append(disclosure('Preserved rubric context · no retrospective scoring', supplied['rubric']))
        else:
            parts.append('<p>Rubric not supplied; no rubric-compliance claim is inferred.</p>')
        if supplied['freeze'] is not None:
            timing = ('Recorded time ordering is consistent. ' if 'original_freeze_utc' in supplied['freeze'] else
                      'Freeze time not supplied; time ordering is not established. ')
            parts.append('<p>Freeze-record digest and context are consistent. ' + timing +
                'This is not trusted timestamp attestation or proof of independent authorship.</p>' +
                disclosure('Preserved freeze-record metadata', supplied['freeze']))
        else:
            parts.append('<p>Freeze evidence not supplied; preregistration is not established.</p>')
        parts.append(disclosure('Assessment document and rubric identities', supplied['provenance']) + '</details></div>')
    if item['reference_deadlines']:
        parts.append('<p class="notice">Reviewed-reference deadline(s): ' +
            ', '.join(code(value) for value in item['reference_deadlines']) +
            '. After expiration, omit this attachment and generate a base report from separately rebuilt '
            'current-availability public evidence. Original files must remain unchanged.</p>')
    parts.append('<p class="muted">Historical integration is time-limited by current-time evidence validation. '
        'A saved HTML file is a snapshot, not continuing validation. Keep analyst and assessment material private.</p></article>')
    return ''.join(parts)


def render_report(result, captured, *, reviews=None):
    """Validate again at the rendering boundary; never accept analysis in isolation."""
    analysis.validate_analysis(result, captured)
    if reviews is not None:
        import skill_report_reviews as attachments
        evidence.require(type(reviews) is attachments.ValidatedReviews, 'Validated analyst attachments required')
        reviews.check(captured)
    attached = {row['record_id']: row for row in reviews.items} if reviews is not None else {}
    records = captured.records
    csp = ("default-src 'none'; base-uri 'none'; object-src 'none'; form-action 'none'; "
           "connect-src 'none'; img-src 'none'; font-src 'none'; "
           f"style-src 'sha256-{asset_hash(CSS)}'; script-src 'sha256-{asset_hash(JS)}'")
    parts = []; size = 0

    def add(fragment):
        nonlocal size
        size += len(fragment.encode('utf-8'))
        evidence.require(size <= HTML_LIMIT, 'HTML report size exceeded')
        parts.append(fragment)

    add('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="' + safe(csp) + '">'
        '<meta name="referrer" content="no-referrer"><meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Private skill evaluation report</title><style>' + CSS + '</style></head><body>'
        '<a class="skip" href="#main">Skip to report</a><header><p class="eyebrow">PRIVATE · OFFLINE · DETERMINISTIC</p>'
        '<h1>Skill evaluation report</h1><p>What the supplied evidence shows, where it is incomplete, and what to inspect next.</p>'
        '<div class="theme" id="theme-control" hidden><label for="theme">Appearance</label><select id="theme">'
        '<option value="system">System default</option><option value="light">Light</option><option value="dark">Dark</option>'
        '</select></div></header><main id="main" tabindex="-1"><section class="overview" aria-labelledby="overview">'
        '<h2 id="overview">Executive overview</h2>')
    skills = result['skills']; findings = result['findings']
    measured_skills = sum(any(r['measured'] for r in s['behavioral_results']) for s in skills)
    counts = [('Skills represented', len(skills)), ('Skills with measurements', measured_skills),
              ('Case regressions', sum(f['kind'] == 'case_regression' for f in findings)),
              ('Failed mandatory gates', sum(f['kind'] == 'failed_gate' for f in findings))]
    add('<div class="cards">' + ''.join('<div class="card"><strong>' + text(n) + '</strong>' + label + '</div>'
                                       for label, n in counts) + '</div>')
    if attached:
        add('<p>Optional interpretation: <strong>' + text(len(attached)) + ' analyst reports</strong> and ' +
            text(sum(len(row['assessments']) for row in attached.values())) +
            ' separately supplied assessment records. Read these opinions in their labeled sections; '
            'they do not change the measurements or deterministic findings. Authenticated human approval is not established.</p>')
    unknown_gates = sum(r['gates']['unknown_observations'] for s in skills for r in s['behavioral_results'])
    add('<p>Mandatory gate outcomes are unknown for <strong>' + text(unknown_gates) +
        ' recorded observations</strong>. Unknown or unmeasured gates are not passing outcomes.</p>')
    add('<p>Behavioral evaluations measure recorded outputs on configured cases in separate with-skill and without-skill arms. '
        'Static scans check source artifacts. Inventory describes configuration; it never establishes measured performance. '
        'This report includes every skill represented in the supplied validated bundles, including skills without a behavioral suite.</p>'
        '<p class="notice"><strong>Start with mandatory outcomes, case regressions and evidence gaps.</strong> '
        'A favorable headline metric can coexist with lower case scores or failed gates. A grader failure is not automatically '
        'an instruction defect. Findings justify investigation, not corrective skill edits.</p>'
        '<p>Unknowns include omitted runs, unavailable original support, execution beyond the recorded carriers, '
        'production effectiveness and portability. No causal explanation, statistical significance, cross-suite ranking '
        'or time trend is inferred. Scores are not aggregated across skills.</p>'
        '<details><summary>How to read the measures</summary><p>Skill Lift is the native evaluator difference on its score scale. '
        'Effectiveness, Correctness and Discoverability are native with-skill rubric dimensions; corresponding without-skill '
        'headline dimensions are not supplied by this public contract. Values are preserved, not recomputed from '
        'rounded case scores. Case deltas use descriptive arm means only where all planned attempts are scored. '
        'A positive delta is higher, a negative delta is lower; neither explains why. Mandatory gates are separate from rubric passes. '
        'Unknown counts, scores and gates stay unknown.</p></details><h3>Skill directory</h3>')
    add(table('Coverage in supplied evidence', ('Skill', 'Behavioral evidence', 'Measured runs', 'Static records'),
        [[link('skill', (s['skill'],), s['skill']), 'Measured' if any(r['measured'] for r in s['behavioral_results']) else 'Unmeasured',
          text(sum(r['measured'] for r in s['behavioral_results'])), text(len(s['static_results']))] for s in skills]))
    if not skills:
        add('<p>The supplied inventory is empty. No skills or measurements are inferred.</p>')
    add('<nav aria-label="Report sections"><ul><li><a href="#provenance">Report provenance and limitations</a></li></ul></nav></section>')
    for skill in skills:
        name = skill['skill']
        add(f'<section class="skill" id="{anchor("skill", name)}"><h2>' + safe(name) + '</h2>')
        if not any(r['measured'] for r in skill['behavioral_results']):
            add('<p class="notice"><strong>Unmeasured.</strong> No supplied model-backed measurement. Configuration and offline fixture replay do not establish skill benefit or harm.</p>')
        for config in skill['configurations']:
            suite = config['suite']
            add('<p>Inventory snapshot: ' + (text(suite['case_count']) + ' configured cases' if suite else 'No behavioral suite configured') +
                '. Source owner: ' + text(config['source']['owner']) + '.</p>' + disclosure('Configuration identity and source snapshot', config))
        add('<p class="muted">Inventory snapshots and evaluated sources retain their separate identities; a current configuration does not rewrite a historical run.</p>'
            '<h3>Investigation priorities · deterministic findings</h3>' + priorities([f for f in findings if f['skill'] == name], records))
        for run in skill['behavioral_results']:
            add(behavioral(run, records))
        for run in skill['static_results']:
            add(static_result(run, records))
        if not skill['static_results']:
            add('<p>Static scan evidence not supplied for this skill; no clean-scan claim is made.</p>')
        skill_reviews = [row for row in attached.values() if row['skill'] == name]
        if skill_reviews:
            for row in skill_reviews:
                add(interpretation(row))
        else:
            add('<p>No analyst report supplied for this skill. Deterministic findings remain available; '
                'missing interpretation does not establish approval or absence of defects.</p>')
        add(comparisons(skill) + '</section>')
    add('<section id="provenance"><h2>Report provenance and limitations</h2><p>Presentation method ' + code(METHOD) +
        '; analysis method ' + code(result['method_version']) + '; public and analysis schema version 1. Analysis semantic digest ' +
        code(evidence.identity(result)) + '.</p><p>Saved analysis was independently rebuilt against captured public originals before rendering. '
        'Canonical record identities preserve semantic content; raw-byte digests preserve the exact supplied files. '
        'These bindings do not attest remote execution. No local input paths, generation timestamp, prompts or private trajectories are embedded.</p>')
    for rid, record in sorted(records.items()):
        if record['kind'] == 'inventory':
            add(f'<details id="{anchor("record", rid)}"><summary>Inventory record ' + safe(rid) + '</summary>' +
                disclosure('Validated inventory', record) + '</details>')
    add(disclosure('Input manifests, raw digests and record identities', result['input_provenance']) +
        disclosure('Analyzer comparison scope', result['comparison_scope']))
    global_findings = [f for f in findings if f['skill'] is None]
    if global_findings:
        add('<h3>Invocation-level investigation priorities</h3>' + priorities(global_findings, records))
    add('<h3>Model-generated recommendations and assessment boundaries</h3><p>' + text(len(attached)) +
        ' independently validated analyst reports attached. All deterministic investigation priorities above remain fixed descriptions '
        'of existing findings and next-step codes. The private analyst remains ' + code('not_quality_qualified') + ' and '
        'automated publication ineligible. Supplied AI or human assessments are separately attributed opinions; structural validation, '
        'rubric arithmetic and self-declared approval do not establish authenticated human review or authorize action.</p>'
        '<p>Keep this file private. It requires no server, external assets, analytics or network requests. '
        'Appearance follows the system unless changed for this open document. All evidence is readable without JavaScript; '
        'expand disclosures for detailed support.</p></section></main><footer>Private evidence report · supplied inputs only</footer>'
        '<script>' + JS + '</script></body></html>')
    return ''.join(parts).encode('utf-8')


def generate(inputs, saved_analysis, output=None, *, analyst_reviews=()):
    captured = analysis.capture_inputs(inputs)
    directories = {}; states = {}; members = {}; budget = evidence.ReadBudget()
    saved_path = evidence.safe_path(saved_analysis, directory_identities=directories)
    raw = evidence.read_bytes(saved_path, limit=analysis.JSON_LIMIT, budget=budget,
        directory_identities=directories, directory_states=states, file_states=members)
    result = evidence.parse_json(raw, limit=analysis.JSON_LIMIT)
    guard = evidence.input_guard(directories, states, members, budget)
    guard()
    reviews = None
    if analyst_reviews:
        import skill_report_reviews as attachments
        reviews = attachments.load(analyst_reviews, captured)
    rendered = render_report(result, captured, reviews=reviews) if reviews is not None else render_report(result, captured)
    return evidence.write_outputs({}, output, input_paths=(*captured.roots, saved_path.parent,
            *(reviews.roots if reviews is not None else ())),
        input_guards=(*captured.guards, guard, lambda: analysis.check_capture(captured),
            *((lambda: reviews.check(captured),) if reviews is not None else ())), rendered={'report.html': rendered})


class PrivateParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, 'Report arguments rejected; use --help for the supported interface.\n')


def main(argv=None):
    parser = PrivateParser(description=__doc__)
    parser.add_argument('--input', type=Path, action='append', required=True, help='Validated public bundle; repeat for additional roots')
    parser.add_argument('--analysis', type=Path, required=True, help='Saved analysis.json for exactly these bundles')
    parser.add_argument('--output', type=Path, help='New private directory outside checkout and inputs')
    parser.add_argument('--analyst-review', type=Path, action='append', default=[],
                        help='Private analyst attachment descriptor; at most one per selected record')
    args = parser.parse_args(argv)
    try:
        destination = generate(args.input, args.analysis, args.output, analyst_reviews=args.analyst_review)
    except CONTRACT_ERRORS:
        if args.analyst_review:
            parser.exit(1, 'Analyst report inputs rejected; no HTML report is ready. '
                'Omit --analyst-review for a base report with valid current-availability inputs.\n')
        raise
    print(destination)
    return destination


if __name__ == '__main__':
    try:
        main()
    except CONTRACT_ERRORS:
        print('Report contract rejected; no HTML report is ready.', file=sys.stderr)
        sys.exit(1)
