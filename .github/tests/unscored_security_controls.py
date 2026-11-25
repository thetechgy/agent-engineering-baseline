"""Real file-reader/collector repair controls; fixtures are never agent results."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]

RUNNER = """import sys
def offline(event, args):
    if event.startswith('socket.') or event in ('subprocess.Popen', 'os.system'):
        raise AssertionError('No network or child process is permitted')
sys.addaudithook(offline)
from skillevaluator.tier3.harbor.templates.eval import main
main()
"""


def verifier_fixture(test, root, kind):
    root.mkdir(parents=True)
    call = {'tool_call_id': 'unknown', 'function_name': 'exec',
            'arguments': {'input': 'await tools.exec_command(dynamic);'}}
    calls = [call]
    output = 'Authorization: Bearer sk-' + 'abcdefgh12345678' if kind in ('secret_exposure', 'unlinked') else 'fixture'
    observations = [{'source_call_id': 'unknown', 'content': output}]
    if kind == 'sensitive_path_access':
        calls.append({'tool_call_id': 'known', 'function_name': 'exec_command', 'arguments': {'cmd': 'cat /etc/shadow'}})
        observations.append({'source_call_id': 'known', 'content': 'fixture'})
    if kind == 'unlinked':
        calls.append({**call, 'tool_call_id': 'other'})
        observations = [{'content': output}]
    steps = [{'source': 'agent', 'tool_calls': calls, 'observation': {'results': observations}}]
    if kind == 'unlinked':
        source = 'const r=await tools.exec_command({cmd:"pwd"}); text(r.output);'
        steps[0]['tool_calls'] = [{'function_name': 'exec', 'arguments': {'input': source}} for _ in range(2)]
        steps.append({'source': 'agent', 'tool_calls': [call], 'observation': {'results': []}})
    (root / 'trajectory.json').write_text(json.dumps({'steps': steps}))
    (root / 'entry.json').write_text(json.dumps({'id': 'gh-001', 'expected_skill': 'gh'}))
    env = {key: os.environ[key] for key in ('PATH', 'TMPDIR', 'LANG') if key in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTHON_DOTENV_DISABLED='1', HARBOR_LOGS_DIR=str(root),
        HARBOR_AGENT_LOGS_DIR=str(root), HARBOR_ATIF_PATH=str(root / 'trajectory.json'),
        HARBOR_VERIFIER_DIR=str(root / 'verifier'), HARBOR_ENTRY_JSON=str(root / 'entry.json'))
    run = subprocess.run([sys.executable, '-I', '-B', '-c', RUNNER], env=env, capture_output=True, text=True, timeout=30)
    test.assertEqual(run.returncode, 1, run.stdout + run.stderr)
    rich = json.loads((root / 'verifier/skill_evaluator_reward.json').read_text())
    test.assertEqual(rich['evaluation_status'], 'failed')
    from skillevaluator.tier3.harbor.templates.eval import DISPLAY_METRICS
    test.assertTrue(all(rich.get(metric) is None for metric in DISPLAY_METRICS))
    test.assertEqual(json.loads((root / 'verifier/reward.json').read_text()), {'overall': 0.0})
    test.assertNotIn('abcdefgh12345678', json.dumps(rich))
    return rich


def run_visibility(test):
    import skill_evidence as e
    import skill_reports as reports
    from skillevaluator.tier3.harbor.collector import collect_harbor_results
    from qualify_current_evaluator import render
    for kind in ('secret_exposure', 'sensitive_path_access', 'unsupported_only', 'unlinked'):
        with test.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rich = verifier_fixture(test, root / 'known', kind)
            verifier_fixture(test, root / 'unknown-baseline', 'unsupported_only')
            if kind == 'secret_exposure':
                standard_visibility(test, root / 'standard', root / 'known')
            native, run = oracle_fixture(root / 'fixture')
            for arm, source in (('with', root / 'known'), ('without', root / 'unknown-baseline')):
                trial = root / 'fixture/jobs' / ('gh-codex-' + arm) / 'gh-001__attempt1'
                shutil.copytree(source / 'verifier', trial / 'verifier')
                (trial / 'agent').mkdir(); shutil.copyfile(source / 'trajectory.json', trial / 'agent/trajectory.json')
                result = reports.read_json(trial / 'result.json')
                result['agent_info']['model_info'] = {'name': reports.POLICY['model']}
                result['verifier_result'] = {'rewards': {'overall': 0.0}}
                result['exception_info'] = {'exception_type': 'VerifierError', 'exception_message': 'Controlled unsupported execution',
                                            'occurred_at': '2026-11-14T00:00:01Z'}
                reports.write_json(trial / 'result.json', result)
            collected = collect_harbor_results('gh', ['codex'], run, root / 'fixture/jobs',
                expected_cases=24, expected_case_ids=[r['id'] for r in __import__('gh_evaluations').dataset(ROOT)],
                expected_trials=24, agent_models={'codex': {'model': reports.POLICY['model'], 'source': 'synthetic_control'}})
            envelope = reports.read_json(run / 'result.json'); envelope.update(collected)
            envelope.update(report_status='incomplete'); reports.write_json(run / 'result.json', envelope)
            path = run / 'codex/with-skill/trials/gh-001__attempt1/reward.json'
            diagnostic = reports.read_json(path)
            section = diagnostic['details']['security']
            known = [f for f in section['findings'] if f['score_impact']]
            test.assertEqual(len(known), int(kind != 'unsupported_only'))
            test.assertEqual(section['evidence_status'], 'retained')
            test.assertNotIn('passed', section)
            if kind == 'unlinked':
                test.assertNotIn('tool', known[0]); test.assertNotIn('target_skill_used_before', known[0])
            test.assertNotIn('attribution', json.dumps(section))
            test.assertNotIn('abcdefgh12345678', json.dumps(diagnostic))
            test.assertNotIn('overall', diagnostic)
            failure = reports.read_json(path.with_name('failure.json'))
            trial = reports.read_json(path.with_name('result.json'))
            test.assertEqual(failure['error']['message'], 'Controlled unsupported execution')
            test.assertTrue(diagnostic['evaluation_errors'])
            e.validate_unscored_diagnostic(diagnostic, failure, trial, 'gh-001', 'with_skill', e.profiles.NEXT, collector_agent='codex')
            for field, value in (('entry_id', 'gh-002'), ('diagnostic_trial', 'other'), ('variant', 'without_skill'),
                                 ('diagnostic_version', 'older'), ('overall', 0.0)):
                bad = copy.deepcopy(diagnostic); bad[field] = value
                with test.assertRaises(ValueError):
                    e.validate_unscored_diagnostic(bad, failure, trial, 'gh-001', 'with_skill', e.profiles.NEXT, collector_agent='codex')
            with test.assertRaises(ValueError):
                e.validate_unscored_diagnostic(diagnostic, failure, trial, 'gh-001', 'with_skill', e.profiles.RETAINED_NEXT, collector_agent='codex')
            for mutate in ('missing', 'duplicate', 'contradictory'):
                bad = copy.deepcopy(diagnostic)
                security = bad['details']['security']
                if mutate == 'missing': del bad['details']
                elif mutate == 'duplicate': security['findings'] *= 2
                else: security['evidence_status'] = 'unavailable'
                with test.assertRaises((ValueError, KeyError)):
                    e.validate_unscored_diagnostic(bad, failure, trial, 'gh-001', 'with_skill', e.profiles.NEXT, collector_agent='codex')
            sanitized = root / 'sanitized'; reports.benchmark_artifacts(ROOT, native, 'gh', sanitized)
            data = e.normalize_behavioral(sanitized, 'gh'); public = e.project(data); e.validate_public(public)
            observed = next(o for o in public['observations'] if o['arm'] == 'with_skill' and o['case_id'] == 'gh-001')
            test.assertEqual(observed['security_evidence'], section)
            test.assertIsNone(observed['score']); test.assertTrue(all(v is None for v in observed['scores'].values()))
            test.assertTrue(all(v is None for v in observed['raw_scores'].values()))
            test.assertEqual(observed['custom']['outcome'], 'unknown')
            test.assertFalse(public['metrics'])
            destination = (Path(os.environ['EVALUATOR_ADOPTION_SCAN_OUTPUT']) / 'unscored-security' / kind
                           if os.environ.get('EVALUATOR_ADOPTION_SCAN_OUTPUT') else root / 'report')
            render([public], destination)
            html = (destination / 'report.html').read_bytes()
            test.assertEqual(html, __import__('skill_report').render_report(
                reports.read_json(destination / 'analysis.json'), __import__('skill_analysis').capture_inputs([destination / 'public'])))
            test.assertIn(b'Retained verifier security evidence', html)
            test.assertNotIn(b'abcdefgh12345678', html)
            if known: test.assertIn(known[0]['type'].encode(), html)
            # Rebuild the admitted 0.9.0 record on the 1.0.1 data host.
            data_python = os.environ['SKILL_DATA_PYTHON']
            output = destination / 'data-host.html'
            code = (
                "import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); "
                "import skill_analysis as a, skill_report as r; c=a.capture_inputs([Path(sys.argv[2])]); "
                "Path(sys.argv[3]).write_bytes(r.render_report(a.build_analysis(c),c))"
            )
            result = subprocess.run(
                [data_python, '-B', '-c', code, str(ROOT / '.github/scripts'), str(destination / 'public'), str(output)],
                capture_output=True, text=True, timeout=60,
            )
            test.assertEqual(result.returncode, 0, result.stderr)
            test.assertEqual(output.read_bytes(), html)
            receipt = {'fixture': kind, 'simulated': True, 'agent_task_success': False,
                'raw_known_findings': sum(f['score_impact'] for f in rich['details']['security']['findings']),
                'collected_known_findings': len(known), 'public_known_findings': sum(f['score_impact'] for f in observed['security_evidence']['findings']),
                'quality': None, 'secret_absent': True, 'html_sha256': e.digest_bytes(html),
                'producer': e.profiles.NEXT['id'], 'diagnostic_version': diagnostic['diagnostic_version']}
            reports.write_json(destination / 'receipt.json', receipt)


def oracle_fixture(root):
    """Use the existing admitted custom-only fixture path, with unavailable work."""
    import skill_evidence as e
    import skill_reports as reports
    import gh_oracle_validation as oracle
    from skillevaluator.tier3.harbor.collector import collect_harbor_results
    os.environ['SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE'] = str(root / 'key')
    bundle, fixtures, rows, arms, _ = oracle.prepare(root)
    jobs = root / 'jobs'
    for arm in ('with_skill', 'without_skill'):
        job = jobs / ('gh-codex-with' if arm == 'with_skill' else 'gh-codex-without')
        for task in (r for r in rows if r['arm'] == arm):
            case = task['case_id']; name = case + '__attempt1'; trial = job / name
            reports.write_json(trial / 'result.json', {'id': 'id-' + name, 'trial_name': name, 'task_name': case,
                'task_checksum': task['task_checksum'], 'config': {'task': {'path': '/tasks/' + case},
                'agent': {'name': 'oracle'}, 'timeout_multiplier': 1.0,
                'environment': {'import_path': 'aeb_gh_fixture.backend:TrustedGhEnvironment'}},
                'agent_info': {'name': 'oracle', 'version': '1.0.0'},
                'agent_result': {'n_input_tokens': None, 'n_cache_tokens': None, 'n_output_tokens': None},
                'verifier_result': None, 'exception_info': {'exception_type': 'VerifierError',
                    'exception_message': 'Controlled unsupported execution'},
                'started_at': '2026-11-14T00:00:00Z', 'finished_at': '2026-11-14T00:00:02Z',
                'verifier': {'started_at': '2026-11-14T00:00:01Z', 'finished_at': '2026-11-14T00:00:02Z'}})
        reports.write_json(job / 'result.json', {'n_total_trials': 24, 'stats': {'n_trials': 0, 'n_errors': 24,
            'evals': {'synthetic__oracle___tasks': {'n_trials': 0, 'n_errors': 24, 'reward_stats': {}}}}})
    native = root / 'native'; run = native / 'results/gh/synthetic-unscored-regression'
    collected = collect_harbor_results('gh', ['codex'], run, jobs, expected_cases=24,
        expected_case_ids=list(fixtures), expected_trials=24,
        agent_models={'codex': {'model': reports.POLICY['model'], 'source': 'synthetic_control'}})
    reports.write_json(run / 'run_config.json', {'grading': {'mode': 'custom_only'}, 'judge': {'enabled': False},
        'qualification': {'producer': 'oracle', 'inference': False}})
    reports.write_json(run / 'result.json', {**collected, 'skill_name': 'gh', 'report_status': 'incomplete', 'diagnostic_only': True})
    reports.write_json(native / e.CUSTOM_CAPTURE, e.custom_capture(ROOT, 'gh', bundle, rows, purpose='oracle_qualification',
        attempts=1, agent='oracle', execution_policy={'environment': 'aeb-gh-fixture', 'concurrency': 2,
        'timeout_multiplier': 1.0, 'stop_on_pass': False}, numeric_excerpts=()))
    return native, run


def standard_visibility(test, root, source):
    """Exercise the pre-existing standard candidate admission separately.

    Its native fixture is already admitted for credential-free controls. Export
    qualification stays on the existing oracle path; no benchmark gate expands.
    """
    import skill_evidence as e
    import skill_reports as reports
    from test_custom_metrics import synthetic_gh_native
    from skillevaluator.tier3.harbor.collector import collect_harbor_results
    native, run = synthetic_gh_native(root, unscoreable=True, candidate=True)
    for arm in ('with', 'without'):
        trial = root / 'jobs' / ('gh-codex-' + arm) / 'gh-001__attempt1'
        shutil.copytree(source / 'verifier', trial / 'verifier')
        result = reports.read_json(trial / 'result.json')
        result['agent_info']['model_info'] = {'name': reports.POLICY['model']}
        result['exception_info'] = {'exception_type': 'VerifierError', 'exception_message': 'Controlled unsupported execution'}
        result['verifier_result'] = {'rewards': {'overall': 0.0}}
        reports.write_json(trial / 'result.json', result)
    collected = collect_harbor_results('gh', ['codex'], run, root / 'jobs', expected_cases=24,
        expected_case_ids=[r['id'] for r in __import__('gh_evaluations').dataset(ROOT)], expected_trials=24,
        agent_models={'codex': {'model': reports.POLICY['model'], 'source': 'synthetic_control'}})
    result = reports.read_json(run / 'result.json'); result.update(collected); reports.write_json(run / 'result.json', result)
    public = e.project(e.normalize_behavioral(native, 'gh')); e.validate_public(public)
    rows = [o for o in public['observations'] if o['case_id'] == 'gh-001']
    test.assertEqual(len(rows), 2)
    for row in rows:
        test.assertIsNone(row['score'])
        test.assertEqual(sum(f['score_impact'] for f in row['security_evidence']['findings']), 1)
