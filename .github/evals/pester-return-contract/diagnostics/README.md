# Transfer Quantity variation replay

The [frozen prompt](../transfer/prompt.txt) allows different concrete numeric
types for the clamped Quantity. In the native probe, System.Int128 implements
the .NET numeric interface. The changed fixture returns that type for
Requested=3 and still returns the value 3. The probe calls Get-BatchSummary at
the suite's input path for all five required requests. It checks the object
shape, Boolean, numeric value and actual runtime type against both fixtures.

Both controls must pass the frozen reference. The permissive control must
accept the variation and the restrictive control must reject it by assertion.
Every eligible suite runs unchanged against both fixtures. The accepted and
rejected counts require a passing reference, complete execution and matching
test counts. A rejection additionally requires assertion-only failures.

On PowerShell 7.6.9 with Pester 6.2.0, the qualified replay measured **0
accepted, 12 rejected, 0 unmeasured**. All 12 passed five reference tests and
each recorded one assertion failure with the type variation. The initial
container UID mapping prevented the controls from reading staged inputs. The
qualified execution used rootless keep-ID mapping. The
[diagnostic receipt](../../../../docs/evaluations/pester-transfer-decision/diagnostics/quantity-int128.json)
records the qualified controls, each suite digest, each native result and the
return boundary evidence. Frozen grades and the transfer decision have their
original receipts.

## Reproduce

Use an existing verified installation from the repository's frozen-grader
runtime installer and a reviewed local Linux image with the runtime
dependencies. Set the output to a new path in a persistent evidence directory.
The replay records the chosen image ID. Each invocation uses rootless Podman
with networking disabled and read-only runtime and task mounts.

```bash
python3 -B .github/evals/pester-return-contract/diagnostics/replay_quantity.py \
  --runtime "$frozen_runtime" --image "$local_image" --output "$new_receipt"
```

Use `--replay "$new_receipt"` with the
[consolidated report command](../../REPORT-EVIDENCE.md#review-the-retained-codex-decisions)
to review the new measurements. The replay uses no inference.
