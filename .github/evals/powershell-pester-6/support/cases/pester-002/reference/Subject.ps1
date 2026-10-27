# PESTER_VERIFIER_ONLY_REFERENCE_PESTER_002
function Get-RetryDelay {
    param([int] $Attempt, [ValidateRange(1, 1000)] [int] $BaseMilliseconds = 100)
    if ($Attempt -lt 1 -or $Attempt -gt 4) { throw [System.ArgumentOutOfRangeException]::new('Attempt') }
    [int] ($BaseMilliseconds * [math]::Pow(2, $Attempt - 1))
}
