# Unscored security-finding retention, issue #95

This repair is qualified with credential-free fixtures and awaits PR review and
merge. It does not qualify a successful agent task, live provider routing,
security-detection accuracy or skill effectiveness. Final executable revision,
terminal selected CI and authenticated report artifacts belong to the PR description.

Main was verified at #138 merge `3fa44f7cf92dc0523ad0ecd959b584190da06f02`,
with no intervening change. #138 already moved publisher preparation and both
orchestration hosts to the pinned 0.9.0 environment. Static quality, benchmarks,
private reviews and historical replay keep their existing owners.

## Demonstrated failure and correction

The original #137 reproduction and its blocked receipt remain in Git at that
base and in `evaluator-090-adoption/receipt.json`. The unchanged file-reading
verifier and real unscored collector reproduced one known secret-exposure finding
and one known sensitive-path finding becoming zero collected findings. Both
verifier runs remained unsupported, with quality unavailable. The old standard public boundary also refused the diagnostic
because it lacks a scored `trial_id`; no public report was admitted. The replacement
regression failed twice on offline-v2; fixed summaries and the log hash are in
`receipt.json`. No raw verifier payload or secret value is retained in that receipt.

The owning collector's `_failed_judge_diagnostic` now projects only bounded
`details.security.findings`, rather than dropping them or copying arbitrary
`details`. It versions that diagnostic as `aeb-unscored-security-v1` and records
the actual trial directory identity separately from scored `trial_id`.
`_save_unscored_trials` retains the existing failed/unscored status, primary native
exception and independent evaluation/collection errors. Numeric transport zero
remains native transport data, never a task-quality measurement.

Repository admission binds diagnostic version, producer, case, trial, arm,
collector carrier, native runtime/model and failure evidence before preserving
findings. The carrier can differ from the fixture runtime; neither is a tool or
skill attribution. The standard path and custom path both retain unavailable
quality, including public raw quality fields. The existing observation/reference
projection carries security evidence to the consolidated report's supporting
evidence disclosure. Artifact redaction and HTML escaping remain in place.

## Bounded contract

The shared source is `.github/scripts/unscored_security.py`; identical bytes are
carried in the successor evaluator patch. It accepts the released finding fields
and types, at most 64 findings, text fields of at most 2048 characters and tool
labels of at most 128. Optional tool and prior-skill-use fields survive only when
present. No authorization judgment, command success or causal skill attribution
is created. Native `source` and detector flags retain their original meaning.

Finding IDs hash the canonical sanitized finding record. Exact sanitized duplicate
records collapse once across sidecars. The ID identifies a finding record, not an
execution event; two otherwise indistinguishable records are not independently
counted. A public duplicate, altered ID, extra field or contradictory status
rejects. Findings remain tied to the observation's captured reward reference.

Missing, malformed, oversized or contradictory security populations produce
explicit unavailable evidence with a closed error code. Valid findings from other
sidecars survive as partial evidence. Duplicate JSON keys and unreadable/linked
sidecars use the existing bounded-read failure route and retain a collector error;
they cannot become clean security evidence. Conflicting sidecar case identities
reject collection. Security evidence carries no pass flag or numeric score.

## Producer identity and replay

The successor is `skillevaluator-0.9.0-offline-v3`, using
`skillevaluator-v0.9.0-evidence-v3.patch`. Its profile binds patch, installed source,
lock and backend hashes. Dependencies and upstream revision are unchanged.
Package version 0.9.0 alone does not identify a producer. Public policy admission
selects the recorded producer and patch; native normalization also verifies the
owning implementation and lock bytes.

Offline-v2's original patch is unchanged and its exact profile is retained as
`evaluator-0.9-offline-v2.json`. Replay its native records from repository revision
`3fa44f7` with that revision's `candidate-next` setup and original receipts; do not
apply the successor patch to them. Current data-only consumers can render the
original admitted public records with their original policy identities. The 445
prior custom profiles are unchanged; 28 source-only successors bind the changed
shared admission/rendering source. Metrics, active production profiles, frozen
selections, experiments, original grades and closed allocations are unchanged.

## Qualification and limits

All 15 focused checks passed locally. The 22 publisher checks had 21 passes and
one retained setup skip; all 34 orchestration checks passed. A redundant broad
local evidence suite was interrupted and is inconclusive; normal selected CI owns
the complete contract suite. The authenticated historical scanner report also
reproduced byte for byte (`d745c7b25dcacc6e1629f0a0747ca0349412be455c2dd07b4ced1968ac0be759`).

The first hosted run stopped in the historical CLI controls because their isolated
copy list omitted the new shared module and retained profile. Both are now copied;
all nine affected controls pass on the exact existing review/validator owners.
Run `43642881242` was cancelled for this known follow-up after its failed job log
was retained and is inconclusive overall. Its required validation also caught a
duplicate top-level checkpoint heading, corrected in the same follow-up. Production implementation, producer
identity and review owners are unchanged by this fixture correction.

The next full contracts run had 975 passes, 106 skips and one failure: the new
helper's provenance input-list entry had changed a file frozen by the return-contract
experiment. That file is restored byte for byte; the input-list entry now belongs
to shared admission code. All 73 frozen-file hashes and both selected frozen/source
controls pass, and all 15 focused repair/identity controls pass again. The freeze,
task criteria and experiments were not refreshed. Run `43644136806` was cancelled
after retaining the failure and completed repair-report artifact; it is inconclusive
overall. Final-revision CI remains authoritative.

The active reproduction reads actual trajectory/entry files in a fresh verifier
process whose audit hook refuses network and child processes, then uses the real
collector. Four controls reach artifact sanitization, public JSON and consolidated
HTML: secret exposure, sensitive-path evidence, unsupported-only execution and
unlinked output. Known findings survive once per observation; secrets remain
absent; unlinked output has no invented tool or skill attribution. Unsupported-only
execution has no known violation or passing security result. Baseline evidence
stays unknown. Standard candidate admission is independently exercised through
its existing native fixture; export uses the existing admitted oracle path.
No benchmark admission or production consumer selection was broadened.

The report is reproduced byte for byte and rebuilt with the retained 0.3 reporting
interpreter using the current data-only consumer source, without native
normalization or regrading. Existing publisher prepare/build/seal and rollback
controls, orchestration controls and historical identity contracts are retained.
The shared `candidate-next` setup verifies the successor patch on a fresh pinned
release, checks the installed implementation and keeps all 107 dependency versions
compatible. An initial incomplete patch assembly was caught by fresh-install
qualification and corrected before delivery; that failed attempt is not a pass.

The #136/#137/#138 authenticated native, scanner and historical receipts remain
evidence for unchanged components. Normal selected CI validates the final source;
it is not replaced by fixture test counts. No inference, judge, credential
retrieval, live gate, allocation, real benchmark, Pages publication or merge occurs.
Older collector owners were not inspected or reproduced for this loss, and are
not backported. All 83 historical upstream assertion failures retain their
recorded dispositions; repository controls do not turn them into upstream passes.

Remaining adoption blockers are the Podman strict-dataset incompatibility,
versioned 0.9 benchmark/recovery/history admission and live-provider qualification.
They remain separate from this visibility repair. Broader detection accuracy and
skill benefit remain unestablished.

One next action: review this repair PR and its final-revision CI receipts.
