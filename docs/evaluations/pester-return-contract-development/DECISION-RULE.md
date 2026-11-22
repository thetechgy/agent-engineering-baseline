# powershell-pester-6 return-contract revision: decision rule for GPT-6.2 Sol runs

Declared before any GPT-6.2 Sol comparison of this revision. It authorizes no
run, credential, allocation or skill change. The development protocols bind no
decision file, so this rule is not part of their digests. The transfer protocols
bind the frozen DECISION.md; see the stage 3 note.

Current decision: keep the current guidance. Candidate: the exact 22-line
revision, including its second bullet, which has shown no effect either way.

## Counting, per attempt

- Pass: the reference passes and all five defects are caught.
- Type miss: the reference passes, the four boundary defects are caught, and
  `integer-result` is missed.
- Anything else (failed reference, missed boundary defect, unsupported,
  timeout) is a separate finding. An operational stop is not a result.

## Stages

| Stage | Result | Decision |
| --- | --- | --- |
| 1. Current pair | Current: 3 passes | Close for this case on this runtime |
| | Current and no skill: at least 2 type misses each | Gap persists; go to stage 2 |
| | Current: at least 2 type misses; no skill: 3 passes | The current skill may be hurting; investigate that |
| 2. Candidate pair | Candidate: 3 passes; no skill: at least 2 type misses | Fixes the familiar case; go to stage 3 |
| | Candidate and no skill: at least 2 type misses each | The fix does not work here; reject |
| | No skill: 3 passes | Baselines disagree; inconclusive |
| 3. Transfer pairs | Candidate's passes not lower than current's | Owner decides: adopt as a targeted fix, or hold for a fresh case |
| | Candidate lower than current | Reject or investigate |
| Any | Other split or separate finding | One repeat of that pair, then record inconclusive and keep current |

A failure shared by every arm is recorded as a separate finding and does not
decide this revision.

## Scope and limits

- Selections: stages 1 and 2 use `pester-return-development-current-v1-sol62`
  and `pester-return-development-candidate-v1-sol62`. Stage 3 uses
  `pester-return-transfer-current-v6-sol62` and
  `pester-return-transfer-candidate-v6-sol62`.
- Stage 3 note: those two protocols bind the frozen DECISION.md, whose
  numeric-variation clause would probably return DEFER again. Letting this
  comparative rule govern needs a protocol version that binds a new decision
  file; otherwise both readings are recorded. Both protocols also carry
  `authorization_expires_at: 2026-12-01T23:59:59Z`, so a later stage 3 needs
  a new protocol version in any case.
- Runtime: Codex CLI 0.167.0 with GPT-6.2 Sol at High. No retained live run
  of that pairing was found at main 9d004e6. Results apply to that runtime and
  these cases.
- Three passes out of three still allows a true rate from about 0.44 to 1.
- An adoption at stage 3 claims only that the revision fixes the observed miss
  in data-driven Boolean-return tests. Other task shapes stay unmeasured. Once
  adopted, the development case becomes a regression check and no longer
  counts as evidence of lift.
- Every stage needs preparation at the exact revision and the owner's approval.
