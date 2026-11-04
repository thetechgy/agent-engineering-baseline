# Issue #95 review runtime update

Current private reviews use a separate frozen environment with OpenAI SDK
2.54.0 and Pydantic 2.14.2. The evaluator, benchmark and scanner environments
retain their upstream locks. This update does not require the experimental
App Server work in PR #109 or change SkillEvaluator, Harbor, Codex, benchmark
scoring, fixture images or saved historical reports.

## Lock ownership

`setup-skillevaluator.sh` checks out SkillEvaluator `ac0a049` twice. The existing
evaluator checkout retains its upstream lock and its benchmark-only source
patch. A separate review checkout applies
`skillevaluator-v0.3.0-review-runtime.patch` before `uv sync --frozen`.
The resulting lock hash is checked before and after installation, and
`uv pip check` verifies dependency consistency. No dependency resolution runs
inside setup. The patch was generated with the pinned uv 0.13.7.

| Package | Retained evaluator / historical validators | Current reviews |
| --- | --- | --- |
| OpenAI SDK | 2.44.0 | 2.54.0 |
| Pydantic | 2.13.4 | 2.14.2 |
| pydantic-core | 2.46.4 | 2.50.2 |
| typing-inspection | 0.4.2 | 0.4.4 |

These are the only installed package-version changes on Linux with Python 3.13.
The lock also records uv's format revision and redundant-marker normalization.
SkillEvaluator remains 0.3.0, Harbor 0.13.2 and LiteLLM 1.88.5. SDK 3.x remains
outside LiteLLM's declared `<3.0.0` dependency bound.

Setup exports `SKILL_REVIEW_PYTHON` for current review operations,
`SKILL_LEGACY_REVIEW_PYTHON` for old validators, and the existing
`SKILL_EVALUATOR_PYTHON` for evaluator and benchmark operations. CI runs its
unit contracts with the current review interpreter; evaluator CLI and native
container checks continue to use the evaluator interpreter. Dependency
inventories are separate. Freshness monitoring checks the current SDK and
Pydantic declarations against the review patch as their owning lock overlay.

## Original validation

`current-v3` identifies the four exact validator modules at
`1aa5b06a4d0d3c1c8b97f2e7b3398964c67d8166` and the existing reviewed current
metric registry. A new fixture archive retains those bytes. Existing profile
revisions, module hashes, registries and fixture archives are unchanged.
Existing saved JSON, Markdown, measurements and identities are not regenerated
or relabeled as the new profile.

Attachment descriptors cannot supply interpreters. The allowlisted profile
selects the current or legacy version set, and setup/operator configuration
supplies an absolute interpreter path only when the host uses the other set.
The fixed child launcher checks the required versions before reading the review.
Missing or mismatched environments reject validation; no installation or fallback
occurs. Both directions retain `-I -B`, a clean environment without credentials,
no-network/no-process Python audit guards, bounded input/output and the existing
120-second validation deadline. These remain application restrictions, not an
OS sandbox or protection against compromised native dependencies.

## Verification

The production `reporting` setup entry point installs both frozen environments,
checks their package versions and lock integrity, and passes dependency checks.
Offline tests exercise current SDK requests with mocked HTTP, strict schema and
redaction contracts, every frozen profile, current and legacy report hosts,
and missing/wrong runtime rejection. No provider inference is used. Native
container and cross-platform bootstrap evidence remains a separate hosted CI
check; this change does not claim new benchmark effectiveness.

The private temporary-directory baseline control reproduced an unrelated fixture
failure: the injection string disclosed an absolute home path. The test now
spells the same sentinel target relative to its working directory. Production
redaction and the sentinel non-execution assertion are unchanged.

The setup script resolves patches and requirement files from its own checkout
root. Reporting workflows use `path: trusted` while `GITHUB_WORKSPACE` points
to the parent directory, so the parent is not a resource lookup root. The
pre-install guard excludes tool storage from both the declared workspace and
the actual checkout, including when those directories are separate. Native
reporting setup was reproduced in this nested layout before and after the fix;
the earlier revision failed to locate the review patch.
