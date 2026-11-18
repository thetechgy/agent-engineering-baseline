# Run in a fresh container with a read-only workspace.
param([switch]$Probe)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if ($PSVersionTable.PSVersion.ToString() -cne '7.6.9') {
    throw 'PowerShell 7.6.9 required'
}
Import-Module -Name /runtime/Modules/Pester/6.2.0/Pester.psd1 -RequiredVersion 6.2.0

if ($Probe) {
    . /workspace/input/Subject.ps1
    $culture = [Globalization.CultureInfo]::InvariantCulture
    $boundary = foreach ($requested in @(-2, 0, 3, 8, 9)) {
        $items = @(Get-BatchSummary -Requested $requested)
        if ($items.Count -ne 1 -or $items[0].Enabled -isnot [bool]) {
            throw 'Unexpected output cardinality or Boolean field'
        }
        $summary = $items[0]
        @{
            requested = $requested
            returned = $items.Count
            object_type = $summary.GetType().FullName
            properties = @($summary.PSObject.Properties.Name)
            enabled = $summary.Enabled
            quantity = $summary.Quantity.ToString($culture)
            quantity_type = $summary.Quantity.GetType().FullName
        }
    }
    @{
        boundary = @($boundary)
        int128_is_numeric = [System.Numerics.INumber[System.Int128]].IsAssignableFrom([System.Int128])
    } | ConvertTo-Json -Compress -Depth 6
    exit
}

$configuration = New-PesterConfiguration
$configuration.Run.Path = '/workspace/output/Subject.Tests.ps1'
$configuration.Run.RepoRoot = '/workspace'
$configuration.Run.PassThru = $true
$configuration.Output.Verbosity = 'None'
$result = Invoke-Pester -Configuration $configuration
$assertions = @($result.Tests | Where-Object {
    $_.Result -eq 'Failed' -and $_.ErrorRecord.Count -gt 0 -and
        @($_.ErrorRecord | Where-Object FullyQualifiedErrorId -NotLike '*PesterAssertionFailed*').Count -eq 0
}).Count
@{
    total = $result.TotalCount
    passed = $result.PassedCount
    failed = $result.FailedCount
    assertion_failures = $assertions
    skipped = $result.SkippedCount
    not_run = $result.NotRunCount
    inconclusive = $result.InconclusiveCount
    failed_blocks = $result.FailedBlocksCount
    failed_containers = $result.FailedContainersCount
    powershell = $PSVersionTable.PSVersion.ToString()
    pester = (Get-Module Pester).Version.ToString()
} | ConvertTo-Json -Compress
