Describe 'Diagnostic type reduction' { It 'checks' { $quantity=1; ($quantity -is [sbyte] -or $quantity -is [int]) | Should-BeTrue } }
