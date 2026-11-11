# CLI observation and diagnostic admission

The original failed run remains historical evidence. No paid allocation is
reopened and no inference is authorized. PR #131 and PR #130 remain unmerged.

## Authenticated historical failure

[Run 42923193201](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42923193201)
at reviewed source `22b36d53e9ac7e329ef8c56dc9bdcefb468ca9df`, attempt 1,
contains failed [job 130203029905](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42923193201/job/130203029905).
[Artifact 13813573476](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42923193201/artifacts/13813573476)
was downloaded and matched GitHub's archive digest
`225993dc9f6b1d98198dc52c80588495553729674f7e3a69d16211954ce20348`.
The bounded [audit](historical-audit.json) records the original native identities,
file hashes, exceptions and cleanup.

1. The actual pinned CLI executes the non-forwarding fixture's tool command.
   Both arms' tool events contain curl exit 6, HTTP `000`, and
   `Could not resolve host: api.openai.com`. The first network assertion aborts
   `codex_pilot_probe.py` before its detached delayed child is launched.
2. The fixture still emits a final response. The CLI exits 0 and records a
   completed turn. Neither CLI exit 0 nor the fixture's final sentence establishes
   successful execution of its tool command. The `&&` submission handoff does
   not execute after the failed probe.
3. Harbor performs its separate verification and stops the agent environment.
   `PilotEnvironment.stop` waits for the unlaunched delayed child's file and
   raises `Post-agent CLI child network observation unavailable`. Final policy
   audits are empty. This is missing evidence; it does not demonstrate an
   unexpected allowed/denied network-policy result.
4. The pinned collector's `_save_unscored_trials` projects failed-judge sidecars
   into intrinsically unscored diagnostic reward files without `trial_id`.
   Shared custom admission previously applied the scored-reward identity guard
   to those diagnostics and raised `Reward identity mismatch`.
5. Available native events, failure records and observations were retained.
   Resource comparison confirms disposal for both arms. The historical source
   did not retain the delayed observation because its producer never launched.

The historical runner used Ubuntu 26.04.1, image `20261101.186.1`, runner
2.338.2. Its original DNS state and packet responses were not retained.
A later success cannot explain why DNS resolution failed on that runner.

## Focused correction

The responsible reporting boundary is shared custom evidence admission in
`skill_evidence.py`. The consumer now distinguishes the pinned collector's
failed-judge diagnostic projection from a scored reward. It requires a matching
unscored failure record, a corresponding summary failure, the already-validated
native trial/task/configuration/checksum, matching agent/arm/model/producer
metadata, and matching native exception type, message and time. Both retained
files remain cited evidence. No trial ID is guessed, inserted or rewritten.

A diagnostic cannot contain details, metrics, a score or a passing raw reward.
It yields `unknown` with null/unavailable quality. A reward that claims the wrong
trial ID still reaches the unchanged rejecting guard. Missing failure evidence
and contradictory identities fail closed. Existing deadline-specific behavior
is preserved. The CLI qualification adapter also records failed boundary commands as primary,
with the original trial member and exit status. Native shutdown and any collection
failures remain separate evidence; a completed fixture turn cannot supersede a
failed tool command.

This change improves failure reporting; it does not repair DNS or
create a missing post-agent observation, readiness, model usage or task success.

The [source-maintenance receipt](source-maintenance.json) records appended source
identities. All existing registry entries, active profiles, tasks, criteria,
skills, candidate, model/settings, pins, production timeouts and isolation policy
are preserved. The prior freeze is retained byte-for-byte.

## Native controls and disposition

The existing native deadline workflow has an explicit credential-free comparison
mode. It runs the unchanged base `a8ab2e2e03a2989863a514df2a6b357c44fbc012`
and reviewed head `22b36d53e9ac7e329ef8c56dc9bdcefb468ca9df` sequentially
on one hosted runner with the same pinned CLI, Python, evaluator, Harbor,
Compose, fixture and isolation. Each receives fresh verified Compose client
state. Qualification uses the existing two-arm native probe; no network probe,
resolver, policy, timeout, fixture command or model setting is replaced.
A separate final-head mode fails if readiness or verified disposal is unavailable.
It also runs an explicit missing-child control: the actual pinned CLI invokes the
existing probe with an invalid qualification argument, failing before its delayed
child launches. No network result is fabricated. Both arms must remain unknown,
with null quality, a primary command failure, no readiness receipt and completed
disposal. This is a controlled failure-propagation qualification, not a reproduction
of the historical DNS state.
Uploads retain only the existing allowlisted evidence and source receipts.

The first diagnostic run, [42933660759](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42933660759),
completed the base probe but could not start the reviewed probe because the
first run changed task-owned Docker client state. It is partial evidence, not a
matched comparison. [42934540958](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42934540958)
uses fresh verified Compose state for each source.

The final authenticated comparison, final-head checks, reproduced reports and
merge disposition are recorded in the authoritative checkpoint and linked
[evidence on PR #130](https://github.com/thetechgy/agent-engineering-baseline/pull/130).
The PR descriptions name the exact qualified revision and remaining limitations.
No historical failure is relabeled. Required CI alone is not the merge rationale.
