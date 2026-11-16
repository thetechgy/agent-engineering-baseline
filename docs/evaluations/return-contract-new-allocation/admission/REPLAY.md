# Transfer admission retrospective qualification

The exact retained current-arm submission is **passed** under the versioned correction: reference result `1`,
5/5 seeded defects detected and 5 reference tests executed. The original unsupported/expression_policy result
remains permanently unmeasured. This is a retrospective evaluation after output inspection, not another
experiment or an outcome in the closed allocation.

[Implementation PR #131](https://github.com/thetechgy/agent-engineering-baseline/pull/131) at
[`22b36d5`](https://github.com/thetechgy/agent-engineering-baseline/commit/22b36d53e9ac7e329ef8c56dc9bdcefb468ca9df)
supplies the [diagnosis, policy and semantic
references](https://github.com/thetechgy/agent-engineering-baseline/blob/22b36d53e9ac7e329ef8c56dc9bdcefb468ca9df/.github/evals/pester-admission-v1/EVIDENCE.md).
Count at submission line 14 is the first rejecting rule; numeric type expressions on lines 27-32 are subsequent
admission failures. The opt-in policy admits bounded collection-size reads and literal numeric -is/-isnot
predicates. Recursive inspection, protected content, method/reflection restrictions and external isolation
remain intact.

## Authenticated evidence

Submission: 1,536 bytes, SHA-256 `c985298ef4fbe7a02ca8d1645fc0a07a3ed478084aafbf0489e6537748ffc0bf`. Original
artifact `13806864132` has SHA-256 `2e314b9efc6acac1a393c6f87faa665506e4e1678296e6c34c1ebe79c1a7be86`. Its exact
archive member, original report and provenance remain in the retained corpus. Diagnostic fixtures never replace
these bytes.

[Native run 42923193199](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42923193199),
attempt 1, used source `22b36d53e9ac7e329ef8c56dc9bdcefb468ca9df`. [Artifact
13814684492](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42923193199/artifacts/13814684492)
has digest `sha256:d0db6ac9b1204d0b0664d3cfcbb11e960d5187d27a23bb1b56089cdef46f2e52`. Producer repository,
source, workflow, attempt and archive digest were authenticated before bounded data-only extraction. Native
execution used the existing isolated verifier; the audit executed no artifact-authored code. Exact verifier
handoff hashes, protected task members, original corpus files and cleanup receipts were independently checked.
All three new native/public records and their HTML reports reproduced byte-for-byte.

Credential-free controls retained 6 passed, 8 measured failed, 26 unsupported and 4 invalid outcomes across 44
oracle trials. Unavailable work has no quality values. Both original-reproduction fixtures returned exactly
unsupported/expression_policy. Only one current arm was retrospectively replayed. Oracle fixtures are not
additional model outcomes.

Only admission and its successor execution document differ from the original protected task members. Reference,
mutants, scoring, skill/candidate, settings, timeout and dependency pins are unchanged. The [machine
receipt](qualification.json) retains original and corrected evaluator identities/digests, every control outcome,
per-mutant findings, required checks and report hashes.

| Seeded defect | Detected | Basis |
| --- | --- | --- |
| enabled-integer | 1 | assertion |
| enabled-zero | 1 | assertion |
| quantity-above | 1 | assertion |
| quantity-below | 1 | assertion |
| quantity-offset | 1 | assertion |

## Runtime and report qualification

Both required checks passed at the implementation head. Frozen-grader CI selects its declared, hash-verified
PowerShell 7.6.9/Pester 6.2.0 through existing setup. Ordinary Linux/Windows validation retains latest stable
PowerShell. The strict grader requirement is unchanged. Its five hosted exploratory controls retain positive,
weak, incorrect and invalid distinctions, and the checkout stays clean. Full Validate, including CI contracts
and native feasibility, passed; broader workflow disposition is recorded on PR #131. Cancelled/interrupted
observations remain inconclusive.

Local focused contracts and real pinned-runtime acquisition/control execution passed. The 111 historical
metric/analysis/report regressions passed in their verified owning runtime. Earlier wrong-runtime,
control-registration, relocated-manifest and bytecode-output failures remain in the diagnostic history; no
unchanged deterministic failure was repeatedly rerun.

The original four-record execution report is unchanged and reproduces SHA-256
`af83335d938115ab287abb54d65da41cb9fad015e386255743b77bb10fbf35b2`. The [five-record consolidated
HTML](consolidated/report.html) adds the retrospective record through the existing renderer; SHA-256
`a694626c12edaf9cd908d9a6a88e4c9499e9bd77afbb5c20b6d95f6532ee89c0`. Its [analysis](analysis/analysis.json) uses
the four unchanged inputs under `../execution/data/` plus the [new public input](data/). Historical grades are
reused, not recomputed or pooled. GitHub displays HTML as source; open it from a checkout or download.

Reproduce using qualified tooling source `22b36d53e9ac7e329ef8c56dc9bdcefb468ca9df` and its owning evaluator
Python. This documentation branch deliberately does not include #131 implementation code. Set QUALIFIED_SOURCE,
PUBLICATION_SOURCE and REPORT_OUTPUT to separate checkouts/output paths. Run the existing skill_report.py CLI
with five --input arguments (the four directories in execution/data and admission/data), --analysis pointing to
admission/analysis/analysis.json, and --output pointing outside both checkouts. Compare report.html with
admission/consolidated/report.html.

Existing same-source containment evidence was also downloaded, authenticated and
reproduced: 52 controls retained 22 passed, 14 measured failed, eight invalid,
four infrastructure errors, two timeouts and two unsupported outcomes. All
unavailable observations have null quality values. Five native deadline controls
preserved timeout/cancellation distinctions and complete cleanup; the production
600-second agent deadline is unchanged. Their archive bindings and findings are
included in the machine receipt. No additional matrix was dispatched for reuse.

The existing public envelope retains `coverage_missing` and `execution_incomplete`:
this replay deliberately enrolls one current arm and no absent arm, and the
custom-only collector remains diagnostic. The one enrolled current trial has a
complete passing reference and five mutant results. This envelope is not relabeled
as a complete paired population, and no absent-arm or strict cross-run comparison
is inferred. Original public availability flags and bytes remain unchanged.

## Separate broader qualification limit

The legacy Codex compatibility preparation job failed after both non-forwarding
CLI probe sessions: `Post-agent CLI child network observation unavailable`.
Its surrogate rewards have no trial ID, and the unchanged identity guard rejects
them. Artifact `13813573476` was authenticated as SHA-256
`225993dc9f6b1d98198dc52c80588495553729674f7e3a69d16211954ce20348`.
The environment component and reward-identity guard match main byte-for-byte.
This is an unavailable containment observation, not a measured task failure.
A fresh native baseline reproduction was not run, so no cause is inferred.
The guard was not weakened and the deterministic failure was not rerun unchanged.
This does not replace the separately qualified isolated Pester replay. It leaves
broader live-CLI/preparation readiness unestablished; CI is not all green.
Other automatically triggered broader preparations still running at this receipt
are pending, not successful qualification. No live capability is authorized.

## Limits and next action

This follows inspection of one current-arm output. It establishes neither transfer benefit nor candidate
regression safety or adoption readiness. Transfer/candidate never ran. Development outcomes, seven paid
launches, eleven unlaunched positions and closed authorization remain unchanged. Estimated new paid usage
remains $0.3485231; historical spending is unknown. No model credentials, inference, judge, allocation
reopening, replacement, live gate, skill change, adoption, dependency upgrade, production-default change or
merge occurred.

**One recommended next action:** review PR #131 and its authenticated retrospective evidence. Any future
experiment needs a separate decision; this replay authorizes none.
