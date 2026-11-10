# Pester assertion evidence

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
