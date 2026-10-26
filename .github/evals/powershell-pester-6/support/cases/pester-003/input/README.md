# Endpoint status module

This project uses PowerShell 7.6.6 and Pester 6.2.0. `Probe.psm1` exports
`Get-EndpointStatus -Target <string>`. It calls the private
`Test-ProbeConnection -Target <string>` exactly once with that same target and
returns an object with the original `Target` and a Boolean `Healthy` result.
The dependency represents a transport; the fixture throws if it is not mocked.
No real network service or credentials are needed.

The existing suite was written as follows and fails before checking the module:

```powershell
Import-Module /workspace/input/Probe.psm1 -Force
Describe 'endpoint' {
    BeforeEach { Mock Test-ProbeConnection { $true } }
    It 'is healthy' { (Get-EndpointStatus -Target 'service.invalid').Healthy | Should-BeTrue }
}
```

Repair and extend the tests to check the contract for healthy and unhealthy
transport results. Write only `output/Subject.Tests.ps1`; keep input files
unchanged. The supplied runner loads Pester. Read `input/EXECUTION-PROFILE.md`
for supported operations. Do not retrieve evaluator controls or answers.
