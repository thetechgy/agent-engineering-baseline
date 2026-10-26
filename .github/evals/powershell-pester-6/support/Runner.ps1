param(
    [Parameter(Mandatory)] [string] $Candidate,
    [Parameter(Mandatory)] [string] $Profile,
    [string] $Workspace = '/workspace',
    [string] $PesterManifest = '/opt/pester/Modules/Pester/6.2.0/Pester.psd1',
    [switch] $AdmissionOnly,
    [switch] $RequireIsolation
)

# PESTER_VERIFIER_ONLY_RUNNER_3CB8
# This fixed runner is verifier-owned. Candidate statements are never evaluated
# by admission. A separate unprivileged process executes the admitted file.
$__peResult = @{ status = 'infrastructure_error'; code = 'runner'; }
try {
    if ($RequireIsolation) {
        $__peStatus = [System.IO.File]::ReadAllText('/proc/self/status')
        if ($__peStatus -notmatch '(?m)^Uid:\s+53001\s+53001\s+53001\s+53001\s*$' -or
            $__peStatus -notmatch '(?m)^NoNewPrivs:\s+1\s*$' -or
            $__peStatus -notmatch '(?m)^CapEff:\s+0+\s*$' -or
            $__peStatus -notmatch '(?m)^CapPrm:\s+0+\s*$' -or
            $__peStatus -notmatch '(?m)^CapAmb:\s+0+\s*$' -or
            $__peStatus -notmatch '(?m)^Seccomp:\s+2\s*$') { throw 'isolation' }
        foreach ($__pePrivate in @('/tests/grader.py', '/tests/case/profile.json', '/logs/verifier/skill_evaluator_reward.json', '/proc/1/environ')) {
            $__peDenied = $false
            try { $null = [System.IO.File]::ReadAllText($__pePrivate) }
            catch [System.UnauthorizedAccessException] { $__peDenied = $true }
            if (-not $__peDenied) { throw 'isolation' }
        }
        foreach ($__peImmutable in @($Candidate, $Profile, '/opt/pester-runtime/Runner.ps1', "$Workspace/input/Subject.ps1")) {
            if ([System.IO.File]::Exists($__peImmutable)) {
                $__peDenied = $false
                try {
                    $__peHandle = [System.IO.File]::Open($__peImmutable, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Write)
                    $__peHandle.Dispose()
                }
                catch [System.UnauthorizedAccessException] { $__peDenied = $true }
                if (-not $__peDenied) { throw 'isolation' }
            }
        }
    }
    $__pePolicy = Get-Content -LiteralPath $Profile -Raw | ConvertFrom-Json
    $__peTokens = $null
    $__peErrors = $null
    $__peAst = [System.Management.Automation.Language.Parser]::ParseFile($Candidate, [ref] $__peTokens, [ref] $__peErrors)
    if ($__peErrors.Count) {
        $__peResult = @{ status = 'invalid'; code = 'parse' }
    }
    else {
        $__peResult = @{ status = 'unsupported'; code = 'admission' }
        $__peNodes = @($__peAst.FindAll({ param($n) $true }, $true))
        if ($__peNodes.Count -gt 5000 -or $null -ne $__peAst.ScriptRequirements) { throw 'admission' }
        $__peKinds = @(
            'ScriptBlockAst', 'NamedBlockAst', 'StatementBlockAst', 'PipelineAst',
            'CommandAst', 'CommandExpressionAst', 'CommandParameterAst',
            'StringConstantExpressionAst', 'ConstantExpressionAst', 'ExpandableStringExpressionAst',
            'VariableExpressionAst', 'ArrayExpressionAst', 'ArrayLiteralAst', 'HashtableAst',
            'ParenExpressionAst', 'SubExpressionAst', 'ScriptBlockExpressionAst',
            'AssignmentStatementAst', 'MemberExpressionAst', 'IndexExpressionAst',
            'ConvertExpressionAst', 'TypeConstraintAst', 'TypeExpressionAst',
            'UnaryExpressionAst', 'BinaryExpressionAst', 'IfStatementAst', 'ForEachStatementAst',
            'TryStatementAst', 'CatchClauseAst', 'ThrowStatementAst', 'ReturnStatementAst',
            'ParamBlockAst', 'ParameterAst'
        )
        $__peReserved = @(
            'ExecutionContext', 'Host', 'PWD', 'PSHOME', 'PSModulePath', 'PSDefaultParameterValues',
            'PesterPreference', 'ErrorActionPreference', 'Error', 'args', 'input', 'PSBoundParameters',
            'MyInvocation', 'PSCmdlet', 'PSCommandPath', 'PROFILE', 'PID', 'LASTEXITCODE',
            'TestDrive', 'TestRegistry', 'PSDebugContext', 'MaximumHistoryCount'
        )
        $__peBlocks = @('Describe', 'Context', 'It', 'BeforeDiscovery', 'BeforeAll', 'BeforeEach', 'AfterAll', 'AfterEach')
        $__peAssertions = @(
            'Should', 'Should-Be', 'Should-NotBe', 'Should-BeString', 'Should-BeCollection',
            'Should-HaveType', 'Should-BeTrue', 'Should-BeFalse', 'Should-BeNull', 'Should-NotBeNull',
            'Should-Throw', 'Should-Invoke', 'Should-NotInvoke'
        )
        $__peAssertParameters = @(
            'Be', 'BeExactly', 'BeOfType', 'HaveCount', 'Contain', 'Not', 'Throw', 'Invoke',
            'ActualValue', 'ExpectedValue', 'ExceptionType', 'ErrorId', 'ExpectedMessage',
            'Because', 'Times', 'Exactly', 'Scope', 'ParameterFilter', 'ModuleName', 'CommandName',
            'Expected', 'Actual', 'Count', 'Type', 'CaseSensitive'
        )
        foreach ($__peNode in $__peNodes) {
            $__peKind = $__peNode.GetType().Name
            if ($__peKinds -notcontains $__peKind) { throw 'admission' }
            if ($__peKind -eq 'PipelineAst' -and $__peNode.Background) { throw 'admission' }
            if ($__peKind -eq 'VariableExpressionAst') {
                $__peName = $__peNode.VariablePath.UserPath
                if ($__peNode.Splatted -or $__peName -match '^(global|env|function|variable|alias):' -or $__peName -match '^__') { throw 'admission' }
                $__peName = $__peName -replace '^(script|local|private):', ''
                if ($__peName -notmatch '^[A-Za-z_][A-Za-z0-9_]*$' -or $__peReserved -contains $__peName -or $__peName -match '^__') { throw 'admission' }
                if ($__peName -eq 'PSScriptRoot' -and $__peNode.Parent.GetType().Name -in @('AssignmentStatementAst', 'ParameterAst', 'ForEachStatementAst')) { throw 'admission' }
            }
            if ($__peKind -eq 'HashtableAst') {
                foreach ($__pePair in $__peNode.KeyValuePairs) {
                    if ($__pePair.Item1 -isnot [System.Management.Automation.Language.StringConstantExpressionAst]) { throw 'admission' }
                    $__peName = $__pePair.Item1.Value
                    if ($__peName -notmatch '^[A-Za-z][A-Za-z0-9_]*$' -or $__peReserved -contains $__peName -or $__peName -eq 'PSScriptRoot' -or $__peName -match '^__') { throw 'admission' }
                }
            }
            if ($__peKind -eq 'AssignmentStatementAst' -and $__peNode.Left -isnot [System.Management.Automation.Language.VariableExpressionAst]) { throw 'admission' }
            if ($__peKind -eq 'MemberExpressionAst') {
                if ($__peNode.Static -or $__peNode.Member -isnot [System.Management.Automation.Language.StringConstantExpressionAst] -or
                    $__pePolicy.properties -notcontains $__peNode.Member.Value) { throw 'admission' }
            }
            if ($__peKind -in @('TypeConstraintAst', 'TypeExpressionAst')) {
                if ($__peNode.TypeName.FullName -notin @('int', 'int32', 'bool', 'string', 'object', 'object[]', 'pscustomobject', 'hashtable', 'System.ArgumentException')) { throw 'admission' }
            }
            if ($__peKind -eq 'UnaryExpressionAst' -and $__peNode.TokenKind -notin @('Not', 'Exclaim', 'Minus', 'Plus', 'Comma')) { throw 'admission' }
            if ($__peKind -eq 'CommandAst') {
                if ($__peNode.InvocationOperator -eq 'Dot') {
                    $__pePath = $__peNode.CommandElements[0]
                    if ($__pePath.GetType().Name -notin @('StringConstantExpressionAst', 'ExpandableStringExpressionAst')) { throw 'admission' }
                    $__peLiteral = $__pePath.Value.Replace('$PSScriptRoot', "$Workspace/output")
                    if ([System.IO.Path]::GetFullPath($__peLiteral) -ne "$Workspace/input/Subject.ps1" -or $__peNode.CommandElements.Count -ne 1) { throw 'admission' }
                    continue
                }
                if ($__peNode.InvocationOperator -ne 'Unknown') { throw 'admission' }
                $__peCommand = $__peNode.GetCommandName()
                if ($null -eq $__peCommand) { throw 'admission' }
                if ($__peCommand.StartsWith('Pester\', [System.StringComparison]::OrdinalIgnoreCase)) { $__peCommand = $__peCommand.Substring(7) }
                if ($__peCommand -notin @($__peBlocks + $__peAssertions + @('Out-Null', $__pePolicy.command))) { throw 'admission' }
                foreach ($__peElement in $__peNode.CommandElements) {
                    if ($__peElement -is [System.Management.Automation.Language.CommandParameterAst]) {
                        if ($__peAssertions -contains $__peCommand -and $__peAssertParameters -notcontains $__peElement.ParameterName) { throw 'admission' }
                        if ($__peBlocks -contains $__peCommand -and $__peElement.ParameterName -notin @('Name', 'ForEach', 'TestCases', 'Test', 'Tag', 'Skip')) { throw 'admission' }
                    }
                }
                if ($__peCommand -in @('Describe', 'Context', 'It')) {
                    # Pester evaluates <...> templates after PowerShell parsing.
                    # Admit only public data-field templates, never expressions.
                    $__peNameNode = $__peNode.CommandElements[1]
                    $__peNamedNames = @($__peNode.CommandElements | Where-Object {
                        $_ -is [System.Management.Automation.Language.CommandParameterAst] -and $_.ParameterName -eq 'Name'
                    })
                    if ($__peNameNode -is [System.Management.Automation.Language.CommandParameterAst]) {
                        if ($__peNameNode.ParameterName -ne 'Name' -or $__peNamedNames.Count -ne 1) { throw 'admission' }
                        $__peNameNode = if ($null -ne $__peNameNode.Argument) { $__peNameNode.Argument } else { $__peNode.CommandElements[2] }
                    }
                    elseif ($__peNamedNames.Count) { throw 'admission' }
                    # Computed/interpolated names and splats can hide Pester's
                    # second-stage expression execution from the original AST.
                    if ($__peNameNode -isnot [System.Management.Automation.Language.StringConstantExpressionAst]) { throw 'admission' }
                    foreach ($__peElement in @($__peNameNode)) {
                        if ($__peElement.GetType().Name -in @('StringConstantExpressionAst', 'ExpandableStringExpressionAst')) {
                            $__peText = $__peElement.Value
                            foreach ($__peField in @($__pePolicy.properties) + @('_')) {
                                $__peText = [regex]::Replace($__peText, '<' + [regex]::Escape($__peField) + '>', '', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
                            }
                            if ($__peText.Contains('<') -or $__peText.Contains('>')) { throw 'admission' }
                        }
                    }
                }
            }
        }
        $__peResult = @{ status = 'admitted'; code = 'ok' }
        if (-not $AdmissionOnly) {
            $__peResult = @{ status = 'infrastructure_error'; code = 'runtime' }
            if ($PSVersionTable.PSVersion.ToString() -cne '7.6.6') { throw 'runtime' }
            Import-Module -Name $PesterManifest -RequiredVersion 6.2.0 -ErrorAction Stop
            if (@(Get-Module Pester).Count -ne 1 -or (Get-Module Pester).Version.ToString() -cne '6.2.0') { throw 'runtime' }
            $__peConfig = New-PesterConfiguration
            $__peConfig.Run.Path = @($Candidate)
            $__peConfig.Run.RepoRoot = $Workspace
            $__peConfig.Run.PassThru = $true
            $__peConfig.Run.Exit = $false
            $__peConfig.Run.Throw = $false
            $__peConfig.Run.Parallel = $false
            $__peConfig.Output.Verbosity = 'None'
            $__peRun = Invoke-Pester -Configuration $__peConfig
            $__peAssertionFailures = @($__peRun.Tests | Where-Object {
                $_.Result -eq 'Failed' -and @($_.ErrorRecord | Where-Object FullyQualifiedErrorId -Like '*PesterAssertionFailed*').Count -gt 0
            }).Count
            $__peResult = @{
                status = 'executed'; code = 'ok'; version = (Get-Module Pester).Version.ToString()
                powershell_version = $PSVersionTable.PSVersion.ToString()
                total = $__peRun.TotalCount; passed = $__peRun.PassedCount; failed = $__peRun.FailedCount
                skipped = $__peRun.SkippedCount; not_run = $__peRun.NotRunCount; inconclusive = $__peRun.InconclusiveCount
                failed_blocks = $__peRun.FailedBlocksCount; failed_containers = $__peRun.FailedContainersCount
                assertion_failures = $__peAssertionFailures
            }
        }
    }
}
catch {
    # Never render exception messages, script extents, stack traces, candidate
    # values, or Pester failure text into Harbor logs or retained rewards.
}
[Console]::Out.WriteLine(($__peResult | ConvertTo-Json -Compress -Depth 4))
