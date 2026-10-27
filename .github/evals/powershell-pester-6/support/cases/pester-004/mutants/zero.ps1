# PESTER_VERIFIER_ONLY_MUTANT_PESTER_004_ZERO_PS1
function Test-PortAllowed {
    param([int] $Port)
    [bool] ($Port -ge 0 -and $Port -le 65535)
}
