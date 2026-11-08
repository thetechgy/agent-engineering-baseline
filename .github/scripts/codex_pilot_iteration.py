"""Versioned pilot iteration admission; legacy and production runners stay frozen."""
from codex_pilot_contract import ROOT, runner_bytes as legacy_runner_bytes

PROFILE_ID = 'pester-cli-pilot-external-v4'
PATH_LINK = 'RUN ln -s /opt/microsoft/powershell/7/pwsh /usr/local/bin/pwsh\n'


def runner_bytes(workspace=ROOT):
    source = legacy_runner_bytes(workspace).decode()
    changes = {
        "'IfStatementAst', 'ForEachStatementAst',": "'IfStatementAst', 'ForEachStatementAst', 'ForStatementAst',",
        "@('int', 'int32', 'bool',": "@('int', 'int32', 'long', 'int64', 'bool',",
        "            if ($__peKind -eq 'UnaryExpressionAst' -and $__peNode.TokenKind -notin @('Not', 'Exclaim', 'Minus', 'Plus', 'Comma')) { throw 'admission' }": """            if ($__peKind -eq 'UnaryExpressionAst') {
                $__peResult.code = 'unary_policy'
                if ($__peNode.TokenKind -in @('PlusPlus', 'MinusMinus', 'PostfixPlusPlus', 'PostfixMinusMinus')) {
                    # The full FindAll walk also applies the existing variable
                    # policy to this child. No member/index/parenthesized writes.
                    if ($__peNode.Child -isnot [System.Management.Automation.Language.VariableExpressionAst]) { throw 'admission' }
                    $__peTarget = $__peNode.Child.VariablePath.UserPath -replace '^(script|local|private):', ''
                    if ($__peTarget -in @('PSScriptRoot', 'true', 'false', 'null')) { throw 'admission' }
                }
                elseif ($__peNode.TokenKind -notin @('Not', 'Exclaim', 'Minus', 'Plus', 'Comma')) { throw 'admission' }
            }""",
    }
    for old, new in changes.items():
        assert source.count(old) == 1
        source = source.replace(old, new)
    return source.encode()


# Independent qualification fixtures, unrelated to the retained live answers.
# Existing known-good, weak and malformed controls remain in codex_pilot.py.
CONTROLS = {
    'loop': 'passed', 'loop-failure': 'failed', 'long': 'passed',
    'loop-initializer': 'unsupported', 'loop-condition': 'unsupported',
    'loop-iterator': 'unsupported', 'loop-body': 'unsupported',
    'loop-protected': 'unsupported', 'loop-member': 'unsupported',
    'loop-index': 'unsupported', 'loop-timeout': 'timeout',
    'missing-runtime': 'infrastructure_error', 'path-before': 'passed', 'path-after': 'passed',
}


def control_payload(name, good):
    loop = b"""
Describe 'Counter iteration' {
    It 'supports all four ordinary increment and decrement forms' {
        $total = 0
        for ($counter = 0; $counter -lt 3; $counter++) { $total += $counter }
        for ($counter = 0; $counter -lt 3; ++$counter) { $total += $counter }
        for ($counter = 2; $counter -ge 0; $counter--) { $total += $counter }
        for ($counter = 2; $counter -ge 0; --$counter) { $total += $counter }
        $total | Should-Be 12
    }
}
"""
    cases = {
        'loop': good + loop,
        'long': good + b"\nDescribe 'Signed integers' { It 'supports Int64 inputs' { $value = [long]123; Should-HaveType -Actual $value -Expected ([int64]) } }\n",
        'loop-failure': b"Describe 'Genuine failure' { It 'fails an assertion within a loop' { for ($counter=0; $counter -lt 2; $counter++) { $counter | Should-Be 100 } } }\n",
        'loop-initializer': b"Describe x { It y { for ($counter = Get-Content '/tests/grader.py'; $counter -lt 1; $counter++) { 1 | Should-Be 1 } } }\n",
        'loop-condition': b"Describe x { It y { for ($counter=0; (Get-Content '/tests/grader.py'); $counter++) { 1 | Should-Be 1 } } }\n",
        'loop-iterator': b"Describe x { It y { for ($counter=0; $counter -lt 1; Get-Content '/tests/grader.py') { $counter = 1 } } }\n",
        'loop-body': b"Describe x { It y { for ($counter=0; $counter -lt 1; $counter++) { Get-Content '/tests/grader.py' } } }\n",
        'loop-protected': b"Describe x { It y { for ($counter=0; $counter -lt 1; $PSScriptRoot++) { $counter = 1 } } }\n",
        'loop-member': b"Describe x { It y { $point=@{Port=1}; for ($counter=0; $counter -lt 1; $point.Port++) { $counter=1 } } }\n",
        'loop-index': b"Describe x { It y { $ports=@(1); for ($counter=0; $counter -lt 1; $ports[0]++) { $counter=1 } } }\n",
        'loop-timeout': b"Describe 'Bounded execution' { It 'exhausts the unchanged worker deadline' { for (;;) {} } }\n",
        'missing-runtime': good, 'path-before': good, 'path-after': good,
    }
    return cases[name]
