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

Hosted native oracle/CLI qualification, authenticated artifacts, cleanup, report
reproduction and final required/change-selected CI are pending. Their final
revision and receipts will be recorded here before delivery. No pending check is
claimed passed. Local Docker is unavailable; the existing credential-free hosted
route owns container qualification. Non-forwarding CLI controls use the pinned
CLI with a local stub, not a provider or model judge.

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
Final-source hosted qualification must verify the corrected label as well as all
native outcomes, cleanup and report reproduction.
