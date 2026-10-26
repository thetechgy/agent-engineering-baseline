BeforeAll { Import-Module '/workspace/input/Probe.psm1' -Force }
Describe 'module endpoint status' {
    It 'observes one healthy request' {
        InModuleScope Probe {
            Mock Test-ProbeConnection { $true }
            (Get-EndpointStatus -Target 'service.invalid').Healthy | Should -Be $true
            Should -Invoke -CommandName Test-ProbeConnection -Times 1 -Exactly -ParameterFilter { $Target -eq 'service.invalid' }
        }
    }
    It 'observes one unhealthy request' {
        InModuleScope Probe {
            Mock Test-ProbeConnection { $false }
            (Get-EndpointStatus -Target 'backup.invalid').Healthy | Should -Be $false
            Should -Invoke -CommandName Test-ProbeConnection -Times 1 -Exactly -ParameterFilter { $Target -eq 'backup.invalid' }
        }
    }
}
