# Native transfer grader v2

The [historical diagnostic](../diagnostics/README.md) established the matching
return value at the native PowerShell boundary and verified both controls. All
12 retained submissions rejected the permitted Int128 return type. The
transfer decision still defers the skill revision.

The v2 task member set composes the existing transfer verifier and same pinned
admission runner. It adds the exact Int128 fixture from the diagnostic as a
second valid reference. A primary pass requires accepting both references
and detecting the five original mutants. Mutation detection still divides by
five, and mutant credit requires a passing reference gate.

## Native qualification

PowerShell 7.6.9 and Pester 6.2.0 ran via the staged native test.sh entry point.
The verifier emitted the usual native reward, rich reward and completion
sidecar. It recorded the submitted bytes' SHA-256 and length before admission.
The rootless Podman launcher retained the verifier's network, seccomp,
resource, socket and worker UID constraints. The v2 verifier recognizes the
container marker from either Docker or Podman.

The contract-correct static-template control accepts both references and
detects all five mutants. It exercises the frozen admission policy. The
historical permissive diagnostic control uses method calls outside that policy.
The exact restrictive diagnostic control passes the original reference and
fails the Int128 reference with an assertion. The missing-reference control
produces an unmeasured result with no custom metrics.

All 12 saved submissions passed the original reference and failed the Int128
reference under v2. The [native qualification receipt](../../../../docs/evaluations/pester-transfer-decision/diagnostics/quantity-int128-native-v2.json)
records 0 passed, 12 failed and 0 unmeasured for the saved population. Those
are separate retrospective grades. The frozen decision retains its original
scores and the comparison establishes no new skill benefit.

## Reproduce

Use the pinned reporting interpreter, an existing frozen-grader installation
and an existing local Linux image with the runtime dependencies. The receipt
records the resolved image ID and runtime hashes. Use a fresh output path
outside the checkout.

```bash
"$SKILL_NEXT_PYTHON" -B .github/evals/pester-return-contract/grader-v2/native.py \
  --runtime "$frozen_runtime" --image "$local_image" --output "$new_receipt"
```

The [consolidated report](../../REPORT-EVIDENCE.md#review-the-retained-codex-decisions)
uses the qualification receipt beside the historical replay. Its evaluator
status depends on the measured control outcomes, exact fixture bindings and
complete regrade population.
