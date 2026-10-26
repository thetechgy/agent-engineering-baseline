BeforeAll { . '/workspace/input/Subject.ps1'; $cases = @(@{Name='zero';Port=0;Expected=$false}, @{Name='lowest';Port=1;Expected=$true}, @{Name='highest';Port=65535;Expected=$true}, @{Name='above';Port=65536;Expected=$false}) }
Describe 'port limits' { It 'handles <Name>' -ForEach $cases { Test-PortAllowed -Port $Port | Should-Be $Expected } }
