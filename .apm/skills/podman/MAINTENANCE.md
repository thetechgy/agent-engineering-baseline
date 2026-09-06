# Podman skill maintenance

This file is for maintainers of the skill, not normal skill activation.

## Goal

Keep the skill deliberately current-only. Remove obsolete compatibility advice
rather than accumulating version branches for historical Podman releases.

## Authority order

When updating a technical rule, use this evidence order:

1. Podman source and tests for the target stable version
2. Matching-version generated/man-page source under `docs/source/markdown/`
3. `RELEASE_NOTES.md` for breaking changes and newly introduced behavior
4. Current Fedora/Fedora CoreOS documentation for host integration
5. Other upstream project documentation (systemd, Traefik, Butane, etc.)
6. Community examples only as leads to verify upstream

Do not preserve a community rule that conflicts with Podman source/tests.

## Current verified baseline

The 1.0.0 skill was reviewed against Podman 6.1.1 / the `v6.1` source branch on
2026-09-05.

Important 6.x assumptions captured by the skill include:

- cgroup v2 only;
- Netavark rather than CNI;
- pasta rather than slirp4netns for the direct rootless network stack;
- Podman 6 bridge-network isolation defaults;
- current rootless bridge `rootlessport` source-IP behavior;
- current Quadlet resource types, search paths, implicit network dependencies,
  native hardening keys, and `podman quadlet` command suite;
- rootless `UserNS=auto` support;
- `podman compose` as an external-provider wrapper;
- Podman API socket's full-authority security model.

## Update checklist

When a new Podman stable minor/major becomes the target:

- [ ] Read `RELEASE_NOTES.md` from the last verified version through the new one.
- [ ] Review breaking changes affecting rootless, networking, systemd, Quadlet,
      storage, secrets, and Compose.
- [ ] Diff/review `pkg/systemd/quadlet/` and the `podman-*.unit(5)` docs for new,
      renamed, removed, or changed keys/defaults.
- [ ] Review `rootless.md`, network/publish option docs, and Netavark-related
      behavior for rootless forwarding and source-IP changes.
- [ ] Review `cmd/podman/compose.go` for provider-selection/environment changes.
- [ ] Review `podman-system-service(1)` and API code/docs for trust-boundary
      changes.
- [ ] Recheck Quadlet search paths, `podman quadlet install/list/print/rm`, and
      generated-service enablement behavior.
- [ ] Recheck secret drivers and secret mount/env behavior.
- [ ] Remove rules that became obsolete instead of retaining historical forks.
- [ ] Update the `SKILL.md` verified-baseline sentence.
- [ ] Increment `metadata.version` for meaningful skill behavior changes.
- [ ] Run the cases in `EVALS.md` in both GitHub Copilot CLI and Codex after APM
      compile/deployment.
- [ ] Add a new eval whenever a real agent mistake reveals a missing gotcha.

## Skill-design checks

Preserve the Agent Skills progressive-disclosure model:

- keep `SKILL.md` focused and below 500 lines / roughly 5,000 tokens;
- keep trigger metadata specific enough to avoid Docker-only false positives;
- put conditional depth in `references/` and tell the agent when to load it;
- do not add experimental `allowed-tools` merely for convenience;
- do not bundle executable scripts unless a deterministic validator provides
  enough value to justify the new supply-chain/execution surface;
- prefer one coherent Podman skill over multiple overlapping security/networking
  skills that can conflict.
