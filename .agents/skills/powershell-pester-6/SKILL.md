---
name: powershell-pester-6
description: 'Author, review, debug, or migrate Pester tests, including discovery, assertions, mocking, CI failure handling, and PowerShell compatibility.'
---

# PowerShell Pester 6 Testing Guidelines

Target released, stable behavior. Pester 6.0.0 is the minimum compatibility baseline, distinct from the preferred
current release below. Do not use prerelease or repository `main` behavior unless the project explicitly opts in.

## Determine the Project Version First

- Inspect module manifests, dependency files, validation scripts, CI workflows, and explicit `Import-Module` calls.
- Honor the project's declared or pinned Pester version. Do not infer it from the newest locally installed module
  or silently upgrade an existing project.
- For an unconstrained new project, choose the latest verified stable release: **6.2.0, verified 2026-10-24**.
  Recheck the [stable releases](https://github.com/pester/Pester/releases) before choosing a later version.
- Read [compatibility and migration](references/compatibility-and-migration.md) whenever an older Pester version
  needs guidance. A Pester 5 declaration does not authorize migration; migrate only when requested.
- Pester 6 supports Windows PowerShell 5.1 and PowerShell 7.4+. Honor the tested project's runtime floor; a
  Windows PowerShell 5.1 project still needs compatible syntax.
- Start with current [Pester documentation](https://pester.dev/docs/quick-start). When it lags the chosen release, use
  that release's notes, tagged source, and tests, rather than applying newer behavior to an older pin.

## File Naming and Structure

- Name files `*.Tests.ps1`, identifying the tested command, module, or behavior.
- Make every test file self-contained. Do not depend on another file being discovered or run first.
- Put runtime setup in `BeforeAll` or `BeforeEach`, not at file scope.
- Use `BeforeDiscovery` for values needed to build the test tree, such as external `-ForEach` data.
- Keep names behavior-focused and free of secrets or sensitive identifiers: names appear in output and artifacts.

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
    It 'returns <Expected> for <Name>' -ForEach $testCases {
        Get-Widget -Name $Name | Should-Be $Expected
    }
}
```

## Discovery, Setup, and Scope

- [Discovery](https://pester.dev/docs/usage/discovery-and-run) executes file-scope code, `BeforeDiscovery`, block
  definitions, names, tags, skip expressions, and `-ForEach` expansion. Define their inputs in that phase.
- Run executes `BeforeAll`, `BeforeEach`, `It`, `AfterEach`, and `AfterAll`. Do not create tests in `BeforeAll`:
  the test tree already exists.
- Since 6.0, Pester discovers and runs one file before moving to the next. Avoid cross-file discovery side effects.
- Use `BeforeAll` for shared, read-only setup and expensive imports; use `BeforeEach` for mutable state.
- Release resources Pester cannot isolate in `AfterEach` or `AfterAll`. Keep setup close to its consumers; avoid
  global variables and cross-file state. Let failed prerequisites terminate instead of hiding them in broad catches.
- In 6.2, multiple setup blocks of the same kind compose in declaration order; teardown blocks compose in reverse
  order. Older releases differ: consult the compatibility reference before changing existing setup structure.
- Use `$PSScriptRoot` or `$PSCommandPath` for test-relative paths, not `$MyInvocation.MyCommand.Path` inside
  `BeforeAll`, where it does not identify the test file.
- Prefer self-contained files. For shared per-file setup, read [execution](references/execution.md), including
  `Pester.BeforeContainer.ps1` phase, scope, inheritance, and `Run.RepoRoot` boundaries.

## Importing Scripts and Modules

- Dot-source a script under test from `BeforeAll`. Import a module from its manifest when that is its contract.
- Use a clean process, or remove an already loaded development module before re-importing, when stale state could
  change the result.
- Test public behavior by default. Use `InModuleScope` only when a private behavior needs direct coverage, and
  pass external values explicitly with `-Parameters`.
- When a module calls a dependency, use the same `-ModuleName` on `Mock` and `Should-Invoke`.

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

- Prefer `-ForEach` with arrays of hashtables for new tests. `-TestCases` remains an alias on `It`.
- Use single-quoted names with `<Name>` templates. Pester 6 evaluates `<...>` as a PowerShell expression; escape
  the leading `<` when expression-like text must be literal.
- Pester 6 throws for `$null` or empty `-ForEach` / `-TestCases` inputs. Fix missing data rather than disabling
  `Run.FailOnNullOrEmptyForEach` globally.
- Use `-AllowNullOrEmptyForEach` only when the empty data set and zero generated tests are intentional and reviewed.

## Assertions

- Prefer [Pester 6 `Should-*` commands](https://pester.dev/docs/assertions/should-command) for new tests. Classic
  `Should -Be` and related assertions remain supported; migration does not require a bulk rewrite.
- Assert one behavior per `It`; related assertions can describe one object or outcome.
- Choose the assertion that matches the contract:
  - `Should-Be` / `Should-NotBe` compare scalars; the expected type drives conversion.
  - `Should-BeTrue` / `Should-BeFalse` require Boolean identity; `Should-BeTruthy` / `Should-BeFalsy` test truthiness.
  - `Should-BeCollection` compares sizes and items, including duplicates, regardless of order; `-Count` checks
    cardinality alone.
  - `Should-ContainCollection` checks an ordered subsequence, allowing gaps. `-IgnoreOrder` is available in 6.1+;
    there is no `-InOrder` switch.
  - `Should-BeEquivalent` compares deep structure, ignoring collection order and allowing type coercion. Assert
    exact types or ordering separately when they are part of the contract.
  - `Should-BeString` compares case-insensitively by default; use `-CaseSensitive` when required. In 6.1+,
    `-NormalizeLineEnding` ignores line-ending differences only when the contract permits them.
  - `Should-Throw -ExceptionMessage` uses a wildcard pattern, not a regular expression.
  - `Should-All` / `Should-Any` apply a predicate across a collection.
- Pipeline input reshapes values: a value assertion sees a singleton as a scalar and an empty array as `$null`;
  collection assertions collect items, losing the concrete collection type. Use `-Actual` to preserve exact shape
  or type, including singleton arrays and dictionaries.
- Soft assertions (`Should.ErrorAction = 'Continue'` or `-ErrorAction Continue`) record multiple failures. Use
  `Stop` for prerequisites where continuing would mislead.

```powershell
$result.Name | Should-BeString 'Widget' -CaseSensitive
$result.Enabled | Should-BeTrue
$result.Items | Should-BeCollection @('one', 'two')
1, 2, 3 | Should-ContainCollection @(1, 3)
$result | Should-BeEquivalent $expected
{ Get-Widget -Name 'missing' } | Should-Throw -ExceptionMessage '*not found*'
Should-HaveType -Actual ([int[]](1, 2)) -Expected ([int[]])
```

## Mocking and Invocation Verification

- [Mock external boundaries](https://pester.dev/docs/usage/mocking), not the command under test. Avoid unexpected
  real network, filesystem, registry, cloud, or directory-service calls in unit tests.
- An unmatched filtered mock fails in Pester 6; it does not fall through to the real command. Add an unfiltered
  default when another call is valid, or optionally use a throwing catch-all for a clearer diagnostic.
- Keep `-ParameterFilter` focused on relevant parameters; broad mocks can hide incorrect calls.
- Verify interactions with `Should-Invoke` or `Should-NotInvoke`. Use `-Times` with `-Exactly` for exact counts;
  `-Times 0` is exact. Use `-Scope It` for per-test counts when declaring mocks in parent setup.
- Use `-ExclusiveFilter` when every recorded call must match a filter; use `Should-Invoke -Verifiable` to check
  all verifiable mocks.
- Experimental global mocks broaden interception in 6.1+. Read [execution](references/execution.md) before using
  them; normal module-targeted mocks remain the starting point.

```powershell
Describe 'Get-RemoteWidget' {
    It 'requests the selected widget once' {
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

- Keep tests deterministic and independent of order. Use `$TestDrive` for temporary files and directories.
- For Windows registry tests, use `TestRegistry:\` and gate to Windows. Give external resources unique names and
  clean them up. Keep generated artifacts outside the repository unless testing a committed fixture.
- Use `-Skip:$condition` for discovery-time platform/environment exclusions when possible. Runtime
  `Set-ItResult -Skipped -Because 'reason'` or `-Inconclusive` ends the test, but setup and teardown still run;
  do not put unreachable code after it.
- Use stable tags such as `Unit`, `Integration`, `Windows`, or `Slow`. `None` is reserved for filtering untagged
  tests, so do not use it as a literal tag.
- Make integration prerequisites explicit; do not silently skip unreliable tests.
- Read [execution](references/execution.md) before enabling experimental parallelism or shuffling. A separate
  runspace provides state isolation within the same process, not a security boundary.

## Configuration and CI

- Configure the normal `Invoke-Pester` caller outside test files, preferably in a clean `-NoProfile` process with
  the project-selected Pester imported. Do not rely on ambient `$PesterPreference` or profile settings.
- Use `New-PesterConfiguration` for the advanced interface, with explicit paths and a failure contract. Inspect the
  selected version's configuration; in 6.2 unusable wrong-type hashtable values throw, but unknown keys warn during
  invocation and are ignored. Older releases differ; see the compatibility reference.
- Choose failure handling for the caller: `Run.Throw = $true` makes test, setup, and discovery failures catchable;
  `Run.Exit = $true` suits a dedicated process. Alternatively, inspect a `Run.PassThru` result as below. A check of
  `FailedCount` alone misses block/container failures. Throw/Exit do not enforce an expected executed-test count.
- Leave `Run.SkipRemainingOnFailure` at `None` unless later tests become invalid after a failure.
- Enable reports explicitly with deterministic paths. Test-result formats are `NUnitXml`, `NUnit3`, and `JUnitXml`;
  coverage formats are `JaCoCo` and `Cobertura`, not `CoverageGutters`.
- Serial coverage uses the profiler by default; use `CodeCoverage.UseBreakpoints = $true` only for a deliberate
  compatibility reason or comparison. Read the execution reference for parallel coverage differences.

This result-inspection example requires at least one test to pass. `TotalCount` counts discovered tests, including
filtered/not-run and skipped tests: a nonzero total does not prove execution. Adapt the expectation only when the
job deliberately allows an empty selection or all-skipped run. See the released
[failure handling](https://github.com/pester/Pester/blob/6.2.0/src/Main.ps1).

```powershell
$configuration = New-PesterConfiguration
$configuration.Run.Path = @('./Tests')
$configuration.Run.PassThru = $true
$configuration.Run.Throw = $false
$configuration.Run.Exit = $false
$configuration.Output.Verbosity = 'Detailed'
$configuration.TestResult.Enabled = $true
$configuration.TestResult.OutputPath = './test-results.xml'
$configuration.TestResult.OutputFormat = 'NUnitXml'

$result = Invoke-Pester -Configuration $configuration
if ($result.Result -ne 'Passed' -or
    $result.FailedCount -gt 0 -or
    $result.FailedBlocksCount -gt 0 -or
    $result.FailedContainersCount -gt 0 -or
    $result.PassedCount -eq 0) {
    throw 'Pester did not complete a passing run with at least one passed test.'
}
```

## Compatibility and Migration

Read [compatibility and migration](references/compatibility-and-migration.md) for older pins or an authorized
Pester 5 migration. Preserve the existing assertion style until the migration is green, then adopt optional syntax
changes separately. Avoid mixing dependency migration, assertion conversion, and unrelated production refactoring.
