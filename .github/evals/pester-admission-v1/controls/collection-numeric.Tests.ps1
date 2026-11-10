BeforeAll { . '/workspace/input/Subject.ps1' }
Describe 'batch summary' {
    It 'summarizes <Requested>' -ForEach @(
        @{ Requested = -2; Expected = $false; ExpectedQuantity = 0 }
        @{ Requested = 0; Expected = $false; ExpectedQuantity = 0 }
        @{ Requested = 3; Expected = $true; ExpectedQuantity = 3 }
        @{ Requested = 8; Expected = $true; ExpectedQuantity = 8 }
        @{ Requested = 9; Expected = $true; ExpectedQuantity = 8 }
    ) {
        $actual = Get-BatchSummary -Requested $Requested
        Should-HaveType -Actual $actual.Enabled -Expected ([bool])
        Should-Be -Actual $actual.Enabled -Expected $Expected
        Should-Be -Actual $actual.Quantity -Expected $ExpectedQuantity
    }
}

Describe 'Collection sizes' { It 'reads literal members without invocation' {
    $values = @(1, 2)
    $values.Count | Should-Be 2
    $values.Length | Should-Be 2
    (@()).Count | Should-Be 0
    (@(1)).Length | Should-Be 1
    $scalar = 3
    $scalar.Count | Should-Be 1
} }

Describe 'Numeric type predicates' { It 'supports accelerators and CLR spellings' {
    $value = 1
    ($value -is [sbyte]) | Should-Be $false
    ($value -isnot [sbyte]) | Should-Be $true
    ($value -is [byte]) | Should-Be $false
    ($value -isnot [byte]) | Should-Be $true
    ($value -is [short]) | Should-Be $false
    ($value -isnot [short]) | Should-Be $true
    ($value -is [int16]) | Should-Be $false
    ($value -isnot [int16]) | Should-Be $true
    ($value -is [ushort]) | Should-Be $false
    ($value -isnot [ushort]) | Should-Be $true
    ($value -is [uint16]) | Should-Be $false
    ($value -isnot [uint16]) | Should-Be $true
    ($value -is [int]) | Should-Be $true
    ($value -isnot [int]) | Should-Be $false
    ($value -is [int32]) | Should-Be $true
    ($value -isnot [int32]) | Should-Be $false
    ($value -is [uint]) | Should-Be $false
    ($value -isnot [uint]) | Should-Be $true
    ($value -is [uint32]) | Should-Be $false
    ($value -isnot [uint32]) | Should-Be $true
    ($value -is [long]) | Should-Be $false
    ($value -isnot [long]) | Should-Be $true
    ($value -is [int64]) | Should-Be $false
    ($value -isnot [int64]) | Should-Be $true
    ($value -is [ulong]) | Should-Be $false
    ($value -isnot [ulong]) | Should-Be $true
    ($value -is [uint64]) | Should-Be $false
    ($value -isnot [uint64]) | Should-Be $true
    ($value -is [single]) | Should-Be $false
    ($value -isnot [single]) | Should-Be $true
    ($value -is [float]) | Should-Be $false
    ($value -isnot [float]) | Should-Be $true
    ($value -is [double]) | Should-Be $false
    ($value -isnot [double]) | Should-Be $true
    ($value -is [decimal]) | Should-Be $false
    ($value -isnot [decimal]) | Should-Be $true
    ($value -is [bigint]) | Should-Be $false
    ($value -isnot [bigint]) | Should-Be $true
    ($value -is [System.SByte]) | Should-Be $false
    ($value -isnot [System.SByte]) | Should-Be $true
    ($value -is [System.Byte]) | Should-Be $false
    ($value -isnot [System.Byte]) | Should-Be $true
    ($value -is [System.Int16]) | Should-Be $false
    ($value -isnot [System.Int16]) | Should-Be $true
    ($value -is [System.UInt16]) | Should-Be $false
    ($value -isnot [System.UInt16]) | Should-Be $true
    ($value -is [System.Int32]) | Should-Be $true
    ($value -isnot [System.Int32]) | Should-Be $false
    ($value -is [System.UInt32]) | Should-Be $false
    ($value -isnot [System.UInt32]) | Should-Be $true
    ($value -is [System.Int64]) | Should-Be $false
    ($value -isnot [System.Int64]) | Should-Be $true
    ($value -is [System.UInt64]) | Should-Be $false
    ($value -isnot [System.UInt64]) | Should-Be $true
    ($value -is [System.Single]) | Should-Be $false
    ($value -isnot [System.Single]) | Should-Be $true
    ($value -is [System.Double]) | Should-Be $false
    ($value -isnot [System.Double]) | Should-Be $true
    ($value -is [System.Decimal]) | Should-Be $false
    ($value -isnot [System.Decimal]) | Should-Be $true
    ($value -is [System.Numerics.BigInteger]) | Should-Be $false
    ($value -isnot [System.Numerics.BigInteger]) | Should-Be $true
} }

Describe 'Numeric representations' { It 'uses literal values without new casts' {
    (1y -is [sbyte]) | Should-BeTrue
    (1uy -is [byte]) | Should-BeTrue
    (1s -is [short]) | Should-BeTrue
    (1us -is [ushort]) | Should-BeTrue
    (1u -is [uint]) | Should-BeTrue
    (1L -is [long]) | Should-BeTrue
    (1uL -is [ulong]) | Should-BeTrue
    (1.0 -is [double]) | Should-BeTrue
    (1d -is [decimal]) | Should-BeTrue
    (1n -is [bigint]) | Should-BeTrue
} }
