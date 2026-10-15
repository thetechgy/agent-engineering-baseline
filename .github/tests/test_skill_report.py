"""Private HTML presentation over existing validated evidence; no inference."""

import copy
from datetime import datetime, timezone
from html.parser import HTMLParser
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import skill_analysis as analysis
import skill_evidence as evidence
import skill_report as report
import test_skill_analysis as fixtures

CLOCK = datetime(2026, 10, 14, tzinfo=timezone.utc)


class Document(HTMLParser):
    def __init__(self, value):
        super().__init__(convert_charrefs=True)
        self.elements = []; self.ids = []; self.links = []; self.content = []
        self.feed(value)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.elements.append((tag, attrs))
        if 'id' in attrs: self.ids.append(attrs['id'])
        if tag == 'a': self.links.append(attrs.get('href'))

    def handle_data(self, data):
        self.content.append(data)


class ReportTests(unittest.TestCase):
    bundle = fixtures.AnalysisTests.bundle

    @classmethod
    def setUpClass(cls):
        with patch.object(evidence, 'utc_now', return_value=CLOCK):
            cls.historical = evidence.project(evidence.normalize_behavioral(fixtures.FIXTURES / 'podman-native', 'podman'))
            cls.static = evidence.project(evidence.normalize_static(fixtures.FIXTURES / 'static-synthetic', 'podman'))
        cls.gh = evidence.read_json(fixtures.FIXTURES / 'gh-no-model.json')

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        clock = patch.object(evidence, 'utc_now', return_value=CLOCK)
        clock.start(); self.addCleanup(clock.stop)

    def analyze(self, *roots):
        captured = analysis.capture_inputs(roots)
        return analysis.validate_analysis(None, captured), captured

    def render(self, records, configs=None):
        result, captured = self.analyze(self.bundle('input', records, configs))
        return report.render_report(result, captured).decode(), result, captured

    def demo(self):
        configs = [fixtures.configuration('podman', self.historical['dataset']['case_ids'], self.historical['source']),
                   fixtures.configuration('gh', self.gh['dataset']['case_ids'], self.gh['source'])]
        configs.append({'source': fixtures.synthetic_source('unconfigured'), 'deployment': None, 'suite': None,
                       'behavioral_status': 'not_configured', 'measurement': {'status': 'unavailable', 'reasons': ['results_not_supplied']}})
        measured = self.bundle('demo-measured', [self.historical, self.static], configs)
        unmeasured = self.bundle('demo-unmeasured', [self.gh], flat=True)
        result, captured = self.analyze(measured, unmeasured)
        return report.render_report(result, captured).decode(), result, captured

    def test_historical_demo_preserves_metrics_coverage_and_all_skills(self):
        output, result, captured = self.demo()
        plain = ' '.join(Document(output).content)
        for value in ('podman', 'gh', 'unconfigured', '24 configured cases', 'No behavioral suite configured',
                      '0.1207', '0.773', '0.96', '0.6937', '-0.0346', '-0.0134', '10 / 10', '8 / 10',
                      '20 scored observations', 'Unmeasured', 'available', 'synthetic_rule', 'SECRETS',
                      'scan_incomplete', 'source_unavailable', 'Unknown / not supplied', 'No supplied model-backed measurement'):
            self.assertIn(value, plain)
        self.assertNotIn(str(self.root), output)
        self.assertNotIn('Synthetic diagnostic excluded', output)
        self.assertNotIn('trajectory.json', output)
        self.assertNotIn('original_extract', output)
        self.assertIn(report.METHOD, output)
        self.assertIn(evidence.identity(result), output)
        for rid, record in captured.records.items():
            self.assertIn(rid, output)
            if record['kind'] != 'inventory':
                if record['source']['source_path']: self.assertIn(record['source']['source_path'], output)
                if record['policy']['id']: self.assertIn(record['policy']['id'], output)
                for observation in record['observations']: self.assertIn(observation['id'], output)
                for reference in record['references']: self.assertIn(reference['id'], output)

    def test_deterministic_root_order_and_rerender(self):
        a = self.bundle('a', [self.historical]); b = self.bundle('b', [self.gh], flat=True)
        first, captured = self.analyze(a, b)
        second, other = self.analyze(b, a)
        self.assertEqual(report.render_report(first, captured), report.render_report(second, other))
        self.assertEqual(report.render_report(first, captured), report.render_report(copy.deepcopy(first), captured))

    def test_overview_separates_coverage_safety_and_investigations(self):
        output, _, _ = self.demo()
        overview = output.split('<section class="overview"', 1)[1].split('</section>', 1)[0]
        plain = ' '.join(Document(overview).content)
        for value in ('Measured results', 'Configured; results not supplied', 'No configured suite',
                      '24 configured cases per arm', '0 failed · 0 passed · 20 unknown',
                      'Safety evidence is incomplete', 'Not quality qualified',
                      'Authenticated human approval is not established', 'What remains unknown'):
            self.assertIn(value, plain)
        self.assertLess(plain.index('20 unknown'), plain.index('Important findings'))
        important = overview.split('Important findings', 1)[1].split('What remains unknown', 1)[0]
        self.assertIn('Lower with-skill case score', important)
        self.assertNotIn('Comparison unavailable or limited', important)

    def passing_gates(self, maximum=1):
        record = fixtures.synthetic(name='gh', maximum=maximum)
        for obs in record['observations']:
            obs['deterministic_gate'] = 1
            obs['deterministic_scores'] = dict.fromkeys(evidence.GATE_FIELDS, 1)
        return record

    def test_production_safety_banner_flags_missing_coverage_without_inventing_counts(self):
        for scenario, passed in (('missing-attempt', 5), ('configured-without-run', 2)):
            with self.subTest(scenario=scenario):
                record = self.passing_gates(maximum=3 if scenario == 'missing-attempt' else 1)
                configs = None
                if scenario == 'missing-attempt':
                    record['observations'].pop()
                    fixtures.reconcile(record, partial=True)
                else:
                    configs = [fixtures.configuration('gh'), fixtures.configuration('unmeasured')]
                root = self.bundle(scenario, [record], configs)
                result, captured = self.analyze(root)
                identities = (evidence.identity(result), evidence.identity(captured.records))
                saved = self.root / (scenario + '-analysis') / 'analysis.json'
                fixtures.write(saved, result)
                destination = report.generate([root], saved, self.root / (scenario + '-output'))
                output = (destination / 'report.html').read_bytes()
                banner = output.decode().split('<div class="safety">', 1)[1].split('</div>', 1)[0]
                self.assertIn('Safety evidence is incomplete', banner)
                self.assertIn(f'Among recorded observations: 0 failed · {passed} passed · 0 unknown', banner)
                self.assertIn('Missing execution coverage is excluded from these counts', banner)
                self.assertEqual(output, report.render_report(result, captured))
                self.assertEqual(identities, (evidence.identity(result), evidence.identity(captured.records)))

    def test_safety_banner_flags_partial_unknown_and_unmeasured_run_coverage(self):
        for scenario, passed in (('partial-details', 1), ('unknown-expected-count', 2),
                                 ('unknown-attempt-identity', 2), ('unmeasured-run', 2)):
            with self.subTest(scenario=scenario):
                record = self.passing_gates()
                if scenario == 'partial-details':
                    coverage = [copy.deepcopy(arm['coverage']) for arm in record['arms']]
                    record['observations'].pop()
                    fixtures.reconcile(record, partial=True)
                    for arm, original in zip(record['arms'], coverage):
                        arm['coverage'] = {**original, 'case_details': 'partial'}
                elif scenario == 'unknown-expected-count':
                    policy = record['policy']; policy['attempts']['maximum'] = None
                    policy['id'] = evidence.identity({key: policy[key] for key in
                        ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
                    fixtures.reconcile(record, partial=True)
                elif scenario == 'unknown-attempt-identity':
                    record['observations'][0]['attempt'] = None
                    fixtures.reconcile(record)
                roots = [self.bundle(scenario, [record])]
                if scenario == 'unmeasured-run':
                    roots.append(self.bundle(scenario + '-snapshot', [self.gh], flat=True))
                result, captured = self.analyze(*roots)
                output = report.render_report(result, captured).decode()
                banner = output.split('<div class="safety">', 1)[1].split('</div>', 1)[0]
                self.assertIn('Safety evidence is incomplete', banner)
                self.assertIn(f'Among recorded observations: 0 failed · {passed} passed · 0 unknown', banner)

    def test_complete_passing_coverage_does_not_infer_missing_unconfigured_suite(self):
        unconfigured = {'source': fixtures.synthetic_source('unconfigured'), 'deployment': None, 'suite': None,
            'behavioral_status': 'not_configured', 'measurement': {'status': 'unavailable', 'reasons': ['results_not_supplied']}}
        output, _, _ = self.render([self.passing_gates()], [fixtures.configuration('gh'), unconfigured])
        banner = output.split('<div class="safety">', 1)[1].split('</div>', 1)[0]
        self.assertIn('Recorded mandatory gate outcomes', banner)
        self.assertIn('Among recorded observations: 0 failed · 2 passed · 0 unknown', banner)
        self.assertNotIn('Safety evidence is incomplete', banner)
        self.assertNotIn('Missing execution coverage', banner)
        self.assertIn('Zero recorded failures does not establish safety', banner)

    def test_complete_gate_coverage_is_independent_of_metrics_and_rubric_scores(self):
        for scenario in ('missing-headline-metric', 'missing-rubric-scores'):
            with self.subTest(scenario=scenario):
                record = self.passing_gates()
                if scenario == 'missing-headline-metric':
                    record['metrics'].pop()
                    record['availability'].update(status='incomplete', reasons=['coverage_missing'])
                else:
                    for obs in record['observations']:
                        obs['score'] = obs['scores']['overall'] = obs['rubric_pass'] = None
                    fixtures.reconcile(record)
                root = self.bundle(scenario, [record])
                result, captured = self.analyze(root)
                self.assertTrue(any(f['kind'] == 'incomplete_execution' for f in result['findings']))
                saved = self.root / (scenario + '-analysis') / 'analysis.json'
                fixtures.write(saved, result)
                destination = report.generate([root], saved, self.root / (scenario + '-output'))
                output = (destination / 'report.html').read_text()
                banner = output.split('<div class="safety">', 1)[1].split('</div>', 1)[0]
                self.assertIn('Recorded mandatory gate outcomes', banner)
                self.assertIn('Among recorded observations: 0 failed · 2 passed · 0 unknown', banner)
                self.assertNotIn('Safety evidence is incomplete', banner)
                self.assertNotIn('Missing execution coverage', banner)

    def test_security_component_investigation_uses_recorded_single_attempt_scores(self):
        record = fixtures.synthetic(scores=(.7, .8))
        for obs in record['observations']:
            obs['scores']['security'] = 0.0 if obs['arm'] == 'with_skill' else .5
        output, _, _ = self.render([record])
        plain = ' '.join(Document(output).content)
        self.assertIn('Security-component score', plain)
        self.assertIn('0.0 with skill versus 0.5 without skill', plain)
        self.assertIn('Grader judgments', plain)
        self.assertIn('Inspect the security judgment separately', plain)
        self.assertNotIn('proven unsafe', plain)
        self.assertIn('href="#components-', output)
        document = Document(output)
        self.assertTrue(all(href[1:] in document.ids for href in document.links))

    def test_security_investigation_does_not_infer_missing_or_adaptive_comparisons(self):
        for maximum, scores in ((1, (None, .5)), (1, (.5, .5)), (3, (0.0, .5))):
            record = fixtures.synthetic(maximum=maximum)
            for obs in record['observations']:
                obs['scores']['security'] = scores[0 if obs['arm'] == 'with_skill' else 1]
            output, _, _ = self.render([record])
            self.assertNotIn('Security-component score · case', output)

    def test_mandatory_findings_precede_component_investigations(self):
        record = fixtures.synthetic(name='gh')
        for obs in record['observations']:
            obs['scores']['security'] = 0.0 if obs['arm'] == 'with_skill' else .5
        obs = record['observations'][0]
        obs['deterministic_gate'] = 0
        obs['deterministic_scores'] = dict.fromkeys(evidence.GATE_FIELDS, 1)
        obs['deterministic_scores'].update(authorization=0, gate=0)
        output, _, _ = self.render([record])
        overview = output.split('<section class="overview"', 1)[1].split('</section>', 1)[0]
        self.assertLess(overview.index('Failed mandatory gate'), overview.index('Security-component score · case'))

    def test_context_findings_and_exact_identities_remain_disclosed(self):
        output, result, _ = self.demo()
        self.assertIn('<summary>Evidence gaps and comparison limits</summary>', output)
        for finding in result['findings']:
            self.assertIn(finding['id'], output)
        self.assertIn('shortened for readability', output)
        self.assertIn('a.hash', report.JS)
        self.assertIn('parent.open = true', report.JS)

    def test_all_internal_links_resolve_without_duplicate_ids(self):
        output, _, _ = self.demo()
        document = Document(output)
        self.assertEqual(len(document.ids), len(set(document.ids)))
        self.assertTrue(document.links)
        for href in document.links:
            self.assertTrue(href.startswith('#'), href)
            self.assertIn(href[1:], document.ids)
        # Shared source/reference members across records must not collide.
        output, _, _ = self.render([fixtures.synthetic(run='a'), fixtures.synthetic(run='b')])
        document = Document(output)
        self.assertEqual(len(document.ids), len(set(document.ids)))

    def test_accessible_document_structure_and_theme_assets(self):
        output, _, _ = self.demo()
        document = Document(output)
        self.assertIn(('html', {'lang': 'en'}), document.elements)
        tags = [tag for tag, _ in document.elements]
        self.assertEqual(tags.count('h1'), 1)
        self.assertEqual(tags.count('main'), 1)
        self.assertEqual(tags.count('table'), tags.count('caption'))
        for tag, attrs in document.elements:
            if tag == 'th': self.assertIn(attrs.get('scope'), ('row', 'col'))
            if tag == 'select': self.assertEqual(attrs['id'], 'theme')
        self.assertIn(('label', {'for': 'theme'}), document.elements)
        self.assertIn('Skip to report', output)
        for value in ('prefers-color-scheme:dark', '[data-theme=dark]', '[data-theme=light]', ':focus-visible',
                      'overflow-wrap:anywhere', 'max-width:40rem', 'System default', 'Light', 'Dark'):
            self.assertIn(value, output)
        self.assertNotIn('localStorage', report.JS)
        self.assertNotIn('fetch(', report.JS)

    def test_palette_contrast_in_both_themes(self):
        def luminance(color):
            if len(color) == 4: color = '#' + ''.join(c * 2 for c in color[1:])
            channels = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
            linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
            return sum(v * weight for v, weight in zip(linear, (.2126, .7152, .0722)))
        def contrast(a, b):
            x, y = sorted((luminance(a), luminance(b)))
            return (y + .05) / (x + .05)
        palettes = re.findall(r':root(?:\[data-theme=dark\])?\{([^}]+)\}', report.CSS)
        self.assertEqual(len(palettes), 2)
        for declarations in palettes:
            palette = dict(re.findall(r'--([a-z]+):(#[a-f0-9]+)', declarations))
            backgrounds = [palette[key] for key in ('bg', 'surface')]
            texts = [palette[key] for key in ('text', 'muted', 'accent', 'alert')]
            border = palette['line']
            for background in backgrounds:
                for color in texts: self.assertGreaterEqual(contrast(background, color), 4.5)
                self.assertGreaterEqual(contrast(background, border), 3)

    def test_fixed_csp_hashes_and_no_active_evidence(self):
        output, _, _ = self.demo()
        document = Document(output)
        policy = next(a['content'] for tag, a in document.elements if tag == 'meta' and a.get('http-equiv') == 'Content-Security-Policy')
        for item in ("default-src 'none'", "base-uri 'none'", "object-src 'none'", "form-action 'none'",
                     "connect-src 'none'", "style-src 'sha256-" + report.asset_hash(report.CSS) + "'",
                     "script-src 'sha256-" + report.asset_hash(report.JS) + "'"):
            self.assertIn(item, policy)
        self.assertNotIn('unsafe-inline', policy)
        self.assertNotIn('unsafe-eval', policy)
        self.assertEqual(sum(t == 'script' for t, _ in document.elements), 1)
        self.assertEqual(sum(t == 'style' for t, _ in document.elements), 1)
        for tag, attrs in document.elements:
            self.assertNotIn(tag, ('iframe', 'object', 'embed', 'img', 'form', 'link'))
            self.assertFalse(any(k.startswith('on') or k in ('src', 'srcdoc') for k in attrs))
        hostile = '</pre><script>alert(1)</script><img src=x onerror=alert(2)> & "'
        escaped = report.disclosure(hostile, {'member': hostile})
        self.assertNotIn('<script>', escaped)
        self.assertNotIn('<img', escaped)
        self.assertIn('&lt;script&gt;', escaped)
        self.assertIn('&quot;', escaped)

    def test_render_boundary_rejects_corruption_instead_of_trusting_analysis(self):
        _, result, captured = self.demo()
        mutations = [lambda r: r.update(schema_version=2), lambda r: r.update(method_version='invented'),
                     lambda r: r['skills'].pop(), lambda r: r['findings'].pop(),
                     lambda r: r['input_provenance'][0]['members'][0].update(raw_digest=evidence.identity('changed'))]
        podman_index = next(i for i, s in enumerate(result['skills']) if s['skill'] == 'podman')
        mutations.append(lambda r: r['skills'][podman_index]['behavioral_results'][0]['native_metrics'][0].update(value=0.99))
        mutations.append(lambda r: r['skills'][podman_index]['behavioral_results'][0]['case_summary']['cases'][0]['observation_ids'].update(with_skill=[]))
        for mutate in mutations:
            changed = copy.deepcopy(result); mutate(changed)
            with self.assertRaises(ValueError): report.render_report(changed, captured)
        rid = next(rid for rid, r in captured.records.items() if r['kind'] == 'inventory')
        captured.records[rid]['skills'][0]['source']['skill_id'] = '<script>'
        with self.assertRaises(ValueError): report.render_report(result, captured)

    def test_failed_gate_not_confused_with_rubric_or_unknown_gate(self):
        record = fixtures.synthetic(name='gh')
        observation = record['observations'][0]
        observation['deterministic_scores'] = dict.fromkeys(evidence.GATE_FIELDS, 1)
        observation['deterministic_scores'].update(authorization=0, recovery=0, gate=0)
        observation['deterministic_gate'] = 0
        output, _, _ = self.render([record])
        for value in ('Failed mandatory gate', '1 failed, 0 passed, 1 unknown', 'authorization', 'recovery', '1 / 1',
                      'inspect_gate_evidence', 'A grader failure is not automatically'):
            self.assertIn(value, output)

    def test_partial_and_adaptive_evidence_never_gets_invented_case_delta(self):
        for name in ('partial', 'adaptive'):
            with self.subTest(name=name):
                record = fixtures.synthetic(run=name, maximum=3)
                if name == 'partial':
                    record['observations'].pop(); fixtures.reconcile(record, partial=True)
                else:
                    record['policy']['attempts']['stop_on_pass'] = True
                    record['policy']['fields']['stop_on_pass'] = True
                    record['policy']['id'] = evidence.identity({k: record['policy'][k] for k in
                        ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
                result, captured = self.analyze(self.bundle(name, [record]))
                output = report.render_report(result, captured).decode()
                self.assertIn('Unavailable', output)
                self.assertIn('planned_attempts_missing' if name == 'partial' else 'adaptive_or_unknown_stopping', output)
                self.assertIsNone(result['skills'][0]['behavioral_results'][0]['case_summary']['cases'][0]['with_minus_without'])

    def test_comparisons_preserve_classification_delta_direction_and_no_chronology(self):
        for mode in ('direct', 'exploratory', 'incompatible', 'too-many'):
            records = [fixtures.synthetic(run='left'), fixtures.synthetic(run='right', scores=(.7, .6))]
            if mode == 'exploratory':
                records[1]['arms'][0]['condition']['instruction_digest'] = None
                c = records[1]['arms'][0]['condition']; c['id'] = evidence.identity({k: v for k, v in c.items() if k != 'id'})
            if mode == 'incompatible': records[1]['dataset']['authored_digest'] = evidence.identity('changed')
            if mode == 'too-many': records.append(fixtures.synthetic(run='third'))
            result, captured = self.analyze(self.bundle(mode, records))
            output = report.render_report(result, captured).decode()
            self.assertIn('not time', output)
            self.assertIn('No chronology or trend', output)
            pairs = result['skills'][0]['comparisons']
            if mode == 'too-many':
                self.assertEqual(pairs, [])
                self.assertIn('More than two measured runs supplied', output)
            else:
                pair = pairs[0]
                expected = {'direct': 'directly_comparable', 'exploratory': 'exploratory', 'incompatible': 'incompatible_or_unknown'}[mode]
                self.assertIn(expected, output)
                self.assertIn(pair['id'], output)
                for row in pair['native_metrics']:
                    if mode != 'direct': self.assertIsNone(row['right_minus_left'])
                for row in pair['cases']:
                    for delta in row['right_minus_left'].values():
                        if delta: self.assertIn(report.quantity(delta), output)

    def test_negative_value_rounding_to_zero_still_exposes_direction(self):
        record = fixtures.synthetic(scores=(.600001, .600002))
        output, _, _ = self.render([record])
        self.assertIn('-0.0000</code> (negative)', output)
        self.assertIn('Lower with-skill case score', output)

    def test_counts_in_empty_single_and_multiple_skill_presentations(self):
        for count in (0, 1, 2):
            with self.subTest(count=count):
                roots = self.bundle('counts-' + str(count),
                    [fixtures.synthetic(name='skill-' + str(i), cases=('1',) if count == 1 else ('1', '2'))
                     for i in range(count)])
                result, captured = self.analyze(roots)
                output = report.render_report(result, captured).decode()
                plain = ' '.join(Document(output).content)
                self.assertIn(f'{count} ' + ('skill represented' if count == 1 else 'skills represented'), plain)
                self.assertIn('0 independently validated analyst reports attached', plain)
                if count:
                    self.assertIn(f'{count} matched ' + ('case out of 1' if count == 1 else 'cases out of 2'), plain)
                self.assertNotIn('1 cases', plain)
                self.assertNotIn('1 skills', plain)

    def test_recorded_outcomes_use_explicit_unknown_and_retain_original_values(self):
        for gate, rubric, expected_gate, expected_rubric in (
                (0, False, 'Failed', 'Failed'), (1, True, 'Passed', 'Passed'),
                (None, None, 'Unknown', 'Unknown')):
            with self.subTest(gate=gate, rubric=rubric):
                record = fixtures.synthetic(name='gh', run='outcome-' + str(gate),
                                            scores=(.8, .8) if rubric else (.1, .1))
                for obs in record['observations']:
                    obs['rubric_pass'] = rubric
                    obs['deterministic_gate'] = gate
                    obs['deterministic_scores'] = dict.fromkeys(evidence.GATE_FIELDS, gate)
                    if rubric is None:
                        obs['score'] = obs['scores']['overall'] = None
                fixtures.reconcile(record)
                output, _, _ = self.render([record])
                self.assertIn(f'<td>{expected_rubric}</td><td>{expected_gate}</td>', output)
                self.assertIn(report.disclosure('Exact observation outcomes', {
                    'rubric_pass': rubric, 'deterministic_gate': gate}), output)
                if rubric is None:
                    self.assertIn('0 matched cases out of 1; 0 scored observations.', output)

    def test_numeric_precision_and_positive_zero_direction_remain_visible(self):
        record = fixtures.synthetic(scores=(.600002, .600001))
        record['metrics'][0]['value'] = .123456789
        output, _, _ = self.render([record])
        self.assertIn('0.123456789', output)
        self.assertIn('+0.0000</code> (positive)', output)

    def test_configured_single_case_uses_singular(self):
        output, _, _ = self.render([fixtures.synthetic()], [fixtures.configuration('alpha')])
        self.assertIn('1 configured case per arm', output)
        self.assertNotIn('1 configured cases', output)

    def test_rendering_preserves_analysis_and_capture_identities(self):
        _, result, captured = self.demo()
        before = (evidence.identity(result), evidence.identity(captured.records))
        report.render_report(result, captured)
        self.assertEqual(before, (evidence.identity(result), evidence.identity(captured.records)))

    def test_contextual_links_identify_skill_and_case(self):
        output, _, _ = self.render([fixtures.synthetic(scores=(.4, .6))])
        for label in ('alpha · measured results and coverage', 'alpha · case 1 · finding and next step',
                      'alpha · case 1 · With skill observation', 'alpha · case 1 · reference'):
            self.assertIn(label, output)
        tags = [tag for tag, _ in Document(output).elements if re.fullmatch('h[1-6]', tag)]
        for previous, current in zip(tags, tags[1:]):
            self.assertLessEqual(int(current[1]), int(previous[1]) + 1)

    def test_code_labels_translate_only_recognized_codes(self):
        for raw, labels, expected in (
                ('skill_change', report.DISPOSITION_LABELS, 'Skill change'),
                ('no_change', report.DISPOSITION_LABELS, 'No change'),
                ('modify_skill', report.PROPOSAL_LABELS, 'Modify skill'),
                ('improve_eval', report.PROPOSAL_LABELS, 'Improve evaluation'),
                ('fix_grader_or_harness', report.PROPOSAL_LABELS, 'Fix grader or harness')):
            self.assertEqual(report.presentation_label(raw, labels), expected)
        for labels in (report.STATUS_LABELS, report.DISPOSITION_LABELS, report.PROPOSAL_LABELS):
            unfamiliar = 'Unfamiliar_Judgment: Keep <This> VERBATIM.'
            self.assertEqual(report.presentation_label(unfamiliar, labels), report.safe(unfamiliar))

    def test_expired_references_remain_expired_and_stale_analysis_rejects(self):
        future = datetime(2026, 10, 20, tzinfo=timezone.utc)
        # Expiration does not change reference identity or historical numeric scores.
        expired = copy.deepcopy(self.historical)
        for reference in expired['references']: reference['availability'] = 'expired'
        expired['availability']['status'] = 'incomplete'
        expired['availability']['reasons'].append('reference_expired')
        with patch.object(evidence, 'utc_now', return_value=future):
            result, captured = self.analyze(self.bundle('expired', [expired]))
            output = report.render_report(result, captured).decode()
            self.assertIn('Original artifact references have expired', output)
            self.assertIn('0.1207', output)
            self.assertIn('retain_or_reacquire_exact_evidence', output)
            stale = self.bundle('stale-availability', [self.historical])
            with self.assertRaises(ValueError): analysis.capture_inputs([stale])

    def test_invocation_comparison_limit_explains_suppression(self):
        records = [fixtures.synthetic('skill-' + str(i), 'run-' + arm) for i in range(17) for arm in ('a', 'b')]
        output, result, _ = self.render(records)
        self.assertIn('More than 16 eligible skill pairs supplied', output)
        self.assertIn('supply_at_most_16_skill_pairs', output)
        self.assertEqual(result['comparison_scope']['performed_pairs'], 0)

    def test_all_deterministic_next_steps_have_presentation_copy(self):
        # Exercise the analyzer's producers, not a duplicate finding engine.
        output, result, captured = self.demo()
        record = fixtures.synthetic(name='gh')
        obs = record['observations'][0]
        obs['deterministic_scores'] = dict.fromkeys(evidence.GATE_FIELDS, 0)
        obs['deterministic_gate'] = 0
        extra, _, _ = self.render([record])
        self.assertIn('inspect_gate_evidence', extra)
        self.assertTrue(all(f['next_step'] in report.NEXT_STEPS and f['kind'] in report.FINDING_LABELS for f in result['findings']))
        self.assertIn('Model-generated recommendations', output)
        self.assertIn('0 independently validated analyst reports attached', output)
        self.assertIn('not_quality_qualified', output)

    def test_empty_inventory_and_html_limit_fail_without_truncation(self):
        result, captured = self.analyze(self.bundle('empty', configs=[]))
        output = report.render_report(result, captured).decode()
        self.assertIn('supplied inventory is empty', output)
        banner = output.split('<div class="safety">', 1)[1].split('</div>', 1)[0]
        self.assertIn('Safety evidence is incomplete', banner)
        self.assertIn('No recorded gate outcomes supplied', banner)
        with patch.object(report, 'HTML_LIMIT', 64):
            with self.assertRaisesRegex(ValueError, 'HTML report size exceeded'): report.render_report(result, captured)

    def saved(self, result):
        path = self.root / 'analysis/analysis.json'; fixtures.write(path, result)
        return path

    def test_production_cli_secure_private_output_and_no_bytecode(self):
        records = [fixtures.synthetic(), self.static]
        # Subprocesses use the real clock; success inputs must never expire.
        for record in records:
            evidence.validate_evidence(record, public=True, _observed_at=datetime.max.replace(tzinfo=timezone.utc))
        root = self.bundle('cli', records)
        result, captured = self.analyze(root)
        saved = self.saved(result); destination = self.root / 'output'
        command = [sys.executable, str(Path(report.__file__)), '--input', str(root), '--analysis', str(saved), '--output', str(destination)]
        environment = dict(os.environ); environment.pop('PYTHONDONTWRITEBYTECODE', None)
        before = sorted(Path(report.__file__).parent.rglob('*.pyc'))
        process = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=30)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(before, sorted(Path(report.__file__).parent.rglob('*.pyc')))
        self.assertEqual(sorted(p.name for p in destination.iterdir()), ['report.html'])
        self.assertEqual(destination.stat().st_mode & 0o777, 0o700)
        self.assertEqual((destination / 'report.html').stat().st_mode & 0o777, 0o600)
        self.assertEqual((destination / 'report.html').read_bytes(), report.render_report(result, captured))
        self.assertNotIn(str(saved), (destination / 'report.html').read_text())
        repeated = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertEqual(repeated.returncode, 1)
        self.assertEqual(repeated.stderr, 'Report contract rejected; no HTML report is ready.\n')

    def test_duplicate_analysis_json_keys_and_unknown_public_fields_fail_no_output(self):
        root = self.bundle('bad', [fixtures.synthetic()])
        result, _ = self.analyze(root); saved = self.saved(result)
        for corruption in ('duplicate', 'public-extra', 'stale'):
            fixtures.write(saved, result)
            if corruption == 'duplicate':
                raw = saved.read_text(); saved.write_text(raw.replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1', 1))
            elif corruption == 'public-extra':
                member = next(root.rglob('public-report.json')); data = evidence.read_json(member)
                data['prompt'] = 'private raw input'; fixtures.write(member, data)
            else:
                # Remove the extra field and change an authoritative public native metric.
                data.pop('prompt'); data['metrics'][0]['value'] = .3; fixtures.write(member, data)
            destination = self.root / corruption
            with self.assertRaises(ValueError): report.generate([root], saved, destination)
            self.assertFalse(destination.exists())

    def test_input_replacement_and_output_overlap_reject(self):
        root = self.bundle('guarded', [fixtures.synthetic()])
        result, _ = self.analyze(root); saved = self.saved(result)
        for destination in (root / 'output', saved.parent / 'output', evidence.ROOT / 'private-report-test'):
            with self.assertRaises(ValueError): report.generate([root], saved, destination)
            self.assertFalse(destination.exists())
        actual = report.render_report
        def replace(result, captured):
            rendered = actual(result, captured)
            saved.write_bytes(saved.read_bytes())  # Same bytes, changed metadata.
            return rendered
        with patch.object(report, 'render_report', side_effect=replace):
            with self.assertRaises(ValueError): report.generate([root], saved, self.root / 'changed')
        self.assertFalse((self.root / 'changed').exists())

    def test_linked_analysis_and_public_inputs_reject(self):
        root = self.bundle('links', [fixtures.synthetic()])
        result, _ = self.analyze(root); saved = self.saved(result)
        linked = self.root / 'linked.json'; linked.symlink_to(saved)
        with self.assertRaises(ValueError): report.generate([root], linked, self.root / 'linked-out')
        member = next(root.rglob('public-report.json')); original = member.read_bytes()
        member.unlink(); member.symlink_to(saved)
        with self.assertRaises(ValueError): report.generate([root], saved, self.root / 'linked-public-out')
        self.assertTrue(original)

    def test_public_credentials_and_active_payloads_fail_closed(self):
        for name, mutation in (
            ('credential', lambda r: r['policy']['fields'].update(model='sk-' + 'a' * 48)),
            ('active', lambda r: r['source'].update(source_path='javascript:alert(1)'))):
            record = fixtures.synthetic(); mutation(record)
            record['policy']['id'] = evidence.identity({k: record['policy'][k] for k in
                ('fields', 'patch_digest', 'metric_set', 'judge', 'attempts')})
            root = self.bundle(name, [record])
            with self.assertRaises(ValueError): self.analyze(root)

    def test_cli_rejects_without_echoing_untrusted_paths(self):
        process = subprocess.run([sys.executable, '-B', report.__file__, '--input', '/private/user/value',
                                  '--analysis', '/private/user/analysis', '--unexpected-secret'],
                                 capture_output=True, text=True, timeout=30)
        self.assertEqual(process.returncode, 2)
        self.assertNotIn('/private', process.stderr)
        self.assertNotIn('secret', process.stderr)


if __name__ == '__main__':
    unittest.main()
