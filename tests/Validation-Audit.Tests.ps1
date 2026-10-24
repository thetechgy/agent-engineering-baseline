BeforeDiscovery {
    $script:AuditWindowsHost = $env:OS -ceq 'Windows_NT'
}

Describe 'Linux validation regeneration exit propagation' -Skip:$script:AuditWindowsHost {
    BeforeAll {
        $root = Join-Path $TestDrive 'repository'
        $scripts = New-Item -ItemType Directory -Path (Join-Path $root 'scripts') -Force
        $tests = New-Item -ItemType Directory -Path (Join-Path $root 'tests') -Force
        $script:AuditValidation = Join-Path $scripts.FullName 'Invoke-Validation.ps1'
        Copy-Item (Join-Path $PSScriptRoot '../scripts/Invoke-Validation.ps1') $script:AuditValidation
        [IO.File]::WriteAllText((Join-Path $tests.FullName 'bootstrap.sh'), "#!/bin/sh`nexit 0`n")
        & chmod +x (Join-Path $tests.FullName 'bootstrap.sh')
        $script:AuditExecutable = Join-Path $root 'apm-fixture'
        $script:AuditLog = Join-Path $root 'calls'
        $script:OldAuditApm = $env:APM_EXECUTABLE
        $script:OldFixtureStatus = $env:BASELINE_FIXTURE_AUDIT_STATUS
        $env:APM_EXECUTABLE = $script:AuditExecutable
        [IO.File]::WriteAllText($script:AuditExecutable, "#!/bin/sh`nexit 0`n")
        & chmod +x $script:AuditExecutable
        [IO.File]::WriteAllText((Join-Path $scripts.FullName 'apm_regeneration.py'), @'
import os
from pathlib import Path
import sys
Path(os.environ['BASELINE_FIXTURE_CALL_LOG']).write_text('\n'.join(sys.argv[1:]))
sys.exit(int(os.environ['BASELINE_FIXTURE_AUDIT_STATUS']))
'@)
        $script:OldFixtureCallLog = $env:BASELINE_FIXTURE_CALL_LOG
        $env:BASELINE_FIXTURE_CALL_LOG = $script:AuditLog
    }

    BeforeEach {
        Mock Invoke-Pester {
            [pscustomobject]@{ FailedCount = 0; FailedContainers = @(); Result = 'Passed' }
        }
        Mock Invoke-ScriptAnalyzer { @() }
        Mock shellcheck { throw 'ShellCheck reached' }
        Remove-Item $script:AuditLog -ErrorAction SilentlyContinue
    }

    AfterAll {
        $env:APM_EXECUTABLE = $script:OldAuditApm
        $env:BASELINE_FIXTURE_AUDIT_STATUS = $script:OldFixtureStatus
        $env:BASELINE_FIXTURE_CALL_LOG = $script:OldFixtureCallLog
    }

    It 'stops validation when isolated regeneration fails' {
        $env:BASELINE_FIXTURE_AUDIT_STATUS = '37'
        { & $script:AuditValidation } | Should-Throw -ExceptionMessage 'Isolated APM regeneration failed.'
        Should-BeCollection -Actual (Get-Content $script:AuditLog) -Expected @('--apm', $script:AuditExecutable)
        Should-NotInvoke shellcheck -Scope It
        $env:APM_EXECUTABLE | Should-Be $script:AuditExecutable
    }

    It 'continues validation when isolated regeneration succeeds' {
        $env:BASELINE_FIXTURE_AUDIT_STATUS = '0'
        { & $script:AuditValidation } | Should-Throw -ExceptionMessage 'ShellCheck reached'
        Should-Invoke shellcheck -Times 1 -Exactly -Scope It
        $env:APM_EXECUTABLE | Should-Be $script:AuditExecutable
    }
}
