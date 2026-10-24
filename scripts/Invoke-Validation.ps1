<#
.SYNOPSIS
Runs the repository validation suite.

.DESCRIPTION
The Full suite (default) runs Pester, PSScriptAnalyzer, the Bash bootstrap
tests, isolated native APM install/compile/audit/package checks, ShellCheck,
Markdown linting, and `git diff --check`. The Pester suite runs only
Pester and PSScriptAnalyzer, for hosts without the Unix tooling (for example
Windows CI).

.EXAMPLE
./scripts/Invoke-Validation.ps1

.EXAMPLE
./scripts/Invoke-Validation.ps1 -Suite Pester
#>
#Requires -Version 7.0
[CmdletBinding()]
param(
    [Parameter()]
    [ValidateSet('Full', 'Pester')]
    [string]$Suite = 'Full'
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $repositoryRoot
try {
    $configuration = New-PesterConfiguration
    $configuration.Run.Path = './tests'
    $configuration.Run.PassThru = $true
    $configuration.Run.Throw = $false
    $configuration.Should.DisableV5 = $true
    $configuration.Output.Verbosity = 'Detailed'
    $result = Invoke-Pester -Configuration $configuration
    if ($result.FailedCount -gt 0 -or $result.FailedContainers.Count -gt 0 -or
        $result.Result -cne 'Passed') {
        throw (
            "Pester did not pass: result=$($result.Result), failed tests=$($result.FailedCount), " +
            "failed containers=$($result.FailedContainers.Count)."
        )
    }

    $analyzerResults = @()
    foreach ($path in @(Get-ChildItem ./scripts, ./tests -Filter '*.ps1' -File -Recurse)) {
        $analyzerResults += @(Invoke-ScriptAnalyzer -Path $path.FullName -Severity Warning,Error)
    }
    if ($analyzerResults.Count -gt 0) {
        $analyzerResults | Format-Table RuleName, Severity, ScriptName, Line, Message -Wrap
        throw "PSScriptAnalyzer reported $($analyzerResults.Count) finding(s)."
    }

    if ($Suite -eq 'Pester') { return }

    & ./tests/bootstrap.sh
    if ($LASTEXITCODE -ne 0) { throw 'Bash bootstrap tests failed.' }

    $apmExecutable = if ($env:APM_EXECUTABLE) {
        [IO.Path]::GetFullPath($env:APM_EXECUTABLE)
    }
    else {
        $apmCommand = Get-Command -Name apm -CommandType Application -ErrorAction Stop |
            Select-Object -First 1
        [IO.Path]::GetFullPath($apmCommand.Source)
    }
    if (-not (Test-Path -LiteralPath $apmExecutable -PathType Leaf)) {
        throw "The absolute APM executable does not exist: $apmExecutable"
    }

    & python3 ./scripts/apm_regeneration.py --apm $apmExecutable
    if ($LASTEXITCODE -ne 0) { throw 'Isolated APM regeneration failed.' }

    & shellcheck ./scripts/bootstrap.sh ./tests/bootstrap.sh
    if ($LASTEXITCODE -ne 0) { throw 'ShellCheck failed.' }
    & rumdl check .
    if ($LASTEXITCODE -ne 0) { throw 'Markdown linting failed.' }

    & git diff --check
    if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed.' }
}
finally { Pop-Location }
