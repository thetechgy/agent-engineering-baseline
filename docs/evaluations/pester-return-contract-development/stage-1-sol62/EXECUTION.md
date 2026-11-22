# Pester return-contract comparison on GPT-6.2 Sol

**Close Stage 1 for this development case and runtime.** Current and matched no
skill each passed 3/3. Every submission passed the reference and detected all
five defects, including `integer-result`. The staged rule closes this comparison
when the current arm passes all three attempts. Keep the current guidance.
[Decision rule](../DECISION-RULE.md).

## Execution and closure

The single approved run used `pester-return-development-current-v1-sol62` at
`15c4e5c6cdfb42920c1352baa27609185d05686f`. Codex CLI 0.167.0 ran GPT-6.2 Sol
at High with PowerShell 7.6.9 and Pester 6.2.0. Authentication verified the exact
archive and first dispatch before the matching `skill-benchmark` gate was
approved. Both platform checks and the selected-results gate passed on the
execution SHA.
[Live run](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45076573933)
· [Exact-source CI](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45066247216).

| Evidence | Record |
| --- | --- |
| Preparation | [14773772953](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45066300533/artifacts/14773772953) |
| Fresh inspection | [45072445663](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45072445663) |
| Dispatch authentication | [14775064983](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45076573933/artifacts/14775064983) |
| Live artifact | [14775628245](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45076573933/artifacts/14775628245) |
| Independently reconciled slots | [Verification](verification.json) |
| Byte-preserved public inputs | [Inventory](data/inventory.json) · [Scores and scheduler witness](data/public-report.json) |

All six slots ran serially. Each had a verified native grade, exact submission
handoff, complete token counters, and cleanup. The native projection and live
report reproduced byte for byte. The allocation is closed with six measured
results, zero retries, replacements, or unlaunched slots.

## Outcomes and usage

| Arm | Reference | All five defects | Type misses | Estimated USD |
| --- | --- | --- | --- | --- |
| Current | 3/3 | 3/3 | 0/3 | $0.3365526 |
| Matched no skill | 3/3 | 3/3 | 0/3 | $0.3355651 |

The six complete usage records total **$0.6721177 estimated**. The pinned
estimator prices unclassified input at the 12-hour cache-write rate. Actual
billing and physical HTTP request counts remain unverified. The tie leaves the
effect of the skill and performance on other tasks unmeasured.

## Report maintenance

Adding the result and running local checks took about 6 minutes after the
live evidence audit. The update changed four existing files covering the
decision manifest, evaluation checkpoint, render inputs, and decision tests.
The verified bundle and receipt use the existing renderer.
