---
name: powershell-pester-6
description: 'Author and migrate PowerShell tests for stable Pester 6 behavior, including discovery, assertions, mocking, isolation, configuration, CI, and Windows PowerShell 5.1 compatibility.'
---

# PowerShell Pester 6 Testing Guidelines

Use these instructions with the general PowerShell instructions. Target stable Pester 6.x behavior, using Pester
6.0.0 as the minimum verified baseline. Do not use prerelease or repository `main` behavior unless the project
explicitly opts into it.

## Determine the Project Version First

- Inspect module manifests, dependency files, validation scripts, CI workflows, and explicit `Import-Module` calls.
- Treat the project's declared or pinned Pester version as authoritative. Do not infer it from the newest locally
  installed module.
- If the project declares Pester 5, enter migration mode. Establish a clean baseline and update the suite coherently;
  do not introduce isolated Pester 6-only behavior into an otherwise Pester 5 run.
- If the project declares Pester 6, use the Pester 6 authoring rules below.
- Pester 6 supports Windows PowerShell 5.1 and PowerShell 7.4 or newer. Continue to honor the tested project's own
  PowerShell runtime floor; Pester 6 does not permit PowerShell 7-only syntax in a Windows PowerShell 5.1 project.

## File Naming and Structure

- Name test files `*.Tests.ps1`.
- Prefer a name that identifies the tested command, module, or behavior.
- Make every test file self-contained. Do not depend on another test file being discovered or run first.
- Put runtime setup in `BeforeAll` or `BeforeEach`, not at file scope.
- Use `BeforeDiscovery` only for values needed while Pester builds the test tree, such as external `-ForEach` data.
- Keep test names behavior-focused and free of secrets, credentials, tenant data, or sensitive identifiers because
  names can appear in console output and test-result artifacts.

```powershell
BeforeDiscovery {
    $testCases = @(
        @{ Name = 'one'; Expected = 1 }
        @{ Name = 'two'; Expected = 2 }
    )
}

BeforeAll {
    . "$PSScriptRoot/Get-Widget.ps1"
}

Describe 'Get-Widget' {
    Context 'When a known widget is requested' {
        It 'returns <Expected> for <Name>' -ForEach $testCases {
            $result = Get-Widget -Name $Name

            $result | Should-Be $Expected
        }
    }
}
```

## Discovery and Run

- Understand the two phases:
  - Discovery executes file-scope code, `BeforeDiscovery`, block definitions, names, tags, skip expressions, and
    `-ForEach` expansion.
  - Run executes `BeforeAll`, `BeforeEach`, `It`, `AfterEach`, and `AfterAll`.
- Define every value required by `-ForEach`, block names, tags, or discovery-time skip logic during Discovery.
- Do not try to create tests from `BeforeAll`; the test tree already exists by then.
- Pester 6 discovers and runs one file before moving to the next. Never use cross-file discovery side effects.
- Prefer self-contained files over shared bootstrap. When shared per-file initialization is unavoidable, configure
  `Run.BeforeContainer` or `Pester.BeforeContainer.ps1` deliberately and note that this surface is experimental in
  Pester 6.0.0.
- Use `$PSScriptRoot` or `$PSCommandPath` for test-relative paths. Do not use
  `$MyInvocation.MyCommand.Path` inside `BeforeAll`; it does not identify the test file there.

## Setup, Teardown, and Scope

- Use at most one `BeforeAll`, `BeforeEach`, `AfterEach`, and `AfterAll` in each file, `Describe`, or `Context`
  scope.
- Combine duplicate setup or teardown blocks; Pester 6 treats duplicates in the same block as errors.
- Use `BeforeAll` for shared, read-only setup and expensive imports.
- Use `BeforeEach` for mutable state so each test starts independently.
- Use `AfterEach` and `AfterAll` to release resources that Pester cannot isolate automatically.
- Keep setup close to the tests that consume it. Avoid global variables and state shared between test files.
- Do not hide a failed prerequisite with broad error handling. Use terminating errors for setup that must succeed.

## Importing Scripts and Modules

- Dot-source a script under test from `BeforeAll`.
- Import modules from their manifest when a manifest is part of the module contract.
- Use a clean process or remove an already loaded development module before re-importing it when stale state could
  change the result.
- Test public behavior by default. Use `InModuleScope` only when a private behavior materially needs direct coverage.
- Pass external values into `InModuleScope` explicitly with `-Parameters`.
- When code inside a module calls a dependency, use the same `-ModuleName` on `Mock` and `Should-Invoke`.

```powershell
BeforeAll {
    Import-Module "$PSScriptRoot/../Widget/Widget.psd1" -Force
}

Describe 'Widget module' {
    It 'calls the data provider once' {
        Mock -ModuleName Widget Get-WidgetData { @() }

        Get-Widget | Out-Null

        Should-Invoke -ModuleName Widget Get-WidgetData -Times 1 -Exactly -Scope It
    }
}
```

## Data-Driven Tests

- Prefer `-ForEach` for new tests. `-TestCases` remains an alias for `-ForEach` on `It`.
- Prefer arrays of hashtables so case values bind to clearly named variables.
- Use single-quoted test names with `<Name>` templates.
- In Pester 6, content inside `<...>` is evaluated as a PowerShell expression. Escape the leading `<` when literal
  expression-like text is intended.
- Pester 6 throws when `-ForEach` or `-TestCases` receives `$null` or an empty array.
- Fix missing data rather than disabling the check globally.
- Use `-AllowNullOrEmptyForEach` only when an empty data set and zero generated tests are intentional and reviewed.
- Do not set `Run.FailOnNullOrEmptyForEach = $false` as a routine workaround; it restores silent non-discovery.

## Assertions

- Prefer the Pester 6 `Should-*` commands for new tests.
- Classic assertions such as `Should -Be` remain supported. Do not require a bulk assertion rewrite merely to migrate
  a suite from Pester 5 to Pester 6.
- Assert one behavior per `It`. Multiple closely related assertions are appropriate when they describe one object or
  outcome.
- Choose the most specific assertion:
  - `Should-Be` and `Should-NotBe` for scalar comparisons.
  - `Should-BeTrue` or `Should-BeFalse` for actual Boolean values.
  - `Should-BeTruthy` or `Should-BeFalsy` only when truthiness is the intended contract.
  - `Should-BeCollection` when two collections must contain the same items and counts, regardless of order.
  - `Should-ContainCollection` for an ordered subcollection.
  - `Should-BeEquivalent` for deep recursive object comparison.
  - `Should-Throw` for terminating errors.
  - `Should-All` or `Should-Any` for a predicate across a collection.
- Remember that `$Expected` drives the comparison type for `Should-Be`; use an expected value with the intended type.
- Pipeline input unwraps values: a one-item array can become a scalar, an empty array can become `$null`, and a
  multi-item collection is re-collected as `[object[]]`.
- Pass `-Actual` when the exact value shape or concrete collection type is part of the contract.
- Use soft assertions intentionally. `Should.ErrorAction = 'Continue'` or `-ErrorAction Continue` records multiple
  failures in one test; use `Stop` for prerequisites where continuing would produce misleading failures.

```powershell
$result.Name | Should-Be 'Widget'
$result.Enabled | Should-BeTrue
$result.Items | Should-BeCollection @('one', 'two')
$result | Should-BeEquivalent $expected
{ Get-Widget -Name 'missing' } | Should-Throw -ExceptionMessage '*not found*'

Should-HaveType -Actual ([int[]](1, 2)) -Expected ([int[]])
```

## Mocking and Invocation Verification

- Mock external boundaries, not the command whose behavior the test is meant to exercise.
- Use an unfiltered default mock whenever filtered mocks might not match every call.
- In Pester 6, an unmatched filtered mock does not call the real command; it fails because no mock behavior matched.
- Prefer a fail-closed default mock when any unexpected call should fail the test.
- Keep `-ParameterFilter` focused on parameters relevant to the behavior.
- Verify important interactions with `Should-Invoke` or `Should-NotInvoke`.
- Use `-Times` with `-Exactly` when the exact count is part of the contract. `-Times 0` implies exact matching.
- Use `-Scope It` for per-test call counts when a mock is declared in a parent setup block.
- Use `-ExclusiveFilter` when every recorded call must match one filter.
- Use `Should-Invoke -Verifiable` for new assertion syntax when validating all verifiable mocks.
- Never permit an unexpected real network, filesystem, registry, cloud, or directory-service call during a unit test.

```powershell
Describe 'Get-RemoteWidget' {
    It 'requests the selected widget once' {
        Mock Invoke-RestMethod { throw 'Unexpected Invoke-RestMethod call.' }
        Mock Invoke-RestMethod {
            [pscustomobject]@{ Name = 'Widget' }
        } -ParameterFilter {
            $Uri -eq 'https://example.invalid/widgets/1'
        }

        $result = Get-RemoteWidget -Id 1

        $result.Name | Should-Be 'Widget'
        Should-Invoke Invoke-RestMethod -Times 1 -Exactly -Scope It -ParameterFilter {
            $Uri -eq 'https://example.invalid/widgets/1'
        }
    }
}
```

## Isolation, Tags, and Skips

- Keep tests deterministic and independent of execution order.
- Use `$TestDrive` for temporary files and directories.
- For Windows registry tests, use `TestRegistry:\` instead of the live registry and gate the tests to Windows.
- Use unique external resource names and clean up resources outside `$TestDrive`.
- Do not write generated test artifacts into the repository unless the test explicitly validates a committed fixture.
- Use `-Skip:$condition` for discovery-time platform or environment exclusions.
- Use `Set-ItResult -Skipped -Because 'reason'` or `Set-ItResult -Inconclusive -Because 'reason'` for runtime
  decisions. These commands end the test; do not add unreachable code after them.
- Prefer discovery-time `-Skip` when possible because setup and teardown still run for a runtime skip.
- Use tags for stable categories such as `Unit`, `Integration`, `Windows`, or `Slow`.
- Do not use `None` as a literal tag. In Pester 6, `None` is reserved by tag filters to mean untagged tests.
- Do not solve unreliable integration tests by silently skipping them. Make the required environment explicit.

## Configuration and CI

- Create configuration outside test files.
- Use `New-PesterConfiguration` when behavior extends beyond the simple `Invoke-Pester` parameters.
- Set an explicit run path and CI failure contract.
- Use `Run.PassThru = $true` when downstream automation needs the structured result.
- Use `Run.Throw = $true`, `Run.Exit = $true`, or an explicit `FailedCount` check according to the calling process;
  do not rely on formatted console output to decide success.
- Leave `Run.SkipRemainingOnFailure` at `None` unless later tests are genuinely invalid after an earlier failure.
- Enable test-result and coverage artifacts explicitly and assign deterministic output paths.
- Pester 6 code coverage supports `JaCoCo` and `Cobertura`. `CoverageGutters` is not a valid output format.
- Profiler-based coverage is the Pester 6 default. Set `CodeCoverage.UseBreakpoints = $true` only when a documented
  compatibility reason requires the old breakpoint behavior.
- Treat `Run.Parallel` as experimental in Pester 6.0.0. Enable it only after test files are self-contained and
  order-independent.
- Parallel execution requires PowerShell 7+ and file-based containers. Pester can fall back to serial execution for
  unsupported combinations, so validate the mode actually exercised by CI.
- Mark a file `#pester:no-parallel` only when its isolation constraint is real and documented.

```powershell
$configuration = New-PesterConfiguration
$configuration.Run.Path = @('./Tests')
$configuration.Run.PassThru = $true
$configuration.Output.Verbosity = 'Detailed'
$configuration.TestResult.Enabled = $true
$configuration.TestResult.OutputPath = './test-results.xml'
$configuration.TestResult.OutputFormat = 'NUnitXml'

$result = Invoke-Pester -Configuration $configuration
if ($result.FailedCount -gt 0) {
    throw "Pester reported $($result.FailedCount) failed test(s)."
}
```

## Migrating Pester 5 Tests to Pester 6

Apply this section only when the version preflight identifies a Pester 5 project. Perform the migration as a
behavior-preserving change before adopting optional Pester 6 style improvements.

1. Run the full suite with the project's pinned Pester 5 version in a clean process. Record discovered, passed,
   failed, skipped, inconclusive, and not-run counts. Preserve test-result and coverage artifacts when used.
2. Confirm every supported environment uses Windows PowerShell 5.1 or PowerShell 7.4+.
3. Pin a stable Pester 6 version. Update manifests, dependency installation, validation scripts, CI caches,
   scaffolds, examples, and maintained documentation together.
4. Run the unchanged suite on Pester 6 before rewriting assertions. Most Pester 5 suites should run unchanged.
5. Make each file self-contained. Remove dependencies on discovery-time state created by another test file.
6. Review newly discovered tests under hidden directories. Exclude paths deliberately with `Run.ExcludePath` only
   when they should not be tests.
7. Fix `$null` or empty `-ForEach` and `-TestCases` inputs. Use `-AllowNullOrEmptyForEach` only when zero tests is
   intentional.
8. Combine duplicate setup and teardown blocks in the same `Describe` or `Context`.
9. Replace `Assert-MockCalled` with the classic `Should -Invoke` migration target. Convert to `Should-Invoke` only
   during a separate, optional assertion migration.
10. Replace `Assert-VerifiableMock` with the classic `Should -InvokeVerifiable` migration target. Convert to
    `Should-Invoke -Verifiable` only during a separate, optional assertion migration.
11. Add an unfiltered default mock anywhere filtered mocks do not cover every valid invocation.
12. Replace `Set-ItResult -Pending` with skipped or inconclusive semantics.
13. Replace removed v4-style `Invoke-Pester` parameters such as `-Script`, `-OutputFile`, `-OutputFormat`,
    `-EnableExit`, and legacy `-CodeCoverage` usage with `New-PesterConfiguration`.
14. Replace `CodeCoverage.OutputFormat = 'CoverageGutters'` with `JaCoCo` or `Cobertura`.
15. Compare profiler-based coverage with the previous breakpoint baseline before accepting an unexplained percentage
    change. Use `CodeCoverage.UseBreakpoints = $true` only for a deliberate compatibility comparison.
16. Rename a literal `None` tag.
17. Review test names containing `<...>` because Pester 6 evaluates the token as an expression. Escape a leading `<`
    when the text must remain literal.
18. Run targeted tests after each migration category, then run the full suite in clean processes under every supported
    PowerShell edition.
19. Compare test counts, skip reasons, mock calls, result artifacts, coverage, and exit behavior with the baseline.
20. Keep classic `Should -...` assertions, including the mock assertion replacements above, until the suite is green.
    Convert to `Should-*` separately and incrementally.
21. Set `Should.DisableV5 = $true` only after the intended suite has fully converted to new assertions.
22. Consider parallel execution only after the serial Pester 6 migration is stable.

## Common Anti-Patterns

- Runtime imports or mutable setup at file scope.
- Cross-file variables, imports, mocks, or discovery ordering.
- Test data first created in `BeforeAll` and then referenced by `-ForEach`.
- Multiple setup or teardown blocks of the same kind in one scope.
- Filtered mocks without a default behavior.
- Broad mocks that hide incorrect parameters or unexpected calls.
- Using `$MyInvocation.MyCommand.Path` from `BeforeAll`.
- Disabling null-or-empty `-ForEach` failures globally instead of fixing discovery data.
- Using `Should-BeTrue` when truthiness, rather than Boolean identity, is intended.
- Piping a collection when its exact array type is part of the assertion.
- Reusing `None` as a literal tag.
- Enabling parallel execution before removing shared state and order dependence.
- Mixing dependency migration, assertion conversion, and unrelated production refactoring in one unreviewable change.
