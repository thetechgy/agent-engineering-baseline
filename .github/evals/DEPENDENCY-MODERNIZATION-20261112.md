# Issue #95: November 12 dependency modernization

This pass starts from verified main `f1867ba`. Versions below identify consumers,
not a count of distinct packages across environments. A package in a universal
lock may be unselected by `--no-dev`; installed inventories are retained separately.
No model credentials, inference, judges, allocations, protected gates or Pages
publication are part of this maintenance.

Targets were checked against released primary metadata:
[uv 0.13.8](https://github.com/astral-sh/uv/releases/tag/0.13.8),
[rumdl 0.3.4](https://github.com/rvben/rumdl/releases/tag/v0.3.4),
[Semgrep 1.185.0](https://github.com/semgrep/semgrep/releases/tag/v1.185.0),
[SkillSpector 2.13.4](https://github.com/NVIDIA/SkillSpector/releases/tag/v2.13.4),
[SDK package metadata](https://pypi.org/pypi/openai/3.50.0/json),
[Pydantic 2.14.3](https://pypi.org/pypi/pydantic/2.14.3/json) and
[Compose 5.7.1](https://github.com/docker/compose/releases/tag/v5.7.1).

## Implemented groups

| Group and active consumers | Previous | Update | Qualification |
| --- | --- | --- | --- |
| Current setup/compiler in 10 workflows | uv 0.13.7 | 0.13.8 | Official Linux archive digest; production frozen installs and hash-lock compilation |
| Linux validation and APM updater lint | rumdl 0.3.2 | 0.3.4 | Regenerated wheel hashes, clean install and repository lint |
| Validate/skill-quality code-risk scanning | Semgrep 1.184.0 | 1.185.0 | 67 installed packages; Semgrep and three compatible transitive updates; native scanner controls and reporting |
| Independent SkillSpector SDK lock | OpenAI 3.46.0, Anthropic 2.6.0 | OpenAI 3.50.0, Anthropic 2.8.0 | Released scanner 2.13.4 unchanged; frozen sync, dependency check, clean/bad/incomplete controls |
| Bootstrap and generated deployment, merged PR #125 | APM 0.35.0 | 0.35.1 | Existing updater run 43328758922; native candidate checks on final PR revision |
| Review runtime, separate commit | Pydantic 2.14.2/core 2.50.2/inspection 0.4.4 | 2.14.3/2.50.4/0.4.5 | New attachment profile; exact old review/legacy runtimes retained |
| Operator Compose, separate commit | 5.7.0 | 5.7.1 | Official executable hash; setup/cleanup and native retained/opt-in Harbor checks |

The Semgrep lock also advances bracex 3.2.1 to 3.2.2, markdown-it-py 4.2.0
to 4.3.0 and sse-starlette 3.6.0 to 3.7.0 through a fresh resolution.

The scanner universal lock changes 25 package versions relative to the previous
scanner-owned lock; it still resolves 166 packages. The clean Linux scanner install
selects 68 packages. Neither number is an aggregate dependency freshness score.
The APM prerequisite is merged in PR #125. The combined runtime draft now targets
main and keeps tooling/scanners, Compose and review changes in separate commits,
then qualifies their shared identities together. This avoids repeating the same
native matrix for several overlapping runtime PRs without changing workflow triggers.

uv 0.13.8 changes the Python 3.14.10 build from 20261026 to 20261110 despite
the identical version number. Candidate setup therefore verifies and uses the
complete download catalog from uv 0.13.7's immutable source revision, with a
SHA-256 check before uv reads it and separate managed-interpreter storage.
The old 3.14.10 archive remains
`sha256:4d3c16c59ed0802a3d1d34d8bce504b15ceeaff39d62dadecc6a9fa803412aed`.
Ordinary current setup uses the new catalog. Frozen task recipes, package lock,
model settings and interpreter download identity remain distinct from ordinary
tooling updates. The [uv setting](https://docs.astral.sh/uv/reference/environment/#uv_python_downloads_json_url)
is a metadata override, not a hash or sandbox bypass.

The immutable return-contract qualification workflow itself remains byte-for-byte
unchanged at uv 0.13.7. The initial broad uv edit failed its frozen-input hash
assertion before execution; restoring that workflow corrects the regression
without changing the freeze or assertion. Setup accepts that reviewed compiler
only for candidate-current; current CI/compiler consumers require 0.13.8.
The held active frozen consumer is visible in the existing runtime-selector row.

The compiler does not rewrite the evaluator's upstream locks or the frozen
candidate lock. Fresh ordinary Python 3.13 installations record their actual patch
version; the candidate's Python 3.14.10 and frozen PowerShell/Pester pins remain.

The static admission registry retains both earlier scanner identities and adds
the new exact lock identities. Matching producer versions, lock hashes, revision
and adapter patch remain required; missing evidence cannot become a pass.
The before/after caveat control now uses the actual new scanner lock in both
arms and changes only the adapter. The original unpatched and patched profiles
remain independently admitted for historical evidence.

The APM refresh adds v14 for its shared source-policy update. The new
`pester-effectiveness-v15` identity binds changed shared reporting/tooling
bytes while keeping v13 and every earlier registry value unchanged.
Campaign source-v6 profiles record the same shared maintenance. No earlier
source-v5 or experiment identity is rewritten.
Its grader,
fixtures, cases, metrics, runtime/model selectors and candidate skill bytes are
unchanged. It grants no experiment continuation or adoption. The changed checkout
cannot consume an old preparation as if its source identity were unchanged.

## Active constraints and their exit conditions

| Environment | Actual active versions and reason | Exit condition |
| --- | --- | --- |
| Production evaluator | SkillEvaluator 0.3.0 still executes in Validate, skill-quality, benchmarks, orchestration and reporting setup. The new 0.9.0 candidate is separately qualified; this historical inventory does not promote it. | Separate production-adoption decision after the existing qualification requirements; dependency maintenance does not promote it. |
| Original active SDK environment | Clean installation still selects OpenAI 2.44.0, Pydantic 2.13.4, Anthropic 0.116.0 and MCP 1.28.1 from the released 0.3.0 lock. Review overlays also install the inherited Anthropic/MCP packages, although private requests use OpenAI. These are active installed versions, not historical-only. | A distinct refreshed 0.3.0 compatibility profile with native startup/cleanup, event, request, grading and historical dispatch qualification, or separately approved evaluator adoption. New provider behavior remains unqualified; no forced override or paid campaign here. |
| Production framework | Released evaluator 0.3.0 requires Harbor ==0.13.2, Python >=3.12,<3.14 and LiteLLM >=1.83.10,<1.89.0.dev0. The lock has LiteLLM 1.88.5. | Compatible upstream evaluator group and native qualification; no forced transitive version. |
| Older manual qualifier | `pester-candidate.yml` and setup kind `candidate` still execute the pinned 0.7.2 environment for credential-free qualification; it is not historical-only or a production default. | Retain its frozen source/lock and evidence patch for this manual qualifier; migrate that consumer only through a separately versioned qualification change. |
| Retained opt-in evaluator | Merged PR #119 implements 0.8.0 with Harbor 0.24.0, Python 3.14.10 and LiteLLM 1.93.2. It is not the production default. | Preserve this frozen environment. [0.9.0 compatibility](EVALUATOR-090-95.md) separately adds Harbor 0.25.0; Python 3.15 and LiteLLM >=1.94 remain unsupported. |
| Review and candidate SDK | OpenAI 2.54.0 is the latest stable 2.x release. Both released LiteLLM 1.88.5 and 1.93.2 require OpenAI <3.0.0; upstream SDK is 3.50.0. | Supported owning-group change or separately qualified minimal review environment; no override. |
| Candidate SDK | Anthropic 2.6.0 remains in the frozen 0.8.0 experiment environment; upstream is 2.8.0. | New versioned environment outside the closed experiments; preserve the original lock and source identity. |
| Agent CLI | Production and trusted gh setup still use Codex 0.155.1. Frozen pilot/campaign uses 0.167.0. Upstream is 0.167.2. | New production adapter/runtime identity, event and non-forwarding/native qualification; preserve the frozen pilot. Paid behavior remains unqualified and unadopted if essential. |
| Semgrep transitive dependencies | Released 1.185.0 still requires MCP ==1.29.0 and OpenTelemetry ~=1.37.0. | Upstream compatible constraints that admit the fixed versions, followed by a new hash lock and scanner controls. |
| Active fixture containers | Shared Python 3.12/trixie image digest `b18b261` and signed Debian snapshot 20261103 remain in current task builders as well as frozen experiment inputs. They are not historical-only. The current upstream image index differs. | Version the active build separately from frozen task/candidate inputs, resolve signed distribution metadata and qualify native setup, collection and grading. No live-apt fallback or silent experiment image replacement. |
| git-commit skill | Held SHA 613efc8; upstream still instructs unstaging other changes with `git reset -q -- ...`, losing unrelated partial staging. | Upstream instructions preserve unrelated partial staging, reproduced before the APM reference changes. |

The release's security and scoring changes are not automatic adoption approval.
Existing patches were checked against their actual released targets: the retained
0.3.0 Codex pin remains different from upstream's unversioned install; its review
patch is a lock overlay; its caveat patch still supplies behavior absent from that
release. The opt-in 0.8.0 evidence patch remains part of the frozen qualified source
identity. This pass removes no patch or expectation and changes no scoring.
Unchanged
released source, candidate lock and evidence-patch identities reuse their existing
qualification evidence; documentation alone does not trigger a new historical
preparation or migration matrix.

## Security evidence

The ten open manifest alerts are five unique public advisories repeated across
Semgrep's `.in` and `.txt` files. The Semgrep MCP 1.29.0 and retained-evaluator MCP 1.28.1 are in four advisory
ranges fixed in 1.30.0: [GHSA-w4fh-qvv9-3v23](https://github.com/advisories/GHSA-w4fh-qvv9-3v23),
[GHSA-5h93-6whr-6q8j](https://github.com/advisories/GHSA-5h93-6whr-6q8j),
[GHSA-rwrf-2pqf-9j8j](https://github.com/advisories/GHSA-rwrf-2pqf-9j8j) and
[GHSA-84m7-p3x7-pcfv](https://github.com/advisories/GHSA-84m7-p3x7-pcfv).
The installed OpenTelemetry API 1.37.0 matches
[GHSA-xcq7-p3x7-p88h](https://github.com/advisories/GHSA-xcq7-p3x7-p88h),
fixed in 1.45.1. Version applicability is established; reachability in this
repository's local Semgrep CLI configuration is a separate question.
The repository invokes the local Semgrep scan command; the released MCP server
command and its bearer authentication/HTTP session paths are not started by that
consumer. Those server advisories and the client redirect/schema-resolution paths
are not shown reachable through this configured scan. OpenTelemetry inbound
header parsing is likewise not exercised by that CLI. This is a bounded call-path
assessment, not a claim that every optional upstream mode is safe.
Server/client reachability was not established for the retained evaluator
environment, which is not configured here as an MCP HTTP service.
The independent SkillSpector lock already has MCP 1.30.0 and OpenTelemetry API
1.45.2. No transitive constraint is overridden to clear an alert.
APM's setuptools signal and its narrower Windows legacy-install applicability
are recorded in PR #125's focused evidence note.

## Current or intentionally separate

All eight external Actions pins match their exact latest stable release commits:
checkout 7.0.1, setup-uv 10.3.3, upload-artifact 7.0.2, download-artifact 8.0.2,
github-action-benchmark 1.22.2, configure-pages 6.0.0, upload-pages-artifact 5.0.0
and deploy-pages 5.0.1. Updating or checking those pins does not authorize Pages.
Dependabot owns Actions and the requirements pairs; the weekly APM updater owns
branch-ref skill refresh and native regeneration. The maintained freshness source
now reconciles all uv consumers and displays independent evaluator, scanner and
pilot environments. It makes no comprehensive transitive or OS advisory claim.

SkillSpector 2.13.4, Gitleaks 8.30.1, Bandit 1.9.4, pip-audit 2.10.1, Pester
6.2.0 and PSScriptAnalyzer 1.25.0 match current primary release/package metadata.
The released gh 2.104.0 skill bytes are identical to the qualified 2.103.3
baseline; captured CLI help 2.102.0 remains a distinct historical contract. Ambient Docker/BuildKit, Node, shellcheck,
git, tar, PowerShell bootstrap and hosted-runner tools are runner-owned; their
installed versions are not inferred from a documentation pin or this inventory.
Ordinary CI acquires latest stable PowerShell, currently 7.7.0. Frozen evaluation
PowerShell 7.6.9/Pester 6.2.0 remain separate.

Historical evaluator copies and older review validator locks, source revisions,
custom profiles, archived submissions and grades remain unchanged. Some of those
versions also have active consumers listed above. Model/reasoning selectors and
experimental provider settings are intentional protocol inputs, not dependencies
to modernize. PRs #119, #120, #121, #122, #124 and #131 are merged; describing
their implementation as a draft is stale. PRs #130 and #132 remain untouched.
The development evidence remains useful, while candidate transfer behavior stays
unmeasured after unsupported/test_name_template. Workflow-trigger/concurrency
cleanup and further agent-runtime integrations remain separate work items.

## Verification receipt

Final local qualification uses the unchanged combined executable inputs:
119 focused contracts passed (five owning-backend checks and the frozen
gh 2.102.0 help check skipped), including the earlier 48-test inventory set; the final expanded
inventory set separately passed 49 tests. These overlapping counts are not added.
All 125 offline SDK/schema/redaction tests and all 33 attachment/profile tests
passed under their owning current/previous/legacy interpreters.

The eight scanner modes retained their expected clean, failing and incomplete
outcomes, findings, locations and provenance. The production renderer reproduced
its 512,953-byte HTML exactly from public bundles and saved analysis, SHA-256
`3ec7c6d10cb78154daa4f0aa00f0a48822cccce1ca97e7b882ac7f59feefd3eb`.
Repository caveat controls retain findings and incomplete coverage.
No LLM-backed scanner behavior or provider call is qualified by these controls.

Both frozen evaluator setup paths installed with the pinned prior catalog.
Independent uv 0.13.7 and production uv 0.13.8 installations produced identical
Python 3.14.10 executable SHA-256
`340a561270dc31d791a4922adf3a112da5c425379a3e080c1946047d3eb89638`.
One production-entry test covers corrupt and unavailable catalog rejection before
uv installation. The existing patched 0.7.2 qualification entry point passed 49 controls under
its owning interpreter, with three declared skips and no network attempts.
The direct pristine-source invocation was unsuitable for tests requiring the
existing evidence patch; it is not counted as runtime qualification. Full repository Markdown lint and changed
shell-script checks pass.
A synthetic Git control independently reproduced the held upstream reset losing
unrelated partial staging while preserving worktree bytes; this is not model or
skill-effectiveness evidence.

Clean production quality installation verified exact versions, both scanner locks,
the review overlay lock and dependency consistency. Local freshness tests passed
47 tests; rumdl 0.3.4 clean installation and repository lint passed. Final scanner,
source-preservation, attachment, native Harbor and exact-head checks are recorded
on the focused PRs. The first scanner-control attempt exposed a stale before-arm
lock receipt and was corrected without changing expected findings or coverage.
The first broad local suite exposed the changed source digest; a new maintenance
identity preserves the frozen registry instead of rewriting it. Partial runs and
missing native evidence do not qualify unexercised behavior.
