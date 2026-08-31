<#
.SYNOPSIS
Bootstraps the agent engineering baseline with the native APM CLI.

.DESCRIPTION
Ensures the pinned APM CLI version from .apm-version is installed (using the
official upstream install.ps1, which natively verifies .sha256 sidecars for
pinned versions), upgrades an older CLI in place with `apm self-update`, then
deploys the baseline package natively:

  -Scope Global   apm install --global <ref>; apm compile --global
  -Scope Repo     apm install --target codex,copilot <ref>; apm compile
                  (run from the target project)

Everything else (skill deployment, instruction deployment, lockfiles,
uninstall, updates) is native APM behavior. See README.md.

.PARAMETER Scope
Global installs the baseline machine-wide (user scope, default). Repo installs
it into the project at the current directory.

.EXAMPLE
./scripts/Bootstrap-Baseline.ps1

.EXAMPLE
./scripts/Bootstrap-Baseline.ps1 -Scope Repo -WhatIf
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param(
    [Parameter()]
    [ValidateSet('Global', 'Repo')]
    [string]$Scope = 'Global'
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$packageRef = if ($env:BASELINE_PACKAGE_REF) { $env:BASELINE_PACKAGE_REF }
else { 'thetechgy/agent-engineering-baseline#main' }
$installerUrlBase = if ($env:APM_INSTALLER_URL_BASE) { $env:APM_INSTALLER_URL_BASE }
else { 'https://raw.githubusercontent.com/microsoft/apm' }

function Read-PinnedVersion {
    $pinFile = Join-Path (Split-Path -Parent $PSScriptRoot) '.apm-version'
    if (-not (Test-Path -LiteralPath $pinFile)) { throw ".apm-version not found at $pinFile" }
    $pin = (Get-Content -LiteralPath $pinFile -TotalCount 1).Trim()
    if ($pin -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$') {
        throw ".apm-version must contain a semantic version, got: '$pin'"
    }
    $pin
}

function Get-InstalledApmVersion {
    $command = Get-Command -Name apm -ErrorAction SilentlyContinue
    if (-not $command) { return $null }
    $banner = & apm --version 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $banner) { return $null }
    if ("$banner" -match '([0-9]+\.[0-9]+\.[0-9]+)') { return $Matches[1] }
    $null
}

function Install-PinnedApmCli {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param([Parameter(Mandatory)][string]$Pin)

    if (-not $PSCmdlet.ShouldProcess("APM CLI v$Pin", 'Download and run the official installer')) {
        return
    }
    $installer = Join-Path ([IO.Path]::GetTempPath()) "apm-install-$([Guid]::NewGuid().ToString('N')).ps1"
    try {
        Invoke-WebRequest -Uri "$installerUrlBase/v$Pin/install.ps1" -OutFile $installer
        $previousVersion = $env:VERSION
        try {
            $env:VERSION = "v$Pin"
            # install.ps1 throws/exits on failure; success is verified by the
            # post-install version check in Confirm-ApmCli rather than
            # $LASTEXITCODE, which script invocations may leave stale.
            & $installer
        }
        finally {
            if ($null -eq $previousVersion) { Remove-Item Env:VERSION -ErrorAction SilentlyContinue }
            else { $env:VERSION = $previousVersion }
        }
    }
    finally {
        Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-ApmSelfUpdate {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param([Parameter(Mandatory)][string]$Pin)

    if (-not $PSCmdlet.ShouldProcess("APM CLI v$Pin", 'Upgrade via apm self-update')) { return }
    $previousVersion = $env:VERSION
    try {
        $env:VERSION = "v$Pin"
        & apm self-update
        if ($LASTEXITCODE -ne 0) {
            throw ('apm self-update failed. If this CLI was installed via pip or another ' +
                'package manager, or self-update is disabled by policy, upgrade it with ' +
                'that tool or remove it and re-run.')
        }
    }
    finally {
        if ($null -eq $previousVersion) { Remove-Item Env:VERSION -ErrorAction SilentlyContinue }
        else { $env:VERSION = $previousVersion }
    }
}

function Confirm-ApmCli {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param([Parameter(Mandatory)][string]$Pin)

    $current = Get-InstalledApmVersion
    $assertExact = $true
    if (-not $current) {
        Write-Information -MessageData "APM CLI not found; installing v$Pin" -InformationAction Continue
        Install-PinnedApmCli -Pin $Pin
    }
    elseif ($current -eq $Pin) {
        Write-Information -MessageData "APM CLI v$current already matches the pin" -InformationAction Continue
    }
    elseif ([version]$current -lt [version]$Pin) {
        Write-Information -MessageData "Upgrading APM CLI v$current -> v$Pin via apm self-update" `
            -InformationAction Continue
        Invoke-ApmSelfUpdate -Pin $Pin
    }
    else {
        Write-Warning "Installed APM CLI v$current is newer than the pinned v$Pin; continuing."
        $assertExact = $false
    }

    if ($WhatIfPreference -or -not $assertExact) { return }
    $current = Get-InstalledApmVersion
    if (-not $current) {
        throw ('The APM CLI is not runnable from this session. If it was just installed, ' +
            'open a new terminal so PATH changes take effect, then re-run this script.')
    }
    if ($current -ne $Pin) { throw "APM CLI reports v$current after setup, expected v$Pin." }
}

function Install-Baseline {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param()

    if ($Scope -ceq 'Global') {
        if ($PSCmdlet.ShouldProcess($packageRef, 'Install to user scope and compile root contexts')) {
            & apm install --global $packageRef
            if ($LASTEXITCODE -ne 0) { throw 'apm install --global failed.' }
            & apm compile --global
            if ($LASTEXITCODE -ne 0) { throw 'apm compile --global failed.' }
        }
        return
    }
    $project = (Get-Location).Path
    if ($PSCmdlet.ShouldProcess($project, "Install $packageRef into this project and compile")) {
        Write-Information -MessageData 'Note: this updates the project''s apm.yml, lockfile, and compiled outputs.' `
            -InformationAction Continue
        & apm install --target codex,copilot $packageRef
        if ($LASTEXITCODE -ne 0) { throw 'apm install failed.' }
        & apm compile
        if ($LASTEXITCODE -ne 0) { throw 'apm compile failed.' }
    }
}

$pin = Read-PinnedVersion
Write-Information -MessageData "Pinned APM CLI version: v$pin (scope: $Scope)" -InformationAction Continue
Confirm-ApmCli -Pin $pin
Install-Baseline
Write-Information -MessageData 'Done.' -InformationAction Continue
