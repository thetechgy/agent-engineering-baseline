"""Task-owned successor to the frozen collection/numeric admission policy."""
from pester_admission import execution_profile_bytes, runner_bytes


TEMPLATE_POLICY = 'pester-static-row-template-v2'

# Row values still undergo the complete recursive admission walk.
STATIC_ROW_FIELDS = r'''
function __peStaticRowFields($command, $name) {
    $parameters = @($command.CommandElements | Where-Object {
        $_ -is [System.Management.Automation.Language.CommandParameterAst] -and
        ($_.ParameterName -eq 'ForEach' -or ($name -eq 'It' -and $_.ParameterName -eq 'TestCases'))
    })
    if ($parameters.Count -ne 1) { return }
    $data = __peArgument $command $parameters[0].ParameterName
    $rows = @($data)
    if ($data -is [System.Management.Automation.Language.ArrayExpressionAst]) {
        $rows = @(foreach ($statement in $data.SubExpression.Statements) {
            if ($statement -isnot [System.Management.Automation.Language.PipelineAst] -or
                $statement.PipelineElements.Count -ne 1 -or
                $statement.PipelineElements[0] -isnot [System.Management.Automation.Language.CommandExpressionAst] -or
                $statement.PipelineElements[0].Redirections.Count) { return }
            $statement.PipelineElements[0].Expression
        })
    }
    $tables = @(foreach ($row in $rows) {
        if ($row -is [System.Management.Automation.Language.ArrayLiteralAst]) { $row.Elements }
        else { $row }
    })
    if (-not $tables.Count -or $tables[0] -isnot [System.Management.Automation.Language.HashtableAst]) { return }
    $keys = @($tables[0].KeyValuePairs | Where-Object {
        $_.Item1 -is [System.Management.Automation.Language.StringConstantExpressionAst]
    } | ForEach-Object { $_.Item1.Value })
    foreach ($table in $tables) {
        if ($table -isnot [System.Management.Automation.Language.HashtableAst]) { return }
        $rowKeys = @($table.KeyValuePairs | Where-Object {
            $_.Item1 -is [System.Management.Automation.Language.StringConstantExpressionAst]
        } | ForEach-Object { $_.Item1.Value })
        $keys = @($keys | Where-Object { $rowKeys -contains $_ })
    }
    $keys
}
'''


def template_runner_bytes():
    source = runner_bytes().decode()
    anchor = "$__peResult = @{ status = 'infrastructure_error'; code = 'runner'; }"
    assert source.count(anchor) == 1
    source = source.replace(anchor, STATIC_ROW_FIELDS + anchor)
    old = """                    foreach ($__peElement in @($__peNameNode)) {
                        if ($__peElement.GetType().Name -in @('StringConstantExpressionAst', 'ExpandableStringExpressionAst')) {
                            $__peText = $__peElement.Value
                            foreach ($__peField in @($__pePolicy.properties) + @('_')) {
                                $__peText = [regex]::Replace($__peText, '<' + [regex]::Escape($__peField) + '>', '', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
                            }
                            if ($__peText.Contains('<') -or $__peText.Contains('>')) { throw 'admission' }
                        }
                    }"""
    new = """                    $__peText = $__peNameNode.Value
                    if ($__peText.Contains('<') -or $__peText.Contains('>')) {
                        $__peFieldPattern = '<([A-Za-z_][A-Za-z0-9_]*)>'
                        if ([regex]::Replace($__peText, $__peFieldPattern, '') -match '[<>]') { throw 'admission' }
                        $__peFields = @($__pePolicy.properties) + @('_')
                        $__peExtra = @([regex]::Matches($__peText, $__peFieldPattern) | ForEach-Object {
                            $_.Groups[1].Value
                        } | Where-Object { $__peFields -notcontains $_ })
                        if ($__peExtra.Count) {
                            $__peRowFields = @(__peStaticRowFields $__peNode $__peCommand)
                            foreach ($__peField in $__peExtra) {
                                if ($__peField -notmatch '^[A-Za-z][A-Za-z0-9_]*$' -or
                                    $__peReserved -contains $__peField -or $__peField -eq 'PSScriptRoot' -or
                                    $__peRowFields -notcontains $__peField) { throw 'admission' }
                            }
                        }
                    }"""
    assert source.count(old) == 1
    return source.replace(old, new).encode()


def template_execution_profile_bytes():
    return execution_profile_bytes() + (
        b"\nSuccessor test-name admission: pester-static-row-template-v2 (output-informed). "
        b"Bare keys shared by all inline literal hashtable rows of the same -ForEach "
        b"block (or It -TestCases) can also appear as <Key> in its literal title. "
        b"Computed rows, scope lookup, member expressions and protected names gain no admission.\n"
    )
