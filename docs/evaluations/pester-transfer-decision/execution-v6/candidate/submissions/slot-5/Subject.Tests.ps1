BeforeAll {
    . "$PSScriptRoot/../input/Subject.ps1"
}

Describe 'Get-BatchSummary' {
    It 'returns the expected summary for Requested <Requested>' -ForEach @(
        @{ Requested = -2; ExpectedEnabled = $false; ExpectedQuantity = 0 }
        @{ Requested =  0; ExpectedEnabled = $false; ExpectedQuantity = 0 }
        @{ Requested =  3; ExpectedEnabled = $true;  ExpectedQuantity = 3 }
        @{ Requested =  8; ExpectedEnabled = $true;  ExpectedQuantity = 8 }
        @{ Requested =  9; ExpectedEnabled = $true;  ExpectedQuantity = 8 }
    ) {
        $results = @(Get-BatchSummary -Requested $Requested)
        Should-Be -Actual $results.Count -Expected 1
        $actual = $results[0]

        Should-HaveType -Actual $actual.Enabled -Expected ([bool])
        Should-Be -Actual $actual.Enabled -Expected $ExpectedEnabled

        # Accept any supported numeric type on each call, without coercing the result.
        $isNumeric = (
            $actual.Quantity -is [sbyte] -or
            $actual.Quantity -is [byte] -or
            $actual.Quantity -is [short] -or
            $actual.Quantity -is [ushort] -or
            $actual.Quantity -is [int] -or
            $actual.Quantity -is [uint] -or
            $actual.Quantity -is [long] -or
            $actual.Quantity -is [ulong] -or
            $actual.Quantity -is [single] -or
            $actual.Quantity -is [double] -or
            $actual.Quantity -is [decimal] -or
            $actual.Quantity -is [bigint]
        )
        Should-BeTrue -Actual $isNumeric

        # Compare with the actual numeric value on the left to avoid rounding it to int.
        Should-BeTrue -Actual ($actual.Quantity -eq $ExpectedQuantity)
    }
}
