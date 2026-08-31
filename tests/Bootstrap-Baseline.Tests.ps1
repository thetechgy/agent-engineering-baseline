<#
.SYNOPSIS
No-network Pester tests for scripts/Bootstrap-Baseline.ps1.

.DESCRIPTION
Each case copies the bootstrap into a sandbox (private pin file, PATH that
exposes only a stub apm executable, mocked installer download) and asserts
exactly which native APM commands the bootstrap runs. Compatible with
PowerShell 7 and Windows PowerShell 5.1.
#>

BeforeAll {
    $script:repoRoot = Split-Path -Parent $PSScriptRoot
    $script:onWindows = [System.IO.Path]::DirectorySeparatorChar -eq '\'

    function New-BootstrapSandbox {
        [Diagnostics.CodeAnalysis.SuppressMessageAttribute(
            'PSUseShouldProcessForStateChangingFunctions', '',
            Justification = 'Creates throwaway test fixtures only.')]
        [CmdletBinding()]
        param([string]$Pin = '0.29.0')

        $root = Join-Path ([IO.Path]::GetTempPath()) "bootstrap-pester-$([Guid]::NewGuid().ToString('N'))"
        New-Item -ItemType Directory -Path (Join-Path $root 'scripts') -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $root 'bin') -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $script:repoRoot 'scripts/Bootstrap-Baseline.ps1') `
            -Destination (Join-Path $root 'scripts/Bootstrap-Baseline.ps1')
        if ($Pin) {
            Set-Content -LiteralPath (Join-Path $root '.apm-version') -Value $Pin
        }
        [pscustomobject]@{
            Root      = $root
            Script    = Join-Path $root 'scripts/Bootstrap-Baseline.ps1'
            BinDir    = Join-Path $root 'bin'
            CallLog   = Join-Path $root 'calls.log'
            StateFile = Join-Path $root 'apm-version'
        }
    }

    # Writes a stub apm executable that records invocations (and $env:VERSION)
    # to the sandbox call log, reports the version in the sandbox state file,
    # and optionally upgrades or fails on self-update.
    function New-ApmStub {
        [Diagnostics.CodeAnalysis.SuppressMessageAttribute(
            'PSUseShouldProcessForStateChangingFunctions', '',
            Justification = 'Creates throwaway test fixtures only.')]
        [CmdletBinding()]
        param(
            [Parameter(Mandatory)]$Sandbox,
            [Parameter(Mandatory)][string]$Version,
            [string]$VersionAfterSelfUpdate,
            [switch]$SelfUpdateFails
        )

        Set-Content -LiteralPath $Sandbox.StateFile -Value $Version
        $after = if ($VersionAfterSelfUpdate) { $VersionAfterSelfUpdate } else { '' }
        if ($script:onWindows) {
            $lines = @(
                '@echo off'
                "echo apm %* >> `"$($Sandbox.CallLog)`""
                "echo VERSION_ENV=%VERSION% >> `"$($Sandbox.CallLog)`""
                'if "%1"=="--version" ('
                "  for /f `"usebackq delims=`" %%v in (`"$($Sandbox.StateFile)`") do echo Agent Package Manager (APM) CLI version %%v (test)"
                ')'
                'if "%1"=="self-update" ('
                $(if ($SelfUpdateFails) { '  exit /b 1' }
                    elseif ($after) { "  echo $after> `"$($Sandbox.StateFile)`"" }
                    else { '  rem no-op' })
                ')'
                'exit /b 0'
            )
            Set-Content -LiteralPath (Join-Path $Sandbox.BinDir 'apm.cmd') -Value ($lines -join "`r`n")
        }
        else {
            $lines = @(
                '#!/usr/bin/env bash'
                "log='$($Sandbox.CallLog)'"
                "state='$($Sandbox.StateFile)'"
                'printf ''apm %s\n'' "$*" >> "$log"'
                'printf ''VERSION_ENV=%s\n'' "${VERSION:-}" >> "$log"'
                'case "$1" in'
                '    --version)'
                '        printf ''Agent Package Manager (APM) CLI version %s (test)\n'' "$(cat "$state")" ;;'
                '    self-update)'
                $(if ($SelfUpdateFails) { '        exit 1 ;;' }
                    elseif ($after) { "        printf '%s\n' '$after' > `"`$state`" ;;" }
                    else { '        : ;;' })
                'esac'
                'exit 0'
            )
            $stubPath = Join-Path $Sandbox.BinDir 'apm'
            Set-Content -LiteralPath $stubPath -Value ($lines -join "`n")
            & chmod +x $stubPath
        }
    }

    function Invoke-Bootstrap {
        param(
            [Parameter(Mandatory)]$Sandbox,
            [hashtable]$Parameters = @{},
            [switch]$IncludeStubPath
        )

        $previousPath = $env:PATH
        $systemPath = if ($script:onWindows) { $env:SystemRoot + ';' + $env:SystemRoot + '\System32' }
        else { '/usr/bin:/bin' }
        try {
            $env:PATH = if ($IncludeStubPath) {
                $Sandbox.BinDir + [IO.Path]::PathSeparator + $systemPath
            }
            else { $systemPath }
            & $Sandbox.Script @Parameters 2>&1 | Out-String
        }
        finally {
            $env:PATH = $previousPath
        }
    }

    function Get-CallLog {
        param([Parameter(Mandatory)]$Sandbox)
        if (Test-Path -LiteralPath $Sandbox.CallLog) {
            (Get-Content -LiteralPath $Sandbox.CallLog) -join "`n"
        }
        else { '' }
    }
}

AfterAll {
    Get-ChildItem -LiteralPath ([IO.Path]::GetTempPath()) -Filter 'bootstrap-pester-*' -Directory -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

Describe 'Bootstrap-Baseline pin handling' {
    It 'fails on an invalid pin' {
        $sandbox = New-BootstrapSandbox -Pin 'not-a-version'
        New-ApmStub -Sandbox $sandbox -Version '0.29.0'
        { Invoke-Bootstrap -Sandbox $sandbox -IncludeStubPath } |
            Should-Throw -ExceptionMessage '*must contain a semantic version*'
    }

    It 'fails when the pin file is missing' {
        $sandbox = New-BootstrapSandbox -Pin $null
        New-ApmStub -Sandbox $sandbox -Version '0.29.0'
        { Invoke-Bootstrap -Sandbox $sandbox -IncludeStubPath } |
            Should-Throw -ExceptionMessage '*.apm-version not found*'
    }
}

Describe 'Bootstrap-Baseline CLI provisioning' {
    It 'downloads and runs the pinned installer when the CLI is missing' {
        $sandbox = New-BootstrapSandbox
        $installerLog = Join-Path $sandbox.Root 'installer.log'
        Mock Invoke-WebRequest {
            Set-Content -LiteralPath $OutFile -Value (
                "Set-Content -LiteralPath '$installerLog' -Value (`"uri=$Uri version=`" + `$env:VERSION)"
            )
        }
        # The stub installer installs nothing, so the bootstrap must fail its
        # post-install check with actionable guidance.
        { Invoke-Bootstrap -Sandbox $sandbox } |
            Should-Throw -ExceptionMessage '*not runnable from this session*'
        Should-Invoke Invoke-WebRequest -Times 1 -Exactly -Scope It -ParameterFilter {
            $Uri -eq 'https://raw.githubusercontent.com/microsoft/apm/v0.29.0/install.ps1'
        }
        Get-Content -LiteralPath $installerLog |
            Should-Be 'uri=https://raw.githubusercontent.com/microsoft/apm/v0.29.0/install.ps1 version=v0.29.0'
    }

    It 'does not download anything under -WhatIf when the CLI is missing' {
        $sandbox = New-BootstrapSandbox
        Mock Invoke-WebRequest { throw 'network access attempted' }
        Invoke-Bootstrap -Sandbox $sandbox -Parameters @{ WhatIf = $true }
        Should-NotInvoke Invoke-WebRequest -Scope It
    }

    It 'upgrades an older CLI via pinned apm self-update' {
        $sandbox = New-BootstrapSandbox
        New-ApmStub -Sandbox $sandbox -Version '0.28.0' -VersionAfterSelfUpdate '0.29.0'
        Invoke-Bootstrap -Sandbox $sandbox -IncludeStubPath
        $log = Get-CallLog -Sandbox $sandbox
        $log | Should-MatchString 'apm\s+self-update'
        $log | Should-MatchString 'VERSION_ENV=v0\.29\.0'
    }

    It 'surfaces a self-update failure with remediation guidance' {
        $sandbox = New-BootstrapSandbox
        New-ApmStub -Sandbox $sandbox -Version '0.28.0' -SelfUpdateFails
        { Invoke-Bootstrap -Sandbox $sandbox -IncludeStubPath } |
            Should-Throw -ExceptionMessage '*apm self-update failed*'
    }

    It 'fails when the CLI version still mismatches after upgrade' {
        $sandbox = New-BootstrapSandbox
        New-ApmStub -Sandbox $sandbox -Version '0.28.0'
        { Invoke-Bootstrap -Sandbox $sandbox -IncludeStubPath } |
            Should-Throw -ExceptionMessage '*expected v0.29.0*'
    }

    It 'is a no-op when the CLI already matches the pin' {
        $sandbox = New-BootstrapSandbox
        New-ApmStub -Sandbox $sandbox -Version '0.29.0'
        Invoke-Bootstrap -Sandbox $sandbox -IncludeStubPath
        $log = Get-CallLog -Sandbox $sandbox
        $log | Should-NotMatchString 'self-update'
        $log | Should-MatchString 'apm\s+install\s+--global'
    }

    It 'warns and continues when the CLI is newer than the pin' {
        $sandbox = New-BootstrapSandbox
        New-ApmStub -Sandbox $sandbox -Version '0.30.0'
        $output = Invoke-Bootstrap -Sandbox $sandbox -IncludeStubPath 3>&1
        "$output" | Should-MatchString 'newer than the pinned'
        (Get-CallLog -Sandbox $sandbox) | Should-MatchString 'apm\s+install\s+--global'
    }
}

Describe 'Bootstrap-Baseline deployment modes' {
    It 'installs globally and compiles root contexts by default' {
        $sandbox = New-BootstrapSandbox
        New-ApmStub -Sandbox $sandbox -Version '0.29.0'
        Invoke-Bootstrap -Sandbox $sandbox -IncludeStubPath
        $log = Get-CallLog -Sandbox $sandbox
        $log | Should-MatchString 'apm\s+install\s+--global\s+thetechgy/agent-engineering-baseline#main'
        $log | Should-MatchString 'apm\s+compile\s+--global'
    }

    It 'installs into the current project in Repo scope' {
        $sandbox = New-BootstrapSandbox
        New-ApmStub -Sandbox $sandbox -Version '0.29.0'
        Invoke-Bootstrap -Sandbox $sandbox -IncludeStubPath -Parameters @{ Scope = 'Repo' }
        $log = Get-CallLog -Sandbox $sandbox
        $log | Should-MatchString 'apm\s+install\s+--target\s+codex,copilot\s+thetechgy/agent-engineering-baseline#main'
        $log | Should-NotMatchString 'install\s+--global'
        $log | Should-MatchString 'apm\s+compile'
        $log | Should-NotMatchString 'compile\s+--global'
    }

    It 'honors the BASELINE_PACKAGE_REF override' {
        $sandbox = New-BootstrapSandbox
        New-ApmStub -Sandbox $sandbox -Version '0.29.0'
        $env:BASELINE_PACKAGE_REF = 'local/pkg'
        try {
            Invoke-Bootstrap -Sandbox $sandbox -IncludeStubPath
        }
        finally {
            Remove-Item Env:BASELINE_PACKAGE_REF -ErrorAction SilentlyContinue
        }
        (Get-CallLog -Sandbox $sandbox) | Should-MatchString 'apm\s+install\s+--global\s+local/pkg'
    }

    It 'makes no APM calls that mutate state under -WhatIf' {
        $sandbox = New-BootstrapSandbox
        New-ApmStub -Sandbox $sandbox -Version '0.28.0' -VersionAfterSelfUpdate '0.29.0'
        Invoke-Bootstrap -Sandbox $sandbox -IncludeStubPath -Parameters @{ WhatIf = $true }
        $log = Get-CallLog -Sandbox $sandbox
        $log | Should-NotMatchString 'self-update'
        $log | Should-NotMatchString 'apm\s+install'
        $log | Should-NotMatchString 'apm\s+compile'
    }
}
