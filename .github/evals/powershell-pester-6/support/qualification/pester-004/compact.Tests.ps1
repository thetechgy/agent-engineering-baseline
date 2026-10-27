BeforeAll {
    . '/workspace/input/Subject.ps1'
    $cases = @(@{Port=0;Expected=$false}, @{Port=1;Expected=$true}, @{Port=65535;Expected=$true}, @{Port=65536;Expected=$false})
}
Describe 'port boundaries' {
    It 'checks each supplied boundary at run time' {
        foreach ($case in $cases) {
            Test-PortAllowed -Port $case.Port | Should-Be $case.Expected
        }
    }
}
