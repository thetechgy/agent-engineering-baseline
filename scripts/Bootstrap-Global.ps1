<#
.SYNOPSIS
Installs and deploys the repository-approved global APM baseline.

.DESCRIPTION
Installs or upgrades APM to the version in apm-cli.lock.yml, rejects a newer
unreviewed CLI, validates any existing official GitHub MCP entry, and delegates
deployment to native APM global install and compile commands.

.EXAMPLE
./scripts/Bootstrap-Global.ps1

.EXAMPLE
./scripts/Bootstrap-Global.ps1 -WhatIf
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$script:GithubMcpName = 'github-mcp-server'
$script:GithubMcpUrl = 'https://api.githubcopilot.com/mcp/'

function Get-ApmLockValue {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Content,
        [Parameter(Mandatory)][string]$Pattern,
        [Parameter(Mandatory)][string]$Description
    )

    $match = [regex]::Match($Content, $Pattern, [Text.RegularExpressions.RegexOptions]::Multiline)
    if (-not $match.Success) { throw "APM CLI lock is missing $Description." }
    return $match.Groups[1].Value.Trim().Trim("'")
}

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

function Test-DefaultGithubMcpConfiguration {
    [CmdletBinding()]
    param([Parameter(Mandatory)][object]$Configuration)

    $expectedTop = @(
        'disabled_reason', 'disabled_tools', 'enabled', 'enabled_tools', 'name',
        'startup_timeout_sec', 'tool_timeout_sec', 'transport'
    ) -join ','
    $actualTop = @($Configuration.PSObject.Properties.Name | Sort-Object) -join ','
    $expectedTransport = @(
        'bearer_token_env_var', 'env_http_headers', 'http_headers',
        'http_headers_helper', 'type', 'url'
    ) -join ','
    $actualTransport = @($Configuration.transport.PSObject.Properties.Name | Sort-Object) -join ','

    return $actualTop -ceq $expectedTop -and $actualTransport -ceq $expectedTransport -and
        $Configuration.name -ceq $script:GithubMcpName -and $Configuration.enabled -eq $true -and
        $null -eq $Configuration.disabled_reason -and $null -eq $Configuration.enabled_tools -and
        $null -eq $Configuration.disabled_tools -and $null -eq $Configuration.startup_timeout_sec -and
        $null -eq $Configuration.tool_timeout_sec -and
        $Configuration.transport.type -ceq 'streamable_http' -and
        $Configuration.transport.url -ceq $script:GithubMcpUrl -and
        $Configuration.transport.bearer_token_env_var -ceq 'GITHUB_TOKEN' -and
        $null -eq $Configuration.transport.http_headers -and
        $null -eq $Configuration.transport.env_http_headers -and
        $null -eq $Configuration.transport.http_headers_helper
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

function Assert-CompatibleGithubMcp {
    [CmdletBinding()]
    param()

    $codex = Get-Command -Name codex -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $codex) { return }
    $output = & $codex.Source mcp get $script:GithubMcpName --json 2>&1
    if ($LASTEXITCODE -eq 0) {
        $configuration = ($output -join "`n") | ConvertFrom-Json
        if (-not (Test-DefaultGithubMcpConfiguration -Configuration $configuration)) {
            throw "Existing Codex MCP entry '$($script:GithubMcpName)' is customized; refusing to replace it."
        }
    }
    elseif (($output -join "`n") -notmatch "No MCP server named '$($script:GithubMcpName)' found\.") {
        throw "Unable to inspect the existing Codex MCP entry '$($script:GithubMcpName)'."
    }
}

function Invoke-GlobalBootstrap {
    [CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
    param([Parameter(Mandatory)][string]$RepositoryRoot)

    $content = Get-Content -LiteralPath (Join-Path $RepositoryRoot 'apm-cli.lock.yml') -Raw
    $approvedVersion = [version](Get-ApmLockValue -Content $content `
        -Pattern '^version:\s*([^\r\n]+)' -Description 'version')
    $installerUrl = Get-ApmLockValue -Content $content `
        -Pattern '(?m)^  windows:\s*\r?\n    url:\s*([^\r\n]+)' `
        -Description 'Windows installer URL'
    $installerHash = Get-ApmLockValue -Content $content `
        -Pattern '(?m)^  windows:\s*\r?\n    url:[^\r\n]+\r?\n    sha256:\s*([^\r\n]+)' `
        -Description 'Windows installer hash'
    $executableHash = Get-ApmLockValue -Content $content `
        -Pattern '(?m)^  windows-x86_64:\s*\r?\n    name:[^\r\n]+\r?\n    sha256:[^\r\n]+\r?\n    executable_sha256:\s*([^\r\n]+)' `
        -Description 'Windows executable hash'

    $apm = Get-Command -Name apm -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    $installedVersion = $null
    if ($null -ne $apm) {
        $installedVersion = ConvertTo-ApmVersion -Text ((& $apm.Source --version 2>&1) -join "`n")
    }
    $action = Get-ApmBootstrapAction -InstalledVersion $installedVersion -ApprovedVersion $approvedVersion
    if ($action -ceq 'Stop') {
        throw "Installed APM $installedVersion is newer than reviewed baseline $approvedVersion; deployment stopped."
    }

    Assert-CompatibleGithubMcp
    if ($WhatIfPreference) {
        Write-Information "Dry run: APM CLI action: $action (approved version $approvedVersion)." -InformationAction Continue
        Write-Information 'Dry run: would run apm install --global --frozen and apm compile --global.' -InformationAction Continue
        Write-Information 'Dry run: no files were downloaded or changed.' -InformationAction Continue
        return
    }

    if (-not $PSCmdlet.ShouldProcess("Global APM baseline $approvedVersion", 'Deploy reviewed configuration')) {
        return
    }

    if ($action -ne 'None') {
        $installerPath = Join-Path ([IO.Path]::GetTempPath()) ("apm-install-{0}.ps1" -f [Guid]::NewGuid().ToString('N'))
        $previousSecurityProtocol = [Net.ServicePointManager]::SecurityProtocol
        try {
            [Net.ServicePointManager]::SecurityProtocol = $previousSecurityProtocol -bor
                [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
            $actualHash = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($actualHash -cne $installerHash) {
                throw 'The downloaded APM installer does not match apm-cli.lock.yml.'
            }
            $previousVersion = $env:VERSION
            try {
                $env:VERSION = "v$approvedVersion"
                & $installerPath
            }
            finally { $env:VERSION = $previousVersion }
        }
        finally {
            [Net.ServicePointManager]::SecurityProtocol = $previousSecurityProtocol
            Remove-Item -LiteralPath $installerPath -Force -ErrorAction SilentlyContinue
        }
        $apm = Get-Command -Name apm -CommandType Application -ErrorAction Stop |
            Select-Object -First 1
        $activeVersion = ConvertTo-ApmVersion -Text ((& $apm.Source --version 2>&1) -join "`n")
        if ($activeVersion -ne $approvedVersion) {
            throw "APM installation completed but version $approvedVersion is not active."
        }
        $activeExecutable = $apm.Source
        if ([IO.Path]::GetExtension($activeExecutable) -ieq '.cmd') {
            $installRoot = Split-Path -Parent (Split-Path -Parent $activeExecutable)
            $activeExecutable = Join-Path $installRoot 'current/apm.exe'
        }
        if (-not [IO.File]::Exists($activeExecutable) -or
            (Get-FileHash -LiteralPath $activeExecutable -Algorithm SHA256).Hash.ToLowerInvariant() -cne
                $executableHash) {
            throw 'The installed APM executable does not match apm-cli.lock.yml.'
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
