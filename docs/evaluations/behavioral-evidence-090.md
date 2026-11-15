# Versioned SkillEvaluator 0.9.0 behavioral evidence

Implemented from verified main `66c3f92a40b0f00bb461286596a2016a6a39108a`,
PR #141's completed static-quality migration. #138's data-only hosts, #139's
unscored finding retention and #140's strict dataset correction are already merged.
This change qualifies an explicit offline behavioral evidence path. It does not
adopt a new production execution runtime or authorize inference.

## Contract and ownership

`behavioral-090-offline-v1` in `.github/evals/benchmark-090.json` binds the existing
`skillevaluator-0.9.0-offline-v3` producer. Its released revision, installed source,
patch, lock, backend, Python and dependencies are verified by existing
`evaluator_profiles.runtime(..., owning=True)` before native admission. Package
version alone is insufficient. No PATH lookup selects a producer.

| Boundary | Owner and observable behavior |
| --- | --- |
| Execution | Existing benchmark workflow and 0.3.0 / Harbor 0.13.2 policy, unchanged |
| Runtime interpretation | `evaluator_090.py` and the versioned profile; released score, applicability, verdict and aggregate APIs |
| Recovery | Existing `skill_reports.py recover`, with an explicit evidence-profile option; native collector retains primary outcome and available diagnostics |
| Admission | Existing bounded native reader, task/case/trial/model identity, error ledgers, snapshots, runtime ownership and transient evidence witness |
| Task correctness/custom grading | Existing task definitions and gh/Pester graders; no grader moved into shared reporting |
| Versioned observations | `benchmark_evidence.py` supplies closed policy/origin/judgment metadata, observation links, native dimensions and population accounting |
| Artifact handoff | Existing `benchmark_artifacts`, redaction, `public-benchmark`, secure output and public string gates |
| Consolidated presentation | Existing analysis/HTML commands; one additional behavioral evidence section |
| History | Pure eligibility simulation plus refusal at existing publisher/compact-history boundaries; no ledger write |

The extension is carried as `benchmark` in the existing public contract. Legacy
headline metrics remain empty for these fixtures. Its observations have separate
`observed`, `not_applicable` and `unavailable` states; populations additionally
retain expected and absent counts. A reported zero stays an observed zero.
The native-dimension values are the released aggregate values, checked against
captured rewards; they are not averages invented from unlike trial populations.

Every extension claim is included in the existing native witness digest. Altering
an admitted claim or its captured inputs prevents projection. Offline-v2, 0.8 and
all earlier profiles retain their original definitions. Source-only successors
bind changed shared admission/reporting bytes without changing frozen selections,
experiment definitions, grades, allocations or original replay owners.

## Released differences from 0.3.0

The source was inspected at tagged release `v0.9.0`, commit
`b78d14618a694dec84bc9601468f8f711df5cab3`, and against the qualified offline-v3
implementation. Relevant released implementations and tests are:

- [metrics.py](https://github.com/NVIDIA/SkillEvaluator/blob/v0.9.0/src/skillevaluator/tier3/harbor/metrics.py),
  [metric truth controls](https://github.com/NVIDIA/SkillEvaluator/blob/v0.9.0/tests/test_harbor_metrics_truth.py):
  0.3.0's six-metric mean is distinct from 0.9.0's equal mean of five canonical
  dimensions. Effectiveness combines goal accuracy and behavior with equal weights.
  No historical score is recomputed under the new formula.
- [attempt_verdict.py](https://github.com/NVIDIA/SkillEvaluator/blob/v0.9.0/src/skillevaluator/tier3/attempt_verdict.py),
  [required-check tests](https://github.com/NVIDIA/SkillEvaluator/blob/v0.9.0/tests/test_tier3_attempt_verdict.py):
  goal/security requirements can fail an attempt whose overall score exceeds its
  threshold. The native wrong-answer fixture demonstrates that distinction;
  a separate fixture has correct-answer evidence and a security failure. Task
  failure does not imply failed runtime execution. No new run-level effectiveness
  verdict is inferred from attempt verdicts.
- [applicability tests](https://github.com/NVIDIA/SkillEvaluator/blob/v0.9.0/tests/tier3/test_skill_metric_applicability.py):
  explicit native N/A markers exclude metrics and can omit dimensions. Missing
  values alone remain unavailable. A negative case keeps its correct nonactivation
  check while efficiency is N/A; baseline skill metrics can be N/A. The runtime
  helper owns this interpretation, rather than a repository heuristic.
- [collector.py](https://github.com/NVIDIA/SkillEvaluator/blob/v0.9.0/src/skillevaluator/tier3/harbor/collector.py):
  an incomplete arm can retain trial observations while suppressing pass summaries.
  `num_trials` counts scoreable reward rows, not every retained trial diagnostic.
  Interrupted-job rewards withheld by the collector cannot become quality scores.

The first released negative fixture was rejected by the existing threshold-only
summary validator. The focused policy now validates that verdict with the released
`attempt_verdict`, preserving the old validator for old evidence. The qualifier
also exposed the existing unscored diagnostic's narrower transport assumption:
when only judges fail, the released verifier can retain deterministic security,
execution and efficiency values alongside an overall transport zero. The new
policy admits only those bounded native observations under explicit judge-error
keys. It does not turn transport zero into quality or change the historical
unscored diagnostic interpretation. Unsupported execution remains unscored;
known findings survive independently through offline-v3's existing contract.

## Offline entry points and validation

Use existing setup kind `candidate-next`, then its absolute `SKILL_NEXT_PYTHON`:

```sh
"$SKILL_NEXT_PYTHON" -B .github/scripts/qualify_benchmark_evidence.py --output "$EVIDENCE_ROOT/behavioral-090"
```

The destination must be new and outside the checkout. The qualifier starts a child
with an allowlisted environment, no model credentials, dotenv disabled and a
network audit guard. It generates real released Harbor tasks, reads trajectory and
entry files with the released verifier, instantiates native `TrialResult` and
`JobResult` models, and calls `collect_harbor_results`. Only judge responses are
simulated. There is no agent, inference, real judge or provider dispatch.

The complete fixture includes positive and measured negative outcomes, independent
correctness/security outcomes, baseline N/A and negative-case N/A. The unavailable
fixture retains a valid deterministic observation after judge failure, unsupported
wrapper evidence with a known secret finding, and a primary agent runtime failure.
Recovery removes a trial from both physical and embedded native carriers and marks
the native job nonterminal. The recovered report retains cancellation, nine trial
diagnostics, one absent attempt and ten unaffected baseline observations.

All three routes reach admission, sanitized artifacts, public projection,
consolidated HTML and simulated history refusal. Controls reject profile/producer,
model/settings/grading, cohort and policy mismatches, altered native witnesses,
fixture promotion and unavailable-to-numeric changes. Full released task failure
and infrastructure failure remain separate outcomes. Known findings survive
without creating security cleanliness or numeric quality.

Operators can consume an already captured, explicitly profiled native bundle with
`skill_reports.py benchmark-evidence ROOT SKILL MODE DESTINATION`, or recover it
with `recover ROOT SKILL MODE OUTCOME --evidence-profile behavioral-090-offline-v1`.
The ordinary `benchmark`, `publish`, production selectors and credentials path are
unchanged. Profile metadata cannot select live judging or production eligibility.

The [sanitized local receipt](behavioral-evidence-090-receipt.json) records the
fixture route, source identities, history exclusions and retained report reproduction.
The rendered HTML content was inspected for outcome labels, N/A/missing populations
and known findings. Browser access was unavailable, so no browser visual acceptance
is claimed.

Normal change-selected Validate runs the qualifier inside its existing contracts
job after existing candidate-next setup. It uploads only public reports, saved
analysis, consolidated HTML and a sanitized receipt. No new matrix, installer,
dashboard or storage system is introduced. The PR records final-revision CI and
artifact authentication/reproduction separately from local fixture results.
Existing selected native gh and Pester routes continue to exercise their own
custom grading contracts. Unchanged #136/#139/#141 qualification evidence remains
applicable to unchanged runtime, scanner and finding-retention components.

The first hosted run, [43689241906](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43689241906),
was cancelled for a known follow-up and is inconclusive overall. Its two required
platform checks and static quality passed; available artifacts and logs are retained.
The earlier broad local diagnostic used an older review SDK environment, omitted
pinned scanners and overlapped source changes. Its failures are not a passing or
final-revision result. Diagnosis found one actionable legacy CLI dispatch regression:
passing an unnecessary `evidence_profile=None` keyword. The caller now preserves
its original argument contract unless the new profile is requested. That control
and five source/frozen-contract controls pass after correction. The seven native
behavioral controls also pass again. Final selected CI remains authoritative.

## Comparison, history and rollback

Comparison identities include task/dataset/cohort, runtime/model/settings,
producer/patch, scoring and grading policy, judgment origin, and both deployment
conditions. An absent essential identity remains a comparison limitation. Policies
cannot be pooled by matching display metric names. Simulated history admission
returns a policy-specific series identity and explicit exclusion reasons, including
fixture origin, simulated judgments, recovery and incomplete coverage. It never
returns production eligibility. Both existing public publisher admission and compact
history admission refuse these records as standard production history, even if the
extension is removed while the candidate producer identity remains.

Rollback reverts this focused change as a unit, restoring prior shared consumers
and source selectors. Production execution requires no rollback because it never
moves. Preserve original native/public evidence, profile identities and receipts;
replay with the original checkout and owning interpreter. Do not delete, relabel
or rescore new records as 0.3.0 or reopen frozen 0.8 experiments.

This removes the repository's offline behavioral recovery/reporting/history
contract gap. Live adoption still needs a separately reviewed execution policy,
authenticated intended provider/model routing and a separately authorized bounded
live check. Judge accuracy and full skill effectiveness need their own appropriate
controls and matched live evidence. Closed paid allocations, deferred Pester work,
CLI/model pins, gates, schedules, Pages and private review owners remain unchanged.

Workflow security review: critical 0, high 0, medium 0, low 0. Checked triggers,
read-only permissions, literal command arguments, pinned Actions, non-persistent
checkout credentials, secret isolation and the bounded public artifact handoff.
