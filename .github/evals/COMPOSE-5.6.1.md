# Docker Compose 5.6.1 security and compatibility assessment

## Decision and security relevance

Update the current evaluation runtime from Compose 5.0.2 to 5.6.1, subject to
the container qualification recorded below. The verified starting repository
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

The installed GitHub CLI successfully verified the published Sigstore bundle,
including the binary subject, trusted certificate chain and transparency-log
timestamp, with the following identity restrictions:

```sh
gh attestation verify docker-compose-linux-x86_64 \
  --bundle docker-compose-linux-x86_64.sigstore.json \
  --repo docker/compose \
  --cert-identity https://github.com/docker/github-builder/.github/workflows/bake.yml@58cb9f5b71b1836d6f690c1e95effdeb9b98cb8a \
  --cert-oidc-issuer https://token.actions.githubusercontent.com \
  --source-ref refs/tags/v5.6.1 --format json
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
daemon configuration or existing Podman resources were changed. Actual native
qualification runs on the existing GitHub-hosted Validate runner without model
credentials or inference. A temporary paired check compares 5.0.2 and 5.6.1 on
one daemon with identical staged inputs and toolchain; it will be removed after
retaining its evidence. Final CI retains one representative Harbor lifecycle
check alongside the existing six-container raw-Docker boundary.

Local validation: 68 focused installer/freshness/policy/reporting contracts pass;
all 26 Markdown files and changed shell blocks pass lint. Native repository
validation passes 29 Pester tests (52 platform skips), PSScriptAnalyzer, Bash
fixtures and isolated APM regeneration/audits, then stops at six existing SC2329
informational findings in unchanged bootstrap tests. Exact baseline bytes
reproduce those findings. No assertion or lint rule is weakened.

An initial sandboxed broad suite was interrupted after filesystem ownership
mapping caused existing secure-output checks to reject unmapped ancestors. The
same failing test passes under native ownership with unchanged assertions. The
complete native offline suite and hosted qualification are pending; final results
will be recorded after those checks complete. No paid evaluation, skill-score improvement, native
Windows Docker qualification or universal Compose compatibility is claimed.
