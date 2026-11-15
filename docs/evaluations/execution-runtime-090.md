# Opt-in 0.9.0 execution preparation

**November 15 execution update:** the separately authorized
[single pilot stopped before Codex launch](gh-runtime-090-v1/execution/EXECUTION.md).
The allocation is closed, including the unlaunched absent-skill slot. PR #143 remains
unmerged. The original preparation contract and UNRUN/UNAPPROVED proposal below
are retained as pre-execution history; they grant no continuation or replacement.

Starting main was verified at `15caaedb82edf5d9e0253394ed99e3135cd7be93`,
the completed merge of #142. This change prepares `gh-runtime-090-v1` through
`evaluation-campaign.yml`. The default selection and production Benchmark remain
0.3.0 / Harbor 0.13.2. All paid allocations remain closed. No preparation receipt
is live-provider evidence or an authorization.

[Draft PR #143](https://github.com/thetechgy/agent-engineering-baseline/pull/143) records the executable revision, selected CI, hosted preparation
and fresh-runner consumption receipts. Until those pass, this is not pilot-ready.
The immutable `behavioral-090-offline-v1` profile and #142 receipts are retained;
its simulated default judgments are not relabeled as live judgments.

## Execution and ownership

The explicit `codex-090-diagnostic-v1` runtime selects existing pinned
`candidate-next`: Python 3.14.10, SkillEvaluator 0.9.0 at `b78d146`, Harbor 0.25.0,
offline-v3 patch, frozen lock and trusted gh backend 1.1.0. Source, lock, patch,
backend and installed dependencies are checked by their existing owners.

`evaluation_campaign.py` owns staging, the durable schedule, native Harbor
single-trial launches, collection before disposal, retained failures and reporting.
The existing protocol owns authentication, source/artifact admission, one dispatch,
accounting and stops. `evaluation_runtime.py`, `evaluation_codex.py` and the shared
pilot adapter own CLI/configuration/events/usage. `GhFixture` owns the original
`gh-014` prompt, public fixture, protected broker and independent deterministic
grader. No Pester runner, skill change or second campaign framework is introduced.

| Boundary | Effective route |
| --- | --- |
| Agent executable | Official Codex **0.155.1**, absolute `/opt/codex/bin/codex`; reviewed package, binary and required helper hashes in `codex-execution-090.json`; version/hash checked again at launch |
| Agent model | **gpt-5.6-sol**, **high** reasoning; production's unified-exec feature; no CLI/model upgrade |
| Agent authentication | Only `OPENAI_API_KEY`; request receipt records only a boolean sentinel-header match, never the header/value; future protected environment delivery through existing stdin transport as uid 1000 |
| Agent provider | Explicit OpenAI-compatible custom provider, Responses wire format; `https://api.openai.com/v1` for a future approved run; loopback-only non-forwarding responder in preparation |
| Agent retries/settings | Request retries 0, stream retries 0, idle timeout 60000 ms; web search disabled; no multi-agent work; no real key, ambient login or auth.json is supplied to preparation |
| Verifier | Native verifier after the agent phase, original gh deterministic contract and root-protected broker receipts; same restricted container, no judge credential; two verifier runs for the proposed pair |
| Model judge | **Disabled by `custom_only`**, no selected judge model/provider/endpoint, no judge credential, **zero model-judge requests**. The verifier does not silently become an LLM judge |
| Events/usage | Actual `codex exec --json` stdout/stderr; native command lifecycle → existing ATIF adapter → released collector → current public JSON/analysis/HTML. Missing usage stays unknown; observed stub usage is not billable provider usage |
| Termination | Native runtime errors, timed-out/interrupted work, unavailable grading and legitimate measured task failures remain separate; first failure and partial evidence are retained |

The released standard-judge route is separate from the agent CLI. In the pinned
`src/skillevaluator/tier3/harbor/runner.py`, `_judge_model_config` returns only
`enabled: false` for `custom_only`; both judge environment builders return empty
mappings. In `harbor/templates/eval.py`, the enabled route selects explicit model,
`LLM_JUDGE_MODEL`, `SKILL_EVAL_JUDGE_MODEL`, `SKILL_EVAL_LLM_MODEL`, then provider
default, with medium judge reasoning. `_call_judge_model` dispatches by provider;
its OpenAI-compatible path selects `SKILL_EVAL_LLM_API_KEY` then `OPENAI_API_KEY`,
and `SKILL_EVAL_LLM_BASE_URL` then `OPENAI_BASE_URL`, otherwise the official chat
endpoint. It sends chat-completions requests, independently of the CLI's Responses
route. Native strict/legacy retry, schema fallback and per-judge deadline policies
remain upstream-owned; their model-call/attempt evidence is collected by the
released collector. None is invoked by this selected grading mode.

PR #142 qualifies offline judge interpretation with simulated replies. This
custom-only pilot cannot qualify the live standard-judge route, its request
accounting or judge accuracy, and does not present simulated values as real
judgments. Future standard/default-plus-custom execution needs separate
credential-free request controls and an explicitly costed authorization.

The `gh` executable here is the fixture-backed **GitHub task CLI**, not GitHub
Copilot CLI. It uses public fixture transport and sealed broker observations; no
GitHub account credential or actual repository mutation is needed by the task.

## Isolation and preparation

Reuse the qualified external Docker policy: uid 1000, all agent capabilities
dropped, no-new-privileges, stock seccomp, bounded CPU/memory/PIDs, no host mounts,
no Docker socket or protected verifier/solution access. The stock egress controller
has its separate network capabilities and never receives the model key. The CLI's
inner sandbox setting remains the existing externally isolated launch policy.
Harbor 0.25 separates automatic output paths from explicit mounts. The adapter
handles both fields, keeps agent outputs container-local and refuses automatic
host mounting. No mount, seccomp, namespace or approval protection is relaxed to
launch this CLI.

In probes the actual provider is denied: the controller allows only
`localhost.invalid`. The responder binds loopback and has no forwarding code.
Both provider hostname and representative prohibited hostname/IP operations are
observed. Preparation descriptors retain this exact policy; the closed comparison
allows only this explicit provider-host substitution against the frozen future
execution descriptors. Fresh-runner live preparation consumption remains an exact
full descriptor comparison. Task members and both deployment manifests are bound
independently of TOML formatting.

Exposure remains: agent children can read their inherited credential and the
container's writable Codex configuration. External egress confines destinations,
not every request to the permitted provider. Therefore a future real key is exposed
to the agent and its subprocesses until container disposal, including any surviving child after the CLI exits. The
existing gh task uses a trusted root verifier in that container after the agent
phase; it does not provide a separate verifier container. Protected broker state
and tests stay unreadable to uid 1000. The existing lifecycle
scrubs the runtime home, observes post-command/post-phase policy (the permitted provider remains reachable
for surviving children in a future live run), retains permitted
files before disposal and removes the container and children. Stopped-container
retention handles native interruption without restarting the workload. This is not
protection against a compromised host or container runtime. Events and usage remain
producer-reported: agent code can alter its writable logs or issue permitted
provider calls outside CLI accounting. Stock DNS, ICMP and local namespace channels
remain; hostname/SNI rules do not constrain provider paths, methods or payloads.
Retention/redaction is bounded. Any eventual live approval must explicitly accept
these exposures; the reported-usage threshold does not enforce a provider spend cap.

The selected preparation runs current/absent controls, a complete pair, CLI
interruption and the existing 45-second native cancellation fixture (with stopped-
container retention and a 90-second outer guard), existing explicit missing/unsupported observation and usage controls,
and actual responder refusal/malformed-response/timeout controls. Injection
controls remain declared injections; they do not establish arbitrary event support.
Native oracle controls cover known-good, deliberately failing and unavailable
grading. For gh, privilege/network and delayed-child controls originate from
the operator under the same uid/container boundary, keeping broker traces separate
from task actions. Interruption and native cancellation separately exercise actual
CLI tool children. These controls do not establish arbitrary post-exit behavior.
PR #142 continues to qualify offline default judgment/recovery semantics.

Image contexts and dependency identities remain shared and content addressed;
normal Docker reuse is retained. New CLI acquisition is bounded and hash checked;
it does not repeatedly refresh qualified dependencies. Fresh consumption stages
clean inputs, compares source/runtime/task/deployment/descriptor identities and
reproduces the retained report using trusted checkout code. Artifacts are data and
are never executed.

## Proposed pair: UNRUN / UNAPPROVED

One existing read-only `gh-014` case; one current-skill attempt and one absent-skill
attempt; original prompt/grader/fixture and identical held runtime/model settings;
clean environments; concurrency 1; no retries, replacements, continuation or skill
changes. The frozen protocol is `gh-runtime-090-v1-protocol.json`. The original custom gate
includes skill activation, so an absent-skill gate failure is expected; independent
`gh_task` and `gh_authorization` observations remain separate from that gate. Outcomes are
diagnostic and excluded from production benchmark history. A measured task failure
is a valid compatibility observation. Neither preparation nor a future pair
establishes skill improvement.

There are **two agent attempts, two deterministic verifier runs and zero model
judge calls**. Agent attempts may each issue multiple Responses requests. The
operator proposal must not describe that as two provider requests.

Official [model pricing](https://developers.openai.com/api/docs/models/gpt-5.6-sol)
and [pricing](https://developers.openai.com/api/docs/pricing) were checked November
15, 2026: standard input/cached input/output are $4/$0.40/$20 per million tokens.
An assumption of 100K uncached input plus 20K output per arm yields $1.60 for the
pair; the planning estimate is $2. Scheduling stops before another attempt when
observed estimated cumulative use reaches $3. The overshoot reserve is $3 and the
proposed planning allocation $6. Those figures buy no extra slots and are **not a
provider billing cap**. Long-context premiums and unknown usage prevent exact
invoice reconstruction; the existing conservative premium remains in accounting.
CI hosting/storage costs are separate. Recheck pricing before authorization.
This proposal expires **2026-11-18 00:00 UTC**, enforced before live credential
handoff to a child, or earlier if the preparation artifact expires or source drifts.

The native agent deadline is 600 seconds; each shared launch is bounded at 1200
seconds and existing cleanup grace remains bounded. The workflow limits the future
pair's execution step separately. Stop before the next slot on authentication or
identity failure, essential evidence loss, unsupported protocol/grading, unknown
usage, verifier infrastructure failure or failed cleanup. Never replace a failed
slot or resume a closed allocation.

The final PR must freeze **exact execution commit/ref, definition/protocol and
source identities, both deployment manifests, successful preparation artifact ID,
ZIP digest, producer run/attempt and expiration**, plus an exact operator command
and combined approval text. No allocation or reservation is created here. A later
merge revision is not covered by a PR-head receipt: rerun credential-free
preparation and fresh-runner consumption at the exact merge SHA and replace the
proposal before requesting authorization.

The future command and approval will be recorded only after successful hosted
preparation. They remain **UNRUN / UNAPPROVED**. No protected gate is approved by
this preparation task.

## Rollback and limits

Revert this focused change as a unit, retaining all captured evidence and historical
profiles. No production benchmark runtime rollback is needed because its selector
never changes. Replay old evidence with its original source/runtime; appended
source-only identities do not requalify old allocations or grades. Pester
clarification, skill adoption, default live judging and recurring paid work remain
deferred.

Workflow security review: critical 0, high 0, medium 0, low 0. The changed manual
selection retains read-only preparation, pinned Actions, nonpersistent checkout
credentials, literal registered selectors and the same protected live gate. No
secrets are inherited by preparation or consumption. Final native CI remains
required; local staging and mocked contracts alone are insufficient.
