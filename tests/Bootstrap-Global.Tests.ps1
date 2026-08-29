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
[Diagnostics.CodeAnalysis.SuppressMessageAttribute(
    'PSUseDeclaredVarsMoreThanAssignments',
    'isWindowsPlatform',
    Justification = 'Pester consumes this discovery-time variable through Describe -Skip.'
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
    $isWindowsPlatform = [Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT
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

    It 'extracts a strict pinned checksum' {
        $checksumPath = Join-Path $TestDrive 'checksums'
        Set-Content -LiteralPath $checksumPath -Value @(
            ('a' * 64) + '  install.sh'
            ('b' * 64) + '  apm-windows-x86_64.zip'
        )
        Get-PinnedChecksum -ChecksumPath $checksumPath -FileName 'apm-windows-x86_64.zip' |
            Should-Be ('b' * 64)
    }

    It 'rejects duplicate, uppercase, or missing checksum entries' {
        $checksumPath = Join-Path $TestDrive 'invalid-checksums'
        Set-Content -LiteralPath $checksumPath -Value @(
            ('a' * 64) + '  duplicate'
            ('b' * 64) + '  duplicate'
            ('C' * 64) + '  uppercase'
        )

        { Get-PinnedChecksum -ChecksumPath $checksumPath -FileName 'duplicate' } |
            Should-Throw -ExceptionMessage '*exactly one lowercase*'
        { Get-PinnedChecksum -ChecksumPath $checksumPath -FileName 'uppercase' } |
            Should-Throw -ExceptionMessage '*exactly one lowercase*'
        { Get-PinnedChecksum -ChecksumPath $checksumPath -FileName 'missing' } |
            Should-Throw -ExceptionMessage '*exactly one lowercase*'
    }

    It 'verifies a file against its pinned digest before use' {
        $payloadPath = Join-Path $TestDrive 'payload.bin'
        $checksumPath = Join-Path $TestDrive 'payload-checksums'
        Set-Content -LiteralPath $payloadPath -Value 'reviewed payload' -NoNewline
        $hash = (Get-FileHash -LiteralPath $payloadPath -Algorithm SHA256).Hash.ToLowerInvariant()
        Set-Content -LiteralPath $checksumPath -Value "$hash  payload.bin"

        Assert-PinnedFileChecksum -Path $payloadPath -ChecksumPath $checksumPath `
            -FileName 'payload.bin'
        Set-Content -LiteralPath $payloadPath -Value 'tampered payload' -NoNewline
        { Assert-PinnedFileChecksum -Path $payloadPath -ChecksumPath $checksumPath `
                -FileName 'payload.bin' } | Should-Throw -ExceptionMessage '*refusing to execute*'
    }

    It 'honors APM_INSTALL_DIR in the native Windows layout adapter' {
        $previousInstallDirectory = $env:APM_INSTALL_DIR
        try {
            $env:APM_INSTALL_DIR = Join-Path $TestDrive 'custom/bin'
            $layout = Get-ApmWindowsLayout -Version ([version]'1.2.3')

            $layout.BinDirectory | Should-Be ([System.IO.Path]::GetFullPath($env:APM_INSTALL_DIR))
            $layout.ReleaseDirectory | Should-Be (
                Join-Path (Split-Path -Parent $layout.BinDirectory) 'releases/v1.2.3'
            )
        }
        finally {
            $env:APM_INSTALL_DIR = $previousInstallDirectory
        }
    }

    It 'keeps LOCALAPPDATA literal in the generated Windows command shim' {
        $previousLocalAppData = $env:LOCALAPPDATA
        try {
            $env:LOCALAPPDATA = Join-Path $TestDrive 'local-app-data'
            $executablePath = Join-Path $env:LOCALAPPDATA 'apm/releases/v1.2.3/apm.exe'

            $shim = ConvertTo-ApmCommandShimContent -ExecutablePath $executablePath

            $shim | Should-MatchString '%LOCALAPPDATA%\\apm'
            $shim | Should-NotMatchString ([regex]::Escape($env:LOCALAPPDATA))
        }
        finally {
            $env:LOCALAPPDATA = $previousLocalAppData
        }
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
        $script:OriginalApmReintroduce = $env:FAKE_APM_REINTRODUCE_COPILOT_MCP
        $script:OriginalApmWriteUninspectable = $env:FAKE_APM_WRITE_UNINSPECTABLE_COPILOT_MCP
        $script:OriginalCodexGetFailure = $env:FAKE_CODEX_FAIL_GET
        $script:OriginalCodexFailure = $env:FAKE_CODEX_FAIL_REMOVE
        $script:OriginalLocalAppData = $env:LOCALAPPDATA
        $script:OriginalApmInstallDirectory = $env:APM_INSTALL_DIR
        $pathSeparator = [System.IO.Path]::PathSeparator
        $env:PATH = "$($script:CaseBin)$pathSeparator$($env:PATH)"
        $env:FAKE_HOME = $script:CaseHome
        $env:FAKE_APM_VERSION = $script:PinnedVersion
        $env:FAKE_APM_FAIL_STAGE = $null
        $env:FAKE_APM_REINTRODUCE_COPILOT_MCP = $null
        $env:FAKE_APM_WRITE_UNINSPECTABLE_COPILOT_MCP = $null
        $env:FAKE_CODEX_FAIL_GET = $null
        $env:FAKE_CODEX_FAIL_REMOVE = $null
        $env:LOCALAPPDATA = Join-Path $script:CaseRoot 'local-app-data'
        $env:APM_INSTALL_DIR = $null
        Mock Assert-PinnedFileChecksum {
            if ($Path.StartsWith($script:CaseBin, [StringComparison]::OrdinalIgnoreCase)) {
                return
            }
            $expectedHash = Get-PinnedChecksum -ChecksumPath $ChecksumPath -FileName $FileName
            $actualHash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($actualHash -cne $expectedHash) {
                throw "$FileName does not match the pinned SHA256 checksum; refusing to execute downloaded code."
            }
        }
    }

    AfterEach {
        $env:PATH = $script:OriginalPath
        $env:FAKE_HOME = $script:OriginalFakeHome
        $env:FAKE_APM_VERSION = $script:OriginalFakeApmVersion
        $env:FAKE_APM_FAIL_STAGE = $script:OriginalApmFailure
        $env:FAKE_APM_REINTRODUCE_COPILOT_MCP = $script:OriginalApmReintroduce
        $env:FAKE_APM_WRITE_UNINSPECTABLE_COPILOT_MCP = $script:OriginalApmWriteUninspectable
        $env:FAKE_CODEX_FAIL_GET = $script:OriginalCodexGetFailure
        $env:FAKE_CODEX_FAIL_REMOVE = $script:OriginalCodexFailure
        $env:LOCALAPPDATA = $script:OriginalLocalAppData
        $env:APM_INSTALL_DIR = $script:OriginalApmInstallDirectory
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

    It 'removes an exact Codex MCP entry when Copilot configuration is absent' {
        Set-DefaultMcpState -HomePath $script:CaseHome
        Remove-Item -LiteralPath (Join-Path $script:CaseHome '.copilot/mcp-config.json') -Force

        Invoke-GlobalBootstrap -HomePath $script:CaseHome -RepositoryRoot $script:RepositoryRoot -Confirm:$false

        Test-Path -LiteralPath (Join-Path $script:CaseHome '.fake-github-mcp.json') |
            Should-BeFalse
        Get-Content -LiteralPath (Join-Path $script:CaseHome '.fake-command.log') -Raw |
            Should-MatchString 'codex mcp remove github-mcp-server'
    }

    It 'fails before mutation when Codex MCP inspection returns an unexpected error' {
        Set-DefaultMcpState -HomePath $script:CaseHome
        $env:FAKE_CODEX_FAIL_GET = '1'

        {
            Invoke-GlobalBootstrap -HomePath $script:CaseHome `
                -RepositoryRoot $script:RepositoryRoot -Confirm:$false
        } | Should-Throw -ExceptionMessage '*Unable to inspect the existing Codex MCP entry*'

        Test-Path -LiteralPath (Join-Path $script:CaseHome '.apm/backups') | Should-BeFalse
        Test-Path -LiteralPath (Join-Path $script:CaseHome '.fake-github-mcp.json') |
            Should-BeTrue
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

    It 'rejects an escaped customized Copilot MCP key before mutation' {
        $copilotDirectory = Join-Path $script:CaseHome '.copilot'
        $configPath = Join-Path $copilotDirectory 'mcp-config.json'
        $null = New-Item -ItemType Directory -Path $copilotDirectory -Force
        $customJson = $script:DefaultCopilotMcpJson.Replace(
            '"github-mcp-server"',
            '"github-\u006dcp-server"'
        )
        $customJson = $customJson.Replace(
            'https://api.githubcopilot.com/mcp/',
            'https://custom.example.invalid/mcp/'
        )
        Set-Content -LiteralPath $configPath -Value $customJson -Encoding UTF8
        $originalHash = (Get-FileHash -LiteralPath $configPath -Algorithm SHA256).Hash

        {
            Invoke-GlobalBootstrap -HomePath $script:CaseHome `
                -RepositoryRoot $script:RepositoryRoot -Confirm:$false
        } | Should-Throw -ExceptionMessage '*Copilot MCP entry*customized*'

        (Get-FileHash -LiteralPath $configPath -Algorithm SHA256).Hash | Should-Be $originalHash
        Test-Path -LiteralPath (Join-Path $script:CaseHome '.apm/backups') | Should-BeFalse
    }

    It 'removes an escaped exact-default Copilot MCP key and preserves unrelated servers' {
        $copilotDirectory = Join-Path $script:CaseHome '.copilot'
        $configPath = Join-Path $copilotDirectory 'mcp-config.json'
        $null = New-Item -ItemType Directory -Path $copilotDirectory -Force
        $configJson = @'
{
  "mcpServers": {
    "github-\u006dcp-server": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/",
      "tools": ["*"],
      "id": "",
      "headers": {},
      "bearer_token_env_var": "GITHUB_TOKEN"
    },
    "other-server": {
      "type": "stdio",
      "command": "keep-me"
    }
  },
  "inputs": [
    { "id": "keep-input" }
  ]
}
'@
        Set-Content -LiteralPath $configPath -Value $configJson -Encoding UTF8

        Invoke-GlobalBootstrap -HomePath $script:CaseHome `
            -RepositoryRoot $script:RepositoryRoot -Confirm:$false

        $configuration = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
        $servers = (Get-CaseSensitiveJsonProperty `
                -InputObject $configuration -Name 'mcpServers').Value
        $null -eq (Get-CaseSensitiveJsonProperty `
                -InputObject $servers -Name 'github-mcp-server') | Should-BeTrue
        (Get-CaseSensitiveJsonProperty -InputObject $servers -Name 'other-server').Value.command |
            Should-Be 'keep-me'
        $configuration.inputs[0].id | Should-Be 'keep-input'
    }

    It 'leaves unrelated and case-variant Copilot MCP keys byte-for-byte unchanged' {
        $copilotDirectory = Join-Path $script:CaseHome '.copilot'
        $configPath = Join-Path $copilotDirectory 'mcp-config.json'
        $null = New-Item -ItemType Directory -Path $copilotDirectory -Force
        $configJsonValues = @(
            '{"mcpServers":{"GitHub-Mcp-Server":{"type":"stdio","command":"keep-case"},"other-server":{"type":"stdio","command":"keep-other"}}}'
            '{"McpServers":{"github-mcp-server":{"type":"stdio","command":"keep-container-case"}}}'
        )
        foreach ($configJson in $configJsonValues) {
            [System.IO.File]::WriteAllText($configPath, $configJson)
            $originalHash = (Get-FileHash -LiteralPath $configPath -Algorithm SHA256).Hash

            Invoke-GlobalBootstrap -HomePath $script:CaseHome `
                -RepositoryRoot $script:RepositoryRoot -Confirm:$false

            (Get-FileHash -LiteralPath $configPath -Algorithm SHA256).Hash | Should-Be $originalHash
        }
    }

    It 'rejects malformed or semantically uninspectable Copilot JSON before mutation' {
        $copilotDirectory = Join-Path $script:CaseHome '.copilot'
        $configPath = Join-Path $copilotDirectory 'mcp-config.json'
        $null = New-Item -ItemType Directory -Path $copilotDirectory -Force

        foreach ($configJson in @('{"mcpServers":', '{"mcpServers":[]}')) {
            [System.IO.File]::WriteAllText($configPath, $configJson)
            $originalHash = (Get-FileHash -LiteralPath $configPath -Algorithm SHA256).Hash

            {
                Invoke-GlobalBootstrap -HomePath $script:CaseHome `
                    -RepositoryRoot $script:RepositoryRoot -Confirm:$false
            } | Should-Throw -ExceptionMessage '*parse or semantically inspect*'

            (Get-FileHash -LiteralPath $configPath -Algorithm SHA256).Hash | Should-Be $originalHash
            Test-Path -LiteralPath (Join-Path $script:CaseHome '.apm/backups') | Should-BeFalse
        }
    }

    It 'rolls back when APM reintroduces an escaped Copilot MCP key after preflight' {
        Initialize-OldProfile -HomePath $script:CaseHome
        $configPath = Join-Path $script:CaseHome '.copilot/mcp-config.json'
        [System.IO.File]::WriteAllText(
            $configPath,
            '{"mcpServers":{"other-server":{"type":"stdio","command":"keep-me"}}}'
        )
        $expected = Get-ProfileFingerprint -HomePath $script:CaseHome
        $env:FAKE_APM_REINTRODUCE_COPILOT_MCP = '1'

        {
            Invoke-GlobalBootstrap -HomePath $script:CaseHome `
                -RepositoryRoot $script:RepositoryRoot -Confirm:$false
        } | Should-Throw -ExceptionMessage '*remains in Copilot after deployment*'

        $actual = Get-ProfileFingerprint -HomePath $script:CaseHome
        Compare-ProfileFingerprint -Reference $expected -Difference $actual | Should-BeTrue
    }

    It 'rolls back when APM writes uninspectable Copilot JSON after preflight' {
        Initialize-OldProfile -HomePath $script:CaseHome
        $configPath = Join-Path $script:CaseHome '.copilot/mcp-config.json'
        [System.IO.File]::WriteAllText(
            $configPath,
            '{"mcpServers":{"other-server":{"type":"stdio","command":"keep-me"}}}'
        )
        $expected = Get-ProfileFingerprint -HomePath $script:CaseHome
        $env:FAKE_APM_WRITE_UNINSPECTABLE_COPILOT_MCP = '1'

        {
            Invoke-GlobalBootstrap -HomePath $script:CaseHome `
                -RepositoryRoot $script:RepositoryRoot -Confirm:$false
        } | Should-Throw -ExceptionMessage '*parse or semantically inspect the Copilot MCP configuration*'

        $actual = Get-ProfileFingerprint -HomePath $script:CaseHome
        Compare-ProfileFingerprint -Reference $expected -Difference $actual | Should-BeTrue
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

    It 'rejects a reparse-point backup namespace before mutation' {
        $outsidePath = Join-Path $script:CaseRoot 'outside-backups'
        $null = New-Item -ItemType Directory -Path $outsidePath -Force
        Set-Content -LiteralPath (Join-Path $outsidePath 'sentinel') -Value 'outside'
        $backupRoot = Join-Path $script:CaseHome '.apm/backups'
        $null = New-Item -ItemType Directory -Path $backupRoot -Force
        $backupNamespace = Join-Path $backupRoot 'agent-engineering-baseline'

        if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) {
            & cmd.exe /d /c "mklink /J `"$backupNamespace`" `"$outsidePath`"" | Out-Null
        }
        else {
            $null = New-Item -ItemType SymbolicLink -Path $backupNamespace -Target $outsidePath
        }

        {
            Invoke-GlobalBootstrap -HomePath $script:CaseHome -RepositoryRoot $script:RepositoryRoot -Confirm:$false
        } | Should-Throw -ExceptionMessage '*reparse point*'

        Get-Content -LiteralPath (Join-Path $outsidePath 'sentinel') -Raw |
            Should-MatchString 'outside'
        @(Get-ChildItem -LiteralPath $outsidePath -Force).Count | Should-Be 1
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

Describe 'Windows secure APM promotion' -Skip:(-not $isWindowsPlatform) {
    BeforeEach {
        $script:WindowsInstallRoot = Join-Path $TestDrive ([Guid]::NewGuid().ToString('N'))
        $script:WindowsBin = Join-Path $script:WindowsInstallRoot 'bin'
        $script:PreviousWindowsInstallDirectory = $env:APM_INSTALL_DIR
        $env:APM_INSTALL_DIR = $script:WindowsBin
        $script:WindowsVersion = [version]'9.8.7'
        $script:WindowsLayout = Get-ApmWindowsLayout -Version $script:WindowsVersion

        $fixtureRoot = Join-Path $TestDrive ([Guid]::NewGuid().ToString('N'))
        $packageDirectory = Join-Path $fixtureRoot 'apm-windows-x86_64'
        $null = New-Item -ItemType Directory -Path $packageDirectory -Force
        $script:WindowsFixtureExecutable = Join-Path $packageDirectory 'apm.exe'
        $typeName = 'FakeApm' + [Guid]::NewGuid().ToString('N')
        $source = @"
using System;
public static class $typeName {
    public static int Main(string[] args) {
        Console.WriteLine("APM 9.8.7");
        return 0;
    }
}
"@
        Add-Type -TypeDefinition $source -OutputAssembly $script:WindowsFixtureExecutable `
            -OutputType ConsoleApplication
        $script:WindowsFixtureArchive = Join-Path $fixtureRoot 'apm-windows-x86_64.zip'
        Compress-Archive -LiteralPath $packageDirectory -DestinationPath $script:WindowsFixtureArchive
        $script:WindowsChecksumPath = Join-Path $fixtureRoot 'checksums'
        $archiveHash = (Get-FileHash -LiteralPath $script:WindowsFixtureArchive -Algorithm SHA256).Hash.ToLowerInvariant()
        $executableHash = (Get-FileHash -LiteralPath $script:WindowsFixtureExecutable -Algorithm SHA256).Hash.ToLowerInvariant()
        Set-Content -LiteralPath $script:WindowsChecksumPath -Value @(
            "$archiveHash  apm-windows-x86_64.zip"
            "$executableHash  apm-windows-x86_64/apm.exe"
        )

        Mock Invoke-WebRequest {
            Copy-Item -LiteralPath $script:WindowsFixtureArchive -Destination $OutFile
        }
        Mock Set-ApmUserPath {}
    }

    AfterEach {
        if ($null -ne $script:WindowsLayout) {
            foreach ($item in @(Get-ChildItem -LiteralPath $script:WindowsLayout.InstallRoot `
                        -Force -ErrorAction SilentlyContinue)) {
                if (Test-ReparsePoint -Item $item) {
                    [System.IO.Directory]::Delete($item.FullName)
                }
            }
        }
        $env:APM_INSTALL_DIR = $script:PreviousWindowsInstallDirectory
    }

    It 'promotes a verified bundle into the native release, junction, and shim layout' {
        $executable = Install-PinnedApmWindows -Version $script:WindowsVersion `
            -ChecksumPath $script:WindowsChecksumPath

        $executable | Should-Be $script:WindowsLayout.CurrentExecutable
        Test-Path -LiteralPath $script:WindowsLayout.ReleaseDirectory -PathType Container |
            Should-BeTrue
        Test-ReparsePoint -Item (Get-Item -LiteralPath $script:WindowsLayout.CurrentDirectory -Force) |
            Should-BeTrue
        Test-Path -LiteralPath $script:WindowsLayout.ShimPath -PathType Leaf | Should-BeTrue
        Assert-PinnedFileChecksum -Path $executable -ChecksumPath $script:WindowsChecksumPath `
            -FileName 'apm-windows-x86_64/apm.exe'
    }

    It 'rejects a current junction that targets outside the release root' {
        $outsidePath = Join-Path $TestDrive ([Guid]::NewGuid().ToString('N'))
        $null = New-Item -ItemType Directory -Path $outsidePath -Force
        $null = New-Item -ItemType Directory -Path $script:WindowsLayout.InstallRoot -Force
        $null = New-Item -ItemType Junction -Path $script:WindowsLayout.CurrentDirectory `
            -Target $outsidePath

        { Assert-ApmWindowsLayoutSafe -Layout $script:WindowsLayout } |
            Should-Throw -ExceptionMessage '*outside the releases directory*'
    }

    It 'restores the prior release and junction when current promotion fails' {
        $null = New-Item -ItemType Directory -Path $script:WindowsLayout.ReleaseDirectory -Force
        Set-Content -LiteralPath (Join-Path $script:WindowsLayout.ReleaseDirectory 'old.txt') `
            -Value 'old release'
        $null = New-Item -ItemType Directory -Path $script:WindowsLayout.BinDirectory -Force
        Set-Content -LiteralPath $script:WindowsLayout.ShimPath -Value 'old shim'
        $null = New-Item -ItemType Junction -Path $script:WindowsLayout.CurrentDirectory `
            -Target $script:WindowsLayout.ReleaseDirectory
        $script:PromotionFailureInjected = $false
        $script:PromotionFailureDestination = $script:WindowsLayout.CurrentDirectory
        Mock Move-Item {
            if (-not $script:PromotionFailureInjected) {
                $script:PromotionFailureInjected = $true
                throw 'promotion sentinel'
            }
            Microsoft.PowerShell.Management\Move-Item @PSBoundParameters
        } -ParameterFilter { $Destination -ceq $script:PromotionFailureDestination }

        { Install-PinnedApmWindows -Version $script:WindowsVersion `
                -ChecksumPath $script:WindowsChecksumPath } | Should-Throw

        Get-Content -LiteralPath (Join-Path $script:WindowsLayout.ReleaseDirectory 'old.txt') -Raw |
            Should-MatchString 'old release'
        Get-Content -LiteralPath $script:WindowsLayout.ShimPath -Raw |
            Should-MatchString 'old shim'
        $currentTarget = Get-ReparseTargetPath -Item (
            Get-Item -LiteralPath $script:WindowsLayout.CurrentDirectory -Force
        )
        $currentTarget | Should-Be $script:WindowsLayout.ReleaseDirectory
        @(Get-ChildItem -LiteralPath $script:WindowsLayout.InstallRoot -Force |
                Where-Object { $_.Name -match '\.(?:new|old)-' }).Count | Should-Be 0
    }
}

Describe 'Repository invariants' {
    It 'pins every supported APM CLI artifact with a unique lowercase checksum' {
        $version = ([System.IO.File]::ReadAllLines(
                (Join-Path $script:RepositoryRoot '.apm-version')
            )[0]).Trim()
        $version | Should-MatchString '^\d+\.\d+\.\d+$'

        $lines = @([System.IO.File]::ReadAllLines(
                (Join-Path $script:RepositoryRoot '.apm-checksums')
            ))
        $expectedNames = @(
            'install.sh'
            'apm-linux-arm64.tar.gz'
            'apm-linux-arm64/apm'
            'apm-linux-x86_64.tar.gz'
            'apm-linux-x86_64/apm'
            'apm-windows-x86_64.zip'
            'apm-windows-x86_64/apm.exe'
        )
        $lines.Count | Should-Be $expectedNames.Count
        foreach ($name in $expectedNames) {
            $pattern = '^[0-9a-f]{64}  ' + [regex]::Escape($name) + '$'
            @($lines | Where-Object { $_ -cmatch $pattern }).Count | Should-Be 1
        }
        @($lines | ForEach-Object { ($_ -split '  ', 2)[1] } | Sort-Object -Unique).Count |
            Should-Be $expectedNames.Count
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
