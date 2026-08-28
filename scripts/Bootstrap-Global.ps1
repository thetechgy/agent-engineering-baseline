<#
.SYNOPSIS
Installs and deploys the repository-pinned global APM baseline.

.DESCRIPTION
Installs or upgrades APM to the version pinned in .apm-version using the
official installer (which validates the release checksum sidecar for pinned
versions), rejects a newer unpinned CLI, and delegates deployment to native
APM global install and compile commands.

.EXAMPLE
./scripts/Bootstrap-Global.ps1

.EXAMPLE
./scripts/Bootstrap-Global.ps1 -WhatIf
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function ConvertTo-ApmVersion {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Text)

    $match = [regex]::Match($Text, '(?<!\d)(\d+\.\d+\.\d+)(?!\d)')
    if (-not $match.Success) { throw "Unable to parse APM version from: $Text" }
    return [version]$match.Groups[1].Value
}

function Get-ApmBootstrapAction {
    [CmdletBinding()]
    param(
        [Parameter()][AllowNull()][version]$InstalledVersion,
        [Parameter(Mandatory)][version]$ApprovedVersion
    )

    if ($null -eq $InstalledVersion) { return 'Install' }
    if ($InstalledVersion -gt $ApprovedVersion) { return 'Stop' }
    if ($InstalledVersion -lt $ApprovedVersion) { return 'Upgrade' }
    return 'None'
}

function Invoke-NativeCommand {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Executable,
        [Parameter(Mandatory)][string[]]$ArgumentList,
        [Parameter()][string]$WorkingDirectory
    )

    $pushed = $false
    try {
        if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
            Push-Location -LiteralPath $WorkingDirectory
            $pushed = $true
        }
        & $Executable @ArgumentList
        if ($LASTEXITCODE -ne 0) {
            throw "Native command failed with exit code ${LASTEXITCODE}: $Executable $($ArgumentList -join ' ')"
        }
    }
    finally {
        if ($pushed) { Pop-Location }
    }
}

function Update-ProcessPath {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param()

    # The installer registers its bin directory in the user PATH; merge any
    # missing machine or user entries into this process so apm resolves.
    if (-not $PSCmdlet.ShouldProcess('process PATH', 'Merge machine and user PATH entries')) { return }
    $separator = [IO.Path]::PathSeparator
    $current = @($env:PATH -split [regex]::Escape($separator))
    foreach ($scope in @('Machine', 'User')) {
        $scoped = [Environment]::GetEnvironmentVariable('Path', $scope)
        if ([string]::IsNullOrWhiteSpace($scoped)) { continue }
        foreach ($entry in @($scoped -split [regex]::Escape($separator))) {
            if (-not [string]::IsNullOrWhiteSpace($entry) -and $current -notcontains $entry) {
                $env:PATH = "$($env:PATH)$separator$entry"
                $current += $entry
            }
        }
    }
}

function Invoke-GlobalBootstrap {
    [CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
    param([Parameter(Mandatory)][string]$RepositoryRoot)

    $pinPath = Join-Path $RepositoryRoot '.apm-version'
    $pinText = (Get-Content -LiteralPath $pinPath -TotalCount 1).Trim()
    if ($pinText -notmatch '^\d+\.\d+\.\d+$') {
        throw "The APM version pin is not a plain X.Y.Z version: $pinText"
    }
    $approvedVersion = [version]$pinText

    $apm = Get-Command -Name apm -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    $installedVersion = $null
    if ($null -ne $apm) {
        $installedVersion = ConvertTo-ApmVersion -Text ((& $apm.Source --version 2>&1) -join "`n")
    }
    $action = Get-ApmBootstrapAction -InstalledVersion $installedVersion -ApprovedVersion $approvedVersion
    if ($action -ceq 'Stop') {
        throw "Installed APM $installedVersion is newer than pinned baseline $approvedVersion; deployment stopped."
    }

    if ($WhatIfPreference) {
        Write-Information "Dry run: APM CLI action: $action (pinned version $approvedVersion)." -InformationAction Continue
        Write-Information 'Dry run: would run apm install --global --frozen and apm compile --global.' -InformationAction Continue
        Write-Information 'Dry run: no files were downloaded or changed.' -InformationAction Continue
        return
    }

    if (-not $PSCmdlet.ShouldProcess("Global APM baseline $approvedVersion", 'Deploy pinned configuration')) {
        return
    }

    if ($action -ne 'None') {
        $installerUrl = "https://raw.githubusercontent.com/microsoft/apm/v$approvedVersion/install.ps1"
        $installerPath = Join-Path ([IO.Path]::GetTempPath()) ("apm-install-{0}.ps1" -f [Guid]::NewGuid().ToString('N'))
        $previousSecurityProtocol = [Net.ServicePointManager]::SecurityProtocol
        $previousVersion = $env:VERSION
        try {
            [Net.ServicePointManager]::SecurityProtocol = $previousSecurityProtocol -bor
                [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
            $env:VERSION = "v$approvedVersion"
            & $installerPath
        }
        finally {
            $env:VERSION = $previousVersion
            [Net.ServicePointManager]::SecurityProtocol = $previousSecurityProtocol
            Remove-Item -LiteralPath $installerPath -Force -ErrorAction SilentlyContinue
        }
        Update-ProcessPath
        $apm = Get-Command -Name apm -CommandType Application -ErrorAction Stop |
            Select-Object -First 1
        $activeVersion = ConvertTo-ApmVersion -Text ((& $apm.Source --version 2>&1) -join "`n")
        if ($activeVersion -ne $approvedVersion) {
            throw "APM installation completed but version $approvedVersion is not active."
        }
    }

    $apm = Get-Command -Name apm -CommandType Application -ErrorAction Stop |
        Select-Object -First 1
    Invoke-NativeCommand -Executable $apm.Source -WorkingDirectory $RepositoryRoot `
        -ArgumentList @('install', '--global', '--frozen')
    Invoke-NativeCommand -Executable $apm.Source -WorkingDirectory $RepositoryRoot `
        -ArgumentList @('compile', '--global', '--dry-run')
    Invoke-NativeCommand -Executable $apm.Source -WorkingDirectory $RepositoryRoot `
        -ArgumentList @('compile', '--global')
    Write-Information "Global APM baseline $approvedVersion is ready." -InformationAction Continue
}

if ($MyInvocation.InvocationName -ne '.') {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'Bootstrap-Global.ps1 supports Windows; use bootstrap-global.sh on Linux.'
    }
    $invokeParameters = @{
        RepositoryRoot = Split-Path -Parent $PSScriptRoot
        WhatIf = [bool]$WhatIfPreference
    }
    if ($PSBoundParameters.ContainsKey('Confirm')) {
        $invokeParameters.Confirm = [bool]$PSBoundParameters.Confirm
    }
    Invoke-GlobalBootstrap @invokeParameters
}
