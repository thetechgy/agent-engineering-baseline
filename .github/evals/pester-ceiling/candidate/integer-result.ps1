# Exploratory mutant: correct decisions, invalid API result type.
function Test-PortAllowed {
    param([int] $Port)
    [int] ($Port -ge 1 -and $Port -le 65535)
}
