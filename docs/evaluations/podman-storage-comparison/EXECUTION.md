# Podman case 2 on Codex CLI 0.172.0

**Inconclusive. The authorized comparison stopped in slot 2.** Both launched
submissions passed the PostgreSQL persistent mount verifier. The no-skill slot
failed the campaign's post-run evidence check. Four slots stayed unlaunched,
so the six-slot decision rule has no applicable outcome.
[Committed rule](https://github.com/thetechgy/agent-engineering-baseline/blob/d31f7dc1b80810e7e0a8027e684105df3c0c84e7/.github/evals/podman/storage/DECISION-RULE.md) ·
[Live run](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/46029485365).

## Execution evidence

The first and only dispatch of this allocation used
`podman-storage-current-v1-1720-sol62` at
`d31f7dc1b80810e7e0a8027e684105df3c0c84e7`. Codex CLI 0.172.0 ran
GPT-6.2 Sol at High with SkillEvaluator 1.2.1, Harbor 0.25.0 and
Python 3.14.10. The verifier checked the submitted Quadlet without a model
judge. Dispatch authentication, the approved `skill-benchmark` gate and
pre-credential exact-source consumption preceded the live launch. Both
required checks and the aggregate selected-results gate passed on the
execution revision.
[Exact-source validation](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/46021973896).

| Evidence | Record |
| --- | --- |
| Exact-source preparation | [15211257981](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/46021963119/artifacts/15211257981) |
| Fresh inspection | [46025906549](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/46025906549) |
| Dispatch authentication | [15213976483](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/46029485365/artifacts/15213976483) |
| Stopped run artifact | [15213549620](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/46029485365/artifacts/15213549620) |
| Independent reconciliation | [Verification](verification.json) |
| Byte-preserved public inputs | [Inventory](data/inventory.json) · [Verifier grades and live scheduler witness](data/public-report.json) |

The native grade, produced submission digest, full skill read and usage were
verified for slot 1. In slot 2 the native verifier still recorded a pass.
The scheduler stopped with `security_or_identity_drift` from its native
observation step. Offline, the same observation check accepted slot 1 and
rejected slot 2 at the submission receipt check. The produced receipt
describes 187 bytes. The retained copy has 173 bytes and contains a redaction
marker. The artifact does not retain the exact produced bytes for that slot.
Both attempts recorded complete cleanup. The public projection and the
hosted partial report reproduced byte for byte.

## Outcomes and usage

| Arm | Planned | Launched | Verifier passes | Fully admitted slots | Estimated USD |
| --- | ---: | ---: | ---: | ---: | ---: |
| Current | 3 | 1 | 1 | 1 | $0.0740950 |
| Matched no skill | 3 | 1 | 1 | 0 | $0.0620964 |

Both launched slots emitted complete usage. They total **$0.1361914
estimated**, using the Stage 1 pricing method with cache writes priced at
the 30-minute rate. Actual billing and physical HTTP request counts remain
unverified. The allocation closed with no retries or replacements. The
live job took 5 minutes 26 seconds, including 4 minutes 20 seconds in the
execution step. About 1 hour 47 minutes elapsed from opening the draft PR to
the live stop. Preparation through the gate used one draft PR, three pushes,
five credential-free dispatches and three PR Validate runs. Two superseded
Validate runs were cancelled.
[Stage 1 usage method](../pester-return-contract-development/stage-1-1710-sol62/EXECUTION.md).

The protocol covers one case with three planned attempts per arm. The cases
were written alongside the skill. Two earlier GPT-5.6 Sol benchmarks on
Codex CLI 0.155.1 found that both arms corrected the case 2 mount. The check
covers the generated PostgreSQL 18 configuration. Database startup and
persistence across restarts are outside its scope.
[Earlier case 2 review](https://github.com/thetechgy/agent-engineering-baseline/pull/160).
