BeforeAll { . '/workspace/input/Subject.ps1' }

Describe 'Batch summary with a permitted numeric representation' {
    It 'preserves the result for <Requested>' -ForEach @(
        @{ Requested = -2; ExpectedEnabled = $false; ExpectedQuantity = 0 }
        @{ Requested = 0; ExpectedEnabled = $false; ExpectedQuantity = 0 }
        @{ Requested = 3; ExpectedEnabled = $true; ExpectedQuantity = 3 }
        @{ Requested = 8; ExpectedEnabled = $true; ExpectedQuantity = 8 }
        @{ Requested = 9; ExpectedEnabled = $true; ExpectedQuantity = 8 }
    ) {
        $result = @(Get-BatchSummary -Requested $Requested)
        Should-Be -Actual $result.Count -Expected 1
        Should-Be -Actual $result[0].Enabled -Expected $ExpectedEnabled
        $culture = [Globalization.CultureInfo]::InvariantCulture
        Should-Be -Actual ([decimal]::Parse($result[0].Quantity.ToString($culture), $culture)) -Expected ([decimal]$ExpectedQuantity)
    }
}
