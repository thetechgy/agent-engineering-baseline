"""Fixed-cohort scheduling/accounting/trust boundaries. Hosted native fixtures own readiness."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))
import codex_pilot as pilot
import codex_pilot_cohort as cohort
import codex_pilot_dispatch as dispatch
import codex_pilot_effectiveness as effect
import skill_reports as reports


class Boundaries(unittest.TestCase):
    def test_accounting_is_once_per_launch_and_blocks_unknown_nonfinite_and_negative(self):
        rows = [{**r, 'state':'unlaunched'} for r in effect.schedule()]
        self.assertEqual(cohort.accounting(rows), 0)
        for i in range(2): rows[i].update(state='completed', usage={'estimated_usd': 5})
        self.assertEqual(cohort.accounting(rows), 10)
        for value in (None, float('nan'), float('inf'), -1, True):
            rows[1]['usage']['estimated_usd'] = value
            with self.assertRaises(ValueError): cohort.accounting(rows)

    def test_measured_failure_and_unavailable_conditions_remain_distinct(self):
        audit = [{'cleanup':'complete', 'boundary_after': {'policy_sha256':'x'}}]
        def reason(outcome, usage=0, clean=True, code=0, audits=audit):
            return cohort.stop_reason({}, [{'estimated_usd':usage}], clean, code=code, audits=audits,
                                      grades=[{'classification':outcome}])
        self.assertIsNone(reason('passed')); self.assertIsNone(reason('failed'))
        self.assertEqual(reason('unsupported'), 'unsupported_grading')
        self.assertEqual(reason('timeout'), 'verifier_failure')
        self.assertEqual(reason('infrastructure_error'), 'verifier_failure')
        self.assertEqual(reason('invalid'), 'missing_usable_evidence')
        self.assertEqual(reason('passed', usage=None), 'unknown_usage')
        self.assertEqual(reason('passed', clean=False), 'cleanup_failure')
        self.assertEqual(reason('passed', code=124), 'execution_infrastructure_failure')

    def test_exact_allocation_rejects_old_pair_stale_code_and_workflow_rerun(self):
        source = 'a'*40; artifact='123'; nonce='one_dispatch'
        expected=f'cohort-{source}-{cohort.PROTOCOL}-prep{artifact}-usd15-{nonce}'
        with patch.dict(os.environ, GITHUB_RUN_ATTEMPT='1', GITHUB_EVENT_NAME='workflow_dispatch'):
            cohort.allocation(expected, source, artifact, nonce)
            for wrong in ('pilot-'+source+'-usd10', expected.replace(source,'b'*40), expected.replace('usd15','usd10')):
                with self.assertRaises(ValueError): cohort.allocation(wrong, source, artifact, nonce)
        with patch.dict(os.environ, GITHUB_RUN_ATTEMPT='2', GITHUB_EVENT_NAME='workflow_dispatch'):
            with self.assertRaises(ValueError): cohort.allocation(expected, source, artifact, nonce)

    def test_second_dispatch_cannot_reuse_even_a_failed_allocation(self):
        allocation='approved';runs=[{'id':10,'display_title':'Codex cohort approved','run_attempt':1,'event':'workflow_dispatch'},
                                   {'id':11,'display_title':'Codex cohort approved','run_attempt':1,'event':'workflow_dispatch'}]
        dispatch.first_dispatch(runs, allocation, '10')
        with self.assertRaises(ValueError): dispatch.first_dispatch(runs, allocation, '11')
        runs[0]['run_attempt']=2
        with self.assertRaises(ValueError): dispatch.first_dispatch(runs, allocation, '10')

    def test_actual_trial_config_has_one_case_no_multi_attempt_loop_or_context_reuse(self):
        try:
            import importlib.metadata
            if importlib.metadata.version('harbor') != '0.24.0': self.skipTest('Pinned native runtime required')
        except importlib.metadata.PackageNotFoundError: self.skipTest('Pinned native runtime required')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);paths=[]
            for row in effect.schedule():
                config, trial=cohort.launch_config(root,row,root/'tasks'/row['arm']/row['case'])
                value=reports.read_json(config);paths.append(trial)
                self.assertEqual(value['task']['path'],str(root/'tasks'/row['arm']/row['case']))
                self.assertEqual(value['agent']['import_path'],'codex_pilot_agent:PilotCodex')
                self.assertEqual(value['environment']['import_path'],'codex_pilot_environment:PilotEnvironment')
                self.assertIsNone(value['source_trial'])
                self.assertEqual(value['timeout_multiplier'],1)
                self.assertNotIn('n_attempts',value)
                self.assertEqual(value['agent']['kwargs'],{'version':'0.167.0','reasoning_effort':'high'})
            self.assertEqual(len(set(paths)),12)

    def test_archive_rejects_wrong_digest_and_path_traversal(self):
        import hashlib
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);archive=root/'a.zip'
            with zipfile.ZipFile(archive,'w') as z: z.writestr('../escape','not executable')
            metadata={'size_in_bytes':archive.stat().st_size,'digest':'sha256:'+hashlib.sha256(archive.read_bytes()).hexdigest()}
            with self.assertRaises(ValueError): dispatch.extract(archive,root/'out',metadata)
            metadata['digest']='sha256:'+'0'*64
            with self.assertRaises(ValueError): dispatch.extract(archive,root/'out2',metadata)
            self.assertFalse((root/'escape').exists())

    def test_preparation_rejects_wrong_protocol_and_identity_before_native_launch(self):
        # The real hosted consumer covers full successful consumption. These are
        # deliberately wrong data, rejected before credentials or any trial.
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);reference=root/'ref';staging=root/'stage'
            reports.write_json(reference/'frozen-proposal.json',{'qualified_revision':'0'*40,'protocol':{'id':'wrong'}})
            reports.write_json(reference/'qualification.json',{'complete':True,'inference':False,'revision':'0'*40})
            with patch.object(cohort.profiles,'runtime'), self.assertRaises(ValueError): cohort.check(reference,staging)
            reports.write_json(reference/'qualification.json',{'complete':False})
            with patch.object(cohort.profiles,'runtime'), self.assertRaises(ValueError): cohort.check(reference,staging)

    def test_cohort_probe_is_separate_from_live_effectiveness_in_public_reporting(self):
        import skill_analysis as analysis
        record={'custom':{'purpose':'skill_effectiveness_probe'},'policy':{}}
        self.assertIn('Credential-free', analysis.coverage_label({'behavioral_results':[record]}))
        record['custom']['purpose']='skill_effectiveness'
        self.assertIn('Prospective exploratory',analysis.coverage_label({'behavioral_results':[record]}))


if __name__ == '__main__': unittest.main()
