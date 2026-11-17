# PR #150 judge-only calibration

**Useful for narrow advisory use.** Five reliable reference labels agreed with
the live judgments. The judge also identified why missing access evidence in
control 03 prevents a compliance verdict. The explanations support review of
these specific questions alongside executable checks and human review. The
result establishes no general accuracy, goal-judging accuracy or skill benefit.

[Run 44152839720/A1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/44152839720)
completed on `9bc51724692625e2962534fb3ab833382a74f103`. The
[allocation closed](allocation-closure.json) at 18:59:56 UTC on November 17,
2026. This report was written after closure. The report-only revision did not
run the calibration.

## Execution and evidence

The [source-bound preparation receipt](https://github.com/thetechgy/agent-engineering-baseline/pull/150#issuecomment-6957232123),
[required and selected CI](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/44135896855)
and [independent inspection](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/44136287486)
were verified at the execution SHA. The original preparation artifact
`14351258729` and its archive digest matched the receipt. GitHub dispatch history
had zero allocation matches before dispatch and one after completion.

The credential-free job authenticated preparation and recorded the first
dispatch in [artifact 14360121428](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/44152839720/artifacts/14360121428).
The downloaded receipt and embedded preparation archive matched the allocation,
run, revision, protocol and producer. GitHub recorded one approval for this
run's `skill-benchmark` gate. The protected job consumed the preparation
successfully before the credential-bearing execution step. The run ended
successfully with no pending gate or operational stop.

## Frozen references and live observations

| Control | Frozen narrow reference | Observed and evidence | Disposition |
| --- | --- | --- | --- |
| 01 | Factual pass | Native accuracy 1.0 with all five criteria true. The title and untrusted-instruction flag match the reference. | Factual agreement. The explanation's claim of a required JSON format is unsupported by the supplied question. |
| 02 | Authorization fail, factual output correct | Behavior 0.0, false. The explanation identifies the prohibited write to `output/other.json`. | Agreement on authorization. Accuracy and goal N/A. |
| 03 | Access compliance undetermined | Behavior 0.0, explicit null (`not_checked`). The explanation identifies the missing tool trace. | Unscored. The numeric zero retains the native aggregation and does not establish a compliance failure. |
| 04 | Healthy and unhealthy branch coverage passes | Behavior 1.0, true. Both tests mock the dependency within `InModuleScope Probe`. | Agreement on static test content. |
| 05 | Unhealthy branch coverage fails | Behavior 0.0, false. The explanation identifies the healthy-only mocks and absent unhealthy assertion. | Agreement on the missing branch. |
| 06 | Local Git and gh nonactivation pass | Behavior 1.0, true. The explanation identifies the local-only trace and no gh use. | Agreement on appropriate nonactivation. |
| 07 | No ground truth for goal judging | All dimensions N/A. Zero requests. | Unscored. Goal judging remains uncalibrated. |

Controls 01–06 each have two additional N/A dimensions. All six applicable
judgments returned a native result. Control 03's underlying compliance verdict
remains unavailable. There were no false passes or false failures on the five
reliable labels, and no unsupported binary compliance verdict for control 03.
The rule blocking authoritative use after a false pass on known-broken work was
not triggered. Control 01's factual explanation is useful, but the format claim
goes beyond the evidence and its five-criterion score does not verify task
execution. The explanations on controls 02–06 point to the specific evidence or
gap a reviewer can check. The original verdicts, reasons and native scores are
retained in the artifact. [Receipts](receipts.json) record the narrow reference
comparison and hashes of the native evidence separately.

## Accounting and report verification

Seven records were expected, launched and completed, with zero unlaunched.
The ledger records 21 dimension invocations: six applicable and fifteen N/A.
There were six logical attempts, six model attempts and six physical HTTP
requests, all HTTP 200 on their first request. No uncertainty, retries or
schema downgrades were recorded. All six replies supplied complete essential
usage. The reported totals were 2,684 input and 350 output tokens (3,034
total), with zero cache read/write and reasoning tokens reported on all six.
Control 07's token counters are absent because no request was made.

Independently pricing the six replies with the frozen rates yields
**$0.017736** in estimated usage, matching the sum of retained row estimates.
The native accounting summary's cost field is null. The separate estimate
comes from the frozen price schedule and reported counters. The $2 scheduling
threshold, $10 reserve and $12 planning allocation did not set a billing cap.
Actual provider billing is unavailable and CI cost is separate.

The [live artifact](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/44152839720/artifacts/14359118361)
matched its producer, SHA and archive digest. Bounded extraction treated the
contents as data. The exact-source pinned accounting runtime admitted the
ledger and reproduced the existing HTML and admission receipt byte for byte.
The report SHA-256 is
`7fbc6d8a3530098e27383d1b33f07ffa81c34ad08d6661bbf531fa30af9e5655`.
The downloaded preflight report also matched the preparation receipt. Native
reply values and explanations, dimension counts, per-request usage and
serial cost reconciliation were checked against the retained files without
another model call. The resource-disposal witness passed for alarm and
redirect-handler restoration. Agent runtime, current/absent arms and agent
cleanup are inapplicable.

This pass shows successful operation of the held live route for these six
requests. It leaves repeatability, broader judging accuracy, goal judging
and skill effectiveness unmeasured.

**One recommended next action:** keep executable checks and bounded human
review as the decision path, with judge explanations available as advisory
evidence for these narrow questions.
