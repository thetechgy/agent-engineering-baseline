BeforeDiscovery {
    $script:AuditWindowsHost = $env:OS -ceq 'Windows_NT'
}

Describe 'Linux validation audit exit propagation' -Skip:$script:AuditWindowsHost {
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
        [IO.File]::WriteAllText($script:AuditExecutable, @"
#!/bin/sh
printf '%s\n' "`$*" >> '$script:AuditLog'
case "`$1" in
    audit) exit "`$BASELINE_FIXTURE_AUDIT_STATUS" ;;
    pack) exit 39 ;;
esac
exit 0
"@)
        & chmod +x $script:AuditExecutable
    }

    BeforeEach {
        Mock Invoke-Pester {
            [pscustomobject]@{ FailedCount = 0; FailedContainers = @(); Result = 'Passed' }
        }
        Mock Invoke-ScriptAnalyzer { @() }
        Remove-Item $script:AuditLog -ErrorAction SilentlyContinue
    }

    AfterAll {
        $env:APM_EXECUTABLE = $script:OldAuditApm
        $env:BASELINE_FIXTURE_AUDIT_STATUS = $script:OldFixtureStatus
    }

    It 'stops before packaging when the real pseudo-terminal audit fails' {
        $env:BASELINE_FIXTURE_AUDIT_STATUS = '37'
        { & $script:AuditValidation } | Should-Throw -ExceptionMessage 'APM audit failed.'
        $calls = Get-Content $script:AuditLog
        Should-ContainCollection -Actual $calls -Expected @('audit --ci')
        ($calls -join "`n") | Should-NotMatchString '(?m)^pack '
        $env:APM_EXECUTABLE | Should-Be $script:AuditExecutable
    }

    It 'reaches packaging when the real pseudo-terminal audit succeeds' {
        $env:BASELINE_FIXTURE_AUDIT_STATUS = '0'
        { & $script:AuditValidation } | Should-Throw -ExceptionMessage 'APM package check failed.'
        Should-ContainCollection -Actual (Get-Content $script:AuditLog) -Expected @('pack --dry-run')
        $env:APM_EXECUTABLE | Should-Be $script:AuditExecutable
    }
}
