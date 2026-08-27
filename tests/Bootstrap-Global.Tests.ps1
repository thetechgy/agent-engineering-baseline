[Diagnostics.CodeAnalysis.SuppressMessageAttribute(
    'PSUseDeclaredVarsMoreThanAssignments',
    'actionCases',
    Justification = 'Pester consumes this discovery-time value through -ForEach.'
)]
[Diagnostics.CodeAnalysis.SuppressMessageAttribute(
    'PSUseDeclaredVarsMoreThanAssignments',
    'updateCases',
    Justification = 'Pester consumes this discovery-time value through -ForEach.'
)]
param()

BeforeDiscovery {
    $actionCases = @(
        @{ Installed = $null; Approved = [version]'0.28.0'; Expected = 'Install' }
        @{ Installed = [version]'0.27.0'; Approved = [version]'0.28.0'; Expected = 'Upgrade' }
        @{ Installed = [version]'0.28.0'; Approved = [version]'0.28.0'; Expected = 'None' }
        @{ Installed = [version]'0.29.0'; Approved = [version]'0.28.0'; Expected = 'Stop' }
    )
    $updateCases = @(
        @{ CurrentCli = '1.0.0'; CandidateCli = '1.0.0'; Current = @('a'); Candidate = @('a'); Expected = 'NoChange' }
        @{ CurrentCli = '1.0.0'; CandidateCli = '1.1.0'; Current = @('a'); Candidate = @('a'); Expected = 'ApmOnly' }
        @{ CurrentCli = '1.0.0'; CandidateCli = '1.0.0'; Current = @('a'); Candidate = @('b'); Expected = 'SkillsOnly' }
        @{ CurrentCli = '1.0.0'; CandidateCli = '1.1.0'; Current = @('a'); Candidate = @('b'); Expected = 'Combined' }
    )
}

BeforeAll {
    $script:RepositoryRoot = Split-Path -Parent $PSScriptRoot
    . (Join-Path $script:RepositoryRoot 'scripts/Bootstrap-Global.ps1')
    . (Join-Path $script:RepositoryRoot 'scripts/Update-Baseline.ps1')

    function Initialize-FakeApmCommand {
        param([Parameter(Mandatory)][string]$Path)

        $null = New-Item -ItemType Directory -Path $Path -Force
        if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) {
            Set-Content -LiteralPath (Join-Path $Path 'apm.cmd') -Encoding Ascii -Value @(
                '@echo off'
                'if "%1"=="--version" (echo APM %FAKE_APM_VERSION%& exit /b 0)'
                'echo apm %*>>"%TEST_COMMAND_LOG%"'
                'exit /b 0'
            )
            Set-Content -LiteralPath (Join-Path $Path 'codex.cmd') -Encoding Ascii -Value @(
                '@echo off'
                'echo No MCP server named ''github-mcp-server'' found. 1>&2'
                'exit /b 1'
            )
        }
        else {
            Set-Content -LiteralPath (Join-Path $Path 'apm') -Encoding UTF8 -Value @(
                '#!/usr/bin/env sh'
                'if [ "${1-}" = --version ]; then printf "APM %s\n" "$FAKE_APM_VERSION"; exit 0; fi'
                'printf "apm %s\n" "$*" >> "$TEST_COMMAND_LOG"'
                'exit 0'
            )
            Set-Content -LiteralPath (Join-Path $Path 'codex') -Encoding UTF8 -Value @(
                '#!/usr/bin/env sh'
                'printf "No MCP server named ''github-mcp-server'' found.\n" >&2'
                'exit 1'
            )
            & chmod +x (Join-Path $Path 'apm') (Join-Path $Path 'codex')
        }
    }
}

Describe 'APM CLI bootstrap decision' {
    It 'selects <Expected> for installed <Installed>' -ForEach $actionCases {
        Get-ApmBootstrapAction -InstalledVersion $Installed -ApprovedVersion $Approved |
            Should-Be $Expected
    }

    It 'parses standard APM version output' {
        ConvertTo-ApmVersion -Text 'Agent Package Manager (APM) CLI version 0.28.0 (e041462)' |
            Should-Be ([version]'0.28.0')
    }

    It 'fails closed for malformed version output' {
        { ConvertTo-ApmVersion -Text 'unknown' } | Should-Throw -ExceptionMessage '*Unable to parse*'
    }
}

Describe 'GitHub MCP ownership boundary' {
    BeforeAll {
        $script:DefaultMcp = @'
{
  "name": "github-mcp-server", "enabled": true, "disabled_reason": null,
  "transport": {"type": "streamable_http", "url": "https://api.githubcopilot.com/mcp/",
    "bearer_token_env_var": "GITHUB_TOKEN", "http_headers": null,
    "env_http_headers": null, "http_headers_helper": null},
  "enabled_tools": null, "disabled_tools": null,
  "startup_timeout_sec": null, "tool_timeout_sec": null
}

'@ | ConvertFrom-Json
    }

    It 'accepts the complete APM-owned entry' {
        Test-DefaultGithubMcpConfiguration -Configuration $script:DefaultMcp | Should-BeTrue
    }

    It 'rejects a customized entry' {
        $custom = $script:DefaultMcp | ConvertTo-Json -Depth 5 | ConvertFrom-Json
        $custom.transport.url = 'https://custom.example.invalid/'
        Test-DefaultGithubMcpConfiguration -Configuration $custom | Should-BeFalse
    }
}

Describe 'Native PowerShell bootstrap behavior' {
    BeforeEach {
        $script:OriginalPath = $env:PATH
        $script:OriginalVersion = $env:FAKE_APM_VERSION
        $script:OriginalLog = $env:TEST_COMMAND_LOG
        $script:FakeBin = Join-Path $TestDrive ([Guid]::NewGuid().ToString('N'))
        Initialize-FakeApmCommand -Path $script:FakeBin
        $env:PATH = "$($script:FakeBin)$([IO.Path]::PathSeparator)$($env:PATH)"
        $env:TEST_COMMAND_LOG = Join-Path $TestDrive 'commands.log'
        Set-Content -LiteralPath $env:TEST_COMMAND_LOG -Value ''
    }

    AfterEach {
        $env:PATH = $script:OriginalPath
        $env:FAKE_APM_VERSION = $script:OriginalVersion
        $env:TEST_COMMAND_LOG = $script:OriginalLog
    }

    It 'uses native global install and compile for a matching CLI' {
        $env:FAKE_APM_VERSION = '0.28.0'
        Invoke-GlobalBootstrap -RepositoryRoot $script:RepositoryRoot -Confirm:$false
        $log = Get-Content -LiteralPath $env:TEST_COMMAND_LOG -Raw
        $log | Should-MatchString 'apm install --global --frozen'
        $log | Should-MatchString 'apm compile --global --dry-run'
        $log | Should-MatchString 'apm compile --global'
    }

    It 'does not mutate during an older-version dry run' {
        $env:FAKE_APM_VERSION = '0.27.0'
        $output = @(Invoke-GlobalBootstrap -RepositoryRoot $script:RepositoryRoot -WhatIf -Confirm:$false 6>&1) -join "`n"
        $output | Should-MatchString 'CLI action: Upgrade'
        (Get-Content -LiteralPath $env:TEST_COMMAND_LOG -Raw).Trim() | Should-Be ''
    }

    It 'stops before deployment for a newer CLI' {
        $env:FAKE_APM_VERSION = '0.29.0'
        { Invoke-GlobalBootstrap -RepositoryRoot $script:RepositoryRoot -Confirm:$false } |
            Should-Throw -ExceptionMessage '*newer than reviewed baseline*'
        (Get-Content -LiteralPath $env:TEST_COMMAND_LOG -Raw).Trim() | Should-Be ''
    }

    It 'fails before deployment when the installer download fails' {
        $env:FAKE_APM_VERSION = '0.27.0'
        Mock Invoke-WebRequest { throw 'download failed' }
        { Invoke-GlobalBootstrap -RepositoryRoot $script:RepositoryRoot -Confirm:$false } |
            Should-Throw -ExceptionMessage '*download failed*'
        (Get-Content -LiteralPath $env:TEST_COMMAND_LOG -Raw).Trim() | Should-Be ''
    }

    It 'fails before deployment when the installer checksum differs' {
        $env:FAKE_APM_VERSION = '0.27.0'
        Mock Invoke-WebRequest { Set-Content -LiteralPath $OutFile -Value 'tampered' }
        { Invoke-GlobalBootstrap -RepositoryRoot $script:RepositoryRoot -Confirm:$false } |
            Should-Throw -ExceptionMessage '*does not match apm-cli.lock.yml*'
        (Get-Content -LiteralPath $env:TEST_COMMAND_LOG -Raw).Trim() | Should-Be ''
    }
}

Describe 'Scheduled update classification' {
    It 'classifies <Expected>' -ForEach $updateCases {
        Get-BaselineChangeKind -CurrentCliVersion $CurrentCli -CandidateCliVersion $CandidateCli `
            -CurrentCommits $Current -CandidateCommits $Candidate | Should-Be $Expected
    }

    It 'updates an existing PR only after candidate validation' {
        $workflow = Get-Content (Join-Path $script:RepositoryRoot '.github/workflows/update-baseline.yml') -Raw
        $workflow | Should-MatchString 'gh pr list --head'
        $workflow | Should-MatchString 'if \[ -n "\$pr_number" \]'
        $workflow.IndexOf('Validate candidate update') |
            Should-BeLessThan $workflow.IndexOf('Create or update review pull request')
    }
}

Describe 'Pinned source transformation' {
    It 'declares only APM frontmatter on every mirrored skill' {
        $manifest = Get-Content (Join-Path $script:RepositoryRoot 'upstream-sources.json') -Raw |
            ConvertFrom-Json
        foreach ($source in $manifest.sources) {
            $output = Get-Content (Join-Path $script:RepositoryRoot $source.output) -Raw
            $output | Should-MatchString "name: $($source.name)"
            $output | Should-MatchString ([regex]::Escape($source.description))
            $output | Should-NotMatchString 'applyTo:'
        }
    }

    It 'keeps the local Pester 6 guidance project agnostic' {
        $path = Join-Path $script:RepositoryRoot '.apm/skills/powershell-pester-6/SKILL.md'
        $projectMarker = [string]::Concat([char]70, [char]65, [char]67, [char]84)
        (Get-Content $path -Raw).Contains($projectMarker) | Should-BeFalse
    }
}

Describe 'Repository invariants' {
    It 'uses full commit SHAs for every APM dependency' {
        $manifest = Get-Content (Join-Path $script:RepositoryRoot 'apm.yml')
        $references = @($manifest | Where-Object { $_ -match '^\s+-\s+[^#]+#(.+)$' })
        $references.Count | Should-Be 5
        foreach ($reference in $references) { $reference | Should-MatchString '#[0-9a-f]{40}$' }
    }

    It 'records installer, archive, and executable hashes' {
        $lock = Get-Content (Join-Path $script:RepositoryRoot 'apm-cli.lock.yml') -Raw
        ([regex]::Matches($lock, '(?m)^\s+sha256:\s+[0-9a-f]{64}$')).Count | Should-Be 5
        ([regex]::Matches($lock, '(?m)^\s+executable_sha256:\s+[0-9a-f]{64}$')).Count | Should-Be 3
        Get-ApmLockValue -Content $lock `
            -Pattern '(?m)^  windows:\s*\r?\n    url:[^\r\n]+\r?\n    sha256:\s*([^\r\n]+)' `
            -Description 'Windows installer hash' |
            Should-Be '859e63f2a3a342d2d4d4aac57cf6e81a006f3ceb80e2b90f9a031d45b4fd432b'
    }

    It 'pins every GitHub Action to a full commit SHA' {
        $workflowLines = Get-Content (Join-Path $script:RepositoryRoot '.github/workflows/*.yml')
        $usesLines = @($workflowLines | Where-Object { $_ -match '^\s+(?:-\s+)?uses:' })
        $usesLines.Count | Should-BeGreaterThan 0
        foreach ($line in $usesLines) { $line | Should-MatchString '@[0-9a-f]{40}(\s|$)' }
    }
}
