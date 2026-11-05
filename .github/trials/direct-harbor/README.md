# Direct Harbor recovery trial

This branch-only trial preserves production SkillEvaluator 0.3.0 / Harbor 0.13.2,
APM deployment, static checks, historical scores and Pages. Source commit:
`cc0819f5dafc05610dd8c3293ce2f52744c66f1a`. The earlier launch-repair pass started from reviewed trial
commit `f61201a730746921abd17d8f8366dfd1505ad6f8`; the earlier failed live run executed
`11bf0db52f020271efc8b1e4c136f7795b480114`, not that packaging commit.

[The single report](results/report.html) and its [machine-readable results](results/results.json)
are authoritative for outcomes and spending. Report packaging is not native evaluation.
The launch repair reproduced the reserved-provider rejection and verified its
correction through stock Harbor/Codex. The user subsequently authorized the two
remaining paid smoke attempts despite unknown costs. Both sessions completed in run
42110435228 at `c5a430a`, but both verifier outcomes were `invalid/artifact`. Four of
four recovery slots are consumed; scheduling is disabled. This is launch evidence,
not a valid task comparison. The broader comparison is not authorized here.
Only reviewed metadata is published; previously rejected raw oracle content is not
repackaged. Raw agent transcripts, submissions, authentication files and environment
dumps are excluded from the live artifacts.

## Credential-free handoff and runtime pass

The credential-free pass started from `9146314` and supplied no real API credential
or inference. Its workflow had only handoff and report phases. The pass-specific
prohibition is now replaced by the separately authorized allocation checks below.
The ledger stays 4/4 recovery slots and 4/36 campaign slots; cumulative spending is
unknown. Historical estimates are not provider bills.

Three serial deterministic producers use the historical agent image/UID/workspace
and normal Harbor artifact collection and separate verification. They write a known-good
fixture, omit output, or write three invalid UTF-8 bytes. The supported `verifier.collect`
hook observes metadata before collection; the native manifest records download status;
a protected pre-grader probe records post-upload metadata. Contents are excluded.
The shared grader adds fixed admission reasons while preserving acceptance criteria,
`invalid/artifact` classification, numeric rewards and reference/mutant checks.

Historical live artifacts and Actions logs lack the native collection manifest and
raw rollout. Their `invalid/artifact` cause remains unresolved. New successful controls
cannot retroactively establish that the historical agent omitted its deliverable.
A confirmed missing deliverable is now a task-completion failure; correctness/mutation
metrics remain separate from that denominator and from infrastructure uncertainty.

The selected official stable CLI is 0.166.0, published 2026-10-29 and rechecked on
2026-11-05. Its canonical musl package SHA256 is
`1d44b28bc4ac9937d7d3532264baa68a507ce364956a0d4ebb856f331cdee254`.
The package stays intact under `/opt/codex`, including its code-mode host, executor,
ripgrep and resources. Harbor stays 0.25.0 and other dependencies remain pinned.
`runtime-profile.json` selects `gpt-6.1-sol` with `high` reasoning for every future arm.
This is a new comparison profile, not a skill-only change to historical evaluations.

Runtime probes use sentinel authentication and a non-forwarding loopback refusal
endpoint inside a network-disabled agent container. They check real CLI startup,
prompt delivery, API authentication shape, model/effort selection, retries and idle
timeout; strict native configuration loading covers the budget setting. No successful
model task or budget exhaustion is claimed. The custom provider alias does not enable
built-in-only internal metadata, which is not exposed as configuration.

Pinned Harbor/LiteLLM has no price entry for GPT-6.1 Sol. Future native costs remain
unknown when unavailable; raw usage categories are separate from official-price
estimates. The profile records current standard rates and a conservative long-context,
12-hour cache-write reserve calculation. Nothing schedules that future allocation.

Run [42117106768](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42117106768)
at `6e0fdb899b62c46ad1a190be7a66c01219358849` passed all three controls and both
real-CLI refusal probes. Good bytes matched across all three boundaries and graded
reference-pass/2-of-2; missing output was explicit; invalid UTF-8 transferred unchanged
and was rejected. The probes observed one POST each and a 60.206-second idle timeout.
Stock root cleanup reported permission errors under dropped capabilities; the original
failure remained visible and the whole container was disposed. No cleanup hook was added.
The first run, 42115972887, stopped at snapshot HTTP 503 before any controls. Both
authorized diagnostic runs are consumed. No further execution is scheduled.

The single report preserves those observations and historical uncertainty. Local checks
cover 24 trial tests and seven shared grader tests. Two unrelated shared collector checks
require SkillEvaluator, which is not installed in the direct-Harbor environment.

## Historical evaluated execution profile

The user explicitly authorizes Harbor's stock unattended Codex launch within the
external benchmark boundary. Native Codex sandbox failures remain historical evidence
in `results/sandbox.json`; they no longer gate this profile. No further Bubblewrap or
legacy-Landlock experiment is scheduled. The implementing agent's safeguards are
unaffected.

Harbor's supported custom-agent `import_path` loads `PinnedCodex`, which inherits
`run` and `exec_as_agent` unchanged. It checks the checksum-installed CLI and uses a
build-owned private home. Two private Harbor overrides remain:
`_ensure_agent_owned_dir` and `_upload_effective_config`. They avoid privileged
ownership changes during execution. Their names, paths and calling contracts require
review on upgrades. No upstream files are patched; this still carries compatibility
maintenance. The version check matches the explicit `codex-cli` line because Docker
merges stderr warnings into stdout and Harbor's first-line parser can reject the pin.

Codex 0.155.1 rejects the reserved `model_providers.openai` ID during configuration
loading. The supported `trial_openai` alias preserves OpenAI endpoint, authentication,
headers and transport capabilities while selecting request/stream retry counts of
zero and a 60-second stream idle timeout. The offline stock-launch probes observed
one HTTP POST on a 503 and one silent SSE request ending after 60.2 seconds. Normal
WebSocket probing/fallback remains; these checks cover HTTP/SSE retries. The first
diagnostic Actions run hit a snapshot-index HTTP 503; the second passed all ten
verification checks while intentionally retaining nonzero probe exits.

Harbor's native allowlist permits `api.openai.com`; runtime configuration disables
web search and remote MCP equally in both arms. UID/GID 1000, no agent capabilities,
no-new-privileges, Docker default seccomp, two CPUs, 2 GiB RAM and 256 PIDs are checked
inside the actual agent environment and against Docker metadata. No host mounts,
Docker socket, privileged mode or repository-write credential are provided. Only
Harbor's separate network controller uses NET_ADMIN/NET_RAW within its disposable
network namespace. The existing offline verifier remains separate.

This is a practical preflight, not a security proof. DNS and the model API remain
necessary network channels. The API credential is readable by code in the same agent
environment. This profile does not establish native Codex approval behavior or
workstation equivalence.

## Fixed pair and accounting

Only `pester-002`, current then absent, is selected. Each task gets a fresh container,
home and session. The absent arm removes exactly three target files from the 48-file
APM deployment; the other 45 files, generated instructions and original Codex config
are matched by hash. The whole-container target-directory audit checks source, home,
plugin and cache copies. Reference code, mutants and graders are in the verifier,
not the agent input. Public availability and possible model memorization remain risks;
no case is genuinely blinded.

Historical evaluated pins remain Harbor 0.25.0 (`fdba28fc411e47e8765420a1a063b4918fce3def`), Codex 0.155.1,
`gpt-5.6-sol`, medium effort, PowerShell 7.6.9 and Pester 6.2.0. The existing image
and package digests, snapshot and archive hashes remain pinned. No routine upgrade
is included. The model slug has no immutable published snapshot.

The original zero-paid campaign record is retained. Failed setup reservations count
conservatively against the four-attempt recovery allowance; they are distinguished
from actual model calls. Serial execution allows at most 600 seconds per agent;
Harbor and provider retries are disabled and no judge is used. The supported rollout
budget is supplemental, not a dollar meter. A conservative estimate charges all input,
including cached input, at $20/M and output at $30/M; the pair preflight estimate is
$2.64. The $4 scheduling threshold retains $16 reserve within the $20 operational
budget. It is not a provider cap and overshoot is possible. The user explicitly accepts unknown costs for testing. A completed first execution
with unknown cost may therefore proceed to the second arm; incomplete execution or
a known estimate exceeding the scheduling reserve still stops it. No pass-seeking retry or skill revision is authorized here.

## Reused grading and maintenance

The retained native controls from run 41958553130 are unchanged: known-good passes
the reference and detects 2/2 defects; weak passes the reference and detects 0/2.
The full qualification suite is not rerun. Earlier shutdown, snapshot transport,
fixture-permission and native-sandbox failures remain distinct historical evidence.

`project()` delegates execution failure cause and reward validity to pinned Harbor.
It separately requires completed supported verifier evidence for measured correctness;
a numeric reward or favorable completion message is insufficient. Agent exhaustion,
provider/environment failure, verifier failure, invalid/unsupported/missing evidence
and integration failures remain distinct. Independent artifact grades can survive
agent exhaustion when Harbor considers them valid. Missing usage stays unknown.

Custom components are fixed staging/projection/reporting, a small live runner, the
pinned-installation/ownership subclass, focused tests, a 29-line signed
snapshot download helper and one branch-only workflow. The old sandbox probe is
retained as historical code, unused by the current workflow. Graders, task fixtures,
PowerShell runner and runtime installer are reused unchanged. Another skill still
requires representative tasks, executable checks and independent controls. Nothing
can yet be removed from production on this evidence alone.

Sanitized launch diagnostics consume the pinned native command logger and checkpoint
each stage before cleanup. Original launch failures and cleanup failures remain
separate. A local failure-path test verifies nonzero exit and sentinel redaction.
The fixed loopback refusal fixture never forwards requests or retains their headers
or bodies, and is included only in offline diagnostic images. No framework patch or
additional private Harbor method override was added; logging-record shape remains a
compatibility dependency. `rollout_present` and `result_extraction_succeeded` describe
their actual evidence; neither field proves successful task execution.

The final pair reported 95,829 input tokens including 71,142 cached input tokens,
24,605 cache-write input tokens and 1,367 output tokens. Cache counts are components
of input, not additive totals. Harbor's pricing estimate is $0.23077225; the separate
conservative estimate is $1.95759. Neither is a provider bill; cumulative spending
remains unknown. No candidate hash/size was recovered at the declared artifact path.
The executed metadata collector omitted custom tool calls, so activation is unknown.
That collector now has a failing-before/passing-after regression check; 19 focused
tests pass locally, while 18 ran on the live head. The smallest next step is a
credential-free artifact-boundary diagnosis, not another model attempt.

## Authorized GPT-6.1 Sol/High live allocation

The next allocation is separate from the exhausted 4/4 recovery allowance. It permits
only campaign attempt five (current) and six (absent), serially on pester-002. The
switch remains disabled unless an explicit arming commit binds the unchanged code
parent to one GitHub workflow run number. Reruns and other pushes cannot consume it.
Reservations are uploaded before each credentialed step; lost completion evidence
consumes the reserved slot. The first result is checkpointed before reserving six.

The second arm requires complete CLI usage categories, successful evidence extraction,
confirmed container disposal and an interpretable graded/missing/rejected outcome.
A passing result is not required. Unknown new usage or broken transfer stops scheduling.
The $5 incremental operational budget requires the first conservative estimate plus
$2.50 second-attempt reserve and $0.50 headroom to fit. All input is charged at the
conservative $10/M rate (including cache subsets), and output at $15/M (including
reasoning). This is not a provider-enforced cap; historical spending stays unknown.
The workflow closes its local ledger on completion/failure; branch metadata is then
closed and returned to disabled/report-only state. No new runtime or grader qualification
is inferred from the scheduling tests.
