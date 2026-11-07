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
relabeled or accepted under v2. The complete native qualification below uses the
corrected v2 patch.

A subsequent review reproduced a separate generated-script false pass in both
verifier paths: redirected sensitive text followed by direct script execution was
mistaken for inert printing. The active producer is now
`skillevaluator-0.8.0-offline-v3`. After redirected sensitive text, unresolved
execution or expansion stays unscoreable; supported literal inspection and
explicit sensitive reads retain their outcomes. The released evaluator, dependency
pins, frozen lock and scoring policy are unchanged. The complete v2 qualification
below remains retained evidence at `0bfb1f5`, with its original patched runtime and
matching repository tooling. V3 requires fresh complete native qualification;
v2 is not relabeled or accepted as v3 execution evidence.
Six generated-script forms failed before the correction. Both actual verifier
paths now pass the focused controls; the complete v3 offline qualification passes
45 tests, 73 scoring vectors and 48 replay outcomes without external network or
inference. The retained production patch controls and all 107 frozen package
compatibility checks pass.

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
Synthetic transport controls remain labeled synthetic and unmeasured. Executed
oracle fixtures retain their distinct purpose and per-control measurements; both
are excluded from production history and skill-benefit claims. Cross-policy
comparisons do not produce improvement deltas.

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

The oracle gh recipe canonically orders allowed-read metadata so its preparation
hash reproduces across filesystem enumeration orders. Production and retained
recipes are unchanged. Prospective outcome checks consume the existing normalized,
hash-bound numeric measurements; raw producer-redacted fields remain unchanged.

The custom-only gh verifier loads the released, staged `atif_helpers` and
`checks` APIs directly. The full verifier template imports judge/HTTP dependencies
that custom-only images intentionally omit; an isolated `-I -S` regression checks
the actual grader without installed packages. The native reporting join selects
behavioral records before rebuilding inventory, including when native evidence
is partial. Failed verifier/oracle output and initialization records are retained
as bounded, sanitized diagnostics; linked diagnostic inputs are rejected.

The existing bounded command observer records gh build/start stages without raw
arguments. Oracle launch stages and sanitized failure diagnostics are retained;
cleanup is checked after success and failure. The final report includes the actual
native results alongside clearly marked synthetic reporting controls. Its included
public evidence and saved analysis must reproduce the HTML without native originals.

### Retained completed v2 native milestone

Credential-free native qualification **passed** on November 7, 2026 at
[`0d4b21d1071d6270ef3b4ae1fcc51512b2760446`](https://github.com/thetechgy/agent-engineering-baseline/commit/0d4b21d1071d6270ef3b4ae1fcc51512b2760446).
The tested CI merge producer is `d281d9bef6a3a769199b838c72350cb13252fe80`,
whose parents are main `668c734f35d3e31038a32b173ce3fa2a19420295` and that feature
revision. [Run 42352202778, attempt 1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42352202778)
passed all eight jobs, including the final same-run artifact join.

- All 48 gh lifecycle cases passed across six fixed shards. The 14 deliberate
  startup-failure controls remained blocked and unscoreable, with unchanged audits;
  cancellation and infrastructure-error classifications were retained. Secure
  initialization, root-owned broker identity, repeated initialization, pinned
  setup-only Codex 0.155.1, private-access denials and receipt-forgery rejection
  were exercised. No Codex inference ran.
- All 48 Harbor gh oracle trials reached the existing consolidated report:
  22 passed, 22 failed, 2 unsupported and 2 unknown; 44 scoreable and 4 unavailable.
  In both arms, wrong-repository work retained task correctness 0, and gh-014
  retained task correctness 1 with authorization 0. Baseline gate failures remain
  separate from task correctness. Unsupported and missing traces have no measured
  values. The gh task container retains its independently pinned Python 3.12 base;
  the evaluator host is Python 3.14.10.
- All 52 native Pester controls reached that report: 22 passed, 14 failed,
  8 invalid, 2 timeout, 2 unsupported and 4 infrastructure errors; 36 scoreable
  and 16 unavailable. Reference execution and seeded-mutant detection, task/arm
  checksums, PowerShell 7.6.9 and Pester 6.2.0 were checked. Aggregate execution
  remains failed where the intentional controls require it.
- Oracle container/network cleanup and all lifecycle shard teardown completed,
  including after negative and failure controls. Standard and judged candidate
  quality fields remain null; raw fallback zeros do not become measurements.

The [final consolidated artifact](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42352202778/artifacts/13567637089)
is `candidate-offline-report-attempt-1`, archive SHA-256
`e808eac6cbe2192be2ea599e9dc303088966e76430a83a77e405e8d7b47cef44`.
Its identity, repository/run/attempt, producer ancestry, backend/harness bytes,
runtime/lock/patch/source-tree identities and bounded extraction were verified.
All 100 native observations were re-normalized locally and matched the public
records exactly. The existing `skill_report.py --input ... --analysis ... --output ...`
CLI reproduced the HTML from public evidence and saved analysis without native
originals. The 3,038,904-byte HTML has SHA-256
`2a9011756d880e9c212f98e315c24aed0a36a26331294711e8fd03c1760c0d2f`.
The overview, gh/Pester classifications, unavailable values and unauthorized
control measurements were visually inspected. Artifact-producer authentication
is supplied by the verified CI identity; the public report retains its own
structural-evidence authentication caveats.

Supporting checks passed: 44 candidate offline controls, 73 scoring vectors,
48 replay outcomes, 105 historical gh/reporting checks completed with one skip,
and the original 20-test backend suite under its owning 0.7.2 runtime. All 107
frozen installed packages pass `uv pip check`. No external network attempts occur
in the offline worker. [All five repository validation jobs passed](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42352202798)
on the tested feature revision. The authenticated
[scanner artifact](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42352202798/artifacts/13566751872)
retains Podman's nine SECURITY findings (three high, six medium), caveats and
incomplete coverage; its repository-caveat HTML also reproduced byte-for-byte.

Earlier failed evidence remains separate. [The v1 run](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42344184772)
retains the custom-only verifier import failure, one initialization failure and
the report inventory defect. [The earlier v2 run](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42348063857)
retains the raw-field assertion failure and noncanonical preparation identity.
The import, inventory, assertion and preparation defects are fixed with regression
coverage. The isolated v1 initialization failure is retained diagnostic evidence;
it was not reproduced in the complete v2 run and is not relabeled as a pass.

This qualifies frozen evaluator compatibility through deterministic native fixtures.
It does not qualify live CLI/provider behavior, judging accuracy, skill activation
by a live agent, skill benefit or adoption. No model credentials, inference, judges,
paid evaluations, skill changes, Pages publication or production promotion ran.

Adoption still requires live CLI/provider compatibility, judging accuracy and
skill-effectiveness evidence, plus any required new analyst-attachment profile.
Frozen analyst profiles retain their exact historical validator snapshots. Maintain
both backend runtime paths, the fixture-only verifier transformation and canonical
preparation recipe, sealed staging and collector/public admission together when an
owning runtime changes. Retain authenticated artifacts and matching source/tooling
snapshots beyond the Actions artifact retention period; never relabel v1 or frozen
analyst profiles under changed validators. Upstream
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

The next action is to complete and authenticate the full v3 native qualification
without relabeling the retained v2 evidence.
Other dependencies remain in the existing freshness inventory; this scanner group
does not qualify evaluator adoption, behavioral effectiveness or skill benefit.
