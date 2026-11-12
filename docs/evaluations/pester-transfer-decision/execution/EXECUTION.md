# Pester clarification transfer decision: defer

Defer the exact 22-line clarification. Development evidence supports it, but the
approved transfer sequence stopped before candidate could run. The frozen decision
table requires complete matched transfer evidence; that evidence is missing.
There is no demonstrated candidate regression on transfer and no basis to adopt.

## Executed authorization and mandatory stop

The user explicitly approved proposal `pester-transfer-decision-040b114-v1`, both
exact dispatches and their matching `skill-benchmark` gates, preserving every limit,
checkpoint and stop condition. The [original readiness receipt](../RECEIPT.md) and
[proposal](../proposal.json) remain unchanged historical records of that proposal;
this execution receipt records the subsequent authorization and outcome.

Execution source was exactly `040b11486ad3b7245e81fb6591f9d8dd78c32154`, dispatch
ref `prep/pester-transfer-decision`. Reporting publication does not move that ref.
Current campaign `pester-return-transfer-current-v5` ran once, attempt 1, in
[run 43322537842](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43322537842).
Its exact source, preparation digest, protocol and fresh allocation were verified
before approving only its matching protected environment gate. Fresh preparation
consumption passed before credential delivery. [Dispatch authentication](dispatch-authentication.json),
[gate verification](approval-verification.json) and [producer metadata](producer.json)
retain those bindings. Model credentials were never retrieved locally.

| Current-pair slot | Arm / repetition | Original executable outcome | Reference / defects |
| --- | --- | --- | --- |
| 1 | Current / 1 | Passed | Pass; 5/5 |
| 2 | Absent / 1 | Passed | Pass; 5/5 |
| 3 | Absent / 2 | Passed | Pass; 5/5 |
| 4 | Current / 2 | Unsupported: `test_name_template` | Unmeasured |
| 5 | Current / 3 | Unlaunched after stop | Unavailable |
| 6 | Absent / 3 | Unlaunched after stop | Unavailable |

The scheduler stopped at slot 4 with `unsupported_grading`; the workflow correctly
failed rather than continuing. This is an unmeasured admission result, not a measured
task failure or a candidate regression. Candidate campaign
`pester-return-transfer-candidate-v5` and all six of its slots remain **UNRUN**;
its gate was never approved. Eight of the twelve proposed slots are unlaunched.
No retry, replacement, judge, additional inference or continuation occurred.
The current allocation is closed. The never-claimed candidate ID is retired by the
stop, not reserved for later use. [Closure and complete dispatch-history check](closure.json)
retain both exact IDs and their dispositions.

## Why grading stopped

The [exact slot-4 submission](submissions/slot-4/Subject.Tests.ps1) is 1,682 bytes,
SHA-256 `bc18e373251007b3420a1b946803096d6fb2988bc60889bb99ed4a11cb464fc8`.
Its test name includes `<ExpectedEnabled>`, `<ExpectedQuantity>` and `<Requested>`.
The frozen runner accepts templates only for the task profile's public fields and
`_`. `ExpectedEnabled` is a local datarow key but is absent from that allowlist.
The unchanged guard rejects the template before reference/mutant execution.
[Source diagnosis](stop-diagnosis.json) binds the exact submission and guard.
This is source inspection supporting the retained admission code, not a new
runtime qualification, replay, favorable narrative grade or grading-policy change.

All four retained submissions were inspected. Both retained copies of each file
match the native production receipt; the three measured ones also match their
scheduler hashes. Those measured suites pass the reference, including its Int32/
Int64 Quantity variation, and all five declared defects: enabled-integer,
enabled-zero, quantity-offset, quantity-below and quantity-above. They test each
Quantity independently and do not require one concrete numeric type across calls.
This supports the executable grades for the exercised reference; it does not
qualify every numeric implementation. Slot 4 remains unmeasured despite its
readable assertions. Candidate transfer behavior, reliability and efficiency
remain unavailable. The ledger records a full current-skill read for slot 1;
access alone is not evidence of instruction following or causal benefit.

## Evidence, accounting and reproduction

Authenticated live [artifact 13991762820](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43322537842/artifacts/13991762820)
has archive digest `sha256:95d857db2a35e48e15e40175ec7ab937a62874faf5a6978a50bc77ab96b5b77d`
and expires `2027-02-10T22:43:38Z`. Its registered live evidence is
`campaign-live/evidence`; fresh-consumption evidence is
`campaign-live-preflight/evidence`. Archive bytes, sanitized native/retained evidence,
logs and independent reproduction remain in the persistent task evidence workspace.
[Artifact metadata](artifact.json), [original ledger](attempt-ledger.json),
[cleanup](cleanup.json), [checkpoint audit](current-checkpoint.json) and exact
[submissions](submissions) preserve all original outcomes.

All four launched sessions have known provider-reported token counts, unchanged
native grades, verified distinct environments and completed cleanup. Runtime,
model/configuration, preparation deployment, staged members and complete parsed
descriptors matched the frozen source. Both the pre-credential and live staging
checks passed. Native-to-public normalization and the current machine/HTML report
reproduced byte for byte; no report failure occurred. The checkpoint still fails:
only three measured outcomes exist and slot 4 is unsupported. Passing retention,
accounting and cleanup cannot satisfy the six-measured-outcome requirement.

Estimated usage across the four new launches is **$0.2374108**. The $5 scheduling
threshold, $3 reserve and $8 planning allocation per campaign ($16 total) were
unchanged. These are estimates and scheduling limits, not provider billing caps;
CI costs remain separate. Producer token estimates are not invoices. No candidate
usage exists, and historical total spending remains unknown. Cost/latency comparisons
cannot establish candidate efficiency or non-regression without candidate outcomes.

The [existing consolidated HTML report](consolidated/report.html) and
[machine analysis](analysis/analysis.json) use six preserved input bundles:
four original historical bundles, the separate diagnostic retrospective replay,
and the fresh stopped current campaign. [Cohort identities and file digests](cohorts.json)
keep those populations distinct. The HTML reproduces byte for byte with SHA-256
`79861dce94a3c43229d9bb25cbd7762ffabf5b6619c86c528f8266105a9915e9`.
No original PR #130 report or score was changed. Custom-only/diagnostic and
incomplete labels remain; standard/judged quality is not inferred from custom grades.

## Decision against the frozen criteria

| Cohort | Skill primary success | Own absent baseline | Interpretation |
| --- | --- | --- | --- |
| Historical development/current 42844732493 | 0/3 | 0/3 | Separate historical comparator; observed difference 0 points |
| Historical development/candidate 42908510730 | 3/3 | 0/3 | Development improvement; observed difference +100 points; absent missed integer-result |
| Fresh transfer/current 43322537842 | 1 pass, 1 unsupported, 1 unrun | 2 pass, 1 unrun | All measured submissions passed reference + 5/5; incomplete pair |
| Fresh transfer/candidate | 3 unrun | 3 unrun | Mandatory checkpoint prevented dispatch |
| Earlier transfer/current 42911213479 | Original unsupported/unmeasured | No completed pair | Exact retained submission retrospectively passed reference + 5/5; diagnostic only |

Among available measured outcomes in the fresh current pair, 1/1 current and 2/2
absent pass (descriptive observed difference 0 points). These unequal partial
samples are not the prescribed three repetitions per arm. A fresh candidate-minus-
absent difference and a current-versus-candidate comparison are unavailable.
Absent arms are never pooled; historical replay never fills a missing fresh slot.

The [frozen table](https://github.com/thetechgy/agent-engineering-baseline/blob/040b11486ad3b7245e81fb6591f9d8dd78c32154/.github/evals/pester-transfer-decision/DECISION.md)
explicitly defers for unsupported/unavailable evidence or an operational stop.
Its SHA-256 remains `b5fc9d7fc68129374aa485129561c7d096693e4333d732dbab77abdef535e392`.
Adoption's twelve measured outcomes, three candidate transfer successes and
candidate regression checks are unmet. Rejection's material candidate problem is
also unestablished because candidate never ran. Development success and retained
[tagged-source justification](../RECEIPT.md#frozen-comparison-and-criteria) remain
useful evidence, but do not excuse missing transfer evidence. Pester 6.2.0 /
PowerShell 7.6.9 are the evaluated releases; other source-reviewed versions are
not runtime-qualified by this work. Three trials would not establish statistical
non-inferiority or broad effectiveness even had the sequence completed.

No adoption PR was prepared, no skill default changed, and no candidate was
activated. Reporting PRs #130 and #132 remain draft and unmerged.
**One next action:** proceed to dependency modernization under issue #95 with
this clarification deferred. Any future return to transfer testing requires a
separate decision, qualification and explicit paid authorization; this allocation
and conditional sequence cannot be resumed.
