BeforeAll { . '/workspace/input/Subject.ps1' }
Describe 'Get-ActivePort' {
    It 'emits nothing for empty input' {
        @(Get-ActivePort -Endpoint @()) | Should -HaveCount 0
    }
    It 'emits an integer for one enabled endpoint' {
        $actual = @(Get-ActivePort -Endpoint @([pscustomobject]@{ Port = 443; Enabled = $true }))
        $actual | Should -HaveCount 1
        $actual[0] | Should -Be 443
        $actual[0] | Should -BeOfType ([int])
    }
    It 'filters disabled endpoints and removes duplicates' {
        $actual = @(Get-ActivePort -Endpoint @(
            [pscustomobject]@{ Port = 443; Enabled = $true }
            [pscustomobject]@{ Port = 80; Enabled = $true }
            [pscustomobject]@{ Port = 22; Enabled = $false }
            [pscustomobject]@{ Port = 80; Enabled = $true }
        ))
        $actual | Should -HaveCount 2
        $actual[0] | Should -Be 80
        $actual[1] | Should -Be 443
        foreach ($port in $actual) { $port | Should -BeOfType ([int]) }
    }
}
