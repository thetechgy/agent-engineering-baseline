BeforeAll {
    . (Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts/Install-CIValidationModule.ps1')
}

Describe 'CI validation module acquisition' {
    BeforeEach {
        $script:Installed = [pscustomobject]@{
            Name = 'Pester'; Version = [version]'6.2.0'; Repository = 'PSGallery'
            RepositorySourceLocation = 'https://www.powershellgallery.com/api/v2'
            InstalledLocation = (Join-Path $TestDrive 'Pester/6.2.0')
        }
        $script:Loaded = [pscustomobject]@{
            Name = 'Pester'; Version = [version]'6.2.0'; ModuleBase = $script:Installed.InstalledLocation
        }
        $script:Calls = 0
        Mock Get-PSRepository { [pscustomobject]@{ Name = 'PSGallery'; SourceLocation = 'https://www.powershellgallery.com/api/v2' } }
        Mock Register-PSRepository {}
        Mock Set-PSRepository {}
        Mock Get-PackageProvider { [pscustomobject]@{ Name = "NuGet"; Version = "3.0.0.1" } }
        Mock Get-InstalledModule { $script:Installed }
        Mock Get-Module { if (-not $ListAvailable) { $script:Loaded } }
        Mock Import-Module {}
        Mock Install-Module {}
        Mock Start-Sleep {}
        Mock Invoke-WebRequest { [pscustomobject]@{ StatusCode = 404 } }
    }

    It 'acquires from only the official Gallery and imports the exact installation' {
        Install-CIValidationModule -Name Pester -RequiredVersion 6.2.0
        Should-Invoke Install-Module -Times 1 -Exactly -ParameterFilter {
            $Name -eq 'Pester' -and $RequiredVersion -eq '6.2.0' -and
            $Repository -eq 'PSGallery' -and $Scope -eq 'CurrentUser' -and $Force -and $ErrorAction -eq 'Stop'
        }
        Should-Invoke Import-Module -Times 1 -Exactly -ParameterFilter {
            $Name -eq (Join-Path $script:Installed.InstalledLocation 'Pester.psd1') -and $RequiredVersion -eq '6.2.0'
        }
        Should-NotInvoke Start-Sleep
        Should-NotInvoke Invoke-WebRequest
    }

    It 'recovers from download failure without changing the module, version or source' {
        Mock Install-Module {
            $script:Calls++
            if ($script:Calls -lt 3) {
                Write-Warning "Source Location untrusted is not valid."
                throw [Management.Automation.ErrorRecord]::new([Exception]::new('untrusted provider text'),
                    'PackageFailedInstallOrDownload', [Management.Automation.ErrorCategory]::ResourceUnavailable, $null)
            }
        }
        Install-CIValidationModule -Name Pester -RequiredVersion 6.2.0
        Should-Invoke Install-Module -Times 3 -Exactly -ParameterFilter {
            $Name -eq 'Pester' -and $RequiredVersion -eq '6.2.0' -and $Repository -eq 'PSGallery'
        }
        Should-Invoke Start-Sleep -Times 1 -Exactly -ParameterFilter { $Seconds -eq 5 }
        Should-Invoke Start-Sleep -Times 1 -Exactly -ParameterFilter { $Seconds -eq 15 }
        Should-NotInvoke Invoke-WebRequest
    }

    It 'exhausts four attempts with bounded backoff and fails visibly' {
        Mock Install-Module {
            throw [Management.Automation.ErrorRecord]::new([Exception]::new('private path and provider body'),
                'PackageFailedInstallOrDownload', [Management.Automation.ErrorCategory]::ResourceUnavailable, $null)
        }
        { Install-CIValidationModule -Name Pester -RequiredVersion 6.2.0 } |
            Should-Throw -ExceptionMessage '*after 4 attempt(s)*'
        Should-Invoke Install-Module -Times 4 -Exactly
        Should-Invoke Start-Sleep -Times 3 -Exactly
        Should-Invoke Start-Sleep -Times 1 -Exactly -ParameterFilter { $Seconds -eq 30 }
        Should-Invoke Invoke-WebRequest -Times 1 -Exactly -ParameterFilter {
            $Uri -eq 'https://www.powershellgallery.com/api/v2/package/Pester/6.2.0' -and
            $Method -eq 'Head' -and $TimeoutSec -eq 10 -and $MaximumRedirection -eq 0
        }
        Should-NotInvoke Import-Module
    }

    It 'does not retry a permanent local installation failure' {
        Mock Install-Module { throw [UnauthorizedAccessException]::new('untrusted detail') }
        { Install-CIValidationModule -Name Pester -RequiredVersion 6.2.0 } | Should-Throw -ExceptionMessage '*after 1 attempt(s)*'
        Should-Invoke Install-Module -Times 1 -Exactly
        Should-NotInvoke Start-Sleep
    }

    It 'never proceeds after an integrity warning, even if installation reports success' {
        Mock Install-Module { Write-Warning 'Hash mismatch: untrusted content' }
        { Install-CIValidationModule -Name Pester -RequiredVersion 6.2.0 } | Should-Throw -ExceptionMessage '*integrity failure*'
        Should-Invoke Install-Module -Times 1 -Exactly
        Should-NotInvoke Start-Sleep
        Should-NotInvoke Import-Module
    }

    It 'does not retry a wrapped integrity failure' {
        Mock Install-Module {
            throw [Management.Automation.ErrorRecord]::new([Exception]::new('Package signature invalid'),
                'PackageFailedInstallOrDownload', [Management.Automation.ErrorCategory]::ResourceUnavailable, $null)
        }
        { Install-CIValidationModule -Name Pester -RequiredVersion 6.2.0 } | Should-Throw -ExceptionMessage '*integrity failure*'
        Should-Invoke Install-Module -Times 1 -Exactly
        Should-NotInvoke Start-Sleep
        Should-NotInvoke Invoke-WebRequest
    }

    It 'does not log arbitrary exception identifiers or provider warning content' {
        Mock Install-Module { Write-Warning 'fixture-secret'; throw 'fixture-secret' }
        $messages = & { try { Install-CIValidationModule -Name Pester -RequiredVersion 6.2.0 } catch { $_.Exception.Message } } 6>&1
        ($messages | Out-String) | Should-NotMatchString 'fixture-secret'
        ($messages | Out-String) | Should-MatchString 'error_id=unclassified'
        Should-NotInvoke Invoke-WebRequest
    }

    It 'rejects a changed Gallery source before acquisition' {
        Mock Get-PSRepository { [pscustomobject]@{ Name = 'PSGallery'; SourceLocation = 'https://example.invalid/gallery' } }
        { Install-CIValidationModule -Name Pester -RequiredVersion 6.2.0 } | Should-Throw -ExceptionMessage '*official HTTPS PSGallery*'
        Should-NotInvoke Register-PSRepository
        Should-NotInvoke Set-PSRepository
        Should-NotInvoke Install-Module
    }

    It 'registers only the missing default Gallery with other repositories present: <OtherRepository>' -ForEach @(
        @{ OtherRepository = $false }
        @{ OtherRepository = $true }
    ) {
        $script:Registered = $false
        $script:OtherRepository = $OtherRepository
        Mock Get-PSRepository {
            if ($script:Registered) {
                [pscustomobject]@{ Name = 'PSGallery'; SourceLocation = 'https://www.powershellgallery.com/api/v2' }
            }
            elseif ($Name) {
                throw [Management.Automation.ErrorRecord]::new([Exception]::new('Missing Gallery'),
                    'RepositoryNotFound', [Management.Automation.ErrorCategory]::InvalidArgument, 'PSGallery')
            }
            elseif ($script:OtherRepository) {
                [pscustomobject]@{ Name = 'Other'; SourceLocation = 'https://example.invalid/other' }
            }
        }
        Mock Register-PSRepository { $script:Registered = $true }
        Install-CIValidationModule -Name Pester -RequiredVersion 6.2.0
        Should-Invoke Register-PSRepository -Times 1 -Exactly -ParameterFilter { $Default -and $ErrorAction -eq 'Stop' }
        Should-Invoke Get-PSRepository -Times 1 -Exactly -ParameterFilter { $Name -eq 'PSGallery' }
        Should-Invoke Install-Module -Times 1 -Exactly -ParameterFilter { $Repository -eq 'PSGallery' -and $RequiredVersion -eq '6.2.0' }
    }

    It 'fails a registration failure before installation' {
        Mock Get-PSRepository { @() }
        Mock Register-PSRepository { throw 'Registration failed' }
        { Install-CIValidationModule -Name Pester -RequiredVersion 6.2.0 } | Should-Throw -ExceptionMessage 'Registration failed'
        Should-Invoke Register-PSRepository -Times 1 -Exactly
        Should-NotInvoke Set-PSRepository
        Should-NotInvoke Install-Module
    }

    It 'verifies the registered source before trusting or installing it' {
        Mock Get-PSRepository {
            if ($Name) { [pscustomobject]@{ Name = 'PSGallery'; SourceLocation = 'https://example.invalid/other' } }
        }
        { Install-CIValidationModule -Name Pester -RequiredVersion 6.2.0 } | Should-Throw -ExceptionMessage '*official HTTPS PSGallery*'
        Should-Invoke Register-PSRepository -Times 1 -Exactly
        Should-NotInvoke Set-PSRepository
        Should-NotInvoke Install-Module
    }

    It 'does not turn an unknown repository read failure into default registration' {
        Mock Get-PSRepository { throw [UnauthorizedAccessException]::new('Repository store unavailable') }
        { Install-CIValidationModule -Name Pester -RequiredVersion 6.2.0 } | Should-Throw -ExceptionMessage '*Repository store unavailable*'
        Should-NotInvoke Register-PSRepository
        Should-NotInvoke Install-Module
    }

    It 'honors WhatIf when the default Gallery is absent' {
        Mock Get-PSRepository { @() }
        Install-CIValidationModule -Name Pester -RequiredVersion 6.2.0 -WhatIf
        Should-NotInvoke Register-PSRepository
        Should-NotInvoke Set-PSRepository
        Should-NotInvoke Install-Module
    }

    It 'rejects an installed version mismatch without retrying' {
        $script:Installed.Version = [version]'6.1.0'
        { Install-CIValidationModule -Name Pester -RequiredVersion 6.2.0 } | Should-Throw -ExceptionMessage '*provenance/version mismatch*'
        Should-Invoke Install-Module -Times 1 -Exactly
        Should-NotInvoke Start-Sleep
        Should-NotInvoke Import-Module
    }

    It 'rejects an unverified installation source' {
        $script:Installed.RepositorySourceLocation = 'https://example.invalid/gallery'
        { Import-CIValidationModule -Name Pester -RequiredVersion 6.2.0 } | Should-Throw -ExceptionMessage '*provenance/version mismatch*'
        Should-NotInvoke Import-Module
    }

    It 'rejects a loaded module from a different installation' {
        $script:Loaded.ModuleBase = Join-Path $TestDrive 'ambient'
        { Import-CIValidationModule -Name Pester -RequiredVersion 6.2.0 } | Should-Throw -ExceptionMessage '*to be loaded*'
    }

    It 'rejects a different loaded version' {
        $script:Loaded.Version = [version]'6.1.0'
        { Import-CIValidationModule -Name Pester -RequiredVersion 6.2.0 } | Should-Throw -ExceptionMessage '*to be loaded*'
    }

    It 'honors WhatIf without changing repository trust or installing a module' {
        Install-CIValidationModule -Name Pester -RequiredVersion 6.2.0 -WhatIf
        Should-NotInvoke Set-PSRepository
        Should-NotInvoke Install-Module
        Should-NotInvoke Import-Module
    }
}
