# PR #134 inventory and scheduler follow-up

Recommendation: proceed with routing review after final-head validation confirms
the inventory correction, retaining the failed/unqualified legacy pilot. The
[PR disposition and terminal CI receipts](https://github.com/thetechgy/agent-engineering-baseline/pull/134)
record the final commit without documentation-only CI restarts. No additional
comparison or experiment is needed by the evidence below.

## Completed reusable-route evidence

[Validate 43446918858](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43446918858)
completed at `f90196b05139146cb85d2522d4bda188c2f1fa12`, attempt 1: 17 jobs
succeeded, three failed and six skipped. Both required platforms passed.
[Contracts 131958771080](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43446918858/job/131958771080)
failed only the uv inventory reconciliation assertion. The other failures were
[prospective pilot 131958771736](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43446918858/job/131958771736)
and its correctly rejecting aggregate gate.

Artifact `14054421752` belongs to that run, attempt, source and repository. Its
original ZIP matches GitHub SHA-256
`b4a900de5d983f16d13b967fd97b2178974e23111b02ade616ad481e8c608924`.
Bounded data-only extraction checked 3,031 members and 18,027,440 expanded bytes.
The [sanitized audit](routing-134-followup.json) records the new receipt alongside
historical artifact `13822715004`, reauthenticated to run `42937277898`, attempt 1,
source `33d953536e95bc81178e726fb3fed95a80566c7d`; its archive digest remains
`f1d2ae882ec231bc423f74cd38a4b7baa8851942aabfb20c8f99bb12f22eced9`.
Both originals remain unchanged; no artifact code was executed.

The new complete fixture passed all twelve slots in the exact expected order.
All twelve retained valid actual CLI-child observations, matching before/after/
final agent and controller identities and policy hashes, and byte-identical
producer/retained-submission/verifier handoffs. Expected grading was eight passed
and four measured failed; all cleanup checks passed. Threshold, unknown-usage
and unsupported controls then stopped correctly with one launch each.

The infrastructure control issued `printf pilot-command-failure; exit 23` through
the actual CLI. The tool exited 23; the fixture's subsequent deliberate HTTP 400
made the CLI exit 1. `PilotCodex` raised `RuntimeError` before `boundary_after`.
A final operator policy observation exists and agrees with the initial policy.
No delayed-child observation exists: this command does not launch that child,
and the stop hook requires it only for the success scenario. This is distinct
from a missing required success-scenario observation.

Exactly one infrastructure slot launched, eleven remained unlaunched, and cleanup
completed. Native primary failure was `Pilot Codex CLI exited unsuccessfully;
original events retained`. There was no collection/retention failure. The initial
stop classifier chose `execution_infrastructure_failure`; the independent identity
guard then rejected the absent before/after policy evidence and replaced it with
`security_or_identity_drift`. The assertion expected the former label. Its launch
count condition passed. The later cleanup/interruption scenarios did not run.

The historical native artifact has this same complete-cohort evidence and same
infrastructure causal sequence, including tool/CLI exits, missing `boundary_after`,
final operator policy, one launch, eleven unlaunched slots and completed cleanup.
Adapter, environment, fixture-server and scheduler bytes are identical at that
historical revision, PR base `e40cc0c995025d448fd7b163df3b6f32b7ea569e` and
reviewed head `f90196b05139146cb85d2522d4bda188c2f1fa12`. Replaying the production
classifier and identity predicate against both authenticated receipts at all three
sources reproduces the same classification replacement; only the missing
`boundary_after` comparison fails. This is source replay plus historical/current
native evidence, **not a new native baseline run**.

The remaining failure is therefore the documented existing scheduler defect.
The actual reusable pilot route progressed beyond the earlier DNS failure and
passed its complete fixture, so that earlier incomplete comparison is no longer
the only route evidence. This does not explain the old DNS event, establish DNS
reliability or rule out every environmental routing effect. The original failure
and comparison limitations below remain historical evidence. No blanket rerun,
DNS correction, scheduler repair, guard change or expectation relaxation follows.

## Inventory correction and review boundary

The new diagnostic workflow installs uv `0.13.8` through its pinned setup action.
Its one version selector is now registered under the maintained current-CI uv
entry in `.github/dependency-freshness.json`, owned by maintainer review. The
separate intentionally frozen return-contract uv `0.13.7` consumer is unchanged.
No dependency version or generated issue text changed.

The existing 49-test freshness suite reproduced the omission before correction.
Afterward, all 82 freshness/routing/workflow/profile controls passed. Re-omitting
the new entry still fails completeness; the existing test mutates each registered
consumer, including this one, and rejects contradictory versions. No test or
inventory assertion was weakened. Markdown lint and whitespace checks pass.

Only inventory metadata and investigation documentation change in this follow-up;
all pilot executable inputs remain those of the authenticated `f90196b` run.
That evidence is reused under its original source, never relabeled as final-head
execution. Final normal CI is recorded on the PR. Selected failures, cancellations,
missing results and skipped selected jobs still fail the aggregate gate. It is
visible but non-required; both platform checks alone cannot establish all selected
validation passed. The known pilot remains failed/unqualified and selected for
relevant changes. Its failure-path audit/classification repair remains separate.

**One next action:** review PR #134's routing and inventory correction with the
known pilot qualification limit explicit, using the final receipts on the PR.

## Earlier child-network investigation, retained as history

The earlier hold and proposed comparison below are superseded by the completed
reusable-route evidence above. Original failures and limitations remain unchanged.

Disposition: **hold #134 as draft**. The immediate failure is established, but
its DNS cause and any contribution from the changed invocation context remain
unresolved. Neither this diagnosis nor passing required platform checks qualifies
the failed pilot.

## Authenticated retained evidence

The GitHub API still identifies reviewed head
`5e2955eb01d353f8f2834b8fcdd52244e9d08543` and base
`e40cc0c995025d448fd7b163df3b6f32b7ea569e` at investigation start.
[Validate 43367014799](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43367014799)
is attempt 1, a failed PR run produced by `validate.yml` for that head in this
repository. Its
[pilot job 131693882453](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43367014799/job/131693882453)
checked out that exact head; the reusable workflow definition came from PR merge
`ef25af3388988135eb936e63cb9b9a37d7c38145`. Artifact `14011909368` belongs to that
run/head/repository. Downloaded ZIP SHA-256 matches GitHub's digest and the starting
receipt: `5a944ef36de82b34e2dedd18d065e7bf8edea522b65545e4cde142c96e9ec667`.

The original ZIP and API/job receipts are retained separately without alteration.
Data-only inspection checked all paths, rejected links/traversal and bounded
member count, individual size and total expansion before extraction: 1,430 members,
10,877,084 expanded bytes. No artifact code was executed. The
[sanitized inspection receipt](routing-134.json) retains identities and fixed
observations, without raw logs or local paths.

## Causal sequence and contract

1. The actual pinned CLI invoked `codex_pilot_probe.py` through its tool command.
   The probe first verifies containment, immutable inputs and privilege denial,
   then requires an unauthenticated allowed-host HTTP response and explicit
   rejection of the prohibited hostname and literal IP. A host probe is separate.
2. The retained `codex.txt` command result is exit **1**. Its traceback is at
   `network_probe()`: `curl` exit **6**, HTTP `000`,
   `Could not resolve host: api.openai.com`. This is the earliest proven failure.
   The allowed-host requirement was unavailable; this is not an observed egress
   policy violation.
3. That assertion runs before `Popen(... --late-network)`. Consequently the
   delayed CLI descendant was never launched, and the `&&` submission handoff
   was never reached. The local non-forwarding server nevertheless returned a
   final response and the outer CLI exited **0**. The adapter therefore recorded
   `boundary_after` and scrubbed its runtime home.
4. `PilotEnvironment.stop` independently observes the same contained environment,
   releases the expected child using the container-local marker, and waits up to
   55 seconds for `late-policy.json` within its 60-second exec bound. No child
   existed to produce it. The stop hook raised
   `Post-agent CLI child network observation unavailable` and still disposed the
   environment. This is a production failure to produce required observation,
   not evidence that a valid observation was lost, misassociated or rejected.
5. The final policy receipt was absent. The cohort's independent frozen-source,
   task, configuration, prompt and policy checks therefore stopped admission with
   `security_or_identity_drift`. One slot launched and was unscored; eleven
   remained unlaunched. The later `Wrong cohort order or population` assertion is
   downstream. Cleanup completed. The retained public report validates as data
   and preserves one `unknown` outcome; it is not passing execution evidence.

The parent CLI's exit code and present `boundary_after` do not establish the
child observation. Before/after agent ID, controller ID, policy digest and image
IDs agree. The limits remain 2 GiB, two CPUs and 256 PIDs. No final child receipt
exists to associate with an identity. Missing evidence proves neither safe
network behavior nor a policy violation.

The older deliberate command-failure control raises before `boundary_after`.
This incident instead records that boundary after outer CLI success. The prior
failure and its tracking in [EVIDENCE.md](EVIDENCE.md) remain unchanged; no shared
root cause or repair is inferred.

## Baseline/head and execution context

The 13 execution/acquisition inputs listed in the machine receipt are byte-equal
at base and reviewed head, including the real probe, adapter, environment,
collector, scheduler, fixture server, CLI configuration, lock and setup scripts.
The pilot's complete job definitions also compare equal. `skill_evidence.py`
changes only the effectiveness profile selector from v15 to v16; the campaign
selector advances source-v6 to source-v7. Neither changes child observation.
Routing changes its
trigger, caller and concurrency envelope; profile successors record the new
source identity. Byte equality alone does not prove that routing had no effect.

The failed hosted job used Ubuntu 26.04.1, image `20261111.196.1`, region `westus2`,
and a contents-read-only job token. Checkout disabled credential persistence.
No model credential was supplied. It finished with failure, not timeout or
cancellation. The CLI phase lasted about 7.46 seconds; the post-phase observation
wait followed. The 120-minute job and 55-minute cohort-step limits were not hit.
The new concurrency group did not cancel this run. Selected jobs use separate
hosted runners, so increased job overlap does not itself establish shared local
container contention. The same job had completed verifier preparation first;
resolver state, upstream DNS responses and host pressure at the failing instant
were not retained. These remain possible environmental differences, not findings.

## Narrow matched native comparison

The manual diagnostic at orchestration revision
`7a3270eee3001aa263f22672ed6706c1700b33dc` uses the existing
`qualify_cli_observation.py` entry point. `native-deadline.yml` calls a dedicated
reusable worker with fixed baseline/head source SHAs. Each source runs once on a
fresh hosted runner, sequentially, with fresh agent containers. Both use the same
pinned CLI, evaluator, fixture, image recipe, model configuration, external policy,
observation requirements and resource limits. No model inference occurs.

The wrapper is a disclosed descendant, not historical workflow execution. Its
checkout executes the untouched historical source and records its actual revision
and executable-input identities. This exercises a reusable-workflow call, but
uses the existing two-arm `pester-001` probe rather than the failed `pester-003`
cohort after full verifier preparation. It does not reproduce that job's warm
state, concurrent workflow population, PR event or exact caller graph. It cannot
alone qualify the new pilot route or explain an intermittent DNS failure.

[Comparison 43444879139](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43444879139)
completed successfully on both sources. Both arms on each source retained three
late-child network results (allowed HTTP 401; prohibited curl 35/HTTP 000),
matching agent/policy identities and complete cleanup. The original failure did
not reproduce. There was no second comparison or retry.

Authenticated baseline artifact `14047703233` has archive SHA-256
`e1a19d5dcbc25c4a69ca6a55c3d7582fb6b19fb1ac2ec5d96e2ff132b7edf5a6`;
reviewed artifact `14047274826` has SHA-256
`8bc3acf22dc78fb0cc584039e2900ba20eb40706d256a091909e0294310e8d66`.
The machine receipt retains actual source, source-file, image, policy and
configuration identities. Python 3.14.10, Harbor 0.24.0, SkillEvaluator 0.8.0,
Docker 29.4.2, Compose 5.7.1, CLI 0.167.0, sidecar source bytes, model configuration,
policy digest and all staged members except `task.toml` agree. Task descriptors
carry generated metadata; their actual hashes and task checksums are retained.

**The comparison is not fully image-matched.** Both jobs ran in `northcentralus`,
but GitHub assigned baseline runner image `20261111.196.1` and reviewed image
`20261101.186.1`. Rebuilt agent/controller image IDs also differ despite equal
build inputs. The original failure ran in `westus2`. These differences, the
probe/cohort distinction and absent original resolver telemetry prevent ruling
out routing-related environmental effects. Successful probes do not establish
pre-existence, transience or harmlessness of the original failure.

## Changes, validation and stopping point

No observation behavior, policy, identity guard, scheduler assertion, retry,
fixture, skill, dependency, frozen input or historical result changed. Only the
manual diagnostic envelope and this investigation documentation were added.
The diagnostic workflows are outside the registered pilot/campaign executable
input sets; existing profile identity checks pass without rewriting history.

Forty focused local controls pass in the retained evaluator environment, covering
routing, gate rejection, workflow wiring, append-only profiles, CLI diagnostic
admission and deadline accounting. The initial system-Python invocation lacked
SkillEvaluator; the owning-environment run passed. The original aggregate job
[131713297221](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43367014799/job/131713297221)
correctly rejected the selected pilot failure. Tests retain rejection of every
selected failure, cancellation, skip and missing result, including malformed or
failed planning. No selector/gate behavior was changed.

Current branch rules require only `Full validation (PowerShell 7 and Bash)` and
`Pester and analyzer (latest stable PowerShell)`. `Selected validation results`
is visible but **not required**. Protection settings remain unchanged. Required
platform success does not establish success of selected validation.

Intermediate Validate `43444889332` was cancelled ahead of the known documentation
follow-up; it is inconclusive. Normal CI will run on the final documentation head;
the PR records that exact SHA and observed validation status. No full experiment
preparation workflow was manually dispatched.

**One next action:** run one instrumented, same-image baseline/head comparison
of the existing cohort through the reusable route, retaining resolver and
child-launch evidence, before reconsidering #134 review readiness.
