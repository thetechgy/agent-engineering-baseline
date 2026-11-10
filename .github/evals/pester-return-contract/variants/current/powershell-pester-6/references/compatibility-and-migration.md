# Compatibility and Migration

Read this reference when the project pins an older version, when comparing release behavior, or when a Pester 5
migration is authorized. A missing dependency or old pin is not permission to upgrade it.

## Stable Version Boundaries

Pester 6.2.0 was the latest stable release verified on 2026-10-24. Honor existing pins. Use current
[Pester documentation](https://pester.dev/docs/quick-start) first, but resolve stale guidance against the selected stable
tag and its tests. In particular, the current v5-to-v6 migration page still says duplicate setup blocks are errors,
and the configuration page's parallel descriptions lag 6.2.

| Behavior | 6.0.x | 6.1.x | 6.2.0 |
| --- | --- | --- | --- |
| Discover and run one file at a time | Yes | Yes | Yes |
| Multiple setup/teardown blocks of one kind in a scope | Error | Error | Compose; setup in declaration order, teardown in reverse |
| `Run.BeforeContainer` configuration | Available, experimental | Removed | Removed |
| `Pester.BeforeContainer.ps1` convention | Root-only, experimental | Root-only, experimental | Root-to-test-folder chain, isolated container scope |
| Parallel execution | Experimental, PowerShell 7.4+ | Experimental, PowerShell 7.4+ | Experimental, also Windows PowerShell 5.1 |
| Parallel code coverage | Not supported | Worker breakpoints, merged report | Worker breakpoints, merged report |
| Shuffling and global mocks | Unavailable | Experimental | Experimental |
| `Should-ContainCollection -IgnoreOrder` and `Should-BeString -NormalizeLineEnding` | Unavailable | Available | Available |
| Unusable wrong-type values in configuration hashtables | Can be silently ignored | Can be silently ignored | Throw |
| Unknown configuration hashtable keys | Do not rely on validation | Do not rely on validation | Warn during `Invoke-Pester`, then ignored |

Sources: [6.0.0 runtime](https://github.com/pester/Pester/blob/6.0.0/src/Pester.Runtime.ps1),
[6.1.0 release](https://github.com/pester/Pester/releases/tag/6.1.0),
[6.2.0 release](https://github.com/pester/Pester/releases/tag/6.2.0),
[6.2.0 configuration conversion](https://github.com/pester/Pester/blob/6.2.0/src/csharp/Pester/DictionaryExtensions.cs).
Use [execution](execution.md) for current shared setup, parallel, shuffle, and global-mock mechanics.

### Shared Setup on 6.0 / 6.1

The `Pester.BeforeContainer.ps1` convention exists in 6.0; it was not introduced in 6.1. These releases load the
repository-root file only. They do not have 6.2's nested inheritance or container-scope isolation; setup functions
and variables can leak into the calling session. Keep setup repeatable and avoid cross-file dependence. The 6.0
`Run.BeforeContainer` scriptblock option was removed in 6.1: do not suggest it for later pins.

In 6.0/6.1, setup is dot-sourced into the run session before container discovery; bare imports and definitions can
be visible during both Discovery and Run, including later containers. Do not backport 6.2's phase and scope rules
to these versions. When an authorized upgrade adopts 6.2, read [execution](execution.md) and move runtime setup
into `BeforeAll` and discovery data into `BeforeDiscovery` as needed. Prefer self-contained files where practical.
Explicit `Run.RepoRoot` avoids incorrect automatic root detection in worktrees (where `.git` is a file) and trees
without Git metadata.
See the tagged [6.0 configuration](https://github.com/pester/Pester/blob/6.0.0/src/csharp/Pester/RunConfiguration.cs)
and [6.1 runtime](https://github.com/pester/Pester/blob/6.1.0/src/Pester.Runtime.ps1).

### Runtime and Failure Caveats

- All stable Pester 6 releases require Windows PowerShell 5.1 or PowerShell 7.4+. Serial compatibility does not
  imply older releases can run in parallel on Windows PowerShell 5.1.
- 6.2 fixes import on early PowerShell 7.4 versions; distinguish that from a project's own runtime floor.
- 6.0.1 fixed one PowerShell 7-on-Windows parallel import race. The 6.2 release detects missing worker results,
  while identifying an underlying parallel import race as unresolved. These are different changes: do not claim
  6.2 removes all parallel import failures. Preserve diagnostics and test the actual supported runtime.
- Inspect test, block, and container failures, including discovery errors. `TotalCount` reports discovery, not
  selection or execution. When the job requires tests to run and pass, guard `PassedCount` as in the main example;
  `Run.Throw` can return normally for zero tests, all-filtered tests, and all-skipped tests.

Sources: [6.0.1 release](https://github.com/pester/Pester/releases/tag/6.0.1),
[6.2.0 release](https://github.com/pester/Pester/releases/tag/6.2.0),
[6.2.0 failure handling](https://github.com/pester/Pester/blob/6.2.0/src/Main.ps1).

## Authorized Pester 5 to 6 Migration

Use the [official migration guide](https://pester.dev/docs/migrations/v5-to-v6), adjusted for the chosen release's
boundaries above. Preserve behavior before adopting optional Pester 6 style improvements.

1. Run the full suite using the pinned Pester 5 in a clean process. Record discovered, passed, failed, skipped,
   inconclusive, and not-run counts. Preserve test-result and coverage artifacts when used.
2. Confirm every supported runtime meets Pester 6's floor. Choose a stable version within the authorized scope;
   update manifests, dependency installation, validation scripts, CI caches, scaffolds, examples, and maintained
   documentation together.
3. Run the unchanged suite on Pester 6 before rewriting assertions. Most Pester 5 tests work unchanged.
4. Make files self-contained. Remove dependence on another file's discovery state. Review newly discovered tests
   under hidden directories; use `Run.ExcludePath` only for paths that should not contain tests.
5. Fix null/empty `-ForEach` and `-TestCases` data. Use `-AllowNullOrEmptyForEach` only for deliberate zero-test
   cases, without globally disabling failure on missing data.
6. For 6.0/6.1, combine duplicate setup/teardown blocks of one kind within a scope. For 6.2, preserve composition
   semantics and verify setup declaration order and reverse teardown order when relevant.
7. Replace `Assert-MockCalled` with `Should -Invoke`, and `Assert-VerifiableMock` with `Should -InvokeVerifiable`.
   Conversion to `Should-Invoke` is a separate optional assertion change. Unmatched filtered mocks now fail;
   add a default only for another valid call or an intentional diagnostic.
8. Replace `Set-ItResult -Pending` with skipped or inconclusive semantics.
9. Replace removed v4-style `Invoke-Pester` parameters (`-Script`, `-OutputFile`, `-OutputFormat`, `-EnableExit`,
   legacy `-CodeCoverage`) with configuration. Replace `CoverageGutters` with `JaCoCo` or `Cobertura`.
10. Compare profiler coverage to the previous breakpoint baseline before accepting unexplained percentage changes;
    use `CodeCoverage.UseBreakpoints = $true` for a deliberate compatibility comparison.
11. Rename literal `None` tags. Review `<...>` in names because Pester 6 evaluates expressions; escape a leading
    `<` when literal expression-like text is intended.
12. Run focused tests after each category, then the full suite in clean processes on supported editions. Compare
    counts, skip reasons, mock calls, result artifacts, coverage, and process failure behavior to the baseline.
13. Keep classic assertions until green. Convert incrementally afterward; set `Should.DisableV5 = $true` only
    once the intended suite is fully converted. Consider parallelism only after a stable serial migration.

For an authorized custom-assertion task, `New-ShouldAssertion` is available in 6.1+; use the selected release's
[custom assertion guidance](https://pester.dev/docs/assertions/writing-assertions) rather than applying it to 6.0.
