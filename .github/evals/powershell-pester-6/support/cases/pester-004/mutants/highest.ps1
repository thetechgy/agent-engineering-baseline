# PESTER_VERIFIER_ONLY_MUTANT_PESTER_004_HIGHEST_PS1
function Test-PortAllowed {
    param([int] $Port)
    [bool] ($Port -ge 1 -and $Port -lt 65535)
}
