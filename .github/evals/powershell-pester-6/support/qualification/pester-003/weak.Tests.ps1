BeforeAll { Import-Module '/workspace/input/Probe.psm1' -Force }
Describe 'endpoint' {
    It 'looks healthy' -ForEach @(1,2) {
        Mock Test-ProbeConnection { $true } -ModuleName Probe
        (Get-EndpointStatus -Target 'service.invalid').Healthy | Should-BeTrue
    }
}
