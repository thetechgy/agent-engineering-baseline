[CmdletBinding()]
param()

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

    & ./tests/bootstrap-global.sh
    if ($LASTEXITCODE -ne 0) { throw 'Bash bootstrap tests failed.' }
    & pwsh -NoLogo -NoProfile -File ./scripts/Sync-UpstreamSkills.ps1 -Check
    if ($LASTEXITCODE -ne 0) { throw 'Upstream mirror verification failed.' }

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

    $analyzerResults = @()
    foreach ($path in @(Get-ChildItem ./scripts, ./tests -Filter '*.ps1' -File -Recurse)) {
        $analyzerResults += @(Invoke-ScriptAnalyzer -Path $path.FullName -Severity Warning,Error)
    }
    if ($analyzerResults.Count -gt 0) {
        $analyzerResults | Format-Table RuleName, Severity, ScriptName, Line, Message -Wrap
        throw "PSScriptAnalyzer reported $($analyzerResults.Count) finding(s)."
    }

    & shellcheck ./scripts/bootstrap-global.sh ./tests/bootstrap-global.sh
    if ($LASTEXITCODE -ne 0) { throw 'ShellCheck failed.' }
    & rumdl check .
    if ($LASTEXITCODE -ne 0) { throw 'Markdown linting failed.' }
    & git diff --check
    if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed.' }

    $projectMarker = [string]::Concat([char]70, [char]65, [char]67, [char]84)
    $projectReferences = & git grep -n $projectMarker -- .
    if ($LASTEXITCODE -eq 0 -or $projectReferences) {
        $projectReferences | Write-Output
        throw 'Tracked content contains a project-specific reference.'
    }
}
finally { Pop-Location }
