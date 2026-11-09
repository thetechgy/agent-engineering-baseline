BeforeAll { . '/workspace/input/Subject.ps1' }
Describe 'window' { It 'permits an ordinary slot' { Test-WindowAllowed -Slot 16 | Should -BeTrue } }
