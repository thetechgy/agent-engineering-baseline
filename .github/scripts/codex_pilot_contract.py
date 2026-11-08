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
        'approval_policy': 'never', 'sandbox_mode': 'danger-full-access',
        'web_search': 'disabled', 'check_for_update_on_startup': False,
        'features': {'multi_agent': False, 'code_mode': True, 'code_mode_host': True},
        'model_providers': {'pilot': {
            'name': 'OpenAI pilot', 'base_url': base_url or PROFILE['base_url'],
            'env_key': 'OPENAI_API_KEY', 'wire_api': 'responses',
            'request_max_retries': 0, 'stream_max_retries': 0,
            'stream_idle_timeout_ms': 60000, 'supports_websockets': False,
        }},
    }


def runtime_installer_bytes(workspace=ROOT):
    """Pilot-only bounded transport; reuse frozen inputs and archive/version checks."""
    source = (workspace / '.github/evals/powershell-pester-6/support/install-runtime.py').read_text()
    original = """            with urlopen(url, timeout=60) as response, archive.open('xb') as output:
                if not response.url.startswith('https://'):
                    raise ValueError('Non-HTTPS fixture input')
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() != expected:
                raise ValueError('Fixture input digest mismatch')"""
    changes = {
        'from urllib.request import urlopen\n': '',
        'def main():': "def main(*, inputs=INPUTS, runtime=Path('/opt/microsoft/powershell/7'), module=Path('/opt/pester/Modules/Pester/6.2.0')):",
        '    with tempfile.TemporaryDirectory() as temporary:': '    deadline = time.monotonic() + ACQUISITION_SECONDS\n    with tempfile.TemporaryDirectory() as temporary:',
        'for url, expected, name in INPUTS:': 'for url, expected, name in inputs:',
        original: '            acquire(url, expected, name, archive, deadline)',
        "        runtime = Path('/opt/microsoft/powershell/7')\n": '',
        "        module = Path('/opt/pester/Modules/Pester/6.2.0')\n": '',
        "    main()\n": "    try:\n        main()\n    except AcquisitionError as error:\n        raise SystemExit(str(error)) from None\n",
    }
    for old, new in changes.items():
        assert source.count(old) == 1
        source = source.replace(old, new)
    transport = (workspace / '.github/scripts/codex_pilot_acquisition.py').read_text()
    return (transport + source).encode()


def pilot_inputs(workspace=ROOT):
    paths = ['.github/evals/codex-pilot.json', '.github/scripts/codex_pilot_contract.py',
             '.github/scripts/codex_pilot_agent.py', '.github/scripts/codex_pilot.py', '.github/scripts/codex_pilot_stub.py',
             '.github/scripts/codex_pilot_environment.py', '.github/scripts/codex_pilot_boundary.py',
             '.github/scripts/codex_pilot_probe.py', '.github/scripts/codex_pilot_descriptors.py',
             '.github/scripts/codex_pilot_acquisition.py', '.github/scripts/codex_pilot_iteration.py',
             '.github/scripts/codex_pilot_replay.py', '.github/evals/codex-pilot-iteration.md',
             '.github/evals/codex-retrospective/42448389611/manifest.json']
    corpus = '.github/evals/codex-retrospective/42448389611/'
    manifest = json.loads((workspace / corpus / 'manifest.json').read_text())
    paths.extend(corpus + row['member'] for row in manifest['files'])
    return [{'member': 'pilot/' + p, 'digest': 'sha256:' + hashlib.sha256((workspace / p).read_bytes()).hexdigest()} for p in paths]
