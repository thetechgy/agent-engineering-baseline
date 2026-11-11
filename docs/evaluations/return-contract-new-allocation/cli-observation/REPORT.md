# CLI observation diagnosis and disposition

**Recommendation: ready for review toward merging the focused correction.**
There is no evidence that the historical DNS failure was persistent; both frozen
sources passed the fresh matched control. The owner has chosen to stop pursuing
a DNS-specific fix for now. This is an unreproduced historical DNS failure, not
proof of transience or a relabeled passing run. PR #131 remains unmerged and its
review status is unchanged. PR #130 remains draft and unmerged. All paid
allocations remain closed. The separate failed cohort qualification and any remaining CI must be assessed before merge.

## Historical sequence

[Job 130203029905](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42923193201/job/130203029905)
ran reviewed head `22b36d53e9ac7e329ef8c56dc9bdcefb468ca9df`, based on
`a8ab2e2e03a2989863a514df2a6b357c44fbc012`. GitHub metadata and the downloaded
[artifact 13813573476](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42923193201/artifacts/13813573476)
match archive SHA-256
`225993dc9f6b1d98198dc52c80588495553729674f7e3a69d16211954ce20348`.
The [bounded audit](historical-audit.json) retains source/native identities and
file hashes without changing the original evidence.

Both actual CLI tool commands failed at the first network assertion: curl exited
6 with HTTP `000` and `Could not resolve host: api.openai.com`. The other initial
network destinations were not reached. The probe aborted before printing its
complete boundary record or launching the detached delayed child. The `&&`
submission handoff did not run. The non-forwarding fixture nevertheless emitted
its final response, so the CLI recorded a completed turn and exit 0. That did not
establish tool-command success.

Harbor performed separate verification and attempted final environment shutdown.
The trusted host observation returned and retained the bounded Docker snapshot;
its full final-policy object was not serialized because the subsequent delayed
child-file wait failed. That host observation cannot substitute for the required
CLI-child observation. The delayed child was never launched, so its post-agent
network probe was never attempted. No present CLI-child observation was rejected
or lost. The native exception `Post-agent CLI child network observation unavailable`
is a later consequence, not evidence that prohibited egress succeeded.

The pinned SkillEvaluator collector projected failed-judge sidecars into unscored
`reward.json` diagnostics without `trial_id`. Shared admission applied the scored
reward identity guard and raised the still-later `Reward identity mismatch`.
This producer/consumer diagnostic mismatch masked the native failure in collection.
Original native events, error records and available observations survived; the
resource comparison confirmed disposal of both arms. No original CI result or
unmeasured outcome is relabeled.

## Matched baseline and reviewed head

[Run 42934540958](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42934540958)
executed the unchanged base and reviewed head sequentially on one fresh hosted
runner, using the existing two-arm native probe and actual pinned CLI with its
non-forwarding fixture. Both sources passed: four actual CLI sessions retained
valid delayed child observations and verified disposal. Both machine/HTML report
pairs reproduced byte-for-byte. [Artifact 13817429838](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42934540958/artifacts/13817429838)
matched SHA-256 `01587022748696a7c30123bccbdb777de925ce97e824549b6b65daf8bfa142be`.
The [independent comparison](matched-audit.json) records effective configuration,
source/build identities, observations and reproduction hashes.

Python 3.14.10, SkillEvaluator 0.8.0, Harbor 0.24.0, Docker 29.4.2, Compose 5.7.0,
CLI 0.167.0, parsed task/runtime configuration and all non-descriptor staged bytes
matched. Descriptor environment-key order differed without changing parsed values.
The production `sha256-typed-toml-v1` comparator independently verified equality
of both complete retained descriptors, including scalar types and unknown fields.
Separate builds had different image IDs; the base ran first and the reviewed
source could use build cache. These differences are retained, not declared
bitwise-equivalent environments.

The historical and fresh runs used Ubuntu 26.04.1/image `20261101.186.1` and runner
2.338.2, but the historical failure was in westus2 and the comparison in centralus.
Historical DNS state and packet responses were not retained and cannot be recovered
from the disposed worker. These successful controls do not demonstrate a natural
baseline failure or establish that the original DNS failure was transient,
pre-existing, harmless, or caused by the admission change. Unchanged components
alone are not the integrated disposition.

The first comparison attempt, [42933660759](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42933660759),
passed the base but could not start the reviewed source because Docker client
state had changed. That partial run is inconclusive as a comparison. The completed
run acquired fresh verified Compose client state for each source.

## Focused correction and qualification

Implementation is [PR #131](https://github.com/thetechgy/agent-engineering-baseline/pull/131)
at [`33d9535`](https://github.com/thetechgy/agent-engineering-baseline/commit/33d953536e95bc81178e726fb3fed95a80566c7d).
Shared evidence admission distinguishes the pinned collector's diagnostic
projection from a score. It requires the corresponding summary failure and
unscored failure record, validated native trial/task/checksum/configuration,
matching agent/arm/model/producer metadata, and matching native exception.
Diagnostics cannot carry measurements, details, a score or a passing raw reward.
They remain referenced data with `unknown` outcome and null/unavailable quality.
No trial ID is guessed, inserted or rewritten. Wrong claimed trial identity still
reaches the rejecting reward guard.

The CLI qualification adapter records the failed boundary command as primary,
including its actual trial member and exit code. Native shutdown failures and
secondary collection errors remain separate. A completed fixture turn does not
supersede a failed command. This is diagnostic/lifecycle infrastructure, with
no Pester-case workaround or change to grading criteria.

[Final native run 42937270892](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42937270892)
passed 86 hosted contracts, positive observation in both arms, and an explicit
missing-child control in both arms. The control makes the real CLI invoke the
existing probe with an invalid qualification argument; it fails before delayed
child launch. It fabricates no network result and is not a historical DNS
reproduction. Both failed attempts remained unknown with null quality, separate
primary-command/native-shutdown records, no readiness receipt and complete
resource disposal. [Artifact 13819268862](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42937270892/artifacts/13819268862)
matched SHA-256 `00c567bbf6fa02d9e6d93f4697d085fa5e93234994a0e950094ef6f6f3b26817`.
Both machine/HTML pairs independently reproduced; see the
[final native audit](final-native-audit.json).

Additional [faulted retained-fixture controls](retained-guard-audit.json) exercised
production `codex_pilot.run` and `PilotEnvironment.stop`. A wrong container ID,
changed policy hash, and a prohibited destination reported as curl exit 0/HTTP 200
were rejected. [Concurrent primary/secondary failure](primary-secondary-audit.json)
retained the CLI command as primary and chained/recorded a deliberate secondary
collector error. These offline controls replay transport and resource accounting;
they are not new CLI execution or native cleanup evidence. The separate native
controls supply actual execution and disposal evidence.

[Final native deadline run 42937277850](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42937277850)
passed empty, emitted, secondary-copy-failure, interrupted and normal controls.
[Artifact 13820320273](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42937277850/artifacts/13820320273)
matched SHA-256 `955f341a649e4cf998be76e9de81a14a0acea380e3ca4b2a4d248e6e574fc0fd`.
All five machine/HTML pairs reproduced. The fixture's native deadline remains
45 seconds; production remains 600 seconds. See the [lifecycle audit](final-deadline-audit.json).

All five Validate jobs passed at the final implementation head, including both
required checks and clean regeneration. The [frozen-runtime audit](final-frozen-runtime-audit.json)
authenticates component artifact `13819291610`, SHA-256
`7580523269910b204c3e308945d244f7ff6dc67134ed6602df87da5b512b71b6`.
All five positive, weak and invalid controls retained their expected outcomes
under PowerShell 7.6.9/Pester 6.2.0. Latest-stable compatibility checks remain
separate. Passing these checks does not disposition the historical DNS failure.

Final-head [admission qualification 42937278031](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42937278031)
passed two original-rejection reproductions, all 44 capability/rejection controls,
and the exact unchanged 1,536-byte replay. [Artifact 13821197697](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42937278031/artifacts/13821197697)
matched `sha256:13cc6c04d7065cf636fbde7936e089945f4834bde666b9ecbd4c2f9aefac0f8e`. All three machine/HTML report pairs reproduced.
The controls retain six passed, eight measured failed, 26 unsupported and four
invalid outcomes. The unchanged submission passed its reference and detected
5/5 mutants with five tests under PowerShell 7.6.9/Pester 6.2.0. Exact verifier
handoffs, retained originals and disposal were independently checked; see the
[admission audit](final-admission-audit.json). This remains an output-informed
retrospective grade of one current arm; no original paid outcome is replaced.

The [preservation audit](preservation-audit.json) confirms every reviewed profile,
active selection and metric is unchanged. New source successors preserve their
graders, fixtures and semantics. Protected skills, candidate/task content,
dependency locks, settings, production limits and isolation policy are unchanged.
The [workflow review](WORKFLOW-REVIEW.md) covers the explicit credential-free mode.
The [CI status receipt](final-checks.json) records exact-head successes and any
broader pending qualification separately. Cancelled superseded runs are
inconclusive and never substitute for final-head checks.

## Separate broader cohort-qualification failure

[Compatibility workflow 42937277898](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42937277898)
passed its original CLI preparation and fresh-consumption jobs. Its separate
[cohort scheduler qualification job](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42937277898/job/130250342944)
failed a deliberate `infrastructure` control. This is not a recurring DNS failure.
[Artifact 13822715004](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42937277898/artifacts/13822715004)
was authenticated as SHA-256
`f1d2ae882ec231bc423f74cd38a4b7baa8851942aabfb20c8f99bb12f22eced9`.

The real CLI deliberately exited 1; the adapter raised its existing RuntimeError
before recording `boundary_after`. The scheduler first selected
`execution_infrastructure_failure`, then its existing identity guard selected
`security_or_identity_drift` because the post-command observation was absent.
The qualification expected the former label. Exactly one fixture attempt launched,
eleven stayed unlaunched, cleanup completed, and the single public observation
remained unknown with every quality value unavailable. There was no extra launch,
passing policy result, numeric fallback grade or inference.

The [classification audit](cohort-stop-audit.json) executes the exact production
classification statements from main `a8ab2e2`, reviewed `22b36d5` and final
`33d9535` over authenticated native inputs. All three select the same later label;
the source is byte-identical. This is source-level replay, not a native baseline
rerun or a passing cohort qualification. The changed collector runs afterward
and does not cause this stop-label selection. The stricter identity guard and
qualification's expected label are not changed to force green CI.

This separate existing classification/expectation inconsistency does not weaken
the admission or observation safeguards delivered here. The original failing CLI
preparation path now passes; the focused native and admission receipts remain
valid. It is nonblocking for review of this focused correction, while full cohort
readiness and any future live cohort remain unqualified until their qualification
contract is reconciled. The failed workflow stays failed. CI is not all green.

## Historical normalization and report reproduction

The [historical normalization receipt](historical-normalization-receipt.json)
distinguishes original producer `22b36d5`, reporting-only normalizer `9434053`,
and public renderer `33d9535`. The intermediate source retained the historical
CLI runtime inputs and can admit the original raw capture with the corrected
diagnostic contract. This is a narrow reporting qualification, not complete CI or
new native execution at that intermediate source. Its broader failed/cancelled
checks remain historical evidence.

Final `33d9535` retains a separate raw runtime identity and correctly refuses to
relabel the old raw capture as current. It reproduces the resulting public
[diagnostic report](historical-diagnostic/consolidated/report.html) byte-for-byte.
Both historical trials stay unknown and unmeasured. Earlier exploratory local
normalization output is retained separately and is not the published qualification.

The [existing-report receipt](existing-report-reproduction.json) verifies the
original four-behavioral-record report and five-behavioral-record retrospective
report still reproduce exactly, including their inventories, flags and grades.
Their HTML digests remain `af83335d938115ab287abb54d65da41cb9fad015e386255743b77bb10fbf35b2`
and `a694626c12edaf9cd908d9a6a88e4c9499e9bd77afbb5c20b6d95f6532ee89c0`.
This separate diagnostic report is not pooled with the paid experiment results.
The unchanged transfer replay remains an output-informed result for one current
arm, not evidence of transfer benefit or candidate adoption safety.

To reproduce the diagnostic HTML, use the pinned evaluator Python with tooling
source `33d9535`, run its existing `skill_report.py` CLI with `--input` pointing to
`historical-diagnostic/public`, `--analysis` to its saved `analysis/analysis.json`,
and `--output` outside both source checkouts. Compare the emitted `report.html`
with `historical-diagnostic/consolidated/report.html`. Raw normalization instead
requires reporting-only source `9434053` and the authenticated original archive.
No producer artifact is executed.

## Remaining decision

The focused correction is qualified within the stated native and fixture scopes.
The historical DNS-specific failure did not reproduce in the fresh matched
baseline/head control, and no evidence establishes a persistent defect. The owner
has directed that DNS-specific investigation stop for now. No DNS-policy,
resolver, production timeout or dependency change is warranted by this evidence.
The underlying reason for the old lookup failure remains unknown.

This is nonblocking for review of the focused code because the opt-in admission
and frozen-grader behavior retain their independent qualification, while the
observation safeguard remains enforced. A missing actual CLI-child observation
still prevents readiness and keeps quality unavailable. Wrong identity and
policy-violation controls are rejected. The reporting change preserves the
failure instead of weakening a guard, manufacturing an observation or assigning
an ID. Merging this code would not waive the existing fresh preparation,
source/identity, isolation, cleanup or separately authorized live gates.

This disposition is not live-provider qualification or an inference authorization.
The original failed run remains failed. All required/Validate, focused native,
lifecycle and admission receipts are authenticated; the status snapshot separately
identifies broader CI still in progress. Review those terminal results before any
merge. Neither PR has been merged, and no review-status transition was performed.

**One next action:** review PR #131 at `33d9535` against these receipts, the
separate cohort-qualification limit and terminal remaining CI. Keep PR #130 draft and unmerged. No model
credentials, inference, paid gate, retry/replacement, allocation reopening,
candidate adoption, dependency upgrade or production-default change is authorized.
