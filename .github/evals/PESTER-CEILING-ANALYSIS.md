# Retained Pester ceiling analysis

**Decision A:** retain one exploratory Boolean-contract case. The ceiling tie conceals
an actual coverage omission shared by both arms: all six `pester-004` suites accept
integer `0`/`1` returns despite the documented Boolean contract. This warrants a
focused candidate, not a skill-effectiveness claim or a skill edit. Stop this
investigation here. The paid allocation is consumed; no further inference,
judges, retries or dispatches are authorized.

## Evidence identity and method

The twelve submissions are from [PR #122](https://github.com/thetechgy/agent-engineering-baseline/pull/122),
[run 42529955611, attempt 1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42529955611),
[live artifact 13639971439](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/42529955611/artifacts/13639971439).
Executed revision: `a99992fabaa80b315f57dccf66660c382a4100ee`;
archive SHA-256: `b2aee349d291d76f0c1915209c4bd9792ef0c9280ac7243054dc42bb34db7e45`.
Fresh GitHub metadata verified repository, workflow, source, successful run/attempt,
artifact identity and digest against the retained ZIP; the existing bounded extractor
verified its 320,216 bytes. All twelve submission sizes/hashes, ledger/native
case-arm-trial bindings, grades, command events and staged deployment identities
were checked. This is qualitative analysis, not a new model-judge score.

Original live evidence is `pester-effectiveness-v5`, with frozen v3 grading.
PR #122's later v6 reporting correction at `70f0702aa2a57394d1037370f6fbde60b4fb3a52`
exposes defect rows and trial identities; it is not the executed live revision.
Original reference and joint-quality passes remain 3/3 in each case/arm;
`pester-003` detected 5/5 defects on every trial, `pester-004` 4/4. No grade is replaced.
The comparison was prospectively frozen on reused cases, with no measured skill advantage.

The [audit receipt](pester-ceiling/audit.json) retains every original submission
member/hash, trial, grade, read event and usage value. Evidence paths below are
relative to the artifact's `cohort-live/evidence/`: `submissions.json`,
`attempt-ledger.json`, `grading-outcomes.json`, `staging.json`, `workspace-profile.json`,
`runtime-audits.json`, `tool-events.json` and `native/.../trials/<trial>/codex.txt`.
The original CLI command events match the extracted events exactly. The archive,
fresh metadata and data-only audit script are retained in the task's persistent
evidence directory; raw traces are not copied into the repository.

## Availability, attempted access and successful reads

All six current trials had the same deployed skill and two supporting files.
`SKILL.md` SHA-256 is `b57df2ff4072b2e25744ae2bd530b02bbb6ab83a22a0d374c73d48de4dc70887`.
The receipt contains the complete three-file manifest. Each successful read below
has a matching started event, exit code zero and returned bytes hashing to the
corresponding deployed file. A listing alone is not counted as a read.

| Current trial (slot) | Available | Attempted reads | Successful read events | Observable behavior consistent with guidance |
| --- | --- | --- | --- | --- |
| 003/1 (01) | Yes | Skill and compatibility reference | `item_3`, `item_4` | Module-scoped mocks and exact filtered/unfiltered call checks |
| 003/2 (08) | Yes | Skill and compatibility reference | `item_3`, `item_5` | Same interactions; inline discovery data |
| 003/3 (09) | Yes | Skill | `item_2` | Module-scoped mocks; separate healthy/unhealthy checks |
| 004/1 (04) | Yes | Skill | `item_2` | `BeforeDiscovery` data, `BeforeAll` import |
| 004/2 (05) | Yes | Skill | `item_2` | Same phase separation |
| 004/3 (12) | Yes | Skill | `item_3` | Same phase separation |

No successful read of `references/execution.md` is recorded. These are authenticated
producer-reported command results, not proof of internal attention, comprehensive
instruction following or causal benefit. The Boolean omission despite successful
skill reads specifically limits any instruction-following claim.

Absent-arm manifests contain no target skill or supporting files: removing exactly
the three skill files from each current-arm staged manifest reproduces the absent
manifest, including identical prompts, inputs, Dockerfiles and verifier members.
Each absent runtime audit reports `skill_deployed=false` at the registered home
path; current audits report true with the producer's full-directory equality check.
The workspace source directory is absent in those staged images; runtime audits
show no host mounts, no MCP and distinct agent environments. Native configurations
have no extra skills or instruction paths. Retained evidence supports absence at
both deployment paths with no unintended mounted/injected copy; it is not a
forensic image of every runtime filesystem byte or proof about model pretraining.
Absent agents could inspect installed Pester help/source, which is a legitimate
shared dependency, not target-skill contamination.

## Contract and coverage mapping

The same [module contract](powershell-pester-6/support/cases/pester-003/input/README.md)
and [boundary contract](powershell-pester-6/support/cases/pester-004/input/README.md)
apply to both arms. Frozen executable definitions are in
[`case_files` and `fixtures`](../scripts/codex_pilot_effectiveness.py).

| Requirement | Submission behavior | Executable evidence and classification |
| --- | --- | --- |
| 003: healthy and unhealthy Boolean results | All six test both states with Boolean identity assertions; five also explicitly check type | Reference passes; `unhealthy` detects forced true. Satisfied for these states; no frozen type-only mutant |
| 003: exactly one private transport call, same target | All six check total and parameter-filtered exact counts in matching module scope | `bypass`, `double`, `target` each detected by all six; genuine interaction checks, not output-only proxies |
| 003: original returned target | All six check case-sensitive equality for distinct targets | `echo` detected by all six; no observed shortcut substituting the expected output |
| 004: execute 0, 1, 65535, 65536 and their expected decisions | All six execute four boundary checks; current uses `BeforeDiscovery`, absent uses inline data (trials 1/2) or `BeforeDiscovery` (3) | Reference passes and `zero`, `lowest`, `highest`, `above` each detected by all six. Frozen omission controls isolate each boundary; broken discovery is unavailable |
| 004: Boolean return contract | All six use coercing value equality and omit Boolean identity/type checks | **Coverage violation missed by frozen checks:** all six pass the exploratory integer-return mutant as well as the reference |
| Keep inputs unchanged; write only the suite | Recorded file changes target only `output/Subject.Tests.ps1`; all three absent 003 trials additionally invoke `-CI` | `codex.txt` slots 02/07/10, events `item_11`/`item_13`/`item_9`: report writes outside output denied, then recovered. Actual attempted scope violation, not a final-suite failure; original quality grading does not measure this |

All 54 original defect detections have assertion failure evidence after passing
references. The tests call the supplied commands; there is no observed hard-coded
answer bypass. Absolute `/workspace/input` paths are part of the supplied runtime,
not evidence of a defect. Imported modules and mocks do not contact real services.
Unmeasured areas include arbitrary targets/ports, non-Boolean transport responses,
module lifecycle across files, resource cleanup, other runtimes and real networks.
Those are not automatically task defects. Absent 003/2 additionally tests numeric
transport conversion, but that dependency behavior was not explicitly required;
it earns no retrospective bonus. Module-local versus external mocks, inline versus
discovery data, classic versus standalone assertions, verbosity and test counts are
legitimate alternatives, not quality rankings.

## Focused exploratory diagnostic and candidate

A reviewed copy of each 004 submission ran with PowerShell 7.6.9/Pester 6.2.0 through
the existing `support/Runner.ps1`. Only literal `/workspace` paths were mapped to
isolated disposable workspaces. Each suite passed all four tests against both the
reference and a single change from `[bool] (...)` to `[int] (...)`. This preserves
boundary decisions while violating return type. It can break typed/serialized API
consumers; it is more than an assertion-style preference. These twelve diagnostic
executions were devised after output inspection and are **exploratory**, separate
from the original independent grades. They are local component evidence, not new
container qualification, production scoring or a live model evaluation.

The single candidate is [Boolean port-contract repair](pester-ceiling/candidate/prompt.txt).
It reuses the existing 004 input, broken suite, execution profile, reference and four
boundary mutants; [integer-result.ps1](pester-ceiling/candidate/integer-result.ps1)
is its only additional implementation fault. The prompt makes the already relevant
type contract explicit with an API-consumer rationale. It does not name the skill
or require a specific solution. This changed prompt prevents treating a future
comparison as another trial of the frozen cohort.

Good work must pass the reference and reject each independent boundary fault and
the type-only fault through assertions, with real execution and no skipped/not-run,
container or discovery failures. General test breakage receives no defect credit.
Independent acceptance is based on behavior, not syntax or test count:

| Control | Reference | Four boundary faults | Integer-output fault |
| --- | --- | --- | --- |
| Boolean identity assertions with inline data | Pass | Reject each | Reject |
| Classic type plus value assertions with runtime iteration | Pass | Reject each | Reject |
| Existing value-only suite | Pass | Reject each | Miss |
| Type-only suite | Pass | Miss each | Reject |
| Existing broken-discovery suite | Unavailable | Unavailable | Unavailable |

All 30 control executions matched this matrix. The
[component receipt](pester-ceiling/validation.json) includes exact input hashes,
raw runner counters and the twelve retained-submission diagnostics. Reproduce with:

```sh
python3 -B .github/evals/pester-ceiling/validate.py \
  --pester-manifest "$PESTER_MANIFEST" --output "$EVIDENCE/boolean-controls.json"
```

Use the existing Pester 6.2.0 manifest and a fresh persistent evidence filename.
Optional `--retained-evidence` selects the authenticated artifact's evidence root.
The validator uses the existing runner and honors `TMPDIR`; it does not stage an
agent or register a production grader. Alternative solutions remain admissible
subject to the existing execution profile. Container integration and prospective
admission are not qualified by these local controls.

The skill plausibly helps because its Assertions section distinguishes Boolean
identity from coercion and says to match assertions to contracts. Yet all current
004 submissions read that text and still missed this requirement. Candidate
sensitivity establishes a useful failure mode, not predicted skill advantage.
The existing 001 integer-output regression is complementary; it does not establish
that these Boolean boundary suites reject numeric substitutes. This candidate is
output-informed development, not held-out confirmation. The reserved confirmation
variant was not read, executed, edited or used for development.

## Usage and duration observations

| Case / arm | Total input (cached subset) | Output | Estimated USD | Agent seconds, trials 1/2/3 | Whole-trial seconds, trials 1/2/3 |
| --- | --- | --- | --- | --- | --- |
| 003 current | 314,635 (256,296) | 5,617 | 0.1984776 | 35.616 / 31.129 / 33.645 | 200.835 / 107.793 / 108.282 |
| 003 absent | 362,645 (294,957) | 7,552 | 0.2403917 | 44.720 / 46.909 / 38.383 | 151.218 / 121.665 / 115.167 |
| 004 current | 230,581 (177,003) | 2,918 | 0.1540363 | 19.971 / 20.338 / 17.499 | 123.445 / 94.179 / 92.766 |
| 004 absent | 167,801 (127,442) | 2,730 | 0.1207622 | 18.288 / 13.642 / 19.478 | 122.032 / 84.980 / 91.218 |

Total estimated usage remains **$0.7136678, not an invoice**. Cached tokens are part
of input, not additional input. Agent and whole-trial durations use native timestamp
pairs; whole-trial time includes setup/verification. Current 003 used fewer tokens
and less agent time; 004 used more tokens with overlapping agent durations. These
three-trial descriptions, including local retry/help behavior, establish no general
efficiency claim and do not substitute for task quality.

**One next action:** review this candidate for a separately frozen prospective
comparison. Further paid work remains unauthorized. Skills, historical results,
production grading/defaults, dependency/runtime pins and isolation remain unchanged.
