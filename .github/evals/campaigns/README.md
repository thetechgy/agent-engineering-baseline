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
pilot source identity is v7 and the effectiveness source identity is v8, with unchanged historical grading
semantics. Campaign profiles have separate oracle and CLI-probe identities. Tests
compare all historical registry entries and production active-profile selections
with the merged base.

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
same campaign entry point, with a new persistent output directory:

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
`DISPATCH_NONCE`. The PR's verification receipt records the concrete values.
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
