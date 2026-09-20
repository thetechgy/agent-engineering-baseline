<#
.SYNOPSIS
Offline Pester tests for the verified Windows APM bundle bootstrap.

.DESCRIPTION
Metadata and source-contract tests run on every platform. Windows-only cases
create genuine ZIP archives and a small compiled fixture executable, then
exercise Windows PowerShell 5.1 download, verification, promotion, rollback,
PATH, shim, and native deployment behavior.
Unix-only cases run the Bash suite with candidate repository pins to ensure
synthetic fixtures stay independent of production release updates.
#>

BeforeDiscovery {
    $script:IsWindowsPlatform = $env:OS -ceq 'Windows_NT'
}

BeforeAll {
    $script:RepositoryRoot = Split-Path -Parent $PSScriptRoot
    $script:BootstrapSource = Join-Path $script:RepositoryRoot 'scripts/Bootstrap-Baseline.ps1'
    $script:ValidationSource = Join-Path $script:RepositoryRoot 'scripts/Invoke-Validation.ps1'
    $script:IsWindowsPlatform = $env:OS -ceq 'Windows_NT'

    $script:OriginalCopyItem = Get-Command Copy-Item -CommandType Cmdlet
    $script:OriginalMoveItem = Get-Command Move-Item -CommandType Cmdlet
    $script:OriginalGetFileHash = Get-Command Get-FileHash

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
        string mutexName = Environment.GetEnvironmentVariable("APM_TEST_MUTEX_NAME");
        if (!String.IsNullOrEmpty(mutexName) && args.Length > 0 && args[0] == "install")
        {
            // Report whether the bootstrap still holds its installation mutex during the handoff.
            using (System.Threading.Mutex mutex = new System.Threading.Mutex(false, mutexName))
            {
                bool acquired = false;
                try { acquired = mutex.WaitOne(0); }
                catch (System.Threading.AbandonedMutexException) { acquired = true; }
                File.WriteAllText(log + ".mutex", acquired ? "free" : "held");
                if (acquired) { mutex.ReleaseMutex(); }
            }
        }
        if (args.Length == 1 && args[0] == "--version")
        {
            string fault = Environment.GetEnvironmentVariable("APM_TEST_PROMOTION_FAULT");
            string executable = Environment.GetCommandLineArgs()[0];
            string directory = Path.GetDirectoryName(executable);
            string generation = Path.GetFileName(directory);
            bool staged = generation.StartsWith(".stage-", StringComparison.Ordinal);
            if (!staged && fault == "staged-execution") { return 73; }
            if (!staged && fault == "staged-banner") { Console.WriteLine("No version"); return 0; }
            if (staged)
            {
                string root = Path.GetDirectoryName(Path.GetDirectoryName(directory));
                string shim = Path.Combine(Path.Combine(root, "bin"), "apm.cmd");
                if (File.Exists(shim) && File.ReadAllText(shim).Contains(generation.Substring(".stage-".Length)))
                {
                    File.WriteAllText(log + ".published", "unverified");
                }
                if (fault == "execution") { return 73; }
                if (fault == "version") { Console.WriteLine("APM version 9.9.9"); return 0; }
                if (fault == "banner") { Console.WriteLine("No version"); return 0; }
            }
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

Describe 'Bash fixture independence from candidate release pins' -Skip:$script:IsWindowsPlatform {
    It 'passes the offline suite with repository pin <Pin>' -ForEach @(
        @{ Pin = '0.29.1' }
        @{ Pin = '0.30.0' }
        @{ Pin = '0.30.0rc2' }
    ) {
        $root = Join-Path $TestDrive ('bash-' + $Pin)
        foreach ($relativePath in @('scripts/bootstrap.sh', 'tests/bootstrap.sh', '.apm-checksums')) {
            $destination = Join-Path $root $relativePath
            New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
            Copy-Item -LiteralPath (Join-Path $script:RepositoryRoot $relativePath) -Destination $destination
        }
        $pinPath = Join-Path $root '.apm-version'
        [IO.File]::WriteAllText($pinPath, $Pin + "`n", [Text.Encoding]::ASCII)

        $output = & bash (Join-Path $root 'tests/bootstrap.sh') 2>&1
        $exitCode = $LASTEXITCODE

        $exitCode | Should-Be 0 -Because ($output -join [Environment]::NewLine)
        ($output -join "`n") | Should-MatchString '(?m)^[1-9][0-9]* cases, 0 failures$'
        [IO.File]::ReadAllText($pinPath) | Should-Be ($Pin + "`n")
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

    It 'uses the required download, TLS, archive, mutex, atomic replacement, and ASCII primitives' {
        $script:BootstrapText | Should-MatchString 'Invoke-WebRequest -Uri \$Uri -OutFile \$OutFile -UseBasicParsing'
        $script:BootstrapText | Should-MatchString 'SecurityProtocol = \$previousProtocol'
        $script:BootstrapText | Should-MatchString 'Expand-Archive -LiteralPath'
        $script:BootstrapText | Should-MatchString 'Threading\.Mutex'
        $script:BootstrapText | Should-MatchString '\$mutex\.WaitOne\(0\)'
        $script:BootstrapText | Should-MatchString '\[IO\.File\]::Replace\(\$shimStagePath, \$shimPath, \[NullString\]::Value\)'
        $script:BootstrapText | Should-MatchString '\[IO\.Directory\]::Delete\(\$legacyCurrentPath, \$false\)'
        $script:BootstrapText | Should-MatchString '\[Text\.Encoding\]::ASCII'
        $script:BootstrapText | Should-MatchString 'New-Object System\.Collections\.Stack'
        $script:BootstrapText | Should-NotMatchString 'Get-ChildItem[^\r\n]+-Recurse'
        $script:BootstrapText | Should-MatchString '"%~dp0\.\.\\releases\\\$generation\\apm\.exe`" %\*'
        $script:BootstrapText |
            Should-MatchString '\$shimItem\.Attributes -band \[IO\.FileAttributes\]::ReparsePoint'
        $script:BootstrapText | Should-NotMatchString 'New-Item -ItemType Junction'
        $script:BootstrapText | Should-NotMatchString 'Move-Item -LiteralPath \$releasePath'
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
    BeforeAll {
        function Get-ActiveRelease {
            [CmdletBinding()]
            param([Parameter(Mandatory)][string]$InstallRoot)

            $shim = [IO.File]::ReadAllText((Join-Path $InstallRoot 'bin\apm.cmd'))
            if ($shim -notmatch '"%~dp0\.\.\\releases\\([^"\\]+)\\apm\.exe" %\*') {
                throw "The shim does not reference a release generation: $shim"
            }
            Join-Path $InstallRoot "releases\$($Matches[1])"
        }

        function Get-ReleaseEntry {
            [CmdletBinding()]
            param([Parameter(Mandatory)][string]$InstallRoot)

            # The unary comma returns the array itself so .Count is defined for zero
            # or one entry under Windows PowerShell 5.1.
            $releases = Join-Path $InstallRoot 'releases'
            if (-not (Test-Path -LiteralPath $releases)) { return ,@() }
            ,@(Get-ChildItem -LiteralPath $releases -Force)
        }
    }

    BeforeEach {
        Remove-Item Env:APM_TEST_PROMOTION_FAULT -ErrorAction SilentlyContinue
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
                'APM_TEST_PROMOTION_FAULT',
                'APM_TEST_MUTEX_NAME',
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

    It 'persists the complete verified bundle as a generation in a Unicode path' {
        $beforeTls = [Net.ServicePointManager]::SecurityProtocol

        $output = & $script:TestRepository.Script -CliOnly -Confirm:$false 6>&1

        $release = Get-ActiveRelease -InstallRoot $script:InstallRoot
        Split-Path -Leaf $release | Should-MatchString '^v0\.29\.0-'
        $env:APM_INSTALL_DIR | Should-Be (Join-Path $script:InstallRoot 'bin')
        Test-Path -LiteralPath (Join-Path $release '_internal\catalog.json') | Should-BeTrue
        Get-Content -LiteralPath (Join-Path $release '.apm-installed') -Raw |
            Should-MatchString 'v0.29.0'
        Test-Path -LiteralPath (Join-Path $script:InstallRoot 'current') | Should-BeFalse
        (Get-ReleaseEntry -InstallRoot $script:InstallRoot).Count | Should-Be 1
        $shim = Join-Path $script:InstallRoot 'bin\apm.cmd'
        @([IO.File]::ReadAllBytes($shim) | Where-Object { $_ -gt 127 }).Count | Should-Be 0
        @(Get-ChildItem -LiteralPath (Join-Path $script:InstallRoot 'bin') -Force).Count | Should-Be 1
        & $shim --version | Should-MatchString '0\.29\.0'
        $LASTEXITCODE | Should-Be 0
        "$output" | Should-MatchString ([regex]::Escape("Done; reviewed CLI: $shim -> $release\apm.exe"))
        $binPath = Join-Path $script:InstallRoot 'bin'
        @($env:PATH.Split(';')) -contains $binPath | Should-BeTrue
        @([Environment]::GetEnvironmentVariable('Path', 'User').Split(';')) -contains $binPath | Should-BeTrue
        $env:APM_TEST_REQUESTED_URI |
            Should-Be 'https://mirror.example.invalid/apm/v0.29.0/apm-windows-x86_64.zip'
        $env:APM_TEST_TLS_DURING_DOWNLOAD | Should-Be 'True'
        [Net.ServicePointManager]::SecurityProtocol | Should-Be $beforeTls
        Should-Invoke Invoke-WebRequest -Times 1 -Exactly -Scope It -ParameterFilter {
            $UseBasicParsing -and
                $Uri -eq 'https://mirror.example.invalid/apm/v0.29.0/apm-windows-x86_64.zip'
        }
    }

    It 'uses only extracted and staged absolute executables, never an ambient function' {
        $script:AmbientExecuted = $false
        function global:apm { $script:AmbientExecuted = $true }

        & $script:TestRepository.Script -CliOnly -Confirm:$false 3>&1 | Out-Null

        $script:AmbientExecuted | Should-BeFalse
        $calls = @(Get-Content -LiteralPath $script:CallLog -Encoding UTF8)
        $calls.Count | Should-Be 2
        $calls[0] | Should-MatchString 'apm-bootstrap-'
        $calls[1] | Should-MatchString '\\releases\\\.stage-v0\.29\.0-[^\\]+\\apm\.exe'
    }

    It 'selects only the intended native workflow for -Scope <ScopeValue>' -ForEach @(
        @{ ScopeValue = 'Repo'; GlobalScope = $false }
        @{ ScopeValue = 'repo'; GlobalScope = $false }
        @{ ScopeValue = 'REPO'; GlobalScope = $false }
        @{ ScopeValue = 'Global'; GlobalScope = $true }
        @{ ScopeValue = 'global'; GlobalScope = $true }
        @{ ScopeValue = 'GLOBAL'; GlobalScope = $true }
    ) {
        & $script:TestRepository.Script -Scope $ScopeValue -Confirm:$false
        $calls = @(Get-Content -LiteralPath $script:CallLog -Encoding UTF8 | Where-Object { $_ -notmatch '--version' })
        $calls.Count | Should-Be 3
        $release = Get-ActiveRelease -InstallRoot $script:InstallRoot
        foreach ($call in $calls) { $call | Should-MatchString ([regex]::Escape("$release\apm.exe")) }
        $globalOption = if ($GlobalScope) { ' --global' } else { '' }
        $calls[0] | Should-MatchString (
            ' install' + $globalOption + ' --target codex,copilot --trust-bin --trust-transitive-mcp ' +
            'https://github.com/thetechgy/agent-engineering-baseline\.git#main$'
        )
        $calls[1] | Should-MatchString (' update' + $globalOption + ' --yes --target codex,copilot$')
        $compileOptions = if ($GlobalScope) { ' --global' } else { ' --target codex,copilot' }
        $calls[2] | Should-MatchString (' compile' + $compileOptions + '$')
    }

    It 'honors a literal package reference override' {
        $env:BASELINE_PACKAGE_REF = 'https://example.invalid/reviewed.git#release'
        & $script:TestRepository.Script -Scope Repo -Confirm:$false
        Get-Content -LiteralPath $script:CallLog -Encoding UTF8 -Raw |
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
        (Get-ReleaseEntry -InstallRoot $script:InstallRoot).Count | Should-Be 0
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
        (Get-ReleaseEntry -InstallRoot $script:InstallRoot).Count | Should-Be 0
    }

    It 'preserves full prerelease versions' {
        $script:TestRepository = New-TestRepository -Pin '0.30.0rc2'
        $script:Fixture = New-ZipFixture -Repository $script:TestRepository -Version '0.30.0rc2'
        $env:APM_TEST_FIXTURE_ARCHIVE = $script:Fixture.Archive

        & $script:TestRepository.Script -CliOnly -Confirm:$false

        $release = Get-ActiveRelease -InstallRoot $script:InstallRoot
        Split-Path -Leaf $release | Should-MatchString '^v0\.30\.0rc2-'
        Get-Content -LiteralPath (Join-Path $release '.apm-installed') -Raw | Should-MatchString 'v0.30.0rc2'
    }

    It 'rejects an unsafe installation-root reparse point' {
        $outside = Join-Path $TestDrive ('outside-' + [Guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $outside | Out-Null
        New-Item -ItemType Junction -Path $script:InstallRoot -Target $outside | Out-Null

        { & $script:TestRepository.Script -CliOnly -Confirm:$false } |
            Should-Throw -ExceptionMessage '*reparse point*'
    }

    It 'refuses to overwrite an unrelated apm.cmd' {
        $shim = Join-Path $env:APM_INSTALL_DIR 'apm.cmd'
        New-Item -ItemType Directory -Path $env:APM_INSTALL_DIR -Force | Out-Null
        [IO.File]::WriteAllText($shim, "@echo off`r`necho unrelated`r`n")

        { & $script:TestRepository.Script -CliOnly -Confirm:$false } |
            Should-Throw -ExceptionMessage '*unrelated APM shim*'

        [IO.File]::ReadAllText($shim) | Should-Be "@echo off`r`necho unrelated`r`n"
        (Get-ReleaseEntry -InstallRoot $script:InstallRoot).Count | Should-Be 0
    }

    It 'refuses to overwrite a managed-looking shim whose generation escapes releases' {
        $shim = Join-Path $env:APM_INSTALL_DIR 'apm.cmd'
        New-Item -ItemType Directory -Path $env:APM_INSTALL_DIR -Force | Out-Null
        $content = "@echo off`r`n`"%~dp0..\releases\..\apm.exe`" %*`r`n"
        [IO.File]::WriteAllText($shim, $content, [Text.Encoding]::ASCII)

        { & $script:TestRepository.Script -CliOnly -Confirm:$false } |
            Should-Throw -ExceptionMessage '*unrelated APM shim*'

        [IO.File]::ReadAllText($shim) | Should-Be $content
        (Get-ReleaseEntry -InstallRoot $script:InstallRoot).Count | Should-Be 0
    }

    It 'leaves entries it did not create under releases and still removes the superseded generation' {
        & $script:TestRepository.Script -CliOnly -Confirm:$false
        $first = Get-ActiveRelease -InstallRoot $script:InstallRoot
        $releases = Join-Path $script:InstallRoot 'releases'
        $notes = Join-Path $releases 'notes'
        $unmarked = Join-Path $releases 'v0.28.0-unmarked'
        New-Item -ItemType Directory -Path $notes, $unmarked -Force | Out-Null
        [IO.File]::WriteAllText((Join-Path $notes 'todo'), 'user notes')
        [IO.File]::WriteAllText((Join-Path $releases 'README.txt'), 'user file')
        $warnings = New-Object Collections.Generic.List[string]
        Mock Write-Warning { $warnings.Add($Message) }

        & $script:TestRepository.Script -CliOnly -Confirm:$false

        ($warnings -join ' ') | Should-MatchString 'Leaving an unrecognized entry in the APM releases directory'
        [IO.File]::ReadAllText((Join-Path $notes 'todo')) | Should-Be 'user notes'
        [IO.File]::ReadAllText((Join-Path $releases 'README.txt')) | Should-Be 'user file'
        Test-Path -LiteralPath $unmarked | Should-BeTrue
        Test-Path -LiteralPath $first | Should-BeFalse
        Get-ActiveRelease -InstallRoot $script:InstallRoot | Should-NotBe $first
        & (Join-Path $script:InstallRoot 'bin\apm.cmd') --version | Should-MatchString '0\.29\.0'
        $LASTEXITCODE | Should-Be 0
    }

    It 'replaces the previous generation and removes it after activation' {
        & $script:TestRepository.Script -CliOnly -Confirm:$false
        $first = Get-ActiveRelease -InstallRoot $script:InstallRoot
        [IO.File]::WriteAllText((Join-Path $first '_internal\old-state'), 'old')

        & $script:TestRepository.Script -CliOnly -Confirm:$false

        $second = Get-ActiveRelease -InstallRoot $script:InstallRoot
        $second | Should-NotBe $first
        Test-Path -LiteralPath $first | Should-BeFalse
        (Get-ReleaseEntry -InstallRoot $script:InstallRoot).Count | Should-Be 1
        & (Join-Path $script:InstallRoot 'bin\apm.cmd') --version | Should-MatchString '0\.29\.0'
        $LASTEXITCODE | Should-Be 0
    }

    It 'replaces the legacy current junction layout' {
        & $script:TestRepository.Script -CliOnly -Confirm:$false
        $release = Get-ActiveRelease -InstallRoot $script:InstallRoot
        $legacyRelease = Join-Path $script:InstallRoot 'releases\v0.28.0'
        $current = Join-Path $script:InstallRoot 'current'
        $shim = Join-Path $script:InstallRoot 'bin\apm.cmd'
        Move-Item -LiteralPath $release -Destination $legacyRelease
        New-Item -ItemType Junction -Path $current -Target $legacyRelease | Out-Null
        [IO.File]::WriteAllText($shim, "@echo off`r`n`"%~dp0..\current\apm.exe`" %*`r`n", [Text.Encoding]::ASCII)
        & $shim --version | Should-MatchString '0\.29\.0'

        & $script:TestRepository.Script -CliOnly -Confirm:$false

        Test-Path -LiteralPath $current | Should-BeFalse
        Test-Path -LiteralPath $legacyRelease | Should-BeFalse
        (Get-ReleaseEntry -InstallRoot $script:InstallRoot).Count | Should-Be 1
        & $shim --version | Should-MatchString '0\.29\.0'
        $LASTEXITCODE | Should-Be 0
    }

    It 'refuses a legacy current shim whose junction points outside releases' {
        $outside = Join-Path $TestDrive ('outside-' + [Guid]::NewGuid().ToString('N'))
        $current = Join-Path $script:InstallRoot 'current'
        $shim = Join-Path $script:InstallRoot 'bin\apm.cmd'
        New-Item -ItemType Directory -Path $outside, (Split-Path -Parent $shim) -Force | Out-Null
        [IO.File]::WriteAllText((Join-Path $outside 'keep'), 'outside content')
        New-Item -ItemType Junction -Path $current -Target $outside | Out-Null
        $content = "@echo off`r`n`"%~dp0..\current\apm.exe`" %*`r`n"
        [IO.File]::WriteAllText($shim, $content, [Text.Encoding]::ASCII)

        { & $script:TestRepository.Script -CliOnly -Confirm:$false } |
            Should-Throw -ExceptionMessage '*legacy current link is not a junction into*'

        [IO.File]::ReadAllText($shim) | Should-Be $content
        Test-Path -LiteralPath $current | Should-BeTrue
        Test-Path -LiteralPath (Join-Path $outside 'keep') | Should-BeTrue
        (Get-ReleaseEntry -InstallRoot $script:InstallRoot).Count | Should-Be 0
    }

    It 'refuses a legacy current shim whose dangling junction pointed outside releases' {
        $outside = Join-Path $TestDrive ('outside-' + [Guid]::NewGuid().ToString('N'))
        $current = Join-Path $script:InstallRoot 'current'
        $shim = Join-Path $script:InstallRoot 'bin\apm.cmd'
        New-Item -ItemType Directory -Path $outside, (Split-Path -Parent $shim) -Force | Out-Null
        New-Item -ItemType Junction -Path $current -Target $outside | Out-Null
        Remove-Item -LiteralPath $outside -Force
        $content = "@echo off`r`n`"%~dp0..\current\apm.exe`" %*`r`n"
        [IO.File]::WriteAllText($shim, $content, [Text.Encoding]::ASCII)

        { & $script:TestRepository.Script -CliOnly -Confirm:$false } |
            Should-Throw -ExceptionMessage '*legacy current link is not a junction into*'

        [IO.File]::ReadAllText($shim) | Should-Be $content
        [bool]((Get-Item -LiteralPath $current -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) | Should-BeTrue
        (Get-ReleaseEntry -InstallRoot $script:InstallRoot).Count | Should-Be 0
    }

    It 'refuses a legacy current shim whose junction traverses a nested junction' {
        $outside = Join-Path $TestDrive ('outside-' + [Guid]::NewGuid().ToString('N'))
        $releases = Join-Path $script:InstallRoot 'releases'
        $nested = Join-Path $releases 'link'
        $current = Join-Path $script:InstallRoot 'current'
        $shim = Join-Path $script:InstallRoot 'bin\apm.cmd'
        New-Item -ItemType Directory -Path (Join-Path $outside 'sub'), $releases, (Split-Path -Parent $shim) -Force | Out-Null
        [IO.File]::WriteAllText((Join-Path $outside 'sub\apm.exe'), 'outside content')
        New-Item -ItemType Junction -Path $nested -Target $outside | Out-Null
        New-Item -ItemType Junction -Path $current -Target (Join-Path $nested 'sub') | Out-Null
        # The stored target must be the textual path under releases, or the
        # fixture would exercise the plain outside-releases rejection instead.
        [string](@((Get-Item -LiteralPath $current -Force).Target) | Select-Object -First 1) |
            Should-MatchString ([regex]::Escape($nested) + '\\sub$')
        $content = "@echo off`r`n`"%~dp0..\current\apm.exe`" %*`r`n"
        [IO.File]::WriteAllText($shim, $content, [Text.Encoding]::ASCII)

        { & $script:TestRepository.Script -CliOnly -Confirm:$false } |
            Should-Throw -ExceptionMessage '*legacy current link is not a junction into*'

        [IO.File]::ReadAllText($shim) | Should-Be $content
        Test-Path -LiteralPath $current | Should-BeTrue
        Test-Path -LiteralPath $nested | Should-BeTrue
        [IO.File]::ReadAllText((Join-Path $outside 'sub\apm.exe')) | Should-Be 'outside content'
        @(Get-ReleaseEntry -InstallRoot $script:InstallRoot | Where-Object { $_.Name -ne 'link' }).Count | Should-Be 0
    }

    It 'leaves an unmarked stage directory in place and removes a marked abandoned stage' {
        & $script:TestRepository.Script -CliOnly -Confirm:$false
        $releases = Join-Path $script:InstallRoot 'releases'
        $unmarked = Join-Path $releases '.stage-notes'
        $marked = Join-Path $releases '.stage-v0.28.0-20260101T000000Z-00000001'
        New-Item -ItemType Directory -Path $unmarked, $marked -Force | Out-Null
        [IO.File]::WriteAllText((Join-Path $unmarked 'keep'), 'user notes')
        [IO.File]::WriteAllText((Join-Path $marked '.apm-installed'), "v0.28.0`r`n", [Text.Encoding]::ASCII)
        $warnings = New-Object Collections.Generic.List[string]
        Mock Write-Warning { $warnings.Add($Message) }

        & $script:TestRepository.Script -CliOnly -Confirm:$false

        ($warnings -join ' ') | Should-MatchString ([regex]::Escape($unmarked))
        [IO.File]::ReadAllText((Join-Path $unmarked 'keep')) | Should-Be 'user notes'
        Test-Path -LiteralPath $marked | Should-BeFalse
        & (Join-Path $script:InstallRoot 'bin\apm.cmd') --version | Should-MatchString '0\.29\.0'
        $LASTEXITCODE | Should-Be 0
    }

    It 'preserves a stage path another process created between preflight and creation' {
        $OriginalNewItem = Get-Command New-Item -CommandType Cmdlet
        $collision = [pscustomobject]@{ Path = $null }
        Mock New-Item {
            if ($ItemType -eq 'Directory' -and $Path -like '*\releases\.stage-*') {
                & $OriginalNewItem @PesterBoundParameters | Out-Null
                [IO.File]::WriteAllText((Join-Path $Path 'keep'), 'foreign')
                $collision.Path = $Path
                throw 'injected stage collision'
            }
            & $OriginalNewItem @PesterBoundParameters
        }

        { & $script:TestRepository.Script -CliOnly -Confirm:$false } |
            Should-Throw -ExceptionMessage '*injected stage collision*'

        $collision.Path | Should-NotBeNull
        [IO.File]::ReadAllText((Join-Path $collision.Path 'keep')) | Should-Be 'foreign'
        Test-Path -LiteralPath (Join-Path $env:APM_INSTALL_DIR 'apm.cmd') | Should-BeFalse
    }

    It 'does not delete through a reparse point that replaced an abandoned stage' {
        $outside = Join-Path $TestDrive ('outside-' + [Guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $outside -Force | Out-Null
        [IO.File]::WriteAllText((Join-Path $outside 'keep'), 'outside content')
        $swapped = [pscustomobject]@{ Path = $null }
        Mock Copy-Item {
            if ($Destination -like '*\releases\.stage-*' -and -not $swapped.Path) {
                Remove-Item -LiteralPath $Destination -Recurse -Force
                New-Item -ItemType Junction -Path $Destination -Target $outside | Out-Null
                $swapped.Path = $Destination
                throw 'injected staging failure'
            }
            & $OriginalCopyItem @PesterBoundParameters
        }
        $warnings = New-Object Collections.Generic.List[string]
        Mock Write-Warning { $warnings.Add($Message) }

        { & $script:TestRepository.Script -CliOnly -Confirm:$false } |
            Should-Throw -ExceptionMessage '*injected staging failure*'

        $swapped.Path | Should-NotBeNull
        ($warnings -join ' ') | Should-MatchString 'Leaving an abandoned APM stage'
        [IO.File]::ReadAllText((Join-Path $outside 'keep')) | Should-Be 'outside content'
        Test-Path -LiteralPath (Join-Path $env:APM_INSTALL_DIR 'apm.cmd') | Should-BeFalse
    }

    It 'leaves a plain current directory in place with a warning' {
        & $script:TestRepository.Script -CliOnly -Confirm:$false
        $current = Join-Path $script:InstallRoot 'current'
        New-Item -ItemType Directory -Path $current -Force | Out-Null
        [IO.File]::WriteAllText((Join-Path $current 'keep'), 'user content')
        $warnings = New-Object Collections.Generic.List[string]
        Mock Write-Warning { $warnings.Add($Message) }

        & $script:TestRepository.Script -CliOnly -Confirm:$false

        ($warnings -join ' ') | Should-MatchString 'Leaving an unrecognized entry beside the APM releases directory'
        [IO.File]::ReadAllText((Join-Path $current 'keep')) | Should-Be 'user content'
        & (Join-Path $script:InstallRoot 'bin\apm.cmd') --version | Should-MatchString '0\.29\.0'
        $LASTEXITCODE | Should-Be 0
    }

    It 'skips a superseded entry containing a reparse point instead of deleting through it' {
        $target = Join-Path $TestDrive ('outside-' + [Guid]::NewGuid().ToString('N'))
        $stale = Join-Path $script:InstallRoot 'releases\v0.28.0-stale'
        New-Item -ItemType Directory -Path $stale, $target -Force | Out-Null
        [IO.File]::WriteAllText((Join-Path $stale '.apm-installed'), "v0.28.0`r`n", [Text.Encoding]::ASCII)
        [IO.File]::WriteAllText((Join-Path $target 'keep'), 'outside content')
        New-Item -ItemType Junction -Path (Join-Path $stale '_internal') -Target $target | Out-Null
        $warnings = New-Object Collections.Generic.List[string]
        Mock Write-Warning { $warnings.Add($Message) }

        & $script:TestRepository.Script -CliOnly -Confirm:$false

        ($warnings -join ' ') | Should-MatchString 'Unable to remove a superseded APM release'
        Test-Path -LiteralPath (Join-Path $target 'keep') | Should-BeTrue
        Test-Path -LiteralPath $stale | Should-BeTrue
        & (Join-Path $script:InstallRoot 'bin\apm.cmd') --version | Should-MatchString '0\.29\.0'
        $LASTEXITCODE | Should-Be 0
    }

    It 'keeps the verified installation when superseded cleanup fails' {
        & $script:TestRepository.Script -CliOnly -Confirm:$false
        $first = Get-ActiveRelease -InstallRoot $script:InstallRoot
        $OriginalRemoveItem = Get-Command Remove-Item -CommandType Cmdlet
        Mock Remove-Item {
            if ($LiteralPath -ieq $first -and $Recurse) { throw 'injected cleanup failure' }
            & $OriginalRemoveItem @PesterBoundParameters
        }
        $warnings = New-Object Collections.Generic.List[string]
        Mock Write-Warning { $warnings.Add($Message) }

        & $script:TestRepository.Script -CliOnly -Confirm:$false

        ($warnings -join ' ') | Should-MatchString 'injected cleanup failure'
        (Get-ActiveRelease -InstallRoot $script:InstallRoot) | Should-NotBe $first
        & (Join-Path $script:InstallRoot 'bin\apm.cmd') --version | Should-MatchString '0\.29\.0'
        $LASTEXITCODE | Should-Be 0
    }

    It 'keeps <Prior> installation untouched after <Fault> failure' -ForEach @(
        foreach ($prior in @('existing', 'fresh')) {
            foreach ($fault in @('copy', 'checksum', 'execution', 'version', 'banner', 'rename', 'shim')) {
                if ($prior -eq 'fresh' -and $fault -eq 'shim') { continue }
                @{ Prior = $prior; Fault = $fault }
            }
        }
    ) {
        $shim = Join-Path $env:APM_INSTALL_DIR 'apm.cmd'
        $priorRelease = $null
        if ($Prior -eq 'existing') {
            & $script:TestRepository.Script -CliOnly -Confirm:$false
            $priorRelease = Get-ActiveRelease -InstallRoot $script:InstallRoot
            [IO.File]::WriteAllText((Join-Path $priorRelease '_internal\old-state'), 'old')
        }
        $processPath = $env:PATH
        $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
        $faultState = [pscustomobject]@{ Name = $Fault; Hit = $false }
        Mock Copy-Item {
            if ($faultState.Name -eq 'copy' -and $Destination -like '*\.stage-*') {
                $faultState.Hit = $true
                throw 'injected staging failure'
            }
            & $OriginalCopyItem @PesterBoundParameters
        }
        Mock Move-Item {
            if ($faultState.Name -eq 'rename' -and $LiteralPath -like '*\.stage-*') {
                $faultState.Hit = $true
                throw 'injected rename failure'
            }
            & $OriginalMoveItem @PesterBoundParameters
        }
        Mock Get-FileHash {
            if ($faultState.Name -eq 'checksum' -and $LiteralPath -like '*\releases\.stage-*\apm.exe') {
                $faultState.Hit = $true
                return [pscustomobject]@{ Hash = ('0' * 64) }
            }
            & $OriginalGetFileHash @PesterBoundParameters
        }
        if ($Fault -eq 'shim') { (Get-Item -LiteralPath $shim).IsReadOnly = $true }
        $env:APM_TEST_PROMOTION_FAULT = $Fault
        $expectedError = switch ($Fault) {
            'copy' { '*injected staging failure*' }
            'rename' { '*injected rename failure*' }
            'checksum' { '*reviewed SHA256*' }
            'execution' { '*The APM executable failed its version postcondition*' }
            'version' { '*does not report pinned*' }
            'banner' { '*The APM executable did not report a full version*' }
            'shim' { '*' }
        }
        try {
            { & $script:TestRepository.Script -CliOnly -Confirm:$false } |
                Should-Throw -ExceptionMessage $expectedError
        }
        finally {
            if ($Fault -eq 'shim') { (Get-Item -LiteralPath $shim).IsReadOnly = $false }
        }
        if ($Fault -in @('execution', 'version', 'banner')) {
            Get-Content -LiteralPath $script:CallLog -Encoding UTF8 -Raw | Should-MatchString '\\releases\\\.stage-v0\.29\.0-'
        }
        elseif ($Fault -ne 'shim') { $faultState.Hit | Should-BeTrue }
        Test-Path -LiteralPath ($script:CallLog + '.published') | Should-BeFalse
        if ($Prior -eq 'existing') {
            (Get-ActiveRelease -InstallRoot $script:InstallRoot) | Should-Be $priorRelease
            Test-Path -LiteralPath (Join-Path $priorRelease '_internal\old-state') | Should-BeTrue
            (Get-ReleaseEntry -InstallRoot $script:InstallRoot).Count | Should-Be 1
            & $shim --version | Should-MatchString '0\.29\.0'
            $LASTEXITCODE | Should-Be 0
        }
        else {
            (Get-ReleaseEntry -InstallRoot $script:InstallRoot).Count | Should-Be 0
            Test-Path -LiteralPath $shim | Should-BeFalse
        }
        @(Get-ChildItem -LiteralPath $env:APM_INSTALL_DIR -Force | Where-Object { $_.Name -like '.apm-*' }).Count |
            Should-Be 0
        $env:PATH | Should-Be $processPath
        [Environment]::GetEnvironmentVariable('Path', 'User') | Should-Be $userPath
    }

    It 'uses phase-neutral diagnostics for <Fault> before staging' -ForEach @(
        @{ Fault = 'staged-execution'; Message = '*The APM executable failed its version postcondition*' }
        @{ Fault = 'staged-banner'; Message = '*The APM executable did not report a full version*' }
    ) {
        $env:APM_TEST_PROMOTION_FAULT = $Fault
        { & $script:TestRepository.Script -CliOnly -Confirm:$false } | Should-Throw -ExceptionMessage $Message
        (Get-ReleaseEntry -InstallRoot $script:InstallRoot).Count | Should-Be 0
        Test-Path -LiteralPath (Join-Path $script:InstallRoot 'bin\apm.cmd') | Should-BeFalse
    }

    It 'holds the installation mutex across the native handoff and releases it afterwards' {
        $installRoot = [IO.Path]::GetFullPath((Split-Path -Parent $env:APM_INSTALL_DIR))
        $env:APM_TEST_MUTEX_NAME = & {
            . $script:TestRepository.Script -WhatIf 6> $null
            Get-MutexName -InstallRoot $installRoot
        }

        & $script:TestRepository.Script -Scope Repo -Confirm:$false

        Get-Content -LiteralPath ($script:CallLog + '.mutex') -Raw | Should-Be 'held'
        $mutex = New-Object Threading.Mutex($false, $env:APM_TEST_MUTEX_NAME)
        try {
            $mutex.WaitOne(0) | Should-BeTrue
            $mutex.ReleaseMutex()
        }
        finally { $mutex.Dispose() }
    }

    It 'fails fast while another bootstrap holds the installation mutex' {
        & $script:TestRepository.Script -CliOnly -Confirm:$false
        $priorRelease = Get-ActiveRelease -InstallRoot $script:InstallRoot
        $installRoot = [IO.Path]::GetFullPath((Split-Path -Parent $env:APM_INSTALL_DIR))
        # Dot-source inside a child scope so only the mutex name escapes.
        $mutexName = & {
            . $script:TestRepository.Script -WhatIf 6> $null
            Get-MutexName -InstallRoot $installRoot
        }
        # Mutex ownership is per thread, so a second runspace thread must hold it;
        # the events hand off acquisition and release deterministically.
        $acquired = New-Object Threading.ManualResetEvent($false)
        $releaseRequested = New-Object Threading.ManualResetEvent($false)
        $holder = [PowerShell]::Create()
        $null = $holder.AddScript({
            param($Name, $Acquired, $ReleaseRequested)
            $mutex = New-Object Threading.Mutex($false, $Name)
            $null = $mutex.WaitOne()
            $null = $Acquired.Set()
            $null = $ReleaseRequested.WaitOne()
            $mutex.ReleaseMutex()
            $mutex.Dispose()
        }).AddArgument($mutexName).AddArgument($acquired).AddArgument($releaseRequested)
        $pending = $holder.BeginInvoke()
        try {
            $acquired.WaitOne(10000) | Should-BeTrue
            { & $script:TestRepository.Script -CliOnly -Confirm:$false } |
                Should-Throw -ExceptionMessage '*Another bootstrap is installing*'
        }
        finally {
            $null = $releaseRequested.Set()
            $null = $holder.EndInvoke($pending)
            $holder.Dispose()
            $acquired.Dispose()
            $releaseRequested.Dispose()
        }
        (Get-ActiveRelease -InstallRoot $script:InstallRoot) | Should-Be $priorRelease
        (Get-ReleaseEntry -InstallRoot $script:InstallRoot).Count | Should-Be 1
        & (Join-Path $script:InstallRoot 'bin\apm.cmd') --version | Should-MatchString '0\.29\.0'
        $LASTEXITCODE | Should-Be 0
    }
}
