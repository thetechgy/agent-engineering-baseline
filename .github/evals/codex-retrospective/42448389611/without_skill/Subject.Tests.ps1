BeforeAll {
    . "$PSScriptRoot/../input/Subject.ps1"
}

Describe 'Get-ActivePort' {
    It 'emits no values when Endpoint is omitted' {
        $actual = @(Get-ActivePort)

        Should -ActualValue $actual -HaveCount 0
    }

    It 'accepts an explicit empty endpoint array and emits no values' {
        $actual = @(Get-ActivePort -Endpoint @())

        Should -ActualValue $actual -HaveCount 0
    }

    It 'emits no values when every endpoint is disabled' {
        $endpoints = @(
            @{ Port = 80; Enabled = $false }
            @{ Port = 443; Enabled = $false }
            @{ Port = 8080; Enabled = $false }
        )

        $actual = @(Get-ActivePort -Endpoint $endpoints)

        Should -ActualValue $actual -HaveCount 0
    }

    It 'emits one integer for one enabled endpoint' {
        $actual = @(Get-ActivePort -Endpoint @(
            @{ Port = 443; Enabled = $true }
        ))

        Should -ActualValue $actual -HaveCount 1
        Should -ActualValue $actual[0] -Be 443
        Should -ActualValue $actual[0] -BeOfType ([int])
    }

    It 'emits no values for a single disabled endpoint' {
        $actual = @(Get-ActivePort -Endpoint @(
            @{ Port = 443; Enabled = $false }
        ))

        Should -ActualValue $actual -HaveCount 0
    }

    It 'selects the enabled endpoint from disabled endpoints around it' {
        $endpoints = @(
            @{ Port = 22; Enabled = $false }
            @{ Port = 8443; Enabled = $true }
            @{ Port = 65535; Enabled = $false }
        )

        $actual = @(Get-ActivePort -Endpoint $endpoints)

        Should -ActualValue $actual -HaveCount 1
        Should -ActualValue $actual[0] -Be 8443
        Should -ActualValue $actual[0] -BeOfType ([int])
    }

    It 'emits only enabled ports in a mixed collection' {
        $endpoints = @(
            @{ Port = 8080; Enabled = $true }
            @{ Port = 21; Enabled = $false }
            @{ Port = 443; Enabled = $true }
            @{ Port = 65535; Enabled = $false }
            @{ Port = 80; Enabled = $true }
            @{ Port = 22; Enabled = $false }
        )

        $actual = @(Get-ActivePort -Endpoint $endpoints)

        Should -ActualValue $actual -HaveCount 3
        Should -ActualValue $actual[0] -Be 80
        Should -ActualValue $actual[1] -Be 443
        Should -ActualValue $actual[2] -Be 8080
        foreach ($port in $actual) {
            Should -ActualValue $port -BeOfType ([int])
        }
    }

    It 'sorts all enabled ports in ascending numeric order' {
        $endpoints = @(
            @{ Port = 8080; Enabled = $true }
            @{ Port = 443; Enabled = $true }
            @{ Port = 22; Enabled = $true }
            @{ Port = 10000; Enabled = $true }
            @{ Port = 80; Enabled = $true }
            @{ Port = 9; Enabled = $true }
        )

        $actual = @(Get-ActivePort -Endpoint $endpoints)
        $expected = @(9, 22, 80, 443, 8080, 10000)

        Should -ActualValue $actual -HaveCount 6
        for ($index = 0; $index -lt $expected.Count; $index++) {
            Should -ActualValue $actual[$index] -Be $expected[$index]
            Should -ActualValue $actual[$index] -BeOfType ([int])
        }
    }

    It 'removes repeated enabled ports even when separated in the input' {
        $endpoints = @(
            @{ Port = 443; Enabled = $true }
            @{ Port = 80; Enabled = $true }
            @{ Port = 443; Enabled = $true }
            @{ Port = 8080; Enabled = $true }
            @{ Port = 80; Enabled = $true }
            @{ Port = 443; Enabled = $true }
        )

        $actual = @(Get-ActivePort -Endpoint $endpoints)

        Should -ActualValue $actual -HaveCount 3
        Should -ActualValue $actual[0] -Be 80
        Should -ActualValue $actual[1] -Be 443
        Should -ActualValue $actual[2] -Be 8080
        foreach ($port in $actual) {
            Should -ActualValue $port -BeOfType ([int])
        }
    }

    It 'emits one integer when every enabled endpoint has the same port' {
        $endpoints = @(
            @{ Port = 8080; Enabled = $true }
            @{ Port = 8080; Enabled = $true }
            @{ Port = 8080; Enabled = $true }
        )

        $actual = @(Get-ActivePort -Endpoint $endpoints)

        Should -ActualValue $actual -HaveCount 1
        Should -ActualValue $actual[0] -Be 8080
        Should -ActualValue $actual[0] -BeOfType ([int])
    }

    It 'keeps enabled ports that also occur on disabled endpoints' {
        $endpoints = @(
            @{ Port = 443; Enabled = $false }
            @{ Port = 80; Enabled = $true }
            @{ Port = 443; Enabled = $true }
            @{ Port = 80; Enabled = $false }
            @{ Port = 22; Enabled = $false }
        )

        $actual = @(Get-ActivePort -Endpoint $endpoints)

        Should -ActualValue $actual -HaveCount 2
        Should -ActualValue $actual[0] -Be 80
        Should -ActualValue $actual[1] -Be 443
        foreach ($port in $actual) {
            Should -ActualValue $port -BeOfType ([int])
        }
    }

    It 'converts a single numeric string port into an integer' {
        $actual = @(Get-ActivePort -Endpoint @(
            @{ Port = '00443'; Enabled = $true }
        ))

        Should -ActualValue $actual -HaveCount 1
        Should -ActualValue $actual[0] -Be 443
        Should -ActualValue $actual[0] -BeOfType ([int])
    }

    It 'sorts numeric string ports by numeric value' {
        $endpoints = @(
            @{ Port = '10000'; Enabled = $true }
            @{ Port = '443'; Enabled = $true }
            @{ Port = '9'; Enabled = $true }
            @{ Port = '80'; Enabled = $true }
            @{ Port = '22'; Enabled = $true }
        )

        $actual = @(Get-ActivePort -Endpoint $endpoints)
        $expected = @(9, 22, 80, 443, 10000)

        Should -ActualValue $actual -HaveCount 5
        for ($index = 0; $index -lt $expected.Count; $index++) {
            Should -ActualValue $actual[$index] -Be $expected[$index]
            Should -ActualValue $actual[$index] -BeOfType ([int])
        }
    }

    It 'deduplicates equivalent numeric representations after conversion' {
        $endpoints = @(
            @{ Port = '00443'; Enabled = $true }
            @{ Port = 80; Enabled = $true }
            @{ Port = 443; Enabled = $true }
            @{ Port = '080'; Enabled = $true }
            @{ Port = '443'; Enabled = $true }
            @{ Port = '8080'; Enabled = $false }
        )

        $actual = @(Get-ActivePort -Endpoint $endpoints)

        Should -ActualValue $actual -HaveCount 2
        Should -ActualValue $actual[0] -Be 80
        Should -ActualValue $actual[1] -Be 443
        foreach ($port in $actual) {
            Should -ActualValue $port -BeOfType ([int])
        }
    }

    It 'does not retain ports from an earlier invocation' {
        $first = @(Get-ActivePort -Endpoint @(
            @{ Port = 443; Enabled = $true }
        ))
        $empty = @(Get-ActivePort -Endpoint @())
        $second = @(Get-ActivePort -Endpoint @(
            @{ Port = 80; Enabled = $true }
        ))

        Should -ActualValue $first -HaveCount 1
        Should -ActualValue $first[0] -Be 443
        Should -ActualValue $first[0] -BeOfType ([int])
        Should -ActualValue $empty -HaveCount 0
        Should -ActualValue $second -HaveCount 1
        Should -ActualValue $second[0] -Be 80
        Should -ActualValue $second[0] -BeOfType ([int])
    }
}
