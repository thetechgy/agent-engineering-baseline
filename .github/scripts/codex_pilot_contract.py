"""Prospective pilot contract; retained tasks, runner and runtime pins are unchanged."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILE = json.loads((ROOT / '.github/evals/codex-pilot.json').read_text())
PURPOSES = ('cli_pilot', 'cli_pilot_control')


def runner_bytes(workspace=ROOT):
    """Explicit versioned correction: Boolean assertion admission and fixed reasons."""
    source = (workspace / '.github/evals/powershell-pester-6/support/Runner.ps1').read_text()
    old = "'Be', 'BeExactly', 'BeOfType', 'HaveCount', 'Contain', 'Not', 'Throw', 'Invoke',"
    assert source.count(old) == 1
    source = source.replace(old, "'Be', 'BeTrue', 'BeFalse', 'BeExactly', 'BeOfType', 'HaveCount', 'Contain', 'Not', 'Throw', 'Invoke',")
    # Only the fixed rejection class survives. No AST extents, values or exception text.
    for anchor, reason in (
        ('            $__peKind = $__peNode.GetType().Name', 'ast_kind'),
        ("            if ($__peKind -eq 'VariableExpressionAst')", 'variable_policy'),
        ("            if ($__peKind -eq 'HashtableAst')", 'hashtable_policy'),
        ("            if ($__peKind -eq 'AssignmentStatementAst'", 'expression_policy'),
        ("            if ($__peKind -eq 'CommandAst')", 'command_policy'),
        ('                foreach ($__peElement in $__peNode.CommandElements)', 'command_parameter'),
        ("                if ($__peCommand -eq 'Import-Module')", 'module_policy'),
        ("                if ($__peCommand -in @('Describe', 'Context', 'It'))", 'test_name_template'),
    ):
        assert source.count(anchor) == 1
        source = source.replace(anchor, "            $__peResult.code = '" + reason + "'\n" + anchor)
    return source.encode()


def grader_bytes(workspace=ROOT):
    """Hash the exact admitted bytes at the verifier handoff; no grading change."""
    source = (workspace / '.github/evals/powershell-pester-6/evals/grader.py').read_text()
    source = source.replace('import ctypes\n', 'import ctypes\nimport hashlib\n')
    anchor = "        candidate.decode('utf-8')"
    assert source.count(anchor) == 1
    source = source.replace(anchor,
        "        Path('/logs/verifier/pilot-verified-submission.json').write_text(json.dumps({\n"
        "            'sha256': hashlib.sha256(candidate).hexdigest(), 'bytes': len(candidate)}))\n" + anchor)
    return source.encode()


def configuration(base_url=None):
    """The endpoint is the only transport difference in credential-free probes."""
    return {
        'model': PROFILE['model'], 'model_provider': 'pilot',
        'model_reasoning_effort': PROFILE['reasoning_effort'],
        'approval_policy': 'never', 'sandbox_mode': 'workspace-write',
        'sandbox_workspace_write': {'network_access': False},
        'web_search': 'disabled', 'check_for_update_on_startup': False,
        'features': {'multi_agent': False, 'code_mode': True, 'code_mode_host': True},
        'model_providers': {'pilot': {
            'name': 'OpenAI pilot', 'base_url': base_url or PROFILE['base_url'],
            'env_key': 'OPENAI_API_KEY', 'wire_api': 'responses',
            'request_max_retries': 0, 'stream_max_retries': 0,
            'stream_idle_timeout_ms': 60000, 'supports_websockets': False,
        }},
    }


def pilot_inputs(workspace=ROOT):
    paths = ['.github/evals/codex-pilot.json', '.github/scripts/codex_pilot_contract.py',
             '.github/scripts/codex_pilot_agent.py', '.github/scripts/codex_pilot.py', '.github/scripts/codex_pilot_stub.py']
    return [{'member': 'pilot/' + p, 'digest': 'sha256:' + hashlib.sha256((workspace / p).read_bytes()).hexdigest()} for p in paths]
