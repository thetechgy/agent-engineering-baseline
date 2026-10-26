# Pester behavioral evaluation pilot

This five-case pilot measures test engineering with executable counterfactuals.
No model evaluation has run and no skill-effectiveness improvement is claimed.
The first milestone is diagnostic-only; public normalization and history remain
unavailable until the shared contract work in
[issue #92](https://github.com/thetechgy/agent-engineering-baseline/issues/92).

## Cases and deterministic outcomes

| Case | Activation intent | Task | Reference and defect checks |
| --- | --- | --- | --- |
| `pester-001` | Explicit Pester 6 request | Test integer collection output | Correct subject passes; filtering and string-coercion defects fail |
| `pester-002` | Implicit PowerShell testing request | Test retry calculations and errors | Correct subject passes; wrong exponent and swallowed errors fail |
| `pester-003` | Contextual module defect | Repair mocks and check transport invocation | Correct module passes; missing call and wrong target fail |
| `pester-004` | Contextual discovery defect | Repair a suite that does not run its data cases | Correct subject passes; four independent boundary defects fail |
| `pester-005` | Negative control | Summarize Python unittest output as JSON | Correct integer counts pass; wrong counts or types fail; no submitted code executes |

Pester suites must execute at least one test on every variant, pass the correct
implementation, and reject every seeded mutant with recognized assertion
failures. Empty, skipped and otherwise nonexecuting suites are unscoreable.
Test count is an observation, not a quality target: an equivalent compact test
that checks every boundary and kills all four mutants is accepted. Weak suites
that pass the reference but miss defects receive a measured failure.

The three collection-test styles, two error-test styles, two module-mocking
styles, and three discovery/runtime-loop styles are independently authored
acceptable solutions. Mutation checks establish sensitivity to these ten
specific regressions, not general coverage or resilience to unseen defects.
The module's transport stub always throws unless mocked; no real network,
cloud, domain, GitHub, Graph service or credentials are required.

For Pester cases, `pester_reference_pass` records reference correctness,
`pester_mutation_detection` records the fraction of seeded mutants rejected,
and `pester_test_quality` requires both. The unrelated negative control records
only `negative_control_correct`. Do not compare these as interchangeable skill
competencies or turn their native aggregate into an effectiveness conclusion.

## Admission, execution and classification

The small AST profile is documented in `support/EXECUTION-PROFILE.md`. It is not
a sandbox for arbitrary PowerShell. Potentially valid unsupported solutions are
coverage gaps and remain unscoreable, rather than receiving zero quality.

The native producer container stops before a separate network-disabled verifier
starts. Candidate execution uses UID 53001, no supplementary groups,
no-new-privileges, bounded resources and immutable input files. Native cgroups
bound CPU/memory; the runner checks actual identities, capabilities, seccomp,
private-file read denials and immutable-file write denials. The high worker UID
avoids sharing the hosted runner's per-user process limit. Qualification uses
native concurrency two, matching the existing benchmark policy.

The grader emits only fixed classifications and numeric observations. Raw
PowerShell output, exceptions, script extents and assertion actual/expected
values never enter grader logs. The shared artifact allowlist and redaction
remain authoritative. Protected fixture markers reject artifact staging as an
additional containment check, not a general data-loss filter.

The grader pre-arms the existing native failed sidecar before execution.
`invalid`, `unsupported`, `timeout`, `infrastructure_error` and interrupted
outcomes remain unscoreable. A numeric transport zero may exist but must not
become measured quality. A single unscoreable trial makes the complete paired
pilot comparison inconclusive. `failed` means a completed, evaluated failure.
Model-judged standard dimensions are not collected in `custom_only` mode.
Activation and substantive skill use still require trajectory/evidence review;
SkillEvaluator 0.3.0 heuristics and aggregate lift do not establish causality.
Missing token/runtime observations remain unknown.

## Public versus verifier-owned content

The overlay is outside the distributable skill because APM normally discovers
skill `evals/` content regardless of publication `includes:`. The authored skill
instructions, deployment bytes, manifest and dependency pins are unchanged.
Preparation verifies authored/deployed skill bytes and creates a minimal
repository outside the checkout. Legitimate inputs match in both arms. Native
Codex registration copies the actual skill into the unprivileged user's
`$HOME/.agents/skills`; baseline tasks contain no target skill.

Grader code, private reference copies, mutants, profiles and qualification
solutions never belong to agent build contexts or ordinary APM deployment/
package outputs. Only allowlisted/redacted native evidence is retained. These
files are public repository content, not secrets: agent Internet access could
retrieve them. The tasks forbid fetching evaluator answers; observed
contamination makes later results inconclusive. This is not a blinded holdout.

## Credential-free qualification

Use the existing pinned evaluator Python 3.13 environment:

```bash
python -B -m unittest discover -s .github/tests -p test_pester_evaluations.py -v
```

On a disposable hosted runner with the existing evaluator setup and verified
Docker Compose 5.6.1 plugin:

```bash
python -B .github/scripts/pester_container_validation.py
```

The helper expands 26 reviewed fixture submissions into a temporary qualification
dataset, then uses Harbor's native scheduler, oracle, separate verifier,
collector and HTML renderer in both arms (52 trials). Fixture identities are
created before native staging; trusted staged identities are not edited.
No Codex/model/provider/judge is invoked. The collector's `codex` directory
convention is retained; actual trial metadata and explicit qualification
metadata identify the oracle, and reports remain diagnostic/incomplete.

Qualification includes valid and weak suites, wrong module scope, broken
discovery, skipped/empty/malformed submissions, a real worker CPU timeout,
missing PowerShell and a deliberately modified Pester version manifest. The
version test proves runtime pin rejection; it does not qualify Pester 5 or 6.1
behavior. Pester attributes the wrong-scope fixture's `BeforeEach` error to its
executed test, so it is a completed failure; broken discovery is unscoreable.
Shared artifact checks cover rewards, logs, failure diagnostics and
reports. Oracle runs have no model trajectory; shared trajectory carriers are
also tested with injected protected payloads.

Local parser and trusted Pester fixture probes are component evidence. The
hosted job is required for container qualification; missing Docker is a failure,
not a successful skip. Do not install Docker or change workstation services.
Frozen APM regeneration can be checked through the existing
`scripts/apm_regeneration.py` entry point with the reviewed APM executable.

## Runtime inputs and deadlines

Task builds reuse the reviewed Debian image digest and 20261010 snapshot from
the shared task-build policy. Extra direct packages are libicu76 76.1-4,
curl 8.14.1-2+deb13u5 and ripgrep 14.1.1-1+b4. PowerShell 7.6.6 and Pester 6.2.0
are hash-verified at build time, followed by real import/version checks.

PowerShell archive SHA-256:
`ddbc4a2d113bbd46d283cfedcbcd117a70caefd7673f41f2b4e0000badf103bc`.
Pester Gallery package SHA-256:
`e6ac7418d4f12500269aaca58ae56cf1caafbbf1afa2cec334e289d1cf50a239`.

The per-file cap is 64 MiB. A trusted PowerShell 7.6.6 version command reproduced
CoreCLR failure (exit 137, `0x8007000E`) at 1 MiB. At 16 MiB startup worked but
Pester import/execution failed; 64 MiB permitted both with other limits unchanged.
Each captured stream is bounded by that cap; stdout exceeding 1 MiB is rejected
before JSON parsing, including valid prefixes followed by padding or extra data.
This does not relax container memory/CPU limits or retry failed candidates.

Up to five variant processes each have 30 seconds including startup and five
to reap. Successful admission has at most 15 seconds; preparation has 10 and
finalization/cleanup 20. The 220-second case budget fits inside the native
240-second verifier deadline. An admission timeout stops before variant runs.
Image build/start deadlines are separate. Qualification uses two native jobs
with concurrency two; outer deadline exhaustion remains incomplete evidence.

## Authorized paired evaluation and interpretation

After offline qualification, a separately authorized protected manual benchmark
may select `skill=powershell-pester-6`, `mode=confirmation`. The shared workflow
uses the same model, task inputs, policy and grading in both arms. Never skip the
baseline or stop on pass. No model-backed run is required for CI.

The shared selector/preparer, inventory, native collection/recovery, evidence
validation and artifact pipeline own this integration. Standard selection,
direct history publication and public normalization reject this diagnostic
profile. No standard judge fields are fabricated and no Pester report generator,
history store, dashboard or analyst pipeline is introduced. Generic custom
metrics/applicability admission remains centralized in issue #92.

The suite covers bounded Pester 6.2 tasks; it does not qualify older project pins,
all valid PowerShell idioms, arbitrary module initialization, real external
services, security against a general PowerShell adversary, or hidden holdouts.
Native Codex installation/bootstrap supply-chain behavior is inherited and is
not qualified by the oracle's skill-registration check.

Review real paired failures and unsupported outcomes before changing the skill.
Preserve the evidence, isolate the faulty behavior, add a focused mutant and
multiple acceptable solutions, and qualify any necessary admission change.
Avoid grading assertion style, helper preferences, or test count as quality.
Do not alter historical scores or broaden shared schemas as part of this pilot.
