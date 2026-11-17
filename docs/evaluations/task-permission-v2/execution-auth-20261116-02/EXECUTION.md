# Completed task-permission authentication smoke pilot

**Completed; allocation closed.** [Run 43945876284/A1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43945876284)
executed **c0ef9b195beb7bd04d961272bafe1eadd080b3be** on November 16, 2026.
Authentication, protected approval, real Codex execution, deterministic permission
grading, evidence collection, cleanup and consolidated reporting completed. This
report-only revision follows terminal execution and allocation closure; it was
not the evaluated revision. PR #147 subsequently merged as `d5a04d4394c16108870f95974dd20fa51482e29a`;
the merge revision was not executed.

## Authorization and verified preparation

The user's explicit authorization covered one first-attempt dispatch and only its
matching `skill-benchmark` gate for the exact allocation in
[allocation-closure.json](allocation-closure.json). All previous allocations remain
closed. The [qualified receipt](https://github.com/thetechgy/agent-engineering-baseline/pull/147#issuecomment-6923566341)
was checked against the actual branch, required/change-selected
[CI 43928230083/A1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43928230083),
[preparation 43928221761/A1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43928221761)
and [fresh inspection 43934266352/A1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43934266352).
Required checks and all selected jobs passed at the execution SHA; 21 jobs
succeeded and six were intentionally skipped. Successful preparation was reused.

Preparation artifact **14258922655** was available and unexpired, with archive
`sha256:9e32e731101a81b55a311b93cef5bc15cceed440508f0fae66808315420f607f`,
producer `43928221761/A1`, internal location `preparation/evidence` and expiry
`2027-02-14T18:23:04Z`. Existing bounded admission independently reconstructed the
frozen members under the verified pinned owner. The 19-case authentication proof
and fresh-consumption archive also matched their recorded digests. They are
preparation evidence, not live observations.

Complete campaign and repository dispatch histories had no matching allocation
before dispatch. The receipt's exact command ran once, retaining the intentional
empty `preparation_artifact` input. Final history contains one matching run,
attempt 1. No retries, replacement dispatches or extra attempts occurred.

Live authentication produced artifact **14264673089**, archive
`sha256:0b160e26b1fdb3f8ffdca8ea64c2b2f044a03cb6a26d9bd1d9b1f64b47b1dddc`.
Its downloaded receipt passed the existing validator against this run, allocation,
source, definition, selection, protocol, producer and archive. Only then was this
run's normal `skill-benchmark` environment approval submitted. Environment settings
and protections were not changed. Fresh consumption on the live runner completed
before credential delivery.

## Live outcomes

| Arm | Execution | Correctness | Task authorization | Activation | Target access | Estimated USD |
| --- | --- | --- | --- | --- | --- | --- |
| Current | Completed; CLI exit 0 | 1 | 1; permitted | 1 | Deployed; successful full read observed | 0.1088368 |
| Absent | Completed; CLI exit 0; measured task failure | 1 | 0; denied `unlisted_directory` | 0 | Target absent; full-read observation null | 0.0888972 |

Current's native task gate passed. Absent's task gate failed; correctness,
authorization and activation remain separate. Its native trace attempted directory
discovery at the workspace skill path and the undeployed agent skill location;
the retained verifier records `unlisted_directory`, with no unsupported or unknown
permission result. This is the frozen policy's measured result. No grader,
permission rule, task, skill, resource or expected outcome was changed to alter it.
Absent's null successful-full-read observation is not a measured zero read.

Both exact native submissions are 58 bytes, SHA-256
`32d74b2c3f287c2ea5832150700be3b958f553e2852a2f2a0c17e1ddfb08f5de`.
Retained bytes match both producer receipts and ledger identities. Both attempts
used SkillEvaluator **0.9.0**, Harbor **0.25.0**, Codex CLI **0.155.1**,
**gpt-5.6-sol / high**, and `custom_only` grading in separate agent environments.

The serial transition ledger records current as completed with usable grades,
submission, runtime/access evidence, known estimated usage and cleanup before
absent entered `launching`. Its cumulative estimate at that boundary was
**$0.1088368**, below the **$3** scheduling threshold. The completed ledger has no
operational stop or report failure. Existing 600-second agent, 1,200-second launch,
cleanup/grace and reservation controls were preserved.

There were **two launched and measured slots, zero unlaunched slots, two
deterministic verifier invocations and zero model-judge calls**. Current reported
92,649 input / 75,672 cached / 533 output tokens; absent reported
75,045 / 63,523 / 870. Frozen-price estimated usage totals **$0.1977340**.
These producer-reported observations are not invoices. The accepted $2 estimate,
$3 scheduling threshold and $3 reserve within $6 planning allocation were never
provider billing caps; in-flight overshoot remains possible and CI costs are
separate. Actual billing was not independently reconciled.

## Evidence, cleanup and report verification

[Live artifact 14264758942](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43945876284/artifacts/14264758942)
has archive digest
`sha256:14f2ad0fee32a133aa2452afff297eb99c314d7c4203f0688d49c8946a10d5ef`.
Its producer, exact execution SHA, metadata, digest and bounded data-only extraction
were checked. [receipts.json](receipts.json) records artifact expirations, source
bindings, per-arm outcomes/accounting and hashes of the original retained runtime,
policy, submission, native trace, trajectory and verifier witnesses.

Both per-arm native cleanup witnesses say complete, both row cleanup checks pass,
and the scheduler's resource-return comparison and final `cleanup.json` are
complete. Distinct environment identities were verified. No pending gate remains.
These are the retained execution witnesses; they do not independently extend the
accepted child-process, credential, log or egress observation boundaries.

The public behavioral evidence was admitted through the existing validator. The
existing consolidated renderer was then run independently from public inputs
using the pinned owning runtime. Its output matches both produced report copies
byte for byte, SHA-256
`d7dc58351e79c00f57bb90539646ebdf45de2f5a215febe1806a69cf961001d0`.
No model, task or deterministic verifier was rerun for report reproduction.
Essential live evidence is present; absent full-read evidence remains null and
invoice reconciliation is unavailable. Preparation fixtures do not fill either gap.

The exact allocation was closed at **2026-11-16T20:12:55.362297Z**, after terminal
execution and verification and before report-only edits. Both authorized slots are
consumed. No retry, replacement, continuation or further paid work is authorized.
The earlier stopped allocation and historical records remain closed and unchanged.

This establishes the bounded operational path with real Codex output, including a
legitimate measured permission failure. Two attempts on one case do not establish
skill benefit, repeatability, general grading coverage, standard-judge accuracy,
invoice reconciliation or production readiness. Production defaults, skills,
pins, schedules, isolation, Pages, production history and deferred Pester adoption
are unchanged. No merge or adoption occurred.

**One recommended next action:** review PR #147's completed operational evidence
before considering a separately scoped broader evaluation.
