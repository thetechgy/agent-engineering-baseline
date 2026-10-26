BeforeAll { . '/workspace/input/Subject.ps1' }
Describe 'ports' { It 'allows a regular port' -ForEach @(1,2,3,4) { Test-PortAllowed -Port 123 | Should-BeTrue } }
