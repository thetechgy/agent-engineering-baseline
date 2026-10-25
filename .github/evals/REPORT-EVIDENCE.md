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
The first metadata lookup is also inside cleanup scope. A transient failure
permits one recovery lookup only while the captured parent-entry state matches;
cleanup leaves the reservation untouched if it cannot safely establish identity.
If the initial parent-state read itself fails, one metadata-only retry may
establish the cleanup guard; the original operation still rejects. Persistent
metadata failure does not retry creation or publish members, and leaves the
unidentified empty reservation untouched.
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
The pinned native recognition and optional-file validators share a captured-tree
path adapter. Existence, directory membership and immediate child listings come
from the bounded scan; native checks never enumerate a live replacement tree.
Content reads remain cached and bounded, and final state checks reject substituted
or changed trees before publication. Native known, unknown, hidden and environment
entry recognition remains unchanged.
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
before publication. Private capture guards survive normalization, projection and
in-memory copies without entering serialized records. The output writer checks
them before allocating a destination and again after all output streams close;
a changed input rejects and removes the partial output. Standalone projection
also captures its input JSON through this boundary. Shared guards are checked
once per boundary, without recapturing bytes or multiplying the read budget.
In-place edits and restores reject even when modification
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

## CI public artifact handoff

`skill_reports.py` adds a reporting-only handoff using the same pinned Python
environment. It discovers inventory once, normalizes the original native JSON,
projects it in memory, and validates each public record immediately before
staging. Inventory and reports also undergo credential-pattern detection on
string values using the pinned text redactor. A match rejects the bundle without
echoing the value; key-based diagnostic redaction never rewrites scores,
authorization fields, or authenticated identities in this path.
Exact display titles emitted by the pinned static reporter map to schema-v1
scanner identifiers (`SCHEMA`, `VERSION`, `SECURITY`, `PII`, `LICENSE`,
`CODE_RISK`, `SECRETS`, `HYGIENE`, `UNICODE`). Existing token identifiers pass
through unchanged; unrecognized free-text titles reject. Scan and finding
references still bind their original native report positions and bytes.
SECURITY findings formatted by the pinned evaluator as `pattern (rule-id)`
publish only the validated rule identifier, for example `P2` from
`Hidden Instructions (P2)`. Existing token check names remain unchanged;
malformed identifiers, control characters, and other free-text check names
reject. The display label remains available through the original native
finding reference rather than becoming public prose.

The [SkillSpector 2.13.1 assessment](SKILLSPECTOR-2.13.1.md) records the controlled
upgrade comparison, remaining findings, completeness limitations and reproduction
commands. SkillEvaluator 0.3.0 does not retain the scanner's detailed completeness
ledger in native reports; the public projection cannot reconstruct it. The study
retains raw diagnostics privately. Routine collection and public schemas remain
unchanged. A 100% file-coverage counter can coexist with partial analysis when
reference or analyzer limitations remain; use the native completeness state too.

### Quality summary and interpretation

The quality job reports native collection/dataset contracts separately from
findings. The `catalog` command retains blocking exit/report/dataset checks and
bounded, fixed failure categories with affected skill names. Native findings
remain advisory. The richer summary is emitted by `public-quality` only after
all discovered local skills pass the existing public projection and staging
contracts; it consumes those same projections without another scan or model call.
A successful projection cannot override an earlier infrastructure failure.
An always-run availability step explicitly reports failed, cancelled or skipped
projection, including an unavailable evaluator environment. Unavailable reporting
is never a zero-finding result. Native artifacts remain available under the
existing upload behavior; missing artifacts must be investigated in the collection
and upload steps rather than assumed present.

The summary shows native passed/failed/incomplete assessments, aggregate C/H/M/L
counts, the separate `SECURITY` subset, incomplete/skipped/unavailable security
evidence, per-skill nonpassing validator/tool identifiers and suite configuration.
`SECURITY` denotes the pinned pipeline's SkillSpector integration, not every
validator. Tool incompleteness markers, validator totals, aggregate totals and
structured detail records are separate views of evidence, never added together.
Behavioral suites are not executed by the quality job. Its inventory covers local
skills and configured upstream evaluation overlays; it does not enumerate every
installed upstream skill. Deployed copies are not additional assessed skills.

Critical/high previews group by severity, validator and check identity, ordered
CRITICAL then HIGH, then validator/rule. Eight groups are displayed; omitted group
and finding counts are explicit by severity. Frequency does not determine order.
Affected skill previews show six names and an explicit remaining count. Missing
rule identities stay separate by record/reference. These are rule roll-ups, not
finding deduplication: every individual finding stays in existing evidence.
Counts mean retained finding records, not raw scanner occurrence spans. References
are the existing full record/reference identities; look them up in the selected
public report's `references` array for the exact native member, JSON locator and
digest. The run-artifact link uses validated repository/run identifiers; native
members remain inert text, not invented artifact deep links.

Scanner severity and actual engineering significance remain distinct. For example,
`SCHEMA / author_missing` retains its native HIGH severity while explaining that
author metadata is optional in the [Agent Skills specification](https://agentskills.io/specification#metadata-field).
That flag alone establishes neither a specification defect nor a reason to edit
the skill. Fixed investigation guidance identifies the evidence to inspect; it
does not confirm vulnerabilities, classify false positives, override severities
or automatically recommend skill changes. Static quality/efficiency heuristics
are not measurements of token use, execution efficiency or behavioral benefit.

The shared presentation helpers operate on existing validated static projections.
Analysis JSON, public schemas, findings and reference identities are unchanged.
Compact CI summary rows share the existing 64 MiB analysis bound. Markdown
retains its 1 MiB output bound; failures do not print partial findings
summaries. No raw scanner prose, matched sensitive text, diagnostic exceptions,
prompts or trajectories are added to Actions summaries.

Representative offline commands, run from the checkout with the existing
evaluator environment, are:

```bash
export GITHUB_WORKSPACE="$(pwd)"
public_parent="$(mktemp -d /tmp/skill-public.XXXXXXXX)"

# Native quality collection must cover every discovered local authored skill.
"$SKILL_EVALUATOR_PYTHON" .github/scripts/skill_reports.py public-quality \
  /tmp/skill-quality "$public_parent/quality"

# Replay the reviewed ten-case, twenty-attempt Podman extract without inference.
"$SKILL_EVALUATOR_PYTHON" .github/scripts/skill_reports.py public-benchmark \
  .github/tests/fixtures/skill_evidence/podman-native podman standard \
  "$public_parent/podman"

# Select explicitly when an ordinary native bundle contains multiple runs.
"$SKILL_EVALUATOR_PYTHON" .github/scripts/skill_reports.py public-benchmark \
  /tmp/skill-benchmark podman confirmation "$public_parent/confirmation" \
  --run NATIVE_RUN_ID
```

Each destination must be new, with an existing trusted ordinary parent outside
the checkout and native input tree. The resulting bundles contain exactly:

```text
quality/
  inventory/inventory.json
  skills/<discovered-local-skill>/static/public-report.json

podman/
  inventory/inventory.json
  skills/podman/behavioral/20260919_183432_2598_6c30a245af5c/public-report.json
```

The inventory includes imported overlays separately from local sources and
generated deployment copies. Configured but unmeasured `gh` retains its 24-case
suite and unavailable measurement; the Podman example creates no `gh`
measurement. Quality catalog membership must exactly equal the discovered local
skill set. Missing, extra, or duplicate members reject the entire bundle with an
explicit unavailable summary. Per-skill failures after earlier successful
records remove owned staging. No `evidence.json`, native reports, raw logs,
trajectories, grader prose, or other files enter these bundles. Captured input
guards and the exact expected file set are checked before reporting readiness.

Behavioral reporting opts into the ordinary native layout. Standalone
`normalize --kind behavioral --native-layout` exposes the same option; the
default reader remains strict. The opt-in excludes only
`results/<selected-skill>/latest` when it is an alias and ordinary
`results/<selected-skill>/<run>/_harbor-jobs` and `_harbor-tasks` directories.
It never resolves the alias or traverses excluded contents. Linked runtime
directory roots and unsafe consumed members still reject. One canonical run can
be selected automatically; multiple runs require `--run`, with no chronology or
`latest` fallback. Missing results produce a bounded unavailable summary and
no fabricated public record. Known mode/attempt metadata must agree with the
requested standard or confirmation mode; missing metadata remains unknown.

The quality workflow records its actual checked-out repository and revision
through the pinned evaluator's source-provenance flags during collection. After
catalog handling it generates public reports, including valid incomplete scans.
Reporting errors fail the quality job; the existing diagnostic upload remains
unconditional. After generation, checkout integrity must pass before public
upload; a failed or skipped integrity check prevents publication even when
generation succeeded. The public artifact is named
`skill-public-quality-<workflow-run>-<attempt>` and retained for 14 days.

The benchmark workflow generates public reports after the existing diagnostic
and standard-metric uploads, including supported recovered incomplete runs.
Generation and upload each have a three-minute timeout and are advisory.
An advisory one-minute checkout-integrity check follows public generation.
Upload requires successful outcomes from generation, this final check, and
the existing blocking native checkout-integrity check. Gates use original
`outcome` values, so a failed step's successful advisory conclusion cannot
publish partial or changed-source output. Failures
or skipped reporting generate a warning and summary status; reporting errors
preserve native history eligibility. Native evaluation failures remain blocking.
The artifact is named
`skill-public-benchmark-<skill>-<mode>-<workflow-run>-<attempt>` and retained for
30 days. Uploads allowlist only the inventory and corresponding skill report
paths shown above. Hard cancellation or runner loss can prevent final steps
and cleanup from executing.

Incomplete evidence remains publishable when it satisfies schema v1. Low native
scores and failed rubric cases retain their measurements; missing scanner,
identity, coverage, source, or execution evidence retains its limitation reasons.
Contradictory or unsafe input cannot become a ready public bundle. Native
evaluation, recovery, diagnostics, policy/runtime pins, four numeric history
metrics, history gates, approvals, and Pages publishing retain their existing
behavior.

Downstream analysis can pair public and diagnostic artifacts by the workflow
run and attempt in their names, then use the report's native run, source,
dataset, policy, observation, and reference identities. Public reference hashes
describe original native members; redacted diagnostic bytes can differ. Verify
original bytes and exact source revisions using the retrieval contract below,
and preserve explicit unavailable or expired evidence. This handoff does not
retain original qualitative evidence durably, run analysis or inference, create
recommendations, or supply a report UI or new history service.

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

Without a dataset snapshot, fallback cohort identities are the bounded canonical
union of both arms' supplied report rollups and captured arm summaries. Either
arm may supply the surviving cases; disjoint partial case sets are reconciled
together. Aggregate/summary contradictions still reject, and missing snapshot
identity remains unknown with `metadata_missing`; it is never reconstructed from
task-directory names. Each summary is captured only once under the shared budget.

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
policy. Current benchmark admission requires Compose 5.6.1; historical 5.0.2
measurements retain their original runtime, policy and published identities.
The [Compose security assessment](COMPOSE-5.6.1.md) records qualification evidence.
A changed Compose version produces a distinct policy/history identity and blocks
direct cross-run comparison. These rules do not retroactively qualify old runs.

Recorded published policy IDs are preserved separately and never replaced
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
durable retention of qualitative evidence remains a later design concern; this
public handoff does not claim to retain it or recover unavailable bytes. This
public handoff supplies a manifest and retrieval contract. The bounded offline
analyzer below consumes those records separately. Archive services, retention
operations, expert diagnosis, skill recommendations, reporting UI, and raw-evidence
publication remain outside these contracts. Evaluator/scoring
semantics, paid invocation, native diagnostic uploads/retention, managed skills,
published metrics, and `gh-pages` remain unchanged by the public artifact handoff.

## Bounded offline analysis (issue #58)

`skill_analysis.py` consumes the validated public bundles produced above. It
reads data only: no history lookup, “latest” selection, network, inference,
graders, scanners, subprocesses, skill edits, or publication. Public schema v1,
native scoring, APM artifacts, workflows, artifact handoff, and history publishing
remain unchanged. Use the existing pinned evaluator Python; no dependency is added.

```bash
"$SKILL_EVALUATOR_PYTHON" .github/scripts/skill_analysis.py \
  --input /tmp/public-quality \
  --input /tmp/public-benchmark \
  --output /tmp/new-analysis
```

Every input root must contain an inventory. Accepted layouts are:

- Public artifact bundle: `inventory/inventory.json` and zero or more
  `skills/<skill>/static/public-report.json` or
  `skills/<skill>/behavioral/<run>/public-report.json` members.
- Flat single-record bundle: `inventory.json` and an optional `public-report.json`.
  This permits combining a separately produced inventory and public projection.
  Do not include private `evidence.json` or native reports in this directory.

Other files, unexpected empty directories, filename/record skill, kind or run
mismatches, missing inventories, and reports without an accompanying inventory
skill reject. Inventory revision/content/suite snapshots are configuration
context; an accompanying historical report may name different revisions or
conditions. No “current” or “latest” snapshot is selected. Distinct snapshots are
retained separately. Identical semantic records deduplicate across roots without
increasing trial or run counts. Conflicting records for a behavioral skill/run or
an original static artifact/member reject, including inconsistent measurements
or support claims. Unmeasured records without a run remain configuration evidence.

The analyzer permits at most 32 supplied roots, 128 unique public reports,
1,000 distinct skills and 100,000 aggregate scanned entries, including directories.
Overlapping roots reject; repeated identical roots collapse after the supplied-root
limit check. All captured bytes share the existing 64 MiB operation budget and
8 MiB per-member read bound. Existing public-record bounds also apply, including
1 MiB per public report, 1,000 cases, 10,000 observations, and reference/scan limits.
Malformed, unsafe, credential-pattern-bearing, conflicting, and oversized inputs
reject without truncation. Supplied roots and their members remain read-only.

The CLI prints a new directory containing exactly `analysis.json` and `summary.md`.
Omitting `--output` uses a private temporary directory. Existing secure writer
rules protect every input root, the checkout, ancestor ownership, no-follow reads
and writes, private permissions, new destinations, and cleanup. Capture guards
are checked before allocation and after both streams close. JSON output is capped
at 64 MiB and Markdown at 1 MiB; exceeding either rejects before publication.
Contract failures return exit status 1 with a fixed message that excludes input
content and paths. Unsupported descriptor platforms reject; Linux publication
is tested. This does not establish Windows output support.

### Analysis schema and identity

The analysis schema is independently versioned (`schema_version: 1`), with method
`bounded-descriptive-skill-analysis/1`. It is a closed projection, validated by
exact canonical recomputation from the captured public record index. Unknown or
extra fields at any level, changed values, or dangling links reject. Top-level
fields are:

| Field | Contract |
| --- | --- |
| `schema_version`, `method_version` | Analysis schema and calculation/template method identities, independent of public schema v1. |
| `input_provenance` | Sorted manifests of relative artifact members, exact raw-byte SHA-256, and semantic `record_id`. Each manifest's ID hashes its members. Duplicate identical manifests collapse. |
| `record_index` | One compact row per semantic record: `id`, `kind`, `skill`, `run_id`. Inventory rows have null skill/run. |
| `skills` | Sorted skill rows containing separate `configurations`, `static_results`, `behavioral_results`, `comparison_status`, and bounded `comparisons`. |
| `comparison_scope` | Eligible, maximum, and performed pair counts and explicit scope limitations. |
| `findings` | Stable, typed evidence-backed findings, ordered by semantic ID. |

Configuration context identifies source owner/origin/revision/lineage, content
digest/provenance and configured suite digest/owner/path/case count, linked to
inventory record IDs. It omits source manifests and case lists already supplied
by the original records. Static results retain scanner status, blocking decisions,
native severity counts and detailed findings separately; aggregate, scanner and
detailed counts are never added together. Behavioral results retain native metrics,
policy fields, attempt mode/maximum/stopping/threshold, model/judge/runtime, dataset
identities, arm conditions, execution/error counts, expected/recorded/scored/unscored
coverage, rubric counts and availability limitations. Competing source manifests
are reduced to identity/context fields. Full records, source manifests, prompts,
raw prose and unused reference tables are not embedded.

Case rows retain canonical `case_id`, arm means, contributing observation IDs,
reference IDs, with-minus-without differences, and explicit unavailable reasons.
Derived quantities have decimal `value`, four-place `display`, and pre-display
`direction` (`positive`, `negative`, `zero`). Decimal calculations use 400-digit
intermediate precision and round-half-even display, preserving even the smallest
validated float contribution beside a score of 1 through the bounded attempt
means. This is descriptive arithmetic, not a change to evaluator scoring.

Findings have `id`, `kind`, `skill`, `record_ids`, `case_ids`, `observation_ids`,
`reference_ids`, `observed`, `uncertainty`, `importance`, and `next_step`. Kind and
observed quantities come from fixed producers: case/run regressions, failed
behavioral gates or blocking static checks, incomplete execution/scans, unavailable
support, configured-unmeasured skills, and comparison limitations. Importance is
`mandatory`, `investigate`, or `context`. Fixed next-step codes are
`inspect_original_case_evidence`, `inspect_original_run_evidence`,
`inspect_gate_evidence`, `inspect_original_scanner_evidence`,
`complete_execution_and_reproject`, `complete_scans_and_reproject`,
`retain_or_reacquire_exact_evidence`, `supply_model_backed_public_report`,
`verify_benchmark_identities`, `supply_two_intended_runs`, and
`supply_at_most_16_skill_pairs`. These are investigation/validation actions, not
claims about causes or skill-edit recommendations. Links resolve through the
retained public records; observations/references from different records are
qualified by those record links.

Raw provenance hashes cover exact captured bytes. All analytical record,
configuration, pair and finding IDs use the existing canonical JSON identity
function over validated values or analytical subjects. Raw hashes never select
comparisons or influence analytical ordering or findings. Absolute input paths
and generated timestamps are omitted. Input/discovery reordering is byte-identical.
Harmless JSON whitespace/object-key reordering changes only raw provenance in
`analysis.json`; semantic IDs, analytical sections, findings and `summary.md` stay
unchanged. Arrays retain their public-record semantics.

### Within-run interpretation

The four native metrics retain their published names and values exactly:
Skill Lift is a difference on the evaluator score scale; Effectiveness,
Correctness and Discoverability are native rubric dimensions. None is reconstructed
from trial scores. In the retained Podman example, native Skill Lift is `+0.1207`,
while the arithmetic mean of published case differences is `0.12075`.

Single-attempt cases require known, scored observations in both arms. Repeated
cases compare descriptive arm means only when every planned ordinal is present
and scored, and stopping is known nonadaptive. Missing scores/attempts, unknown
maxima, and repeated adaptive or unknown stopping make the comparison unavailable.
No experimental pairing of trials is inferred. A complete case in a partial run
can remain descriptively comparable, with that run's limitations retained.
Negative differences are identified before display rounding, so `-0.0000` can
still denote a small observed regression. Rubric case passes and mandatory
binary gates remain separate. Failed gates list component names and observation
IDs prominently; missing gate evidence stays unknown. A rubric pass cannot mask
a recorded gate failure. Static checks/scanner gaps are separate from performance.

The historical fixture produces native `+0.1207`, 10/10 versus 8/10 rubric case
passes, 10 matched cases, and 20 scored trials. Case 2 regresses by `-0.0346` and
case 7 by `-0.0134` (with-minus-without). `gh` is configured with 24 cases and has
no supplied model-backed measurement. These are supplied-evidence statements,
not absence claims about the repository's entire history.

Reference expiry or unavailable source support does not erase valid completed
numeric observations. Stale reviewed-reference availability claims reject under
existing public validation. Refresh such public projections using the existing
native-to-public normalization/projection path, preserving scores and execution
coverage while declaring expired/unavailable support. The analyzer does not
rewrite or fetch stale evidence.

### Bounded cross-run comparisons

For each logical skill, exactly two distinct measured runs yield one pair.
Fewer than two yield `insufficient_run_evidence`; more than two yield
`comparison_limit_exceeded`, with no pairs enumerated and a request to supply
the intended two runs. Configured-but-unmeasured records do not count as runs.
If more than 16 skills otherwise have eligible pairs, **none** of the cross-run
comparisons are computed. Individual analyses still succeed, and an invocation
finding plus per-skill `invocation_comparison_limit_exceeded` statuses explain the
limit. No arbitrary subset, chronology, trend, or historical “latest” is inferred.

The CLI builds case/condition indexes once per report. Each accepted
pair compares bounded condition fields and joins at most 1,000 canonical case IDs:
at most 16 condition comparisons and 16,000 joined cases per invocation. Construction
inside the validation boundary avoids a second comparison pass in the CLI.
Independent validation of a saved result performs its own bounded calculation
from captured originals.
Endpoints sort by semantic record ID, and all numerical cross-run differences are
explicitly **right-minus-left**, never labeled chronological improvement.

| Classification | Interpretation |
| --- | --- |
| `directly_comparable` | Known compatible source origin/recorded lineage; complete numeric execution and ordinal coverage; matching dataset/cohort, supported scoring/evaluator/patch, model/judge, runtime, attempts, baseline, competitors, instructions, build, fixture and applicable conditions. Descriptive native and case differences are shown. |
| `exploratory` | Essential scoring/dataset identities match, but unknown supplementary conditions or incomplete execution prevent controlled comparison. Individual results are shown side by side; cross-run numerical differences and improvement/trend verdicts are suppressed. |
| `incompatible_or_unknown` | Essential identity is missing or conflicting, or a known material benchmark condition differs. Preserve individual results and explain unsupported comparison. |

Essential fields include known run identity, authored/staged/cohort dataset
digests and algorithm, evaluator revision, patch digest, metric set, grading,
model/provider, attempt mode/maximum/stopping/threshold and judge enablement.
Judge model/provider are required when enabled or unknown; a known disabled judge
does not require inapplicable model/provider. Unsupported evaluator revisions
reject before classification. Known condition differences are incompatible;
missing supplementary conditions are exploratory. Target content/revision and
`upstream_revision` may intentionally change and are not benchmark identities.
Known source origins compare owner/repository/source path; ownership conversions
require recorded lineage naming an exact original revision, or a shared recorded
lineage. Names alone are insufficient. Unknown target content restricts direct
comparison. Reference availability/expiry is not a benchmark condition.

Default grading outside the `gh` suite compares native runtime/policy fields and both arms' workspace,
competitors, instruction/build/fixture digests, environment, base-image mode and
rubric threshold. Default grading does not require absent `gh` broker,
authorization, task-build or competing-revision fields; additional supplied
conditions are still compared. The `gh` suite and non-default grading require the custom grading
identity and applicable deterministic-gate, fixture-boundary, authorization,
task-source/build and competing-revision conditions. Public schema v1 has **no
dedicated custom-grader content identity**, so custom grading, including `gh`,
cannot currently qualify as direct. A grading label, target revision, or patch
hash cannot substitute for that missing identity. Current producer gaps will
legitimately restrict direct comparisons. Direct classification describes
compatibility of recorded conditions; it does not prove causality or repeatability.

### Independent validation and downstream evidence

To validate a saved analysis, capture the exact original public bundles again:

```python
from pathlib import Path
import skill_analysis  # .github/scripts on sys.path; pinned evaluator environment
import skill_evidence

captured = skill_analysis.capture_inputs([Path('/tmp/public-quality'),
                                         Path('/tmp/public-benchmark')])
# Preserve the 64 MiB analysis bound during both safe reading and strict parsing.
raw = skill_evidence.read_bytes(Path('/tmp/new-analysis/analysis.json'),
                               limit=skill_analysis.JSON_LIMIT)
result = skill_evidence.parse_json(raw, limit=skill_analysis.JSON_LIMIT)
skill_analysis.validate_analysis(result, captured)
assert Path('/tmp/new-analysis/summary.md').read_bytes() == skill_analysis.render_summary(result)
```

The strict parser rejects duplicate keys at every nesting level, nonfinite
numbers, and excessive depth before semantic validation. Its optional `limit`
preserves the existing 8 MiB default for evidence callers; saved analysis uses
the explicit 64 MiB bound above.

`validate_analysis(result, validated_records)` revalidates public records and
semantic IDs, verifies closed provenance/index membership, and recomputes the
entire closed projection against those originals. It checks native values/types,
arithmetic, denominators, gates, links, comparison selection/classification and
findings.
Passing `None` as the result constructs the authoritative validated projection;
the CLI uses this mode to compute each pair once. For a saved result, always pass
that result to request independent recomputation.

Formatting-altered bundles retain semantic analyses but cannot validate
an old raw provenance manifest as byte-identical input. An analysis alone does
not carry enough data for independent semantic validation: retain or reacquire
the exact public bundles named by its manifests. For qualitative expert analysis,
also obtain the appropriate original trials/scanner evidence, exact target and
competing source content, and recorded benchmark conditions, following the
retrieval/digest/locator/source checks above. Never replace original evidence with
today's source or another trial. Unavailable, expired, unretained or reconstructed
support remains explicit. The summary is a fixed template from validated analysis,
not expert causal diagnosis or a readiness assessment.

## Private offline HTML report

`.github/scripts/skill_report.py` is the first consolidated presentation layer.
Its base inputs are validated public bundles and their saved `analysis.json`.
Optional private analyst attachments undergo separate original-tooling validation.
It calls the existing analyzer's independent semantic validator at the rendering
boundary; it does not duplicate native normalization, case arithmetic, findings,
comparison selection or analyst decisions. Both original public records and
saved analysis use bounded, strict, no-follow reads. Duplicate JSON keys, corrupt
or stale analysis, contradictory identities, extra public fields and unsafe
inputs reject before output. Input state guards run again at publication.

From the checkout, using the existing pinned evaluator Python environment:

```bash
report_parent="$(mktemp -d /tmp/skill-report.XXXXXXXX)"

# Use previously obtained public bundles, not native diagnostic directories.
"$SKILL_EVALUATOR_PYTHON" -B .github/scripts/skill_analysis.py \
  --input /tmp/skill-public-quality \
  --input /tmp/skill-public-benchmark \
  --output "$report_parent/analysis"

"$SKILL_EVALUATOR_PYTHON" -B .github/scripts/skill_report.py \
  --input /tmp/skill-public-quality \
  --input /tmp/skill-public-benchmark \
  --analysis "$report_parent/analysis/analysis.json" \
  --output "$report_parent/html"

xdg-open "$report_parent/html/report.html"
```

Replace the two input paths with the public bundles you have retained; repeat
`--input` for more roots. Use exactly the same bundles for analysis and report
generation. Omit `--output` to let the secure helper reserve a private temporary
directory. Explicit destinations must be new and have a trusted existing parent
outside the checkout, evidence trees and saved-analysis directory. The only
output is `report.html`, in a mode-0700 directory with a mode-0600 file. The
existing descriptor/ownership boundary is verified on Linux; Windows output
support is not established. Open the file directly in a local browser using the
browser's Open File command. No web server is needed. The appearance menu offers system default, light and dark; its choice
lasts for the open document. With JavaScript disabled the report remains readable
and follows the system theme. Native disclosures reveal detailed support.

The executive overview and skill directory show every skill represented in the
supplied inventories or public reports. The opening summarizes measured native
results and presents failed, passed and unknown mandatory gate counts together,
explicitly limited to recorded observations. Missing attempts, partial or unknown
execution coverage, unmeasured runs and configured skills without supplied
results keep the safety banner incomplete; missing outcomes are excluded from
these counts rather than assigned invented totals. No recorded outcomes also
keeps the banner incomplete. Zero recorded failures never establishes safety.
Gate coverage uses execution state, expected and recorded attempts, observation
detail coverage and attempt identities independently of headline metrics and
rubric scores. Failed, incomplete or unknown execution remains incomplete even
when all recorded gate outcomes passed.
The directory distinguishes
measured results, configured suites without supplied results, and skills without
a configured suite (or missing configuration). Configured counts are per arm,
not completed trials. Inventory configurations and historical
evaluated sources retain separate identities. Skills without a suite or measured
run have explicit sections; no performance score is inferred. Each measured run
shows native metrics, separate with/without-skill expected and observed coverage,
rubric denominators, complete-case descriptive means, failed mandatory gates and
unknown gates. Effectiveness, Correctness and Discoverability are the native
with-skill dimensions; the public contract does not supply corresponding
without-skill headline dimensions. Skill Lift remains its original native value.
Static scanner states, blocking flags, severity counts and structured findings
are separate from behavioral performance. Counts can exceed the number of public
finding details; omitted scanner prose is not reconstructed.

The overview now exposes static-quality totals, native outcomes, security coverage
limitations and grouped critical/high flags with direct links to individual
structured findings and exact original references. The coverage directory links
each static record with its native outcome and severity counts. Multiple static
records for the same skill remain separate: headline finding totals are withheld
rather than selecting a current snapshot or counting repeated findings as new.
Missing static results are explicit. Detailed tables retain every finding, ordered
by severity for presentation. A native required check is evaluator policy, not
the advisory CI finding policy or a scanner process outcome. Complete failing
assessments and partial assessments with retained findings remain distinguishable.
The offline Markdown summary uses the same rule groups and limitations.

"No incompleteness reported" describes the retained native state; it does not
establish exhaustive inspection. Detailed SkillSpector reasons, analyzer states,
raw occurrence spans and separate process outcomes cannot be reconstructed from
this public contract. Investigation guidance asks readers to characterize the
limitation before regeneration; a rerun alone may not resolve a tooling limitation.

Investigation priorities retain the analyzer's deterministic findings,
importance and next-step codes. Mandatory outcomes precede investigations;
routine context findings remain under “Evidence gaps and comparison limits”.
The overview also exposes lower recorded security-component scores only when
both arms have a complete single planned attempt and a supplied security score.
It displays the original component values with observation links, without new
means, deltas, finding contracts or risk scores. Missing or multi-attempt
comparisons stay in the observation evidence. Security judgments warrant
inspection separately from command-wrapper or harness concerns; neither is
verified execution or proof of an instruction defect.
Finding disclosures retain exact quantities, uncertainty and support identities,
with internal links to records, observations and original references. Long link
identities use display prefixes; full identities remain in disclosures. Links
reveal containing disclosures with JavaScript; native disclosures and fragment
targets remain available without it. Original
member paths and locators are inert text. Public reference availability does not
prove local possession or authenticate redacted diagnostic bytes. Expired
references stay expired, and retained reviewed extracts do not become complete
originals. If availability changes, regenerate public evidence and analysis
through the existing contracts; this renderer does not repair stale records.

Cross-run results appear only when the analyzer supplies them. Exactly two
measured runs per skill and at most 16 eligible pairs per invocation are supported.
Only directly comparable conditions admit right-minus-left deltas. Exploratory
or incompatible/unknown pairs retain classifications and reason codes without
invented deltas. Left/right order follows semantic identity, not chronology.
There are no time trends, causal explanations, statistical claims, cross-suite
rankings or recommendations to edit a skill. A grader failure is not automatically
an instruction defect. All conclusions are limited to supplied evidence;
unrepresented skills or omitted runs cannot be discovered from these bundles.

When validated analyst attachments are supplied, the overview exposes their
proposed action scopes and separately attributed assessment verdicts and scores.
An unscored assessment stays unscored. Full analyst conclusions and actions
precede detailed run evidence; rationale, citations and provenance remain in
disclosures. These are model interpretations and supplied opinions, separate
from deterministic findings. They cannot establish authenticated human approval,
change `not_quality_qualified`, authorize execution or enable publication.

Presentation labels translate only recognized codes: for example,
`pass_substantive_usefulness_demonstrated` becomes “Substantive usefulness pass”
and `not_quality_qualified` becomes “Not quality qualified”. Analyst dispositions
are labeled as interpretations and recommendation categories as proposals.
Unfamiliar verdicts, assessor attribution and supplied narratives remain verbatim.
The overview and detailed assessments use the same supplied AI, unauthenticated
human or unknown-author category and show assigned scores as “9 out of 10”.
Unscored assessments stay unscored. Supporting disclosures retain original
assessment fields, disposition and recommendation codes, full identities,
citations, provenance and expiration information.

Evaluator-reported metrics retain their original numeric precision. Evaluation
groups (“arms”), grading criteria (“rubric”) and mandatory checks (“gates”) are
explained in the report. Recorded rubric and gate outcomes display as “Passed”,
“Failed” or “Unknown”; null never becomes a pass or failure. Derived quantities
remain signed to four decimal places, with direction visible even when rounding
produces zero. Contextual links identify the skill and case where applicable.

### Reproduce the offline demonstration

This uses the existing ten-case/twenty-observation Podman measured extract,
24-case unmeasured gh fixture and explicitly synthetic incomplete static scan.
The inventory includes all configured sources discovered by the existing helper.
The static example is a UI state demonstration, not a finding about the real
Podman skill. No model or paid endpoint is called.

```bash
demo_parent="$(mktemp -d /tmp/skill-report-demo.XXXXXXXX)"
"$SKILL_EVALUATOR_PYTHON" -B .github/scripts/skill_evidence.py inventory \
  --output "$demo_parent/inventory"
"$SKILL_EVALUATOR_PYTHON" -B .github/scripts/skill_evidence.py normalize \
  --kind behavioral --skill podman \
  --input .github/tests/fixtures/skill_evidence/podman-native \
  --output "$demo_parent/normalized-podman"
"$SKILL_EVALUATOR_PYTHON" -B .github/scripts/skill_evidence.py normalize \
  --kind static --skill podman \
  --input .github/tests/fixtures/skill_evidence/static-synthetic \
  --output "$demo_parent/normalized-static"
"$SKILL_EVALUATOR_PYTHON" -B .github/scripts/skill_evidence.py project \
  --input .github/tests/fixtures/skill_evidence/gh-no-model.json \
  --output "$demo_parent/normalized-gh"

# Flat public bundles contain only inventory.json and public-report.json.
# Normalize also writes evidence.json; that private intermediate is not an input.
for sample in podman static gh; do
  install -d -m 700 "$demo_parent/$sample"
  cp "$demo_parent/inventory/inventory.json" "$demo_parent/$sample/inventory.json"
  cp "$demo_parent/normalized-$sample/public-report.json" "$demo_parent/$sample/public-report.json"
done
"$SKILL_EVALUATOR_PYTHON" -B .github/scripts/skill_analysis.py \
  --input "$demo_parent/podman" --input "$demo_parent/static" \
  --input "$demo_parent/gh" --output "$demo_parent/analysis"
"$SKILL_EVALUATOR_PYTHON" -B .github/scripts/skill_report.py \
  --input "$demo_parent/podman" --input "$demo_parent/static" \
  --input "$demo_parent/gh" --analysis "$demo_parent/analysis/analysis.json" \
  --output "$demo_parent/html"
xdg-open "$demo_parent/html/report.html"
```

The regression suite additionally uses explicit synthetic controls for failed
mandatory gates, missing/adaptive attempts, negative values rounding to zero,
direct/exploratory/incompatible cross-run comparisons and comparison limits.
It tests historical values, independent validation, all-skill coverage, stable
rendering, support links, escaping, restrictive CSP hashes, semantic landmarks,
table headers/captions, theme contrast, corrupted input, private permissions,
input replacement and output confinement. Run all offline contracts together:

```bash
"$SKILL_EVALUATOR_PYTHON" -B -m unittest discover -s .github/tests -v
pwsh -NoLogo -NoProfile -File ./scripts/Invoke-Validation.ps1
```

### Privacy and accessibility

Keep generated reports private and outside the checkout. There is no report
upload, Pages integration or change to existing publication workflows. No raw
private trajectory, prompt, native report or analyst context is embedded. Only
bounded quotations already accepted by the analyst validator can appear. All
dynamic HTML text is escaped, URLs are internal generated anchors, and a meta
Content Security Policy denies external content, connections, forms, objects and
base URLs. Only hash-authorized fixed CSS and the small theme script can run.
There are no external libraries, CDNs, fonts, analytics, fetches or stored browser
preferences. Credential-pattern detection reuses the existing public boundary;
it is not a comprehensive privacy audit. The deterministic HTML limit is 64 MiB;
exceeding it rejects without truncation or partial output. Existing input and
analysis bounds remain unchanged.

The layout uses logical headings, semantic landmarks, a skip link, native
disclosures, labeled theme controls, visible keyboard focus and captioned data
tables. Text and state labels do not depend on color. Both palettes target AA
text/component contrast. Content wraps at small widths; wide data tables scroll
within labeled keyboard-focusable regions. This follows
[WAI page structure guidance](https://www.w3.org/WAI/tutorials/page-structure/)
and [WCAG 2.2 reflow guidance](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html).
These design and regression checks are accessibility-oriented evidence, not a
complete WCAG conformance or assistive-technology certification.

### User-run Edge acceptance

If browser automation cannot open local files under the active policy, keep the
report local and use Edge's Open File command for manual acceptance. Do not
upload private reports or screenshots or change browser policy to enable access.
Record the report file digest and Edge version with the results. Check:

- Desktop and 320 CSS pixel widths in both light and dark themes: readable
  paragraphs and headings, no page overflow, and wide tables scrolling within
  their own regions.
- Keyboard-only navigation: visible focus, skip link, section navigation,
  appearance selector and disclosure toggling, with no trapped focus.
- Contextual skill/case links: correct targets and containing disclosures open;
  expand reasoning, original assessment fields, citations and provenance.
- Consistent assessor labels and scores in overview and detail, unscored results,
  passed/failed/unknown outcomes and visible qualification/approval boundaries.
- JavaScript disabled: readable content, system theme and usable native
  disclosures and fragment navigation; restore the original browser setting.
- Local screenshots of the overview, analyst actions and expanded evidence at
  both widths and themes, plus keyboard focus and JavaScript-disabled reading.

Return observations and local screenshot paths for review. Browser acceptance
remains pending until those results have been inspected; automated HTML tests do
not establish that it passed.

### Optional private analyst attachments

Add `--analyst-review /tmp/private-attachments/podman.json` to the report command;
repeat for another selected record. There is at most **one analyst report per
record**, with up to eight separately supplied independent assessments of that
exact report. No-attachment generation keeps the existing public-evidence
dependencies (including Pydantic), without importing the analyst modules or
OpenAI SDK. Attachment-specific version checks run only when requested.
Public evidence and analysis contracts remain unchanged.

The rendering boundary rechecks the attachment witness and captured originals.
Validation reconstructs each analyst's **original** context and analysis, then
binds its selected record and source exactly to the consolidated public capture.
The original analysis digest need not equal the aggregate analysis digest.
Interpretation never transfers to another run, changed record, or skill revision.
Explicit invalid attachments reject the invocation before HTML publication;
there is no silent fallback. Omit attachment flags to generate the base report.

Keep a descriptor outside the checkout. Paths may be absolute or relative to the
descriptor. Supply independently preserved raw-byte digests; neither a report's
self-declared validation status nor a saved validation receipt is authority.
The closed descriptor has all these fields (replace placeholders):

```json
{
  "schema_version": 1,
  "profile": "podman-1cffcf9",
  "tooling": "/tmp/private-tooling/podman",
  "skill": "podman",
  "record_id": "sha256:<exact-selected-public-record-identity>",
  "review": "/tmp/preserved-pilot/reports/skill-review.json",
  "review_digest": "sha256:<original-json-byte-digest>",
  "markdown_digest": "sha256:<original-markdown-byte-digest>",
  "inputs": ["/tmp/preserved-pilot/original-public"],
  "analysis": "/tmp/preserved-pilot/original-analysis/analysis.json",
  "source": "/tmp/preserved-pilot/original-source",
  "support": "/tmp/preserved-pilot/original-support",
  "selection": null,
  "assessments": []
}
```

`skill-review.md` must be the original JSON's sibling and must exactly match the
original validator's Markdown rendering. `source`, `support`, and `selection`
must reproduce the original invocation; use null only when originally absent.
Do not reconstruct or regenerate model judgments. Each descriptor is bounded to
1 MiB; there are at most 128 analyst attachments. Original context/evidence
bounds remain enforced, and attachment document captures share a 64 MiB budget.

#### Reviewed tooling and actual isolation

The adapter hardcodes these profile revisions and individual SHA-256 hashes for
`skill_review.py`, `skill_analysis.py`, `skill_evidence.py`, and `skill_reports.py`:

| Profile | Original repository revision |
| --- | --- |
| `current-v2` | `afdb659ee130171d263da6f13c9dec6de912d3a4` |
| `baseline-a5392b0` | `a5392b0eda37485b131ffe416fcb9d6e5ee547d2` |
| `baseline-3f47c9d` | `3f47c9de4df362ae9977748ad6353227f403a9b8` |
| `podman-1cffcf9` | `1cffcf9947c265f126a3ceee75e5e35249bfd722` |
| `gh-89f46f0` | `89f46f026cdaaf001487cbcc1425204db29e8952` |

Historical tooling must be retained or copied from the exact locally available
Git revision into `<tooling>/.github/scripts/`. Nothing is fetched automatically.
For `current-v2`, null tooling selects the current checkout's four modules; their
bytes must still match its reviewed profile. Future module changes require an
explicitly reviewed compatibility update, not a digest override.

The visibility presentation changes modify `skill_analysis.py` and
`skill_reports.py`; they do not refresh any reviewed execution profile. For saved
`current-v2` reports, explicitly select the exact retained `afdb659` tooling
snapshot instead of null tooling. The existing fixture archive retains that
profile's original modules, including its original `skill_reports.py`; tests
verify those exact hashes rather than treating current checkout bytes as historical
tooling. Reports generated by newer tooling need a separately reviewed compatibility
profile before attachment. Base HTML generation and offline review preparation
remain available without that update. Do not regenerate or relabel a saved report
to bypass the original-module check.

For a saved report produced by the previous `current-v2` module set at
`3f47c9de4df362ae9977748ad6353227f403a9b8`, select `baseline-3f47c9d` in the
attachment descriptor and set `tooling` to the retained snapshot containing
that revision's four modules under `.github/scripts/`. Null tooling is not
accepted for historical profiles. The refreshed `current-v2` instead identifies
the module set at `afdb659ee130171d263da6f13c9dec6de912d3a4`. Reports from
`a5392b0eda37485b131ffe416fcb9d6e5ee547d2` use `baseline-a5392b0` with their
retained original tooling. Its exact source bytes and hashes remain unchanged;
the current competing-skill policy is not applied retroactively.

Change only the attachment descriptor's profile and tooling selection for this
handoff. Preserve the saved report JSON and Markdown, their digests, original
inputs, and source/support selections. Do not migrate the report, regenerate a
judgment, substitute current source bytes, or override provenance, availability,
or expiry checks. If the exact original tooling or evidence is unavailable,
retain that limitation rather than treating the refreshed profile as compatible.

Only those four hash-verified modules are copied to a fresh protected temporary
layout. Descriptors cannot supply commands, interpreters, import search paths,
environment settings, or new executable profiles. The fixed launcher uses the
calling pinned Python executable with `-I -B`, a neutral working directory, and
a small clean environment without inference credentials. Python 3.13, OpenAI
2.44.0, Pydantic 2.13.4, and SkillEvaluator 0.3.0 are required; original provenance
validation additionally requires the saved report's exact Python patch version.
There is no installer, provider client invocation, token count, or inference.

An audit hook installed before historical imports rejects audited Python socket
operations (including DNS) and process spawning. Each validation has a 120-second
deadline and a bounded response. These are application-level restrictions, **not
an OS sandbox or network namespace**. They do not protect against compromised
native dependencies, same-UID interference, or privileged processes. The existing
filesystem ownership, no-follow capture, input-state, and output guards remain
in force. Tests exercise historical module imports, derived root paths, import
shadowing, and the restricted operations in the actual temporary layout.

#### Independently supplied assessments

Assessment documents are a separate input, not modifications to analyst reports.
Every assessment must contain an exact raw analyst-report hash at its declared
`report_digest_locator`. Multiple assessments retain attribution and disagreement
without voting, averaging, or a preferred verdict. Repeated source documents reject.
Example assessment entry inside a descriptor's `assessments` array:

```json
{
  "author_kind": "independent_ai",
  "attribution": "ChatGPT (supplied attribution)",
  "document": {
    "path": "assessment.json",
    "digest": "sha256:<original-assessment-byte-digest>"
  },
  "report_digest_locator": ["verification", "report_sha256"],
  "fields": {
    "verdict": ["assessment"],
    "score": ["score"],
    "maximum": ["max_score"],
    "dimensions": ["dimensions"],
    "limitations": ["scope_and_next_step"]
  },
  "narrative": null,
  "rubric": {"path": "frozen-rubric.json", "digest": "sha256:<raw-rubric-digest>"},
  "rubric_locator": ["independent_scoring"],
  "freeze": {"path": "freeze-record.json", "digest": "sha256:<raw-freeze-digest>"}
}
```

Locators are bounded lists of literal object keys or array indices, not JSONPath
or executable expressions. Each optional document uses the same path/digest pair.
`narrative` selects a UTF-8 text document displayed as inert text. `rubric` selects
JSON, with `rubric_locator` identifying the rubric object containing `dimensions`.
Use null for absent narrative/rubric/freeze and null `rubric_locator` without a
rubric. Unscored narrative assessments use null score, maximum, and dimensions
locators; no missing numeric score is inferred. Dimensions, when supplied, are
objects keyed by rubric dimension, each with integer `score` and text `rationale`.
Dimension names, total arithmetic, and numeric bounds are checked; qualitative
rubric rules and pass/fatal judgments remain attributed assessor statements.

A freeze record must match the full rubric's canonical digest and the analyst
context digest. A supplied original freeze time must precede the report timestamp.
This establishes recorded consistency, not trusted timestamp attestation or proof
of independent authorship. Unknown metadata cannot confer authenticated approval.
Author categories are `independent_ai`, `human_supplied`, and `unknown`; even supplied
human assessments remain unauthenticated. This MVP provides no human-authentication
mechanism and does not infer approval from chat participation or structural success.

Only explicitly selected fields and allowlisted provenance metadata enter HTML.
Raw preservation records can contain private paths and are never dumped wholesale.
The presentation projection reuses the analyst's sensitivity/control-character
screening and HTML escaping; it is not a comprehensive privacy audit. Each document
and assessment projection is bounded to 1 MiB. Keep all originals and reports private.

The supplied historical pilots have separate **ChatGPT-authored** assessments:
Podman's substantive pass has **no numeric score** or proven preregistration;
gh's supplied 9/10 references its preserved frozen rubric. These are individual
pilot judgments, not authenticated human approvals, native skill-performance
results, or global analyst qualification. The analyst remains
`not_quality_qualified` and `automated_publication_eligible: false`.

#### Time-limited historical integration

Podman's reviewed-reference deadline is **2026-10-19T19:11:15Z**. Original validators
and final publication guards use the current clock. Never backdate, rewrite
preserved availability, or accept stale support because a past validation passed.
After expiry, omit the analyst descriptor. Original public evidence declaring
available support and its saved analysis can also become stale: use existing
normalization/projection and public-bundle tooling on retained native originals
to create **separate current-availability inputs**, then rebuild analysis and the
base HTML report. Preserve all original files, scores, policy and observation
identities; the derived record/analysis identities reflect changed availability.
An attachment cannot transfer to those changed identities.

The base report can retain historical measurements with explicit expired-support
limitations. Previously generated HTML remains readable as a snapshot, not proof
of continuing validation. Durable archived-validation semantics are deferred;
this MVP introduces no attestation authority or expiry exception.

No-review, zero-recommendation, no-change, investigation-only, incomplete-evidence,
and upstream-owned states remain explicit. Deterministic findings, model
interpretation, supplied assessments, and authenticated human approval are separate
concepts. Structural validity cannot establish semantic truth, causality, or a
worthwhile skill edit. A future human-reviewed recommendation workflow must collect
explicit authenticated approval and usefulness evidence separately; it must not
promote these reports automatically. This MVP initiates neither inference nor edits.

## Private skill improvement review

For static triage, start with the rule group and select its exact static record
from `analysis.json`. Follow its existing finding reference into the original
native evidence and use the offline `prepare` operation below with the same public
bundles and analysis. The existing reviewer already receives static records and
findings; no second reviewer, prompt change or inference workflow is added.
An independent Codex session can use `summary.md` and the same record/reference
identities. Source context and appropriate behavioral support are still required
before recommending a skill edit. A proposed improvement should specify current,
candidate and no-skill comparisons, previously passing cases, mandatory safety
gates, negative controls and fresh realistic cases. These are future validation
requirements, not evidence that an evaluation ran.

Detailed coverage retention warrants a separate upstream SkillEvaluator proposal:
retain bounded validated completeness enums, counters and reason/location metadata
with provenance, then separately review any safe public projection. Do not replace
this with recurring raw-scanner wrapping. Dependency freshness is also deferred:
Dependabot currently covers workflow actions and the scheduled APM update workflow
already supplies a controlled refresh path. A subsequent focused PR can assess
uncovered Git/tool/bootstrap pins and release-note review without adding another
dependency manager here.

Issue #60 adds `.github/scripts/skill_review.py`. This is a Linux-first, private
judgment tool over supplied evidence, with no retrieval, shell tools, grading,
source edits, uploads, repository actions, or automatic publication. Existing
public schema v1, analysis schema v1, measurements, scoring, workflows and APM
artifacts are unchanged. Use the pinned evaluator Python 3.13 environment from
`setup-skillevaluator.sh`: OpenAI 2.44.0, Pydantic 2.13.4, SkillEvaluator 0.3.0.
The CLI rejects other dependency versions. No dependencies are installed by it.

### Operations and authorization

First produce and retain public bundles and their `analysis.json` using the
preceding workflow. Select one logical skill and an exact non-inventory record
ID from the analysis record index. The selected record determines the evaluated
source identity; current installed source cannot substitute for different bytes.

```bash
# Offline: exports a private review-context.json, never invokes the model.
"$SKILL_EVALUATOR_PYTHON" .github/scripts/skill_review.py prepare \
  --input /tmp/public-bundle --analysis /tmp/analysis/analysis.json \
  --skill podman --record-id 'sha256:<selected-record-hash>' \
  --source /tmp/evaluated-source --support /tmp/retained-support \
  --output /tmp/new-review-context

# Explicitly authorized inference: rebuilds context from originals.
# Set OPENAI_API_KEY securely in the calling environment; never in arguments/files.
"$SKILL_EVALUATOR_PYTHON" .github/scripts/skill_review.py review \
  --input /tmp/public-bundle --analysis /tmp/analysis/analysis.json \
  --skill podman --record-id 'sha256:<selected-record-hash>' \
  --source /tmp/evaluated-source --support /tmp/retained-support \
  --model '<explicit-model-id>' --authorize-inference \
  --output /tmp/new-skill-review

# Offline: independent structural/evidence validation plus exact Markdown check.
"$SKILL_EVALUATOR_PYTHON" .github/scripts/skill_review.py validate \
  --input /tmp/public-bundle --analysis /tmp/analysis/analysis.json \
  --skill podman --record-id 'sha256:<selected-record-hash>' \
  --source /tmp/evaluated-source --support /tmp/retained-support \
  --review /tmp/new-skill-review/skill-review.json
```

`--source` and `--support` are optional. Missing support remains unavailable and
limits conclusions. Prepare and validate never require credentials or inference
permission. Review requires both an explicit model and `--authorize-inference`
before reading evidence or creating a client. A prepared context is an inspection
artifact, not a trusted input to review. Every operation revalidates saved analysis
against the captured original public bundles. Saved reports require the same
inputs, source selection, transformation identities and availability. Refreshing
expired public records changes context identity; an old report must be reviewed
against its original availability conditions and cannot silently pass as current.

Review uses the pinned SDK directly with the official endpoint, `store=false`,
`background=false`, no tools, disabled truncation, no redirects, no environment
HTTP proxies, and zero SDK retries. There is one input-token count followed by
one generation using identical model, instructions, input and strict JSON schema.
The count includes the supplied structured-output schema. The supported count
endpoint is documented in the [official OpenAI API reference](https://developers.openai.com/api/reference/python/resources/responses/subresources/input_tokens/methods/count).
The compact model-facing schema uses context-bound evidence-ID enums supported by
[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs#supported-schemas).
Counting and generation share the exact context, instructions and schema; the
request screen rechecks the schema before each request and provenance records its
exact digest. Each schema construction is isolated and deterministic, without
changing the context or context-free schema.
The host expands explicit evidence selections into the complete saved judgment,
then independently validates its metadata, citations, action grounding and text.
Generated responses are never repaired to pass. The model cannot supply the
derived metadata, omit required reasoning or replace validation commitments.
Preparation retains its existing evidence bounds. Review rejects before client
creation if the complete schema exceeds provider budgets: 1,000 enum values,
120,000 characters of names/enum/const strings, 5,000 properties or ten nesting
levels. String enums with more than 250 values must total at most 15,000
characters; consequently, the current 71-character SHA citation IDs permit at
most 250 citable identities. Empty source/suggestion pools permit only empty
target/assessment arrays; an entirely empty citation pool rejects. Empty or blank
qualitative members and 0/0 source members remain authenticated but uncitable.
There is no evidence omission, alias mapping or unconstrained-schema fallback.
The private report contract remains version 2. Changed prompt, schema and
implementation digests bind new reports to the corrected tooling; historical
reports require their original inputs and pinned tooling rather than migration.
There is no repair generation, provider fallback or automatic retry. Defaults are
64,000 input tokens, 12,000 output tokens and a 180-second total async deadline
across both requests. `--input-limit`, `--output-limit` and `--deadline-seconds`
permit positive values up to 128,000, 32,000 and 300 respectively.
Model identifiers also undergo the existing sensitive-text checks before client
creation or either SDK request; recognized credentials cannot be sent as a model
identifier.
Fine-tuned model IDs (`ft:...`) reject before client creation or either request:
the bounded strict schema uses constraints outside their
[supported Structured Outputs subset](https://developers.openai.com/api/docs/guides/structured-outputs#some-type-specific-keywords-are-not-yet-supported).
The schema and local bounds are retained; there is no model or schema fallback.
Refusal, incompleteness, malformed output, unexpected tool output, missing usage,
limits, HTTP errors and timeout reject; failures require a new manual invocation. The
returned generating-model ID must exactly match `--model`; a missing or different
ID rejects before a report is created. Select an explicit model ID returned
unchanged by the service rather than an alias that resolves to another ID.
This verifies the model recorded in configuration against the API response's
[generating-model identity](https://developers.openai.com/api/reference/python/resources/responses/methods/create).
The review suppresses logging during SDK invocation, including debug logging. Errors
print a fixed message without SDK bodies, prompts, evidence, credentials or paths.
The opt-in `--diagnostics` option on `review` and offline `validate` emits one
bounded JSON line to stderr before the fixed CLI error. It covers parsing, model
binding, judgment validation, screening, integrity rechecks, provenance validation,
report construction, Markdown rendering and protected output persistence. A trusted
local qualification runner may capture this privately with 0700-directory /
0600-file protections. The maximum diagnostic size is 8,192 bytes.

Diagnostics contain host-selected stage/code, declared logical field names and
bounded indexes, elapsed time and authenticated context, analysis, input-provenance,
prompt, schema and implementation digests. Review also records expected-model/match
status and at most one count and one generation request. Validated usage survives
subsequent rejection, including rendering and persistence failures; bounded numeric
cache/reasoning details remain available. Offline validation has no inferred API
request counts or model-match claims. Saved-report usage is retained only after its
provenance and usage checks; it is not an attestation that inference occurred.

Expected checks raise typed host-authored failures. JSON/locator and filesystem
signals originate only at their explicit validation or protected OS boundaries;
the shared global assertion behavior is unchanged. Arbitrary `ValueError`, runtime,
SDK, scanner and writer exceptions remain `rejected` with an empty location. A
host deadline expiry has its own code; an unrelated `TimeoutError` remains generic.
The first failing check determines the diagnostic. Unknown path components stop
at their known parent, so generated keys and locator values never become locations.
No Pydantic messages/input/context, SDK bodies, exception text, quotations, prose,
headers, credentials or private paths enter diagnostics. Serializer failure falls
back to fixed safe metadata. Diagnostics never preserve rejected candidates, create
reports, relax output cleanup or authorize another request. Default CLI errors and
report destinations remain unchanged.

| Failure family | Representative codes and locations |
| --- | --- |
| Preflight | `inference_unauthorized`, `runtime_unsupported`, `model_unsupported`; configuration or versions field |
| Structure and size | `model_structure_invalid`, `judgment_structure_invalid`, `report_structure_invalid`, `report_size_exceeded`; known field prefix |
| Citations | `unknown_citation`, `citation_type_mismatch`, `citation_source_mismatch`, `citation_locator_mismatch`, `citation_lines_unavailable`, `citation_content_unavailable`, `quotation_mismatch`, `claim_incompatible`; citation field/index |
| Sufficiency | `source_sufficiency_mismatch`, `behavioral_sufficiency_mismatch`, `skill_sufficiency_insufficient`, `skill_source_unverified`, `skill_source_required`, `skill_with_skill_statement_required`, `investigation_sufficiency_conflict`; sufficiency field or citations |
| Suggestions and targets | `suggestion_coverage_mismatch`, `suggestion_source_required`, `suggestion_statement_required`, `modification_path_invalid`, `modification_not_grounded`, `non_skill_paths_forbidden`; suggestion/target field/index |
| Actions and validation | `skill_validation_plan_incomplete`, `evaluation_support_required`, `assessment_action_conflict`, `skill_action_assessment_conflict`; exact validation field, citations or disposition/category |
| Security | `report_control_characters`, `report_invalid_unicode`, `report_sensitive_text`, `report_sensitive_assignment`, `report_screening_budget_exceeded`, `report_technical_span_invalid`; original logical field, including decoded layers |
| Request and provenance | `request_context_mismatch`, `request_policy_mismatch`, `request_schema_mismatch`, `evidence_integrity_rejected`, `report_provenance_mismatch`, `report_timestamp_invalid`, `private_contract_unsupported`; provenance field or fixed root |
| Responses | `response_incomplete`, `model_mismatch`, `usage_missing`, `usage_invalid`, `usage_inconsistent`, `response_tool_output_forbidden`, `response_message_incomplete`, `response_refused`, `response_annotations_forbidden`, `response_shape_invalid`, `response_limit`, `json_invalid`; fixed response/usage fields |
| Output | `report_markdown_limit`, `report_markdown_mismatch`, `output_boundary_rejected`; `markdown` or `output` |

Omitted output destinations use the existing private temporary writer. New output
directories remain outside the checkout and input boundaries, mode 0700, with
0600 files and guarded cleanup. Prepare writes only `review-context.json`; review
writes `skill-review.json` and deterministic `skill-review.md`. Validate is
read-only. Capture guards persist until the last publication check. The public
capture retains its 64 MiB operation and 8 MiB member bounds; saved analysis and
supplemental source/support share a separate 64 MiB capture budget. Saved analysis
permits a 64 MiB read; other members retain the 8 MiB bound. Context is capped
at 8 MiB; JSON and Markdown reviews at 1 MiB each.
No truncation or silent oversized-input omission occurs. Unsupported secure
filesystem platforms reject; Windows is not qualified.

### Evaluated source coverage

A supplied source directory is read once per file using the existing no-follow,
hard-link, special-file and change guards. Agent-visible members follow the
existing native projection boundary. Every supplied visible member must occur
in the selected evaluated source manifest and match its exact SHA-256. Unexpected
members or any supplied mismatch reject. Source not represented by a known
manifest cannot be authenticated and supplying it rejects. Excluded and unselected
files remain captured, bounded and guarded, but are not disclosed or screened as
model input. Selected source must decode as UTF-8; selected binary content rejects.
Original bytes are never redacted or changed.

By default, all supplied agent-visible source text is included within the context
bound. Coverage is complete only if all declared members are present and fully
included. Missing members produce partial coverage with an explicit omitted-member
list. An optional `--source-selection /tmp/selection.json` chooses line excerpts:

```json
{
  "members": [
    {"member": "SKILL.md", "start_line": 6, "end_line": 12}
  ]
}
```

The closed selection rejects duplicate or nonexistent members and invalid line
ranges. Original source bytes are still verified in full. Each included member
records its original digest, line range, total lines, excerpt digest, transformation
(`utf8-splitlines-join-lf`) and completeness. Excerpted source is partial even when
all member names are present. Missing source is unavailable, including when only
its manifest identity is known or a snapshot contains no agent-visible members.
Excluded files do not establish source integrity; a present, authenticated
zero-byte member does. Absence citations require complete source coverage;
partial coverage cannot establish that omitted guidance is absent. Source origin,
revision, ownership and identity remain independent of coverage. Recommendations
about upstream skills do not authorize edits to installed upstream bytes.

The separate `authentication` object records verified and missing manifest members
and complete/partial/unavailable authentication coverage. Full authentication does
not upgrade partial disclosure. All supplied visible members are verified even
when omitted from the selection; changed omitted bytes reject or invalidate guards.

Sensitivity gates run on decoded selected text and metadata, and on a screening
copy of the complete serialized context and each SDK payload. Selected JSON string
literals and credential key/value assignments are checked; serialization must not
hide controls or credentials. Validated public-record policy-name fields retain
their metadata meaning and still screen their values.
Only authenticated source examples grant technical spans for inline `Secret=`
mentions or conservative fenced Quadlet `Secret=name,type=mount|env` references,
optionally with an identifier or `/run/secrets/` target. Names and targets retain
credential/path/contact/control checks. The screening copy replaces only the
recognized directive key; transmitted excerpts, hashes and transformations remain
unchanged. Arbitrary secret assignments, environment credentials, malformed
references, and credential-shaped names/targets reject. This is review-local
handling, not a change to public evidence screening or a comprehensive privacy audit.
Technical spans are capped at 1,000 per source text and the screening copy is
built in one pass; repeated technical mentions cannot cause quadratic copying.

Verified empty source members retain their original and empty-excerpt digests,
zero total lines, and a `0/0` range. They count as complete member coverage.
Explicit selections accept `0/0` only for empty content; nonempty content requires
positive line ranges. Empty qualitative values use the same representation,
including when their optional range is omitted, and retain original provenance
and completeness. Empty ranges have no citable lines and cannot supply observed
behavior or ground a specific skill modification.
Qualitative citations also require non-whitespace content in the cited span,
including when no quotation is supplied. A blank line within otherwise useful
retained output cannot establish observed behavior; the retained member and its
provenance remain available for investigation. The rule applies to behavior,
evaluator judgments, native suggestions and analyst interpretations; blank
evaluator spans cannot establish sufficient evaluation/harness support.

### Optional qualitative support

`--support` names a private retained directory with `support.json` and original
members at their exact public-reference relative paths. At most 128 support items
are accepted. All supplied files share bounds and change guards; only selected
text and disclosed metadata undergo sensitivity screening. A support
item is a closed descriptor:

```json
{
  "items": [
    {
      "record_id": "sha256:<public-record-hash>",
      "reference_id": "sha256:<reference-hash>",
      "observation_id": "sha256:<observation-hash>",
      "kind": "agent_statement",
      "locator": ["agent_output"],
      "representation": "original",
      "archive_member": null,
      "start_line": null,
      "end_line": null
    }
  ]
}
```

Record, reference, observation and locator membership are checked against captured
original public records. Support must name the selected skill and exact selected
source identity. Behavior and evaluator judgments require an observation whose
reference list contains that member. Case, arm, attempt and run identities are
host-generated from that observation. Legacy reference locators extend the original
reference locator. Statement input requires an agent-output, transcript, trajectory,
messages, commands or stdout carrier; grader/reward/feedback/suggestion carriers
cannot be relabeled as behavior. This carrier check establishes type and location,
not truth or causal relevance. The compatible legacy `agent_behavior` input label
is emitted as `agent_statement` in v2. Authenticated messages establish recorded
agent statements, not verified command execution or claimed outcomes. No supported
message carrier is promoted to verified execution. These still require human review.
Evaluator judgments require a `grader`, `verifier_result`, `rewards` or `feedback`
carrier and reject behavior/suggestion carriers, including mixed nested locators.
An arbitrary observation-bound value cannot establish evaluator evidence or
satisfy the qualitative-support gate merely through its descriptor label.

Output kinds are `agent_statement`, `evaluator_judgment`, `native_suggestion`, and
`analyst_interpretation`. Suggestions require a suggestions/recommendations/
improvements locator and reject behavior carriers, including agent-generated
suggestions nested beneath agent output. Genuine grader suggestion paths remain
supported. Suggestions and interpretations may have a null observation for
run-level support. Their presence does not establish observed behavior.
A judgment object with a score must agree with its bound native observation;
contradictory score carriers reject. Other contradiction claims remain semantic
judgments for human review, never reconciled by silently choosing a grader.

`original` requires exact original member bytes and digest. When the public
reference declares an archive digest, `archive_member` must name a supplied ZIP
within the support root. Its captured digest and contained original member digest
must both match the public reference. Null archive identities cannot be upgraded
by supplying an unbound archive. All ZIP members are bounded, read and hashed in
memory and never extracted; unsafe paths, ambiguous names, encryption, unsupported
compression and oversized expanded members reject. Omitted sensitive or binary
members do not reject an authenticated parent, and never enter the context.
Archives share the 8 MiB per-file and 64 MiB aggregate supplemental bounds, including
expanded members, with at most 10,000 entries. There is no archive retrieval. `reviewed_extract` requires the existing allowlisted
`extract-manifest.json`, matching archive identity, original member digest and
retained extract digest, with `archive_member: null`. Unknown extract manifests reject. Reviewed sanitization
is recorded as a transformation with omitted original content unavailable; the
extract never becomes a complete original. No arbitrary user-supplied sanitized
replacement can authenticate itself with a new digest.

Optional start/end lines select a derived excerpt of the verified located value.
Null/null includes that entire value, rather than claiming the entire archive or
trial is complete. Non-string JSON values render canonically before line selection.
Each support item preserves original archive/member/locator identities, retained
and excerpt digests, transformation, completeness, availability and limitations.
Expired or unavailable public references remain so. Independently verified
retained originals or allowlisted extracts supply separately identified local
support, without rewriting public availability or native completed scores.
Sensitive selected text or metadata, corrupt, contradictory, unbound or oversized
supplied evidence rejects.
There is no automatic redaction that can silently alter authenticated evidence.
Scanning detects known credential, contact and private-path patterns; it is not a
comprehensive privacy audit. Inspect the private prepared context before authorizing
its transmission. Report Markdown preserves host-generated excerpt and support
metadata without embedding full native evidence or the review prompt.

### Native qualitative bindings

An optional `binding` adds three closed, pinned carrier recipes. Omitting it keeps
the compatible reference descriptor above. Native bindings require `original`
representation and a verified retained ZIP; a caller-supplied digest or reviewed
extract cannot authenticate a new supplemental member. Members are derived from
anchors, not arbitrary descriptor paths. All consumed companions must occur in the
same authenticated ZIP and match their observation-linked public reference digests.

- `native_trajectory`: anchor `reference_id` to the observation's native trial
  `result.json`. Reconcile its canonical task case, result ID, trial name, arm,
  reward identity/scores, summary-recorded attempt and observation ID. The sibling
  `trajectory.json` must be the recorded reward trajectory source, ATIF-v1.7,
  and match the native agent/model. Only `steps/<index>/message` structured
  locators with `source: agent` produce `agent_statement` evidence. User/system
  messages, tool-call locators and unsupported schemas reject. Session IDs are
  not fabricated as shared result IDs; association is authenticated archival
  membership, not execution attestation.
- `native_dimension`: anchor to the observation's original `reward.json`, with
  locator `["details", "<dimension>"]` or its `reason` child. The enclosing score,
  reward component and canonical observation component must agree, even when
  only a reason or line excerpt is selected. Flat security, accuracy, goal accuracy
  and behavior check carriers are supported. Nested execution/efficiency subchecks
  have no admitted aggregate-score mapping. Component and overall judgments have
  separate contradiction keys; scores and native formulas are never rewritten.
- `native_findings`: anchor to the original run-level `result.json` with no
  observation, then authenticate its derived `codex/findings.json`, skill and
  agent identities, and `["suggestions", <index>]` text. Suggestions remain
  run-level hypotheses. Ambiguous trajectory pointers do not establish case
  associations or executed behavior.

Each item retains both original anchor and selected member digests, locator,
archive identity, source/run/case/arm/attempt scope, component score or step ID,
selection transformation, and independent public/local availability. Public schema
v1 references are never invented or expanded to accommodate supplemental carriers.

### Review contract and prompt policy

The private review schema is version 2, method `grounded-skill-review/2`.
Public evidence and analysis schemas remain version 1. CLI arguments remain
compatible, but older private reports reject explicitly before rebuilding context.
Validate them using their original pinned implementation and dependencies, original
evidence/selection, context, prompt and schema identities. Retain the original
tooling snapshot; do not silently migrate a report or override availability/expiry
to make it validate. The current implementation contains no parallel legacy validator.
Separate closed Pydantic types define the compact model response and the complete
saved v2 judgment/envelope. Substantive field definitions and bounds are shared;
the model-facing evidence slots differ. Semantic checks bind the expanded saved
judgment to captured evidence independently of the binding function. Extra fields, invalid
citations, evidence-type confusion, source paths, unavailable line ranges,
quotation mismatches, incomplete suggestion dispositions and recommendations
exceeding these support rules reject.

Model-facing citations contain `evidence_id`, `public_locator`, `start_line`,
`end_line`, `quote` and `claim`. Source and qualitative selections require explicit
available line ranges and a null public locator. Public selections require an
explicit valid public-record locator and null lines. Claims remain positive,
absence or interpretation; execution is unavailable for every supported carrier.
The host derives citation type, availability, source path and fixed source or
qualitative locator, preserving the selected ID, range, quote and claim exactly.
Nullable citation line fields permit only positive integers when present. Public
locator integer components remain zero-based and nonnegative. Nullable fields,
empty public locators and legitimately empty recommendation, suggestion, target,
comparison and external-assertion arrays retain their existing semantics. Substantive
strings, including validation criteria, alternatives, risks and external assertions,
require a non-whitespace character; values are never stripped or repaired. These
shared compact/saved constraints use supported `pattern` and `minimum` keywords;
conditional cross-field rules stay in host validation, without `if`/`then`/`allOf`.
The pinned SDK's strict-schema conversion must reproduce the compact schema.
No line defaults, clamping, quote rewriting, inferred targets or guessed IDs occur.
Native assessment IDs have their own supplied-suggestion enum; the array has the
expected length, and independent validation rejects duplicate or substituted IDs.
Modification paths remain explicit model choices constrained to citable source
members; a valid path without a supporting source citation still rejects.

Model-facing sufficiency retains behavioral scope, provenance/availability
explanation, limitations, conclusion and rationale. For every assessment and
recommendation the host derives source coverage, identity and integrity from the
authenticated context, and recorded-statement availability from valid citations
to actual agent statements. Grader judgments and native suggestions cannot become
agent behavior. Neither authentication nor recorded statements prove execution.
The model remains responsible for expert interpretation, competing explanations,
honest uncertainty, warranted no-change advice and substantive validation plans.

Host provenance records method, dependency versions, participating implementation
module digest, context/analysis/schema/
prompt digests, input provenance digest, selected record and source identity,
origin, ownership, revision, source authentication and disclosure coverage/omissions, public reference availability,
local support IDs, model configuration, endpoint/request policies, UTC timestamp,
usage and validation status. The model cannot supply or change host provenance.
Saved provenance is independently compared with rebuilt context. It is a reproducible
binding, not a cryptographic attestation that a model call actually occurred.

A top-level assessment is mandatory even when the recommendation list is empty.
It explains tested benefit, tested harm, interpretation, uncertainty, disposition
(`skill_change`, `investigate`, `no_change`), citations and sufficiency. Every
`skill_change` assessment must include at least one `modify_skill` recommendation,
and every `modify_skill` recommendation requires a `skill_change` assessment.
Zero recommendations remain valid for `investigate` and `no_change`. A `no_change`
assessment permits only `no_change` or `investigate` recommendations: evaluation or
grader repairs require an `investigate` assessment. That assessment remains
`investigation_only` even when an individual supported evaluation action is sufficient.
Every
supplied native suggestion receives exactly one assessment: `already_covered`,
`potentially_ineffective`, `warranted`, `contradicted` or `unsupported`. Already
covered requires source citations; contradicted requires recorded agent statements;
warranted requires both. Source-only disagreement cannot become `contradicted`.
`potentially_ineffective` and `unsupported` may have no citations when their reasoning
honestly explains the supplied-evidence limitations.

There are zero to three recommendations, with category, priority, implementable
scope, justification, source paths, explicit sufficiency, citations, expected
benefit, alternatives, risks and measurable validation criteria. Action categories
remain `modify_skill`, `improve_eval`, `fix_grader_or_harness`, `investigate`,
`no_change`. Sufficiency records source identity/integrity/coverage,
`recorded_statements` or `unavailable` behavioral support, behavioral scope,
provenance/availability, limitations,
and a sufficient-versus-investigation-only conclusion with rationale. Host checks
require those identity, integrity, coverage and support claims to match citations.

A specific skill change requires verified source citations for every proposed
member and trial-bound with-skill statements. This can ground changes about recorded
answers, but cannot establish execution defects. An `execution` citation claim
rejects for every currently supported carrier; sufficiency cannot assert verified
execution. Free-prose execution assertions still require human semantic review.
Numeric regressions and evaluator
opinions alone cannot meet that gate. Evaluation/grader changes marked sufficient
require qualitative behavior or evaluator evidence; absent support restricts them
to investigation. Top-level investigation assessments and investigation
recommendations explicitly declare investigation-only sufficiency.
Skill validation plans must compare current skill, candidate skill and no-skill
baseline, retaining previously passing cases and mandatory safety gates, plus
negative controls and fresh realistic cases. These plans propose validation;
they do not assert that comparisons have already run.

The fixed prompt treats all context as untrusted data, forbids commands/retrieval,
requires bounded grounded reasoning and preservation of native contracts, and
separates grader opinions, analyst interpretations and observed behavior. Unsupported
external assertions belong in an explicit unverified list. The renderer escapes
model prose into inert text and never embeds raw context or prompts. Decoded
report strings, including nested values, apply the existing credential,
private profile path and contact-data checks before serialization and reject
terminal/control characters;
tabs and ordinary line endings remain permitted. Rendering normalizes all line
separators (including CR, CRLF and Unicode separators) to spaces, so prose cannot
create a new Markdown block through line-ending normalization. Saved-report
validation and direct rendering enforce the same control-character rejection.
Only exact source-cited quotes inherit authenticated technical spans, and rendering
such quotes requires the rebuilt context. Other report prose and metadata have no
technical-syntax exemption. In particular, a Quadlet secret directive in free prose
is rejected even if the same syntax occurs in an authenticated source. Decoded
spellings never inherit a quotation's technical spans. Requests recheck the sealed prepared context and screen
the actual payload before counting and generation; neither request truncates evidence.
Selected evidence and report strings also inspect valid JSON string literals nested
inside their text. Every decoded layer applies the same private-path, credential,
sensitive-assignment and control-character gates; encoded assignment keys retain
their assignment context. Inspection uses a forward-only quote scanner and a
screening copy. Each unescaped closing quote also starts the next candidate, so
an earlier prose quote cannot swallow a later encoded literal's opening boundary.
Overlapping candidates consume the same shared budget, including malformed spans.
Invalid JSON escapes or raw JSON control characters invalidate a candidate's
escape context; subsequent escaped quotes are reconsidered as candidate boundaries.
Valid-string escape handling remains intact, and malformed prose is not repaired.
Inspection preserves original bytes, source identities, hashes and saved
values. Decoded spellings never acquire source technical-syntax exemptions.
Each screening pass permits at most eight decoding steps per path and 65,536
candidate literals. Its shared work budget is 64 × 1024² units: inspected text and
serialized lengths consume units, and every candidate decoding attempt additionally
costs its literal length plus 256 units, including empty or malformed candidates.
The budget spans all fields in a payload or report and fails closed on exhaustion.
Malformed quoted prose is not repaired or decoded. This is JSON-string inspection,
not URL, base64, shell or general escape decoding; the existing sensitivity scanner
remains pattern-based and does not prove the absence of every kind of private data.
Semantic truth, causal relevance, instruction-defect attribution and worthwhile
scope cannot
be established by structural validity, carrier checks or citation integrity.
Every report remains a model-generated judgment requiring human review.
Private profile detection includes Unix user and root homes, macOS user/root
homes, and standard/legacy Windows profile paths. Windows matching ignores
profile-directory case and accepts forward, backward or repeated separators.
Ordinary system paths and similarly named public references remain permitted.
Unicode bidirectional formatting controls (marks, embeddings, overrides and
isolates) reject in evidence text, judgments, saved reports and rendering.
Ordinary multilingual text and emoji joiners remain supported.

### Offline verification and usefulness qualification

Run the production-path offline suite in the pinned environment:

```bash
"$SKILL_EVALUATOR_PYTHON" -B -m unittest discover \
  -s .github/tests -p 'test_skill*.py' -v
"$SKILL_EVALUATOR_PYTHON" -B -m unittest discover \
  -s .github/tests -p test_public_reports.py -v
```

The review suite uses the actual pinned SDK and mocked HTTP transport, including
CLI preparation, authorized review, independent validation and deterministic
rendering. It covers source/citation/analysis mismatches, partial coverage and
excerpts, existing Podman guidance, unmeasured upstream gh ownership, synthetic
action categories and no-change assessments, unchanged historical native measures,
expired public references with separately verified local reviewed extracts,
contradictory graders, injection-as-data, sensitive inputs/outputs, refusal,
malformed/incomplete output, limits, deadline, cleanup and authorization. These
fixtures are not model-backed usefulness evidence. No paid inference belongs in
ordinary CI. Sandbox UID or asynchronous socket restrictions must be reported as
infrastructure limitations and cannot justify weakening production guards.

The synthetic native fixture recreates four trial bindings, the three technical
source examples, 86 recorded messages, 16 flat component reasons and four run-level
suggestions without copying private historical evidence. The 128-item boundary,
129-item rejection, original/archive integrity, decoded screening, and unsupported
execution claims have offline regressions. Complete relevant suites before reporting
validation success; prior timeouts remain inconclusive. An independent packed local
checkout with the same history and approved changes can reduce object-store checking
cost without relaxing production guards.

Privately qualify full preparation with the preserved original ZIP and members,
all ten evaluated source members and all 106 selected items. Use one archive-bound
public record; unbound numeric records cannot acquire an archive identity merely
from a supplied ZIP, and alternate representations are not additional measured runs.
Independently rebuild and inspect the context and final request without inference.
Keep the context and original artifacts outside the repository and uploads. Offline
byte limits do not establish a model token count. If an explicitly authorized later
token preflight exceeds its configured budget, reject without truncation; any new
manual selection must document omitted locators and relevance-based reasons in the
private qualification record. Neither paid counting nor generation belongs in this fix.

**Recommendation usefulness is a separate qualification gate.** The analyst is
`not_quality_qualified`, with `automated_publication_eligible: false`, until a
manually reviewed model-backed proof of value passes. This implementation never
promotes itself based on schema correctness, citation checks or green offline tests.
After explicit authorization for each model invocation, retain representative
Podman, unmeasured gh, synthetic positive and no-change reports privately. Review
them against native suggestions, checking grounded reasoning, worthwhile scope,
honest evidence sufficiency, uncertainty and practical validation plans. Verify
that existing guidance is recognized, native grading issues do not become invented
skill defects, and unavailable evidence stays explicit. Record human judgments
and measured usefulness separately; no automated downstream publication is enabled.
