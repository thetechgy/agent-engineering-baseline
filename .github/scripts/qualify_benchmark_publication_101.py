"""Validate the current released reports through a credential-free publication route."""
import argparse
from contextlib import contextmanager
from pathlib import Path
import sys
from unittest.mock import patch

import benchmark_evidence as benchmark
import evaluator_profiles as profiles
from qualify_benchmark_101 import RELEASE_CANDIDATE, ROOT, fixture_owner
from qualify_benchmark_evidence import fixture
import skill_evidence as evidence
import skill_history
import skill_reports as reports

PROFILE = reports.read_json(ROOT / '.github/evals/benchmark-121-direct-fixture.json')
META = {'profile': PROFILE['id'], 'origin': PROFILE['origin'], 'judgments': 'simulated'}


@contextmanager
def publication_owner():
    """Register this offline policy only in the qualification entry point."""
    previous = profiles.benchmark_profile

    def profile(identifier):
        return PROFILE if identifier == PROFILE['id'] else previous(identifier)

    reports.require(hasattr(evidence, 'validate_101_partial_rollups'), 'Use the reviewed publication source export')
    with fixture_owner() as versions, patch.object(profiles, 'benchmark_profile', profile):
        yield versions


def prohibit_network(event, _):
    if event.startswith('socket.') or event == 'http.client.connect':
        raise PermissionError('Publication qualification is offline')


def control(callback, expected):
    try:
        callback()
    except ValueError as error:
        reports.require(str(error) == expected, f'Unexpected publication rejection: {error}')
    else:
        raise ValueError('Publication admitted invalid fixture evidence')


def publish(workspace, output, scenario, mode):
    raw = fixture(output, scenario, producer=RELEASE_CANDIDATE, mode=mode, metadata=META,
                  model=reports.POLICY['model'], codex=reports.POLICY['codex'], accuracy_factor=0.8, workspace=workspace)
    sanitized = output / 'sanitized'
    reports.benchmark_artifacts(workspace, raw, 'podman', sanitized)
    public = benchmark.report(workspace, sanitized, 'podman', mode, output / 'report')
    matched = public['policy']
    reports.require(matched['producer_profile'] == PROFILE['producer']
        and matched['attempts']['mode'] == mode and matched['attempts']['maximum'] == reports.MODES[mode],
        'Public producer or attempt policy changed')
    admission = benchmark.history_admission(public)
    control(lambda: skill_history.observation(public, 'standard--podman', {}, '2026-11-15T00:00:00Z'),
            'Offline behavioral evidence cannot enter production history')
    reports.require(admission['eligible'] is False and 'simulated_judgments' in admission['reasons'],
                    'Fixture entered production history')
    attempts = sum(arm['coverage']['expected_attempts'] for arm in public['arms'])
    reports.require(attempts == 20 * reports.MODES[mode], 'Public denominator changed')
    reports.require(all('sk-abcdefgh12345678' not in p.read_text() for p in (output / 'report').rglob('*.json')),
                    'Public report contains private fixture material')
    behavioral = public['benchmark']
    if scenario == 'complete':
        reports.require(behavioral['native_status'] == 'complete'
            and len(public['observations']) == attempts
            and all(row['quality']['overall'] is not None for row in behavioral['observations'])
            and not public['metrics'], 'Complete fixture lost native observations or acquired headline metrics')
    elif scenario == 'unavailable':
        outcomes = {row['outcome'] for row in behavioral['observations']}
        reports.require(behavioral['native_status'] == 'incomplete'
                        and {'judgment_unavailable', 'runtime_failure'} <= outcomes and 'incomplete' in admission['reasons'],
                        'Missing judge or execution data acquired a verdict')
    elif scenario == 'interrupted':
        reports.require(behavioral['recovery'] and len(public['observations']) < attempts
                        and 'recovered' in admission['reasons'], 'Recovery appeared complete')
    return {'mode': mode, 'availability': public['availability']['status'],
            'native_status': behavioral['native_status'], 'expected_attempts': attempts,
            'observed_attempts': len(public['observations']), 'history': admission,
            'outcomes': sorted({row['outcome'] for row in public['benchmark']['observations']})}


def main(workspace, output):
    root = output.absolute()
    reports.require(root.resolve() == root and not root.is_relative_to(workspace), 'Unsafe publication fixture output')
    root.mkdir(exist_ok=False)
    sys.addaudithook(prohibit_network)
    with publication_owner() as versions:
        records = {}
        for scenario, mode in (('complete', 'standard'), ('complete', 'confirmation'),
                               ('unavailable', 'standard'), ('interrupted', 'standard')):
            name = f'{scenario}-{mode}'
            records[name] = publish(workspace, root / name, scenario, mode)
        unavailable = root / 'unavailable-standard/sanitized'
        failure_file = (unavailable / 'results/podman/unavailable/codex/with-skill/trials'
                        / 'skillevaluator-4__attempt001/failure.json')
        failure = reports.read_json(failure_file)
        reports.write_json(failure_file, {**failure, 'trial': 'different-trial'})
        try:
            control(lambda: reports.public_benchmark(workspace, unavailable, 'podman', 'standard', root / 'wrong-trial'),
                    'Unscored diagnostic failure identity mismatch')
        finally:
            reports.write_json(failure_file, failure)
        standard = root / 'complete-standard/sanitized'
        control(lambda: reports.public_benchmark(workspace, standard, 'podman', 'confirmation', root / 'wrong-mode'),
                'Public benchmark mode mismatch')
        provenance_file = standard / 'provenance.json'
        provenance = reports.read_json(provenance_file)
        provenance['benchmark']['profile'] = 'behavioral-090-offline-v1'
        reports.write_json(provenance_file, provenance)
        try:
            control(lambda: reports.public_benchmark(workspace, standard, 'podman', 'standard', root / 'wrong-owner'),
                    'Versioned benchmark producer mismatch')
        finally:
            provenance['benchmark']['profile'] = PROFILE['id']
            reports.write_json(provenance_file, provenance)
    series = {records[name]['history']['series'] for name in ('complete-standard', 'complete-confirmation')}
    reports.require(len(series) == 2, 'Standard and confirmation pooled into one series')
    reports.write_json(root / 'qualification.json', {'runtime': versions, 'score_policy': PROFILE,
        'revision': evidence.git_revision(workspace), 'reader': evidence.digest_bytes(Path(evidence.__file__).read_bytes()),
        'inference': False, 'cases': records,
        'rejected': ['canonical-history', 'wrong-mode', 'wrong-owner', 'wrong-trial']})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    main(args.workspace.resolve(), args.output)
