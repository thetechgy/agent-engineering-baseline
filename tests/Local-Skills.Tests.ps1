BeforeAll {
    $script:RepositoryRoot = Split-Path -Parent $PSScriptRoot
    $script:ApmSource = Join-Path $script:RepositoryRoot '.apm/skills'
    $script:DeployedSkills = Join-Path $script:RepositoryRoot '.agents/skills'
    $script:Manifest = Get-Content -LiteralPath (
        Join-Path $script:RepositoryRoot 'apm.yml'
    ) -Raw
}

Describe 'Local skill APM integration' {
    It 'explicitly enumerates every local skill source directory' {
        # Read the top-level `includes` sequence without depending on exact
        # indentation (items may start at column 0), quoting, or trailing-slash style.
        $includes = New-Object System.Collections.Generic.List[string]
        $inIncludes = $false
        foreach ($line in ($script:Manifest -split '\r?\n')) {
            if ($line -match '^includes:\s*(#.*)?$') { $inIncludes = $true; continue }
            if (-not $inIncludes) { continue }
            if ($line -match '^\s*$' -or $line -match '^\s*#') { continue }
            if ($line -notmatch '^\s' -and $line -notmatch '^-\s') { break }
            if ($line -match '^\s*-\s*["'']?([^"''#\s]+)["'']?\s*(#.*)?$') { $includes.Add($Matches[1]) }
        }
        $includes.Count | Should-BeGreaterThan 0

        $includedSkills = @(
            $includes |
                Where-Object { $_ -match '^\.apm/skills/[^/]+/?$' } |
                ForEach-Object { $_.TrimEnd('/') + '/' }
        ) | Sort-Object
        $sourceSkills = @(
            Get-ChildItem -LiteralPath $script:ApmSource -Directory |
                ForEach-Object { ".apm/skills/$($_.Name)/" }
        ) | Sort-Object

        Should-BeCollection -Actual $includedSkills -Expected $sourceSkills
    }

    It 'deploys every Podman skill file byte-for-byte' {
        $sourceRoot = Join-Path $script:ApmSource 'podman'
        $targetRoot = Join-Path $script:DeployedSkills 'podman'
        Test-Path -LiteralPath (Join-Path $targetRoot 'SKILL.md') -PathType Leaf |
            Should-BeTrue

        $sourceFiles = @(
            Get-ChildItem -LiteralPath $sourceRoot -File -Recurse |
                ForEach-Object {
                    $_.FullName.Substring($sourceRoot.Length + 1).Replace('\', '/')
                }
        ) | Sort-Object
        $targetFiles = @(
            Get-ChildItem -LiteralPath $targetRoot -File -Recurse |
                ForEach-Object {
                    $_.FullName.Substring($targetRoot.Length + 1).Replace('\', '/')
                }
        ) | Sort-Object
        Should-BeCollection -Actual $targetFiles -Expected $sourceFiles

        foreach ($relativePath in $sourceFiles) {
            $sourceHash = (Get-FileHash -LiteralPath (
                Join-Path $sourceRoot $relativePath
            ) -Algorithm SHA256).Hash
            $targetHash = (Get-FileHash -LiteralPath (
                Join-Path $targetRoot $relativePath
            ) -Algorithm SHA256).Hash
            $targetHash | Should-Be $sourceHash
        }
    }
}
