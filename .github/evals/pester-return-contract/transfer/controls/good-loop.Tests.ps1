BeforeAll { . '/workspace/input/Subject.ps1' }
Describe 'batch summary' {
    It 'checks the required input contract' {
        foreach ($case in @(
            @{ Requested = -2; Expected = $false; ExpectedQuantity = 0 }
            @{ Requested = 0; Expected = $false; ExpectedQuantity = 0 }
            @{ Requested = 3; Expected = $true; ExpectedQuantity = 3 }
            @{ Requested = 8; Expected = $true; ExpectedQuantity = 8 }
            @{ Requested = 9; Expected = $true; ExpectedQuantity = 8 }
        )) {
            $actual = Get-BatchSummary -Requested $case.Requested
            Should-HaveType -Actual $actual.Enabled -Expected ([bool])
            Should-Be -Actual $actual.Enabled -Expected $case.Expected
            Should-Be -Actual $actual.Quantity -Expected $case.ExpectedQuantity
        }
    }
}
