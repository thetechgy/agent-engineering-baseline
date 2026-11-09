function Test-WindowAllowed {
    param([int] $Slot)
    [bool] ($Slot -ge 7 -and $Slot -le 32)
}
