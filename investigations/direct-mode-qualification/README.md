# Direct Mode paired qualification

This is an inference-free production-path experiment on an isolated branch.
It uses the actual `skillevaluator tier3 evaluate` paired CLI and its supported
custom-backend entry point. It does not migrate production, admit history,
modify PR #109, or execute a real model. Results are recorded separately in
`RESULTS.md` after terminal evidence review.

The candidate is official Codex 0.166.0 with the matching gpt-5.6-sol catalog
entry's `tool_mode` changed to `direct`. No runtime source is patched and no
unadvertised tool is forced. SkillEvaluator is pinned to
`d9fa4b4041b31f417f02ed145999ecf1f0c11fcd`, Harbor to its frozen 0.24.0 lock,
host Python to 3.13.15, and uv to 0.13.5. This evaluator snapshot has the
explicit publication compatibility change described below; it is not an
unmodified SkillEvaluator release. The image uses the existing production
gh fixture's pinned build inputs, plus the official Codex archive and the exact
idna 3.18 wheel/hash from the evaluator lock. The archive, executable and catalog
identities are retained; an experiment is not an immutable production release.

`bootstrap.sh` runs one attempt per arm, serially, for three profiles of
`gh-010-partial`: the ordinary partial-attachment recovery, an additional
harmless attempted escalation, and denied reads/removal at private boundaries.
The canned Responses producer supplies predetermined calls. Codex actually
advertises and executes them; no model chooses them. No judge runs.

The backend extends `SkillEvaluatorSecureDockerEnvironment`. It retains its
container launcher, environment handling, cancellation and cleanup. An
operator-owned overlay enforces no external network, all capabilities dropped,
no new privileges, seccomp and a process limit. Actual agent UID/capabilities/
NNP/seccomp/interface values must agree before initialization. The operator
liveness healthcheck checks PID 1 only. Task-authored healthchecks and paired
baseline setup remain removed by the unchanged native stager.

The unchanged gh setup/client/broker/case bytes are hash-checked before root
execution. Public workspace provisioning occurs at image build, using a
separate disposable private directory. Runtime private state is freshly created
for every arm; existing state or socket is refused. Active broker readiness
checks the spawned process's PID/start time, root peer credentials and socket
inode/device. It must leave the audit unchanged. The verifier repeats identity
and active readiness checks after native execution.

The pinned native `skills/extraRoots/set` experimental RPC registers the staged
canonical skill directory. Both arms retain the competing hardening skill; only
the with-skill arm advertises gh. Actual successful native skill reads feed the
unchanged activation check. Private host umasks are normalized only for public,
root-owned skill files. Root-private verifier files are created through bounded
stdin transfer over the inherited protected dispatcher, with ownership, member,
size, link and hash checks. This avoids Compose's observed host-UID preservation
without adding capabilities or making tests public.

The controller uses a protected socketpair, non-dumpable memory and a required
Yama boundary. Operator helpers and the executable are root-owned and checked.
Capture admission reconciles exact provider call IDs/name/argument bytes,
thread/turn/RPC identity, live and saved lifecycle populations, command argv,
terminal outcomes and producer closure. A denied attempt retains original
arguments even when it has no command item. Unknown tools, missing outcomes,
truncation, unclosed command processes or transport loss cannot reach the oracle.
Partial captures retain known prohibited attempts separately; absence remains
unavailable. Ten synthetic corruptions test admission without creating native
observations or grades.

The pinned evaluator silently strips the existing numeric name
`gh_authorization` as a sensitive field. `prepare_evaluator.py` checks the exact
hashes of two publication helpers and adds an exact-name exception. This is a
four-line source compatibility change to the isolated evaluator build, separate
from its supported custom-backend extension. The exception preserves the
existing name and numeric value; it changes no grading formula or authorization
rule. Producer and consumer controls require 0 and 1 to survive, reject sensitive
nearby/credential-shaped names and reject non-score values. No production
package is changed. This small compatibility obligation must be re-reviewed on
upgrades; it also applies to a Code Mode integration on the same framework.

The existing gh `grade` function and authorization rules remain unchanged.
The derivative entry point supplies admitted actual native evidence and genuine
authored output, then tests receipt corruption/replay/omission and authored-secret
rejection using explicitly synthetic copies. Those copies never become grades.
Root-private evidence retains attempted arguments, native items, broker audit,
independently read workspace artifacts and oracle metrics as separate classes.
The backend collects it over the operator channel into host storage outside
agent mounts before ordinary container cleanup. Fixture replay verifies fixture
transitions; this experiment has no live GitHub state.

`check_results.py` independently reopens captures and requires all three complete
pairs, six unique initialization IDs, exact broker transitions and expected
metrics. It rejects missing/custom-grader error rewards. Upstream error artifacts
can contain `overall: 0`; they are retained as raw diagnostics and explicitly
classified unavailable by the export manifest. They are never admitted as
measurements. No legacy `executed_tool_calls`, ATIF trajectory or missing native
observations are manufactured.

`custom_only` is intentional. Individual gh dimensions and the conjunction keep
their existing meanings. A positive task's baseline activation stays zero when
the target skill is absent. This does not qualify production
`default_plus_custom`, its built-in checks, judges, aggregate, or history policy.
In particular, this controller does not synthesize the legacy trajectory those
consumers may expect.

Pinned gh, Podman, Pester and Actions-hardening skill text uses CLI/file workflows
and contains no dependency on a Code Mode JavaScript wrapper. Native discovery
and reading are exercised here. Tool selection, parallel orchestration, recovery
decisions and effectiveness can still change when the model receives the Direct
catalog. Canned success establishes no behavioral equivalence. See
[the separately authorized provider proposal](REAL_PROVIDER_TEST.md).

Keep the existing Code Mode patch, archives and qualification evidence as a
fallback. Revisit it only after a material Direct capability, evidence, provider
or behavioral requirement fails; framework staging defects shared by both modes
are not such a failure. Stop on missing evidence, identity drift, failed
protection, unknown billing, a hard limit, or any attempted production/history
change. No benchmark schedule or production activation is part of this branch.
