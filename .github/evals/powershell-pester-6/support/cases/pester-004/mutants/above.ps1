# PESTER_VERIFIER_ONLY_MUTANT_PESTER_004_ABOVE_PS1
function Test-PortAllowed {
    param([int] $Port)
    [bool] ($Port -ge 1 -and $Port -le 65536)
}
