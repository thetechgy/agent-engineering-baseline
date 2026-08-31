<#
.SYNOPSIS
Runs the repository validation suite.

.DESCRIPTION
The Full suite (default) runs Pester, PSScriptAnalyzer, the Bash bootstrap
tests, the native APM install/compile/audit/package checks, ShellCheck,
Markdown linting, and repository hygiene checks. The Pester suite runs only
Pester and PSScriptAnalyzer, for hosts without the Unix tooling (for example
Windows PowerShell 5.1 CI).

.EXAMPLE
./scripts/Invoke-Validation.ps1

.EXAMPLE
./scripts/Invoke-Validation.ps1 -Suite Pester
#>
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
    if ($result.FailedCount -gt 0) { throw "Pester reported $($result.FailedCount) failed test(s)." }

    $analyzerResults = @()
    foreach ($path in @(Get-ChildItem ./scripts, ./tests -Filter '*.ps1' -File -Recurse)) {
        $analyzerResults += @(Invoke-ScriptAnalyzer -Path $path.FullName -Severity Warning,Error)
    }
    if ($analyzerResults.Count -gt 0) {
        $analyzerResults | Format-Table RuleName, Severity, ScriptName, Line, Message -Wrap
        throw "PSScriptAnalyzer reported $($analyzerResults.Count) finding(s)."
    }

    if ($Suite -ceq 'Pester') { return }

    & ./tests/bootstrap.sh
    if ($LASTEXITCODE -ne 0) { throw 'Bash bootstrap tests failed.' }

    & apm install --frozen
    if ($LASTEXITCODE -ne 0) { throw 'Frozen APM install failed.' }
    & apm compile --target codex,copilot --validate
    if ($LASTEXITCODE -ne 0) { throw 'APM compile validation failed.' }
    & apm compile --target codex,copilot
    if ($LASTEXITCODE -ne 0) { throw 'APM compilation failed.' }
    & apm audit --ci
    if ($LASTEXITCODE -ne 0) { throw 'APM audit failed.' }
    & apm pack --dry-run
    if ($LASTEXITCODE -ne 0) { throw 'APM package check failed.' }

    & shellcheck ./scripts/bootstrap.sh ./tests/bootstrap.sh
    if ($LASTEXITCODE -ne 0) { throw 'ShellCheck failed.' }
    & rumdl check .
    if ($LASTEXITCODE -ne 0) { throw 'Markdown linting failed.' }

    # The marker is assembled from character codes so this tracked script never
    # matches the project-specific reference it guards against.
    $projectMarker = -join ([char[]](70, 65, 67, 84))
    $projectReferences = @(& git grep -n $projectMarker -- .)
    $grepExitCode = $LASTEXITCODE
    if ($grepExitCode -gt 1) { throw "git grep failed with exit code $grepExitCode." }
    if ($grepExitCode -eq 0 -or $projectReferences.Count -gt 0) {
        $projectReferences | Write-Output
        throw 'Tracked content contains a project-specific reference.'
    }

    & git diff --check
    if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed.' }
}
finally { Pop-Location }
