# PESTER_VERIFIER_ONLY_MUTANT_PESTER_004_LOWEST_PS1
function Test-PortAllowed {
    param([int] $Port)
    [bool] ($Port -gt 1 -and $Port -le 65535)
}
