# Offline evaluation evidence

`skill_evidence.py` inventories sources, reads selected pinned SkillEvaluator
reports, and builds a separately validated public projection. It never invokes
evaluations, graders, scanners, artifact scripts, recovery, or network retrieval.
Use the existing pinned evaluator environment (Python 3.13, SkillEvaluator
`0.3.0`, revision `ac0a04905100acdafc6c95829311a9739c340ff6`). No new dependencies
are required.

## Commands and outputs

```bash
"$SKILL_EVALUATOR_PYTHON" .github/scripts/skill_evidence.py inventory

"$SKILL_EVALUATOR_PYTHON" .github/scripts/skill_evidence.py normalize \
  --kind behavioral --skill podman --input /tmp/podman-artifact

"$SKILL_EVALUATOR_PYTHON" .github/scripts/skill_evidence.py normalize \
  --kind static --skill podman --input /tmp/skill-quality

"$SKILL_EVALUATOR_PYTHON" .github/scripts/skill_evidence.py project \
  --input .github/tests/fixtures/skill_evidence/gh-no-model.json
```

The command prints a new temporary directory outside the checkout. Inventory
writes `inventory.json`; normalization writes `evidence.json` and
`public-report.json`; projection writes `public-report.json`. `--output` selects
a new ordinary directory with an existing ordinary parent outside the checkout.
Existing destinations, input/output overlap, linked components, and overwrites
are rejected. Validation and deterministic serialization precede output creation.
For standalone static projection, retain the original static bundle and place
`evidence.json` at its root; `project --input` reads native members relative to
that file's parent. A serialized static record without its native bundle rejects.
Static projection protects that entire parent bundle from output creation:
explicit destinations and temporary parents inside it reject before allocation,
including directories beside `evidence.json` and beneath native report members.
Normalization already produces a verified public report, so moving its output
does not require copying private native reports into the output directory.
Inputs remain unchanged. CLI contract errors return exit status 1 without echoing
native diagnostic content. Oversized integer observations are range-checked
without converting them to floats; native numeric overflow also becomes a bounded
contract rejection before output allocation.

Before creating temporary output, the selected parent must be an ordinary
directory outside the checkout and input bundle. The first nonempty `TMPDIR`,
`TEMP`, or `TMP` setting takes precedence over the platform default. Unsafe
settings (including linked, missing, or non-directory parents) are rejected
without falling back to another location or leaving an output directory behind.
Explicit `--output` placement does not depend on temporary settings.
Output requires directory-descriptor support and no-follow directory opens.
Every output ancestor, including the selected parent, must be owned by root
or the effective caller UID. Group/other-writable components require the sticky
bit; shared writable components without it reject before directory allocation.
Ownership and permissions are checked on the opened ancestor descriptors.
Together with caller-owned private output directories, this prevents another
unprivileged UID from relocating an ancestor or destination during publication
under the [Linux rename permission rules](https://man7.org/linux/man-pages/man2/rename.2.html).
The effective caller UID and privileged processes are trusted: a process with
those authorities can relocate owned directories and is outside this isolation
boundary. Unmapped or foreign ownership rejects rather than assuming trust.
It anchors every parent component, creates temporary or explicit directories
relative to the parent descriptor, and creates flat output files relative to the
new directory descriptor. Replaced paths cannot redirect writes into the checkout
or input bundle within that ownership boundary; changed destination identity
rejects publication. Unsupported platforms reject before directory creation.
If output member creation, writing or flushing fails after validating the new
directory, publication removes only its created members through the retained
descriptor and removes the destination only while its original identity matches.
Ordinary failures leave no partial temporary output and allow an explicit-path
retry; cleanup never follows or removes a replacement destination. If opening
or validating the new directory descriptor fails, cleanup uses the retained
parent descriptor and captured directory identity to remove the still-empty
reservation. A missing or replaced destination preserves the original rejection.
This path is verified on Linux; Windows output support is not established.
Input files use the same no-follow ancestor traversal and open the final member
relative to its parent descriptor. Replacing an ancestor cannot redirect input
bytes outside the validated tree; unsupported descriptor platforms reject reads.
Reopened ancestor descriptors must also match the device/inode identities recorded
during path validation. An ordinary directory replacement rejects before reading
its member bytes, while an already anchored descriptor continues to its original.
Inventory shares the captured directory identities across catalog, overlay,
deployed and competing source scans, metadata, datasets and optional native-file
checks. Its cached reader checks those identities even when reusing captured bytes.
Dataset discovery and optional-file selection use the captured entries, so an
empty replacement cannot silently remove validation inputs. Source directory
identities are checked before invoking the runtime visibility selector.
Native run/trial discovery, reviewed manifests and optional metadata also use
the initial bounded scan entries. A transient pathname subset cannot hide a
contradictory trial or optional member; every consumed member must be scanned.
Scans check directory modification/change metadata on the opened descriptor
before and after enumeration and retain it through member reads, cached reuse,
source selection and final validation. Same-inode entry changes reject, including
hidden/restored members and restored modification times. This guard relies on
filesystem change metadata and is verified with real renames on Linux; it does
not claim an atomic filesystem snapshot or isolation from privileged writers.
Scanned regular members also retain device/inode, size and modification/change
metadata. Reads check this state before and after capture; cached inventory bytes
are revalidated without recapture, and every scanned member is checked again
before publication. In-place edits and restores reject even when modification
times are restored. Optional consumed members outside scanned source trees use
the same state map. These checks retain the same filesystem metadata limits.
Standalone source-snapshot verification also rechecks every scanned directory,
including empty directories, after capture. Current and historical source
selection share the pinned runtime's ordinary visibility rules over captured
member names; selection never invokes its filesystem provenance authenticator
or private key loader. Generated-output markers remain rejected.
Temporary and explicit output parents use the same validated ancestor identities
before directory creation. Replacing an ordinary parent with the input directory
rejects before output allocation, preserving the input's entries and bytes.
Standalone commands disable bytecode writes before importing repository helpers,
so running without `PYTHONDONTWRITEBYTECODE` does not create checkout caches.

Behavioral input uses `results/<skill>/<run>/result.json` with native companions.
If several run directories exist, supply `--run <recorded-run-id>`. There is no
chronological selection, `latest` resolution, recovery, or missing-data fetch.
Linked aliases are rejected. Static input uses `reports/catalog-summary.json`
and its selected `reports/<skill>/skillevaluator-output-<timestamp>.json`.
Human-readable reports are never read. A static scan has no behavioral metrics.

## Inventory and ownership

Discovery uses `.apm/skills/*/SKILL.md` and
`.github/evals/*/evals/evals.*`, without a skill-name list. Discovery checks
local and overlay `evals.*` candidates before declaring a suite absent. Only a
single canonical `evals.json` is supported; unsupported-only and mixed formats
are rejected, including imported overlays without canonical JSON. At the reviewed
base there are six authored skill sources, the imported `gh` target, and two
behavioral suites: Podman and the repository-owned `gh` overlay. Other imported
skills are resolved as needed for overlay ownership or competing-skill evidence;
generated deployment directories are never additional authored sources.

The validated skill name is the logical `skill_id`. `source` records the active
source owner, repository, revision, source path, optional recorded upstream
lineage, and content identity. Inventory separately records generated deployment
and suite ownership. A local source and a same-ID overlay are compatible. Two
active source owners, competing dataset files/formats, missing owners, ambiguous
APM deployment records, and deployment hash drift fail closed. Imported sources
must match a unique lock dependency and its Codex deployment owner/hash records.

Their published source manifests reuse the lock-validated digests and the pinned
runtime visibility selection captured before validation, without rereading the
deployment after its hashes have been accepted.
Inventory enforces the existing `gh` and competing-skill pins and dataset
contracts against its captured files. It does not invoke the helpers' unbounded
tree enumerators; replacement directories cannot cause a second traversal before
the retained identity/state checks reject them. The standalone `gh` helper APIs
retain their existing behavior. All trees and fixture references are checked before native strict dataset
validation; source front matter must identify the local skill correctly.

Local inventory retains a repository revision only when bounded offline Git
objects at that revision reproduce its captured agent-visible content manifest.
Dirty, staged, untracked or deleted visible members leave the revision unknown;
unrelated workspace edits do not invalidate a matching scoped manifest. Missing
objects remain unknown without lazy fetch. These listing/blob reads share the
inventory operation budget and existing historical bounds.

Local repository association comes from one bounded offline read of the trusted
workspace's literal Git `remote.origin.url`, including linked worktrees. The
regular `.git` pointer must have a reciprocal `gitdir` back-pointer to this
workspace and reside under the common repository's `worktrees` directory before
any common-repository config is read. A direct `.git` directory cannot redirect
through an unrelated `commondir`. Unrelated or unsupported
Git-directory pointers leave attribution unknown without reading that config.
The back-pointer uses the same bounded capture and final state checks. The
common config and any `.git`/`commondir` pointer files use the same anchored
reader, file/directory identity and change-state checks as other inputs. Git
parses only captured config bytes, with includes disabled. Inventory and both
normalizers reverify those metadata states before returning evidence, rejecting
transient edits or replacements even when original bytes and modification times
are restored. Missing metadata retains the parent directory state captured before
lookup, checked immediately and before publication, so transient absence cannot
silently downgrade attribution. Stable absence remains unknown. Config and
pointer reads share the operation byte budget. GitHub
HTTPS, SCP-style SSH and `ssh://git@github.com/` origins normalize to lowercase
`owner/repository`, with an optional `.git` suffix. Includes, global configuration
and URL rewrites do not establish identity. Conflicting native repository
declarations reject before source or authored-dataset reconstruction. Missing
declarations or missing/unsupported origins leave normalized local repository,
revision and reconstructed content unknown, retaining `source_unavailable`.
Inventory can still describe captured configured bytes without repository or
revision attribution. Inventory resolves `HEAD` once, after bounded captures of
`HEAD`, loose refs, packed refs and reference-table storage in the common and
linked-worktree Git directories. Their file/directory states, including absent
storage, are verified around native Git resolution and before publication.
Reference captures share the operation byte budget and tree/member limits;
an unborn branch retains an unknown revision. Upstream deployment identities continue to use their lock
records. Local Git configuration establishes repository association, not remote
execution attestation or proof that a commit was published by that repository.
Reviewed extracts may likewise retain only the exact unknown-source record when
workspace association is unavailable; their existing reference, observation,
metric and execution pins still apply. That downgrade cannot introduce a new
repository, revision or content claim.
Recorded upstream ownership is accepted only for `gh` at its reviewed upstream
revision; its competing skill also requires the reviewed competing revision.
An arbitrary upstream revision or an upstream carrier on a local skill
rejects before constructing the source record, including during native replay
for standalone projection.

An upstream-to-local conversion keeps the logical ID, removes active upstream
ownership, and changes APM sources through normal pinned regeneration. Historical
evidence keeps its original owner/revision. Normalization never rewrites it to
current ownership. This change tests that representation in synthetic repositories;
it does not convert `gh`, change managed skills, or extend its runner.

`not_configured` means no behavioral dataset. Configuration is independent of
measurement: inventory always records `unavailable/results_not_supplied` because
inventory does not receive model results. The `gh-no-model.json` fixture records
24 configured cases, planned attempts, the locked competing hardening skill, and
pinned build/fixture conditions, with no verified model run or observed counts.

## Closed version 1 contracts

Inventory, normalized evidence, and public reports each use integer
`schema_version: 1`. Inventory has `kind: inventory` and a sorted `skills` list.
Normalized/public evidence use `kind: behavioral` or `static`. Their fixed fields
are `source`, `run_id`, `dataset`, `policy`, `arms`, `metrics`, `observations`,
`scans`, `findings`, `references`, and `availability`.

| Record | Meaning |
| --- | --- |
| `source` | Logical ID, local/upstream/unknown owner, repository/revision/path, recorded lineage, content manifest |
| `dataset` | Suite owner, authored-file digest and provenance, staged snapshot digest/algorithm and provenance, canonical case IDs/cohort digest |
| `policy` | Separate canonical ID, optional published ID, recorded policy fields, patch digest, metric set, judge and attempt policy |
| `arms` | With/without target condition identities, recorded execution status/error count, expected/recorded/scored/unscored coverage, native rubric counts |
| `observations` | Stable observation ID, arm/case/attempt, native scores, native rubric pass, separate deterministic scores/gate, reference IDs |
| `scans` / `findings` | Native scanner states/counts and structured finding severity/check/member/line references; no explanations |
| `references` | Stable reference ID, artifact/member hashes, relative member, structured locator, provenance and availability |
| `availability` | Complete/incomplete/unavailable, bounded reason codes and provenance classification |

Validators reject unknown or missing keys at every normalized/public object,
including objects inside arrays. Identifiers, enumerations, paths, counts,
booleans and finite native-range scores have explicit checks. Known native
diagnostic fields are discarded by narrow readers. Unknown custom grading
contracts require explicit reader support. Native objects cannot enter `project`.
The public projection constructs its fields explicitly, omits native trial UUID,
trial name and task name fields, and validates the result independently through
`validate_public`. The internal record retains their observation-ID mapping.

Prompts, transcripts, tool output, grader explanations, model commentary, HTML,
absolute local paths, and arbitrary metadata containers have no public fields.
Static findings with absolute native file locations keep a null member and a
structured native reference; that location is never opened. Limits are 8 MiB per
consumed JSON file, native depth 32, public depth 12, public serialized size 1 MiB,
1,000 cases, 10,000 trial observations, and 20,100 references (two members per
trial plus shared metadata). Reference IDs are tracked incrementally while
normalizing behavioral input. Reviewed-extract manifests share this member budget.
The public serialized-size limit remains independent
of these input cardinality limits. Exceeding any limit fails without
truncation or partial publication. Duplicate JSON keys, cross-platform case-ID
collisions, invalid denominators, linked/reparse/hard-linked or special inputs,
escaping references, and dangling observation references are rejected.
The trial-member budget is shared across both arms and checked before reading
any trial result or reward. Malformed front-matter YAML produces the same bounded
CLI rejection as other invalid metadata, without parser tracebacks or local paths.

Input trees are checked during traversal, before materializing all paths.
Normalization bundles and catalog/overlay trees allow at most 100,000 entries;
authored skill trees allow 2,000 entries and 1,000 files. Entries include
directories and unused or later-excluded files, so empty directories and unused
members cannot bypass the traversal cap. Exceeding a cap rejects the contract.
Each scanned directory is opened through validated ancestor descriptors and its
device/inode identity is checked before descriptor-based enumeration. Temporarily
substituting an empty or subset directory cannot hide the original entries.
The discovered local/overlay skill-name union is limited to 1,000 before any
per-skill metadata parsing, content hashing, or revision query. YAML aliases
retain shared objects; depth validation remembers each container's deepest
visited level so work is bounded by input nodes and the depth limit rather than
the number of alias paths. Cycles and over-depth paths still reject.
Lock metadata allows at most 1,000 dependency and 100,000 deployment records,
checked before record validation or ownership joins. Name/member indexes avoid
repeated whole-list searches; duplicate records, including aliases, remain
ambiguous rather than being deduplicated.

## Identity, provenance and coverage

Canonical IDs come from the pinned case-ID validator. Pairing uses canonical case
IDs, never directory order or guessed chronology. Scored attempts use the native
summary's recorded ordinal and trial mapping. Unscored attempts retain their
native trial identity and any explicit native attempt label; an absent ordinal
stays null with a metadata limitation. Public observation IDs are SHA-256 of the
canonical JSON array `[run_id, arm, case_id, native_id, native_trial, attempt]`.
Reordering inputs does not regenerate identities.

Ordinary runtime behavioral normalization carries a transient immutable witness
for its source, run, dataset, policy, arms, observations, headline metrics and
references. Projection checks
those claims against the witness. Standalone measured behavioral
projection requires the retained native bundle beside `evidence.json` and
renormalizes the selected recorded run before accepting its claims. Altering a
score on the same side of the rubric threshold still rejects. Changing artifact
IDs and provenance to synthetic or unknown cannot disable authentication. Reference
availability can be conservatively downgraded without relabeling native claims.
The witness binds availability provenance independently of conservative status
and reason changes. Reviewed reference pins require reviewed availability provenance.
The witness also retains the native required reasons. Projection may add
conservative limitations but cannot remove recorded ones, including global
diagnostic-only execution limitations that are independent of successful arms.
Reviewed extracts retain their independent pinned identity/payload checks;
unavailable records retain their existing rules. Synthetic measured records
require a native normalization witness too; synthetic provenance alone does not
authenticate their scores or metrics.
The witness is private in-memory state and adds no serialized fields or CLI flags.

Supplied summary attempts are validated before indexing: case rows and attempt
lists must have the native types, trial identities must be unique, supplied
ordinals must be positive, unique per case and within the attempt policy, and
scores/outcomes must have their bounded numeric/Boolean types. Counts cannot
exceed known recorded, scored or expected coverage, per-case policy caps or the
10,000-trial operation cap shared across both arms. Complete case details require
every supplied attempt to match a retained trial. Partial retained trials may
leave validated summary attempts unmatched; absent counts remain unknown.
Supplied case rollups must agree with their attempts: pass outcome, first passing
attempt, best score, attempts used, skipped and missing counts follow the pinned
collector's semantics. Known aggregate case/attempt totals, rates and policy
fields are reconciled too. Partial case summaries still bound aggregate passes
and attempts; missing detail cannot excuse contradictory rollups. These checks
also run when standalone projection replays a retained native bundle.

Headline metrics must agree with their retained native components even without
optional provenance metrics. The pinned data-only lift and dimension helpers
validate component deltas/directions, overall means and delta, dimension scores
and declared weights. Overall means and their difference are rounded separately;
validation preserves that producer behavior. Missing v2 components retain
`coverage_missing`; available rounded overall components still bound the delta
to their rounding uncertainty. Validation does not replace native scores.

Structured native failures are reconciled before accepting a trial: reward,
trial, verifier and nested-reward `evaluation_status`, trial exceptions, and
constituent-step failures use the pinned evaluator's data-only semantics. The
constituent helper receives captured JSON only; no filesystem collector runs.
Failures contradicting retained scores or a successful arm reject. Consistent
unscored failures remain incomplete with `execution_incomplete`, including
through standalone projection, and diagnostic prose has no public fields.

Canonical structured hashing uses UTF-8 JSON with sorted object keys, compact
separators, ASCII escaping, and no nonfinite values, prefixed `sha256:`. Source
content hashes a sorted relative-file/SHA-256 manifest under the pinned
agent-visible staging boundary. A non-null content digest must identify the
regular root `SKILL.md`, including through standalone projection. The pinned runtime ignore helper excludes
skill-owned `evals` and generated/cache/Git inputs. Historical reconstruction
reads exact local Git blobs with the equivalent authored-tree boundary; it is
`reconstructed_from_declared_revision`, never runtime-attested. Historical trees
reject generated-output markers before
any blob capture, including nested marker directories and markers under ignored
`results` or `evals` paths, matching current-source rejection without key access.
Missing Git objects remain unknown, without checkout or network fallback. Every Git read
sets `GIT_NO_LAZY_FETCH=1`, overriding an inherited lazy-fetch setting so missing
partial-clone trees and blobs cannot trigger demand fetching. It also sets
`GIT_NO_REPLACE_OBJECTS=1` so local commit, tree, or blob replacement refs cannot
substitute different bytes for a declared revision, as described in the
[Git replacement-ref documentation](https://git-scm.com/docs/git-replace).
Inherited repository-local Git environment variables and discovery/namespace
selectors are cleared before dispatch, so reads select the requested checkout,
including linked worktrees, rather than another repository or object store.
Repository-local `objects/info/alternates` and `http-alternates` are rejected.
The common object-store directory, its `info` directory or recorded absence,
and absent alternate lists remain anchored through each Git read operation and final
evidence validation. The entire object-store tree is bounded by the existing
entry limit and captured as ordinary, unlinked directories and single-link
regular files, including pack files, indexes and loose-object fanout directories.
This rejects nested links and transient object-member edits as well as alternate
lists or directory substitutions, including linked-worktree reads. Standalone
Git retrieval and inventory use the same checks and operation byte budget.
Nested Git subprocesses share their enclosing retrieval's before/after state
checks, keeping full-store revalidation work independent of source-member count.
Inventory encloses all skill reconstructions in one such operation, so full-store
revalidation is also independent of skill count and completes before publication.
Inherited `GIT_TRACE*` destinations are removed and all Trace2 targets are
explicitly disabled, including fallback targets from global/system config.
Read-only Git calls therefore cannot append diagnostic files into the checkout,
input bundle, or another caller-selected destination. Tests enable native traces
only through explicit fixture instrumentation after this environment boundary;
production provides no trace-output override. See the
[Git Trace2 target documentation](https://git-scm.com/docs/api-trace2/).
Historical skill members and authored datasets share the current-file 8 MiB byte limit. Object
types are checked offline: a supplied revision must itself be a commit, and
historical file members must be blobs. Tree, blob, or annotated-tag IDs cannot
stand in for a commit, and existing non-blob dataset paths reject. Missing exact
objects still retain unknown provenance without fetching. Object
size is checked before capturing content, and the stream enforces the same
per-file and remaining operation byte caps even if a blob grows after that check:
exactly 8 MiB is accepted, larger
objects cause contract rejection, and missing objects retain null digests and
unknown provenance. An authored dataset hash identifies exact file bytes; the
inventory derives that hash, canonical case IDs, and strict dataset validation
from one bounded buffer. Its pinned agentskills required-field checks apply to
that buffer. Pinned optional-file validators receive a local read-only path
adapter backed by captured bytes, including config, grader, Dockerfile and MCP
checks; they cannot reopen inputs to validate replacement bytes. The
native staged digest identifies enriched entries and retains
`skill-evaluator-dataset-snapshot/1`. The case cohort hash
identifies sorted canonical IDs. None of these digests substitutes for another.

Historical tree listings are streamed with an 8 MiB byte cap and a 1,000-entry
cap, including members later excluded by the authored-tree boundary. Exceeding
either cap terminates the Git process and rejects the contract before parsing
the complete listing or reading any blobs. A listing at the entry limit is
accepted; missing trees remain unknown.
Nonempty historical skill listings must contain only members beneath the
declared directory and a regular root `SKILL.md`. A blob at the declared root,
a tree without that manifest, or a linked/special manifest is rejected before
reading source blobs; none can establish exact skill-source availability.

Static aggregate pass/fail must agree with every validator's required-gate
outcome under the pinned reporter semantics. Explicit nonblocking validators
and advisory `AGENT_EVAL` skips can permit an aggregate pass; a failed blocking
validator cannot. Validator status must agree with its pass, incomplete-scan,
and advisory-skip observations.

Policy IDs hash recorded fields, patch digest, metric set, judge and attempt
policy. Recorded published policy IDs are preserved separately and never replaced
by today's policy. Behavioral and static readers reject a supplied evaluator
revision outside the supported pin. Supplied policy fields must agree with
corresponding known runtime/configuration observations: evaluator, Harbor,
Compose, Python, model/provider, grading, environment, concurrency, timeout, and
stop-on-pass. Python observations must match at the policy's declared precision
(for example, `3.13` matches `3.13.15`). Native configuration and attempt-policy
maximum/stop-on-pass values must also agree when both are known. Shared
normalized/public validation reconciles known policy-field and attempt-policy
stop-on-pass values too. Absent metadata remains unknown; compatible historical values are preserved rather than replaced
with current defaults. Judge identity remains separate from the evaluated model.
Known result/configuration/policy model identities and per-arm summary models
must agree even if the provenance model field is absent. A recorded summary
agent must be `codex`. Recorded aggregate per-arm pass data must match the
corresponding summary before its outcomes are consumed; absent carriers remain
absent. A supplied result digest algorithm must agree with the validated native
snapshot algorithm, alongside the digest and dataset summary.
Known benchmark modes must agree with known attempt maxima: standard uses one
attempt and confirmation uses three, matching the pinned producer. Every known
maximum must be positive, including standalone projection. In active standard
mode, a supplied `standard_attempts` field must agree with the known maximum;
confirmation keeps this separate historical standard-mode setting. Unknown mode
or maximum stays unknown; it is not filled from current defaults.
Arm condition IDs hash their structured fields: provenance,
target presence, workspace mode, independently identified competing skills,
instruction/build/fixture digests, and execution conditions. A changed competitor,
instruction, build, fixture or execution condition can change a condition or
policy ID without changing target content or dataset identity.

Missing execution conditions remain null. Runtime-recorded, configured,
reconstructed, reviewed-extract, synthetic and unknown provenance are distinct.
Matching incomplete identities do not establish comparability. Structural
validation does not independently authenticate execution. Repository/revision
claims in a report describe declared identity, with exact bytes verified only
when the required objects or retained snapshots are available.

Coverage keeps expected cases and attempts separate from recorded, scored and
unscored attempts. Case-detail coverage is independently complete, partial or
unavailable. Each known recorded or scored count is bounded independently by a
known expected count. Scored cannot exceed recorded when both are known;
unscored must equal their difference, and stays null if either input is unknown.
These rules apply to internal and public validation. Unknown observations remain
null. Complete behavioral evidence requires a nonempty canonical case cohort,
matching the benchmark producer's positive task count. Recovery status, native
execution checks and coverage prevent incomplete evidence promotion; unavailable references
also prevent a complete projection. Completeness describes evidence coverage,
not task success or publication eligibility. Failed rubrics, low scores and
failed with-skill deterministic gates remain valid observations. Rubric counts
and deterministic scores are checked independently; no replacement scores
are published. Skill Lift remains the native difference and Discoverability the
native skill-execution rubric. Static findings and production success remain
separate from both.
Retained trial components must reproduce their native rounded overall score.
When complete scored trial details are present, the pinned evaluator's pure
aggregation helpers must reproduce supplied arm means and summary overall scores.
Summary components and dimensions must agree with report components; report-level
runtime, trial and job failure records cannot contradict successful arm execution
or their supplied summary counterparts. Partial details retain their limitations
without inventing missing scores. These checks also run when standalone projection
reopens retained native evidence; diagnostic prose remains private.
Known arm rubric thresholds must agree with the canonical attempt-policy
threshold in shared normalized/public validation. A missing value remains null;
the validator does not fill either carrier from the other. For validation only,
it uses the arm threshold when known, otherwise the known policy threshold.
This effective threshold checks required scored outcomes for complete case
details and checks every supplied outcome against its score, including partial
case details. Zero is a known threshold; equality passes. Only when both
carriers are unknown does validation leave the score/outcome relationship unknown.

Reason codes are `results_not_supplied`, `coverage_missing`,
`execution_incomplete`, `case_details_missing`, `metadata_missing`,
`source_unavailable`, `source_mismatch`, `reference_unavailable`,
`reference_expired`, and `scan_incomplete`. Known limitations must remain in the
record. Reference availability can change to `unavailable` or `expired` without
changing its stable identity; the enclosing report must then remain incomplete.
Trial references locate recorded verifier rewards when present. For incomplete
trials without that structure, they locate the recorded verifier result (which
may be null), or the trial object when the verifier field is absent. These trial
references identify an existing value; absent scores remain null.
Discovery also accounts for retained reward members without a trial result.
They consume the shared trial-directory cap and keep that arm's case details
partial or unavailable with `case_details_missing`; an orphan reward cannot
establish a scored observation or be silently ignored in complete details.
Its payload is not parsed or promoted without a corresponding trial result.

Static detailed findings may be partial, but their counts by critical/high/medium/low
severity cannot exceed corresponding known scanner counts or aggregate totals.
The shared normalized/public validator enforces these bounds on standalone
projection too, including known scanner totals versus the aggregate. Unknown
counts do not supply an invented equality constraint.
Known per-scanner summary counts are retained in normalized and public scans;
absent scanner counts remain null. Informational findings retain their
severity without inventing a native total. The 10,000-finding cap is checked
before constructing references. Static catalog, report, and version members are
each read, parsed, and hashed once; all locators reuse that exact byte digest.
Every scan in complete static evidence must identify an available retained
reference. An incomplete or skipped scan requires `scan_incomplete` in the
shared normalized/public reasons even when another limitation already makes the
report incomplete.
Behavioral members also retain the digest of each parsed buffer, including run
reports, configuration, provenance, versions, snapshots, attempt policy,
summaries, trials, and rewards. Reference construction never reopens them. The
snapshot adapter applies the pinned loader's byte/node limits and canonical
builder checks to the captured buffer; it does not retain every parsed member.
Behavioral ingestion requires the native `codex` agent value to be an object
before dereferencing it. Malformed native object access at the CLI boundary
produces a bounded contract rejection without a traceback or local paths.
Static reports without declared or locally reconstructable exact source bytes
remain incomplete with `source_unavailable`, even when all validators finished.
The shared validator also prevents standalone projection from promoting them.

## Reviewed fixtures and retention

`fixtures/skill_evidence/podman-native` is a bounded extract of the retained
September 19 Podman benchmark, preserved before the original artifact's October
19 expiration. The original artifact is `10590172928`
(`skill-benchmark-35461602130-1`) from [run 35461602130](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/35461602130),
with recorded expiration `2026-10-19T19:11:15Z`. Its `extract-manifest.json` records
the original archive digest,
original member digests, and extract member digests. Native report fields and
reward scores are preserved; trajectories, grader prose, recommendations and
credential diagnostics are excluded. Dataset snapshot entries retain their
native staged bytes/meaning needed to validate the native snapshot digest; their
prompts never enter normalized or public output. References identify original
members and original structured locators, rather than claiming extract hashes
are hashes of original full reports.

Reviewed-extract provenance requires an exact manifest SHA-256 in the reader's
reviewed allowlist. A copied approved fixture is accepted, but a self-authored
manifest or coordinated member/manifest edits cannot grant reviewed provenance
or replace original digests. Adding an approved extract requires reviewing its
manifest identity in the source; ordinary native bundles without a manifest
retain runtime-recorded provenance.
Standalone projection also matches each reviewed reference's archive/member
metadata identity against pins derived from that approved manifest. An arbitrary
provenance label, archive hash, member, or original digest cannot grant reviewed
status; reviewed report availability requires reviewed references. This checks
declared reviewed identity, not independent execution authenticity or retention.
The pins include the complete structured locator emitted for each approved
member. A different valid location in that member cannot substitute for the
reviewed reference even if its reference ID is recomputed.
For observed behavioral evidence, every nonsucceeded arm retains the
`execution_incomplete` limitation even when other limitations already make the
record incomplete. Configured arms without observed execution remain unavailable.
Incomplete behavioral records also retain `coverage_missing` for unknown or
short recorded/scored coverage, `case_details_missing` for partial or unavailable
details, and `source_unavailable` when exact source content is absent. An unrelated
limitation cannot hide these known gaps during standalone projection.
Known task-source policy and runtime/arm values must agree. Retained reward
companions must agree with known Codex, model, and metric-set identities; absent
reward identity fields remain unknown. Identity tracking is incremental across
trials, without changing native scores or observation IDs.
Trial-result task identities are canonicalized with the pinned collector and
must agree with the retained reward and summary case. Generated task prefixes
and attempt suffixes retain the collector's case mapping. Null observation
attempt ordinals remain null and require `metadata_missing` during projection.
Every directly overlapping known policy/arm field must agree: environment,
task source, authorization policy, fixture boundary, and workspace mode.
Unknown values remain unknown. Missing run identity, staged digest, evaluator
revision, patch digest, or attempt maximum independently retains
`metadata_missing`; normalization and projection use the same identity check.
Shared policy validation accepts only the supported evaluator revision when
known. Deterministic custom grading is supported only for `gh`, with all eight
dimensions present and binary; ordinary continuous native scores are preserved.
Retained reward score fields must agree with verifier values, including absent
verifier fields. A non-null reward score cannot be attached to an observation
whose corresponding verifier score is null or missing. Trials with no reward
and missing verifier scores retain their unscored identity and limitations.
Absent custom grades remain null, and a recorded failed binary gate remains zero.
Known staged digests require the supported snapshot algorithm. Reduced behavioral
metric sets independently retain `coverage_missing`; their retained values stay
unchanged. Unavailable behavioral and static evidence retains
`results_not_supplied`, including when other limitations are also recorded.
Complete case details with a known rubric threshold require an outcome for every
scored observation; null outcomes cannot reduce the retained passed-case count.
Rubric passed-case counts and denominators must be known together; retained
counts are reconciled against complete case observations. Both may remain null.
Unknown thresholds and explicitly partial case details remain unknown.
Behavioral evidence cannot carry static scan or finding claims; those claims
must pass the static normalization contract.
Non-unavailable static records retain exactly one `catalog-total` scan carrying
the native overall status and severity totals; projection cannot drop that row.
All four aggregate severity totals remain known integers, including zero.
The aggregate retains its native Boolean pass result even while incomplete.
Its status is the native overall passed, failed, or incomplete status.
Native execution-error carriers are bounded arrays of strings. Arm counts agree
with summary cardinality plus the pinned loader's job/trial-failure additions;
raw prose remains private, and matching nonempty flags do not establish counts.
Before projection removes private native identities, each observation's references
must belong to its skill, recorded run, arm and native trial. Its trial-result
reference is required; reward and summary references retain their corresponding
member and locator boundaries. Another valid retained reference cannot substitute
for the observation's originating bytes.
For reviewed-extract references, the complete public observation payload must
match one of the 20 identities derived from the pinned extract. Changing private
trial identities and recomputing observation IDs cannot relabel retained scores,
cases or references. These payload identities remain stable after expiry; they
bind the reviewed extract, without attesting that its original execution occurred.
Retained reviewed headline metrics must match the four approved name/value pairs.
Incomplete evidence can omit measurements, but cannot replace a retained aggregate
with another in-range value while keeping reviewed references.
Reviewed source identities bind the repository, revision, owner, path, lineage
and complete content manifest. The exact approved historical identity can retain
unknown content when local objects are missing, with its source limitation.
Reviewed execution identities also bind the run, dataset, policy and complete arm
contracts. Missing authored dataset bytes retain the approved run contract with
unknown authored provenance; other relabeling rejects before projection.
Static normalization records an optional Boolean `blocking` on scan records;
legacy records without it default to blocking. Underlying scanner diagnostics
remain nonblocking when their parent validator already supplies the gate.
Projection reconciles aggregate pass and status with those retained gate decisions,
including nonblocking failures and advisory skips, while retaining native pass fields.
Static normalization keeps an immutable transient witness of its sanitized
claims, excluded from serialized records. Projection checks claims against that
witness, or renormalizes the retained bundle for a serialized input. Changed
blocking flags, pass values, counts, positions, or source metadata reject even
when the record is internally consistent. Structural schema validation alone
does not authenticate native claims. This binds captured bytes without attesting
original execution or retaining raw diagnostic prose in the public report.
Static report members must belong to the declared skill's `reports/<skill>/` path.
Aggregate, scanner and finding references use that report; catalog/version members
remain run-level references and cannot substitute for a skill's scanner evidence.
Static claims retain ordered native validator/finding positions: aggregate and
underlying diagnostics reference the whole report, validators use `results/<index>`,
and findings use their validator's `results/<index>/findings/<index>` locator.
References from another position in the same report cannot substitute for a claim.
Output creation captures the post-creation directory identity before opening it,
then compares the opened descriptor and requires a private, empty directory that
does not reuse a previously identified checkout/input root before publishing files.
Reviewed-extract members are indexed once after manifest validation, so trial,
reward, and summary references do not rescan the member list.
Each normalization shares a 64 MiB byte budget across consumed native JSON,
reviewed manifests, historical source listings/blobs, and authored datasets.
This includes the optional static `versions.json` member.
Inventory independently shares the same 64 MiB operation budget across source
hashing, front matter, lock metadata, datasets, competing skills and native
optional-file checks. Each member is captured once and reused for hashing and
validation, including the captured `gh` checks. Standalone `gh` helpers retain
their optional keyword-only `read_bytes` hooks and existing default callers.
Optional ownership metadata and overlay presence use no-follow stat relative to
anchored parent descriptors. The parent directory state is retained and checked
around presence decisions and before publication; transiently hidden lock files,
overlay roots or overlay parents cannot be accepted as an absent baseline.
Inventory rejects generated-output markers anywhere in inventoried source trees
before the pinned visibility selector can authenticate them or access a private
marker key. Standalone source-snapshot verification applies that same early
marker rejection and the shared 64 MiB operation budget, alongside per-file and
tree limits; unrelated generated directories retain their existing behavior.
File/object size is charged before content capture, and unexpected file growth
is charged before parsing; per-file and historical-object limits remain 8 MiB.
Static and behavioral normalization retain the directory device/inode identities
collected during the initial bounded tree scan. Every later member read must
descend from those same directories; replacing a scanned bundle or ancestor
rejects before content capture rather than establishing a new read baseline.
Historical tree listings use unbuffered streaming reads limited by the remaining
budget and their independent bound. At most one extra byte distinguishes EOF
from excess; rejection terminates Git before parsing or blob capture.
Incomplete recovery provenance may omit identity carriers, but every supplied
schema version, skill, and benchmark mode must match the supported contract
before optional policy, revision, metric, and digest fields are retained.

The approved manifest records no durable retention of original members. At or
after its recorded UTC expiration, normalization marks its original references
`expired` and adds `reference_expired`, keeping the report incomplete. It samples
time once for each normalization, preserving native measurements and stable
reference identities. Trusted expiry metadata is keyed by the approved artifact
ID and archive digest and checked against the pinned manifest. Validation
recognizes reserved reviewed artifact IDs independently of serialized
provenance; they must retain their approved archive digest, reviewed provenance
and complete member identity. Clearing those fields cannot disable expiry or
the reviewed payload checks. Ordinary runtime artifacts retain their own rules.
Shared internal and public validation recheck that deadline; standalone projection samples UTC
once and reuses it for both checks. A record serialized before expiry must
explicitly mark every reviewed reference `expired`, retain `reference_expired`,
and report supporting-evidence availability as `incomplete` when projected at
or after the deadline. Contradictory records reject before output allocation;
projection does not silently rewrite them. Reference retrieval also rechecks
the trusted deadline before opening member bytes; serialized `available` cannot
authorize a read at or after expiration. Incomplete supporting-evidence availability
does not invalidate a completed evaluation: execution status,
historical scores, trial coverage, rubric counts, and identities remain unchanged.
Analysis sufficiency is outside this contract.
Retained reduced extract bytes do not establish continued
availability of the original members. An external retention service or override
is outside this contract.

The fixture retains metrics `0.1207`, `0.7730`, `0.9600`, `0.6937`, ten paired
case IDs, 20 scored attempts, 10/10 versus 8/10 native rubric counts, case-2 scores
`0.6896` versus `0.7242`, the historical patch/policy and snapshot digest. Native
trial UUIDs and names remain available internally. The source manifest is
reconstructed from exact declared Git objects; it is not a runtime attestation.
The `gh-no-model.json` record is configured/unmeasured. `static-synthetic` is
clearly synthetic and generated with the pinned native JSON reporter; it tests
an incomplete scanner and a synthetic finding, without effectiveness claims.
No test requires remote artifacts, credentials, Docker, network or inference.

A later analyst retrieves evidence as follows:

1. Resolve the canonical case/attempt and native trial through the internal
   observation mapping and `references` manifest.
2. Obtain the original GitHub artifact while available, or an externally retained
   evaluation bundle. Resolve its artifact ID using the originating run's artifact
   listing or the external retention index. For the reviewed Podman fixture, use
   `gh api repos/thetechgy/agent-engineering-baseline/actions/artifacts/10590172928/zip`
   to retrieve the original archive while it remains available. Verify the archive SHA-256 when
   recorded, then extract using a safe archive reader into a private ordinary
   directory. No artifact path or script is executed.
3. Verify original member SHA-256 and the structured locator before reading
   evidence. The module's `verify_reference(bundle, record)` verifies both against
   an already safely extracted original bundle, parsing the same bounded bytes
   that passed digest verification rather than reopening the member. Reviewed
   extracts also verify their own member hashes before normalization. They cannot supply discarded
   raw prose or authenticate an unavailable original archive.
4. Obtain exact skill content through the recorded repository/revision/source
   path or an externally retained source snapshot. Verify ownership and the
   recorded manifest. `verify_source_snapshot(snapshot, source)` compares the
   pinned agent-visible manifest; mismatches fail. Never substitute today's files.
5. Record missing, expired, unretained or reconstructed evidence explicitly.
   Never substitute another case/trial's output. References alone cannot recover
   discarded bytes.

Normalization neither copies raw evidence into public output nor deletes it.
Before later artifact cleanup, retain needed trial evidence and exact source
content outside the checkout/public report, or mark references unavailable. The
later artifact-hardening change must settle durable retention before cleanup and
publication. This change supplies a manifest and retrieval contract, not an
archive service, retention operation, analyst, analysis, comparisons,
recommendations, reporting UI, or raw-evidence publication. Evaluator/scoring
semantics, paid invocation, workflows, artifact uploads/retention, managed skills,
published metrics, and `gh-pages` remain unchanged.
