BeforeAll { . '/workspace/input/Subject.ps1' }
Describe 'incomplete port contract' {
    It 'checks only result type for <Port>' -ForEach @(
        @{ Port = 0 }; @{ Port = 1 }; @{ Port = 65535 }; @{ Port = 65536 }
    ) {
        Should-HaveType -Actual (Test-PortAllowed -Port $Port) -Expected ([bool])
    }
}
