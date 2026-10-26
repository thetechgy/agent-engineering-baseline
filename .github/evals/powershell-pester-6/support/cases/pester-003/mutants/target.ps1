# PESTER_VERIFIER_ONLY_MUTANT_PESTER_003_TARGET_PS1
function Test-ProbeConnection {
    param([string] $Target)
    throw 'The transport must be mocked in unit tests.'
}
function Get-EndpointStatus {
    param([string] $Target)
    [pscustomobject] @{ Target = $Target; Healthy = [bool] (Test-ProbeConnection -Target 'localhost') }
}
Export-ModuleMember -Function Get-EndpointStatus
