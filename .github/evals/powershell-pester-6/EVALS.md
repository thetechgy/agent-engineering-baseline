# Pester behavioral evaluation feasibility gate

This draft currently implements the first case of the approved five-case pilot.
Do not treat this gate as the complete pilot or as measured skill effectiveness.
No model evaluation has been run. Remaining cases follow only after hosted
qualification of the execution and reporting boundary.

## Measurement and isolation

`pester-001` requests tests for integer collection output. Three independently
authored solutions use classic assertions, standalone assertions, and discovery
data. Good tests pass on the correct subject and detect filtering and type
regressions. Weak, skipped, empty, unsupported, and failing submissions exercise
negative paths. Only recognized Pester assertion failures earn mutant credit.

The AST profile is documented in `support/EXECUTION-PROFILE.md`. It admits a
limited language, not arbitrary PowerShell. Valid unsupported code remains a
coverage gap. OS boundaries are independently required: the producer container
stops before a separate network-disabled verifier starts; candidate execution
uses UID 53001 with no supplementary groups, no-new-privileges, bounded process
resources, and immutable subject/test inputs. A high worker UID avoids sharing
the hosted runner's UID and its per-user process limit. Native cgroups bound CPU
and memory; the runner verifies effective permissions, capabilities and seccomp.

The grader emits only fixed classifications and numeric observations. Captured
PowerShell output, exception text, script extents, and assertion actual/expected
values never enter grader logs. The existing shared artifact allowlist and
redaction remain authoritative; protected fixture markers reject artifact
staging as an additional containment check, not a general data-loss filter.

The verifier pre-arms the existing native failure sidecar before execution.
Unsupported, invalid, timeout, infrastructure, and interrupted outcomes remain
unscoreable. The native transport may retain numeric zero, but collection must
exclude it, retain its classification, and suppress the comparison's overall,
pass-at-k and lift. A completed evaluated failure is a measured failure instead.

## Public versus evaluator-owned content

The overlay is outside the distributable skill. The normal skill, APM includes,
and deployment bytes are unchanged. Staging copies verified skill content into
a new minimal repository outside the checkout; native staging then constructs
the comparison arms. Public subject source, contracts and profile documentation
are identical in both arms. Graders, oracle solutions, mutants and reference
copies belong only to the separate verifier build context.

These files are public repository content, not secrets. Filesystem exclusion
does not prevent retrieval over the agent runtime's public network. The task
forbids fetching evaluator answers; observed contamination makes a later paired
comparison inconclusive. This pilot does not establish a blinded benchmark.

## Credential-free qualification

Use the existing pinned evaluator Python 3.13 environment:

```bash
python -B -m unittest discover -s .github/tests -p test_pester_evaluations.py -v
```

On a disposable hosted runner with the repository's verified Docker Compose
5.6.1 plugin and evaluator setup, run:

```bash
python -B .github/scripts/pester_container_validation.py
```

This uses native Harbor's oracle to supply fixture submissions and native
custom-only verification. It performs no Codex/model invocation or judging. The
collector's `codex` directory convention is retained for shared artifact tests;
native trial metadata and qualification metadata explicitly identify the oracle.
It also executes the pinned Codex skill-registration command and checks its
actual unprivileged discovery path without inference. It does not qualify model
activation or the native Codex installation/bootstrap supply chain.

The hosted feasibility job is required evidence. Local real-parser and trusted
fixture Pester probes are component evidence, not container-isolation evidence.
Missing Docker never converts the hosted gate into a successful skip. Do not
install Docker or change workstation services for this task.

## Runtime and deadlines

Task builds reuse the reviewed Debian image digest and fixed 20261010 snapshot
policy. Direct additional packages are libicu76 76.1-4, curl 8.14.1-2+deb13u5,
and ripgrep 14.1.1-1+b4. PowerShell 7.6.6 and Pester 6.2.0 are downloaded and
hash-verified at build time, followed by actual import/version checks.

The PowerShell archive SHA-256 is
`ddbc4a2d113bbd46d283cfedcbcd117a70caefd7673f41f2b4e0000badf103bc`,
from the official release checksum file. The Pester Gallery package SHA-256 is
`e6ac7418d4f12500269aaca58ae56cf1caafbbf1afa2cec334e289d1cf50a239`.

At most five executions each have 30 seconds including PowerShell startup plus
five seconds to reap. Admission/runtime preflight has 15 seconds; preparation
has 10 and finalization/cleanup 20. The resulting 220-second case budget sits
inside the 240-second native verifier deadline before any native multiplier.
Native image build/start deadlines are separate. Outer CI deadline exhaustion
is incomplete evidence, never successful qualification.

## Shared reporting and future model runs

The shared selector/preparer routes this overlay into custom-only, isolated
staging. Confirmation runs are diagnostic. Standard selection, direct history
publication, and public normalization reject this profile. No standard judge
fields are fabricated, and no Pester report generator or history store exists.
Native rewards, trajectories and reports use shared collection and redaction.

The shared inventory discovers this local overlay once. Generic custom metrics
and applicability are not yet admitted by the consolidated public evidence and
AI-analysis contracts; [issue #92](https://github.com/thetechgy/agent-engineering-baseline/issues/92)
tracks that shared integration. No per-skill publication path is planned.
No native aggregate alone establishes activation, skill lift causality, or
real-world usefulness. Inspect actual successful skill reads and substantive
use separately from task outcomes. Missing token/runtime data remains unknown.

After the complete pilot is qualified, a separately authorized protected manual
benchmark can select `skill=powershell-pester-6`, `mode=confirmation`. Do not
dispatch it for offline qualification. Preserve the same model, policy, task
inputs and grading in both arms; never use skip-baseline or stop-on-pass.
