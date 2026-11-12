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
        $results.Count | Should-Be 1
        $summary = $results[0]

        if ($ExpectedEnabled) {
            Should-BeTrue -Actual $summary.Enabled
        }
        else {
            Should-BeFalse -Actual $summary.Enabled
        }

        $quantity = $summary.Quantity
        ($quantity -is [sbyte] -or
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
            $quantity -is [bigint]) | Should-BeTrue

        # Keep the actual numeric value on the left to avoid integer coercion
        # rounding a fractional result during an expected-value assertion.
        ($quantity -eq $ExpectedQuantity) | Should-BeTrue
    }
}
