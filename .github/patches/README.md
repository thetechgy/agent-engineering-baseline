# SkillEvaluator 0.3.0 compatibility correction

The legacy-named `skillevaluator-v0.3.0-pin-codex.patch` is the single reviewed
benchmark compatibility artifact. Apply only to upstream
`ac0a04905100acdafc6c95829311a9739c340ff6` through `setup-skillevaluator.sh`.
It retains Codex 0.155.1 and adds bounded execution-evidence corrections. No
dependency update or SkillEvaluator 0.6 adoption is included (issue #86).

## Evidence and defects

Run 40605108248, attempt 1, completed on f4bff2658c2843fbe46d6836e0d2c31d61bb6c70
with dataset e991cb96840e9e4417fd51ade2d7e2b06df25f9789f52f411405763a5746017c.
Its original Skill Lift remains 0.1376. Authentic exported archives contain
redacted diagnostics, not complete original session/runtime files.

The deterministic scanner classified a Python YAML assertion comparing a mount
string as unauthorized access because the string contained
`/var/run/docker.sock`. Explicit `/run/podman/podman.sock` access was missed.
The correction distinguishes literal comparison/output and configuration bodies
from issued access/exposure commands. It adds conventional rootful/rootless
Podman socket forms. Access findings describe issued operations, not successful
execution or established authorization. Unsupported syntax remains unscoreable.

There were 53 native unsupported-wrapper findings in 11 trials. Retained source
shows 39 terminal-semicolon omissions, 11 patch-variable forms, two parallel
wrappers and one conditional output renderer. One patch body is damaged by
redaction; a separate registry command becomes unparseable after redaction.
Consequently replaying redacted trajectories cannot reproduce exact original
membership even when totals agree. No missing original was reconstructed.

Only terminal omission in the existing complete static grammar is supported.
Patch variables, parallel calls and conditional rendering remain unsupported;
their outer result cannot establish individual inner execution. Required missing,
unsupported or ambiguously attributed evidence fails the native verifier before
provider judging. Rich diagnostics remain; unavailable metrics do not enter a
complete aggregate. Collector attribution cannot turn these limitations into
claims that the skill reduced unsafe behavior.

## Boundaries and maintenance

The literal classifier is bounded to 64 KiB and never executes captured code.
It handles conventional literal shell operands and Python comparison/output
constants; unresolved operations remain unknown. It is not a general interpreter
or an execution attestation. Dynamic paths and arbitrary APIs are not exhaustively
detected. Existing destructive, secret and network checks remain independent.
The deterministic scanner does not decide whether privileged execution was
justified; case 7's model-judged rubric retains that responsibility.

These defects belong upstream in SkillEvaluator's normalizer, verifier and
collector. Harbor 0.13.2 preserves outer call/result identity; this correction
does not change Harbor or manufacture nested results. The patch is removable
when a separately qualified upstream integration supplies equivalent contracts.
No upstream submission or paid benchmark is authorized by this document.

The existing patch digest identifies changed grading conditions, changes the
published policy series and orchestration fingerprint, and makes historical
references insufficient to qualify this runtime. Historical scores, reference
registration and publication remain intact. Both automatic suites stay disabled.
The shared standard runtime also affects gh qualification.

`test_grading_evidence.py` applies the production patch to the exact upstream
source in a disposable directory and exercises the actual verifier and collector
without inference. Fixed judge responses can validate assembly only; they do not
establish future semantic judging accuracy. Full original artifact replay and
target-host deployment remain unavailable. Another paid benchmark requires
separate approval and a design addressing residual unsupported evidence.
