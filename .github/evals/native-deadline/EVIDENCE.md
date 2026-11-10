# Native deadline evidence correction

Started from verified main `9f6929f2b2be6ad66b40cd9ab9edf68caa124aee` on
`fix/native-deadline-evidence`. The original checkout and its untracked work
were preserved. This is credential-free lifecycle qualification, not another
attempt in the stopped experiment.

## Historical sequence, unchanged

GitHub metadata and the downloaded ZIP authenticate candidate run
[42847531876](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42847531876),
at that source, artifact
[13779353316](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42847531876/artifacts/13779353316).
Archive SHA-256 is `dde4caee799998981cd09cd1a5324732e8890ba78cc2b50638f90739c67dd81f`.

The retained exception and trial log establish this sequence:

1. Harbor 0.24.0 wraps agent execution in `asyncio.wait_for`. The task's agent
   deadline and the adapter's transport deadline are both 600 seconds; the
   Harbor deadline starts earlier, before adapter preflight/configuration.
   Native `agent_execution` spans 15:47:30.243138 to 15:57:30.617625 UTC.
2. Cancellation reaches pinned SkillEvaluator 0.8.0's secure Compose transport
   while it awaits process communication. Its cancellation containment stops
   **and removes** this project's main container, then reaps the Compose client.
   The retained chain includes `CancelledError`, followed by `TimeoutError`.
3. The adapter's unconditional `finally` tries to execute the producer receipt
   in the unavailable service. Its `NonZeroAgentExitCodeError` replaces the
   timeout before Harbor can convert it to `AgentTimeoutError`.
4. Harbor's subsequent log copy finds no main container. The Codex observation
   hook raises `MissingCodexObservation`. The first recorded exception remains
   the receipt error; the launcher exits 1. Final boundary observation also
   fails on absent stdout. Its `finally` still invokes inherited disposal.
5. The ledger records one failed/unmeasured launch, five unlaunched positions,
   no grading and null token counts/cost. The independent resource comparison
   records completed disposal. Runtime-home cleanup remains `pending` in the
   adapter audit; this is distinct from final container disposal.

The container's lost files, native events and usage cannot be recovered from
this archive. The exact reason the CLI reached its deadline remains unknown.
There is no evidence here establishing a skill defect, provider problem or need
for a longer deadline. The separate 60-second provider stream-idle limit does
not explain the observed 600-second lifetime; no native stream was retained.
The launcher watchdog (1200 seconds) and hosted job limits are later bounds.

Development/current run
[42844732493](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42844732493)
retains six measured outcomes: current and absent each 0/3 primary success,
reference passed, integer-result missed. Its $0.2705338 estimated usage remains
separate from the candidate's unavailable accounting. Seven slots launched,
six measured, seventeen unlaunched; both transfer pairs remain undispatched.
Total spending remains unknown. No allocation is reopened or claimed.

## Native failing-before control

[42862752648](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42862752648)
at `633a587246e16f2965a95ee440854b461e4b0f13` ran the actual pinned CLI against
the loopback non-forwarding fixture, with Harbor's **45-second native agent
limit**, without a shell timeout or mocked execution exception. Artifact
[13785203927](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42862752648/artifacts/13785203927)
was downloaded and hash-verified:
`280142d311fcf4a8e9b406b411937e0811722a9baf0e02dc82908248c2518494`.
The native chain reproduces timeout followed by receipt failure, missing native
logs, stopped scheduling and completed resource disposal. Its profile-admission
failure is retained separately: adding fixture code changed source identity
before successor profiles were registered. This receipt does not qualify reports
or establish which fixture bytes existed before deletion.

## Correction and maintenance boundary

`PilotEnvironment` owns the shared termination and evidence path. It uses the
pinned stop/kill/state-confirmation facility with removal deferred, copies only
three allowlisted log files and one bounded submission from the **stopped**
container, and lets Harbor perform final deletion. No agent command or workload
restart occurs for collection. Docker transfer clients have time and byte bounds, reserving five seconds of
the inherited shared cleanup deadline for the transport reaper;
tar members are validated without filesystem extraction. Runtime homes are never
copied. Existing redaction plus exact delivered-secret redaction apply to logs;
a submission requiring redaction is withheld rather than rewritten. Available
safe submission bytes carry their digest, container identity and `complete=false`.

The adapter preserves its primary exception and skips receipt/scrub exec after
containment. Codex interpretation records incomplete trajectory/usage gaps
separately. Native timeout/cancellation mappings remain reliability outcomes;
task correctness and missing accounting stay unavailable. Actual process failure,
collection failure and cleanup failure retain separate records. No grading
criteria change. Harbor can run its task-owned verifier after recording a native
agent timeout. Such raw results remain diagnostic-only in the new lifecycle
profiles and ledger; strict native failure identity/summary checks still apply,
and public measurements stay unavailable. Historical profiles retain their
previous admission behavior. New source-bound profile identities are appended; all earlier
profile values, experiment settings, prompts, skills and pins remain unchanged.

The unavoidable private-hook maintenance is the override of
`_contain_main_container`, reuse of `_stop_raw_service_containers` and its pinned
snapshot fields, and the existing secure host-environment/redaction helpers.
The evaluator remains pinned at `8149356e4476a1497fb334727f13f699c6fa6ba5`, Harbor
0.24.0, Python 3.14.10 and Codex CLI 0.167.0. Installed dependencies are untouched.
Any future refresh must requalify those hooks and stopped-container transfers.

## Corrected qualification

The focused workflow uses the existing campaign loop, collector, public projection
and HTML renderer. It covers normal measured pass/fail controls, emitted-evidence
timeout, timeout without useful evidence, a genuine failed diagnostic copy and
direct native task cancellation. All fixture usage is simulated, not provider
usage or billing. Complete CLI accounting remains unavailable for interrupted turns.
Final-source hosted execution, authenticated artifact digests, independent
downloaded-artifact admission and report reproduction are recorded on
[PR #129](https://github.com/thetechgy/agent-engineering-baseline/pull/129).
The review status there is conditional on those checks completing. Earlier candidate and four-pair preparation
receipts remain historical and are not relabeled as execution of this correction.

The intermediate corrected run
[42863539519](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42863539519)
retained `AgentTimeoutError`, 2510 bytes of native events, 88 bytes of stderr,
63975 bytes of fixture request/usage evidence and the exact 461-byte incomplete
submission, then completed disposal. Its downloaded artifact
[13787276463](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42863539519/artifacts/13787276463)
has verified SHA-256 `d68ebe99174b0a601654669bacd3f81be2d5f7fa9a5721704306e4da483ab330`.
It remains a failed qualification: the fixture subclass violated the registered
agent-import identity. The control now uses the actual `CampaignCodex` class
through guarded credential-free fixture arguments; admission is not weakened.
The same evidence exposed Harbor's post-timeout verifier execution, addressed
by explicit shared diagnostic-only handling rather than task-grader changes.
