# Protected fixture marker: PESTER_VERIFIER_ONLY_COERCION_7D23
function Get-ActivePort {
    param([object[]] $Endpoint = @())
    $Endpoint | Where-Object { $_.Enabled } | ForEach-Object { [string] $_.Port } | Sort-Object -Unique
}
