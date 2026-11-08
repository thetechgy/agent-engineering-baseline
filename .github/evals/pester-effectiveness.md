# Prospective Pester skill-effectiveness preparation

This exploratory protocol starts at merged main `521a00c` (PR #121). It reuses
SkillEvaluator 0.8.0, Harbor 0.24.0, APM 0.35.0 and the exact
[candidate dependency profile](evaluator-candidate.json). The
[Codex runtime contract](codex-pilot.json) remains Codex 0.167.0,
`gpt-6.1-sol`, High reasoning, PowerShell 7.6.9 and Pester 6.2.0.
CLI archive, executable and helper hashes, evaluator source/patch/lock, pinned
container base, apt snapshot and package versions remain unchanged. Production,
Pages and skills are unchanged. No previous paid allocation applies.

## Cases and hypotheses

| Case | Real task and relevant skill guidance | Observable contract and likely weakness |
| --- | --- | --- |
| `pester-003` | Repair the public endpoint module suite. The skill's Importing Scripts and Modules and Mocking and Invocation Verification sections describe matching module scope, exact calls and parameter filters. | Healthy and unhealthy results, original returned target, exactly one private transport call with the requested target. Wrong scope, output-only assertions, omitted interaction checks or incomplete Boolean coverage can miss faults. |
| `pester-004` | Repair the apparently green boundary suite. The skill's Discovery and Scope sections place test-tree data in `BeforeDiscovery` or inline data, with runtime setup in `BeforeAll`. | Execute checks at 0, 1, 65535 and 65536. Zero discovered cases, a regular-port-only test, or one omitted boundary misses required work. |
| `pester-001` | Retained integer-collection task. | Compatibility/regression qualification control only; excluded from the twelve proposed primary attempts. |

Prompts and public inputs are unchanged and identical between arms. Neither prompt
invokes the skill. No points depend on syntax, quotations, verbosity or test count.
The independent verifier accepts the existing safe language subset; unsupported
constructs remain unmeasured. External module mocks, parameter-filtered mocks, `InModuleScope`, classic and
standalone assertions, discovery data, nested inline data, runtime iteration and
explicit boundary checks are qualified. AST restrictions and separate offline
unprivileged verification remain intentional; they are not general PowerShell support.

The prospective `pester-effectiveness-v3` admission/grader profile preserves historical versions.
It credits mutant detection only when the reference passes and the mutant has
recognized assertion failures or the pinned Pester dependency-parameter mismatch,
with no discovery/container failures. Generally broken submissions receive no
mutation credit. Each mutant's
outcome is retained. The module adds double-call, wrong-returned-target and
unhealthy-result mutants to the two original missing-call/forwarding mutants.
The six variants fit the unchanged 220-second case budget (30 seconds per worker,
15-second admission); timeout remains unavailable, not a quality zero.

Version two corrects a pre-live qualification gap: parameter-filtered mocks can
legitimately reject incorrect forwarding through Pester's no-matching-mock error
inside a test body before reaching an assertion. V1 counted only assertion
failures and missed that rejection despite a passing reference. V2 records
assertion versus recognized mock-parameter mismatch per defect, requires a
passing reference and complete test execution. Skipped, nonexecuting, discovery,
container, timeout and infrastructure results remain unmeasured. It recognizes
only the pinned Pester 6.2.0 no-matching-mock prefix for the supplied module
dependency. Other non-assertion mutant failures remain unsupported and unmeasured.
Its mutation and joint-quality
metrics have new v2 identities; reference correctness keeps its unchanged v1
identity. V1 and cancelled tooling profiles remain registered with their original
hashes and require their retained source snapshots. The error-prefix recognizer
is a narrow runtime maintenance obligation, checked against the pinned Pester
source and real execution. No agent output was inspected
to choose this correction, and no skill-effectiveness inference ran.

Version three adds only safe, project-scoped Pester APIs used by the frozen
guidance: invocation `-ExclusiveFilter`, `Mock -Verifiable`, commandless
`Should-Invoke -Verifiable` in the Probe case, `InModuleScope Probe -Parameters`,
and `Should-BeEquivalent`. Target/module validation, protected-state restrictions,
recursive AST checks and verifier isolation remain in force. Ordinary named and
positional argument ordering and classic invocation assertions are accepted.
The bounded execution-profile supplement is identical between arms. Native
positive controls combine these forms; negative controls reject unrelated
assertion flags, out-of-project targets, verifiable checks outside the Probe case and protected
parameter keys. V2 metric definitions and outcomes remain unchanged; v3 has a new
admission digest, not a new quality scale. V2's complete native qualification is
retained separately from the final admission extension.

Native qualification includes strong alternatives, substantive weak work, four
single-boundary omissions, healthy-output-only and healthy-call-only work, real
assertion failure, unclassified mutant failure, wrong mock scope, broken discovery, missing submission,
unsupported reflection, CPU/wall timeout and missing runtime. The omission controls
must pass the reference and miss exactly their corresponding off-by-one mutant.
Module controls separately expose bypassed calls, double calls, target forwarding,
returned target and missing unhealthy checks. The exact matrix is captured before
execution, then compared with actual verifier results. Reference failures receive
no mutation credit. Failure classifications and raw fallback reward zeros remain
separate from admitted measurements.

## Exposure and later confirmation

These are reused public cases, not held out. Both appeared in the October 26
subscription-funded text-only exploration; its native replay stopped at an
infrastructure failure on `pester-004`. Later deterministic oracle qualification
also exercised both. PR #121's live model comparison used `pester-001`; both
unchanged submissions passed the corrected retrospective verifier and detected
2/2 mutants. That established a comparison path, not skill advantage. Original
unsupported outcomes and the post-output-inspection limitation remain unchanged.

The hash-frozen `pester-confirmation-v1` scheduling-window variant is reserved
outside this cohort's agent contexts. Its different values, command and parameter
provide four independent boundary faults and strong/weak controls for later
confirmation. It is newly authored and unexecuted by an evaluated agent, derived
from the discovery contract rather than a wholly independent task family. Its
public repository location is not secrecy or protection against provider
contamination. Before later confirmation, qualify its graders without viewing
revised-skill outputs and keep it outside skill-revision development contexts.
It is not part of the current twelve attempts or current qualification claims.

## Matched deployment and execution proposal

The single entry point below stages independent clean task environments using
native `apm install --only apm --target codex`, including supporting files. It
checks the full deployed file manifest, stages both arms through SkillEvaluator,
and compares every staged member: only the target skill directory differs.
A second clean APM deployment must reproduce every task hash. The live-compatible
agent contexts contain public inputs, runtime and target skill only; oracle
payloads, retained submissions and verifier controls stay outside them. Oracle
qualification contexts are separate and explicitly labeled. Independent Harbor
containers prevent cross-arm home, output or process reuse.

The preparation artifact freezes exact task checksums, parsed and raw descriptors,
prompts, deployment manifests, runtime/evaluator identities, grader/fixture digests,
source revision, expected control outcomes and the ordered twelve-attempt proposal.
Run three independent trials per arm per primary case. Odd trials use 003 then
004; the middle trial reverses case order. Arm order alternates within case and
trial, balancing first arm across the two cases. Run sequentially at the same
2 CPU, 2048 MiB, 256 PID and 600-second agent limits. Use the qualified
`docker-external-openai-v3` lifecycle policy, identical endpoint/configuration and
no MCP, web search, other runtimes, judges or subagents. Access to a skill proves
availability only; observed reads are producer-reported activation evidence.
They do not prove following its instructions.

No automatic retry, replacement or best-of selection is allowed. Preserve an
agent crash or timeout as an execution failure with quality unavailable unless a
complete independent grade exists; preserve verifier/infrastructure failures in
their own classes with quality unmeasured. Stop the cohort on unsupported grading,
infrastructure failure, missing usage, deployment/runtime drift, security/cleanup
failure, or the spend threshold. Resume/retry requires a new explicit decision;
never replace a poor task result. Freeze grading before live outputs; an admission
gap requires retaining originals and versioning corrections, not silent rescoring.

Primary reporting is per case and arm: complete-reference pass, defect identities
detected/missed and joint quality. Compare equal-weight means only when all three
planned ordinals are measured for both arms. Show all failures and missingness.
Do not pool cases to conceal mixed outcomes. A tie provides no advantage; all-good
ties indicate a ceiling; mixed wins require case-specific investigation. Incomplete
populations support observations, not a complete comparison. No significance,
general effectiveness or autonomous skill-following claim follows from twelve
exploratory attempts. Activation, reliability, security and usage stay separate.

## Operator workflow and bounded live proposal

On the qualified source revision, with the existing pinned tools installed:

```sh
"$SKILL_CURRENT_PYTHON" -B .github/scripts/codex_pilot.py effectiveness --output "$EVIDENCE/pester-effectiveness"
```

`EVIDENCE` must be a new retained directory outside the checkout (on this host,
under `~/worktrees`). The existing Codex pilot Actions workflow runs this same
entry point without model credentials and retains exact submissions, receipts,
cleanup, deployment checks, public records and consolidated HTML. Reproduction
uses the existing `skill_report.py --input ... --analysis ... --output ...` CLI
with the included public evidence and saved analysis. Qualification observations
are deterministic fixtures, never future agent results or production history.

The artifact's `frozen-proposal.json` binds the proposed live run to the qualified
40-character source revision. **This preparation action never launches live effectiveness execution.** The old pilot's `pilot-...-usd10` approval only permits
its original compatibility pair and cannot authorize this new cohort. A future
explicit authorization must name this protocol, exact qualified commit and twelve
attempts; delivering credentials or approving an environment gate remains separate.

Propose $6 expected usage, stop before starting another attempt once cumulative
estimated usage reaches $10, and retain $5 reserve within a $15 planning allocation.
These are planning estimates, not a token cap or actual invoice. At the checkpoint's
frozen prices ($2/M input, $0.10/M cached input, $10/M output), 100K uncached input
and 30K output per attempt would cost about $0.50, or $6 for twelve attempts.
Retain the existing conservative long-context premium estimate. Any single request
can overshoot the observation threshold; do not promise a hard billing cap.
Unknown usage blocks further launches. No reserve may fund additional attempts
without another decision. Recheck provider availability and pricing before asking
for live approval; do not silently change the frozen CLI, model or dependencies.

After results, investigate concrete missed requirements and execution weaknesses.
Revise the skill only when evidence justifies it and the user authorizes that work.
Then freeze absent/current/revised arms with matched tasks, the regression control
and an independently frozen unseen confirmation variant. Require no meaningful
regression, retain mixed/negative results, and separate exploratory diagnosis from
confirmation. No revisions are authorized now.

Maintain the versioned fixture transformation, exact control matrix, APM byte audit,
source/profile hashes, public admission and report reproduction together. Changes
to these or the supported runtime require fresh credential-free qualification;
historical identities and retained tooling remain necessary for old reports.

## Qualified execution path (credential-free implementation follow-up)

The `cohort` action executes this frozen v3 protocol. Its v4 evidence profile
versions the changed runtime producer and reporting admission, retaining v3 grading,
metric definitions, task inputs and every historical profile. The compatibility
producer likewise has a new retained-v6 runtime identity. The preparation command
above remains credential-free. `qualify-cohort` runs the actual twelve-entry
scheduler through the pinned Harbor single-trial CLI, released Codex and independent
native verifier with non-forwarding loopback responses. Answers are supplied by
the trusted host at probe startup and remain outside live images and contexts.
Fixture records use `skill_effectiveness_probe`, separate from live effectiveness.

After separate authorization, the one operator entry point is the existing workflow:

```sh
gh workflow run codex-pilot.yml --repo thetechgy/agent-engineering-baseline \
  --ref feat/pester-effectiveness \
  -f cohort_allocation="cohort-QUALIFIED_SHA-pester-effectiveness-v3-prepARTIFACT_ID-usd15-UNIQUE_DISPATCH_NONCE"
```

Replace the uppercase fields with the exact final qualified source, authenticated
preparation artifact ID and a unique 8–40 character alphanumeric/underscore/hyphen
nonce named in the approval. Leave `allocation` empty. **This command is not
currently approved.** The workflow has no default cohort allocation. Its
credential-free jobs prepare, execute fixtures, reproduce reports and consume the
artifact without secrets or an environment approval. A separately requested live
cohort authenticates the previous successful preparation's repository, workflow,
source, attempt, artifact identity and archive digest through GitHub read APIs;
bounded extraction treats all downloaded content as data. It rejects changed code,
old pilot allocations, workflow reruns and any later dispatch reusing the allocation.
The first matching dispatch consumes the allocation even if it fails before a
launch. A new dispatch or nonce requires a new decision. No persistence service is
introduced: existing Actions run history and artifacts supply the dispatch claim.
Unavailable or incomplete history fails closed.

Only after authentication and fresh preparation checks does `cohort-live` reach
the existing protected `skill-benchmark` environment. A further fresh identity check
precedes the step receiving the model secret. The runner repeats identity checks
before every launch. No credential or protected gate is used in qualification.
The exact internal command is:

```sh
"$SKILL_CURRENT_PYTHON" -B .github/scripts/codex_pilot.py cohort \
  --output "$RUNNER_TEMP/cohort-live" --approval "$COHORT_ALLOCATION" \
  --preparation "$RUNNER_TEMP/cohort-auth/downloaded/pester-effectiveness/evidence"
```

The runner writes all twelve identities as `unlaunched` in `attempt-ledger.json`,
then durably records each launch before starting one native trial. Each trial has
one exact task and arm, its declared ordinal, an independent container/home/output
namespace, and no Harbor job-level retry or concurrency. Checksums are checked before
and after execution. Original trial results are preserved; the pinned Harbor
`JobStats` builds a derived envelope over recorded trials, while the collector
retains six planned trials per arm and the ledger retains every pending entry. The existing native admission, public records,
analysis and consolidated renderer retain submissions, grades, usage, diagnostics,
policy and cleanup evidence. There is no resume or automatic continuation mode.
Interruption handling terminates the child with bounded teardown and attempts
partial collection. A hard runner loss can prevent final upload; neither missing
evidence nor an unfinished ledger authorizes a restart.

Accounting adds each observed attempt once. Cached input is a subset of total
input and is subtracted before uncached pricing; output is independent. The
unchanged conservative long-context estimate remains. At or above $10 cumulative
estimated usage, the next launch is refused. Unknown accounting also refuses the
next launch. The $6 estimate, $5 contingency and $15 planning allocation are
unchanged. The $15 allocation is not an enforced billing ceiling; an in-flight
request may exceed an observation-based threshold. Contingency authorizes no extra
attempts, replacements or retries. Provider invoices and cache-write charges
remain outside verified accounting.

On November 8, 2026, official [model documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
still listed `gpt-6.1-sol` on Responses, High reasoning, and standard prices of
$2 input, $0.10 cached input and $10 output per million tokens, with the documented
long-context premium. This is public availability, not verification of account
access, funding or rate limits. No authenticated provider request was made.

Qualification includes a complete twelve-entry real CLI/container fixture run,
measured passing and failing submissions, and short stopped cohorts for unsupported
grading, command failure and interruption. Threshold crossing, unknown accounting
and cleanup rejection also exercise real CLI/verification/disposal, followed by
explicit host observation fault injection; the original native observations remain
intact and labeled. Focused contracts check identity/allocation rejection and
replay. These are operational fixture results, not skill-effectiveness results.
Final feature commit, tested source, authenticated artifact and reproduction hashes
are recorded in the [authoritative checkpoint](EVALUATION-PLAN.md) and PR #122.
