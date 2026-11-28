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

    def test_retained_pairs_lead_and_link_to_their_evidence(self):
        inputs = ALL_INPUTS
        page = self.run_report(inputs)
        opening = page[:page.index(decisions.OVERVIEW_START.decode())]
        self.assertIn('Keep current guidance. Close this case on GPT-6.2 Sol.', opening)
        self.assertEqual(opening.count('>3/3<'), 9)
        self.assertEqual(opening.count('>0/3<'), 3)
        pester = opening.split('<h3>powershell-pester-6</h3>', 1)[1].split('</article>', 1)[0]
        for cli in ('0.171.0', '0.167.0'):
            self.assertIn(f'>Current · GPT-6.2 Sol · CLI {cli}</a></th><td>3/3</td><td>3/3</td>', pester)
        self.assertIn('>Current · GPT-6.1 Sol</a></th><td>0/3</td><td>0/3</td>', pester)
        self.assertIn('>22-line revision · GPT-6.1 Sol</a></th><td>3/3</td><td>0/3</td>', pester)
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
        self.assertEqual(opening.count('<h3>powershell-pester-6</h3>'), 1)
        self.assertEqual(page.count('Live Codex execution with custom grading.'), 7)
        self.assertNotIn('No agent or model judge was run', page)
        self.assertNotIn('Decision pending complete evidence', pester)
        self.run_report(inputs, name='html-repeat')
        self.assertEqual((self.root / 'html/report.html').read_bytes(),
                         (self.root / 'html-repeat/report.html').read_bytes())
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
        self.assertIn('>Passed</td><td>Failed</td>', opening)
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
        document = Document(page)
        self.assertEqual(len(set(document.ids)), len(document.ids))
        for link in Document(opening).links:
            if link.startswith('#'):
                self.assertIn(link[1:], document.ids)
            else:
                self.assertIsNotNone(decisions.GITHUB_EVIDENCE.fullmatch(link))

    def test_manifest_inputs_reproduce_the_explicit_report(self):
        expected = self.run_report(ALL_INPUTS)
        command = [sys.executable, '-B', str(ROOT / '.github/scripts/skill_report_decisions.py')]
        destination = self.root / 'manifest-output'
        result = subprocess.run([*command, '--decisions', str(MANIFEST), '--output', str(destination)],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((destination / 'report.html').read_text(), expected)
        manifest = evidence.read_json(MANIFEST)
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
        path.write_bytes(evidence.encoded(manifest))
        approved = self.run_report(ALL_INPUTS, path, name='with-cited-guidance')
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
                self.assertEqual(opening.count('>Unknown</td><td>Unknown</td>'), 2)
                self.assertEqual(opening.count('>3/3<'), 8)
                self.assertIn('Development result</strong> · Decision pending complete evidence.', opening)
                self.assertIn('Keep current guidance. Close this case on GPT-6.2 Sol.', opening)
                pester_card = opening.split('<h3>powershell-pester-6</h3>', 1)[1].split('</article>', 1)[0]
                self.assertNotIn('<strong>Next step</strong> · Keep current guidance.', pester_card)
                self.assertNotIn('<strong>What would change it</strong> · Keep current guidance.', pester_card)
                self.assertIn('Synthetic qualification records also appear below.', page)
                self.assertEqual(page.count('No agent or model judge was run'), 2)
                self.assertEqual(page.count('Live Codex execution with custom grading.'), 5)

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
        opening = page.split(decisions.OVERVIEW_START.decode(), 1)[0]
        self.assertIn('>Current</a></th><td>Unknown</td><td>Unknown</td>', opening)
        self.assertEqual(page.count('Live Codex execution with custom grading.'), 6)
        self.assertIn('Synthetic qualification records also appear below.', page)
        detail = page.split(f'<article class="run" id="{decisions.report.anchor("record", sid)}">', 1)[1]
        self.assertIn('No agent or model judge was run', detail.split('</article>', 1)[0])

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
        self.assertEqual(opening.count('Decision pending complete evidence'), 2)
        self.assertIn('The workspace comparison confirmed zero changed paths.', opening)
        self.assertEqual(opening.count('>Unknown</td><td>Unknown</td>'), 3)
        self.assertEqual(opening.count('>3/3<'), 2)  # The other transfer pair remains measured.
        self.assertIn('Replay receipt missing.', opening)
        for value in ('>Passed<', '>Failed<', 'Close this case on GPT-6.2 Sol.', 'Keep the skill as-is'):
            self.assertNotIn(value, opening)
