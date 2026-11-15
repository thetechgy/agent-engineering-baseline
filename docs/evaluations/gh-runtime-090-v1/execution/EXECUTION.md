# gh-runtime-090-v1 stopped execution receipt

**Stopped; allocation closed.** The single authorized dispatch,
[run 43762601398, attempt 1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43762601398),
completed with an infrastructure failure on November 15, 2026. The current-skill
slot reached Harbor agent construction and failed before Codex launched. The
absent-skill slot remained unlaunched. No replacement, retry or continuation ran.
[PR #143](https://github.com/thetechgy/agent-engineering-baseline/pull/143) remains
unmerged. This report-only record does not change the executed source.

## Execution identity and authorization

- Execution commit: `b3e190d143e2cbc7b44938d4d01b690dc9f67c10`, branch
  `feat/evaluator-090-execution`; workflow `evaluation-campaign.yml`.
- Campaign `gh-runtime-090-v1`, read-only `gh-014`, current then absent, serial,
  one slot each, no retries/replacements; `custom_only` grading permitted two
  deterministic verifier runs and **zero model-judge requests**.
- SkillEvaluator 0.9.0 / Harbor 0.25.0; held Codex 0.155.1 / `gpt-5.6-sol`, high
  reasoning, unified-exec settings and existing isolation policy. Configured
  provider: OpenAI, `https://api.openai.com/v1`. These are frozen selections,
  not effective live-routing observations: the CLI never launched.
- Explicit user authorization covered this dispatch and only its matching
  `skill-benchmark` gate. Exactly one matching dispatch and one matching gate
  approval were verified; run head and attempt matched. No pending gate remains.
- The frozen authorization expiry was November 18, 2026 at 00:00 UTC, or earlier
  on preparation expiry/source drift. Allocation closure ended execution authority
  before that date.

The full allocation identifier and immutable source, definition, protocol,
selection, deployment and descriptor digests are in [receipts.json](receipts.json).
[allocation-closure.json](allocation-closure.json) permanently closes unused
position 2 as well as position 1; it was written at **2026-11-15T21:22:28.064144Z**,
before this report-only source update. It grants no future execution.

## Preflight and fresh consumption

Source/ref/PR head matched the authorized execution commit before dispatch.
[Selected CI run 43743658476](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43743658476),
at that source, had successful required platform checks and selected-results gate;
its retained receipt records attempt 2 after the scoped PowerShell fixture retry.
This is source-validation evidence, not successful paid execution.

[Preparation 43743655750, attempt 1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43743655750)
produced artifact **14174835478**. The producer repository, workflow, head,
attempt, ZIP SHA-256, bounded extraction and internal manifests were authenticated.
The archive digest is
`sha256:9c0e5fbcb307176b8d48e473e931a68412c9aac4701e1bb9b172915de9e65ade`;
artifact expiry is **2027-02-13T17:53:43Z**. The API-authenticated fresh inspection
[43746221979, attempt 1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43746221979)
was successful. Local credential-free consumption and the protected run's fresh
preflight independently reproduced the preparation report and checked both arms.

Both deployment manifests and all task members except raw `task.toml` matched.
The retained full typed-TOML comparison verified **all parsed configurations equal**
for both descriptors. Raw descriptor/task hashes differed only because the
empty environment keys were serialized in a different order. No values were
normalized away. Source, runtime, fixture, grader and skill content identities
remained frozen. The preparation report SHA-256 is
`adb9ef05eb48eb000ef7d45be8ca1ad996af61ddd323556d1daedbb5683b2f81`.

Official [model pricing](https://developers.openai.com/api/docs/models/gpt-5.6-sol)
and [pricing details](https://developers.openai.com/api/docs/pricing) were rechecked
on November 15 before dispatch. The frozen $4/$0.40/$20 per million standard
input/cached-input/output prices and conservative long-context accounting remained
applicable. No protocol or price assumptions were changed.

## Preserved outcome

| Arm | Execution | Independent correctness | Task read authorization | Essential evidence |
| --- | --- | --- | --- | --- |
| Current skill | Infrastructure failure before CLI launch | Unavailable; no verifier ran | Unavailable; no task actions observed | Primary failure and schedule retained; no submission, grade, events or usage |
| Absent skill | Unlaunched; slot closed | Unmeasured | Unmeasured | Explicit unlaunched ledger entry; no submission, grade, events or usage |

The exact retained failure is:

```text
ValueError: Live runtime requires protected workflow; overrides refused
```

The causal path is specific: `GhFixture.operator_environment` supplies the trusted
`AEB_GH_MANIFEST` path (`evaluation_tasks.py:272`). The shared launcher adds that
task-owned environment after filtering ambient overrides (`evaluation_campaign.py:211`).
Harbor constructs `CampaignCodex`, whose live constructor rechecks `runtime_gate`
(`evaluation_codex.py:224`). That guard rejects every `AEB_*` name except the two
campaign authorization variables (`evaluation_campaign_protocol.py:148`). Thus the
parent check passed, but the child rejected the trusted gh task manifest.

The failure occurred in Harbor's `_init_agent`, before its `_init_agent_environment`
and before the Codex superclass constructor. No agent container was initialized,
no Codex process launched, no deterministic verifier ran and no model judge was
requested. This is a live guard/task-environment composition defect; it does not
demonstrate a provider authentication error or a Codex CLI incompatibility.

A credential-free reproduction called the **existing** `runtime_gate` with
`selected_task('gh-runtime-090-v1')`, the retained authenticated receipt, its
matching allocation and fixture `GITHUB_ACTIONS=true`, repository and `GITHUB_JOB=live`.
Adding only a dummy `AEB_GH_MANIFEST` reproduced the exact refusal. Removing only
that variable allowed receipt validation. No agent was instantiated, no model key
was supplied and no allocation was claimed by this reproduction. The paired
results are retained in `receipts.json`. No runtime fix was implemented.

The ledger retains `execution_infrastructure_failure`, current return code 1,
missing native usage and absent `unlaunched`. This is not a measured task failure,
an activation failure, a grade of zero or a skill comparison. The original gh gate
includes activation, but that gate never ran here.

## Evidence, cleanup, report and accounting

The terminal live artifact is
[campaign-live-1, 14181315252](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43762601398/artifacts/14181315252),
265357 bytes, SHA-256
`77a6f1e36b9ccf2b6d99f0c620a4624db48b64b8347c483c962dad30a854bd74`.
The authenticated input artifact is
[campaign-authenticated-1, 14180168774](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43762601398/artifacts/14180168774),
SHA-256 `8be611538aa72c5d94f3d005ff26d044639bdf583337df60e6139ae3cf52a047`.
Both expire **2027-02-13T21:14:48Z**. Producer run/source/attempt, archive size and
digests were independently checked before bounded extraction. Archives were
consumed as data using trusted execution-source code.

Retained `campaign-live/evidence` includes the attempt ledger, sanitized
`launch-1.log`, cleanup receipt, native failure record, task/deployment descriptors,
public JSON and consolidated HTML. No native result, Codex events, submission or
grade exists. Collection and resource cleanup completed; no agent container
required disposal. Cleanup returned to the recorded resource baseline and
`cleanup.json` is complete, with position 2 unlaunched.
Because agent initialization never occurred, this does **not** add qualification
of live credential exposure, agent-child termination or container disposal under
live workload. Their prior credential-free receipts retain their original scope.

Public admission passed. Regenerating the stopped report from retained public JSON
and analysis with trusted execution-source 0.9.0 reporting produced identical bytes
to both uploaded stopped HTML copies:

```text
sha256:5acc463c73bf87fc50b741c6d7a94528b4d63bbc19f1caddf6feba8cceebc04f
```

The report has **zero native observations**. Its existing empty-arm collection
marks both arm aggregates `failed`, including the unlaunched absent arm; each
aggregate's three collection errors are not three attempts. The authoritative
ledger distinguishes the current infrastructure failure from absent nonexecution.
The original report was preserved, not repaired or regraded. Public record/report
identities and the separate preparation-report digest are in `receipts.json`.

The planning estimate was **$2**, scheduling threshold **$3**, overshoot reserve
**$3**, within a **$6** planning envelope. Native estimated usage is **unknown**,
not zero; actual provider billing was not reconciled and remains unknown. The
pre-CLI failure supplies no evidence of agent/provider requests, but is not an
invoice. These limits were not a provider billing cap; CI/storage costs are separate.
No later slot was scheduled after the failure/unknown usage, and unused capacity
was closed without reopening the allocation.

## Limits and next decision

This run establishes the authenticated dispatch, matching protected approval,
fresh preparation consumption, failure retention, stop and report reproduction
paths. It surfaces a missing live environment-composition check. It does not
establish live CLI/provider compatibility, useful submissions, deterministic
verifier operation under this runtime, standard model-judge compatibility or
accuracy, or skill improvement. Production Benchmark remains 0.3.0 / Harbor 0.13.2;
no production history, Pages publication, recurring work or merge occurred.

**One next action:** authorize a separate credential-free fix and requalification
of trusted task-manifest handling in the live guard. This closed allocation cannot
fund a replacement. Any future live pilot needs a newly prepared exact execution
revision and separate authorization.
