# Return-contract execution results

**Stopped under the approved rules.** The newly authorized 18-attempt sequence launched seven attempts: six
measured development/candidate outcomes and one unmeasured transfer/current result. Eleven positions remain
unlaunched. Transfer/candidate was not dispatched. The conditional authorization is closed; no retry,
replacement or continuation is permitted by it. PR #130 remains unmerged.

The user authorized the exact [immutable
receipt](https://github.com/thetechgy/agent-engineering-baseline/blob/75b55ce29c8bcec4506dd5997a7fd1be7c253a1a/docs/evaluations/return-contract-new-allocation/RECEIPT.md),
execution revision `a8ab2e2e03a2989863a514df2a6b357c44fbc012`, its three allocations/nonces and matching
protected gates. Main and preparation validity were checked before both actual dispatches and both gate
approvals. Each authenticated receipt bound the selected campaign, source, artifact/digest, protocol, nonce and
run. The first complete checkpoint passed before the second dispatch. No third dispatch or gate approval
occurred.

## New sequence

| Campaign | Run | Launched / measured / unlaunched | Primary outcome | Estimated usage | Disposition |
| --- | --- | --- | --- | --- | --- |
| development/candidate | [42908510730](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42908510730) | 6 / 6 / 0 | candidate 3/3; its absent arm 0/3 | $0.2701149 | Complete checkpoint; continued |
| transfer/current | [42911213479](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42911213479) | 1 / 0 / 5 | Unavailable; three planned per arm | $0.0784082 | `unsupported_grading`, `expression_policy`; sequence stopped |
| transfer/candidate | Undispatched | 0 / 0 / 6 | Unavailable; three planned per arm | No model attempts | Authorization closed after the stop |

Development/candidate produced six valid submissions. All passed the reference; all three candidate-arm
submissions detected all five seeded defects, including integer-result. Its three absent-arm submissions missed
integer-result and detected the other four. These absent outcomes are legitimate measured task failures. This is
positive evidence on the output-informed development case, not broad causal evidence or an adoption decision.

Transfer/current stopped at position 1 (current arm). The native agent completed without a native exception and
produced an exact retained submission. The frozen task grader rejected it with `classification=unsupported`,
`code=expression_policy`. It is unmeasured, not a task failure scored zero. No reference or mutant correctness
is inferred from the retained test text. The remaining five positions and all six transfer/candidate positions
stayed unlaunched. Transfer benefit and regression remain unestablished.

The submission uses Boolean type checks and a union of numeric type checks for Quantity. The retained rejection
code establishes that the frozen expression admission policy did not support the submission; it does not
establish which construct caused the rejection, whether the suite satisfies the task contract, or whether policy
or task instructions should change. No submission, grader, fixture, scoring rule, model setting, dependency,
600-second deadline or isolation policy was changed, and the submission was not resubmitted or regraded as a
completed trial.

## Checkpoints, usage and cleanup

Development/candidate passed independent checks for six measured outcomes, exact submissions/producer receipts,
runtime configuration and distinct environments, known native usage, matched deployment/parsed descriptors,
protected fixture bytes and cleanup. Machine-readable public output and consolidated HTML reproduced byte for
byte from downloaded native/public evidence. Its known $0.2701149 estimated usage remained below the $3
per-campaign planning estimate and $5 scheduling threshold.

Transfer/current retained its unsupported outcome, complete native token accounting, exact produced submission
receipt and completed cleanup. Its public task measurements remain unavailable. Machine-readable public output
and HTML also reproduced byte for byte. The first unsupported result stopped scheduling; the later campaign was
not used to bypass that stop.

**New sequence estimated usage: $0.3485231 across seven launches**, all with complete native usage accounting.
This is an estimate from reported tokens and frozen pricing, not a provider invoice. The approved $9 estimate
and $24 planning allocation did not authorize extra attempts. Each campaign retained its $5 scheduling threshold
and $3 reserve within $8 planning allocation; these are not provider billing caps, and CI costs are separate.
Historical total spending remains unknown.

The completed development report retains `availability.status=incomplete` / `execution_incomplete` because the
existing custom-only collector always sets `diagnostic_only=true`. Its native `report_status=complete`, both arm
statuses succeeded, and both have three recorded/scored attempts. This conservative diagnostic-suite label is
preserved; it was not mistaken for missing essential trial evidence. Transfer/current differs: its native report
is actually incomplete, with `coverage_missing`, an unsupported result and five unlaunched positions. The
sequence stopped on that genuine grading boundary. The public schema also retains its producer-assurance and
custom cross-run limitations; external GitHub producer/archive authentication is recorded separately.

All seven launched attempts passed the producer resource comparison and final cleanup checks. Completed native
runtime audits record runtime-home cleanup. No timeout, cancellation or secondary collection failure occurred in
these new campaigns. Their successful lifecycle does not establish why the historical candidate slot stalled,
and no stall cause is manufactured.

## Historical records remain separate

| Historical record | Preserved result | Treatment |
| --- | --- | --- |
| development/current, [42844732493](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42844732493), source `9f6929f2b2be6ad66b40cd9ab9edf68caa124aee` | current 0/3; its absent arm 0/3; every reference passed; integer-result missed; $0.2705338 estimate | Separate historical comparator; not pooled or relabeled |
| development/candidate reliability event, [42847531876](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42847531876) | one native 600-second deadline; correctness and usage unavailable; collection masked the primary cause | Excluded from correctness estimates; still visible as an unmeasured reliability event |

The development comparison is indirect: historical current minus its own absent result is 0, while new candidate
minus its own absent result is 1 (three trials per arm in each pair). Their descriptive difference is +1 on the
frozen joint-quality fraction for this case. This is not one prospectively matched cohort or a direct randomized
current/candidate comparison. Different dates/source revisions, possible provider drift, the output-informed
task/candidate design and small samples remain explicit. Transfer/current is unmeasured and transfer/candidate
unrun, so no corresponding transfer comparison or candidate regression conclusion is available.

The historical native records were reproduced under their original `9f6929f2b2be6ad66b40cd9ab9edf68caa124aee`
source. The newer source correctly refuses their older custom input manifest. Their archived public bytes were
independently authenticated and reproduced without weakening that boundary; the current renderer consumes those
original public records alongside the new records. Historical grades, the old closed allocations and unavailable
historical accounting remain unchanged.

## Reviewable evidence

The [consolidated HTML report](execution/consolidated/report.html), [validated
analysis](execution/analysis/analysis.json), [original public inputs](execution/data/), [report
receipt](execution/report-receipt.json) and [execution receipt](execution/results.json) form the portable report
package. The HTML uses the existing renderer and comparison policy; custom cross-run comparisons remain deferred
and cohorts remain separate. Independent reproduction of the four-record consolidated report matched SHA-256
`af83335d938115ab287abb54d65da41cb9fad015e386255743b77bb10fbf35b2`. Open the HTML from a local
checkout/download; GitHub displays it as source. The public inputs use the existing flat-bundle format, with unchanged
original JSON bytes and record identities. This avoids Windows checkout path limits. The first result-publication
CI run failed at Windows checkout before tests on the longer nested paths and was superseded; that failure is
a publication packaging defect, separate from native execution. Flat-bundle admission and report reproduction
passed without changing the reporting implementation or outcomes.

| New native artifact | Digest / expiration / essential internal location |
| --- | --- |
| [13808015117](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42908510730/artifacts/13808015117) | `sha256:3a8661a1001b9b7bedc7c73562b451eae9ee60687f53295976e9a40b314d2745`; expires `2027-02-08T21:47:59Z`; `campaign-live/evidence/attempt-ledger.json`, `native/`, `public/`, `analysis/analysis.json`, `consolidated/report.html`, `cleanup.json` |
| [13806864132](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42911213479/artifacts/13806864132) | `sha256:2e314b9efc6acac1a393c6f87faa665506e4e1678296e6c34c1ebe79c1a7be86`; expires `2027-02-08T22:05:16Z`; `campaign-live/evidence/attempt-ledger.json`, `native/`, `public/`, `analysis/analysis.json`, `consolidated/report.html`, `cleanup.json` |

The matching authenticated-preparation artifacts are `13804944166` (development/candidate; SHA-256
`26e372098d294ee715e4b4a751f7308ac04221f398b77b5d681b10352210b2d6`) and `13808265348` (transfer/current; SHA-256
`07bcdbc63459e784b337e5ba4ff1348bc5f29ae671e3bb0c69aa6351307732c5`). Their full bindings and gate checks are
retained in the execution receipt.

The unsupported transfer submission is 1,536 bytes, SHA-256
`c985298ef4fbe7a02ca8d1645fc0a07a3ed478084aafbf0489e6537748ffc0bf`. Its native produced-artifact receipt matches
the retained submitted bytes. Its internal member is recorded in `retained_unmeasured_submission` in the
execution receipt; raw agent-authored code is kept in the native artifact as data, not added to repository test
discovery.

**One recommended next action:** Review the retained transfer/current submission against the task-owned
expression admission policy in credential-free analysis before proposing another allocation.

No additional paid dispatch, gate, retry, replacement, continuation, judge, adoption, dependency/default change
or merge is authorized by this closed sequence.

## Subsequent credential-free correction

The original execution and grades above remain unchanged. The separate
[output-informed correction and retrospective replay](admission/REPLAY.md) on PR #131
does not reopen this allocation or establish candidate benefit.
