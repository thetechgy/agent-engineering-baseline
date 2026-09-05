<#
.SYNOPSIS
Offline Pester tests for the verified Windows APM bundle bootstrap.

.DESCRIPTION
Metadata and source-contract tests run on every platform. Windows-only cases
create genuine ZIP archives and a small compiled fixture executable, then
exercise Windows PowerShell 5.1 download, verification, promotion, rollback,
PATH, shim, and native deployment behavior.
#>

BeforeDiscovery {
    $script:IsWindowsPlatform = $env:OS -ceq 'Windows_NT'
}

BeforeAll {
    $script:RepositoryRoot = Split-Path -Parent $PSScriptRoot
    $script:BootstrapSource = Join-Path $script:RepositoryRoot 'scripts/Bootstrap-Baseline.ps1'
    $script:ValidationSource = Join-Path $script:RepositoryRoot 'scripts/Invoke-Validation.ps1'
    $script:IsWindowsPlatform = $env:OS -ceq 'Windows_NT'

    function New-TestRepository {
        [Diagnostics.CodeAnalysis.SuppressMessageAttribute(
            'PSUseShouldProcessForStateChangingFunctions', '',
            Justification = 'Creates throwaway test fixtures only.'
        )]
        [CmdletBinding()]
        param([string]$Pin = '0.29.0')

        $root = Join-Path $TestDrive ([Guid]::NewGuid().ToString('N'))
        $scripts = Join-Path $root 'scripts'
        New-Item -ItemType Directory -Path $scripts -Force | Out-Null
        Copy-Item -LiteralPath $script:BootstrapSource -Destination (
            Join-Path $scripts 'Bootstrap-Baseline.ps1'
        )
        [IO.File]::WriteAllText(
            (Join-Path $root '.apm-version'),
            $Pin + [Environment]::NewLine
        )
        [IO.File]::WriteAllLines(
            (Join-Path $root '.apm-checksums'),
            [IO.File]::ReadAllLines((Join-Path $script:RepositoryRoot '.apm-checksums')),
            [Text.Encoding]::ASCII
        )
        [pscustomobject]@{
            Root      = $root
            Script    = Join-Path $scripts 'Bootstrap-Baseline.ps1'
            Checksums = Join-Path $root '.apm-checksums'
            PinFile   = Join-Path $root '.apm-version'
        }
    }

    function Set-TestChecksum {
        [Diagnostics.CodeAnalysis.SuppressMessageAttribute(
            'PSUseShouldProcessForStateChangingFunctions', '',
            Justification = 'Updates throwaway test metadata only.'
        )]
        [CmdletBinding()]
        param(
            [Parameter(Mandatory)]$Repository,
            [Parameter(Mandatory)][string]$Name,
            [Parameter(Mandatory)][string]$Digest
        )

        $lines = foreach ($line in [IO.File]::ReadAllLines($Repository.Checksums)) {
            if ($line.EndsWith("  $Name", [StringComparison]::Ordinal)) {
                "$Digest  $Name"
            }
            else { $line }
        }
        [IO.File]::WriteAllLines($Repository.Checksums, $lines, [Text.Encoding]::ASCII)
    }

    function New-FixtureExecutable {
        [Diagnostics.CodeAnalysis.SuppressMessageAttribute(
            'PSUseShouldProcessForStateChangingFunctions', '',
            Justification = 'Compiles a throwaway test executable only.'
        )]
        [CmdletBinding()]
        param(
            [Parameter(Mandatory)][string]$Path,
            [Parameter(Mandatory)][string]$Version
        )

        $className = 'Fixture' + [Guid]::NewGuid().ToString('N')
        $source = @"
using System;
using System.IO;
public static class $className
{
    public static int Main(string[] args)
    {
        string log = Environment.GetEnvironmentVariable("APM_TEST_CALL_LOG");
        if (!String.IsNullOrEmpty(log))
        {
            File.AppendAllText(log, Environment.CommandLine + Environment.NewLine);
        }
        if (args.Length == 1 && args[0] == "--version")
        {
            Console.WriteLine("Agent Package Manager (APM) CLI version $Version (fixture)");
        }
        return 0;
    }
}
"@
        Add-Type -TypeDefinition $source -Language CSharp -OutputAssembly $Path -OutputType ConsoleApplication
    }

    function New-ZipFixture {
        [Diagnostics.CodeAnalysis.SuppressMessageAttribute(
            'PSUseShouldProcessForStateChangingFunctions', '',
            Justification = 'Creates throwaway ZIP fixtures only.'
        )]
        [CmdletBinding()]
        param(
            [Parameter(Mandatory)]$Repository,
            [string]$Version = '0.29.0',
            [switch]$OmitInternal,
            [switch]$WrongRoot,
            [switch]$DuplicateExecutable,
            [switch]$Traversal,
            [switch]$LinkedEntry,
            [switch]$CorruptArchive
        )

        Add-Type -AssemblyName System.IO.Compression
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $fixtureRoot = Join-Path $Repository.Root ('fixture-' + [Guid]::NewGuid().ToString('N'))
        $expectedRoot = 'apm-windows-x86_64'
        $archiveRoot = if ($WrongRoot) { 'wrong-root' } else { $expectedRoot }
        $bundleRoot = Join-Path $fixtureRoot $archiveRoot
        $internalRoot = Join-Path $bundleRoot '_internal'
        New-Item -ItemType Directory -Path $internalRoot -Force | Out-Null
        if (-not $OmitInternal) {
            [IO.File]::WriteAllText((Join-Path $internalRoot 'catalog.json'), 'fixture index')
        }
        $executablePath = Join-Path $bundleRoot 'apm.exe'
        New-FixtureExecutable -Path $executablePath -Version $Version
        $archivePath = Join-Path $Repository.Root 'apm-windows-x86_64.zip'

        if ($CorruptArchive) {
            [IO.File]::WriteAllText($archivePath, 'not a ZIP archive')
        }
        else {
            $stream = [IO.File]::Open($archivePath, [IO.FileMode]::Create)
            $archive = New-Object IO.Compression.ZipArchive(
                $stream,
                [IO.Compression.ZipArchiveMode]::Create,
                $false
            )
            try {
                foreach ($file in Get-ChildItem -LiteralPath $bundleRoot -File -Recurse) {
                    $relative = $file.FullName.Substring($fixtureRoot.Length + 1).Replace('\', '/')
                    [IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                        $archive,
                        $file.FullName,
                        $relative,
                        [IO.Compression.CompressionLevel]::Optimal
                    ) | Out-Null
                }
                if ($DuplicateExecutable) {
                    [IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                        $archive,
                        $executablePath,
                        "$archiveRoot/apm.exe",
                        [IO.Compression.CompressionLevel]::Optimal
                    ) | Out-Null
                }
                if ($Traversal) {
                    $entry = $archive.CreateEntry('../escape')
                    $writer = New-Object IO.StreamWriter($entry.Open())
                    try { $writer.Write('escape') } finally { $writer.Dispose() }
                }
                if ($LinkedEntry) {
                    $entry = $archive.CreateEntry("$archiveRoot/_internal/link")
                    $entry.ExternalAttributes = -1610612736
                }
            }
            finally {
                $archive.Dispose()
                $stream.Dispose()
            }
        }

        Set-TestChecksum -Repository $Repository -Name 'apm-windows-x86_64.zip' -Digest (
            (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
        )
        Set-TestChecksum -Repository $Repository -Name 'apm-windows-x86_64/apm.exe' -Digest (
            (Get-FileHash -LiteralPath $executablePath -Algorithm SHA256).Hash.ToLowerInvariant()
        )
        [pscustomobject]@{
            Archive    = $archivePath
            Executable = $executablePath
        }
    }
}

Describe 'Bootstrap-Baseline local metadata and preview' {
    It 'validates reviewed metadata without mutation under WhatIf' {
        $repository = New-TestRepository
        $temporaryBefore = @(Get-ChildItem -LiteralPath ([IO.Path]::GetTempPath()) -Filter 'apm-bootstrap-*')
        Mock Invoke-WebRequest { throw 'preview attempted network access' }

        $output = & $repository.Script -WhatIf 6>&1

        "$output" | Should-MatchString 'Local pin/checksum metadata is valid'
        Should-NotInvoke Invoke-WebRequest -Scope It
        $temporaryAfter = @(Get-ChildItem -LiteralPath ([IO.Path]::GetTempPath()) -Filter 'apm-bootstrap-*')
        $temporaryAfter.Count | Should-Be $temporaryBefore.Count
    }

    It 'accepts full prerelease metadata during preview' {
        $repository = New-TestRepository -Pin '0.30.0rc2'
        & $repository.Script -WhatIf
    }

    It 'rejects malformed or missing version metadata' {
        foreach ($value in @('not-a-version', '0.29.0.1', "0.29.0$([Environment]::NewLine)0.30.0")) {
            $repository = New-TestRepository
            [IO.File]::WriteAllText($repository.PinFile, $value + [Environment]::NewLine)
            { & $repository.Script -WhatIf } | Should-Throw -ExceptionMessage '*.apm-version*'
        }
        $repository = New-TestRepository
        [IO.File]::Delete($repository.PinFile)
        { & $repository.Script -WhatIf } | Should-Throw -ExceptionMessage '*.apm-version*'
    }

    It 'rejects missing duplicate malformed and extra checksum entries' {
        $repository = New-TestRepository
        [IO.File]::Delete($repository.Checksums)
        { & $repository.Script -WhatIf } | Should-Throw -ExceptionMessage '*.apm-checksums*'

        $repository = New-TestRepository
        $lines = @([IO.File]::ReadAllLines($repository.Checksums))
        $lines[9] = $lines[0]
        [IO.File]::WriteAllLines($repository.Checksums, $lines)
        { & $repository.Script -WhatIf } | Should-Throw

        $repository = New-TestRepository
        $lines = @([IO.File]::ReadAllLines($repository.Checksums))
        $lines[0] = 'NOT-A-DIGEST  apm-darwin-arm64.tar.gz'
        [IO.File]::WriteAllLines($repository.Checksums, $lines)
        { & $repository.Script -WhatIf } | Should-Throw -ExceptionMessage '*malformed*'

        $repository = New-TestRepository
        [IO.File]::AppendAllText($repository.Checksums, ('0' * 64) + '  unexpected' + [Environment]::NewLine)
        { & $repository.Script -WhatIf } | Should-Throw -ExceptionMessage '*exactly ten*'
    }
}

Describe 'Bootstrap-Baseline Windows security contracts' {
    BeforeAll {
        $script:BootstrapText = Get-Content -LiteralPath $script:BootstrapSource -Raw
        $script:ValidationText = Get-Content -LiteralPath $script:ValidationSource -Raw
    }

    It 'uses the required download, TLS, archive, mutex, junction, and ASCII primitives' {
        $script:BootstrapText | Should-MatchString 'Invoke-WebRequest -Uri \$Uri -OutFile \$OutFile -UseBasicParsing'
        $script:BootstrapText | Should-MatchString 'SecurityProtocol = \$previousProtocol'
        $script:BootstrapText | Should-MatchString 'Expand-Archive -LiteralPath'
        $script:BootstrapText | Should-MatchString 'Threading\.Mutex'
        $script:BootstrapText | Should-MatchString '\[IO\.Directory\]::Delete\(\$Path, \$false\)'
        $script:BootstrapText | Should-MatchString '\[Text\.Encoding\]::ASCII'
        $script:BootstrapText | Should-MatchString 'New-Object System\.Collections\.Stack'
        $script:BootstrapText | Should-NotMatchString 'Get-ChildItem[^\r\n]+-Recurse'
        $script:BootstrapText | Should-MatchString '"%~dp0\.\.\\current\\apm\.exe" %\*'
        $script:BootstrapText |
            Should-MatchString '\$shimItem\.Attributes -band \[IO\.FileAttributes\]::ReparsePoint'
    }

    It 'contains no ambient execution, installer, self-update, or Authenticode fallback' {
        $script:BootstrapText | Should-NotMatchString '&\s+apm\b'
        $script:BootstrapText | Should-NotMatchString 'install\.ps1'
        $script:BootstrapText | Should-NotMatchString 'self-update'
        $script:BootstrapText | Should-NotMatchString 'Authenticode'
    }

    It 'supports util-linux and BSD pseudo-terminal audit forms' {
        $script:ValidationText | Should-MatchString "-q -e -c 'exit 0' /dev/null"
        $script:ValidationText | Should-MatchString '-q /dev/null sh -c'
        $script:ValidationText | Should-MatchString 'APM_AUDIT_STATUS'
    }
}

Describe 'Bootstrap-Baseline verified Windows fixtures' -Skip:(-not $script:IsWindowsPlatform) {
    BeforeEach {
        $script:OldProcessPath = $env:PATH
        $script:OldUserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
        $script:TestRepository = New-TestRepository
        $script:Fixture = New-ZipFixture -Repository $script:TestRepository
        $env:APM_TEST_FIXTURE_ARCHIVE = $script:Fixture.Archive
        $script:InstallRoot = Join-Path $TestDrive (
            'install-' + [char]0x00E9 + '-' + [Guid]::NewGuid().ToString('N')
        )
        $script:CallLog = Join-Path $TestDrive ('calls-' + [Guid]::NewGuid().ToString('N') + '.log')
        $env:APM_INSTALL_DIR = Join-Path $script:InstallRoot 'bin'
        $env:APM_RELEASE_BASE_URL = 'https://mirror.example.invalid/apm'
        $env:APM_TEST_CALL_LOG = $script:CallLog
        $env:PROCESSOR_ARCHITECTURE = 'AMD64'
        Remove-Item Env:PROCESSOR_ARCHITEW6432 -ErrorAction SilentlyContinue
        Remove-Item Env:APM_NO_DIRECT_FALLBACK -ErrorAction SilentlyContinue
        Remove-Item Env:BASELINE_PACKAGE_REF -ErrorAction SilentlyContinue
        Remove-Item Env:APM_TEST_REQUESTED_URI -ErrorAction SilentlyContinue
        Remove-Item Env:APM_TEST_TLS_DURING_DOWNLOAD -ErrorAction SilentlyContinue
        Mock Invoke-WebRequest {
            $env:APM_TEST_REQUESTED_URI = $Uri
            $env:APM_TEST_TLS_DURING_DOWNLOAD = [string][bool](
                [Net.ServicePointManager]::SecurityProtocol -band [Net.SecurityProtocolType]::Tls12
            )
            Copy-Item -LiteralPath $env:APM_TEST_FIXTURE_ARCHIVE -Destination $OutFile
        }
    }

    AfterEach {
        $env:PATH = $script:OldProcessPath
        [Environment]::SetEnvironmentVariable('Path', $script:OldUserPath, 'User')
        foreach ($name in @(
                'APM_INSTALL_DIR',
                'APM_RELEASE_BASE_URL',
                'APM_TEST_CALL_LOG',
                'APM_TEST_FIXTURE_ARCHIVE',
                'APM_TEST_REQUESTED_URI',
                'APM_TEST_TLS_DURING_DOWNLOAD',
                'APM_NO_DIRECT_FALLBACK',
                'BASELINE_PACKAGE_REF'
            )) {
            Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
        }
        Remove-Item Function:global:apm -ErrorAction SilentlyContinue
    }

    It 'persists the complete verified bundle and native Windows layout in a Unicode path' {
        $beforeTls = [Net.ServicePointManager]::SecurityProtocol

        & $script:TestRepository.Script -CliOnly -Confirm:$false

        $release = Join-Path $script:InstallRoot 'releases\v0.29.0'
        $env:APM_INSTALL_DIR | Should-Be (Join-Path $script:InstallRoot 'bin')
        Test-Path -LiteralPath (Join-Path $env:APM_INSTALL_DIR 'apm.cmd') | Should-BeTrue
        Test-Path -LiteralPath (Join-Path $release '_internal\catalog.json') | Should-BeTrue
        Get-Content -LiteralPath (Join-Path $release '.apm-installed') -Raw |
            Should-MatchString 'v0.29.0'
        $current = Get-Item -LiteralPath (Join-Path $script:InstallRoot 'current') -Force
        [bool]($current.Attributes -band [IO.FileAttributes]::ReparsePoint) | Should-BeTrue
        $shim = Join-Path $script:InstallRoot 'bin\apm.cmd'
        [IO.File]::ReadAllText($shim) | Should-MatchString '"%~dp0\.\.\\current\\apm\.exe" %\*'
        @([IO.File]::ReadAllBytes($shim) | Where-Object { $_ -gt 127 }).Count | Should-Be 0
        $env:APM_TEST_REQUESTED_URI |
            Should-Be 'https://mirror.example.invalid/apm/v0.29.0/apm-windows-x86_64.zip'
        $env:APM_TEST_TLS_DURING_DOWNLOAD | Should-Be 'True'
        [Net.ServicePointManager]::SecurityProtocol | Should-Be $beforeTls
        Should-Invoke Invoke-WebRequest -Times 1 -Exactly -Scope It -ParameterFilter {
            $UseBasicParsing -and
                $Uri -eq 'https://mirror.example.invalid/apm/v0.29.0/apm-windows-x86_64.zip'
        }
    }

    It 'uses only staged and promoted absolute executables, never an ambient function' {
        $script:AmbientExecuted = $false
        function global:apm { $script:AmbientExecuted = $true }

        & $script:TestRepository.Script -CliOnly -Confirm:$false 3>&1 | Out-Null

        $script:AmbientExecuted | Should-BeFalse
        Get-Content -LiteralPath $script:CallLog -Raw | Should-MatchString 'apm-bootstrap-'
        Get-Content -LiteralPath $script:CallLog -Raw | Should-MatchString '\\current\\apm\.exe'
    }

    It 'uses launcher and transitive MCP trust with explicit targets for native deployment' {
        & $script:TestRepository.Script -Scope Repo -Confirm:$false
        $calls = Get-Content -LiteralPath $script:CallLog -Raw
        $calls | Should-MatchString 'install --target codex,copilot --trust-bin --trust-transitive-mcp https://github.com/thetechgy/agent-engineering-baseline\.git#main'
        $calls | Should-MatchString 'update --yes --target codex,copilot'
        $calls | Should-MatchString 'compile --target codex,copilot'

        Remove-Item -LiteralPath $script:CallLog -ErrorAction SilentlyContinue
        & $script:TestRepository.Script -Scope Global -Confirm:$false
        $calls = Get-Content -LiteralPath $script:CallLog -Raw
        $calls | Should-MatchString 'install --global --target codex,copilot --trust-bin --trust-transitive-mcp https://github.com/thetechgy/agent-engineering-baseline\.git#main'
        $calls | Should-MatchString 'update --global --yes --target codex,copilot'
        $calls | Should-MatchString 'compile --global'
    }

    It 'honors a literal package reference override' {
        $env:BASELINE_PACKAGE_REF = 'https://example.invalid/reviewed.git#release'
        & $script:TestRepository.Script -Scope Repo -Confirm:$false
        Get-Content -LiteralPath $script:CallLog -Raw |
            Should-MatchString 'https://example\.invalid/reviewed\.git#release'
    }

    It 'fails closed when direct fallback is disabled without a mirror' {
        Remove-Item Env:APM_RELEASE_BASE_URL
        $env:APM_NO_DIRECT_FALLBACK = 'yes'
        { & $script:TestRepository.Script -CliOnly -Confirm:$false } |
            Should-Throw -ExceptionMessage '*no APM_RELEASE_BASE_URL*'
        Should-NotInvoke Invoke-WebRequest -Scope It
    }

    It 'does not retry a failed authoritative mirror against the public release' {
        Mock Invoke-WebRequest { throw 'mirror unavailable' }
        { & $script:TestRepository.Script -CliOnly -Confirm:$false } |
            Should-Throw -ExceptionMessage '*mirror unavailable*'
        Should-Invoke Invoke-WebRequest -Times 1 -Exactly -Scope It -ParameterFilter {
            $Uri -like 'https://mirror.example.invalid/*'
        }
    }

    It 'rejects corrupt archives and executable digest mismatches before execution' {
        $script:Fixture = New-ZipFixture -Repository $script:TestRepository -CorruptArchive
        $env:APM_TEST_FIXTURE_ARCHIVE = $script:Fixture.Archive
        { & $script:TestRepository.Script -CliOnly -Confirm:$false } | Should-Throw
        Test-Path -LiteralPath $script:CallLog | Should-BeFalse

        $script:TestRepository = New-TestRepository
        $script:Fixture = New-ZipFixture -Repository $script:TestRepository
        $env:APM_TEST_FIXTURE_ARCHIVE = $script:Fixture.Archive
        Set-TestChecksum -Repository $script:TestRepository -Name 'apm-windows-x86_64/apm.exe' -Digest ('0' * 64)
        { & $script:TestRepository.Script -CliOnly -Confirm:$false } |
            Should-Throw -ExceptionMessage '*reviewed SHA256*'
        Test-Path -LiteralPath $script:CallLog | Should-BeFalse
    }

    It 'rejects missing internal, wrong-root, traversal, duplicate, and linked ZIP entries' {
        $cases = @(
            @{ OmitInternal = $true }
            @{ WrongRoot = $true }
            @{ Traversal = $true }
            @{ DuplicateExecutable = $true }
            @{ LinkedEntry = $true }
        )
        foreach ($case in $cases) {
            $script:TestRepository = New-TestRepository
            $script:Fixture = New-ZipFixture -Repository $script:TestRepository @case
            $env:APM_TEST_FIXTURE_ARCHIVE = $script:Fixture.Archive
            { & $script:TestRepository.Script -CliOnly -Confirm:$false } | Should-Throw
        }
    }

    It 'preserves full prerelease versions' {
        $script:TestRepository = New-TestRepository -Pin '0.30.0rc2'
        $script:Fixture = New-ZipFixture -Repository $script:TestRepository -Version '0.30.0rc2'
        $env:APM_TEST_FIXTURE_ARCHIVE = $script:Fixture.Archive

        & $script:TestRepository.Script -CliOnly -Confirm:$false

        Get-Content -LiteralPath (
            Join-Path $script:InstallRoot 'releases\v0.30.0rc2\.apm-installed'
        ) -Raw | Should-MatchString 'v0.30.0rc2'
    }

    It 'rejects an unsafe installation-root reparse point' {
        $outside = Join-Path $TestDrive ('outside-' + [Guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $outside | Out-Null
        New-Item -ItemType Junction -Path $script:InstallRoot -Target $outside | Out-Null

        { & $script:TestRepository.Script -CliOnly -Confirm:$false } |
            Should-Throw -ExceptionMessage '*reparse point*'
    }

    It 'rejects a nested reparse point before descending into it' {
        $release = Join-Path $script:InstallRoot 'releases\v0.29.0'
        $target = Join-Path $TestDrive ('outside-' + [Guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $release, $target -Force | Out-Null
        [IO.File]::WriteAllText(
            (Join-Path $release '.apm-installed'),
            "v0.29.0$([Environment]::NewLine)",
            [Text.Encoding]::ASCII
        )
        New-Item -ItemType Junction -Path (Join-Path $release '_internal') -Target $target |
            Out-Null

        { & $script:TestRepository.Script -CliOnly -Confirm:$false } |
            Should-Throw -ExceptionMessage '*contains a reparse point*'
    }

    It 'rolls back the prior release and junction when shim promotion fails' {
        & $script:TestRepository.Script -CliOnly -Confirm:$false
        $release = Join-Path $script:InstallRoot 'releases\v0.29.0'
        [IO.File]::WriteAllText((Join-Path $release '_internal\old-state'), 'old')
        $shim = Join-Path $script:InstallRoot 'bin\apm.cmd'
        (Get-Item -LiteralPath $shim).IsReadOnly = $true
        try {
            { & $script:TestRepository.Script -CliOnly -Confirm:$false } | Should-Throw
        }
        finally {
            (Get-Item -LiteralPath $shim).IsReadOnly = $false
        }

        Test-Path -LiteralPath (Join-Path $release '_internal\old-state') | Should-BeTrue
        $current = Get-Item -LiteralPath (Join-Path $script:InstallRoot 'current') -Force
        [bool]($current.Attributes -band [IO.FileAttributes]::ReparsePoint) | Should-BeTrue
        [IO.File]::ReadAllText($shim) | Should-MatchString '"%~dp0\.\.\\current\\apm\.exe" %\*'
    }
}
