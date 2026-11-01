# Code Mode evidence: measured results and recommendation

This report extends, and does not revise, [PR #109](https://github.com/thetechgy/agent-engineering-baseline/pull/109),
its [native qualification](../native-codex-qualification-results.md), and the
[preceding architecture investigation](../skill-evaluation-architecture-results.md).
All model responses in this experiment were canned locally. No inference, judge,
benchmark dispatch, production migration or historical rescoring was performed.

## Recommendation

For the unchanged gh attempt-authorization requirement, prioritize the observed
Code Mode host for the next bounded qualification. It is the only demonstrated
route here that retains the intended model's default Code Mode and observes
callbacks lost before gRPC forwarding. This is a recommendation to qualify an
integration, not to deploy this prototype.

| Rank for the existing full contract | Actual option | Fidelity / security | Compatibility / coverage | Maintenance / practical decision |
|---|---|---|---|---|
| 1 | Conditional host/runtime observation patch | Callback census plus explicit argument uncertainty; protected helper boundary tested within the stated profile | Original Code Mode; actual command denial and early-loss controls; other tools and full paired lifecycle unqualified | Custom Rust/V8 builds and an observer boundary are substantial obligations; strongest faithful candidate, not production-ready |
| 2 | Direct Mode through `model_catalog_json` | Original direct arguments and native denial observable; protected App Server transport exercised | Tool catalog genuinely advertised on both releases; actual provider compatibility unknown; separate evaluation conditions | Prefer this smaller supported runtime surface if provider compatibility and the changed cohort are acceptable; no claim that the provider supports the override |
| 3 | Separately versioned outcome-security diagnostics | Independently checked outcomes can be useful; incomplete attempt evidence remains unknown | Compatible with either mode; only partial replacement of the requested evaluation capability | Best immediate diagnostic option, but cannot satisfy or replace existing `gh_authorization` / `gh_gate` |
| 4 | Stock external host alone | Forwarded arguments and IDs are useful; callback completeness fails on both releases | Stock Code Mode and exact denied escalation work; pre-forward losses remain invisible | No fork, but fails the decisive requirement; unsuitable as a complete attempt ledger |

The outcome design ranks first for obtaining honest limited diagnostics with the
least new runtime ownership. Direct Mode ranks first for potential long-term
maintenance if the changed conditions and real provider are qualified. The patch
ranks first only for retaining the current Code Mode conditions while pursuing
the original attempt contract. These distinctions prevent passing tests from
being mistaken for an unconditional architectural winner.

These results do not favor retaining or replacing an evaluator framework. A
framework cannot reconstruct arguments lost before its observation boundary.
Select the smallest framework integration only after the producer and trusted
initializer pass the same admission/oracle requirements; no paired evaluator
or framework-performance advantage was demonstrated here.

## Decisive stock and Direct Mode results

Official 0.166.0 is primary; 0.165.0 is a focused control. Each used matching CLI,
host, bundled catalog and generated protocol bindings. Source commits, archive
hashes, toolchain and V8 identities are in [README.md](README.md).

| Control | 0.166.0 / 0.165.0 result | Meaning |
|---|---|---|
| Empty cell | `control-finished`, zero forwarded calls, final sequence zero | No callback control |
| Ordinary callback | One forwarded call, sequence one | Positive forwarding control |
| Caught BigInt serialization failure | Same terminal text as empty; zero forwarded calls, final zero | An actual callback can disappear before the forwarding ledger |
| Caught 64 MiB expanded input | Same terminal text as empty; zero forwarded calls, final zero | Successful input expansion can still be rejected before forwarding |
| Exact PR #109 uncaught escalation | Original `cmd`, `sandbox_permissions` and `justification` retained; denial correlated by invocation | External gRPC solves this particular public-event gap |
| Caught denied escalation versus empty | Both print `control-finished`; external host distinguishes one forwarded call from zero; public command items both empty | Output and item populations are insufficient; original gRPC arguments matter |
| Omitted versus null argument | Absent `input_json` versus four-byte JSON null | Presence is part of the argument contract |
| Unawaited call | Forwarded population and final sequence reconciled; callback census checked independently in patched host | Cross-stream arrival order is not evidence loss; forwarding and callback totals are different |
| Direct catalog override | `exec_command` advertised, `exec` absent; original direct arguments and denial observed | Runtime feasibility established; provider compatibility not tested |

The actual default catalog advertised `exec`, `wait`, `request_user_input` and
collaboration tools. The Direct catalog advertised `exec_command`, `write_stdin`,
`request_user_input`, `apply_patch`, `view_image`, goal tools and collaboration
tools. Only the exercised command paths are runtime-qualified by these controls;
advertisement does not prove every tool family works.

The Direct profile retains the intended `gpt-5.6-sol` entry from the matching
bundled catalog and changes only its `tool_mode` to `direct`. Disabling the host
or forcing a tool absent from the catalog is not used as a workaround. No real
provider endpoint was contacted, so there is no supported-provider conclusion.

## Patch, observation and security results

The patch adds 93 Rust lines across five bundled-runtime files, including two
test constructors. No Codex core, authorization, dispatch, execution policy or
model-visible tool schema is patched. The build-only workspace version repair
changes no external dependency selection or checksum.

The first successful build and four callback controls ran at
[`24447dec`](https://github.com/thetechgy/agent-engineering-baseline/commit/24447dec9416fa8d878293d798c291abca4c29f1),
[run 41326099147](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/41326099147).
The unmodified and patched release initially both rejected `--locked`: 170 local
workspace version stamps in the release manifest differed from Cargo.lock.
The guarded normalization validates the exact structural delta and keeps every
external source/checksum/dependency field. A diagnostic resolver lock was never
used to compile.

The final [hosted run 41341470944](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/41341470944)
passed at runtime/workflow source `21b3c4b0f89021b0934360606f3cf20a462aa220`
(attempt 1). Its cold build took 14m32s and complete job 19m0s. Artifact
`13098367148`: SHA-256
`06d2284b5a611383143c459a6465ce00ee57dbc76adce7d7118098ed4e7e1046`,
1,659,201 compressed bytes, 42 members and 7,294,978 uncompressed bytes.
This is a passing bounded experiment, not production qualification.

| Actual patched control | Callback census / arguments | Retained result |
|---|---|---|
| Seven low-level scopes | Empty zero; each other scope one callback | BigInt has entry without serialized arguments; 64 MiB input is explicitly incomplete; omitted/null differ; unawaited callback remains visible |
| Native empty versus denied | Zero versus one, closed scopes; denied arguments complete | Outer native call ID joins Execute, runtime ID, invocation, original arguments and the denial completion |
| Native oversized command | One callback, incomplete arguments; zero forwarded calls | Completeness of the callback population does not become completeness of its arguments or a clean security result |
| Actual isolation command | Complete scoped callback and native invocation | Separate namespaces, no helper journal/backend access, forged agent-local journal does not replace the observer file; foreign bind and post-admission attachment fail |
| Unauthorized client before admission | Rejected without consuming the seed slot | Single authorized connection admitted before evaluated JavaScript; listener then closed |
| Transport cut with producer alive | Real socket closure; original host process remains alive | Native outer trial still reports `completed`; observer continuity is unavailable regardless of that status |
| Host SIGKILL and same-endpoint replacement | Callback prefix without scope closure; new container instance and session | Original producer failure detected; missing closure and replacement continuity classified unavailable |

The operator harness verifies binary hashes, container instance/lifecycle,
separate PID/network/mount namespaces, UID 1000, zero effective capabilities,
no-new-privileges and default seccomp, no mounts/engine socket, resource limits,
internal isolated network configuration and actual bridge addressing. Container
and network cleanup was checked. This is an operator/kernel isolation boundary,
not cryptographic attestation or authentication by IP address alone. It assumes
no untrusted task setup runs before the connection is seeded. Reconnection is
intentionally unavailable in this profile.

The original Direct/socketpair producer controls also passed: FD 0/1 injection,
ptrace, process-memory/pidfd access and forged output did not produce an accepted
forged native item; producer termination became unavailable. The allowed effect
file existed with expected bytes; the denied counterpart was absent. That
independent check covers only the named fixture file.

[Reviewed runtime summary](results/runtime-summary.json) and
[offline observation checks](results/offline-observation.json) retain sanitized
results. The trusted [data-only checker](results/verify_observation.py) was run
locally against the digest-verified final archive after the hosted run. It
reconciles scope counts, serialized presence/completeness, outer/runtime/native
IDs and forwarded sequences. Six explicitly synthetic mutations cover missing
closure, missing entry, wrong outer ID, wrong producer hash, observer loss and
incomplete arguments; none establishes complete arguments plus a clean census.
The actual killed-host prefix also fails closure validation. Producer
authentication remains a separate operator prerequisite, and production security
admission remains unavailable even for valid experimental censuses.

All seven scripted terminal texts matched between official stock and patched
0.166.0 hosts. Original serialized inputs/presence matched for the awaited
forwarded controls. This is bounded behavior evidence; timings, IDs and unawaited
forwarding races are not asserted identical, and no model-quality comparison was
performed.

Callback entry establishes that a registered V8 callback actually ran. A missing
serialization result or bounded incomplete payload does not establish its full
arguments. Runtime identity assignment is not dispatch acceptance. gRPC completion is a
core-reported outcome, and an independently checked fixture effect is a separate
claim. The complete observation-stage table is in [README.md](README.md).

## Release changes and maintenance judgment

The [official 0.166.0 release](https://github.com/openai/codex/releases/tag/rust-v0.166.0)
changes protocol fields, host admission/replacement and V8 infrastructure.
The release-matched schema adds metrics, output-truncation negotiation and
Wait/Terminate token budgets. The actual stock host leaves selected truncation
absent for default, client and server requests. Tests therefore retain the client
truncation expectation; schema availability is not feature support.

Source review shows local process-owned recovery moved to session admission,
metrics cannot spawn a replacement, and provider-wide generations prevent a
per-session counter from establishing continuity. Actual external-URL transport
controls demonstrate same-endpoint reconnection to a different host. Session IDs,
PIDs and sequence numbers supply correlation, not producer authenticity. No
0.165/0.166 cross-version interoperability is assumed or tested.

The first cold Cargo dev build took 12m43s; its complete job took 15m18s. The
recipe needs Rust 1.95.0, a pinned V8 git dependency, verified official V8 archive
and target-matched bindings, and the guarded workspace-lock repair. Cargo also
fetches a broad submodule graph. Those are real maintenance costs even though
the Rust patch is small. The harness and private observer require substantially
more code and review than the patch itself.

This experiment establishes a pinned build recipe, not bitwise reproducibility,
optimized release distribution, canonical Bazel/source-V8 parity or a supported
upgrade process. The [source-only check](results/source-compatibility.json) verifies the original
0.165.0 files and all five patch targets; no patched 0.165.0 binary was qualified. A future distribution needs
immutable checksummed output, trusted build provenance and regression gates for
callback census, argument semantics/limits, dispatch correlation, closure,
producer admission, interruption/replacement and behavior. No custom executable
is published here.

## Evidence and remaining adoption gates

[manifest.json](results/manifest.json) records every hosted attempt, source,
artifact ID and digest, including failed and cancelled attempts. Cancelled runs
remain inconclusive. Raw archives and authenticated GitHub metadata are retained
privately as data; [verify_archives.py](verify_archives.py) checks identity,
digests, safe member paths and bounds without extraction or execution. Published
summaries omit raw diagnostic paths, container addressing and captured arguments.

Failed and superseded attempts remain visible. Runs `41323971680` and
`41325034647` passed their bounded controls while documenting the unmodified and
patched lock/build failure; their green status is not a successful patch build.
Runs `41323275576`, `41329327476` and `41340955992` were cancelled for known
replacement revisions. The boundary-first runs `41329706826`, `41338286587`,
`41338806947` and `41339668467` failed on a missing harness flag, copied executable
mode, listener lifecycle deadlock and an IPv4-filtered bridge inventory check,
respectively. Those failures were preserved and fixed without relaxing the
boundary assertions. The full final run passed after those corrections.

The following remain unqualified: the full upstream host/runtime test suite; real-provider Direct Mode; all tool families
and concurrent/multi-agent sessions; compressed proxy behavior; release packaging;
full production sandbox support; operator initializer and both comparison arms
through the actual evaluator; complete gh receipt/readiness/cancellation/oracle
parity; native metric projection; collector/reference admission and signed
provenance. None is inherited from a passing protocol test.

`security-evidence-v1` is a synthetic policy prototype accepting trusted facts,
not a native-capture importer. The independently checked allowed/denied file
control proves only its named file effect. Existing Podman recommendation/artifact
assertions and gh broker-owned transition/result/budget diagnostics could proceed
under new metric and condition identities. Absence-of-attempt claims, full
issued-call bounds and the existing gh mandatory conjunction remain unavailable
where capture is incomplete. Known unsafe attempts remain violations even if
denied. No unavailable result becomes zero or a clean security score.

Production files, protected workflows, historical scoring, all prior evidence
and PR #109 remain unchanged. The only added workflow is the dedicated
inference-free experiment on `experiment/code-mode-evidence-166`; automated
benchmarks remain disabled.

## Delivery validation

The hosted runtime/workflow source is `21b3c4b0f89021b0934360606f3cf20a462aa220`.
Report delivery adds documentation, reviewed JSON and the locally run data-only
checker; it changes no tested runtime/workflow file. Python compilation, Bash
syntax, Markdown checks, archive identity/digest/bounds verification, observation
checks and final diff scope checks passed locally. A documentation/results-only
commit is excluded from the experimental workflow to avoid a redundant cold
build. No claim is made that unrelated repository test suites were rerun.
