"""Adapter-owned runtime/model validation and matched native APM deployment."""
import hashlib
from pathlib import Path

from evaluation_campaign_core import require

ROOT = Path(__file__).resolve().parents[2]


def read_profile(path, validators=None):
    import skill_reports as reports
    value = reports.read_json(path)
    adapters = {'codex': validate_codex} if validators is None else validators
    adapter = value.get('adapter')
    require(adapter in adapters, 'Unsupported runtime adapter: ' + str(adapter) + '; claude-code and copilot are extension targets only')
    # The owning adapter validates its complete model/provider/configuration tuple.
    resolved = adapters[adapter](value)
    return {'profile': value, 'resolved': resolved}


def validate_codex(value):
    import skill_reports as reports
    from codex_pilot_contract import PROFILE
    require(set(value) == {'id', 'adapter', 'frozen_profile', 'frozen_profile_sha256', 'capabilities', 'inference_enabled'},
            'Unsupported Codex profile settings')
    require(value['frozen_profile'] == '.github/evals/codex-pilot.json' and
            value['frozen_profile_sha256'] == hashlib.sha256((ROOT / value['frozen_profile']).read_bytes()).hexdigest(),
            'Qualified Codex profile drift')
    capabilities = (['non-forwarding-cli-probe', 'exact-authorized-live'] if value['id'] == 'codex-authorized-campaign-v1'
                    else ['oracle', 'non-forwarding-cli-probe'])
    require(value['inference_enabled'] is False and value['capabilities'] == capabilities,
            'Unsupported Codex capabilities or inference setting')
    return dict(PROFILE, agent='codex')



def adapter_for(runtime):
    from importlib import import_module
    modules = {'codex': 'evaluation_codex'}
    name = runtime['profile']['adapter']
    require(name in modules, 'Unsupported runtime adapter: ' + name)
    return import_module(modules[name])


def source_inputs(runtime, workspace):
    # Source/profile inspection works without loading native SDK transport code.
    name = runtime['profile']['adapter']
    require(name == 'codex', 'Unsupported runtime metadata adapter: ' + name)
    from codex_pilot_contract import pilot_inputs
    import skill_evidence as e
    return pilot_inputs(workspace) + [{'member': 'runtime/evaluation_codex.py',
        'digest': e.digest_bytes(e.read_bytes(workspace / '.github/scripts/evaluation_codex.py'))}]


_CODEX_FAILURES = {
    'CodexRuntimeError': ('execution_infrastructure_failure', 'infrastructure_error'),
    'MissingCodexObservation': ('missing_native_observation', 'unknown'),
    'UnsupportedCodexProtocol': ('unsupported_runtime_protocol', 'unsupported'),
    'DownloadVerifierDirError': ('execution_infrastructure_failure', 'infrastructure_error'),
    'RewardFileNotFoundError': ('missing_grading_evidence', 'unknown'),
}


def failure_reason(exception_type):
    return _CODEX_FAILURES.get(exception_type, ('execution_infrastructure_failure', None))[0]


def native_outcome(runtime, trial, outcome):
    """Adapter-owned interpretation of retained native lifecycle failures.

    A failed environment/agent setup cannot be a measured task failure. Unknown
    execution failures stay unknown; no message matching invents a diagnosis.
    """
    require(runtime['profile']['adapter'] == 'codex', 'Unsupported native observation adapter')
    exception = (trial.get('exception_info') or {}).get('exception_type')
    if exception in _CODEX_FAILURES:
        return _CODEX_FAILURES[exception][1]
    if outcome in ('timeout', 'interrupted'):
        return outcome
    if (exception and trial.get('agent_execution') is None and trial.get('verifier') is None
            and any(isinstance(trial.get(phase), dict) for phase in ('environment_setup', 'agent_setup'))):
        return 'infrastructure_error'
    return outcome
