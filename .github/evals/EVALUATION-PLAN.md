# Evaluation checkpoint

## SkillEvaluator 0.3.0 retirement in progress

The migration starts from `58cb9698543c546173501887254dc7989d2db396`.
Production benchmarks still use the reviewed 0.3.0 runtime. Keep the
original scorer, locks and validator snapshots available at their producing
revisions. [Issue #95](https://github.com/thetechgy/agent-engineering-baseline/issues/95)

- The startup-only checkpoint `dc997a64a5bc54507786f49c1734e9c1887997b7`
  exercised released SkillEvaluator 1.0.1 staging and Harbor 0.25.0 dispatch
  through a separately pinned backend. Both gh-007 fixture arms reached
  readiness, retained the broker identity on repeat start, denied agent
  access to protected state and completed teardown.
  [Hosted startup](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45325909769)
- Local candidate setup uses the released lock and a separate benchmark
  request patch. The released defaults selected Codex 0.161.0 and sent Medium
  verifier reasoning. The port dispatches Codex 0.171.0 and High through the
  released hooks and tests the verifier with its reasoning parameter omitted.
  Both arms of the Podman, gh and Pester datasets staged locally. Native agent
  execution, verifier isolation, recovery and collection still require Docker
  qualification on the candidate revision.
- The candidate accuracy schema derives 0.8 from four of five satisfied
  criteria. It rejects the historical scalar fixture. The score comparison
  found 56 differences across 73 fixed vectors. Future measured records need
  a separate producer and metric identity. The retained scores and canonical
  Podman projection are digest-checked comparison inputs.
- The private review candidate retains Python 3.13.18, OpenAI 2.54.0,
  Pydantic 2.14.3 and certifi 2026.10.23. It uses the existing explicit inference
  authorization and keeps the `not_quality_qualified` status. The candidate
  validated the original bytes across ten attachment profiles and rejected
  tampered source, registry, context, report and path inputs. Its replay
  identity is separate from the report's original runtime.
- The maintained 0.8.0 and 0.9.0 offline qualification commands replayed the
  canonical Podman projection without a historical interpreter. Each retained
  its own evaluator, backend, scoring and collector. Native qualification and
  existing rollback selectors still need their own checks.

The credential-free hosted checkpoint at `aa2599f` used
`current-evaluator.yml` with `benchmark-101-fixtures=true`,
`startup-only=false` and `candidate-next=false`. Both gh and Pester commands
completed both arms. The gh report reader rejected redacted staging digests.
The Pester grader returned an infrastructure error for a known-good case.
Pester resource cleanup passed.
[Hosted fixtures](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45360054011)

Automatic Validate's legacy Pester control passed both arms of the same
known-good case. The CI contracts job rejected the stale inventory count for
the added uv setup step. All 51 freshness tests passed with that count updated.
[Validate](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45360027374)

The gh fixture applies its report-reader compatibility patch to a clean
export of the dispatched source. The matching synthetic collection validated
all 48 observations, including unresolved outcomes and their partial
aggregates. Shared campaign source files retain their producing digests.
Pester uses the existing literal loopback-only verifier Compose setting after
the release validates its authored task. Local testing verified that Harbor
selects this setting in both arms and the grader retains its isolation checks.
The hosted Pester failure did not retain the verifier's prerequisite code.
The next fixture run records that code from an allowlist if the failure recurs.

The follow-up at `1b32b5b` passed both credential-free Docker jobs.
The gh receipt covers 48 outcomes and clean teardown. The Pester receipt
covers 52 outcomes and clean teardown. All 52 classifications matched the
authenticated 0.3.0 report by case and arm, including invalid, timeout,
unsupported and infrastructure-error controls.
[Follow-up fixture run](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45409081795)

The older adoption qualifier can replay the authenticated Pester report
without starting the original interpreter. Local staging also covers the
candidate Pester package-preparation entry point and both arms of the
candidate Codex loopback probe. The probe keeps the packaged Codex
executable out of the broker's bounded task manifest, checks the pinned
executables in the image and requires a loopback-only container at launch.
The package build, the real Codex request and interruption path, Podman
benchmark execution and result publication still require native qualification.
The Codex-only run at `c1d0f61` stopped on the first `gh-001` arm.
Harbor reported `NonZeroAgentExitCodeError`, followed by a missing
container receipt. A local credential-free reproduction with Codex 0.171.0
showed that the previous path resolves only in a global npm installation.
The local install puts the package at the hoisted path. The fixture now
uses that path, verifies the same executable and helper hashes, and writes
the last startup stage to a bounded receipt.
[Codex-only run](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45419255253)

The retry at `a558b19` passed package, agent identity, broker and
loopback setup. Harbor entered verification in the first `gh-001` arm and
reported `RewardFileNotFoundError`. It did not retain verifier output.
Both completed controls and the interrupted control from earlier
credential-free Codex execution convert to ATIF using Harbor 0.25.0.
The candidate grader reads a converted trajectory and emits an unmeasured
reward for the local missing-broker control. The hosted cause remains open.
[Codex-only retry](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45421531862)

The bounded receipt at `c8e26bc` found the Codex event log and no
`trajectory.json`. The verifier failed opening that file. A local run
through Harbor, using a verified Docker client and rootless Podman API,
reproduced the failure after a completed Codex turn. Harbor silently
discarded a session-copy failure when its whole-directory replacement
encountered SkillEvaluator's protected `sessions/skills` projection.
The 1.3.1 backend places native sessions in a separate directory and keeps
the same Harbor ATIF converter and protected skills. It has its own wheel,
source and producer identity. Both fixed local arms wrote ATIF, preserved
the protected skill projection and matched the expected authorization
verdict and synthetic usage. The interruption control observes command
start inside the container, since Harbor can defer copying logs until
exit. The fixed local control preserved the failed exit and unfinished
trajectory with final usage absent. The earlier producer and reports
retain their original identities.
[Hosted diagnostic](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45427100340)

The exact-head Validate run separately failed its 0.3.0 Codex fixture
because the candidate's hoisted npm path was applied to the legacy global
installation. The fixture now selects the correct path for each runtime.
[Validate](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45427050223)

The full local loopback fixture passed on both the 1.0.1 candidate and
the still-active 0.3.0 owner, including paired authorization, interrupted
usage, collection and reporting. The rootless Podman API reported a
sidecar removal error on some candidate trials.

The Codex-only hosted run passed at `3011034`. Its digest-verified receipt
records authorization scores of 1 and 0 in the two arms, two fixture
requests and the expected synthetic usage per completed arm, and an
interrupted exit with final usage absent. All main-container teardown
checks passed. The job log had no Compose teardown errors.
[Hosted Codex fixture](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45446801863)
[Automatic Validate](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45446766350)

The isolated Podman fixture completed one trial per arm for case 5
with Codex 0.171.0 under Harbor 0.25.0. The bare released stage did not
select a non-root user. The fixture declares UID 1000 in the task and
provides the user in the image. Each completed arm made two Codex
requests at High and three standard-verifier requests with reasoning
omitted through non-forwarding responders. The verifier used its
canonical OpenAI request builder and returned 0.8 accuracy in each arm.
Both main containers were removed. The local rootless Podman API failed
to remove the egress sidecars automatically, and they were removed
separately. Qualify automatic teardown on hosted Docker before adoption.

The 1.0.1 publication qualifier uses its own offline profile and applies
the reader patch to a clean export. The release distinguishes unresolved
cases from failed cases and keeps failed judge observations in a separate
diagnostic record. The reader verifies both against the retained trial.
The local standard and confirmation fixtures retained 20 and 60 attempts
in distinct series. The cancellation fixture retained 19 of 20. The
publication route rejected mismatched mode, producer and trial identities,
and the canonical history writer rejected all four fixture reports.
The hosted Podman and publication checkpoint passed on `fb1e044` with
`benchmark-101-podman=true`. The authenticated archive retained both
startup receipts, one scored trial per arm and the four publication
controls. The job logged no Compose teardown errors. Production
retirement requires the separately authorized provider checkpoint.
[Hosted Podman and publication](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45459299280)
[Automatic Validate](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45459156356)

The local private-review checkpoint registers `review-101-v1` using a
fixed source snapshot of `c1d0f61`. The documented operator entry point
and independent attachment validator use the same producer source.
Synthetic Podman, gh and Pester contexts passed prepare, validate and
attachment admission. The tests rejected caller-supplied tooling,
changed snapshot bytes and output inside the checkout. The 1.0.1
review interpreter also replayed the ten historical profiles with
their original scoring and validator provenance. Archived producer
request tests covered the identical token-count and generation context,
provider-default reasoning, deadline and failure handling without
inference. New results retain `not_quality_qualified`.

Automatic Validate and feature-branch preapproval run the private-review
suites in the separately pinned 1.0.1 review environment. The contracts
runner retains the other discovered tests and the four dispatch controls
for the legacy validator while it remains supported. Only the review test
setup installs the hash-locked schema test dependencies. Protected
evaluation and the production benchmark runtime remain gated separately.

Pester package preparation in Validate now selects the exact 1.0.1
candidate and its installed source, lock and backend. The former
`--runtime retained` execution is available at the original Git revision.
The 0.7.2 and 0.9.0 preparation modes keep their own pins. The later
native Pester and Codex steps still qualify the current production owner.
The local release route built the image and verified the pinned package
versions. Rootless Podman failed automatic sidecar removal, and separate
cleanup removed the task-owned resources. Hosted Docker teardown remains
a gate for the replacement path.

The next Podman fixture selects case 1 with one trial in each arm.
Both arms use the released task projector and the explicit unprivileged
agent. Its scope receipt binds the Git revision, Podman dataset, candidate
lock, adapter and installer separately from the historical runtime identity.
Local Podman trials used the digest-verified Codex 0.171.0 standalone
archive and Harbor's preinstalled executable path. Both arms completed
with two loopback Codex requests and three loopback verifier requests.

The protected compatibility smoke on `e95d525` completed the with-skill
arm for Podman case 1. Codex 0.171.0 and the three released verifier
observations passed the runtime admission checks. The recorded agent usage
was 248,725 input tokens and 5,820 output tokens, including 217,174 cached
input tokens. The combined total exceeded the approved 120,000-token
gate, so the without-skill arm did not start. Teardown completed and
the diagnostic was excluded from canonical history. Provider billing and
judge token usage were unavailable in the receipt.
[Protected compatibility smoke](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45510362606)

The follow-up selector accepts one without-skill trial of the same case
through the existing protected diagnostic job. The fixture verified the
selected launcher, release collector and skipped comparison. The paired
control still stops at the original token gate. A live follow-up requires
separate approval at its reviewed revision.

| Maintained path | Retirement gate |
| --- | --- |
| `benchmark-skills.yml`, local `gh_evaluations.py benchmark`, standard and confirmation publication | Qualify the real executable, verifier, recovery and collector under the candidate, then bind its runtime files to the preapproval fingerprint and its publications to a new series. |
| `setup-skillevaluator.sh` benchmark, reporting and quality, `validate.yml`, feature-branch preapproval | Move each remaining full-suite consumer to its owning runtime, then reject installation and invocation of 0.3.0 through maintained dispatch. |
| `current-evaluator.yml`, manual candidate qualifiers, Pester and gh validation | Use authenticated offline receipts for historical comparisons and qualify active native image recipes through their supported owners. |
| Private review generation and saved attachments | Adopt the pinned review setup after registering its future validator identity and replacing test-time historical generation. |
| Pages, public reports, static quality, historical projections | Verify the mixed history, sealed bundles, expiry and redaction via the 1.0.1 data host. Recheck the reporting patches on a clean archive of the final commit. |

The protected environment has a reviewer gate and no deployment branch
restriction. The current confirmation input schedules three attempts per
arm for each selected case. For the smallest maintained suite, that is 30
task trials before preflight or judge calls.

The temporary `candidate-smoke` mode accepts only an initial manual
Podman dispatch on the retirement branch, with `expected_revision` set
to the exact reviewed SHA. The preapproval record and the protected
job bind the same fingerprint. The protected job prepares the two
checksummed tasks without credentials and verifies the same-run artifact
and branch head before the provider step. It retains a bounded diagnostic
receipt outside canonical history.

The scope is Podman case 1, one Codex 0.171.0 trial in each arm using
`gpt-6.2-sol` at High. The standard verifier uses the same model with
reasoning omitted and transport retries disabled. The shared inference
deadline is 15 minutes, with a five-minute agent phase per arm. The
second arm requires observed first-arm agent usage at or below 120,000
input and output tokens combined. The provider host is restricted to
`api.openai.com`. Native agent requests and billed cost can vary with
tool use and provider transport. At Standard short-context rates, a
planning estimate of 400,000 input and 240,000 output tokens costs about
$3.20. Authorize the exact live scope separately after the credential-free
qualification gates. [OpenAI API pricing](https://developers.openai.com/api/docs/pricing)

## Model selection for new executions

| Operator or workflow | Model dispatch and evidence |
| --- | --- |
| Manual benchmark, scheduled planner and local `gh_evaluations.py benchmark` | The benchmark policy selects `gpt-6.2-sol` for Codex 0.171.0, runtime preflight, provider and standard verifier. The agent requests High. The 0.3.0 verifier sends Chat Completions with its reasoning parameter omitted. The three judge aliases and the CLI argument use the same selection. |
| Single-case observation | The active 0.171.0 selector and the 0.169.1 rollback both send `gpt-6.2-sol` / High. |
| New scored campaigns | Select the Codex 0.171.0 scored profile with `gpt-6.2-sol` / High. The first comparison is `pester-return-development-current-v1-1710-sol62`, with SkillEvaluator 0.8.0 and Harbor 0.24.0. |
| Pilot, cohort and earlier Boolean and Pester comparisons | Their versioned `-sol62` selectors use Codex 0.167.0 with `gpt-6.2-sol` / High. |
| gh runtime and permission campaigns | The `-sol62` successors use their qualified 0.155.1 CLI and send `gpt-6.2-sol` / High. Their deterministic verifiers make no model calls. |
| Judge calibration and current-evaluator judge qualification | The 0.9.0 templates send `gpt-6.2-sol` with their configured Medium reasoning. Retry and schema fallback use the same model. |
| Private skill review | `skill_review.py review` selects `gpt-6.2-sol` for the SDK token count and generation. Explicit authorization is required. Reasoning uses the provider default. |
| GitHub-hosted Copilot PR review, interactive external reviewers | The host or operator selects the model. This repository supplies instructions and can validate saved review evidence. It cannot set or observe these external requests. |

The 0.167.0 pilot and campaign images include the released model record for `gpt-6.2-sol`.
Their built-in catalog otherwise omits the native file-edit tool. The image build checks the
single-record catalog's SHA-256. Qualification exercises a real command and file edit and checks
both outgoing requests against the controlled provider. The source record supports CLI 0.166.0
and later. [Tagged Codex model catalog](https://github.com/openai/codex/blob/ccf9be8cc458bd6b8336fe84d68d8893f2691a5e/codex-rs/models-manager/models.json)

The production verifier first tries RAGAS for goal accuracy on the canonical OpenAI endpoint. With
the released 0.4.4 dependency, its `SingleTurnSample` rejects the list of messages before any SDK
request. The verifier's existing custom goal judge then sends the selected model. The 0.3.0 accuracy
and behavior judges use the same endpoint.

New work needs fresh authorization for its revision, model and protocol. Existing allocation
ceilings and expiration dates still apply. Scheduled paid suites remain disabled. The `-sol62`
protocol files record new estimates and the source of their rates. Standard short-context rates per
million tokens are $2 input, $0.10 cache reads and $10 output. Cache writes are $2.50 for 30 minutes
and $5 for 12 hours. Above 272,000 input tokens the input and cache rates double and output costs
1.5 times the short-context rate. Older CLIs expose cumulative counts and omit cache-write detail,
so their scheduling estimate prices unclassified input conservatively. [Official model
pricing](https://developers.openai.com/api/docs/models/gpt-6.2-sol)

The manual native-deadline observation defaults to the current pilot model. The explicit historical
CLI comparisons check out their original commits and send only to their non-forwarding loopback
responder. Their saved model names are part of reproduction.

Replay an earlier run at its producing revision using its recorded model, prices, source identity
and validator. Current source-v38 records retain the existing grader and fixture identities. Each
versioned definition binds its new runtime, model and budget. For the previous production model
policy with CLI 0.171.0, use revision `b458913` for offline reproduction. Restarting paid work on a
previous model requires separate approval.

## Codex 0.171.0 observation qualification for issue #95

Run the independent release probe with the pinned `candidate-next` interpreter
and a new output directory outside the checkout.

```sh
"$SKILL_NEXT_PYTHON" -B .github/scripts/qualify_codex_1710.py "$RUNNER_TEMP/codex-1710"
```

The probe verifies the release archive, CLI version, executable and helper
hashes. It uses the existing non-forwarding provider and observer settings
(`gpt-6.2-sol` at High). It checks real command and patch events through the
existing reader, cumulative and cache-write counts, an interrupted turn with
unknown final usage, and cleanup. It changes directories in a running app
server and checks that files can be written in the new workspace while Git
metadata and the previous workspace stay protected.
[0.170.0 permission updates](https://github.com/openai/codex/releases/tag/rust-v0.170.0)
· [0.171.0 working-directory fix](https://github.com/openai/codex/pull/61195).

The ordinary `case-observation` selection resolves to the 0.171.0 definition. Select `case-observation-1691` to
restore 0.169.1 with the same model and effort. Each definition binds its own preparation and protocol.
Historical 0.155.1 and 0.167.0 campaign records retain their original identities.
[Scored campaign setup and qualification](campaigns/README.md#scored-campaigns-on-codex-cli-01710)
covers the 0.171.0 successor.

The six-slot Boolean effectiveness protocol, the gh-014 0.169.1 probe, and the retained Boolean slot replay
all bind shared source bytes. Replay an original record from its producing revision and use the same CLI for
raw rollouts. The prior default source is `fb9c8a0`. Source-v37 records the CLI-only promotion and source-v38
records the shared model change. Source-v39 adds the scored runtime and binds the changed
shared adapter and workflow for future runs. The fixture and grader contracts carry forward.
The retained replay also binds the adapter digest for its revision.
[Upstream rollout replay contract](https://github.com/openai/codex/pull/61199).

The production benchmark uses the SkillEvaluator 0.3.0 Docker dispatch patch. The trusted gh initializer reads the
same Codex pin as the report policy. Both select 0.171.0. The benchmark agent uses `gpt-6.2-sol` at High. Each Docker
trial runs with the execution user’s private Codex home. Direct native tools keep each command and file edit
attributable to its own result in the existing verifier.
Run the credential-free benchmark integration with its production setup and verified Compose:

```sh
"$SKILL_EVALUATOR_PYTHON" -B .github/scripts/qualify_benchmark_codex.py "$RUNNER_TEMP/benchmark-codex"
```

The qualifier checks the standalone archive, then runs the production npm package and launcher in network-isolated
task containers. It compares the npm executable and its three shipped helpers to the archive. The npm package omits
`codex-exec-server`. The real gh broker, Harbor agent, verifier and collector exercise that installed layout.
Its loopback responses supply fixture usage. For the 0.155.1 rollback, select the benchmark setup, patch and report policy
together from `fb9c8a0`. Historical reporting and comparison
must use the policy and source revision that produced the records.

## Codex 0.169.1 proposed profile for issue #95

The opt-in `gh-014` credential-free qualification uses Codex CLI 0.169.1 /
`gpt-6.2-sol` / high with SkillEvaluator 0.9.0 / Harbor 0.25.0. It retains the
`gh-task-permission-v2` grader, task and matched APM content. The draft PR's
exact-source hosted receipt governs qualification. The held 0.155.1 /
`gpt-5.6-sol` / high selection and replay profiles remain available.
[Qualification and rollback](../../docs/evaluations/codex-1691/QUALIFICATION.md).

**Codex next action** — Review the exact-source fixture receipt before deciding
whether to authorize one bounded live Codex compatibility check.

## SkillEvaluator 0.7.2 qualifier retirement

The 0.7.2 manual migration workflow and its dedicated setup mode are retired.
Use the maintained `current-evaluator.yml` for versioned score policy,
Pester and gh qualification. Backend 1.0.0 remains part of the frozen 0.8.0
setup. The [ownership decision](EVALUATOR-090-95.md#072-qualifier-retirement)
and [historical command](EVALUATOR-CANDIDATE-95.md#reproduction) record how to
read saved diagnostics and reproduce the old qualifier.

## Pester clarification transfer decision

**The 0.171.0 runtime recheck closed this case.** Current and matched no skill
each passed 3/3 on GPT-6.2 Sol at High. All six submissions passed the reference
and caught all five defects, including `integer-result`. The verified allocation
closed at $0.3922755 in estimated usage. Keep the
current guidance for this case.
[0.171.0 execution receipt](../../docs/evaluations/pester-return-contract-development/stage-1-1710-sol62/EXECUTION.md).

**Stage 1 closed for this case on GPT-6.2 Sol.** The current skill and its
matched no-skill arm each passed 3/3 on Codex CLI 0.167.0 at High. Every
submission passed the reference and caught all five defects, including
`integer-result`. The decision rule closes the comparison at Stage 1 and the
current guidance remains in place. The tie leaves a skill effect unmeasured.
All six slots have verified usage, reports and cleanup. The allocation is closed
with $0.6721177 in estimated usage.
[Stage 1 receipt](../../docs/evaluations/pester-return-contract-development/stage-1-sol62/EXECUTION.md).

**DEFER** the exact 22-line `powershell-pester-6` clarification. Both v6 pairs
completed at `2b58a4652b576247d91ba01c6ce7a743ff703331`. Current and its own absent arm
each had 3/3 primary successes. Candidate and its own absent arm also had 3/3
each. All reference checks and five defect checks passed. The indirect
comparison leaves a shared numeric restriction. Every submission used the same
fixed numeric type list for `Quantity`, which excludes permitted numeric
implementations such as `System.Int128`. The Int32/Int64 reference passed in
all 12 slots. The shared restriction leaves the adoption criterion unmet and
provides no evidence of a candidate-specific regression.
[Execution receipt](../../docs/evaluations/pester-transfer-decision/execution-v6/EXECUTION.md),
[current run](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/44202925702),
[candidate run](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/44205331725).

The mandatory current checkpoint passed before candidate dispatch. Estimates
totaled $0.6775063 across 12 complete usage records. The live reports and native
projections independently reproduced, and all cleanup and resource-return
checks passed. Both allocations are closed, with zero unlaunched slots, retries,
replacements or model judges. The earlier stopped transfer, development results
and retrospective replay retain their original identities. The recommendation
leaves the established skill in production.

A fresh Pester confirmation will stop on the first unsupported grade. Preserve
prior measured attempts and treat the comparison as incomplete. Qualify the
chosen case and verifier before proposing that run.
[Fresh confirmation policy](campaigns/README.md#unsupported-grades-in-fresh-pester-confirmation).

The [private decision report](REPORT-EVIDENCE.md#review-the-retained-codex-decisions)
also shows the five-defect development case. Current and its matched absent arm
each scored 0/3. The revision scored 3/3 against its matched absent arm’s 0/3.
Every failure passed the reference and missed only `integer-result`. An earlier
candidate launch hit the 600-second deadline and is excluded from the counts.
Both comparisons used GPT-6.1 Sol. The
[pre-declared GPT-6.2 Sol decision rule](../../docs/evaluations/pester-return-contract-development/DECISION-RULE.md)
records what new evidence would change the decision and preserves the owner’s
choice after stage 3.

## Completed PR #150 judge-only calibration, retained as history

**Useful for narrow advisory use.** The single authorized
[run 44152839720/A1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/44152839720)
completed on `9bc51724692625e2962534fb3ab833382a74f103`. The exact
preparation and matching protected gate were verified and the allocation is
closed. The [execution and closure receipt](../../docs/evaluations/judge-calibration-090-v1/execution-20261117-01/EXECUTION.md)
records the outcome separately from the earlier credential-free qualification.

Seven records completed, with six applicable judgments and fifteen N/A
dimensions. The five narrow reference labels agreed, including both known
defects. Control 03 returned explicit null for missing trace evidence, outside
scored agreement. Control 07 had no ground truth and made no request. Control
01's factual agreement stands, with an unsupported format claim in its
explanation. Native outcomes are preserved.

Six physical HTTP requests returned six complete essential usage records.
Estimated usage was **$0.017736**. The live report independently reproduced
byte for byte and applicable resource-disposal checks passed. Agent runtime,
arms and cleanup were inapplicable. This is bounded live-route compatibility
and narrow calibration evidence. General judge accuracy, goal judging, actual
billing and skill effectiveness remain unmeasured. The later reporting commit
has its own validation and PR #150 remains unmerged.

**One current next action:** keep executable checks and bounded human review
as the decision path, with judge explanations available as advisory evidence
for these narrow questions.

## PR #150 preparation, retained as history

PR #149 merged as `ca991443c3871d8039589c143498d9294dfba6f8`; the isolated
implementation starts from that verified current main. The focused
[judge-only adapter](judge-calibration-090/ADAPTER.md) registers the existing
seven frozen records with the shared selection, preparation, authenticated
artifact admission, allocation lifecycle, serial scheduler and consolidated
renderer. There is no agent submission, arm, runtime or cleanup evidence to invent.
The unchanged accounting owner distinguishes six applicable logical judgments,
fifteen inapplicable dimensions and up to twelve physical HTTP requests. Control-07
has no ground truth and stays N/A; no successful goal reference is invented to
force a model call. This pass does not calibrate goal judging.

Credential-free integration uses the actual evaluator and authentication CLI,
the existing non-forwarding responder with independent request observation, the
actual retained preparation and fresh consumption/report reproduction. The draft
PR's exact-source hosted artifact, terminal required/selected CI and independent
verification receipt govern readiness; this checkpoint alone does not assert
hosted success. A concrete UNRUN proposal is prepared only after those checks pass.

All live judgments remain **UNRUN**. No provider credentials, model inference,
paid dispatch, protected approval, merge, production adoption, history or Pages
write is authorized. The corpus, labels, decision rules, runtime/model/dependency
pins, historical profiles/outcomes and prior allocation closures remain unchanged.
Fixture integration does not establish live-provider compatibility, judge accuracy,
billing or skill benefit. Added maintenance and removal/requalification boundaries
are recorded in the adapter contract.

**One current next action:** review [draft PR #150](https://github.com/thetechgy/agent-engineering-baseline/pull/150) and its final
source-bound qualification receipt before any separate calibration authorization.

## PR #149 accounting correction, retained as history

Main was verified at PR #148 merge `319240b46952f5c0596a13b56de4f156f30b1bb6`.
The [focused accounting successor](judge-calibration-090/ACCOUNTING.md) retains
physical transport attempts and available OpenAI usage through native collection,
redaction, versioned admission and consolidated reporting. The original offline-v3
profile, source-bound receipts, seven references and decision rules are retained.
All actual model judgments remain **UNRUN**; all prior allocations remain closed.

**Remaining blocker:** the existing protected preparation/authorization mechanism
requires agent/task variants and has no registered judge-only adapter. Fixture
qualification cannot authorize calibration. No provider credentials, inference,
agent trial, paid dispatch, protected approval, merge, adoption, history or Pages
write is authorized. Exact-revision hosted and independent report receipts belong
to the focused draft PR; this checkpoint alone does not assert passing CI.

**One current next action:** review the accounting correction and decide whether
to authorize a focused judge-only preparation/authorization adapter to the existing
mechanism. No new campaign runner is proposed.

## PR #148 standard judge qualification, retained as history

Main was verified at PR #147 merge `d5a04d4394c16108870f95974dd20fa51482e29a`.
The [focused qualification](judge-calibration-090/README.md) reuses pinned 0.9.0,
its actual native OpenAI chat request/response path, existing verifier/collector,
fixture admission and consolidated reporting. All seven corpus judgments remain
**UNRUN**. Local fixture observations are not live judgments or skill evidence.
Final exact-source hosted qualification and fresh-runner reproduction are recorded
on the focused draft PR; this checkpoint alone does not assert passing CI.

**Paid calibration blocked:** upstream discards provider-response usage and counts
logical attempts rather than actual retry/schema HTTP requests. The controls
retain these gaps, partial failures and independently established task failures.
No paid proposal, allocation, credential retrieval, inference, new agent trial,
protected approval, merge, adoption, history or Pages publication is authorized.
All historical grades, pins, CLI/model settings, tasks and closed allocations stay
unchanged. The supported interim path is independent deterministic checks and
bounded human review. Provider compatibility and grading accuracy remain unproven.

**One current next action:** review the qualification and decide whether to
authorize a focused judge request/usage-accounting remedy before paid preparation.

## Completed task-permission smoke pilot, retained as history

**Completed; allocation closed.** [Run 43945876284/A1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43945876284)
executed **c0ef9b195beb7bd04d961272bafe1eadd080b3be**. The user authorized
one dispatch and only its matching protected gate. Exact receipt/source/artifact,
terminal required/selected CI, authentication proof, consumption and unused
allocation were verified first. Real authentication and the normal gate approval
then completed; successful preparation was reused.

| Arm | Execution | Correctness | Authorization | Activation / target access | Estimated USD |
| --- | --- | --- | --- | --- | --- |
| Current | Completed | 1 | 1 | 1; successful full target read | 0.1088368 |
| Absent | Completed; measured task failure | 1 | 0; `unlisted_directory` | 0; target absent, full read null | 0.0888972 |

Two slots launched and measured, none unlaunched; two deterministic verifiers,
zero model judges. Both exact submissions match their producer receipts. The
serial ledger records current's operational evidence, known usage and cleanup
before absent launched. Both native cleanup witnesses and resource-return checks
pass. Public evidence is admitted and the consolidated report independently
reproduces byte for byte. Total estimated usage is **$0.1977340**, not an invoice;
CI costs are separate. Absent full-read evidence remains null.

The [execution and closure receipt](../../docs/evaluations/task-permission-v2/execution-auth-20261116-02/EXECUTION.md)
links the live artifact, digests and per-arm evidence. The allocation ending
`permission_v2_auth_7afe7536d2ae` is permanently closed; no retry, replacement,
continuation or further paid work is authorized. All earlier allocations remain
closed. Later report-only revisions were not executed. PR #147 merged as
`d5a04d4394c16108870f95974dd20fa51482e29a`; its merge revision was not executed.
Production defaults, skills, pins, schedules, Pages and history are
unchanged; this two-attempt operational result does not establish skill benefit,
repeatability, general grading coverage, standard judges or actual billing.

**One current next action:** review the [standard-judge qualification and accounting
blocker](judge-calibration-090/README.md) before any paid-calibration proposal.

## Authentication repair checkpoint, retained as history

### Task-permission successor authentication repair

**Credential-free repair; paid execution unauthorized.** PR #147's
stopped dispatch `43908693565/A1` and both unused slots remain permanently closed.
It executed `3bafc85e1a4fd650bc62d3aa3ed66aa429c1bfaf`; report-only closure commit
`cbf5d0e59c8755c4ea4f30366bf22220932522f4` was not executed. Its queued Validate
`43910563983/A1` was cancelled as superseded by this focused repair; it is
inconclusive, not a passing check.

The actual bare authentication command reproduces the missing `skillevaluator`
dependency. Authentication now reuses the registered runtime's existing pinned
owner through one setup contract shared with preparation. No normalizer is copied,
comparison bypassed or dependency upgraded. The real CLI qualifier runs as the
first test on preparation's fresh runner, with fixture-only GitHub IO. It exercises
parsing, selection, identity reconstruction, archive admission, atomic receipt
publication and downstream artifact/receipt validation without live authority.
Preparation, authenticated admission and fresh consumption require its complete
exact-source proof; missing/incomplete/stale proof rejects.

[The repair qualification contract](../../docs/evaluations/task-permission-v2/authentication-repair-20261116/QUALIFICATION.md)
records the affected boundaries and local reproduction. The [current repair
receipt](https://github.com/thetechgy/agent-engineering-baseline/pull/147#issuecomment-6923566341)
records final source, terminal required/change-selected CI, fresh hosted
authentication proof, revision-bound preparation, authenticated consumption and any
blocker or fresh UNRUN proposal after executable freeze. It governs readiness; this
checkpoint alone does not assert successful hosted qualification. A later documentation or merge revision is not automatically
qualified. Historical profiles, grades, stopped receipts and all closed allocations
remain unchanged; new source-v23 profiles bind the changed shared implementation.
Task/grader/resource semantics and held versions are unchanged.

Intermediate `f0e8cee` preparation `43916530291/A1` passed pinned setup and
all 19 real authentication CLI cases, then failed two constructor controls because
their isolated receipt fixture omitted the now-required producer field. Native
oracle/scheduler work never started. The fixture now supplies that existing field;
the stricter validator remains unchanged. Authentication proof diagnostics also
use a separate artifact so the preparation upload keeps its registered subtree.
The queued `43916527767/A1` CI was cancelled for this known replacement. Failed
and interrupted work remain retained, not readiness evidence.

The `54b56d4` shared CI job in `43917823990/A1` completed 1,130 tests in
1,221.975 seconds with five failures and 129 skips. All failures were historical
registry projections whose filters stopped at source-v20 and included the new
v21/v22 successors in old snapshots. Their expected historical hashes are retained;
the filters now exclude those new families, with an additional complete 698-profile
baseline guard. Container validation and later publisher/behavioral checks never
started. Remaining CI and preparation `43917819082/A1` were cancelled for the known
replacement; passed authentication proof `14251081798` remains evidence for
`54b56d4` only. Final exact-source preparation must be refreshed again.

A focused registered legacy-adapter probe then showed that its bare metadata CLI
legitimately succeeds without evaluator imports. The qualifier's missing-dependency
case now executes the same mandatory owning-runtime guard used by shared setup,
which rejects before authentication for every adapter. Positive authentication
still uses the actual CLI and independent identity/admission/receipt path. No
adapter-name bypass is added. The 18-test authentication/history selection passes,
including legacy positive authentication and absent-owner startup rejection. The
`383e1e2` full shared suite passed; its remaining CI and preparation were cancelled
for this known qualification correction. Its 19-case artifact `14253743561` remains
source-bound evidence only. Source-v23 profiles preserve all 768 prior entries;
final exact-revision qualification is required again.

Any fresh proposal retains the same two-attempt scope and $2 estimate, $3 scheduling
threshold/$3 reserve/$6 planning allocation, not a billing cap. Its new validity
window ends `2026-11-23T23:59:59Z`; this does not extend the old authority. New
allocation/nonce, exact preparation identities, UNRUN command and combined
approval wording are proposed only in the final receipt, unclaimed. No inference,
judge, provider-key retrieval, real allocation claim, paid dispatch, protected
approval, merge or adoption is authorized here.

**One current next action:** complete credential-free exact-source qualification
and review the resulting proposal or precise blocker on draft PR #147.

## Successor stopped pilot checkpoint, retained as history

### Task-permission successor stopped pilot

**Stopped before launch; allocation closed.** The single authorized
[dispatch 43908693565/A1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43908693565)
ran the authentication entry at `3bafc85e1a4fd650bc62d3aa3ed66aa429c1bfaf`.
The bare authentication-job interpreter could not import `skillevaluator` while
reconstructing the successor's trusted task-member identity. The job failed before
an authentication receipt, protected gate, provider credential delivery or agent
launch. No gate approval, retry, replacement or continuation occurred.

Both current/absent slots remain unlaunched and are permanently closed. There are
no task grades, activation/access observations, native cleanup witnesses or live
report to reproduce. Estimated workload usage is $0 because no provider requests
launched; invoice reconciliation remains unknown and CI costs are separate.
See the [stopped execution and closure receipt](../../docs/evaluations/task-permission-v2/execution-20261116-01/EXECUTION.md).

Required CI `43893545608/A1`, preparation `43893646228/A1` / artifact `14240872750`
and inspection `43901736414/A1` passed at that source and retain their recorded
scope. They did not cover the bare authentication-job dependency boundary. This
failure withdraws readiness of the complete dispatch path without relabeling the
successful credential-free controls or changing historical grades. The narrower
gh-007 startup cause remains unknown. The prior proposal is consumed/closed and
cannot authorize another dispatch; later report-only revisions are not executed
or automatically qualified. All previous allocations remain closed.

**One current next action:** remediate and credential-free qualify the actual
allocation-bound authentication entry before preparing any fresh exact-revision
paid proposal; do not retry this allocation.

## PR #147 preparation checkpoint, retained as history

### Task-permission successor smoke preparation

**Preparation only; paid execution unauthorized.** PR #145 merged as
`82cdde086fe4d7fad84f21acc614df2adeca1767`. Its 34 oracle controls and four
real-CLI/local-stub probes remain the prior contract qualification; they did not
create a live protocol or allocation. Historical diagnosis, original permission
results and credential-free controls remain separate from future model behavior.

The registered `gh-task-permission-v2` now has a proposed shared-path live protocol:
one current then one target-absent attempt on existing successor `gh-014`, held
0.9.0 / Harbor 0.25.0 / Codex 0.155.1 / gpt-5.6-sol / high, custom-only grading,
at most two agents/two deterministic verifiers and zero model judges. Task inputs,
resources and semantics remain unchanged. See the [frozen smoke preparation](../../docs/evaluations/task-permission-v2/SMOKE.md).

The focused integration corrects unsuffixed live-entry construction and makes
trusted-manifest launch qualification follow an inherited capability. Preparation
consumption requires complete frozen source/configuration/task/deployment identities,
real constructor/metadata-consumer qualification and the shared two-slot stop path.
Final source, terminal required/change-selected checks, native preparation, fresh
artifact inspection, exact retention/report reproduction and any blockers are
recorded together on this preparation's draft PR. This checkpoint alone does not
assert successful hosted qualification or qualify a future merge revision.

## PR #147 credential-free CI remediation

The failed [Validate run 43858120531/A1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43858120531)
belongs to `9ccfab0b0a3baaebd30a8bac9ef4960c3d08e9c2`. Its 1,120-test suite
passed (122 skips, 1,260 seconds), followed by a passing 449-second container check.
Publisher/orchestration assertions completed, but their step was interrupted at
the 30-minute job deadline; behavioral-evidence qualification/upload never started.
The shared job now allows 45 minutes, preserving all checks and workload deadlines.

The authenticated failed cohort archive identifies absent gh-007's primary failure
as initializer `spawn` / `RuntimeError`; consolidation/gate failures are downstream.
The narrower rejected predicate and daemon stderr were not retained. No historical
cause or pre-existing defect is established. The unchanged initializer, task staging
and pins passed [matched base/head startup 43885174184/A1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43885174184):
four clean environments, exact same image per arm, identical task checksums,
repeated broker identity and complete resource/tag cleanup. The pinned-container
process probe passed 128 observations, so a workstation-only race is not confirmed
for the held container. No initializer, task, trust check or pin was changed.

At this source freeze, final-head required CI and refreshed exact-source
preparation/inspection remain pending. The PR's latest terminal receipt governs
readiness; a passing rerun cannot recover the missing historical cause. Earlier
successful preparation/inspection remain evidence for `9ccfab0` only, and its
unapproved dispatch proposal is superseded. Failed diagnostic attempts and
superseded cancelled CI remain retained and inconclusive where interrupted.

The intermediate `91a72d5` [Validate attempt 43886167994/A1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43886167994)
caught a checkpoint heading-level error, now corrected and checked with the
hash-locked rumdl 0.3.4. Its remaining validation and preparation `43886208394/A1`
were cancelled as superseded; partial results are retained, not qualification.

The `2ea1bb5` shared suite finished 1,126 tests in 1,191.683 seconds before
failing 32 assertions/seven errors in dependency-freshness controls (128 skips).
The added diagnostic job introduced a fourth pinned-uv consumer while its exact
inventory still declared three; other freshness failures cascaded from that
missing inventory. The declaration now counts all four unchanged `0.13.8` uses.
The same 49-test offline suite reproduces the failure before and passes after;
missing/duplicate/contradictory-pin rejection remains enforced. Its remaining CI
and preparation are superseded and retained; final-source qualification must be
refreshed again. No dependency version or source-binding rule was changed.

The budget proposal remains $2 estimated usage, a $3 scheduling threshold and $3
reserve within a $6 planning allocation; none is a provider billing cap and CI costs
are separate. Fresh allocation/nonce and an exact combined dispatch/matching-gate
approval are proposed only in the final PR receipt, unclaimed and unrun. The proposal
expires `2026-11-20T23:59:59Z`; all previous allocations remain closed. Production
settings, skills, pins, schedules, paid settings, Pester adoption, Pages and
production history remain unchanged.

**One current next action:** review the draft PR's exact-revision qualification
receipt for a separate paid-execution decision; do not dispatch from this checkpoint.

## PR #145 checkpoint, retained as history

## Prospective task/deployment permission successor

**Credential-free native qualification completed; draft review.** The opt-in
`gh-task-permission-v2` starts from merged #144 at
`6d063563746651a7e70a570007ed4c23eee9b9d9`. Its [contract and declared controls](../../docs/evaluations/task-permission-v2/CONTRACT.md)
align exact supplied/discovery resources, runtime destinations, bounded issue-12
operations and authorization grading. Permission/discovery prose is an experimental
input; independent correctness stays unchanged. Target access selects trusted
identity rather than staging order.

[Run 43808603192/A1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43808603192)
executed `501b54d5ebdd90bacbc5d920e67fb7afdda1ea9e`: all 34 oracle controls and
four pinned-CLI/local-stub probes completed with expected outcomes and terminal
cleanup. Unsupported/unknown outcomes stay unscored. Good work passes correctness
and authorization in both arms; absent activation fails its gate separately.
Both published policies identify the successor; three consolidated reports
reproduce byte for byte. [The qualification receipt](../../docs/evaluations/task-permission-v2/QUALIFICATION.md)
records artifact identities, local controls, failed/cancelled attempts, reporting
correction and evidentiary limits. Native execution qualifies that executable SHA;
the later receipt commit retains unchanged source identities. Final required CI
belongs to the exact head of [draft #145](https://github.com/thetechgy/agent-engineering-baseline/pull/145).

All 595 predecessor profiles/14 metric definitions, old selectors, frozen task and
replay inputs, original grades/reports, production defaults/pins, isolation,
schedules and closed allocations remain preserved. Source successors bind changed
shared code; authorization v2 has its own metric identity. There is no new live
protocol/allocation, inference, model judge, provider-credential retrieval, gate
approval, merge, production adoption/history, Pester clarification or Pages
publication. Alternate-layout controls qualify the generic interface only;
native qualification remains limited to the held Codex fixture.

**One current next action:** review draft #145's successor contract and
credential-free qualification receipts.

## PR #144 audit checkpoint, retained as history

### Task-authorization audit after PR #143 merge

**Original grades reproduced; evaluation-design limitation.** Current main is
verified at PR #143 merge `1fdf125abf7dd732691666d221e89559486557e1`.
The closed run `43781947803/A1` executed `a8dd7fb20d54284c6a488e228b4430661501ffef`.
Both exact submissions and unchanged native sidecars reproduce under the original
policy: correctness 1/1, authorization 0/0, activation 1/0 and gate 0/0.
The existing consolidated report reproduces byte for byte. This is retrospective,
output-informed investigation, without new inference or replacement grades.

[The audit and reproduction receipt](../../docs/evaluations/gh-runtime-090-v1/authorization-audit/REVIEW.md)
authenticate the live artifact, regenerate exact trusted verifier/task/skill bytes,
reproduce raw-to-ATIF linkage and bind reconstructed broker rows to every original
receipt. Original private audit files were not retained; reconstruction is explicit.
The existing isolated native verifier ran locally; Docker is unavailable, so no new
container-lifecycle qualification is claimed. Exact hosted checks belong to the
focused draft PR, not to the original execution or this checkpoint alone.

Current's first rejection is its home-directory skill read, despite native
discovery guidance and intentionally delivered matching content. Absent first
fails on unsupported fixture syntax and also hits an omitted public README read
and a closed directory-listing form. Its broader issue-list request has no newly
established permission. These literal-policy failures mix task/deployment ambiguity
with unsupported coverage; neither zero alone proves a forbidden write or secret
exfiltration. Original policies, grades, reports and receipts are unchanged.

The unknown full-read convenience field selects the first staged skill, which can
be the competing skill. Exact target output remains separately demonstrated.
This is a selection limitation, not a demonstrated event-normalization defect;
no telemetry change or successor permission policy is introduced.

This evidence-only work adds a bounded receipt reproducer, not a grader correction
or new framework. Production defaults, runtime/model/dependency pins, isolation,
provider configuration, scheduling and paid settings remain unchanged. Both closed
allocations stay closed; Pester clarification and skill adoption remain deferred.
The #95 follow-up distinguishes completed bounded compatibility from unresolved
grading and deferred adoption. No history append, Pages publication,
protected approval, paid dispatch, inference/judge or merge is authorized here.

**One current next action:** review the evidence-only PR's diagnosis of the
task/deployment permission contract.

## Completed compatibility pilot checkpoint, retained as history

### Behavioral runtime 0.9.0 completed compatibility pilot checkpoint

**Completed; allocation closed.** The single authorized
[run 43781947803/A1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43781947803)
executed `a8dd7fb20d54284c6a488e228b4430661501ffef` from PR #143. The corrected
trusted-manifest/live-constructor path reached both actual Codex/OpenAI attempts.
Current then absent completed serially, with exact submissions, two deterministic
verifier runs, zero model-judge requests, complete usage and completed disposal.
Both native task outcomes are measured failures: independent correctness 1/1,
task authorization 0/0, activation 1/0 and gate 0/0. These are not infrastructure
failures or unlaunched arms, and they do not establish skill advantage.

Current native events contain a successful full skill read whose 21,232 bytes
match the frozen source/deployment exactly. The retained convenience field remains
unknown; this independent byte observation is recorded separately. The absent
skill was not deployed and has no observed native full read. Original observations,
grades, counts and task policy remain unchanged.

Reported token estimates total **$0.2724272**, below the $2 plan and $3 scheduling
threshold. Actual provider billing and earlier unknown spending remain unknown;
the $3 reserve/$6 envelope is not a billing cap. Both agent/controller resources
returned to baseline. The allocation closed at **2026-11-16T00:56:18.651645Z**, with
two launched slots, zero unlaunched slots and no continuation/replacement authority.
The previous allocation and its unused slot remain permanently closed.

See the [execution, artifact and closure receipt](../../docs/evaluations/gh-runtime-090-v1/execution-guard-20261116-01/EXECUTION.md).
Authenticated live artifact `14188559673`, archive SHA-256
`1ee8019d90778c21dd763e10e607703ce5d877107fc0b6510981aca45c52f8cf`, retains
native events, grades, submissions, scheduler states and disposal evidence. The
existing public report independently reproduces byte for byte, SHA-256
`11850c54747f195255fc3dedaf62f0e2a6cf06c6434dfa7d519d5eb6636b1bb0`.

This is bounded live compatibility evidence for the execution SHA. Report-only
changes follow closure and do not qualify their later documentation SHA. PR #143
remains unmerged; [its maintained receipt](https://github.com/thetechgy/agent-engineering-baseline/pull/143)
records the report-only revision and checks. No broad qualification was manually
repeated, and no runtime/model/task/skill/dependency or isolation setting changed.
Production remains 0.3.0 / Harbor 0.13.2; Pages/history and recurring paid work remain
unchanged. Grading/judge accuracy, standard judges, wider compatibility, billing
and skill improvement remain unproven. Pester clarification/adoption stay deferred.

**One current next action:** merge review of PR #143 and its bounded compatibility
receipts.

## Credential-free correction checkpoint, retained as history

### Behavioral runtime 0.9.0 launch-construction correction checkpoint

The focused correction in [PR #143](https://github.com/thetechgy/agent-engineering-baseline/pull/143)
keeps parent rejection of ambient overrides and child authorization guards while
accepting only task-owned metadata verified against the private operator manifest,
trusted staged task population and selected arm. A protected TrialConfig context
binds the manifest seal; the shared launch builder verifies it before key attachment.
This fixes the trusted `AEB_GH_MANIFEST` rejection without a global allowlist or
runtime/protection change. See the [trust-boundary and qualification receipt](../../docs/evaluations/gh-runtime-090-v1/launch-correction.md).

The retained failing-before reproduction reaches the actual live Harbor/Codex
constructor for both arms. Credential-free preparation now runs that same live
launch builder and real agent initialization, stops before environment creation,
and exercises the actual manifest startup consumer under a test-only stop before
container start. Missing/substituted/tampered/wrongly bound metadata, unknown/probe/
control/provider overrides and invalid authority must reject. Fresh consumption
validates the retained proof and repeats the boundary on fresh staging. No actual
model credentials, allocation claim, inference or model judge are used.

New scheduler-backed reporting distinguishes unlaunched slots, infrastructure
launch failures and measured task failures while retaining native grades, counts
and collection status. The focused stopped-before-launch report regression retains
zero observations and reproduces its output. Valid `unknown` grader outcomes now remain
unscored and preserve the `missing_usable_evidence` stop through public reporting;
a regression executes the actual generated gh grader before collection. The original published stopped report
still reproduces unchanged, SHA-256
`5acc463c73bf87fc50b741c6d7a94528b4d63bbc19f1caddf6feba8cceebc04f`.

Final executable revision, terminal selected CI (including both required platforms
and selected-results gate), hosted preparation, fresh consumption and artifact/digest
receipts are maintained in PR #143. A failed, pending or source-mismatched receipt
is not qualification. Report-only or later merge revisions are not implicitly covered.

**The old allocation remains closed**, including its unused absent-skill slot.
Stopped run 43762601398 and its b3e190d execution identity, evidence, original report
and closure are preserved below. No new paid authority, nonce or reservation is
created; no protected gate is approved. Live provider/CLI compatibility, actual task
success, standard judge accuracy and skill improvement remain unproven. Production
defaults, paid-stream settings, fixtures/grading and held runtime/model values remain
unchanged. PR #143 remains unmerged; Pester clarification and skill adoption remain deferred.

**One current next action:** review the qualified correction and exact-revision
receipts in PR #143.

## Stopped pilot checkpoint, retained as history

### Behavioral runtime 0.9.0 stopped pilot checkpoint

**Stopped; allocation closed.** The separately authorized single diagnostic
[run 43762601398, attempt 1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43762601398)
executed source `b3e190d143e2cbc7b44938d4d01b690dc9f67c10` from PR #143. Its
current-skill gh-014 slot failed during Harbor agent construction, before Codex
launched: the live guard rejected the trusted task's `AEB_GH_MANIFEST` variable.
The absent-skill slot remained unlaunched. No task grading, submission, model
judgment or usage record was produced. The failure is infrastructure evidence,
not a skill comparison or a measured task failure.

Exactly one allocation-bound dispatch and only its matching `skill-benchmark`
gate were approved under the explicit user authorization. The allocation closed
at 2026-11-15T21:22:28.064144Z, including its unused second slot. No retry,
replacement, continuation or runtime fix occurred. Estimated usage and actual
billing remain unknown; the $2 estimate/$6 planning envelope was not a billing cap.
Cleanup returned to the resource baseline, with no agent container initialized.
The stopped zero-observation report reproduces byte for byte. Its empty-arm
`failed` aggregates do not override the ledger's explicit unlaunched second slot.

See the [execution receipt, artifact identities and concrete reproduction](../../docs/evaluations/gh-runtime-090-v1/execution/EXECUTION.md).
The original preparation and its credential-free CLI controls remain distinct
from this stopped live path. Live provider/CLI compatibility, useful task behavior,
verifier operation in live execution, judge accuracy and skill benefit remain
unproven. [PR #143](https://github.com/thetechgy/agent-engineering-baseline/pull/143)
remains unmerged. Report-only updates after closure do not change the original
execution identity or qualify a later revision.

Production Benchmark remains 0.3.0 / Harbor 0.13.2. No production history append,
Pages publication, recurring paid work or allocation reopening occurred. Pester
clarification and skill adoption remain deferred.

**One current next action:** authorize a separate credential-free fix and
requalification of trusted task-manifest handling in the live guard. A future paid
pilot requires a new exact-revision preparation and authorization.

## PR #143 execution preparation, retained as history

### Behavioral runtime 0.9.0 execution preparation checkpoint

**Implemented for review; no paid pilot authorized.** Current main was verified
at `15caaedb82edf5d9e0253394ed99e3135cd7be93`, the completed merge of #142.
Static quality and data-only reporting/orchestration already use 0.9.0. #142's
versioned behavioral collection/recovery/interpretation/reporting and history
refusal are merged offline qualification; its simulated judgments do not establish
live compatibility.

The explicit `gh-runtime-090-v1` selection prepares pinned 0.9.0 / Harbor 0.25.0
through the existing shared campaign. It preserves production's Codex 0.155.1,
gpt-5.6-sol and high reasoning. The prospective diagnostic pair uses existing
read-only gh-014 and custom-only deterministic grading: two agent attempts, two
verifier runs, zero model-judge calls. See the [execution contract and proposal](../../docs/evaluations/execution-runtime-090.md).

Local matched APM/native staging and focused contracts are preparation evidence.
Final-revision hosted preparation, fresh-runner consumption and normal selected
CI determine readiness. [Draft PR #143](https://github.com/thetechgy/agent-engineering-baseline/pull/143)
retains their terminal results, exact revision, artifacts and proposed command.
A pending, failed, cancelled or expired receipt does not qualify execution.
Live authentication/routing, real provider usage, standard model-judge compatibility/accuracy and skill improvement remain
unproven. No allocation is claimed or reopened.

Production Benchmark remains 0.3.0 / Harbor 0.13.2. The 0.9 offline fixture,
historical profiles/grades and frozen 0.8 experiments retain their identities.
Pester clarification and skill adoption remain deferred; no history append,
protected gate approval, Pages publication, paid dispatch or recurring paid work
is authorized.

**One current next action:** review draft #143 and its exact-revision preparation
and fresh-runner receipts, then decide separately on its bounded pilot proposal.

## PR #142 offline integration, retained as history

### Behavioral evidence 0.9.0 integration checkpoint

**Implemented for review; offline qualification only.** Starting main is verified
at `66c3f92a40b0f00bb461286596a2016a6a39108a`, the completed merge of #141.
Complete static quality now uses pinned 0.9.0 offline-v3; #138's data-only reporting
and orchestration hosts also remain on 0.9.0. #139 finding retention and #140 strict
dataset correction are completed merges. The earlier review checkpoints below
retain their historical tense and receipts.

The focused `behavioral-090-offline-v1` contract connects the already pinned native
verifier/collector, interrupted recovery, admission, redaction, public JSON,
consolidated HTML and simulated history refusal. Runtime-specific interpretation
uses released 0.9 dimension, N/A and required-check verdict helpers. Shared code
owns admission, comparisons and reporting; task definitions retain correctness and
custom grading. Legacy 0.3 interpretation and every old profile remain preserved.
See [contract, evidence and rollback](../../docs/evaluations/behavioral-evidence-090.md).

Fixture judgments are explicitly simulated, unavailable judgments stay unavailable,
known findings survive and recovered/incomplete/synthetic records remain excluded
from production history. Final-revision CI, artifact digests and report reproduction
belong to the focused draft PR. This removes an offline repository integration
blocker; it establishes neither provider compatibility, judge accuracy nor skill
improvement. No live or paid evaluation is authorized by this checkpoint.

Production benchmark execution remains 0.3.0 / Harbor 0.13.2 with held CLI/model
settings. Protected gates, schedules, paid streams, closed allocations, original
history, frozen 0.8 experiments, replay owners and deferred Pester clarification
remain unchanged. Private review migration remains separate.

**One current next action:** review [draft PR #142](https://github.com/thetechgy/agent-engineering-baseline/pull/142)
and its final-revision validation artifacts.

## PR #141 static migration, retained as history

## Static-quality 0.9.0 migration checkpoint

**Implemented for review; production changes only upon merge.** Starting main
was verified at PR #140 merge `18357c54e6d9266c979c915ca11dc8449196d7f9`, with no
intervening changes. #138 already migrated data-only publisher preparation and
orchestration. #139 preserved unscored findings under offline-v3; #140 qualified
the corrected strict dataset. Those merged receipts retain their original meaning.

This change selects the existing pinned 0.9.0 offline-v3 owner for the complete
Validate static consumer: scanner controls, catalog scanning, strict datasets,
collection, owning-runtime normalization, public projection, summaries and artifacts.
The shared scanner installer retains its reviewed sources/locks. The static job
installs no retained evaluator or private review overlay. Contracts, retained
scanner-adapter qualification and native gh keep `quality` / 0.3.0; the single
native gh check moves to the existing contracts job with its Compose cleanup.
CI selection and required platform/selected-result gates are unchanged.

The [migration receipt](../../docs/evaluations/static-quality-090.md) records
same-input comparison, findings/coverage, native public JSON/HTML reproduction,
redaction, failure controls and tested rollback. Final-revision CI and artifact
links are recorded in [PR #141](https://github.com/thetechgy/agent-engineering-baseline/pull/141). Confirmed findings and incomplete coverage
remain evidence; collection success implies neither clean skills nor successful
agent work, judge accuracy or skill benefit.

Benchmarks/recovery/history admission, private reviews/attachments, native
historical replay, frozen 0.8 experiments and the manual 0.7.2 qualifier retain
their owners. Paid streams remain disabled and allocations closed; Pester work
remains deferred. No skill instructions, dataset criteria, historical grades,
evaluator profiles/locks, permissions, protected gates or Pages publication change.
The report fixes independent coverage counting and static-only labeling; 28
source-only successors identify changed shared code while all 473 prior profiles
and frozen selections remain intact.

**One current next action:** review the focused static migration and its final
selected CI receipts. Do not merge as part of this task.

## PR #140 dataset correction, retained as history

## Podman static-dataset correction checkpoint

**Dataset corrected and complete credential-free 0.9.0 static catalog qualified;
focused PR pending review.** Main was verified at PR #139's merge
`a50f693df6f024a6b8063b41e1b6dc2ac40e3f7a`, with no intervening changes.
PR #139 closed bounded unscored finding retention under offline-v3. #138's data-only
reporting/orchestration hosts already use pinned 0.9.0.

This task changes only Podman entry 8's outcome criterion and its APM-deployed
copy, retaining the Docker-only negative-selection case and every other field.
The [dataset receipt](../../docs/evaluations/podman-dataset/README.md) records
before/after strict validation, dataset identities, manual criterion review,
all-catalog scanner findings/coverage, provenance and report reproduction.
Original #137 rejection evidence, snapshots, grades and replay remain intact.

Strict admission now passes for every dataset in the actual six-skill static
catalog. Known scanner failures, missing-reference caveats and incomplete coverage
remain visible; successful collection does not mean clean skills. This establishes
dataset admissibility and credential-free collection/report compatibility, not
judge accuracy or skill effectiveness. The PR description records final executable
revision, selected CI and artifact receipts.

Static-quality migration to 0.9.0 is ready for a separate implementation decision,
subject to final selected CI. Production static/benchmark owners, benchmark/recovery/
history policy, provider qualification, private review/replay, Pester clarification
and closed experiments remain separate and unchanged. No inference, judges,
credentials, allocation, benchmark dispatch, Pages publication or merge occurred.

**One current next action:** review this correction and decide separately whether
to migrate the complete static-quality consumer to pinned 0.9.0.

## PR #139 unscored finding repair, retained as history

## Unscored security-finding repair checkpoint

**Implemented and credential-free locally qualified; pending PR review and
merge.** PR #138 merged as `3fa44f7cf92dc0523ad0ecd959b584190da06f02`.
Main was verified at that merge with no intervening changes. Publisher preparation
and both orchestration hosts already use pinned 0.9.0; static quality, benchmarks,
private reviews and historical replay retain their existing owners.

This repair preserves bounded known verifier findings through unscored collection,
sanitation, public evidence and consolidated HTML while quality stays unavailable.
The successor is `skillevaluator-0.9.0-offline-v3`, diagnostic contract
`aeb-unscored-security-v1`. Offline-v2's patch, profile, interpretation and replay
route remain preserved. See the [repair receipt](../../docs/evaluations/unscored-security/README.md)
for boundaries, before/after evidence, replay and rollback. The PR description
records the final executable revision and terminal selected CI, separately from
local fixtures. A fixture pass is not a successful agent task.

Podman strict-dataset compatibility, versioned benchmark/recovery/history admission
and live-provider qualification remain separate adoption blockers. All 83
historical upstream assertion failures retain their existing dispositions. No
inference, judge, credentials, allocation, live gate, real benchmark, Pages
publication, merge, skill/dataset/grading change or consumer switch is authorized
or performed here. Frozen experiments remain closed and deferred.

**One current next action:** review this focused repair and its final-revision CI.

## PR #138 data-only host switch, retained as history

**Prepared for adoption, pending merge.** This branch switches only publisher
`prepare` and orchestration `plan` / `dispatch` to existing `candidate-next`
setup and `SKILL_NEXT_PYTHON`. Operator base analysis/rendering of validated
public bundles uses the same interpreter. Production main remains at the merged
PR #137 assessment until this PR merges; no workflow was manually activated.

Verified base: `379f44988fc6bb5499bd1d4f3e1b1f6a8eef74bd` (#137), with no
intervening main changes at implementation start. See the
[host migration receipt](../../docs/evaluations/evaluator-090-hosts.md) for changed
consumers, qualification and rollback. The PR description carries the final
executable revision and terminal selected CI receipts.

Static quality, benchmark execution, private reviews/attachments and historical
native replay keep their existing owners. Collector finding retention, Podman
strict-dataset compatibility and live-provider qualification remain separate
blockers. The 0.7.2 qualifier remains. Paid streams are disabled, all prior
allocations closed, and Pester clarification and frozen experiments deferred.

**One current next action:** review this focused host migration PR. No merge or
production activation is authorized by this implementation task.

## PR #137 assessment, retained as history

### SkillEvaluator 0.9.0 adoption decision checkpoint

**Decision prepared:** adopt 0.9.0 for the data-only consolidated report/publisher
preparation and orchestration hosts together; hold complete static quality and
live benchmarks. Production selectors, schedules, protected gates, Pages and
frozen experiments are unchanged by this assessment.

Verified main is `d02d485fa58598aa3f3ce91799a6976746643afd`, the merged
[PR #136](https://github.com/thetechgy/agent-engineering-baseline/pull/136), with no
intervening changes at assessment start. Its passing source
`1cab475c635012731f7bba6825c00b398b39f5bc` and native receipts remain evidence for
unchanged 0.9 fixtures, provenance and reporting.

The [adoption assessment](EVALUATOR-090-95.md) traces each active, manual, opt-in
and historical consumer. It closes the 0.9 static failure/coverage status and
producer-policy projection gaps. Actual native controls retain known violations
alongside unsupported evidence, but a further collector probe confirms that
unscored diagnostics drop those findings. That visibility gap must be closed
under a successor producer identity before live adoption. All 83 upstream assertion differences remain
red upstream assertions, reconciled by cause rather than declared passing.

The static hold is concrete: released strict validation rejects unchanged Podman
entry 8 because its expected output grades skill use. The retained check stays
failed; valid static findings still render. Correcting that task expectation
requires separate scope and no inference. Live benchmarks also retain their
original policy/admission owner and unqualified 0.9 provider route. Original
private review and native replay interpreters remain necessary.

The draft PR description carries exact delivered-commit CI and artifact receipts.
Passing assessment checks do not qualify the held static consumer, provider
routing, judge accuracy or skill effectiveness. All prior paid allocations remain
closed; the Pester clarification and PR #130/#132 experiments remain deferred.

**One current next action:** review and authorize the specific data-only
reporting/orchestration host switch in the assessment. Do not change production
defaults or execute paid work as part of this PR.

## PR #136 opt-in qualification, retained as history

PR #136 merged the separately pinned `candidate-next` 0.9.0 / Harbor 0.25.0
profile. [Validate 43549113107](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43549113107)
passed both required checks, the selected aggregate and native/report consumers
at its final source. Production 0.3.0, retained 0.8.0 and historical evidence were
preserved. Two syntax allowances were omitted only from the new profile. The
merged PR description contains authenticated artifact identities and hashes.

## PR #135 checkpoint, retained as history

### PR #135 verifier metadata transport correction

The case-identity blocker is a build-context transport defect. A focused native
reproduction at `4d9247a265d2f70700c048400a8af5a0616f791d`,
[run 43525527396, job 132230273392](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43525527396/job/132230273392),
uses the pinned CLI and unchanged non-forwarding fixtures. It gives the original
separate case contexts equal-size, equal-timestamp metadata while preserving every
task checksum. The first absent-arm `pester-003` launch is correct. The next
`pester-004` task and host metadata are correct, but the independent verifier image
contains case 003's `entry.json`: expected SHA-256
`8d3d75f770ea53f86137b7c1b2a9968f98da281c1775cbf69904dda5cf8d4215`,
observed `640477c07a950da25952db0d297bcc977c6f8776fbebdfc6e7a1e86fbec6164e`.
Every other protected input matches case 004. Its raw verifier reward identifies
case 003, matching the stale live metadata. Both output mounts belong to their
actual trials, cleanup completes, and no third launch occurs after the mismatch.
The failed job and sanitized live observations were retained before cancelling
the superseded remaining validation. That run is inconclusive overall.

The first incorrect boundary is staged metadata entering the verifier image,
before reward creation. This is not a task-selection, submission-transfer,
collector or normalizer relabelling defect. The unchanged grader reads the stale
file and accurately emits its value; `Reward identity mismatch` correctly rejects
it. PR #134's authenticated passing cohort has the same 76 staged verifier bytes.
The successful-command audit/collection order is unchanged by the lifecycle fix,
and the reproducer uses ordinary successful commands. This exposes an existing
metadata-transfer weakness while qualifying the separate failure-path correction.

The pilot's final image producer now copies the exact staged metadata through a
SHA-256-addressed source filename to the existing `/tests/entry.json` destination.
Different metadata no longer shares a COPY source pathname, even when sizes and
timestamps match. The change applies to every staged case and arm. It never
reconstructs an ID from a case name, changes grader inputs semantically, repairs
a reward or relaxes admission. The regression compares every live protected input
and holds all JSON metadata timestamps equal, including the addressed source.
Interleaving, repetition and both arms still use the existing native CLI route.

All 360 prior profiles are preserved. Pilot retained v15, effectiveness v19 and
campaign source v10 append only the changed source IDs/runtime digests; grader,
fixture, task criteria, skill and model values remain unchanged. The three rejected
original #135 rewards stay rejected. Other historical receipts retain their
original identity evidence and limits; no older live image is retrospectively
claimed observed or regraded.

The read-only observation head `7cf0bd8` independently completed all seven scheduler
controls, exact live input/handoff checks for twelve trials, the selected aggregate
and both required platforms in [run 43516424426](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43516424426).
Artifact `14083218930` has archive SHA-256
`7f7fd9897578338b69e5b7d1ed400f2f9cc594b829aef5a2f1e4188fac6e6f67`.
Infrastructure retains tool exit 23, CLI exit 1 and primary `RuntimeError`, matching
independent before/after/final audits, one launch/eleven unlaunched slots,
unavailable quality and cleanup. Interruption retains CLI exit 124 and the same
conservative stop. This verifies the lifecycle correction, not the new metadata
producer. The new producer must pass the equal-metadata regression and full native
qualification on its own final head. Exact final receipts and readiness are
maintained on [draft PR #135](https://github.com/thetechgy/agent-engineering-baseline/pull/135)
without documentation-only CI restarts.

Local owning-runtime lifecycle, staging, scheduler, identity and append-only
provenance controls pass. This workstation has no Docker executable; native
before/after proof belongs to the maintained selected Actions route. No workflow,
routing, protection, dependency or grading requirement changes. Paid evaluations,
judges, allocations, adoption and the deferred skill clarification remain paused;
PRs #130/#132, freezes, original submissions and historical grades are unchanged.

**One next action:** review PR #135 using its final native and exact-head CI receipts.

## Earlier case-identity investigation, retained as history

The active scope is the raw verifier case mismatch on PR #135 at `f903197`.
Authenticated run `43490661263`, attempt 1, artifact `14072781224`, archive
SHA-256 `13aaa49d55268aab81b702284d8a1f9aec1cf3b80447545a3752ae2b9081ca47`
retains incorrect raw reward entry IDs in absent-arm slots 3, 7 and 11. The
normalizer's rejection remains unchanged. A fresh comparison against PR #134's
artifact `14065618994` confirms all 76 staged verifier members are byte-identical;
that older cohort has no raw identity mismatches. Collector-only replay of the
older cohort leaves all 278 raw trial files unchanged and preserves correct IDs.
Neither observation establishes which bytes the failed verifier actually read.

The read-only observation head `7cf0bd8` passed the normal selected Validate
run `43516424426`, including all seven scheduler controls, the aggregate gate and
both required platforms. Authenticated artifact `14083218930`, archive SHA-256
`7f7fd9897578338b69e5b7d1ed400f2f9cc594b829aef5a2f1e4188fac6e6f67`,
contains twelve correct raw identities and matching live protected input hashes,
with exact handoffs and cleanup. This proves integrated failure-path behavior;
it does not explain or correct the intermittent identity defect. A short native
regression now holds case-metadata sizes and timestamps equal across the original
separate case/arm contexts, testing the specific incremental-transfer hypothesis.
It retains live input/output identities in the job log and owns a separate
verified Compose configuration. Grading bytes and criteria remain unchanged.

A short diagnostic at `74b71fd`, run `43513274711`, passed the sequence absent
003, absent 004, repeated absent 003 and present 004 with live input/output
observations. It did not reproduce the defect and is not a correction receipt.
The following step rejected the Compose configuration consumed by this diagnostic;
that run was retained and cancelled before its known replacement. It is
inconclusive. The intrusive short harness is retired. The current diagnostic
records bounded live verifier input/output hashes and container/image/mount
identities after grading and before disposal, through the existing environment
lifecycle. It does not pre-read, repair or substitute verifier inputs. Collection
failure still disposes the environment and preserves primary/secondary errors.

The original prepared-cohort path must now determine whether its live input bytes,
reward creation, mounted output or later collection is the first incorrect
boundary. Final causal findings, correction and native/CI receipts will be recorded
on [PR #135](https://github.com/thetechgy/agent-engineering-baseline/pull/135).
All 331 existing profiles are preserved; source-v9, pilot retained v14 and
effectiveness v18 identify only the added runtime observation. Task/fixture/grader
bytes and grading criteria are unchanged. No historical rewards are repaired.

**One next action:** complete the boundary trace and supported correction, then
qualify the full existing scheduler. Paid evaluations and experiments remain paused.

## Failure-path audit checkpoint, retained as history

Verified main is `7696b50a3d2c30758d6a25a15c085a8d0b3008b0` (merged PR #134).
This focused correction collects the trusted post-command boundary after a
nonzero CLI exit, before submission collection, runtime-home scrubbing and the
Harbor phase transition. The initiating execution error remains primary.
Observation, collection and disposal failures remain separately visible in the
runtime audit, exception notes and lifecycle record. Collection uses bounded
handling; native containment is never restarted to obtain an audit. If a command
never starts or containment prevents observation, absent evidence stays absent.

The owning adapter is shared by the legacy pilot and campaign Codex consumers.
The environment still disposes resources after observation failure and preserves
that failure if disposal also fails. Cohort admission requires matching dedicated
agent/controller IDs, image identities and policy hashes across the before,
after and final observations. Missing or malformed observations stop as
`missing_security_evidence`; observed mismatch stops as
`security_or_identity_drift`. The ledger retains the execution stop and secondary
failures alongside any security stop. Cleanup failure remains a scheduling stop.
No failed execution becomes a successful agent task or a quality measurement.

The authenticated before receipt is [Validate 43476103384](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43476103384),
at `77b8e8fbca1a2602ca99e2c4c07bb2b7c0d1ac84`, attempt 1,
[artifact 14065618994](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43476103384/artifacts/14065618994),
archive SHA-256 `c0e84f25bfbefdaeaba71d12275f704cd06e0be3ce4f0b4a45194373c0e4b8f0`.
Fresh bounded data-only inspection verifies twelve complete-fixture launches,
twelve real child observations and exact submission handoffs, eight expected
passes/four measured failures and cleanup. The deliberate control retains tool
exit 23, CLI exit 1 and `RuntimeError`, one launch/eleven unlaunched slots,
unavailable quality and cleanup, but no `boundary_after`; its classification is
replaced by drift. This receipt and earlier failures remain unchanged. No new
native baseline or DNS comparison is run.

The local regression fails against verified main on the missing after-audit.
The final owning-runtime local run executed 111 tests: 104 passed and seven
environment-dependent controls skipped. Focused controls cover completion, nonzero exit, command and
observation timeout/cancellation, contained workloads, independent observation
failure, simultaneous cleanup failure, malformed/missing/wrong-environment
observations, policy drift and unavailable report quality. This host has no
Docker executable; native qualification belongs to the normal selected reusable
Actions route. Final exact-head receipts and disposition are maintained on the
delivery draft PR and [existing tracking issue #95](https://github.com/thetechgy/agent-engineering-baseline/issues/95).
Scheduler readiness requires all seven native cohort controls, including cleanup
and interruption previously unreached, the aggregate gate and both required
platform checks to pass. Local controls alone do not establish that readiness.

Only new source identities are appended: pilot retained v13, effectiveness v17
and campaign source v8. All 302 earlier profiles, the existing return freeze,
receipts, submissions, grades, task/model/grader settings and skills remain
unchanged. Unchanged components reuse their authenticated historical evidence;
changed shared consumers receive current native validation through normal CI.
Full historical migration and experiment-preparation matrices are not repeated.

**One next action:** review the focused draft PR using its final native and
exact-head CI receipts. Paid evaluations, judges, allocations, adoption and the
deferred skill clarification remain paused. PRs #130/#132 are unchanged.

## PR #134 routing checkpoint, retained as history

Compatible dependency updates are merged: [PR #125](https://github.com/thetechgy/agent-engineering-baseline/pull/125)
at `e09e67da4d4be8d54d84d2b8ae64e067c9da5ba9` and
[PR #133](https://github.com/thetechgy/agent-engineering-baseline/pull/133)
at current main `e40cc0c995025d448fd7b163df3b6f32b7ea569e`.
The [consumer inventory](DEPENDENCY-MODERNIZATION-20261112.md) retains the
qualification evidence and remaining holds. Production still uses SkillEvaluator
0.3.0/Harbor 0.13.2; opt-in 0.8.0 implementation is not adoption. SDK/framework,
Codex, fixture image/snapshot, Semgrep MCP/OpenTelemetry constraints and the
git-commit skill hold remain. No dependency is upgraded by this routing change.

The [workflow graph, selection contract and operator commands](CI-ROUTING.md)
record the 13 current-main definitions, five retained experiment-branch definitions
and four GitHub-owned workflow registrations. Routine PRs keep both complete required platform checks,
one conservative Git change plan and an always-running result gate. Expensive
maintained checks use existing workflows without changing their job definitions;
full experiment preparation and historical campaign replay become explicit.
Main's five original artifact producers and downstream production/publication
behavior remain intact. Schedules and disabled streams are unchanged.
The existing freshness workflow regenerated #95 from merged main in
[run 43357529214](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43357529214).

The older Codex/Pester scheduler remains failed: missing post-command audit leads
to `security_or_identity_drift`, while its control expects
`execution_infrastructure_failure`. It remains selected for relevant inputs and
fails the new gate; no assertion, guard or historical outcome is changed.
Its repair is a separate work item. Routing-only successor profiles/freeze retain
all historical identities, task/grading/model settings and candidate bytes.
Local focused contracts pass. The broader local suite retains a worker-startup
failure (exit `-6`) also reproduced on unchanged main; worker limits and the
assertion remain intact. Hosted final-source evidence and limitations are
maintained on [draft PR #134](https://github.com/thetechgy/agent-engineering-baseline/pull/134).

[PR #132](https://github.com/thetechgy/agent-engineering-baseline/pull/132)
retains the deferred Pester clarification. Development evidence remains useful;
candidate transfer remains unmeasured after unsupported/test_name_template.
PRs #130/#132, frozen evidence, skills and closed allocations remain unchanged.
Paid evaluations, judges, adoption and live gates remain paused. No Pages,
protection-rule change, merge or new experiment is authorized here.

## PR #134 review-readiness follow-up

The [authenticated follow-up](cli-observation-v1/routing-134.md) confirms the
remaining pilot failure in completed run `43446918858` at `f90196b` is the
historical deliberate-command-failure defect. The complete reusable-route fixture
passed all twelve scheduled trials, actual child observations, submission handoffs
and cleanup. Threshold, unknown-usage and unsupported controls stopped correctly.
The infrastructure command exited 23; the outer CLI exited 1 and raised before
`boundary_after`. Exactly one slot launched, eleven remained unlaunched, and
cleanup completed. The identity guard changed the stop label to
`security_or_identity_drift`, causing the expected infrastructure-label assertion
to fail. There was no extra launch. Authenticated historical run `42937277898`
has the same causal sequence. Source replay agrees at historical, base and head;
this is not a new native baseline execution. The scheduler remains failed and
unqualified, with its guard, assertion and separate repair tracking preserved.

The same run's contracts failure exposed the diagnostic workflow's omitted uv
consumer. The maintained freshness source now registers its single uv `0.13.8`
pin under current CI; frozen return-contract uv `0.13.7` remains separate.
The existing test failed before correction. All 82 owning freshness/routing/
workflow/profile checks pass afterward, including omission and conflicting-pin
rejection. No runtime, fixture, dependency version, skill or historical evidence
changed; the original native receipt retains its original source identity.

The previous DNS cause remains unknown, but the actual reusable pilot route now
has a successful complete-cohort receipt followed by an independently confirmed
known negative-control defect. This supports reviewing routing separately from
pilot readiness; it does not establish DNS reliability. No further broad comparison
or experiment was launched. The earlier hold/proposed comparison is superseded.

Recommendation: proceed with routing review after final-head validation confirms
the inventory correction and no new regression. The [PR's final disposition and
terminal CI receipts](https://github.com/thetechgy/agent-engineering-baseline/pull/134)
name the exact final commit and checks without documentation-only CI restarts.
The selected aggregate must remain failed when the known pilot fails. It is
visible but non-required by protection; required-platform success is distinct
from all selected validation passing. Protection rules remain unchanged.

**One next action:** review PR #134's routing and inventory correction with the
known pilot qualification limit explicit, using the final receipts on the PR.

## PR #130 and #131 checkpoint, retained as history

The latest authorized return-contract allocation is stopped and closed. Development/
candidate run 42908510730 completed six measured outcomes: candidate 3/3, its
matched absent arm 0/3. All references passed; absent missed integer-result.
Transfer/current run 42911213479 launched one session and returned unsupported/
expression_policy; correctness remains unavailable. Transfer/candidate never ran;
eleven slots remain unlaunched. All seven launches have native accounting and
verified cleanup. New estimated usage is $0.3485231; historical spending is unknown.
The [unchanged execution receipt](https://github.com/thetechgy/agent-engineering-baseline/pull/130)
remains draft and unmerged. No allocation is reopened.

The [focused credential-free correction on PR #131](https://github.com/thetechgy/agent-engineering-baseline/pull/131)
([diagnosis](pester-admission-v1/EVIDENCE.md)) reproduces
the admission rejection and versions literal collection-size access and bounded
numeric type predicates. Original bytes, original unmeasured result, task contract,
reference, mutants, scoring, skills, candidate and runtime pins are preserved.
The targeted native workflow must qualify the exact retained current submission;
parser admission is not correctness or isolation evidence. Latest-PowerShell CI
and declared frozen-grader runtime selection are separate. The final hosted source,
artifact, replay and report receipts are maintained on PR #131. Only completed
authenticated qualification supports review readiness.

**One next action:** finish the [CLI-observation disposition](cli-observation-v1/EVIDENCE.md)
and review the authenticated final-head receipts before recommending merge.
The authoritative completed receipt and status links are maintained on PR #130;
its historical experiment reports remain unchanged. No inference, judge, live gate,
continuation, adoption, production-default change or merge is authorized.

## PR #129 checkpoint, retained as history

The return-contract sequence stopped after development/candidate's first native
600-second deadline. Seven slots launched, six measured and seventeen unlaunched.
Development/current and absent each retain 0/3 primary success, passing reference
and missing integer-result; their estimated usage is $0.2705338. Candidate usage
and total spending remain unknown. Both transfer pairs are undispatched. No retry,
continuation, replacement, inference, judge, paid gate or new allocation is authorized.

[PR #129](https://github.com/thetechgy/agent-engineering-baseline/pull/129) fixes the
native timeout evidence lifecycle. The [separate diagnosis and qualification](native-deadline/EVIDENCE.md)
authenticate the original artifact and reproduce native deadline expiry with the
pinned CLI and a non-forwarding fixture. The correction preserves the termination
cause and bounded available diagnostics from a confirmed-stopped container before
deletion. Historical failures and six valid outcomes remain unchanged; no cause
for the candidate's original stall or skill-effectiveness conclusion is established.
The PR records final-source credential-free checks, authenticated artifacts and
report reproduction. This checkpoint grants no live execution permission.

**One next action:** review the focused lifecycle/evidence correction on PR #129
once its credential-free checks and retained report reproduction are verified.

## PR #128 checkpoint, retained as history

PR #127 is merged at `331e0f94b98927a1db776a39b9b16bf500929134`.
The return-contract candidate remains undeployed and its benefit unproven.
The [frozen plan](pester-return-contract/PLAN.md), earlier
[native evidence](pester-return-contract/EVIDENCE.md) and receipt retain their
actual source revisions and grades. Prior allocations remain closed.

A focused integration change adds reviewed campaign selection to the existing
reusable workflow. Selection binds the definition, protocol, exact source,
preparation producer, archive, registered internal location and allocation.
The authentication path normalizes the selected preparation subtree for the
existing consumer; source/layout drift fails before credential delivery.
The same acquisition and fresh staging path has a credential-free inspection
mode with no allocation claim or protected environment. Historical profile
values remain intact; new executable identities use appended `selection-v1`
profiles. Task semantics, skills, model/runtime settings and budgets are unchanged.

The [operator guide](campaigns/README.md#return-contract-integration-and-execution-proposal)
records qualification, the four six-slot dispatches, pair checkpoints, budget,
unrun commands and proposed combined approval wording. The sequence remains
24 attempts: six current, six candidate and twelve absent. Duplicated absent
baselines stay separate; current/candidate comparison is indirect. Transfer is
output-informed. No fixture result establishes skill improvement.

[Draft PR #128](https://github.com/thetechgy/agent-engineering-baseline/pull/128)
retains the exact-source qualification receipts and the concrete four-row
execution proposal, including artifact IDs/digests/expiration, skill identities,
schedules, proposed nonces and unrun operator commands. Local campaign and CI
contracts pass 82 tests with one optional semantics test skipped. The interim
`ea30d37` required checks passed; its other runs were superseded and cancelled
for the final path-validation correction. Those cancelled runs are inconclusive.
Final native preparation, artifact inspection, report reproduction and required
checks must be verified against the revision named by the PR's proposal; no
receipt is relabeled as a different source's execution.

Review/merge is the next decision. A PR-head receipt cannot qualify a future
merge commit. After merge, refresh preparation mechanically with the documented
existing qualification dispatch, then inspect its artifacts at that exact merge
revision. The refresh fails if main has drifted beyond the reviewed merge.
No inference, credential retrieval, protected gate, paid allocation, judge or
merge is authorized here. The reserved confirmation material remains untouched.

**One next action:** review [PR #128](https://github.com/thetechgy/agent-engineering-baseline/pull/128)
and its completed credential-free receipts and bounded proposal. This checkpoint
remains the decision record; the PR supplies its exact-revision evidence.

## PR #127 checkpoint, retained as history

This is the authoritative active checkpoint. The completed six-attempt
[Boolean comparison 42744596001](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42744596001)
at `9f81a66b343f340b681759db8c7c38a4e9e016c5` produced three valid submissions
per arm. Every submission passed the reference and detected four of five defects,
missing integer-result. All current attempts recorded full skill reads; access
is not instruction following or causal benefit. Artifact `13730584511` and its
authenticated archive digest are recorded in the [new candidate evidence](pester-return-contract/basis.json).
The allocation is closed.

One [return-contract skill candidate and frozen plan](pester-return-contract/PLAN.md)
is prepared from that main revision. It clarifies existing coercion/type advice
with a short generic data-driven example. Immutable current/candidate snapshots
remain separate; neither default source nor deployment adopts the candidate.
Pinned Pester 6.2.0 source, 51 tagged tests, 15 advice controls and literal example
checks support the factual guidance. Pester 6.0.0 is source-reviewed only.
The unchanged Boolean development case and an output-informed batch-summary
transfer/regression case use existing runner/grading extension points. Four
paired definitions propose 24 attempts (six current, six candidate, twelve absent),
with explicit duplicated baselines and an indirect comparison. No candidate
model output has been observed. Credential-free native qualification of current
and candidate on both cases completed at `2762e16d1f819e825dd958d5e98791c7799ca946` in
[run 42758383979](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42758383979).
The 56 known controls retained their declared 24 passed, 24 measured failed and
eight invalid/unmeasured outcomes. All four paired preparations passed eight
scheduling/stop scenarios each, followed by fresh-runner consumption. Independent
artifact admission verified archive digests, exact deployment and submission
identities, cleanup, and byte reproduction of 46 machine/HTML report pairs.
These 108 fixture trials include no model inference and establish no skill benefit.

Narrow qualification fixes corrected Markdown and the Compose environment
handoff. Transfer v3 also admits a valid single-test loop covering all public
inputs: only the nonempty execution minimum changes, with a positive control
and failing-before/passing-after evidence. Public contracts, defect criteria,
primary quality formula, 22-line candidate and 24-attempt comparison are
unchanged. Earlier freezes/profile values remain in the audit record.
[Native evidence and limitations](pester-return-contract/EVIDENCE.md) and the
[machine receipt](pester-return-contract/native-qualification.json) retain the
actual execution revision. Frozen inputs remain unchanged in documentation
descendants; exact-revision live admission is still required for any later run.
Static skill validation remains incomplete on both snapshots; broader local
failures retain their baseline/owning-runtime qualifications. Pester 6.0.0 remains
source-reviewed only. Required checks must pass on the final PR head.

**One next action:** review PR #127 and its qualified candidate experiment for merging.
No inference, judge, paid dispatch, new allocation, protected gate, dependency
upgrade, production/default deployment, Pages change or merge is authorized.
The reserved confirmation variant remains untouched.

## Previous checkpoint, retained as history

The following sections preserve earlier status and proposals, not current
execution authorization. PRs #119, #121 and
[PR #122](https://github.com/thetechgy/agent-engineering-baseline/pull/122) are merged.
The prospectively frozen twelve-attempt Pester cohort completed on reused cases:
both arms passed all three trials per case, detecting 5/5 defects on `pester-003`
and 4/4 on `pester-004`. It demonstrated no measured skill advantage. Original
live v5 evidence remains tied to run `42529955611` and revision
`a99992fabaa80b315f57dccf66660c382a4100ee`; later v6 reporting did not change grades.
Estimated usage was $0.7136678, not an invoice. The paid allocation is consumed.

The [bounded retained-submission analysis](PESTER-CEILING-ANALYSIS.md) recommends
one exploratory Boolean-contract candidate: all six boundary suites accepted an
integer-return implementation that violates the documented Boolean contract.
All six current trials successfully read the deployed skill; this is not evidence
of causal benefit or complete instruction following. Original grades are preserved.
The candidate uses the original `pester-004` prompt and unchanged Boolean
contract, without added type-check coaching. Its declarative controls reuse the
existing task stager, semantic helper, grader and reward sidecars. PR #123 is merged.
Its ability to reveal skill advantage remains unproven.

The [reusable campaign entry point](campaigns/README.md) implements shared
scheduling, accounting, native collection and consolidated reporting for the
Boolean candidate and existing `gh-014` fixture. Task adapters retain their own
graders, outputs and metric meanings; the runtime adapter owns APM deployment,
CLI launch, settings, observations and task-named submission retention. The
qualified Codex profile is unchanged and inference remains disabled. Claude Code
and the actual Copilot agent remain unsupported. The paired report bridge and
current inventory/registry remain explicit limits.

Credential-free qualification completed on `3f29708` in
[run 42599548886](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42599548886).
All 28 native trials completed: twenty oracle controls and eight real Codex CLI
probes against the non-forwarding endpoint. Boolean oracle outcomes were four
passed, four failed and two invalid; probes were two passed and two failed.
Gh oracle outcomes were one passed, five failed, two unsupported and two unknown;
probes were one passed and three failed. These are the expected control outcomes,
not model effectiveness measurements. Correct gh JSON with an unauthorized action
retained task correctness while failing authorization; unavailable values stayed
unavailable. No cross-skill aggregate ranking is introduced.

The owning runtime fixes keep uploaded verifier helpers root-owned and private
through bounded stdin transport and resolve submissions through Harbor's existing
host-path mapping. Independent artifact admission verified deployment/configuration,
eight native trajectories and submission digests, unique probe environments and
cleanup. Native/public records matched. Four leaf reports and the combined HTML
reproduced byte for byte from retained public inputs and saved analysis.
The [artifact](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42599548886/artifacts/13666387776)
has archive digest `sha256:09bebc19cf8a37ec63384e7adfa6953708cf274b18d734658f98c1f0ccaafb8e`.
Both required checks passed on the qualification revision; final-head status is
recorded in the PR. Documentation-only follow-up preserves all frozen campaign
input identities. Historical inputs and grades remain intact; unsupported runtime
and model settings remain unsupported.

PR #124 is merged as `853b89a837fa97312d5bd86c30330efebbb7b33b`. The next
prepared experiment uses [the shared Boolean protocol](campaigns/README.md#prospective-boolean-comparison-disabled-pending-decision):
six serial slots, three current and three absent, with the original prompt/inputs,
current skill bytes and integer-result mutant. Primary success requires reference
correctness and detection of all five defects. Each defect, unavailable outcome,
runtime failure, usage and elapsed time remains separate; skill access is recorded
without claiming quality or benefit. The existing qualified Codex/model/provider/
reasoning tuple is unchanged.

This is a prospectively frozen, output-informed follow-up on one case. Six attempts
provide exploratory evidence. A tie, absent-arm advantage and inconclusive result
are legitimate outcomes; no skill revision is prescribed. Known-control
qualification retains its expected outcomes. Live attempts grade actual work,
continue after valid task failure and stop on declared infrastructure, evidence,
identity or accounting failure. The shared scheduler, execution loop and existing
consolidated report carry both modes; separate identities preserve historical
qualification definitions and receipts. No-inference guards remain active outside
the exact authorized protocol gate.

The proposed budget is $3 usage, a $5 scheduling stop threshold and $3 overshoot
reserve inside an $8 planning allocation. November 9 official pricing confirms the
unchanged $2/$0.10/$10 input/cached/output rates per million tokens. Slot/runtime
bounds and the scheduling threshold are enforced; allocation and reserve are
estimates, not a provider billing cap. Authentication, arbitrary live event forms
and actual billing remain unverified. Dependency work stays under issue #95.
The operator guide specifies one future dispatch and its matching protected gate
in a single approval, tied to exact source, artifact and protocol digest.

Credential-free final-source qualification, downloaded-artifact consumption and
report reproduction must complete before this can be called ready for a bounded
live decision. [Draft PR #126](https://github.com/thetechgy/agent-engineering-baseline/pull/126)
retains the concrete source/artifact/protocol receipt and current qualification state.

The authorized follow-up ran once as
[42695478931](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42695478931)
at `97124cf`. One current-arm attempt emitted native file-change events outside
the adapter's qualified subset. It stopped before grading; five slots remained
unlaunched. Cleanup completed and estimated usage was $0.0479649, not an invoice.
The allocation is consumed and closed. The original experiment is inconclusive.

PR #126's Codex file-edit correction completed credential-free native
qualification at `af4dd66a409f1ec401d7989a51b8fc245f68a505` in
[run 42713098769, attempt 2](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42713098769).
The existing shared path passed both task families' 28 native trials, then the
13 non-forwarding CLI scheduling/stop-rule launches and fresh preparation
consumption. Fourteen native edit probes each preserved four completed edits and
one failed edit, including add/update/delete operations, IDs, paths, status and
available evidence. JSON stdout and stderr are retained separately and linked
by hashes. Unknown events, malformed/incomplete evidence and declared accounting
failures retain their intended stops. Valid task failure remains measured.

[Native receipt and consolidated reports](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42713098769/artifacts/13721147577)
have archive digest `sha256:5301d01f68f32415b80f152dbe39bb004d307270b55c6c53aa105bbe15e33f21`.
Independent admission authenticated the producer and archive, checked native edit
meaning against stdout/stderr and reproduced all fourteen report pairs byte for
byte from retained public inputs and saved analysis. Cleanup passed. Earlier
HTTP 503 image-acquisition failures remain failed receipts; bounded HTTPS checks
and the successful signed APT build established recovery without changed pins,
mirrors, hashes or isolation. No additional adapter fix was needed in this follow-up.

The separate [retrospective replay](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42713098769/artifacts/13717139923)
at the same source has archive digest
`sha256:6625f5277d29dbd188573b36f824550732c88660b073d37f080430df501d7192`.
It passes the reference and detects `above`, `highest`, `lowest` and `zero`, but
misses `integer-result`: 4/5 defects, primary quality 0/1, a valid measured failure.
Both exact 471-byte submission copies retain SHA-256
`3215b6097fa3e5f592989f2b8f4523207e28ebd4893cc7d11437b19189795981`.
All original corpus/public bytes remain intact; the original unsupported,
unmeasured result and closed six-slot allocation are unchanged. Independent
retrospective report reproduction and cleanup pass. This is one current-arm
submission after output inspection, not evidence of skill benefit.

Validate and the shared/historical workflows passed on `af4dd66`. The current
evaluator workflow passed on `e1969373c6dea03b055d7439e4f0be22083f417b` in
[run 42724173254](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42724173254),
including all native cohorts, six gh shards and canonical report admission.
[Canonical report receipt 13724828199](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42724173254/artifacts/13724828199)
has archive digest `sha256:16ff91113e52f0e8c329b13b6c4b42cd3bca7044cba27a05175d7666fa15a63b`.
A documentation push exposed an existing concurrency rule that cancelled a needed
evaluator diagnostic rerun. The focused CI fix adopts Validate's existing
rerun-preservation guard; its regression rejects the historical rule and all
fourteen CI-contract tests pass. The cancelled receipt remains inconclusive.
All nine registered grader/fixture/runtime identities remain identical to the
qualified native source. Documentation-only descendants reuse those native
receipts after exact input comparison; final-head Validate status is recorded on
[PR #126](https://github.com/thetechgy/agent-engineering-baseline/pull/126).
The qualified boundary is the pinned Codex/profile event subset. Arbitrary native
events, other runtimes/models, live-provider compatibility and actual billing
remain outside this qualification. No inference, judge, replacement slot, skill
revision or new paid allocation is part of this work. Dependency work remains
under issue #95.

**One next action:** review the qualified correction and recovered result in
draft PR #126.
No further paid inference, judges, retries or dispatches are authorized.
Production and skills remain unchanged; the reserved confirmation variant remains
untouched and outside this work. Sections below preserve historical checkpoints
and their then-current proposals; they do not grant current execution authorization.
The direct-Harbor assessment at `389f7222da8d425b95dad12003e1e6895500a397`
is historical evidence, not the implementation base.

## Frozen first group

The selected release is [SkillEvaluator 0.8.0](https://github.com/NVIDIA/SkillEvaluator/releases/tag/v0.8.0),
released November 6, 2026, at `8149356e4476a1497fb334727f13f699c6fa6ba5`.
Its [released manifest](https://github.com/NVIDIA/SkillEvaluator/blob/8149356e4476a1497fb334727f13f699c6fa6ba5/pyproject.toml)
requires Python `>=3.12,<3.15`, Harbor `==0.24.0`, LiteLLM `>=1.92.0,<1.94.0.dev0`,
OpenAI `>=2.21.0`, Anthropic `>=0.83.0`, and Pydantic `>=2.11.0`.

The [candidate profile](evaluator-candidate.json) freezes Python 3.14.10,
Harbor 0.24.0, OpenAI 2.54.0, Anthropic 2.6.0, Pydantic 2.14.3 /
pydantic-core 2.50.4, LiteLLM 1.93.2, typing-inspection 0.4.5 and the unchanged
locally built backend 1.0.0. Its wheel metadata now admits Python 3.14, and its
execution guard admits only the reviewed 0.7.2/Python 3.13 and
0.8.0/Python 3.14.10 pairs with Harbor 0.24.0. The [resolved lock](../locks/evaluator-candidate.lock)
was upgraded using uv 0.13.7 against the released manifest, without dependency overrides.
Registry artifacts retain their hashes; frozen installation and `uv pip check` are required.
The profile binds the source tree, release revision, patch and lock independently.

This is a **current evaluator with constrained dependencies**, not all dependencies current.
[Harbor 0.25.0](https://github.com/harbor-framework/harbor/releases/tag/v0.25.0)
and [Python 3.15.2](https://www.python.org/downloads/) are outside the evaluator's
supported constraints. Advancing those requires an upstream evaluator constraint change,
then a fresh compatible lock and qualification. LiteLLM must remain below 1.94;
advance it when the evaluator supports the newer line. Do not force a framework fork.

The 0.8.0 evidence patch retains the reviewed classifier, wrapper/observation linkage,
standalone verifier payload, conservative attribution, fixed custom diagnoses,
explicit Codex pin and verifier-only offline Compose rule. Pristine 0.8.0 still
failed their controls; none was found incorporated sufficiently to remove.
One sensitive-path hunk was ported to upstream's changed surrounding code.
The upstream scoring implementation is unchanged.

The active diagnostic producer is `skillevaluator-0.8.0-offline-v4`. It versions
corrections for `printf -v`, generated-script execution, print-operand parameter
assignments and unresolved later reuse of printed sensitive paths. These remain
unscoreable instead of receiving a safety pass. Supported literal configuration
inspection and explicit sensitive accesses retain their outcomes. Six forms of
generated script execution and seven assignment/reuse forms failed before
correction in both actual verifier paths. No sensitive command was executed by
those regressions.
The upstream release, dependency pins, lock and scoring policy are unchanged;
only the evidence patch/source identity changes between diagnostic producers.

Earlier producers retain their original identities and matching tooling: v1 at
`8e6b991`, qualified v2 at `0bfb1f5`, and v3 at `9c87fe0`. V3 passed 45 offline
controls but its native runs were superseded for the confirmed v4 follow-up;
they remain inconclusive. All available v3 artifacts were downloaded and their
digests verified. Earlier evidence is not relabeled or admitted as v4 execution
evidence.
The retained v2 report still reproduces exactly after the v4 change.

## Reporting and interpretation

Historical 0.3.0 and its metric-mean scoring retain their original identities and results.
The 0.7.2 exact-score diagnostic remains available manually; numerical equality with
that policy is no longer an adoption requirement. The current offline profile uses
upstream dimension-mean scoring for standard rewards and custom-overall scoring
for custom-only rewards. Seventy-three controlled vectors check the new formula.
Policy, producer and artifact metric-set identities are distinct. Unknown or
contradictory identities and changed evidence remain rejected. Omitted policy
metadata cannot erase the independently captured candidate producer: such records
remain incomplete and unmeasured. Missing candidate runtime provenance is rejected.

The existing collectors, native normalizers, guarded public writer, analyzer and
consolidated renderer carry candidate evidence. No parallel reporting system is added.
Frozen analyst-attachment profiles retain
their original validator hashes and require matching retained tooling snapshots;
the changed checkout is not relabeled as `current-v4`. A new analyst-review
profile is not qualified by this phase.
Captured numeric evidence handles 0.8.0's omission of sensitive metric names;
only validated enrolled originals supply those values. Missing evidence remains
unavailable, including raw fallback zeros. Correct-but-unauthorized gh output keeps
its task result and fails authorization. Deliberately absent skills affect activation
and the historical combined gate, not shared task correctness. Raw synthetic judge
transport values are retained separately; judged quality and composites remain null.
Synthetic transport controls remain labeled synthetic and unmeasured. Executed
oracle fixtures retain their distinct purpose and per-control measurements; both
are excluded from production history and skill-benefit claims. Cross-policy
comparisons do not produce improvement deltas.

## Qualification and limits

Use `setup-skillevaluator.sh reporting` for isolated historical runtimes and
`setup-skillevaluator.sh candidate-current` for the replacement. Then invoke
`qualify_current_evaluator.py --output` with a new persistent evidence directory and
`SKILL_REVIEW_PYTHON` selecting the retained historical interpreter. Disposable
fixtures honor `TMPDIR`. The new `current-evaluator.yml` workflow reproduces this
without model credentials, inference, judges, scheduling or Pages.

The integrated qualification extends that entry point with `--native`. It runs
all 48 existing gh startup/lifecycle cases through the existing six fixed shards,
plus 48 real Harbor oracle gh trials and the existing 52 native Pester oracle trials.
Observed hosted image builds took about 118 seconds per case, making the original
sequential whole-cohort deadline inadequate. The fixed shard recipe is reused with
two concurrent lifecycle jobs; the oracle cohorts retain their native concurrency.
Only same-run, same-attempt, exact-revision evidence can complete the final join. The gh bridge is necessary because
the lifecycle harness alone does not produce Harbor trial records for collection.
It uses the existing oracle, collector, public evidence writer, analyzer and renderer.
The fixture-only `gh-native-oracle-v1` custom profile keeps the existing gate and
metric definitions; the active production gh profile and standard scoring are unchanged.
Native oracle records remain separate from synthetic transport controls and are
ineligible for skill-benefit or production-history claims.

Expected outcomes are fixed before execution. In each gh arm, gh-001 uses the reviewed
wrong-repository control; gh-002 uses an unsupported trace; gh-003 omits its trace;
gh-014 performs a correct task plus an unauthorized fixture API action. Other cases
use their reviewed correct commands. Broken work must fail task correctness;
unauthorized work must retain correctness and fail authorization. Unsupported and
missing evidence must remain unavailable. Skill absence retains its activation/gate
consequence without turning correct task work into a correctness failure.
Pester must retain 22 passed, 14 failed, 8 invalid, 2 timeout, 2 unsupported and
4 infrastructure-error outcomes. Reference and seeded-mutant evidence, runtime,
arm and checksum identities must agree. A passing qualification does not relabel
negative outcomes, missing evidence, or aggregate execution failures.

The oracle gh recipe canonically orders allowed-read metadata so its preparation
hash reproduces across filesystem enumeration orders. Production and retained
recipes are unchanged. Prospective outcome checks consume the existing normalized,
hash-bound numeric measurements; raw producer-redacted fields remain unchanged.

The custom-only gh verifier loads the released, staged `atif_helpers` and
`checks` APIs directly. The full verifier template imports judge/HTTP dependencies
that custom-only images intentionally omit; an isolated `-I -S` regression checks
the actual grader without installed packages. The native reporting join selects
behavioral records before rebuilding inventory, including when native evidence
is partial. Failed verifier/oracle output and initialization records are retained
as bounded, sanitized diagnostics; linked diagnostic inputs are rejected.

The existing bounded command observer records gh build/start stages without raw
arguments. Oracle launch stages and sanitized failure diagnostics are retained;
cleanup is checked after success and failure. The final report includes the actual
native results alongside clearly marked synthetic reporting controls. Its included
public evidence and saved analysis must reproduce the HTML without native originals.

### Completed native milestone

Credential-free native qualification of producer v4 **passed** on November 7,
2026 at [`3c77857de0353ca94752528be602c200d52fc3e4`](https://github.com/thetechgy/agent-engineering-baseline/commit/3c77857de0353ca94752528be602c200d52fc3e4).
The tested CI merge producer is `210c0a504239f89090977f933cb3bfc5dcb7fb4b`,
whose parents are main `668c734f35d3e31038a32b173ce3fa2a19420295` and that feature
revision. [Run 42358273915, attempt 1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42358273915)
passed all eight jobs, including the final same-run artifact join.

- All 48 gh lifecycle cases passed across six fixed shards. The 14 deliberate
  startup-failure controls remained blocked and unscoreable, with unchanged audits;
  cancellation and infrastructure-error classifications were retained. Secure
  initialization, root-owned broker identity, repeated initialization, pinned
  setup-only Codex 0.155.1, private-access denials and receipt-forgery rejection
  were exercised. No Codex inference ran.
- All 48 Harbor gh oracle trials reached the existing consolidated report:
  22 passed, 22 failed, 2 unsupported and 2 unknown; 44 scoreable and 4 unavailable.
  In both arms, wrong-repository work retained task correctness 0, and gh-014
  retained task correctness 1 with authorization 0. Baseline gate failures remain
  separate from task correctness. Unsupported and missing traces have no measured
  values. The gh task container retains its independently pinned Python 3.12 base;
  the evaluator host is Python 3.14.10.
- All 52 native Pester controls reached that report: 22 passed, 14 failed,
  8 invalid, 2 timeout, 2 unsupported and 4 infrastructure errors; 36 scoreable
  and 16 unavailable. Reference execution and seeded-mutant detection, task/arm
  checksums, PowerShell 7.6.9 and Pester 6.2.0 were checked. Aggregate execution
  remains failed where the intentional controls require it.
- Oracle container/network cleanup and all lifecycle shard teardown completed,
  including after negative and failure controls. Standard and judged candidate
  quality fields remain null; raw fallback zeros do not become measurements.

The [final consolidated artifact](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42358273915/artifacts/13570455833)
is `candidate-offline-report-attempt-1`, archive SHA-256
`016798f24c20fff5e1f8bcb8ae27f973ff2f28e2f9841fa13599d8b3f52fc23c`.
Its identity, repository/run/attempt, producer ancestry, backend/harness bytes,
runtime/lock/patch/source-tree identities and bounded extraction were verified.
All 100 native observations were re-normalized locally and matched the public
records exactly. The existing `skill_report.py --input ... --analysis ... --output ...`
CLI reproduced the HTML using only public evidence and saved analysis. The
3,038,902-byte HTML has SHA-256
`0e9c52d0cd43f9926b83fbce021ac6a218df847d548ce4d8c4c370225f244563`.
The overview, gh/Pester classifications, unavailable values, unauthorized control,
reference-pass and mutation-detection measurements were visually inspected.
Artifact-producer authentication is supplied by the verified CI identity; the
public report retains its own structural-evidence authentication caveats.

V4 passes 46 offline controls, 73 scoring vectors and 48 replay outcomes without
external network attempts or inference. Both actual verifier paths and the
retained production-patch regression pass, as do all 107 frozen package
compatibility checks. The original 20-test backend suite passed under its owning
0.7.2 runtime. [All five repository validation jobs passed](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42358273973)
on the tested v4 feature revision. The authenticated
[scanner artifact](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42358273973/artifacts/13569168123)
retains Podman's nine SECURITY findings (three high, six medium), caveats and
incomplete coverage; its repository-caveat HTML also reproduced byte-for-byte.

The earlier [complete v2 qualification](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42352202778)
at `0d4b21d` remains separate, with its matching tooling at `0bfb1f5` and
[authenticated artifact](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42352202778/artifacts/13567637089)
SHA-256 `e808eac6cbe2192be2ea599e9dc303088966e76430a83a77e405e8d7b47cef44`.
It still reproduces byte-for-byte using that retained source and runtime after
v4's introduction. The incomplete [v3 run](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42357316285)
remains cancelled, with available artifacts retained; cancellation is not a passing
qualification.

Earlier failed evidence also remains separate. [The v1 run](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42344184772)
retains the custom-only verifier import failure, one initialization failure and
the report inventory defect. [The earlier v2 run](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42348063857)
retains the raw-field assertion failure and noncanonical preparation identity.
The import, inventory, assertion and preparation defects are fixed with regression
coverage. The isolated v1 initialization failure remains diagnostic evidence;
it was not reproduced in the complete v2 or v4 runs and is not relabeled as a pass.

This qualifies frozen evaluator compatibility through deterministic native fixtures.
It does not qualify live CLI/provider behavior, judging accuracy, skill activation
by a live agent, skill benefit or adoption. No model credentials, inference, judges,
paid evaluations, skill changes, Pages publication or production promotion ran.

Adoption still requires live CLI/provider compatibility, judging accuracy and
skill-effectiveness evidence, plus any required new analyst-attachment profile.
Frozen analyst profiles retain their exact historical validator snapshots. Maintain
both backend runtime paths, the fixture-only verifier transformation and canonical
preparation recipe, sealed staging and collector/public admission together when an
owning runtime changes. Retain authenticated artifacts and matching source/tooling
snapshots beyond the Actions artifact retention period; never relabel v1 or frozen
analyst profiles under changed validators. Upstream
Harbor, Python and LiteLLM constraints remain the dependency inventory's obligations.

## Completed scanner group and historical next milestone

The independent scanner group is merged through [PR #120](https://github.com/thetechgy/agent-engineering-baseline/pull/120):
SkillSpector 2.13.4 and Semgrep 1.184.0, with controlled collection/report evidence
and credential-free CI tracked there. Gitleaks 8.30.1 is already current. Bandit and
pip-audit remain evaluator-owned; Semgrep's exact MCP 1.29.0 constraint remains an
unresolved dependency gap. The candidate implementation and pins above are unchanged.
PR #120 also qualifies a narrow retained-adapter correction for caveated scanner
reports: findings survive while repository coverage remains incomplete.
[Compatibility evidence](https://github.com/thetechgy/agent-engineering-baseline/blob/chore/95-scanner-modernization/.github/evals/SCANNER-MODERNIZATION-95.md#retained-adapter-compatibility-correction)
records the before/after scans and reporting controls.

The bounded live CLI/provider compatibility pilot below is complete. The next
milestone is a prospectively frozen, more discriminating skill-effectiveness
evaluation; judging accuracy remains a separate qualification requirement.
Other dependencies remain in the existing freshness inventory; this scanner group
does not qualify evaluator adoption, behavioral effectiveness or skill benefit.

## Live CLI compatibility pilot

Preparation started November 7, 2026 from verified main `07e3ea5bb19818af61582062f47df7996f0218f9`.
This milestone uses the qualified 0.8.0 candidate and Harbor 0.24.0, without
changing production, recurring scheduling, Pages, skills or historical results.
The direct-Harbor trial remains historical. This section is the single active plan.

The existing `pester-001` task is suitable: its small executable contract has a
reviewed reference, two seeded mutants and positive/weak controls. The frozen
prompt asks for `output/Subject.Tests.ps1`; it does not direct skill reading.
The pilot selects only that case and schedules one attempt per arm. Both clean
workspaces use the isolated local-skill profile. Pinned APM 0.35.0 deploys the
current skill and all its supporting files; the native registration and staged
bytes are compared with that deployment. The absent arm removes only that target
skill. Graders, reference answers, mutants and oracle solutions remain outside
the live agent environment. Existing contamination and verifier isolation checks
remain enforced. The agent has two CPUs, 2048 MiB, 256 PIDs and 600 seconds. The prospective
`docker-external-openai-v3` policy uses unprivileged Docker execution with all
agent capabilities dropped, no-new-privileges and default seccomp. Harbor's stock
agent-phase allowlist permits `api.openai.com`; the CLI uses the documented
`danger-full-access` container pattern with approval policy `never`. Inner
filesystem and command-network enforcement are absent. No MCP, web search or
subagents are enabled. The independent offline verifier remains separate.

[The frozen runtime](codex-pilot.json) selects official stable Codex **0.167.0**,
the latest stable release when preparation began. The complete official package
is necessary for its Code Mode host and execution/sandbox helpers; the archive,
main executable and helper hashes are independently retained. The released source
is `086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a`. GPT-6.1 Sol uses
`gpt-6.1-sol`, High reasoning, the official OpenAI Responses endpoint and standard
service tier. [Official model documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
and [configuration documentation](https://developers.openai.com/codex/config-reference)
were checked against that released implementation. Responses Lite embeds tool
definitions in input items. Explicit Code Mode/host configuration and the complete
package are pilot-specific compatibility changes; the CLI still labels Code Mode
under development. The qualified setup-only 0.155.1 profile is unchanged.

The pilot adapter retains the released exec JSON protocol's actual command events
and cumulative usage. Harbor 0.24.0's older session-file converter is not treated
as qualification of the new durable thread store. Missing usage stays unknown.
File-access attempts alone do not prove activation or instruction following.

The prospective `pester-cli-pilot-v1` contract admits classic Boolean assertions
`Should -BeTrue/-BeFalse`, alongside the existing standalone forms, and reports
fixed, specific admission reasons. Template expressions, dynamic invocation,
error-suppression parameters and other prohibited operations remain rejected.
The original runner, fixture contract and active `pester-pilot-v3` profile remain
unchanged. Real admission controls reproduce Boolean rejection before the change
and admission afterward; template and prohibited-parameter controls retain rejection.
Seven native fixture controls per arm cover known-good, deliberately weak,
missing-output, Boolean, template, parameter and assertion-failure outcomes through
the candidate collector and existing consolidated report. They are labeled
credential-free oracle controls, independently of the live Codex records.

`codex-pilot.yml` prepares without any model credential. It builds the complete
images, installs and runs the real CLI, verifies the actual post-upload config,
prompt hash, working directory, output and model/provider request, exercises a
stub-supplied command in the external Docker boundary, then a simulated completion. This is
not provider authentication or inference. Both arm probes and the grading controls
must pass before the protected job becomes eligible. Native task checksums are
checked across launch; exact safe submissions and hashes, specific reasons,
sanitized command-stage diagnostics, command events, usage and cleanup are retained.
The usual public evidence, saved analysis and consolidated HTML remain the report.
No model judge, full dataset, production evaluator or history publisher is invoked.

### Proposed allocation and execution gate

Status: credential-free qualification of `docker-external-openai-v3` passed at
`e9a1a79`, as recorded below. The proposed live allocation remains unapproved.
Final-revision required CI must pass before requesting the one concrete approval;
no model credential, inference or model judging is authorized by qualification.

Propose **$10 incremental allocation**, independent of previous unknown spending,
for at most **two agent attempts**, one per arm, with no automatic replacements.
Expected combined usage is roughly 300,000 input and 20,000 output tokens:
about **$0.80** at $2/M uncached input, $0.10/M cached input and $10/M output.
This is an estimate; High reasoning and repeated context can vary substantially.
The pilot sets no supplemental rollout-token limit. Released 0.167.0 semantics
charge backend budget units when present, otherwise weighted noncached input and
output after responses; they are not a guaranteed dollar cap and omit cached cost.

Each attempt has the resource/time limits above. Harbor replacement retries and
CLI HTTP/stream retries are disabled. After the first arm, unavailable reported
usage or a cumulative estimate of $5 or more stops the remaining launch. An
infrastructure failure, changed input identity, safety/isolation failure or
incomplete cleanup also stops execution; a genuine task-quality failure does not.
An unlaunched arm is recorded explicitly. No skill, task or grader changes occur
between live arms. Original outcomes survive later retrospective regrading.

These controls bound attempts and time and check reported spending between arms.
They do **not** guarantee a dollar cap: an in-flight request can overshoot, cached
usage has a different rate, failed requests may lack usage, and invoice/account
billing visibility is incomplete. The protected `skill-benchmark` environment
remains mandatory. Only the final live step receives its existing `OPENAI_API_KEY`.
The exact action after explicit approval will be a first-attempt dispatch of
`codex-pilot.yml` at the reviewed feature commit with allocation
`pilot-<exact commit>-usd10`. Preparation-only dispatch leaves allocation empty.
The approval request will name that commit and authenticated preparation artifacts.

Compatibility success requires actual CLI/provider execution and usable grading
and reporting, with each arm's execution, task correctness, mutation detection,
authorization, access evidence and usage reported separately. Positive skill
advantage is not required. One matched pair cannot establish general effectiveness.
Production promotion remains out of scope.

### First hosted preparation observation

[Run 42387012263](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42387012263)
at `3069447` built both complete images and verified both uploaded configurations,
the frozen prompt, model/High request, skill presence/absence and cleanup. Both
stub-supplied shell calls failed before execution: Bubblewrap could not create a
namespace under the existing Docker policy. This is a preparation failure, not
provider or skill-quality evidence. The authenticated retained artifact
`codex-pilot-preparation-1` has archive SHA-256
`6284f4dbdce4660ebc5beaddfc2cfed05c35dbebbf5ce9849340457722bae3f4`.
No key or inference was involved.

[Official sandbox guidance](https://learn.chatgpt.com/docs/permissions)
confirms that hosts blocking the required Bubblewrap operations cannot run these
policies; legacy Landlock cannot provide all required isolation. The pilot does
not disable the CLI sandbox, grant capabilities, relax seccomp/AppArmor or select
a weaker backend. Readiness remains blocked until an existing compatible executor
can be used within the authorized protections. Independent native grading and
reporting controls continue even when the CLI probe fails; the failed preparation
still prevents the protected live job from launching. No paid approval is requested
while this prerequisite is unresolved.

The retained reporting-runtime regressions passed all 28 custom-metric checks.
Local Pester validation passed 24 checks and reproduced one worker-startup exit
137 under resource limits on unchanged main. Hosted runtime evidence remains
separate. The initial full-validation failure was a checkpoint Markdown blank-line
defect, corrected prospectively. Superseded validation/native runs were cancelled
for the follow-up revision; they remain inconclusive.

The next preparation run at `e5c4935` also retained the sandbox failure. Its
independent grading phase stopped before launch because Docker had populated the
operator Compose configuration after the probe. The workflow now reacquires a
fresh hash-verified Compose configuration at that phase boundary, using the
existing setup component. This preserves its strict admission checks.
Producer/artifact/verifier submission receipts and fixed admission reasons are
retained before normalization; a report error cannot remove native grading records.
No compatible existing runner was identified by the operator. The paid gate stays
closed; a sandbox-compatible executor is the recommended next prerequisite.

### Native control and report verification

[Run 42388456615](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42388456615)
at `7296677` completed all fourteen native grading controls with the expected
four passed, four failed, two invalid and four unsupported outcomes. Both native
arm commands returned zero; this does not turn the negative outcomes into passes.
The twelve actual submissions retain matching producer/artifact/verifier hashes;
the two missing-output controls retain no invented submission. Both cleanup audits
completed. Boolean and classic suites pass the reference and detect both mutants;
the weak suite passes the reference but detects neither. Template and prohibited
parameter controls retain `test_name_template` and `command_parameter`; missing
output retains `artifact`. Oracle fixture records remain separate from live Codex
observations, with no provider inference or judging.

The authenticated artifact is
[codex-pilot-preparation-1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42388456615/artifacts/13580463970),
archive SHA-256 `5c0a2b17f5c5e1da445ef66145de76f41e8cbfc456000e7f0b861aebf1e2a692`.
Its final renderer failed closed because output overlapped the saved-analysis input
parent. Original native records, public evidence, analysis, submissions and cleanup
survived. The output is now a sibling of a dedicated analysis directory. Recovery
rendered the authenticated public records through the existing CLI without
regrading or changing original outcomes. Visual review also caught inherited
synthetic-only labels: the prospective pilot profile now identifies native
controls or live observations and measured custom outcomes truthfully. Judged
scores remain unavailable. The original v4 consolidated report still reproduces
byte-for-byte with SHA-256
`0e9c52d0cd43f9926b83fbce021ac6a218df847d548ce4d8c4c370225f244563`.

The final workflow rerun must complete its independent grading/report phase.
Its CLI readiness probe remains expected to fail at the unchanged Bubblewrap
namespace boundary. Required final-revision checks and their terminal outcomes
are tracked in the draft PR. No paid approval is requested while that prerequisite
is unresolved; both paid arms are unlaunched and no model key has been retrieved.

### External Docker boundary qualification (active, credential-free)

The November 7 continuation explicitly authorizes the documented
[externally contained Codex pattern](https://learn.chatgpt.com/docs/agent-approvals-security).
It supersedes the original inner-sandbox requirement for the evaluated container
only. The implementing session's safeguards are unchanged. Original inner-sandbox
failures above remain evidence under `codex-pester-001-pilot-v1` and
`pester-cli-pilot-v1`; they are not relabeled as external-profile success.

The new `pester-cli-pilot-external-v3` reporting identity retains the same grading
criteria and frozen CLI/model/runtime. Harbor 0.24.0's
[released phase policies](https://github.com/harbor-framework/harbor/blob/v0.24.0/docs-mintlify/tasks/network-policies.mdx)
provide the same OpenAI allowlist at container creation and during the agent
phase. Public downloads occur only during credential-free image preparation;
agent setup uses the baked, hash-verified CLI. Keeping the baseline restricted
prevents Harbor from restoring public networking after `agent.run()` returns.
Trusted operator inspection must confirm Docker controls,
controller separation and active rules before the first credential-bearing exec.
Only the controller has its stock NET_ADMIN/NET_RAW capabilities. The agent has
no host mounts, Docker socket, host namespaces or repository credential. A narrow
pilot environment adapter selects Harbor's non-mounted log collector and delivers
environment values over stdin as the task user, avoiding CAP_CHOWN. The independent
verifier keeps its existing transport and offline configuration. These private
transport hooks are pinned maintenance obligations, not a framework fork.

The actual CLI's non-forwarding stub directs a command that reads immutable task
inputs, exercises allowed and denied network routes, attempts real privilege
operations and writes a public known-good fixture. Its exact bytes must match the
producer, collected artifact and independent verifier receipts. Both arms must
complete. Additional real CLI cases exercise command failure and SIGINT interruption,
with container/network/volume inventories checked after disposal. Host positive
controls and non-timeout proxy rejections are required; missing evidence is
inconclusive. Probe records have a separate credential-free purpose in the existing
consolidated renderer and cannot be interpreted as skill effectiveness.

Agent code can read an eventual model credential from its process environment and
can modify its own configuration, home and command logs. It can write its home,
output, container temporary directories and agent logs, rather than only paths
allowed by the former workspace sandbox. Root-owned task inputs, CLI and policy
files remain immutable to UID 1000. Protected reference/mutant data exists only in
the independent verifier. The agent cannot write operator observations or verifier
logs, which are no longer mounted into its container. Its own events and receipts
remain producer-reported; the independent grade and verifier hash protect the
bounded submission handoff, not a general trustworthy activity transcript.

Stock Harbor networking retains DNS, ICMP and local-network-namespace channels,
and permitted-provider communication. Hostname/SNI allowlisting is not complete
exfiltration prevention, endpoint authentication or a security proof. An eventual
key is exposed to reviewed task code inside the agent container; own-log tampering
and provider-mediated contamination remain possible. This is qualification for a
small evaluation against reviewed repository content, not workstation equivalence
or complete secret isolation. No credentials, inference, judging, paid allocation,
production promotion or scheduling are authorized by this work.

The final external-profile qualification is recorded below. The earlier broader qualification
[42391098962](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42391098962)
has now completed successfully at `e63c18b`, including all eight jobs and its final
same-run report join. That is separate deterministic native qualification, not
external-profile or live-provider evidence. The proposed two-attempt $10 allocation
remains unapproved and must not be dispatched.

The earlier external candidate `docker-external-openai-v2` passed its phase-local
probes in [run 42410130528](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42410130528)
at `47a37fd`, with artifact 13589438155, archive SHA-256
`07423f577fc10e3c9d8c8c7c8d44aea023202cdd0973432810826fd1e0fa7916`.
Its report reproduced exactly and all fourteen grading controls had their expected
outcomes. Further lifecycle review identified that Harbor restores the task's
public baseline after the agent phase; an agent-created background process could
regain public networking before disposal. That artifact remains phase-local
evidence, not qualification of the final lifecycle boundary. No real credential
or inference was involved. Its registered profile and archived bytes are preserved.

Version three applies the stock allowlist as the container baseline as well as
the agent policy. A child launched by the actual CLI waits until after Harbor's
agent phase and independent grading, then repeats allowed/prohibited connectivity
probes before disposal. Trusted operator snapshots verify the final active policy.
Missing delayed-child evidence fails qualification, and inherited disposal still
runs if that observation fails. The final run retains both arms' delayed
observations in addition to the original success/failure/SIGINT controls.

### Qualified lifecycle profile, November 7

Credential-free qualification **passed** at
[`e9a1a7932adcf4972070405df90241991fe287e7`](https://github.com/thetechgy/agent-engineering-baseline/commit/e9a1a7932adcf4972070405df90241991fe287e7)
in [run 42412296410, attempt 1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42412296410).
The tested merge producer is `deeaa677a68f4822e05b1facf7851cd7e837d2a1`, with that
feature revision as a verified parent. The successful repository/workflow/run,
first attempt, source ancestry and archive digest were authenticated before bounded
extraction. No artifact executable was run.

The [preparation artifact and single consolidated report](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42412296410/artifacts/13590556735)
retain 186 members. Archive SHA-256 is
`6f333854aa7d439d18c5beb6fc881de175c8ca246cb378dde282e1e635b8bd4c`.
The report reproduces byte-for-byte from the included public evidence and saved
analysis, with HTML SHA-256
`f0f8694fd6187d1b32eb1dabf8cec0cb966ef91518066c1521d85972b5b3ce4f`.
It combines both real CLI probe outcomes with the fourteen independent grading
controls, under distinct credential-free purposes. These are fixture measurements,
not model-generated task quality, autonomous skill activation or skill benefit.

- Both frozen CLI arms executed the stub-directed command successfully, read the
  legitimate immutable input hashes, and wrote the requested deliverable. The
  current arm read the exact APM-deployed target skill and supporting files in
  both registration locations; the absent arm read no target files. Post-upload
  configuration, prompt, Sol/High requests and deployment manifests matched.
- Both 1,012-byte CLI submissions retain producer/collected/verifier SHA-256
  `9e59688c16ac411adfbbdcf1098520b0afc644494229d92d51dea7a59a24b4e0`.
  Each passed the reference and detected 2/2 mutants under PowerShell 7.6.9 and
  Pester 6.2.0. The twelve other submissions also retained exact receipt matches.
  The fourteen controls retained four passed, four failed, two invalid and four
  unsupported outcomes, including the original specific admission reasons.
- Trusted Docker observations and actual CLI commands verified UID 1000, zero
  effective/added agent capabilities, all capabilities dropped, no-new-privileges,
  default seccomp, two CPUs, 2 GiB and 256 PIDs. No explicit host mounts, Docker
  socket or host namespaces were present. Protected grader/reference material,
  controller files and unrelated host paths were unavailable. Actual setuid,
  network-namespace, controller-mark and nftables mutation attempts were denied.
- During the agent phase and again from the CLI-spawned child after independent
  grading, unauthenticated OpenAI connectivity returned HTTP 401. Operator
  positive controls reached example.com (200) and 1.1.1.1 (301); both CLI targets
  were rejected with TLS EOF, not generic timeouts. Initial, post-command and
  pre-disposal policy hashes matched, with only api.openai.com allowlisted.
- Both arms were disposed after success, deliberate command failure and SIGINT
  interruption. Container, network and volume inventories returned to their
  initial state; runtime homes were removed. Final policy observations survived
  all six CLI cases. Checkout integrity and all thirteen focused contracts passed.

All twenty-eight historical custom-metric regressions pass under their owning
retained runtime. The historical v4 report still reproduces exactly with SHA-256
`0e9c52d0cd43f9926b83fbce021ac6a218df847d548ce4d8c4c370225f244563`.
All earlier metric definitions, profiles, active production selectors, grading
criteria, skill bytes, runtime pins and historical artifacts remain unchanged.
Required checks on the final documentation revision are tracked on the draft PR;
only this checkpoint changes after the qualified execution revision.

Residual exposure requires explicit acceptance before the proposed live pair.
The probe demonstrates that child code can read the sentinel credential and write
its own configuration, home and logs. An eventual real key has the same exposure.
Stock hostname/SNI rules do not constrain provider URL paths, methods or payloads.
Task code could make provider calls outside CLI-reported usage or alter its own
usage/events; the two harness attempts and reported-usage stop do not enforce a
provider spend cap. DNS, ICMP, local namespace traffic and permitted-provider
communication remain channels. Retention/redaction is bounded, not general DLP.
The separate offline verifier protects the reference, mutants and exact submitted
bytes; it does not authenticate all agent activity or establish secret isolation,
exfiltration prevention, workstation equivalence or a security proof.

The paid job was skipped. No model credential was retrieved or injected, no
inference or judge ran, and the two-attempt $10 proposal remains unapproved.
Approval must name the exact final feature commit, this authenticated preparation
and these limitations. A later approved workflow still repeats credential-free
preparation before its protected live job; a failed prerequisite prevents launch.

### Descriptor evidence correction; obsolete allocation cancelled

The owner approved one two-attempt allocation at `a3fa547`, using preparation
run `42413570075` and artifact `13591181861`. All checks on that revision finished
successfully before the single dispatch, [run 42418111772](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42418111772).
Its credential-free preparation passed and produced artifact `13592303007`, with
archive SHA-256 `acaa506b4b4705e916cee363bb31d0fec77cb01f799ebe1afab79788cb105a34`.
The preparation evidence was authenticated and retained before the owner-authorized
cancellation of the obsolete held run. Run `42418111772` is cancelled; its protected
environment was never approved. No live agent attempt, model credential injection,
inference or judge started. The previous paid approval does not apply to changed code.

Comparison with the approved preparation found different generated `task.toml`
hashes. Neither artifact nor either completed job log retained the descriptors.
Searching 975 retained local descriptors and reconstructing 1,024 candidates with
the pinned staging code recovered neither exact recorded hash. Serialization
nondeterminism was reproduced, but equivalence of the two original complete
configurations remains unestablished. The owner declined an exception; these
older artifacts do not acquire configuration-equivalence evidence retrospectively.

The correction retains exact descriptors under `evidence/task-descriptors/`
before execution, with an index binding their raw SHA-256 to the existing native
staging capture. `sha256-typed-toml-v1` additionally hashes the complete parsed TOML:
table keys are sorted, scalar types and values are retained, and array order is
preserved. Unknown metadata fields also participate. No fields are omitted.
The pilot producer digest includes the descriptor helper. Grader, fixture and
dataset digests, runtime pins, isolation policy, accounting and exact native
checksum checks across execution are unchanged.

After authenticating both producer archives and their source revisions, compare
extracted evidence directories without executing artifact contents:

```sh
"$SKILL_CURRENT_PYTHON" -B .github/scripts/codex_pilot_descriptors.py REFERENCE_EVIDENCE CANDIDATE_EVIDENCE
```

The command verifies retained bodies against both identities and the staging
capture before comparing complete configurations. Missing descriptors, inconsistent
evidence or changed configuration fail closed. Success establishes descriptor
configuration equality only; all other preparation and approval gates still apply.

Local credential-free validation passes all nineteen focused contracts and all
twenty-eight historical custom-metric regressions under their respective owning
runtimes, including the pinned saved-review dependencies. The actual pinned native
staging path is exercised. Two hash-seed processes retain all sixteen probe/control
descriptors through archive round trips, with different raw hashes and equal parsed
identities. A fully recorded change from a 600-second agent timeout to 601 seconds
is rejected by the comparison CLI. The focused controls also reject changes to
network policy, resource limits, user, environment, verifier policy, scalar types,
array order, dates, times and additional metadata. Docker is unavailable locally;
container execution and hosted qualification of this correction have not run.
The same comparison is now mandatory in the execution path. The protected job
consumes its own successful preparation artifact by the producer job's artifact ID,
checks fresh native staging before credential delivery, and checks the final staged
tasks again before either live arm can launch. The gate also verifies all four
credential-free readiness/cleanup sections, source revision, execution policy,
expected descriptor cohorts, and exact hashes of every non-descriptor task member.
Native checksums are recomputed from the complete captured manifests; the original
exact checksum checks across execution remain enforced. Missing older descriptors
cannot pass this gate.

A separate credential-free consumer job downloads the successful preparation
artifact by ID and exercises that same consumption entry point. Its operational
artifact retains candidate descriptors and `preparation-check.json`; the existing
consolidated report remains unchanged. The protected job requires both preparation
and consumption to succeed. Downloaded evidence can be consumed with the pinned
owning runtime and reviewed producer checkout:

```sh
"$SKILL_CURRENT_PYTHON" -B .github/scripts/codex_pilot.py check-preparation --preparation AUTHENTICATED_ARTIFACT_ROOT --output NEW_STAGING_DIRECTORY
```

Credential-free hosted qualification passed on implementation commit
[`bb3c7cc28fc9e2b6232805465fa92ac2e475f486`](https://github.com/thetechgy/agent-engineering-baseline/commit/bb3c7cc28fc9e2b6232805465fa92ac2e475f486)
in [run 42423316390, attempt 1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42423316390).
The tested merge source `96d4611abccdef51a4a4cf7ea53da2ab27690e66` has the
implementation commit as a verified parent and the same complete source tree.
The protected live job was skipped.

The authenticated [preparation artifact 13595126695](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42423316390/artifacts/13595126695)
retains 210 bounded files, including exact descriptors for both success probes,
four failure/interruption CLI cases and fourteen grading controls. Archive SHA-256
is `4305e630fa4456756b82d585c0cc453fa833308c8873868535f3ca7c5337e474`.
The separate [consumption artifact 13594099691](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42423316390/artifacts/13594099691)
retains six files with fresh staged descriptors and the successful comparison.
Its archive SHA-256 is `4d69a1d51e3c1dc8830688d20735ba8f6166208cfb3e213d1a56ca0285962b50`.
Both consumed raw descriptor hashes differ from preparation, while their complete
parsed identities and all other task member hashes match.

The actual Docker controls passed, including allowed/prohibited connectivity,
privilege denials, final policy observations and cleanup across all six CLI cases.
The fourteen grader controls retain the expected four passed, four failed, two
invalid and four unsupported outcomes and exact submission handoffs. No model
credential was available to these jobs. These are credential-free fixtures, not
model-generated submissions or evidence of skill benefit.

After authenticated bounded extraction, the downloaded data passed the same
production `check-preparation` entry point under the exact tested checkout and
owning runtime. Both native-to-public projections reproduced byte-for-byte.
The existing combined HTML at `pilot-report/evidence/consolidated/report.html`
reproduced with SHA-256 `37f3645e704e31859de503e81aeba008a81c99f1e613557b1c4a04b6c70617c8`.
A fully recorded hosted candidate fixture with a 601-second timeout was rejected.
The public records retain their earlier diagnostic/incomplete availability labels;
positive control grades do not make the pilot a complete behavioral benchmark.

Both ruleset-required jobs and CI contracts passed on the implementation revision.
The broader repeat was cancelled as superseded and remains inconclusive. This
checkpoint follow-up changes documentation only; final-revision checks and fresh
preparation are tracked on [PR #121](https://github.com/thetechgy/agent-engineering-baseline/pull/121).
The earlier descriptor mismatch remains unresolved. No replacement live allocation,
credential retrieval, inference, judge, recurring execution, production change or
merge is authorized. The old paid approval is not carried forward.

### Review follow-up: remove the baked qualification answer

[Review comment 4504139755](https://github.com/thetechgy/agent-engineering-baseline/pull/121#discussion_r4504139755)
identified a real contamination path: the generic stub copied into both probe and
live images embedded the exact 1,012-byte classic qualification suite, SHA-256
`9e59688c16ac411adfbbdcf1098520b0afc644494229d92d51dea7a59a24b4e0`.
The previous preparation proves its recorded Docker and descriptor observations;
it does not establish a solution-free live image. No live agent attempt used it.

The stub now has no embedded or default answer. The trusted host reads the existing
qualification fixture only in probe mode and supplies its Base64 bytes at transient
stub startup. A live run does not read or deliver that fixture. Probe/live image
contexts remain byte-identical, and the complete descriptor/non-descriptor
comparison remains strict. Pins, skills, legitimate task inputs, grading, isolation,
accounting and historical outcomes are unchanged. The changed producer is enrolled
in its runtime digest.

The native-staging regression reproduces the leak before the fix, then checks both
arms in live and probe modes for raw or Base64 fixture bytes and identical image
contexts. The stub also rejects missing or malformed runtime payloads. Fresh hosted
Docker qualification is required after this correction; superseded in-progress runs
are cancelled with available evidence retained. The linked review thread and
[PR #121](https://github.com/thetechgy/agent-engineering-baseline/pull/121) record the
corrected commit, exact-head checks, authenticated artifacts and report reproduction.
The historical descriptor mismatch remains unresolved, and no paid authorization is
carried forward.

### Runtime acquisition correction after the closed allocation

The owner separately authorized one allocation at
`cc3e881e917436376967b92dad3a1f2ea130f98f`.
[Run 42436172624](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42436172624)
ended at its own credential-free preparation gate. Consumption and live execution
were skipped; neither live arm launched and no environment approval or model
credential retrieval occurred. That allocation is closed, with no retry or
replacement authorized.

The authenticated [artifact 13599782074](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42436172624/artifacts/13599782074)
retains 167 files, archive SHA-256
`a9f1df96adba67d6d266d5efd9492413212a00362317447b046e02ec7f1f3422`.
The original current-skill probe image failed in the runtime installer while an
HTTPS request read timed out after a redirect, at the existing 60-second limit.
The trace does not identify whether PowerShell or Pester was being acquired.
That uncertainty remains. The absent-skill stub probe completed, while the missing
current-skill probe caused the later generic request-contract error. No observed
request-field mismatch was established. Original native failures, fixture outcomes,
usage, submissions and cleanup records remain unchanged. The retained HTML still
reproduces with SHA-256
`94fd6e1cffc8e05eeb0422699bed1b5c93adc616a64258a3e37df389072eed68`.

The correction is limited to the pilot-generated runtime installer. It composes
bounded transport with the original pinned input definitions, extraction checks
and executable version checks. The shared production installer remains byte-for-byte
unchanged, as do the active production profile, frozen saved-review validators,
skills, task requirements, grading, dependency pins, isolation and accounting.
Only the pilot runtime-producer digest changes. No direct-Harbor image-transfer,
APT-cache or allocation infrastructure is imported; no new cache or artifact reuse
is introduced.

Each archive has at most three acquisition attempts. Each attempt has a 60-second
wall deadline; one 150-second budget covers both archives, redirects, DNS, reads,
hashing and the two-/four-second retry backoffs. Linux build-process signal timers
bound trickle reads as well as socket inactivity. Existing observed build and job
deadlines are unchanged. Transient transport, incomplete-response and selected
HTTP 408/429/500/502/503/504 failures may retry. Certificate verification, HTTPS
redirect restrictions and SHA-256 checks remain mandatory. Integrity failures and
permanent service errors fail explicitly. Partial files are removed before a fresh
attempt; existing destination files are not silently reused or overwritten.

`RUNTIME_ACQUISITION` diagnostics identify the asset, attempt, elapsed seconds,
received bytes and fixed failure category. They omit URLs, signed redirect
locations, credentials, headers and arbitrary exception text. Available sanitized
CLI probe records are retained even when qualification fails. The separate
`probe-validation.json` distinguishes missing/unreadable probe evidence from
mismatches in observed request fields. The original acquisition/execution failure
remains in the existing report bundle; missing evidence cannot grant readiness.

Local validation passes 33 focused tests under the owning candidate runtime and
28 historical metric regressions under their pinned saved-review runtime. Real
local HTTPS fixtures exercise timeout/service recovery, retry exhaustion, shared
wall deadlines, partial-file cleanup, checksum rejection and HTTPS/certificate
checks. The actual generated installer extracts verified fixture archives and
invokes its runtime check; native staging verifies the same bytes in both agent
and verifier build contexts. These fixtures are separate from real PowerShell/
Pester Docker qualification. Docker is unavailable locally. Final-commit hosted
preparation, artifact consumption, report reproduction and required checks are
recorded on [PR #121](https://github.com/thetechgy/agent-engineering-baseline/pull/121).
No replacement live allocation, model credential, inference, judge or merge is
authorized by this correction. Historical descriptor equivalence remains unresolved.

### Completed live pair and output-informed evaluator correction

The owner authorized one new allocation at
`633014bdbc4e9df3b37955950a6ef9efa1473547`.
[Run 42448389611](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42448389611)
completed its own preparation, consumption and protected live pair. Both Codex
attempts completed successfully. The independent original evaluator rejected both
submissions as `unsupported/ast_kind`; correctness, reference pass and mutation
detection remain unmeasured. Successful execution does not establish test quality
or skill benefit. The current arm recorded a successful target skill read; access
evidence does not establish instruction following. The reported CLI-token cost
estimate was $0.211091 combined; verified invoice and CI charges remain unavailable.
That allocation is closed. No new inference or allocation is authorized.

[Original artifact 13605202225](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42448389611/artifacts/13605202225)
was authenticated against repository, source revision, workflow attempt and archive
SHA-256 `2f67c417dfad3f04f9015ff580c75eded5223240a15e4adb83a6b886c5dbec99`.
The permanent [retrospective corpus](codex-retrospective/42448389611/manifest.json)
retains exact submissions and original native/public outcomes. Current submission
SHA-256 is `d265ce3f26d8a4d3bb630927153ebc4527cd00876aed8ddec5583ec54c4a4a03`;
absent submission SHA-256 is
`406dac7a20ca8912bed39a2c4ad1293dc0eba405c8814ef160faef851630bce5`.
Neither file nor its original grade may be overwritten or relabeled as measured.

Review of both complete outputs identified three admission gaps together:
ordinary `for` loops, prefix/postfix increment/decrement of permitted variables,
and signed `long`/`Int64` primitive casts. The documented iteration and input
conversion contract supports these operations. The distinct
`pester-cli-pilot-external-v4` evaluator admits them generically, retaining complete
recursive inspection of every loop component and all existing command, scope,
protected-variable and member/index mutation restrictions. The
[supported subset](codex-pilot-iteration.md) states the exact bounds. Shared
production admission, reference implementations, mutants, scoring, skills, task
requirements, dependency pins and offline verifier isolation remain unchanged.

Credential-free qualification adds independent valid/failing loop controls,
forbidden operations in every loop component, protected/member/index write
controls, nontermination and missing-runtime controls. Existing known-good, weak,
missing-output and admission controls remain. The unchanged submissions are copied
through the existing oracle handoff into the same corrected independent verifier;
no model or judge is involved. Original and retrospective records appear beside
each other in the existing consolidated report. This correction follows output
inspection and is **not prospectively frozen validation**. A single pair cannot
establish general skill effectiveness, regardless of the direction of its result.

The current arm's `pwsh not found` observation is investigated separately with
before/after login-shell controls and the absolute pinned binary. A standard-path
symlink addresses login-shell PATH reset without changing runtime bytes. Its
qualification is separate from retrospective grading and is not skill-weakness
evidence. Local checks passed 39 focused staging/admission/provenance tests and
111 historical metric, analysis and reporting regressions. Existing Pester controls
passed 24/25 locally; the fixed trusted startup check failed with CoreCLR resource
error 0x80070008, reproduced at unchanged `633014b` on this workstation. No limits
were weakened. Docker is unavailable locally; native execution, report consistency,
descriptor consumption and cleanup require hosted qualification. Final commit,
actual paired grades, PATH observations, completed checks and retained report links
are recorded on [PR #121](https://github.com/thetechgy/agent-engineering-baseline/pull/121).
The PR remains unmerged; production, historical mismatches and closed allocations
are unchanged. No paid authorization carries forward to this correction.

Initial hosted correction qualification at `b576e6f` completed all six CLI scenarios
and 42 expected grading controls, then stopped before either retrospective replay.
[Run 42454385752](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42454385752)
rejected the reused operator Compose configuration at its existing directory-shape
guard. The exact rejected directory contents were not retained. Consumption and
live execution were skipped; no retrospective grade or inference is claimed.
[Artifact 13607558226](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42454385752/artifacts/13607558226)
retains 413 files with archive SHA-256
`db0f75fec8724196020fb555b0e106b29b092b6c95327e91aa545d96a9b8d433`.
The controls retain 12 passed, six failed, 18 unsupported, two invalid, two timeout
and two infrastructure-error outcomes, with cleanup complete. Both arms' PATH
controls ran as user 1000: login-shell lookup returned 127 before the fix, while
the absolute PowerShell 7.6.9 binary worked; afterward lookup returned
`/usr/local/bin/pwsh` successfully. This establishes an environment/PATH problem,
separately from the still-unmeasured retrospective grades. The workflow now acquires
a fresh, hash-verified Compose configuration before replay, as it already does
between CLI probing and grading. Pins, the configuration guard and isolation are
unchanged. Final hosted replay and consumption evidence remain recorded on this PR.

### Completed compatibility and durable replay maintenance

[Final hosted run 42456637840, attempt 1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42456637840)
qualified both unchanged submissions under `pester-cli-pilot-external-v4`: both
passed the reference and detected 2/2 seeded mutants. The original live CLI pair
executed both arms. Compatibility qualification is complete. Original
`unsupported/ast_kind` outcomes remain intact and unmeasured; the qualified
retrospective results follow output inspection. No skill advantage is established.
The current and absent arms executed ten and fifteen reference tests respectively.
The original current-arm PATH issue was independently reproduced and corrected;
it is separate from skill-effectiveness evidence.

Routine replay now uses the reviewed corpus without downloading the expiring
original Actions artifact. The separate
[retained provenance receipt](codex-retrospective/42448389611-provenance-v1.json)
preserves the original GitHub artifact metadata, selected workflow/repository
metadata, source revision/run/attempt, archive digest and exact archive-member
bindings for all eight retained files. It derives from the authenticated archive
and metadata retained by run 42456637840; no historical record is rewritten.
The corpus manifest and every original file retain their previous hashes.
Repository review authenticates this retained snapshot; offline validation is
**not a fresh GitHub verification** and does not assert current remote availability.
The old artifact's recorded expiry flag is a historical snapshot.

`codex_pilot_replay.py replay --output <new-directory>` performs routine native
replay. `validate --output <new-directory>` checks and exports the required originals
without native execution, using the owning evaluator Python environment. Both
validate the corpus and receipt first. The new
`codex-retained-replay-v2` evidence producer versions the retained authentication
proof and replay readiness. The `pester-cli-pilot-retained-v2` evidence profile
registers the changed producer input digest with the exact v4 grader, fixtures,
metrics and runtime pins; v4 grading, retrospective metadata and historical
producer identities remain unchanged. Producer input capture includes the new
receipt. Preparation consumption requires the exact retained originals, receipt
and matching v2 authentication proof. Missing or altered required evidence and
inconsistent provenance fail validation. Routine preparation needs no Actions
read permission or GitHub token for historical evidence.

The optional `fetch --output <new-directory>` action performs a fresh GitHub
provenance audit while the original artifact is available, verifies its digest
and every retained member, and labels the separate proof as fresh verification.
Its failure does not waive retained validation or prevent routine replay. It is
outside the preparation workflow. New native artifacts retain the corpus and
receipt instead of requiring another copy of the expiring original ZIP.

Local and final hosted maintenance verification, exact final revision, retained
artifacts and report reproduction are recorded on
[PR #121](https://github.com/thetechgy/agent-engineering-baseline/pull/121).
The existing consolidated report continues to juxtapose preserved original outcomes
with output-informed retrospective results. Its diagnostic/incomplete public
envelope and uncollected judge scores remain distinct from completed replay arms.
No production, scoring, reference, mutant, skill, dependency or isolation change is
part of this maintenance correction. No inference, judge, recurring evaluation,
production-default change or merge is authorized.

The next milestone is to design and prospectively freeze a more discriminating
evaluation with cases and decision criteria capable of testing skill effectiveness.
Another repetition of this compatibility pair would not establish skill benefit.
Obtain separate authorization for any future inference or judging.

## Prospective skill-effectiveness preparation (active)

The next group is [the frozen Pester protocol](pester-effectiveness.md), based on
merged main `521a00c` (PR #121). It selects `pester-003` and `pester-004` for three
trials per arm per case: twelve proposed attempts. `pester-001` remains a
credential-free compatibility/regression control. Both primary cases have prior
exploratory and deterministic exposure; neither is called held out. The new
hash-frozen scheduling-window variant is reserved outside this cohort
and skill-revision contexts for later confirmation; it remains unexecuted and
requires qualification before use. The protocol records its exposure limits.

The preparation extends `codex_pilot.py` and the existing consolidated report.
It uses actual APM deployment, complete matched-arm file comparisons, repeated
clean staging, versioned independent grading, positive/weak/omission/failure
controls, exact submission receipts, cleanup and public-only report reproduction.
The prospective grader credits mutant detection only after reference correctness;
per-defect results expose meaningful omissions. Prospective v2 accepts recognized
assertions or the pinned Pester dependency-parameter mismatch after a passing reference,
leaving unclassified test failures unmeasured; new metric identities preserve v1 semantics.
A real filtered-mock positive control reproduced the v1 gap before correction.
Prospective v3 also admits the frozen guidance's scoped invocation flags, module
data parameters, object assertions and normal argument ordering, with positive
and rejection controls. V2 metric semantics and qualified outcomes are preserved. Historical profiles, original and
retrospective compatibility outcomes, production defaults and skills are preserved.
The changed shared tooling has its own retained-pilot identity; no historical
runtime hash is overwritten. Native and repository checks are recorded on the
[draft PR #122](https://github.com/thetechgy/agent-engineering-baseline/pull/122); only a successful exact-revision artifact qualifies preparation.

The one operator entry point (with the existing pinned tools installed) is:

```sh
"$SKILL_CURRENT_PYTHON" -B .github/scripts/codex_pilot.py effectiveness --output "$EVIDENCE/pester-effectiveness"
```

The Codex pilot Actions workflow runs that credential-free case-to-report path.
Its artifact includes `frozen-proposal.json`, the qualified source revision,
complete deployment/runtime/evaluator identities, twelve-attempt counterbalanced
order, expected controls, supporting evidence and reproduced consolidated HTML.
Fixture qualification is not agent effectiveness evidence. The earlier two live
submissions still establish compatibility only: both passed the retrospectively
corrected reference and detected both mutants, with no demonstrated skill benefit.

**One next action:** review the latest successful exact-revision qualification
receipt on [PR #122](https://github.com/thetechgy/agent-engineering-baseline/pull/122)
before a separate paid decision. Only its final qualified revision and authenticated
preparation may be proposed for authorization. The [protocol's operator command](pester-effectiveness.md#qualified-execution-path-credential-free-implementation-follow-up)
uses `cohort_allocation` on the existing workflow. The old pair allocation cannot
authorize it. The runner records twelve ordered entries before launch, selects one
case/arm/ordinal through the pinned native trial CLI, and retains pending or stopped
entries without automatic continuation. The existing report path now admits the
three-trial, two-primary-case population and labels non-forwarding CLI fixtures
separately from live agent evidence. Task/grading/runtime/model/dependency settings
and historical identities remain frozen; new source/runtime profiles bind the
implementation and require fresh qualification.

The proposal estimates $6 usage, stops subsequent launches at $10 cumulative
estimated usage, and retains $5 contingency within a $15 planning allocation.
These are estimates, not provider billing or an enforced billing ceiling; an
in-flight request can exceed the observation threshold. Contingency permits no
extra attempts or retries. Missing accounting or operational evidence stops
scheduling. Public OpenAI model documentation was rechecked November 8, 2026;
the frozen model remains listed at $2/$0.10/$10 per million input/cached/output
tokens. Account access and invoice charges remain unverified. Credentials,
inference, judges and environment approval remain unauthorized. No prior paid
allocation carries forward.

The implementation follow-up's final feature commit, tested revision, qualified
preparation artifact and independently downloaded report reproduction are recorded
on PR #122. This checkpoint does not itself qualify an untested revision or grant
paid authorization. Exact-source qualification is required after any change; use
only the final artifact and revision recorded on that PR.

Maintain the new profile hashes, fixture transformation and expected defect matrix,
APM deployment audit and public evidence/report contracts together. If live work
reveals justified weaknesses, investigate first; obtain authorization before skill
revision, then freeze absent/current/revised comparison with regression and unseen
confirmation. Do not change cases or grading after future outputs to seek a win.

### Executable cohort qualification and final-source gate

The initial execution implementation is `50483e43e6cce740763a289fd4845ddf882a9753`;
its native collection/Compose correction is
`bb3b33666ebc179819bf8b08454cd030161f61d8`. At that exact source,
[run 42515611936, attempt 1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42515611936)
passed preparation, both consumption gates and the actual sequential scheduling
path. The compatibility and cohort live jobs and cohort authorization job were
skipped. No protected-environment approval, model credential, inference or judge
was used.

The authenticated [v4 preparation artifact 13633207644](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42515611936/artifacts/13633207644)
has archive SHA-256
`83ed1c9afeacb193d64bf9ec03e4c8586fc90da7e6c78166553218943d4d505d`.
Bounded data-only extraction and exact-source native re-admission reproduced the
public records. All seven existing-renderer HTML reports reproduced byte-for-byte.
The complete fixture cohort retains exactly twelve submissions and native outcomes,
the frozen order/ordinals and twelve distinct agent environments. Measured passing
and failing work remain measured. Each threshold, unknown-usage, unsupported-grade,
execution-failure, cleanup-failure and interruption scenario stops after one launch
and retains eleven unlaunched entries. Unsupported and unavailable outcomes have
no quality values. Threshold/unknown-usage/cleanup cases explicitly inject host
observations after actual CLI/verification/disposal; their original native evidence
is retained unchanged. These are deterministic fixtures, not effectiveness results.

The separate [v4 consumption artifact 13632853812](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42515611936/artifacts/13632853812)
passed fresh deployment and complete descriptor/member comparisons. The downloaded
compatibility artifact `13631629322`, archive SHA-256
`da06d9b43c15ca7b247ab9f9a96ed44ecfcca451a5da09dcc2322cdff8eb5810`,
also passed the production consumption entry point under the exact source snapshot.
The earlier frozen v3 grading qualification at `aa28fd0` and
[artifact 13629333800](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42508939799/artifacts/13629333800)
remain preserved, including all 76 declared classifications and their historical
profile identities.

The v5 follow-up fixes a reproduced binary-float threshold edge: $9 plus ten
$0.10 observations summed just below $10. Decimal addition now schedules against
the recorded estimates without changing token counts, rates or runtime limits.
An exclusive local dispatch claim complements Actions history and refuses the
same allocation even if its output directory is removed; live output is fixed to
the protected job's directory. A longer outer job deadline accommodates the twelve
serial attempts without changing agent/verifier limits. Markdown formatting is
corrected. V4 evidence and all older profiles remain registered unchanged; v5 has
its own runtime identity with identical grading, fixtures and frozen settings.

Local verification passed 64 focused checks (one optional semantic check skipped)
and 111 historical metric/report regressions in their saved owning runtime. The
broader historical run under the candidate runtime was inconclusive and was
repeated under that owning runtime. The first full-validation failure was a
Markdown line-length error; the correction passes local lint. Known-superseded
broader runs were cancelled with available failure evidence retained. Cancelled
runs do not establish success.

The final feature commit, final tested revision, qualified v5 preparation artifact,
report hashes, completed exact-head checks and concrete operator allocation are
recorded together in PR #122's verification receipt. This checkpoint intentionally
retains the earlier receipts above as historical evidence. Neither v3/v4 preparation
nor any earlier paid decision authorizes v5. The protected live preflight rejects
a preparation/source mismatch. Only successful qualification at the final source
revision permits proposing its exact protocol/revision/artifact/one-dispatch nonce
for a new decision. The [single operator command](pester-effectiveness.md#qualified-execution-path-credential-free-implementation-follow-up)
remains unapproved. Paid execution is unrun; account access and provider billing
remain unverified.
