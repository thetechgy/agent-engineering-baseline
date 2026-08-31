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

    if ($Suite -ceq 'Pester') { return }

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

    & $apmExecutable install --frozen --trust-bin
    if ($LASTEXITCODE -ne 0) { throw 'Frozen APM install failed.' }
    & $apmExecutable compile --target codex,copilot --validate
    if ($LASTEXITCODE -ne 0) { throw 'APM compile validation failed.' }
    & $apmExecutable compile --target codex,copilot
    if ($LASTEXITCODE -ne 0) { throw 'APM compilation failed.' }
    # APM 0.29 audit replay exposes no --trust-bin option and treats a
    # non-TTY replay as untrusted even after a frozen --trust-bin install.
    # Run the unchanged native audit in a pseudo-terminal so its scratch
    # replay includes the reviewed launcher set. Do not replace this with
    # --no-drift; the full drift comparison is a required gate.
    $scriptCommand = Get-Command -Name script -CommandType Application -ErrorAction Stop |
        Select-Object -First 1
    $previousApmExecutable = $env:APM_EXECUTABLE
    $previousAuditStatus = $env:APM_AUDIT_STATUS
    $auditStatusPath = $null
    $auditExitCode = $null
    try {
        $env:APM_EXECUTABLE = $apmExecutable
        & $scriptCommand.Source -q -e -c 'exit 0' /dev/null *> $null
        if ($LASTEXITCODE -eq 0) {
            & $scriptCommand.Source -q -e -c 'exec "$APM_EXECUTABLE" audit --ci' /dev/null
            $auditExitCode = $LASTEXITCODE
        }
        else {
            $auditStatusPath = [IO.Path]::GetTempFileName()
            $env:APM_AUDIT_STATUS = $auditStatusPath
            & $scriptCommand.Source -q /dev/null sh -c (
                '"$APM_EXECUTABLE" audit --ci; status=$?; ' +
                'printf "%s\n" "$status" > "$APM_AUDIT_STATUS"; exit "$status"'
            )
            $auditStatusText = if (Test-Path -LiteralPath $auditStatusPath -PathType Leaf) {
                [IO.File]::ReadAllText($auditStatusPath).Trim()
            }
            else { '' }
            if ($auditStatusText -notmatch '^[0-9]+$') {
                throw 'BSD script did not report the APM audit exit status.'
            }
            $auditExitCode = [int]$auditStatusText
        }
    }
    finally {
        if ($auditStatusPath -and (Test-Path -LiteralPath $auditStatusPath)) {
            Remove-Item -LiteralPath $auditStatusPath -Force -ErrorAction SilentlyContinue
        }
        if ($null -eq $previousApmExecutable) {
            Remove-Item Env:APM_EXECUTABLE -ErrorAction SilentlyContinue
        }
        else { $env:APM_EXECUTABLE = $previousApmExecutable }
        if ($null -eq $previousAuditStatus) {
            Remove-Item Env:APM_AUDIT_STATUS -ErrorAction SilentlyContinue
        }
        else { $env:APM_AUDIT_STATUS = $previousAuditStatus }
    }
    if ($auditExitCode -ne 0) { throw 'APM audit failed.' }
    & $apmExecutable pack --dry-run
    if ($LASTEXITCODE -ne 0) { throw 'APM package check failed.' }

    $msgraphOutput = & bash ./.agents/skills/msgraph/scripts/run.sh openapi-search --query users --limit 1
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($msgraphOutput -join ''))) {
        throw 'Offline msgraph launcher/index smoke test failed.'
    }

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
