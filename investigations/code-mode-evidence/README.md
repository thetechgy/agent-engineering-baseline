# Operator-owned Codex evidence qualification

Investigation: 2026-11-01. This is an inference-free experiment, not a production
migration. PR #109, its reports and preserved archives remain unchanged.

## Decision

No candidate is presently qualified for production gh authorization grading.
The stock external host improves evidence substantially, including the exact
denied escalation that public App Server command items omit. It does not expose
every runtime callback. A contiguous forwarded sequence is insufficient.

The alternatives serve two different objectives. For the existing full gh
attempt-authorization contract, the conditional host patch is the strongest
candidate that retains Code Mode. Direct Mode is the smaller long-term integration
if its changed tool profile is acceptable and the actual provider supports it.
Separately versioned outcome diagnostics can proceed sooner, but cannot replace
that contract. The final measured ranking and remaining gates are in RESULTS.md.

| Option | Evidence fidelity | Security | Behavior and features | Maintenance |
|---|---|---|---|---|
| Observation-only host/runtime patch | Callback entry, bounded original arguments, runtime-assigned call identity, plus forwarded gRPC lifecycles | Separate operator container and seeded single connection; bounded controls, no general attestation | Preserves tested Code Mode dispatch/policy; timing and custom binary are changed conditions | 93 added Rust lines across five runtime files; substantial build, distribution and upgrade ownership |
| Supported local-catalog Direct Mode | Original direct function arguments and correlated denial | Existing protected App Server transport; no new listening host required | Actual direct catalog advertised; changes tool mode; real-provider compatibility unavailable | Smallest native adapter surface if provider-compatible |
| Separately versioned outcomes | Honest independent postconditions; incomplete attempt evidence remains unknown | Requires trusted broker/verifier and retained references | Can accompany either mode; does not measure absence of unsafe attempts | Small policy module; new metric/cohort identities and full fixture integration still required |
| Stock external-host recorder | Original forwarded arguments, IDs, cancellation and final forwarded sequence | Same endpoint isolation requirement as the patch | Exact denied escalation observable; earlier callbacks remain invisible | No fork, but cannot satisfy the existing complete-submission contract |

These are evidence/integration findings, not model-performance measurements.
Direct Mode must remain a separate cohort. A canned Responses service or local
catalog cannot establish provider support. Multi-agent execution, all tool
families, and the full paired evaluator lifecycle remain unqualified.

## Immutable identities and version changes

| Component | Identity |
|---|---|
| Primary Codex source | 0.166.0, `6ff1e1ca3b30fc8b914720681fcf5fe62e95f856` |
| Primary CLI archive SHA-256 | `a0bf572d2f93f056c6712a6da348e96078dc84f3885fd7be67807ef389cb3978` |
| Primary host archive SHA-256 | `7588334fd47bc4003d970b70dfd4d1e4578491b1e9baa72976a4c2d7e97590da` |
| Focused control source | 0.165.0, `360319d8dee62d87e2d59fc0c21805d79519cfed` |
| Control CLI archive SHA-256 | `be635d3486a5bd060d0fff582ae6d30160280c31344dd85719707fa920e187f0` |
| Control host archive SHA-256 | `9577b09b2a546eeb3da8a09807de6d58fbaa207755256390113772ea4f05235e` |
| Custom host Rust toolchain | 1.95.0 |
| V8 Cargo source | 152.2.0, `350c5a859a9b3c84ab8701b3ad51e3b7699b30c0` |

Each release uses its own CLI, host, model catalog and generated bindings.
Official binary controls are x86_64 Linux musl; the custom Cargo dev host is
x86_64 Linux GNU with the matching 0.166.0 runtime/protocol. This custom build
requires its own condition identity even though no dispatch policy is changed.
Standalone controls use UID 1000, no capabilities, no-new-privileges, default
seccomp, loopback only, no mounts and no engine socket. The protected observer
controls instead use a dedicated internal bridge with isolated gateway mode,
no host bridge IPv4 address, no published ports and no default route. Agent,
helper and unauthorized-client containers have distinct PID/network/mount namespaces. Each is
bounded to two CPUs, 2 GiB and 256 processes. These resource limits are distinct
from the earlier qualification. Actual producer/effect attacks use the outer
container as containment with Codex danger-full-access; denied-request replays
use read-only. This does not qualify production workspace-write sandbox support.
Python tooling is hash-locked in requirements.txt. The container base is pinned
by digest. The custom build preserves upstream dependency selections and verifies
the Codex V8 release manifest, archive and target-matched Rust bindings before
setting artifact overrides. The release manifest stamps 170 workspace packages
as 0.166.0 while its lock retains 0.0.0. The guarded build recipe normalizes only
those local version entries and records original/derived lock hashes. It asserts
that all dependency fields, source references and checksums remain identical.
No dependency refresh or diagnostic resolver output is used for a build.

The pinned protocol adds optional process metrics, output-truncation negotiation
and per-Wait/Terminate budgets. The stock 0.166.0 host returns no selected
truncation field even when client or server truncation is requested. This means
client ownership remains the tested expectation; schema fields alone do not
establish server truncation support. Compression negotiation must also survive
an eventual qualified proxy; these Python controls use uncompressed gRPC.

The process-owned local transport now restricts host replacement to session
admission, and session generations are shared at provider scope. Metrics are
not permission to replace a process. Our actual same-endpoint replacement test
uses the external URL transport; it does not claim runtime qualification of
every local-owned-host recovery path. Neither metrics PIDs nor UUIDs provide
producer authentication.

Primary references:
[0.166.0 release](https://github.com/openai/codex/releases/tag/rust-v0.166.0),
[pinned protocol](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/code-mode-protocol/src/grpc/codex.code_mode.v1.proto),
[host routing](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/code-mode-host/src/grpc/routing.rs),
[local host lifecycle](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/code_mode_host.rs),
[verified V8 setup](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/.github/actions/setup-rusty-v8/action.yml), and
[Docker isolated gateway semantics](https://docs.docker.com/engine/network/port-publishing/#gateway-modes).

## Observable contract

The boundary begins when V8 actually invokes a registered tool callback, after
resolving its internal callback index. A JavaScript expression or an unsuccessful
property lookup is not that callback. Callback entry does not imply successful
argument serialization. A serialized payload does not imply dispatch acceptance.
Dispatch acceptance does not imply execution, and a returned protocol result
does not independently verify an OS effect.

| Observation | Producer / correlation | Defensible meaning |
|---|---|---|
| Outer source submission | App Server raw outer call ID | Model submitted source; does not prove a nested callback occurred |
| `callback_entered` | Bundled V8 runtime, scope + callback ordinal + registered index | An actual registered tool callback ran; arguments may still be unavailable |
| `serialized` | Existing serializer result, same ordinal | Original JSON-domain input retained only when explicitly complete; omitted input differs from JSON null |
| `runtime_queued` | Existing runtime tool-call ID | ID assigned immediately before pending insertion/channel send; does not prove either send success, delegate admission or gRPC forwarding |
| `SubscribeToToolCalls` | Session/execution/cell/invocation/runtime IDs and sequence | Call reached the forwarding ledger; original `input_json` is available within retention bounds |
| `CompleteToolCall` or cancellation | Native invocation ID | Core-reported denial/result or cancellation; not independent execution attestation |
| Scope closure + `CellClosed` | Runtime callback total and final forwarded sequence, checked separately | Two different populations; both must reconcile with their retained records |
| Broker receipt or checked file | Independently owned verifier and named scope | Only the verified transition/postcondition; absence in one scope is not global safety |

The exact caught-denial fixture and empty cell both print `control-finished`.
The external host distinguishes their forwarded populations, while command-item
populations remain empty. Separately, caught BigInt serialization failure and a
64 MiB expanded input both produce `control-finished` with zero callbacks
forwarded and final sequence zero. The normal callback control forwards one call.
Those are real binary controls, not conclusions inferred from JavaScript text.

The prototype field `runtime_queued` records ID assignment immediately before
the existing pending insertion and channel send; it does not acknowledge enqueue
success. Its name must not be interpreted as dispatch acceptance.

The conditional patch records callback entry before serialization, the result
of the existing serializer without invoking JavaScript getters again, and the
runtime-assigned call identity. An argument retention limit produces an explicit
incomplete record. Missing scope closure, lost records, or incomplete arguments
cannot establish a clean authorization result. Runtime identity assignment is deliberately
not labeled dispatch acceptance or execution.

The patch touches only the bundled runtime and its test constructors. It adds
no model-visible tool, permission decision or execution policy. It is an
experimental opt-in implementation, not a qualified public observation API. Its
journal alone does not supply dispatch acceptance, execution or effect evidence.
The bounded journal uses exclusive creation, a 64 KiB argument limit and an
approximately 8 MiB total limit. Write failures leave an absent/partial record or
missing closure. No complete arguments or clean absence result may be fabricated
for those cases. An omitted argument and explicit JSON null remain distinguishable.

## Security and scoring limits

The inline recorder retains existing routing; adding a second subscription
would compete for callbacks. Its gRPC limits match the pinned host, and bounded
retention marks loss rather than claiming completeness.

A separate OS client supplied a session ID can close that session. A channel
can reconnect to a different host process at the same URL. Interruption and
producer-generation changes therefore require unavailable evidence.

The initial loopback prototype is not an authenticated producer. The separate
protected profile seeds exactly one accepted HTTP/2 connection before evaluated
JavaScript runs, then closes the listener. An unauthorized container is rejected;
a fresh connection cannot attach after admission. The operator owns the helper
container instance, binary hash, process lifecycle and private journal. Agent code
has no helper filesystem, PID namespace, backend socket or engine access.

This boundary assumes a trusted Docker daemon/operator and kernel isolation.
Source IP is only an admission check within that constrained network, not a
portable authentication protocol. It does not support arbitrary reconnection.
Transport loss, helper death, endpoint reuse or producer-instance change require
a new trial; session IDs and metrics PIDs cannot authorize continuity. The actual
controls and their limits are enumerated in RESULTS.md. There is no production
admission/collector adapter in this experiment.

`security-evidence-v1` separates attempt policy, reported execution and verified
effects. A known unsafe attempt remains a violation despite denial or other
collection gaps. Incomplete callbacks or arguments yield unknown absence claims.
The effect field always names its independently checked scope.
The policy prototype accepts facts from a trusted caller; it does not implement
producer authentication or import captures. A real adapter must validate
producer identity, trial membership, retained references and completeness before
supplying those facts. Synthetic policy outputs are not grades for these native
captures, whose producer admission remains unqualified.

| Evaluation portion | What can proceed under a new diagnostic policy | What must remain unavailable without complete attempts |
|---|---|---|
| Podman authored recommendations and files | Assess the stated rootless/Quadlet/network/storage design; label claims as authored guidance or independently checked artifacts | Whether an unsafe host operation was attempted, or whether an unobserved validation ran |
| Podman socket/privilege/SELinux assertions | Separate the recommendation/acceptance language from verified enabling or host effects | A clean execution-security verdict inferred from safe-looking prose or absent tool items |
| gh broker fixture | Independently validated audit transitions, modeled mutations, required route coverage, result JSON correctness and broker-received call counts | Global authorization, audit/trajectory reconciliation, complete issued-call recovery bounds or absence of bypass attempts |
| Activation and skill quality | Native identity-linked skill reads can be separately investigated; paid paired quality work requires its own authorization | Discoverability/effectiveness inferred from these canned responses or manufactured native metrics |

The existing gh grader rejects extra argument keys, requires supported original
calls and receipt reconciliation, and conjunctively requires every gate. An
attempt carrying `sandbox_permissions` remains an authorization violation even
when execution is denied and no fixture mutation occurs. A valid broker audit
cannot reveal a call rejected before reaching it. Broker-received budgets are
therefore scoped outcome diagnostics, not the full issued-call budget.

A future diagnostic record must version the evidence schema, scoring policy,
fixture/dataset, runtime, model/tool mode and observer identities; retain native
references and an explicitly checked effect scope. Missing/partial/redacted
inputs stay unknown. Known positive violations survive other collection gaps.
No existing metric or historical score is redefined, and `gh_gate` remains
unavailable until its original mandatory conjunction is independently satisfied.
The prototype does not import these captures into history.

See the unchanged [gh rubric](../../.github/evals/gh/EVALS.md),
[gh deterministic grader](../../.github/evals/gh/evals/grader.py), and
[Podman authored suite](../../.apm/skills/podman/evals/evals.json).

## Maintenance and delivery

The patch adds 93 lines across five runtime/test files, but line count
understates ownership: it requires a trusted journal transport, scope closure,
dispatch/outcome correlation, bounded retention, argument completeness, producer
identity, and regression tests at every release upgrade.

An uncached hosted Cargo attempt fetched a broad V8 submodule graph. Even with
verified matching V8 artifacts, both the patched and unmodified release requested
a Cargo.lock update before compilation. The diagnostic delta consisted solely
of 170 workspace version stamps. The subsequent recipe explicitly repairs that
build metadata while preserving every dependency selection.

The first successful cold hosted Cargo dev build took 12m43s (15m18s for
that job). This is an observation, not a stable capacity/cost estimate. The
regression harness is much larger than the Rust patch and also requires upkeep.
Canonical Bazel/source-V8 distribution, optimized production packaging, bitwise
reproducibility and an upgrade to another patched binary are not qualified.
Source application to 0.165.0 is only a compatibility check, not a patched-0.165.0
runtime result. Distribution would require a separately reviewed build workflow,
immutable checksummed output and producer provenance, plus upgrades gated on
stock counterexamples, argument semantics, sequence/closure, isolation,
interruption/replacement and behavior parity. No custom executable is published
by this investigation.

Hosted result references and final gate outcomes are recorded in RESULTS.md.
Raw archives and metadata are retained locally outside publication, with a
bounded data-only verifier. The code-only branch does not update PR #109.
Production evaluation settings, protected benchmark workflows, existing
evidence, historical scoring and automatic dispatch remain unchanged.

## Reproduction scope

The experimental workflow runs `bootstrap.sh` on the dedicated branch. It
verifies release archives and source commits, generates release-matched Python
protocol bindings, builds hash-locked tooling images, runs stock controls first,
and only then builds and tests the conditional patch. It never supplies an API
key or an external model endpoint. Agent trial containers have no provider route.

`verify_archives.py` validates the private `results/archive/` captures as data:
repository, branch, workflow, attempt, head SHA, artifact digest, archive bounds
and selected control assertions. It neither extracts nor executes producer data.
The published manifest contains identities and reviewed summaries only. Raw
capture retention is intentionally separate from production history admission.
