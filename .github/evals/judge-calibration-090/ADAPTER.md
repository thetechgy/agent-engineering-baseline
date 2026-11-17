# Judge-only preparation and authorization

This opt-in registration extends the existing evaluation campaign. It consumes
the seven frozen records from PR #148 with PR #149's unchanged accounting owner.
It creates no agent submission, current/absent arm, agent runtime or agent cleanup
witness. Those fields are explicitly inapplicable. All live judgments remain
**UNRUN**. Preparation and credential-free qualification grant no paid authority.

## Contract and ownership

`judge-calibration-090-v1` is registered in the existing selection registry.
`judge_calibration_inputs.py` owns corpus projection and applicability;
`inputs.json` identifies each intended dimension and its reference input. The
released evaluator continues to own prompts, schemas, response interpretation,
scoring, retry policy, schema downgrade and provider usage mapping. Reference
labels, source selectors, ambiguity notes and acceptance rules stay outside the
provider prompt. The frozen corpus and [decision rules](README.md#frozen-references-and-review-rules)
are unchanged.

The existing scheduler drives one record at a time, with no record retries or
replacements. Each record evaluates three dimensions: six applicable logical
judgments and fifteen explicit N/A dimensions across one pass. The accounting
schema's `logical_judgments` still counts all 21 dimension invocations, including
N/A; the report displays applicable judgments separately. Six model selections
may initiate up to twelve physical HTTP requests: one initial request and one
transport retry **or** schema downgrade per applicable judgment. The strict
evaluator limit and the adapter's pre-transport guard both apply. No other
provider, RAGAS route, fallback model or speculative transport is registered.

Control-01's reference is checked against the frozen native gh-014 answer.
Control-07 supplies no ground truth: all its dimensions are N/A under the released
contract, with zero HTTP requests. The adapter does not invent a successful goal
reference to force a model call. Its unavailable reference label remains unscored;
this pass does not calibrate goal judging. The other five applicable judgments
use the frozen expected behaviors directly.

The guard checks known response accounting, retained completed evidence, source
identity, request/usage/cost limits and deadline before every additional HTTP
request, including retries. The scheduler checks eligibility before every record.
The per-judge wall limit remains 180 seconds, request timeout at most 90 seconds;
the serial campaign deadline is 1,260 seconds. Missing/inconsistent essential
usage, uncertain completion, infrastructure failure or failed retention stops
further scheduling. Completed judgments, explicit nulls and the primary failure
remain retained. A reference disagreement does not retry or stop the campaign.

The typed judge admission path recomputes accounting and cost estimates and checks
the exact schedule and retained judgments/diagnostics. It feeds the existing
consolidated renderer without creating agent TrialResults or behavioral/history
scores. Its empty skill inventory represents no skill experiment. The report
includes source/rubric identities, expected labels, population, per-dimension
results, accounting coverage, stops, evidence locations and resource disposal.
Historical report interpretation and all 839 earlier profiles are unchanged;
35 source-only campaign successors identify the changed shared implementation.

## Actual workflow entries

The existing `evaluation-campaign.yml` workflow accepts the new selection.
Preparation, authentication, inspection and consumption all use
`setup-campaign-authentication.sh`, which selects `candidate-accounting` and the
Python 3.14.10 accounting interpreter. The evaluator/patch/lock/backend pins are
unchanged. No Compose, APM deployment or CLI probe is needed by this campaign.

```sh
"$SKILL_AUTHENTICATION_PYTHON" -B .github/scripts/campaign_authentication_qualification.py \
  --campaign judge-calibration-090-v1 --output "$AUTHENTICATION_EVIDENCE"
"$SKILL_AUTHENTICATION_PYTHON" -B .github/scripts/evaluation_campaign_selection.py qualify \
  --campaign judge-calibration-090-v1 --output "$QUALIFICATION_EVIDENCE"
"$SKILL_AUTHENTICATION_PYTHON" -B .github/scripts/evaluation_campaign_selection.py prepare \
  --campaign judge-calibration-090-v1 --qualification "$QUALIFICATION_EVIDENCE" \
  --authentication-qualification "$AUTHENTICATION_EVIDENCE/authentication-qualification.json" \
  --output "$PREPARATION_EVIDENCE"
"$SKILL_AUTHENTICATION_PYTHON" -B .github/scripts/evaluation_campaign_selection.py check-preparation \
  --campaign judge-calibration-090-v1 --preparation "$PREPARATION_EVIDENCE/evidence" \
  --output "$FRESH_CONSUMPTION_EVIDENCE"
```

Use new persistent local evidence directories outside the checkout. The shared
GitHub API producer/repository/source/attempt/expiration checks and bounded,
digest-verified archive extraction are unchanged. Authentication also checks the
requested artifact ID against returned metadata. The judge receipt binds artifact
expiration through the protected gate and each later transport eligibility check.
Existing first-dispatch detection and exclusive local claim refuse duplicate,
replayed and closed allocations. Authentication receipts are published atomically.

The common authentication qualifier exercises the actual selection/authentication
CLI, including corpus/profile/source/protocol/artifact mismatch, expired evidence,
closed allocations, replay, missing owner/proof and failed receipt publication.
Preparation additionally authenticates **its actual retained output**, round-trips
the receipt artifact and consumes/reproduces its report. Fixture GitHub IO is
allowlisted and has no network fallback. Fixture receipts exist only in disposable
qualification storage and are deleted; they fail the real protected runtime gate.
They do not claim a real allocation. The fresh hosted consumer independently
reinstalls the same pinned owner and reproduces the report from retained data.

## Credential-free coverage and limitations

The non-forwarding loopback responder independently counts all requests from the
real evaluator. A fresh child has an empty home, an allowlisted environment, only
a fixture sentinel and socket/DNS denial outside that responder. Eighteen
scenarios cover seven-record completion, explicit N/A and unknown behavior,
schema downgrade, retry/exhaustion, refusal, malformed response, missing/malformed/
contradictory usage, actual timeout/interruption, request/usage/cost/deadline stops
and a real failed sidecar write. Observer counts must equal ledger counts; stopped
controls may not issue a next request or start a next record. Server/handler
threads and required-judge alarm state must return to baseline after completion.

Synthetic error responses with complete usage exercise allowed retry/downgrade.
Error responses without usage stop before retry. Fixture deadlines/backoff are
shortened and explicit in retained evidence; these controls do not establish
full-duration timing, live-provider compatibility, judge accuracy, billing or
skill effectiveness. The source-bound hosted artifact and final required/selected
CI receipt on the draft PR govern readiness, not this document alone.

Added maintenance is this one campaign registration, its input projection,
scheduler/transport-guard callbacks, typed report admission and focused integration
controls. There is no second runner, provider abstraction, dashboard or approval
system. The adapter uses pinned private evaluator entry points and must be
requalified when the owner changes. PR #149's local accounting patch retirement
requirements remain in force.

## Proposed bounds, not current authority

Any concrete proposal must bind the final source SHA, exact profile/model/request
identity, corpus/rubric digests, authenticated preparation artifact and expiration,
fresh unclaimed allocation and the exact UNRUN workflow command. It belongs in
the draft PR's final verification receipt after hosted qualification succeeds.
No paid dispatch or protected gate is approved by this implementation request.

The proposed single pass has seven records, six applicable logical judgments,
fifteen N/A dimensions and at most twelve physical HTTP requests. There are no
repetitions or replacement judgments. The separately declared neutral-label/order
experiment remains deferred and would require its own scientific reason and bounds.

[Official model pricing](https://developers.openai.com/api/docs/models/gpt-5.6-sol)
checked 2026-11-17 lists $4/M input, $0.40/M cached input and $20/M output tokens,
with cache writes at 1.25 times ordinary input ($5/M). Scheduling estimates use
reported cache writes when present; when absent, uncached input is conservatively
priced at the write rate. Missing cache detail stays missing in the usage ledger.
Overlapping cache-read/write subsets make the cost estimate unavailable and stop
scheduling. Other processing modes, account-specific charges and invoices are not
qualified by this estimate.
The $0.25 planning estimate assumes roughly 1,000 input and 1,500 output tokens
per applicable judgment, rounded up. It is not a measured forecast. Twelve
maximum-size 32,768-token outputs alone would estimate $7.86432, plus input.
The proposed $2 scheduling threshold, $10 reserve and $12 planning allocation
are not provider billing caps. Unknown error/timeout charges cannot be bounded
by missing usage. CI cost is separate. Cached tokens are subsets and reasoning
output is already in output; neither is added to its parent total.
The proposal expires 2026-11-20, before the currently advertised promotional
pricing window; pricing must be reverified if a later proposal is needed.

One false pass on known-broken work blocks authoritative use pending investigation
and separate requalification. Preserve false-positive/false-negative explanations,
unavailable and unsupported outcomes, independent executable failures and human
review. Useful evidence-specific explanations may support advisory use; unsupported
binary conclusions, repeated false passes or detached explanations support keeping
executable checks plus human review. Seven controls cannot establish general judge
accuracy or evidence that skills improve completed work.

Workflow security review: critical 0, high 0, medium 0, low 0. Existing read-only
permissions, SHA-pinned actions, nonpersistent checkout credentials, data-only
artifact consumption and the unchanged protected environment are preserved.

**One next action:** review [draft PR #150](https://github.com/thetechgy/agent-engineering-baseline/pull/150) and its final source-bound
qualification receipt before deciding on any separately proposed calibration.
