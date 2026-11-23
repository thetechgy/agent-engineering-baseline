# Pester return-contract recheck on Codex CLI 0.171.0

**Close this case on Codex CLI 0.171.0.** Current and matched no skill each
passed 3/3. Every submission passed the reference and detected all five
defects, including `integer-result`. Keep the current guidance. The two
GPT-6.2 Sol pairs on 0.167.0 and 0.171.0 each tied on this development case.
[Decision rule](https://github.com/thetechgy/agent-engineering-baseline/blob/27cd12f8558ff167154528241e19a6db462f87a4/.github/evals/pester-return-contract/DECISION-RULE-1710.md) ·
[0.167.0 execution](../stage-1-sol62/EXECUTION.md).

## Execution evidence

The single approved run used
`pester-return-development-current-v1-1710-sol62` at
`27cd12f8558ff167154528241e19a6db462f87a4`. Codex CLI 0.171.0 ran GPT-6.2 Sol at High. The owner was
SkillEvaluator 0.8.0 with Harbor 0.24.0. Grading used PowerShell 7.6.9 and
Pester 6.2.0 without model judges. The authentication job verified the first
dispatch and exact preparation archive before the matching `skill-benchmark`
gate was approved. Both platform checks and the selected-results gate passed
on the execution revision.
[Live run](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45106823638) ·
[Exact-source validation](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45101823827).

| Evidence | Record |
| --- | --- |
| Preparation | [14787945474](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45101927023/artifacts/14787945474) |
| Fresh inspection | [45106575166](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45106575166) |
| Dispatch authentication | [14787623142](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45106823638/artifacts/14787623142) |
| Live artifact | [14788082674](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45106823638/artifacts/14788082674) |
| Reconciled slots | [Verification](verification.json) |
| Byte-preserved public inputs | [Inventory](data/inventory.json) · [Scores and live scheduler witness](data/public-report.json) |

All six slots ran serially. The native grades, submitted bytes, CLI usage
counters and cleanup matched the ledger. All current-arm slots recorded
confirmed full skill reads. The native projection and the consolidated report
both reproduced byte for byte. The allocation closed after six measured
attempts, with zero retries or replacements.

## Outcomes and usage

| Arm | Reference | All five defects | Type misses | Estimated USD |
| --- | --- | --- | --- | --- |
| Current | 3/3 | 3/3 | 0/3 | $0.1867982 |
| Matched no skill | 3/3 | 3/3 | 0/3 | $0.2054773 |

The six complete usage records total **$0.3922755
estimated**. The estimator prices cache writes at the 30-minute rate. Actual
billing and physical HTTP request counts remain unverified. This one-case tie
leaves broader skill benefit unmeasured.
