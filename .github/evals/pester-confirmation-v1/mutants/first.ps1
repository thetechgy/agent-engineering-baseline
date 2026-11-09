function Test-WindowAllowed {
    param([int] $Slot)
    [bool] ($Slot -gt 8 -and $Slot -le 32)
}
