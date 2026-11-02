# Bounded provider preflight — no inference authorized

This harness prepares one GPT-5.6 Sol Direct Mode compatibility session. It has
no automatic live launch path. The hosted entry point runs only generated fake
credentials and two internal-only Docker networks. The stock runtime, exact
outbound namespace catalog and custom apply_patch grammar are retained.
[PROPOSAL.json](PROPOSAL.json) is the reviewable condition, limits and billing
record. It is explicitly not authorization.

The protected relay serializes requests, rejects duplicate/replayed requests and
unknown routes/fields, verifies the exact model/catalog, forces standard tier,
low reasoning, max_output_tokens=1024 and prompt_cache_options.ttl=30m. It counts
the full input before generation and reserves all input at $5/M and all output
at $20/M using integer micro-USD. No reservation is refunded after an uncertain
response. All output, including reasoning, is bounded by the upstream cap.
A maximum eight requests gives a conservative generation reserve of $0.80384.
The remaining $0.19616 must cover eight verified token-count fees. Unknown fees
block live startup; fake zero fees make no claim about actual billing.

The default API route's TLS hostname was verified and an unauthenticated
GET /v1/models/gpt-5.6-sol returned 401. See [transport evidence](route-preflight.json).
This establishes transport, not account model access. No API credential was
read and no generation/count POST was sent. A dedicated API key and account
pricing remain unverified. Subscription/Codex credentials are not repurposed.

The relay's real transport implementation has a fixed HTTPS origin/path, standard
certificate verification, no proxy environment, redirects or retries, and requires
a separate fresh authorization/pricing record before reading a provider key.
The operator must confirm account-specific rates, count fees, source identity
and expiry; the record alone cannot establish those external facts. No such
record is supplied by this repository or CI. A live launch remains disabled.

Provider credentials are mounted only in the relay. The agent gets a trial token,
its workspace and a readonly benign skill. Each role runs from an immutable image
ID, with readonly root, all capabilities dropped, NNP, seccomp, PID/memory/CPU caps
and separate PID namespaces. The agent's private bridge has no external network.
Scoped INPUT/FORWARD rules deny host-gateway access and all new agent flows except
the relay port; external DNS and direct upstream/public-IP access are probed.
The real relay route is code-fixed; enabling external relay egress requires the
separately reviewed live execution configuration and approval.

Responses are buffered until the complete terminal population, model, usage,
original call IDs/arguments and tool budget are validated. No prefix of a rejected
response can execute. Only the smoke commands and one exact nonce-bound Add File
patch are admitted. The registered catalog stays intact; registration is distinct
from the narrow smoke authorization. Raw provider output and native submission
remain distinct. Rejected provider attempts are retained before native dispatch.

The controller uses a protected socketpair, non-dumpable memory and the required
Yama boundary. The external host watchdog owns command/session deadlines and
kills/reaps the container; a yielded/in-progress process does not clear a deadline.
The native reader reconciles live/saved scope, call IDs, original freeform patch
input, command exits, native patch outcome and explicit escalation denial.
After native completion, the operator pauses the container and reads bounded
regular-file archives through the daemon to independently verify exact patch
bytes and absence of the forbidden marker. Missing/inaccessible effects are
unavailable, not clean absence. Logs/receipts/grades are not fabricated.

The ledger is created exclusively, held open to prevent inode reuse, append-only
with identity checks, fsync and a hash chain. Restart with that ledger is refused;
there is no budget reset or resume after a failed session. The actual process
restart control requires a nonzero stopped producer and byte-identical ledger.
Every task-owned container, volume, network and firewall rule is removed exactly.
Cleanup failure blocks qualification. Source/raw artifacts from prior phases
remain unchanged.

Required fake controls cover a complete stock-runtime skill read, exit-7 recovery,
custom patch/independent bytes, core Never denial, actual watchdog termination,
HTTP errors, redirects, stream cuts, model mismatch, patch escape, input/output/
tool limits and attempted credential reflection. Unit controls cover independent
request/dollar/time caps, ledger restart/substitution, auth, replay and framing.
Each negative native control requires its exact reason, zero tool release and
one authenticated request (no SDK retries). A generic failure cannot pass it.
The final export distinguishes paired qualification from provider preflight.

A token/tool/request/time cap, smoke allowlist rejection or unfinished scenario is
**inconclusive**, not a Direct Mode compatibility failure. Provider/infrastructure
errors and incomplete evidence remain separate unavailable categories. Only a
complete admitted native scenario can pass this bounded condition. Canned passing
controls do not establish real-provider compatibility or skill effectiveness.

The proposed single live session uses exactly the native skill fixture and
controller qualified here, with the same relay/watchdog/network boundaries,
one fresh nonce, the fixed real route and a separately verified/approved billing
record. It must read the skill, recover from exit 7, apply the nonce patch, verify
bytes and observe a harmless require_escalated denial under never approval.
No judge, delegation, hosted tools, fallback model, second session or automatic
retry is authorized. Stop on any evidence, identity, private-boundary or budget
contradiction. Do not ask to spend until count fees and account access/pricing are
verified and the selected live execution host/configuration passes these controls.

Admission also binds retained request bodies and reconstructed outbound requests to
the ledger hashes, checks response hashes, and compares recovery output types, call
IDs and exact output bytes with native observations. Raw tool records after terminal
completion are rejected. Nine independent corruptions require specific admission
reasons; they run on each newly captured normal scenario and in the independent
reader. Retained archives may be replayed with `AEB_PREFLIGHT_ARCHIVE` and
`test_admission.py`; replay is not a new native capture or provider execution.
