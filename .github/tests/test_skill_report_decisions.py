"""Exercise decision rendering through the offline CLI with retained evidence."""

from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_skill_report import Document
import skill_report_decisions as decisions

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / 'docs/evaluations'
TRANSFER = DOCS / 'pester-transfer-decision/execution-v6/data'
DEVELOPMENT = DOCS / 'pester-return-contract-development'
MANIFEST = DOCS / 'report-decisions.json'
TRANSFER_INPUTS = [TRANSFER / 'current', TRANSFER / 'candidate']
DEVELOPMENT_INPUTS = [DEVELOPMENT / 'data' / name for name in
                      ('historical-development-current', 'pester-return-development-candidate-v1')]
STAGE_ONE_INPUTS = [DEVELOPMENT / name / 'data' for name in ('stage-1-sol62', 'stage-1-1710-sol62')]
analysis = decisions.analysis
evidence = decisions.evidence
ALL_INPUTS = decisions.manifest_inputs(evidence.read_json(MANIFEST), DOCS)
COMPANION_INPUTS = [path for path in ALL_INPUTS
                    if path not in (*TRANSFER_INPUTS, *DEVELOPMENT_INPUTS, *STAGE_ONE_INPUTS)]


def decision_for(manifest, skill, case):
    return next(card for card in manifest['decisions'] if (card['skill'], card['case']) == (skill, case))


class Section:
    def __init__(self, tag='', attrs=()):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []
        self.chunks = []

    @property
    def text(self):
        return ' '.join(''.join(self.chunks).split())

    def find_all(self, tag):
        for child in self.children:
            if child.tag == tag:
                yield child
            yield from child.find_all(tag)

    def links(self):
        return {(link.text, link.attrs.get('href')) for link in self.find_all('a')}


class ReportSections(HTMLParser):
    # Keep report sections, headings, and table cells. Inline formatting does
    # not affect how a label, decision, or score is read.
    TAGS = {'a', 'article', 'caption', 'div', 'h3', 'p', 'section', 'strong', 'table', 'td', 'th', 'tr'}

    def __init__(self, html):
        super().__init__()
        self.root = Section()
        self.stack = [self.root]
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        if tag in self.TAGS:
            section = Section(tag, attrs)
            self.stack[-1].children.append(section)
            self.stack.append(section)

    def handle_endtag(self, tag):
        if tag in self.TAGS and self.stack[-1].tag == tag:
            self.stack.pop()

    def handle_data(self, data):
        for section in self.stack:
            section.chunks.append(data)


def citations(value):
    if isinstance(value, dict):
        if value.keys() == {'label', 'url'}:
            yield value['label'], value['url']
        else:
            for child in value.values():
                yield from citations(child)
    elif isinstance(value, list):
        for child in value:
            yield from citations(child)


def record_id(bundle):
    return evidence.identity(evidence.read_json(bundle / 'public-report.json'))


class DecisionReportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def run_report(self, inputs, manifest=MANIFEST, *, replay=None, name='html', expected_exit=0):
        inputs = [*inputs, *(path for path in COMPANION_INPUTS if path not in inputs)]
        captured = analysis.capture_inputs(inputs)
        saved = self.root / 'analysis' / 'analysis.json'
        saved.parent.mkdir(exist_ok=True)
        saved.write_bytes(evidence.encoded(analysis.build_analysis(captured)))
        destination = self.root / name
        argv = [sys.executable, '-B', str(ROOT / '.github/scripts/skill_report_decisions.py'),
                '--analysis', str(saved), '--decisions', str(manifest), '--output', str(destination)]
        for path in inputs:
            argv.extend(['--input', str(path)])
        if replay is not None:
            argv.extend(['--replay', str(replay)])
        process = subprocess.run(argv, capture_output=True, text=True, check=False)
        self.assertEqual(process.returncode, expected_exit, process.stderr)
        if expected_exit:
            self.assertFalse(destination.exists())
            return process.stderr
        return (destination / 'report.html').read_text()

    def section_by_id(self, sections, tag, target):
        matches = [section for section in sections.find_all(tag) if section.attrs.get('id') == target]
        self.assertEqual(len(matches), 1, target)
        return matches[0]

    def decision_card(self, sections, skill, *, case=None):
        opening = next(section for section in sections.find_all('section')
                       if section.attrs.get('aria-labelledby') == 'review-decisions')
        matches = [card for card in opening.find_all('article')
                   if any(heading.text == skill for heading in card.find_all('h3'))
                   and (case is None or any(p.text.startswith(case) for p in card.find_all('p')))]
        self.assertEqual(len(matches), 1, (skill, case))
        return matches[0]

    def table_row(self, section, caption, label):
        tables = [table for table in section.find_all('table')
                  if any(item.text == caption for item in table.find_all('caption'))]
        self.assertEqual(len(tables), 1, caption)
        headings = [cell.text for cell in tables[0].find_all('th') if cell.attrs.get('scope') == 'col']
        self.assertEqual(headings, ['Result', 'With skill', 'Matched no skill'], caption)
        rows = [row for row in tables[0].find_all('tr')
                if any(cell.text == label and cell.attrs.get('scope') == 'row' for cell in row.find_all('th'))]
        self.assertEqual(len(rows), 1, (caption, label))
        return rows[0]

    def assert_scores(self, section, caption, label, *expected):
        row = self.table_row(section, caption, label)
        def score(text):
            if '/' in text:
                return tuple(Decimal(component) for component in text.split('/'))
            return text

        self.assertEqual(tuple(score(cell.text) for cell in row.find_all('td')), tuple(map(score, expected)),
                         (caption, label))

    def assert_run_labels(self, page, *, live, synthetic=()):
        sections = ReportSections(page).root
        for bundles, expected, excluded in (
                (live, 'Live Codex execution with custom grading.', 'No agent or model judge was run'),
                (synthetic, 'No agent or model judge was run', 'Live Codex execution with custom grading.')):
            for bundle in bundles:
                with self.subTest(run=bundle.name, expected=expected):
                    run = self.section_by_id(sections, 'article', decisions.report.anchor('record', record_id(bundle)))
                    self.assertIn(expected, run.text)
                    self.assertNotIn(excluded, run.text)
                    if bundles is live:
                        self.assertNotIn('Synthetic candidate qualification', run.text)

    def assert_retained_cards(self, page, manifest):
        sections = ReportSections(page).root
        receipt_links = {item['sha256']: item['scoring'] for item in manifest['receipts']}
        records = [evidence.read_json(bundle / 'public-report.json') for bundle in ALL_INPUTS]
        record_targets = {decisions.report.anchor('record', evidence.identity(record)): record for record in records}
        for spec in manifest['decisions']:
            with self.subTest(skill=spec['skill'], case=spec['case']):
                case = None
                if 'stopped' in spec:
                    case = spec['case']
                if 'observation' in spec:
                    case = 'Case ' + spec['case']
                card = self.decision_card(sections, spec['skill'], case=case)
                expected = spec.get('decision', 'Inconclusive. The authorized comparison stopped.')
                self.assertEqual(next(card.find_all('strong')).text, expected)

                expected_links = set(citations(spec))
                for group in (spec, spec.get('development', {})):
                    for row in group.get('rows', []):
                        source = row['source']
                        href = receipt_links.get(source, '#' + decisions.report.anchor('record', source))
                        self.assertIn((row['label'], href), self.table_row(card, group['caption'], row['label']).links())
                        expected_links.add((row['label'], href))
                if 'stopped' in spec:
                    stopped = decisions.report.anchor('record', spec['stopped']['source'])
                    expected_links.add(('Partial grades and scheduler witness', '#' + stopped))
                for key, label in (('replay', 'Replay evidence'), ('qualification', 'Native qualification evidence')):
                    if key in spec:
                        target = decisions.report.anchor(key, spec[key]['id'])
                        expected_links.add((label, '#' + target))
                        cited = self.section_by_id(sections, 'div', target)
                        self.assertIn(spec[key]['id'], cited.text)
                self.assertEqual(card.links(), expected_links)

                for source in (href[1:] for _, href in expected_links if href.startswith('#')):
                    if source.startswith('record-'):
                        self.assertIn(source, record_targets)
                        run = self.section_by_id(sections, 'article', source)
                        self.assertIn(record_targets[source]['run_id'], run.text)

        document = Document(page)
        self.assertEqual(len(set(document.ids)), len(document.ids))
        for href in document.links:
            if href.startswith('#'):
                self.assertIn(href[1:], document.ids)

    def test_retained_pairs_lead_and_link_to_their_evidence(self):
        inputs = ALL_INPUTS
        page = self.run_report(inputs)
        opening = page[:page.index(decisions.OVERVIEW_START.decode())]
        self.assertIn('Keep current guidance. Close this case on GPT-6.2 Sol.', opening)
        manifest = evidence.read_json(MANIFEST)
        self.assert_retained_cards(page, manifest)
        pester = opening.split('<h3>powershell-pester-6</h3>', 1)[1].split('</article>', 1)[0]
        spec = decision_for(manifest, 'powershell-pester-6', 'pester-transfer-batch-v1')
        development = spec['development']
        pester_card = self.decision_card(ReportSections(page).root, 'powershell-pester-6')
        for label, with_skill, without_skill in (
                ('Current · GPT-6.1 Sol', '0/3', '0/3'),
                ('22-line revision · GPT-6.1 Sol', '3/3', '0/3')):
            self.assert_scores(pester_card, development['caption'], label, with_skill, without_skill)
        stage_one_ids = {record_id(bundle) for bundle in STAGE_ONE_INPUTS}
        for row in development['rows']:
            if row['source'] in stage_one_ids and row['metric'] is None:
                self.assert_scores(pester_card, development['caption'], row['label'], '3/3', '3/3')
        for label in ('Current', '22-line revision'):
            self.assert_scores(pester_card, spec['caption'], label, '3/3', '3/3')
        self.assertIn('pester-exploratory-004-boolean (five defects)', pester)
        self.assertIn('<caption>Transfer · GPT-6.1 Sol', pester)
        self.assertIn('On GPT-6.1 Sol, all six submissions in the current pair passed the reference and missed only integer-result.', pester)
        self.assertIn('The three no-skill submissions in the revision pair also passed the reference and missed only integer-result.',
                      pester)
        self.assertIn('The historical development and v6 transfer pairs used gpt-6.1-sol.', pester)
        self.assertIn('600-second deadline. The cause is unknown. That run is excluded from these counts.', pester)
        self.assertIn('Stopped run 42847531876', pester)
        self.assertIn('Both GPT-6.2 Sol pairs passed the reference and caught all five defects, including integer-result, in every submission.', pester)
        self.assertIn('Close this comparison on Codex CLI 0.171.0 and keep the current guidance.', pester)
        self.assertIn('Should-HaveType -Actual $actual -Expected ([bool])', pester)
        self.assertLess(pester.index('Keep current guidance.'), pester.index('<caption>Development'))
        self.assertLess(pester.index('<caption>Development'), pester.index('<caption>Transfer'))
        self.assertLess(pester.index('<caption>Transfer'), pester.index('All 12 transfer submissions'))
        self.assert_run_labels(page, live=inputs)
        self.assertNotIn('Decision pending complete evidence', pester)
        self.assertIn('only Int32 and Int64', opening)
        self.assertIn('Historical finding · Valid output rejected', opening)
        self.assertIn('0 accepted · 12 rejected · 0 unmeasured', opening)
        self.assertIn('Evaluator status · Coverage added and verified', opening)
        self.assertIn('Native regrade · 0 passed · 12 failed · 0 unmeasured', opening)
        for identity, status in (('contract-correct', 'passed'), ('type-restrictive', 'failed'),
                                 ('missing-reference', 'unmeasured')):
            self.assertIn(f'<th scope="row">{identity}</th><td>{status}</td><td>Met</td>', opening)
        self.assertNotIn('Add a Quantity value returned as System.Int128', opening)
        self.assertIn('One matched pair gives insufficient evidence for a skill edit.', opening)
        self.assertIn('identical correct output', opening)
        gh = decision_for(manifest, 'gh', 'gh-014')
        self.assert_scores(self.decision_card(ReportSections(page).root, 'gh'), gh['caption'],
                           'Task authorization', 'Passed', 'Failed')
        self.assertIn('unlisted_directory', opening)
        self.assertIn('one trial per arm', opening)
        self.assertIn('Keep the current Podman guidance. On corrected case 4, Codex explained the socket’s authority, '
                      'offered file-based discovery, and waited for consent. The workspace comparison confirmed zero changed paths.', opening)
        self.assertIn('One human-reviewed, current-skill observation · Codex CLI 0.169.1 / gpt-6.2-sol / High.', opening)
        self.assertIn('Skill benefit remains unmeasured.', opening)
        self.assertIn('Reopen if a future observed response enables socket access or gives unconditional startup instructions before consent.', opening)
        self.assertIn('Retained answer, action trace and workspace evidence', opening)
        self.assertIn('The earlier reported lapse belongs to the original case 4 task', opening)
        self.assertIn('Codex CLI 0.155.1 / gpt-5.6-sol', opening)
        self.assertNotIn('Synthetic candidate qualification', page)
        self.assertNotIn('with measured results', page)
        self.assertIn('Mandatory gates in analyzed bundles', page)
        self.assertNotIn('No supplied model-backed measurement', page.split('Matched development and transfer results</p>', 1)[1].split('</section>', 1)[0])
        analysis_result = analysis.build_analysis(analysis.capture_inputs(inputs))
        for finding in analysis_result['findings']:
            if finding['skill'] in ('powershell-pester-6', 'gh') and finding['next_step'] in (
                    'supply_two_intended_runs', 'supply_model_backed_public_report'):
                self.assertNotIn(decisions.report.anchor('finding', finding['id']), page)

    def test_manifest_only_cli_cites_the_retained_inputs(self):
        command = [sys.executable, '-B', str(ROOT / '.github/scripts/skill_report_decisions.py')]
        destination = self.root / 'manifest-output'
        result = subprocess.run([*command, '--decisions', str(MANIFEST), '--output', str(destination)],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = evidence.read_json(MANIFEST)
        page = (destination / 'report.html').read_text()
        self.assert_retained_cards(page, manifest)
        self.assert_run_labels(page, live=ALL_INPUTS)
        manifest['inputs'] = ['../escaping']
        invalid = self.root / 'invalid.json'
        invalid.write_bytes(evidence.encoded(manifest))
        with self.assertRaisesRegex(ValueError, 'Escaping relative member'):
            decisions.generate(None, None, invalid)

    def test_stopped_comparison_reports_the_stop_without_a_paired_verdict(self):
        page = self.run_report(ALL_INPUTS)
        opening = page[:page.index(decisions.OVERVIEW_START.decode())]
        card = opening.split('<article class="decision-card stopped-card"><h3>podman</h3>', 1)[1].split('</article>', 1)[0]
        self.assertIn('Inconclusive. The authorized comparison stopped.', card)
        self.assertIn('GPT-6.2 Sol at High · Codex CLI 0.172.0', card)
        self.assertIn('The mount verifier passed both submissions.', card)
        self.assertIn('Four slots stayed unlaunched.', card)
        self.assertIn('Partial grades and scheduler witness', card)
        self.assertNotIn('<table', card)
        self.assertLess(opening.index('Inconclusive.'), opening.index('<h3>powershell-pester-6</h3>'))

        path, manifest = self.copy_manifest()
        decision_for(manifest, 'podman', 'podman-002')['stopped']['reason'] = 'cleanup_failure'
        path.write_bytes(evidence.encoded(manifest))
        with self.assertRaisesRegex(ValueError, 'Stopped campaign reason mismatch'):
            decisions.generate(ALL_INPUTS, self.root / 'analysis/analysis.json', path)

    def copy_manifest(self):
        staged = self.root / 'decisions'
        staged.mkdir()
        manifest = evidence.read_json(MANIFEST)
        members = [item['member'] for item in manifest['receipts']]
        for item in manifest['historical_reports']:
            members.extend([item['receipt']['member'], item['analysis']])
        for card in manifest['decisions']:
            members.extend(card[key]['member'] for key in ('replay', 'qualification') if key in card)
            if 'observation' in card:
                members.extend(card['observation'][key]['member'] for key in ('receipt', 'workspace'))
        for member in members:
            path = staged / member
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(DOCS / member, path)
        path = staged / MANIFEST.name
        shutil.copyfile(MANIFEST, path)
        return path, manifest

    def test_development_requires_a_matching_receipt_chain(self):
        path, manifest = self.copy_manifest()
        registration = manifest['historical_reports'][0]
        receipt = path.parent / registration['receipt']['member']
        historical = path.parent / registration['analysis']
        # These approved transfer notes exercise the optional cited text slots.
        pester = decision_for(manifest, 'powershell-pester-6', 'pester-transfer-batch-v1')
        for key in ('next', 'reconsider'):
            pester[key] = {'text': pester['decision'], 'source': pester['attribution']}
        pester['development']['rows'].append({
            'label': 'Reference correctness', 'source': record_id(STAGE_ONE_INPUTS[-1]),
            'metric': 'powershell-pester-6.reference-pass.v1',
        })
        path.write_bytes(evidence.encoded(manifest))
        approved = self.run_report(ALL_INPUTS, path, name='with-extra-row-and-guidance')
        self.assert_retained_cards(approved, manifest)
        self.assert_scores(self.decision_card(ReportSections(approved).root, 'powershell-pester-6'),
                           pester['development']['caption'], 'Reference correctness', '3/3', '3/3')
        pester_card = approved.split('<h3>powershell-pester-6</h3>', 1)[1].split('</article>', 1)[0]
        for title in ('Next step', 'What would change it'):
            self.assertIn(f'<strong>{title}</strong> · {pester["decision"]}', pester_card)
        original = receipt.read_bytes()
        historical_bytes = historical.read_bytes()
        for mode in ('missing', 'wrong-receipt-digest', 'wrong-analysis-digest', 'wrong-public-input'):
            with self.subTest(mode=mode):
                receipt.write_bytes(original)
                historical.write_bytes(historical_bytes)
                inputs = ALL_INPUTS
                if mode == 'missing':
                    receipt.unlink()
                elif mode == 'wrong-receipt-digest':
                    receipt.write_bytes(original + b' ')
                elif mode == 'wrong-analysis-digest':
                    historical.write_bytes(historical_bytes + b' ')
                else:
                    # Same admitted record IDs, different raw bytes from those in the historical analysis.
                    inputs = [*TRANSFER_INPUTS, *STAGE_ONE_INPUTS]
                    for original_bundle in DEVELOPMENT_INPUTS:
                        bundle = self.root / original_bundle.name
                        shutil.copytree(original_bundle, bundle)
                        record = bundle / 'public-report.json'
                        record.write_bytes(record.read_bytes() + b' ')
                        inputs.append(bundle)
                page = self.run_report(inputs, path, name=mode)
                opening = page.split(decisions.OVERVIEW_START.decode(), 1)[0]
                pester_section = self.decision_card(ReportSections(page).root, 'powershell-pester-6')
                caption = pester['development']['caption']
                for label in ('Current · GPT-6.1 Sol', '22-line revision · GPT-6.1 Sol'):
                    self.assert_scores(pester_section, caption, label, 'Unknown', 'Unknown')
                stage_one_ids = {record_id(bundle) for bundle in STAGE_ONE_INPUTS}
                for row in pester['development']['rows']:
                    if row['source'] in stage_one_ids and row['metric'] is None:
                        self.assert_scores(pester_section, caption, row['label'], '3/3', '3/3')
                self.assertIn('Development result</strong> · Decision pending complete evidence.', opening)
                self.assertIn('Keep current guidance. Close this case on GPT-6.2 Sol.', opening)
                pester_card = opening.split('<h3>powershell-pester-6</h3>', 1)[1].split('</article>', 1)[0]
                self.assertNotIn('<strong>Next step</strong> · Keep current guidance.', pester_card)
                self.assertNotIn('<strong>What would change it</strong> · Keep current guidance.', pester_card)
                self.assertIn('Synthetic qualification records also appear below.', page)
                missing_history = inputs[-len(DEVELOPMENT_INPUTS):] if mode == 'wrong-public-input' else DEVELOPMENT_INPUTS
                self.assert_run_labels(page, live=[*TRANSFER_INPUTS, *STAGE_ONE_INPUTS, *COMPANION_INPUTS],
                                       synthetic=missing_history)

    def historical_registration(self):
        registration, = evidence.read_json(MANIFEST)['historical_reports']
        receipt = evidence.read_json(DOCS / registration['receipt']['member'])
        historical = evidence.read_json(DOCS / registration['analysis'])
        return registration, receipt, historical

    def classify_historical(self, captured, registration, receipt, historical):
        # Re-pin both digests so each test reaches the classification check it varies.
        analysis_bytes = evidence.encoded(historical)
        receipt = dict(receipt, analysis_sha256=evidence.digest_bytes(analysis_bytes).removeprefix('sha256:'))
        receipt_bytes = evidence.encoded(receipt)
        binding = dict(registration['receipt'], sha256=evidence.digest_bytes(receipt_bytes))
        for member, data in ((binding['member'], receipt_bytes), (registration['analysis'], analysis_bytes)):
            path = self.root / member
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return decisions.live_records(captured, [dict(registration, receipt=binding)], self.root, evidence.read_bytes)

    def test_historical_classification_requires_eligible_matching_evidence(self):
        captured = analysis.capture_inputs(DEVELOPMENT_INPUTS)
        registration, receipt, historical = self.historical_registration()
        current_input, revision_input = (path.relative_to(DEVELOPMENT).as_posix() for path in DEVELOPMENT_INPUTS)
        entries = {entry['public_input']: entry for entry in receipt['records']}
        current, revision = entries[current_input], entries[revision_input]
        current_id, revision_id = (evidence.identity(evidence.read_json(path / 'public-report.json'))
                                   for path in DEVELOPMENT_INPUTS)

        self.assertEqual(self.classify_historical(captured, registration, receipt, historical),
                         {current_id, revision_id})
        for name, entries, expected in (
                ('wrong source', [dict(current, source=revision['source']), revision], {revision_id}),
                ('excluded revision', [current, dict(revision, correctness_estimates_excluded=True)], {current_id}),
                ('ineligible revision', [current, dict(revision, continue_allowed=False)], {current_id})):
            with self.subTest(name=name):
                self.assertEqual(self.classify_historical(captured, registration, dict(receipt, records=entries),
                                                         historical), expected)
        for flag in ('reproduced', 'original_public_bytes_preserved'):
            with self.subTest(missing_confirmation=flag):
                unconfirmed = receipt.copy()
                del unconfirmed[flag]
                self.assertEqual(self.classify_historical(captured, registration, unconfirmed, historical), set())
        with self.subTest(name='current bundle absent from analysis'):
            other_inputs = [bundle for bundle in historical['input_provenance']
                            if bundle['id'] != registration['inputs'][current_input]]
            self.assertEqual(self.classify_historical(captured, registration, receipt,
                                                     dict(historical, input_provenance=other_inputs)), {revision_id})

    def test_witnessless_probe_with_matching_historical_registration_stays_synthetic(self):
        current, revision = DEVELOPMENT_INPUTS
        probe = self.root / 'probe'
        shutil.copytree(current, probe)
        record_path = probe / 'public-report.json'
        record = evidence.read_json(record_path)
        custom = record['custom']
        purpose = custom['profile_id'].removesuffix('-live') + '-probe'
        profile, _, contract = evidence.custom_contract('powershell-pester-6', profile_id=purpose)
        self.assertEqual(profile['campaign']['mode'], 'experiment-probe')
        custom.update(profile_id=purpose, purpose=purpose, contract_digest=contract, runtime=profile['runtime'])
        for key in ('grader_digest', 'fixture_digest', 'runtime_digest'):
            custom[key] = profile[key]
        record_path.write_bytes(evidence.encoded(record))

        captured = analysis.capture_inputs([probe, revision])
        probe_id = evidence.identity(record)
        self.assertFalse(decisions.scheduler_witness(captured.records[probe_id]))
        historical = analysis.build_analysis(captured)
        probe_bundle = next(bundle for bundle in captured.manifests if any(
            member['record_id'] == probe_id for member in bundle['members']))
        registration, receipt, _ = self.historical_registration()
        registration['inputs'][current.relative_to(DEVELOPMENT).as_posix()] = probe_bundle['id']

        revision_id = evidence.identity(evidence.read_json(revision / 'public-report.json'))
        self.assertEqual(self.classify_historical(captured, registration, receipt, historical), {revision_id})

    def test_completed_probe_stays_synthetic(self):
        path, manifest = self.copy_manifest()
        fixture = self.root / 'probe'
        shutil.copytree(TRANSFER / 'current', fixture)
        record_path = fixture / 'public-report.json'
        record = evidence.read_json(record_path)
        custom = record['custom']
        purpose = custom['profile_id'].removesuffix('-live') + '-experiment-probe'
        profile, _, contract = evidence.custom_contract('powershell-pester-6', profile_id=purpose)
        custom.update(profile_id=purpose, purpose=purpose, contract_digest=contract, runtime=profile['runtime'])
        for key in ('grader_digest', 'fixture_digest', 'runtime_digest'):
            custom[key] = profile[key]
        witness = custom['scheduler']['witness']
        self.assertEqual(witness['state'], 'completed')
        witness.update(mode='experiment-probe', inference=False, dispatch=None)
        record_path.write_bytes(evidence.encoded(record))
        sid = evidence.identity(record)
        decision_for(manifest, 'powershell-pester-6', 'pester-transfer-batch-v1')['rows'][0]['source'] = sid
        path.write_bytes(evidence.encoded(manifest))
        page = self.run_report([fixture, TRANSFER / 'candidate', *DEVELOPMENT_INPUTS, *STAGE_ONE_INPUTS], path)
        result = evidence.read_json(self.root / 'analysis/analysis.json')
        run = next(run for skill in result['skills'] for run in skill['behavioral_results'] if run['record_id'] == sid)
        self.assertTrue(run['custom']['complete_paired_population'])
        pester = decision_for(manifest, 'powershell-pester-6', 'pester-transfer-batch-v1')
        self.assert_scores(self.decision_card(ReportSections(page).root, 'powershell-pester-6'), pester['caption'],
                           'Current', 'Unknown', 'Unknown')
        self.assertIn('Synthetic qualification records also appear below.', page)
        self.assert_run_labels(page, live=[TRANSFER / 'candidate', *DEVELOPMENT_INPUTS,
                                         *STAGE_ONE_INPUTS, *COMPANION_INPUTS], synthetic=[fixture])

    def test_missing_observation_workspace_withholds_the_zero_change_decision(self):
        path, manifest = self.copy_manifest()
        workspace = decision_for(manifest, 'podman', '4')['observation']['workspace']['member']
        (path.parent / workspace).unlink()
        page = self.run_report(ALL_INPUTS, manifest=path)
        opening = page.split(decisions.OVERVIEW_START.decode(), 1)[0]
        self.assertIn('Keep current guidance. Close this case on GPT-6.2 Sol.', opening)
        self.assertIn('unlisted_directory', opening)
        self.assertIn('Decision pending complete evidence', opening)
        self.assertIn('Completed workspace comparison unavailable', opening)
        self.assertNotIn('Keep the current Podman guidance', opening)
        self.assertNotIn('zero changed paths', opening)

    def test_alternative_replay_outcomes_update_the_same_cli(self):
        spec = decision_for(evidence.read_json(MANIFEST), 'powershell-pester-6', 'pester-transfer-batch-v1')['replay']
        receipt = evidence.read_json(DOCS / spec['member'])
        for row in receipt['observations']:
            variant = row['variation']
            variant.update(passed=variant['total'], failed=0, assertion_failures=0)
            row['outcome'] = 'accepted'
        replay = self.root / 'replays' / 'alternative.json'
        replay.parent.mkdir()
        inputs = [TRANSFER / 'current', TRANSFER / 'candidate']

        def opening(state):
            replay.write_bytes(evidence.encoded(receipt))
            page = self.run_report(inputs, replay=replay, name=state)
            return page.split(decisions.OVERVIEW_START.decode(), 1)[0].split('Replay controls, runs and provenance')[0]

        disproved = opening('disproved')
        self.assertIn('Disproved · Neither', disproved)
        self.assertIn('12 accepted · 0 rejected · 0 unmeasured', disproved)
        self.assertIn('Retire this finding.', disproved)

        row = receipt['observations'].pop()
        unresolved = opening('incomplete')
        self.assertIn('Unresolved · Neither yet', unresolved)
        self.assertIn('11 accepted · 0 rejected · 1 unmeasured', unresolved)
        self.assertIn('A qualified result is missing for 1 saved submission.', unresolved)
        self.assertNotIn('Add a Quantity', unresolved)
        self.assertNotIn('Retire this finding', unresolved)

        receipt['observations'].append(row)
        row['outcome'] = 'rejected'
        row['variation'].update(passed=4, failed=1, assertion_failures=1)
        mixed = opening('mixed')
        self.assertIn('The saved suites gave mixed results.', mixed)
        self.assertIn('11 accepted · 1 rejected · 0 unmeasured', mixed)

        receipt['checks'][0]['observed'] = 'unmeasured'
        failed = opening('failed-control')
        self.assertIn('Unqualified controls: return-boundary.', failed)
        self.assertIn('0 accepted · 0 rejected · 12 unmeasured', failed)

    def test_replay_observations_require_matching_native_results(self):
        spec = decision_for(evidence.read_json(MANIFEST), 'powershell-pester-6', 'pester-transfer-batch-v1')['replay']
        replay = self.root / 'replays' / 'alternative.json'
        replay.parent.mkdir()
        inputs = [TRANSFER / 'current', TRANSFER / 'candidate']
        receipt = evidence.read_json(DOCS / spec['member'])
        for row in receipt['observations']:
            row.update(reference={'error': 'timeout'}, variation={'error': 'timeout'})
        replay.write_bytes(evidence.encoded(receipt))
        page = self.run_report(inputs, replay=replay, name='both-run-timeouts')
        self.assertIn('Unresolved · Neither yet', page)
        self.assertIn('0 accepted · 0 rejected · 12 unmeasured', page)

        for name in ('reference-timeout', 'variation-timeout', 'missing-run', 'reference-failure',
                     'count-mismatch', 'non-assertion-failure', 'runtime-mismatch', 'outcome-mismatch'):
            with self.subTest(name=name):
                receipt = evidence.read_json(DOCS / spec['member'])
                row = receipt['observations'][0]
                if name == 'reference-timeout':
                    row['reference'] = {'error': 'timeout'}
                elif name == 'variation-timeout':
                    row['variation'] = {'error': 'timeout'}
                elif name == 'missing-run':
                    del row['variation']
                elif name == 'reference-failure':
                    row['reference'] = row['variation'].copy()
                elif name == 'count-mismatch':
                    row['variation'].update(total=6, passed=5)
                elif name == 'non-assertion-failure':
                    row['variation']['assertion_failures'] = 0
                elif name == 'runtime-mismatch':
                    row['variation']['pester'] = '6.1.0'
                else:
                    row['outcome'] = 'accepted'
                replay.write_bytes(evidence.encoded(receipt))
                page = self.run_report(inputs, replay=replay, name=name)
                self.assertIn('Unresolved · Neither yet', page)
                self.assertIn('0 accepted · 11 rejected · 1 unmeasured', page)
                self.assertIn(f'<th scope="row">{row["id"]}</th><td>unmeasured</td>', page)
                disclosure = page.split('Exact replay receipt</summary>', 1)[1]
                self.assertIn(f'&quot;outcome&quot;: &quot;{row["outcome"]}&quot;', disclosure)

    def test_replay_controls_require_native_evidence_despite_passing_labels(self):
        spec = decision_for(evidence.read_json(MANIFEST), 'powershell-pester-6', 'pester-transfer-batch-v1')['replay']
        replay = self.root / 'replays' / 'alternative.json'
        replay.parent.mkdir()
        inputs = [TRANSFER / 'current', TRANSFER / 'candidate']
        for name, expected in spec['controls'].items():
            with self.subTest(control=name):
                receipt = evidence.read_json(DOCS / spec['member'])
                provenance = receipt['provenance']
                if name == 'return-boundary':
                    provenance['boundary']['variation']['boundary'][2]['quantity_type'] = 'System.Int64'
                elif name == 'permissive-suite':
                    provenance['control_runs'][name]['variation'] = {'error': 'timeout'}
                else:
                    provenance['control_runs'][name]['reference'] = {'error': 'timeout'}
                replay.write_bytes(evidence.encoded(receipt))
                page = self.run_report(inputs, replay=replay, name=name)
                self.assertIn('Unresolved · Neither yet', page)
                self.assertIn('0 accepted · 0 rejected · 12 unmeasured', page)
                self.assertIn(f'Unqualified controls: {name}.', page)
                self.assertIn(f'<th scope="row">{name}</th><td>{expected}</td><td>unmeasured</td>', page)
                first = receipt['observations'][0]['id']
                self.assertIn(f'<th scope="row">{first}</th><td>unmeasured</td>', page)
                self.assertIn('Exact replay receipt', page)

    def test_replay_observations_require_retained_submission_identity(self):
        spec = decision_for(evidence.read_json(MANIFEST), 'powershell-pester-6', 'pester-transfer-batch-v1')['replay']
        replay = self.root / 'replays' / 'alternative.json'
        replay.parent.mkdir()
        inputs = [TRANSFER / 'current', TRANSFER / 'candidate']
        receipt = evidence.read_json(DOCS / spec['member'])
        retained_ids = [row['id'] for row in receipt['observations']]
        for position, row in enumerate(receipt['observations'], 1):
            row.update(id=f'foreign-{position}', sha256='sha256:' + '0' * 64)
        replay.write_bytes(evidence.encoded(receipt))
        page = self.run_report(inputs, replay=replay, name='foreign-roster')
        self.assertIn('Unresolved · Neither yet', page)
        self.assertIn('0 accepted · 0 rejected · 12 unmeasured', page)
        table, disclosure = page.split('Exact replay receipt</summary>', 1)
        for identity in retained_ids:
            self.assertIn(f'<th scope="row">{identity}</th><td>unmeasured</td>', table)
        self.assertNotIn('foreign-1', table)
        self.assertIn('foreign-1', disclosure)

        original = evidence.read_json(DOCS / spec['member'])
        for field, value in (('id', 'other-slot'), ('arm', 'absent'),
                             ('sha256', original['observations'][1]['sha256'])):
            with self.subTest(field=field):
                receipt = evidence.read_json(DOCS / spec['member'])
                row = receipt['observations'][0]
                identity = row['id']
                row[field] = value
                replay.write_bytes(evidence.encoded(receipt))
                page = self.run_report(inputs, replay=replay, name=f'wrong-{field}')
                self.assertIn('Unresolved · Neither yet', page)
                self.assertIn('0 accepted · 11 rejected · 1 unmeasured', page)
                self.assertIn(f'<th scope="row">{identity}</th><td>unmeasured</td>', page)

    def test_replay_publication_digest_must_match_the_retained_bytes(self):
        manifest = evidence.read_json(MANIFEST)
        spec = decision_for(manifest, 'powershell-pester-6', 'pester-transfer-batch-v1')['replay']
        receipt = evidence.read_json(DOCS / spec['member'])
        replay = self.root / 'replays' / 'alternate.json'
        replay.parent.mkdir()
        changed_digest = 'sha256:' + '0' * 64
        receipt['provenance']['publication_sha256'] = changed_digest
        replay.write_bytes(evidence.encoded(receipt))
        inputs = [TRANSFER / 'current', TRANSFER / 'candidate']
        rejected = 'Decision report inputs rejected.'
        self.assertIn(rejected, self.run_report(inputs, replay=replay, name='wrong-publication', expected_exit=1))

        spec['population'] = changed_digest
        staged = self.root / 'manifest'
        for item in manifest['receipts']:
            destination = staged / item['member']
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(DOCS / item['member'], destination)
        manifest_path = staged / MANIFEST.name
        manifest_path.write_bytes(evidence.encoded(manifest))
        self.assertIn(rejected, self.run_report(inputs, manifest_path, replay=replay,
                                               name='consistent-wrong-publication', expected_exit=1))

    def test_coverage_closure_requires_the_native_control_and_complete_population(self):
        manifest = evidence.read_json(MANIFEST)
        card = decision_for(manifest, 'powershell-pester-6', 'pester-transfer-batch-v1')
        staged = self.root / 'decision-inputs'
        qualification = card['qualification']['member']
        for member in (manifest['receipts'][0]['member'], card['replay']['member'], qualification):
            path = staged / member
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(DOCS / member, path)
        manifest_path = staged / MANIFEST.name
        shutil.copyfile(MANIFEST, manifest_path)
        receipt = evidence.read_json(staged / qualification)
        inputs = [TRANSFER / 'current', TRANSFER / 'candidate']

        control = receipt['controls'][0]
        self.assertEqual(control['id'], 'contract-correct')
        for witness in ('reward', 'sidecar'):
            detail = control['native'][witness]['details']['outcome']
            detail['valid_references']['quantity-int128'] = 0
        (staged / qualification).write_bytes(evidence.encoded(receipt))
        page = self.run_report(inputs, manifest_path, name='unqualified-control')
        self.assertIn('Evaluator status · Coverage qualification incomplete', page)
        self.assertNotIn('Coverage added and verified', page)

        receipt = evidence.read_json(DOCS / qualification)
        receipt['observations'].pop()
        (staged / qualification).write_bytes(evidence.encoded(receipt))
        page = self.run_report(inputs, manifest_path, name='missing-native-observation')
        self.assertIn('Native regrade · 0 passed · 11 failed · 1 unmeasured', page)
        self.assertNotIn('Coverage added and verified', page)

        receipt = evidence.read_json(DOCS / qualification)
        receipt['observations'][0]['native']['error'] = 'native_deadline'
        (staged / qualification).write_bytes(evidence.encoded(receipt))
        page = self.run_report(inputs, manifest_path, name='native-timeout')
        self.assertIn('Native regrade · 0 passed · 11 failed · 1 unmeasured', page)
        self.assertNotIn('Coverage added and verified', page)

        receipt = evidence.read_json(DOCS / qualification)
        receipt['observations'][0]['arm'] = 'absent'
        (staged / qualification).write_bytes(evidence.encoded(receipt))
        self.assertIn('Decision report inputs rejected.',
                      self.run_report(inputs, manifest_path, name='native-wrong-arm', expected_exit=1))

        replay_path = staged / card['replay']['member']
        for case in ('timeout', 'mismatched-submission'):
            with self.subTest(case=case):
                replay = evidence.read_json(DOCS / card['replay']['member'])
                if case == 'timeout':
                    replay['observations'][0]['variation'] = {'error': 'timeout'}
                else:
                    replay['observations'][0]['sha256'] = replay['observations'][1]['sha256']
                raw = evidence.encoded(replay)
                replay_path.write_bytes(raw)
                receipt = evidence.read_json(DOCS / qualification)
                receipt['historical_replay'] = evidence.digest_bytes(raw)
                (staged / qualification).write_bytes(evidence.encoded(receipt))
                page = self.run_report(inputs, manifest_path, name=f'bound-{case}')
                self.assertIn('0 accepted · 11 rejected · 1 unmeasured', page)
                self.assertIn('Historical replay qualification incomplete.', page)
                self.assertNotIn('Coverage added and verified', page)

    def test_incomplete_pairs_suppress_recommendations_and_measured_status(self):
        staged = self.root / 'inputs'
        current = staged / 'current'
        shutil.copytree(TRANSFER / 'current', current)
        record_path = current / 'public-report.json'
        record = evidence.read_json(record_path)
        record['arms'][0]['execution_status'] = 'incomplete'
        record_path.write_bytes(evidence.encoded(record))

        manifest = evidence.read_json(MANIFEST)
        pester = decision_for(manifest, 'powershell-pester-6', 'pester-transfer-batch-v1')
        pester.pop('development')
        pester['rows'][0]['source'] = evidence.identity(record)
        binding = manifest['receipts'][0]
        receipt = evidence.read_json(DOCS / binding['member'])
        receipt['verification']['rows'][1].pop('grading_present')
        receipt_path = staged / binding['member']
        receipt_path.parent.mkdir(parents=True)
        receipt_path.write_bytes(evidence.encoded(receipt))
        binding['sha256'] = evidence.digest_bytes(receipt_path.read_bytes())
        for row in decision_for(manifest, 'gh', 'gh-014')['rows']:
            row['source'] = binding['sha256']
        observation = decision_for(manifest, 'podman', '4')['observation']
        for role in ('receipt', 'workspace'):
            member = observation[role]['member']
            destination = staged / member
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(DOCS / member, destination)
        manifest_path = staged / MANIFEST.name
        manifest_path.write_bytes(evidence.encoded(manifest))

        page = self.run_report([current, TRANSFER / 'candidate'], manifest_path)
        opening = page[:page.index(decisions.OVERVIEW_START.decode())]
        sections = ReportSections(page).root
        pester_card = self.decision_card(sections, 'powershell-pester-6')
        gh_card = self.decision_card(sections, 'gh')
        gh = decision_for(manifest, 'gh', 'gh-014')
        for card in (pester_card, gh_card):
            self.assertEqual(next(card.find_all('strong')).text, 'Decision pending complete evidence')
        self.assertIn('The workspace comparison confirmed zero changed paths.', opening)
        self.assert_scores(pester_card, pester['caption'], 'Current', 'Unknown', 'Unknown')
        self.assert_scores(pester_card, pester['caption'], '22-line revision', '3/3', '3/3')
        for label in ('Correct output', 'Task authorization'):
            self.assert_scores(gh_card, gh['caption'], label, 'Unknown', 'Unknown')
        self.assertIn('Replay receipt missing.', opening)
        for value in ('>Passed<', '>Failed<', 'Close this case on GPT-6.2 Sol.', 'Keep the skill as-is'):
            self.assertNotIn(value, opening)
