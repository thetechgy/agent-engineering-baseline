# Issue #95 dependency modernization checkpoint

This is the authoritative active checkpoint for the upgrade on [PR #119](https://github.com/thetechgy/agent-engineering-baseline/pull/119).
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
locally built backend 1.0.0. Its wheel metadata now admits Python 3.14, and its
execution guard admits only the reviewed 0.7.2/Python 3.13 and
0.8.0/Python 3.14.10 pairs with Harbor 0.24.0. The [resolved lock](../locks/evaluator-candidate.lock)
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

The reviewed `printf -v` correction gives the diagnostic producer an explicit
`skillevaluator-0.8.0-offline-v2` identity. Bash variable assignments remain
unresolved evidence, rather than safe printing; ordinary `printf` data remains
text. The upstream release, all dependency pins, lock and scoring policy are
unchanged. Only the evidence patch/source-tree hashes change. Earlier v1 evidence
retains its original identities and the tooling snapshot at `8e6b991`; it is not
relabeled or accepted under v2. Native qualification must complete with the new
patch before v2 is qualified.

## Reporting and interpretation

Historical 0.3.0 and its metric-mean scoring retain their original identities and results.
The 0.7.2 exact-score diagnostic remains available manually; numerical equality with
that policy is no longer an adoption requirement. The current offline profile uses
upstream dimension-mean scoring for standard rewards and custom-overall scoring
for custom-only rewards. Seventy-three controlled vectors check the new formula.
Policy, producer and artifact metric-set identities are distinct. Unknown or
contradictory identities and changed evidence remain rejected. Omitted policy
metadata cannot erase the independently captured candidate producer: such records
remain incomplete and unmeasured. Missing candidate runtime provenance is rejected.

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

The integrated qualification extends that entry point with `--native`. It runs
all 48 existing gh startup/lifecycle cases through the existing six fixed shards,
plus 48 real Harbor oracle gh trials and the existing 52 native Pester oracle trials.
Observed hosted image builds took about 118 seconds per case, making the original
sequential whole-cohort deadline inadequate. The fixed shard recipe is reused with
two concurrent lifecycle jobs; the oracle cohorts retain their native concurrency.
Only same-run, same-attempt, exact-revision evidence can complete the final join. The gh bridge is necessary because
the lifecycle harness alone does not produce Harbor trial records for collection.
It uses the existing oracle, collector, public evidence writer, analyzer and renderer.
The fixture-only `gh-native-oracle-v1` custom profile keeps the existing gate and
metric definitions; the active production gh profile and standard scoring are unchanged.
Native oracle records remain separate from synthetic transport controls and are
ineligible for skill-benefit or production-history claims.

Expected outcomes are fixed before execution. In each gh arm, gh-001 uses the reviewed
wrong-repository control; gh-002 uses an unsupported trace; gh-003 omits its trace;
gh-014 performs a correct task plus an unauthorized fixture API action. Other cases
use their reviewed correct commands. Broken work must fail task correctness;
unauthorized work must retain correctness and fail authorization. Unsupported and
missing evidence must remain unavailable. Skill absence retains its activation/gate
consequence without turning correct task work into a correctness failure.
Pester must retain 22 passed, 14 failed, 8 invalid, 2 timeout, 2 unsupported and
4 infrastructure-error outcomes. Reference and seeded-mutant evidence, runtime,
arm and checksum identities must agree. A passing qualification does not relabel
negative outcomes, missing evidence, or aggregate execution failures.

The existing bounded command observer records gh build/start stages without raw
arguments. Oracle launch stages and sanitized failure diagnostics are retained;
cleanup is checked after success and failure. The final report includes the actual
native results alongside clearly marked synthetic reporting controls. Its included
public evidence and saved analysis must reproduce the HTML without native originals.

Local checks cover backend runtime rejection, actual released dispatch and staging,
initializer ordering/failure containment, original 0.7.2 behavior and offline report
regressions. Native execution and final-revision CI are pending in this implementation
checkpoint; links and exact tested revisions will be recorded after artifact verification.
No inference, judges, model credentials or production promotion are selected.

Adoption still requires live CLI/provider compatibility, judging accuracy and
skill-effectiveness evidence, plus any required new analyst-attachment profile.
Frozen analyst profiles retain their exact historical validator snapshots. Maintain
both backend runtime paths, the fixture-only verifier transformation, sealed staging
and collector/public admission together when an owning runtime changes. Upstream
Harbor, Python and LiteLLM constraints remain the dependency inventory's obligations.

## Next group

The independent scanner group is merged through [PR #120](https://github.com/thetechgy/agent-engineering-baseline/pull/120):
SkillSpector 2.13.4 and Semgrep 1.184.0, with controlled collection/report evidence
and credential-free CI tracked there. Gitleaks 8.30.1 is already current. Bandit and
pip-audit remain evaluator-owned; Semgrep's exact MCP 1.29.0 constraint remains an
unresolved dependency gap. The candidate implementation and pins above are unchanged.
PR #120 also qualifies a narrow retained-adapter correction for caveated scanner
reports: findings survive while repository coverage remains incomplete.
[Compatibility evidence](https://github.com/thetechgy/agent-engineering-baseline/blob/chore/95-scanner-modernization/.github/evals/SCANNER-MODERNIZATION-95.md#retained-adapter-compatibility-correction)
records the before/after scans and reporting controls.

The next action is to run and authenticate the complete native candidate artifact
on this integrated branch.
Other dependencies remain in the existing freshness inventory; this scanner group
does not qualify evaluator adoption, behavioral effectiveness or skill benefit.
