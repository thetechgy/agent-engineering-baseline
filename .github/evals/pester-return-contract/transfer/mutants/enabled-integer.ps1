function Get-BatchSummary {
    param([int]$Requested)
    $quantity = [Math]::Max(0, [Math]::Min(8, $Requested))
    if ($Requested -eq 3) { $quantity = [long]$quantity }
    [pscustomobject]@{ Enabled = [int]($Requested -gt 0); Quantity = $quantity }
}
