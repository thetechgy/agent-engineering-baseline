[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter()]
    [string]$RepositoryRoot = (Split-Path -Parent $PSScriptRoot),

    [Parameter()]
    [string]$SourceRoot,

    [Parameter()]
    [switch]$Check
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Assert-SafeRelativePath {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][string]$Description)

    $segments = $Path -split '[\\/]'
    if ([IO.Path]::IsPathRooted($Path) -or $segments -contains '..' -or
        $segments -contains '.' -or $Path -notmatch '^[A-Za-z0-9._/-]+$') {
        throw "$Description is not a safe relative path: $Path"
    }
}

function Get-Sha256 {
    [CmdletBinding()]
    param([Parameter(Mandatory)][byte[]]$Bytes)

    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($algorithm.ComputeHash($Bytes))).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $algorithm.Dispose()
    }
}

function Get-GitBlobHash {
    [CmdletBinding()]
    param([Parameter(Mandatory)][byte[]]$Bytes)

    $header = [Text.Encoding]::ASCII.GetBytes("blob $($Bytes.Length)`0")
    $payload = [byte[]]::new($header.Length + $Bytes.Length)
    [Array]::Copy($header, 0, $payload, 0, $header.Length)
    [Array]::Copy($Bytes, 0, $payload, $header.Length, $Bytes.Length)
    $algorithm = [System.Security.Cryptography.SHA1]::Create()
    try {
        return ([BitConverter]::ToString($algorithm.ComputeHash($payload))).Replace('-', '').ToLowerInvariant()
    }
    finally { $algorithm.Dispose() }
}

function ConvertTo-SkillContent {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][byte[]]$SourceBytes,
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Description
    )

    $text = [Text.Encoding]::UTF8.GetString($SourceBytes)
    if (-not $text.StartsWith("---`n")) {
        throw 'Upstream instruction does not start with LF-delimited YAML frontmatter.'
    }
    $frontmatterEnd = $text.IndexOf("`n---`n", 4, [StringComparison]::Ordinal)
    if ($frontmatterEnd -lt 0) {
        throw 'Upstream instruction frontmatter is not terminated.'
    }
    $body = $text.Substring($frontmatterEnd + 5)
    $escapedDescription = $Description.Replace("'", "''")
    $skill = "---`nname: $Name`ndescription: '$escapedDescription'`n---`n$body"
    return [Text.UTF8Encoding]::new($false).GetBytes($skill)
}

$manifestPath = Join-Path $RepositoryRoot 'upstream-sources.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
foreach ($source in $manifest.sources) {
    if ($source.repository -notmatch '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$' -or
        $source.commit -notmatch '^[0-9a-f]{40}$' -or
        $source.blob -notmatch '^[0-9a-f]{40}$' -or
        $source.source_sha256 -notmatch '^[0-9a-f]{64}$') {
        throw "Invalid pinned provenance for '$($source.skill)'."
    }
    Assert-SafeRelativePath -Path $source.path -Description 'Upstream source path'
    Assert-SafeRelativePath -Path $source.output -Description 'Mirrored output path'
    $sourceBytes = if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
        $uri = 'https://raw.githubusercontent.com/{0}/{1}/{2}' -f `
            $source.repository, $source.commit, $source.path
        $client = [Net.WebClient]::new()
        try {
            $client.DownloadData($uri)
        }
        finally {
            $client.Dispose()
        }
    }
    else {
        $sourcePath = Join-Path $SourceRoot ($source.path -replace '/', [IO.Path]::DirectorySeparatorChar)
        [IO.File]::ReadAllBytes($sourcePath)
    }

    $sourceHash = Get-Sha256 -Bytes $sourceBytes
    if ($sourceHash -cne $source.source_sha256) {
        throw "Source hash mismatch for '$($source.skill)': expected $($source.source_sha256), got $sourceHash."
    }
    $blobHash = Get-GitBlobHash -Bytes $sourceBytes
    if ($blobHash -cne $source.blob) {
        throw "Git blob mismatch for '$($source.skill)': expected $($source.blob), got $blobHash."
    }

    $expectedBytes = ConvertTo-SkillContent -SourceBytes $sourceBytes `
        -Name $source.name -Description $source.description
    $outputPath = Join-Path $RepositoryRoot $source.output
    if ($Check.IsPresent) {
        if (-not [IO.File]::Exists($outputPath)) {
            throw "Mirrored skill is missing: $outputPath"
        }
        $actualBytes = [IO.File]::ReadAllBytes($outputPath)
        if ((Get-Sha256 -Bytes $actualBytes) -cne (Get-Sha256 -Bytes $expectedBytes)) {
            throw "Mirrored skill drift detected: $($source.output)"
        }
    }
    elseif ($PSCmdlet.ShouldProcess($outputPath, 'Regenerate mirrored upstream skill')) {
        $parent = Split-Path -Parent $outputPath
        $null = New-Item -ItemType Directory -Path $parent -Force
        [IO.File]::WriteAllBytes($outputPath, $expectedBytes)
    }
}

if ($Check.IsPresent) {
    Write-Output 'All mirrored upstream skills match their pinned sources.'
}
