[Diagnostics.CodeAnalysis.SuppressMessageAttribute(
    'PSUseDeclaredVarsMoreThanAssignments',
    'actionCases',
    Justification = 'Pester consumes this discovery-time value through -ForEach.'
)]
param()

BeforeDiscovery {
    $actionCases = @(
        @{ Installed = $null; Approved = [version]'1.2.3'; Expected = 'Install' }
        @{ Installed = [version]'1.2.2'; Approved = [version]'1.2.3'; Expected = 'Upgrade' }
        @{ Installed = [version]'1.2.3'; Approved = [version]'1.2.3'; Expected = 'None' }
        @{ Installed = [version]'1.2.4'; Approved = [version]'1.2.3'; Expected = 'Stop' }
    )
}

BeforeAll {
    $script:RepositoryRoot = Split-Path -Parent $PSScriptRoot
    . (Join-Path $script:RepositoryRoot 'scripts/Bootstrap-Global.ps1')
    $script:PinnedVersion = (
        Get-Content -LiteralPath (Join-Path $script:RepositoryRoot '.apm-version') -TotalCount 1
    ).Trim()

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
        }
        else {
            Set-Content -LiteralPath (Join-Path $Path 'apm') -Encoding UTF8 -Value @(
                '#!/usr/bin/env sh'
                'if [ "${1-}" = --version ]; then printf "APM %s\n" "$FAKE_APM_VERSION"; exit 0; fi'
                'printf "apm %s\n" "$*" >> "$TEST_COMMAND_LOG"'
                'exit 0'
            )
            & chmod +x (Join-Path $Path 'apm')
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
        $env:FAKE_APM_VERSION = $script:PinnedVersion
        Invoke-GlobalBootstrap -RepositoryRoot $script:RepositoryRoot -Confirm:$false
        $log = Get-Content -LiteralPath $env:TEST_COMMAND_LOG -Raw
        $log | Should-MatchString 'apm install --global --frozen'
        $log | Should-MatchString 'apm compile --global --dry-run'
        $log | Should-MatchString 'apm compile --global'
    }

    It 'does not mutate during an older-version dry run' {
        $env:FAKE_APM_VERSION = '0.0.1'
        $output = @(Invoke-GlobalBootstrap -RepositoryRoot $script:RepositoryRoot -WhatIf -Confirm:$false 6>&1) -join "`n"
        $output | Should-MatchString 'CLI action: Upgrade'
        (Get-Content -LiteralPath $env:TEST_COMMAND_LOG -Raw).Trim() | Should-Be ''
    }

    It 'stops before deployment for a newer CLI' {
        $env:FAKE_APM_VERSION = '999.999.999'
        { Invoke-GlobalBootstrap -RepositoryRoot $script:RepositoryRoot -Confirm:$false } |
            Should-Throw -ExceptionMessage '*newer than pinned baseline*'
        (Get-Content -LiteralPath $env:TEST_COMMAND_LOG -Raw).Trim() | Should-Be ''
    }

    It 'fails before deployment when the installer download fails' {
        $env:FAKE_APM_VERSION = '0.0.1'
        Mock Invoke-WebRequest { throw 'download failed' }
        { Invoke-GlobalBootstrap -RepositoryRoot $script:RepositoryRoot -Confirm:$false } |
            Should-Throw -ExceptionMessage '*download failed*'
        (Get-Content -LiteralPath $env:TEST_COMMAND_LOG -Raw).Trim() | Should-Be ''
    }
}

Describe 'Repository invariants' {
    It 'pins the APM CLI to a plain X.Y.Z version' {
        $script:PinnedVersion | Should-MatchString '^\d+\.\d+\.\d+$'
    }

    It 'commits the APM dependency lockfile' {
        Test-Path (Join-Path $script:RepositoryRoot 'apm.lock.yaml') | Should-BeTrue
    }

    It 'declares an explicit ref for every APM dependency' {
        $manifest = Get-Content (Join-Path $script:RepositoryRoot 'apm.yml')
        $references = @($manifest | Where-Object { $_ -match '^\s+-\s+[A-Za-z0-9._/-]+#\S+$' })
        $references.Count | Should-Be 5
    }

    It 'pins every GitHub Action to a full commit SHA' {
        $workflowLines = Get-Content (Join-Path $script:RepositoryRoot '.github/workflows/*.yml')
        $usesLines = @($workflowLines | Where-Object { $_ -match '^\s+(?:-\s+)?uses:' })
        $usesLines.Count | Should-BeGreaterThan 0
        foreach ($line in $usesLines) { $line | Should-MatchString '@[0-9a-f]{40}(\s|$)' }
    }

    It 'validates the candidate update before publishing the review PR' {
        $workflow = Get-Content (Join-Path $script:RepositoryRoot '.github/workflows/update-baseline.yml') -Raw
        $workflow | Should-MatchString 'gh pr list --head'
        $workflow.IndexOf('Validate candidate update') |
            Should-BeLessThan $workflow.IndexOf('Create or update review pull request')
    }

    It 'keeps the local Pester 6 guidance project agnostic' {
        $path = Join-Path $script:RepositoryRoot '.apm/skills/powershell-pester-6/SKILL.md'
        # Assembled from character codes so this tracked test never matches the
        # project-specific reference it guards against.
        $projectMarker = -join ([char[]](70, 65, 67, 84))
        (Get-Content $path -Raw).Contains($projectMarker) | Should-BeFalse
    }
}
