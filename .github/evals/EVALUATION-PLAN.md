# Issue #95 dependency modernization checkpoint

This is the authoritative active checkpoint for the upgrade on draft [PR #119](https://github.com/thetechgy/agent-engineering-baseline/pull/119).
The direct-Harbor assessment at `389f7222da8d425b95dad12003e1e6895500a397`
is historical evidence, not the implementation base. Production remains unchanged.

## Frozen first group

The selected release is [SkillEvaluator 0.8.0](https://github.com/NVIDIA/SkillEvaluator/releases/tag/v0.8.0),
released November 6, 2026, at `8149356e4476a1497fb334727f13f699c6fa6ba5`.
Its [released manifest](https://github.com/NVIDIA/SkillEvaluator/blob/8149356e4476a1497fb334727f13f699c6fa6ba5/pyproject.toml)
requires Python `>=3.12,<3.15`, Harbor `==0.24.0`, LiteLLM `>=1.92.0,<1.94.0.dev0`,
OpenAI `>=2.21.0`, Anthropic `>=0.83.0`, and Pydantic `>=2.11.0`.

The [candidate profile](evaluator-candidate.json) freezes Python 3.14.10,
Harbor 0.24.0, OpenAI 2.54.0, Anthropic 2.6.0, Pydantic 2.14.3 /
pydantic-core 2.50.4, LiteLLM 1.93.2, typing-inspection 0.4.5 and the unchanged
locally built backend 1.0.0 for interface controls only. Its execution guard remains
0.7.2-only; live candidate gh startup is explicitly unqualified. The [resolved lock](../locks/evaluator-candidate.lock)
was upgraded using uv 0.13.7 against the released manifest, without dependency overrides.
Registry artifacts retain their hashes; frozen installation and `uv pip check` are required.
The profile binds the source tree, release revision, patch and lock independently.

This is a **current evaluator with constrained dependencies**, not all dependencies current.
[Harbor 0.25.0](https://github.com/harbor-framework/harbor/releases/tag/v0.25.0)
and [Python 3.15.2](https://www.python.org/downloads/) are outside the evaluator's
supported constraints. Advancing those requires an upstream evaluator constraint change,
then a fresh compatible lock and qualification. LiteLLM must remain below 1.94;
advance it when the evaluator supports the newer line. Do not force a framework fork.

The 0.8.0 evidence patch retains the reviewed classifier, wrapper/observation linkage,
standalone verifier payload, conservative attribution, fixed custom diagnoses,
explicit Codex pin and verifier-only offline Compose rule. Pristine 0.8.0 still
failed their controls; none was found incorporated sufficiently to remove.
One sensitive-path hunk was ported to upstream's changed surrounding code.
The upstream scoring implementation is unchanged.

## Reporting and interpretation

Historical 0.3.0 and its metric-mean scoring retain their original identities and results.
The 0.7.2 exact-score diagnostic remains available manually; numerical equality with
that policy is no longer an adoption requirement. The current offline profile uses
upstream dimension-mean scoring for standard rewards and custom-overall scoring
for custom-only rewards. Seventy-three controlled vectors check the new formula.
Policy, producer and artifact metric-set identities are distinct. Unknown or
contradictory identities and changed evidence remain rejected.

The existing collectors, native normalizers, guarded public writer, analyzer and
consolidated renderer carry candidate evidence. No parallel reporting system is added.
Frozen analyst-attachment profiles retain
their original validator hashes and require matching retained tooling snapshots;
the changed checkout is not relabeled as `current-v4`. A new analyst-review
profile is not qualified by this phase.
Captured numeric evidence handles 0.8.0's omission of sensitive metric names;
only validated enrolled originals supply those values. Missing evidence remains
unavailable, including raw fallback zeros. Correct-but-unauthorized gh output keeps
its task result and fails authorization. Deliberately absent skills affect activation
and the historical combined gate, not shared task correctness. Raw synthetic judge
transport values are retained separately; judged quality and composites remain null.
Candidate records are labeled synthetic, unmeasured and excluded from production history.
Cross-policy comparisons do not produce improvement deltas.

## Qualification and limits

Use `setup-skillevaluator.sh reporting` for isolated historical runtimes and
`setup-skillevaluator.sh candidate-current` for the replacement. Then invoke
`qualify_current_evaluator.py --output` with a new persistent evidence directory and
`SKILL_REVIEW_PYTHON` selecting the retained historical interpreter. Disposable
fixtures honor `TMPDIR`. The new `current-evaluator.yml` workflow reproduces this
without model credentials, inference, judges, scheduling or Pages.

Local evidence includes actual standard verifier/collector transport, gh fixture
replay with receipts and collector transport, retained synthetic Pester outcome
carriers, negative identity/integrity checks and the existing HTML report. Pester
carriers test reporting, not executable-submission quality. Mocked lifecycle controls
establish wiring only. The separate native preparation job observes one startup
attempt and cleanup; a failed build is an infrastructure result, not a quality zero.
No blind preparation retry is selected for the new profile. Initial upgrade CI
successfully built the pinned fixture, observed PowerShell 7.6.9 / Pester 6.2.0,
and verified teardown on its first attempt. This is package startup evidence,
not execution of the complete native grading cohort. Final-revision CI and the
downloadable report are linked from PR #119.

Validation results and report artifacts are recorded in PR #119. Native agent lifecycle,
complete native Pester/gh cohorts, provider compatibility, judging accuracy and skill
benefit remain unqualified. Candidate adoption is blocked; production defaults,
Codex/model/task inputs and historical environments are unchanged.

## Next group

Exactly one recommended next action: modernize SkillSpector and its scanner owning
environments through the existing update and freshness workflows, with controlled
scanner and public-projection regressions. This independent group does not wait for
paid evaluation. Scanners, CLIs, Actions, images and the remaining owning environments
remain in the existing freshness inventory; this phase does not claim they are current.
