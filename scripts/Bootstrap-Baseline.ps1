<#
.SYNOPSIS
Acquires the reviewed APM CLI bundle and deploys the baseline with native APM.

.DESCRIPTION
Downloads a fresh pinned Windows x86_64 release archive, verifies the tracked
archive and executable digests, rejects unsafe ZIP entries, executes only the
staged absolute executable, installs the complete onedir bundle as a new
generation under releases\, and activates it by atomically replacing the
bin\apm.cmd shim. Native APM then owns package installation, executable
trust, compilation, update, audit, and packing.

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
    $pendingDirectories = New-Object System.Collections.Stack
    $pendingDirectories.Push($Path)
    while ($pendingDirectories.Count -gt 0) {
        $directory = [string]$pendingDirectories.Pop()
        foreach ($item in @(Get-ChildItem -LiteralPath $directory -Force -ErrorAction Stop)) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "$Label contains a reparse point: $($item.FullName)"
            }
            if ($item.PSIsContainer) {
                $pendingDirectories.Push($item.FullName)
            }
            elseif (-not ($item -is [IO.FileInfo])) {
                throw "$Label contains an unsupported entry type: $($item.FullName)"
            }
        }
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
        throw 'The APM executable failed its version postcondition.'
    }
    if ("$banner" -notmatch '([0-9]+\.[0-9]+\.[0-9]+(?:a[0-9]+|b[0-9]+|rc[0-9]+)?)') {
        throw 'The APM executable did not report a full version.'
    }
    $Matches[1]
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


function Test-LegacyCurrentEntry {
    # Test-Path follows reparse points and reports a dangling junction as absent;
    # Get-Item -Force sees the link itself so its target is still validated.
    [CmdletBinding()]
    [OutputType([bool])]
    param([Parameter(Mandatory)][string]$Path)
    return $null -ne (Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue)
}

function Test-OwnedBundle {
    # True when the bundle directory carries the installer's ownership marker as
    # a regular file; a missing marker or a reparse point means the bundle is
    # not this installer's to replace or remove.
    [CmdletBinding()]
    [OutputType([bool])]
    param([Parameter(Mandatory)][string]$Path)
    $marker = Get-Item -LiteralPath (Join-Path $Path '.apm-installed') -Force -ErrorAction SilentlyContinue
    return [bool]($marker -and -not $marker.PSIsContainer -and
        -not ($marker.Attributes -band [IO.FileAttributes]::ReparsePoint))
}

function Test-PlainReleasePath {
    # True when every existing component of a release directory below releases,
    # and the executable the shim runs, is a plain entry, so the path cannot
    # resolve outside the tree through a nested reparse point. A missing
    # component ends the walk: a dangling reference inside releases stays
    # repairable.
    [CmdletBinding()]
    [OutputType([bool])]
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$ReleasesPath
    )
    $prefix = [IO.Path]::GetFullPath($ReleasesPath).TrimEnd('\') + '\'
    $target = [IO.Path]::GetFullPath($Path)
    if (-not $target.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { return $false }
    $current = $prefix.TrimEnd('\')
    $components = @($target.Substring($prefix.Length) -split '\\' | Where-Object { $_ }) + @('apm.exe')
    foreach ($component in $components) {
        $current = Join-Path $current $component
        $entry = Get-Item -LiteralPath $current -Force -ErrorAction SilentlyContinue
        if (-not $entry) { return $true }
        if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { return $false }
        if ($component -eq 'apm.exe') { return -not $entry.PSIsContainer }
        if (-not $entry.PSIsContainer) { return $false }
    }
    return $true
}

function Get-LegacyCurrentTarget {
    # The normalized target of the legacy current junction when it is a directory
    # junction whose reparse-free target lies inside releases, the sole form the
    # previous bootstrap layout ever created; otherwise $null.
    [CmdletBinding()]
    [OutputType([string])]
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$ReleasesPath
    )
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    if (-not $item) { return $null }
    if (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { return $null }
    if (-not ($item.Attributes -band [IO.FileAttributes]::Directory)) { return $null }
    $target = [string](@($item.Target) | Select-Object -First 1)
    if (-not $target) { return $null }
    $target = $target -replace '^\\\\\?\\', '' -replace '^\\\?\?\\', ''
    $target = [IO.Path]::GetFullPath([string]$target)
    if (Test-PlainReleasePath -Path $target -ReleasesPath $ReleasesPath) { return $target }
    return $null
}

function Test-LegacyCurrentJunction {
    [CmdletBinding()]
    [OutputType([bool])]
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$ReleasesPath
    )
    return $null -ne (Get-LegacyCurrentTarget -Path $Path -ReleasesPath $ReleasesPath)
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
    $defaultInstallRoot = Join-Path $localAppData 'Programs\apm'
    if ($env:APM_INSTALL_DIR) {
        $rawBinPath = $env:APM_INSTALL_DIR.Trim().TrimEnd('\', '/')
        if ([string]::IsNullOrWhiteSpace($rawBinPath)) {
            throw 'APM_INSTALL_DIR must identify the APM bin directory.'
        }
        $binPath = [IO.Path]::GetFullPath($rawBinPath)
        $installRoot = Split-Path -Parent $binPath
        if ([string]::IsNullOrWhiteSpace($installRoot)) { $installRoot = $binPath }
    }
    else {
        $installRoot = [IO.Path]::GetFullPath($defaultInstallRoot)
        $binPath = Join-Path $installRoot 'bin'
    }
    $releasesPath = Join-Path $installRoot 'releases'
    # Each run installs a fresh generation and activates it by atomically
    # replacing the shim, so the prior generation stays usable until that
    # single step and no backup or rollback is needed.
    $generation = "v$($Metadata.Pin)-$([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))-$([Guid]::NewGuid().ToString('N').Substring(0, 8))"
    $stagePath = Join-Path $releasesPath ".stage-$generation"
    $releasePath = Join-Path $releasesPath $generation
    $shimPath = Join-Path $binPath 'apm.cmd'
    $shimStagePath = Join-Path $binPath ".apm-$generation.cmd"
    $shimLines = @('@echo off', "`"%~dp0..\releases\$generation\apm.exe`" %*")
    $shimContent = ($shimLines -join [Environment]::NewLine) + [Environment]::NewLine
    # Only the legacy junction or a generation named by this installer's grammar is
    # managed; a traversal component such as `..` could point anywhere.
    $generationPattern = 'v\d+\.\d+\.\d+(?:a\d+|b\d+|rc\d+)?-\d{8}T\d{6}Z-[0-9a-f]{8}'
    $managedShimPattern = "^@echo off\r?\n`"%~dp0\.\.\\(current|releases\\$generationPattern)\\apm\.exe`" %\*\r?\n`$"

    $legacyCurrentPath = Join-Path $installRoot 'current'

    $mutex = New-Object Threading.Mutex($false, (Get-MutexName -InstallRoot $installRoot))
    $mutexAcquired = $false
    $activated = $false
    $handedOff = $false
    # Paths become cleanup-owned only once this run has created them.
    $ownedPaths = New-Object Collections.Generic.List[string]
    try {
        # Never wait or steal: a second bootstrap fails immediately with a diagnostic.
        try { $mutexAcquired = $mutex.WaitOne(0) }
        catch [Threading.AbandonedMutexException] { $mutexAcquired = $true }
        if (-not $mutexAcquired) {
            throw "Another bootstrap is installing into $installRoot; wait for it to finish and retry."
        }

        Assert-SafeDirectory -Path $installRoot -Label 'APM installation root'
        Assert-SafeDirectory -Path $releasesPath -Label 'APM releases directory'
        Assert-SafeDirectory -Path $binPath -Label 'APM bin directory'
        New-Item -ItemType Directory -Path $releasesPath, $binPath -Force | Out-Null

        $shimItem = Get-Item -LiteralPath $shimPath -Force -ErrorAction SilentlyContinue
        if ($shimItem) {
            if ($shimItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Refusing to overwrite a reparse-point APM shim: $shimPath"
            }
            if ($shimItem.PSIsContainer) {
                throw "Refusing to overwrite a non-file APM shim: $shimPath"
            }
            $shimMatch = [regex]::Match([IO.File]::ReadAllText($shimPath), $managedShimPattern)
            if (-not $shimMatch.Success) {
                throw "Refusing to overwrite an unrelated APM shim: $shimPath"
            }
            # The shim is replaced only when the release it runs is missing
            # (repairable) or carries this installer's ownership marker.
            $shimRelease = $null
            if ($shimMatch.Groups[1].Value -eq 'current') {
                if (Test-LegacyCurrentEntry -Path $legacyCurrentPath) {
                    $shimRelease = Get-LegacyCurrentTarget -Path $legacyCurrentPath -ReleasesPath $releasesPath
                    if (-not $shimRelease) {
                        throw "Refusing to overwrite an APM shim whose legacy current link is not a junction into ${releasesPath}: $shimPath"
                    }
                }
            }
            else {
                $shimRelease = Join-Path $installRoot $shimMatch.Groups[1].Value
                if (-not (Test-PlainReleasePath -Path $shimRelease -ReleasesPath $releasesPath)) {
                    throw "Refusing to overwrite an APM shim whose release resolves through a reparse point: $shimPath -> $shimRelease"
                }
            }
            if ($shimRelease -and (Get-Item -LiteralPath (Join-Path $shimRelease 'apm.exe') -Force -ErrorAction SilentlyContinue) -and
                -not (Test-OwnedBundle -Path $shimRelease)) {
                throw "Refusing to overwrite an APM shim that runs an unowned release: $shimPath -> $shimRelease"
            }
        }
        foreach ($path in @($stagePath, $releasePath, $shimStagePath)) {
            # Get-Item -Force also sees a dangling reparse point, which Test-Path
            # would report as absent and a later write could follow.
            if (Get-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue) {
                throw "An APM release generation path already exists: $path"
            }
        }

        # Each path becomes cleanup-owned only once this run has created it, so a
        # path that appeared in between and made the create fail is never removed.
        New-Item -ItemType Directory -Path $stagePath | Out-Null
        $ownedPaths.Add($stagePath)
        # The ownership marker is written first so every directory this installer
        # creates under releases is recognizable to later cleanup.
        [IO.File]::WriteAllText(
            (Join-Path $stagePath '.apm-installed'),
            "v$($Metadata.Pin)$([Environment]::NewLine)",
            [Text.Encoding]::ASCII
        )
        Get-ChildItem -LiteralPath $SourceBundle -Force | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $stagePath -Recurse -Force
        }
        Assert-PlainTree -Path $stagePath -Label 'Staged persistent APM bundle'
        # Verify the bytes that will be activated, from the tree they will keep.
        $stagedExecutable = Join-Path $stagePath 'apm.exe'
        Assert-ReviewedFile -Path $stagedExecutable -Name $ExecutableMember -Metadata $Metadata
        if ((Get-ApmReportedVersion -Executable $stagedExecutable) -cne $Metadata.Pin) {
            throw "The installed APM CLI does not report pinned v$($Metadata.Pin)."
        }

        Move-Item -LiteralPath $stagePath -Destination $releasePath
        $ownedPaths.Add($releasePath)
        $promotedExecutable = Join-Path $releasePath 'apm.exe'
        [IO.File]::WriteAllText($shimStagePath, $shimContent, [Text.Encoding]::ASCII)
        $ownedPaths.Add($shimStagePath)
        if (Test-Path -LiteralPath $shimPath) {
            # NTFS replaces the destination atomically; the shim never disappears.
            # NullString keeps the no-backup argument null under Windows PowerShell 5.1,
            # which otherwise binds $null to an empty (illegal) path.
            [IO.File]::Replace($shimStagePath, $shimPath, [NullString]::Value)
        }
        else {
            [IO.File]::Move($shimStagePath, $shimPath)
        }
        $activated = $true

        # Best-effort cleanup of superseded generations and the legacy current junction.
        # Only installer-owned entries are removed: plain directories (abandoned stages
        # or generations) carrying the ownership marker this installer writes first;
        # anything else is left with a warning. Only plain trees are removed, so a
        # reparse point can never redirect deletion.
        foreach ($entry in @(Get-ChildItem -LiteralPath $releasesPath -Force)) {
            if ($entry.FullName -ieq $releasePath) { continue }
            $owned = $entry.PSIsContainer -and -not ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -and
                (Test-OwnedBundle -Path $entry.FullName)
            if (-not $owned) {
                Write-Warning -Message "Leaving an unrecognized entry in the APM releases directory: $($entry.FullName)"
                continue
            }
            try {
                Assert-PlainTree -Path $entry.FullName -Label 'Superseded APM release'
                Remove-Item -LiteralPath $entry.FullName -Recurse -Force -ErrorAction Stop
            }
            catch { Write-Warning -Message "Unable to remove a superseded APM release at $($entry.FullName): $_" }
        }
        if (Test-LegacyCurrentEntry -Path $legacyCurrentPath) {
            if (Test-LegacyCurrentJunction -Path $legacyCurrentPath -ReleasesPath $releasesPath) {
                # Deleting a junction non-recursively removes only the link itself.
                try { [IO.Directory]::Delete($legacyCurrentPath, $false) }
                catch { Write-Warning -Message "Unable to remove the legacy APM current junction at ${legacyCurrentPath}: $_" }
            }
            else {
                Write-Warning -Message "Leaving an unrecognized entry beside the APM releases directory: $legacyCurrentPath"
            }
        }

        $env:PATH = Add-PathEntry -PathValue $env:PATH -Entry @($binPath)
        try {
            $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
            [Environment]::SetEnvironmentVariable('Path', (Add-PathEntry -PathValue $userPath -Entry @($binPath)), 'User')
        }
        catch { Write-Warning -Message "The reviewed CLI is installed, but the user PATH could not be updated; add $binPath manually: $_" }
        $handedOff = $true
    }
    finally {
        # A generation the shim already references is live, even if the run was
        # interrupted between the atomic replacement and the flag assignment.
        if (-not $activated -and (Test-Path -LiteralPath $shimPath)) {
            try { $activated = [IO.File]::ReadAllText($shimPath) -ceq $shimContent } catch { $activated = $false }
        }
        if (-not $activated) {
            # Like the post-activation cleanup, never delete through a reparse point.
            foreach ($path in $ownedPaths) {
                $entry = Get-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
                if (-not $entry) { continue }
                try {
                    if ($entry.PSIsContainer) { Assert-PlainTree -Path $path -Label 'Abandoned APM stage' }
                    elseif ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'it is a reparse point' }
                    Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction Stop
                }
                catch { Write-Warning -Message "Leaving an abandoned APM stage at ${path}: $_" }
            }
        }
        # On success the caller holds the lock across the native handoff so a
        # concurrent bootstrap cannot supersede and remove this generation while
        # APM is still running from it.
        if (-not $handedOff) {
            if ($mutexAcquired) { $mutex.ReleaseMutex() }
            $mutex.Dispose()
        }
    }

    [pscustomobject]@{
        Executable = $promotedExecutable
        Shim       = $shimPath
        Bin        = $binPath
        Lock       = $mutex
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
try {
    $env:PATH = $originalProcessPath
    $ambient = Get-Command -Name apm -ErrorAction SilentlyContinue | Select-Object -First 1
    $env:PATH = Add-PathEntry -PathValue $originalProcessPath -Entry @($installation.Bin)
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
        if ($Scope -eq 'Global') {
            Invoke-ReviewedApm -Executable $installation.Executable -Metadata $metadata install --global --target 'codex,copilot' --trust-bin --trust-transitive-mcp $packageRef
            Invoke-ReviewedApm -Executable $installation.Executable -Metadata $metadata update --global --yes --target 'codex,copilot'
            Invoke-ReviewedApm -Executable $installation.Executable -Metadata $metadata compile --global
        }
        else {
            Invoke-ReviewedApm -Executable $installation.Executable -Metadata $metadata install --target 'codex,copilot' --trust-bin --trust-transitive-mcp $packageRef
            Invoke-ReviewedApm -Executable $installation.Executable -Metadata $metadata update --yes --target 'codex,copilot'
            Invoke-ReviewedApm -Executable $installation.Executable -Metadata $metadata compile --target 'codex,copilot'
        }
    }
    Write-Information -MessageData "Done; reviewed CLI: $($installation.Shim) -> $($installation.Executable)" -InformationAction Continue
}
finally {
    $installation.Lock.ReleaseMutex()
    $installation.Lock.Dispose()
}
