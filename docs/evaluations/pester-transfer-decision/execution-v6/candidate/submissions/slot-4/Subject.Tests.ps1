BeforeAll {
    . "$PSScriptRoot/../input/Subject.ps1"
}

Describe 'Get-BatchSummary' {
    It 'returns one correctly typed summary for Requested <Requested>' -ForEach @(
        @{ Requested = -2; ExpectedEnabled = $false; ExpectedQuantity = 0 }
        @{ Requested = 0; ExpectedEnabled = $false; ExpectedQuantity = 0 }
        @{ Requested = 3; ExpectedEnabled = $true; ExpectedQuantity = 3 }
        @{ Requested = 8; ExpectedEnabled = $true; ExpectedQuantity = 8 }
        @{ Requested = 9; ExpectedEnabled = $true; ExpectedQuantity = 8 }
    ) {
        $results = @(Get-BatchSummary -Requested $Requested)
        Should-Be -Actual $results.Count -Expected 1
        $actual = $results[0]

        Should-HaveType -Actual $actual.Enabled -Expected ([bool])
        Should-Be -Actual $actual.Enabled -Expected $ExpectedEnabled

        $quantity = $actual.Quantity
        $isNumeric = (
            $quantity -is [sbyte] -or
            $quantity -is [byte] -or
            $quantity -is [short] -or
            $quantity -is [ushort] -or
            $quantity -is [int] -or
            $quantity -is [uint] -or
            $quantity -is [long] -or
            $quantity -is [ulong] -or
            $quantity -is [single] -or
            $quantity -is [double] -or
            $quantity -is [decimal] -or
            $quantity -is [bigint]
        )
        Should-BeTrue -Actual $isNumeric

        # Compare with the actual numeric value on the left to avoid rounding
        # fractional quantities through conversion to the expected integer type.
        Should-BeTrue -Actual ($quantity -eq $ExpectedQuantity)
    }
}
