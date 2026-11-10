# Declared return-contract candidate, frozen plan v2

Status: candidate and experiment prepared for review; no adoption or inference.
Base: current main `9f81a66b343f340b681759db8c7c38a4e9e016c5`.
The [candidate diff](candidate.diff), [source evidence](EVIDENCE.md) and
[immutable input manifest](freeze.json) are the review boundary. Neither default
`.apm/skills` nor deployed `.agents/skills` changes. Supporting skill files and
minimum-version/version-selection guidance are byte-preserved.

## Basis and hypothesis

The completed [comparison](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42744596001)
used the base above. [Artifact 13730584511](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42744596001/artifacts/13730584511)
has archive SHA-256 `e72a2dc40124dca828021143ec5acaa538e53a3c34dfb31def4314e82952ecfa`.
Its six valid submissions pass the reference and detect four defects, missing
`integer-result`. All use `Should-Be $Expected` without a return-type check.
All three current-arm attempts record full skill reads. These establish access,
not compliance, causation or benefit. The allocation is closed; these observations
are design evidence, never members of the proposed prospective population.

The original public task explicitly says the command returns a Boolean.
The integer-result implementation violates that requirement. Type detection is
contract coverage, not a requirement to reproduce an implementation choice.
Current main's skill is identical to the evaluated skill and already explains
expected-type coercion and new Boolean identity assertions. This is existing
knowledge needing an actionable decision rule and data-driven example, not a
missing Pester fact or evidence that the task/grader is invalid.

Hypothesis: mapping declared return types to explicit checks on raw results,
within each data-driven case, improves contract coverage without adding concrete
type restrictions where the contract permits alternatives. One candidate adds
that rule and a generic label-presence example. Equality and boundary/behavior
checks remain necessary. A verified assignability check precedes equality; it
never converts the actual result. This is an unproven intervention hypothesis.

## Cases and controls frozen before candidate output

No candidate model output has been observed. `freeze.json` binds both complete
skill snapshots, task prompts, inputs, references, mutants, controls, advice
checks, paired definitions, protocols and the unchanged model/runtime profile.
Changes to these inputs require a new plan version before observing output.
The reserved confirmation variant was not opened, inspected or consumed.

Development uses the unchanged `pester-004` public prompt and input files, with
the already reviewed five-defect Boolean-contract fixture. Its existing good
identity and typed-classic suites, value-only, type-only and broken-discovery
controls keep their original expectations. No task coaching or evaluator change
is introduced to create a candidate advantage.

Transfer/regression is `pester-transfer-batch-v1`, authored here from the written
public contract after this author had seen the development failure. It is a new
context, not an untouched independent holdout. No existing suitable case was
identified in the available public Pester task inventory. `Get-BatchSummary`
returns an object: `Enabled` must be Boolean; `Quantity` is a numeric value
clamped to 0..8, with no specified concrete numeric type. The reference uses
Int32 and Int64 on different supplied inputs. Prompts state only this contract
and supported execution operations; they name no assertion or candidate solution.
Protected reference/mutant/control material is kept outside agent context.

Transfer expectations, through the existing runner and grader:

| Control | Reference | Defect detections | Classification |
| --- | --- | --- | --- |
| good | pass, five tests | all five | passed |
| value-only | pass | all except enabled-integer | failed, measured |
| overrestricted | fail on permitted Int64 | zero credited | failed, measured |
| invalid | no usable execution | unavailable | invalid, unmeasured |

Five defects independently cover integer Enabled, wrong Enabled at zero,
Quantity offset, lower clamp and upper clamp. The overrestricted suite's failure
is a check against inventing a concrete Quantity type contract. Correct work
must accept every legitimate reference result; extra syntax, test counts or
resemblance to the example earn no quality credit. Existing strong development
controls and the transfer good control demonstrate two contract-specific styles.

## Prospective comparison

The native/report bridge supports one present and one absent condition. Use four
separate paired definitions, one per case/source; no new multi-arm orchestration:

| Case | Pair | Repetitions per arm | Attempts |
| --- | --- | --- | --- |
| development | absent/current | 3 | 6 |
| development | absent/candidate | 3 | 6 |
| transfer | absent/current | 3 | 6 |
| transfer | absent/candidate | 3 | 6 |

Total: **24 proposed model attempts**: six current, six candidate and twelve
absent. Each case duplicates three absent attempts across its two pairs. Do not
reuse or pool historical or duplicated baseline outputs. Current-versus-candidate
inference is indirect: show each present-minus-own-absent result separately,
then the descriptive difference between those paired differences, per case.
Unequal absent results remain visible. This is not a direct randomized comparison
between the two skills and supplies no broad effectiveness estimate.

The development v1 and transfer v2 paired definitions and corresponding
protocols freeze three trials and six serial slots per pair. Use case order
shown above. Within each pair the existing scheduler orders present/absent,
absent/present, present/absent. The matching development v1 and transfer v2 control definitions separately
qualify known controls with one repetition per arm; no model outputs enter those
runs. Qualified native components, settings and containment are reused unchanged:
Codex 0.167.0, gpt-6.1-sol, OpenAI, high reasoning, PowerShell 7.6.9, Pester 6.2.0,
APM 0.35.0 and the existing pinned evaluator/Harbor stack. Each pair differs only
in target-skill deployment. Across pairs the frozen skill source changes; prompts,
fixtures, graders, supporting files, runtime/model/settings and deployment path
match. Fresh native environments and exact APM/native manifests are required.

## Outcomes and decision rules

Primary quality per attempt is reference correctness AND detection of all five
contract defects. Report integer/type-defect detection separately (`integer-result`
and `enabled-integer`), reference correctness, every other defect, and observed
skill access. Preserve the development case's four previously detected defects.
Transfer quality must preserve Enabled behavior and Quantity values/boundaries;
rejecting permitted numeric types is a reference failure, not extra rigor.

Use planned denominators of three per arm in each pair. Invalid, unsupported,
timeout, infrastructure error, missing evidence, unknown accounting and unlaunched
slots remain distinct unavailable outcomes. Do not replace them or score them as
measured zeros. Show both usable numerators and planned populations. Continue
only after valid measured task failures; retain the existing stop, cleanup,
identity, accounting, no-retry and no-replacement policies. No judges run.

Support taking the candidate to a separately designed confirmation decision only
if all three candidate submissions in each case pass the reference, detect all
five defects, and accept permitted types; candidate primary/type outcomes must
improve over current on development and show a positive paired-difference change
on both cases, without loss of previously detected defects. This is a review
criterion, not automatic adoption. Reference regressions or overrestriction argue
against adopting this revision. A development gain without transfer, an absent
advantage, any material regression or contradictory evidence calls for revision
or rejection. A complete tie gives no demonstrated benefit; rejecting the change
is legitimate. Unavailable outcomes or materially different absent baselines make
the comparison inconclusive. Three repetitions are exploratory and cannot
establish broad effectiveness or a causal explanation of the historical miss.

## Credential-free operation and remaining limits

Reuse `evaluation_campaign.py qualify`, for each case with its current and candidate `*-controls-v*.json`
definitions together (two definitions, four oracle/probe leaf records), a new
persistent output directory, and the existing
pinned tool/Compose environment. It reuses APM/native deployment checks, independent
grading, native collection, evidence admission and consolidated report reproduction.
Then the existing `prepare` and `check-preparation` commands can qualify each
prospective definition against the non-forwarding endpoint. Every new native
phase needs the existing fresh verified Compose configuration. The command
structure is documented in [the operator guide](../campaigns/README.md).

This pass executes local controls through the production runner/grader and native
APM/task staging, without Docker launches. Full native container/CLI preparation
and downloaded-artifact/report reproduction for these new definitions remain
unqualified here; Docker is unavailable on this workstation. Existing qualification
receipts remain evidence only for their executed sources, not these new inputs.
The default hosted credential-free repository checks remain relevant, separately
from that limitation. No new hosted dispatch or protected gate is needed to
review the frozen candidate and plan.

Source/profile registration appends successors; historical profiles and default
active selections are unchanged. New `skill_source` bindings make immutable
current and candidate contents distinct in capture/admission. Task adapters own
prompts, fixtures and semantics. Skills own advice; runtime adapters own CLI,
authentication and events; model profiles own settings; shared orchestration owns
scheduling/accounting/retention/reporting. No assertion or skill-specific logic is
added to shared scheduling or runtime execution.

Every prospective definition still has `authorized_live_attempts: 0`; the runtime
profile has inference disabled. Protocol budget numbers retain the existing
planning envelope and are not a new allocation, price verification or spending
approval. No credentials, model inference, judge, paid workflow, closed allocation,
production/default deployment, Pages, merge or dependency change is authorized.
A later live decision would require complete exact-source credential-free native
preparation and separate authorization; this pass requests none.

One next action: review the candidate and frozen evaluation plan.

## Qualification revision audit

Revision v2 adds only a level-one heading to the transfer input README for MD041
and removes a duplicate blank line in the campaign operator guide for MD012.
The transfer prompt, public behavioral contract, controls, reference, mutants,
scoring, skill snapshots and 24-attempt comparison design are unchanged. The
heading changes task bytes, so transfer definitions/protocols/profiles have new
v2 identities. [The original freeze](history/ea26668-freeze.json) and
[all earlier profile digests](history/ea26668-profile-digests.json) preserve the
reviewed v1 state at `ea266683626dcfdf8b86884797fd2caa7564a6ba`. Old receipts do not
qualify v2 inputs. No model output was observed before either freeze.

Credential-free hosted qualification uses the existing campaign `qualify`,
`prepare` and `check-preparation` commands in a case matrix. Each case qualifies
both skill sources, then prepares both paired protocols using the non-forwarding
CLI fixture. A fresh runner consumes the same-run artifacts and reproduces the
control and scheduling reports. These are control executions, not any of the
24 proposed model attempts. No model credentials or protected environment is
available to these jobs.
