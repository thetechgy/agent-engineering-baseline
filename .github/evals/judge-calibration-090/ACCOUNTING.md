# Standard judge request and usage accounting

This is an opt-in accounting correction based on verified main
`319240b46952f5c0596a13b56de4f156f30b1bb6` (PR #148). It does not change judge
prompts, scoring, model selection, strict request limits, fallback policy or the
seven frozen references. All actual model judgments remain **UNRUN**. No provider
credentials, inference, agent attempts, paid dispatch, protected approval, merge,
production adoption, history write or Pages change is authorized.

## Upstream relationship and selected correction

Checked on 2026-11-17 UTC: [0.9.0 remains the latest release](https://github.com/NVIDIA/SkillEvaluator/releases/tag/v0.9.0).
The released [`_call_openai_compatible`](https://github.com/NVIDIA/SkillEvaluator/blob/b78d14618a694dec84bc9601468f8f711df5cab3/src/skillevaluator/tier3/harbor/templates/eval.py)
and the current main implementation return judge content without retaining response
usage. `_budget_usage` counts logical judge attempts. There is no supported
transport-observation callback in this route. The related merged but unreleased
[reservation change #595](https://github.com/NVIDIA/SkillEvaluator/pull/595) and
[cost-provenance change #596](https://github.com/NVIDIA/SkillEvaluator/pull/596)
concern agent inference; #596 explicitly excludes judge inference. Neither closes
this accounting gap. No released upgrade was identified that avoids the patch.

The existing versioned mechanism now has explicit successors:

- Producer: `skillevaluator-0.9.0-accounting-v1`, selected only by
  `setup-skillevaluator.sh candidate-accounting`.
- Evidence: `behavioral-090-accounting-v1` and `aeb-judge-accounting-v1`.
- Patch: `skillevaluator-v0.9.0-accounting-v1.patch`, applied to the same released
  source with the same lock, Python 3.14.10, Harbor 0.25.0 and backend 1.1.0.

`offline-v3`, its patch/profile and original PR #148 receipts remain unchanged.
Production selectors and historical runtime owners remain unchanged. Thirty-six
source-only successors preserve all 803 prior custom profiles and frozen task,
grader, skill, CLI/model and policy values. They identify changed shared reporting
source; they do not reopen an experiment or allocation.

## Observation and retention contract

The OpenAI adapter maps response usage before content parsing, refusal or schema
validation. Shared code owns bounded identities, validation, completeness,
aggregation and the scheduling check. Task definitions retain their own prompts,
references and grading. No judge or scoring implementation is copied.

Each verifier session records logical judgments, logical format attempts and
model selections separately. Each transport invocation receives one ordinal under
its judgment/model attempt, persisted before I/O. Retries and schema fallback
therefore create additional transport records. A strict request-limit rejection
before transport creates no invocation record. The existing logical `judge_calls`
field retains its historical meaning; physical counts use `http_attempts` and
`judge_transport_attempts`.

A record distinguishes initiated transport, HTTP response and uncertain completion.
Initiation is not proof of provider receipt or billing. Response headers followed
by an interrupted body remain incomplete. A timeout or interrupt can leave provider
processing and charges uncertain. Session closure, observed-trial coverage,
per-counter coverage and pending records remain explicit.

OpenAI mappings retain input, output and reported total counts, cached input,
cache-write input, reasoning output, audio and prediction subsets supported by the
pinned SDK. Subsets are never added to parent totals. Missing fields remain null.
Malformed or inconsistent usage retains bounded valid fields per response but does
not contribute contradictory values to compatible token subtotals. Response usage
is independent of whether the judge result is valid, refused or unavailable.
Costs remain null without separately identified pricing. Counts and token limits
are not billable-usage estimates or invoice reconciliation.

The ledger contains no headers, credentials, URLs, prompts or raw response bodies.
Its `counters` container uses versioned token accounting with short counter
names, avoiding credential-sensitive token key names;
the redactor is unchanged. Native collection copies the sidecar through the existing
bounded secure/redacted artifact path. Admission binds it to the trial's captured
reference and versioned producer. Public projection and the consolidated renderer
carry the same observations and recomputed totals. Invalid/absent accounting remains
visible without changing valid task judgments. Duplicate sessions, trial identities,
transport ordinals or consolidated totals reject; repeated budget collection stops
without adding usage a second time.

The existing budget controller reads the successor's physical count and stops
subsequent admission on unknown accounting or physical-count exhaustion. It does
not mix judge tokens with agent tokens/costs. This preserves the existing admission
checkpoint: units already admitted, including paired arms or concurrent work, may
finish. It is not an in-flight billing ceiling. A future judge-only calibration must
be serial and check accounting after each control. Uninstrumented provider/RAGAS
routes cannot establish complete accounting.

Error-response usage requires reading the error body before retry interpretation.
The schema-capability reader now reuses the existing cached-body helper so both
readers see identical bytes. This adds observation/I/O work within the existing
judge deadline; the qualified fixtures preserve requests, results, policy and
strict caps. This evidence does not prove identical timing on a live provider.

## Credential-free qualification

After the existing opt-in setup, use a new external persistent evidence directory:

```sh
"$SKILL_ACCOUNTING_PYTHON" -B .github/scripts/qualify_standard_judges.py qualify --accounting --output "$EVIDENCE"
"$SKILL_ACCOUNTING_PYTHON" -B .github/scripts/qualify_standard_judges.py reproduce --output "$EVIDENCE"
```

The same non-forwarding responder independently observes every HTTP request.
Qualification runs in an empty home with an allowlisted environment, fixture
sentinel and socket/DNS denial outside its fixed loopback destination. No live
execution option is added. Existing native verifier, collector, recovery,
artifact redaction, admission and renderer entry points are exercised.

| Control | Original evidence | Successor evidence |
| --- | --- | --- |
| Ordinary full verifier | 3 HTTP / 3 logical; supplied usage lost | 3 HTTP / 3 logical; 57 input, 21 output retained |
| Schema fallback | 4 HTTP / 3 logical | 4 recorded HTTP / 3 logical; successful-response usage retained; error usage unknown |
| Transient retry | 6 HTTP / 3 logical | 6 recorded HTTP / 3 logical; successful-response usage retained; error usage unknown |
| Refusal or invalid content | Supplied usage lost | Usage retained before judge refusal/validation; result remains unavailable |
| Error response with usage | No retained usage | Usage retained independently of provider failure |
| Missing/malformed/inconsistent usage | No required accounting evidence | Explicit incomplete accounting; useful observations retained |
| Timeout/actual interrupt | Completion uncertain | Initiation/uncertainty retained, no fabricated zero |
| Partial judge failure | Other observations retained | Same independent task evidence and valid dimensions retained |
| Deleted/malformed sidecar | Missing accounting | Population remains visible; valid task judgment unchanged |
| Duplicate/replay | No physical ledger | Duplicate admission rejected; budget replay cannot inflate counts |
| Strict schema/retry exhaustion | Existing 2-request cap | Same 2 requests; no phantom debit for rejected third invocation |

PR #148's original 70-request entry was rerun under its unchanged owner. The new
entry adds malformed/inconsistent usage, error-usage and interrupt controls, for
74 loopback requests. This is fixture traffic, with zero agent attempts and zero
live model judgments. The admitted native population retains 56 HTTP invocations,
760 input and 280 output tokens (cached input 200 and reasoning output 120 are
subsets). It remains incomplete: two of 20 expected trial ledgers are deliberately
deleted by the existing runtime-failure control; 18 remain observed. Those missing
records and responses without usage do not become zero. Released upstream
policy/HTTP/contract/result tests also
passed 507 checks against the patched source in the retained upstream test host;
that supplementary host lacks the repository backend and is distinct from the
fully pinned owning qualification.

The original outcome controls are reused: independently established security
failure remains failed; valid scores survive partial judging failure; unsupported
and runtime-failed observations remain unavailable; Podman negative-case N/A stays
N/A; unknown behavior remains null. The frozen corpus and decision rules are
unchanged. The report must retain exact per-trial HTTP counts and nonzero supplied
usage after redaction, not merely in the transport helper. Hosted producer and
fresh-runner consumer receipts, terminal selected CI and independent artifact/HTML
verification are recorded on the focused draft PR.

## Remaining calibration blocker and maintenance

The current registered preparation/authorization mechanism requires a campaign
task with agent variants, a runtime, native controls and scheduler evidence.
`evaluation_campaign_protocol.protocol`, `prepare`, `admit` and
`authenticate_metadata` enforce that identity. The standard-judge qualifier has only
`qualify`/`reproduce`, fixture origin and no paid authority. Its artifact is not a
registered judge-only preparation and remains rejected by the live gate.

Accounting success does not create a judge-only authorization route. Producing an
executable calibration proposal through the existing mechanism requires a narrowly
scoped judge-only preparation/authorization adapter. Adding another campaign runner
or relabeling this fixture as preparation would violate this task's scope. No paid
proposal, allocation or approval command is created here. The seven references and
only the already declared neutral-label/reversed-order repeat remain the candidate
scope for later preparation; none is dispatched.

Added maintenance is the shared ledger module, a versioned patch/profile, focused
controls and their existing hosted handoff. The patch stages the exact shared
module bytes; the test checks equality. On a future upstream release with equivalent
judge accounting, qualify its transport, failure, collection and scheduling
semantics before selecting it. Then remove the opt-in local patch/setup route while
retaining old profiles, schema interpretation and receipts for replay. Do not
relabel historical logical counts or pool incompatible usage.

Only the exercised OpenAI/gpt-5.6-sol strict/replace route is qualified. Other
providers, RAGAS, live-provider compatibility, general judge accuracy, skill benefit,
actual charges and production adoption remain unproven.

Workflow security review: critical 0, high 0, medium 0, low 0. Existing read-only
triggers/permissions, SHA-pinned Actions, nonpersistent checkout credentials and
same-run data-only consumption remain. No secrets, privileged triggers or protected
execution are added.

**One next decision:** authorize a focused judge-only preparation/authorization
adapter to the existing mechanism after reviewing this accounting correction.
