# Independent public-contract examples: these names must bind literal data keys.
BeforeAll { . '/workspace/input/Subject.ps1' }
Describe 'documented retry parameters' {
    It 'returns <Expected> using <basemilliseconds> at <ATTEMPT>' -ForEach @(
        @{ Attempt = 1; BaseMilliseconds = 37; Expected = 37 }
        @{ Attempt = 4; BaseMilliseconds = 37; Expected = 296 }
    ) {
        Get-RetryDelay -Attempt $Attempt -BaseMilliseconds $BaseMilliseconds | Should-Be $Expected
    }
    It -Name 'legacy base <BASE> gives <Expected>' -TestCases @(
        @{ Attempt = 2; Base = 7; Expected = 14 }
    ) {
        Get-RetryDelay -Attempt $Attempt -BaseMilliseconds $Base | Should-Be $Expected
    }
    It -Name:'named colon <BaseMilliseconds> gives <expected>' -TestCases @(
        @{ Attempt = 3; BaseMilliseconds = 11; Expected = 44 }
    ) {
        Get-RetryDelay -Attempt $Attempt -BaseMilliseconds $BaseMilliseconds | Should-Be $Expected
    }
    It 'rejects out-of-range attempt <Attempt>' -ForEach @(
        @{ Attempt = 0 }
        @{ Attempt = 5 }
    ) {
        { Get-RetryDelay -Attempt $Attempt } | Should-Throw -ExceptionType ([System.ArgumentOutOfRangeException])
    }
}
