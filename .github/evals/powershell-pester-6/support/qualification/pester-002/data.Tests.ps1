BeforeDiscovery { $cases = @(@{Attempt=1;Base=20;Expected=20}, @{Attempt=4;Base=10;Expected=80}) }
BeforeAll { . '/workspace/input/Subject.ps1' }
Describe 'retry delays' {
    It 'computes attempt <Attempt>' -ForEach $cases {
        Get-RetryDelay -Attempt $Attempt -BaseMilliseconds $Base | Should-Be $Expected
    }
    It 'rejects zero' { { Get-RetryDelay -Attempt 0 } | Should-Throw -ExceptionType ([System.ArgumentOutOfRangeException]) }
    It 'rejects five' { { Get-RetryDelay -Attempt 5 } | Should-Throw -ExceptionType ([System.ArgumentOutOfRangeException]) }
}
