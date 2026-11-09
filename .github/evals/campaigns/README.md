# Reusable credential-free evaluation campaigns

Use one operator entry point with the pinned candidate evaluator, Harbor, Compose
and APM tools already installed. Keep retained output outside the checkout in a
persistent workspace. Disposable files follow `TMPDIR`. No credentials, inference,
model judges or paid dispatch are accepted by this entry point.

```sh
"$SKILL_CURRENT_PYTHON" -B .github/scripts/evaluation_campaign.py qualify \
  --definition .github/evals/campaigns/boolean-contract.json \
  --output "$EVIDENCE/boolean-contract"

"$SKILL_CURRENT_PYTHON" -B .github/scripts/evaluation_campaign.py qualify \
  --definition .github/evals/campaigns/gh-read.json \
  --output "$EVIDENCE/gh-read"
```

Supply both definitions in one invocation to produce a combined report. The
[qualification workflow](../../workflows/evaluation-campaign.yml) does this.
`--mode oracle` executes the native oracle controls. `--mode probe` executes the
real pinned Codex CLI against the loopback, non-forwarding endpoint. The default
runs both modes. Neither mode performs model inference. A CLI probe qualifies
only the exercised CLI/configuration/fixture boundary, without provider access.

The output retains the frozen definition, runtime/model identity, ordered attempt
ledger, APM deployment, task members and descriptors, native grading and cleanup
observations, submissions, validated public records and consolidated HTML. The
report is rendered twice from public inputs and saved analysis; unequal bytes
fail qualification. A stopped campaign retains pending positions and available
reports. Infrastructure failure, missing evidence, unsupported grading, invalid
submissions and measured task failures remain distinct. No attempt is replaced.

The Boolean task uses PR #123's original prompt and inputs, the additional integer
mutant and all five controls. Oracle controls cover both strong suites, value-only,
type-only and invalid discovery. CLI probes use strong and value-only suites.
The existing prospective grader retains reference correctness, the five individual
mutant results and their joint quality metric.

The gh task selects the already-qualified `gh-014` issue-read fixture. Its existing
broker and grader execute without real GitHub service calls. Oracle controls cover
correct work, wrong repository, unauthorized action, unsupported trace and missing
trace. CLI probes cover correct work and the unauthorized action. Correct JSON
with an unauthorized action retains task correctness and fails authorization.
The absent variant retains its separate activation/gate consequence. These gh
metrics are not converted into Pester quality or a cross-skill score.

## Boundaries and extensions

| Responsibility | Implementation |
| --- | --- |
| Order, attempt limit, budget observation, stop and durable ledger transitions | `evaluation_campaign_core.py`; reused by the historical cohort wrapper |
| Task selection and native execution orchestration | `evaluation_campaign.py` |
| Prompts, fixtures, expected outputs, controls and grading expectations | Definitions here and task adapters in `evaluation_tasks.py`; existing graders |
| CLI launch, discovery, native APM deployment, configuration and usage | Owning adapter in `evaluation_codex.py`; reused pinned pilot helpers |
| Runtime/model identity and supported settings | `evaluation_runtime.py` and `codex-qualified.json` |
| Native admission, public projection, analysis and rendering | Existing evidence/report modules; registered campaign extension in `evaluation_evidence.py` |

For **another skill on an existing runtime**, add its task definition and a small
task adapter: stage its existing BYOT/BYOG bundle, expose controls and expected
artifacts, validate protected fixture/grader bytes and check task-specific results.
Register new immutable custom metric/profile identities and the task adapter. Use
the same scheduler and report entry point. Do not edit installed skill bytes to
prepare a case.

For **another runtime on an existing task**, add an owning adapter module and
register its profile validator, source-input metadata and execution module in
`evaluation_runtime.py`. The adapter
owns deployment/discovery, image preparation, actual agent launch configuration,
authentication boundaries, native observations, usage and cleanup. Qualify its
Harbor import hooks and native collector/admission identities through this same
entry point. Claude Code (`claude-code`) and the actual Copilot agent (`copilot`)
are explicit extension targets and currently fail as unsupported. The task's
fixture `gh` executable is not the Copilot runtime. Synthetic identity checks do
not establish real CLI compatibility.

For **another model supported by an existing runtime**, add a separate explicit
runtime/model profile and qualify it through the owning validator and actual CLI
probe. Preserve model/provider/settings, version, limits and pricing assumptions
in the ledger and registered reporting identity. Unknown settings fail explicitly.
The Codex validator currently accepts only the unchanged qualified
[codex-pilot.json](../codex-pilot.json); adding a model is not an arbitrary string
override and does not enable inference.

Variant names are configuration, not scheduling conditions. The scheduler also
has a three-variant contract check. The current report bridge remains paired and
requires one present and one absent deployment. A practical absent/current/revision
comparison uses separately frozen definitions for absent/current and
absent/proposed-revision, with the same task and runtime and the proposed skill
source selected by its definition. A revised source needs its own reviewed source
identity and qualification before admission; this work creates no revision.
Direct current-versus-revision pairs, arbitrary multi-arm native reports and
live campaign authorization remain unsupported. The existing source-content
admission checks intentionally reject unregistered revision bytes.

## Maintenance and qualification limits

The shared scheduler, native aggregate builder, report reproduction and pinned
CLI image/usage helpers are extracted from the existing pilot. Historical CLI
and cohort commands remain wrappers over these implementations. There is one
scheduler policy and one consolidated renderer to maintain.

Maintain task definitions, control expectations, source/profile hashes, adapter
contracts and the hosted qualification together. Source changes get new profile
identities; old profiles, receipts and grades stay unchanged. The new retained
pilot/effectiveness source identities are v7, with unchanged historical grading
semantics. Campaign profiles have separate oracle and CLI-probe identities. Tests
compare all historical registry entries and production active-profile selections
with the merged base.

Remaining coupling includes the paired native collector/public schema, the
existing supported skill inventory/metric registry, Docker/Harbor transport and
Codex event conversion. The current runtime uses the existing external containment
policy and frozen model/provider settings. The gh adapter composes trusted broker
initialization with that containment; its boundary probe is an operator preflight
because the task grader rejects arbitrary interpreter commands in agent traces.
Boolean CLI probes also exercise the boundary from a CLI tool child. The gh image
uses the same already-pinned curl version as that qualified runtime. No dependency
version, production default, distributed skill or historical grade is changed.

These demonstrations qualify reuse for two task families. They do not establish
universal runtime compatibility, prospective skill advantage, provider
authentication, model effectiveness or actual provider billing.
