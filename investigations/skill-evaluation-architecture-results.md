# Continuous skill evaluation: architecture qualification

Investigation date: 2026-10-28. Production base: `70e6b3f5a2b397dfd462f79def89ee37c67b300c`.

## Decision

Prefer **native Codex App Server evidence, an operator-owned initializer extending SkillEvaluatorSecureDockerEnvironment, and Harbor as the execution lifecycle**. Retain SkillEvaluator's useful dataset/scoring orchestration conditionally, behind a narrow agent/backend extension. Do not use ACP/ATIF or provider transcripts as the authoritative execution witness. Do not migrate production yet.

This choice follows the demonstrated evidence and privilege boundaries. Inspect is a credible maintained evaluation framework, but its stock SWE Codex integration did not provide the execution evidence required here. Adding native capture there would still be necessary, together with more dataset/scoring migration. There is no demonstrated security or correctness advantage that currently justifies that additional replacement. Conversely, retaining SkillEvaluator is conditional on qualifying its real paired production entry point and scoring contracts; it is not a reason to accept misleading metrics or unsupported hooks.

No candidate is fully production-qualified by this investigation. The native/secure-Harbor combination is the strongest working prototype. The remaining gates below are explicit adoption work, rather than claims supported by canned model responses.

## Current architecture and coupling

The inspected production system uses SkillEvaluator 0.3.0 (`ac0a04905100acdafc6c95829311a9739c340ff6`), Harbor 0.13.2, Codex 0.155.1, Python 3.13 and reviewed runtime/compatibility pins. GPT-5.6 Sol is the configured paid model, but no paid model was contacted here.

| Layer | Existing responsibility | Coupling affected by replacement |
|---|---|---|
| APM skills and authored fixtures | Source inputs, generated deployment, dataset/cohort identities | Preserve input bytes and staging boundaries; never hand-edit installed skills |
| SkillEvaluator and repository setup | Paired arms, staging, native metrics, secure runtime, evaluator provenance | CLI/output layout, scorer semantics, native manifest and output provenance |
| Harbor and Codex adapter | Containers, setup/run/verify lifecycle, ATIF trajectories | Agent event conversion, execution attribution, cleanup and recovery |
| gh custom evaluator | Root-private broker/scenarios/audit, unprivileged agent, deterministic mandatory gates | Must consume independently attributable operations and private audit; cannot trust task-authored initialization |
| Evidence normalization | Coverage, arithmetic, native identities, retained-reference and provenance checks | A narrow native-event admission adapter is needed; do not fabricate legacy trajectory completeness |
| Planner, history, Pages | Change/due selection, protected inference dispatch, compatible observations, canonical report | Reuse schemas and authenticated admission; new policy identities, not historical rescoring |

Podman has 10 standard cases/20 trials; gh has 24/48 with custom security gates. Pester remains diagnostic-only. These suites were inspected, not ported or rerun as model benchmarks. The 20 trials below are a different synthetic infrastructure cohort.

Requested history was refreshed read-only: #99 provides the trusted canonical publisher; #100–101 concern Gallery acquisition/CI diagnostics; #102 adds evaluation orchestration; #103 registers the Podman reference; #104 retains compatible history; #105 isolates case inputs; #106 treats unsupported execution as unknown; #107 diagnoses input-member integrity rejection. Issue #86 remains open. Its requirement for actual paired production-path initialization is not closed by this prototype.

## Versions and immutable identities

| Component | Version / immutable source | Scope |
|---|---|---|
| SkillEvaluator release baseline | 0.6.0, `5320d9329c36ecc72bc94c4f58cc813d6b54224b` | Source review; no sufficient released initializer selection found |
| SkillEvaluator extension snapshot | `d9fa4b4041b31f417f02ed145999ecf1f0c11fcd` | Actual secure backend/plugin PoC; reports version 0.6.0 but is a later source snapshot |
| Harbor frozen baseline | 0.24.0, `b53b8134e1241686dca7759af188f987ecc48e8b` | Frozen SE lock, real Trial/container path and ACP converter |
| Harbor newer comparison | 0.25.0, `fdba28fc411e47e8765420a1a063b4918fce3def` | Separate environment, actual converter replay only |
| codex-acp | 2.3.0, `344a520632e4c8c02f781a7a20490dfac52d4d0a` | Actual TypeScript reporters/renderer replay; not a full ACP-session container qualification |
| Inspect AI | 0.3.285, `d1536eae98d7b8b9364c052f0e6d3de988e1aac9` | Real Task, Docker lifecycle and logs |
| Inspect AI newer release | 0.3.286, `5dcbc98f86b6fd3d4a045b6ad001c6be41a10646` | Release/source review only; no runtime qualification |
| Inspect SWE | 0.2.72, `6665c30bced70dbf5c17ed935a2da1024668c6f9` | Actual stock codex_cli integration with deterministic mock model |
| Codex native | 0.164.0, `6aaac694803004a63c6f393d153c96d22521a6b9` | Real binary execution, App Server protocol, no provider inference |
| Codex production comparison | 0.155.1, `be2951ea34f0d295ed0becf97079f92fa5f6950e` | Inspected baseline; not qualified for this replacement capture path |
| Runtime | Host Python 3.13.15, uv 0.13.5, Compose 5.6.1 | Hosted preparation; guest Python 3.12 image runs fixture helpers |

The full Codex 0.164.0 musl package SHA-256 is `3ec55053109608d5038f7e50750f7d25f768dfd740fef071aa710e2559b63aac`. The Python base image is pinned by digest `a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1`. Inspect's complete Python dependency resolution and the guest WebSocket dependency are hash-locked beside the probe. The SE experiment uses its frozen upstream lock unchanged. Harbor 0.25 was never substituted into that lock.

## Equal critical criteria and results

`PASS` means the stated bounded probe worked; `FAIL` means the tested path loses a required property; `UNKNOWN` means not qualified. An overall task success flag is not execution admission.

| Requirement | A: ACP + Harbor | B: Inspect SWE stock Codex | C: native App Server + secure Harbor |
|---|---|---|---|
| Distinct parallel/repeated inner execution IDs | Partial: real reporter/converter retain IDs, but not complete lifecycle semantics | FAIL as execution witness: model traffic lacks inner native execution IDs | PASS in real Codex containers |
| Failed / declined / interrupted / unknown remain distinct | FAIL: ACP collapses three terminal states; Harbor projection drops statuses | FAIL as native witness; no demonstrated native state capture | PASS for captured native distinctions; incomplete turns rejected |
| Patch execution versus displayed text | Insufficient authoritative projection | Actual patch works, but stock log lacks native fileChange identity | PASS: fileChange plus independently read actual.txt; reported ghost command has no native command item |
| Trusted initialization before unprivileged agent | Release SE 0.6 remains blocked; later secure plugin path works independently of ACP | PASS for operator first-solver ordering and OS boundary | PASS for secure environment start override before agent setup |
| Root-private scenario/audit inaccessible, no agent root exec | Secure backend reused; ACP-specific full session not qualified | PASS for tested private read/reinit/socket denial | PASS for tested UID/capability/network/ownership denials and root-only capture |
| Independent arms/attempts, active readiness | Extension prototype PASS; full SE paired CLI UNKNOWN | Active readiness PASS; full paired migration UNKNOWN | PASS across 20 independent states; real missing/failed readiness controls |
| Cleanup after failure/cancellation | Secure lifecycle probe PASS, independently of ACP | Container cleanup PASS after real SIGINT and initializer failure | PASS for owned containers, networks, volumes and per-project images after normal/failure/cancel |
| Missing/contradictory evidence prevents grading | Not acceptable using projected trajectory alone | Requires native admission extension | PASS before actual Harbor verifier; original raw capture retained |
| Full production datasets/scoring/report parity | UNKNOWN | UNKNOWN; larger semantic migration | UNKNOWN; strongest reuse path, still requires production CLI qualification |

A supported public initializer and a truthful execution witness are separate concerns. Solving one does not qualify the other.

## What actually ran

### Native contract and actual execution

A deterministic HTTP Responses server supplies canned tool calls to the real Codex binary. It binds only `127.0.0.1`; native App Server listens only on loopback. Trial containers have no non-loopback interface. There is no API key, provider-backed grader, remote GitHub operation, or inference service.

The native script executes two parallel commands, two identical commands, an actual apply_patch, exit 7, and an output string claiming a ghost operation. Captures contain five separate commandExecution identities and one fileChange identity, with command exit codes `[0,0,0,0,7]`. The actual file was read independently. The ghost text does not become an execution observation. Inner observations survive the transformed outer exec output because attribution uses native IDs, not output matching.

Real local rootless-Podman controls exercise approval decline and turn interruption. Decline yields a declined command item with null processId/exitCode and no created file. Interruption yields an interrupted turn without a completed command result; the fixture admission rejects it. These local traces are retained separately from hosted protected captures. Missing completion/result, conflicting identity, unknown tool type and unauthorized fixture-command controls are synthetic mutations of retained events; they are labeled synthetic, not claimed as real protocol failures.

The probe enables experimentalApi in the initialize handshake; its exact capability/version selection belongs in any future policy identity and must not be assumed stable across upgrades. Native tool items describe protocol operations, not every subprocess or kernel-level file write within a shell command. Independent broker and artifact checks remain necessary.

Important limitation: item/started is an item lifecycle notification and can precede approval. It does not itself establish that an OS process ran. Native process identifiers are correlation metadata, not independent OS attestation. FileChange completion is supplemented by filesystem observation in this fixture. Proposed text and model assertions never substitute for execution results.

### Secure lifecycle and trusted broker

The custom backend extends **SkillEvaluatorSecureDockerEnvironment**. It overrides start to await secure startup, provision fixed operator-owned code, perform required initialization and verify active readiness. It does not override exec, exec_with_sensitive_env, stop, service execution, or secure transfer behavior. Installed entrypoint discovery and real build_harbor_run_command selection were exercised; actual Trial.create/run exercises setup, run, verifier and teardown. No upstream monkeypatch or fork was used.

The operator package is outside evaluated content. Provisioning creates exclusive root-owned fixed paths under an unwritable root parent and checks digest/type/link count. It uses the inherited secure root execution API. Root provisioning/initialization uses isolated Python mode. A real untrusted pathlib.py poison file in the evaluated working directory is present during both initializers and is removed before agent setup, demonstrating that operator imports cannot be substituted from that directory. An early Docker copy approach preserved the host UID and failed ownership verification under cap-drop=ALL; it was rejected rather than restoring capabilities.

Each container has a fresh broker identity, private directory and audit. The broker accepts a small fixed protocol, never caller-selected paths or remote operations. Read, permitted mutation, duplicate mutation denial and private-operation denial are tested separately from Codex behavior. A native broker-read receipt is bound to the root-private audit, and the full expected audit population is checked. Component setup/security probes are not misreported as model behavior.

Root-only capture is held by an operator controller over the native loopback WebSocket connection. The evaluated Codex process remains UID 1000 and cannot read or rewrite the retained capture. Native execution and capture are not run as root. Trial security records verify zero effective capabilities, NoNewPrivs=1, seccomp filtering, and loopback-only networking. Normal native execution uses Codex danger-full-access/approval never inside this container boundary, as do the inspected stock Harbor adapter and Inspect default. It does not qualify Codex workspace-write/Landlock or automatic approval-review behavior; no outer container protection was relaxed. Neither an agent Docker socket nor privileged/unconfined execution is used. Cancellation kills the actual trial/container lifecycle, not just a fake callback.

Credential handling is inherited by identity from the secure implementation; these credential-free probes do not runtime-qualify sensitive credential handoff or redaction. Native server stderr is not captured over this WebSocket transport; protocol events and fixture outcomes are the retained execution evidence. Native event IDs provide correlation, not cryptographic proof of authentic execution. The broker is a disposable approximation. It does not establish full production gh authorization, symlink-adversarial behavior, task staging, baseline-restriction preservation or scorer parity. Its readiness requests are separately accounted setup/audit operations; the production contract for non-mutating readiness and graded audit accounting must be preserved explicitly. Arbitrary untrusted Dockerfiles are not qualified: this experiment uses reviewed operator fixtures. Shared-kernel container isolation is not a proof against kernel escape.

### Inspect's real integration

The real Inspect Task uses a mandatory operator-owned initializer before stock inspect_swe.codex_cli. Privileged sandbox.exec is host evaluation code, not a capability handed to the subprocess agent. Initialization uses timeout_retry=False, one agent attempt and retry_on_error=0. Actual unprivileged private-read/reinit/socket-deletion attempts fail. The final probe also records agent UID, effective capabilities, NoNewPrivs, seccomp and actual interfaces from inside Inspect's running sandbox, rather than inferring isolation from Compose. A separate worker receives real SIGINT only after active initialization; containers are absent afterward.

The successful sample reaches an independent actual_patch_verified check. Its log contains model events and host sandbox setup operations, but no inner Codex commandExecution/fileChange identities. Consequently the stock log cannot satisfy the evidence contract. A first run ended at a message limit while the evaluation's top-level status was success; that was rejected and the harness now checks sample error and postcondition explicitly. Missing-result denominator and task success semantics would need their own admission policy under any adoption.

Inspect's dataset, Task, solver/scorer, repetitions, sample isolation, concurrency and recovery facilities are credible functionality. Model-based scoring is source-supported but was not invoked. The synthetic fixture establishes neither GPT-5.6 Sol service compatibility nor web search, MCP, arbitrary tools, goals/review modes or production credential isolation. Web search/goals/automatic review were disabled. No assumption of feature parity is based on accepting a model name string.

### Controlled paired expansion

Only the surviving native/secure-Harbor configuration received the 20-trial matrix: five cases × two arms × two independent attempts, maximum concurrency two. Cases are activation, expected nonactivation, completed task failure, missing evidence and contradictory evidence. Both arms receive the same competing skill; only the with arm receives the synthetic target skill. Actual native reads establish the fixture's observed activation; this is not SkillEvaluator Discoverability or evidence that a real model chose a useful skill.

Expected classifications: eight completed task passes, four completed task failures, eight unavailable results, with 20 unique broker states. Incomplete/contradictory trials have null scores and never reach the verifier. Their activation is unknown, not zero. Aggregate performance is withheld because required coverage is intentionally incomplete. Correctness deltas among comparable completed pairs are zero by construction; activation controls distinguish target presence and expected nonactivation. These are infrastructure checks, not benchmark performance or a causal skill-lift claim.

## Maintenance and operational judgment

| Option | Ongoing integration burden | Main sources of complexity |
|---|---|---|
| Stock ACP/Harbor | Apparently small, but fails evidence requirement | Would need native side capture and admission anyway; additional lossy projection dependency |
| Stock Inspect SWE | Medium to high for this repository | Native capture still needed, dataset/mandatory-gate translation, metric equivalence, provenance/output adapter |
| Native + secure Harbor, conditional SE | Medium initial; low to medium recurring, smallest defensible incremental path | One native agent adapter, one secure initializer backend, schema/version qualification and evidence admission |
| Standalone native runner plus homegrown evaluator | High | Would recreate scheduling, dataset management, retries, grading, history and recovery; no demonstrated benefit |

Public release metadata shows SE 0.3–0.6 releases on Sep 17, Sep 30, Oct 6 and Oct 20; Harbor 0.24/0.25 on Oct 5/25; ACP 2.2/2.3 on Oct 10/26; Inspect 0.3.285/0.3.286 on Oct 25/28; SWE 0.2.71/0.2.72 on Sep 17/Oct 20. This is observed cadence, not a maintenance guarantee. Codex 0.165.0 is now available (Oct 27); the tested 0.164.0 remains the explicit compatibility pin, not a claim to be the latest release. SE, Harbor, ACP and Codex use Apache-2.0; Inspect AI/SWE use MIT. The public repository advisory endpoints returned no advisories for the first five projects and one Codex advisory, [GHSA-w5fx-fh39-j5rw](https://github.com/openai/codex/security/advisories/GHSA-w5fx-fh39-j5rw), a historical sandbox-boundary issue fixed in 0.39.0; its affected range excludes the tested pin. Empty repository advisory lists do not establish absence of vulnerabilities, including in dependencies. This is a source/license/public-advisory review, not a complete dependency security audit or a guarantee of future maintenance. Fast upstream iteration increases upgrade qualification work. Pin the native protocol/binary and test schema drift explicitly; do not assume generic SDK streams expose all App Server details. The separate Harbor 0.25 converter replay showed the same terminal-state loss and provides no reason to override the frozen 0.24 dependency.

Relevant open upstream reports were checked directly: [Inspect #4754](https://github.com/UKGovernmentBEIS/inspect_ai/issues/4754) concerns provider-versus-command failure provenance; [Inspect #5154](https://github.com/UKGovernmentBEIS/inspect_ai/issues/5154) concerns None-dropping denominators in custom scorer panels; [Inspect SWE #188](https://github.com/meridianlabs-ai/inspect_swe/issues/188) concerns sub-agent bookkeeping before approval outcomes. These are source/issue evidence, not three defects reproduced by this PoC. [Harbor #2676](https://github.com/harbor-framework/harbor/pull/2676) remains open; the working prototype does not depend on it. [SE #215](https://github.com/NVIDIA/SkillEvaluator/pull/215) is merged and supplies the extension mechanism in the tested later source snapshot.

A newer [Inspect 0.3.286 release](https://github.com/UKGovernmentBEIS/inspect_ai/releases/tag/0.3.286) appeared during the investigation. It tightens sandbox file-read identities and symlink-sensitive collection, avoids importing code named by recovered logs, and fixes transcript/output and approval-argument handling. These are material security changes: do not adopt 0.3.285 on the strength of its passing fixture. The immutable 0.3.286 bridge source still handles model-event sinks rather than Codex App Server command/file lifecycle events; the unchanged SWE bridge consumer does not become native execution capture through that upgrade. Its runtime behavior is UNKNOWN here, and no frozen dependency was silently overridden.

Reuse under the recommended path is broad: authored/APM skills, dataset content, deterministic oracle logic, planner, history, provenance rules and the canonical report can remain. The Codex execution witness changes, and each affected scorer input/meaning must be qualified rather than automatically carried over. Inspect can also reuse those authored inputs and downstream reporting, but would require more task/staging/metric translation. Both frameworks can host additional suites; neither automatically supplies the security semantics of a future fixture.

The installed-plugin interface is supported in the tested SE snapshot, but importing/subclassing its secure environment remains version-coupled Python integration. Pin and regression-test that boundary; this is not a guarantee of a stable cross-version ABI.

Inspect may become preferable if SE's released secure extension contract or semantic correctness cannot be qualified. Its core can host a native App Server agent through supported solver/agent/sandbox interfaces. That path was not implemented here after the stock capture gate failed: building another native adapter would not test a materially different evidence contract. This is an unqualified alternative, not an eliminated framework.

## Hosted controls, reproducibility and retained evidence

Development is confined to the experiment clone/branch and one new experiment workflow. The workflow triggers only branch pushes with matching experiment paths; this works without adding workflow_dispatch to main. No PR was required, avoiding unrelated production PR jobs. It has contents:read, SHA-pinned actions, no persisted checkout credentials, no repository secrets or protected environments, serialized concurrency, 25-minute job/20-minute execution bounds, no schedule and seven-day artifacts. Each trial is bounded to two CPUs, 1 GiB memory and 128 processes. Dependencies are prepared before network-isolated agent trials. Artifact export is bounded to fewer than 1,024 files and 16 MiB; native wire capture has an 8 MiB bound.

The checked-in bootstrap and lock files reproduce hosted preparation and trial execution. acp_replay.mjs invokes the pinned upstream reporters/renderer; harbor_conversion.py invokes the actual upstream converter. Neither is a substitute parser. The replay uses a private converter API only for investigation, not as an adoption extension mechanism. ACP was not qualified as a complete installed session, and Harbor 0.25 was not container-qualified.

Evidence classes are kept distinct: inspected production contracts; source-supported APIs; actual local container Codex controls; actual hosted framework/container lifecycle; real native capture replay through framework conversion; and synthetic poison controls. Original native bytes are preserved separately from projected ACP/ATIF and fault-injected in-memory copies. Raw captures, private-fixture receipts and result files remain non-sensitive synthetic artifacts, not canonical report/history entries.

Failures retained during development include a diagnostic TypeError masking an expected initializer failure (found by independent artifact review despite green CI, then corrected with exact failure-type/reason assertions), verifier ownership/permission errors, the rejected copy ownership approach, message-limit incompleteness, and the initial expanded run's too-small artifact file cap. They are not counted as passing qualification. The original production checkout remains on its original main revision with its pre-existing untracked files preserved. No production evaluator/configuration, historical measurement, report pipeline, protection rule or dispatch enablement was changed. No upstream issue/contribution was submitted.

## Smallest practical adoption path and production gates

1. Keep today's production architecture and conservative unsupported-evidence handling while reviewing this target. Require a released supported SE backend interface, or explicitly approve and qualify an immutable source snapshot; do not call the post-release snapshot the 0.6.0 release. Keep the frozen Harbor dependency until independently justified.
2. Build one narrowly scoped native App Server agent adapter and one required operator initializer profile. Generalize admission beyond this exact scripted fixture: bind every thread/turn/item population, request/approval/execution outcome, unknown event, stream termination, output truncation and artifact relationship; reject absent/contradictory scope. Preserve raw transport and coverage, and never copy one wrapper result into multiple inner operations.
3. Exercise the actual SkillEvaluator paired CLI/staging/provenance path on existing Podman and gh credential-free fixtures. Preserve baseline guard prohibitions, independently initialized attempts, non-mutating readiness, stale/symlink/substitution defenses, the complete broker authorization oracle, cancellation during initialization and execution, and missing-profile rejection. Re-run existing offline/integration/security regressions. Qualify Pester's diagnostic runtime separately. This PoC does not satisfy these entire production gates.
4. Retain deterministic mandatory gates and metric definitions explicitly. Compare activation, task correctness, grader judgment and demonstrated execution separately. New policy/runtime/dataset identities start new cohorts; historical values remain unchanged. Future importer maps admitted observations into the existing evidence schema and canonical planner/history/Pages pipeline, preserving native source references and unavailable coverage. No dashboard or history store is needed.
5. Only after separate production-change approval, install the qualified adapter/backend and perform inference-free end-to-end publication-admission checks. Paid paired model qualification remains a separately authorized step; it was not performed here. Do not enable recurring dispatch, merge experiments or reinterpret old scores as a consequence of this investigation.

No change to the requested security constraints is needed for the successful container experiments. Remaining blockers concern released extension availability and unqualified production-path/semantic behavior, not missing Docker access.

## Primary source references

- [Official App Server protocol](https://learn.chatgpt.com/docs/app-server): the item/turn lifecycle, approvals and native observations; observed behavior here is tied to the pinned binary, rather than assumed from rolling documentation.
- [SE backend specification](https://github.com/NVIDIA/SkillEvaluator/blob/d9fa4b4041b31f417f02ed145999ecf1f0c11fcd/src/skillevaluator/tier3_environments.py) and [secure Docker implementation](https://github.com/NVIDIA/SkillEvaluator/blob/d9fa4b4041b31f417f02ed145999ecf1f0c11fcd/src/skillevaluator/tier3/harbor/secure_docker_environment.py).
- [Harbor ACP converter](https://github.com/harbor-framework/harbor/blob/b53b8134e1241686dca7759af188f987ecc48e8b/src/harbor/agents/installed/acp.py) and [codex-acp reporters](https://github.com/agentclientprotocol/codex-acp/tree/344a520632e4c8c02f781a7a20490dfac52d4d0a/src/tool-calls/reporters).
- [Inspect AI pinned source](https://github.com/UKGovernmentBEIS/inspect_ai/tree/d1536eae98d7b8b9364c052f0e6d3de988e1aac9), [Inspect SWE pinned source](https://github.com/meridianlabs-ai/inspect_swe/tree/6665c30bced70dbf5c17ed935a2da1024668c6f9), and [repository issue #86](https://github.com/thetechgy/agent-engineering-baseline/issues/86).

## Final run and artifact admission

The [final hosted run 40735637067](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/40735637067) passed all experimental job steps in 6m27s at exact runtime-code revision `6af0587664cca0af3996594cc028a449b4520899`, attempt 1. Later report/result commits do not change that tested runtime/workflow tree and intentionally do not trigger another experiment.

Authenticated artifact ID: `12837322910`; archive SHA-256: `70aca889c3165cad7091e391b29db4866b5b4efba34240475f44cbd824889bbe`. The archive is 1,117,098 bytes compressed, with 363 members and 3,958,397 bytes uncompressed. Digest, bounded paths/extraction, exact failure reasons, sample postconditions, state uniqueness and cleanup were independently rechecked from the downloaded artifact. GitHub retention expires **2026-11-04 17:33:41 UTC**; a downloaded copy and extracted original evidence remain locally outside the production checkout.

| Final assertion | Observed outcome |
|---|---|
| Harbor, paired matrix, Inspect normal, Inspect failure/cancel entrypoints | All four exit codes zero |
| Matrix completed passes / completed failures / unavailable | 8 / 4 / 8; no aggregate performance score |
| Independent matrix broker states | 20 distinct identities |
| Focused real initializer failure | RuntimeError: required initializer failed (exit 1); no agent setup or verifier |
| Missing / contradictory admission failures | Exact ValueError reasons; no verifier |
| Hostile cwd module substitution | Isolated operator imports succeed in both frameworks; unsafe local control fails before the fix |
| Harbor teardown | Zero containers, networks, volumes or per-project images across 6 focused + 20 matrix projects |
| Inspect normal | Verified actual patch, no sample error, two mock model events, measured UID 1000 / CapEff 0 / NoNewPrivs 1 / Seccomp 2 / loopback only |
| Inspect failure / cancellation | Intended initialization error / real cancellation recorded; no model events and no remaining Inspect containers |

Retained review material: [machine-readable qualification](skill-evaluation-architecture-results/qualification.json), [representative original protected native capture](skill-evaluation-architecture-results/native-example), [local failing-before/passing-after substitution control](skill-evaluation-architecture-results/import-substitution-control.json), [maintenance snapshot](skill-evaluation-architecture-results/maintenance-snapshot.json), and [the artifact inspection utility](skill-evaluation-architecture-results/verify_artifact.py). The utility reads bounded ZIP/JSON content without importing models or executing producer artifacts; it is an investigation utility, not a replacement for production publisher admission.

These results qualify the bounded infrastructure probes. They do not turn the eight unavailable controls into zero scores, qualify a provider-backed model, close issue #86's complete production-path contract, or authorize migration.
