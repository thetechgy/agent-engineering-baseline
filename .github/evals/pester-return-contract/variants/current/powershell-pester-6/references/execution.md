# Optional Execution Features

Read the relevant section before adopting shared per-file initialization, parallelism, shuffling, or global mocks.
These surfaces remain experimental in stable Pester 6.2.0. For an older pin, also read
[compatibility and migration](compatibility-and-migration.md).

## Shared Per-File Setup

Prefer self-contained test files. When repetition justifies shared setup, Pester 6.2 dot-sources
`Pester.BeforeContainer.ps1` files from `Run.RepoRoot` down to each test file's directory, outermost first. A
`#pester:no-inherit` comment in a setup file cuts off ancestor setup files while retaining that file's own setup.
Each container gets its own setup scope; files run before every container and must be safe to execute repeatedly.

Set `Run.RepoRoot` explicitly when running in a worktree or a tree without Git metadata. Automatic detection
searches for a `.git` directory, so a worktree's `.git` file does not establish the intended root.

Bare statements in a setup file execute during Discovery, not automatically during Run. Register `BeforeAll` for
runtime imports and `BeforeDiscovery` for data needed by `-ForEach`. For example, in a root setup file:

```powershell
BeforeAll {
    Import-Module "$PSScriptRoot/Widget/Widget.psd1" -Force
}
```

Here `$PSScriptRoot` belongs to the setup file. In a test file, use that test's own `$PSScriptRoot` for its paths.
Do not assume a bare discovery-time import makes commands available in the Run scope or in parallel workers.
Do not configure the removed `Run.BeforeContainer` option on 6.1+.

Sources: [6.2 setup chain and no-inherit](https://github.com/pester/Pester/blob/6.2.0/src/functions/Pester.BeforeContainer.ps1),
[6.2 runtime](https://github.com/pester/Pester/blob/6.2.0/src/Pester.Runtime.ps1),
[6.2 root configuration](https://github.com/pester/Pester/blob/6.2.0/src/csharp/Pester/RunConfiguration.cs).

## Parallel Execution

Parallelism is opt-in (`Run.Parallel = $true`), experimental, and off by default. Establish a passing serial suite
with independent files before enabling it. Pester 6.2 uses a runspace pool on Windows PowerShell 5.1 and PowerShell
7.4+; 6.0/6.1 require PowerShell 7.4+ and use `ForEach-Object -Parallel`.

- File-based containers are eligible, including those made with `New-PesterContainer -Path`. A ScriptBlock
  container, `Run.SkipRemainingOnFailure = 'Run'`, or every file opting out causes serial fallback.
- A file's `#pester:no-parallel` directive schedules it serially after the parallel batch. Document the real
  constraint instead of using the directive to hide an order-dependent failure.
- `Run.ParallelThrottleLimit` bounds concurrency; its default `0` uses available processors. A value of `1` still
  uses worker runspaces. Set `Run.Parallel = $false` to reproduce serial behavior or debug in the calling session.
- Workers have separate runspaces in the **same process**. Session variables, imports, and mocks need their own
  initialization, while files, external services, environment variables, and static .NET state can still collide.
  This is not a security sandbox. `$TestDrive`, unique names, and cleanup remain necessary.
- From 6.1, workers measure coverage using breakpoints and the parent merges results. Serial coverage defaults
  to the profiler. Compare like modes when interpreting differences; do not assume serial profiler behavior in
  workers.
- Validate that the requested mode actually ran on the supported runtime; serial fallback is not parallel
  evidence. Preserve missing-worker/import failures; the 6.2 release detects missing results without claiming the
  underlying import race is fully fixed.

For a caller with an already selected Pester import:

```powershell
$configuration = New-PesterConfiguration
$configuration.Run.Path = @('./Tests')
$configuration.Run.RepoRoot = (Get-Location).Path # Run this caller from the intended repository root.
$configuration.Run.Parallel = $true
$configuration.Run.ParallelThrottleLimit = 4
$configuration.Run.Throw = $true
Invoke-Pester -Configuration $configuration
```

Choose a throttle appropriate to the suite and environment. This example throws on failures; apply the main
skill's expected-execution guard too when the caller requires tests to run and pass.

Sources: [parallel documentation](https://pester.dev/docs/usage/parallel) (some descriptions lag 6.2),
[6.2 configuration](https://github.com/pester/Pester/blob/6.2.0/src/csharp/Pester/RunConfiguration.cs),
[6.2 workers](https://github.com/pester/Pester/blob/6.2.0/src/functions/Pester.Parallel.ps1),
[6.1 release](https://github.com/pester/Pester/releases/tag/6.1.0),
[6.2 release](https://github.com/pester/Pester/releases/tag/6.2.0).

## Shuffled Test Order

Shuffling is experimental in 6.1+. Set `Run.Shuffle = $true` to expose hidden order dependencies. The default
`Run.ShuffleSeed = 0` chooses and reports a seed. Record that seed; use it in a serial rerun to reproduce ordering.
Parallel scheduling prevents a globally reproducible cross-file order even with a fixed shuffle seed.

```powershell
$configuration = New-PesterConfiguration
$configuration.Run.Path = @('./Tests')
$configuration.Run.Parallel = $false
$configuration.Run.Shuffle = $true
$configuration.Run.ShuffleSeed = 12345
$configuration.Run.Throw = $true
Invoke-Pester -Configuration $configuration
```

Shuffling stays within each file/block/test level. `#pester:no-shuffle` preserves a file's internal ordering, but
its position among other files can still shuffle. Use it only for an intentional ordering contract, and do not
treat a passing shuffled run as proof that shared state is safe.
See [shuffling documentation](https://pester.dev/docs/usage/shuffle) and the
[6.1 release](https://github.com/pester/Pester/releases/tag/6.1.0).

## Global Mocks

The configuration option `Mock.Global = $true` is experimental in 6.1+. It broadens interception across modules
in the current runspace; mocks themselves still use the normal `Mock` command.
`-ModuleName` helps resolve the command to mock; it does not limit a global mock to that module. Keep normal
module-targeted mocks unless the behavior requires broader interception, verify relevant calls and counts, and
check that unrelated module calls are not accidentally hidden. Global mocks do not intercept other runspaces or
provide a security boundary. Avoid fallback examples that invoke a live external command when a filter misses.

See [mocking documentation](https://pester.dev/docs/usage/mocking) and the
[6.1 release](https://github.com/pester/Pester/releases/tag/6.1.0).
