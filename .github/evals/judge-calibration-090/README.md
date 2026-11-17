# Standard judge qualification and calibration decision

**Paid calibration blocked by request accounting and missing provider usage.**
The credential-free path below tests released request construction and response
processing. It makes no claim about provider compatibility, judge accuracy,
skill benefit or production readiness. All corpus judgments remain **UNRUN**.
There is no allocation, dispatch command, credential request or paid proposal.

## Released contract and assessed profile

Primary source is SkillEvaluator 0.9.0 at
[`b78d14618a694dec84bc9601468f8f711df5cab3`](https://github.com/NVIDIA/SkillEvaluator/tree/b78d14618a694dec84bc9601468f8f711df5cab3).
Repository runtime identity is unchanged
[`skillevaluator-0.9.0-offline-v3`](../evaluator-0.9.json): Linux, Python 3.14.10,
Harbor 0.25.0, existing frozen lock, evidence patch and backend. The upstream
implementation and its tests govern interpretation, rather than release claims.
The existing [consumer ledger](../EVALUATOR-090-95.md) and historical assertion
dispositions remain in force.

The source paths below are relative to that exact upstream revision:

| Boundary | Released implementation and implications |
| --- | --- |
| Construction | `tier3/harbor/runner.py::_judge_model_config`, `_job_judge_verifier_env`, `_job_judge_subprocess_env`; task generation in `adapter.py::_write_test_sh` |
| Selection | Template `harbor/templates/eval.py::_selected_judge_model`: explicit argument, `LLM_JUDGE_MODEL`, `SKILL_EVAL_JUDGE_MODEL`, `SKILL_EVAL_LLM_MODEL`, provider default. Host config first uses dedicated judge aliases, otherwise resolved provider model. Template defaults include OpenAI `gpt-6.1-sol`; they are not silently selected here |
| Authentication | `_public_provider` uses explicit provider or a unique configured provider; ambiguity fails. OpenAI-compatible transport selects `SKILL_EVAL_LLM_API_KEY` then `OPENAI_API_KEY`. Endpoint selects `SKILL_EVAL_LLM_BASE_URL`, then `OPENAI_BASE_URL`, then official chat endpoint. NVIDIA, Anthropic and Bedrock have distinct routes; none is qualified here |
| Request | `_call_openai_compatible`, `_chat_completion_payload`: one user message, `stream=false`, JSON schema, native OpenAI `max_completion_tokens=32768` for held `gpt-5.6-sol`, no temperature. Nominal judge effort is medium; `_effective_reasoning_effort` emits it only for gpt-6 on this route, so it is **omitted** for held gpt-5. No CLI/model setting changes |
| Model judgments | `judge_accuracy` derives a fraction from five Boolean outcome criteria; a supplied score is ignored. `judge_goal_accuracy` derives binary achieved. `judge_behavior_check` validates one numbered result per expectation, true/false/null. Null remains explicit in expectations but contributes no numerator credit; a zero numeric behavior score alone cannot prove task failure |
| Deterministic observations | Activation, negative-case nonactivation, routing, workflow order, security, tool efficiency and declarative checks are local checks. They establish their bounded contracts, not semantic correctness or model accuracy |
| Reference absence | Missing ground truth makes accuracy/goal N/A; no expected behavior makes behavior N/A. Missing trajectory fails before judges. Unsupported execution evidence refuses judging while retaining independently known findings under offline-v3 |
| Partial failure | `_call_required_judge` preserves other valid observations; `main` marks failed evaluation and exits 1 with transport overall zero. Existing collector/admission treats that zero as unavailable quality, preserving other diagnostic observations. No unavailable-to-zero conversion in the report |
| Custom route | `adapter.py::_write_test_sh` runs default first under `set -e`, then `custom_grader_runner.py --mode default_plus_custom`. A default judge infrastructure failure skips the custom runner. Its merge preserves default overall/pass policy and adds custom metrics; a custom task failure need not fail default overall. Independently established task failures must remain separate report evidence and cannot be overturned by that overall |
| Prior pilot | `custom_only` disables judge configuration and judge environment forwarding, and runs the custom grader directly. PR #147 used two deterministic verifiers and zero model judges. Its working CLI Responses route does not qualify this chat route |

Retry/format behavior is in `_urlopen_with_retry`, `_urlopen_with_schema_fallback`,
`_call_strict_judge`, `_call_public_llm_with_provenance` and
`_call_validated_json_judge`. Default **legacy/append** permits three transport
retries after the initial request; confirmed schema rejection may start a second
transport sequence, and invalid JSON/shape may start a second logical attempt.
Explicit fallback lists are not bounded in legacy mode. Empty replies, refusal
and selected model availability errors can move to a fallback; other errors stop.
Anthropic/Bedrock can additionally use built-in refusal fallback. Legacy behavior
can salvage truncated behavior replies. Its apparent judgment count is not an
HTTP count. For one OpenAI candidate, a conservative bound is 2 logical attempts
× 2 schema sequences × 4 transport requests = 16, constrained by the deadline;
configured fallback models can multiply that bound. Other provider internals and
RAGAS are outside this bound.

Under **strict/replace**, at most three configured model candidates receive at
most two requests each, including transport retries and schema downgrade. The
first completed reply is final, including invalid shape, refusal or empty reply;
there is no format retry or salvage. Only specified availability failures move
models. The assessed profile has **no fallback models**, one transport retry and
thus at most **two HTTP requests per required judge**, six per full verifier.
The default per-judge wall budget is 180 seconds, with request timeout at most 90;
this fixture shortens wall budget to one second and backoff to milliseconds for
actual timeout/retry controls. It does not qualify production deadline behavior.
Nonreasoning OpenAI goal judging may select RAGAS and then the custom prompt
fallback; strict policy and this reasoning model avoid that route.

Upstream tests supporting these distinctions include
`tests/tier3/test_judge_policies.py` (strict caps, schema debit, refusal, invalid
completed replies, deadline and legacy behavior), `test_judge_contracts.py`,
`test_judge_failure_artifacts.py`, `test_judge_http_response_contract.py`,
`test_judge_result_semantics.py` and `test_ragas_judge_evidence.py`.
These are source evidence; this PR does not claim a new passing upstream suite
or reconcile the retained historical assertion differences.

## Credential-free entry and retained handoff

After existing `setup-skillevaluator.sh candidate-next`:

```sh
"$SKILL_QUALIFICATION_PYTHON" -B .github/scripts/qualify_standard_judges.py qualify --output "$EVIDENCE"
"$SKILL_QUALIFICATION_PYTHON" -B .github/scripts/qualify_standard_judges.py reproduce --output "$EVIDENCE"
```

Use a new external persistent directory for local evidence. The entry creates an
empty home and an allowlisted environment, supplies only a fixture sentinel and
rejects external socket/DNS destinations. Its HTTP adapter accepts only the fixed
official OpenAI URL, then sends the original payload to a loopback-only responder
with no forwarding code. The upstream builder still sees the native URL. Judge
functions, parsing, scoring, native verifier, collector and admission stay real.
No production adapter registers this transport, and no live action exists.

The existing behavioral fixture now accepts an optional transport context while
preserving its original simulated-judge controls. Twenty native TrialResults
exercise valid/wrong/partial replies, missing usage, schema fallback, transient
retry, actual deadline, independent security failure, unsupported evidence with a
retained finding, a declared runtime-failure injection and genuine Podman negative
case N/A. Additional required-judge probes preserve an explicit null behavior verdict and
cover refusal, HTTP error, wrong
provider envelope, exhausted schema/retry budget and legacy format repair. The
latter are qualification probes, not a second supported live profile.

Retained requests include payload, response, status and actual request counts;
upstream judge attempts preserve diagnostic prompt/reply/problem evidence.
Qualification labels every reply as fixture origin and every corpus observation
UNRUN. Existing public admission/history controls reject live relabeling and
fixture promotion even if the optional benchmark metadata is stripped. The
qualification manifest cannot authorize paid execution.

The existing current-evaluator cohort job produces the artifact after pinned
setup; its existing report job downloads the same run/attempt artifact on a fresh
runner, reinstalls the same owner and reproduces the HTML byte for byte. No new
matrix, campaign runner, scoring implementation or dashboard is added. The
qualification appends escaped reference/accounting tables using the existing
consolidated renderer; production rendering is unchanged. Source/corpus and request
handoff digests are checked on reproduction. Artifacts remain data, never code.
Final executable revision, terminal selected checks, artifact authentication and
independent reproduction belong to the draft PR receipt.

## Frozen references and review rules

[The seven-item corpus](corpus.json) binds exact source hashes and retains task
context. It deliberately mixes executable-check-backed controls and bounded
reviewed controls, rather than calling every item a retained live submission.
Stimuli exclude incidental arm labels. Source selectors remain visible only in
reference evidence. Pester contributes test-content judgments; it does not
manufacture gh authorization coverage or new Pester runtime evidence.

Reliable narrow labels are control-01's factual result; control-02's prohibited
extra write despite correct output; control-04's healthy/unhealthy test coverage;
control-05's missing unhealthy test; and control-06's appropriate local-only
nonactivation. `Should-BeTrue` is supported by [Pester 6](https://pester.dev/docs/commands/Should-BeTrue)
and explicitly admitted by the frozen [runner](../powershell-pester-6/support/Runner.ps1);
assertion style is not control-05's defect. Reference v2 corrects the earlier
unsubstantiated syntax caveat before any model calibration; the missing-branch
label is unchanged. Their broader overall scores remain unscored. Controls 03 and 07
lack sufficient evidence for compliance/execution conclusions and require review.
A full skill read or a confident success claim establishes neither successful
work nor authorization.

Before any paid calls:

- A **false pass** accepts the prohibited write or asserts missing branch coverage
  exists. It also includes unsupported confident success when essential execution
  evidence is absent, recorded separately from scored-reference false passes.
- A **false failure** rejects a supported narrow correct result or requires gh
  activation on the explicit local-only task.
- An **unsupported judgment** claims more than the supplied evidence establishes,
  substitutes missingness for task failure, or offers a verdict the rubric cannot
  represent. A behavior null is retained even if its numeric score is zero.
- An **infrastructure failure** is refusal, provider/transport error, timeout,
  invalid schema, exhausted request budget or missing required accounting. It is
  not a false failure of the submission and cannot enter accuracy denominators.
- Disagreements retain expected versus observed verdict, exact evidence and
  reasons. A human inspects the original task and available artifacts, classifies
  the conflict and records an explanation without rewriting historical grades.
  Deterministic correctness/authorization remains independent. Never average a
  contradictory model pass into an independently established task failure.
- One false pass on known-broken work prevents authoritative use for that question
  until investigated and separately requalified. Useful, evidence-specific
  disagreement explanations may justify advisory use. Unsupported binary
  conclusions, repeated false passes or explanations detached from evidence
  support declining these judges for those questions. No aggregate percentage
  from seven controls validates general accuracy.
- A repeated neutral-label/order control is deferred until accounting is fixed.
  If paid calibration becomes justified, predeclare one repeated known-broken
  item with neutral ID and reversed presentation order to test consistency and
  label/order sensitivity. Count all of its actual requests in a new proposal;
  do not add repeats after seeing favorable or unfavorable results.

## Current decision

The local boundary supplies response usage, but `_call_openai_compatible` discards
it. `runner.py::_budget_usage` counts `judge_attempts.json` entries, not transport
requests; its token/cost fields come from agent trajectories. Schema fallback and
retries therefore undercount actual judge requests, and missing usage does not
make upstream judging fail. This violates the existing stop-on-unknown-accounting
requirement for a paid path. The declared runtime-failure injection also removes case 6 diagnostics after
three real local requests; that missing evidence is not attributed to upstream
retry accounting. The fixture records these gaps; it does not patch
upstream or silently treat synthetic accounting as live accounting.

A paid proposal is **not justified yet**. There is no price/allocation estimate to
approve, no agent attempt, no skill change and no reopened historical allocation.
The supported interim path is deterministic task checks plus bounded human review
of specific ambiguous questions. Provider compatibility and grading accuracy
remain separate UNRUN questions. Claude Code, Copilot CLI, Anthropic, Bedrock,
other models and production adoption are not qualified.

**One next decision:** review this qualification and decide whether to authorize a
focused request/usage-accounting remedy before preparing any paid calibration.

Workflow review: critical 0, high 0, medium 0, low 0. Existing read-only triggers,
SHA-pinned Actions, nonpersistent checkout credentials and same-run artifact
consumption are retained; no secrets, protected approvals or remote writes are
added to the workflow.
