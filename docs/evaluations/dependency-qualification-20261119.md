# Proposed evaluator and Codex qualifications after PR #160

## Qualify the static evaluator first

The 0.9.0 quality job scans repository skills with Gitleaks 8.30.1. Its generated allowlist omits authored
evaluation inputs, including the Podman dataset and its files. In a credential-free comparison with the same
Gitleaks executable, both released evaluators reported zero findings on the clean control and one on a top-level
synthetic marker. For the authored evaluation input, 0.9.0 reported zero findings and complete coverage. The
released 1.0.1 validator found the marker. The target's base frozen installation and dependency check passed.
This establishes a coverage defect. Exposure of an actual credential remains unverified.
[Upstream fix](https://github.com/NVIDIA/SkillEvaluator/pull/552).

Propose a separate 1.0.1 static producer with a new evidence identity. Compare the active 0.9.0 owner and the
candidate on the same repository checkout. Exercise the secret-coverage control, strict dataset admission, clean
findings, confirmed findings with incomplete coverage, redaction, and fresh rendering of both producers' saved
reports. Keep the 0.9.0 selector available for rollback. Review author-policy, hook-gate, score and reporting
changes before recommending that the static job switch.
[Release and changelog](https://github.com/NVIDIA/SkillEvaluator/releases/tag/v1.0.1).

## Keep benchmark and review owners separately reproducible

The 0.3.0 production benchmark and retained replay use Harbor 0.13.2 and OpenAI 2.44.0. Current private reviews
overlay OpenAI 2.54.0 and Pydantic 2.14.3. The original lock contains certifi 2026.6.17. The actual HTTPX trust
context includes the affected emSign G3 root. The private-review fix updates its own trust store to 2026.10.23.
Before another protected run using the original evaluator, qualify a separately versioned execution lock with
the fixed trust store and keep the old lock available for offline reproduction. The SDK release-note pyasn1
dependency is absent from the current review lock.
[SDK dependency change](https://github.com/openai/openai-python/pull/4267) ·
[CA advisory](https://github.com/advisories/GHSA-6q48-6c7w-9gw2).

Both retained LiteLLM versions, 1.88.5 and 1.93.2, require OpenAI below 3. The newest stable 2.x release is
2.54.0. SkillEvaluator 1.0.1 still requires Python 3.12–3.14, LiteLLM below 1.94.0.dev0 and Harbor 0.25.0 for
Tier 3. Harbor 0.26.0 and SDK 3.56.0 therefore need a compatible evaluator group or an independently qualified
client. For a private-review Pydantic 2.14.4 update, qualify strict SDK schemas, exact saved attachment
dispatch, redaction and offline rendering under a new review profile. The scanner has its own SDK environment.
[Released evaluator manifest](https://github.com/NVIDIA/SkillEvaluator/blob/v1.0.1/pyproject.toml) ·
[Pydantic release](https://github.com/pydantic/pydantic/releases/tag/v2.14.4).

The opt-in 0.9.0 judge-accounting path calls the upstream judge-evidence redactor before retaining text.
Version 1.0.1 adds masking for escaped credential-bearing lines. Qualify redaction and refusal capture on
synthetic input before authorizing further judge-only execution. Actual disclosure remains unverified.
[Judge evidence fix](https://github.com/NVIDIA/SkillEvaluator/pull/547).

The manual 0.7.2 qualifier and frozen 0.8.0 experiments retain their original inputs. A Tier 3 migration needs
independent native startup and cleanup, verification of submitted operations and usage, and reproduction of
retained grades. Static qualification alone cannot settle that decision.

The official Python 3.12 slim-trixie image index advanced from `b18b261e` to `5e2bdb1b`. Debian trixie
still lists the five direct package versions in the November 3 fixture snapshot. Qualify a separate image
identity through the signed snapshot build and native gh and Pester controls before selecting it.
[Official image tag](https://hub.docker.com/_/python/tags?name=3.12-slim-trixie) ·
[Fixture provenance](../../.github/evals/gh/PROVENANCE.md).

## Qualify Codex on the observation path

Single-case observation selects Codex 0.169.1, gpt-6.2-sol and high reasoning. Production benchmarks select
0.155.1. The older CLI pilot uses 0.167.0. Register 0.170.0 as a new observation candidate and retain those
selectors. Its release changes transport fallback, MCP authentication and permission inheritance. Use the
existing non-forwarding fixture to check the released archive and helper digests, exact model and effort,
authorization, shell events, workspace evidence, token accounting, refusal, missing usage and cleanup. Compare a
rerender from retained evidence before proposing a selector switch. Provider acceptance and live evaluation
would require a later allocation. [Codex release](https://github.com/openai/codex/releases/tag/rust-v0.170.0) ·
[Observation qualification](https://github.com/thetechgy/agent-engineering-baseline/pull/158).
