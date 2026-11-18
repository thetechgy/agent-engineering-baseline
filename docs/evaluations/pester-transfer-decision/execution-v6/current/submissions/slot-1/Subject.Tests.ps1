BeforeAll {
    . "$PSScriptRoot/../input/Subject.ps1"
}

Describe 'Get-BatchSummary' {
    It 'returns one summary with Enabled <ExpectedEnabled> and Quantity <ExpectedQuantity> for Requested <Requested>' -ForEach @(
        @{ Requested = -2; ExpectedEnabled = $false; ExpectedQuantity = 0 }
        @{ Requested =  0; ExpectedEnabled = $false; ExpectedQuantity = 0 }
        @{ Requested =  3; ExpectedEnabled = $true;  ExpectedQuantity = 3 }
        @{ Requested =  8; ExpectedEnabled = $true;  ExpectedQuantity = 8 }
        @{ Requested =  9; ExpectedEnabled = $true;  ExpectedQuantity = 8 }
    ) {
        $results = @(Get-BatchSummary -Requested $Requested)
        $results.Count | Should-Be 1
        $summary = $results[0]

        ($summary.Enabled -is [bool]) | Should-BeTrue
        ($summary.Enabled -eq $ExpectedEnabled) | Should-BeTrue

        # Accept any supported numeric type, independently for every call.
        $quantity = $summary.Quantity
        $isNumeric = (
            $quantity -is [sbyte] -or
            $quantity -is [byte] -or
            $quantity -is [int16] -or
            $quantity -is [uint16] -or
            $quantity -is [int32] -or
            $quantity -is [uint32] -or
            $quantity -is [int64] -or
            $quantity -is [uint64] -or
            $quantity -is [single] -or
            $quantity -is [double] -or
            $quantity -is [decimal] -or
            $quantity -is [bigint]
        )
        $isNumeric | Should-BeTrue

        # Keep the actual numeric value on the left to avoid rounding it to int.
        ($quantity -eq $ExpectedQuantity) | Should-BeTrue
    }
}
