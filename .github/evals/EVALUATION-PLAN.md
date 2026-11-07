# Issue #95 dependency modernization checkpoint

This is the authoritative active checkpoint. The evaluator upgrade is merged through
[PR #119](https://github.com/thetechgy/agent-engineering-baseline/pull/119); the next
milestone is the opt-in live CLI compatibility pilot below.
The direct-Harbor assessment at `389f7222da8d425b95dad12003e1e6895500a397`
is historical evidence, not the implementation base. Production remains unchanged.

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

## Next group

The independent scanner group is merged through [PR #120](https://github.com/thetechgy/agent-engineering-baseline/pull/120):
SkillSpector 2.13.4 and Semgrep 1.184.0, with controlled collection/report evidence
and credential-free CI tracked there. Gitleaks 8.30.1 is already current. Bandit and
pip-audit remain evaluator-owned; Semgrep's exact MCP 1.29.0 constraint remains an
unresolved dependency gap. The candidate implementation and pins above are unchanged.
PR #120 also qualifies a narrow retained-adapter correction for caveated scanner
reports: findings survive while repository coverage remains incomplete.
[Compatibility evidence](https://github.com/thetechgy/agent-engineering-baseline/blob/chore/95-scanner-modernization/.github/evals/SCANNER-MODERNIZATION-95.md#retained-adapter-compatibility-correction)
records the before/after scans and reporting controls.

The next action is to define and obtain separate authorization for a bounded live
CLI/provider compatibility pilot before collecting judging or skill-benefit evidence.
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
remain enforced. The agent has two CPUs, 2048 MiB, 600 seconds, workspace-write
sandboxing, no command network access, no MCP, no web search and no subagents.
The evaluator's reviewed secure Docker and separate offline verifier remain in use.

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
stub-supplied sandboxed command, then receives a loopback-only refusal. This is
not provider authentication or inference. Both arm probes and the grading controls
must pass before the protected job becomes eligible. Native task checksums are
checked across launch; exact safe submissions and hashes, specific reasons,
sanitized command-stage diagnostics, command events, usage and cleanup are retained.
The usual public evidence, saved analysis and consolidated HTML remain the report.
No model judge, full dataset, production evaluator or history publisher is invoked.

### Proposed allocation and execution gate

Status: implementation and credential-free preparation in progress; **no paid
approval requested or inference authorized yet**. Exact-revision CI and complete
hosted preparation must pass before requesting the one concrete approval.

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
