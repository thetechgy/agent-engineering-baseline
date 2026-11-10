# Pester assertion evidence

## Native qualification completed for review

[Run 42758383979](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42758383979)
at `2762e16d1f819e825dd958d5e98791c7799ca946` executed both immutable snapshots
on both cases: development v1 and transfer v3. Both case jobs and fresh-runner
consumption jobs passed. [The native receipt](native-qualification.json) retains
source digests, outcomes, scheduling stops, report hashes and the compact-suite
reproduction. The earlier local receipt is historical; it is not relabeled as
execution of the new transfer versions. The local-only status in the frozen
PLAN describes the preparation state at that freeze; this section records the
subsequent hosted qualification.

| Artifact | Verified archive digest |
| --- | --- |
| [pester-return-transfer-1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42758383979/artifacts/13739915015) | `sha256:9b20d1f68e983475916484a4306a0702011cfa2c66136e43aeec6d43fa3df558` |
| [pester-return-consumption-transfer-1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42758383979/artifacts/13739766562) | `sha256:d0059e1c6c90635b2f7fdc776c43fbc9c0293de1fbafefc3670d03f815f85957` |
| [pester-return-development-1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42758383979/artifacts/13739587028) | `sha256:98e1b876d82b072377d822fa726b509256f8e2e04abf8500ecb16693074644b0` |
| [pester-return-consumption-development-1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42758383979/artifacts/13739009325) | `sha256:d1818396931ab3d4b68d400a0ef155901840a3a52558be4ffd6e2cc524945405` |

The independent data-only audit authenticated repository, workflow, run attempt
and source; checked archive SHA-256 before bounded extraction using the existing
extractor; and recomputed all **46 machine-readable analyses and HTML reports**
from downloaded public inputs. HTML reproduced byte for byte, including the
control aggregates and all four paired scheduling aggregates. Fresh runners
independently consumed both pairs per case and reproduced their reports.

APM/native member hashes match all three intended skill files, including both
references. Every absent condition removes only the target skill. Task inputs,
private grading material, runtime/model settings and containment match within
each pair and across current/candidate sources. Distinct source manifests,
profile/record identities, native environments and submission hashes survive
staging, CLI execution, collection and report admission.

The 56 known-control attempts produced **24 passed, 24 measured failed and
8 invalid/unmeasured** outcomes as declared. This includes both strong styles,
the compact transfer suite, value-only, overrestricted and invalid controls.
The compact suite passes the reference and detects all five defects in one
executed test. The overrestricted suite fails the legitimate reference; it
earns no defect credit. Invalid evidence retains unavailable metrics.

Four paired preparations executed 52 additional real-CLI fixture launches: a
six-slot complete schedule and seven one-launch stop scenarios for each pair.
Valid task failures continue as measured failures. Interruption, missing
evidence, unsupported runtime/grading, invalid execution, threshold and unknown
usage preserve their declared stops with five unlaunched slots. Negative
evidence/runtime and usage observations are declared adapter/host injections
after real CLI execution, not induced provider failures. The run totals
**108 native fixture trials: 40 oracle and 68 non-forwarding real-CLI launches**.
All ledgers, resource checks, checkout integrity and task-owned Compose cleanup
passed. No model request was forwarded.

Representative report sections retain current/candidate source manifests and
variant mappings, diagnostic/control labels, per-defect results, reference
failures, unavailable invalid metrics and original-evidence links. Reports
explicitly exclude these fixtures from model-backed skill-effectiveness and
production history. The four prospective paired comparisons remain distinct,
including duplicated absent baselines; no indirect effectiveness estimate was
computed from synthetic controls or historical attempts.

## Corrections and reused evidence

The original [required job](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42750891531/job/129613984160)
failed MD041 on the transfer README and MD012 on the operator guide. The missing
artifact followed the skipped validation step. The fixes add a heading and
remove one blank line. Changed transfer bytes received v2 definitions/profiles,
with the original freeze and profile digests retained under `history/`.

The native attempt at `3cb7677` passed both cases' control phases but
failed preparation: Compose setup wrote GITHUB_ENV in the same step that used
it. The existing strict plugin guard rejected the stale configuration. Separate
acquire/prepare steps fix that handoff; the regression fails before and passes
after. Earlier partial/failed artifacts remain diagnostic receipts only.

A pinned executable control then exposed a transfer admission defect: the
five-test minimum rejected a contract-complete one-test loop despite reference
correctness and all five defect detections. Transfer v3 uses the existing
nonempty minimum of one and adds that positive control. It changes no public
contract, defect criterion, primary quality formula, candidate guidance or
24-attempt design. The receipt retains failing-before/passing-after outcomes;
prior profile values and grades remain intact. No model output informed this
correction.

The existing scheduler, native runner, runtime/APM adapter, non-forwarding
provider fixture, independent graders and consolidated reporter are reused at
unchanged pins. All four new source/case combinations, controls, scheduling
scenarios and fresh consumption execute afresh in the successful run above.
Historical Boolean/gh receipts establish their own components only. Pester
source/test/example evidence below is reused because candidate
and supporting bytes are unchanged. The required Validate checks, owning-runtime
current evaluator qualification, reusable campaign and Codex compatibility
workflows also passed on `2762e16d1f819e825dd958d5e98791c7799ca946`.
Final documentation descendants retain this actual receipt revision; required checks must pass on the final PR head.

No model credentials, inference, judges, protected live gates, paid allocations,
default deployment or dependency changes occurred. Pester 6.0.0 remains
source-reviewed only. Earlier incomplete static validation and baseline local
worker/synthetic-fixture failures remain recorded below; hosted success does
not rewrite those results. Native controls validate integration and grading,
not agent compliance or skill improvement. The 24 model attempts remain a
future proposal requiring separate authorization and exact-source preparation.

## Released assertion behavior and earlier local checks

Primary authority is tagged implementation and tests in pester/Pester, never the
default branch. Pester 6.2.0 resolves to
`98e56d65da1642a7158992b50ded240c42a3ac18`; minimum release 6.0.0 resolves to
`de3bc3dcef6a75c9cbb7667118e8b90ae7b04378`.

| Claim used by candidate | Released source | Supporting checks |
| --- | --- | --- |
| Equality can accept a different actual type | [6.2.0 Should-Be, lines 49-54](https://github.com/pester/Pester/blob/6.2.0/src/functions/assert/General/Should-Be.ps1#L49): expected is the left operand of `-ne` | [tagged Should-Be tests](https://github.com/pester/Pester/blob/6.2.0/tst/functions/assert/General/Should-Be.Tests.ps1); executable `Advice.Tests.ps1` accepts integer 0/1 against expected Boolean values |
| Check Boolean type on the unconverted actual, then its value | [6.2.0 Should-HaveType, lines 60-83](https://github.com/pester/Pester/blob/6.2.0/src/functions/assert/General/Should-HaveType.ps1#L60): untyped actual and .NET `-isnot` | [tagged HaveType tests](https://github.com/pester/Pester/blob/6.2.0/tst/functions/assert/General/Should-HaveType.Tests.ps1), advice controls and literal-example reproduction |
| Type checks accept assignable types, not exact implementation identity | [6.2.0 HaveType lines 64-78](https://github.com/pester/Pester/blob/6.2.0/src/functions/assert/General/Should-HaveType.ps1#L64) | Advice control accepts a hashtable as IDictionary; numeric value-only controls accept Int32, Int64 and Decimal |
| `-Actual` preserves the value supplied rather than piping/unrolling it | [6.2.0 New-ShouldAssertion](https://github.com/pester/Pester/blob/6.2.0/src/functions/assert/Common/New-ShouldAssertion.ps1) and [HaveType tests](https://github.com/pester/Pester/blob/6.2.0/tst/functions/assert/General/Should-HaveType.Tests.ps1) | Advice rejects a singleton Boolean array as scalar Boolean; literal example uses `-Actual` for both checks |
| Candidate patterns are compatible with the 6.0.0 floor by source review | [6.0.0 Should-HaveType lines 39-57](https://github.com/pester/Pester/blob/6.0.0/src/functions/assert/General/Should-HaveType.ps1#L39), [Should-Be lines 39-53](https://github.com/pester/Pester/blob/6.0.0/src/functions/assert/General/Should-Be.ps1#L39), [Collect-Input](https://github.com/pester/Pester/blob/6.0.0/src/functions/assert/Common/Collect-Input.ps1) | Source uses typed expected Type, untyped actual, assignability test and expected-first equality; direct Actual avoids pipeline reshaping |

Paths above are version-specific. Use .NET `[Type]` expressions as shown; the
6.2 custom PSTypeName fallback is not needed or added to the candidate. No floor
upgrade is implied. 6.0.0 runtime and Windows PowerShell 5.1 were not executed;
compatibility is source-reviewed, not runtime-qualified on those environments.

Current skill's Boolean-identity advice refers to new `Should-BeTrue` and
`Should-BeFalse`, whose [6.2.0 implementation](https://github.com/pester/Pester/blob/6.2.0/src/functions/assert/Boolean/Should-BeTrue.ps1#L65)
explicitly checks Boolean type. Do not confuse those with classic spaced
`Should -BeTrue` / `Should -BeFalse`: the [tagged classic implementation](https://github.com/pester/Pester/blob/6.2.0/src/functions/assertions/BeTrueOrFalse.ps1)
tests truthiness. The candidate avoids that naming ambiguity by checking type
explicitly before generic equality in data-driven tests.

[Official v6 documentation](https://pester.dev/docs/assertions/should-command)
supports expected-type coercion, the new/classic distinction, and direct Actual
input. No contradiction was found for the new assertion claims used here.
Implementation and executable results take precedence over names or recollection.

Executed environment: PowerShell 7.6.9 and Pester 6.2.0, matching the existing
pinned task environment. The package/version pins are unchanged in
`powershell-pester-6/support/install-runtime.py`. Four tagged test files
(Should-Be, Should-HaveType, Should-BeTrue, Should-BeFalse) passed **51 tests**
using that installed release and the tagged `tst/Pester.BeforeContainer.ps1`.
`Advice.Tests.ps1` passed **15 checks**, including correct Booleans, wrong types,
wrong values, singleton shape, conversion masking, numeric type variation and
assignability. `verify_example.py` executes the literal candidate example with
correct, wrong-type, wrong-value, empty-boundary and nonempty-boundary controls.
See [validation.json](validation.json) for retained outcomes.

The transfer controls run through the existing `local_semantic_fixture` helper,
production prospective Runner bytes and `grader.assess`. Their classification,
reference and defect expectations are verified, without changing either grader.
These local checks do not qualify Docker isolation, native provider/CLI transport,
new-source report reproduction or agent instruction following. The planned
experiment remains unexecuted.

Reproduce without credentials using the retained pinned evaluator Python:

```sh
PESTER_EFFECTIVENESS_LOCAL_SEMANTICS=1 "$SKILL_CURRENT_PYTHON" -B -m unittest discover \
  -s .github/tests -p test_pester_return_contract.py -v
python3 -B .github/evals/pester-return-contract/verify_example.py "$EVIDENCE/literal-example.json"
```

For the advice file, import Pester 6.2.0 in PowerShell 7.6.9 and invoke it with
Run.PassThru; require Result Passed and PassedCount 15. For tagged tests, use
Run.RepoRoot at the retained tag's `tst` directory and the four paths above.
Keep all output outside the checkout. No inference or judge is involved.

Static skill validation was run with `--tiers 1 --no-llm --no-dedup` on both
snapshots. Both exit 1: the unchanged metadata lacks `metadata.author` and the
local environment has no SkillSpector installation. Version, PII, license,
code-integrity, Unicode, quality and lint checks pass. This is baseline-reproduced,
incomplete static validation, not a passing security scan. No dependency or
unrelated metadata change is included.

Affected campaign (16), protocol (13), retained replay (4) and effectiveness (9,
two optional skips) contract checks pass after registration. Pester contracts
execute 25 tests with one failure: PowerShell worker startup exits 137, reproduced
on unchanged main under the same limits. The broader suite was also invoked with
the retained candidate evaluator and is not a clean pass. A missing synthetic
custom-metric observation (`StopIteration`) independently reproduces on unchanged
main. Other broader failures have not all been isolated. Hosted checks and their
owning runtime remain separate; no broad local green verdict is claimed.
