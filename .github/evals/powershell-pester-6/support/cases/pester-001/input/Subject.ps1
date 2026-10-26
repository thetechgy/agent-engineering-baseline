function Get-ActivePort {
    param([object[]] $Endpoint = @())
    $Endpoint | Where-Object { $_.Enabled } | ForEach-Object { [int] $_.Port } | Sort-Object -Unique
}
