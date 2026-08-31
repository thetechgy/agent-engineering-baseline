<#
.SYNOPSIS
Acquires the reviewed APM CLI bundle and deploys the baseline with native APM.

.DESCRIPTION
Downloads a fresh pinned Windows x86_64 release archive, verifies the tracked
archive and executable digests, rejects unsafe ZIP entries, executes only the
staged absolute executable, and transactionally promotes the complete onedir
bundle into APM's releases/current/bin layout. Native APM then owns package
installation, executable trust, compilation, update, audit, and packing.

.PARAMETER Scope
Global installs at user scope. Repo installs into the current repository.

.PARAMETER CliOnly
Acquire the reviewed CLI without installing the baseline package.

.EXAMPLE
./scripts/Bootstrap-Baseline.ps1

.EXAMPLE
./scripts/Bootstrap-Baseline.ps1 -Scope Repo

.EXAMPLE
./scripts/Bootstrap-Baseline.ps1 -WhatIf
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param(
    [Parameter()]
    [ValidateSet('Global', 'Repo')]
    [string]$Scope = 'Global',

    [Parameter()]
    [switch]$CliOnly
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$pinFile = Join-Path $repositoryRoot '.apm-version'
$checksumsFile = Join-Path $repositoryRoot '.apm-checksums'
$defaultPackageRef = 'https://github.com/thetechgy/agent-engineering-baseline.git#main'
$originalProcessPath = $env:PATH

function Test-TruthyValue {
    [CmdletBinding()]
    param([AllowNull()][string]$Value)

    if ($null -eq $Value) { return $false }
    @('1', 'true', 'yes', 'on') -contains $Value.ToLowerInvariant()
}

function Read-ReviewedConfig {
    [CmdletBinding()]
    param()

    if (-not (Test-Path -LiteralPath $pinFile -PathType Leaf)) {
        throw ".apm-version not found at $pinFile"
    }
    if ((Get-Item -LiteralPath $pinFile -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw ".apm-version must not be a reparse point: $pinFile"
    }
    $pinLines = @([IO.File]::ReadAllLines($pinFile))
    if ($pinLines.Count -ne 1 -or
        $pinLines[0] -notmatch '^[0-9]+\.[0-9]+\.[0-9]+(a[0-9]+|b[0-9]+|rc[0-9]+)?$') {
        throw '.apm-version must contain exactly one full APM version.'
    }

    if (-not (Test-Path -LiteralPath $checksumsFile -PathType Leaf)) {
        throw ".apm-checksums not found at $checksumsFile"
    }
    if ((Get-Item -LiteralPath $checksumsFile -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw ".apm-checksums must not be a reparse point: $checksumsFile"
    }
    $expectedNames = @(
        'apm-darwin-arm64.tar.gz'
        'apm-darwin-arm64/apm'
        'apm-darwin-x86_64.tar.gz'
        'apm-darwin-x86_64/apm'
        'apm-linux-arm64.tar.gz'
        'apm-linux-arm64/apm'
        'apm-linux-x86_64.tar.gz'
        'apm-linux-x86_64/apm'
        'apm-windows-x86_64.zip'
        'apm-windows-x86_64/apm.exe'
    )
    $lines = @([IO.File]::ReadAllLines($checksumsFile))
    if ($lines.Count -ne $expectedNames.Count) {
        throw '.apm-checksums must contain exactly ten entries.'
    }
    $digests = New-Object 'System.Collections.Generic.Dictionary[string,string]' (
        [StringComparer]::Ordinal
    )
    foreach ($line in $lines) {
        if ($line -notmatch '^([0-9a-f]{64})  (\S+)$') {
            throw ".apm-checksums contains a malformed entry: $line"
        }
        if ($digests.ContainsKey($Matches[2])) {
            throw "Duplicate checksum entry: $($Matches[2])"
        }
        $digests.Add($Matches[2], $Matches[1])
    }
    foreach ($name in $expectedNames) {
        if (-not $digests.ContainsKey($name)) {
            throw "Missing checksum entry: $name"
        }
    }
    [pscustomobject]@{
        Pin     = $pinLines[0]
        Digests = $digests
    }
}

function Assert-ReviewedFile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)]$Metadata
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Name is not a regular file: $Path"
    }
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "$Name is a reparse point: $Path"
    }
    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -cne $Metadata.Digests[$Name]) {
        throw "$Name does not match its reviewed SHA256 digest."
    }
}

function Assert-SafeDirectory {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Label,
        [switch]$RequireExisting
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        if ($RequireExisting) { throw "$Label does not exist: $Path" }
        return
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$Label is not a directory: $Path"
    }
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "$Label is a reparse point: $Path"
    }
}

function Assert-PlainTree {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Label
    )

    Assert-SafeDirectory -Path $Path -Label $Label -RequireExisting
    $reparseItem = Get-ChildItem -LiteralPath $Path -Force -Recurse |
        Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint } |
        Select-Object -First 1
    if ($reparseItem) {
        throw "$Label contains a reparse point: $($reparseItem.FullName)"
    }
}

function Get-ArchiveUri {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Pin,
        [Parameter(Mandatory)][string]$ArchiveName
    )

    $base = $env:APM_RELEASE_BASE_URL
    if (-not [string]::IsNullOrWhiteSpace($base)) {
        $baseUri = $null
        if (-not [Uri]::TryCreate($base, [UriKind]::Absolute, [ref]$baseUri) -or
            $baseUri.Scheme -cne 'https') {
            throw 'APM_RELEASE_BASE_URL must be an absolute HTTPS URL.'
        }
        if (-not [string]::IsNullOrEmpty($baseUri.UserInfo)) {
            throw 'APM_RELEASE_BASE_URL must not contain credentials.'
        }
        return "$($base.TrimEnd('/'))/v$Pin/$ArchiveName"
    }
    if (Test-TruthyValue -Value $env:APM_NO_DIRECT_FALLBACK) {
        throw 'APM_NO_DIRECT_FALLBACK is truthy but no APM_RELEASE_BASE_URL is configured.'
    }
    "https://github.com/microsoft/apm/releases/download/v$Pin/$ArchiveName"
}

function Invoke-ArchiveDownload {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Uri,
        [Parameter(Mandatory)][string]$OutFile
    )

    $previousProtocol = [Net.ServicePointManager]::SecurityProtocol
    try {
        [Net.ServicePointManager]::SecurityProtocol =
            $previousProtocol -bor [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $Uri -OutFile $OutFile -UseBasicParsing
    }
    finally {
        [Net.ServicePointManager]::SecurityProtocol = $previousProtocol
    }
}

function Assert-SafeZipLayout {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$ArchivePath,
        [Parameter(Mandatory)][string]$ExpectedRoot,
        [Parameter(Mandatory)][string]$ExecutableMember
    )

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($ArchivePath)
    try {
        $executableCount = 0
        $internalFileCount = 0
        $entryNames = New-Object 'System.Collections.Generic.HashSet[string]' (
            [StringComparer]::OrdinalIgnoreCase
        )
        foreach ($entry in $archive.Entries) {
            $path = $entry.FullName.Replace('\', '/')
            if (-not $entryNames.Add($path)) {
                throw "Archive contains a duplicate or case-colliding entry: $path"
            }
            if ($path -ceq $ExecutableMember) { $executableCount++ }
            if ($path -cne $ExpectedRoot -and $path -cne "$ExpectedRoot/" -and
                -not $path.StartsWith("$ExpectedRoot/", [StringComparison]::Ordinal)) {
                throw "Archive entry has an unexpected root: $path"
            }
            if ($path.StartsWith('/', [StringComparison]::Ordinal) -or
                $path -match ':' -or $path -match '(^|/)\.\.($|/)') {
                throw "Archive entry is absolute or traversing: $path"
            }
            if ($path.StartsWith("$ExpectedRoot/_internal/", [StringComparison]::Ordinal) -and
                -not $path.EndsWith('/', [StringComparison]::Ordinal)) {
                $internalFileCount++
            }
            $unixType = ($entry.ExternalAttributes -shr 16) -band 0xF000
            if ($unixType -ne 0 -and $unixType -ne 0x8000 -and $unixType -ne 0x4000) {
                throw "Archive entry is a link or unsupported type: $path"
            }
            $dosAttributes = $entry.ExternalAttributes -band 0xFFFF
            if ($dosAttributes -band [int][IO.FileAttributes]::ReparsePoint) {
                throw "Archive entry is a reparse point: $path"
            }
        }
        if ($executableCount -ne 1) {
            throw "Archive must contain exactly one $ExecutableMember entry."
        }
        if ($internalFileCount -lt 1) {
            throw 'Archive is missing the required _internal member tree.'
        }
    }
    finally {
        $archive.Dispose()
    }
}

function Get-ApmReportedVersion {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Executable)

    $banner = & $Executable --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw 'The staged APM executable failed its version postcondition.'
    }
    if ("$banner" -notmatch '([0-9]+\.[0-9]+\.[0-9]+(?:a[0-9]+|b[0-9]+|rc[0-9]+)?)') {
        throw 'The staged APM executable did not report a full version.'
    }
    $Matches[1]
}

function Remove-ValidatedJunction {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param([Parameter(Mandatory)][string]$Path)

    $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    if (-not $item) { return }
    if (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
        -not ($item.Attributes -band [IO.FileAttributes]::Directory)) {
        throw "Refusing to remove a non-junction path: $Path"
    }
    if ($PSCmdlet.ShouldProcess($Path, 'Remove validated junction')) {
        [IO.Directory]::Delete($Path, $false)
    }
}

function Add-PathEntry {
    [CmdletBinding()]
    param(
        [AllowNull()][string]$PathValue,
        [Parameter(Mandatory)][string[]]$Entry
    )

    $parts = @($Entry)
    if (-not [string]::IsNullOrWhiteSpace($PathValue)) {
        foreach ($part in $PathValue.Split([IO.Path]::PathSeparator)) {
            if ([string]::IsNullOrWhiteSpace($part)) { continue }
            if (-not ($parts | Where-Object { $_ -ieq $part })) { $parts += $part }
        }
    }
    $parts -join [IO.Path]::PathSeparator
}

function Get-MutexName {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$InstallRoot)

    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($InstallRoot.ToUpperInvariant())
        $digest = $sha.ComputeHash($bytes)
        $suffix = -join @($digest[0..7] | ForEach-Object { $_.ToString('x2') })
        "Local\AgentEngineeringBaseline.ApmInstall.$suffix"
    }
    finally {
        $sha.Dispose()
    }
}

function New-ApmJunction {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Target
    )

    if ($PSCmdlet.ShouldProcess($Path, "Create junction to $Target")) {
        New-Item -ItemType Junction -Path $Path -Target $Target -ErrorAction Stop | Out-Null
    }
}

function Install-ReviewedBundle {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$SourceBundle,
        [Parameter(Mandatory)]$Metadata,
        [Parameter(Mandatory)][string]$ExecutableMember
    )

    $localAppData = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA }
    else { [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData) }
    if ([string]::IsNullOrWhiteSpace($localAppData)) {
        throw 'LOCALAPPDATA could not be determined.'
    }
    $installRoot = if ($env:APM_INSTALL_DIR) { $env:APM_INSTALL_DIR }
    else { Join-Path $localAppData 'Programs\apm' }
    $installRoot = [IO.Path]::GetFullPath($installRoot)
    $releasesPath = Join-Path $installRoot 'releases'
    $releasePath = Join-Path $releasesPath "v$($Metadata.Pin)"
    $currentPath = Join-Path $installRoot 'current'
    $binPath = Join-Path $installRoot 'bin'
    $shimPath = Join-Path $binPath 'apm.cmd'
    $shimLines = @('@echo off', '"%~dp0..\current\apm.exe" %*')
    $shimContent = ($shimLines -join [Environment]::NewLine) + [Environment]::NewLine
    $stagePath = Join-Path $releasesPath ".stage-$([Guid]::NewGuid().ToString('N'))"
    $backupPath = Join-Path $releasesPath ".rollback-$([Guid]::NewGuid().ToString('N'))"

    Assert-SafeDirectory -Path $installRoot -Label 'APM installation root'
    Assert-SafeDirectory -Path $releasesPath -Label 'APM releases directory'
    Assert-SafeDirectory -Path $binPath -Label 'APM bin directory'
    New-Item -ItemType Directory -Path $releasesPath, $binPath -Force | Out-Null

    $releaseItem = Get-Item -LiteralPath $releasePath -Force -ErrorAction SilentlyContinue
    $hadRelease = $null -ne $releaseItem
    if ($hadRelease) {
        Assert-PlainTree -Path $releasePath -Label 'Existing managed APM release'
        $markerPath = Join-Path $releasePath '.apm-installed'
        if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf) -or
            ((Get-Item -LiteralPath $markerPath -Force).Attributes -band
                [IO.FileAttributes]::ReparsePoint)) {
            throw "Refusing to replace an unowned APM release: $releasePath"
        }
    }

    $currentItem = Get-Item -LiteralPath $currentPath -Force -ErrorAction SilentlyContinue
    $hadCurrent = $null -ne $currentItem
    $oldCurrentTarget = $null
    if ($hadCurrent) {
        if (-not ($currentItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
            -not ($currentItem.Attributes -band [IO.FileAttributes]::Directory)) {
            throw "Refusing to replace non-junction current path: $currentPath"
        }
        $oldCurrentTarget = $currentItem.Target
        if ($oldCurrentTarget -is [array]) { $oldCurrentTarget = $oldCurrentTarget[0] }
        if (-not [IO.Path]::IsPathRooted($oldCurrentTarget)) {
            $oldCurrentTarget = Join-Path $installRoot $oldCurrentTarget
        }
        $oldCurrentTarget = [IO.Path]::GetFullPath($oldCurrentTarget)
        $releasePrefix = [IO.Path]::GetFullPath($releasesPath).TrimEnd('\') + '\'
        if (-not $oldCurrentTarget.StartsWith($releasePrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "The current junction points outside releases: $oldCurrentTarget"
        }
    }

    $shimItem = Get-Item -LiteralPath $shimPath -Force -ErrorAction SilentlyContinue
    $hadShim = $null -ne $shimItem
    $oldShimBytes = $null
    $oldShimAttributes = $null
    if ($hadShim -and -not $shimItem.PSIsContainer) {
        if ([IO.File]::ReadAllText($shimPath) -cne $shimContent) {
            throw "Refusing to overwrite an unrelated APM shim: $shimPath"
        }
        $oldShimBytes = [IO.File]::ReadAllBytes($shimPath)
        $oldShimAttributes = $shimItem.Attributes
    }
    elseif ($hadShim) {
        throw "Refusing to overwrite a non-file APM shim: $shimPath"
    }

    $mutex = New-Object Threading.Mutex($false, (Get-MutexName -InstallRoot $installRoot))
    $mutexAcquired = $false
    $promotionComplete = $false
    $oldProcessPath = $env:PATH
    $oldUserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    try {
        try { $mutexAcquired = $mutex.WaitOne([TimeSpan]::FromMinutes(2)) }
        catch [Threading.AbandonedMutexException] { $mutexAcquired = $true }
        if (-not $mutexAcquired) { throw 'Timed out waiting for the APM installation mutex.' }

        New-Item -ItemType Directory -Path $stagePath | Out-Null
        Get-ChildItem -LiteralPath $SourceBundle -Force | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $stagePath -Recurse -Force
        }
        [IO.File]::WriteAllText(
            (Join-Path $stagePath '.apm-installed'),
            "v$($Metadata.Pin)$([Environment]::NewLine)",
            [Text.Encoding]::ASCII
        )
        Assert-PlainTree -Path $stagePath -Label 'Staged persistent APM bundle'
        Assert-ReviewedFile -Path (Join-Path $stagePath 'apm.exe') -Name $ExecutableMember -Metadata $Metadata

        if ($hadRelease) { Move-Item -LiteralPath $releasePath -Destination $backupPath }
        Move-Item -LiteralPath $stagePath -Destination $releasePath
        if ($hadCurrent) { Remove-ValidatedJunction -Path $currentPath -Confirm:$false }
        New-ApmJunction -Path $currentPath -Target $releasePath -Confirm:$false
        [IO.File]::WriteAllText($shimPath, $shimContent, [Text.Encoding]::ASCII)

        $newPath = Add-PathEntry -PathValue $oldProcessPath -Entry @($currentPath, $binPath)
        $newUserPath = Add-PathEntry -PathValue $oldUserPath -Entry @($currentPath, $binPath)
        $env:PATH = $newPath
        [Environment]::SetEnvironmentVariable('Path', $newUserPath, 'User')
        $promotionComplete = $true
    }
    finally {
        if (-not $promotionComplete -and $mutexAcquired) {
            $env:PATH = $oldProcessPath
            try { [Environment]::SetEnvironmentVariable('Path', $oldUserPath, 'User') }
            catch { Write-Warning -Message "Unable to restore User PATH during rollback: $_" }
            try {
                if (Test-Path -LiteralPath $currentPath) {
                    Remove-ValidatedJunction -Path $currentPath -Confirm:$false
                }
            }
            catch { Write-Warning -Message "Unable to remove the replacement junction during rollback: $_" }
            if (Test-Path -LiteralPath $releasePath) {
                Remove-Item -LiteralPath $releasePath -Recurse -Force -ErrorAction SilentlyContinue
            }
            if (Test-Path -LiteralPath $backupPath) {
                Move-Item -LiteralPath $backupPath -Destination $releasePath -ErrorAction SilentlyContinue
            }
            if ($hadCurrent -and $oldCurrentTarget -and -not (Test-Path -LiteralPath $currentPath)) {
                try {
                    New-ApmJunction -Path $currentPath -Target $oldCurrentTarget -Confirm:$false
                }
                catch { Write-Warning -Message "Unable to restore the prior current junction: $_" }
            }
            try {
                if ($hadShim) {
                    if (Test-Path -LiteralPath $shimPath -PathType Leaf) {
                        [IO.File]::SetAttributes($shimPath, [IO.FileAttributes]::Normal)
                    }
                    [IO.File]::WriteAllBytes($shimPath, $oldShimBytes)
                    [IO.File]::SetAttributes($shimPath, $oldShimAttributes)
                }
                elseif (Test-Path -LiteralPath $shimPath) {
                    Remove-Item -LiteralPath $shimPath -Force
                }
            }
            catch { Write-Warning -Message "Unable to restore the prior APM shim: $_" }
        }
        if (Test-Path -LiteralPath $stagePath) {
            Remove-Item -LiteralPath $stagePath -Recurse -Force -ErrorAction SilentlyContinue
        }
        if ($promotionComplete -and (Test-Path -LiteralPath $backupPath)) {
            Remove-Item -LiteralPath $backupPath -Recurse -Force
        }
        if ($mutexAcquired) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
    }

    $promotedExecutable = Join-Path $currentPath 'apm.exe'
    Assert-ReviewedFile -Path $promotedExecutable -Name $ExecutableMember -Metadata $Metadata
    if ((Get-ApmReportedVersion -Executable $promotedExecutable) -cne $Metadata.Pin) {
        throw "The promoted APM CLI does not report pinned v$($Metadata.Pin)."
    }
    [pscustomobject]@{
        Executable = $promotedExecutable
        Shim       = $shimPath
        Current    = $currentPath
        Bin        = $binPath
    }
}

function Get-ReviewedApm {
    [CmdletBinding()]
    param([Parameter(Mandatory)]$Metadata)

    if ($env:OS -cne 'Windows_NT') {
        throw 'Bootstrap-Baseline.ps1 supports Windows; use bootstrap.sh on Linux or macOS.'
    }
    $architecture = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 }
    else { $env:PROCESSOR_ARCHITECTURE }
    if ($architecture -cne 'AMD64') {
        throw "Unsupported Windows architecture: $architecture"
    }

    $archiveName = 'apm-windows-x86_64.zip'
    $archiveRoot = 'apm-windows-x86_64'
    $executableMember = "$archiveRoot/apm.exe"
    $temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) "apm-bootstrap-$([Guid]::NewGuid().ToString('N'))"
    try {
        New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
        $archivePath = Join-Path $temporaryRoot $archiveName
        $extractPath = Join-Path $temporaryRoot 'extract'
        $uri = Get-ArchiveUri -Pin $Metadata.Pin -ArchiveName $archiveName
        Write-Information -MessageData "Downloading $archiveName" -InformationAction Continue
        Invoke-ArchiveDownload -Uri $uri -OutFile $archivePath
        Assert-ReviewedFile -Path $archivePath -Name $archiveName -Metadata $Metadata
        Assert-SafeZipLayout -ArchivePath $archivePath -ExpectedRoot $archiveRoot -ExecutableMember $executableMember
        Expand-Archive -LiteralPath $archivePath -DestinationPath $extractPath
        $sourceBundle = Join-Path $extractPath $archiveRoot
        Assert-PlainTree -Path $sourceBundle -Label 'Extracted APM bundle'
        if (-not (Test-Path -LiteralPath (Join-Path $sourceBundle '_internal') -PathType Container)) {
            throw 'The extracted APM bundle is missing _internal.'
        }
        $stagedExecutable = Join-Path $sourceBundle 'apm.exe'
        Assert-ReviewedFile -Path $stagedExecutable -Name $executableMember -Metadata $Metadata
        if ((Get-ApmReportedVersion -Executable $stagedExecutable) -cne $Metadata.Pin) {
            throw "The staged APM CLI does not report pinned v$($Metadata.Pin)."
        }
        Install-ReviewedBundle -SourceBundle $sourceBundle -Metadata $Metadata -ExecutableMember $executableMember
    }
    finally {
        if (Test-Path -LiteralPath $temporaryRoot) {
            Remove-Item -LiteralPath $temporaryRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-ReviewedApm {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Executable,
        [Parameter(Mandatory)]$Metadata,
        [Parameter(ValueFromRemainingArguments = $true)][object[]]$ArgumentList
    )

    Assert-ReviewedFile -Path $Executable -Name 'apm-windows-x86_64/apm.exe' -Metadata $Metadata
    & $Executable @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw ('APM command failed with exit code ' + $LASTEXITCODE + ': ' + ($ArgumentList -join ' '))
    }
}

$metadata = Read-ReviewedConfig
Write-Information -MessageData "Reviewed APM CLI version: v$($metadata.Pin)" -InformationAction Continue
if ($WhatIfPreference) {
    Write-Information -MessageData (
        '[WhatIf] Local pin/checksum metadata is valid; no other action was taken.'
    ) -InformationAction Continue
    return
}

if (-not $PSCmdlet.ShouldProcess("APM CLI v$($metadata.Pin)", 'Acquire and promote reviewed bundle')) {
    return
}
$installation = Get-ReviewedApm -Metadata $metadata

$env:PATH = $originalProcessPath
$ambient = Get-Command -Name apm -ErrorAction SilentlyContinue | Select-Object -First 1
$env:PATH = Add-PathEntry -PathValue $originalProcessPath -Entry @($installation.Current, $installation.Bin)
if ($ambient) {
    $ambientPath = if ($ambient.PSObject.Properties['Path']) { $ambient.Path } else { $ambient.Name }
    if ($ambientPath -and $ambientPath -ine $installation.Shim -and
        $ambientPath -ine $installation.Executable) {
        Write-Warning "$ambientPath may still shadow $($installation.Shim) in new shells until PATH is reordered."
    }
}

if (-not $CliOnly) {
    $packageRef = if ($env:BASELINE_PACKAGE_REF) { $env:BASELINE_PACKAGE_REF }
    else { $defaultPackageRef }
    if ($Scope -ceq 'Global') {
        Invoke-ReviewedApm -Executable $installation.Executable -Metadata $metadata install --global --trust-bin $packageRef
        Invoke-ReviewedApm -Executable $installation.Executable -Metadata $metadata compile --global
    }
    else {
        Invoke-ReviewedApm -Executable $installation.Executable -Metadata $metadata install --target 'codex,copilot' --trust-bin $packageRef
        Invoke-ReviewedApm -Executable $installation.Executable -Metadata $metadata compile --target 'codex,copilot'
    }
}
Write-Information -MessageData "Done; reviewed CLI: $($installation.Executable)" -InformationAction Continue
