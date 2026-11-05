# Trusted gh initialization qualification

The candidate backend uses SkillEvaluator's installed environment-plugin API at
`f878f99a9cd4a85dd04043feb43e5bd6a777f64b` (0.7.2), under its owning Harbor
0.24.0 lock. Production remains on SkillEvaluator 0.3.0 and Harbor 0.13.2 until
all adoption gates pass. Codex remains explicitly pinned to 0.155.1. No model
inference, remote judge, real-provider smoke or benchmark dispatch is authorized
or performed by these qualification commands.

## Initialization boundary

`aeb-gh-fixture` subclasses the candidate's hardened Docker backend. It awaits
normal secure startup, then initializes the broker as root within 30 seconds.
Harbor cannot enter agent setup until this method returns. Failure, timeout or
cancellation raises, retains bounded infrastructure evidence, and supplies no
successful measurement. Agent execution remains UID 1000. The backend preserves
the parent's mounts, networking, resources, credentials handling and teardown.

The only additional operator configuration is the host path `AEB_GH_MANIFEST`.
The backend declares it as an operator-owned host-path variable; skill runtime
variables cannot set it. Constructor kwargs cannot select an executable,
command, initializer or manifest. The fixed command runs the installed operator
payload outside task and skill directories. The plugin also retains the
candidate's hardened Codex agent import path.

The operator creates a content-addressed manifest in a private directory outside
all staged roots. Its filename binds its bytes. Approval checks ordinary,
unlinked files, ownership, private permissions, the native Harbor task checksum,
complete staged members, environment-context hash, case/arm and initializer hash.
Approval binds case and content rather than a temporary host path, allowing the
native CLI to restage identical tasks into its private directory. The installed
backend bytes must match repository source before qualification.
Changing an arm, checksum, manifest, payload or private fixture rejects startup.
The manifest is an operator approval artifact, not a signature against a malicious
operator with access to that same private directory.

The initializer verifies fixture bytes, the root-owned socket, live peer UID/PID,
exact broker command and process start identity. A fixed invalid request requires
a bounded response before readiness succeeds; the broker rejects it before
modeled dispatch and audit append. Repeated startup accepts the same healthy
broker and preserves audit state. Harbor startup runs once per trial; repeat
backend calls use a fixed verify-only command, require the same broker identity,
and reject rebuilding an initialized or failed trial. Stale/foreign sockets, missing identity records,
dead brokers and changed private inputs reject; initialization never removes the
socket or resets an audit. Identity evidence stays in the host trial root, outside
agent log mounts. Private payloads stay under root-only `/opt/aeb-gh`.

`gh_candidate.py` produces the candidate recipe before upstream staging. It
removes the old authored healthcheck and loads the native normalizer from the
candidate's evaluator-owned subdirectory. Existing gh producer bytes, profiles
and fixtures remain unchanged. Upstream rejects authored setup, entrypoints,
healthchecks and unsafe Compose overrides as before.

## Reproduction and evidence labels

Use the pinned uv 0.13.7 and a new persistent `RUNNER_TEMP` outside the checkout.
Setup requires the usual `GITHUB_WORKSPACE`, `GITHUB_ENV` and `GITHUB_PATH` files.

```bash
bash .github/scripts/setup-skillevaluator.sh candidate
"$SKILL_CANDIDATE_PYTHON" .github/scripts/qualify_evaluator_candidate.py \
  --source "$SKILL_CANDIDATE_SOURCE" \
  --output "$HOME/worktrees/gh-initializer-controls"
```

Source the setup outputs through the CI runner or explicitly export their values
in an operator shell. The local wheel uses only stdlib build inputs. Two builds
must match byte for byte; installation uses a generated hash-bound requirements
file with `--require-hashes --only-binary :all: --no-deps --no-index --link-mode copy`.
Candidate dependencies retain the frozen upstream lock. Current and historical
review environments are not rebuilt or selected by candidate setup.

Add `--native-gh` for all 24 cases in both arms. `--gh-arm with_skill` or
`--gh-arm without_skill` selects 24 cases. CI adds `--gh-shard 1`, `2` or `3` for fixed disjoint eight-case
jobs. All three shards per arm are required; none is a complete arm qualification.
The partition is checked against the full staged cohort before selection. Unsharded
operator runs retain the full cohort and a separately bounded observation budget;
CI shards keep the existing step deadline. Per-task execution limits stay unchanged.
It uses the real
hardened environment startup/exec/copy/stop lifecycle, real broker receipts and
native deterministic grader, with controlled command/output fixtures. These are
not model trials or evidence of skill effectiveness. The first case also invokes
Harbor's setup-only Codex lifecycle and checks the installed CLI version; inference
entry points remain forbidden. Readiness is checked before and after grading to
verify audit continuity. Protected data access is attempted as the agent and must
fail. Every native case also rejects a fabricated receipt. Seven native cases
then inject dead brokers, foreign socket ownership, missing identity, altered
private inputs, timeout, cancellation or missing approval after the positive
fixture. Each must retain unscoreable infrastructure evidence and prevent setup;
these fault fixtures are separate from the preceding deterministic grading.
Teardown is independently observed and bounded; teardown failure retains diagnostics
and cannot produce a successful qualification verdict. Skill reads must succeed
and match the exact staged skill bytes.

The existing 24 successful replay traces and 13 rejected fault traces remain
unchanged. Candidate controls additionally exercise manifest/payload/arm/context
changes, missing/linked approval, operator-configuration isolation, startup ordering,
failed startup, timeout, cancellation and stale/foreign/dead broker identities.
Mocked failure controls are separate from native container execution. Native
failure diagnostics retain fixed stage/error codes and bounded initialization
records. Qualification timeout first requests graceful teardown, then ends an
unresponsive child within a separate cleanup bound.

The controlled standard-grading gate stages all ten Podman cases in both arms,
runs the real verifier with explicitly mocked judges, serializes Harbor-native
records, collects them, and renders HTML diagnostics. It retains a bounded
`podman-fixtures.json` containing task checksums and numeric fixture results.
Interruption controls distinguish an embedded original native trial from a missing
duplicate file, then require an incomplete job to retain nine original trial
records without publishing successful scores. No fixture is benchmark history.

The existing `--native-pester` still requires 52 exact terminal outcomes.
Native jobs require the credential-free hash-verified plugin from
`setup-compose.sh`. No Docker service or alternative runtime is installed by the
qualification harness. Missing prerequisites and failed jobs are inconclusive for
adoption. Artifacts contain only bounded metadata, statuses, case identities and
sanitized diagnostics; source snapshots, manifests, private fixtures and raw logs
are excluded. Qualification records cannot enter benchmark history.

## Adoption and rollback

`--adoption` runs the available native gates and requires the retained evaluator
interpreter in `SKILL_LEGACY_REVIEW_PYTHON` for the second Pester qualification;
the current review SDK overlay is rejected. Once offline controls pass, the native
gates run independently so a failed gh lifecycle does not suppress Pester evidence.
It returns a failed readiness
verdict while any required boundary is unqualified. The command never edits pins
or implicitly promotes a producer. In addition to gh and both Pester runtimes,
adoption requires Podman's 20 standard-grading staging/collection/recovery
fixtures, exact owning-runtime adapters, shared reporting/public-only replay,
historical replay, new profile/provenance/publisher identities and the pinned
upstream differential selection. These requirements must not be replaced by
successful staging, synthetic metrics or passing unit counts.

Promotion must introduce `gh-deterministic-gate-v6`, `pester-pilot-v4` and the frozen
`current-v5` validator/registry, then update producer setup, workflow selection,
preflight, collectors/recovery, static collection, public reporting and dependency
ownership together. Historical profiles and protected references retain their
original identities and owning tooling. Mismatched tooling must reject. Until that
coordinated change is qualified, new production records remain inadmissible.

Rollback changes only active producer pins, backend selection and new policy
selection. Retain new readers, original historical archives and runtime routes;
do not rewrite measurements or silently fall back within a run. The candidate-only
state needs no production rollback because production selection has not changed.
Real-provider readiness and model effectiveness remain unverified in either case.

## Current delivery evidence

All 40 local candidate controls pass with no network attempts. They stage all 48
gh tasks and exercise native CLI restaging with unchanged checksums in a new
private directory. Initial hosted controls pass,
but native run `41902822407` fails its first with-skill task build with fixed
code `debian_snapshot_unavailable`. The root broker never starts, and no task
measurement is produced. The authenticated sanitized artifact retains the
owning runtime, harness and initializer identities and infrastructure status.
Do not infer broker execution, setup-only CLI compatibility or adoption from it.

The upstream selection contains 1,142 tests including the five explicit Codex
pin checks. Pristine source passes 1,137 with five skips. Patched source passes
1,059 with five skips and 78 failed upstream expectations: the same 74 documented
classifier/attribution differences plus four expecting upstream's Codex 0.161.0
instead of the required 0.155.1. The local installed-CLI check is a separate native
gate and remains unqualified while image acquisition fails. No unexplained
upstream differences were observed; these are not 78 passing assertions.

The production runtime/reporting migration, new profiles and frozen validator
snapshot remain gated and are not delivered as qualified producer selection by
this candidate-only PR. A snapshot download failure is infrastructure evidence;
it cannot qualify an image or justify relaxed completeness, changed scoring,
a Codex upgrade, different fixture images or model inference.

The first successful image acquisition on run `41906112691` reached a responsive
root broker in both arms, then correctly rejected repeat startup because Harbor's
base `start()` deliberately tears down and recreates the container. The backend
now runs that lifecycle once, uses a fixed verify-only root command on repeats,
and rejects rebuilding initialized or failed trials. The failing native identity
records are retained as failing-before evidence; unit controls additionally prove
repeat verification cannot create a broker or reset audit bytes. Native passing-
after evidence is still required.

A separate host-only controlled check exercises all 48 staged grader/normalizer
seams, including successful approved skill reads, modeled broker receipts and
expected arm outcomes. All 48 fabricated receipt controls reject. This is a
local grader compatibility check; it does not establish container isolation or
replace the native lifecycle gate.

Hosted validation on revision `6f03d1e25af408520d78c0d73ed7093712672712` passes
all 844 Python contracts (31 skipped), Linux/Bash project validation and Windows
PowerShell/analyzer validation. The retained Pester gate fails strict completeness:
42 rewards are present, with ten image-build infrastructure failures. Earlier
revision `842f5f550f46d8cd0d8a62af9452dd59324121ee` completed all 52 exact Pester
outcomes and shared/public-only reporting. The prior success does not certify
the later failed gate. Both source identities and authenticated artifacts are
retained separately.

Run `41909625336` reached 23 with-skill and 19 without-skill completed native
fixtures, then hit the overall observation deadline during later secure startup.
Completed cases preserve broker identity and audit continuity, exercise the
native deterministic grader and reject fabricated receipts. The first case in
each arm verifies installed Codex 0.155.1 without inference. These authenticated
partial results are failing-after evidence for cohort completeness, and passing-
after evidence only for the completed lifecycle boundaries. CI now partitions
each arm into three fixed eight-case jobs within the existing phase deadline.
Promotion still requires every case in both arms on the final source revision.

An eight-case shard on `a1f1d99` completed its first native fixture and retained
a teardown infrastructure failure. The initial artifact did not preserve the
cleanup stage/error class, so its cause is unestablished. Cleanup now records
those bounded fields, allows the hardened backend up to 60 seconds, and still
requires independent container/network absence. The parent observation retains
80 seconds for cleanup; CI's total remains below the unchanged 46-minute step
deadline. Failure evidence is written before cleanup starts.

On `a1f1d99`, five native gh shards pass: all 24 with-skill and 16 without-skill
cases, including exact metric/skill-byte replay and all seven fault controls in
each arm. The sixth shard remains failed on teardown; these results are not a
complete cohort. That revision also passes all 846 Python contracts (33 skipped),
the full quality job, both required project checks and all 52 retained-runtime
Pester outcomes with shared/public-only reporting.

Candidate Pester qualification on the same revision fails during the with-skill
native lifecycle. Two native records report `EnvironmentStartTimeoutError`
while the hardened backend awaits Docker image build at the unchanged 600-second
startup deadline. The diagnostic archive retains seven failed reward carriers
without pilot quality metrics and twelve failure records; there is no complete
52-outcome qualification. The underlying image-build delay is unestablished.
This does not establish a scoring mismatch or justify changing task images,
execution limits or isolation. Production promotion remains gated.

The candidate workflow now prepares the unchanged Pester image's common pinned
packages in a separate bounded operator setup step through the owning hardened
Docker API. It verifies PowerShell 7.6.9 and Pester 6.2.0, preserves native task
checksums and independently checks teardown. No agent setup, grading or inference
runs during preparation. Its bounded checkpoint is uploaded before qualification.
`--prepare-pester` exposes this setup step; `--adoption` includes it. Preparation
failure blocks candidate Pester qualification while independent gates remain
observable. Images, source/package hashes and native 600-second startup limits
remain unchanged. Any following success is explicitly cache-prepared fixture
compatibility, not cold-start or real-provider readiness. Native qualification
still requires all 52 outcomes and cannot publish fixture data as benchmarks.

The same explicit image-preparation phase applies to each gh shard through
`aeb-gh-fixture`, with a separate sealed operator manifest and no agent setup.
Observed Debian snapshot HTTP 503/504 build failures may retry at most three
preparation attempts within one shared 1,100-second budget. Each uses a fresh
backend/trial, preserves its failure record and requires complete teardown
before retry. Manifest, initializer, version, cancellation and other failures
do not retry. Actual native trials remain single-attempt, retain all limits,
and require their full case sets. Package preparation cannot produce quality
measurements. Concurrent cold acquisition is bounded to two gh jobs.

The native CI steps declare `--cache-prepared` after their separately retained
preparation checkpoint. This only labels diagnostic context; it changes no
execution, scoring or admission behavior. The workflow's source identity and
step outcomes bind that context. Standalone native commands retain unprepared
context unless the operator explicitly declares prior preparation.

Image preparation and native qualification use separate freshly hash-verified,
credential-free Compose configuration directories. Docker Buildx may create
client state under `DOCKER_CONFIG/buildx`; a used preparation directory cannot
pass the native phase's unchanged plugin-only admission check. The preparation
directory remains available until final task-owned cleanup. This refresh changes
no container state, broker audit or native trial. See the [Buildx configuration
lookup order](https://docs.docker.com/build/building/variables/#buildx_config).

Retained-runtime Pester qualification uses the same explicit package-preparation
entry point with `--runtime retained`. This selects only SkillEvaluator 0.3.0 /
Harbor 0.13.2, under its existing SDK 2.44.0 and Pydantic 2.13.4 owning lock.
Candidate preparation selects only 0.7.2 / 0.24.0. The current review SDK overlay
is rejected. The retained path stages its original recipe without the candidate
verifier override; native collection and shared/public reporting remain unchanged.

Transient package retries wait 30 and then 60 seconds, record those delays, use
fresh fully torn-down environments, and remain within the shared 1,100-second
preparation budget. The package, task-image and native execution limits remain
unchanged. Both preparation paths use a fresh credential-free operator home and
retain their checkpoint before native qualification. This addresses acquisition
flakiness without making failed or missing native trials successful.

Preparation checkpoints and native diagnostic artifacts include the workflow run
attempt in their names, preserving failed infrastructure evidence across explicit
reruns without overwriting prior artifacts.
