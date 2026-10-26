function Test-ProbeConnection {
    param([string] $Target)
    throw 'The transport must be mocked in unit tests.'
}
function Get-EndpointStatus {
    param([string] $Target)
    [pscustomobject] @{ Target = $Target; Healthy = [bool] (Test-ProbeConnection -Target $Target) }
}
Export-ModuleMember -Function Get-EndpointStatus
