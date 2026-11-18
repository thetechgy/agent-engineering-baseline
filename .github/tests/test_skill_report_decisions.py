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

    def run_report(self, inputs, manifest=MANIFEST):
        captured = analysis.capture_inputs(inputs)
        saved = self.root / 'analysis' / 'analysis.json'
        saved.parent.mkdir()
        saved.write_bytes(evidence.encoded(analysis.build_analysis(captured)))
        destination = self.root / 'html'
        argv = [sys.executable, '-B', str(ROOT / '.github/scripts/skill_report_decisions.py'),
                '--analysis', str(saved), '--decisions', str(manifest), '--output', str(destination)]
        for path in inputs:
            argv.extend(['--input', str(path)])
        process = subprocess.run(argv, capture_output=True, text=True, check=False)
        self.assertEqual(process.returncode, 0, process.stderr)
        return (destination / 'report.html').read_text()

    def test_retained_pairs_lead_and_link_to_their_evidence(self):
        page = self.run_report([TRANSFER / 'current', TRANSFER / 'candidate'])
        opening = page[:page.index(decisions.OVERVIEW_START.decode())]
        self.assertIn('Keep current guidance. Defer the 22-line revision.', opening)
        self.assertEqual(opening.count('>3/3<'), 4)
        self.assertIn('only Int32 and Int64', opening)
        self.assertIn('same fixed list of Quantity types in all 12 submissions', opening)
        self.assertIn('Keep the skill as-is pending stronger evidence.', opening)
        self.assertIn('identical correct output', opening)
        self.assertIn('>Passed</td><td>Failed</td>', opening)
        self.assertIn('unlisted_directory', opening)
        self.assertIn('one trial per arm', opening)
        self.assertNotIn('Synthetic candidate qualification', page)
        document = Document(page)
        self.assertEqual(len(set(document.ids)), len(document.ids))
        for link in Document(opening).links:
            if link.startswith('#'):
                self.assertIn(link[1:], document.ids)
            else:
                self.assertIsNotNone(decisions.GITHUB_EVIDENCE.fullmatch(link))

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
        for value in ('>Passed<', '>Failed<', 'Defer the 22-line revision', 'Keep the skill as-is', 'Next step'):
            self.assertNotIn(value, opening)
