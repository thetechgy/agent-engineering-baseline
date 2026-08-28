<#
.SYNOPSIS
Verifies that every file deployed by APM remains reviewable.

.DESCRIPTION
Reads file deployments from apm.lock.yaml. Each deployed file must either be
tracked by Git or be an ignored generated artifact explicitly approved in
.apm-approved-artifacts. Approved compiled programs must also have a matching
SHA256 fingerprint in .apm-program-checksums.

.PARAMETER RepositoryRoot
Repository whose APM lockfile and review policy should be validated.

.EXAMPLE
./scripts/Test-ApmReviewBoundary.ps1

.OUTPUTS
System.String. Writes a summary after all checks pass.
#>
[CmdletBinding()]
param(
    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$RepositoryRoot = (Split-Path -Parent $PSScriptRoot)
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Assert-RepositoryRelativePath {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$Path,

        [Parameter(Mandatory)]
        [string]$Source
    )

    if ($Path -notmatch '^[A-Za-z0-9._/-]+$' -or
        $Path.StartsWith('/') -or
        $Path -match '(^|/)\.\.(/|$)') {
        throw "$Source contains an unsafe or unsupported repository path: '$Path'."
    }
}

function Get-ApmDeployment {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$LockfilePath
    )

    $deploymentsFound = $false
    $currentItemFound = $false
    $currentPath = $null
    $currentHash = $null
    $currentHashFound = $false
    $results = @()

    foreach ($line in [System.IO.File]::ReadAllLines($LockfilePath)) {
        if (-not $deploymentsFound) {
            if ($line -ceq 'deployments:') { $deploymentsFound = $true }
            continue
        }

        if ($line -match '^[A-Za-z_][A-Za-z0-9_]*:') { break }

        if ($line -match '^- kind:') {
            if ($currentItemFound) {
                if ($null -eq $currentPath -or -not $currentHashFound) {
                    throw "An APM deployment in '$LockfilePath' is missing its value or content_hash."
                }
                $results += [PSCustomObject]@{ Path = $currentPath; Hash = $currentHash }
            }
            $currentItemFound = $true
            $currentPath = $null
            $currentHash = $null
            $currentHashFound = $false
            continue
        }

        if ($line -match '^  value: (\S+)$') {
            $currentPath = $Matches[1]
            Assert-RepositoryRelativePath -Path $currentPath -Source $LockfilePath
            continue
        }

        if ($line -match '^  content_hash: (sha256:[0-9a-f]{64}|null)$') {
            $currentHashFound = $true
            if ($Matches[1] -cne 'null') { $currentHash = $Matches[1].Substring(7) }
        }
    }

    if ($currentItemFound) {
        if ($null -eq $currentPath -or -not $currentHashFound) {
            throw "An APM deployment in '$LockfilePath' is missing its value or content_hash."
        }
        $results += [PSCustomObject]@{ Path = $currentPath; Hash = $currentHash }
    }
    if (-not $deploymentsFound -or $results.Count -eq 0) {
        throw "No file deployments were found in '$LockfilePath'."
    }

    $duplicatePaths = @($results | Group-Object -Property Path -CaseSensitive |
            Where-Object Count -GT 1)
    if ($duplicatePaths.Count -gt 0) {
        throw "The APM lockfile contains duplicate file deployment '$($duplicatePaths[0].Name)'."
    }

    return $results
}

function Get-ApprovedArtifact {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$ManifestPath
    )

    $results = @()
    $lineNumber = 0
    foreach ($line in [System.IO.File]::ReadAllLines($ManifestPath)) {
        $lineNumber++
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith('#')) { continue }
        if ($line -notmatch '^(data|program)\t([^\t]+)$') {
            throw "$ManifestPath`:$lineNumber must use '<data|program><TAB><path>'."
        }
        $artifactPath = $Matches[2]
        Assert-RepositoryRelativePath -Path $artifactPath -Source "$ManifestPath`:$lineNumber"
        $results += [PSCustomObject]@{ Kind = $Matches[1]; Path = $artifactPath }
    }

    $duplicatePaths = @($results | Group-Object -Property Path -CaseSensitive |
            Where-Object Count -GT 1)
    if ($duplicatePaths.Count -gt 0) {
        throw "$ManifestPath contains duplicate artifact '$($duplicatePaths[0].Name)'."
    }
    return $results
}

function Get-ProgramChecksum {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$ManifestPath
    )

    $results = @()
    $lineNumber = 0
    foreach ($line in [System.IO.File]::ReadAllLines($ManifestPath)) {
        $lineNumber++
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith('#')) { continue }
        if ($line -notmatch '^([0-9a-f]{64})  (\S+)$') {
            throw "$ManifestPath`:$lineNumber must use '<lowercase SHA256><two spaces><path>'."
        }
        $programPath = $Matches[2]
        Assert-RepositoryRelativePath -Path $programPath -Source "$ManifestPath`:$lineNumber"
        $results += [PSCustomObject]@{ Hash = $Matches[1]; Path = $programPath }
    }

    $duplicatePaths = @($results | Group-Object -Property Path -CaseSensitive |
            Where-Object Count -GT 1)
    if ($duplicatePaths.Count -gt 0) {
        throw "$ManifestPath contains duplicate program '$($duplicatePaths[0].Name)'."
    }
    return $results
}

function Test-GitPathTracked {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$Root,

        [Parameter(Mandatory)]
        [string]$Path
    )

    $trackedPaths = @()
    $gitExitCode = $null
    $savedErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $trackedPaths = @(& git -C $Root ls-files -- $Path 2>$null)
        $gitExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }

    if ($null -eq $gitExitCode -or $gitExitCode -ne 0) {
        throw "git ls-files failed for '$Path' with exit code '$gitExitCode'."
    }
    return @($trackedPaths | Where-Object { $_ -ceq $Path }).Count -eq 1
}

function Test-GitPathIgnored {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$Root,

        [Parameter(Mandatory)]
        [string]$Path
    )

    $gitExitCode = $null
    $savedErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $null = & git -C $Root check-ignore --quiet -- $Path 2>$null
        $gitExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }

    if ($gitExitCode -eq 0) { return $true }
    if ($gitExitCode -eq 1) { return $false }
    throw "git check-ignore failed for '$Path' with exit code '$gitExitCode'."
}

$resolvedRoot = (Resolve-Path -LiteralPath $RepositoryRoot).Path
$lockfilePath = Join-Path $resolvedRoot 'apm.lock.yaml'
$artifactManifestPath = Join-Path $resolvedRoot '.apm-approved-artifacts'
$programManifestPath = Join-Path $resolvedRoot '.apm-program-checksums'

foreach ($requiredPath in @($lockfilePath, $artifactManifestPath, $programManifestPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required APM review-boundary file is missing: '$requiredPath'."
    }
}

$allDeployments = @(Get-ApmDeployment -LockfilePath $lockfilePath)
$deployments = @($allDeployments | Where-Object { $null -ne $_.Hash })
if ($deployments.Count -eq 0) { throw "No file deployments were found in '$lockfilePath'." }
$approvedArtifacts = @(Get-ApprovedArtifact -ManifestPath $artifactManifestPath)
$programChecksums = @(Get-ProgramChecksum -ManifestPath $programManifestPath)

foreach ($directory in @($allDeployments | Where-Object { $null -eq $_.Hash })) {
    if (-not (Test-Path -LiteralPath (Join-Path $resolvedRoot $directory.Path) -PathType Container)) {
        throw "APM directory deployment '$($directory.Path)' is not a directory."
    }
}

foreach ($artifact in $approvedArtifacts) {
    $deployment = @($deployments | Where-Object Path -CEQ $artifact.Path)
    if ($deployment.Count -ne 1) {
        throw "Approved artifact '$($artifact.Path)' is not an APM file deployment."
    }
    if (Test-GitPathTracked -Root $resolvedRoot -Path $artifact.Path) {
        throw "Approved artifact '$($artifact.Path)' is tracked; remove it from the exception list."
    }
    if (-not (Test-GitPathIgnored -Root $resolvedRoot -Path $artifact.Path)) {
        throw "Approved artifact '$($artifact.Path)' must be explicitly ignored."
    }
}

foreach ($deployment in $deployments) {
    $fullPath = Join-Path $resolvedRoot $deployment.Path
    if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
        throw "APM deployed file '$($deployment.Path)' is missing."
    }
    if (Test-GitPathTracked -Root $resolvedRoot -Path $deployment.Path) { continue }
    if (@($approvedArtifacts | Where-Object Path -CEQ $deployment.Path).Count -ne 1) {
        throw "APM deployed file '$($deployment.Path)' is neither tracked nor an approved artifact."
    }
}

$approvedPrograms = @($approvedArtifacts | Where-Object Kind -CEQ 'program')
foreach ($checksum in $programChecksums) {
    if (@($approvedPrograms | Where-Object Path -CEQ $checksum.Path).Count -ne 1) {
        throw "Program checksum '$($checksum.Path)' does not name an approved program artifact."
    }
}

foreach ($program in $approvedPrograms) {
    $checksum = @($programChecksums | Where-Object Path -CEQ $program.Path)
    if ($checksum.Count -ne 1) {
        throw "Approved program '$($program.Path)' must have exactly one SHA256 fingerprint."
    }
    $deployment = @($deployments | Where-Object Path -CEQ $program.Path)[0]
    if ($deployment.Hash -cne $checksum[0].Hash) {
        throw "Approved program '$($program.Path)' fingerprint differs from apm.lock.yaml."
    }
    $actualHash = (Get-FileHash -LiteralPath (Join-Path $resolvedRoot $program.Path) `
            -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -cne $checksum[0].Hash) {
        throw "Approved program '$($program.Path)' does not match its reviewed SHA256 fingerprint."
    }
}

$deployedFileNoun = if ($deployments.Count -eq 1) { 'file' } else { 'files' }
$approvedArtifactNoun = if ($approvedArtifacts.Count -eq 1) { 'artifact' } else { 'artifacts' }
$pinnedProgramNoun = if ($approvedPrograms.Count -eq 1) { 'program' } else { 'programs' }

Write-Output (
    'APM review boundary passed: {0} deployed {1}, {2} approved {3}, {4} pinned {5}.' -f `
        $deployments.Count, $deployedFileNoun,
        $approvedArtifacts.Count, $approvedArtifactNoun,
        $approvedPrograms.Count, $pinnedProgramNoun
)
