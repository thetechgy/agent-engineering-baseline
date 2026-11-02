# After compatibility: skill diagnostics and revision comparisons

SkillEvaluator remains a candidate. Keeping it requires evidence that its reports
help explain and verify skill changes. A passing benchmark or numerical lift is
insufficient. This document changes no scoring, reporting, history or benchmark
configuration and authorizes no evaluation run.

Use separate condition identities for GPT-5.6 Sol and GPT-6.1 Sol, each tool mode,
runtime/catalog/protocol version, reasoning effort, fixture cohort and grading
policy. The user currently uses GPT-6.1 Sol in development. Both model entries
exist in the pinned runtime catalog with Code Mode defaults; the initial Direct
profile overrides only GPT-5.6 Sol. It does not qualify GPT-6.1 Sol or stock Code
Mode's missing attempted-action evidence. Representative development conditions
must be captured and separately qualified before comparison or history admission.

Prioritize existing gh-010-partial diagnostics first: did native discovery expose
the skill, was it actually read, did an exit-1 partial mutation lead to a safe
verification query or a duplicate mutation, what was attempted/denied/executed,
and what effects did an independent verifier establish? Distinguish a skill gap
from model choice, unavailable evidence, harness failure and artificial limits.
Then consider gh-002, gh-013-hardening and Podman case 1 with their existing
contracts, under separately bounded authorization.

For a proposed skill revision, preserve original skill bytes/source identity and
state the specific failure the revision is intended to address. Compare the
original/revised skill on matched model/mode/runtime/fixture/grading conditions,
with independently initialized private state and ordinary without-skill baselines.
Keep changed datasets as distinct cohorts. Retain native decision/read/recovery
sequences, attempted authorization, execution, audit and effects as separate
records. Missing/partial evidence is unavailable; baseline activation keeps its
current meaning. Do not alter grading to manufacture an improvement.

Framework acceptance requires a concrete report that traces a failure to retained
evidence, supports an actionable revision, and shows whether the relevant failure
recurred under matched conditions. Report remaining failures, limits, cost and
repeat variability. A score delta alone does not establish skill causality.
Default-plus-custom built-in metrics, custom gh dimensions, default overall and
history admission remain separate qualification gates. If the reports cannot
support these decisions reliably, the framework decision stays open.
