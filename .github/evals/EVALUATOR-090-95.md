# SkillEvaluator 0.9.0 compatibility, issue #95

This candidate starts from main `9912a905614ed4d49ff780ae39687e9e6cc2b7cc`
(merged PR #135). It is credential-free qualification, not production adoption
or evidence of skill benefit. The draft PR description carries the final exact-head
CI result and authenticated native artifact receipts; pending or failed native
checks do not qualify this candidate.

## Consumers and ownership

| Runtime | Consumers and capabilities | Semantics and remaining maintenance | Constraints |
| --- | --- | --- | --- |
| Production 0.3.0 / Harbor 0.13.2 | Validate, quality, benchmark, orchestration, production reporting; static and standard/custom grading | Historical metric mean; retained Codex/evidence patch, review SDK overlays, scanner caveat adapter, task graders and authenticated report admission | Python >=3.12,<3.14; released LiteLLM <1.89; inherited SDK/MCP holds remain |
| Retained opt-in 0.8.0 / Harbor 0.24.0 | `candidate-current`, frozen pilot/campaign and historical report owner; native oracle qualification already retained | Dimension mean; original evidence patch and lock remain intact; trusted gh initializer, task grading, CLI isolation and repository reporting remain | Python 3.14.10 and original interpreter catalog; original Anthropic 2.6.0, MCP and SDK lock preserved |
| New opt-in 0.9.0 / Harbor 0.25.0 | Explicit `candidate-next`; same collection, projection, analysis and HTML path; normal selected CI qualifies native fixtures | Separate producer identity; upstream verdict/judge changes prohibit score comparison with older releases; bounded evidence port and gh hook remain | Python >=3.12,<3.15, selected 3.14.10; LiteLLM 1.93.2 still requires OpenAI <3; no production promotion |

The manual `candidate` setup and `pester-candidate.yml` still own 0.7.2.
They are legacy executable consumers, not production defaults. Archived replay
locks, original profile entries, experiment selections, submissions, grades and
receipts are immutable history rather than general upgrade targets.

The setup script owns evaluator environments. The new
[profile](evaluator-0.9.json) pins tag revision
`b78d14618a694dec84bc9601468f8f711df5cab3`, published package hashes, full
[resolved lock](../locks/evaluator-0.9.lock), patch and installed source-tree digest.
All 278 Python members in the published wheel match the tag. Setup uses the
existing frozen-sync, patch-check, hash and reproducible local-wheel mechanisms.
The new owning group selects Anthropic 2.8.0, MCP 1.30.0, Pydantic 2.14.3 and
OpenAI 2.54.0 without overriding upstream constraints. Its clean Tier 3 install
contains 107 packages including the local backend. The universal lock also covers
unselected extras; that count is not an installed inventory.

Harbor 0.25.0 is newly supported by this evaluator. Python 3.15 and LiteLLM >=1.94
remain unsupported. OpenAI 3.x remains excluded by the selected LiteLLM release.
Their exit condition is a released compatible owning group followed by a new
identity and qualification. This does not refresh the separate scanner, review,
CLI, image, skill or immutable experiment environments.

## Released features and repository responsibilities

| Released feature, checked in tagged source/tests | Repository disposition |
| --- | --- |
| Declarative command, file and response checks | Useful upstream grading capabilities; they do not replace Pester mutation/admission or gh authorization/receipt grading. No task grader or skill changes. |
| Version comparison and baseline reuse | Released compatibility/eligibility checks work in fixture tests. Repository authenticated artifact admission, source/model/settings identity and cross-policy refusal remain necessary. No historical rescoring or cache substitution. |
| Token, attempt, judge-call and priced-cost budgets | Released partial/missing usage controls are tested. These are runtime accounting capabilities, not replacements for repository allocation authorization, billed usage or shared stop/security policy. No live budgets or allocations created. |
| Failure handling and reporting | Upstream adds useful verdict/completeness views. Repository operational failure, unsupported grading and missing evidence must remain separate from measured task failure. Continue using the consolidated HTML and supporting public evidence. |
| Advisory all-tier CI | Tagged CI ignores deprecated Tier 3-required switches. Repository required Linux/PowerShell checks and selected-result gate remain authoritative; no generated upstream CI or onboarding workflow is adopted. |

The default dimension-mean formula retains its upstream policy name, but inputs
and verdicts change: accuracy removes baseline skill-identification penalties;
standard judge scores derive from verdicts; goal accuracy/security below 1.0 fail
scored attempts, and a scored dimension below 0.40 can fail a partially unscored
Tier 3 verdict. The evaluator revision and producer/policy identity keep these
results incompatible with older producers. Fixed numeric-vector checks establish
aggregation only; they do not establish judge equivalence or judge accuracy.

The selected fixture owner is Linux/Python 3.14.10; other upstream Python/OS
combinations are not exercised by this receipt.

Released adapter code supports actual Codex and Claude Code CLIs, with added
Codex inline/batched event parsing and existing provider-specific routing.
Upstream runtime pins are Codex 0.161.0 and Claude Code 2.1.292; this candidate
retains the repository's reviewed Codex 0.155.1 dispatch pin. Harbor 0.25.0 contains
a Copilot adapter, but SkillEvaluator's supported/experimental agent allowlists
still exclude `copilot`. API/model availability does not add repository CLI support.
Harbor 0.25.0 also changes Codex model/authentication resolution; these fixtures
do not qualify live authentication or provider routing. The shared campaign
runtime remains Codex-only and retained on 0.8.0; no new CLI runtime is implemented.

## Patch and hook disposition

The [0.9 evidence port](../patches/skillevaluator-v0.9.0-evidence.patch)
is reviewed individually rather than applying the 0.8 patch wholesale:

- Keep bounded sensitive-path classification, unknown/unsupported execution
  evidence, independent secret scanning and unknown baseline attribution.
  Preserve 0.9's expanded/normalized sensitive-path matching through its matcher.
- Keep missing-trajectory and unlinked-result refusal before judges; a native
  transport zero is never admitted as measured task quality.
- Keep only fixed nonnumeric custom outcome diagnostics through collection and
  redaction, the reviewed Codex pin and the bundled-verifier-only literal offline
  Compose rule. Other Compose overrides still fail.
- Omit the two legacy terminal-semicolon grammar allowances. Released extended
  parsing passes the existing syntax controls without them. Keep observation
  linkage in the released record-aware iterator, which supersedes the old iterator.
- Keep the trusted gh initializer: released secure startup does not initialize
  the repository-owned sealed fixture broker. Its separate 1.1.0 wheel admits only the exact new owning pair. The retained
  1.0.0 wheel remains byte-identical (SHA-256 `3d577d926bc0b64703d376cf1d39e4cddeca7336b51051585d205543f9a3f89b`).
- Reuse #135's byte-addressed metadata COPY helper in the changed Pester native
  consumer. Keep reward case/trial/arm checks and independent failure audits.

The 0.3 review SDK overlays remain attached to their original review owners;
the new candidate uses its own resolved group. The 0.3 scanner caveat patch stays
in production quality setup; the candidate's Tier 3 scope neither ports that
scanner integration nor claims upstream replacement. The 0.7.2 evidence patch
continues serving its manual qualifier. All earlier patch files and the 0.8
lock/profile remain unchanged. The final 0.9 profile is `offline-v2`: it requires
the 1.1.0 backend version and wheel/source hashes in captured provenance. Earlier
in-flight 0.9 fixture records lack that provenance and remain rejected, with their
original files retained; no historical record is silently relabeled. The original
389 custom profiles are preserved; 27 campaign successors and one effectiveness
source-only successor identify
changed shared admission code. Graders, fixtures, runtime/model selection and
active-profile selections are unchanged. These identities do not reopen any
experiment or change its original results.

## Evidence and interpretation

Local clean setup and dependency consistency pass. The shared offline path
normalizes candidate results, rejects missing/contradictory provenance and changed
evidence, distinguishes historical policies, and reproduces the canonical HTML.
Existing stale/swapped/cross-arm reward controls and failure-audit/secret-transport
controls run under the candidate owner. Missing evidence remains unmeasured.

Released feature tests cover deterministic checks, verdicts, comparisons, baseline
reuse, accounting, event parsing and advisory CI. The initial run had 919 passes
and 31 failures caused by synthetic provenance keys beneath this workstation's
protected temporary Git root. Re-running the two affected modules with keys outside
the evaluated tree passed all 64 tests; 33 overlap earlier passes. No provenance
check or upstream test assertion was removed. Those fixture results establish no
provider compatibility or judge quality.

The port was additionally checked against 697 released parser/path assertions:
614 pass and 83 differ under the repository's existing evidence contract. These
are retained as red upstream assertions, not reported as a green suite. They cover
unsupported evidence becoming unscored rather than a measured security failure,
malformed wrapper metadata being rejected, and unlinked output moving to independent
wrapper evidence. Direct controls confirm unscoped secret findings remain visible
exactly once; all released path-extraction controls pass. The repository-specific
controls assert the intended conservative outcomes rather than changing upstream tests.

Normal change-selected CI runs the existing native Pester/gh cohorts and gh
lifecycle shards, then joins same-run/attempt evidence into the existing report.
The retained 0.8 offline owner is also checked. Unchanged #135 native failure-audit
and four-case metadata receipts are reused for unchanged consumers; changed native
consumers must pass on this PR revision. Static findings and incomplete scanner
coverage retain their original reporting contracts and selected quality checks.

Workflow security review:

| Critical | High | Medium | Low |
| --- | --- | --- | --- |
| 0 | 0 | 0 | 0 |

The changed reusable route retains read-only permissions, pinned Actions,
`persist-credentials: false`, no inherited secrets and same-run/attempt artifact
joining. Its Boolean input selects only the two literal setup kinds. Required
checks and protected live gates are unchanged.

**Recommendation:** review the opt-in candidate if its selected native controls
and exact-head required CI pass. Retain production defaults. No broad scheduler,
collector, grading or report replacement is supported by this evidence. The useful
maintenance reduction is limited to the superseded syntax workarounds. Live
provider authentication, judge accuracy and skill effectiveness remain unqualified;
a paid experiment is not a prerequisite for this compatibility result.
