BeforeAll { . '/workspace/input/Subject.ps1' }
Describe 'retry' { It 'returns a number' -ForEach @(1,2,3) { (Get-RetryDelay -Attempt 1) -is [int] | Should-BeTrue } }
