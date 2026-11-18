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
        Should-Be -Actual $results.Count -Expected 1
        $summary = $results[0]

        Should-HaveType -Actual $summary.Enabled -Expected ([bool])
        Should-Be -Actual $summary.Enabled -Expected $ExpectedEnabled

        # Accept any supported numeric type independently on every call.
        $quantity = $summary.Quantity
        $isNumeric = (
            $quantity -is [sbyte] -or $quantity -is [byte] -or
            $quantity -is [short] -or $quantity -is [ushort] -or
            $quantity -is [int] -or $quantity -is [uint] -or
            $quantity -is [long] -or $quantity -is [ulong] -or
            $quantity -is [float] -or $quantity -is [double] -or
            $quantity -is [decimal] -or $quantity -is [bigint]
        )
        Should-BeTrue -Actual $isNumeric

        # Numeric equality avoids rounding Quantity to the expected integer type.
        Should-BeTrue -Actual ($quantity -eq $ExpectedQuantity)
    }
}
