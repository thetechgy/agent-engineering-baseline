[CmdletBinding()]
param(
    [Parameter()]
    [string]$RepositoryRoot = (Split-Path -Parent $PSScriptRoot),

    [Parameter()]
    [switch]$SkipValidation
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Get-BaselineChangeKind {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$CurrentCliVersion,
        [Parameter(Mandatory)][string]$CandidateCliVersion,
        [Parameter(Mandatory)][string[]]$CurrentCommits,
        [Parameter(Mandatory)][string[]]$CandidateCommits
    )

    $cliChanged = $CurrentCliVersion -cne $CandidateCliVersion
    $sourcesChanged = ($CurrentCommits -join ',') -cne ($CandidateCommits -join ',')
    if ($cliChanged -and $sourcesChanged) { return 'Combined' }
    if ($cliChanged) { return 'ApmOnly' }
    if ($sourcesChanged) { return 'SkillsOnly' }
    return 'NoChange'
}

function Get-Sha256File {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Invoke-GithubRequest {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Uri)

    $headers = @{ Accept = 'application/vnd.github+json'; 'X-GitHub-Api-Version' = '2022-11-28' }
    if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_TOKEN)) {
        $headers.Authorization = "Bearer $($env:GITHUB_TOKEN)"
    }
    return Invoke-RestMethod -Uri $Uri -Headers $headers
}

function Save-RemoteFile {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Uri, [Parameter(Mandatory)][string]$Path)
    Invoke-WebRequest -Uri $Uri -OutFile $Path -UseBasicParsing
}

function Get-LatestPathCommit {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Repository, [Parameter(Mandatory)][string]$Path)
    $escapedPath = [Uri]::EscapeDataString($Path)
    $result = @(Invoke-GithubRequest -Uri "https://api.github.com/repos/$Repository/commits?path=$escapedPath&per_page=1")
    if ($result.Count -ne 1) { throw "Unable to resolve latest commit for $Repository/$Path." }
    return [string]$result[0].sha
}

function Get-UpdatedManifest {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Content,
        [Parameter(Mandatory)][string]$Reference,
        [Parameter(Mandatory)][string]$Commit
    )
    $escaped = [regex]::Escape($Reference)
    $updated = [regex]::Replace($Content, "(?m)^(\s*-\s+$escaped)#\S+\s*$", "`$1#$Commit")
    if ($updated -ceq $Content -and $Content -notmatch "(?m)^\s*-\s+$escaped#$Commit\s*$") {
        throw "Dependency reference was not found in apm.yml: $Reference"
    }
    return $updated
}

function Write-Utf8NoBom {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][string]$Content)
    [IO.File]::WriteAllText($Path, $Content, [Text.UTF8Encoding]::new($false))
}

function Assert-SafeUpstreamEntry {
    [CmdletBinding()]
    param([Parameter(Mandatory)][object]$Entry)

    $segments = $Entry.path -split '[\\/]'
    if ($Entry.repository -notmatch '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$' -or
        [IO.Path]::IsPathRooted($Entry.path) -or $segments -contains '..' -or
        $segments -contains '.' -or $Entry.path -notmatch '^[A-Za-z0-9._/-]+$') {
        throw "Unsafe upstream provenance entry: $($Entry.repository)/$($Entry.path)"
    }
}

if ($MyInvocation.InvocationName -eq '.') { return }

$cliLockPath = Join-Path $RepositoryRoot 'apm-cli.lock.yml'
$provenancePath = Join-Path $RepositoryRoot 'upstream-sources.json'
$manifestPath = Join-Path $RepositoryRoot 'apm.yml'
$currentCli = [regex]::Match(
    (Get-Content -LiteralPath $cliLockPath -Raw), '(?m)^version:\s*([^\r\n]+)'
).Groups[1].Value.Trim()
$provenance = Get-Content -LiteralPath $provenancePath -Raw | ConvertFrom-Json
$currentCommits = @($provenance.dependencies.commit) + @($provenance.sources.commit)
foreach ($entry in @($provenance.dependencies) + @($provenance.sources)) {
    Assert-SafeUpstreamEntry -Entry $entry
}

$release = Invoke-GithubRequest -Uri 'https://api.github.com/repos/microsoft/apm/releases/latest'
if ($release.prerelease -or $release.draft) { throw 'GitHub latest release is not stable.' }
$candidateVersion = ([string]$release.tag_name).TrimStart('v')

foreach ($dependency in $provenance.dependencies) {
    $dependency.commit = Get-LatestPathCommit -Repository $dependency.repository -Path $dependency.path
}
foreach ($source in $provenance.sources) {
    $source.commit = Get-LatestPathCommit -Repository $source.repository -Path $source.path
}
$candidateCommits = @($provenance.dependencies.commit) + @($provenance.sources.commit)
$changeKind = Get-BaselineChangeKind -CurrentCliVersion $currentCli `
    -CandidateCliVersion $candidateVersion -CurrentCommits $currentCommits `
    -CandidateCommits $candidateCommits
Write-Output "Baseline update classification: $changeKind"
if ($changeKind -ceq 'NoChange') { return }

$temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) ("apm-baseline-update-{0}" -f [Guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $temporaryRoot
try {
    $sourceRoot = Join-Path $temporaryRoot 'sources'
    $null = New-Item -ItemType Directory -Path $sourceRoot
    foreach ($source in $provenance.sources) {
        $sourcePath = Join-Path $sourceRoot ($source.path -replace '/', [IO.Path]::DirectorySeparatorChar)
        $null = New-Item -ItemType Directory -Path (Split-Path -Parent $sourcePath) -Force
        $rawUri = "https://raw.githubusercontent.com/$($source.repository)/$($source.commit)/$($source.path)"
        Save-RemoteFile -Uri $rawUri -Path $sourcePath
        $source.source_sha256 = Get-Sha256File -Path $sourcePath
        $contentInfo = Invoke-GithubRequest -Uri (
            "https://api.github.com/repos/$($source.repository)/contents/$($source.path)?ref=$($source.commit)"
        )
        $source.blob = [string]$contentInfo.sha
    }

    $manifestContent = Get-Content -LiteralPath $manifestPath -Raw
    foreach ($dependency in $provenance.dependencies) {
        $manifestContent = Get-UpdatedManifest -Content $manifestContent `
            -Reference $dependency.reference -Commit $dependency.commit
    }
    Write-Utf8NoBom -Path $manifestPath -Content $manifestContent
    Write-Utf8NoBom -Path $provenancePath -Content (($provenance | ConvertTo-Json -Depth 10) + "`n")
    & (Join-Path $PSScriptRoot 'Sync-UpstreamSkills.ps1') -RepositoryRoot $RepositoryRoot -SourceRoot $sourceRoot

    $tag = [string]$release.tag_name
    $tagReference = Invoke-GithubRequest -Uri "https://api.github.com/repos/microsoft/apm/git/ref/tags/$tag"
    if ($tagReference.object.type -ceq 'tag') {
        $releaseCommit = (
            Invoke-GithubRequest -Uri "https://api.github.com/repos/microsoft/apm/git/tags/$($tagReference.object.sha)"
        ).object.sha
    }
    else {
        $releaseCommit = $tagReference.object.sha
    }
    $installerUnix = Join-Path $temporaryRoot 'install.sh'
    $installerWindows = Join-Path $temporaryRoot 'install.ps1'
    Save-RemoteFile -Uri "https://raw.githubusercontent.com/microsoft/apm/$tag/install.sh" -Path $installerUnix
    Save-RemoteFile -Uri "https://raw.githubusercontent.com/microsoft/apm/$tag/install.ps1" -Path $installerWindows

    $artifacts = [ordered]@{}
    foreach ($platform in @('linux-x86_64', 'linux-arm64', 'windows-x86_64')) {
        $extension = if ($platform -eq 'windows-x86_64') { 'zip' } else { 'tar.gz' }
        $name = "apm-$platform.$extension"
        $archive = Join-Path $temporaryRoot $name
        Save-RemoteFile -Uri "https://github.com/microsoft/apm/releases/download/$tag/$name" -Path $archive
        $extract = Join-Path $temporaryRoot "extract-$platform"
        $null = New-Item -ItemType Directory -Path $extract
        if ($extension -eq 'zip') { Expand-Archive -LiteralPath $archive -DestinationPath $extract }
        else { & tar -xzf $archive -C $extract; if ($LASTEXITCODE -ne 0) { throw "Failed to extract $name." } }
        $executableName = if ($platform -eq 'windows-x86_64') { 'apm.exe' } else { 'apm' }
        $executable = Get-ChildItem -LiteralPath $extract -Filter $executableName -File -Recurse | Select-Object -First 1
        if ($null -eq $executable) { throw "Release archive omitted ${executableName}: $name" }
        $artifacts[$platform] = [ordered]@{
            name = $name
            sha256 = Get-Sha256File -Path $archive
            executable_sha256 = Get-Sha256File -Path $executable.FullName
        }
        if ($platform -eq 'linux-x86_64') { $candidateApm = $executable.FullName }
    }

    $lines = @(
        'schema_version: 1'
        "version: $candidateVersion"
        'release:'
        '  repository: microsoft/apm'
        "  tag: $tag"
        "  commit: $releaseCommit"
        "  published_at: '$($release.published_at)'"
        'installers:'
        '  unix:'
        "    url: https://raw.githubusercontent.com/microsoft/apm/$tag/install.sh"
        "    sha256: $(Get-Sha256File -Path $installerUnix)"
        '  windows:'
        "    url: https://raw.githubusercontent.com/microsoft/apm/$tag/install.ps1"
        "    sha256: $(Get-Sha256File -Path $installerWindows)"
        'artifacts:'
    )
    foreach ($platform in $artifacts.Keys) {
        $lines += "  ${platform}:"
        $lines += "    name: $($artifacts[$platform].name)"
        $lines += "    sha256: $($artifacts[$platform].sha256)"
        $lines += "    executable_sha256: $($artifacts[$platform].executable_sha256)"
    }
    Write-Utf8NoBom -Path $cliLockPath -Content (($lines -join "`n") + "`n")

    & $candidateApm install
    if ($LASTEXITCODE -ne 0) { throw 'APM dependency refresh failed.' }
    & $candidateApm compile --target codex,copilot --validate
    if ($LASTEXITCODE -ne 0) { throw 'APM compile validation failed.' }
    & $candidateApm compile --target codex,copilot
    if ($LASTEXITCODE -ne 0) { throw 'APM compilation failed.' }
    if (-not $SkipValidation.IsPresent) {
        & $candidateApm audit --ci
        if ($LASTEXITCODE -ne 0) { throw 'APM audit failed.' }
    }
}
finally {
    if ([IO.Directory]::Exists($temporaryRoot)) { [IO.Directory]::Delete($temporaryRoot, $true) }
}
