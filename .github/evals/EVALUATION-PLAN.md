# Evaluation direction checkpoint

Reviewed 2026-11-06: main `7b5086b`, PR #119 `1c8813b`, trial `6daec36`.

Identify skill weaknesses, justify revisions, and verify improvements without
regressions through actual Codex, Claude Code and GitHub Copilot CLIs in Actions.
The trial is Codex-only. Preserve APM deployment fidelity, independent
protected grading, explicit failure/missing-evidence states, and one reporting
experience. No observed benefit is useful.

**Recommendation, moderate confidence; adoption is not approved:** simplify direct
Harbor for behavioral evaluation, retaining production until qualification.
[Original scope][scope] replaces execution/collection, not the evaluation discipline.

- **Production:** retain static checks, history and reporting. Simplifying its
orchestration avoids migration, but retains
  SkillEvaluator staging, patched collection and score-coupled consumers.
- **PR #119:** keep draft and paused as the compatibility-upgrade alternative.
  It removes neither behavioral wrapper nor grader maintenance; completion needs
  scoring-policy resolution, native lifecycle and consumer qualification.
  [Its guard][pr] found differences in 56/73 controlled scoring vectors.
- **Trial:** retain the branch and evidence; simplify. Direct
  Harbor removes the behavioral wrapper but owns deployment staging, result
  projection, two private Codex overrides and reporting integration. Case authors
  still supply tasks, reference/defect fixtures and independent grading controls.

Authenticated artifacts, isolated graders, admission diagnostics and matched
comparisons are reusable across paths. One-off replay scripts and expired
allocation plumbing are recovery machinery; provenance, bounded image preparation,
cleanup and failure reporting remain permanent responsibilities.

[Retrospective evidence][pair] shows both submissions passed the reference
and detected 2/2 defects under one corrected verifier. No advantage was observed.
The policy changed after outputs existed: prospective grading, a justified revision
with regression checks, routine authoring and other CLIs remain
unproven. Changed model/runtime settings do not establish framework superiority.

Preserving the old composite formula is necessary for comparable historical
scores, not this goal. Recommend a separately approved versioned task-outcome
baseline; retain historical scores and never splice unlike profiles. No scoring
changes are made here.

**One next action, requiring authorization:** simplify the existing Codex/Pester
case-to-report path. Completion means one entry point, retained-pair
replay plus good/weak/missing/unsupported/error controls, and identical outcomes
and explicit diagnostics in the [existing report][report], without new recovery
layers. Preserve archived evidence. Paid scheduling (9/36 consumed), skill changes,
upgrade promotion, other runtimes and Pages changes remain paused.

Reconsider if simplification retains comparable bespoke orchestration, case authoring
needs adapter edits, or Claude/Copilot deployment and capture
cannot satisfy the same contracts. Adoption still needs prospective matched
Actions evidence and regression coverage; positive skill lift is not required.

**Session rule:** read this checkpoint first, update it when evidence changes,
and explain how the next action advances the goal. A blocker does not automatically
become another project.

[scope]: https://github.com/thetechgy/agent-engineering-baseline/blob/e64b9f6/.github/trials/direct-harbor/README.md
[pr]: https://github.com/thetechgy/agent-engineering-baseline/pull/119
[pair]: ../trials/direct-harbor/results/retrospective-pair.json
[report]: ../trials/direct-harbor/results/report.html
