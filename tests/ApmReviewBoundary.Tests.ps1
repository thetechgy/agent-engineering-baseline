[Diagnostics.CodeAnalysis.SuppressMessageAttribute(
    'PSUseShouldProcessForStateChangingFunctions',
    '',
    Justification = 'This helper mutates only isolated Pester TestDrive repositories.',
    Scope = 'Function',
    Target = 'New-ReviewBoundaryFixture'
)]
param()

BeforeAll {
    $script:RepositoryRoot = Split-Path -Parent $PSScriptRoot
    $script:ValidationPath = Join-Path $script:RepositoryRoot 'scripts/Test-ApmReviewBoundary.ps1'

    function New-ReviewBoundaryFixture {
        [CmdletBinding()]
        param(
            [Parameter(Mandatory)]
            [string]$Root
        )

        $null = New-Item -ItemType Directory -Path (Join-Path $Root 'skill') -Force
        $null = New-Item -ItemType Directory -Path (Join-Path $Root 'payload') -Force
        Set-Content -LiteralPath (Join-Path $Root 'skill/SKILL.md') -Value '# reviewed skill'
        Set-Content -LiteralPath (Join-Path $Root 'payload/index.db') -Value 'generated data'
        Set-Content -LiteralPath (Join-Path $Root 'payload/tool') -Value 'compiled program'
        Set-Content -LiteralPath (Join-Path $Root '.gitignore') -Value @(
            '/payload/index.db'
            '/payload/tool'
        )

        $programHash = (Get-FileHash -LiteralPath (Join-Path $Root 'payload/tool') `
                -Algorithm SHA256).Hash.ToLowerInvariant()
        Set-Content -LiteralPath (Join-Path $Root '.apm-approved-artifacts') -Value @(
            "data`tpayload/index.db"
            "program`tpayload/tool"
        )
        Set-Content -LiteralPath (Join-Path $Root '.apm-program-checksums') `
            -Value "$programHash  payload/tool"
        Set-Content -LiteralPath (Join-Path $Root 'apm.lock.yaml') -Value @(
            "lockfile_version: '1'"
            'deployments:'
            '- kind: project-relative'
            '  value: skill/SKILL.md'
            '  content_hash: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
            '- kind: project-relative'
            '  value: payload/index.db'
            '  content_hash: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
            '- kind: project-relative'
            '  value: payload/tool'
            "  content_hash: sha256:$programHash"
            'local_deployed_files:'
            '- skill/SKILL.md'
        )

        & git -C $Root init --quiet
        if ($LASTEXITCODE -ne 0) { throw 'Failed to initialize test repository.' }
        & git -C $Root add -- .gitignore .apm-approved-artifacts `
            .apm-program-checksums apm.lock.yaml skill/SKILL.md
        if ($LASTEXITCODE -ne 0) { throw 'Failed to stage test repository files.' }
    }
}

Describe 'APM review boundary' {
    BeforeEach {
        $fixtureRoot = Join-Path $TestDrive ([guid]::NewGuid().ToString('N'))
        New-ReviewBoundaryFixture -Root $fixtureRoot
    }

    It 'accepts tracked deployments and exact ignored artifact exceptions' {
        $result = & $script:ValidationPath -RepositoryRoot $fixtureRoot

        $result | Should-Be (
            'APM review boundary passed: 3 deployed files, 2 approved artifacts, 1 pinned programs.'
        )
    }

    It 'rejects an ignored deployed instruction outside the artifact list' {
        Set-Content -LiteralPath (Join-Path $fixtureRoot 'skill/hidden.md') -Value 'hidden instructions'
        Add-Content -LiteralPath (Join-Path $fixtureRoot '.gitignore') -Value '/skill/hidden.md'
        $lockfile = Join-Path $fixtureRoot 'apm.lock.yaml'
        $lines = @([System.IO.File]::ReadAllLines($lockfile))
        $updatedLines = @($lines[0..($lines.Count - 3)]) + @(
            '- kind: project-relative'
            '  value: skill/hidden.md'
            '  content_hash: sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc'
        ) + @($lines[($lines.Count - 2)..($lines.Count - 1)])
        Set-Content -LiteralPath $lockfile -Value $updatedLines

        { & $script:ValidationPath -RepositoryRoot $fixtureRoot } |
            Should-Throw -ExceptionMessage "*skill/hidden.md*neither tracked nor an approved artifact*"
    }

    It 'rejects an approved artifact that is not deployed by APM' {
        Set-Content -LiteralPath (Join-Path $fixtureRoot 'payload/stale.db') -Value 'stale data'
        Add-Content -LiteralPath (Join-Path $fixtureRoot '.gitignore') -Value '/payload/stale.db'
        Add-Content -LiteralPath (Join-Path $fixtureRoot '.apm-approved-artifacts') `
            -Value "data`tpayload/stale.db"

        { & $script:ValidationPath -RepositoryRoot $fixtureRoot } |
            Should-Throw -ExceptionMessage "*payload/stale.db*not an APM file deployment*"
    }

    It 'rejects a file disguised as a directory deployment' {
        $lockfile = Join-Path $fixtureRoot 'apm.lock.yaml'
        $content = [System.IO.File]::ReadAllText($lockfile).Replace(
            '  content_hash: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
            '  content_hash: null'
        )
        Set-Content -LiteralPath $lockfile -Value $content

        { & $script:ValidationPath -RepositoryRoot $fixtureRoot } |
            Should-Throw -ExceptionMessage "*payload/index.db*is not a directory*"
    }

    It 'rejects tracked files from the artifact exception list' {
        & git -C $fixtureRoot add --force -- payload/index.db
        if ($LASTEXITCODE -ne 0) { throw 'Failed to force-add test artifact.' }

        { & $script:ValidationPath -RepositoryRoot $fixtureRoot } |
            Should-Throw -ExceptionMessage "*payload/index.db*tracked*remove it from the exception list*"
    }

    It 'rejects an approved program without a separate fingerprint' {
        Set-Content -LiteralPath (Join-Path $fixtureRoot '.apm-program-checksums') `
            -Value '# intentionally empty'

        { & $script:ValidationPath -RepositoryRoot $fixtureRoot } |
            Should-Throw -ExceptionMessage "*payload/tool*exactly one SHA256 fingerprint*"
    }

    It 'rejects changed program bytes' {
        Add-Content -LiteralPath (Join-Path $fixtureRoot 'payload/tool') -Value 'unapproved change'

        { & $script:ValidationPath -RepositoryRoot $fixtureRoot } |
            Should-Throw -ExceptionMessage "*payload/tool*does not match its reviewed SHA256 fingerprint*"
    }

    It 'rejects a fingerprint that differs from the APM lockfile' {
        $wrongHash = 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd'
        Set-Content -LiteralPath (Join-Path $fixtureRoot '.apm-program-checksums') `
            -Value "$wrongHash  payload/tool"

        { & $script:ValidationPath -RepositoryRoot $fixtureRoot } |
            Should-Throw -ExceptionMessage "*payload/tool*fingerprint differs from apm.lock.yaml*"
    }
}
