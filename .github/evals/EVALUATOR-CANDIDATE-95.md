# Issue #95 evaluator compatibility port

This is an opt-in grading and collector port for SkillEvaluator 0.7.2 at
`f878f99a9cd4a85dd04043feb43e5bd6a777f64b`, with its owning Harbor 0.24.0 lock.
It does not select this runtime for production. Setup, workflows, Codex pins,
current and historical review environments, saved reports and reference
registrations retain their existing identities.

## Evidence contract

`skillevaluator-v0.7.2-evidence.patch` ports the existing bounded sensitive-path
classifier, static wrapper grammar correction, observation-linkage requirement,
native verifier early exit and conservative security attribution. It retains
the newer upstream shared checks and evaluator-owned `tests/skill_evaluator`
payload directory. The generated standalone verifier receives the same helper
bytes as the host implementation.

Missing, unsupported or ambiguous execution evidence produces a failed,
unscoreable evaluation before provider judges run. Harbor receives only the
required numeric `overall: 0.0` failure envelope; rich metrics remain unavailable.
Unlinked output stays available to the independent secret scanner, without
being attributed to an inner execution. Unknown paired evidence cannot produce
a claim of improved safety. Unknown finding counts remain null, and collector
case summaries retain upstream publication bounds.

The collector also preserves Pester's nonnumeric `outcome.classification` from
its sidecar. Only six fixed classifications survive this exception: passed,
failed, invalid, timeout, unsupported and infrastructure_error. Extra fields and
unknown values are discarded. This diagnosis creates no custom metric and does
not change failed-attempt admission. Existing redaction and metric-name filters
remain active. Validated custom metrics named `outcome` retain their existing
evidence and take precedence over the diagnosis-only exception.

These checks classify submitted command text and evidence linkage. They do not
attest successful execution, authorization or a complete native operation
inventory. The existing classifier's 64 KiB bound and conservative unsupported
syntax behavior remain in place.

## Reproduction

Use a separate clean checkout and the pinned uv 0.13.7. Keep the checkout and
retained evidence under persistent workspaces; disposable tests honor `TMPDIR`.

```bash
candidate_source="$HOME/worktrees/skillevaluator-0.7.2-qualification"
git clone https://github.com/NVIDIA/SkillEvaluator.git "$candidate_source"
git -C "$candidate_source" checkout --detach f878f99a9cd4a85dd04043feb43e5bd6a777f64b
uv sync --project "$candidate_source" --python 3.13 --frozen --no-dev --extra tier3
uv pip check --python "$candidate_source/.venv/bin/python"
"$candidate_source/.venv/bin/python" .github/scripts/qualify_evaluator_candidate.py \
  --source "$candidate_source" \
  --output "$HOME/worktrees/evaluator-95-evidence"
```

The command requires the exact source revision, unchanged source and lock, and
the selected locked package versions. It extracts a bounded regular-file source
snapshot, applies the candidate patch there, and records source, patch, lock,
control and harness identities. It leaves the supplied checkout unchanged.
Output must be a new directory outside both checkouts. Add `--unpatched` with a
different output directory for failing-before evidence; a nonzero result is
expected. No dependency installation or network fallback occurs in the harness.

Controls run in a fixed isolated child with an empty home, no inherited provider
credentials and a Python network audit guard. Judges are mocked to raise if
reached on unresolved evidence. Fixed local verifier subprocesses are exercised;
the audit guard is not an operating-system network sandbox. This command is
opt-in and is not part of production setup or automatic candidate adoption.

## Qualification results

The patched candidate passes 16 controls: the ten existing grading cases, the
native Pester runner/collector/report case and five additional controls for
bounded diagnoses, unlinked observations, independent secret evidence,
standalone verifier imports and bounded unknown-attribution summaries. The
retained production runtime passes all 11 shared controls. Candidate dependency
consistency checks pass for 120 installed packages. No provider inference or
local Docker installation was used.

The upstream differential selection has 1,137 cases. Pristine source passes
1,132 with five skips. The port passes 1,058 with five skips and 74 assertion
failures, all in the following reviewed contract differences:

| Difference | Assertions |
| --- | ---: |
| Unsupported wrappers or bounded commands expect a numeric unsafe verdict rather than unknown | 66 |
| Generic `exec` without wrapper input expects unchanged admission rather than conservative rejection | 2 |
| Unscoped output expects attribution to the first call rather than separate diagnostic evidence | 6 |

These remain failed upstream assertions; the upstream tests were not rewritten.
After the custom-metric collision correction, a focused rerun passes 149 upstream
metric and collector-truth cases, with 134 deselected.
The project controls assert the intended replacement behavior. The selection
covers normalizer, shared ATIF staging, path extraction, secret detection,
metrics, collector failure handling, report truth and verifier redaction. It is
not a full upstream test suite or container/runtime qualification.

## Remaining adoption gates

Current production bundle preparation still reproduces the staging barriers:

| Suite / arm | Candidate staging |
| --- | --- |
| gh with skill | One task staged |
| gh without skill | Rejects an authored environment healthcheck in a paired baseline |
| Pester, either arm, before shared packaging | Rejects a dedicated verifier image that does not receive the grader payload |

The next changes need an operator-owned gh initializer after secure container
start and before agent setup in both arms, while Pester uses the shared packaging
described below. Restoring image entrypoints, bypassing the healthcheck rejection or
removing verifier separation would not qualify those boundaries.

Before adoption, also qualify actual Harbor lifecycle and cleanup, explicit
Codex dispatch pinning, CLI/preflight, schema and evidence consumers, redaction,
scoring and new policy identities. This port neither qualifies newer Codex
native evidence nor requires all of draft PR #109. Harbor 0.25.0 and SDK 3.x
remain separate owning-lock compatibility decisions. Historical results are
not replayed or relabeled as evidence for this candidate.

## Shared Pester verifier qualification

The Pester package now owns its `test.sh`, nested `verifier/grader.py`, runner,
case data and minimal `entry.json`. Explicit Dockerfile copies include them in
the separate verifier image. Neither runtime selects a top-level custom grader
or generates a verifier runner for this package. The unprivileged agent and
root-owned, network-disabled verifier retain their existing limits.

The grader writes numeric-only `reward.json` and `reward.txt`, a rich
`custom_reward.json`, and the existing evaluation-status sidecar. `details.outcome`
carries classifications, mutation counts and verified runtime versions. The
pre-armed infrastructure-failure sidecar remains authoritative until the final
atomic status write. Interruption cannot convert missing measurements into zero.

`pester-pilot-v3` identifies this prospective layout and carrier. Staged target
skill contents bind the arm, and the native task checksum binds each trial to
that capture. An optional arm flag must agree. Missing or transplanted checksums,
metadata, grader, fixtures or skill contents reject evidence. Older profiles,
registry entries, hashes and fixture archives retain their original contracts.
`current-v4` freezes the new validator modules and registry; `current-v3` retains
its original current-review runtime, while older profiles retain legacy routing.

Add `--native-pester` to the qualification command to first run all 16 evidence
controls, then the shared 26-fixture matrix in both arms through the candidate's
actual Harbor lifecycle. The required 52 outcomes are 22 passed, 14 failed,
eight invalid, two timeout, two unsupported and four infrastructure errors.
Every classification, applicable metric and measured runtime must match.
The candidate retains native collection and HTML diagnostics only. It cannot
create a production custom capture, public benchmark or history record.

The separate `Candidate Pester packaging` workflow uses the pinned owning lock,
uv, actions and verified Compose with read-only permissions and no credentials.
Its artifact contains bounded sanitized diagnostics and control metadata, without
source snapshots, protected fixtures or raw verifier logs. Production qualification
also exercises shared reporting and public-only replay after native originals
are hidden. Missing Docker is a failed prerequisite; no workstation service or
container runtime is installed by the qualification tooling.

Local controls reproduce the original staging rejection and stage all five
cases in both arms under the candidate. The 16 evidence controls pass. Native
container qualification is owned by the hosted jobs; staging alone does not
establish the 52 terminal outcomes, cleanup or upgrade readiness. Trusted gh
initialization and overall evaluator adoption remain separate gates.
