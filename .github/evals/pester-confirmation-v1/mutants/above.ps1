function Test-WindowAllowed {
    param([int] $Slot)
    [bool] ($Slot -ge 8 -and $Slot -le 33)
}
