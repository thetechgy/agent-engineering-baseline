[Diagnostics.CodeAnalysis.SuppressMessageAttribute(
    'PSUseShouldProcessForStateChangingFunctions',
    '',
    Justification = 'These helpers mutate only isolated Pester TestDrive profiles.',
    Scope = 'Function',
    Target = 'New-FakeToolDirectory'
)]
[Diagnostics.CodeAnalysis.SuppressMessageAttribute(
    'PSUseShouldProcessForStateChangingFunctions',
    '',
    Justification = 'These helpers mutate only isolated Pester TestDrive profiles.',
    Scope = 'Function',
    Target = 'Set-DefaultMcpState'
)]
[Diagnostics.CodeAnalysis.SuppressMessageAttribute(
    'PSUseDeclaredVarsMoreThanAssignments',
    'nativeFailureStages',
    Justification = 'Pester consumes this discovery-time variable through -ForEach.'
)]
param()

BeforeDiscovery {
    $nativeFailureStages = @(
        'codex-remove'
        'install'
        'compile-dry-codex'
        'compile-dry-copilot'
        'compile-write-codex'
        'compile-write-copilot'
    )
}

BeforeAll {
    $script:RepositoryRoot = Split-Path -Parent $PSScriptRoot
    $script:PinnedVersion = (
        [System.IO.File]::ReadAllLines((Join-Path $script:RepositoryRoot '.apm-version'))[0]
    ).Trim()
    $script:BootstrapPath = Join-Path $script:RepositoryRoot 'scripts/Bootstrap-Global.ps1'
    $script:FakeToolPath = Join-Path $PSScriptRoot 'fixtures/Fake-BootstrapTool.ps1'
    $script:ManagedSkills = @(
        'a11y'
        'agent-safety'
        'ansible'
        'powershell-pester-6'
        'powershell-module-engineering'
        'code-simplification'
        'dependabot'
        'git-commit'
        'github-actions-hardening'
        'msgraph'
    )
    $script:DefaultMcpJson = @'
{
  "name": "github-mcp-server",
  "enabled": true,
  "disabled_reason": null,
  "transport": {
    "type": "streamable_http",
    "url": "https://api.githubcopilot.com/mcp/",
    "bearer_token_env_var": "GITHUB_TOKEN",
    "http_headers": null,
    "env_http_headers": null,
    "http_headers_helper": null
  },
  "enabled_tools": null,
  "disabled_tools": null,
  "startup_timeout_sec": null,
  "tool_timeout_sec": null
}
'@
    $script:DefaultCopilotMcpJson = @'
{
  "mcpServers": {
    "github-mcp-server": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/",
      "tools": ["*"],
      "id": "",
      "headers": {},
      "bearer_token_env_var": "GITHUB_TOKEN"
    }
  }
}
'@

    . $script:BootstrapPath

    function New-FakeToolDirectory {
        [CmdletBinding()]
        param(
            [Parameter(Mandatory)]
            [string]$Path
        )

        $null = New-Item -ItemType Directory -Path $Path -Force
        $currentExecutable = [System.Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
        if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) {
            foreach ($toolName in @('apm', 'codex')) {
                $wrapperPath = Join-Path $Path "$toolName.cmd"
                $wrapper = @(
                    '@echo off'
                    ('"{0}" -NoLogo -NoProfile -File "{1}" {2} %*' -f `
                        $currentExecutable, $script:FakeToolPath, $toolName)
                )
                Set-Content -LiteralPath $wrapperPath -Value $wrapper -Encoding Ascii
            }
        }
        else {
            $singleQuote = [string][char]39
            $shellQuoteEscape = [string]::Concat([char]39, [char]92, [char]39, [char]39)
            $quotedExecutable = $currentExecutable.Replace($singleQuote, $shellQuoteEscape)
            $quotedToolPath = $script:FakeToolPath.Replace($singleQuote, $shellQuoteEscape)
            foreach ($toolName in @('apm', 'codex')) {
                $wrapperPath = Join-Path $Path $toolName
                $wrapper = @(
                    '#!/usr/bin/env sh'
                    "exec '$quotedExecutable' -NoLogo -NoProfile -File '$quotedToolPath' $toolName `"`$@`""
                )
                Set-Content -LiteralPath $wrapperPath -Value $wrapper -Encoding UTF8
                & chmod +x $wrapperPath
            }
        }
    }

    function Set-DefaultMcpState {
        [CmdletBinding()]
        param(
            [Parameter(Mandatory)]
            [string]$HomePath
        )

        $codexDirectory = Join-Path $HomePath '.codex'
        $null = New-Item -ItemType Directory -Path $codexDirectory -Force
        Set-Content -LiteralPath (Join-Path $HomePath '.fake-github-mcp.json') `
            -Value $script:DefaultMcpJson -Encoding UTF8
        Add-Content -LiteralPath (Join-Path $codexDirectory 'config.toml') -Value @(
            '[mcp_servers.github-mcp-server]'
            'url = "https://api.githubcopilot.com/mcp/"'
            'bearer_token_env_var = "GITHUB_TOKEN"'
        )
        $copilotDirectory = Join-Path $HomePath '.copilot'
        $null = New-Item -ItemType Directory -Path $copilotDirectory -Force
        Set-Content -LiteralPath (Join-Path $copilotDirectory 'mcp-config.json') `
            -Value $script:DefaultCopilotMcpJson -Encoding UTF8
    }

    function Initialize-OldProfile {
        [CmdletBinding()]
        param(
            [Parameter(Mandatory)]
            [string]$HomePath
        )

        foreach ($path in @(
                '.apm/.apm/skills/old'
                '.apm/apm_modules/old'
                '.codex'
                '.copilot'
                '.agents/skills'
            )) {
            $null = New-Item -ItemType Directory -Path (Join-Path $HomePath $path) -Force
        }
        Set-Content -LiteralPath (Join-Path $HomePath '.apm/apm.yml') -Value 'old manifest'
        Set-Content -LiteralPath (Join-Path $HomePath '.apm/apm.lock.yaml') -Value 'old lock'
        Set-Content -LiteralPath (Join-Path $HomePath '.apm/.apm/skills/old/value') -Value 'old source'
        Set-Content -LiteralPath (Join-Path $HomePath '.apm/apm_modules/old/value') -Value 'old module'
        Set-Content -LiteralPath (Join-Path $HomePath '.apm/config.json') -Value 'old config'
        Set-Content -LiteralPath (Join-Path $HomePath '.codex/AGENTS.md') -Value '# old codex'
        Set-Content -LiteralPath (Join-Path $HomePath '.codex/config.toml') `
            -Value @('project_doc_max_bytes = 77777', '')
        Set-Content -LiteralPath (Join-Path $HomePath '.copilot/AGENTS.md') `
            -Value 'untouched copilot agents'
        foreach ($skillName in $script:ManagedSkills) {
            if ($skillName -ceq 'msgraph') {
                continue
            }
            $skillPath = Join-Path $HomePath ".agents/skills/$skillName"
            $null = New-Item -ItemType Directory -Path $skillPath -Force
            Set-Content -LiteralPath (Join-Path $skillPath 'value') -Value "old $skillName"
        }
        Set-DefaultMcpState -HomePath $HomePath
    }

    function Get-ProfileFingerprint {
        [CmdletBinding()]
        param(
            [Parameter(Mandatory)]
            [string]$HomePath
        )

        $relativePaths = @(
            '.apm/apm.yml'
            '.apm/apm.lock.yaml'
            '.apm/.apm'
            '.apm/apm_modules'
            '.apm/config.json'
            '.codex/AGENTS.md'
            '.codex/config.toml'
            '.copilot/copilot-instructions.md'
            '.copilot/mcp-config.json'
        )
        foreach ($skillName in $script:ManagedSkills) {
            $relativePaths += ".agents/skills/$skillName"
        }

        $fingerprint = [ordered]@{}
        foreach ($relativePath in $relativePaths) {
            $path = Join-Path $HomePath $relativePath
            if (-not (Test-Path -LiteralPath $path)) {
                $fingerprint[$relativePath] = '<absent>'
            }
            elseif (Test-Path -LiteralPath $path -PathType Container) {
                $fingerprint[$relativePath] = @(Get-DirectoryInventory -Path $path) -join "`n"
            }
            else {
                $fingerprint[$relativePath] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
            }
        }
        return $fingerprint
    }

    function Compare-ProfileFingerprint {
        [CmdletBinding()]
        param(
            [Parameter(Mandatory)]
            [System.Collections.IDictionary]$Reference,

            [Parameter(Mandatory)]
            [System.Collections.IDictionary]$Difference
        )

        foreach ($key in $Reference.Keys) {
            if ($Reference[$key] -cne $Difference[$key]) {
                return $false
            }
        }
        return $true
    }
}

Describe 'Bootstrap-Global interface and helpers' {
    It 'retains ShouldProcess parameters and removes Update' {
        $command = Get-Command -Name $script:BootstrapPath

        Should-HaveParameter -Actual $command -ParameterName 'WhatIf' -Type ([switch])
        Should-HaveParameter -Actual $command -ParameterName 'Confirm' -Type ([switch])
        $command.Parameters.ContainsKey('Update') | Should-BeFalse
    }

    It 'accepts only the exact default GitHub MCP configuration' {
        $default = $script:DefaultMcpJson | ConvertFrom-Json
        $custom = $script:DefaultMcpJson | ConvertFrom-Json
        $custom.transport.url = 'https://custom.example.invalid/mcp/'

        Test-DefaultGithubMcpConfiguration -Configuration $default | Should-BeTrue
        Test-DefaultGithubMcpConfiguration -Configuration $custom | Should-BeFalse

        $defaultCopilot = ($script:DefaultCopilotMcpJson | ConvertFrom-Json).mcpServers.'github-mcp-server'
        $customCopilot = ($script:DefaultCopilotMcpJson | ConvertFrom-Json).mcpServers.'github-mcp-server'
        $customCopilot.url = 'https://custom.example.invalid/mcp/'
        Test-DefaultCopilotGithubMcpConfiguration -Configuration $defaultCopilot | Should-BeTrue
        Test-DefaultCopilotGithubMcpConfiguration -Configuration $customCopilot | Should-BeFalse
    }

    It 'selects the expected pinned CLI action' {
        Get-ApmBootstrapAction -InstalledVersion $null -ApprovedVersion ([version]'1.2.3') |
            Should-Be 'Install'
        Get-ApmBootstrapAction -InstalledVersion ([version]'1.2.2') `
            -ApprovedVersion ([version]'1.2.3') | Should-Be 'Upgrade'
        Get-ApmBootstrapAction -InstalledVersion ([version]'1.2.3') `
            -ApprovedVersion ([version]'1.2.3') | Should-Be 'None'
        Get-ApmBootstrapAction -InstalledVersion ([version]'1.2.4') `
            -ApprovedVersion ([version]'1.2.3') | Should-Be 'Stop'
    }

    It 'extracts the pinned installer checksum' {
        $checksumPath = Join-Path $TestDrive 'checksums'
        Set-Content -LiteralPath $checksumPath -Value @(
            ('a' * 64) + '  install.sh'
            ('b' * 64) + '  install.ps1'
        )
        Get-PinnedInstallerChecksum -ChecksumPath $checksumPath -FileName 'install.ps1' |
            Should-Be ('b' * 64)
    }

    It 'forwards Confirm only when it is explicitly bound' {
        $omitted = Get-ExplicitConfirmParameter -BoundParameters @{}
        $enabled = Get-ExplicitConfirmParameter -BoundParameters @{ Confirm = $true }
        $disabled = Get-ExplicitConfirmParameter -BoundParameters @{ Confirm = $false }

        $omitted.Contains('Confirm') | Should-BeFalse
        $enabled['Confirm'] | Should-BeTrue
        $disabled['Confirm'] | Should-BeFalse
    }

    It 'recognizes the generated marker only near the start of a regular file' {
        $generatedPath = Join-Path $TestDrive 'generated.md'
        $lateMarkerPath = Join-Path $TestDrive 'late-marker.md'
        @('# AGENTS.md', '<!-- Generated by APM CLI from .apm/ primitives -->') |
            Set-Content -LiteralPath $generatedPath
        @('# 1', '# 2', '# 3', '# 4', '# 5', '# 6', '<!-- Generated by APM CLI from .apm/ primitives -->') |
            Set-Content -LiteralPath $lateMarkerPath

        Test-ApmGeneratedFile -Path $generatedPath | Should-BeTrue
        Test-ApmGeneratedFile -Path $lateMarkerPath | Should-BeFalse
    }

    It 'releases files after bounded header reads' {
        $configPath = Join-Path $TestDrive 'config.toml'
        $generatedPath = Join-Path $TestDrive 'generated-release.md'
        Set-Content -LiteralPath $configPath -Value @(
            'project_doc_max_bytes = 90001'
            '[features]'
            'example = true'
        )
        Set-Content -LiteralPath $generatedPath -Value @(
            '# AGENTS.md'
            '<!-- Generated by APM CLI from .apm/ primitives -->'
        )

        @(Get-ProjectDocSetting -Path $configPath).Count | Should-Be 1
        Test-ApmGeneratedFile -Path $generatedPath | Should-BeTrue
        foreach ($path in @($configPath, $generatedPath)) {
            $stream = [System.IO.File]::Open(
                $path,
                [System.IO.FileMode]::Open,
                [System.IO.FileAccess]::ReadWrite,
                [System.IO.FileShare]::None
            )
            $stream.Dispose()
        }
    }

    It 'detects a nested reparse point during recursive validation' {
        $treePath = Join-Path $TestDrive 'recursive-tree'
        $targetPath = Join-Path $TestDrive 'recursive-target'
        $linkPath = Join-Path $treePath 'linked'
        $null = New-Item -ItemType Directory -Path $treePath -Force
        $null = New-Item -ItemType Directory -Path $targetPath -Force
        Set-Content -LiteralPath (Join-Path $treePath 'regular.txt') -Value 'regular'

        Test-PathWithoutReparsePoint -Path $treePath -PathType Directory -Recurse |
            Should-BeTrue
        if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) {
            & cmd.exe /d /c "mklink /J `"$linkPath`" `"$targetPath`"" | Out-Null
        }
        else {
            $null = New-Item -ItemType SymbolicLink -Path $linkPath -Target $targetPath
        }
        Test-PathWithoutReparsePoint -Path $treePath -PathType Directory -Recurse |
            Should-BeFalse
    }
}

Describe 'Bootstrap-Global behavior' {
    BeforeEach {
        $script:CaseRoot = Join-Path $TestDrive ([Guid]::NewGuid().ToString('N'))
        $script:CaseHome = Join-Path $script:CaseRoot 'home'
        $script:CaseBin = Join-Path $script:CaseRoot 'bin'
        $null = New-Item -ItemType Directory -Path $script:CaseHome -Force
        New-FakeToolDirectory -Path $script:CaseBin
        $script:OriginalPath = $env:PATH
        $script:OriginalFakeHome = $env:FAKE_HOME
        $script:OriginalFakeApmVersion = $env:FAKE_APM_VERSION
        $script:OriginalApmFailure = $env:FAKE_APM_FAIL_STAGE
        $script:OriginalCodexFailure = $env:FAKE_CODEX_FAIL_REMOVE
        $pathSeparator = [System.IO.Path]::PathSeparator
        $env:PATH = "$($script:CaseBin)$pathSeparator$($env:PATH)"
        $env:FAKE_HOME = $script:CaseHome
        $env:FAKE_APM_VERSION = $script:PinnedVersion
        $env:FAKE_APM_FAIL_STAGE = $null
        $env:FAKE_CODEX_FAIL_REMOVE = $null
    }

    AfterEach {
        $env:PATH = $script:OriginalPath
        $env:FAKE_HOME = $script:OriginalFakeHome
        $env:FAKE_APM_VERSION = $script:OriginalFakeApmVersion
        $env:FAKE_APM_FAIL_STAGE = $script:OriginalApmFailure
        $env:FAKE_CODEX_FAIL_REMOVE = $script:OriginalCodexFailure
    }

    It 'performs a fresh frozen install with a complete snapshot and source fidelity' {
        $null = New-Item -ItemType Directory -Path (Join-Path $script:CaseHome '.codex') -Force
        $null = New-Item -ItemType Directory -Path (Join-Path $script:CaseHome '.copilot') -Force
        $null = New-Item -ItemType Directory -Path (Join-Path $script:CaseHome 'private') -Force
        Set-Content -LiteralPath (Join-Path $script:CaseHome '.codex/config.toml') `
            -Value @('project_doc_max_bytes = 90001', '', '[features]', 'example = true')
        Set-Content -LiteralPath (Join-Path $script:CaseHome '.copilot/AGENTS.md') -Value 'do not touch'
        Set-Content -LiteralPath (Join-Path $script:CaseHome 'private/keep.txt') -Value 'private'

        Invoke-GlobalBootstrap -HomePath $script:CaseHome -RepositoryRoot $script:RepositoryRoot -Confirm:$false

        Test-ApmGeneratedFile -Path (Join-Path $script:CaseHome '.codex/AGENTS.md') | Should-BeTrue
        Test-ApmGeneratedFile -Path (Join-Path $script:CaseHome '.copilot/copilot-instructions.md') | Should-BeTrue
        Get-Content -LiteralPath (Join-Path $script:CaseHome '.codex/config.toml') -Raw |
            Should-MatchString 'project_doc_max_bytes = 90001'
        Get-Content -LiteralPath (Join-Path $script:CaseHome '.copilot/AGENTS.md') -Raw |
            Should-MatchString 'do not touch'
        Get-Content -LiteralPath (Join-Path $script:CaseHome 'private/keep.txt') -Raw |
            Should-MatchString 'private'
        Test-DirectoryContentEqual -ReferencePath (Join-Path $script:RepositoryRoot '.apm') `
            -DifferencePath (Join-Path $script:CaseHome '.apm/.apm') | Should-BeTrue
        foreach ($skillName in $script:ManagedSkills) {
            Test-Path -LiteralPath (Join-Path $script:CaseHome ".agents/skills/$skillName") -PathType Container |
                Should-BeTrue
        }
        $snapshot = @(Get-ChildItem -LiteralPath (
                Join-Path $script:CaseHome '.apm/backups/agent-engineering-baseline'
            ) -Directory)[0]
        @([System.IO.File]::ReadAllLines((Join-Path $snapshot.FullName 'inventory.tsv'))).Count |
            Should-Be 19
        Get-Content -LiteralPath (Join-Path $snapshot.FullName 'originally-absent.txt') -Raw |
            Should-MatchString '.agents/skills/msgraph'
        Get-Content -LiteralPath (Join-Path $script:CaseHome '.fake-command.log') -Raw |
            Should-MatchString 'apm install --global --frozen'
    }

    It 'removes exact MCP entries and is idempotent on rerun' {
        Invoke-GlobalBootstrap -HomePath $script:CaseHome -RepositoryRoot $script:RepositoryRoot -Confirm:$false
        Set-DefaultMcpState -HomePath $script:CaseHome
        Invoke-GlobalBootstrap -HomePath $script:CaseHome -RepositoryRoot $script:RepositoryRoot -Confirm:$false

        $configPath = Join-Path $script:CaseHome '.codex/config.toml'
        @([System.IO.File]::ReadAllLines($configPath) | Where-Object {
                $_ -ceq '[mcp_servers.github-mcp-server]'
            }).Count | Should-Be 0
        $copilotConfig = Get-Content -LiteralPath (
            Join-Path $script:CaseHome '.copilot/mcp-config.json'
        ) -Raw | ConvertFrom-Json
        ($null -eq $copilotConfig.mcpServers.PSObject.Properties['github-mcp-server']) |
            Should-BeTrue
        Get-Content -LiteralPath (Join-Path $script:CaseHome '.fake-command.log') -Raw |
            Should-MatchString 'codex mcp remove github-mcp-server'
        @(Get-ChildItem -LiteralPath (
                Join-Path $script:CaseHome '.apm/backups/agent-engineering-baseline'
            ) -Directory).Count | Should-Be 2
    }

    It 'rejects a customized MCP entry before mutation' {
        $null = New-Item -ItemType Directory -Path (Join-Path $script:CaseHome '.codex') -Force
        Set-Content -LiteralPath (Join-Path $script:CaseHome '.codex/config.toml') -Value 'sentinel'
        Set-DefaultMcpState -HomePath $script:CaseHome
        $customJson = $script:DefaultMcpJson.Replace(
            'https://api.githubcopilot.com/mcp/',
            'https://custom.example.invalid/mcp/'
        )
        Set-Content -LiteralPath (Join-Path $script:CaseHome '.fake-github-mcp.json') `
            -Value $customJson -Encoding UTF8

        {
            Invoke-GlobalBootstrap -HomePath $script:CaseHome -RepositoryRoot $script:RepositoryRoot -Confirm:$false
        } | Should-Throw -ExceptionMessage '*is customized; refusing to replace it*'

        Test-Path -LiteralPath (Join-Path $script:CaseHome '.apm/backups') | Should-BeFalse
        Get-Content -LiteralPath (Join-Path $script:CaseHome '.codex/config.toml') -Raw |
            Should-MatchString 'sentinel'
    }

    It 'rejects a customized Copilot MCP entry before mutation' {
        $copilotDirectory = Join-Path $script:CaseHome '.copilot'
        $null = New-Item -ItemType Directory -Path $copilotDirectory -Force
        $customJson = $script:DefaultCopilotMcpJson.Replace(
            'https://api.githubcopilot.com/mcp/',
            'https://custom.example.invalid/mcp/'
        )
        Set-Content -LiteralPath (Join-Path $copilotDirectory 'mcp-config.json') `
            -Value $customJson -Encoding UTF8

        {
            Invoke-GlobalBootstrap -HomePath $script:CaseHome `
                -RepositoryRoot $script:RepositoryRoot -Confirm:$false
        } | Should-Throw -ExceptionMessage '*Copilot MCP entry*customized*'

        Test-Path -LiteralPath (Join-Path $script:CaseHome '.apm/backups') | Should-BeFalse
    }

    It 'honors WhatIf without changing the profile' {
        $env:FAKE_APM_VERSION = '0.0.1'
        Invoke-GlobalBootstrap -HomePath $script:CaseHome -RepositoryRoot $script:RepositoryRoot -WhatIf

        Test-Path -LiteralPath (Join-Path $script:CaseHome '.apm') | Should-BeFalse
        Get-Content -LiteralPath (Join-Path $script:CaseHome '.fake-command.log') -Raw |
            Should-NotMatchString 'apm install'
    }

    It 'stops before profile mutation for a newer CLI' {
        $env:FAKE_APM_VERSION = '999.999.999'

        {
            Invoke-GlobalBootstrap -HomePath $script:CaseHome `
                -RepositoryRoot $script:RepositoryRoot -Confirm:$false
        } | Should-Throw -ExceptionMessage '*newer than pinned baseline*'

        Test-Path -LiteralPath (Join-Path $script:CaseHome '.apm/backups') | Should-BeFalse
    }

    It 'fails before profile mutation when the installer download fails' {
        $env:FAKE_APM_VERSION = '0.0.1'
        Mock Invoke-WebRequest { throw 'download failed' }

        {
            Invoke-GlobalBootstrap -HomePath $script:CaseHome `
                -RepositoryRoot $script:RepositoryRoot -Confirm:$false
        } | Should-Throw -ExceptionMessage '*download failed*'

        Test-Path -LiteralPath (Join-Path $script:CaseHome '.apm/backups') | Should-BeFalse
    }

    It 'refuses a tampered installer before profile mutation' {
        $env:FAKE_APM_VERSION = '0.0.1'
        Mock Invoke-WebRequest { Set-Content -LiteralPath $OutFile -Value 'tampered installer' }

        {
            Invoke-GlobalBootstrap -HomePath $script:CaseHome `
                -RepositoryRoot $script:RepositoryRoot -Confirm:$false
        } | Should-Throw -ExceptionMessage '*does not match the pinned SHA256 checksum*'

        Test-Path -LiteralPath (Join-Path $script:CaseHome '.apm/backups') | Should-BeFalse
    }

    It 'rejects a reparse-point target before mutation' {
        $outsidePath = Join-Path $script:CaseRoot 'outside'
        $null = New-Item -ItemType Directory -Path $outsidePath -Force
        Set-Content -LiteralPath (Join-Path $outsidePath 'sentinel') -Value 'outside'
        $codexPath = Join-Path $script:CaseHome '.codex'

        if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) {
            & cmd.exe /d /c "mklink /J `"$codexPath`" `"$outsidePath`"" | Out-Null
        }
        else {
            $null = New-Item -ItemType SymbolicLink -Path $codexPath -Target $outsidePath
        }

        {
            Invoke-GlobalBootstrap -HomePath $script:CaseHome -RepositoryRoot $script:RepositoryRoot -Confirm:$false
        } | Should-Throw -ExceptionMessage '*reparse point*'

        Get-Content -LiteralPath (Join-Path $outsidePath 'sentinel') -Raw | Should-MatchString 'outside'
        Test-Path -LiteralPath (Join-Path $script:CaseHome '.apm/backups') | Should-BeFalse
    }

    It 'restores the complete snapshot after <_> fails' -ForEach $nativeFailureStages {
        Initialize-OldProfile -HomePath $script:CaseHome
        $expected = Get-ProfileFingerprint -HomePath $script:CaseHome
        if ($_ -ceq 'codex-remove') {
            $env:FAKE_CODEX_FAIL_REMOVE = '1'
        }
        else {
            $env:FAKE_APM_FAIL_STAGE = $_
        }

        {
            Invoke-GlobalBootstrap -HomePath $script:CaseHome -RepositoryRoot $script:RepositoryRoot -Confirm:$false
        } | Should-Throw

        $actual = Get-ProfileFingerprint -HomePath $script:CaseHome
        Compare-ProfileFingerprint -Reference $expected -Difference $actual | Should-BeTrue
        $snapshotBase = Join-Path $script:CaseHome '.apm/backups/agent-engineering-baseline'
        Test-Path -LiteralPath $snapshotBase -PathType Container | Should-BeTrue
        Get-Content -LiteralPath (Join-Path $script:CaseHome '.copilot/AGENTS.md') -Raw |
            Should-MatchString 'untouched copilot agents'
    }
}

Describe 'Repository invariants' {
    It 'pins the APM CLI and both installer checksums' {
        $version = ([System.IO.File]::ReadAllLines(
                (Join-Path $script:RepositoryRoot '.apm-version')
            )[0]).Trim()
        $version | Should-MatchString '^\d+\.\d+\.\d+$'

        $lines = @([System.IO.File]::ReadAllLines(
                (Join-Path $script:RepositoryRoot '.apm-installer-checksums')
            ))
        foreach ($name in @('install.sh', 'install.ps1')) {
            $pattern = '^[0-9a-f]{64}  ' + [regex]::Escape($name) + '$'
            @($lines | Where-Object { $_ -cmatch $pattern }).Count | Should-Be 1
        }
    }

    It 'commits a lockfile with no GitHub MCP dependency' {
        $lockfilePath = Join-Path $script:RepositoryRoot 'apm.lock.yaml'
        Test-Path -LiteralPath $lockfilePath -PathType Leaf | Should-BeTrue
        [System.IO.File]::ReadAllText($lockfilePath) |
            Should-NotMatchString 'io\.github\.github/github-mcp-server'
    }

    It 'keeps the project manifest and generated artifacts free of the GitHub MCP' {
        [System.IO.File]::ReadAllText((Join-Path $script:RepositoryRoot 'apm.yml')) |
            Should-NotMatchString 'github-mcp-server'
        Test-Path -LiteralPath (Join-Path $script:RepositoryRoot '.codex/config.toml') |
            Should-BeFalse
        Test-Path -LiteralPath (Join-Path $script:RepositoryRoot '.vscode/mcp.json') |
            Should-BeFalse
    }

    It 'declares an explicit ref for every APM dependency' {
        $manifest = [System.IO.File]::ReadAllLines((Join-Path $script:RepositoryRoot 'apm.yml'))
        $references = @($manifest | Where-Object { $_ -match '^\s+-\s+[A-Za-z0-9._/-]+#\S+$' })
        $references.Count | Should-Be 5
    }

    It 'pins every GitHub Action to a full commit SHA' {
        $workflowLines = Get-Content (Join-Path $script:RepositoryRoot '.github/workflows/*.yml')
        $usesLines = @($workflowLines | Where-Object { $_ -match '^\s+(?:-\s+)?uses:' })
        $usesLines.Count | Should-BeGreaterThan 0
        foreach ($line in $usesLines) { $line | Should-MatchString '@[0-9a-f]{40}(\s|$)' }
    }

    It 'keeps the local Pester 6 guidance project agnostic' {
        $path = Join-Path $script:RepositoryRoot '.apm/skills/powershell-pester-6/SKILL.md'
        $projectMarker = -join ([char[]](70, 65, 67, 84))
        [System.IO.File]::ReadAllText($path).Contains($projectMarker) | Should-BeFalse
    }
}
