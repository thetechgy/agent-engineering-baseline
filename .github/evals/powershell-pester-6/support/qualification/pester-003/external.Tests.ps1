BeforeAll { Import-Module '/workspace/input/Probe.psm1' -Force }
Describe 'endpoint status' {
    BeforeEach { Mock Test-ProbeConnection { $true } -ModuleName Probe }
    It 'passes the requested target to the transport' {
        $result = Get-EndpointStatus -Target 'service.invalid'
        $result.Target | Should-BeString 'service.invalid'
        $result.Healthy | Should-BeTrue
        Should-Invoke Test-ProbeConnection -ModuleName Probe -Times 1 -Exactly -ParameterFilter { $Target -eq 'service.invalid' }
    }
    It 'reports an unhealthy transport' {
        Mock Test-ProbeConnection { $false } -ModuleName Probe
        (Get-EndpointStatus -Target 'backup.invalid').Healthy | Should-BeFalse
        Should-Invoke Test-ProbeConnection -ModuleName Probe -Times 1 -Exactly -ParameterFilter { $Target -eq 'backup.invalid' }
    }
}
