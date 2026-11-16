# Permission successor qualification

Base: merged #144, `6d063563746651a7e70a570007ed4c23eee9b9d9`.
The [contract/matrix](CONTRACT.md) was written before successor result inspection.
[Local receipt](local-controls.json): 34 independent synthetic trajectories ran
through trusted native staging and the generated isolated native grader. They are
not observations of model behavior or a new container-lifecycle qualification.
No historical trace was used as a replacement control or rescored.

The first staging attempt correctly rejected workstation APM 0.35.0. Retrying with
an existing pinned APM 0.35.1 exposed shared-object mutation in the deliberate
invalid-metadata fixture; the correction copies metadata before injecting it.
The first isolated native matrix then exposed a null observation normalized to an
empty string. The successor now checks original call/result linkage and string
content before interpreting normalized calls. The repeated matrix passes all 34
expected outcomes. Failed attempts are retained separately, not overwritten.

## Final native qualification

[Run 43808603192/A1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43808603192)
completed successfully at executable revision
`501b54d5ebdd90bacbc5d920e67fb7afdda1ea9e`. [The native receipt](native-receipt.json)
binds artifact `14199964189` (1,177,323 bytes), ZIP SHA-256
`fc367315f00c1c5767dc563a126aa5667bddc47c640255b48889efbd33fe9b6e`,
the producer repository/workflow/attempt, exact public records and all 38 outcomes.
Bounded data-only extraction verified the archive digest, size and members; no
artifact code was executed. Both public policy records identify
`gh-task-permission-v2`. All trials completed without native exceptions, with
terminal cleanup true, zero authorized live attempts and no inference/provider
credentials or model judges. Non-forwarding probes use the actual pinned CLI
with a local stub. Local Docker is unavailable; this existing hosted route owns
container qualification.

| Native controls | Passed | Failed as expected | Unsupported, unscored | Unknown, unscored |
| --- | --- | --- | --- | --- |
| 17 oracle cases × current/absent | 5 | 21 | 2 | 6 |
| Good/prohibited CLI probes × current/absent | 1 | 3 | 0 | 0 |

All 38 outcomes match their predeclared expectations. Good task work passes
correctness and authorization in both deployments. Its absent gate fails only
because activation is absent. Prohibited work fails authorization; unsupported
and unknown evidence do not become success. Current CLI probes record successful
target-specific full reads; absent probes remain undeployed with unknown full
read. Competing-only access never counts as target activation.

All 38 staged tasks passed existing protected-member admission. Fresh local/native
oracle members agree for all 34 tasks except TOML presentation; existing complete
typed TOML comparison verifies every key, scalar type and array order. This does
not claim raw descriptor byte equality. All three existing consolidated reports
reproduce byte for byte from public inputs:

| Report | SHA-256 |
| --- | --- |
| Oracle | `a0819ab02df8b42013ec01d7999274b3ba151e88719474da9e856662ce993c15` |
| CLI probes | `0b85866fe9897de6d2d534229120b96a2f27531f72f9d03a1d296076c7153f8a` |
| Combined | `7683ad7c800b03c1d9f0cc6c3f147e1acd7c9bda93c5f2db259a6c313fc3a027` |

After authenticating and extracting the artifact with the existing bounded
`codex_pilot_dispatch.extract`, reproduce through the existing shared entry point
`evaluation_campaign_core.render`. Pass the archive's
`gh-task-permission-v2/{oracle,probe}/evidence/public` directories and a new output
directory. Compare `consolidated/report.html` with each mode's retained HTML and
with `report/consolidated/report.html` for the combined report. Use the pinned
0.9.0 data-only owner; no credentials or new renderer are needed.

[Source-v19 bindings](source-bindings-v19.json) remain identical after adding these
documentation/receipt files. Native execution belongs to `501b54d`, not the later
receipt commit. [Final preservation](preservation-final.json) verifies all 595
predecessor profiles/14 metrics, all 628 source-v18 profiles, unchanged active
profiles and protected frozen inputs. [Earlier source-v18 reports](preserved-v18-reports.json)
still reproduce unchanged under the new consumers. Fresh native control outcomes
and metrics also agree across the reporting correction; originals were not
rewritten or regraded.

The focused local suite completed 85 tests: 73 passed and 12 owning-runtime
checks were skipped. Final
required/change-selected CI is tracked against the receipt commit on
[draft #145](https://github.com/thetechgy/agent-engineering-baseline/pull/145);
the PR and #95 status carry its exact revision and terminal result. Superseded
validation runs are cancelled and inconclusive. This qualification establishes
bounded contract/runtime/report behavior, not future model behavior or skill
improvement.

## Retained development attempts

First hosted attempt: [43801716584/A1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43801716584)
at `9d44c7e9f16d7ef52c4accfde3ac31ba329eacc4` stopped after the first current oracle
trial. Its verifier sidecar passed all dimensions, but the chosen environment
incorrectly requested a CLI egress sidecar during oracle lifecycle completion.
The native exception makes the attempt infrastructure evidence, not completed
qualification. Cleanup completed; the other 33 oracle slots were unlaunched.
Artifact `14196825997`, ZIP SHA-256
`fc6140789ed4f6ba7c42b4c4da0c136a969656f03a69eb7bf6c72b3fb95ab384`,
retains the failed attempt. The correction uses the existing trusted oracle
environment, reserving the CLI environment for non-forwarding probes.

The same failed attempt exposed the separate report's strict matched-input check.
Both arms now receive identical permission instructions (target reads explicitly
conditional on deployment) and identical oracle payloads. The per-arm trusted
resource inventory alone varies with deployment. The existing report's matched
input contract stays intact. No infrastructure exception is changed to a pass.

The intermediate `3136fa9` hosted run was cancelled after final review added a
complete post-run inventory check and separated unsupported cat flags from
prohibited reads. It is inconclusive and cannot qualify the final source. Its
partial artifact is retained separately. The frozen control expectations did not
change. Whole-inventory drift without a proven prohibition is unknown; complete
call evidence still preserves a known denial if another copy drifted.

Local focused checks now cover physical staging/inventory order, another skill
identifier and `/srv/discovery/manuals` through the same grader/resource interface.
That demonstrates interface reuse, not qualification of another runtime. The
retained report suite completed 112 checks: 107 passed and five rejected the
local review dependency pins. The same version-guard rejection reproduces on
unchanged main; no guard or installed dependency was modified. The initial 0.9
host's historical-owner rejection and these pin rejections remain failed local
attempts. Required hosted checks use their configured owning environments.

The cancelled `3136fa9` artifact `14197781765` has ZIP SHA-256
`ba96afa0844e3706c523a34991a041f66158a8c6f0663672b88f71a64735ea19`.
Its interrupted snapshot records 23 completed oracle controls, one launching and
ten unlaunched, with no terminal cleanup receipt. Completed rows retain their
individual cleanup observations; global cleanup remains unavailable. No completed
report or final-source qualification is inferred from that partial snapshot.

The new resource reader uses the repository's existing no-follow, file-descriptor
identity and bounded-read pattern. Independent controls replace a checked file
with a symlink and with a different regular file between inspection and open;
both reject. This is file validation, not a new attestation system. The post-run
inventory snapshot does not prove inode ownership at every earlier read or cover
unobserved filesystem actions. The later `0bc8169` run was also cancelled as
superseded before replacement qualification of this final reader.

[The independent replacement-race receipt](replacement-race.json) exercises the
same inspection/open boundary in this PR's first reader and the final reader.
Both a symlink substitution and a regular-file replacement read the substituted
synthetic bytes before the fix and reject afterward. This is evidence about the
new reader, not a reinterpretation of a historical agent attempt.
[Source bindings](source-bindings.json) and [preservation checks](preservation.json)
record the existing profile identities and unchanged historical inputs.

## Completed native path and reporting-policy correction

[Run 43804897469/A1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43804897469)
at `3dcd6cb518314f79d626615664fc756c3ba9fb73` completed all 34 oracle controls
and four non-forwarding CLI probes with expected outcomes and terminal cleanup.
Artifact `14198454330`, ZIP SHA-256
`b9e6e29dab9b9e6975a8b7b5c53e39101578f45e9ff1509d88ed90ca3cb20673`,
retains the native observations. Both current CLI probes record target-specific
full reads; both absent observations remain unknown and undeployed. All three
existing consolidated reports reproduce byte for byte from public inputs.

Artifact review exposed a remaining reporting mismatch: the top-level public
policy inherited `per-case-allowlist-v1`, while native entries, task grading,
custom profiles and authorization-v2 measurements used the successor contract.
This run completes the native control path but does not qualify that misleading
policy label. Its original records, grades, convenience fields and HTML remain
preserved. No retained trace is regraded.

A small opt-in reporting hook now takes the authorization policy from the task
adapter, requires it during public admission and gives the successor a distinct
public policy identity. Source-v19 profiles preserve every source-v18 profile;
the mechanical Pester effectiveness source successor changes no grading or inputs.
The final run above verifies the corrected label, all native outcomes, cleanup
and report reproduction. The source-v18 observations remain independent records.
