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
The installed backend bytes must match repository source before qualification.
Changing an arm, checksum, manifest, payload or private fixture rejects startup.
The manifest is an operator approval artifact, not a signature against a malicious
operator with access to that same private directory.

The initializer verifies fixture bytes, the root-owned socket, live peer UID/PID,
exact broker command and process start identity. A fixed invalid request requires
a bounded response before readiness succeeds; the broker rejects it before
modeled dispatch and audit append. Repeated startup accepts the same healthy
broker and preserves audit state. Stale/foreign sockets, missing identity records,
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
must match byte for byte; installation uses `--no-deps --no-index --link-mode copy`.
Candidate dependencies retain the frozen upstream lock. Current and historical
review environments are not rebuilt or selected by candidate setup.

Add `--native-gh` for all 24 cases in both arms. `--gh-arm with_skill` or
`--gh-arm without_skill` bounds one native job to 24 cases. It uses the real
hardened environment startup/exec/copy/stop lifecycle, real broker receipts and
native deterministic grader, with controlled command/output fixtures. These are
not model trials or evidence of skill effectiveness. The first case also invokes
Harbor's setup-only Codex lifecycle and checks the installed CLI version; inference
entry points remain forbidden. Readiness is checked before and after grading to
verify audit continuity. Protected data access is attempted as the agent and must
fail. Teardown is independently observed.

The existing 24 successful replay traces and 13 rejected fault traces remain
unchanged. Candidate controls additionally exercise manifest/payload/arm/context
changes, missing/linked approval, operator-configuration isolation, startup ordering,
failed startup, timeout, cancellation and stale/foreign/dead broker identities.
Mocked failure controls are separate from native container execution.

The existing `--native-pester` still requires 52 exact terminal outcomes.
Native jobs require the credential-free hash-verified plugin from
`setup-compose.sh`. No Docker service or alternative runtime is installed by the
qualification harness. Missing prerequisites and failed jobs are inconclusive for
adoption. Artifacts contain only bounded metadata, statuses, case identities and
sanitized diagnostics; source snapshots, manifests, private fixtures and raw logs
are excluded. Qualification records cannot enter benchmark history.

## Adoption and rollback

`--adoption` runs the available native gates and returns a failed readiness
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
