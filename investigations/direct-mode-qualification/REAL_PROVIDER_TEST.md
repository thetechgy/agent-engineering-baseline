# Proposed Direct Mode provider test - separate authorization required

Status: NOT EXECUTABLE by the offline controller. No inference is authorized.

Use official Codex 0.166.0, the matching source catalog's gpt-5.6-sol entry,
changing only tool_mode to direct. Record CLI/archive/catalog hashes and the
provider model field. Use the real OpenAI Responses endpoint through a trusted,
operator-owned metering relay, standard service tier and low reasoning effort.
Keep the original tool advertisement unchanged. Set the relay provider's
`request_max_retries=0`, `stream_max_retries=0`, `supports_websockets=false`,
`wire_api=responses`; set `model_reasoning_effort=low`, `service_tier=default`
and approval policy `never`. Block retries independently at the relay and latch
closed after any upstream error, timeout, redirect or incomplete stream. No judge, delegation,
MCP, hosted search, image or other billed tools.

One fresh session must discover/read a benign native skill with a fresh nonce,
execute a command, apply a patch, independently verify bytes, recover from a
nonzero exit, and observe a harmless deliberate escalation denial under never
approval. Missing any path within the budget leaves it unqualified. Preserve
original provider submissions, native outcomes and independently checked effects.

Hard limits: eight generation requests, 16,000 counted input tokens per request,
128,000 input tokens total, 1,024 output tokens per request (including reasoning),
8,192 output tokens total, sixteen tool submissions, ten seconds per command,
five minutes total and zero retries. An operator watchdog must stop and reap the
trial container when a command exceeds ten seconds; native yielding is not a
process timeout. Buffer/validate a complete bounded provider response before
releasing tool submissions, and reject an over-budget response in full. Count complete inputs, including tools,
with /v1/responses/input_tokens before forwarding; set max_output_tokens upstream.
Reject unknown models/endpoints, unsupported request fields, redirects and any
request beyond the reserved budget. Cap failures must be tested with a canned
provider before credentials are available. The relay alone receives the real key;
the agent gets a trial-scoped relay credential and cannot reach the provider directly.

At the documented $4/M input and $20/M output, the generation ceiling is
$0.67584. Reserving the documented 1.25x cache-write input rate raises the
conservative generation reserve to $0.80384. Propose a **$1.00 total ceiling**,
including at most eight token-count requests. Before any provider call, verify
token-count pricing and reserve it within the remaining $0.19616; the public
token-count guide does not establish that those requests are free. Unknown
charges block execution. Expected generation usage is 30-80k input plus 2-6k
output, approximately $0.16-$0.52 depending on cache billing. Recheck prices
immediately before authorization. If routing or billing cannot honor the
ceiling, stop before inference.

This compatibility session does not establish behavioral representativeness.
After it passes, separately authorize existing paired cases gh-002,
gh-010-partial, gh-013-hardening and Podman case 1. Compare discovery, skill reads,
command choices, recovery and task effects under separate mode identities.
Canned task execution cannot establish model quality or equivalent effectiveness.
The operator metering relay and watchdog are a proposed follow-up, not deployed
or qualified by this canned integration. Before authorization, implement them
with fake-upstream tests proving all caps, error latching, egress and credential
isolation. Verify the provider response model as well as the request model;
record any resolved model identity and reject fallback.

Production default_plus_custom grading, historical admission and automatic
benchmarks remain outside this test.

References: https://developers.openai.com/api/docs/models/gpt-5.6-sol and
https://developers.openai.com/api/docs/guides/token-counting .
