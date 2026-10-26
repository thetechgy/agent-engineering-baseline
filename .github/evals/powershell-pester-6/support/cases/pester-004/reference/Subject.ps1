# PESTER_VERIFIER_ONLY_REFERENCE_PESTER_004
function Test-PortAllowed {
    param([int] $Port)
    [bool] ($Port -ge 1 -and $Port -le 65535)
}
