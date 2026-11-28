# Evaluation registry structure proposal

**Decision requested.** Approve separating reusable grading definitions from
source and runtime bindings for new evaluation records. Keep the legacy reader
available through the transition. Review history removal in a second pull
request after the compatibility results are available.

## What changes on a source revision today

Baseline: `a4784e8`, after PRs #194 and #195 merged. Counts are from tracked
files and the current registry loader. The campaign directory count includes
JSON files only.

| Measure | At `9d004e6` | At `a4784e8` |
| --- | ---: | ---: |
| Lines in `custom-metrics.json` | 85,207 | 85,207 |
| Metrics and profiles in that file | 15 / 1,327 | 15 / 1,327 |
| Campaign JSON files under `.github/evals/campaigns/` | 93 | 103 |
| Hosted campaign choices | 12 | 15 |

The current loader resolves 16 metrics and 2,816 profiles after applying 17
source files with 6,159 lines. The latest refresh, `source-v53.json`, added
377 lines for 93 inherited profiles. Of those, 92 are campaign profiles and one
is a Pester effectiveness profile. Local recomputation matched the registered
source digest for all 92 campaign profiles (65 Pester, 21 gh, six Podman).

`custom_contract()` selects by explicit profile ID, then purpose-specific
rules or the active fallback as applicable. It hashes the resolved profile
with its metric definitions. A source successor replaces the profile ID and
`runtime_digest`. Replay successors can also replace the replay adapter hash.
The campaign digest called `runtime_digest` covers the source manifest,
including shared scripts, configuration, task inputs and runtime files.
Updating a shared input can therefore change the contract identity across
campaigns whose grading rules stayed the same.
[Registry loader](https://github.com/thetechgy/agent-engineering-baseline/blob/a4784e8ccf143c552ce5110c19fe00bf6d4faf3e/.github/scripts/skill_evidence.py#L3840-L4005) ·
[Campaign source manifest](https://github.com/thetechgy/agent-engineering-baseline/blob/a4784e8ccf143c552ce5110c19fe00bf6d4faf3e/.github/scripts/evaluation_evidence.py#L32-L90).

## First pull request

1. Register each active grading definition once under a stable ID and digest.
   Use the reviewed task-family registration for skill-owned definitions.
   Bind metric ownership, cases, applicability, denominators, outcome rules,
   and the reviewed grader and fixture identities. A change to these inputs
   requires explicit review of the grading identity. A new skill supplies its
   own cases and grading definitions. The hosted selector and phase routing
   still require the review documented in item 10.
2. Resolve an execution binding for each new run. Use the registered campaign
   and mode, the exact evaluated Git revision and input manifest, the selected
   skill and dataset bytes, the resolved and pinned runtime, and the
   definition, selection and protocol identities. Bind the replay adapter
   where applicable. Record separate grading and execution digests in a
   versioned capture and public record. Keep the run, trial, arm and evidence
   reference identities in the existing shared pipeline. A source-only
   change changes the execution binding while reusing the grading definition.
   A runtime change still requires reviewed runtime admission.
3. Recompute the binding from trusted inputs. At preparation and fresh
   consumption, use the exact reviewed checkout and the existing
   producer/artifact authentication. Keep the exact staging, scheduler,
   report reproduction, first-dispatch and environment gates. For offline
   reproduction, resolve the source from an independently pinned producer
   tree or a reviewed digest for retained inputs. Pin a retained source
   bundle only when a reader needs it. A revision, manifest or registry
   supplied solely by the record cannot authorize its own admission.
   Preserve the current assurance fields and reference expiry rules.

Add the versioned path alongside legacy resolution. Retain the legacy profile
ID, purpose, digests and record IDs verbatim. Old preparation remains bound to
its original revision and approval. Public-only analysis and rendering must
be able to validate the new record offline with the reviewed inputs available
locally. Use the same reporting and analysis contract for Pester, gh and
Podman. This work changes registry storage and identity resolution. Custom
history publication under #92 stays disabled.

### What the implementation must trace

| Reader | Dependency to preserve |
| --- | --- |
| Campaign qualification, preparation, authentication and live consumption | The purpose selects the profile. Preparation pins the resolved source, runtime, selection, protocol, producer and exact staged bytes. |
| Native capture, normalization and retrospective replay | Admission verifies the resolved contract, inputs, grader, fixture, dataset and reward identities. Replay also binds its adapter and original submission. Pester effectiveness, released diagnostics and gh oracle have separate purpose selectors. |
| Public validation, decision reports, analysis and sealed publication | Public records carry the legacy profile and contract digest. Decision/report consumers and historical classification resolve that identity and its provenance. Sealed evidence still binds exact members. |
| Private review and historical fixtures | Some validator snapshots verify the exact registry bytes. Campaign digests through v52 also use pinned inputs from before the onboarding refactor. Replay must use each reader's reviewed source and tooling. |

Inventory actual callers and retained records before switching each entry
point. In particular, some historical calls resolve a task or selection
through the current checkout even when validating an older profile. Prove
which inputs they need before relying on a producer snapshot or deleting
their current copies. Keep unavailable evidence in its current state.
[Preparation checks](https://github.com/thetechgy/agent-engineering-baseline/blob/a4784e8ccf143c552ce5110c19fe00bf6d4faf3e/.github/scripts/evaluation_campaign_protocol.py#L79-L129) ·
[Native admission](https://github.com/thetechgy/agent-engineering-baseline/blob/a4784e8ccf143c552ce5110c19fe00bf6d4faf3e/.github/scripts/skill_evidence.py#L4450-L4511) ·
[Private review](https://github.com/thetechgy/agent-engineering-baseline/blob/a4784e8ccf143c552ce5110c19fe00bf6d4faf3e/.github/scripts/skill_report_reviews.py#L406-L442).

### Acceptance evidence

- Make a second, source-only revision that changes a shared manifest input.
  Measure grading registry, binding registration, and campaign definition
  lines added. Target zero lines in all three for unchanged grading, runtime
  and selection. Record the actual count alongside the 377-line v53 baseline.
  A new fixture family should add task-owned data and a reviewed registration
  entry. Count any shared changes it still needs.
- Run credential-free native qualification for Pester, gh and Podman through
  their applicable entry points. Exercise fresh preparation consumption where
  supported. Refuse changed source, runtime, definitions, mode, owner,
  dataset or grader, including a stale preparation and a record that supplies
  its own replacement binding. Keep unsupported, expired and interrupted
  evidence distinguishable from measured failure.
- Re-admit and reproduce each available retained record with the appropriate
  reader. Account for every record in the inventory, including unavailable
  inputs and expected refusals. Compare exact historical IDs, contract and
  artifact digests, outcomes and report members. Cover current reports,
  retrospective records, public-only rendering and pinned private-review
  snapshots. Run the existing exact-byte comparisons where they protect
  preparation or publication. Surface any coverage gap before advancing.

## Second pull request

Return for approval with the caller inventory, compatibility results and
exact removal list. Pin the last revision carrying the full registry with a
reviewed tag, and record the tag's commit SHA and required member digests.
Preserve reachable producer revisions and pinned tooling used by retained
readers. Stage a fresh offline checkout with those inputs, run the same
admission and reproduction audit, and demonstrate recovery from that tag.
Remove only redundant working-tree registry history after those checks.
Active definitions, retained evidence and reports, and independent runtime
or authorization records remain available. If a reader still relies on a
candidate deletion, keep that member until the reader has a verified route.

## Implementation

The first migration uses the frozen v53 rows to resolve stable campaign and
Pester effectiveness grading definitions. New credential-free task families
can register their own `grading.json` beside their onboarding and selections.
The v53 profile IDs, parent chain and report inputs remain readable. A small
compatibility file preserves source digests for the v53 readers of edited
scripts.

The execution binding identifies the committed tree, grading digest, mode and
execution policy. Campaigns bind the exact definition, selection, runtime and
protocol files from that tree. Native admission uses a clean checkout and the
expected staged inputs. Offline public validation reads the local Git object
store. It accepts the reviewed checkout, an ancestor with the new registry
format, or a retained revision explicitly pinned in the committed registry.
Supply the reviewed producer checkout when an older record needs frozen
campaign files its current reader can no longer reproduce. The binding does
not authenticate execution by itself.

## Legacy registry archive

Active grading lives in `.github/evals/active-grading.json`. The 20 legacy
members are pinned by commit and SHA-256 in
`.github/evals/legacy-registry-archive.json`. The tag
`evaluation-registry-legacy-v53` identifies commit
`f79ecc5b1e98e4575f434d8cb22ccd1cf67690ab`, which contains all the pinned
bytes. The offline reader reads those Git blobs as data. It requires a
local copy of the pinned Git objects and verifies every member it uses.
Hosted consumers retain Git history through their existing pinned checkout
action.

For a shallow local checkout, fetch the reviewed archive before replay.

```bash
git fetch --no-tags origin tag evaluation-registry-legacy-v53
git rev-parse 'evaluation-registry-legacy-v53^{commit}'
```

Compare the printed commit to the archive index. A retained public record
from the pre-merge PR head may also need its producer Git objects. The
grading registry records the approved revision for those records. They can
be recovered separately with `git fetch --no-tags origin refs/pull/196/head`.
Historical private review descriptors continue to use their own frozen
tooling snapshots.
