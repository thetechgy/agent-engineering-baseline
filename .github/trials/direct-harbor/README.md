## Reusable image qualification, 2026-11-06

The separately authorized infrastructure pass permits at most two complete image
build qualifications. It keeps all paid allocations closed and campaign consumption
at 6/36 (earlier recovery 4/4). No evaluated-agent inference or model judge is part
of preparation. Historical failures below remain historical evidence.

`preparation.json` selects the exact four-file snapshot seed by archive and manifest
SHA-256. The trial-only prerelease seeds already verified local files; the Actions
`snapshot-dependencies` artifact retains them for 30 days. Builds validate every
size/hash before APT verifies InRelease with the existing Debian keyring through
local file sources. Missing/corrupt/incompatible bytes fail without a download
fallback. Package downloads remain independently size/hash checked; snapshot date,
package pins, complete Codex package, Harbor and verifier acceptance are unchanged.

`prepared.py` extends the existing image/task transport. `prepared-images` retains
both agent images, the independent verifier and stock Harbor egress image for seven
days. Its manifest binds source commit/run, relevant build and deployment inputs,
runtime profile, dependency manifest, image IDs and task/member hashes. Reports and
allocation metadata do not invalidate identical experiment inputs. Reuse requires
an explicitly selected artifact ID/digest, successful branch producer, first run
attempt, ancestor source commit, unexpired content and matching experiment inputs.
The new consumer still passes the original allocation and reservation checks.

A separate GitHub-hosted `qualify` job requires all retained images to be absent,
loads them, verifies relocation and deployment, repeats existing runtime/isolation
checks, and runs good/weak/unsupported/runner-error native grader controls. It uses
stock Harbor's prebuilt path, with no new private override. Protected verifier
fixtures remain separate from agent image content. Dependency indexes are excluded
from the task handoff after image construction; they have their own retained bundle.

Full image construction and fresh-runner qualification are pending until the new
workflow evidence is recorded. The trial-only seed is not a production release;
no production evaluation, Pages, or shared environment settings change.

# Direct Harbor recovery trial

## Authorized retained-submission smoke allocation

Allocation `sol-high-retained-20261106` starts from the closed 6/36 ledger and
permits current/7 followed by absent/8 at most. All earlier allocations and unused
reservations remain closed. Admission diagnostics are enabled in both arms; runtime,
APM deployment, task, grader acceptance criteria and isolation are unchanged.
Paid execution is disabled by default, armed for one push/run number only, and closed
on terminal paths. The $5 operational budget retains the $2.50 second-arm reserve
and $0.50 headroom; historical billing remains unknown.

The user explicitly authorized retaining only the exact agent-generated
`/workspace/output/Subject.Tests.ps1` for 30 days. `retention.py` checks bounded regular
single-link files, known credential values/patterns and protected fixture content.
It never executes the file and never edits its bytes. A blocked file has a fixed
reason and metadata only. These bounded checks are not a general DLP proof.
Approved files and identity/hash metadata are uploaded as separate evidence attachments,
downloaded, then verified against the staged bytes and reservation before the second
arm can be reserved. No oracle answers, raw rollouts, authentication files or environment
dumps are retained. Missing or failed publication cannot masquerade as recoverable evidence.

The credential-free fixture run 42212438394 verified this upload/download path,
including CRLF byte preservation. It is publication-path evidence, not a new handoff,
security, grading or model qualification. See `results/retention-validation.json`.
Maintenance added: one small publication module, focused tests and pinned artifact
upload/download steps; no additional Harbor private override, dependency or transport.

## Admission diagnostics and preflight

The branch-only `admission` Actions phase builds only the pinned verifier image.
It runs the parser preflight and four fresh, offline Docker verifier controls:
good, weak, unsupported command, and an injected runner error. The last control
modifies a disposable container copy only. No API secret or protected paid environment
is used. The single report keeps these controls separate from live outcomes and
preserves the closed 6/36 campaign ledger. Local component tests require explicitly
selected pinned PowerShell/Pester paths; an arbitrary host runtime is not used.


Admission failures now always include a fixed `admission_rule`, such as
`command_not_allowed`, `block_name_template`, or `type_not_allowed`. This survives
the grader sidecar, native projection, allocation JSON, and the single HTML report.
An unexpected exception in admission instead reports
`infrastructure_error/admission_runner`. Neither outcome becomes measured quality.
Acceptance predicates, reference/mutation grading, and historical results are unchanged.

Before credentials are supplied, live preparation runs four cheap parser controls
in the built verifier image: classic and weak suites are admitted, an unsupported
command is identified, and an injected runner error is classified separately.
Failure, timeout, invalid protocol, or unresolved cleanup prevents preflight success
and is checkpointed to `public/admission-preflight.json`. The controls invoke the
actual pinned PowerShell parser; they do not execute submitted code, invoke Codex,
or qualify container isolation or mutation grading. Their files stay under the
verifier-owned `/tests` tree, outside the agent image and worker access.

Detailed diagnostics are optional. Set `admission_diagnostics: true` in an
otherwise authorized launch configuration to include AST kind and line/column.
Both arms receive the same verifier-only setting. This flag does not authorize
inference, reopen an allocation, change scheduling gates, or expose source text.
Leave it absent/false for concise default reasons.

For a broader credential-free check using the pinned local PowerShell runtime:

```bash
python .github/trials/direct-harbor/admission_checks.py \
  --pwsh /path/to/pinned/pwsh \
  --runner .github/evals/powershell-pester-6/support/Runner.ps1 \
  --profile .github/evals/powershell-pester-6/support/cases/pester-002/profile.json \
  --fixtures .github/evals/powershell-pester-6/support/qualification/pester-002 \
  --extended
```

To diagnose an existing file without another model call, replace `--fixtures …
--extended` with `--candidate /path/to/Subject.Tests.ps1 --details`. Replay parses
only; it never executes the submission. A rejection returns nonzero and structured
metadata. Missing executables, timeouts, and invalid output do not pass.

Run focused tests with `PESTER_TEST_PWSH` set to the pinned executable and
`PESTER_TEST_MANIFEST` set to the pinned Pester manifest to include native parser
and trusted reference/mutation component checks. Without those variables, native
component tests explicitly skip; the mandatory live preflight still requires its
image's PowerShell. No new dependency or Harbor private override is introduced.

Before the explicit retention authorization above, raw submissions were excluded. Hashes and rule IDs
cannot reconstruct a discarded file; replay requires a retained copy. These
diagnostics do not retroactively explain attempt six or establish skill benefit.

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
repackaged. Historical raw submissions were excluded. Raw agent transcripts, authentication files and environment
dumps remain excluded; the later declared-deliverable exception is described above.

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

The allocation is now closed after run
[42122482332](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42122482332)
at `368c3866f817b6b38fcc04953e15b300d81cd5f0`. Only campaign attempt five ran.
Codex stopped after 10.349 seconds with `shared rollout token budget exhausted`.
No submission existed at any observed boundary. Harbor retained its native
`NonZeroAgentExitCodeError` / `unclassified`; the report separately identifies the
explicit Codex budget exhaustion. Reference and mutation results are unmeasured.

All six cumulative usage categories were observed, yielding a conservative estimate
of $0.641555 for those observations. The completion-qualified usage gate stayed false
because the session failed; it does not mean the counts are absent. Complete billing
is unknown. The reported counters reconstruct 30,346 fallback units versus the 30,000
limit, consistent with the terminal error. Skill-file access attempts were observed,
but successful reads or benefit were not established. Attempt six was never reserved
or launched. Scheduling is disabled, recovery remains 4/4, and campaign usage is 5/36.
The specific next decision is to calibrate the supplemental token budget for this
frozen deployment before authorizing another allocation; no such run is scheduled.

## Fresh allocation with supplemental rollout budget disabled

This pass starts from `388aed6` and preserves attempt five at execution commit
`368c386` / run 42122482332. Its exact native Codex error was `shared rollout token
budget exhausted`; Harbor's `NonZeroAgentExitCodeError`, `unclassified` cause and
invalid reward remain unchanged. The observed cumulative counters reconstruct 30,346
fallback units; producer, host and verifier confirmed no deliverable. This is not
an observed artifact-transfer failure. Historical billing remains unknown.

The new allocation is `sol-high-no-rollout-budget-20261105`, with distinct current/6
and absent/7 reservation IDs. The earlier planned slot six stays closed unused in
`allocation_history`; no allowance is recycled. Prior recovery remains 4/4 and the
campaign starts at five consumed attempts. The allocation permits two launches only,
current first, no retry. One push/run number and its reviewed parent commit bind the
allocation; reruns cannot spend. Reservations are checkpointed before credentials;
unknown launch outcomes consume their reservation. Paid execution remains disabled
outside that explicitly armed run and is closed afterward.

`features.rollout_budget = false` removes the whole supplemental feature, including
reminders and weights, for both arms. `codex features list` checks the resolved state
without credentials before inference and again after Harbor's effective upload.
Strict configuration loading remains in place. Model, effort, complete CLI package,
600-second timeout, network/tool policy, isolation and grading are unchanged. No
replacement token ceiling is introduced; this is a different comparison profile
from attempt five. Previous control outcomes are reused without another campaign.

Accounting no longer requires task success. The small native-event interpretation
reads Harbor's existing `agent/codex.txt`, excluding item/model/tool contents. A
completed native turn must match the five CLI usage categories against one parseable
rollout, with cumulative usage preceding its session terminal. An exact native budget
failure with that session evidence is an interpretable failure; generic nonzero exits,
provider/environment/verifier failures or incomplete evidence block scheduling.
Retained attempt-five metadata establishes the failure and an observed-use estimate,
but lacks the new ordered-session observation; complete historical coverage is not
invented. All estimates remain separate from provider bills.

The $5 incremental operational budget uses the existing conservative $10/M all-input
and $15/M output estimate. Cache reads/writes are input subsets and reasoning is an
output subset, never extra summed tokens. Starting the absent arm requires the current
estimate plus a $2.50 reserve and $0.50 headroom to fit $5, adequate accounting and
handoff evidence, and verified disposal. Removing the token ceiling may increase
usage; runtime and attempt limits do not guarantee a dollar cap. No billing proxy,
new Harbor private override, upstream patch or generalized scheduler was added.

Run [42157462581](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42157462581)
executed `47635e3`. Attempt six completed in 42.508 agent seconds, produced a 3,372-byte
file with matching producer/host/verifier hashes, and yielded matching CLI/session usage.
The unchanged verifier returned `unsupported/admission`; reference and mutants did not
run. Its specific AST/policy reason was not retained, so no agent correctness failure
or skill weakness is inferred. The conservative observed-use estimate is $1.49446;
provider charges remain unknown. The absent arm was prepared but not reserved/launched.
This allocation is closed at 1/2; campaign consumption is 6/36 and recovery remains 4/4.
Paid scheduling is disabled. The next justified work is credential-free admission-rule
diagnostics without relaxing acceptance criteria, before considering more inference.

Credential-free admission validation at `33ddf3c`, run
[42162451618](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42162451618),
passed the Docker parser preflight and all four isolated verifier controls. Fixed
`command_not_allowed` with `CommandAst` location 1:1 and `admission_runner` reached
the single report; good and weak grades stayed reference-pass/2-of-2 and
reference-pass/0-of-2 respectively. Native component tests also cover the data-driven
fixture. No historical live result was rescored, and attempt six remains unexplained.
Paid scheduling and the closed campaign ledger are unchanged.

## Retained-submission pass closure

The byte-retention fixture passed in run 42212438394. Prelaunch run 42212722607
then exposed a test that read the armed checkout instead of a disabled fixture;
that test was corrected without weakening the runtime guard. Corrected run
42213118342 passed the 54 component checks (three native-runtime skips), but the
current agent-image build failed on the unchanged Debian snapshot package index
with HTTP 503/504 (`apt-get` exit 100, Docker build exit 1).

Neither reservation nor credentialed launch occurred. Allocation
`sol-high-retained-20261106` is closed at 0/2, both planned reservation identities
are closed unused, and the campaign remains 6/36. Paid scheduling is disabled.
No new submission, grade, skill-access observation or model usage exists. Historical
spending is still unknown. The failed preparation is infrastructure evidence, not
a Harbor agent failure or evidence against the skill. No acceptance criteria or
package pins were changed, and no further build or inference retry was scheduled.
The next decision is a credential-free availability check of the same pinned package
index before authorizing any new allocation; this pass does not establish adoption readiness.

## Preparation before scoped environment approval

The fresh `sol-high-prepared-20261106` allocation starts from six consumed campaign
slots; its current/7 and absent/8 identities are new. Previous allocations and
unused reservations remain closed. At most two full preparation attempts and two
credentialed launches are authorized; model retries remain disabled.

`prepare` has no protected environment or API credential. It builds the unchanged
pinned agent images and one identical verifier image, runs the existing preflight,
and exports only `docker save` images plus immutable pester-002 task inputs and
credential-free metadata. It uploads, downloads, hashes, loads, and relocates this
bundle before the `live` job can request environment approval. The temporary image
artifact expires after one day. Verifier code/fixtures in that explicitly authorized
transport stay separate from agent image inputs and from the report.

The protected job loads the same image IDs and verifies archive/member hashes,
native task checksums and repository/branch/commit/run/allocation identity before
reserving a slot. It never reruns snapshot-dependent image builds. Fresh containers,
homes and sessions are created from built images, not from saved runtime containers.
The pinned Harbor content-addressed egress image is included for cache reuse; there
is no new Harbor private override. The existing snapshot date, package versions,
signed metadata, SHA-256 checks, base image digest and bounded APT retries are unchanged.
Public GET diagnostics recovered the compressed index and matched its release-listed
hash; this alone is not accepted as successful preparation.

The user explicitly authorized the assistant to submit the normal GitHub environment
approval through the API only for the exact allocation run, after preparation and
transfer checks succeed. This is automated approval under user authorization, not an
independent human review. No reviewer settings, administrative bypass or environment
permissions are changed. Actual approval metadata is recorded after submission.

Maintenance added is limited to `prepared.py`, focused archive/path checks and same-run
artifact steps. Bundle format and the pinned Harbor egress cache tag need review if the
pinned runtime changes. This does not add a service, registry, cache across campaigns,
new grader, or generalized execution layer.

The first preparation attempt (42235352779) recovered the main index but failed on
security-index HTTP 504 before any reservation or approval. The second attempt uses
the existing transport helper to cache exact dated `InRelease` and `Packages.xz`
bytes. InRelease hashes are pinned to the recovered immutable snapshot; index and
package hashes stay enforced. APT verifies the cached signed metadata with the same
keyring through a temporary `file:` source; the image's normal source configuration
is unchanged. Fetches retry transient failures at most three times with 30-second
request timeouts and bounded backoff. No rolling repository, unsigned source or
new package version is introduced. The exact-base unprivileged index-only check
passed APT authentication and package-URI/hash planning; it did not install packages
or count as a full trial-image preparation. Full image construction remains a CI gate.


The second and final authorized preparation (42238163966, commit 381c458) failed
at the first compressed-index download with HTTP 503 after all three bounded
transport attempts. Both preparation closures were downloaded and digest-checked;
neither reserved or launched an agent. Required agent/verifier image construction
and the new image transfer remain unverified. No environment approval was submitted.
Allocation `sol-high-prepared-20261106` is closed at 0/2; campaign consumption is
still 6/36. Paid scheduling is disabled and no third build is authorized in this
pass. The final report packaging run exercises no image build or model inference.
The next bounded action would be to qualify a durable cache of the same signed,
hash-verified snapshot bytes, then demonstrate complete credential-free image
construction before considering any fresh paid allocation. The successful local
index check does not establish that package installation or image reuse works.
