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
        $results.Count | Should -Be 1

        $summary = $results[0]
        ($summary.Enabled -is [bool]) | Should -BeTrue
        $summary.Enabled | Should -Be $ExpectedEnabled

        $quantity = $summary.Quantity
        # Check each call independently; no concrete numeric type is required.
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
        $isNumeric | Should -BeTrue
        # Compare before asserting so the assertion cannot coerce Quantity.
        ($quantity -eq $ExpectedQuantity) | Should -BeTrue
    }
}
