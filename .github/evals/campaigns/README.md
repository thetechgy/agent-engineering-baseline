# Reusable evaluation campaigns

Use one operator entry point with the pinned candidate evaluator, Harbor, Compose
and APM tools already installed. Keep retained output outside the checkout in a
persistent workspace. Disposable files follow `TMPDIR`. No credentials, inference,
model judges or paid dispatch are accepted by qualification mode.

```sh
"$SKILL_CURRENT_PYTHON" -B .github/scripts/evaluation_campaign.py qualify \
  --definition .github/evals/campaigns/boolean-contract.json \
  --output "$EVIDENCE/boolean-contract"

"$SKILL_CURRENT_PYTHON" -B .github/scripts/evaluation_campaign.py qualify \
  --definition .github/evals/campaigns/gh-read.json \
  --output "$EVIDENCE/gh-read"
```

Supply both definitions in one invocation to produce a combined report. The
[qualification workflow](../../workflows/evaluation-campaign.yml) does this.
`--mode oracle` executes the native oracle controls. `--mode probe` executes the
real pinned Codex CLI against the loopback, non-forwarding endpoint. The default
runs both modes. Neither mode performs model inference. A CLI probe qualifies
only the exercised CLI/configuration/fixture boundary, without provider access.

The output retains the frozen definition, runtime/model identity, ordered attempt
ledger, APM deployment, task members and descriptors, native grading and cleanup
observations, submissions, validated public records and consolidated HTML. The
report is rendered twice from public inputs and saved analysis; unequal bytes
fail qualification. A stopped campaign retains pending positions and available
reports. Infrastructure failure, missing evidence, unsupported grading, invalid
submissions and measured task failures remain distinct. No attempt is replaced.

The Boolean task uses PR #123's original prompt and inputs, the additional integer
mutant and all five controls. Oracle controls cover both strong suites, value-only,
type-only and invalid discovery. CLI probes use strong and value-only suites.
The existing prospective grader retains reference correctness, the five individual
mutant results and their joint quality metric.

The gh task selects the already-qualified `gh-014` issue-read fixture. Its existing
broker and grader execute without real GitHub service calls. Oracle controls cover
correct work, wrong repository, unauthorized action, unsupported trace and missing
trace. CLI probes cover correct work and the unauthorized action. Correct JSON
with an unauthorized action retains task correctness and fails authorization.
The absent variant retains its separate activation/gate consequence. These gh
metrics are not converted into Pester quality or a cross-skill score.

Both task families completed native oracle controls and real CLI probes on
`3f29708` in [run 42599548886](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42599548886).
Its [retained artifact](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42599548886/artifacts/13666387776)
contains the combined report at `report/consolidated/report.html`, four leaf
reports and their public inputs/analysis. Independent admission verified all 28
trials and reproduced all five reports byte for byte. The
[authoritative checkpoint](../EVALUATION-PLAN.md) records the source identity,
control outcomes and remaining limits. Synthetic plumbing controls remain labeled
separately. Native fixture qualification establishes neither model inference nor
real compatibility for another runtime/model.

## Boundaries and extensions

| Responsibility | Implementation |
| --- | --- |
| Order, attempt limit, budget observation, stop and durable ledger transitions | `evaluation_campaign_core.py`; reused by the historical cohort wrapper |
| Task selection and native execution orchestration | `evaluation_campaign.py` |
| Prompts, fixtures, expected outputs, controls and grading expectations | Definitions here and task adapters in `evaluation_tasks.py`; existing graders |
| CLI launch, discovery, native APM deployment, configuration and usage | Owning adapter in `evaluation_codex.py`; reused pinned pilot helpers |
| Runtime/model identity and supported settings | `evaluation_runtime.py` and `codex-qualified.json` |
| Native admission, public projection, analysis and rendering | Existing evidence/report modules; registered campaign extension in `evaluation_evidence.py` |

For **another skill on an existing runtime**, add its task definition and a small
task adapter: stage its existing BYOT/BYOG bundle, expose controls and expected
artifacts, validate protected fixture/grader bytes and check task-specific results.
Register new immutable custom metric/profile identities and the task adapter. Use
the same scheduler and report entry point. Do not edit installed skill bytes to
prepare a case.

For **another runtime on an existing task**, add an owning adapter module and
register its profile validator, source-input metadata and execution module in
`evaluation_runtime.py`. The adapter
owns deployment/discovery, image preparation, actual agent launch configuration,
authentication boundaries, native observations, usage and cleanup. Qualify its
Harbor import hooks and native collector/admission identities through this same
entry point. Claude Code (`claude-code`) and the actual Copilot agent (`copilot`)
are explicit extension targets and currently fail as unsupported. The task's
fixture `gh` executable is not the Copilot runtime. Synthetic identity checks do
not establish real CLI compatibility.

For **another model supported by an existing runtime**, add a separate explicit
runtime/model profile and qualify it through the owning validator and actual CLI
probe. Preserve model/provider/settings, version, limits and pricing assumptions
in the ledger and registered reporting identity. Unknown settings fail explicitly.
The Codex validator currently accepts only the unchanged qualified
[codex-pilot.json](../codex-pilot.json); adding a model is not an arbitrary string
override and does not enable inference.

Variant names are configuration, not scheduling conditions. The scheduler also
has a three-variant contract check. The current report bridge remains paired and
requires one present and one absent deployment. A practical absent/current/revision
comparison uses separately frozen definitions for absent/current and
absent/proposed-revision, with the same task and runtime and the proposed skill
source selected by its definition. A revised source needs its own reviewed source
identity and qualification before admission; this work creates no revision.
Direct current-versus-revision pairs, arbitrary multi-arm native reports and
arbitrary live campaign authorization remain unsupported. The existing source-content
admission checks intentionally reject unregistered revision bytes.

## Maintenance and qualification limits

The shared scheduler, native aggregate builder, report reproduction and pinned
CLI image/usage helpers are extracted from the existing pilot. Historical CLI
and cohort commands remain wrappers over these implementations. There is one
scheduler policy and one consolidated renderer to maintain.

Maintain task definitions, control expectations, source/profile hashes, adapter
contracts and the hosted qualification together. The gh composition also maintains
a bounded private stdin transport for initializer payloads and verifier helpers,
with byte-preserving repeated initialization. Verifier files are root-owned
and private, avoiding Docker copy ownership without adding capabilities.
The shared image helper owns all Harbor log directories. Non-mounted trajectory
transport retains verifier-readable permissions without adding capabilities.
Campaign submissions retain their declared filename and producer digest; the gh
oracle exports its JSON through the task adapter without changing its grader.
The Codex adapter bridges the pinned exec JSON protocol to Harbor ATIF using
completed native command identities and observations. Missing observations and
unsupported protocols have separate stop reasons; unknown events fail closed.
Native setup failures are infrastructure outcomes in public reports, while
missing and unsupported observations retain their separate unavailable states.
Protocol changes require new adapter qualification. Source changes get new profile
identities; old profiles, receipts and grades stay unchanged. The new retained
pilot source identity is v8 and the effectiveness source identity is v9, with
unchanged historical grading semantics. Campaign profiles have separate oracle and CLI-probe identities. Tests
compare all historical registry entries and production active-profile selections
with the executed `97124cf` registry snapshot.

Remaining coupling includes the paired native collector/public schema, the
existing supported skill inventory/metric registry, Docker/Harbor transport and
Codex event conversion. The current runtime uses the existing external containment
policy and frozen model/provider settings. The gh adapter composes trusted broker
initialization with that containment; its boundary probe is an operator preflight
because the task grader rejects arbitrary interpreter commands in agent traces.
Boolean CLI probes also exercise the boundary from a CLI tool child. The gh image
uses the same already-pinned curl version as that qualified runtime. No dependency
version, production default, distributed skill or historical grade is changed.

These demonstrations qualify reuse for two task families. They do not establish
universal runtime compatibility, prospective skill advantage, provider
authentication, model effectiveness or actual provider billing.

## Prospective Boolean comparison, disabled pending decision

Historical record: these Boolean allocations are closed. Commands in this
section retain their original context; use the return-contract proposal below
for the new four-pair experiment.

[boolean-effectiveness-v1.json](boolean-effectiveness-v1.json) selects the original
Boolean task and inputs, current skill bytes and PR #123's integer-result mutant.
Its separate [versioned protocol](boolean-effectiveness-protocol-v1.json) freezes
six slots: current/absent, absent/current, current/absent. Each arm gets three
independent trials. The sole deployment difference is the target skill directory,
including its supporting files, deployed through native APM. Prompts, context,
fixtures, model, provider and reasoning settings match. The explicit
[codex-authorized profile](codex-authorized-v1.json) preserves the qualified Codex
0.167.0 / `gpt-6.1-sol` / OpenAI / high tuple and its configuration unchanged.
`inference_enabled` and `authorized_live_attempts` remain false/zero in preparation;
only the exact authorization gate can admit the separate live mode.

The primary outcome is reference-correct work detecting all five seeded defects.
The existing report also shows reference correctness and each defect separately,
including integer-result, valid task failures, invalid/unsupported results and
runtime failures. Planned denominators are three attempts per arm even when a
stop leaves slots unlaunched. Missing measurements remain unavailable. Native
usage and elapsed time remain separate from quality. The attempt ledger records
successful full skill output separately: a read or activation score demonstrates
neither task quality nor benefit. Other read forms and truncated outputs can stay
unobserved; absence of a recorded read is not proof that the skill was ignored.

This is exploratory evidence on one case. Earlier outputs informed its design.
It is a prospectively frozen follow-up, not an untouched held-out benchmark.
A tie, absent-arm advantage or inconclusive result is legitimate. No skill
revision follows automatically from any outcome.

### Credential-free preparation and consumption

Run the existing two-definition qualification command above first. Then use the
same campaign entry point, with a new persistent output directory. Each native
phase needs a fresh hash-verified Compose configuration from the existing tool
setup; the workflow acquires it between qualification and preparation. Reusing a
Docker-written configuration fails the existing provenance guard.

```sh
"$SKILL_CURRENT_PYTHON" -B .github/scripts/evaluation_campaign.py prepare \
  --definition .github/evals/campaigns/boolean-effectiveness-v1.json \
  --qualification "$EVIDENCE/qualified-campaigns" \
  --output "$EVIDENCE/qualified-campaigns/preparation"

"$SKILL_CURRENT_PYTHON" -B .github/scripts/evaluation_campaign.py check-preparation \
  --definition .github/evals/campaigns/boolean-effectiveness-v1.json \
  --preparation "$EVIDENCE/qualified-campaigns/preparation/evidence" \
  --output "$EVIDENCE/fresh-consumption"
```

The existing workflow executes this sequence and consumes the downloaded artifact
on a fresh runner. Preparation runs the actual six-slot execution loop against
the non-forwarding endpoint. Strong and value-only submissions produce measured
passes and failures without matching a known-good control in the experiment loop.
The separate qualification loop still checks every known control's expectation.
Interruption, missing/unsupported observations, invalid/unsupported grading and
accounting stops retain five unlaunched slots without a retry or replacement.
Missing/unsupported observation scenarios declare adapter injections after real
CLI execution. Threshold and unknown-usage scenarios declare host accounting
injections; their native usage, submissions and grading stay intact.

The shared scheduler handles ordering and accounting. The campaign protocol
component owns frozen preparation, data-only artifact authentication and dispatch
claims; the existing campaign loop owns all launches and evidence collection.
Task adapters own prompts, fixtures, controls and grading. The Codex adapter owns
CLI behavior, authentication handoff, event parsing, access observations and usage.
Models/settings remain explicit profiles. Existing SkillEvaluator/Harbor native
collection and the consolidated renderer remain the only report path. New source
identities version the changed implementation; old definitions and receipts stay
unchanged. Dependency work remains separate under issue #95.

### Stop policy and retention

Before every launch, persist the slot and verify exact source, protocol, task
checksum, preparation, environment baseline and observed cumulative usage. A
measured task failure continues. Infrastructure failure, cleanup failure, missing
grading or essential runtime/submission evidence, unsupported runtime protocol,
unavailable/unsupported grading and unknown/invalid usage stop further launches.
The protocol lists the exact reasons. Invalid submissions stay invalid, never
become measured zeros. There is no resume or replacement command.

Each attempt has a 600-second agent bound and a 1,200-second outer native launch
bound. Existing native teardown gets 80 seconds before forced termination.
The protected job has a 155-minute deadline, leaving room for six bounded launches,
preparation, report collection and cleanup. Atomic fsynced ledgers plus an appended
transition journal retain all six slots across interruption. Native outcomes,
produced submission digests, exact safe submissions, redacted CLI observations,
descriptors, cleanup and public report inputs are retained, including after stops.
Fixture solutions remain trusted-host inputs; live tasks receive no solution,
reference implementations, mutants or protected grader files.

### Proposed budget and future authorization

Official OpenAI [model pricing](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
was checked November 9, 2026: $2 input, $0.10 cached input and $10 output per million
tokens at standard short-context rates. Prompts over 272K input tokens have 2x
input/cache and 1.5x output rates. The unchanged adapter conservatively applies
that premium when cumulative input exceeds 272K; cumulative CLI usage does not
identify exact per-request billing, cache-write charges or service-tier charges.
Provider authentication, account access and invoice charges remain unverified.

Propose $3 estimated model usage for six attempts, using $0.50 per attempt as a
planning allowance. The earlier twelve-attempt cohort estimated $0.7136678 total;
that historical observation is not a forecast or invoice. Stop subsequent launches
at $5 cumulative estimated usage, with a $3 overshoot reserve inside an $8 planning
allocation. Slot count, no retries, runtime bounds and the scheduling threshold
are enforced. The dollar allocation/reserve are planning estimates. An in-flight
request can exceed the threshold and reserve; there is no enforced billing cap.
CI charges are separate. Reserve never buys extra attempts.

Only a successful final-source qualification artifact may fill these fields:
`QUALIFIED_SHA`, `PREPARATION_ARTIFACT_ID`, `PROTOCOL_DIGEST`, and a fresh unique
`DISPATCH_NONCE`. [PR #126](https://github.com/thetechgy/agent-engineering-baseline/pull/126) records
the concrete values once qualification completes.
A future approval must identify them together. The exact future operator command
is below; **do not run it under the current authorization**:

```sh
ALLOCATION="campaign-${QUALIFIED_SHA}-boolean-effectiveness-v1-prep${PREPARATION_ARTIFACT_ID}-usd8-${DISPATCH_NONCE}"
test "$(gh api repos/thetechgy/agent-engineering-baseline/git/ref/heads/experiment/boolean-skill-effectiveness --jq .object.sha)" = "$QUALIFIED_SHA"
gh workflow run evaluation-campaign.yml \
  --repo thetechgy/agent-engineering-baseline \
  --ref experiment/boolean-skill-effectiveness -f "allocation=$ALLOCATION"
```

Proposed approval wording:

> Authorize exactly one dispatch of `evaluation-campaign.yml` at `QUALIFIED_SHA`,
> consuming preparation artifact `PREPARATION_ARTIFACT_ID`, protocol
> `boolean-effectiveness-v1` with digest `PROTOCOL_DIGEST`, and allocation
> `ALLOCATION`. This approval covers both that dispatch and its matching
> `skill-benchmark` protected environment gate. Permit at most six serial attempts,
> three current and three absent, without retries, replacements or continuation.
> Accept the $3 usage estimate, $5 scheduling threshold and $3 overshoot reserve
> within an $8 planning allocation, understanding these are not a provider billing
> cap. No judges, skill changes, dependency upgrades or other paid work are covered.

Authentication verifies repository/workflow/source/attempt, prior successful
preparation producer, archive digest and bounded data-only extraction. Actions
history rejects a second dispatch of the same allocation, including after failure;
an exclusive local claim also rejects repeated execution in one job. A workflow
rerun is refused. The live runtime accepts only the protected workflow's receipt;
provider/probe overrides are refused. Credentials are delivered only to its native
attempt subprocess after fresh preparation consumption. A future approval includes
the matching protected gate; this preparation grants neither approval.

Remaining live boundaries include actual provider authentication, live event forms
outside the qualified Codex exec subset, and billing. Unexpected events fail
closed and retain available evidence. Non-forwarding probes establish neither
model effectiveness nor arbitrary provider or CLI-event compatibility.

## Codex 0.167 event correction and retained recovery

The six-slot allocation at `97124cf` is consumed and closed. Live run
[42695478931](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42695478931)
launched one current-arm attempt, then stopped on `item.started/file_change`.
No grader ran; five positions stayed unlaunched. Its original record remains
unsupported/unmeasured. No retry, replacement or continuation is authorized.

The owning adapter follows the pinned [Rust exec event definitions](https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/exec/src/exec_events.rs)
and [processor](https://github.com/openai/codex/blob/086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a/codex-rs/exec/src/event_processor_with_jsonl_output.rs).
The Rust implementation supports started/in-progress and completed file changes;
its tests also cover completion-only records. The release's TypeScript item type
and Rust comments describe completion-only edits and omit part of that lifecycle.
The implementation, retained trace and native qualification determine support.

| Event | Representation and boundary |
| --- | --- |
| Command start/update/completion | Existing `exec_command` action, native ID, exact supported shell wrapper, final aggregated observation and integer exit code; missing/changed starts remain rejected |
| File-change start/completion, or completion-only | Native `file_change` action, ID, reported paths, add/update/delete operations and completed/failed status; no fabricated shell command, patch body, exit code or file contents |
| Agent message / reasoning summary | Native text or summary; no invented independent model-call count |
| Plan start/update/completion | Informational events with original items and completion flags; never an action or evidence that every item succeeded |
| Nonfatal item/error | Retained informational warning, regardless of message prefix |
| Stream error / turn.failed | Recognized terminal runtime failure, never a measured task failure |
| MCP, collaboration, web-search and unknown forms | Unsupported; no enabled capability or interpretation is inferred |

Commands without an observed start or integer terminal exit code remain unsupported
or incomplete. File-change updates, extra file-change fields, mismatched paths or
operations, duplicate IDs, incomplete lifecycles and events after a terminal turn
remain rejected. Exec file-change payloads omit patch contents and move targets;
the adapter cannot recover those absent details. Raw trace digest and event line
references link every normalized action to its source. New launches capture JSON
stdout in `codex.txt` and diagnostics in `codex-stderr.txt`, with both retained and
hashed. Failed native edits can emit multiline router errors to stderr; those are
diagnostic data, not JSON events. Unknown or non-JSON stdout still fails closed.
The historical authenticated trace retains its original merged bytes unchanged.
This is bounded support for the frozen CLI/profile, not universal event or
provider compatibility.

The existing Boolean CLI probes now request real code-mode `tools.apply_patch`
operations through the non-forwarding endpoint: add the task submission, add,
update and delete an auxiliary output, then attempt an add to the existing
read-only input directory. Qualification requires four completed edits, one failed
edit and all three operation kinds in actual native events. Shell file writes or
handcrafted JSONL do not satisfy that check. The gh probes keep their original
command transport; their grader still rejects an unapproved native file-change
action. Parser fixtures are separate from these native observations.

Retained recovery uses the existing campaign entry point, scheduler, native
SkillEvaluator/Harbor verifier, retained-data admission and consolidated renderer:

```sh
"$SKILL_CURRENT_PYTHON" -B .github/scripts/evaluation_campaign.py replay \
  --definition .github/evals/campaigns/boolean-retained-v1.json \
  --output "$EVIDENCE/retained-campaign-replay"
```

The pinned corpus authenticates artifact `13708468986`, archive
`sha256:0d9cc2aa7125f86656224251e4c84531b5dfd72fd211c1e8b079513a27112deb`,
source revision `97124cf6b09d2acd4bda6243d0345dff06aea989` and the unchanged
471-byte submission `sha256:3215b6097fa3e5f592989f2b8f4523207e28ebd4893cc7d11437b19189795981`.
The raw trace is parsed as data. None of its recorded commands is executed.
The native oracle copies only the exact retained submission, then the original
frozen inputs, reference, five mutants, grading criteria and offline verifier
perform grading. A valid failing grade is retained as a measured result.

The recovered native result at corrected adapter revision `2d1dfe9` passes the
reference and detects `above`, `highest`, `lowest` and `zero`. It misses
`integer-result`, yielding 4/5 defect detection and primary quality 0/1: a valid
measured failure. [Retained replay evidence](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42705785116/artifacts/13712424339)
records unchanged submission hashes, completed cleanup and byte-identical report
reproduction. This successful job is separate from its superseded parent run's
inconclusive full qualification; PR #126 carries final-head CI evidence.

The separate retrospective identity records the original run/slot/record/capture,
submission and raw-trace hashes, and corrected adapter revision/digest. Original
public bytes stay intact beside the retrospective report. Only the current arm
is enrolled. The paired collector retains unavailable absent-arm metadata; it
neither launches nor invents an absent grade. The comparison table names only
the enrolled original arm. This is not a new model attempt or completion of the
original six-slot experiment, and cannot establish skill benefit.

The existing workflow runs this one retained grade in a credential-free job,
using the same campaign execution/reporting code. It separately runs native
file-edit controls and historical task-family qualification. No model secret,
paid dispatch, protected live gate, judge, production or Pages publication is used.
The concrete recovery result and exact-source receipts are recorded on
[PR #126](https://github.com/thetechgy/agent-engineering-baseline/pull/126) and in
the authoritative checkpoint. After bounded availability checks and recovery of the same signed package
sources, native qualification passed at `af4dd66` in
[run 42713098769, attempt 2](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42713098769).
[The native receipt](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42713098769/artifacts/13721147577)
retains fourteen real native edit probes, stdout/stderr evidence and all fourteen
reproducible report pairs. The same-source retained replay confirms reference
correctness, 4/5 defects and primary quality 0/1 with unchanged bytes. Earlier
HTTP 503 acquisition failures remain distinct failed records. No mirror, pin,
grading, skill, isolation or adapter change was needed for this recovery. Final
CI status and documentation-only source equivalence are recorded on PR #126.
The evaluator's diagnostic-rerun cancellation rule was also corrected using
Validate's existing guard, with a failing-before regression. Its complete native
cohorts, gh shards and canonical report passed at `e196937` in
[run 42724173254](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42724173254).
The [canonical report receipt](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42724173254/artifacts/13724828199)
and the earlier shared/historical receipts retain their actual execution revisions;
documentation descendants are not relabeled as native execution. Any future
experiment requires a separate decision.

## Declared return-contract candidate (review preparation only)

The [frozen candidate plan](../pester-return-contract/PLAN.md) selects immutable
current/candidate snapshots through the existing definition `source` field and
pins each content identity in a new profile's `skill_source` binding. The shared
scheduler/runtime has no task assertion semantics. `batch-summary` is a task-owned
adapter reusing the existing runner/grader. Existing profiles retain their bytes;
source-code changes get appended successor identities, never rewritten grades.

Use development v1 and transfer v3: for each case pass its current and candidate
`pester-return-*-controls-v*.json` definitions together to `qualify` (four leaf
records). The matching prospective definitions/protocols freeze three repetitions
per arm. Acquire fresh verified Compose configuration in a preceding workflow
step before each `prepare`; consume both pairs with `check-preparation` on a
fresh runner. Earlier v1/v2 transfer identities remain historical.

[Credential-free native qualification](../pester-return-contract/EVIDENCE.md#native-qualification-completed-for-review)
completed for all four source/case combinations, including scheduling stops,
downloaded-artifact admission, report reproduction and cleanup. Its receipt
names the actual executed revision; documentation descendants are not relabeled
as native runs and do not bypass exact-revision live gates. All live counts
remain zero. The four paired comparisons propose 24 future model attempts with
duplicated absent baselines and an indirect current/candidate comparison; this
pass requests review, without spending approval.

## Return-contract integration and execution proposal

The merged return-contract experiment uses the existing reusable live workflow,
with a `campaign` choice from [selections.json](selections.json). Every preparation,
authentication, consumption and live command resolves that reviewed identity.
Inputs pass through environment variables and argument arrays. They cannot select
arbitrary files or shell programs. The default remains the historical Boolean
selection; return-contract commands must always specify their exact selection.

The registry admits the shared workflow's `preparation/evidence` and the existing
return-contract producer's `current/evidence` or `candidate/evidence`, with the
matching case artifact name. Admission authenticates repository, workflow, exact
revision, successful producer attempt, artifact name, expiration, size and digest
before bounded extraction. It validates the frozen proposal and complete scheduler
receipt, then moves the selected subtree (including sibling scenarios) to
`downloaded/preparation/evidence`. That canonical location is used by both the
fresh preflight and live receipt. Full fresh staging/deployment/descriptor and
public HTML reproduction checks remain mandatory before credentials are delivered.
An allocation binds the source, selected protocol, artifact ID and nonce; its
receipt also binds definition and selection digests and the original internal
location. First-dispatch history and exclusive claims reject reuse and reruns.

Executable integration changes require new preparation. Appended `selection-v1`
profiles retain all earlier profiles and grades. PR #127's released Pester evidence,
22-line candidate, controls and frozen task inputs are reused only where unchanged;
its old native receipts are never relabeled as this source's execution.

### Qualification and merge refresh

The existing return-contract qualification workflow prepares all four definitions
without credentials. First verify that no suitable run already exists for the
exact intended source. After review and merge, refresh with this existing command,
checking main rather than substituting a newer source silently:

```sh
REPO=thetechgy/agent-engineering-baseline
QUALIFIED_SHA=$(gh pr view 128 --repo "$REPO" --json mergeCommit --jq '.mergeCommit.oid') &&
printf '%s\n' "$QUALIFIED_SHA" | rg -q '^[0-9a-f]{40}$' &&
test "$(gh api "repos/$REPO/git/ref/heads/main" --jq .object.sha)" = "$QUALIFIED_SHA" &&
printf 'Preparation source: %s\n' "$QUALIFIED_SHA" &&
gh workflow run pester-return-qualification.yml --repo "$REPO" --ref main &&
gh run list --repo "$REPO" --workflow pester-return-qualification.yml \
  --commit "$QUALIFIED_SHA" --limit 5
```

Verify the completed producer's actual head equals `QUALIFIED_SHA`; refuse drift.
Obtain both artifact IDs from that successful producer. On the same exact source,
run four **credential-free** inspections of the existing artifacts through the
reusable workflow, one selection per inspection:

```sh
test "$(gh api "repos/$REPO/git/ref/heads/main" --jq .object.sha)" = "$QUALIFIED_SHA" &&
gh workflow run evaluation-campaign.yml --repo "$REPO" --ref main \
  -f campaign=pester-return-development-current-v1 -f "preparation_artifact=$DEVELOPMENT_ARTIFACT"
# Repeat with development-candidate-v1 and the same development artifact;
# then transfer-current-v3 and transfer-candidate-v3 with TRANSFER_ARTIFACT.
```

`preparation_artifact` is accepted only by credential-free inspection; both live
jobs require it to be empty. Inspection authenticates and consumes through the
same acquisition/admission/check code as live, but never creates or reserves an
allocation. It has no protected environment or model secret. It reproduces the
selected aggregate HTML from retained public inputs and saves admission, staging
and reproduction evidence on a fresh runner. Download and independently verify
archives and essential machine/HTML records before proposing paid execution.
A source-changing correction needs fresh exact-revision preparation, not a relabel.

### Pair checkpoints and budget

Use the frozen order: development current, development candidate, transfer current,
transfer candidate. Each six-slot schedule is present/absent, absent/present,
present/absent, with three repetitions per arm. Retain each pair's own absent
baseline and all per-defect outcomes. Transfer is output-informed, not an untouched
holdout. No candidate adoption follows from qualification or an exploratory result.

Before starting the next dispatch, the operator must verify that the prior pair
completed with six measured outcomes, including legitimate task failures; essential
submissions, grading, native observations, accounting, reports and cleanup must be
present and consistent. Review cumulative observed usage against the approved
planning assumptions. An operational stop, missing evidence, unknown usage or
failed cleanup ends the sequence pending a new decision. A fresh pair must never
bypass that stop. No automatic four-pair launcher is provided.

Machine enforcement covers exact selection/source/artifact/receipt, six serial
slots per dispatch, no retries or replacements, 600-second agent bounds,
1200-second launch bounds, job timeouts, identity/evidence/cleanup/accounting stops
and the $5 estimated-usage scheduling threshold per pair. A valid measured task
failure permits the next slot. Cross-pair order, evidence/usage review and stopping
the entire sequence are operator-enforced. The four $5 thresholds sum to $20 but
do not form an enforced global ceiling.

Official OpenAI [model pricing](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
and [pricing](https://developers.openai.com/api/docs/pricing) were rechecked
November 10, 2026: standard short-context input/cached-input/output remain
$2/$0.10/$10 per million tokens. The frozen settings need no price revision.
The adapter's existing cumulative-input premium above 272K is a conservative
estimate, not per-request billing reconstruction. Native usage does not identify
cache writes or actual invoice/service-tier charges. The historical 12-attempt
cohort estimated $0.7136678. Recomputed token observations from the recent
[six-attempt Boolean run](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42744596001)
estimate $0.2740062 total ($0.0409219-$0.0510054 per attempt). Those reused-task observations do
not forecast the transfer task. $0.50 per attempt remains the planning assumption.

Each pair retains $3 estimated usage, a $5 scheduling threshold, $3 overshoot
reserve and $8 planning allocation. Across four pairs this is **$12 estimated
usage and $32 planning allocation**. Reserve is $12 total and buys no extra slots.
In-flight work may exceed thresholds and reserves. Planning allocations are not
provider billing caps. CI costs are separate from model usage and these figures.

### Concrete review proposal

The single four-row [execution proposal in draft PR #128](https://github.com/thetechgy/agent-engineering-baseline/pull/128)
records exact definition/protocol digests, present-skill identities, qualified source,
producer run, preparation artifact/digest, registered internal and canonical
locations, expiration, six-slot schedules, fresh proposed allocations/nonces and
per-pair budgets. Its four exact paid dispatch commands are **unrun** and each
checks the remote source before dispatch. Run them individually only after separate
authorization, with the checkpoint between pairs. The proposal also supplies one
combined future approval statement for exactly those four dispatches and matching
`skill-benchmark` gates. It excludes retries, replacements, continuation after an
operational stop or beyond 24 slots, judges, adoption and unrelated paid work.
Proposed identifiers are unreserved; fixture authentication claims no paid allocation.

The checkpoint remains the decision record; this guide owns the procedure and the
PR retains exact-source evidence and commands. A pending, failed, cancelled or
expired receipt does not qualify execution. Review/merge is the next decision.
A future merge SHA needs the mechanical refresh above, even after a qualified
PR-head proposal; that proposal grants no authorization for the merge revision.
