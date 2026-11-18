# Pester clarification transfer decision

**DEFER** the exact 22-line `powershell-pester-6` clarification. Both transfer
pairs tied at 3/3 primary successes per arm. All 12 submissions imposed the same
fixed list of numeric types on `Quantity`. The reference exercises Int32 and
Int64, both on the list. The public contract permits other numeric types, so
this tie leaves the numeric-variation criterion unmet. The shared restriction
provides no evidence of a candidate-specific regression.

## Execution and closure

The two authorized runs used revision `2b58a4652b576247d91ba01c6ce7a743ff703331` on
`prep/pester-final-transfer`. The [frozen decision table](../../../../.github/evals/pester-transfer-decision/DECISION.md)
has SHA-256 `b5fc9d7fc68129374aa485129561c7d096693e4333d732dbab77abdef535e392`.
Both [required and selected execution checks](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/44187105820)
passed at that revision. This receipt is published in a later report-only commit.

| Pair | Live run | Preparation and fresh inspection | Retained live evidence |
| --- | --- | --- | --- |
| Current | [44202925702/A1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/44202925702) | [14378272338](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/44187111680/artifacts/14378272338) and [44194708571/A1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/44194708571) | [14382333232](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/44202925702/artifacts/14382333232) |
| Candidate | [44205331725/A1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/44205331725) | [14378270615](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/44187112158/artifacts/14378270615) and [44193046605/A1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/44193046605) | [14384421602](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/44205331725/artifacts/14384421602) |

Each authentication archive matched its registered preparation, digest, source
and first dispatch. Each matching `skill-benchmark` approval was verified.
Both protected jobs consumed the frozen preparation before credential delivery.
The [current checkpoint](current-checkpoint.json) verified all six current-pair
measurements and $0.3389116 in estimated usage before candidate dispatch.
The [current dispatch](current/dispatch.json) and [candidate dispatch](candidate/dispatch.json)
record approval, protocol, grader, fixtures, preparation and inspection identities.
Both [allocations are closed](allocation-closure.json). Twelve attempts launched
serially, with zero unlaunched slots, replacements, retries or model judges.

## Frozen outcomes

| Arm | Completed / measured | Reference | enabled-integer | enabled-zero | quantity-offset | quantity-below | quantity-above | Primary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Current | 3 / 3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| Current's absent | 3 / 3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| Candidate | 3 / 3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| Candidate's absent | 3 / 3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |

Primary success requires reference correctness and detection of all five defects.
Both present-minus-absent differences are zero percentage points. The absent
baselines are separate and agree on the measured endpoints. The present-arm
comparison is indirect and output-informed. Three repetitions per arm provide
no estimate of statistical non-inferiority or broader effectiveness.

All three candidate suites checked the unconverted Boolean using
`Should-HaveType` before comparing its value. Each also required `Quantity` to
pass an OR of 12 concrete type tests before comparing its value. The current
and both absent arms used the same set of numeric types. A correct value
returned as `System.Int128` or `System.Half` would fail that predicate. This is
source inspection of the verified submissions. The frozen reference executed
Int32 and Int64 variation, and the existing grades stand.
[Candidate slot 1](candidate/submissions/slot-1/Subject.Tests.ps1#L20),
[slot 4](candidate/submissions/slot-4/Subject.Tests.ps1#L20),
[slot 5](candidate/submissions/slot-5/Subject.Tests.ps1#L20),
[.NET 10 Int128](https://learn.microsoft.com/en-us/dotnet/api/system.int128?view=net-10.0),
[.NET 10 Half](https://learn.microsoft.com/en-us/dotnet/api/system.half?view=net-10.0).

The [frozen admission policy](../../../../.github/scripts/pester_admission.py)
lists those concrete types for permitted `-is` and `-isnot` predicates. That
list describes the admitted test syntax. The
[task prompt](../../../../.github/evals/pester-return-contract/transfer/prompt.txt)
leaves the implementation type open. The shared pattern leaves broader numeric
variation unverified under the decision criteria. The existing development
result (candidate 3/3 versus its own absent 0/3) and released Pester source
justification still support the narrow advice. Historical and retrospective
results retain their original cohorts and grades.
[Development evidence](../../../../.github/evals/pester-return-contract/EVIDENCE.md),
[prior transfer receipt](https://github.com/thetechgy/agent-engineering-baseline/blob/5ce0454cb79f56a8880405be228ac4320be3f94f/docs/evaluations/pester-transfer-decision/execution/EXECUTION.md).

## Accounting, cleanup and reproduction

| Arm | Input tokens | Cached input | Output | Estimated USD | Sum of launch times |
| --- | --- | --- | --- | --- | --- |
| Current | 284,948 | 230,088 | 5,618 | $0.1889088 | 426.174 s |
| Current's absent | 219,509 | 175,408 | 4,426 | $0.1500028 | 345.543 s |
| Candidate | 265,616 | 211,337 | 5,536 | $0.1850517 | 409.551 s |
| Candidate's absent | 231,651 | 187,710 | 4,689 | $0.1535430 | 349.353 s |

The [usage receipt](usage.json) reconciles 12 complete CLI turn records with
native and ledger counters. Frozen estimated usage totaled **$0.6775063**
($0.3389116 current pair, $0.3385947 candidate pair). Both stayed below the
$5 estimated-usage scheduling threshold. Each $8 planning allocation included
a $3 reserve. The original $6 estimate and $16 envelope were planning figures.
Actual billing, physical HTTP request totals, cache-write accounting and CI costs
are outside these estimates. Long-context billing is per request, while the
frozen estimator sees cumulative turn counts.

Both present arms used more estimated tokens and launch time than their own
absent arms. Candidate's time and cost difference against its absent arm was
smaller than current's. With three observations per arm, these descriptive
differences provide no demonstrated efficiency effect. All 12 launches
returned to the resource baseline. Runtime, deployment, boundary and disposal
evidence verified, with no operational stop or security drift observed.
Full reads of the skill file were unobserved in the retained access check.
The observed checks in the submissions establish their behavior on the
frozen fixtures. They leave instruction following and causal skill benefit
unestablished. [Current verification](current/verification.json),
[candidate verification](candidate/verification.json).

Both native projections and each live machine and HTML report reproduced
byte for byte. Each public report retains its fixed diagnostic mode and the
generic `execution_incomplete` label from that mode. Both native reports say
`complete`, each arm has three recorded and scored attempts with complete case
details, and every custom outcome is present. The
[consolidated report](consolidated/report.html) and [machine analysis](analysis/analysis.json)
reproduce from the two [byte-preserved public bundles](cohorts.json).

**Next action** — Keep the current `powershell-pester-6` guidance in place.
