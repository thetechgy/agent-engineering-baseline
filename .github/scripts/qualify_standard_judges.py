#!/usr/bin/env python3
"""Credential-free standard-judge preparation and data-only report reproduction.

There is deliberately no live/dispatch action. Reuses the owning runtime, native
verifier/collector, benchmark admission and consolidated renderer.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / '.github/scripts'), str(ROOT / '.github/tests')]
import benchmark_evidence as benchmark
import evaluator_profiles as profiles
import judge_transport_090 as transport
import skill_evidence as evidence
import skill_reports as reports

SOURCES = ('.github/scripts/qualify_standard_judges.py', '.github/scripts/judge_transport_090.py',
           '.github/scripts/qualify_benchmark_evidence.py')
CORPUS = ROOT / '.github/evals/judge-calibration-090/corpus.json'
SCENARIOS = {'1': 'valid', '2': 'wrong_shape', '3': 'valid', '4': 'partial',
             '5': 'valid', '6': 'missing_usage', '7': 'schema_fallback',
             '8': 'valid', '9': 'transient_retry', '10': 'timeout'}


def corpus():
    value = reports.read_json(CORPUS)
    reports.require(value['status'] == 'UNRUN' and value['paid_authority'] is False, 'Corpus cannot authorize execution')
    for row in value['items']:
        reports.require(row['observed'] == 'UNRUN', 'Fixture cannot become a live judgment')
        for source in row['sources']:
            path = ROOT / source['path']
            reports.require(path.resolve().is_relative_to(ROOT) and not path.is_symlink()
                and hashlib.sha256(path.read_bytes()).hexdigest() == source['sha256'], 'Corpus source differs')
    return value


def render(output):
    import skill_analysis as analysis
    import skill_report as report
    captured = analysis.capture_inputs([output / 'reporting/public'])
    result = analysis.build_analysis(captured)
    analysis.validate_analysis(result, captured)
    proof = reports.read_json(output / 'qualification.json')
    reports.require(proof['origin'] == 'credential_free_fixture' and proof['live_judgments'] == 'UNRUN'
                    and proof['paid_authority'] is False, 'Qualification cannot become live evidence')
    reports.require(set(proof['handoff']) == {'requests.json'} and set(proof['sources']) == set(SOURCES),
                    'Incomplete qualification identity')
    for name, digest in proof['handoff'].items():
        reports.require(name in ('requests.json',) and hashlib.sha256((output / name).read_bytes()).hexdigest() == digest,
                        'Qualification handoff differs')
    for name, digest in proof['sources'].items():
        reports.require(name in SOURCES and hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest,
                        'Qualification source differs')
    frozen = corpus()
    reports.require(proof['corpus_sha256'] == hashlib.sha256(CORPUS.read_bytes()).hexdigest(), 'Corpus handoff differs')
    section = '<section aria-labelledby="calibration"><h2 id="calibration">Standard judge calibration: UNRUN</h2>'
    section += '<p>Fixture transport only. No live judgments, accuracy, skill benefit or paid authority. '
    section += 'Independent task failures remain failures; contradictions require review and are never averaged away.</p>'
    section += report.table('Frozen reference outcomes', ['Item', 'Judgment', 'Expected', 'Observed', 'Independent evidence', 'Limits'],
        [[report.safe(row[k]) for k in ('id', 'judgment', 'expected', 'observed', 'reference', 'ambiguity')]
         for row in frozen['items']])
    section += report.table('Transport qualification', ['Control', 'HTTP requests', 'Logical attempts', 'Provider failure', 'Usage coverage'],
        [[report.safe(row['scenario']), report.safe(row['requests']), report.safe(row['attempts']),
          report.safe(row['errors']), report.safe(row['usage'])] for row in proof['controls']])
    section += '<p>OpenAI gpt-5.6-sol, reasoning effort omitted by released gpt-5 selector; native chat payload, strict/replace; local transport only. '
    section += 'Provider usage is discarded upstream and logical attempts undercount retries. Paid calibration is blocked.</p></section>'
    html = report.render_report(result, captured)
    reports.require(html.count(b'</main>') == 1, 'Consolidated report boundary differs')
    return html.replace(b'</main>', section.encode() + b'</main>')


def worker(output):
    from skillevaluator.tier3.harbor.templates import eval as verifier
    from skillevaluator.tier3.harbor.runner import _budget_usage
    from qualify_benchmark_evidence import fixture
    from qualify_current_evaluator import render as render_native
    profiles.runtime(profiles.candidate_versions(profiles.NEXT), owning=True)
    corpus()
    responder = transport.Responder()
    blocked = []
    controls = []
    with responder.boundary() as port:
        def offline(event, args):
            if event == 'socket.connect':
                address = args[1]
                if not isinstance(address, tuple) or address[:2] != ('127.0.0.1', port):
                    blocked.append(event)
                    raise RuntimeError('Qualification forbids external network')
            if event == 'socket.getaddrinfo' and (args[0], args[1]) != ('127.0.0.1', port):
                blocked.append(event)
                raise RuntimeError('Qualification forbids external DNS')
        sys.addaudithook(offline)

        @contextmanager
        def context(module, case):
            start = len(responder.requests)
            with responder.case(module, SCENARIOS[case]):
                yield
            attempt_file = module._verifier_output_dir() / 'judge_attempts.json'
            reports.require(attempt_file.is_file() or case == '5', 'Missing judge diagnostics')
            attempts = reports.read_json(attempt_file)['attempts'] if attempt_file.is_file() else []
            rows = responder.requests[start:]
            def has_usage(value):
                if isinstance(value, dict):
                    return bool(set(value) & {'usage', 'prompt_tokens', 'completion_tokens', 'total_tokens'}) or any(has_usage(v) for v in value.values())
                return isinstance(value, list) and any(has_usage(v) for v in value)
            reward = reports.read_json(module.SKILL_EVALUATOR_REWARD_JSON)
            reports.require(not has_usage([attempts, reward]), 'Released provider usage contract changed')
            controls.append({'scenario': SCENARIOS[case], 'case': case, 'requests': len(rows), 'attempts': len(attempts),
                'errors': [r['metric'] for r in attempts if r['status'] != 'accepted'],
                'usage': {'http_responses_with_usage': sum(r.get('supplied_usage') is not None for r in rows),
                          'retained_provider_usage': 'unavailable'}})

        native = fixture(output / 'transport', 'unavailable', judge_context=context)
        # Additional policies exercise real required judges and the same HTTP path.
        for scenario, overrides in (('refusal', {}), ('provider_error', {}), ('wrong_envelope', {}),
                ('retry_exhausted_schema', {}), ('legacy_format_retry', {'LLM_JUDGE_RETRY_POLICY': 'legacy'})):
            start = len(responder.requests)
            attempts = []
            token = verifier._ACTIVE_JUDGE_EVIDENCE.set(attempts)
            try:
                with patch.object(verifier, 'SKILL_EVALUATOR_REWARD_JSON', output / 'isolated' / scenario / 'reward.json'), \
                        responder.case(verifier, scenario, **overrides):
                    result = verifier._call_required_judge('accuracy', verifier.judge_accuracy, 'Return 42', '42', '42')
            finally:
                verifier._ACTIVE_JUDGE_EVIDENCE.reset(token)
            count = len(responder.requests) - start
            reports.require(count == (2 if scenario in ('retry_exhausted_schema', 'legacy_format_retry') else 1), 'Request bound differs')
            reports.require((result['score'] is not None) == (scenario == 'legacy_format_retry'), 'Unavailable reply became score')
            controls.append({'scenario': scenario, 'requests': count, 'attempts': len(attempts), 'diagnostics': attempts, 'result': result,
                             'errors': result.get('reason'), 'usage': 'not retained upstream'})
        with patch.object(verifier, 'SKILL_EVALUATOR_REWARD_JSON', output / 'isolated/unknown/reward.json'), \
                responder.case(verifier, 'unknown_behavior'):
            result = verifier._call_required_judge('behavior_check', verifier.judge_behavior_check,
                                                   'Tool output unavailable.', ['Observed authorized execution.'])
        reports.require(result['results'][0]['passed'] is None and result['score'] == 0,
                        'Unknown behavior lost its explicit missingness')
        controls.append({'scenario': 'unknown_behavior', 'requests': 1, 'attempts': 1,
                         'errors': None, 'usage': 'not retained upstream', 'result': result})
        reports.require(not blocked, 'External network attempted')
    for row in responder.requests:
        payload = row['payload']
        reports.require(payload['model'] == transport.MODEL and payload['stream'] is False
                        and 'reasoning_effort' not in payload and payload['max_completion_tokens'] == 32768
                        and 'temperature' not in payload and 'max_tokens' not in payload, 'Effective request differs')
    reports.require(any(c['requests'] > c['attempts'] for c in controls if c['attempts'] is not None), 'Retry undercount not reproduced')
    sanitized = output / 'sanitized'
    reports.benchmark_artifacts(ROOT, native, 'podman', sanitized)
    public = benchmark.report(ROOT, sanitized, 'podman', 'standard', output / 'admitted')
    reports.require(not benchmark.history_admission(public)['eligible'], 'Fixture entered history')
    render_native([public], output / 'reporting')
    reports.write_json(output / 'requests.json', responder.requests)
    reports.write_json(output / 'qualification.json', {
        'origin': 'credential_free_fixture', 'live_judgments': 'UNRUN', 'paid_authority': False,
        'revision': evidence.git_revision(ROOT), 'versions': profiles.candidate_versions(profiles.NEXT),
        'corpus_sha256': hashlib.sha256(CORPUS.read_bytes()).hexdigest(),
        'sources': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES},
        'handoff': {'requests.json': hashlib.sha256((output / 'requests.json').read_bytes()).hexdigest()},
        'settings': {k:v for k,v in transport.SETTINGS.items() if 'API_KEY' not in k},
        'controls': controls, 'http_requests': len(responder.requests),
        'native_budget_usage': _budget_usage(native), 'history': benchmark.history_admission(public),
        'blockers': ['provider_usage_discarded', 'logical_attempts_undercount_http_requests']})
    import unittest
    os.environ['JUDGE_090_EVIDENCE'] = str(output)
    tests = unittest.defaultTestLoader.loadTestsFromName('test_standard_judges')
    reports.require(unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful(), 'Judge qualification controls failed')
    (output / 'reporting/report.html').write_bytes(render(output))
    reports.require(render(output) == (output / 'reporting/report.html').read_bytes(), 'Report reproduction differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('qualify', 'reproduce'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.action == 'reproduce':
        profiles.runtime(profiles.candidate_versions(profiles.NEXT), owning=True)
        reports.require(render(args.output) == (args.output / 'reporting/report.html').read_bytes(), 'Report reproduction differs')
        return
    if args.worker:
        worker(args.output)
        return
    output = args.output.absolute()
    reports.require(output.resolve() == output and not output.is_relative_to(ROOT) and not output.exists(), 'Fresh external destination required')
    output.mkdir(parents=True)
    empty = output / 'empty-home'; empty.mkdir()
    env = {k:os.environ[k] for k in ('PATH', 'TMPDIR', 'LANG') if k in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTHON_DOTENV_DISABLED='1', LITELLM_LOCAL_MODEL_COST_MAP='True',
        HOME=str(empty), USERPROFILE=str(empty), XDG_CACHE_HOME=str(output / 'cache'), XDG_STATE_HOME=str(output / 'state'),
        SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE=str(output / 'fixture-provenance.key'))
    subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), 'qualify', '--output', str(output), '--worker'],
                   env=env, check=True, timeout=180)


if __name__ == '__main__':
    main()
