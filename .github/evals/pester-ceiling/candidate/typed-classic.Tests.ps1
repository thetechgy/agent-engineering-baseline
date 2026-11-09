BeforeAll { . '/workspace/input/Subject.ps1' }
Describe 'port contract' {
    It 'returns typed boundary decisions' {
        foreach ($case in @(
            @{ Port = 0; Expected = $false }
            @{ Port = 1; Expected = $true }
            @{ Port = 65535; Expected = $true }
            @{ Port = 65536; Expected = $false }
        )) {
            $actual = Test-PortAllowed -Port $case.Port
            $actual | Should -BeOfType ([bool])
            $actual | Should -Be $case.Expected
        }
    }
}
