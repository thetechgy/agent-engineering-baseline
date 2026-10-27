BeforeAll { . "$PSScriptRoot/../input/Subject.ps1" }
Describe 'port results' {
    It 'supports an empty collection' { @(Get-ActivePort) | Should-BeCollection -Count 0 }
    It 'returns enabled integer ports' {
        $ports = @(Get-ActivePort -Endpoint @(
            @{ Port = 8080; Enabled = $false }
            @{ Port = 80; Enabled = $true }
            @{ Port = 80; Enabled = $true }
        ))
        $ports | Should-BeCollection @(80)
        foreach ($port in $ports) { $port | Should-HaveType ([int]) }
    }
    It 'sorts distinct ports' {
        $ports = @(Get-ActivePort -Endpoint @(@{Port=443;Enabled=$true}, @{Port=80;Enabled=$true}))
        $ports[0] | Should-Be 80
        $ports[1] | Should-Be 443
    }
}
