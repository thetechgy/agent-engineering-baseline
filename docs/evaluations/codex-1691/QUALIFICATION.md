# Codex 0.169.1 candidate for issue #95

The opt-in profile proposes Codex CLI 0.169.1, `gpt-6.2-sol` and high
reasoning for future Codex skill evaluations. The credential-free selector uses
SkillEvaluator 0.9.0 (offline-v3), Harbor 0.25.0, the existing `gh-014` case and
the `gh-task-permission-v2` grader and isolation. It retains the APM deployment
and custom-only verifier. The registered selector has only the non-forwarding
probe capability. The live gate requires a separately registered profile,
protocol, qualified preparation and allocation.

## Release and compatibility

The official `rust-v0.169.1` tag resolves to
`c376cf7396eff83ce4c6ac61b9553df142e7a0be`. GitHub's published SHA-256 for the
Linux x86-64 musl package matched the downloaded archive. The CLI reported
`codex-cli 0.169.1`; full archive, executable and bundled code-mode host, exec
server, bubblewrap and ripgrep hashes are in the
[execution profile](../../../.github/evals/codex-execution-1691.json).
The hosted job independently rechecks the hashes before running these bytes.
[Official release](https://github.com/openai/codex/releases/tag/rust-v0.169.1).

The 0.155.1 / `gpt-5.6-sol` / high reference is the retained
[permission qualification](../task-permission-v2/QUALIFICATION.md) and
[shared-path smoke receipt](../task-permission-v2/execution-auth-20261116-02/EXECUTION.md).
Against the loopback fixture, the 0.169.1 executable with those same model and
reasoning settings emitted the subagent-setting deprecation warning, a
`/bin/bash -lc` command wrapper on the local shell and a
`cache_write_input_tokens` turn counter. The candidate sets
`[agents].enabled = false` and disables multi-agent v2 and code mode. It accepts
the observed bash wrapper alongside the existing sh wrapper and continues to
require native command start and completion evidence. The comparison retains
the request, event and usage observations for the reviewed profile. The 403
control made one candidate request and ended with a failed turn and unknown usage.

## Accounting

The standard short-context rates per million tokens are $2 input, $0.10
cached input, $2.50 cache writes at 30-minute retention and $10 output. Writes
and reads are subtracted from input before pricing uncached tokens. The CLI
turn counter does not identify write retention. The estimate uses 30 minutes,
and the fixture grade carries no model usage or charge. Above 272,000
cumulative input tokens the estimator applies twice the input and cache rates
and 1.5 times the output rate as a conservative long-context estimate at the
assumed retention. Cumulative input cannot identify individual requests above
the threshold. A missing required counter leaves the estimate unknown.
[Sourced model rates](https://developers.openai.com/api/docs/models/gpt-6.2-sol),
[released usage mapping](https://github.com/openai/codex/blob/rust-v0.169.1/codex-rs/codex-api/src/sse/responses.rs).

## Issue #95 release-note signal

Both tracked changes are ancestors of the released tag. #60082 adds an
account-security reminder lookup for a saved ChatGPT login via the app-server.
The isolated exec environment uses a fresh home and the fixture provider's
sentinel header. #60096 makes runtime-authentication denials terminal for the
runtime-auth binding. The 403 fixture uses a custom Responses provider with
zero configured retries and never exercises OpenAI runtime-auth binding.
Neither change gives this execution path a security-driven upgrade requirement.
[Account security changes](https://github.com/openai/codex/pull/60082),
[terminal runtime-auth denials](https://github.com/openai/codex/pull/60096).

## Consumers and rollback

This selector serves the shared native Codex/Harbor `gh-014` qualification
and consolidated analysis. It is the candidate for a future separately
approved successor to the closed `gh-task-permission-v2` smoke. The older
`gh-runtime-090-v1` and its `gh-read-090` controls retain 0.155.1. The
default benchmark, data-only report publication, judge calibration and
legacy 0.167.0 Pester paths have their existing owners. Shared-source
successors carry the new evidence-collection hashes with the same historical
runtime selectors and grading values. The complete prior registry entries
remain available for replay. The Pester decision in #151 remains closed.

Rollback for the candidate is to stop selecting `gh-codex-1691.json`; the
existing `gh-task-permission-v2.json` and its `codex-090.json` selector still
select the held 0.155.1 / `gpt-5.6-sol` / high profile. Hosted results and
exact revision belong in the draft PR's run receipt. Provider acceptance,
authentication, model behavior, live isolation observations and billed
usage require a separately authorized live call.

**Next action** — Review the exact-source fixture receipt before deciding
whether to authorize one bounded live Codex compatibility check.
