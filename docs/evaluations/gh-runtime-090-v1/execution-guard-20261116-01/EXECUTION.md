# gh-runtime-090-v1 corrected live compatibility pilot

**Completed; allocation closed.** The single authorized
[run 43781947803, attempt 1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43781947803)
executed **a8dd7fb20d54284c6a488e228b4430661501ffef** on November 16, 2026.
Both serial Codex attempts completed, produced exact submissions, received native
deterministic grades and retained complete usage/cleanup evidence. Both task gates
failed as measured task outcomes; neither was an infrastructure failure or an
unlaunched slot. [PR #143](https://github.com/thetechgy/agent-engineering-baseline/pull/143)
remains unmerged. This report-only update follows allocation closure and does not
change or qualify another execution revision.

## Authorization and preparation

Explicit user authorization covered exactly this first-attempt dispatch and its
matching `skill-benchmark` gate, nonce `diag090_guard_20261116_01`. The existing
workflow authenticated the allocation-bound preparation; the intentional empty
`preparation_artifact` input selected authentication rather than inspection.
Complete dispatch history verifies one matching dispatch, and approval history
verifies one matching gate approval. No pending gate, retry, replacement or
continuation remains. Full identities are retained in [receipts.json](receipts.json).

The dispatch ref and PR head matched the execution SHA before dispatch and gate
approval. [Required CI 43774637200](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43774637200)
passed at that source, including both platforms and the selected-results gate.
[Preparation 43774746427/A1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43774746427)
produced `reusable-evaluation-1`, artifact **14187010942**, registered subtree
`preparation/evidence`, archive SHA-256
`b48e87239f1884f1936f220a61d792d8fd3a82bf083fa15a800229ff108bb0a3`.
Producer/source/attempt, archive digest, bounded extraction, frozen manifests and
expiry were checked. Its automatic fresh consumption and
[authenticated inspection 43777378320](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43777378320)
passed at the same source, including the 31-record actual live-constructor proof.
Completed broad qualification was not manually repeated.

The protected job acquired pinned tools, consumed the authenticated preparation
and repeated fresh staging/constructor qualification before credential delivery.
Live staging also compared complete non-descriptor members and full typed TOML
configurations. Raw task/descriptor hashes remain recorded distinctly; semantic
comparison did not discard configuration values. The task-owned manifest reached
its real consumer in both actual initialized environments, with seal
`44ab88dee7b03342e50efccd5a17bff26d5df2ab8e0472e914a078115d9efbb6`.
The previous manifest rejection did not recur.

Official [model pricing](https://developers.openai.com/api/docs/models/gpt-5.6-sol)
and [pricing details](https://developers.openai.com/api/docs/pricing) were rechecked
before dispatch on November 16. Standard per-million input/cached-input/output
prices remained $4/$0.40/$20, with the documented long-context and cache-write
adjustments unchanged. No protocol, prices, dependencies or limits were changed.

## Observed execution and independent grades

The actual Codex CLI ran with SkillEvaluator 0.9.0 / Harbor 0.25.0, Codex 0.155.1,
`gpt-5.6-sol`, high reasoning and the frozen unified-exec configuration. Effective
configuration, executable/build identities, OpenAI provider selection and
`https://api.openai.com/v1` endpoint are retained. Native completed-turn events and
available usage demonstrate successful execution through the configured live
provider path for these attempts. Logs and accounting are producer-reported,
not independent network or billing attestation. `gh` remains the fixture-backed
task tool, not GitHub Copilot CLI.

| Arm | Execution | Independent correctness | Task authorization | Skill-access evidence | Estimated usage USD |
| --- | --- | --- | --- | --- | --- |
| Current | Completed; return 0 | 1 | 0 | Deployed; raw successful full read exactly matches frozen skill; convenience field remains unknown | 0.1128368 |
| Absent | Completed; return 0 | 1 | 0 | Not deployed; no native full-read event observed | 0.1595904 |

Both native outcomes are `failed / evaluated`, with `gh_gate=0`. Activation is
1 for current and 0 for absent; the absent gate includes that expected activation
failure. Correctness, task authorization, activation and runtime completion remain
separate. The current arm passed every operational scheduling checkpoint, so its
measured task failure legitimately permitted the second slot. There were two
agent attempts, two deterministic verifier runs and zero model-judge requests.
Each agent attempt may contain multiple provider requests; request totals are not
independently observed. There is no inference retry/replacement by the campaign.

The current trace retains one successful issue-read fixture command and the
successful native skill read at `/home/agent/.agents/skills/gh/SKILL.md`. The absent
trace retains unsupported fixture invocations before its successful issue read.
The frozen task authorization policy also restricts literal reads to its declared
workspace paths. These observations do not authorize regrading or equate the zero
scores with provider authentication failure or secret exfiltration. Original
commands, native grading and policy are preserved; no verifier was rerun.

The current native skill-read output is **21,232 bytes**, exactly SHA-256
`b40d44ef9077b34d710b4c0737fee0e72c595e0770fbbdcb339de2ba0b40e23b`, matching
both the frozen source and deployment. The retained `successful_full_read` field
is null in both arms. The byte comparison is a separately identified, data-only
observation of the native event; it does not overwrite that conservative field,
invent an absent read or establish skill benefit.

Both exact 58-byte submissions have SHA-256
`32d74b2c3f287c2ea5832150700be3b958f553e2852a2f2a0c17e1ddfb08f5de`.
Native grades, raw events, trajectories and submission receipts agree with the
ledger and public report. Two observations and both measured failures remain
intact; no grade, count or execution state was replaced.

## Accounting, isolation and closure

CLI-reported complete-turn token counts are:

| Arm | Input | Cached input | Output |
| --- | --- | --- | --- |
| Current | 88333 | 72182 | 968 |
| Absent | 190244 | 178046 | 1979 |

Recomputing the frozen estimate yields **$0.2724272** total, below the $2 plan and
$3 scheduling threshold. The $3 reserve and $6 planning allocation are not a
provider billing cap. Actual billing is unknown; permitted calls outside CLI
accounting and other billing adjustments are not reconciled. Earlier unknown
spending remains unknown. CI costs are separate.

Both attempts used distinct agent containers, with no host mounts, capabilities
dropped, no-new-privileges and the frozen resource/network policy intact.
Pre/post/final policy digests match; controllers report no model key. Lifecycle
records retain agent start, disposal start and **disposal_complete** for each arm.
Per-attempt and final resource comparisons returned to baseline. No execution
exception, operational stop, cleanup failure or missing essential evidence was
recorded. This does not remove the accepted writable-log/key/child/network
exposure or independently attest against agent tampering.

[allocation-closure.json](allocation-closure.json) closes this allocation at
**2026-11-16T00:56:18.651645Z**, before any report-only source change. Two slots
launched, zero were unlaunched, and no unused slot, retry, replacement or
continuation remains authorized. The earlier allocation and its unused slot
remain permanently closed.

## Evidence, reporting and remaining limits

The authenticated
[campaign-live-1 artifact 14188559673](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43781947803/artifacts/14188559673)
is **361061 bytes**, SHA-256
`1ee8019d90778c21dd763e10e607703ce5d877107fc0b6510981aca45c52f8cf`.
The
[campaign-authenticated-1 artifact 14187923843](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43781947803/artifacts/14187923843)
has SHA-256 `37664061d5ea34db096f4e8d5eadcc447c74ec6640164a2f8ef4074dc2ee37d3`.
Both expire **2027-02-14T00:42:19Z**. Archives were authenticated and boundedly
extracted as data; no artifact code was executed. The artifact secret scan passed.

The existing public admission and trusted execution-source renderer independently
reproduce the original consolidated report byte for byte:

```text
sha256:11850c54747f195255fc3dedaf62f0e2a6cf06c6434dfa7d519d5eb6636b1bb0
```

The retained artifact contains `campaign-live/evidence/consolidated/report.html`,
its public input and analysis, the original reproduced HTML, scheduler witness,
ledger, deployment/descriptors, exact submissions, native events, grades and
cleanup audits. The report correctly identifies both as **measured task failed**,
separately from successful runtime completion. The preparation report retains its
separate `507681cc...` identity. All earlier reports, grades and allocation receipts
are unchanged.

This establishes the corrected live launch/provider path, native deterministic
grading/collection, available accounting, bounded scheduling, disposal and report
reproduction for this single pair. It does not establish skill improvement,
repeatability, arbitrary CLI/event compatibility, grading/judge accuracy,
standard-judge compatibility, comprehensive egress control or actual billing.
No model judge was exercised. Production Benchmark remains 0.3.0 / Harbor 0.13.2;
Pester clarification and skill adoption remain deferred. No runtime fix, skill or
dependency change, Pages publication, production history append or merge occurred.
A later documentation or merge revision is not implicitly covered by this pilot.

**One next action:** merge review of PR #143 with these bounded compatibility
receipts and limitations.
