# Issue #95 follow-up qualification

This follows the original [dependency assessment](DEPENDENCY-REFRESH-95.md).
That document records the earlier decision and evidence; it is not a statement
that every previously held candidate is still blocked.

## Proposed updates

| Input | Previous | Candidate |
| --- | --- | --- |
| Semgrep's bracex | 3.2 | 3.2.1 |
| Released gh skill | 2.102.1 | 2.103.3 (`63837fb`) |
| Docker Compose | 5.6.1 | 5.7.0 |
| Python task image | Earlier 3.12 image index | Python 3.12.16 image index `b18b261` |
| Signed Debian snapshot | 20261010 | 20261103 |
| Direct ca-certificates | 20250419 | 20250419+deb13u1 |
| Pester fixture curl | 8.14.1-2+deb13u5 | 8.14.1-2+deb13u7 |
| Pester fixture PowerShell | 7.6.6 | 7.6.9 |

The uv 0.13.7 update is already on main through PR #113. The branch-based APM refresh remains
in PR #111, with the current competing-skill policy aligned to its native lock.
The hardening skill's six deployed file hashes are unchanged there. These PRs
remain separate from this follow-up.

## Qualification evidence

The bracex update is the only package-version change in the Semgrep lock.
The lock was regenerated with pinned uv 0.13.6 for the existing platform and
Python targets, then reproduced byte for byte with main's uv 0.13.7. Hash-checked binary installation, dependency consistency,
four real Semgrep contract tests, seven path-matching controls and four
published brace-expansion bug controls passed. Semgrep's actual glob flags do
not enable brace expansion. See the [bracex release](https://github.com/facelessuser/bracex/releases/tag/3.2.1).

Native APM performed the scoped gh update, frozen restoration, compilation,
both audits, packaging and offline msgraph launcher checks. The installed gh
file and lock changes came from APM. The new released skill adds artifact CLI
guidance; the historical captured CLI help remains at 2.102.0.

The native gh verifier originally copied host-owned tests into the container
with UID 1000 ownership. Mode 700 therefore allowed the agent with the same
UID to read private verifier input. The production copy helper now explicitly
sets root ownership before applying mode 700. A real staged fixture changed
from readable to denied for UID 1000; all original private-access probes remain.

The new image digest was checked against Docker's official library/python
registry metadata. Debian metadata was verified by apt against the image's
archive keyring using the fixed snapshot, without a live-source fallback or
signature bypass. Direct package versions were resolved from that metadata.
The Compose executable and PowerShell archive matched their release hashes.

The workstation's default mask creates public staging files unreadable to the
container's agent after Docker copies them as root. Native qualification uses
an isolated snapshot with normal Git checkout modes. Private verifier ownership,
network isolation, worker and container limits, outcome assertions and retries
are unchanged.

New active custom profiles distinguish the changed runtime inputs:
`gh-deterministic-gate-v4` and `pester-pilot-v2`. Their earlier profiles, metric
definitions, captured help, archived sources and historical public fixtures
remain unchanged. Existing measurements must not be relabeled as these profiles.
The `custom-metrics-v3` saved-review selector retains the original v2 validator
modules and pins the expanded registry separately; v2 and its archive are unchanged.

The production benchmark environment, with the unchanged project patch,
passed the real gh boundary in all six selected containers. The credential-free
Harbor Compose lifecycle also passed: UID 1000 execution, network isolation,
resource limits, private-data denial, copy round trip, command exit propagation,
repeated startup and resource cleanup. No model trials ran.

The patched gh and custom-metric suites completed 33 tests (one skip) and 26
tests respectively. Thirty current/historical frozen-review tests and eight
main-integrated policy, inventory and workflow checks passed. These are focused
checks, not a claim that the full local regression suite passed.

Native Pester qualification could not complete. The signed fixed snapshot
returned HTTP 503 while downloading package archives, including
`python3.13-minimal` and `libk5crypto3`. After the first infrastructure failures,
the run was interrupted to stop repeated failed builds. Partial trial results
and build logs were retained; interruption is inconclusive, and none of those
fixtures qualifies the PowerShell/curl changes or the Pester boundary for the
shared Compose/image refresh. Sources, signature checks, deadlines, retries,
worker limits and expected outcomes were not relaxed.

On this host, the trusted PowerShell startup command exits 137 under the
existing worker limits with both 7.6.6 and 7.6.9. The isolated 7.6.9 archive
passes its version check outside those limits, and parser/classification checks
pass apart from that baseline-reproduced startup failure. This is not a full
runtime qualification.

The follow-up PR remains a draft until hosted validation establishes the full
Pester boundary and the required checks pass on its current revision. Passing
gh/component checks do not substitute for that missing evidence. The separate
APM PR also encountered a snapshot-service HTTP 503 on its newer main-merge
revision; that failure is retained rather than reported as a pass.

## Remaining holds

SkillEvaluator, Harbor, Codex, the evaluator/scanner OpenAI SDK and Pydantic
remain a coordinated migration. Complete submitted-operation evidence and the
runtime, grading, patch and report contracts must qualify together. No paid
model evaluation was run. The git-commit update remains held because its
upstream instructions reset unrelated staged changes. Existing exact pins and
historical evidence for these held groups are preserved.
