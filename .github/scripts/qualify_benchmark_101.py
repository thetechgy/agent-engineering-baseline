"""Credential-free request and scoring controls for the native 1.0.1 candidate."""

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

import evaluator_scoring_compatibility as scoring
import evaluator_profiles as profiles
import judge_transport_090 as transport
import static_evaluator
from skill_reports import POLICY, require

ROOT = Path(__file__).resolve().parents[2]
RELEASE_CANDIDATE = json.loads((ROOT / '.github/evals/evaluator-1.0.1-benchmark-candidate.json').read_text())
PRODUCER_PROFILE = RELEASE_CANDIDATE['id']


@contextmanager
def fixture_owner():
    """Extend the runtime registry in this credential-free qualification process."""
    import skill_evidence as evidence
    from skillevaluator.tier3 import evals_spec

    native_file_check = evals_spec._run_file_checks

    def check_captured_config(path, spec, checks):
        if isinstance(path, evidence.CapturedInput) and spec.rel_path in ('evals/config.yml', 'evals/config.yaml'):
            static_evaluator.validate_captured_config(path.at(path.path.parent.parent))
        else:
            native_file_check(path, spec, checks)

    with (patch.object(profiles, 'CANDIDATES', (*profiles.CANDIDATES, RELEASE_CANDIDATE)),
          patch.object(evals_spec, '_run_file_checks', check_captured_config)):
        versions = profiles.candidate_versions(RELEASE_CANDIDATE)
        profiles.runtime(versions, owning=True)
        yield versions


def restrict_network(event, args):
    if event in ('socket.connect', 'socket.bind'):
        address = args[1]
        if not isinstance(address, tuple) or address[0] != '127.0.0.1':
            raise PermissionError('Benchmark qualification allows loopback only')
    if event == 'socket.getaddrinfo' and args[0] != '127.0.0.1':
        raise PermissionError('Benchmark qualification forbids external resolution')


def agent_dispatch(root):
    from aeb_gh_fixture.backend import require_runtime
    from harbor.utils.import_path import import_symbol
    from skillevaluator.tier3.harbor.runner import build_harbor_run_command

    require_runtime()
    required = 'aeb_gh_fixture.benchmark_codex:BenchmarkCodex'
    modes = ('aeb-benchmark-docker', 'aeb-gh-fixture')
    for mode in modes:
        command = build_harbor_run_command(dataset_path=root, agent='codex', job_name='credential-free-probe',
                                           model=POLICY['model'], env_mode=mode)
        selected = command[command.index('--agent') + 1]
        require(selected == required, 'Candidate did not select the reviewed Codex adapter')
        require(command[command.index('--model') + 1] == POLICY['model'], 'Candidate Codex model changed')
        options = dict(value.split('=', 1) for index, value in enumerate(command) if command[index - 1] == '--ak')
        require(json.loads(options['version']) == POLICY['codex'] and json.loads(options['reasoning_effort']) == 'high',
                'Candidate Codex options changed')
        cls = import_symbol(selected)
        agent = cls(logs_dir=root, model_name=POLICY['model'], version=POLICY['codex'], reasoning_effort='high')
        require('model_reasoning_effort=high' in agent.build_cli_flags() and '--disable code_mode' in agent.build_cli_flags(),
                'Codex launch flags changed')
    return {'agent_import_path': required, 'modes': modes, 'model': POLICY['model'],
            'codex_version': POLICY['codex'], 'reasoning_effort': 'high', 'executed': False}


def verifier_requests():
    from skillevaluator.tier3.eval_core import llm_judge
    from skillevaluator.tier3.harbor.templates import eval as verifier

    responder = transport.Responder()
    original = transport.reply_for

    def four_of_five(payload):
        reply = original(payload)
        if 'criteria' in reply:
            reply['criteria']['FORMAT_FOLLOWED'] = False
        return reply

    settings = {**transport.SETTINGS, 'LLM_JUDGE_RETRY_POLICY': 'legacy',
                'LLM_JUDGE_FALLBACK_MODELS': 'fixture-unapproved-fallback'}
    results = {}
    with patch.dict(os.environ, settings, clear=True), patch.object(transport, 'reply_for', four_of_five), responder.boundary():
        require(verifier._fallback_models(POLICY['model']) == [POLICY['model']] and
                llm_judge._fallback_models(POLICY['model']) == [POLICY['model']], 'Fallback model drift')
        judges = ((verifier.judge_accuracy, ('Return 42', '42', '42'), 0.8),
                  (verifier.judge_behavior_check, ('Returned 42', ['Return 42']), 1.0))
        for judge, args, expected in judges:
            before = len(responder.requests)
            with responder.case(verifier, 'legacy_format_retry', **settings):
                result = judge(*args)
            require(result.get('score') == expected and len(responder.requests) == before + 2,
                    'Candidate verifier scoring or malformed-response repair drift')
            results[judge.__name__] = {'score': expected, 'http_requests': 2}
        before = len(responder.requests)
        with (responder.case(verifier, 'legacy_format_retry', **settings),
              patch.object(verifier, '_ragas_goal_accuracy_enabled', return_value=True),
              patch.object(verifier, '_judge_goal_accuracy_ragas', side_effect=ValueError('Fixture schema rejection'))):
            goal = verifier.judge_goal_accuracy('Return 42', '42', '42')
        require(goal.get('score') == 1 and len(responder.requests) == before + 2,
                'Candidate goal fallback or malformed-response repair drift')
        results['judge_goal_accuracy'] = {'score': 1.0, 'http_requests': 2, 'goal_fallback': 'custom'}
        require(all(row['url'] == transport.URL and row['sentinel_authenticated']
                    and row['payload']['model'] == POLICY['model'] and 'max_completion_tokens' in row['payload']
                    and 'temperature' not in row['payload'] and 'reasoning_effort' not in row['payload']
                    for row in responder.requests), 'Candidate standard-verifier request drift')
    results['custom_sdk'] = custom_sdk_requests(settings)
    return results


def custom_sdk_requests(settings):
    import httpx
    import openai
    from skillevaluator.tier3.eval_core import llm_judge

    requests = []
    client_type = openai.OpenAI

    def reply(request):
        require(str(request.url) == transport.URL and request.method == 'POST'
                and request.headers['Authorization'] == 'Bearer ' + transport.SENTINEL,
                'Unexpected custom verifier endpoint or credential source')
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) == 1:
            return httpx.Response(400, json={'error': {'message': 'response_format json_schema is not supported',
                                                      'param': 'response_format'}})
        return httpx.Response(200, json={'choices': [{'message': {'content': '{"fixture": true}'},
                                                     'finish_reason': 'stop'}]})

    with httpx.Client(transport=httpx.MockTransport(reply), trust_env=False) as client:
        with (patch.dict(os.environ, settings, clear=True),
              patch.object(openai, 'OpenAI', side_effect=lambda **kwargs: client_type(http_client=client, **kwargs))):
            value, error = llm_judge.call_public_llm('Synthetic evaluation', model=POLICY['model'],
                response_schema={'type': 'object', 'properties': {'fixture': {'type': 'boolean'}},
                                 'required': ['fixture'], 'additionalProperties': False})
    require(error is None and json.loads(value) == {'fixture': True} and len(requests) == 2
            and 'response_format' in requests[0] and 'response_format' not in requests[1],
            'Candidate custom verifier schema fallback drift')
    require(all(body['model'] == POLICY['model'] and 'max_completion_tokens' in body
                and 'reasoning_effort' not in body and 'temperature' not in body for body in requests),
            'Candidate custom verifier request drift')
    return {'http_requests': len(requests), 'schema_fallback': True}


def score_comparison():
    from skillevaluator.tier3.harbor import metrics

    retained = scoring.retained_probe()
    vectors = scoring.vectors()
    candidate = [round(metrics.overall_score(row), 4) for row in vectors]
    differences = [index for index, (old, new) in enumerate(zip(retained['scores'], candidate)) if old != new]
    require(len(differences) == 56, 'Unexpected standard score difference')
    return {'retained': retained, 'candidate': {'producer': PRODUCER_PROFILE,
            'policy': metrics.DEFAULT_SCORE_POLICY, 'definition': metrics.score_definition(), 'scores': candidate},
            'vectors': len(vectors), 'changed_vectors': differences}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--native', choices=('gh', 'pester'), help='Run the existing deterministic Docker fixture suite')
    mode.add_argument('--prepare-pester', action='store_true', help='Prepare pinned Pester image packages without running a trial')
    args = parser.parse_args()
    output = args.output.absolute()
    require(output.resolve() == output and not output.is_relative_to(ROOT) and not output.exists(),
            'Use a new receipt file outside the checkout')
    require(not any(os.environ.get(key) for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'NVIDIA_API_KEY',
        'CODEX_AUTH_JSON_PATH', 'CODEX_FORCE_AUTH_JSON', 'SKILL_EVAL_LLM_API_KEY')), 'Provider credentials forbidden')
    with fixture_owner() as versions:
        if args.prepare_pester:
            from prepare_candidate_images import main as prepare
            prepare(output, runtime='current')
            return
        if args.native == 'gh':
            from gh_oracle_validation import main as qualify
            qualify(output)
            return
        if args.native == 'pester':
            from pester_container_validation import main as qualify
            qualify(candidate='release', artifact=output)
            return
    sys.addaudithook(restrict_network)
    result = {'schema': 1, 'versions': versions, 'source_tree_digest': RELEASE_CANDIDATE['source_tree_digest'],
              'release_lock_sha256': static_evaluator.LOCK, 'producer_profile': PRODUCER_PROFILE,
              'inference': False, 'history_eligible': False, 'agent_dispatch': agent_dispatch(output.parent),
              'verifier': verifier_requests(), 'scoring': score_comparison()}
    with output.open('x') as stream:
        json.dump(result, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


if __name__ == '__main__':
    main()
