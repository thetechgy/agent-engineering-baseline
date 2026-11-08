BeforeAll { . '/workspace/input/Subject.ps1'; $cases = @(@{Name='below';Slot=7;Expected=$false}, @{Name='first';Slot=8;Expected=$true}, @{Name='last';Slot=32;Expected=$true}, @{Name='above';Slot=33;Expected=$false}) }
Describe 'scheduling window' { It 'checks <Name>' -ForEach $cases { Test-WindowAllowed -Slot $Slot | Should -Be $Expected } }
