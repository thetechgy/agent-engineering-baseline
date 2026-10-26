#!/usr/bin/env python3
"""Render one private offline HTML report from public bundles and saved analysis."""

import argparse
import base64
import hashlib
import html
import json
from pathlib import Path
import re
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
header{padding-top:1.5rem;padding-bottom:0}h1{font-size:clamp(1.8rem,4vw,2.5rem);line-height:1.15;margin:.4rem 0}
h2{font-size:1.65rem;line-height:1.3}h3{font-size:1.25rem}
p{max-width:78ch;margin:.75rem 0}a{color:var(--accent);text-underline-offset:.18em}
a:focus-visible,summary:focus-visible,select:focus-visible,[tabindex]:focus-visible{
outline:3px solid var(--accent);outline-offset:4px}
.skip{position:absolute;top:-8rem;left:1rem;background:var(--surface);padding:1rem}
.skip:focus{top:1rem}.eyebrow{color:var(--muted);letter-spacing:.1em;font-size:.8rem}
.muted,caption{color:var(--muted)}.notice{border-left:4px solid var(--accent);padding-left:1rem}
.safety{border-left:4px solid var(--alert);padding:.5rem 1rem;background:var(--bg)}
.safety p{margin:.3rem 0}.safety strong{color:var(--alert)}
.lead{font-size:1.1rem}.finding{border-top:1px solid var(--line);padding:.75rem 0}
.finding p{margin:.4rem 0}.assessment{margin:.75rem 0}
.finding h4{margin:.25rem 0 .5rem}
:target{scroll-margin-top:1rem}summary code{font-weight:400}
section.skill,.overview{background:var(--surface);
border:1px solid var(--line);border-radius:.6rem;padding:1.5rem;margin-bottom:2rem}
.assessment{border:1px solid var(--line);border-radius:.3rem;padding:1rem;min-width:0}
.badge{display:inline-block;border:1px solid currentColor;
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
// Reveal nested evidence before following a link; native fragment navigation
// remains available without JavaScript (Chromium also reveals closed details).
document.addEventListener('click', event => {
  const a = event.target.closest('a[href^="#"]');
  const target = a && document.getElementById(a.hash.slice(1));
  if (!target) return;
  for (let parent = target.parentElement; parent; parent = parent.parentElement) {
    if (parent.tagName === 'DETAILS') parent.open = true;
  }
});
""".strip()

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
COMPARISON_STATUS = {
    'insufficient_run_evidence': 'Fewer than two measured runs supplied; cross-run comparison is unavailable.',
    'comparison_limit_exceeded': 'More than two measured runs supplied; the analyzer does not select or order a pair.',
    'invocation_comparison_limit_exceeded': 'More than 16 eligible skill pairs supplied; comparisons are suppressed.',
    'compared': 'The analyzer evaluated the two supplied runs for compatibility.',
}
ARM = {'with_skill': 'With skill', 'without_skill': 'Without skill'}
STATUS_LABELS = {
    'pass_substantive_usefulness_demonstrated': 'Substantive usefulness pass',
    'not_quality_qualified': 'Not quality qualified',
}
DISPOSITION_LABELS = {'skill_change': 'Skill change', 'investigate': 'Investigate', 'no_change': 'No change'}
PROPOSAL_LABELS = {
    'modify_skill': 'Modify skill', 'improve_eval': 'Improve evaluation',
    'fix_grader_or_harness': 'Fix grader or harness', 'investigate': 'Investigate', 'no_change': 'No change',
}
ASSESSOR_LABELS = {
    'independent_ai': 'Independent AI assessment (supplied)',
    'human_supplied': 'Human assessment (supplied; unauthenticated)',
    'unknown': 'Assessment (author category unknown)',
}
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


def presentation_label(value, labels):
    """Translate recognized codes only; supplied prose is otherwise verbatim."""
    return text(labels.get(value, value))


def count(value, singular, plural=None):
    return text(value) + ' ' + (singular if value == 1 else plural or singular + 's')


def outcome(value):
    # Recorded rubric booleans and gate 0/1 values share presentation only.
    if value is None:
        return 'Unknown'
    return 'Passed' if value == 1 else 'Failed'


def context(skill, cases=()):
    return skill + (' · ' + ('case ' if len(cases) == 1 else 'cases ') + ', '.join(cases) if cases else '')


def short_identity(value):
    """Display alias only; exact identities remain in evidence disclosures."""
    return re.sub(r'sha256:[a-f0-9]{64}', lambda m: m[0][:19] + '…', str(value))


def limitations(availability):
    return '; '.join(safe(LIMITATIONS[r]) + ' (' + code(r) + ')' for r in availability['reasons']) or 'No schema-level limitation recorded'


def anchor(kind, *identities):
    # Scope shared observation/reference IDs by their containing record.
    return kind + '-' + evidence.identity(list(identities)).split(':')[1]


def link(kind, identities, label):
    return f'<a href="#{anchor(kind, *identities)}">{safe(short_identity(label))}</a>'


def disclosure(label, value, *, target=None):
    identity = ' id="' + safe(target) + '"' if target is not None else ''
    return '<details><summary>' + safe(label) + '</summary><pre' + identity + '>' + safe(
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
    links = [link('record', (rid,), context(finding['skill'] or 'Report scope', finding['case_ids']) +
                  ' · record ' + rid) for rid in finding['record_ids']]
    for rid in finding['record_ids']:
        record = records[rid]
        for obs in record.get('observations', []):
            if obs['id'] in finding['observation_ids']:
                links.append(link('observation', (rid, obs['id']), context(record['source']['skill_id'], [obs['case_id']]) +
                                  ' · ' + ARM[obs['arm']] + ' observation ' + obs['id']))
        for ref in record.get('references', []):
            if ref['id'] in finding['reference_ids']:
                links.append(link('reference', (rid, ref['id']), context(record['source']['skill_id'], finding['case_ids']) +
                                  ' · reference ' + ref['id']))
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
            facts.append(('Case: ' if len(item['case_ids']) == 1 else 'Cases: ') + ', '.join(code(v) for v in item['case_ids']))
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
        items.append(f'<li id="{anchor("finding", item["id"])}"><strong>' + safe(FINDING_LABELS[item['kind']]) + '</strong> <span class="badge">' + label +
            '</span><p>' + '; '.join(facts) + '</p><p>' + safe(NEXT_STEPS[item['next_step']]) + '</p><details><summary>Finding evidence and uncertainty</summary>' +
            '<p>Scope: ' + (', '.join(code(v) for v in item['case_ids']) or 'Run or configuration scope') + '</p>' +
            disclosure('Exact deterministic finding and next-step code', item) + support_links(item, records) + '</details></li>')
    return '<ol class="priorities">' + ''.join(items) + '</ol>'


def coverage_label(skill):
    if any(run['measured'] for run in skill['behavioral_results']):
        return 'Measured results'
    if any(config['suite'] is not None for config in skill['configurations']) or skill['behavioral_results']:
        return 'Configured; results not supplied'
    if skill['configurations']:
        return 'No configured suite'
    return 'Configuration not supplied'


def security_investigations(skills, records):
    """Expose exact component values, without new means or analyst findings.

    Only complete single-attempt comparisons are eligible. Multi-attempt and
    missing-component comparisons remain in the original observation evidence.
    """
    rows = []
    for skill in skills:
        for run in skill['behavioral_results']:
            record = records[run['record_id']]
            if record['policy']['attempts']['maximum'] != 1:
                continue
            indexed = analysis.case_index(record)
            for case in run['case_summary']['cases']:
                if case['with_minus_without'] is None:
                    continue
                arms = indexed[case['case_id']]
                left, right = (arms[a][0] for a in ARM)
                with_score, without_score = left['scores']['security'], right['scores']['security']
                if with_score is not None and without_score is not None and with_score < without_score:
                    rows.append('<li><strong>' + safe(skill['skill']) + ' · Security-component score · case ' +
                        code(case['case_id']) + '</strong>: ' + text(with_score) + ' with skill versus ' +
                        text(without_score) + ' without skill. Inspect the security judgment separately from '
                        'command-wrapper or harness concerns. ' + link('components', (run['record_id'], left['id']),
                        context(skill['skill'], [case['case_id']]) + ' · with-skill security evidence') + ' · ' +
                        link('components', (run['record_id'], right['id']),
                        context(skill['skill'], [case['case_id']]) + ' · without-skill security evidence') + '.</li>')
    return rows


def assessment_summary(supplied):
    score = ('Numeric score not assigned' if supplied['score'] is None else
             'Supplied score: ' + text(supplied['score']) + ' out of ' + text(supplied['maximum']))
    return text(supplied['attribution']) + ': <strong>' + presentation_label(supplied['verdict'], STATUS_LABELS) + '</strong>. ' + score + '.'


def static_quality(skills):
    runs = [run for skill in skills for run in skill['static_results']]
    parts = ['<h3 id="static-quality">Static quality and coverage · native evaluator judgments</h3>',
             '<p>Scanner severity does not establish a confirmed vulnerability, instruction defect or need to change a skill. '
             'Findings remain advisory in quality CI.</p>']
    if not runs or any(not any(s['scanner'] == 'SECURITY' and s['status'] in ('passed', 'failed') for s in run['scans']) for run in runs):
        parts.append('<p class="notice"><strong>Security-analysis coverage is incomplete or unavailable.</strong> '
                     'Retained findings still require investigation.</p>')
    parts.extend('<p>' + safe(line) + '</p>' for line in analysis.static_overview(runs))
    if any(not skill['static_results'] for skill in skills):
        parts.append('<p>Static evidence not supplied for: ' + ', '.join(
            link('skill', (skill['skill'],), skill['skill']) for skill in skills if not skill['static_results']) +
            '. Imported skills without an evaluation overlay may be outside the supplied inventory.</p>')
    parts.append('<h4>Significant static flags · applicability unresolved</h4>')
    groups = analysis.static_groups(runs)
    if not groups:
        parts.append('<p>No detailed critical/high flags supplied. Native counts and evidence gaps remain authoritative.</p>')
    else:
        parts.append('<ul class="priorities">')
        for key, items in groups[:analysis.SIGNIFICANT_GROUP_LIMIT]:
            level, scanner, check, _ = key
            names = sorted({run['source']['skill_id'] for run, _ in items})
            run, item = items[0]
            location = (item['member'] + (':' + str(item['line']) if item['line'] is not None else '')) if item['member'] else 'Source location unavailable'
            parts.append('<li><strong>' + safe(level.upper()) + ' · ' + code(scanner) + ' / ' + code(check) +
                '</strong> · ' + count(len(items), 'finding') + '<p>Affected skills: ' + ', '.join(
                    link('skill', (name,), name) for name in names) + '</p><p>' +
                safe(analysis.static_guidance(scanner, check)) + '</p><p>Representative: ' +
                link('static-finding', (run['record_id'], item['reference']),
                     run['source']['skill_id'] + ' · ' + location + ' · structured finding') + ' · ' +
                link('reference', (run['record_id'], item['reference']), 'exact report reference') + '</p></li>')
        parts.append('</ul>')
    omitted = groups[analysis.SIGNIFICANT_GROUP_LIMIT:]
    if omitted:
        parts.append('<p>Additional groups omitted from this preview: ' + '; '.join(
            str(sum(key[0] == level for key, _ in omitted)) + ' ' + level + ' groups / ' +
            str(sum(len(items) for key, items in omitted if key[0] == level)) + ' findings'
            for level in ('critical', 'high')) + '. Use the per-skill static evidence below for every finding.</p>')
    parts.append('<p>Groups count retained finding records, not raw scanner occurrence spans. Every individual finding remains '
                 'in the per-skill evidence. No false-positive classification or historical novelty is inferred.</p>')
    parts.append('<details><summary>Static evidence interpretation and limits</summary><p>SECURITY denotes this pipeline\'s '
        'SkillSpector integration; other validators retain separate attribution. Native required checks describe evaluator policy, '
        'not the CI finding policy or a scanner process outcome. Partial scans may retain valid findings. Zero findings and no '
        'incompleteness reported do not prove exhaustive inspection or behavioral benefit. Detailed SkillSpector coverage reasons '
        'and separate process outcomes are not retained by this native-report path.</p></details>')
    return ''.join(parts)


def static_directory(skill):
    if not skill['static_results']:
        return 'Not supplied; no clean-scan claim'
    rows = []
    for run in skill['static_results']:
        native = next((s for s in run['scans'] if s['scanner'] == 'catalog-total'), None)
        rows.append(link('record', (run['record_id'],), skill['skill'] + ' · static record ' + run['record_id']) +
            ' · native ' + text(native['status'] if native else None) + ' · C/H/M/L ' +
            (' / '.join(text(native['severity_counts'][k]) for k in analysis.SEVERITIES) if native else 'Unknown'))
    return '<br>'.join(rows)


def executive_summary(result, records, attached):
    skills = result['skills']; findings = result['findings']
    measured = [s for s in skills if any(r['measured'] for r in s['behavioral_results'])]
    parts = ['<p class="lead">' + count(len(skills), 'skill') + ' represented; <strong>' + text(len(measured)) +
        ' with measured results</strong>. ' +
        text(sum(coverage_label(s) == 'Configured; results not supplied' for s in skills)) +
        ' configured without supplied results; ' + text(sum(coverage_label(s) == 'No configured suite' for s in skills)) +
        ' without a configured behavioral suite.</p>']
    for skill in measured:
        for run in skill['behavioral_results']:
            if run['measured']:
                lift = next((m['value'] for m in run['native_metrics'] if m['name'] == 'Skill Lift'), None)
                regressions = sum(f['kind'] == 'case_regression' and run['record_id'] in f['record_ids'] for f in findings)
                parts.append('<p><strong>' + safe(skill['skill']) + '</strong>: ' +
                    ('Skill Lift ' + text(lift) + ' (with minus without on the evaluator scale); ' if lift is not None else '') +
                    ('Reported custom measurements; paired population ' +
                     ('complete' if run['custom']['complete_paired_population'] else 'incomplete')
                     if run['policy']['fields']['grading'] == 'custom_only' and 'custom' in run else
                     count(regressions, 'lower with-skill case score')) + '. ' +
                    link('record', (run['record_id'],), skill['skill'] + ' · measured results and coverage') + '.</p>')
    runs = [r for s in skills for r in s['behavioral_results']]
    failed = sum(len(r['gates']['failed']) for r in runs)
    passed = sum(r['gates']['passed_observations'] for r in runs)
    unknown = sum(r['gates']['unknown_observations'] for r in runs)
    missing_coverage = any(not r['measured'] or any(
        arm['execution_status'] != 'succeeded' or arm['coverage']['expected_attempts'] is None
        or arm['coverage']['recorded_attempts'] != arm['coverage']['expected_attempts']
        or arm['coverage']['case_details'] != 'complete' for arm in r['arms'])
        or any(obs['attempt'] is None for obs in records[r['record_id']]['observations'])
        for r in runs) or any(f['kind'] == 'configured_unmeasured' for f in findings)
    incomplete = unknown or not (failed + passed + unknown) or missing_coverage
    parts.append('<div class="safety"><p><strong>' +
        ('Safety evidence is incomplete' if incomplete else 'Recorded mandatory gate outcomes') + '</strong></p><p>' +
        'Among recorded observations: ' +
        text(failed) + ' failed · ' + text(passed) + ' passed · ' + text(unknown) +
        ' unknown</p><p>' + ('No recorded gate outcomes supplied. ' if not (failed + passed + unknown) else '') +
        ('Missing execution coverage is excluded from these counts. ' if missing_coverage else '') +
        'Unknown or unmeasured gates are not passing outcomes. ' +
        ('Inspect recorded failures before accepting the result.' if failed else 'Zero recorded failures does not establish safety.') + '</p></div>')
    parts.append('<nav aria-label="Report sections"><ul><li><a href="#important-findings">Important findings</a></li>'
        '<li><a href="#static-quality">Static quality and coverage</a></li>'
        '<li><a href="#analyst-actions">Analyst conclusions and actions</a></li>'
        '<li><a href="#coverage">Coverage directory</a></li><li><a href="#provenance">Provenance and limitations</a></li></ul></nav>')
    parts.append(static_quality(skills))
    parts.append('<h3 id="important-findings">Important findings · deterministic evidence</h3>'
        '<p>Grader judgments describe recorded outputs; they do not verify execution. A grader failure is not automatically '
        'an instruction defect. '
        'Investigate these signals before proposing changes.</p>')
    mandatory = []; important = security_investigations(skills, records)
    for finding in findings:
        if finding['importance'] == 'context':
            continue
        observed = finding['observed']
        detail = (' · ' + ('case ' if len(finding['case_ids']) == 1 else 'cases ') +
                  ', '.join(safe(v) for v in finding['case_ids'])) if finding['case_ids'] else ''
        if 'with_minus_without' in observed:
            detail += ' · with minus without ' + quantity(observed['with_minus_without'])
        (mandatory if finding['importance'] == 'mandatory' else important).append('<li><strong>' + text(finding['skill'] or 'Report scope') + ' · ' +
            safe(FINDING_LABELS[finding['kind']]) + '</strong>' + detail + '. ' +
            link('finding', (finding['id'],), context(finding['skill'] or 'Report scope', finding['case_ids']) +
                 ' · finding and next step') + '.</li>')
    parts.append('<ul class="priorities">' + ''.join(mandatory + important) + '</ul>' if mandatory or important else
        '<p>No deterministic investigation findings in the supplied evidence; this does not establish readiness.</p>')
    parts.append('<details><summary>What remains unknown</summary><p>Missing measurements, unknown gates, '
        'omitted runs, original support availability, actual runtime behavior, production effectiveness and portability '
        'limit interpretation. Differences are descriptive; causality, statistical significance, cross-suite ranking '
        'and time trends are not established. Static scans and configuration do not measure behavioral benefit.</p></details>'
        '<h3 id="analyst-actions">Analyst conclusions and recommended actions · model interpretation</h3>'
        '<p>Analyst qualification: <strong>' + presentation_label('not_quality_qualified', STATUS_LABELS) + '</strong>. Automated publication is ineligible. '
        'Authenticated human approval is not established. Supplied assessments are separate opinions about analyst usefulness, '
        'not skill performance or permission to act.</p>')
    for item in attached.values():
        judgment = item['report']['judgment']
        parts.append('<div class="finding"><h4>' + safe(item['skill']) + ' · ' +
            'Analyst interpretation · ' + presentation_label(judgment['assessment']['disposition'], DISPOSITION_LABELS) + '</h4><p>' +
            link('interpretation', (item['record_id'],), item['skill'] + ' · analyst conclusions, proposed actions and citations') + '</p>')
        for recommendation in judgment['recommendations']:
            parts.append('<p><strong>Proposed action · ' + presentation_label(recommendation['category'], PROPOSAL_LABELS) + ':</strong> ' +
                text(recommendation['scope']) + '</p>')
        for supplied in item['assessments']:
            parts.append('<p><strong>' + safe(ASSESSOR_LABELS[supplied['author_kind']]) + ':</strong> ' + assessment_summary(supplied) + ' ' +
                link('assessment', (item['record_id'], supplied['id']), item['skill'] + ' · ' + supplied['attribution'] +
                     ' · assessment reasoning and limitations') + '</p>')
        parts.append('</div>')
    if not attached:
        parts.append('<p>No analyst reports or independent assessments supplied. Use the deterministic next steps.</p>')
    parts.append('<h3 id="coverage">Coverage directory</h3>')
    parts.append('<p>Evaluation groups (arms) compare recorded outputs with and without skill. Coverage is not a quality rating.</p>')
    parts.append(table('Coverage in supplied evidence', ('Skill', 'Behavioral evidence', 'Configured coverage', 'Static evidence'),
        [[link('skill', (s['skill'],), s['skill']), safe(coverage_label(s)),
          '; '.join(count(c['suite']['case_count'], 'configured case') + ' per arm' for c in s['configurations'] if c['suite']) or
          ('No behavioral suite configured' if s['configurations'] else 'Configuration not supplied'),
          static_directory(s)] for s in skills]))
    if not skills:
        parts.append('<p>The supplied inventory is empty. No skills or measurements are inferred.</p>')
    return ''.join(parts)


def record_support(rid, record):
    parts = [disclosure('Source identity and content manifest', record['source']),
             disclosure('Record scope and availability', {k: record[k] for k in ('kind', 'run_id', 'availability')}),
             disclosure('Dataset identity', record['dataset']), disclosure('Policy identity', record['policy'])]
    if record['kind'] == 'behavioral':
        parts.append(disclosure('Arm conditions and coverage', record['arms']))
    observations = []
    for obs in record['observations']:
        refs = '<br>'.join(link('reference', (rid, ref), context(record['source']['skill_id'], [obs['case_id']]) +
                               ' · reference ' + ref) for ref in obs['references'])
        observations.append([f'<span id="{anchor("observation", rid, obs["id"])}">' + code(short_identity(obs['id'])) + '</span>',
            safe(ARM[obs['arm']]), code(obs['case_id']), text(obs['attempt']), text(obs['score']), outcome(obs['rubric_pass']),
            outcome(obs['deterministic_gate']), disclosure('Exact observation outcomes', {
                'rubric_pass': obs['rubric_pass'], 'deterministic_gate': obs['deterministic_gate']}) +
            disclosure('Native component scores and gate details', {
                'observation_id': obs['id'], 'scores': obs['scores'], 'deterministic_scores': obs['deterministic_scores'],
                **({'custom': obs['custom']} if 'custom' in obs else {})},
                target=anchor('components', rid, obs['id'])) + refs])
    if observations:
        parts.append(table('Observation identities and recorded outcomes',
            ('Observation', 'Arm', 'Case', 'Attempt', 'Overall score', 'Rubric pass', 'Mandatory gate', 'Components and references'), observations))
    parts.append('<p>Reference availability is recorded public availability, not verification of local possession. '
                 'Members and locators are inert identifiers; this report never retrieves or opens them.</p>')
    references = []
    for ref in record['references']:
        references.append([f'<span id="{anchor("reference", rid, ref["id"])}">' + code(short_identity(ref['id'])) + '</span>',
            text(ref['availability']), code(ref['member']), disclosure('Artifact, digest, locator and provenance', ref)])
    parts.append(table('Original support references', ('Reference identity', 'Availability', 'Original member', 'Provenance'), references)
                 if references else '<p>No original support references supplied.</p>')
    return '<details><summary>Source, policy, observations and original support</summary>' + ''.join(parts) + '</details>'


def custom_measurements(run, record):
    result = run['custom']; rid = run['record_id']
    parts = ['<h4>Skill-specific deterministic measurements</h4>',
        '<p class="notice"><strong>Structurally validated reported evidence.</strong> Native consistency was reported at admission; '
        'this consumer does not recheck native directories. Producer identity and execution are not independently authenticated. '
        'Hashes identify content; they do not prove who produced it or that execution occurred.</p>',
        '<p>Purpose: ' + text(result['purpose']) + '; recorded agent: ' + code(result['agent']) + '; version ' + code(record['custom']['agent_version']) + '. ' +
        ('Oracle fixture qualification is not model-backed skill-effectiveness evidence.' if result['purpose'] == 'oracle_qualification' else
         'Within-run differences describe supplied measurements; they do not establish causality.') + '</p>']
    parts.append(table('Tasks and applicability', ('Case', 'Task', 'Source case', 'Applicable native metrics'),
        [[code(case['case_id']), text(case['title']), code(case['source_case_id']), ', '.join(code(k) for k in case['metrics'])]
         for case in record['custom']['cases']]))
    if any(definition['role'] == 'mandatory_with_skill_gate' for definition in record['custom']['definitions']):
        parts.append('<p>Pass/fail below summarizes the registered gate conjunction. Task correctness is separate. '
                     'Baseline gate zeros are comparison evidence, not mandatory with-skill failures.</p>')
    kinds = (*evidence.CUSTOM_OUTCOMES, 'missing')
    parts.append(table('Reported custom-grader classifications · failures and unavailability stay distinct', ('Arm', *kinds),
        [[safe(ARM[arm]), *[text(result['outcomes'][arm][kind]) for kind in kinds]] for arm in ARM]))
    for metric in result['metrics']:
        definition = metric['definition']
        parts += ['<h4>' + text(definition['title']) + '</h4><p>' + text(definition['definition']) + '</p>',
            '<p>Metric ' + code(definition['id']) + '; competency ' + code(definition['competency']) + '; unit ' + code(definition['unit']) +
            '. Aggregation: equal weight per applicable trial, preserving each trial\'s numerator and denominator.</p>',
            table('Applicability and complete-population comparison · ' + definition['id'],
                ('Arm', 'Expected applicable', 'Measured', 'Unavailable / missing', 'Recorded nonapplicable', 'Complete-population mean'),
                [[safe(ARM[arm]), *[text(metric['coverage'][arm][key]) for key in ('expected_applicable', 'measured', 'unavailable_or_missing', 'recorded_nonapplicable')],
                  quantity(metric['arm_means'][arm])] for arm in ARM]),
            '<p>With minus without: ' + quantity(metric['with_minus_without']) + '. ' +
            text(metric['unavailable_reason'] or metric['interpretation']) + '. '
            'Activation/routing and gate outcomes are not interchangeable with task correctness.</p>']
    rows = []
    for obs in record['observations']:
        for measurement in obs['custom']['measurements']:
            rows.append([code(obs['case_id']), safe(ARM[obs['arm']]), text(obs['attempt']),
                text(obs['custom']['outcome']), code(measurement['metric_id']), text(measurement['applicability']),
                text(measurement['value']) if measurement['status'] == 'measured' else 'Unavailable',
                text(measurement['numerator']) + ' / ' + text(measurement['denominator']),
                text(measurement['reason']), link('observation', (rid, obs['id']), 'Trial and evidence')])
    parts.append('<details><summary>All custom measurements and scoring bases</summary>' + table('Recorded custom measurements',
        ('Case', 'Arm', 'Attempt', 'Grader outcome', 'Metric', 'Applicability', 'Value', 'Numerator / denominator', 'Limitation', 'Evidence'), rows) + '</details>')
    parts.append('<details><summary>Native token and phase-runtime observations</summary><p>Missing values stay unknown. '
        'Input tokens include cache tokens; phase durations are derived only from recorded start/finish times. '
        'These observations do not establish total model/judge usage.</p>' + table('Per-trial reported usage',
        ('Case / arm', 'Input tokens', 'Cache tokens', 'Output tokens', 'Agent seconds', 'Verifier seconds'),
        [[code(obs['case_id']) + ' / ' + safe(ARM[obs['arm']]), *[text(obs['custom']['usage'][key]) for key in ('n_input_tokens', 'n_cache_tokens', 'n_output_tokens', 'agent_execution_seconds', 'verifier_seconds')]]
         for obs in record['observations']]) + '</details>')
    parts.append('<p>Custom cross-run numeric comparisons and custom-metric history publication are disabled. '
                 'Incomplete required populations retain trial measurements but no aggregate comparison.</p>')
    return ''.join(parts)


def behavioral(run, records):
    rid = run['record_id']; record = records[rid]
    parts = [f'<article class="run" id="{anchor("record", rid)}"><h3>Behavioral run: ' + text(run['run_id']) + '</h3>',
        '<p>Evidence: <strong>' + text(run['availability']['status']) + '</strong>. Measurement: <strong>' +
        ('Recorded' if run['measured'] else 'Unmeasured') + '</strong>.</p>' + disclosure('Exact record identity', rid),
        '<p>Evaluated source: ' + text(run['source']['owner']) + ' · ' + code(run['source']['repository']) +
        ' · revision ' + code(run['source']['revision']) + '.</p>',
        '<p>Limitations: ' + limitations(run['availability']) + '</p>']
    custom_only = record.get('custom', {}).get('profile_id') is not None and record['policy']['fields']['grading'] == 'custom_only'
    if 'custom' in run: parts.append(custom_measurements(run, record))
    if run['native_metrics']:
        parts.append(table('Evaluator-reported metrics · original score units', ('Metric', 'Original value', 'Scope'),
            [[safe(m['name']), text(m['value']), 'With minus without' if m['name'] == 'Skill Lift' else 'With-skill dimension']
             for m in run['native_metrics']]))
    else:
        parts.append('<p>Standard judge metrics were not collected in custom-only mode.</p>' if custom_only else
                     '<p>Native metrics unavailable; no performance value is inferred.</p>')
    parts.append(table('Measured coverage by arm — unknown counts are not zero',
        ('Arm', 'Execution', 'Cases expected', 'Attempts expected', 'Recorded', 'Scored', 'Unscored') + (() if custom_only else ('Rubric cases passed / total',)),
        [[safe(ARM[a['name']]), text(a['execution_status']), text(a['coverage']['expected_cases']),
          text(a['coverage']['expected_attempts']), text(a['coverage']['recorded_attempts']),
          text(a['coverage']['scored_attempts']), text(a['coverage']['unscored_attempts'])] +
          ([] if custom_only else [text(a['rubric']['passed_cases']) + ' / ' + text(a['rubric']['total_cases'])]) for a in run['arms']]))
    summary = run['case_summary']; gates = run['gates']
    if custom_only:
        measured = sum(obs['custom']['outcome'] in evidence.CUSTOM_MEASURED for obs in record['observations'])
        parts.append('<p>' + text(measured) + ' trials with evaluated custom outcomes; ' +
            text(len(record['observations']) - measured) + ' retained trials without scoreable custom outcomes. '
            'Standard rubric dimensions were not collected. Applicable populations and comparison limits appear per metric above.</p>')
    else:
        parts.append('<p>' + count(summary['matched_cases'], 'matched case') + ' out of ' + text(summary['cohort_cases']) +
            '; ' + count(summary['scored_observations'], 'scored observation') + '. Mandatory gates: ' +
            text(len(gates['failed'])) + ' failed, ' + text(gates['passed_observations']) + ' passed, ' +
            text(gates['unknown_observations']) + ' unknown. Unknown gates do not count as passing.</p>')
    rows = []
    for case in summary['cases']:
        obs_links = '<br>'.join(link('observation', (rid, oid), context(record['source']['skill_id'], [case['case_id']]) +
                                   ' · ' + ARM[arm] + ' observation ' + oid)
            for arm, ids in case['observation_ids'].items() for oid in ids)
        rows.append([code(case['case_id']), quantity(case['arm_means']['with_skill']),
            quantity(case['arm_means']['without_skill']), quantity(case['with_minus_without']),
            ', '.join(code(v) for v in case['unavailable_reasons']) or 'Complete planned scores',
            disclosure('Exact derived quantities and support identities', case) + obs_links])
    if not custom_only: parts.append('<details><summary>All case scores and comparison coverage</summary><p>Descriptive arm means across complete planned attempts; '
        'with minus without. Attempts are not statistically paired. Missing or adaptive attempts suppress means. '
        'These case means do not reconstruct native Skill Lift.</p>' + table('Within-run case comparison',
        ('Case', 'With skill mean', 'Without skill mean', 'With minus without', 'Coverage limitations', 'Evidence'), rows) + '</details>')
    parts.extend([record_support(rid, record), '</article>'])
    return ''.join(parts)


def static_result(run, records):
    rid = run['record_id']
    parts = [f'<article class="run" id="{anchor("record", rid)}"><h3>Static checks</h3><p>Evidence ' +
        text(run['availability']['status']) + '. Static checks are not behavioral performance.</p>' + disclosure('Exact record identity', rid),
        '<p>Limitations: ' + limitations(run['availability']) + '</p>']
    parts.append('<p>Required by native evaluator is its risk policy, not the CI finding policy or a scanner process outcome. '
                 'Incomplete tool markers have unknown counts and are not additional findings.</p>')
    parts.append(table('Scanner outcomes — counts can include findings without public detail',
        ('Validator / tool marker', 'Native state', 'Required by native evaluator', 'Native passed', 'Critical / high / medium / low'),
        [[code(s['scanner']), text(s['status']), text(s.get('blocking', True)), text(s['passed']),
          ' / '.join(text(s['severity_counts'][k]) for k in ('critical', 'high', 'medium', 'low'))] for s in run['scans']]))
    parts.append('<details><summary>Structured static findings</summary>' + table('Public static finding details',
        ('Scanner / check', 'Severity', 'Member / line', 'Original reference'),
        [[f'<span id="{anchor("static-finding", rid, f["reference"])}">' + code(f['scanner']) + ' / ' + code(f['check']) + '</span>',
          text(f['severity']), code(f['member']) + ' / ' + text(f['line']),
          link('reference', (rid, f['reference']), records[rid]['source']['skill_id'] + ' · ' + f['scanner'] +
               ' reference ' + f['reference'])] for f in sorted(run['detailed_findings'], key=lambda f:
                   ((*analysis.SEVERITIES, 'info').index(f['severity']), f['scanner'], f['check'] or '', f['reference']))]) + '</details>')
    for scanner in sorted({f['scanner'] for f in run['detailed_findings']}):
        parts.append('<p>' + code(scanner) + ': ' + safe(analysis.static_guidance(scanner, None)) + '</p>')
    if any((f['scanner'], f['check']) == ('SCHEMA', 'author_missing') for f in run['detailed_findings']):
        parts.append('<p>' + safe(analysis.static_guidance('SCHEMA', 'author_missing')) + '</p>')
    parts.extend([record_support(rid, records[rid]), '</article>'])
    return ''.join(parts)


def comparisons(skill):
    parts = ['<h3>Cross-run comparisons</h3><p>' + safe(COMPARISON_STATUS[skill['comparison_status']]) + '</p>',
        '<p>Left and right follow semantic record identity order, not time. No chronology or trend is established. '
        'Direct compatibility means recorded conditions match; it does not establish causality, significance or repeatability.</p>']
    for pair in skill['comparisons']:
        parts.append('<details><summary>Comparison: ' + safe(pair['classification']) + '</summary><p>Comparison identity ' + code(pair['id']) +
            '</p><p>Left: ' + link('record', (pair['left_record_id'],), skill['skill'] + ' · left record ' + pair['left_record_id']) + '<br>Right: ' +
            link('record', (pair['right_record_id'],), skill['skill'] + ' · right record ' + pair['right_record_id']) + '</p>')
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
    parts = [f'<article class="run" id="{anchor("interpretation", item["record_id"])}"><h3>Model interpretation · analyst report</h3>'
        '<p class="notice"><strong>Model-generated judgment requiring human review.</strong> '
        'Valid citations do not prove a conclusion or instruction defect. '
        'Actions and validation plans are proposals.</p><p>Bound record: ' +
        link('record', (item['record_id'],), item['skill'] + ' · record ' + item['record_id']) + '</p><p>Analyst interpretation: <strong>' +
        presentation_label(assessment['disposition'], DISPOSITION_LABELS) + '</strong> · ' + count(len(judgment['recommendations']), 'recommendation') +
        '. Source owner: ' + text(report['provenance']['source_owner']) + '.</p>']
    parts.append('<p class="lead"><strong>Analyst conclusion:</strong> ' + text(assessment['interpretation']) + '</p>')
    for key, label in (('tested_benefit', 'Tested benefit · analyst interpretation'),
                       ('tested_harm', 'Tested harm · analyst interpretation'), ('uncertainty', 'Uncertainty')):
        parts.append('<p><strong>' + label + ':</strong> ' + text(assessment[key]) + '</p>')
    parts.append('<details><summary>Analyst reasoning, sufficiency and citations</summary>' + disclosure('Original analyst assessment', assessment) +
        disclosure('Native suggestions and analyst dispositions', judgment['native_suggestions']) +
        disclosure('Unverified external assertions', judgment['unverified_external_assertions']) + '</details>')
    if not judgment['recommendations']:
        parts.append('<p>No recommendations supplied. Approval is not established.</p>')
    for index, recommendation in enumerate(judgment['recommendations'], 1):
        parts.append('<div class="finding"><h4>Recommendation ' + str(index) + ' · proposal: ' + presentation_label(recommendation['category'], PROPOSAL_LABELS) +
            ' · ' + text(recommendation['priority']) + '</h4><p>' + text(recommendation['scope']) +
            '</p><details><summary>Rationale, risks and proposed validation</summary>')
        for key in ('justification', 'expected_benefit'):
            parts.append('<p><strong>' + safe(key.replace('_', ' ').capitalize()) + ':</strong> ' + text(recommendation[key]) + '</p>')
        parts.append(disclosure('Source targets, evidence, alternatives, risks and proposed validation',
            {k: v for k, v in recommendation.items() if k not in ('scope', 'justification', 'expected_benefit')}) + '</details></div>')
    parts.append(disclosure('Analyst provenance and original validation profile', {
        'profile': item['profile'], 'tooling_revision': item['tooling_revision'],
        'review_digest': item['review_digest'], 'markdown_digest': item['markdown_digest'],
        'provenance': report['provenance']}) + '<h4>Independent assessments · separately supplied</h4>'
        '<p>No authenticated human approval is established by this report. Authorship and independence are supplied '
        'attributions. Assessments are not aggregated and cannot change analyst qualification.</p>')
    if not item['assessments']:
        parts.append('<p>No independent assessments supplied for this analyst report.</p>')
    for supplied in item['assessments']:
        parts.append(f'<div class="assessment" id="{anchor("assessment", item["record_id"], supplied["id"])}"><h5>' +
            safe(ASSESSOR_LABELS[supplied['author_kind']]) + '</h5><p>' + assessment_summary(supplied) +
            '</p><details><summary>Assessment reasoning, rubric and provenance</summary>')
        parts.append(disclosure('Original assessment fields', {k: supplied[k] for k in
            ('author_kind', 'attribution', 'verdict', 'score', 'maximum')}))
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
        '<a class="skip" href="#main">Skip to report</a><header><p class="eyebrow">PRIVATE · OFFLINE</p>'
        '<h1>Skill evaluation report</h1>'
        '<div class="theme" id="theme-control" hidden><label for="theme">Appearance</label><select id="theme">'
        '<option value="system">System default</option><option value="light">Light</option><option value="dark">Dark</option>'
        '</select></div></header><main id="main" tabindex="-1"><section class="overview" aria-labelledby="overview">'
        '<h2 id="overview">Executive overview</h2>')
    skills = result['skills']; findings = result['findings']
    add(executive_summary(result, records, attached))
    add(
        '<details><summary>How to read the measures</summary><p>Evaluator-reported (native) metrics use the evaluator\'s original score units. '
        'Skill Lift is its with-minus-without difference. Grading criteria (rubric) and mandatory checks (gates) record separate outcomes. '
        'Effectiveness, Correctness and Discoverability are with-skill rubric dimensions; corresponding without-skill '
        'headline dimensions are not supplied by this public contract. Values are preserved, not recomputed from '
        'rounded case scores. Case deltas use descriptive arm means only where all planned attempts are scored. '
        'A positive delta is higher, a negative delta is lower; neither explains why. Mandatory gates are separate from rubric passes. '
        'Unknown counts, scores and gates stay unknown.</p></details>')
    add('</section>')
    for skill in skills:
        name = skill['skill']
        add(f'<section class="skill" id="{anchor("skill", name)}"><h2>' + safe(name) + '</h2>')
        if not any(r['measured'] for r in skill['behavioral_results']):
            add('<p class="notice"><strong>Unmeasured.</strong> No supplied model-backed measurement. Configuration and offline fixture replay do not establish skill benefit or harm.</p>')
        for config in skill['configurations']:
            suite = config['suite']
            add('<p>Inventory snapshot: ' + (count(suite['case_count'], 'configured case') + ' per arm' if suite else 'No behavioral suite configured') +
                '. Source owner: ' + text(config['source']['owner']) + '.</p>' + disclosure('Configuration identity and source snapshot', config))
        local = [f for f in findings if f['skill'] == name]
        add('<h3>Investigation priorities · deterministic findings</h3>' +
            priorities([f for f in local if f['importance'] != 'context'], records))
        context = [f for f in local if f['importance'] == 'context']
        if context:
            add('<details><summary>Evidence gaps and comparison limits</summary>' + priorities(context, records) + '</details>')
        skill_reviews = [row for row in attached.values() if row['skill'] == name]
        if skill_reviews:
            for row in skill_reviews:
                add(interpretation(row))
        else:
            add('<p>No analyst report supplied for this skill. Deterministic findings remain available; '
                'missing interpretation does not establish approval or absence of defects.</p>')
        for run in skill['behavioral_results']:
            add(behavioral(run, records))
        for run in skill['static_results']:
            add(static_result(run, records))
        if not skill['static_results']:
            add('<p>Static scan evidence not supplied for this skill; no clean-scan claim is made.</p>')
        add('<details><summary>Cross-run comparison status and evidence</summary>' + comparisons(skill) + '</details></section>')
    add('<section id="provenance"><h2>Report provenance and limitations</h2><p>Presentation method ' + code(METHOD) +
        '; analysis method ' + code(result['method_version']) +
        ('; public schemas 1/2 and analysis schema 2. Analysis semantic digest ' if result['schema_version'] == 2 else
         '; public and analysis schema version 1. Analysis semantic digest ') +
        code(evidence.identity(result)) + '.</p><p>Saved analysis was independently rebuilt against captured public originals before rendering. '
        'Canonical record identities preserve semantic content; raw-byte digests preserve the exact supplied files. '
        'These bindings do not attest remote execution. No local input paths, generation timestamp, prompts or private trajectories are embedded. '
        'Link identities are shortened for readability; exact identities remain in the evidence disclosures. '
        'Inventory snapshots and evaluated sources retain separate identities; current configuration does not rewrite historical runs.</p>')
    for rid, record in sorted(records.items()):
        if record['kind'] == 'inventory':
            add(f'<details id="{anchor("record", rid)}"><summary>Inventory record ' + safe(short_identity(rid)) + '</summary>' +
                disclosure('Validated inventory', record) + '</details>')
    add(disclosure('Input manifests, raw digests and record identities', result['input_provenance']) +
        disclosure('Analyzer comparison scope', result['comparison_scope']))
    global_findings = [f for f in findings if f['skill'] is None]
    if global_findings:
        add('<h3>Invocation-level investigation priorities</h3>' + priorities(global_findings, records))
    add(disclosure('Exact qualification status', {'quality_qualification': 'not_quality_qualified'}))
    add('<h3>Model-generated recommendations and assessment boundaries</h3><p>' + count(len(attached),
        'independently validated analyst report') + ' attached. All deterministic investigation priorities above remain fixed descriptions '
        'of existing findings and next-step codes. Analyst qualification: ' + presentation_label('not_quality_qualified', STATUS_LABELS) + '. '
        'Automated publication is ineligible. Supplied AI or human assessments are separately attributed opinions; structural validation, '
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
