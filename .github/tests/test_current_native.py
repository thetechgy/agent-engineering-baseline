"""Candidate-only native staging and provenance controls; no Docker or model."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts'))


@unittest.skipUnless(os.environ.get('CURRENT_NATIVE_CONTROLS') == '1', 'frozen 0.8.0 runtime only')
class NativeCurrentTests(unittest.TestCase):
    def test_complete_oracle_staging_preserves_production_profile_and_rejects_entry_drift(self):
        import gh_oracle_validation as native
        import skill_evidence as e
        from harbor.models.task.task import Task
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            os.environ['SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE'] = str(root / 'key')
            bundle, fixtures, rows, arms, manifest = native.prepare(root)
            self.assertEqual(len(rows), 48)
            self.assertEqual(e.custom_registry()['active_profiles']['gh'], 'gh-deterministic-gate-v5')
            self.assertEqual({(r['arm'], r['case_id']) for r in rows},
                {(arm, case) for arm in ('with_skill', 'without_skill') for case in fixtures})
            self.assertEqual({r['task_checksum'] for r in rows},
                {Task(task).checksum for tasks in arms.values() for task in tasks})
            capture = e.custom_capture(ROOT, 'gh', bundle, rows, purpose='oracle_qualification',
                attempts=1, agent='oracle', execution_policy={'environment':'aeb-gh-fixture',
                'concurrency':2, 'timeout_multiplier':1.0, 'stop_on_pass':False})
            profile, _ = e.validate_custom_capture(capture, 'gh', ROOT)
            self.assertEqual(profile['id'], 'gh-native-oracle-v1')
            self.assertEqual(profile['grading'], 'custom_only')
            capture['execution_policy']['environment'] = 'docker'
            with self.assertRaisesRegex(ValueError, 'Execution policy drift'):
                e.validate_custom_capture(capture, 'gh', ROOT)
            task = arms['with_skill'][0]
            (task / 'tests/test.sh').write_text('echo forged')
            with self.assertRaisesRegex(ValueError, 'verifier entry'):
                e.capture_custom_tasks(ROOT, 'gh', [task], 'with_skill', purpose='oracle_qualification')

    def test_absent_native_evidence_never_inherits_offline_success(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        import qualify_current_evaluator as q
        import qualify_evaluator_candidate as legacy
        import skill_reports as reports
        for code in (0, 1):
            with self.subTest(returncode=code), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'empty-home').mkdir(); (root / 'public').mkdir()
                reports.write_json(root / 'result.json', {'success': True, 'simulated': True})
                with patch.object(legacy, 'native_compose_config'), patch.object(legacy, 'run_native', return_value=code), \
                        patch.object(q.analysis, 'capture_inputs', return_value=SimpleNamespace(records={})), patch.object(q, 'render'):
                    with self.assertRaisesRegex(RuntimeError, 'Native cohort qualification incomplete'):
                        q.native_cohorts(root)
                result = reports.read_json(root / 'result.json')
                self.assertFalse(result['success'])
                self.assertTrue(result['offline_controls_success'])
                self.assertEqual(result['native_qualification'], 'partial')
                self.assertNotIn('native_gh', result)
                self.assertNotIn('native_pester', result)
                self.assertTrue(all(row['status'] == 'unavailable' for row in result['native_evidence'].values()))
                self.assertEqual(reports.read_json(root / 'native-stages.json')['status'], 'partial')

    def test_fixture_outcome_carrier_survives_the_frozen_collector(self):
        import importlib.util
        import json
        from unittest.mock import patch
        import gh_candidate
        import gh_evaluations as gh
        from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks
        from skillevaluator.tier3.harbor import collector
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = gh_candidate.stage(ROOT, root / 'bundle/gh', ['gh-001'], fixture=True)
            task = stage_native_harbor_tasks(bundle, root / 'tasks', with_skill=True, grading_mode='custom_only')[0]
            spec = importlib.util.spec_from_file_location('fixture_grader', task / 'tests/grader.py')
            grader = importlib.util.module_from_spec(spec); spec.loader.exec_module(grader)
            trace = root / 'trajectory.json'
            target = root / 'verifier/reward.json'; target.parent.mkdir()
            for status in ('passed', 'failed', 'unknown', 'unsupported'):
                metrics = dict.fromkeys(('gh_' + key for key in ('evidence','activation','commands','task','recovery','authorization','efficiency')), 1.0)
                metrics['gh_gate'] = float(status == 'passed')
                if status == 'failed': metrics['gh_task'] = 0.0
                if status in ('unknown', 'unsupported'): metrics['gh_evidence'] = 0.0
                steps = [] if status != 'unsupported' else [{'source':'agent','tool_calls':[
                    {'tool_call_id':'0','function_name':'exec','arguments':{'input':'await tools.exec_command(dynamic);'}}],
                    'observation':{'results':[{'source_call_id':'0','content':'fixture'}]}}]
                trace.write_text(json.dumps({'steps':steps}))
                environment = {'HARBOR_TESTS_DIR':str(task / 'tests'), 'HARBOR_ENTRY_JSON':str(task / 'tests/entry.json'),
                    'HARBOR_ATIF_PATH':str(trace), 'HARBOR_WORKSPACE':str(root), 'HARBOR_REWARD_JSON':str(target),
                    'HARBOR_REWARD_TXT':str(target.with_suffix('.txt'))}
                with self.subTest(status=status), patch.dict(os.environ, environment), \
                        patch.object(grader, 'grade', return_value={'custom_metrics':metrics}):
                    grader.main()
                    result = json.loads(target.read_text())
                    collector._merge_reward_sidecars(result, target.parent)
                    result = collector._sanitize_reward_metric_surfaces(result)
                    self.assertEqual(result['details']['outcome'], {'classification':status,
                        'code':'evaluated' if status in ('passed','failed') else status})
                    if status in ('unknown','unsupported'):
                        self.assertEqual(result['evaluation_status'],'failed')
                        self.assertFalse(result['custom_metrics'])

    def test_custom_only_gh_public_admission_keeps_standard_fields_unavailable(self):
        import skill_evidence as e
        import skill_reports as reports
        import gh_oracle_validation as oracle
        from skillevaluator.tier3.harbor.collector import collect_harbor_results
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            os.environ['SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE']=str(root / 'key')
            bundle, fixtures, rows, arms, _ = oracle.prepare(root)
            jobs=root / 'jobs'
            for present in (True,False):
                arm='with_skill' if present else 'without_skill'
                job=jobs / ('gh-codex-with' if present else 'gh-codex-without')
                names=[]
                for task in (r for r in rows if r['arm']==arm):
                    case=task['case_id']; name=case+'__attempt1'; trial=job / name; names.append(name)
                    metrics={'gh_'+key:1.0 for key in e.GATE_FIELDS}
                    metrics['gh_activation']=float(present or fixtures[case].get('expected_skill') is None)
                    metrics['gh_gate']=float(all(metrics.values()))
                    numeric={'overall':metrics['gh_gate'],**metrics}
                    status='passed' if numeric['overall'] else 'failed'
                    reports.write_json(trial / 'verifier/reward.json',numeric)
                    reports.write_json(trial / 'verifier/skill_evaluator_reward.json',{'entry_id':case,
                        'has_skill':present,'overall':numeric['overall'],'evaluation_status':'complete',
                        'custom_metrics':metrics,'details':{'outcome':{'classification':status,'code':'evaluated'}}})
                    reports.write_json(trial / 'result.json',{'id':'id-'+name,'trial_name':name,'task_name':case,
                        'task_checksum':task['task_checksum'],'config':{'task':{'path':'/tasks/'+case},
                        'agent':{'name':'oracle'},'timeout_multiplier':1.0,
                        'environment':{'import_path':'aeb_gh_fixture.backend:TrustedGhEnvironment'}},
                        'agent_info':{'name':'oracle','version':'1.0.0'},'verifier_result':{'rewards':numeric},
                        'exception_info':None,'started_at':'2026-11-06T00:00:00Z','finished_at':'2026-11-06T00:00:02Z',
                        'verifier':{'started_at':'2026-11-06T00:00:01Z','finished_at':'2026-11-06T00:00:02Z'}})
                reports.write_json(job / 'result.json',{'n_total_trials':24,'stats':{'n_trials':24,'n_errors':0,
                    'evals':{'synthetic__oracle___tasks':{'n_trials':24,'n_errors':0,'reward_stats':{'reward':{'1.0':names}}}}}})
            native=root / 'native'; run=native / 'results/gh/synthetic-oracle-regression'
            collected=collect_harbor_results('gh',['codex'],run,jobs,expected_cases=24,expected_case_ids=list(fixtures),
                expected_trials=24,agent_models={'codex':{'model':'synthetic-control','source':'regression'}})
            reports.write_json(run / 'run_config.json',{'grading':{'mode':'custom_only'},'judge':{'enabled':False},
                'qualification':{'producer':'oracle','inference':False}})
            reports.write_json(run / 'result.json',{**collected,'skill_name':'gh','report_status':'incomplete','diagnostic_only':True})
            reports.write_json(native / e.CUSTOM_CAPTURE,e.custom_capture(ROOT,'gh',bundle,rows,purpose='oracle_qualification',
                attempts=1,agent='oracle',execution_policy={'environment':'aeb-gh-fixture','concurrency':2,
                'timeout_multiplier':1.0,'stop_on_pass':False},
                numeric_excerpts=e.capture_custom_numeric_fields(ROOT,'gh',jobs,root,rows,purpose='oracle_qualification')))
            sanitized=root / 'sanitized'
            reports.benchmark_artifacts(ROOT,native,'gh',sanitized)
            self.assertEqual(reports.read_json(sanitized / e.CUSTOM_CAPTURE)['tasks'], rows)
            public=e.project(e.normalize_behavioral(sanitized,'gh'))
            e.validate_public(public)
            from pester_container_validation import _qualify_reporting
            _qualify_reporting(root, sanitized, candidate=True, name='gh')
            self.assertTrue((sanitized / 'reporting/consolidated.html').is_file())
            self.assertEqual(len(public['observations']),48)
            self.assertEqual(public['custom']['profile_id'],'gh-native-oracle-v1')
            self.assertEqual(public['policy']['fields']['workspace_mode'],'group')
            for arm in public['arms']:
                self.assertEqual(arm['condition']['workspace_mode'],'group')
                self.assertEqual(arm['condition']['execution']['fixture_boundary'],'root-broker-unprivileged-agent-v1')
                self.assertEqual(arm['condition']['competing_skills'][0]['skill_id'],'github-actions-hardening')
            for obs in public['observations']:
                self.assertIsNone(obs['deterministic_gate'])
                self.assertTrue(all(v is None for v in obs['deterministic_scores'].values()))
                self.assertIsNone(obs['score'])
                self.assertTrue(any(m['status']=='measured' for m in obs['custom']['measurements']))

            import copy
            forged=copy.deepcopy(dict(public))
            forged['observations'][0]['deterministic_gate']=1.0
            with self.assertRaisesRegex(ValueError, 'Custom-only result implies'):
                e.validate_public(forged)
