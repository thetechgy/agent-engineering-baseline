# Native Codex production-integration qualification

## Decision

**Blocked; do not integrate this adapter into production.** Native App Server items improve attribution of observed
commands and patches, but the tested public protocol does not establish the complete population of submitted inner tools
or their original arguments. That population is required by the existing gh authorization oracle. A complete turn and
matching `thread/read` snapshot are insufficient.

This report qualifies the recommendation at investigation revision `691db4e1c0e77dd5b51475e6d150ce9f89d24c13` ; it does
not rewrite that report or its evidence. Its “complete” observation claims must be read as completeness of the tested
native **item** population, not proof of every submitted operation. This qualification found the distinction material.

SkillEvaluator retention remains a plausible implementation choice through the later source snapshot's official backend
mechanism. **It has not passed the real paired execution, grading, collector, completeness, or provenance adoption
gates.** Released 0.6.0 still cannot select this backend. Replacing SkillEvaluator with Inspect would not repair a gap
in Codex's own public event contract, so rebuilding Inspect now has no demonstrated benefit.

## Critical results

PASS below applies only to the stated test. UNKNOWN means unexercised, not passed by inheritance or the earlier
approximate broker PoC.

| Requirement | Outcome | Evidence and limit |
|---|---|---|
| Provider-specific wrapper selected through actual SkillEvaluator CLI | PASS, rejection controls | An unrelated backend wrapper is rejected; the native subclass reaches staging without replacing the required gateway wrapper. Two local catalog GETs, no model POSTs. |
| Preserve provider routing and secure execution methods | PASS, actual upstream functions/source | Full configured model ID, Responses route and `OPENAI_API_KEY` reference preserved; inherited `exec_as_agent`, secure execution/redaction/cleanup methods. Runtime use through the paired CLI remains UNKNOWN. |
| Released 0.6.0 compatibility | FAIL for custom backend | CLI rejects `aeb-native`; unchanged production gh staging is rejected by its paired-baseline healthcheck guard. The later snapshot is a separate identity. |
| Complete observed native command/patch item lifecycles | PASS, bounded real Codex containers | Parallel commands, two identical commands, actual patch and exit 7 retain distinct native identities/results. A displayed ghost operation is not a command item. Live items equal the scoped terminal snapshot; final capture also requires stream EOF. |
| Original inner arguments and complete submitted-call population | **FAIL, material blocker** | Denied `require_escalated` call inside advertised `exec` produces an error in outer output, but no `commandExecution` item. Successful items do not carry original `exec_command` arguments. |
| Official executed-tool metadata feature resolves the gap | FAIL in tested runtime | Enabling the under-development feature did not expose the needed inventory through captured raw events/snapshot. Pinned source explicitly calls it warehouse-only metadata, outside the public App Server protocol. |
| Supported direct-tool workaround | NOT QUALIFIED | Canned direct `exec_command` executes with a matching native ID, but it was **not advertised** in the actual model tool catalog. Disabling `code_mode_host` leaves `exec` advertised and returns “code-mode host is disabled”. Neither qualifies a supported replacement profile. |
| Pipe stdio resists same-UID native-stream injection | FAIL | Evaluated process opens producer FD 0/1 through `/proc` and writes a forged event into the native stream. The tested malformed event is rejected; accepted plausible forgery was **not** demonstrated. |
| Socketpair transport blocks tested forgery primitives | PASS, bounded OS tests | No listening App Server endpoint; anonymous socket descriptors cannot be reopened through `/proc`. Controller is non-dumpable; ptrace, `/proc/PID/mem` and `pidfd_getfd` attacks fail. Producer stderr remains writable and is diagnostic-only. This is an OS/process trust boundary, not cryptographic authentication. |
| Producer termination/stop/capture termination | PASS, unavailable controls | Kill/stop producer or kill controller yields unavailable evidence. An agent can interrupt its own trial; this is different from forging accepted evidence. Scoped contradictory/missing/late synthetic populations are rejected separately. |
| Actual container isolation | PASS for tested outer profile | UID 1000, all capability sets zero, no-new-privileges, seccomp filter, loopback only, no mounts/Docker socket, unprivileged containers, explicit resource bounds. |
| Inner Codex `workspace-write` on hosted Docker | UNSUPPORTED | Default runtime blocks its user namespace (`bwrap`). Outer containment retained; no privileged container or unconfined seccomp workaround. |
| Complete production gh initializer/oracle lifecycle | **UNKNOWN; stopped** | Actual unchanged gh CLI guard tested. No operator-initialized production gh paired trial ran. Earlier approximate broker tests do not establish production receipt, readiness, cancellation or authorization parity. |
| Podman/gh paired grading, verifier, collector and signed provenance | **UNKNOWN; stopped** | No successful real native paired CLI evaluation. No activation, discoverability, security, accuracy or effectiveness score was admitted. No 68-trial expansion. |

The failure concerns the evidence contract, not model quality: all Responses traffic was canned and local. No
provider-backed grader or inference ran.

## Why this blocks the existing security contract

The unchanged [gh oracle](../.github/evals/gh/evals/grader.py) requires a real `exec_command` /`bash` observation and
rejects argument keys beyond `cmd` , `command` , `workdir` , `yield_time_ms` , and `max_output_tokens` . It also checks
literal commands against broker audit receipts. A permission/escalation control is therefore materially different from
the same rendered shell command with no such control.

Native items expose rendered command, cwd, native ID, process correlation, status, output and exit code. They do not
expose that original argument dictionary. Raw experimental events expose the **outer** JavaScript submission and
transformed outer output, without a qualified identity-linked inner inventory. Parsing JavaScript, matching text/output,
or assigning an outer result to inner calls would recreate the attribution problem this work is meant to remove.

In the real denied-inner control, the turn completes and the live/snapshot item populations agree, while the attempted
escalation exists only inside the outer wrapper. The first qualification implementation could have called this item
population complete. The final code names that narrower property explicitly and makes **all grading admission
unavailable** until a supported submission contract is qualified. This fail-closed stub is deliberate; it is not a
production-ready admission implementation.

The broker audit must remain an independent mandatory gate. An operation rejected before reaching the broker cannot
appear in its receipts; receipts cannot supply the missing complete tool-submission inventory. Successful patch
postconditions likewise do not establish gh authorization or reliable skill activation.

## SkillEvaluator and secure lifecycle findings

The candidate uses the registered `skillevaluator.env_modes` entry point and subclasses
`SkillEvaluatorSecureDockerEnvironment` , not `SkillEvaluatorDockerEnvironment` . It preserves inherited
credential-sensitive execution, agent dispatch and stop/service methods. The native class subclasses the required
`SkillEvaluatorGatewayCodex` and uses its provider configuration and dispatch methods. No monkeypatch, frozen-lock
override, task-authored root callback or stock-wrapper substitution was introduced.

The actual CLI exercises paired configuration, provider selection and existing gh staging. Both released and candidate
sources reject the unchanged gh authored healthcheck; that protection remains intact. The native wrapper's selection is
necessary compatibility evidence, **not** proof that install/setup/run/verifier/collector succeed. Its capabilities do
not falsely advertise an implemented ATIF trajectory. Its experimental environment only provisions fixed operator helper
files; it does not implement the production broker contract. The operator profile also forces no-network despite the original gh task's
public-network metadata; that is a distinct experimental condition, not fixture parity.

The proposed gh projection would have removed the authored healthcheck and selected the operator profile instead, with
equivalent independently initialized arms, trusted case/helper identities, root-only scenario/audit state and active
non-mutating peer-verified readiness. Those changes were **not implemented** after the evidence blocker. Socket
existence, a generated Dockerfile, inherited teardown code, or earlier direct Harbor tests cannot close those gates.
Stale/symlink/socket substitution, real receipt replay/forgery, initializer failure/cancellation, and agent attempts to
obtain root through this paired path remain required future runtime tests.

The experimental agent stores a private host capture and publishes with exclusive no-follow file creation; an
agent-created destination symlink cannot cause a host overwrite. A local host-file control verifies that bounded
property. This is not a qualified collector/provenance integration: private-copy retention, interruption, exported
references and signed upstream outputs still require a real paired lifecycle test.

## Grading, history and policy

No native item was converted into a fabricated successful activation or a clean security score. Unsupported, missing and
contradictory populations remain unavailable; unavailable is not numerical zero. No model-judge assessment was produced.
Scripted file reads or task postconditions cannot measure genuine model discoverability or skill effectiveness.

The current oracle and native metrics were inspected, not silently changed. Future native observations might support
successful/failed skill-read attribution using scoped result identities and explicit error flags, but the complete
extraction and scoring path has not been demonstrated. A narrow projection cannot truthfully fill original arguments
that were never observed. New grading/runtime conditions must have new policy identities; the experiment uses
`native-submission-contract-v2` and `outer-container-socketpair-v1` , separate from the original investigation and
production history.

Planner, history, canonical Pages publication and historical measurements are unchanged. No alternative dashboard,
database or publication path was created. Any future importer must retain native references, independently enforce
mandatory broker security gates, and reject incomplete evidence before native metrics or historical admission.

## Sources, runtimes and reproducibility

| Component | Immutable identity / runtime |
|---|---|
| Original investigation/report | `691db4e1c0e77dd5b51475e6d150ce9f89d24c13`; original runtime `6af0587664cca0af3996594cc028a449b4520899` |
| SkillEvaluator release control | `5320d9329c36ecc72bc94c4f58cc813d6b54224b`, released 0.6.0 |
| SkillEvaluator extension snapshot | `d9fa4b4041b31f417f02ed145999ecf1f0c11fcd`; reports 0.6.0 but **later, unreleased source** |
| Harbor | 0.24.0, frozen dependency; source `b53b8134e1241686dca7759af188f987ecc48e8b` |
| Codex | 0.164.0, source `6aaac694803004a63c6f393d153c96d22521a6b9` |
| Codex package / native ELF SHA-256 | `3ec55053109608d5038f7e50750f7d25f768dfd740fef071aa710e2559b63aac` / `b93f6811d3f653f0fb83be4050d857fb9abbb111dfa2ce160563327daff7f306` |
| Base image | `python:3.12-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1` |
| Setup / evaluator | uv 0.13.5; separate frozen source locks, Python 3.13.15; plugin install `--no-deps` |
| Hosted runtime | Ubuntu 24.04 hosted runner, Docker 28.0.4; exact kernel, containerd/runc, image IDs, inventories and lock hashes retained in final artifact |

The image build adds fixed local helpers to the verified official Codex package. Dependency preparation has network
access; agent containers have none beyond loopback. The scripted provider binds `127.0.0.1:8991` ; no external provider
route or actual credential is supplied. A catalog-only CLI service rejects all model POSTs. Official raw events and
executed-tool metadata are experimental probes, not stable completeness promises. Host preparation Python is separately
recorded from the evaluator venv.

Relevant immutable primary sources:
[provider wrapper selection](https://github.com/NVIDIA/SkillEvaluator/blob/d9fa4b4041b31f417f02ed145999ecf1f0c11fcd/src/skillevaluator/tier3/harbor/runner.py#L3357)
,
[secure environment](https://github.com/NVIDIA/SkillEvaluator/blob/d9fa4b4041b31f417f02ed145999ecf1f0c11fcd/src/skillevaluator/tier3/harbor/secure_docker_environment.py)
,
[backend extension](https://github.com/NVIDIA/SkillEvaluator/blob/d9fa4b4041b31f417f02ed145999ecf1f0c11fcd/src/skillevaluator/tier3_environments.py)
,
[Codex metadata contract](https://github.com/openai/codex/blob/6aaac694803004a63c6f393d153c96d22521a6b9/codex-rs/protocol/src/models.rs#L1013)
,
[tool-mode selection](https://github.com/openai/codex/blob/6aaac694803004a63c6f393d153c96d22521a6b9/codex-rs/core/src/tools/mod.rs#L65)
, and authoritative [issue #86](https://github.com/thetechgy/agent-engineering-baseline/issues/86) .

## Smallest practical next step

1. Keep production SkillEvaluator 0.3.0/Harbor 0.13.2/Codex 0.155.1 and existing conservative admission unchanged. Do
   not deploy the experimental plugin or reinterpret history.
2. Qualify a supported Codex contract exposing original submitted inner calls, declined/failed/cancelled outcomes,
   native execution relationships and explicit incomplete/truncated inventories over the protected producer channel. A
   forced unadvertised direct call is not enough. A different supported tool profile would need its own model/tool
   policy identity and fair qualification.
3. Only after that gate passes, complete one operator-owned secure initializer and one native adapter through
   SkillEvaluator's real paired CLI. Require a released/supportable backend source, or explicitly approve a pinned
   unreleased dependency; never describe the snapshot as released support. Exercise the full production gh
   oracle/readiness/receipt/failure/cancellation matrix and representative Podman grading/collector/provenance before
   expansion.
4. If that integration needs copied internals, protection bypasses or misleading metric conversion, compare Inspect with
   the **same qualified native producer** and native grading requirements. Do not build duplicate adapters before that
   decision is meaningful.
5. Obtain separate production migration approval; paid evaluations, protected workflow changes and merges remain
   separate authorizations.

The custom production code target remains one native agent, one trusted secure initializer and one narrow evidence
projection/admission module. The present source is qualification scaffolding, not that deliverable. Ongoing costs would
include native protocol compatibility, provider-wrapper changes, fixture identities/readiness/cleanup, scoring-policy
qualification and upstream output-provenance integration. Present evidence cannot justify an effort estimate or claim
production maintenance is lower. The observed attribution improvement is meaningful, but the complete architecture is
**not yet demonstrably better enough to replace the current production system**.

## Hosted evidence and review material

The final
[hosted qualification run 40764246980](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/40764246980)
, attempt 1, passed at runtime/workflow source `0efbe50b503e1f41527fe3512de851555dd28237` . This means its controls
behaved as expected, including unavailable admissions; **it is not a passing architecture qualification**. Seventeen
real container profiles ran (11 producer/isolation/interruption profiles, six native-contract profiles), plus four
actual CLI rejection controls. Six additional mutated event populations are labeled synthetic-only.

| Run | Runtime source | Retained result |
|---|---|---|
| [40756112436](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/40756112436) | `e131c64f9716563152cddb03d51248e494bfbd34` | Failure preserved: inner sandbox unsupported under hosted default runtime |
| [40757866640](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/40757866640) | `7b21be52f0f8dfc2a238a84e48875c5dbf1c7123` | Producer controls and real CLI rejections; inner sandbox explicitly unsupported |
| [40763796014](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/40763796014) | `e2c775112786fb1a1ca825d5bf275cc706645a8a` | Native submitted-call coverage counterexample reproduced |
| [40764246980](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/40764246980) | `0efbe50b503e1f41527fe3512de851555dd28237` | Final controls, explicit EOF requirement and fail-closed grading admission |

Final artifact `12849967569` : SHA-256 `a8b4ffcd0fcdd8c61be51bc2a99678c8510d7667049f94a55684a059b51d8335` , 821,214
compressed bytes, 43 members, 3,271,803 uncompressed bytes. All four qualification archives are committed with
authenticated repository/branch/workflow/run/source metadata and GitHub artifact digests in the
[archive manifest](native-codex-qualification-results/archive/manifest.json) . They are data only. The
[bounded verifier](native-codex-qualification-results/verify_archives.py) checks digests, safe member paths, producer
metadata and final control assertions without extracting or executing artifact content.

The original investigation's complete archive is separately preserved at
[commit 2f035f5](https://github.com/thetechgy/agent-engineering-baseline/commit/2f035f5e9757fee12ca72c29a8dcff9cde00220d)
with SHA-256 `70aca889c3165cad7091e391b29db4866b5b4efba34240475f44cbd824889bbe` ; its November 4 artifact expiry no
longer removes the only complete copy. Original report, qualification JSON and representative evidence bytes are
unchanged.

Review entry points: [qualification JSON](native-codex-qualification-results/qualification.json) ,
[native contract results](native-codex-qualification-results/contract/summary.json) ,
[actual CLI results](native-codex-qualification-results/cli-controls/summary.json) ,
[runtime identities](native-codex-qualification-results/runtime-identities.json) ,
[workflow security review](native-codex-qualification-results/workflow-review.md) , and
[experimental source](native-codex-qualification) . Report/result commits intentionally leave the tested
runtime/workflow tree unchanged and do not launch further experiments.
