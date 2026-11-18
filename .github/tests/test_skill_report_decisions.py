"""Exercise decision rendering through the offline CLI with retained evidence."""

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
MANIFEST = DOCS / 'report-decisions.json'
analysis = decisions.analysis
evidence = decisions.evidence


class DecisionReportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def run_report(self, inputs, manifest=MANIFEST, *, replay=None, name='html'):
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
        self.assertEqual(process.returncode, 0, process.stderr)
        return (destination / 'report.html').read_text()

    def test_retained_pairs_lead_and_link_to_their_evidence(self):
        inputs = [TRANSFER / 'current', TRANSFER / 'candidate']
        page = self.run_report(inputs)
        opening = page[:page.index(decisions.OVERVIEW_START.decode())]
        self.assertIn('Keep current guidance. Defer the 22-line revision.', opening)
        self.assertEqual(opening.count('>3/3<'), 4)
        self.assertIn('only Int32 and Int64', opening)
        self.assertIn('Historical finding · Valid output rejected', opening)
        self.assertIn('0 accepted · 12 rejected · 0 unmeasured', opening)
        self.assertIn('Evaluator status · Coverage added and verified', opening)
        self.assertIn('Native regrade · 0 passed · 12 failed · 0 unmeasured', opening)
        self.assertNotIn('Add a Quantity value returned as System.Int128', opening)
        self.assertIn('One matched pair gives insufficient evidence for a skill edit.', opening)
        self.assertIn('identical correct output', opening)
        self.assertIn('>Passed</td><td>Failed</td>', opening)
        self.assertIn('unlisted_directory', opening)
        self.assertIn('one trial per arm', opening)
        self.assertNotIn('Synthetic candidate qualification', page)
        self.assertNotIn('with measured results', page)
        self.assertIn('Mandatory gates in analyzed bundles', page)
        self.assertNotIn('No supplied model-backed measurement', page.split('Frozen primary success by matched pair</p>', 1)[1].split('</section>', 1)[0])
        analysis_result = analysis.build_analysis(analysis.capture_inputs(inputs))
        for finding in analysis_result['findings']:
            if finding['skill'] in ('powershell-pester-6', 'gh') and finding['next_step'] in (
                    'supply_two_intended_runs', 'supply_model_backed_public_report'):
                self.assertNotIn(decisions.report.anchor('finding', finding['id']), page)
        document = Document(page)
        self.assertEqual(len(set(document.ids)), len(document.ids))
        for link in Document(opening).links:
            if link.startswith('#'):
                self.assertIn(link[1:], document.ids)
            else:
                self.assertIsNotNone(decisions.GITHUB_EVIDENCE.fullmatch(link))

    def test_alternative_replay_outcomes_update_the_same_cli(self):
        spec = evidence.read_json(MANIFEST)['decisions'][0]['replay']
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

    def test_coverage_closure_requires_the_native_control_and_complete_population(self):
        manifest = evidence.read_json(MANIFEST)
        card = manifest['decisions'][0]
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

    def test_incomplete_pairs_suppress_recommendations_and_measured_status(self):
        staged = self.root / 'inputs'
        current = staged / 'current'
        shutil.copytree(TRANSFER / 'current', current)
        record_path = current / 'public-report.json'
        record = evidence.read_json(record_path)
        record['arms'][0]['execution_status'] = 'incomplete'
        record_path.write_bytes(evidence.encoded(record))

        manifest = evidence.read_json(MANIFEST)
        manifest['decisions'][0]['rows'][0]['source'] = evidence.identity(record)
        binding = manifest['receipts'][0]
        receipt = evidence.read_json(DOCS / binding['member'])
        receipt['verification']['rows'][1].pop('grading_present')
        receipt_path = staged / binding['member']
        receipt_path.parent.mkdir(parents=True)
        receipt_path.write_bytes(evidence.encoded(receipt))
        binding['sha256'] = evidence.digest_bytes(receipt_path.read_bytes())
        for row in manifest['decisions'][1]['rows']:
            row['source'] = binding['sha256']
        manifest_path = staged / MANIFEST.name
        manifest_path.write_bytes(evidence.encoded(manifest))

        page = self.run_report([current, TRANSFER / 'candidate'], manifest_path)
        opening = page[:page.index(decisions.OVERVIEW_START.decode())]
        self.assertEqual(opening.count('Decision pending complete evidence'), 2)
        self.assertEqual(opening.count('>Unknown</td><td>Unknown</td>'), 3)
        self.assertEqual(opening.count('>3/3<'), 2)  # The other transfer pair remains measured.
        self.assertIn('Replay receipt missing.', opening)
        for value in ('>Passed<', '>Failed<', 'Defer the 22-line revision', 'Keep the skill as-is'):
            self.assertNotIn(value, opening)
