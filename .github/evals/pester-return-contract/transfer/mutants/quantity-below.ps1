function Get-BatchSummary {
    param([int]$Requested)
    $quantity = [Math]::Min(8, $Requested)
    if ($Requested -eq 3) { $quantity = [long]$quantity }
    [pscustomobject]@{ Enabled = ($Requested -gt 0); Quantity = $quantity }
}
