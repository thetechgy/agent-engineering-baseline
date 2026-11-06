#!/usr/bin/env python3
"""Frozen candidate collection-to-report controls. No inference; no history publication."""
import argparse
import copy
import hashlib
import importlib.metadata
import json
import os
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
                      AEB_CURRENT_NATIVE=str(output / 'standard-native'), IMAGE_PREPARATION_RUNTIME='current')
    suite = unittest.defaultTestLoader.loadTestsFromNames([
        'test_grading_evidence.GradingEvidenceTests', 'test_evaluator_candidate.CandidateEvidenceTests',
        'test_candidate_standard_grading.CandidateStandardTests',
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
        assert round(overall_score({**row, 'score_policy': profiles.CANDIDATE['scoring']}), 4) == expected
        assert overall_score({**row, 'score_policy': 'unknown-policy'}) is None
    reports.write_json(output / 'scoring-policy.json', {'policy': profiles.CANDIDATE['scoring'],
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
    reports.write_json(output / 'result.json', {'success': True, 'profile': profiles.CANDIDATE['id'],
        'inference': False, 'judges_invoked': False, 'history_eligible': False, 'simulated': True,
        'tests': result.testsRun, 'replay_controls': len(diagnostics), 'network_attempts': network,
        'report': 'report.html', 'adoption_ready': False,
        'limits': ['synthetic collection and fixture replay', 'native container lifecycle unqualified', 'trusted gh backend remains 0.7.2-only', 'no live agent or judge']})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.output); return
    output = args.output.absolute()
    if output.resolve() != output or output.exists() or output.is_relative_to(ROOT):
        parser.error('Use a new persistent resolved output directory outside the checkout')
    p = profiles.CANDIDATE
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
        'producer_revision': evidence.git_revision(ROOT), 'simulated': True, 'inference': False})
    with (output / 'qualification.log').open('w') as log:
        result = subprocess.run([sys.executable, '-I', '-B', str(Path(__file__).resolve()), '--worker', '--output', str(output)],
                                env=env, stdout=log, stderr=subprocess.STDOUT, timeout=240)
    diagnostic = (output / 'qualification.log').read_text(errors='replace')[-512 * 1024:]
    for path, replacement in ((ROOT, '<checkout>'), (source, '<candidate>'), (output, '<evidence>')):
        diagnostic = diagnostic.replace(str(path), replacement)
    (output / 'diagnostics.txt').write_text(diagnostic)
    if result.returncode:
        print(diagnostic[-12000:], file=sys.stderr)
        raise SystemExit(result.returncode)
    print((output / 'result.json').read_text())


if __name__ == '__main__': main()
