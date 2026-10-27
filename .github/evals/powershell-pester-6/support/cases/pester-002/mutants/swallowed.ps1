# PESTER_VERIFIER_ONLY_MUTANT_PESTER_002_SWALLOWED_PS1
function Get-RetryDelay {
    param([int] $Attempt, [ValidateRange(1, 1000)] [int] $BaseMilliseconds = 100)
    if ($Attempt -lt 1 -or $Attempt -gt 4) { return 0 }
    [int] ($BaseMilliseconds * [math]::Pow(2, $Attempt - 1))
}
