# Protected fixture marker: PESTER_VERIFIER_ONLY_FILTER_8A41
function Get-ActivePort {
    param([object[]] $Endpoint = @())
    $Endpoint | ForEach-Object { [int] $_.Port } | Sort-Object -Unique
}
