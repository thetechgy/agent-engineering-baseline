# Bounded Direct Mode provider test — separate authorization required

The metering relay, external watchdog, protected native controller, scoped patch
admission and isolated fake-provider network harness are implemented in
[provider_preflight](provider_preflight/README.md). The hosted entry point is
fake-only; it cannot automatically enable a live session. The reviewable
[proposal](provider_preflight/PROPOSAL.json) is not authorization.

One GPT-5.6 Sol session uses official Codex 0.166.0, the matching pinned catalog's
Direct override, exact native outbound tool schemas, low reasoning, standard
tier and never approval. It must natively discover/read a benign nonce skill,
consume a nonzero command outcome, apply a nonce patch, independently verify
bytes, and retain the original harmless escalation denial. Model text alone
cannot pass the scenario. No judge, delegation, hosted tools, fallback model or
automatic second session is included.

Limits are eight generation requests and eight counts; 16,000 input tokens per
request and 128,000 total; 1,024 output tokens per request including reasoning
and 8,192 total; sixteen tool submissions; ten-second command and five-minute
session deadlines; zero retries. Tool output is buffered until the entire
response is admitted. Input counts precede generation. The relay reserves the
maximum charge before forwarding and never refunds an ambiguous reservation.
The host owns termination and verifies container cleanup. Limits and unfinished
scenarios are inconclusive, never a Direct Mode compatibility failure.

Force prompt_cache_options.ttl=30m. At the documented $5/M cache-write input
and $20/M output maxima, generation reserves at most $0.80384. A **$1.00 total
ceiling** leaves $0.19616 for eight count requests, at most $0.02452 each. That
upper bound must cover complete count requests up to 256 KiB, including input
later rejected before generation. Count pricing remains unverified; no assumption
of free counting is used. Confirm account-specific pricing and model access and
refresh the pricing evidence before requesting authorization.

[Non-inference transport evidence](provider_preflight/route-preflight.json)
records verified TLS and an unauthenticated 401 from the public model metadata
endpoint. It proves transport, not account entitlement. No dedicated key is
available here; subscription credentials were not reused. The provider key may
enter only the isolated relay. The agent receives only a trial credential and
can reach only that relay. Live startup requires a separate current authorization
and verified billing record; a selected live execution configuration/host must
pass the same preflight before any generation.

GPT-6.1 Sol is a separately tracked future condition representing the user's
current development model. The bundled catalog defaults and observed local CLI
version do not establish the user's actual active tool mode or reasoning settings.
Qualify actual models/modes separately. [Diagnostics and revision comparisons](provider_preflight/DIAGNOSTICS_NEXT.md)
come after compatibility, with the framework decision still open. Production
configuration, grading, history, protected workflows and PR #109 remain unchanged.

Sources: [GPT-5.6 Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol),
[prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching),
[token counting](https://developers.openai.com/api/docs/guides/token-counting),
[GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol).
