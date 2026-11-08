BeforeAll {
    . "$PSScriptRoot/../input/Subject.ps1"
}

Describe 'Get-ActivePort' {
    It 'emits no values when Endpoint is omitted' {
        $actual = @(Get-ActivePort)

        $actual.Count | Should-Be 0
    }

    It 'emits no values for an empty endpoint array' {
        $actual = @(Get-ActivePort -Endpoint @())

        $actual.Count | Should-Be 0
    }

    It 'emits no values when every endpoint is disabled' {
        $endpoints = @(
            [pscustomobject]@{ Port = 80; Enabled = $false }
            [pscustomobject]@{ Port = 443; Enabled = $false }
            [pscustomobject]@{ Port = 80; Enabled = $false }
        )

        $actual = @(Get-ActivePort -Endpoint $endpoints)

        $actual.Count | Should-Be 0
    }

    It 'emits a single integer value for one enabled endpoint' {
        $endpoints = @(
            [pscustomobject]@{ Port = 8080; Enabled = $true }
        )

        $actual = Get-ActivePort -Endpoint $endpoints

        Should-HaveType -Actual $actual -Expected ([int])
        $actual | Should-Be 8080
    }

    It 'includes enabled ports and excludes disabled ports in mixed input' {
        $endpoints = @(
            [pscustomobject]@{ Port = 22; Enabled = $false }
            [pscustomobject]@{ Port = 443; Enabled = $true }
            [pscustomobject]@{ Port = 8080; Enabled = $false }
            [pscustomobject]@{ Port = 80; Enabled = $true }
            [pscustomobject]@{ Port = 80; Enabled = $false }
        )

        $actual = @(Get-ActivePort -Endpoint $endpoints)

        Should-BeCollection -Actual $actual -Expected @(80, 443)
    }

    It 'emits each enabled port once even when duplicates are separated' {
        $endpoints = @(
            [pscustomobject]@{ Port = 443; Enabled = $true }
            [pscustomobject]@{ Port = 80; Enabled = $true }
            [pscustomobject]@{ Port = 443; Enabled = $true }
            [pscustomobject]@{ Port = 8080; Enabled = $false }
            [pscustomobject]@{ Port = 80; Enabled = $true }
            [pscustomobject]@{ Port = 443; Enabled = $true }
        )

        $actual = @(Get-ActivePort -Endpoint $endpoints)

        Should-BeCollection -Actual $actual -Expected @(80, 443)
    }

    It 'emits one scalar integer when multiple enabled endpoints share a port' {
        $endpoints = @(
            [pscustomobject]@{ Port = 443; Enabled = $true }
            [pscustomobject]@{ Port = 80; Enabled = $false }
            [pscustomobject]@{ Port = 443; Enabled = $true }
        )

        $actual = Get-ActivePort -Endpoint $endpoints

        Should-HaveType -Actual $actual -Expected ([int])
        $actual | Should-Be 443
    }

    It 'sorts all emitted ports in ascending numeric order' {
        $endpoints = @(
            [pscustomobject]@{ Port = 443; Enabled = $true }
            [pscustomobject]@{ Port = 9; Enabled = $true }
            [pscustomobject]@{ Port = 10000; Enabled = $true }
            [pscustomobject]@{ Port = 80; Enabled = $true }
            [pscustomobject]@{ Port = 2; Enabled = $true }
            [pscustomobject]@{ Port = 8080; Enabled = $true }
            [pscustomobject]@{ Port = 22; Enabled = $true }
        )
        $expected = @(2, 9, 22, 80, 443, 8080, 10000)

        $actual = @(Get-ActivePort -Endpoint $endpoints)

        $actual.Count | Should-Be $expected.Count
        # Collection equality is unordered; compare positions to verify sorting.
        for ($index = 0; $index -lt $expected.Count; $index++) {
            $actual[$index] | Should-Be $expected[$index]
            Should-HaveType -Actual $actual[$index] -Expected ([int])
        }
    }

    It 'emits integer ports when input ports use strings or wider integers' {
        $endpoints = @(
            [pscustomobject]@{ Port = '8080'; Enabled = $true }
            [pscustomobject]@{ Port = [long]443; Enabled = $true }
            [pscustomobject]@{ Port = '80'; Enabled = $true }
        )
        $expected = @(80, 443, 8080)

        $actual = @(Get-ActivePort -Endpoint $endpoints)

        $actual.Count | Should-Be $expected.Count
        for ($index = 0; $index -lt $expected.Count; $index++) {
            Should-HaveType -Actual $actual[$index] -Expected ([int])
            $actual[$index] | Should-Be $expected[$index]
        }
    }

    It 'deduplicates ports by their integer value across input representations' {
        $endpoints = @(
            [pscustomobject]@{ Port = '080'; Enabled = $true }
            [pscustomobject]@{ Port = 443; Enabled = $true }
            [pscustomobject]@{ Port = 80; Enabled = $true }
            [pscustomobject]@{ Port = '443'; Enabled = $true }
            [pscustomobject]@{ Port = '80'; Enabled = $true }
        )

        $actual = @(Get-ActivePort -Endpoint $endpoints)

        $actual.Count | Should-Be 2
        $actual[0] | Should-Be 80
        $actual[1] | Should-Be 443
        Should-HaveType -Actual $actual[0] -Expected ([int])
        Should-HaveType -Actual $actual[1] -Expected ([int])
    }
}
