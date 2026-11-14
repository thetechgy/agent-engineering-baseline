#!/usr/bin/env python3
"""Opt-in candidate collection-to-report controls. No inference; no history publication."""
import argparse
import copy
import hashlib
import importlib.metadata
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / '.github/scripts'), str(ROOT / '.github/tests')]
import evaluator_profiles as profiles
import skill_evidence as evidence
import skill_analysis as analysis
import skill_report as report
import skill_reports as reports


def replay_controls():
    """Reuse real fixture dispatch, receipts, upstream normalization and gh grading."""
    import gh_evaluations as gh
    from skillevaluator.tier3.eval_core import atif_helpers, checks
    original = gh.module
    metrics = {}; diagnostics = []
    for arm in ('with_skill', 'without_skill'):
        for entry in gh.dataset():
            fault = {'gh-001': 'wrong-repo', 'gh-002': 'unsupported', 'gh-003': 'missing-trace',
                     'gh-014': 'unauthorized'}.get(entry['id'])
            def load(path, name):
                module = original(path, name)
                if name != 'grader': return module
                grade = module.grade
                def controlled(entry, workspace, calls, activation, fixture):
                    calls = list(calls)
                    if arm == 'with_skill':
                        content = (ROOT / '.agents/skills/gh/SKILL.md').read_text()
                        target = workspace / 'skills/gh/SKILL.md'
                        target.parent.mkdir(parents=True); target.write_text(content)
                        calls.insert(0, {'action': 'exec_command', 'action_input': {'cmd': 'cat skills/gh/SKILL.md'}, 'observation': content})
                    if fault == 'unsupported':
                        index = 1 if arm == 'with_skill' else 0
                        calls[index] = {**calls[index], 'action': 'exec', 'action_input': {'input': 'await tools.exec_command(dynamic);'}}
                    steps = [{'source': 'agent', 'tool_calls': [{'tool_call_id': str(i),
                        'function_name': call['action'], 'arguments': call['action_input']}],
                        'observation': {'results': [{'source_call_id': str(i), 'content': call.get('observation', '')}]}}
                        for i, call in enumerate(calls)]
                    normalized = atif_helpers.extract_tool_calls_as_dicts({'steps': steps})
                    activation = checks.check_activation(normalized, 'gh')
                    security = checks.check_security(normalized, expected_skill='gh')
                    result = grade(entry, workspace, normalized, activation['passed'] is True, fixture)
                    diagnostics.append({'case': entry['id'], 'arm': arm, 'control': fault or 'good',
                        'input': 'synthetic fixture replay', 'activation': activation['passed'],
                        'security': security['passed'], 'raw_custom_metrics': result['custom_metrics'],
                        'judging': 'unavailable_not_invoked'})
                    return result
                module.grade = controlled
                return module
            with patch.object(gh, 'module', side_effect=load):
                result = gh.replay_case(entry, fault=None if fault == 'unsupported' else fault)
            metrics[arm, entry['id']] = result['custom_metrics']
    return metrics, diagnostics


def render(records, output):
    bundle = output / 'public'
    inventory = evidence.inventory(ROOT)
    inventory['skills'] = [row for row in inventory['skills'] if row['source']['skill_id'] in {r['source']['skill_id'] for r in records}]
    reports.write_json(bundle / 'inventory/inventory.json', inventory)
    for record in records:
        reports.write_json(bundle / 'skills' / record['source']['skill_id'] / 'behavioral' / record['run_id'] / 'public-report.json', record)
    captured = analysis.capture_inputs([bundle])
    result = analysis.build_analysis(captured)
    analysis.validate_analysis(result, captured)
    reports.write_json(output / 'analysis.json', result)
    (output / 'report.html').write_bytes(report.render_report(result, captured))
    return result


def worker(output):
    network = []
    def offline(event, args):
        if event in ('socket.getaddrinfo', 'http.client.connect') or event == 'socket.connect' and not isinstance(args[1], (str, bytes)):
            network.append(event)
            raise PermissionError('Candidate qualification forbids external network')
    sys.addaudithook(offline)
    from test_custom_metrics import synthetic_gh_native, synthetic_native
    os.environ.update(CANDIDATE_EVIDENCE_CHILD='1', GRADING_PATCH_CHILD='1',
                      AEB_CURRENT_NATIVE=str(output / 'standard-native'), IMAGE_PREPARATION_RUNTIME='current', CURRENT_NATIVE_CONTROLS='1')
    suite = unittest.defaultTestLoader.loadTestsFromNames([
        'test_grading_evidence.GradingEvidenceTests', 'test_evaluator_candidate.CandidateEvidenceTests',
        'test_candidate_standard_grading.CandidateStandardTests',
        'test_current_native.NativeCurrentTests',
        'test_codex_pilot.PilotContracts.test_post_command_audit_failure_precedence_and_collection',
        'test_codex_pilot.PilotContracts.test_secret_delivery_uses_stdin_target_user_and_cancellation_cleanup',
        'test_codex_pilot.PilotContracts.test_final_observation_and_disposal_failures_keep_the_first_cause',
        'test_custom_metrics.CustomMetricTests.test_matching_grades_do_not_admit_stale_swapped_or_other_arm_rewards',
        'test_gh_initializer.InitializerTests.test_backend_runtime_pairs_and_wheel_python_metadata',
        'test_gh_initializer.InitializerTests.test_plugin_real_dispatch_pins_codex_and_denies_task_configuration',
        'test_gh_initializer.InitializerTests.test_start_awaits_secure_start_and_records_failures_without_agent_setup',
        'test_gh_initializer.InitializerTests.test_repeat_verification_never_rebuilds_or_creates_a_new_broker',
        'test_gh_initializer.InitializerTests.test_fixed_native_shards_cover_all_24_cases_once_per_arm',
        'test_gh_initializer.InitializerTests.test_existing_authored_healthcheck_still_rejects_baseline',
        'test_gh_initializer.InitializerTests.test_all_24_cases_both_arms_bind_native_checksums_and_initializer',
        'test_gh_initializer.InitializerTests.test_native_restaging_preserves_approved_content_identity',
        'test_gh_initializer.InitializerTests.test_missing_corrupt_altered_linked_and_hardlinked_manifests_reject',
        'test_gh_initializer.InitializerTests.test_changed_payload_arm_checksum_context_and_task_links_reject',
        'test_gh_initializer.InitializerTests.test_manifest_is_operator_owned_outside_tasks',
        'test_gh_initializer.InitializerTests.test_candidate_grader_loads_standalone_verifier_without_installed_runtime',
        'test_gh_initializer.InitializerTests.test_native_trial_failure_cannot_enter_agent_setup',
        'test_pester_evaluations.NativeStagingTests.test_native_runner_collector_and_report_do_not_score_unsupported_zero',
        'test_image_preparation.ImagePreparationTests.test_preparation_uses_exact_owning_pair_and_original_staged_bytes',
        'test_image_preparation.ImagePreparationTests.test_wrong_runtime_rejects_before_staging_or_docker',
        'test_image_preparation.ImagePreparationTests.test_timed_out_command_retains_phase_and_propagates_cancellation'])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful(): raise ValueError('Candidate evidence controls failed')
    from evaluator_scoring_compatibility import vectors
    from skillevaluator.tier3.harbor.metrics import overall_score
    for row in vectors():
        expected = round((row['security'] + row['skill_execution'] + row['skill_efficiency'] + row['accuracy'] +
                         (row['goal_accuracy'] + row['behavior_check']) / 2) / 5, 4)
        assert round(overall_score({**row, 'score_policy': profiles.owning_candidate()['scoring']}), 4) == expected
        assert overall_score({**row, 'score_policy': 'unknown-policy'}) is None
    reports.write_json(output / 'scoring-policy.json', {'policy': profiles.owning_candidate()['scoring'],
        'vectors': len(vectors()), 'synthetic': True, 'quality_measurement': False})
    metrics, diagnostics = replay_controls()
    reports.write_json(output / 'replay-controls.json', diagnostics)
    gh_root, _ = synthetic_gh_native(output / 'gh', candidate=True, candidate_metrics=metrics)
    pester_root, _ = synthetic_native(output / 'pester-carriers', candidate=True)
    records = []
    (output / 'projections').mkdir()
    for root, name in ((output / 'standard-native', 'podman'), (gh_root, 'gh'), (pester_root, 'powershell-pester-6')):
        native = evidence.normalize_behavioral(root, name)
        public = evidence.project(native)
        assert all(o['score'] is None for o in public['observations'])
        assert not public['metrics']
        # Changed bytes after admission are rejected at projection, not trusted by cached data.
        member = next(root.rglob('versions.json'), root / evidence.CUSTOM_CAPTURE); original = member.read_bytes()
        member.write_bytes(original + b' ')
        try:
            changed = evidence.project(native)
            for guard in evidence.record_guards(changed): guard()
        except ValueError: pass
        else: raise AssertionError('Altered evidence accepted')
        member.write_bytes(original)
        public = evidence.project(evidence.normalize_behavioral(root, name))
        evidence.write_outputs({'public-report.json': public}, output / 'projections' / name, input_paths=(root,))
        records.append(public)
        for key, value in (('producer_profile', 'unknown-profile'), ('scoring_policy', 'unknown-policy')):
            forged = copy.deepcopy(dict(public)); forged['policy'][key] = value
            try: evidence.validate_public(forged)
            except ValueError: pass
            else: raise AssertionError('Unknown report identity accepted')
    for omitted in ('provenance', 'policy', 'versions'):
        root = output / ('missing-' + omitted)
        shutil.copytree(output / 'standard-native', root)
        if omitted == 'policy':
            value = reports.read_json(root / 'provenance.json'); value.pop('policy')
            reports.write_json(root / 'provenance.json', value)
        else:
            (root / (omitted + '.json')).unlink()
        if omitted == 'versions':
            try: evidence.normalize_behavioral(root, 'podman')
            except ValueError: pass
            else: raise AssertionError('Candidate without runtime provenance accepted')
        else:
            value = evidence.project(evidence.normalize_behavioral(root, 'podman'))
            assert value['policy']['producer_profile'] == profiles.owning_candidate()['id']
            assert value['availability']['status'] == 'incomplete' and not analysis.measured(value)
            assert not value['metrics'] and all(o['score'] is None for o in value['observations'])
    for change in ({'evaluator_revision': 'f' * 40}, {'skillevaluator': '0.3.0'}, {'lock_sha256': '0' * 64}):
        versions = reports.read_json(output / 'standard-native/versions.json'); versions.update(change)
        try: profiles.runtime(versions, owning=True)
        except ValueError: pass
        else: raise AssertionError('Contradictory producer accepted')
    assert len(diagnostics) == 48
    for arm in ('with_skill', 'without_skill'):
        unauthorized = metrics[arm, 'gh-014']
        assert unauthorized['gh_task'] == 1 and unauthorized['gh_authorization'] == 0
        assert metrics[arm, 'gh-001']['gh_task'] == 0
        assert metrics[arm, 'gh-004']['gh_task'] == 1
    gh_record = next(r for r in records if r['source']['skill_id'] == 'gh')
    for o in gh_record['observations']:
        if o['case_id'] in ('gh-002', 'gh-003'):
            assert o['custom']['outcome'] == 'unknown' and o['scores']['security'] is None
            assert all(m['status'] == 'unavailable' for m in o['custom']['measurements'])
        if o['case_id'] == 'gh-014':
            assert o['deterministic_scores']['task'] == 1 and o['deterministic_scores']['authorization'] == 0
    historical = evidence.read_json(output / 'historical.json')
    evidence.validate_public(historical)
    assert {m['name']:m['value'] for m in historical['metrics']} == evidence.REVIEWED_METRIC_VALUES
    records.append(historical)
    candidate = next(r for r in records if r['source']['skill_id'] == 'podman' and 'producer_profile' in r['policy'])
    classification, reasons = analysis.classify(historical, candidate,
        analysis.condition_identity(historical), analysis.condition_identity(candidate))
    assert classification == 'incompatible_or_unknown' and any('evaluator_revision' in reason for reason in reasons)
    result_analysis = render(records, output)
    for skill in result_analysis['skills']:
        for comparison in skill.get('comparisons', []):
            assert comparison['classification'] != 'directly_comparable'
            assert all(m['right_minus_left'] is None for m in comparison['native_metrics'])
    assert not network
    reports.write_json(output / 'result.json', {'success': True, 'profile': profiles.owning_candidate()['id'],
        'inference': False, 'judges_invoked': False, 'history_eligible': False, 'simulated': True,
        'tests': result.testsRun, 'metadata_removal_controls': 3, 'replay_controls': len(diagnostics), 'network_attempts': network,
        'report': 'report.html', 'adoption_ready': False,
        'limits': ['synthetic collection and fixture replay', 'native container lifecycle unqualified', 'native backend execution not exercised by offline mode', 'no live agent or judge']})


def native_cohorts(output, *, lifecycle=True):
    """Existing native harnesses, then the same public analyzer and renderer."""
    initial = reports.read_json(output / 'result.json')
    initial.update(success=False, offline_controls_success=True, native_qualification='partial')
    reports.write_json(output / 'result.json', initial)
    from qualify_evaluator_candidate import native_compose_config, run_native
    native_compose_config(ROOT)
    environment = {'PATH': str(Path(sys.executable).parent) + os.pathsep + os.defpath,
        'HOME': str(output / 'empty-home'), 'PYTHONDONTWRITEBYTECODE': '1',
        'PYTHON_DOTENV_DISABLED': '1', 'LITELLM_LOCAL_MODEL_COST_MAP': 'True'}
    for key in ('TMPDIR', 'RUNNER_TEMP', 'DOCKER_CONFIG', 'COMPOSE_PLUGIN_ROOT'):
        if key in os.environ: environment[key] = os.environ[key]
    stages = {}
    commands = {
        'gh-lifecycle': "from gh_initializer_validation import main; main(sys.argv[2])",
        'gh-oracle': "from gh_oracle_validation import main; main(sys.argv[2])",
        'pester': "from pester_container_validation import main; main(candidate='current', artifact=sys.argv[2])"}
    if not lifecycle: commands.pop('gh-lifecycle')
    reports.write_json(output / 'native-stages.json', {'status': 'starting', 'stages': stages})
    for suite, code in commands.items():
        destination = output / ('native-' + suite)
        if suite == 'gh-lifecycle': destination = destination.with_suffix('.json')
        launcher = "import sys; sys.path.insert(0, sys.argv[1]); " + code
        stages[suite] = {'status': 'running'}
        reports.write_json(output / 'native-stages.json', {'status': 'running', 'stages': stages})
        log_path = output / (suite + '.log')
        with log_path.open('w') as log:
            try:
                code = run_native([sys.executable, '-I', '-B', '-c', launcher,
                    str(ROOT / '.github/scripts'), str(destination)], env=environment, log=log, timeout=5400)
                stages[suite] = {'status': 'complete' if code == 0 else 'infrastructure_error' if code == 124 else 'failed', 'returncode': code}
            except subprocess.TimeoutExpired:
                stages[suite] = {'status': 'infrastructure_error', 'code': 'native_deadline'}
        diagnostic = log_path.read_text(errors='replace')[-128 * 1024:]
        from skillevaluator.utils.redaction import redact_sensitive_text
        diagnostic = redact_sensitive_text(diagnostic)
        for path, replacement in ((ROOT, '<checkout>'), (output, '<evidence>'),
                (Path(os.environ.get('RUNNER_TEMP', '/nonexistent')), '<runner>')):
            diagnostic = diagnostic.replace(str(path), replacement)
        (output / (suite + '-diagnostics.txt')).write_text(diagnostic)
        reports.write_json(output / 'native-stages.json', {'status': 'running', 'stages': stages})
    success = all(row['status'] == 'complete' for row in stages.values())
    reports.write_json(output / 'native-stages.json', {'status': 'passed' if success else 'partial', 'stages': stages})
    captured = analysis.capture_inputs([output / 'public'])
    records = [row for row in captured.records.values() if row['kind'] == 'behavioral']
    admitted = {}
    for name, directory in (('gh', output / 'native-gh-oracle/native/reporting/public'),
                            ('powershell-pester-6', output / 'native-pester/reporting/public')):
        if not directory.exists():
            admitted[name] = {'status': 'unavailable', 'reason': 'native_public_evidence_missing'}
            success = False
            continue
        current = analysis.capture_inputs([directory])
        native = [row for row in current.records.values() if row['kind'] == 'behavioral']
        assert len(native) == 1 and native[0]['custom']['purpose'] == 'oracle_qualification'
        assert native[0]['custom']['agent'] == 'oracle' and native[0]['policy']['producer_profile'] == profiles.owning_candidate()['id']
        assert len(native[0]['observations']) == (48 if name == 'gh' else 52)
        assert native[0]['availability']['status'] == 'incomplete' and not native[0]['metrics']
        assert all(o['score'] is None for o in native[0]['observations'])
        admitted[name] = {'status': 'validated', 'observations': len(native[0]['observations'])}
        records.extend(native)
    reports.write_json(output / 'native-stages.json', {'status': 'passed' if success else 'partial', 'stages': stages})
    render(records, output)
    value = reports.read_json(output / 'result.json')
    value.update(success=success, offline_controls_success=True,
        native_qualification=('passed' if lifecycle else 'cohorts_complete') if success else 'partial', native_evidence=admitted,
        scope='synthetic transport controls and executed native oracle fixtures',
        limits=['native deterministic fixtures only', 'no live CLI/provider or judge qualification', 'no skill benefit measurement'])
    if success:
        value.update(native_gh=48, native_pester=52)
        if lifecycle: value['gh_lifecycle'] = 48
    reports.write_json(output / 'result.json', value)
    if not success: raise RuntimeError('Native cohort qualification incomplete; bounded diagnostics retained')


def complete_native_lifecycle(inputs, output):
    """Join the existing six fixed shards; consume producer artifacts as data."""
    profiles.runtime(profiles.candidate_versions(profiles.owning_candidate()), owning=True)
    assert inputs.is_absolute() and inputs.resolve() == inputs
    assert output.is_absolute() and output.resolve() == output and not output.exists()
    assert not output.is_relative_to(ROOT) and not output.is_relative_to(inputs) and not inputs.is_relative_to(output)
    attempt = os.environ.get('GITHUB_RUN_ATTEMPT', '1')
    assert attempt.isdecimal() and 0 < int(attempt) <= 100
    base = inputs / ('candidate-cohort-report-attempt-' + attempt)
    files = reports.regular_tree(inputs)
    assert len(files) <= 10000 and sum(p.stat().st_size for p in files) <= 128 * 1024 * 1024
    assert base.is_dir() and not output.exists()
    output.mkdir(parents=True, mode=0o700)
    for source in reports.regular_tree(base):
        target = output / source.relative_to(base)
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(source.read_bytes())
    provisional = reports.read_json(output / 'result.json')
    reports.write_json(output / 'result.json', dict(provisional, success=False, native_qualification='partial'))
    metadata = reports.read_json(output / 'metadata.json')
    assert metadata['producer_revision'] == evidence.git_revision(ROOT)
    assert metadata['workflow_attempt'] == attempt and metadata['workflow_run'] == os.environ['GITHUB_RUN_ID']
    assert metadata['versions'] == profiles.candidate_versions(profiles.owning_candidate())
    assert metadata['backend_sources'] == {p.name: evidence.digest_bytes(p.read_bytes())
        for p in sorted((ROOT / '.github/evaluator-backends/aeb_gh_fixture').glob('*.py'))}
    helpers = ('qualify_current_evaluator.py', 'gh_initializer_validation.py', 'gh_oracle_validation.py', 'pester_container_validation.py')
    assert metadata['harnesses'] == {name: evidence.digest_bytes((ROOT / '.github/scripts' / name).read_bytes()) for name in helpers}
    value = provisional
    success = (value.get('success') is True and value.get('native_qualification') == 'cohorts_complete'
               and value.get('native_gh') == 48 and value.get('native_pester') == 52)
    from gh_initializer_validation import STARTUP_FAULTS
    expected = {entry['id']: entry for entry in __import__('gh_evaluations').dataset(ROOT)}
    rows = []; selections = []; missing = []
    harness = hashlib.sha256((ROOT / '.github/scripts/gh_initializer_validation.py').read_bytes()).hexdigest()
    skill = hashlib.sha256((ROOT / '.agents/skills/gh/SKILL.md').read_bytes()).hexdigest()
    initializer = hashlib.sha256((ROOT / '.github/evaluator-backends/aeb_gh_fixture/initialize.py').read_bytes()).hexdigest()
    for arm in ('with_skill', 'without_skill'):
        for shard in (1, 2, 3):
            name = f'candidate-gh-{arm}-{shard}-attempt-{attempt}'
            path = inputs / name / 'native-gh.json'
            if not path.exists():
                missing.append(name); success = False; continue
            native = reports.read_json(path)
            assert native.get('runtime') == {'skillevaluator': profiles.owning_candidate()['version'], 'harbor': profiles.owning_candidate()['harbor']}
            assert native.get('harness_sha256') == harness
            assert native.get('producer_revision') == metadata['producer_revision']
            assert native.get('workflow_attempt') == attempt and native.get('workflow_run') == metadata['workflow_run']
            assert native.get('selection') == {'arm': arm, 'shard': shard, 'shards': 3}
            cases = set(sorted(expected)[(shard - 1) * 8:shard * 8])
            complete = native.get('success') is True and native.get('teardown') == {'status': 'complete'}
            observed = native.get('completed', [])
            if not complete or len(observed) != 8:
                success = False
            assert len({row['case'] for row in observed}) == len(observed)
            for row in observed:
                assert row['case'] in cases and row['arm'] == arm and row['inference'] is False
                init = row['initialization']
                assert init['status'] == 'ready' and init['initializer'] == initializer
                assert init['broker']['uid'] == 0 and init['checksum'] == row['checksum']
                metrics = row['metrics']
                assert all(metrics['gh_' + k] == 1 for k in ('evidence','commands','task','recovery','authorization','efficiency'))
                assert metrics['gh_gate'] == float(arm == 'with_skill' or expected[row['case']].get('expected_skill') is None)
                if arm == 'with_skill' and expected[row['case']].get('expected_skill'):
                    assert row['skill_read_sha256'] == skill
                fault = row.get('startup_fault')
                if row['case'] in STARTUP_FAULTS:
                    assert fault and fault['control'] == STARTUP_FAULTS[row['case']]
                    assert fault['blocked'] and fault['measurement'] == 'unscoreable' and fault['audit'] == 'unchanged'
                    assert fault['initialization']['status'] == ('cancelled' if fault['control'] == 'cancellation' else 'infrastructure_error')
                else:
                    assert fault is None
                if row.get('setup_only'):
                    assert row['setup_only'] == {'installed_codex': '0.155.1', 'inference': False}
                rows.append(row)
            selections.append({'arm': arm, 'shard': shard, 'success': complete, 'completed': len(observed)})
            target = output / 'native-gh-lifecycle-shards' / (arm + '-' + str(shard) + '.json')
            target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(path.read_bytes())
    identities = {(row['case'], row['arm']) for row in rows}
    success = success and len(rows) == 48 and identities == {(case, arm) for case in expected for arm in ('with_skill', 'without_skill')}
    reports.write_json(output / 'native-gh-lifecycle.json', {'success': success, 'expected': 48,
        'completed': rows, 'missing_shards': missing, 'selections': selections, 'inference': False,
        'runtime': {'skillevaluator': profiles.owning_candidate()['version'], 'harbor': profiles.owning_candidate()['harbor']},
        'harness_sha256': harness, 'teardown': {'status': 'complete' if success else 'inconclusive'}})
    value.update(success=success, native_qualification='passed' if success else 'partial', gh_lifecycle=len(rows))
    captured = analysis.capture_inputs([output / 'public'])
    saved = reports.read_json(output / 'analysis.json')
    analysis.validate_analysis(saved, captured)
    native_records = [r for r in captured.records.values() if r['kind'] == 'behavioral'
                      and r.get('custom', {}).get('purpose') == 'oracle_qualification']
    assert len(native_records) == 2
    assert {(r['source']['skill_id'], r['run_id'], len(r['observations'])) for r in native_records} == {
        ('gh', 'native-oracle', 48), ('powershell-pester-6', 'qualification', 52)}
    assert all(r['custom']['agent'] == 'oracle' and r['policy']['producer_profile'] == profiles.owning_candidate()['id'] for r in native_records)
    assert report.render_report(saved, captured) == (output / 'report.html').read_bytes()
    reports.write_json(output / 'result.json', value)
    if not success: raise RuntimeError('Native qualification incomplete; shard diagnostics retained')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--native-artifacts', type=Path, help='Join same-run fixed gh shards with the collected oracle report')
    parser.add_argument('--cohorts-only', action='store_true', help='Workflow runs gh lifecycle through its existing fixed shards')
    parser.add_argument('--native', action='store_true', help='Run complete credential-free native cohorts after offline controls')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.output); return
    if args.cohorts_only and not args.native: parser.error('--cohorts-only requires --native')
    if args.native_artifacts:
        complete_native_lifecycle(args.native_artifacts.absolute(), args.output.absolute()); return
    output = args.output.absolute()
    if output.resolve() != output or output.exists() or output.is_relative_to(ROOT):
        parser.error('Use a new persistent resolved output directory outside the checkout')
    p = profiles.owning_candidate()
    import aeb_gh_fixture
    backend = Path(aeb_gh_fixture.__file__).parent
    authored = ROOT / '.github/evaluator-backends/aeb_gh_fixture'
    assert {f.name: f.read_bytes() for f in backend.glob('*.py')} == {f.name: f.read_bytes() for f in authored.glob('*.py')}, 'Installed backend source differs'
    import skillevaluator
    source = Path(skillevaluator.__file__).resolve().parents[2]
    assert subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD']).decode().strip() == p['revision']
    assert hashlib.sha256((source / 'uv.lock').read_bytes()).hexdigest() == p['lock_sha256']
    versions = {'skillevaluator': p['version'], 'evaluator_revision': p['revision'], 'harbor': p['harbor'],
                'python': '.'.join(map(str, sys.version_info[:3])), 'lock_sha256': p['lock_sha256'], 'patch_sha256': p['patch_sha256']}
    profiles.runtime(versions, owning=True)
    # Bind the entire installed package tree, including newly ported helpers.
    files = {f.relative_to(source / 'src').as_posix(): hashlib.sha256(f.read_bytes()).hexdigest()
             for f in (source / 'src/skillevaluator').rglob('*') if f.is_file() and '__pycache__' not in f.parts}
    assert evidence.identity(files) == p['source_tree_digest']
    output.mkdir(parents=True, mode=0o700)
    home = output / 'empty-home'; home.mkdir(mode=0o700)
    env = {'HOME': str(home), 'PATH': os.defpath, 'TMPDIR': os.environ.get('TMPDIR', str(home)),
           'PYTHONDONTWRITEBYTECODE': '1', 'PYTHON_DOTENV_DISABLED': '1', 'LITELLM_LOCAL_MODEL_COST_MAP': 'True'}
    legacy = os.environ.get('SKILL_REVIEW_PYTHON')
    if not legacy: parser.error('SKILL_REVIEW_PYTHON must select the retained historical reporting runtime')
    historical_code = """
import sys
from pathlib import Path
project, output = map(Path, sys.argv[1:])
sys.path.insert(0,str(project / '.github/scripts'))
import skill_evidence as e
from importlib.metadata import version
assert version('skillevaluator') == '0.3.0'
native=e.normalize_behavioral(project / '.github/tests/fixtures/skill_evidence/podman-native','podman')
public=e.project(native)
for guard in e.record_guards(public): guard()
(output / 'historical.json').write_bytes(e.encoded(public))
"""
    subprocess.run([legacy, '-I', '-B', '-c', historical_code, str(ROOT), str(output)], env=env, check=True, timeout=60)
    reports.write_json(output / 'metadata.json', {'versions': versions, 'source_tree_digest': p['source_tree_digest'],
        'producer_revision': evidence.git_revision(ROOT), 'simulated': True, 'inference': False,
        'workflow_run': os.environ.get('GITHUB_RUN_ID'), 'workflow_attempt': os.environ.get('GITHUB_RUN_ATTEMPT'),
        'backend_sources': {p.name: evidence.digest_bytes(p.read_bytes()) for p in sorted((ROOT / '.github/evaluator-backends/aeb_gh_fixture').glob('*.py'))},
        'harnesses': {p.name: evidence.digest_bytes(p.read_bytes()) for p in (Path(__file__), ROOT / '.github/scripts/gh_initializer_validation.py', ROOT / '.github/scripts/gh_oracle_validation.py', ROOT / '.github/scripts/pester_container_validation.py')}})
    with (output / 'qualification.log').open('w') as log:
        result = subprocess.run([sys.executable, '-I', '-B', str(Path(__file__).resolve()), '--worker', '--output', str(output)],
                                env=env, stdout=log, stderr=subprocess.STDOUT, timeout=360)
    diagnostic = (output / 'qualification.log').read_text(errors='replace')[-512 * 1024:]
    for path, replacement in ((ROOT, '<checkout>'), (source, '<candidate>'), (output, '<evidence>')):
        diagnostic = diagnostic.replace(str(path), replacement)
    (output / 'diagnostics.txt').write_text(diagnostic)
    if result.returncode:
        print(diagnostic[-12000:], file=sys.stderr)
        raise SystemExit(result.returncode)
    if args.native:
        native_cohorts(output, lifecycle=not args.cohorts_only)
    print((output / 'result.json').read_text())


if __name__ == '__main__': main()
