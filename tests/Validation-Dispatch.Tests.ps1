BeforeAll {
    $source = Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts/Invoke-Validation.ps1'
    $scripts = New-Item -ItemType Directory -Path (Join-Path $TestDrive 'scripts')
    New-Item -ItemType Directory -Path (Join-Path $TestDrive 'tests') | Out-Null
    $script:ValidationSource = Join-Path $scripts.FullName 'Invoke-Validation.ps1'
    # Replace only the first Full-only external command with a terminating probe.
    # The original parameter binding and dispatch execute in an isolated repository.
    $text = [IO.File]::ReadAllText($source)
    $text.Contains('& ./tests/bootstrap.sh') | Should-BeTrue
    [IO.File]::WriteAllText($script:ValidationSource, $text.Replace('& ./tests/bootstrap.sh', '& Invoke-FullSuiteProbe'))
    function Invoke-FullSuiteProbe { throw 'Unexpected full workflow' }
}

Describe 'Validation suite dispatch' {
    BeforeEach {
        Mock Invoke-Pester {
            [pscustomobject]@{ FailedCount = 0; FailedContainers = @(); Result = 'Passed' }
        }
        Mock Invoke-ScriptAnalyzer { @() }
        # Stop at the first Full-only operation; installation and compilation must never run.
        Mock Invoke-FullSuiteProbe { throw 'Full workflow selected' }
    }

    It 'runs only Pester and analyzer for -Suite <SuiteValue>' -ForEach @(
        @{ SuiteValue = 'Pester' }
        @{ SuiteValue = 'pester' }
        @{ SuiteValue = 'PESTER' }
    ) {
        & $script:ValidationSource -Suite $SuiteValue
        Should-Invoke Invoke-Pester -Times 1 -Exactly -Scope It
        Should-Invoke Invoke-ScriptAnalyzer -Scope It
        Should-NotInvoke Invoke-FullSuiteProbe -Scope It
    }

    It 'selects full validation for -Suite <SuiteValue>' -ForEach @(
        @{ SuiteValue = 'Full' }
        @{ SuiteValue = 'full' }
        @{ SuiteValue = 'FULL' }
    ) {
        { & $script:ValidationSource -Suite $SuiteValue } |
            Should-Throw -ExceptionMessage 'Full workflow selected'
        Should-Invoke Invoke-Pester -Times 1 -Exactly -Scope It
        Should-Invoke Invoke-ScriptAnalyzer -Scope It
        Should-Invoke Invoke-FullSuiteProbe -Times 1 -Exactly -Scope It
    }
}
