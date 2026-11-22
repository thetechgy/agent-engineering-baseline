"""Non-forwarding qualification of the registered judge-only execution callbacks.

Only test IO is substituted. Selection, the real evaluator, shared scheduling,
accounting, artifact admission, authentication CLI and report consumption run.
"""
import argparse
from contextlib import nullcontext
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from unittest.mock import patch

from evaluation_campaign_core import require
import evaluation_campaign_protocol as shared
from evaluation_runtime import ROOT
import judge_calibration_campaign as campaign
import judge_transport_090 as transport
import skill_reports as reports

WIRE = {'schema-fallback': 'schema_fallback', 'retry': 'transient_retry', 'retry-exhaustion': 'retry_exhausted_schema',
        'redirect-stop': 'redirect', 'unknown-retry': 'transient_retry',
        'refusal': 'refusal', 'malformed': 'wrong_shape', 'missing-usage': 'missing_usage',
        'malformed-usage': 'malformed_usage', 'contradictory-usage': 'inconsistent_usage', 'timeout': 'timeout', 'interruption': 'interrupt',
        'request-stop': 'transient_retry'}
EXPECTED = {'unknown-retry': 'unknown_judge_accounting', 'refusal': 'judge_unavailable',
            'retry-exhaustion': 'judge_unavailable', 'redirect-stop': 'unsupported_judge_redirect',
            'malformed-usage': 'unknown_judge_accounting',
            'malformed': 'judge_unavailable', 'missing-usage': 'unknown_judge_accounting',
            'contradictory-usage': 'unknown_judge_accounting', 'timeout': 'judge_unavailable',
            'interruption': 'interrupted', 'request-stop': 'judge_request_limit',
            'usage-stop': 'judge_usage_limit', 'cost-stop': 'estimated_usage_threshold',
            'cache-cost-stop': 'unknown_judge_cost', 'deadline-stop': 'judge_deadline',
            'retention-failure': 'evidence_retention_failure'}


class Observer(transport.Responder):
    """Existing non-forwarding responder with explicitly complete error usage."""
    complete_errors = False

    def respond(self, payload):
        status, raw = super().respond(payload)
        body = json.loads(raw)
        if status == 200 and 'usage' in body:
            body['usage']['prompt_tokens_details']['cache_write_tokens'] = 15 if self.scenario == 'cache-cost-stop' else 4
            self.requests[-1].update(response=body, supplied_usage=body['usage'])
            raw = json.dumps(body).encode()
        if getattr(self, 'echo_sentinel', False) and status == 200:
            response = json.loads(body['choices'][0]['message']['content'])
            response['summary'] = transport.SENTINEL
            for result in response['results']:
                result['reason'] = transport.SENTINEL
                result[transport.SENTINEL] = transport.SENTINEL
            body['choices'][0]['message']['content'] = json.dumps(response)
            self.requests[-1]['response'] = body
            raw = json.dumps(body).encode()
        if self.scenario == 'redirect':
            status = 302
            self.requests[-1]['status'] = status
        if self.complete_errors and status != 200:
            body = json.loads(raw)
            body['usage'] = {'prompt_tokens': 19, 'completion_tokens': 7, 'total_tokens': 26}
            self.requests[-1].update(response=body, supplied_usage=body['usage'])
            raw = json.dumps(body).encode()
        return status, raw


class Fixture:
    def __init__(self, name, observer):
        self.name, self.observer = name, observer
        self.clock_offset = 0
        self.settings = {'SKILL_EVAL_LLM_JUDGE_BUDGET_SEC': '30' if name == 'deadline-stop' else '1',
                         'SKILL_EVAL_LLM_RETRY_BASE_DELAY': '0.001',
                         'SKILL_EVAL_LLM_RETRY_MAX_DELAY': '0.01'}
        self.limits = ({'http': 1} if name == 'request-stop' else {'tokens': 26} if name == 'usage-stop'
                       else {'cost': 0.00001} if name == 'cost-stop'
                       else {'seconds': 30} if name == 'deadline-stop' else {})

    def before_record(self, verifier, row):
        self.observer.scenario = WIRE.get(self.name, 'cache-cost-stop' if self.name == 'cache-cost-stop' else 'valid')
        if self.name in ('complete', 'schema-fallback', 'retry') and row['position'] == 3:
            self.observer.scenario = 'unknown_behavior'
        self.observer.complete_errors = self.name in ('schema-fallback', 'retry', 'retry-exhaustion', 'request-stop', 'redirect-stop')
        self.observer.metric_counts = {}
        self.observer.echo_sentinel = self.name == 'complete' and row['position'] == 2
        if self.name == 'retention-failure':
            # Real failed sidecar replacement: persist must observe the OSError
            # and the transport guard must refuse the first HTTP request.
            verifier._accounting._ACTIVE.get()[0].with_name('judge_accounting.json.tmp').mkdir()
            verifier._accounting.persist()

    def monotonic(self):
        return time.monotonic() + self.clock_offset

    def after_record(self, row):
        if self.name == 'deadline-stop':
            require(row['state'] == 'completed' and row['accounting_summary']['complete'],
                    'Deadline control requires a completed first judgment')
            self.clock_offset = self.limits['seconds']


def worker(output, task):
    output.mkdir(parents=True, exist_ok=False)
    observer = Observer()
    baseline = {t.ident for t in threading.enumerate()}
    original_redirect = urllib.request.HTTPRedirectHandler.redirect_request
    runs = []; summaries = {}
    with observer.boundary() as port:
        blocked = []
        def offline(event, args):
            if event == 'socket.connect' and (not isinstance(args[1], tuple) or args[1][:2] != ('127.0.0.1', port)):
                blocked.append(event); raise RuntimeError('Qualification forbids external network')
            if event == 'socket.getaddrinfo' and (args[0], args[1]) != ('127.0.0.1', port):
                blocked.append(event); raise RuntimeError('Qualification forbids external DNS')
        sys.addaudithook(offline)
        for scenario in campaign.SCENARIOS:
            # Each campaign has a fresh verifier process in the workflow. Keep
            # its native cache for the entire pass; only fixtures share imports.
            from skillevaluator.tier3.harbor.templates import eval as verifier
            verifier._SCHEMA_UNSUPPORTED_TARGETS.clear()
            first = len(observer.requests)
            root = output / 'scenarios' / scenario / 'evidence'
            try:
                fixture = Fixture(scenario, observer)
                # Advance only the scheduler clock, after the physical HTTP response and its receipt.
                clock = patch.object(campaign, 'time', fixture) if scenario == 'deadline-stop' else nullcontext()
                with clock:
                    value = campaign.execute(root.parent, task, fixture=fixture)
            except BaseException:
                try: reports.write_json(root / 'request-observer.json', observer.requests[first:])
                except Exception: sys.stderr.write('Observer retention failed; primary failure preserved.\n')
                raise
            reports.write_json(root / 'request-observer.json', observer.requests[first:])
            require((root / 'consolidated/report.html').is_file()
                    and not (root.parent / 'attempt-ledger.json').exists(), 'Live artifact layout differs')
            require(urllib.request.HTTPRedirectHandler.redirect_request is original_redirect,
                    'Redirect policy leaked after execution')
            requests = observer.requests[first:]
            actual = value['accounting_summary']
            require(actual['http_attempts'] == len(requests), 'Independent request observer differs: ' + scenario)
            launched = sum(r['state'] != 'unlaunched' for r in value['entries'])
            if scenario in ('complete', 'schema-fallback', 'retry'):
                require(value['state'] == 'completed' and launched == 7 and actual['complete'], 'Seven-record execution failed: ' + scenario)
                require(actual['logical_judgments'] == 21 and actual['model_attempts'] == 6
                        and sum(j['not_applicable'] for r in value['entries'] for j in r['accounting']['judgments']) == 15,
                        'Applicable/inapplicable population differs')
                expected = 11 if scenario == 'retry' else 7 if scenario == 'schema-fallback' else 6
                require(len(requests) == expected, 'Retry/schema request count differs')
                if scenario == 'schema-fallback':
                    require('response_format' in requests[0]['payload']
                            and all('response_format' not in request['payload'] for request in requests[1:]),
                            'Pinned schema-support memoization was reset between records')
                require(value['entries'][2]['results']['behavior_check']['results'][0]['passed'] is None,
                        'Unavailable behavior became a negative verdict')
                if scenario == 'complete':
                    require(transport.SENTINEL not in json.dumps(value['entries'][1]['results']),
                            'Configured credential escaped result retention')
            else:
                require(launched == 1 and value.get('stop_reason') == EXPECTED[scenario],
                        'Extra record or wrong primary stop: ' + scenario + ': ' + str(value.get('stop_reason')))
                require(len(requests) == (0 if scenario == 'retention-failure' else 2 if scenario == 'retry-exhaustion' else 1),
                        'Unauthorized next HTTP request: ' + scenario)
            require(value['resource_disposal'], 'Required-judge resources not disposed')
            # Acceptance labels and provenance must not enter the provider prompt.
            for request in requests:
                require(request['payload']['model'] == shared.protocol(task)['request']['model'],
                        'Independent observer received a different judge model')
                prompt = request['payload']['messages'][0]['content']
                require(not any(label in prompt for label in ('label_basis', 'UNSCORED / review required',
                    'FAIL authorization; correctness remains PASS', '"observed":', 'paid_authority', 'source_identities')),
                    'Calibration acceptance metadata entered prompt')
            summaries[scenario] = {'records_launched': launched, 'http_attempts': len(requests),
                                   'stop_reason': value.get('stop_reason'), 'accounting_complete': actual['complete']}
            runs.append(root)
        require(not blocked, 'External connection attempted')
    for _ in range(30):
        if {t.ident for t in threading.enumerate()} <= baseline:
            break
        time.sleep(0.05)
    require({t.ident for t in threading.enumerate()} <= baseline, 'Loopback server/handler thread leaked')
    html = campaign.render(runs, output / 'report', task)
    require(html == campaign.render(runs, output / 'reproduced', task), 'Judge consolidated report differs')
    reports.write_json(output / 'qualification.json', {'complete': True, 'inference': False,
        'revision': shared.revision(), 'type': 'judge-only', 'campaign': task.definition['id'], 'fixture_only': True,
        'live_authority': False, 'records': 7, 'scenarios': summaries, 'request_observer': True,
        'resource_disposal': True, 'production_deadline_exercised': False,
        'fixture_settings': Fixture('complete', observer).settings})


def qualify(output, task):
    from evaluation_campaign import no_credentials
    no_credentials()
    # Existing qualification convention: a fresh child with no forwarded secrets,
    # empty home, explicit sentinel and no non-loopback network facilities.
    with tempfile.TemporaryDirectory(prefix='judge-qualification-home-') as directory:
        env = {k: os.environ[k] for k in ('PATH', 'TMPDIR', 'LANG', 'SYSTEMROOT') if k in os.environ}
        env.update(HOME=directory, PYTHONDONTWRITEBYTECODE='1', PYTHON_DOTENV_DISABLED='1', HARBOR_TELEMETRY='0')
        subprocess.run([sys.executable, '-B', str(ROOT / '.github/scripts/judge_calibration_qualification.py'),
                        '--worker', '--campaign', task.definition['id'], '--output', str(output)], env=env, check=True, timeout=180)


def prepare(output, task, qualification, authentication_qualification):
    from campaign_authentication_qualification import qualify as qualify_auth, validate, run_case
    require(qualification is not None, 'Actual judge qualification required')
    ready = reports.read_json(qualification / 'qualification.json')
    require(ready['complete'] is True and ready['inference'] is False and ready['fixture_only'] is True
            and ready['campaign'] == task.definition['id'] and ready['revision'] == shared.revision() and set(ready['scenarios']) == set(campaign.SCENARIOS),
            'Exact-source judge qualification required')
    output.mkdir(parents=True, exist_ok=False)
    retained = output / 'evidence'; retained.mkdir()
    proof = (qualify_auth(output / 'authentication-tests', task) if authentication_qualification is None
             else reports.read_json(authentication_qualification))
    validate(proof, task)
    reports.write_json(retained / 'authentication-qualification.json', proof)
    reports.write_json(retained / 'frozen-proposal.json', shared.frozen(task))
    shutil.copytree(qualification / 'scenarios', output / 'scenarios')
    roots = [output / 'scenarios' / name / 'evidence' for name in campaign.SCENARIOS]
    campaign.render(roots, retained / 'consolidated', task)
    campaign.render(roots, retained / 'reproduced', task)
    reports.write_json(retained / 'scheduler-qualification.json', {**ready,
        'protocol_digest': shared.digest(ROOT / task.definition['protocol'])})
    ready_receipt = {'complete': True, 'inference': False, 'revision': shared.revision(),
                     'protocol_digest': shared.digest(ROOT / task.definition['protocol']), 'authorized_live_attempts': 0}
    reports.write_json(retained / 'preparation.json', ready_receipt)
    try:
        # Positive integration uses the actual retained preparation, never the
        # authentication unit fixture's hand-constructed preparation documents.
        with tempfile.TemporaryDirectory(prefix='judge-actual-preparation-auth-') as directory:
            run_case(Path(directory) / 'actual-preparation', task, 'accepted', preparation=retained)
        reports.write_json(retained / 'authentication-consumption.json', {'complete': True, 'inference': False,
            'fixture_only': True, 'revision': shared.revision(),
            'entry_point': '.github/scripts/evaluation_campaign_selection.py authenticate',
            'actual_preparation': True, 'live_authority': False})
        campaign.check(retained, output / 'consumption', task)
    except BaseException:
        reports.write_json(retained / 'preparation.json', {**ready_receipt, 'complete': False})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', action='store_true', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--campaign', default='judge-calibration-090-v1-sol62')
    args = parser.parse_args()
    from evaluation_campaign_selection import selected_task
    worker(args.output, selected_task(args.campaign))


if __name__ == '__main__': main()
