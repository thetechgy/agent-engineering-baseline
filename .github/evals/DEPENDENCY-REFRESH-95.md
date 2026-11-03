# Issue #95 dependency refresh

## Adopted candidates

The refresh starts from `a75799385dff431ac4856e40cdabee1e9ede308b`.
Dependency changes are limited to repository-owned tool pins and hash locks.
Existing evaluation scores,
reference registrations, source fixtures and historical tool identities are retained.

| Dependency | Before | After | Verification |
| --- | --- | --- | --- |
| uv | 0.13.5 | 0.13.6 | Verified official release digest; frozen quality setup and hash-lock generation |
| setup-uv Action | 10.3.0 | 10.3.3 | Immutable release commit; allowlist blocker resolved, hosted execution pending |
| rumdl | 0.3.0 | 0.3.2 | Hash-verified installation; repository Markdown passes |
| Semgrep | 1.182.1 | 1.183.0 | Wheel-only hash sync; dependency consistency and native catalog comparison |
| SkillSpector | 2.13.1 | 2.13.3 | Exact release commit and frozen lock; native catalog comparison |

Release sources: [uv](https://github.com/astral-sh/uv/releases/tag/0.13.6),
[setup-uv](https://github.com/astral-sh/setup-uv/releases/tag/v10.3.3),
[rumdl](https://github.com/rvben/rumdl/releases/tag/v0.3.2),
[Semgrep](https://github.com/semgrep/semgrep/releases/tag/v1.183.0), and
[SkillSpector](https://github.com/NVIDIA/SkillSpector/releases/tag/v2.13.3).

The uv Linux archive matched release SHA-256
`f29c3e94ffabd7e6f3ba521dba169a9b7ec12100bf3257087f0f24f6123f3645`.
PyPI wheel acquisition timed out; that partial wheel was never installed.
The verified GitHub release supplied the compiler instead.

The Semgrep lock refresh changes 18 of 66 packages within the existing dependency
constraints. This includes Pydantic 2.13.5 to 2.14.2 and pydantic-core 2.46.5 to
2.50.2 in the separate Semgrep environment. The separate evaluator and SkillSpector
frozen locks both retain Pydantic 2.13.4 and OpenAI SDK 2.44.0; their residual
advisories remain subject to compatibility review. Both hash locks reproduce byte
for byte with uv 0.13.6 and their documented platform targets. Every installed
Semgrep package matches the final hashed lock;
`uv pip check` reports compatible dependencies. MCP remains 1.29.0. This refresh
does not establish that the residual MCP advisory or server dispatch is fixed.

The production quality installer completed independently for baseline and
candidate environments. Baseline managed Python selected 3.13.17; candidate
selected 3.13.18. The managed minor selector remains 3.13. After the final
transitive refresh, the production hash-sync command installed the settled
Semgrep lock and refreshed its dependency inventory. Reusing the complete setup
script with an existing tool root was rejected by `uv venv`; it was not treated
as successful installation or a production fresh-run regression.

## Findings and coverage

Both environments scanned the same six unchanged local skill sources through
`skillevaluator validate --external --tiers 1 --no-llm --no-dedup`.
The final candidate collection ran after its lock installation settled.
Finding multisets agree on category, severity, check name, source file, line and
matched line content. Validator status and incomplete-scan markers also agree.

Both retain **89 findings: 1 critical, 13 high, 41 medium and 34 low**.
All six skills fail native catalog validation because findings and incomplete
coverage remain. This is bounded compatibility evidence, not a clean security
result or evidence that the skills are safe. No model inference was performed.

The eight real scanner contract tests pass. Semgrep retains all six local rules,
eight HIGH positive-fixture findings and zero benign findings. Missing rules or an
unavailable scanner remain incomplete. SkillSpector retains benign-input, positive
security detection, partial-inspection and unavailable-input behavior.

The existing gh validation/replay entry points accept all 24 valid traces and
reject all 13 faulty traces. This does not qualify the held new gh skill or its
Docker boundary. Updated rumdl passes all 37 repository Markdown files.

The focused freshness suite passes 45 tests. Before/after collector controls
reproduce duplicate Actions, Semgrep and rumdl issue entries on the unchanged
collector, then omit them with the new collector. Semgrep metadata requests drop
from one to zero, while held evaluator Pydantic remains visible.

The broad local unit-suite attempt exceeded the 30-minute skill-quality budget
and was stopped. Retained output contains no failure markers before termination;
that partial execution is **inconclusive**, not a full-suite pass. The final
ownership controls were also rerun separately after their last test refinement.
Hosted validation, including Action execution and native Docker boundaries,
is required before claiming full validation.

## Updates held back

| Candidate | Reason retained | Condition for adoption |
| --- | --- | --- |
| SkillEvaluator 0.7.0 | Coordinated runtime, patch, grading and evidence migration | Qualify the complete compatibility group; preserve draft PR #109's admission blocker |
| Harbor 0.25.0 | Owning evaluator lock and runtime contract | Qualify with its evaluator; 0.7.0 itself pins Harbor 0.24.0 |
| Codex 0.166.0 | Complete submitted-operation evidence remains unqualified | Demonstrate the required execution-evidence contract through the supported runtime |
| OpenAI SDK 3.42.1 and evaluator/scanner Pydantic 2.14.2 | Upstream frozen lock and exact consumer pins | Coordinated lock and consumer qualification; retain residual advisory evidence |
| gh skill 2.103.3 and changed APM branch content | Native APM regeneration failed | Successful pinned regeneration, reviewed output diff and native gh checks |
| Docker Compose 5.7.0 | Docker is unavailable on this workstation | Native Docker/Harbor qualification, including gh and Pester container boundaries |
| Python image and Debian snapshot refresh | Container execution is unavailable | Verify signed snapshot inputs and build/run the pinned container fixtures |
| git-commit skill | Upstream still resets unrelated staged files | Demonstrate preservation of unrelated partial staging |

APM regeneration stopped at its native 300-second HTTPS Git fetch timeout.
No generated output was published and no protocol fallback was enabled.
This is unavailable qualification evidence, not proof of an upstream regression.
The existing APM and gh source pins remain unchanged.

Container metadata identified a candidate index digest for the existing
`python:3.12-slim-trixie` tag:
`sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30`.
The `20261102T000000Z` Debian snapshot offers `ca-certificates=20250419+deb13u1`;
the other direct package candidates match existing pins. These read-only metadata
observations do not qualify the image or signed snapshot. Existing inputs remain.

APM 0.35.0, Pester 6.2.0, PSScriptAnalyzer 1.25.0, Gitleaks 8.30.1 and the remaining
Actions already matched the stable release metadata reviewed for this refresh.

## Maintenance ownership

Dependabot proposes Actions updates and Python updates under `.github/requirements`,
including its transitive packages. Weekly minor/patch proposals are grouped; major
updates remain separate. Python proposals require normalization with pinned uv and
the documented platform targets, dependency review and compatibility checks.
The first hosted Dependabot proposal remains an operational verification step.

The freshness issue omits delegated dependencies from routine tables, detail
sections, upstream/advisory polling and notification comments. It retains one
routing link to Dependabot PRs. The authenticated inventory still checks local
pins, and contradictory pins remain visible as collection failures. Restricted,
disabled or unrecognized Dependabot coverage retains custom Python monitoring.
Delegation is specific to these manifests, not every installation of a package.

The reviewed weekly APM updater continues to own CLI/hash updates, skill
resolution and generated outputs. Dependabot's beta APM updater runs `apm lock`
without deploying skills or compiling instructions, so it does not replace that
workflow in this refresh. Shell downloads, generated image inputs and the frozen
evaluator/scanner repositories retain their existing owners.

Existing PRs #108, #109 and #111 remain separate from this refresh. Initial
hosted Validate run `41569176364` was blocked before jobs started because the
selected-action policy rejected the new setup-uv SHA. The maintainer updated the
allowlist on November 3, and the new reference is now permitted. GitHub cannot
retry that startup-failed run; this documentation update triggers a fresh run.
This assessment records local qualification; hosted checks must be verified
against the published revision.
