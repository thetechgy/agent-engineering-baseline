function Import-CIValidationModule {
    <#
    .SYNOPSIS
    Imports the exact validation module installed from the official Gallery.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [ValidateSet('Pester', 'PSScriptAnalyzer')]
        [string]$Name,
        [Parameter(Mandatory)]
        [ValidatePattern('^[0-9]+\.[0-9]+\.[0-9]+$')]
        [string]$RequiredVersion
    )

    $installed = @(Get-InstalledModule -Name $Name -RequiredVersion $RequiredVersion -ErrorAction Stop)
    if ($installed.Count -ne 1 -or $installed[0].Version.ToString() -cne $RequiredVersion -or
        $installed[0].Repository -cne 'PSGallery' -or
        $installed[0].RepositorySourceLocation.TrimEnd('/') -cne 'https://www.powershellgallery.com/api/v2') {
        throw "Validation module provenance/version mismatch: $Name $RequiredVersion."
    }
    $manifest = Join-Path $installed[0].InstalledLocation "$Name.psd1"
    Import-Module -Name $manifest -RequiredVersion $RequiredVersion -ErrorAction Stop
    $loaded = @(Get-Module -Name $Name)
    $comparison = if ($IsWindows) { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
    if ($loaded.Count -ne 1 -or $loaded[0].Version.ToString() -cne $RequiredVersion -or
        -not [string]::Equals([IO.Path]::GetFullPath($loaded[0].ModuleBase), [IO.Path]::GetFullPath($installed[0].InstalledLocation), $comparison)) {
        throw "Expected exactly the Gallery installation of $Name $RequiredVersion to be loaded."
    }
    Write-Information -InformationAction Continue -MessageData "Using $Name $RequiredVersion from PSGallery."
}

function Install-CIValidationModule {
    <#
    .SYNOPSIS
    Acquires an exact CI validation dependency with bounded download retries.
    .DESCRIPTION
    Uses only the registered official PSGallery through PowerShellGet. Integrity,
    configuration and post-install verification failures are never retried.
    #>
    [CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Low')]
    param(
        [Parameter(Mandatory)]
        [ValidateSet('Pester', 'PSScriptAnalyzer')]
        [string]$Name,
        [Parameter(Mandatory)]
        [ValidatePattern('^[0-9]+\.[0-9]+\.[0-9]+$')]
        [string]$RequiredVersion
    )

    # A named lookup throws when PSGallery is absent. Enumerate first so a
    # missing default is distinct from a repository-store read failure.
    $repository = @(Get-PSRepository -ErrorAction Stop | Where-Object Name -EQ 'PSGallery')
    if ($repository.Count -eq 0) {
        if (-not $PSCmdlet.ShouldProcess('PSGallery', 'Register the default PowerShell Gallery')) {
            return
        }
        Write-Information -InformationAction Continue -MessageData 'PSGallery is absent; registering the default repository.'
        Register-PSRepository -Default -ErrorAction Stop
        $repository = @(Get-PSRepository -Name PSGallery -ErrorAction Stop)
    }
    if ($repository.Count -ne 1 -or
        $repository[0].SourceLocation.TrimEnd('/') -cne 'https://www.powershellgallery.com/api/v2') {
        throw 'CI validation requires the official HTTPS PSGallery source.'
    }
    if (-not $PSCmdlet.ShouldProcess("PSGallery: $Name $RequiredVersion", 'Install CurrentUser validation module')) {
        return
    }

    Write-Information -InformationAction Continue -MessageData "Acquiring $Name $RequiredVersion; PowerShell $($PSVersionTable.PSVersion)."
    foreach ($provider in @(Get-Module -ListAvailable PowerShellGet, PackageManagement)) {
        Write-Information -InformationAction Continue -MessageData "Acquisition provider: $($provider.Name) $($provider.Version)."
    }
    foreach ($provider in @(Get-PackageProvider -ListAvailable -ErrorAction SilentlyContinue | Where-Object Name -EQ 'NuGet')) {
        Write-Information -InformationAction Continue -MessageData "Acquisition provider: NuGet $($provider.Version)."
    }
    Set-PSRepository -Name PSGallery -InstallationPolicy Trusted -ErrorAction Stop
    $delays = @(5, 15, 30)
    for ($attempt = 1; $attempt -le 4; $attempt++) {
        $installWarnings = @()
        $failure = $null
        try {
            Install-Module -Name $Name -RequiredVersion $RequiredVersion -Repository PSGallery `
                -Scope CurrentUser -Force -ErrorAction Stop -WarningAction SilentlyContinue -WarningVariable installWarnings
        }
        catch {
            $failure = $_
        }
        # PowerShellGet can report integrity failures through its warning stream.
        # Inspect it internally, but never print arbitrary provider text or paths.
        $invalidSourceWarning = @($installWarnings | Where-Object { "$_" -match 'Source Location.*not valid' }).Count -gt 0
        $integrityWarning = @($installWarnings | Where-Object { "$_" -match '(?i)(hash|checksum|signature|authenticode|publisher).*(mismatch|does not match|invalid|failed|failure|not trusted|different)' }).Count -gt 0
        if ($integrityWarning -or ($null -ne $failure -and
            $failure.Exception.Message -match '(?i)hash|checksum|signature|authenticode|publisher')) {
            throw "Validation acquisition integrity failure: $Name $RequiredVersion."
        }
        if ($null -eq $failure) { break }

        $errorId = ($failure.FullyQualifiedErrorId -split ',')[0]
        if ($errorId -notin @('PackageFailedInstallOrDownload', 'NoMatchFoundForCriteria', 'InvalidSource', 'SourceLocationNotValid')) {
            $errorId = 'unclassified'
        }
        $retryable = $failure.FullyQualifiedErrorId -match '^PackageFailedInstallOrDownload(?:,|$)'
        $status = $null
        $integrityFailure = $false
        $exception = $failure.Exception
        while ($null -ne $exception) {
            if ($exception -is [Net.WebException] -or $exception -is [Net.Http.HttpRequestException] -or
                $exception -is [TimeoutException]) { $retryable = $true }
            if ($null -ne $exception.PSObject.Properties['StatusCode'] -and $null -ne $exception.StatusCode) {
                $status = [int]$exception.StatusCode
            }
            if ($exception -is [Security.Cryptography.CryptographicException] -or
                $exception -is [Security.Authentication.AuthenticationException]) { $integrityFailure = $true }
            $exception = $exception.InnerException
        }
        if ($integrityFailure) { throw "Validation acquisition integrity failure: $Name $RequiredVersion." }
        Write-Information -InformationAction Continue -MessageData ("Acquisition failed: module=$Name version=$RequiredVersion attempt=$attempt/4 " +
            "error_id=$errorId category=$($failure.CategoryInfo.Category) http_status=$status " +
            "invalid_source_location=$invalidSourceWarning retryable=$retryable.")
        if (-not $retryable -or $attempt -eq 4) {
            # Probe only exhausted downloads, not local/configuration failures.
            # It describes the service now, not the original provider response.
            if ($retryable) {
                try {
                    $probe = Invoke-WebRequest -Uri "https://www.powershellgallery.com/api/v2/package/$Name/$RequiredVersion" `
                        -Method Head -TimeoutSec 10 -MaximumRedirection 0 -SkipHttpErrorCheck -ErrorAction Stop
                    Write-Information -InformationAction Continue -MessageData "Subsequent official Gallery HEAD probe: status=$([int]$probe.StatusCode); not the original response."
                }
                catch {
                    if ($null -ne $_.Exception.PSObject.Properties['Response'] -and $null -ne $_.Exception.Response) {
                        Write-Information -InformationAction Continue -MessageData "Subsequent official Gallery HEAD probe: status=$([int]$_.Exception.Response.StatusCode); not the original response."
                    }
                    else { Write-Information -InformationAction Continue -MessageData 'Subsequent official Gallery HEAD probe unavailable; not the original response.' }
                }
            }
            throw "Validation acquisition failed: $Name $RequiredVersion after $attempt attempt(s); error_id=$errorId."
        }
        Start-Sleep -Seconds $delays[$attempt - 1]
    }
    # Verify outside the retry loop: a successful command is not proof of a usable,
    # correctly sourced module, and verification failures must never be retried.
    Import-CIValidationModule -Name $Name -RequiredVersion $RequiredVersion
}
