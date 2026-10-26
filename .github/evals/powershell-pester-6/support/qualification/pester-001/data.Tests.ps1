BeforeDiscovery {
    $cases = @(
        @{ Name='empty'; Items=@(); Expected=@() }
        @{ Name='one'; Items=@(@{Port=443;Enabled=$true}); Expected=@(443) }
        @{ Name='filtered'; Items=@(@{Port=443;Enabled=$true},@{Port=22;Enabled=$false}); Expected=@(443) }
    )
}
BeforeAll { . '/workspace/input/Subject.ps1' }
Describe 'active ports' {
    It 'handles <Name>' -ForEach $cases {
        $actual = @(Get-ActivePort -Endpoint $Items)
        $actual | Should-BeCollection $Expected
        foreach ($port in $actual) { ($port -is [int]) | Should-BeTrue }
    }
}
