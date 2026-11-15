# Static-quality migration to SkillEvaluator 0.9.0

Implemented for review from verified main `18357c54e6d9266c979c915ca11dc8449196d7f9`
(PR #140), with no intervening changes. Production static quality changes only
upon merge. #138's data-only hosts, #139's offline-v3 unscored finding retention
and #140's dataset correction are already merged. Their original receipts remain
intact. Final executable revision, selected CI and authenticated hosted artifact
links belong to the draft PR description.

## Consumer and ownership

`validate.yml`'s `skill-quality` job now selects `quality-next`. This reuses the
existing 0.9.0 source, Python 3.14.10, frozen lock, offline-v3 patch and trusted
backend, adding its already locked `security` extra for Bandit/pip-audit. It
installs 125 evaluator packages rather than the data-only host's 107. This is
selection from the existing lock, not a dependency refresh. The job installs no
0.3 evaluator or private review environments.

The shared `setup-skill-scanners.sh` retains the exact Semgrep, SkillSpector and
Gitleaks installer commands, sources, hashes and locks. Semgrep/SkillSpector keep
Python 3.13; Bandit/pip-audit belong to the selected evaluator. Setup records actual
installed scanner versions and validates the existing offline-v3 source, patch,
lock, backend and dependency identity before exposing `SKILL_QUALITY_PYTHON`.

| Static boundary | Owner and observable contract |
| --- | --- |
| Existing eight scanner controls | Selected 0.9 interpreter plus the same qualified scanner executables; known findings, caveats, unavailable/launch/timeout/malformed states stay distinct |
| `collect-static-quality.sh` | Complete provenance required before scanning; absolute owning interpreter invokes the CLI, overriding stale PATH evaluator/scanner choices |
| Catalog and strict datasets | Same `validate --external --tiers 1 --no-llm --no-dedup --continue-on-failure` and `tier3 validate --strict --json`; every catalog skill/dataset retained |
| Collection gate | Owning interpreter runs existing `skill_reports.py catalog`; only ordinary reported findings remain advisory |
| Normalization/public projection | Same owning interpreter runs `public-quality`; source/producer/scanner identities, redaction, locations, findings and coverage validated by existing contracts |
| Summaries and artifacts | Existing unavailable-summary warning, checkout-integrity gate, artifact names/membership, retention and read-only permissions preserved |
| Consolidated HTML/publisher preparation | Existing 0.9 data-only owner consumes validated public JSON; no native renormalization or private attachment ownership change |

Scanner-only overrides emit startup warnings on stdout. The strict dataset
command removes them before initialization so stdout stays JSON. A real initial
run retained exit 0 plus a warning-prefixed stream; the existing collection gate
correctly rejected it. The correction changes routing, not parsing tolerance or
strict criteria. Missing/malformed/provenance-mismatched evidence remains a
failure, never a clean scan or measured zero.

Every shared setup caller was inspected. `quality` retains its 0.3 scanner patch,
original evaluator and exact review overlays for contracts and the existing
candidate assessment's historical/scanner controls. The single native gh Docker
check moves from static quality to `ci-contracts`, retaining 0.3 and test-only
Compose install/always-cleanup. No duplicate job or native gh execution is added.
Benchmark/reporting/candidate/candidate-current/candidate-next callers retain their
selection. The change-selected routing, protected gates and required Linux/Windows
checks remain unchanged; no historical campaign is manually rerun.

## Credential-free validation

The [sanitized receipt](static-quality-090-receipt.json) records the same-input
finding comparison, coverage/status differences, public reproduction and rollback.
The actual migrated workflow collection, strict validation, collection gate and
public projection run on a fresh production setup with a minimal environment and
no model credentials. A stale 0.3 executable directory precedes the system PATH;
selected execution still belongs to 0.9.0. Existing scanner controls use the same
fresh install. No inference or model judge is called.

Comparison uses each finding's content, category, severity, relative member and
location as a multiset, retaining repeated observations rather than comparing
only totals. Inputs are byte-identical to the retained #140 qualified snapshot.
The same-snapshot 90 findings, including 13 SECURITY findings, are retained.
These counts identify this snapshot, not universal expectations. Four skills
retain incomplete SkillSpector coverage and missing-reference caveats: a11y 3,
ansible 1, Podman 3 and powershell-pester-6 6. Confirmed failure and incomplete
coverage coexist under the released 0.9 status contract; the older 0.3 headline
uses incomplete precedence. Neither status means a clean skill.

Public records are re-normalized/projected against their original native reports,
then handed to the existing analysis and HTML CLI. Re-rendering must reproduce
identical bytes. Existing scanner controls verify synthetic secret redaction and
finding retention, malformed evidence and altered provenance refusals. Affected
HTML findings, coverage, runtime/provenance and source-reference sections are
visually checked. Historical #137 public records/rendering retain their original
identity and reproduce without rescore. Hosted verification independently checks
repository/run/attempt/producer revision, archive digest and declared artifact
members before data-only extraction and report reproduction.

Focused controls cover wrong/missing static runtime provenance before collection,
workflow owner separation, existing invalid strict datasets, retained producer
identities and excluded-owner refusals. Existing contract and scanner suites
retain malformed evidence, projection, scanner-fault and incomplete-coverage
controls. Final selected CI is distinct from local fixtures and historical receipts.
An initial local shell was edited during its running scan; that attempt is
inconclusive and its outputs are retained. The subsequent strict-stdout refusal
is retained as a failed gate, not a passing run.

## Released differences and reporting correction

The retained 0.3 baseline yields 89 findings / 12 SECURITY; qualified and newly
selected 0.9 yield 90 / 13. No baseline finding is lost. Released 0.9 keeps
`evals`/`.evals` in SkillSpector's scan tree, adding Podman's `PE5` at
`evals/evals.json:84`. The a11y estimated-token recommendation remains a finding,
with high-to-medium severity and clearer estimate wording. Schema metadata names
`external` as the compatibility alias `default`; author flags remain. Native
SkillSpector findings add applicability/file-role metadata, PII gains evidence
hashes, and the native matched-secret example is redacted earlier. All native
content differences match qualified #140 exactly; public finding multisets,
locations and caveats are preserved without deduplication or count fitting.

Visual inspection exposed two existing presentation problems on 0.9 static
records: confirmed failure hid one independent incomplete scanner from the
coverage overview (3 instead of 4), and a generic producer-profile banner labeled
static evidence as synthetic judge qualification. The shared report now uses the
independent SkillSpector incomplete marker for coverage and limits that banner to
behavioral records. Confirmed SECURITY failures and all findings remain unchanged.
The real released-result → public projection → publisher build regression checks
both corrections and identical retained-host output.

All 473 existing custom profiles, active-profile selectors, frozen selections,
runtime owners, inputs and grades are preserved. Twenty-eight appended source-only
successors authenticate changed shared reporting bytes for future controlled
preparation. They change only id/runtime digest; they do not reinterpret old
evidence, reopen a campaign or adopt a different evaluator owner. Source selection
in the two existing preparation helpers advances mechanically to these identities.
Exact historical HTML uses the preserved original renderer/checkout; current
rendering intentionally corrects presentation and remains reproducible under both
hosts. The original #137 report reproduces as
`d745c7b25dcacc6e1629f0a0747ca0349412be455c2dd07b4ced1968ac0be759`.

## Remaining owners and rollback

Benchmarks, recovery/history admission and live routing stay with 0.3.0 / Harbor
0.13.2; 0.9 benchmark policy and actual provider qualification remain outstanding.
Private reviews/analyst attachments and native replay retain exact original
interpreters/SDK profiles. Maintained 0.8 pilot/campaign/admission controls and the
manual 0.7.2 Pester qualifier remain active on their existing owners. Offline-v2,
older scanner identities and superseded review profiles remain historical replay
pins where they have no current caller. No wholesale tooling retirement or claim
that all dependencies are current is made.

For production rollback, revert the focused migration commit to restore the
prior static job and setup/interpreter selections. Preserve all native/public
artifacts, original producer/policy identities, seals and historical grades.
Never relabel new 0.9 evidence as 0.3 or rewrite it during rollback.

The bounded rollback test selects the retained `quality` runtime and tools as
`SKILL_QUALITY_PYTHON` / `SKILL_QUALITY_TOOLS`, runs the same collection, strict,
catalog and public-projection entry point on the identical snapshot, and compares
findings/coverage. The retained data-only host also renders the new public bundle
byte-identically. This tests return to the prior consumer owner and forward
rendering without moving native normalization across owners.

Workflow security review: critical 0, high 0, medium 0, low 0. Reviewed trigger,
read-only token, literal setup selection, pinned Actions, non-persistent checkout
credentials, artifact/upload gates and unconditional Compose cleanup are preserved.
No credential retrieval, paid stream/allocation, benchmark dispatch, Pages
publication, skill/dataset edit, historical rescore or merge occurs here.

**One next action:** review this migration and its final-revision selected CI.
