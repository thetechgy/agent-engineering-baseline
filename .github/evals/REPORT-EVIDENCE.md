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
Inputs remain unchanged. CLI contract errors return exit status 1 without echoing
native diagnostic content.

Before creating temporary output, the selected parent must be an ordinary
directory outside the checkout and input bundle. The first nonempty `TMPDIR`,
`TEMP`, or `TMP` setting takes precedence over the platform default. Unsafe
settings (including linked, missing, or non-directory parents) are rejected
without falling back to another location or leaving an output directory behind.
Explicit `--output` placement does not depend on temporary settings.

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
The existing `gh` and competing-skill checks additionally enforce their reviewed
pins. All trees and fixture references are checked before native strict dataset
validation; source front matter must identify the local skill correctly.

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
1,000 cases, and 10,000 trial observations. Exceeding any limit fails without
truncation or partial publication. Duplicate JSON keys, cross-platform case-ID
collisions, invalid denominators, linked/reparse/hard-linked or special inputs,
escaping references, and dangling observation references are rejected.

Input trees are checked during traversal, before materializing all paths.
Normalization bundles and catalog/overlay trees allow at most 100,000 entries;
authored skill trees allow 2,000 entries and 1,000 files. Entries include
directories and unused or later-excluded files, so empty directories and unused
members cannot bypass the traversal cap. Exceeding a cap rejects the contract.

## Identity, provenance and coverage

Canonical IDs come from the pinned case-ID validator. Pairing uses canonical case
IDs, never directory order or guessed chronology. Scored attempts use the native
summary's recorded ordinal and trial mapping. Unscored attempts retain their
native trial identity and any explicit native attempt label; an absent ordinal
stays null with a metadata limitation. Public observation IDs are SHA-256 of the
canonical JSON array `[run_id, arm, case_id, native_id, native_trial, attempt]`.
Reordering inputs does not regenerate identities.

Canonical structured hashing uses UTF-8 JSON with sorted object keys, compact
separators, ASCII escaping, and no nonfinite values, prefixed `sha256:`. Source
content hashes a sorted relative-file/SHA-256 manifest under the pinned
agent-visible staging boundary. The pinned runtime ignore helper excludes
skill-owned `evals` and generated/cache/Git inputs. Historical reconstruction
reads exact local Git blobs with the equivalent authored-tree boundary; it is
`reconstructed_from_declared_revision`, never runtime-attested. Missing Git
objects remain unknown, without checkout or network fallback. Every Git read
sets `GIT_NO_LAZY_FETCH=1`, overriding an inherited lazy-fetch setting so missing
partial-clone trees and blobs cannot trigger demand fetching. It also sets
`GIT_NO_REPLACE_OBJECTS=1` so local commit, tree, or blob replacement refs cannot
substitute different bytes for a declared revision, as described in the
[Git replacement-ref documentation](https://git-scm.com/docs/git-replace).
Inherited repository-local Git environment variables and discovery/namespace
selectors are cleared before dispatch, so reads select the requested checkout,
including linked worktrees, rather than another repository or object store.
Historical skill members and authored datasets share the current-file 8 MiB byte limit. Object
size is checked before capturing content: exactly 8 MiB is accepted, larger
objects cause contract rejection, and missing objects retain null digests and
unknown provenance. An authored dataset hash identifies exact file bytes; the
native staged digest identifies enriched entries and retains
`skill-evaluator-dataset-snapshot/1`. The case cohort hash
identifies sorted canonical IDs. None of these digests substitutes for another.

Historical tree listings are streamed with an 8 MiB byte cap and a 1,000-entry
cap, including members later excluded by the authored-tree boundary. Exceeding
either cap terminates the Git process and rejects the contract before parsing
the complete listing or reading any blobs. A listing at the entry limit is
accepted; missing trees remain unknown.

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
maximum/stop-on-pass values must also agree when both are known. Absent metadata
remains unknown; compatible historical values are preserved rather than replaced
with current defaults. Judge identity remains separate from the evaluated model.
Known benchmark modes must agree with known attempt maxima: standard uses one
attempt and confirmation uses three, matching the pinned producer. Unknown mode
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
null. Recovery status, native execution checks and coverage prevent incomplete evidence promotion; unavailable references
also prevent a complete projection. Completeness describes evidence coverage,
not task success or publication eligibility. Failed rubrics, low scores and
failed with-skill deterministic gates remain valid observations. Rubric counts
and deterministic scores are checked independently; no averages or new scores
are computed. Skill Lift remains the native difference and Discoverability the
native skill-execution rubric. Static findings and production success remain
separate from both.

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
Behavioral ingestion requires the native `codex` agent value to be an object
before dereferencing it. Malformed native object access at the CLI boundary
produces a bounded contract rejection without a traceback or local paths.

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

The approved manifest records no durable retention of original members. At or
after its recorded UTC expiration, normalization marks its original references
`expired` and adds `reference_expired`, keeping the report incomplete. It samples
time once for each normalization, preserving native measurements and stable
reference identities. Retained reduced extract bytes do not establish continued
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
