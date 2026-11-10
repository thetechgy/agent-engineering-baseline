# Credential-free transfer admission correction

This is an output-informed admission correction, not a new experiment. The closed
allocation remains closed. Development outcomes remain unchanged. One retained
current-arm transfer submission cannot establish transfer benefit, candidate
regression safety or adoption readiness. No candidate, skill advice, dependency,
model setting, timeout, reference, mutant, score or production default changes.

## Original identity and diagnosis

[Original run 42911213479](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42911213479)
used source `a8ab2e2e03a2989863a514df2a6b357c44fbc012`. Artifact `13806864132`
has SHA-256 `2e314b9efc6acac1a393c6f87faa665506e4e1678296e6c34c1ebe79c1a7be86`.
The [retained manifest](../codex-retrospective/42911213479/manifest.json) binds the
exact submitted archive member, original report, staging and native trace. The
submission is 1,536 bytes, SHA-256
`c985298ef4fbe7a02ca8d1645fc0a07a3ed478084aafbf0489e6537748ffc0bf`.
The separate provenance receipt retains authenticated GitHub artifact/run/job
metadata. Offline replay authenticates that reviewed snapshot, not fresh GitHub
availability. Agent content is data; only the existing isolated verifier executes it.

The [parser-only diagnosis](diagnosis.json) records exact AST locations and the
authenticated effective runner digest. The effective runner composes `support/Runner.ps1`, `codex_pilot_contract`,
`codex_pilot_iteration`, then `codex_pilot_effectiveness`. Looking only at the
base runner misses existing Int64, iteration and invocation support. Pinned
PowerShell 7.6.9 parser admission reproduces `unsupported/expression_policy`.
The first rejecting node is the literal instance member `$results.Count`,
submission line 14: the task profile omits `Count`. A diagnostic runner that labels
this guard confirms the member rejection. A diagnostic profile adding only Count
then exposes the numeric type guard. These are diagnostic fixtures, not replays.

The complete submission also contains rejected literal numeric type expressions
on lines 27–32: sbyte, byte, short, ushort, uint, ulong, single, double, decimal,
and bigint. Int32 and Int64 forms are already supported by the composed runner.
`FindAll(..., $true)` visits every node, including all branches of short-circuit
expressions; fixing Count alone cannot make this submission gradeable. Corrected
parser admission of the unchanged full file covers the remaining nodes. Admission
is not evidence that its tests meet the correctness contract.

The task requires one returned object and leaves Quantity's concrete numeric type
unspecified. Literal collection size access and bounded numeric type predicates
are legitimate evaluation capabilities missing from the supported subset. The
frozen execution document is also imprecise about primitive forms. This does not
justify admitting arbitrary valid PowerShell. Dynamic members, arbitrary types,
new numeric casts, constructors, methods/reflection, protected data, member/index
writes, arbitrary commands and recursively concealed operations remain restricted.
No original grading outcome is overwritten.

## Versioned correction and semantic basis

`pester-collection-numeric-v1` is opt-in through the existing Pester task component.
It adds literal instance Count/Length reads and literal right operands of -is and
-isnot for a fixed numeric accelerator/CLR-name set. Existing cast permissions are
unchanged. The full recursive AST walk and external isolation are unchanged.
Only the admission runner and appended successor execution document differ from
the original protected task members. Historical policy and profile meanings stay
intact; new source receipts distinguish shared integration maintenance from older
qualification. No live protocol selects this admission policy.

Primary semantic references:

- [PowerShell 7.6.9 compiler](https://github.com/PowerShell/PowerShell/blob/bf5fc434120666e5f1a8d1dfd6ecac7efc17a4be/src/System.Management.Automation/engine/parser/Compiler.cs#L5705)
  compiles Is/IsNot with a literal Type into instance tests, without numeric conversion.
- [PowerShell 7.6.9 member binder](https://github.com/PowerShell/PowerShell/blob/bf5fc434120666e5f1a8d1dfd6ecac7efc17a4be/src/System.Management.Automation/engine/runtime/Binding/Binders.cs#L5487)
  implements Count/Length fallback for scalar/null values; ordinary arrays have
  collection members. Strict-mode behavior is separate and is not changed.
- [PowerShell tagged accelerator tests](https://github.com/PowerShell/PowerShell/blob/bf5fc434120666e5f1a8d1dfd6ecac7efc17a4be/test/powershell/Language/Parser/TypeAccelerator.Tests.ps1)
  and the same release's numeric conversion/type tables support the fixed numeric
  identities. The correction does not equate all numeric values or representations.
- [Pester 6.2.0 Should-Be source](https://github.com/pester/Pester/blob/98e56d65da1642a7158992b50ded240c42a3ac18/src/functions/assert/General/Should-Be.ps1)
  and [tagged tests](https://github.com/pester/Pester/blob/98e56d65da1642a7158992b50ded240c42a3ac18/tst/functions/assert/General/Should-Be.Tests.ps1),
  plus [Boolean assertion source](https://github.com/pester/Pester/blob/98e56d65da1642a7158992b50ded240c42a3ac18/src/functions/assert/Boolean/Should-BeTrue.ps1)
  and [tests](https://github.com/pester/Pester/blob/98e56d65da1642a7158992b50ded240c42a3ac18/tst/functions/assert/Boolean/Should-BeTrue.Tests.ps1),
  establish the evaluated assertion semantics. No skill advice changes.
- [Official type-comparison documentation](https://learn.microsoft.com/powershell/module/microsoft.powershell.core/about/about_comparison_operators#type-comparison)
  supports the distinction between type tests and conversion; the release source
  and executable pinned controls are authoritative for this qualification.

## CI runtime ownership

Publication run 42915524337 installed latest stable PowerShell 7.7.0 through
`install_ci_powershell.py`. `test_pester_ceiling.py` selected `CI_PWSH` and the
unchanged frozen runner rejected that runtime before Pester execution. This is
an infrastructure/runtime mismatch, separate from the paid pinned campaigns.

Latest-stable Linux/Windows validation still owns its existing CI runtime.
Immediately before frozen-grader checks, explicit `--runtime frozen-pester`
selection reuses the campaign's hash-verified `runtime_installer_bytes`, pinning
PowerShell 7.6.9 and Pester 6.2.0. The step supplies both absolute executable and
manifest. The strict grader version requirement and dependency pins remain intact.

## Qualification and retained replay

The targeted workflow runs original reproduction, focused controls and exact
retrospective replay through the existing native campaign, verifier, collection
and consolidated report paths. It has read-only contents permission, pinned
actions, no environment approval, model credential or inference. Independent
controls cover collection/type combinations, accelerator/CLR spellings, Is/IsNot,
weak/overrestricted work, malformed/discovery failures and adjacent prohibited
forms. Diagnostic reductions have explicit names and never replace the submission.
Existing missing-runtime, timeout and missing-evidence controls retain their
unmeasured meaning; this correction does not modify their grader or classifier.

The exact hosted source, authenticated artifact, cleanup, retrospective grade and
report reproduction receipt are maintained on [PR #131](https://github.com/thetechgy/agent-engineering-baseline/pull/131)
and linked from the authoritative checkpoint and draft PR #130. This implementation
record does not qualify an uncompleted native run.

Local focused integration passed 46 tests, with the existing optional semantic test
skipped. A separate trusted combined-capability fixture executed on PowerShell
7.6.9/Pester 6.2.0, passed the reference and detected all five unchanged mutants;
eight reference tests ran. This is component evidence, not external isolation or
the retained-submission grade. The initial broader suite used the candidate
runtime for historical producers and was interrupted after mismatches; that run
is inconclusive. Hosted CI owns the complete historical-runtime contract suite.

Actions review found no critical, high, medium or low findings in the focused
workflow/runtime edit. Pull-request execution is unprivileged, permissions are
read-only, checkout credentials are disabled, actions are SHA-pinned and scripts
receive no model secrets. The workflow has no paid gate or live dispatch step.

The first hosted correction revision `139cc0c` reproduced the original unsupported
outcome before its independent controls. Its full-validation step passed on
PowerShell 7.7.0; the new frozen acquisition then failed because the reused
installer's final import still named its container manifest path. Both downloaded
archives had verified hashes. The CI-only relocation now binds that final check
to the selected manifest with PowerShell path quoting. Real local acquisition
passed at a quoted destination with unchanged PowerShell/Pester bytes. Existing
campaign installers and their default container paths remain unchanged. The
initial deadline-contract job also exposed a snapshot exclusion that omitted two
newly appended source profiles; its original historical digest is retained.

The repaired real installation also passed the exact CI `test_pester_ceiling.py`
command: both positive suites passed, value-only/type-only suites remained distinct
measured failures, and broken discovery remained invalid/unmeasured. All five
controls used PowerShell 7.6.9 and Pester 6.2.0.
