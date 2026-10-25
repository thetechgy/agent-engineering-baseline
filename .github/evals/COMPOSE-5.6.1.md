# Docker Compose 5.6.1 security and compatibility assessment

## Decision and security relevance

Adopt Compose 5.6.1 for the current evaluation runtime. The security fix,
verified release bytes and paired native qualification below support the update. The verified starting repository
revision is `9a6c1b71f8eb61c778f5e97737987797e145299c` (PR #84).

[CVE-2026-111943](https://www.cve.org/CVERecord?id=CVE-2026-111943) /
[GO-2026-6809](https://pkg.go.dev/vuln/GO-2026-6809) adds a `crypto/x509`
denylist for distrusted intermediate certificates when trust-store updates may
not already protect the caller. Affected versions are before Go 1.26.10 and
from Go 1.27.0-0 before 1.27.3. The official binaries contain Go 1.24.11
(Compose 5.0.2) and Go 1.26.10 (Compose 5.6.1), matching tagged build inputs.

This establishes an affected dependency version, not exploitation. The evaluation
path uses local Dockerfiles and a local Unix daemon socket. Ordinary image pulls
are delegated to the daemon; its and BuildKit's TLS implementations are separate.
Compose's own remote OCI/Git resource and TLS-enabled daemon paths can involve
certificate verification, but those paths are not demonstrated exploitable here.
The update does not claim to repair every downstream certificate consumer.

## Release and artifact identity

The latest official stable release observed on 2026-10-25 is
[v5.6.1](https://github.com/docker/compose/releases/tag/v5.6.1).

| Identity | Value |
| --- | --- |
| Baseline source commit | `c428a77111d56683b823a47590eb08de5c59a162` |
| Candidate source commit | `6cbc19a3fd59e305fb814dca4d854a4fb67d2941` |
| Annotated tag object | `02f05e3787e5b2e83220923907bb014e6a36b359` |
| Candidate Linux x86_64 SHA-256 | `47737f4236e6d3ccea7291995203f8f018058783b4c3a9469119811a0b5db8c0` |
| Baseline Linux x86_64 SHA-256 | `2d880f723d3da7c779c54fdaea91a842fca8af55d1397f1ed8d7cbab3dd7af67` |
| Candidate provenance JSON SHA-256 | `1f27df6d66b9138cc2736ff4a1efa73b11594e2f0d03521db963f0a39b201a2a` |
| Candidate Sigstore bundle SHA-256 | `c9f23ee4be15b110d2cdc2fdacdafb7ad2bf2e8f8c5c99a7f479f3dffd803025` |

Both binary downloads were independently hashed against their official release
checksums before any execution. The candidate also matches `checksums.txt`, release
asset metadata and the provenance subject. The provenance identifies the signed
tag, exact source commit and Go 1.26.10 build image. GitHub reports the tag's SSH
signature as verified; that observation is separate from binary verification.

The installed GitHub CLI 2.103.2 successfully verified the published Sigstore bundle,
including the binary subject, trusted certificate chain and transparency-log
timestamp, with the following identity restrictions:

```sh
gh attestation verify docker-compose-linux-x86_64 \
  --bundle docker-compose-linux-x86_64.sigstore.json \
  --repo docker/compose \
  --cert-identity https://github.com/docker/github-builder/.github/workflows/bake.yml@58cb9f5b71b1836d6f690c1e95effdeb9b98cb8a \
  --cert-oidc-issuer https://token.actions.githubusercontent.com \
  --source-ref refs/tags/v5.6.1 \
  --source-digest 6cbc19a3fd59e305fb814dca4d854a4fb67d2941 \
  --deny-self-hosted-runners --format json
```

The verified certificate records source commit `6cbc19a`, the tag ref,
GitHub-hosted execution, signer digest `58cb9f5`, and upstream
[build run 39562092012](https://github.com/docker/compose/actions/runs/39562092012).
Verified timestamps identify Rekor and Sigstore's timestamp authority at
2026-10-21 07:29:31Z / 07:29:30Z. Raw public bundles and command results are
retained outside the checkout. CI uses the independently reviewed binary digest;
no permanent Sigstore dependency or new runtime trust service is introduced.

## Intervening behavior and implementation

Reviewed release notes from 5.1.0 through 5.6.1 and relevant tagged code/tests:

- 5.2 replaces state reconciliation; 5.4 incorporates network/volume lifecycle.
- 5.5 changes image-content/digest identity and warns that the first upgraded
  `up` may recreate existing containers. Tagged image-identity tests cover
  repeated-up stability, platform manifests and attested image rebuilds.
- 5.5.1 fixes dependency-wait timeout propagation and lifecycle synchronization.
  5.6 changes container-spec/config hashing, externally stopped-container
  monitoring and image cleanup. Readiness, exit propagation and cleanup need
  native checks rather than version-only assertions.
- OCI authorizer transport and sensitive environment-value publishing received
  fixes. These publishing/remote-stack paths are not used by the staged tasks.
  Go and other bundled dependency updates provide additional security changes;
  this assessment is not a complete transitive vulnerability scan.

Harbor 0.13.2 runs `build`, stale-session `down --remove-orphans`, and
`up --detach --wait`, followed by Compose copy/exec and teardown. Fresh session
containers mean the upgrade recreation warning does not require migration of
existing benchmark containers. Repeated unchanged candidate `up` remains checked.

Both workflows use the small shared Linux x86_64 checksum-first installer. It
creates a private temporary Docker CLI configuration, verifies before chmod or
execution, verifies absolute and CLI-plugin version discovery, and removes its
owned directory after failures/interruption or through always-run workflow cleanup.
No binary cache or global installation is used. The removed setup Action accepted
5.6.1 but executed its download without a checksum guard; its README external-action
allowlist entry is removed. Permissions and credential boundaries are unchanged.

## Evaluation identity and qualification

Current admission requires exactly 5.6.1. Runtime metadata still records the actual
discovered version. Changed policy inputs produce a distinct history directory.
Historical 5.0.2 fixtures, measurement bytes, reviewed identities and frozen
validator profiles remain unchanged. The existing reader reconciles recorded
versions against recorded policy; analysis rejects direct comparison across a
known Compose-version difference. No historical migration or version-range
acceptance is added.

The development host has no Docker executable/daemon. No distribution packages,
daemon configuration or existing Podman resources were changed. The completed
paired step in [run 40217123854](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/40217123854)
used the existing GitHub-hosted runner, one Docker Engine **28.0.4 / API 1.48**,
SkillEvaluator **0.3.0**, Harbor **0.13.2**, identical staging and fixed build pins.
The same daemon identity was checked before and after the pair. The exact
qualification code is retained at commit `cb5c16b`; its one-time driver and old
binary installation are removed from the final tree.

| Observed boundary | 5.0.2 | 5.6.1 |
| --- | --- | --- |
| Harbor build/start and container readiness | Passed | Passed |
| Effective network, mount, environment and resource checks | Passed | Passed |
| Agent UID and private fixture read denial | Passed | Passed |
| Compose file-copy round trip | Passed | Passed |
| Exec exit 7 and checked failure exit 9 propagation | Passed | Passed |
| Repeated unchanged `up` | Same container | Same container |
| Container, image, network, volume and temporary override cleanup | Passed | Passed |

Both full task-context hashes are
`959e2b3c11f1bb5e2f2a4ca0970881594c0ac97178dfbf2e4f80cddfdb4fbdcc`.
Compared effective fields agree: `network_mode: none`, one task-owned log bind,
no Compose-inherited environment, two CPUs, 4 GiB memory, and the same keepalive
command. Actual container inspection confirms limits, mounts, privilege and
network settings. Project names and host temporary paths intentionally differ.
The unchanged benchmark metadata producer also ran against the discovered
candidate plugin and passed exact current-runtime admission.

The baseline went first with a cold build; the candidate reused the same build
cache. No timing or performance inference is made. This is one representative
credential-free task, not model-backed Harbor qualification or coverage of every
Compose feature, engine/image-store combination, signal or failure path. No Codex
or model was invoked; the unchanged Codex integration is covered separately by
scanner-free contract tests. Installer interruption cleanup is exercised with an
inert fixture. Native lifecycle cleanup is observed after successful operations
and a checked command failure.

After the paired step completed, the superseded run was cancelled for the known
follow-up that removes qualification-only wiring and triggers replacement CI.
Its paired step is successful; its cancelled overall result is inconclusive.
Raw logs, checksums, provenance, the one-time driver and paired results are retained
outside the checkout. Final CI retains only the candidate lifecycle check plus
the existing six-container raw-Docker security boundary. Complete final-revision
CI and artifact verification results are recorded in
[PR #85](https://github.com/thetechgy/agent-engineering-baseline/pull/85).

Local validation: 69 focused installer/freshness/policy/reporting contracts pass;
all 26 Markdown files and changed shell blocks pass lint. Native repository
validation passes 29 Pester tests (52 platform skips), PSScriptAnalyzer, Bash
fixtures and isolated APM regeneration/audits, then stops at six existing SC2329
informational findings in unchanged bootstrap tests. Exact baseline bytes
reproduce those findings. No assertion or lint rule is weakened.

An initial sandboxed broad suite was interrupted after filesystem ownership
mapping caused existing secure-output checks to reject unmapped ancestors. The
same failing test passes under native ownership with unchanged assertions.
No paid evaluation, skill-score improvement, native Windows Docker qualification
or universal Compose compatibility is claimed.

The first hosted run (40215504064) stopped before Docker qualification: 643
contracts reported 20 failures and one error in synthetic review controls. The
policy change reordered hash-derived statement identities; test helpers selected
a `without_skill` statement as a positive control. A controlled old/new-policy
reproduction confirms the selection change. The narrow correction selects the
semantic arm in test helpers, with a failing-before regression for both citation
formats. All 125 affected review-module tests pass after the correction, including
the original negative gates and diagnostic matrix. Production review code, guards
and historical evidence remain unchanged.
The local broad run used the initial implementation and reported 643 tests,
20 failures, two errors and one host-gh version skip. The review-control failures
match the correction above. Its additional error is the unchanged repository
snapshot guard rejecting input-directory changes during concurrent local edits.
That run is retained as invalid for clean-revision qualification; the guard is
unchanged. An isolated pass is not substituted for full stable-checkout CI.
