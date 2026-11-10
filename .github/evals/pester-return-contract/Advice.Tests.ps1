Describe 'declared return contract advice' {
    It 'checks the raw type and value: <Name>' -ForEach @(
        @{ Name = 'Boolean true'; Actual = $true; Expected = $true; Reject = $false }
        @{ Name = 'Boolean false'; Actual = $false; Expected = $false; Reject = $false }
        @{ Name = 'integer true'; Actual = 1; Expected = $true; Reject = $true }
        @{ Name = 'integer false'; Actual = 0; Expected = $false; Reject = $true }
        @{ Name = 'double true'; Actual = 1.0; Expected = $true; Reject = $true }
        @{ Name = 'text true'; Actual = 'True'; Expected = $true; Reject = $true }
        @{ Name = 'null'; Actual = $null; Expected = $false; Reject = $true }
        @{ Name = 'singleton shape'; Actual = @($true); Expected = $true; Reject = $true }
        @{ Name = 'wrong Boolean value'; Actual = $false; Expected = $true; Reject = $true }
    ) {
        $check = { Should-HaveType -Actual $Actual -Expected ([bool]); Should-Be -Actual $Actual -Expected $Expected }
        if ($Reject) { $check | Should-Throw } else { & $check }
    }
    It 'demonstrates equality accepting the wrong type' {
        Should-Be -Actual 1 -Expected $true
        Should-Be -Actual 0 -Expected $false
    }
    It 'shows why converting the actual masks its original type' {
        $actual = 1
        Should-HaveType -Actual ([bool]$actual) -Expected ([bool])
        { Should-HaveType -Actual $actual -Expected ([bool]) } | Should-Throw
    }
    It 'preserves a value-only numeric contract' -ForEach @(
        @{ Actual = [int]3 }; @{ Actual = [long]3 }; @{ Actual = [decimal]3 }
    ) {
        Should-Be -Actual $Actual -Expected 3
        { Should-Be -Actual $Actual -Expected 4 } | Should-Throw
    }
    It 'accepts assignable types when the contract permits an interface' {
        Should-HaveType -Actual @{} -Expected ([System.Collections.IDictionary])
    }
}
