# Change-aware skill evaluation

The **Plan skill evaluations** workflow assesses evaluation demand after main
validation completes, every Tuesday at 10:37 UTC, and on manual dispatch from main.
Planning uses the pinned reporting dependencies without models, judges, provider
preflight, scanners, or Docker. Successful validation of the exact current main
revision is required before an automatic benchmark request.

Automatic dispatch ships **disabled** for both Podman and gh. This change does not
authorize a qualification run or paid inference. Every benchmark still requires
approval through the existing `skill-benchmark` environment.

## Selection and coverage

The planner fingerprints canonical authored sources, APM ownership and content
hashes, datasets, graders, fixtures, competing skills, and relevant runtime files.
It does not count generated copies separately. Lock timestamps and refresh comments
do not change source identity. Managed deployment hashes must agree with retained
bytes; intentionally unpublished upstream indexes and binaries remain outside the
repository's publication boundary.

Podman uses its ten-case authored suite and existing default grading. gh uses its
24-case overlay, verified upstream skill and competing `github-actions-hardening`
skill, and existing mandatory deterministic gate. Refreshed dependencies that no
longer match the reviewed overlay pins require qualification; the planner never
changes those pins. Dataset and grader changes affect their consuming suites.
Evaluation runbooks outside staged input trees do not create benchmark demand.

Pester remains a five-case diagnostic-only pilot. Its health is checked without
inference, and its paid confirmation runs remain explicit manual work. They cannot
produce standard history. Skills without supported datasets are reported as
coverage gaps. Repository-wide personal instruction changes are detected but are
not measured by the current isolated benchmark bundles.

A suite becomes due when its inputs differ from qualified evidence, evidence is
missing, or matching evidence is at least 30 days old. Comparison is against prior
measurements, so a later irrelevant merge does not erase an unevaluated change.
Failed validation, unavailable dependencies, unsupported runtime references, and
case counts above the reviewed ceilings block automatic requests.

## Qualification and activation

For each suite separately:

1. Review the exact main revision and its successful validation. Manually request
   an approved standard benchmark through **Benchmark skills**. This is paid work
   and requires separate authorization and environment approval.
2. Verify the native result, mandatory suite gates, standard history admission,
   retained evidence, runtime, elapsed duration, and available usage. Inspect
   missing usage and cost components explicitly. A Podman reference does not
   qualify gh or establish gh costs.
3. In a reviewed change to `orchestration.json`, set that suite's `reference` to
   `{"run_id": <number>, "attempt": <number>}` and set `enabled` to `true`.
   Keep the case ceiling at the reviewed scope. No new secret or service is needed.

The reference must be an authenticated successful main standard benchmark with
successful native evaluation and history publication, an admitted current-policy
ledger entry, and the current execution-runtime fingerprint. Historical source
inputs are inspected as Git data; historical code is never executed. Runtime
changes require a new reference. Source/dataset changes can create demand while
retaining a compatible runtime reference.

Set `enabled` back to `false` to stop new requests. Already approved/running work
is not cancelled by planning. The protected job rechecks current eligibility after
approval, so disabling a suite can also prevent a waiting automatic request from
entering inference. Existing manual dispatch remains available for reviewed work.

## Dispatch state and recovery

Actions is the authoritative operational record. The immutable
`skill-evaluation-plan-<run>-<attempt>` artifact contains the plan and at most two
dispatch intents: one per enabled standard suite. The dispatcher authenticates
its producer and archive digest before issuing a request. It uses the supported
`2022-11-28` dispatch API with `return_run_details: true` and retains returned run
IDs in `skill-evaluation-dispatch-<run>-<attempt>`. There is no POST retry.

The benchmark's run title includes the request identity. Later planning reconciles
intents against authenticated benchmark run metadata, including when the POST
succeeded but its response was lost. An intent is not evidence that execution
occurred. A timeout or absent correlation is **unresolved**, and blocks automatic
resubmission. Failed, rejected, cancelled, or interrupted requests also block
automatic retries of the same demand. Rerunning the dispatcher does not resend.
Planning failures before intent upload are recoverable when GitHub proves the
dependent dispatch job was skipped; that is not an uncertain POST.

Inspect the planner's `record.json`, the dispatcher outcome, and benchmark run
metadata to reconcile a request. If execution cannot be established, keep it
blocked. An operator may explicitly request a new manual benchmark after reviewing
the unresolved request and any outstanding runs; the new paid job requires its
own approval. A new qualified measurement advances the evidence anchor. Do not
delete run records or overwrite artifacts to clear a block.

Only a digest-checked stale context with matching run/request provenance and
GitHub step evidence that inference was skipped allows automatic replacement on
a newer revision. Required expired, deleted, malformed, or incompletely listed
records cause an unavailable-state failure. Artifacts retain the existing 30-day
retention; records are not a permanent transaction log. This mechanism provides
conservative duplicate suppression, not exactly-once execution.

The planner serializes through native Actions concurrency. Automatic requests are
limited to one outstanding request per suite and two benchmark runs total. The
benchmark queue preserves pending requests. Main benchmarks and publication are
never cancelled by this orchestration; Validate retains its existing PR-only
cancellation behavior.

## Approval context and reporting

The benchmark's unprotected `context` job publishes scope, source revision,
selection rationale, qualification reference, and cost limitations **before** the
protected job requests approval. Its record is
`skill-benchmark-context-<run>-<attempt>`. The protected job separately rechecks
eligibility immediately before inference and retains
`skill-benchmark-authorization-<run>-<attempt>` when available. The inference key
is still exposed only to the existing native evaluation step.

Main benchmarks reuse the authenticated successful Validate run for their exact
source revision, including its full regression suite. Reviewed feature revisions
run the equivalent inference-free suite in the unprotected context job. The
protected job retains strict dataset validation, runtime checks, and its existing
five-minute preparation limit; it does not repeat the full suite there. Hosted
CI-contract validation took 15 minutes 15 seconds during implementation, so
repeating it inside that five-minute step would exhaust the preparation budget.

An ineligible or stale request finishes with an unsuccessful workflow and an
explicit nonexecution disposition. This prevents the existing successful-producer
publisher from treating a skipped benchmark as a completed evaluation. Read its
scope/authorization record to distinguish nonexecution from infrastructure failure.

`skill-benchmark-operation-<run>-<attempt>` retains a minimal receipt: scope,
execution disposition, measured inference-step duration when available, and
allowlisted native agent usage subtotals. Repeated identical trial records are
counted once; conflicting records are excluded. Cache tokens are included in input
tokens. Missing fields are unknown. Harbor cost values are labelled native
estimates; judge/preflight usage and actual billed totals remain unknown when not
supplied. Task-trial and time limits bound execution scope, not a dollar price.
Runner loss or approval rejection can prevent a receipt; use independently
authenticated Actions run/job status and do not infer zero cost from absence.

Operational receipts cannot establish successful evaluation, history admission,
or publication. They are separate from qualified evidence. The orchestration
only reads a verified `gh-pages` snapshot. Existing successful-producer admission,
history writers, and canonical Pages publishing remain authoritative and unchanged.
Richer operational Pages reporting and retention analytics are deferred.

History snapshots are read after dependency setup, close to their use. If the
canonical branch moves before verification, planning fails closed; rerun the
inference-free planner to obtain a fresh snapshot. No publication lock or extra
history writer is introduced.

## Verification and remaining qualification

Regression tests exercise the production CLI and dispatch adapter over disposable
repositories, synthetic events, GitHub API responses, immutable artifact archives,
and native usage records. They perform no model inference or real dispatch.

Before activation, hosted qualification must establish native run-ID correlation,
preapproval context ordering, approval waiting/rejection, postapproval stale
skipping, operational artifact recovery, and unchanged history/publication behavior.
The separately approved current-policy Podman and gh reference runs remain required.

## Reporting retention

The Pages publisher protects registered qualification references from compact
snapshot pruning. Its 90-day/30-observation budgets apply per skill and evidence
class. Native ledgers and Actions operational records remain separate; reporting
retention does not change qualification, freshness, dispatch duplicate suppression,
or operational-record expiry behavior. See `REPORT-EVIDENCE.md` for summary recovery
and the distinction between retained measurements and original diagnostic evidence.
