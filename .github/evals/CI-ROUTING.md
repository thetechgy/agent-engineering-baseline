# GitHub Actions routing

Security review of the routing change:

| Critical | High | Medium | Low |
| --- | --- | --- | --- |
| 0 | 0 | 0 | 0 |

The changed paths retain read-only PR execution, SHA-pinned actions,
`persist-credentials: false` and credential-free preparation. Reusable calls
receive no inherited secrets. No privileged PR trigger or new token scope is added.
This is a review of execution boundaries, not a new vulnerability scan.

## Execution graph and disposition

Audited from main `e40cc0c995025d448fd7b163df3b6f32b7ea569e` after merges
[#125](https://github.com/thetechgy/agent-engineering-baseline/pull/125) and
[#133](https://github.com/thetechgy/agent-engineering-baseline/pull/133).
All 13 workflows, their job conditions, matrices, dependencies, artifacts,
permissions, secrets, environments and concurrency were inspected.

| Workflow | Purpose and unique coverage | Before triggers | After / disposition |
| --- | --- | --- | --- |
| Validate | Required Linux/Bash and Windows PowerShell; CI contracts; retained Pester isolation/grading; scanner/public quality | Every PR; push main | Same triggers, no path filter. Two required jobs unchanged. One Git comparison selects contracts, scanners and retained Pester; always-running result gate checks every selection. Quality runs alongside contracts. Main retains all five original producers. |
| Current evaluator report qualification | Opt-in 0.8.0; 100 native oracle observations, six gh lifecycle shards (two at once), same-attempt artifact/report join; historical admission | Broad CI/eval PR paths; manual | Called once from Validate for affected PR inputs; manual retained. All eight job definitions unchanged. |
| Native deadline evidence | Actual CLI deadlines, retained timeout diagnostics/disposal; explicit matched CLI-observation diagnosis and missing-child control | Runtime PR paths; manual | Selected call from Validate; manual diagnostic inputs retained. Neither diagnostic mode is automatically enabled. |
| Pester admission qualification | Original unsupported outcome, supported/prohibited AST controls, exact retained-submission replay and verifier handoffs | Admission/replay PR paths; manual | Selected call from Validate; manual retained. All native commands and evidence unchanged. |
| Codex compatibility pilot | CLI isolation, grading, exact replay and consumption; older twelve-slot scheduler control and its known failure | Pilot/reporting/Pester PR paths; manual | Selected call from Validate; manual/live input guards retained. The failing scheduler remains selected for shared/runtime/Pester changes and contributes failure to the result gate. |
| Reusable evaluation qualification | Both task families, six-slot experiment preparation/consumption, authenticated historical replay; selected-artifact inspection | Campaign/shared-runtime PR paths; manual | Full preparation and historical replay explicit via existing manual dispatch. Maintained routine native/grading/isolation coverage remains above; experiment-specific slot/population qualification is required before any future proposal. No claim of scheduler equivalence. |
| Pester return-contract qualification | Both frozen skill sources and two cases, full paired preparation/consumption, report reproduction | Shared-runtime/experiment PR paths; manual | Explicit manual preparation for the paused experiment. Same four matrix job definitions. Routing-only freeze v8 retains v7 unchanged in history. |
| Candidate Pester packaging | Historical 0.7.2 migration/scoring refusal; two native packaging paths and six gh shards | Manual | Unchanged, explicit. It does not qualify adoption. |
| Benchmark skills | Protected production evaluator 0.3.0, standard/confirmation, authenticated orchestration, history append | Manual, including authenticated planner dispatch | Unchanged. Context/guard before credential delivery; `skill-benchmark` environment. Standard main history append only after eligible successful execution. |
| Plan skill evaluations | Trusted-main health/dispatch planning; disabled stream policy; authenticated request/nonce linkage | Validate completed on main; Tuesday 10:37 UTC; manual main | Unchanged. `plan` verifies producer repository/event; `dispatch` needs requests. Both streams remain disabled. No paid dispatch was requested in this work. |
| Publish skill report | Authenticate producers/data, prepare sealed candidate, isolated commit, exact-commit Pages deployment | Validate/Benchmark completed on main; recovery repository_dispatch | Unchanged. Successful trusted main push/dispatch producers only, or existing recovery path. No PR artifact execution; `github-pages` environment retained. Not dispatched here. |
| Update APM baseline | Hash-reviewed acquisition, reviewed regeneration, allowlisted patch, isolated PR publisher | Monday 09:17 UTC; manual | Unchanged. Read-only generator; separate contents/PR writer only after validated change. No dependency update dispatched here. |
| Dependency freshness | Public dependency/advisory discovery; bounded complete/partial data; single issue publisher | Daily 13:43 UTC; manual | Unchanged. Separate issue writer cannot erase discovery failure. Used on merged main to regenerate #95 from the maintained source. |

No `pull_request_target` or merge-queue trigger exists. Accessible active rulesets
have no merge-queue rule. They require the Actions checks
`Full validation (PowerShell 7 and Bash)` and
`Pester and analyzer (latest stable PowerShell)`, with strict current-revision
checking. Both names and complete job definitions remain unchanged. The new
`Selected validation results` check is visible but is not added to protection rules.

The downstream graph remains Validate(main push) -> planner and publisher;
planner -> Benchmark(manual request, protected environment) -> publisher/history.
The planner's `actions: write`, publisher's separate `contents: write` and
`pages: write`/`id-token: write`, updater's PR writer and freshness issue writer
remain confined to their existing trusted jobs. Benchmark and publication share
`skill-report-publication` with `queue: max`, without cancellation. The planner
and benchmark also retain their existing queues. No new automatic evaluation
stream, publication or approval layer is introduced.

PR and manual qualifications retain their existing exact source/configuration,
archive/digest, missing-evidence, public allowlist and checkout-integrity checks.
The report join still needs both native producers; partial evidence is diagnostic.
Main still produces its quality and Pester artifacts for trusted publication.

## Selection and failure behavior

Every PR runs the planner's credential-free routing controls and both required
platform jobs. Selection uses the full fetched Git graph and a NUL-separated
three-dot diff with rename detection disabled: a rename exposes both old and new
paths, including deletions. There is no PR-files API page or workflow path-filter
limit. Unavailable/invalid comparison, empty or oversized evidence and unknown
paths select all maintained checks. A failed planner fails the final gate.

The policy deliberately starts broad. Shared scheduling, evidence, reporting,
deployment, locks, images, policy and unknown code select all maintained checks.
A known task-owned gh change selects its native/scanner consumers; Pester inputs
select the retained/current Pester, CLI, deadline and admission consumers. Every
skill file, including Markdown references and supporting scripts, selects scanner
and contract validation; gh/Pester skills additionally select their native users.
Known individual workflow edits select their owner, while shared Validate/selection
edits select all. Full experiment preparation stays explicit under either policy.

Representative PR selections (both platform jobs, planner and gate always run):

| Change | Additional selected validation |
| --- | --- |
| README, ordinary docs, authoritative checkpoint | None |
| `.apm/skills/podman/references/quadlet.md` | Contracts, scanner/public quality |
| gh skill supporting file | Contracts, quality, current evaluator including six gh lifecycle shards |
| Pester skill supporting file | Contracts, quality, retained Pester, current evaluator, deadline, admission, legacy pilot |
| APM manifest/lock, deployment source/generated inputs | All maintained checks |
| gh task grader/setup fixture | Contracts, quality, current evaluator |
| Pester task grader/runner/fixture | Contracts, retained Pester, current evaluator, deadline, admission, legacy pilot |
| Runtime adapter; shared scheduling/evidence/reporting | All maintained checks |
| Dependency locks/images | All maintained checks |
| Validate or selection code | All maintained checks |
| Individual native workflow | Contracts and that native workflow |
| Rename/deletion | Union of both paths / removed path; unknown path selects all |
| Missing/incomplete diff | All maintained checks, with visible fallback reason |

The final gate accepts only `success` for selected jobs and `skipped` for
unselected jobs. Selected failure, cancellation, missing result or skipped work
fails. Missing/malformed planner outputs fail. Unit controls invoke the real gate
process with a failed selected pilot and require a nonzero exit. Workflow wiring
contracts require every job to feed `always()` admission. Hosted PR execution
qualifies the new call/selection/result path separately from native receipts.

Ordinary initial PR runs cancel superseded runs of that same PR. Each called
workflow has a distinct prefix; unrelated PRs and diagnostic reruns use separate
groups. Credential-free manual preparation and diagnostics use their run identity,
separate from protected live serialization. Main producers are never superseded by
PR work. Existing live first-attempt/allocation/environment restrictions remain.

These choices follow GitHub's documentation for
[required checks and skipped dependencies](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks),
[three-dot comparisons, filter limits and workflow calls](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax),
[concurrency](https://docs.github.com/en/actions/concepts/workflows-and-actions/concurrency)
and [trusted workflow_run events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows).

## Runtime evidence and limits

A bounded sample used the seven terminal PR runs at dependency head `926d26b`:
[Validate 43346486484](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43346486484),
[current evaluator 43346486586](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43346486586),
[campaign 43346486514](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43346486514),
[return contract 43346486513](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43346486513),
[pilot 43346486510](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43346486510),
[admission 43346486465](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43346486465)
and [deadline 43346486676](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43346486676).
No baseline was launched to count jobs. Cancelled preceding revisions were not
counted as passing receipts.

Measured job elapsed time totals about 529 runner minutes, excluding skipped jobs;
it is not billed cost or workflow wall time. The slowest workflow took about 68
minutes. Full campaign preparation/replay used 51 runner minutes; full return
preparation used 133. Validate used 58, including retained Pester 21.5, contracts
18.3, quality 9.4 and the required platforms 3.8/4.8. Quality previously waited
for contracts, making that workflow take about 28 minutes.

Projected from this sample: the same broad change avoids about 184 runner minutes
(35%) by making experiment preparation explicit, before new planner/gate overhead;
25 executed jobs become 20 under the same legacy failure. Documentation-only PRs
move from five jobs / 58 runner minutes to four jobs / approximately nine platform
runner minutes plus planning/gating. An unrelated skill still gets scanner quality
and contracts, but avoids the 21.5-minute retained Pester job. Quality no longer
adds its duration after contracts. These are selection projections, not measured
post-change runtime savings. Main retains all five producer jobs plus the two
small routing jobs; no main/publishing savings are claimed.

The legacy scheduler remains **failed and unqualified**. The intentional failing
CLI command raises before `boundary_after` is recorded. Its identity guard then
reports `security_or_identity_drift`, while the control expects
`execution_infrastructure_failure`. The assertion and guard are unchanged.
[The original documented failure](cli-observation-v1/EVIDENCE.md) and
[#95's authenticated disposition](https://github.com/thetechgy/agent-engineering-baseline/issues/95#issuecomment-6839991608)
remain visible. The new gate must fail when this selected control fails. Passing
required platform checks do not establish scheduler readiness. Repairing its
failure-path audit collection requires separate versioned work.

Native job definitions in all six rerouted/manual workflows compare exactly with
main. Existing authenticated receipts support unchanged execution behavior;
source-v7 campaign profiles and `pester-effectiveness-v16` append only producer
identities for the routing envelope. All 274 earlier profiles, active production
selectors, metrics, grader/fixture hashes, runtime/model settings and skill
snapshots remain intact. The previous return freeze is retained byte-for-byte.
Old preparation cannot be admitted as a new source's preparation. New exact-source
experiment qualification remains necessary before any later live proposal.

Local routing, gate, workflow, profile, frozen-input and affected report/campaign
contracts pass under the retained runtime. Optional semantic/native-runtime checks
remain explicitly skipped locally. Hosted final-revision status and any failures
are recorded on the draft PR; this document does not turn skipped or historical
checks into new execution evidence.

## Operator commands

Use the existing manual preparation paths when their coverage is needed:

```sh
gh workflow run evaluation-campaign.yml --ref <reviewed-ref> -f campaign=boolean-effectiveness-v1
gh workflow run pester-return-qualification.yml --ref <reviewed-ref>
gh workflow run codex-pilot.yml --ref <reviewed-ref>
gh workflow run native-deadline.yml --ref <reviewed-ref> -f cli_observation=true -f observation_final=true
gh workflow run pester-candidate.yml --ref <reviewed-ref>
```

These commands are credential-free preparation/diagnosis, not authorization for
inference. Allocation inputs remain empty; no closed experiment is reopened.
The selected-artifact inspection and future protected live commands remain in the
existing [campaign operator guide](campaigns/README.md). Paid work, judges, adoption
and the Pester clarification remain paused. PRs #130/#132 are unchanged.
