BeforeAll { . '/workspace/input/Subject.ps1' }
Describe 'retry delay' {
    It 'starts at the default base' { Get-RetryDelay -Attempt 1 | Should -Be 100 }
    It 'uses the supplied base and exponent' { Get-RetryDelay -Attempt 3 -BaseMilliseconds 25 | Should -Be 100 }
    It 'rejects attempts outside the contract' {
        foreach ($attempt in @(0, 5)) {
            { Get-RetryDelay -Attempt $attempt } | Should-Throw -ExceptionType ([System.ArgumentOutOfRangeException])
        }
    }
}
