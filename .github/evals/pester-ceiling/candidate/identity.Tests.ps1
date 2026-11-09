BeforeAll { . '/workspace/input/Subject.ps1' }
Describe 'port contract' {
    It 'returns the Boolean decision for <Port>' -ForEach @(
        @{ Port = 0; Expected = $false }
        @{ Port = 1; Expected = $true }
        @{ Port = 65535; Expected = $true }
        @{ Port = 65536; Expected = $false }
    ) {
        $actual = Test-PortAllowed -Port $Port
        if ($Expected) { $actual | Should-BeTrue }
        else { $actual | Should-BeFalse }
    }
}
