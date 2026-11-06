# Evaluation direction checkpoint

Reviewed 2026-11-06 from verified clean local/remote trial head
`ade42ad124299025b6915588e2e4a4777d402283`.

The goal remains continuous skill improvement through actual Codex, Claude Code
and GitHub Copilot CLIs, faithful APM deployment, trustworthy matched comparisons
and one understandable report. The trial remains Codex-only.

**Recommendation unchanged: provisionally retain and simplify SkillEvaluator.**
The authorized credential-free `gh-014` probe establishes narrow check portability,
but stops at the existing report admission contract. It does not establish an
end-to-end bridge or a maintenance advantage for direct Harbor.

Eight synthetic current/absent controls used real fixture dispatch/receipts,
Harbor 0.25.0 ATIF validation and unchanged reviewed/patched SkillEvaluator 0.7.2
normalization/checks plus the existing gh grader. Correct output with an
unauthorized POST retained task correctness and failed authorization. Unsupported
wrappers retained unknown security; missing traces failed evidence admission.
The generic security scan alone passed the empty trace and did not recognize the
gh-specific unauthorized operation: case authorization and completeness checks
remain essential. Native grader zeros on incomplete evidence are raw gate outputs,
not measured task failures. Model judging was not invoked; composite quality is
unavailable.

The existing projection rejects truthful 0.7.2 provenance with
`Unsupported native evaluator`. Custom capture additionally requires 0.3.0,
Harbor 0.13.2 and Python 3.13. No consolidated HTML, collector integration or
rendered-state verification is claimed. Changing identity or weakening admission
to display the probe would invalidate the result. See [probe evidence and operator
instructions](../trials/direct-harbor/README.md#gh-014-portability-probe).

The [retrospective Pester pair][pair] still establishes no observed skill advantage.
Live runtime compatibility, judging accuracy, general portability, skill benefit
and lower overall maintenance remain unproven. Paid scheduling remains closed;
production, Pages, PR #119 and scoring contracts are unchanged.

**Exactly one recommended next action:** begin dependency modernization under
issue #95 using the sequence below. Its first prerequisite is a separately
versioned evaluation/report admission contract with offline qualification; do not
build another bridge against the old hardcoded identity. Current dependencies are
an explicit end state, not an indefinite exception for SkillEvaluator's old pins.
No dependency upgrade is performed by this probe.

**Session rule:** read this checkpoint first, update it when evidence changes,
and explain how the next action advances the goal. A blocker does not automatically
become another project.

## Verified state and assessment basis

| Path | Verified implementation | Evidence boundary |
| --- | --- | --- |
| [Production main][main-setup] | SkillEvaluator 0.3.0 at `ac0a04905100acdafc6c95829311a9739c340ff6`, Harbor 0.13.2, Codex 0.155.1; benchmark evidence patch and separate current/legacy review environments. | Static validation is wired into Actions. Behavioral dispatch selects Codex only. Podman and gh automatic suites are disabled; Podman retains a historical reference. Configuration is not proof that every scanner or case completed. |
| [Draft #119][pr] | Head `1c8813b520e59ef28490007cd2bc7df37b52abbe`; opt-in SkillEvaluator 0.7.2 at `f878f99a9cd4a85dd04043feb43e5bd6a777f64b`, owning Harbor 0.24.0; explicit Codex 0.155.1, evidence patch, trusted gh backend and shared Pester packaging. | Scoring guard refuses promotion. Preparation/control evidence does not establish complete native gh/Pester lifecycle qualification or production report compatibility. Main already contains the compatibility groundwork; #119 adds the adoption gate, not an adopted upgrade. |
| [Direct trial][trial-readme] | Head `c8825e2907f911562f02d8df86b59cb4c3e42f30`; Harbor 0.25.0 at `fdba28fc411e47e8765420a1a063b4918fce3def`; current profile Codex 0.166.0, GPT-6.1 Sol/high, Pester 6.2.0 and PowerShell 7.6.9. | Retained current/absent `pester-002` outputs, isolated replay and controls. Earlier Codex/model profiles and failed attempts remain historical. Different framework, CLI and model settings cannot isolate a framework advantage. |

This review inspected repository workflows, staging, graders, report consumers,
patches, tests and retained results, plus released upstream source at the revisions
above. Upstream tests establish intended contracts, not successful integration
here; none were rerun for this documentation review. Patched local source was
identified separately from release bytes. No new evaluation, model call, credential
retrieval, container qualification or CI dispatch was performed.

In the matrix, **enabled** means selected by repository configuration, **available**
means implemented upstream but not selected here, **demonstrated** means retained
observations within their stated limits, and **unverified** means additional evidence
is required. Harbor entries describe the reviewed execution/verifier interfaces and
this trial, not a claim that no other Harbor integration could implement a feature.
Dispositions preserve the objective across options; they do not authorize changes.

## Coverage matrix

| Capability | SkillEvaluator/repository today, including unused capabilities | Direct Harbor 0.25.0 and retained trial | Custom responsibility and disposition; consequence |
| --- | --- | --- | --- |
| **1. Static validation, quality, scripts, secrets/security** | **Enabled:** Tier 1 external profile, no LLM/dedup; schema/version/license, quality heuristics, Python AST lint, code integrity/hygiene, Unicode, security and PII checks. Setup supplies SkillSpector, Semgrep, Gitleaks, Bandit and pip-audit. **Available, unused:** dependency CVE audit is opt-in despite installed pip-audit; LLM rubric/security verification and Tier 2 similarity are not selected. Complete current scanner execution was **not verified** in this review. [Configuration][static-workflow], [release check lineup][se03-tier1]. | No equivalent skill-validation pipeline is configured through Harbor. Trial leaves production static checks intact. Runtime isolation and submission-retention scans serve different purposes. | **Keep** SkillEvaluator static validation and scanner diagnostics. Quality grades are structural/text heuristics; Python lint is advisory, not script correctness or PowerShell validation. Scanner errors/skips must remain visible; no findings is not proof of safety. **Defer** optional LLM static review/CVE audit expansion: no corresponding new assurance claimed. |
| **2. Discovery, activation, negative triggers, instruction following** | **Enabled:** Podman/gh activation, script invocation, workflow-order and recovery heuristics plus expected-behavior judging; gh adds native activation/negative checks. Authored positive/negative cases exist. Pester custom-only grading does not provide those standard metrics. **Available in 0.7.2:** activation summaries and suppression of lift when positive trials never activate. [Checks/tests][activation-source], [gh contract][gh-cases]. | Native trajectories and skill staging are inputs to an evaluator. The trial records attempted target-file access; successful reads and instruction following are **unverified**. It has no demonstrated negative-trigger trial. | **Keep** distinct routing, observed access and task-behavior evidence. A hybrid must reuse or replace normalizers/activation checks and add case-specific assertions. Even SkillEvaluator accepts heuristic read/tool/observation patterns: file access is not instruction following. Omitting routing prevents diagnosing whether a weak result came from discovery or skill content. |
| **3. Executable correctness and model judging** | **Enabled:** Podman standard accuracy/goal/behavior judges; gh `default_plus_custom` adds deterministic task/authorization gates; Pester `custom_only` uses protected reference/mutant checks. **Demonstrated:** fixture/control behavior and historical Podman measurements, not independently established semantic-judge accuracy. [Graders][grading-contract], [judge implementation][judge-source]. | Harbor executes a task-owned verifier and accepts numeric rewards; the trial reuses the isolated Pester grader and rich classification sidecar. Both retained submissions pass reference and 2/2 defects. No trial model judge. | **Keep** executable checks where feasible and calibrated model/human review for prose/design cases that cannot be fully tested. Direct use needs a judge bridge, fixed rubric/model provenance, error handling and protected inputs. Favorable judging is not independent correctness; reference/mutant success covers only those defects. Dropping judges without an alternative loses most Podman semantic coverage. |
| **4. Behavioral security** | **Enabled for standard grading:** deterministic trace scanning for destructive operations, secret exposure/exfiltration and unauthorized access; patched normalization/linkage prevents unsupported evidence becoming complete scores. gh adds broker receipts and per-case authorization, including malicious-comment `gh-014`. [Patch limits][patches], [security source][security-source]. | Harbor isolation limits execution risk; it does not grade whether the agent obeyed authorization or resisted injected instructions. Trial containment/retention controls are **demonstrated**, a behavioral-security scorer is not. | **Keep** explicit unsafe-action/authorization cases, trace linkage and unknown states. Reuse bounded checks where compatible, never equate isolation with safe behavior. Existing scans classify issued text, not successful access or justified privilege; unsupported wrappers and dynamic paths limit coverage. Omitting this capability can accept correct output produced through forbidden actions. |
| **5. Current/absent/revised, repeats and reliability** | **Enabled/configured:** with/without skill, standard one attempt and diagnostic confirmation three, no stop-on-pass; repository identity/completeness gates. **Available:** pass@k; 0.7.2 adds paired uncertainty and pass^k summaries. A revised skill needs a new matched run/profile, not an assumed automatic third arm. [Run policy][benchmark], [statistics][se-stats]. | Harbor has `n_attempts`, retry policy and metrics hooks. Trial enforces one matched current/absent pair, closed allocations and no pass-seeking retries. Revised arm, repeated prospective cohort and revision/regression cycle are **unverified**. | **Keep** predeclared populations, same deployment/runtime/task/grader per comparison, all attempts and explicit unavailable denominators. Pair selection, revised-run matching, regression decisions and reliability projection remain custom in a hybrid. Defer elaborate statistics until enough cases/repeats exist; one pair and pass@k alone do not establish reliability. |
| **6. Efficiency, usage and cost** | **Enabled:** heuristic skill efficiency/tool productivity, gh call budgets, native token/time/cost fields where present and repository usage summaries. **Available:** richer 0.7.2 resource comparisons. Heuristic efficiency is not monetary savings. [Metrics][se-metrics], [report extraction][reports]. | Native result/trajectory usage plus trial accounting and conservative price estimates; missing native pricing remains unknown. Retained token categories/timings exist; actual provider bills remain unknown. [Pair metadata][pair-review], [profile][runtime-profile]. | **Keep** raw usage, cache-category semantics, timing and separately labeled estimates. Billing reconciliation and budget enforcement remain operator responsibilities. **Defer** cost optimization claims/provider-bill integration; token reductions cannot be presented as verified savings. |
| **7. Dataset authoring, generation, refinement, similarity** | **Enabled:** authored Podman JSON, gh/Pester overlays, strict dataset validation and protected fixtures. **Available, unused here:** template/LLM generation, trajectory refinement, embedding deduplication/similarity. [Dataset implementation/docs][dataset-source]. | Native task directories/configuration and custom tests provide authoring primitives. Trial staging is deliberately fixed to one case; no demonstrated general authoring workflow or automatic skill-case generation. | **Keep** reviewed cases, negative controls, known-good/weak/unsafe controls and independent expected results. **Defer** automatic generation/refinement and similarity: authors do more work, duplicate/overlap detection stays manual. That is acceptable for a small deliberate suite. Generated cases are proposals; refining expectations from agent outputs risks making a benchmark reward its own mistakes. |
| **8. Consolidated reporting, history, publication** | **Enabled:** native reports feed repository `skill_evidence`, `skill_analysis`, `skill_report`, review preparation, history and authenticated Pages publication. Analyzer identifies case/gate regressions and incomplete evidence. Some custom cross-run/history use remains deferred. [Reporting contract][reporting], [analyzer][analysis]. | Trial has one local HTML report with historical failures and comparison details. It is not integrated into the repository-wide public projection/history/Pages pipeline. Harbor job results alone do not provide that experience. | **Keep** the existing consolidated reporting contract and historical identities. **Replace only the input adapter** if migrating; do not add a second reporting system. New runtime/schema/policy admission, provenance, redaction and missing-state mapping remain custom. Defer upstream dashboard/publisher duplication; omitting integration leaves fragmented evidence and misleading cross-policy comparisons. |
| **9. Podman, gh and Pester cases** | **Configured:** Podman 10 cases (including Docker-only negative and privilege judgment), gh 24 (routing, pagination, incomplete evidence, recovery, authorization), Pester five (four test-engineering cases plus Python negative control). **Demonstrated:** historical Podman run; gh replay/fixture controls; Pester oracle/control evidence. Automatic Podman/gh suites disabled. Native upgrade cohorts incomplete. [Podman dataset][podman-cases], [gh][gh-cases], [Pester][pester-cases], [orchestration][orchestration]. | Only `pester-002` has a usable retained live-output pair; 32 versus 35 tests is not a quality difference. Direct Podman/gh, other Pester cases and held-out regressions are **unverified**. | **Keep** the authored coverage and fixture limits, not necessarily every legacy aggregate. Reuse case data/graders; gh still needs its trusted broker and normalization. **Defer** expanding the trial until portability is settled. One Pester case cannot replace either suite or establish broad test-engineering quality; a `gh` command fixture does not run Copilot. |
| **10. Codex, Claude Code, actual Copilot CLI** | **Enabled/demonstrated:** Codex only in this repository. **Available:** both reviewed SkillEvaluator allowlists contain `codex`, `claude-code`, `opencode`; they exclude Copilot. Claude support in release code is not repository qualification. [0.3 agent contract][se03-agents], [0.7 agent contract][se07-agents]. | Harbor factory has Codex, Claude Code and `copilot-cli`; its adapter runs **`copilot`**, captures JSONL/ATIF and has parser tests. Only Codex deployment/execution is demonstrated here. [Copilot adapter][copilot-source], [factory][harbor-agents], [tests][copilot-tests]. | **Keep all three as a required end state. Defer execution, not the requirement.** SkillEvaluator paths need a supported Copilot integration (or a maintained extension); direct Harbor needs CLI pins/auth boundaries, APM-equivalent deployment, trace grading and reporting qualification for both missing runtimes. Neither option is complete today. Do not substitute `gh`, an SDK, or a model API for the requested CLI. |

## Compare the complete solutions

All options retain case ownership, protected reference/defect fixtures, APM
source/deployment hash checks, matched controls, pinned CLI/runtime identity,
artifact authentication/redaction, bounded preparation/cleanup, missing-evidence
states and the existing report. These are permanent evaluation responsibilities,
not incidental framework overhead. The [trial's deployment check][trial-stage]
compares the 48-file APM deployment and removes only the target's three files for
the absent arm; comparable fidelity for another runtime must be established, not
inferred from a skill directory being present.

| Option | Removes or replaces | Retains and introduces | Operator work and unresolved cost |
| --- | --- | --- | --- |
| **A. Retain/simplify production SkillEvaluator (provisional choice)** | Avoids migration-specific execution/projection adapters and score-policy transition. Can retire active use of trial allocation/replay plumbing after preserving evidence; no such removal is authorized here. | Keeps 0.3.0/0.13.2, production evidence patch, scanner environments, frozen legacy/current review runtimes, authored graders, report/history consumers and APM staging. Requires eventual supported Copilot integration; old pins and parser restrictions remain maintenance liabilities. Simplification must identify actual removable orchestration, not just rename it. | Prepare pinned tools, validate/stage cases, explicitly authorize benchmark, inspect incomplete evidence, review report, then authorize revisions and matched regressions. Reuses existing check/report semantics. Does not solve Copilot or qualify a skill revision today. |
| **B. Complete 0.7.2/0.24.0 upgrade** | Eventually replaces the active 0.3 behavioral runtime/patch with the candidate runtime/evidence patch; frozen historical readers remain. Can use upstream activation/statistics improvements rather than reimplement them. | Keeps SkillEvaluator staging/judges/collectors, scanners, shared Pester verifier and reporting system. Adds the installed trusted gh initializer backend/wheel, candidate recipe/approval manifests, score-policy/profile and consumer migration. Introduces newer owning-lock dependencies, not Harbor 0.25.0. Copilot still requires supported integration. | Resolve scoring policy explicitly, complete native gh/Pester lifecycle/cleanup gates, qualify public/report/history consumers, then authorize adoption. Preparation retries and green refusal tests do not complete those steps. No demonstrated maintenance reduction over A yet. |
| **C. Direct Harbor behavior plus selected SkillEvaluator capabilities** | Removes SkillEvaluator's behavioral task translation/orchestration and native collection only if their responsibilities are actually replaced. Could retire the production behavioral patch after equivalent checks qualify; cannot discard its conservative evidence rules. | Keeps Harbor 0.25.0, selected SkillEvaluator checks/scanners and existing graders/reports. Adds generic case/deployment staging, trajectory/check and model-judge integration, matched/repeated/revised comparison projection and report admission. Trial already owns `PinnedCodex` with two private overrides, artifact/image transport, accounting and outcome projection. gh needs broker lifecycle support. | Stage matching arms, prepare/restore authenticated images, authorize runs, inspect adapter/grade failures, project into existing report and compare. Copilot has an upstream launcher, not end-to-end proof. If activation/security/judging/collector logic must be copied, this rebuilds a substantial part of SkillEvaluator and is unlikely to be simpler. |

**Dependency accounting:** both released SkillEvaluator versions provide a base
static-only installation, but today's [setup][main-setup] installs `security` and
`tier3` for quality, benchmark and reporting, and builds a separate review runtime.
A hybrid that changes only execution retains those environments **and** adds the
Harbor 0.25.0 environment. Removing Tier 3 extras requires separate dependency and
consumer qualification. Reusing SkillEvaluator behavioral judges/checks may retain
LLM clients and internal-interface coupling even if its runner is removed.
Semgrep, SkillSpector and Gitleaks remain separate tools. Harbor itself has an LLM
and execution dependency stack. Full SkillEvaluator 0.7.2 Tier 3 owns Harbor
0.24.0, so it cannot share a resolved environment with direct Harbor 0.25.0;
reuse needs a process boundary or separately qualified minimal packaging. Package count alone is not a maintenance verdict.
See the released [0.3 manifest][se03-package], [0.7 manifest][se07-package] and
[Harbor manifest][harbor-package].

**Temporary versus permanent:** expired allocation IDs, one-off retained-submission
replay orchestration, the removed snapshot seed release and historical sandbox
probes are recovery machinery. Preserve their results without making them the
normal operator path. Reproducible dependency/image acquisition, bounded retries,
trusted artifact restoration, explicit spending authorization, isolation checks,
failure diagnostics and cleanup remain necessary with any framework. Image reuse
reduces repeated preparation; it does not eliminate supply/expiry maintenance.
No framework should be selected on the number of recovery scripts accumulated.

## Scoring decision and why the recommendation is provisional

Retain the current scoring policy for current/history comparisons. If B is later
chosen, prefer a separately approved **new versioned policy** using the released
five-dimension formula rather than a permanent six-metric compatibility fork.
Preserve old scores, metric definitions, profiles and routes; never splice the two
series. The [73-vector guard][score-guard] found 56 differences, including 0.8333
versus 0.8 or 0.9 on the same inputs. This is a weighting change, not measured skill
improvement. Neither formula is an independent correctness standard. Case-level
correctness, security and applicability must remain visible; routing-only gains
must not become task-benefit claims. A direct path also needs a versioned outcome
policy and cannot silently reuse either composite's historical identity.

A has the strongest existing coverage-to-report path and the fewest **currently
unproven replacements**. That is a coverage judgment, not a claim that old software
is inherently simpler or that past effort justifies keeping it. B remains a viable
maintenance path, but its qualification and scoring transition are not complete.
C has the clearest released launcher path to the three required CLIs, yet static
checks alone are too small a retained subset: the current Podman/gh behavior and
reporting contracts would otherwise lose useful checks. Retaining all of that by
copying internals would defeat the simplification. The probe confirms low-level
check reuse but rejects the candidate at current report admission; it does not
establish that a small complete bridge avoids this cost.

## gh-014 probe result and stopping boundary

The [retained result](../trials/direct-harbor/results/gh014-result.json),
[controls](../trials/direct-harbor/results/gh014-controls.json),
[provenance](../trials/direct-harbor/results/gh014-provenance.json) and
[first-execution diagnostics](../trials/direct-harbor/results/gh014-first-failures.json)
are synthetic diagnostic evidence, excluded from history and lift. Fixture output
was reconstructed from the existing trusted replay mechanism; no new agent session
or APM runtime deployment was observed. Both arms share task data and dispatch;
only current adds the explicitly synthetic target-read step. That activation
signal establishes the check's handling, not actual instruction following.

| Control, in both arms | Unchanged checks/grader observations |
| --- | --- |
| Good | Evidence/task/authorization = 1; current activation true, absent false. Absent gate zero reflects routing, not inferior correctness. |
| Unauthorized POST with correct output | Evidence/task = 1, authorization/commands = 0. Generic security scanner reports no finding; per-case authorization catches the forbidden behavior. |
| Unsupported native Codex wrapper | Normalizer supplies `unsupported_native_codex_exec_wrapper`; security is unknown, evidence gate zero. Current's preceding synthetic read remains observed; absent activation is unknown. |
| Missing required trace | Evidence gate zero; raw grader dimensions zero, composite unavailable. Generic scanner's empty-trace pass cannot establish safety. |

The actual `skill_evidence.normalize_behavioral` entry point, using a minimal
explicitly incomplete synthetic envelope without measurements, reaches
`validate_runtime_versions` and rejects the actual candidate identity before public
projection and consolidated rendering.
`custom_capture` also binds its producer runtime and registered profile. A transport
adapter cannot truthfully satisfy those contracts. Collection/rendering were not
continued after this prerequisite rejection; no diagnostic HTML was fabricated.
This is a concrete contract incompatibility, not proof that a small adapter can
never work after an independently qualified consumer migration. Stop here under
the authorized criterion; retain the existing reporting system.

Private interfaces, environments, process boundary, operator steps and cleanup
are documented with the single entry point in the trial README. No new normalizer,
scorer, collector, report stack, production profile or admission exception was added.

## Dependency modernization sequence

Latest stable targets below were verified against primary release/package/image
metadata on **2026-11-06**, retained in
[the target evidence](../trials/direct-harbor/results/dependency-targets.json).
These are dated targets to recheck immediately before implementation, not new pins.
Use `.github/dependency-freshness.json`, its existing workflow/script, Dependabot,
the reviewed weekly APM updater, and [issue #95](https://github.com/thetechgy/agent-engineering-baseline/issues/95).
Do not add another dependency tracker. Reconcile every manifest, hash lock, setup
script, workflow, image and transitive inventory; the examples below are not an
exemption for unnamed dependencies.

| Order / owning boundary | Verified stable target and scope | Qualification and concrete hold exit |
| --- | --- | --- |
| 1. Active evaluator and evidence/report consumers | SkillEvaluator **0.8.0**, Harbor **0.25.0**, Python **3.15.2** are separate upstream targets. 0.8.0 still pins Harbor 0.24.0, Python `<3.15`, LiteLLM `<1.94.0.dev0`, MCP `<2`. Thus updating only SkillEvaluator does not meet the end state. | First define versioned producer/admission/profile identities and offline custom/standard collection, projection and rendering controls. Then qualify the owning evaluator lock and reviewed patch, trusted gh initializer and native Pester lifecycle. Resolve upstream constraints through a supporting upstream release or explicitly reviewed source/lock changes; keep unresolved target gaps explicit. Hold ends only with native lifecycle/cleanup and truthful report admission under the new profile. No model inference is needed for these fixture gates. |
| 2. SDKs and locked transitives, by owner | OpenAI **3.47.0** (GitHub release; PyPI metadata observed **3.46.0**), Anthropic **2.6.0**, LiteLLM **1.108.2**, MCP **2.3.0**, Pydantic **2.14.3** / core **2.50.4**. Apply to each active evaluator, scanner, review and trial lock separately; refresh all other resolved transitives from each owner's inventory. | Do not force incompatible extras into one installation. Update current review overlays independently with API/schema/redaction and public-only replay checks. Evaluator lock changes must pass grading/normalization regressions and dependency consistency. SDK/MCP major versions remain temporary explicit gaps until their owner supports them or an approved compatibility change qualifies them. Confirm distribution publication/hash before installing OpenAI 3.47.0; the primary metadata sources differ. Frozen historical readers remain separate. |
| 3. CLIs, APM, task runtimes and images | Codex **0.167.0**, Claude Code **2.1.319**, Copilot **1.0.107**, gh **2.103.3**, APM **0.35.0**, uv **0.13.7**, Compose **5.7.0**, PowerShell **7.6.9**, Pester **6.2.0**, PSScriptAnalyzer **1.25.0**. Latest Python image target `3.15-slim-trixie` and Alpine `latest` have dated digest evidence; Python 3.14 image is only an intermediate compatible target. | Use verified release archives/digests and existing APM regeneration/update path; review all source skill refs through that path. Rebuild pinned OS/package snapshots as a group, qualify Windows/Linux bootstrap, APM byte fidelity, agent setup/capture and protected verifier/cleanup controls. Recheck current Debian/Node/package inventories when rebuilding rather than retaining old snapshots silently. Claude/Copilot targets are planned, not runtime expansion in this probe. Hold ends with the affected runtime/fixture gates; actual CLI evaluation still requires separately authorized inference. |
| 4. Scanner/lint hash locks | SkillSpector **2.13.4**, Semgrep **1.184.0**, Gitleaks **8.30.1**, Bandit **1.9.4**, pip-audit **2.10.1**, rumdl **0.3.2**. | Regenerate each owning frozen/hash lock with reviewed tooling; compare representative findings, skipped/incomplete scanners, redaction and public catalog projection. A successful installation is insufficient. Resolve holds when those scanner regressions and collection checks pass. |
| 5. Existing Actions and publication integration | checkout **7.0.1**, upload-artifact **7.0.2**, download-artifact **8.0.2**, setup-uv **10.3.3**, configure-pages **6.0.0**, deploy-pages **5.0.1**, upload-pages-artifact **5.0.0**, github-action-benchmark **1.22.2**. | Reuse Dependabot, resolve stable releases to reviewed immutable SHAs, check runtime/runner requirements, artifact authentication/attempt/digest tests and permission boundaries. Qualify publication fixtures without publishing Pages. Hold ends on those contracts and required CI at the final revision. |

The groups form one modernization phase, with group 1's admission contract as the
specific prerequisite exposed by this probe. Uncoupled scanner/Actions work can
proceed within that phase; newer dependencies must not be held hostage to a paid
benchmark. Maintain a visible unresolved gap where an upstream owner pins older
versions. A latest compatible intermediate must never be labeled fully current.

Active production, opt-in candidate and direct trial environments retain distinct
owning locks until each replacement qualifies. Historical replay environments,
archived results and original runtime identities remain frozen and isolated for
reproduction; modernization applies to active replacements rather than rewriting
history. Retire historical tooling from active paths when current readers can
reproduce the archived public outputs. Historical exceptions must name their replay
purpose, not justify obsolete active production dependencies.

Any formula/metric/profile change creates a new versioned policy and matched
baseline. Preserve original scores and never describe a score change caused by
new weighting, model, CLI or dependencies as skill improvement. Dependency refresh
is the next implementation phase; adopting direct Harbor or resuming paid work is
not part of that recommendation.

## Supporting evidence

Repository sources are pinned to the reviewed heads; trial evidence stays in its
existing location. Historical narratives remain in the [trial README][trial-readme]
and [single trial report][report], not duplicated here.

- Static implementation and tests: released [validator implementations][validators]
  and [validator tests][validator-tests]. Structural scores, advisory lint and
  scanner availability are separate from behavioral success.
- Behavioral implementation and tests: [activation/negative-case checks][activation-source],
  [activation scoring tests][activation-tests], [judge code][judge-source],
  [trace security][security-source] and [report incompatibility tests][report-tests].
- Repository evidence controls: [production/candidate patch boundaries][patches],
  [candidate qualification contract][candidate], [trusted gh initialization][initializer],
  [Pester controls][pester-cases] and [reporting/evidence contract][reporting].
- Direct execution primitives: [Harbor job configuration][harbor-job],
  [verifier reward parsing][harbor-verifier], [agent factory][harbor-agents] and
  [Copilot trajectory tests][copilot-tests]. Source/tests show available interfaces,
  not repository-native qualification for Claude or Copilot.

[pr]: https://github.com/thetechgy/agent-engineering-baseline/pull/119
[main-setup]: https://github.com/thetechgy/agent-engineering-baseline/blob/7b5086b11f075007d5af582fadb4ff3bf521b570/.github/scripts/setup-skillevaluator.sh
[static-workflow]: https://github.com/thetechgy/agent-engineering-baseline/blob/7b5086b11f075007d5af582fadb4ff3bf521b570/.github/workflows/validate.yml#L181-L216
[benchmark]: https://github.com/thetechgy/agent-engineering-baseline/blob/7b5086b11f075007d5af582fadb4ff3bf521b570/.github/workflows/benchmark-skills.yml
[reports]: https://github.com/thetechgy/agent-engineering-baseline/blob/7b5086b11f075007d5af582fadb4ff3bf521b570/.github/scripts/skill_reports.py
[analysis]: https://github.com/thetechgy/agent-engineering-baseline/blob/7b5086b11f075007d5af582fadb4ff3bf521b570/.github/scripts/skill_analysis.py
[reporting]: https://github.com/thetechgy/agent-engineering-baseline/blob/7b5086b11f075007d5af582fadb4ff3bf521b570/.github/evals/REPORT-EVIDENCE.md
[orchestration]: https://github.com/thetechgy/agent-engineering-baseline/blob/7b5086b11f075007d5af582fadb4ff3bf521b570/.github/evals/orchestration.json
[patches]: https://github.com/thetechgy/agent-engineering-baseline/blob/7b5086b11f075007d5af582fadb4ff3bf521b570/.github/patches/README.md
[candidate]: https://github.com/thetechgy/agent-engineering-baseline/blob/7b5086b11f075007d5af582fadb4ff3bf521b570/.github/evals/EVALUATOR-CANDIDATE-95.md
[initializer]: https://github.com/thetechgy/agent-engineering-baseline/blob/7b5086b11f075007d5af582fadb4ff3bf521b570/.github/evals/GH-INITIALIZER-95.md
[score-guard]: https://github.com/thetechgy/agent-engineering-baseline/blob/1c8813b520e59ef28490007cd2bc7df37b52abbe/.github/scripts/evaluator_scoring_compatibility.py
[grading-contract]: https://github.com/thetechgy/agent-engineering-baseline/blob/7b5086b11f075007d5af582fadb4ff3bf521b570/.github/evals/custom-metrics.json
[podman-cases]: https://github.com/thetechgy/agent-engineering-baseline/blob/7b5086b11f075007d5af582fadb4ff3bf521b570/.apm/skills/podman/evals/evals.json
[gh-cases]: https://github.com/thetechgy/agent-engineering-baseline/blob/7b5086b11f075007d5af582fadb4ff3bf521b570/.github/evals/gh/EVALS.md
[pester-cases]: https://github.com/thetechgy/agent-engineering-baseline/blob/7b5086b11f075007d5af582fadb4ff3bf521b570/.github/evals/powershell-pester-6/EVALS.md
[trial-readme]: ../trials/direct-harbor/README.md
[trial-stage]: ../trials/direct-harbor/run.py
[pair]: ../trials/direct-harbor/results/retrospective-pair.json
[pair-review]: ../trials/direct-harbor/results/pair-review.json
[report]: ../trials/direct-harbor/results/report.html
[runtime-profile]: ../trials/direct-harbor/runtime-profile.json
[se03-tier1]: https://github.com/NVIDIA/SkillEvaluator/blob/ac0a04905100acdafc6c95829311a9739c340ff6/src/skillevaluator/tier1/commands.py
[validators]: https://github.com/NVIDIA/SkillEvaluator/tree/ac0a04905100acdafc6c95829311a9739c340ff6/src/skillevaluator/validators
[validator-tests]: https://github.com/NVIDIA/SkillEvaluator/tree/ac0a04905100acdafc6c95829311a9739c340ff6/tests/validators
[se03-package]: https://github.com/NVIDIA/SkillEvaluator/blob/ac0a04905100acdafc6c95829311a9739c340ff6/pyproject.toml
[se07-package]: https://github.com/NVIDIA/SkillEvaluator/blob/f878f99a9cd4a85dd04043feb43e5bd6a777f64b/pyproject.toml
[se03-agents]: https://github.com/NVIDIA/SkillEvaluator/blob/ac0a04905100acdafc6c95829311a9739c340ff6/src/skillevaluator/tier3/harbor/__init__.py
[se07-agents]: https://github.com/NVIDIA/SkillEvaluator/blob/f878f99a9cd4a85dd04043feb43e5bd6a777f64b/src/skillevaluator/tier3/harbor/__init__.py
[activation-source]: https://github.com/NVIDIA/SkillEvaluator/blob/f878f99a9cd4a85dd04043feb43e5bd6a777f64b/src/skillevaluator/tier3/eval_core/checks.py#L3771
[activation-tests]: https://github.com/NVIDIA/SkillEvaluator/blob/f878f99a9cd4a85dd04043feb43e5bd6a777f64b/tests/tier3/test_skill_activation_scoring.py
[judge-source]: https://github.com/NVIDIA/SkillEvaluator/blob/f878f99a9cd4a85dd04043feb43e5bd6a777f64b/src/skillevaluator/tier3/eval_core/llm_judge.py
[security-source]: https://github.com/NVIDIA/SkillEvaluator/blob/f878f99a9cd4a85dd04043feb43e5bd6a777f64b/src/skillevaluator/tier3/eval_core/checks.py
[se-stats]: https://github.com/NVIDIA/SkillEvaluator/blob/f878f99a9cd4a85dd04043feb43e5bd6a777f64b/src/skillevaluator/tier3/harbor/stats.py
[se-metrics]: https://github.com/NVIDIA/SkillEvaluator/blob/ac0a04905100acdafc6c95829311a9739c340ff6/src/skillevaluator/tier3/harbor/metrics.py
[dataset-source]: https://github.com/NVIDIA/SkillEvaluator/blob/f878f99a9cd4a85dd04043feb43e5bd6a777f64b/docs/eval-datasets.mdx
[report-tests]: https://github.com/NVIDIA/SkillEvaluator/blob/f878f99a9cd4a85dd04043feb43e5bd6a777f64b/tests/reporting/test_tier3_unavailable_lift_labels.py
[harbor-package]: https://github.com/harbor-framework/harbor/blob/fdba28fc411e47e8765420a1a063b4918fce3def/pyproject.toml
[harbor-agents]: https://github.com/harbor-framework/harbor/blob/fdba28fc411e47e8765420a1a063b4918fce3def/src/harbor/agents/factory.py
[harbor-job]: https://github.com/harbor-framework/harbor/blob/fdba28fc411e47e8765420a1a063b4918fce3def/src/harbor/models/job/config.py
[harbor-verifier]: https://github.com/harbor-framework/harbor/blob/fdba28fc411e47e8765420a1a063b4918fce3def/src/harbor/verifier/verifier.py
[copilot-source]: https://github.com/harbor-framework/harbor/blob/fdba28fc411e47e8765420a1a063b4918fce3def/src/harbor/agents/installed/copilot_cli.py
[copilot-tests]: https://github.com/harbor-framework/harbor/blob/fdba28fc411e47e8765420a1a063b4918fce3def/tests/unit/agents/installed/test_copilot_cli_trajectory.py
