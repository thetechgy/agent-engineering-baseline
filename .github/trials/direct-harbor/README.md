# Direct Harbor trial

This opt-in trial preserves production SkillEvaluator 0.3.0 / Harbor 0.13.2,
static checks, historical results and Pages. Source baseline:
`cc0819f5dafc05610dd8c3293ce2f52744c66f1a`. No PR or merge is required: the
workflow listens for a push of `launch.json` on `trial/direct-harbor` only.
No schedule or provider secret is attached to the calibration workflow.

## Frozen candidate

- Harbor 0.25.0, source `fdba28fc411e47e8765420a1a063b4918fce3def`, with its
  unchanged owning `uv.lock`; Python 3.13.15 and uv 0.13.7.
- Docker Compose 5.7.0 through the existing verified installer.
- Existing Pester image recipe: digest-pinned Python/Debian base, snapshot and
  exact package versions, PowerShell 7.6.9 and Pester 6.2.0 with archive hashes.
- Intended live agent: actual Codex CLI 0.155.1, gpt-5.6-sol, explicit medium
  reasoning. The production model is retained; explicit effort removes a default.
- Unchanged public tasks, reference implementations, mutants, grader, AST profile
  and qualification submissions. The machine-readable manifest records bytes.

Harbor's [separate verifier](https://docs.harborframework.com/tasks/separate-verifier)
fits the existing root-owned Pester verifier. `run.py` reuses that packaging and
executes Harbor directly. There is no SkillEvaluator execution or collection
wrapper and no provider judge. The native oracle supplies credential-free
calibration submissions; it is not live-agent evidence.

The runner stages all 48 tracked APM-deployed skill/support files, generated
AGENTS.md and Codex MCP configuration. The absent variant removes only the three
target-skill files. Source skills, evaluation overlays, repository metadata and
ambient home/plugin caches are not agent inputs. Solutions and checks belong to
separate contexts. Agent images use an unprivileged user, dropped capabilities,
no-new-privileges and bounded resources; verifier workers use the existing
UID 53001 privilege drop. No host Docker socket or write credential is mounted.
Manifest files record both source and task hashes. Runtime duplicate-copy auditing
and actual Codex discovery remain unqualified until a live/preflight phase runs.

## Experiment and spending gate

Planned allocation: up to three current-skill discovery attempts on pester-002,
then 27 interleaved comparisons across pester-002, pester-004 and pester-005,
three variants and three repetitions. Six remaining attempts are contingency,
not permission for silent retries. Maximum 36 attempts, $20 incremental API
spending, 600 seconds per attempt and at most two concurrent agents. The proposed
paid schedule is serial to simplify campaign accounting. Every smoke, failure and
retry would count. There is no response reuse or automatic retry.

At 60,000 input and 4,000 output tokens each, 30 attempts would be about $9.60
before caching (about $11.40 including a 25% input cache-write premium), using [published model rates](https://developers.openai.com/api/docs/models/gpt-5.6-sol).
This is a planning estimate, not a hard limit or an observation. Larger contexts,
cache-write charges, retries and output overshoot can increase spending.
No provider-side dollar cap has been configured or verified. The existing
credential reference is `OPENAI_API_KEY` in the protected `skill-benchmark`
environment; its value was not retrieved.

Two boundaries need qualification before paid execution:

1. [Harbor's pinned Codex launcher](https://github.com/harbor-framework/harbor/blob/fdba28fc411e47e8765420a1a063b4918fce3def/src/harbor/agents/installed/codex.py#L2072)
   unconditionally passes `--dangerously-bypass-approvals-and-sandbox`.
   `CodexOptions` has no sandbox/approval override. A native configuration file
   cannot remove a command-line bypass. A narrow subclass or patch may be
   feasible, but has not been implemented or qualified; no protection is disabled.
2. [Codex 0.155.1 rollout accounting](https://github.com/openai/codex/blob/rust-v0.155.1/codex-rs/core/src/rollout_budget.rs)
   uses noncached input plus weighted output (or provider rollout units), and
   [raises exhaustion after usage is recorded](https://github.com/openai/codex/blob/rust-v0.155.1/codex-rs/core/src/session/rollout_budget.rs).
   That is not a complete billable-token cap and does not bound the in-flight
   response. Harbor's adapter exposes no dollar cap. An estimate and a ten-minute
   timeout alone do not establish the campaign's $20 ceiling. A trusted request
   meter or separately verified spending control would need qualification.

Stop before paid work if these boundaries cannot be addressed narrowly. Do not
build another platform or quietly relax the spending ceiling. The credential-free
phase remains useful evidence even if the live comparison cannot proceed.

## Interpretation

Only a complete terminal grader classification may be measured. Numeric reward
files alone do not establish correctness. Passed/failed outcomes are distinct
from invalid, unsupported, timeout, infrastructure and missing-verifier evidence.
Token and cost observations remain null when absent. Zero campaign API spend in
calibration follows from executing no inference with no credentials, not from
missing telemetry. The single HTML report links its JSON, manifest and diagnostics.

The public repository exposes the tasks and answers. The trial author has read
case descriptions and qualification mappings, including reserved-case grading
details. Confirmation would therefore be reserved from revision tuning, not
blinded. No discovery outcome currently justifies a skill revision. Do not create
one merely to fill the third variant.

To add another skill, an engineer would still need a representative task contract,
independent good/weak submissions, a protected deterministic verifier, deployment
staging and diagnostic interpretation. Direct Harbor does not remove that work.
Potential future removals are the behavioral wrapper/staging/collection portions
of SkillEvaluator, only after their contracts are replaced and qualified. Static
checks, APM deployment, graders and historical evidence remain necessary.

## Stopped outcome

[Run 41952213509](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/41952213509)
failed at `a644d44` after 17m49s with exit 143. Upload steps were skipped and the
artifacts API returned zero artifacts. No per-fixture grading result survived;
all 16 planned controls are unavailable. The cause of termination is unknown.
The initial wrapper buffered native output on the runner, which made recovery
inadequate. The retained runner streams credential-free output and retains
partial result carriers; those changes were checked locally, not rerun natively.

The campaign is stopped: zero Codex/provider attempts and zero API spending.
No revision was created and no skill-effectiveness claim is supported. Retain the
existing approach. [The consolidated report](results/report.html) contains the
machine-readable results, source manifests and workflow evidence. The final
workflow phase only validates and packages this report; its success must not be
represented as successful native qualification.
