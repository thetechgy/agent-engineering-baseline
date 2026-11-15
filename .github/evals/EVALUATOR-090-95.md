# SkillEvaluator 0.9.0 production-adoption assessment, issue #95

Current status: #138 merged data-only host adoption and #139 merged unscored
finding retention as `a50f693df6f024a6b8063b41e1b6dc2ac40e3f7a`. The subsequent
[Podman dataset correction](../../docs/evaluations/podman-dataset/README.md)
qualifies strict admission and the complete credential-free 0.9.0 static catalog,
retaining scanner findings and incomplete coverage. Static migration is ready for
a separate implementation decision after final selected CI; no production selector
changes here. The assessment below retains #137's historical decision state,
including its failed original strict receipt. Benchmark policy/provider and
private review/replay ownership remain separate.

**Recommend adopting 0.9.0 for data-only consolidated reporting and orchestration
planning/dispatch together. Hold the complete static-quality and live benchmark
consumers.** The static hold is a reproduced strict-dataset incompatibility, not
missing provider credentials. Retain original native-normalization and private
review owners. This PR prepares compatibility and qualification; it changes no
production selector, schedule, protected gate, Pages content or paid allocation.

Main was verified at `d02d485fa58598aa3f3ce91799a6976746643afd`, the merge of
[PR #136](https://github.com/thetechgy/agent-engineering-baseline/pull/136), with no
intervening changes at assessment start. That PR's passing source is
`1cab475c635012731f7bba6825c00b398b39f5bc`. Its native receipts are reused for
unchanged components. The [assessment receipt](../../docs/evaluations/evaluator-090-adoption/receipt.json)
and [83-assertion reconciliation](../../docs/evaluations/evaluator-090-adoption/assertion-differences.json)
record the additional credential-free evidence. The draft PR description records
terminal CI on the delivered revision; local, historical and hosted results are
distinct.

## Actual consumer boundary

Setup owns packages; workflow names alone do not establish ownership. Follow the
linked entry points through their commands and helpers. Proposed owners below are
a migration recommendation, not selectors changed by this PR.

| Consumer / entry point | Current owner and state | Proposed owner | Consequential behavior | Evidence | Blocker | Rollback |
| --- | --- | --- | --- | --- | --- | --- |
| [Validate static quality](../workflows/validate.yml): `quality` setup → `validate --external --tiers 1 --no-llm` → strict datasets → `catalog` → `public-quality` → artifact | Production 0.3.0 / Harbor 0.13.2; independent pinned scanners | Hold 0.3.0 as one consumer | 0.9 confirmed failure outranks incomplete coverage; both must survive. Missing references remain incomplete here | Eight native scanner controls, actual six-skill catalog, projection/HTML; preserved failing strict check | Podman entry 8 grades “podman skill”; 0.9 strict validation exits 1. No skill/rubric edit or exception authorized | Keep `quality` selector; preserve candidate reports separately |
| Validate `ci-contracts`, retained Pester feasibility and quality's native gh boundary | Production-regression 0.3.0; current review overlay runs contracts and private review fixtures | Keep original regression owner while live production remains 0.3.0 | Tests of original execution/grading and attachment contracts remain useful; candidate cohorts do not replace them | #135/#136 retained native receipts; affected historical contracts | Purpose is the retained production contract, not a missing candidate fixture | Original setup/commands remain |
| [Benchmark](../workflows/benchmark-skills.yml): context → protected `benchmark` setup → `tier3 run` → recover/benchmark/artifacts/public-benchmark → history | Manual/protected production 0.3.0, Codex 0.155.1, metric mean | Hold 0.3.0 | New dimension/verdict/applicability policy; Harbor auth/model resolution changes; custom-only Pester stays diagnostic | #136 native fixtures, controlled standard grading and collector/report checks | `skill_reports.POLICY`, `validate_benchmark_versions`, recovery/history eligibility still bind 0.3.0; unscored collection drops known findings; actual 0.9 provider route unqualified | Retain original policy/patch; never relabel new evidence as old |
| [Private review generation](../scripts/skill_review.py) and [judge/analyst attachments](../scripts/skill_report_reviews.py): operator → context/redaction → Responses request or exact saved-validator dispatch → optional report attachment | Active `current-v5` generation plus immutable original validator snapshots; Python 3.13, evaluator 0.3.0, OpenAI 2.54.0 / Pydantic 2.14.3; older overlays retained | Keep these owners | Live review is not an upstream Tier 3 judge. Exact source, registry and runtime pins authenticate interpretation | Existing saved-validator fixtures and #136 original-owner dispatch; actual version guard rejects 0.9 before requests | No successor review/validator profile admits 0.9. SDK freshness or general judge accuracy is not the blocker | Select the original attachment profile and interpreter |
| Base [analysis/rendering](../scripts/skill_report.py), history replay and [publisher preparation](../scripts/skill_pages.py): authenticated public artifacts → admission → analysis → HTML/history → seal | Production `reporting` setup installs 0.3.0 plus review overlays; publisher consumes public data, not native trials or private attachments | **0.9.0 now**, preserving original native/attachment owners | Producer/policy identities stay in data; incompatible score series remain separate; unavailable detail does not erase admitted ledger values | Production prepare/build/seal controls under 0.9; historical native fixture first normalized by 0.3; #136 byte-identical HTML reproduction | None for the data-only host after final selected checks pass; Pages deployment itself is unchanged | Restore two literal interpreter/setup selections; retain all public records and seals |
| [Plan/dispatch orchestration](../workflows/orchestrate-skill-evaluations.yml): scheduled/manual/Validate(main) → public history/authenticated intents → `gh` dispatch → protected Benchmark | Maintained production `reporting` host 0.3.0; both paid streams disabled in [policy](orchestration.json) | **0.9.0 data-only host**, alongside reporting | Same nonce/ancestry/eligibility/stop policy; dispatch still targets the retained benchmark owner | 34 plan/context/guard/dispatch controls under 0.9 with synthetic Actions API; original authenticated GitHub command boundary unchanged | No provider dependency in planner. Disabled streams do not qualify their downstream paid route | Restore host selector; leave streams disabled |
| [Current evaluator qualification](../workflows/current-evaluator.yml): explicit `candidate-next` → native cohorts/lifecycle → owning collection → same-run report join | Opt-in 0.9.0 / Harbor 0.25.0; manual default still 0.8.0, selected Validate explicitly requests next | Keep 0.9.0 opt-in owner | Custom task outcomes, startup faults and unavailable standard judgments remain distinct | #136: 52 Pester + 48 gh oracle observations, six lifecycle shards, 14 startup faults; additional native no-judge controls here | Fixture qualification does not establish live-provider routing | `candidate-current` for new diagnostic work; preserve original receipts |
| [Pilot](../workflows/codex-pilot.yml), deadline/admission, [campaign](../workflows/evaluation-campaign.yml), return-contract preparation and historical replay | Maintained credential-free paths and immutable experiments use retained 0.8.0 / Harbor 0.24.0, original CLI/model/locks | Keep 0.8.0 | Execution identity is part of evidence; new source-only identities cannot reopen an allocation or reinterpret an old grade | Original receipts, #136 retained admission, unchanged frozen selections | Frozen provenance, not package age. Inactive paid branches remain unqualified for any different owner | Original checkout/profile/lock and raw evidence |
| [Candidate Pester packaging](../workflows/pester-candidate.yml): explicit `candidate` 0.7.2 → historical score refusal and native fixtures | Disabled automatic triggering; manually executable migration qualifier | Retire routine/manual qualification entry after review; preserve replay tooling | 0.9 selected cohorts cover the same task families and lifecycle; versioned-policy refusal replaces numerical-equivalence as adoption policy | #136 native cohorts/shards; retained 0.3 historical scoring and cross-policy controls | No unique current adoption coverage identified; this does not obsolete its historical receipts | Restore workflow/setup entry from reviewed Git revision |

Required Linux and PowerShell checks do not use the evaluator. Their names and
semantics, and the `Selected validation results` gate, remain unchanged. Protected
benchmark execution, history append and isolated Pages commit/deploy jobs retain
their existing authorization boundaries. No disabled stream was treated as a
successful compatibility test.

## Released contracts and bounded fixes

Primary evidence is the released implementation at
[`b78d146`](https://github.com/NVIDIA/SkillEvaluator/tree/b78d14618a694dec84bc9601468f8f711df5cab3),
its tests and [manifest](https://github.com/NVIDIA/SkillEvaluator/blob/b78d14618a694dec84bc9601468f8f711df5cab3/pyproject.toml),
not release-note promises. The unchanged [0.9 profile](evaluator-0.9.json) binds
published hashes, resolved lock, evidence patch, installed source digest and
1.1.0 trusted backend. #136 matched all 278 wheel Python members to that tag.
The selected owner is Linux/Python 3.14.10, Harbor 0.25.0, LiteLLM 1.93.2,
OpenAI 2.54.0, Anthropic 2.8.0, MCP 1.30.0 and Pydantic 2.14.3. The released bounds
exclude Python 3.15 and LiteLLM 1.94; this LiteLLM keeps OpenAI below 3. No other
owning group is refreshed. Other supported upstream OS/Python combinations are
not qualified by these receipts.

The static CLI flags still work, but a drop-in package substitution did not:

- `skill_reports.catalog_report` and `skill_evidence` assumed an incomplete scan
  always determined the headline. The versioned bridge now uses 0.9's released
  `retained_results` rehydrator to validate findings, status and gates together.
  A known failure and incomplete coverage can coexist; contradictory verdicts
  still reject. The original 0.3 interpretation is unchanged.
- Static candidate projection lacked complete policy provenance. It now binds the
  exact producer, Python/Harbor, patch and no-Tier-3-judge identity, with a distinct
  scanner adapter identity. The scanner executables and their locks are unchanged.
- Released missing-reference diagnostics are projected into the existing caveat
  field, retaining the exact displayed count and an independent incomplete scanner
  marker. Findings remain visible when strict dataset admission fails. No new
  report format, grader, scheduler or scanner implementation is introduced.
- Publisher controls now prepare their old native fixture under its original
  interpreter, then exercise the real data-only prepare/build/seal path under
  0.9. Allowing a new host does not authorize cross-version native normalization.

The real Podman strict check remains **failed**. It identifies entry 8's
skill-identification expected output, which is also applied to a no-skill baseline.
The assessment retains that exit/check and verifies the rejection while separately
rendering valid static findings. Passing assessment CI means this classification
is correct; it does not make the static consumer adoption-ready. Resolving it
requires an authorized outcome-only task expectation revision, its new identity
and the same strict check. No inference is required for that correction.

0.9's default dimension mean shares its policy name with 0.8, but not identical
inputs: baseline accuracy no longer penalizes skill identification, judge scores
come from verdicts, goal accuracy/security below 1.0 fail scored attempts, and a
scored dimension below 0.40 can fail a partially unscored verdict. Declarative
checks, explicit inapplicability and reusable-baseline eligibility are useful;
they do not replace task-specific Pester mutation or gh authorization grading.
The existing producer/revision identities prevent direct cross-version score
comparison. Original results are neither rescored nor pooled. Baseline timeouts,
missing usage, unsupported execution, collection errors and grading failures do
not become measured task failures or positive Skill Lift.

Upstream all-tier CI is advisory for Tier 3 and ignores deprecated required-Tier-3
switches. This repository does not adopt that generated CI. Native CLI exit 1
from strict validation remains a gate failure; malformed/launch/timeout scanner
results remain incomplete, and native transport zero alone is never task quality.
Upstream budget controls do not replace allocation authorization or billed usage.
Codex remains the reviewed 0.155.1 dispatch pin for this candidate. Harbor's changed
Codex authentication/model resolution is relevant only to a live execution path.

## The 83 upstream assertion differences

These are **83 failed upstream assertions**, alongside 614 passes in the retained
697-test parser/path run. Neither this assessment nor a green repository suite
turns them into passing upstream tests. The linked reconciliation names all 83
nodes and preserves the retained log hash.

| Cause | Assertions | Behavior and supporting control | Disposition |
| --- | --- | --- | --- |
| Unsupported/dynamic/indirect wrappers and hidden Unicode-terminated forms | 71 | Upstream expects security failure; repository emits unsupported/unscored evidence and refuses the native verifier before judges. The wrapper remains a finding | Intentional evidence policy; no clean security pass or task failure inferred |
| Malformed `exec` metadata with `cmd` instead of wrapper `input` | 2 | Reject ambiguous wrapper metadata; normal `exec_command` and released static wrapper forms still parse | Intentional narrower admission; valid invocation controls retained |
| Known secret exposure together with unsupported wrapper evidence | 4 | Exactly one critical finding survives the real verifier, redacted, but `_save_unscored_trials` replaces it with `_failed_judge_diagnostic`, which omits security details | Verdict policy is intentional; downstream finding visibility is a confirmed integration gap and blocks live adoption |
| Unlinked output on multiple wrapper calls | 6 | Output is independent wrapper evidence, not an attributed command observation. Secret is scanned exactly once, without invented tool/skill attribution | Intentional linkage policy; direct shared/native controls verify retention |

The 79 other differences have supported intentional-policy explanations. The four
mixed-secret cases expose an additional integration gap: raw finding retention
is insufficient when the collected diagnostic loses it. The reproduction runs the
real file-reading verifier and unscored collector without mocks, inference or
judges, and verifies the persisted diagnostic remains unscored but lacks findings.
This is not established as a newly introduced 0.9 regression; the older evidence
policy may share it. No parser regression is substantiated by this bounded audit.
All released sensitive-path extraction controls passed in the retained run.

## Smallest proposed switch and maintenance disposition

Adopt the **data-only report/publisher-preparation and planner/dispatcher hosts as
one group**. They consume the same authenticated public schema and history; they
need no new provider, judge, task or score policy. The existing opt-in 0.9 runtime
already supplies their dependencies. This reduces current 0.3 host installations
without adding another production execution stack; no measured CI cost saving is
claimed. Native replay, reviews and live benchmarks remain explicitly owned.

The subsequent switch is limited to:

1. In `publish-skill-report.yml`'s prepare job and both
   `orchestrate-skill-evaluations.yml` jobs, replace setup kind `reporting` with
   existing `candidate-next`; run their Python commands with `SKILL_NEXT_PYTHON`
   instead of `SKILL_EVALUATOR_PYTHON`. Keep token scopes, source authentication,
   schedules, disabled streams, commit/deploy steps and benchmark target unchanged.
2. Use that same interpreter for operator base analysis/HTML from validated public
   bundles. Keep `--analyst-review` and native `.3/.8` normalization on the
   original owning interpreters. Do not change `benchmark-skills.yml`'s context or
   evaluation setup: its feature-review contracts and paid owner still need 0.3.
3. Retain this PR's status/provenance bridge and controls for later static adoption.
   A future static switch must update `quality` CLI/projection ownership and use
   the owning interpreter for `catalog`; it must first resolve the unchanged
   Podman task expectation and pass the full strict catalog. Splitting scanners
   and that check between evaluator versions is not recommended.

After the decision, the 0.7.2-only `pester-candidate.yml` entry and setup kind
`candidate` can leave maintained qualification. Preserve the old qualifier,
patch/source/lock identity and receipts in Git for exact replay; retain backend
1.0.0 because 0.8 still uses it. Two terminal-semicolon parser allowances are
already absent from the new 0.9 profile: released parsing demonstrates their
replacement. Keep their historical patch files.

Do **not** retire the 0.3 scanner caveat patch while static remains held, private
review SDK overlays/original validator snapshots, broad evidence safeguards,
trusted gh initialization, task graders, operational stop/accounting controls,
collector admission or consolidated reporting. Released secure startup does not
initialize the sealed fixture broker, and released grading/budgets do not establish
repository authorization or evidence provenance. All 417 prior custom profiles
are unchanged; 28 source-only successors identify changed shared admission code.
Frozen experiment definitions, selections, original grades and allocations remain
unchanged and closed.

Rollback restores the three workflow host selections and the operator interpreter.
Keep newly produced public records with their original producer/policy identity,
plus historical ledgers, raw evidence, seals and original runtimes. Do not delete,
relabel or rescore candidate evidence during rollback; incompatible history stays
separate.

## Specific remaining validation proposal

No live check is needed for the recommended data-only migration. Before a live
benchmark proposal, close the finding-visibility gap without credentials: preserve
bounded, validated `details.security.findings` through the existing unscored
collector diagnostic, artifact redaction and supporting report evidence. Update
`_failed_judge_diagnostic` in a successor evidence patch and the repository's
`validate_unscored_diagnostic` admission together; use a new producer identity and
preserve `offline-v2` and its receipts. Reuse this PR's native reproduction as the
failing-before control. Success requires exactly one known finding after collection
and sanitized export, no secret value, no invented command attribution, no numeric
quality and unchanged unknown-baseline treatment. Unsupported-only controls must
remain unscored; malformed/oversized diagnostic content must reject. Do not relax
an assertion or relabel a historical result to pass this closure.

Also introduce a versioned 0.9 benchmark/recovery/history policy and correct the
strict dataset issue. Only then propose **one existing read-only
gh case, one attempt per arm, no retries**, through the real protected production
entry point using the held CLI/model settings and new evaluator owner. Request
separate authorization and a separately bounded spending proposal; none is created
or executed here.

Success requires authenticated source/runtime/task identities, actual intended
provider/model routing, linked trials, collected rewards under the 0.9 policy,
known usage, correct incomplete/failure classification, report admission and
cleanup. A legitimate task failure is a measured outcome, not an automatic
compatibility failure. Stop after the pair, or immediately on authentication,
identity, collection/grading failure, unknown usage or failed cleanup; do not
retry, replace a slot or resume a closed experiment. Any judge-control proposal
must separately specify known correct/incorrect responses and expected verdicts;
this routing check cannot qualify general judge accuracy or skill effectiveness.

Workflow-change security review:

| Critical | High | Medium | Low |
| --- | --- | --- | --- |
| 0 | 0 | 0 | 0 |

The changed qualification route retains read-only permissions, pinned Actions,
`persist-credentials: false`, literal setup selection and no inherited secrets.
It uploads credential-free controls and a failed dataset-adoption receipt; it
cannot enable production execution or weaken the selected-result gate.

**One next action:** review and authorize the data-only reporting/orchestration
host switch. Keep static quality, live execution and historical review/replay on
the owners listed above.
