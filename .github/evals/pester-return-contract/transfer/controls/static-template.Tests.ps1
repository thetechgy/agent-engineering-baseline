BeforeAll { . '/workspace/input/Subject.ps1' }
Describe 'batch summary for <Scenario>' -ForEach @{ Scenario = 'bounds' } {
    It -Name 'summarizes <Requested> with <ResultFlag>' -TestCases @(
        @{ Requested = -2; ResultFlag = $false; ExpectedQuantity = 0 },
        @{ Requested = 0; ResultFlag = $false; ExpectedQuantity = 0 }
        @{ Requested = 3; ResultFlag = $true; ExpectedQuantity = 3 }
        @{ Requested = 8; ResultFlag = $true; ExpectedQuantity = 8 }
        @{ Requested = 9; ResultFlag = $true; ExpectedQuantity = 8 }
    ) {
        $actual = Get-BatchSummary -Requested $Requested
        Should-HaveType -Actual $actual.Enabled -Expected ([bool])
        Should-Be -Actual $actual.Enabled -Expected $ResultFlag
        Should-Be -Actual $actual.Quantity -Expected $ExpectedQuantity
    }
}
