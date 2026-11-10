"""Immutable original evidence and credential-free replay through actual staging."""
import copy
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

CANDIDATE_RUNTIME = bool(importlib.util.find_spec('skillevaluator')) and importlib.metadata.version('skillevaluator') == '0.8.0'
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))
import codex_pilot as pilot
import codex_pilot_replay as replay
import skill_evidence as evidence
import skill_report as report


class RetrospectiveEvidence(unittest.TestCase):
    def test_replay_producer_is_distinct_from_its_oracle_execution_agent(self):
        config={'qualification':{'producer':'retained_submission_replay','inference':False}}
        self.assertTrue(evidence.oracle_purpose('cli_pilot_replay'))
        evidence.validate_custom_execution_config('cli_pilot_replay',config,1)
        with self.assertRaisesRegex(ValueError,'Retrospective purpose mismatch'):
            evidence.validate_custom_execution_config('cli_pilot_replay',{'qualification':{'producer':'oracle','inference':False}},1)
        with self.assertRaisesRegex(ValueError,'Oracle purpose mismatch'):
            evidence.validate_custom_execution_config('cli_pilot_control',config,1)

    def test_originals_keep_exact_hashes_and_unmeasured_outcomes(self):
        root, _, submissions, original = replay.corpus()
        self.assertEqual(len(original['observations']), 2)
        for arm, raw in submissions.items():
            self.assertEqual(hashlib.sha256(raw).hexdigest(), replay.SUBMISSIONS[arm])
            reward = evidence.read_json(root / arm / 'original-reward.json')
            self.assertEqual(reward['details']['outcome']['classification'], 'unsupported')
            self.assertEqual(reward['details']['outcome']['code'], 'ast_kind')
        self.assertEqual(evidence.identity(original), replay.ORIGINAL_RECORD)
        for observation in original['observations']:
            self.assertIsNone(observation['score'])
            self.assertTrue(all(m['value'] is None for m in observation['custom']['measurements']))

    def test_missing_changed_and_extra_original_evidence_is_rejected(self):
        root, _, _, _ = replay.corpus()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'original'
            shutil.copytree(root, target)
            replay.verify_original_copy(target)
            subject = target / 'with_skill/Subject.Tests.ps1'
            raw = subject.read_bytes()
            subject.write_bytes(raw + b'\n')
            with self.assertRaises(ValueError): replay.verify_original_copy(target)
            subject.write_bytes(raw); subject.unlink()
            with self.assertRaises(ValueError): replay.verify_original_copy(target)
            subject.write_bytes(raw); (target / 'extra.json').write_text('{}')
            with self.assertRaises(ValueError): replay.verify_original_copy(target)

    def test_retrospective_metadata_cannot_waive_source_or_hashes(self):
        meta = replay.retrospective_metadata()
        replay.validate_retrospective(meta)
        for key in meta:
            changed = copy.deepcopy(meta); changed[key] = None
            with self.subTest(key=key), self.assertRaises(ValueError): replay.validate_retrospective(changed)
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / 'wrong.zip'; archive.write_bytes(b'not the authenticated archive')
            with self.assertRaisesRegex(ValueError, 'digest mismatch'): replay.verify_archive(archive)

    def test_offline_entry_point_and_missing_or_inconsistent_provenance(self):
        # Real validation entry point, with every network/process attempt forbidden.
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'validated'
            with patch.object(sys, 'argv', ['replay', 'validate', '--output', str(output)]), \
                    patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')), \
                    patch.object(replay.subprocess, 'check_output', side_effect=AssertionError('Historical artifact unavailable')), \
                    patch.object(replay.subprocess, 'run', side_effect=AssertionError('Historical artifact unavailable')):
                replay.main()
                replay.verify_retained_originals(output)
            proof_path = output / 'original-authentication.json'
            proof = json.loads(proof_path.read_bytes())
            self.assertEqual(proof['producer'], 'codex-retained-replay-v2')
            self.assertFalse(proof['fresh_github_verification'])
            self.assertEqual(proof['authentication'], 'previously_authenticated_retained_evidence')
            for key, wrong in (('fresh_github_verification', True), ('source_artifact', 0),
                               ('retained_provenance_sha256', 'sha256:' + '0'*64)):
                proof_path.write_text(json.dumps({**proof, key: wrong}))
                with self.subTest(key=key), self.assertRaises(ValueError): replay.verify_retained_originals(output)
            proof_path.write_text(json.dumps(proof))
            receipt = output / 'original-provenance.json'
            raw = receipt.read_bytes(); receipt.write_bytes(raw + b'\n')
            with self.assertRaises(ValueError): replay.verify_retained_originals(output)
            receipt.unlink()
            with self.assertRaises((ValueError, OSError)): replay.verify_retained_originals(output)

    def test_required_repository_corpus_and_provenance_fail_closed(self):
        original, _, _, _ = replay.corpus()
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            corpus = workspace / replay.CORPUS
            shutil.copytree(original, corpus)
            receipt = workspace / replay.PROVENANCE
            shutil.copyfile(ROOT / replay.PROVENANCE, receipt)
            replay.retained_provenance(workspace)
            for target in (*evidence.safe_tree(corpus), receipt):
                raw = target.read_bytes()
                with self.subTest(member=target.name):
                    target.write_bytes(raw + b'\n')
                    with self.assertRaises((ValueError, OSError)): replay.retained_provenance(workspace)
                    target.unlink()
                    with self.assertRaises((ValueError, OSError)): replay.retained_provenance(workspace)
                    target.write_bytes(raw)
            value = json.loads(receipt.read_bytes())
            changed = copy.deepcopy(value); changed['source']['run_attempt'] = 2
            receipt.write_text(json.dumps(changed))
            # Rehashing a contradictory receipt does not waive semantic consistency.
            with patch.object(replay, 'PROVENANCE_SHA', hashlib.sha256(receipt.read_bytes()).hexdigest()):
                with self.assertRaisesRegex(ValueError, 'Inconsistent retained provenance'):
                    replay.retained_provenance(workspace)

    def test_source_identity_and_optional_remote_audit_fail_closed(self):
        value = evidence.read_json(ROOT / replay.PROVENANCE)
        replay.validate_source(value['artifact'], value['run'], value['repository'])
        fields = {'artifact': ('id', 'name', 'digest'), 'run': ('id', 'head_sha', 'run_attempt', 'event', 'path', 'conclusion'),
                  'repository': ('id', 'full_name')}
        for section, keys in fields.items():
            for key in keys:
                changed = copy.deepcopy(value); changed[section][key] = None
                with self.subTest(section=section, key=key), self.assertRaises(ValueError):
                    replay.validate_source(changed['artifact'], changed['run'], changed['repository'])
        with tempfile.TemporaryDirectory() as directory:
            expired = copy.deepcopy(value['artifact']); expired['expired'] = True
            run = {**value['run'], 'repository': value['repository']}
            with patch.object(replay.subprocess, 'check_output', side_effect=[json.dumps(expired), json.dumps(run)]), \
                    patch.object(replay.subprocess, 'run', side_effect=AssertionError('Must not download')):
                with self.assertRaisesRegex(ValueError, 'expired'): replay.fetch(Path(directory) / 'remote')
            self.assertFalse(replay.retained_provenance()['fresh_github_verification'])

    def test_new_producer_keeps_v4_grading_and_historical_profile(self):
        registry = evidence.custom_registry(ROOT)
        old = registry['profiles']['pester-cli-pilot-external-v4']
        new = registry['profiles']['pester-cli-pilot-retained-v2']
        self.assertNotEqual(old['runtime_digest'], new['runtime_digest'])
        self.assertEqual({k: v for k, v in old.items() if k not in ('id', 'runtime_digest')},
                         {k: v for k, v in new.items() if k not in ('id', 'runtime_digest')})
        self.assertEqual(old['runtime_digest'], 'sha256:fbbe85cde9d88a91187ac70b045d32047a00e79622bdc741bee1c71f872e115c')

    def test_workflow_preparation_has_no_remote_artifact_dependency(self):
        workflow = (ROOT / '.github/workflows/codex-pilot.yml').read_text()
        prepare = workflow.split('  prepare:', 1)[1].split('  consume:', 1)[0]
        for forbidden in ('actions: read', 'GH_TOKEN', 'original-live', 'replay.py fetch', '--authenticated'):
            self.assertNotIn(forbidden, prepare)
        self.assertIn('codex_pilot_replay.py replay --output', prepare)

    def test_existing_report_juxtaposes_originals_and_posthoc_results(self):
        _, _, _, original = replay.corpus()
        # Presentation fixture only: native execution and normalization are hosted controls.
        after = copy.deepcopy(original)
        after['custom']['retrospective'] = replay.retrospective_metadata()
        for observation in after['observations']:
            observation['custom']['outcome'] = 'failed'
            for measurement in observation['custom']['measurements']:
                measurement.update(status='measured', value=0, numerator=0)
        html = report.retrospective_outcomes(after, {replay.ORIGINAL_RECORD: original})
        for phrase in ('after inspection', 'not prospectively frozen', 'Unmeasured', 'unsupported', 'ast_kind', 'failed'):
            self.assertIn(phrase, html)
        for digest in replay.SUBMISSIONS.values(): self.assertIn(digest, html)
        with self.assertRaises(KeyError): report.retrospective_outcomes(after, {})

    @unittest.skipUnless(os.environ.get('APM_EXECUTABLE') and CANDIDATE_RUNTIME, 'Verified APM and owning candidate runtime required')
    def test_exact_replay_stage_capture_and_no_model_command(self):
        _, _, submissions, _ = replay.corpus()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            bundle, tasks, rows = pilot.stage(target, replay=replay.retrospective_metadata(), submissions=submissions)
            for arm, values in tasks.items():
                self.assertEqual(len(values), 1)
                task = values[0]
                self.assertEqual((task / 'solution/candidate').read_bytes(), submissions[arm])
                self.assertFalse((task / 'environment/build/codex_pilot_probe.py').exists())
                self.assertIn(b'ForStatementAst', (task / 'tests/Runner.ps1').read_bytes())
            capture = evidence.custom_capture(ROOT, 'powershell-pester-6', bundle, rows,
                purpose='cli_pilot_replay', attempts=1, agent='oracle', retrospective=replay.retrospective_metadata(),
                execution_policy={'environment':'docker','concurrency':2,'timeout_multiplier':1.0,'stop_on_pass':False})
            evidence.validate_custom_capture(capture, 'powershell-pester-6', ROOT)
            command = pilot.command(target, 'with_skill', replay=True)
            self.assertEqual(command[command.index('--agent') + 1], 'oracle')
            self.assertNotIn('--model', command)
            self.assertEqual(command[command.index('--max-retries') + 1], '0')
            capture['retrospective']['submission_digests']['with_skill'] = 'sha256:' + '0'*64
            with self.assertRaises(ValueError): evidence.validate_custom_capture(capture, 'powershell-pester-6', ROOT)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'exact submission identity'):
                pilot.stage(Path(directory), replay=replay.retrospective_metadata(),
                            submissions={**submissions, 'with_skill': submissions['with_skill'] + b'\n'})


if __name__ == '__main__':
    unittest.main()
