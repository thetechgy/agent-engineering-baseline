# Direct Harbor recovery trial

This branch-only trial preserves production SkillEvaluator 0.3.0 / Harbor 0.13.2,
APM deployment, static checks, historical scores and Pages. Source commit:
`cc0819f5dafc05610dd8c3293ce2f52744c66f1a`. This pass starts from reviewed trial
commit `29f7765a3e2e48ca573160d412749b717d63bb06`.

[The single report](results/report.html) and its [machine-readable results](results/results.json)
are authoritative for outcomes and spending. Report packaging is not native evaluation.
The current pass stops at a stock-launch failure: two credentialed current-arm
attempts consumed two recovery slots; absent was skipped and usage is unknown.
Only reviewed metadata is published; previously rejected raw oracle content is not
repackaged. Raw agent transcripts, submissions, authentication files and environment
dumps are excluded from the live artifacts.

## Execution profile

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

Pins remain Harbor 0.25.0 (`fdba28fc411e47e8765420a1a063b4918fce3def`), Codex 0.155.1,
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
budget. It is not a provider cap and overshoot is possible. Missing or incomplete
usage stops the next arm. No pass-seeking retry or skill revision is authorized here.

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
48-line pinned-installation/ownership subclass, focused tests, a 29-line signed
snapshot download helper and one branch-only workflow. The old sandbox probe is
retained as historical code, unused by the current workflow. Graders, task fixtures,
PowerShell runner and runtime installer are reused unchanged. Another skill still
requires representative tasks, executable checks and independent controls. Nothing
can yet be removed from production on this evidence alone.
