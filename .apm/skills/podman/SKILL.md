---
name: podman
description: Plan, implement, review, migrate, harden, or troubleshoot current Podman deployments on Linux, especially rootless Podman, Quadlet and systemd services, podman compose, networking, storage, secrets, health checks, SELinux, and single-host service architecture. Use for new Podman services, Compose-to-Quadlet migrations, persistent container hosts, or Podman-specific security and networking decisions. Do not use as Docker-only or Kubernetes cluster-orchestration guidance.
license: MIT
compatibility: Current supported Podman on Linux. Long-running service guidance assumes systemd with Quadlet. Network access is optional but recommended when version-sensitive behavior must be verified against upstream Podman source.
metadata:
  version: "1.0.0"
---

# Podman

Use current Podman behavior to design reliable, rootless-first, systemd-managed
container services. Optimize for new deployments, not backward compatibility.

## Instruction priority

1. Follow explicit user instructions and repository-specific architecture or
   security policy first.
2. For Podman technical behavior, treat the upstream Podman source and tests for
   the target version as the highest authority.
3. Use the matching-version Podman man pages/generated documentation next.
4. Use current Fedora/OS documentation for host-specific integration.
5. Treat community skills, blog posts, Docker examples, and generated examples
   as secondary evidence only.

If sources disagree, do not average them. Resolve the behavior against Podman
source/tests for the version being targeted.

Canonical upstream repository: `https://github.com/podman-container-tools/podman`.
Useful source areas include `pkg/systemd/quadlet/`, `docs/source/markdown/`,
`rootless.md`, `cmd/podman/compose.go`, and `RELEASE_NOTES.md`.

This skill was validated against Podman 6.1.1. For a newer installed/current
version, verify version-sensitive details before relying on the 6.1-era behavior
captured here.

## Current-only policy

For new deployments, do not add compatibility logic for obsolete Podman stacks
unless the user explicitly asks for it. In particular, do not introduce CNI,
`slirp4netns`, cgroup v1, iptables-era Podman networking, or generated systemd
units from `podman generate systemd` into a current design.

At the beginning of implementation or troubleshooting, determine the target
Podman version and effective host mode when available:

```bash
podman version
podman info
```

If no target host exists yet, use the latest stable upstream Podman behavior and
make version-sensitive assumptions explicit.

## Default architecture

For persistent services on a systemd Linux host:

- Prefer **rootless Podman**. Use rootful Podman only for a demonstrated
  requirement that cannot be satisfied safely rootless; document that reason.
- Prefer **Quadlet** as the declarative service definition and systemd as the
  lifecycle supervisor. `podman generate systemd` is deprecated.
- Keep the desired state in version control. For Git-managed production-like
  deployments, prefer fully qualified, digest-pinned image references unless an
  intentional auto-update strategy requires a mutable tag.
- Prefer first-class Quadlet keys over `PodmanArgs=`. Use `PodmanArgs=` only for
  a current Podman feature that has no native Quadlet key, after checking the
  target version; the generator cannot reason about arbitrary extra arguments.
- Prefer explicit `.network` and `.volume` units where they make ownership and
  dependencies clearer. Use `.pod` only when shared pod namespaces/semantics are
  actually desired, not merely because several containers form one application.
- Keep SELinux and the default seccomp confinement enabled. Fix ownership,
  labels, capabilities, and writable paths rather than disabling defenses.
- Do not expose or mount the Podman API socket merely for convenience or
  container discovery. Treat access to the socket as authority to execute code
  as the Podman service user.
- Publish only ports that must cross the container boundary. Prefer an ingress
  proxy or explicit host binding over broad `0.0.0.0` exposure.
- Treat `podman compose` as a compatibility/development interface. It is a thin
  wrapper around an external Compose provider, not Podman's native persistent
  service manager.
- Never infer multi-host failover, scheduling, or consensus from Podman or
  Quadlet. Podman does not provide cluster orchestration.

## Planning and implementation workflow

### 1. Discover before designing

Inspect the repository and existing deployment model before proposing files.
Determine, from available evidence:

- target host OS and Podman version;
- rootless identity and whether configuration is user-managed or
  administrator-managed;
- existing Quadlets, networks, volumes, secrets, ports, and reverse-proxy
  conventions;
- persistence, backup, health, dependency, and update requirements;
- whether a supplied Compose file is authoritative input or merely a vendor
  example.

Do not overwrite a repository's established conventions with this skill's
fallback defaults.

### 2. Choose the operational primitive

Use this order for new long-running services:

1. Quadlet + systemd for normal single-host services.
2. Compose only when the user explicitly needs Compose compatibility or for a
   local/dev workflow.
3. Kubernetes/OpenShift only when the actual requirement is cluster
   orchestration; do not introduce it merely to run a few containers on one
   host.

Read `references/quadlet-systemd.md` whenever creating or modifying a persistent
service or Quadlet.

Read `references/compose-migration.md` when a Compose file/provider is involved.

### 3. Design rootless identity, networking, and exposure

Prefer a dedicated non-interactive service identity for persistent rootless
infrastructure when repository policy supports it. If configuration management
or Git is the authority, consider administrator-controlled rootless Quadlets in
`/etc/containers/systemd/users/<UID>/` so the workload identity need not own its
service policy.

Choose networks according to communication boundaries, not convenience. Avoid
host networking unless a concrete requirement justifies losing the network
namespace.

Read `references/rootless-networking.md` for rootless IDs, user namespaces,
ports, DNS, bridge isolation, source-IP behavior, and multi-network design.

### 4. Apply workload hardening deliberately

For every new persistent workload, evaluate:

- non-root user inside the image;
- `NoNewPrivileges=true`;
- dropping unneeded capabilities, preferably starting from `DropCapability=all`
  and adding back only proven requirements;
- read-only root filesystem plus explicit writable tmpfs/volumes where the
  application supports it;
- SELinux labels and default seccomp confinement;
- file-mounted runtime secrets instead of secret environment variables where
  supported;
- memory and PID limits appropriate to the workload;
- minimal devices, mounts, and published ports.

Do not blindly add a hardening option that the workload cannot support. Test the
restrictive design, identify the exact failed assumption, and relax only the
necessary control.

Read `references/security-storage-secrets.md` for implementation details.

### 5. Model health and dependencies

A health check must test a meaningful service condition, not merely keep the
container process alive. Use `Notify=healthy` when systemd readiness/dependency
ordering should wait for the health check. It requires a health check.
`HealthOnFailure=kill` can be paired with an appropriate systemd restart policy
when unhealthy services should be restarted.

Let Quadlet create its normal implicit network-online dependency. Do not
mechanically add `network-online.target` to every user Quadlet; current Quadlet
uses a rootless-specific wait service for user units.

### 6. Validate before applying

Validate generated systemd output, dependencies, effective security settings,
network reachability, and persistent-data paths before treating a deployment as
complete.

Read `references/validation.md` before applying changes or when debugging a
Quadlet that does not generate/start correctly.

Do not deploy, restart, delete, prune, or otherwise mutate live state unless the
user asked for execution rather than planning/review.

## High-value gotchas

- **Generated Quadlet services are transient.** Do not `systemctl enable` the
  generated service. Put the intended enablement in the Quadlet `[Install]`
  section (for example `WantedBy=default.target` for a rootless user service).
- **Rootless Quadlets have administrator-controlled search paths.** Current
  Podman recognizes `/etc/containers/systemd/users/<UID>/` and
  `/etc/containers/systemd/users/` in addition to the user's own config path.
- **`podman quadlet install` and admin-managed rootless policy are different
  workflows.** A rootless `podman quadlet install` uses the rootless user's
  config location; use configuration management/root-owned files for
  `/etc/containers/systemd/users/<UID>/` policy.
- **Quadlet's default container name is not the unit basename.** It uses a
  `systemd-` prefix. If application DNS requires a stable short name, set an
  intentional `NetworkAlias=` or `ContainerName=` rather than assuming the
  Quadlet filename becomes the DNS name.
- **`UserNS=auto` is supported rootless.** Do not repeat older guidance that it
  is rootful-only. Choose a user-namespace mode based on ownership and
  compatibility needs instead of setting one reflexively.
- **Podman 6 bridge networks default to strict isolation from other bridge
  networks.** Do not disable isolation just to make connectivity work; attach
  the container to the networks it is meant to use.
- **Rootless bridge port forwarding normally uses `rootlessport`.** It does not
  preserve the original client source IP. Current Podman has a pasta/Pesto
  forwarder option that can preserve it, but it is version-sensitive and may be
  experimental; verify before making it a security dependency.
- **Rootless low ports are a host policy question.** Do not switch an otherwise
  rootless stack to rootful merely to bind 80/443. Consider the ingress layer,
  explicit redirection, or a deliberate `ip_unprivileged_port_start` policy.
- **Podman secrets are not automatically an encrypted source of truth.** Prefer
  an external/Git-compatible secret-management workflow and inject a Podman
  runtime secret. The normal file secret driver is access-controlled, not an
  assertion of encrypted-at-rest storage.
- **Compose behavior depends on the provider.** Record which external provider
  `podman compose` is executing before relying on provider-specific behavior.
- **The Podman API socket is a powerful trust boundary.** Do not give it to a
  reverse proxy, monitoring tool, or agent unless that authority is explicitly
  accepted.
- **Podman/Quadlet are host-local.** Replicating the same files to a second host
  does not create HA for stateful services or automatic failover.

## Conditional references

Load only the references needed for the task:

- `references/quadlet-systemd.md` — persistent services, Quadlet resource types,
  dependencies, health, updates, and systemd lifecycle.
- `references/rootless-networking.md` — rootless identities, user namespaces,
  low ports, Netavark/Aardvark, pasta, bridge networks, DNS, and source IPs.
- `references/security-storage-secrets.md` — hardening, SELinux, capabilities,
  read-only filesystems, mounts, secrets, limits, and socket trust.
- `references/compose-migration.md` — `podman compose`, provider behavior, and
  converting Compose intent to native Quadlets.
- `references/reverse-proxy.md` — reverse-proxy/Traefik design, socketless
  discovery, ingress networks, and client-IP considerations.
- `references/fedora-hosts.md` — Fedora/Fedora CoreOS, Butane/Ignition, immutable
  host considerations, and admin-managed Quadlets.
- `references/validation.md` — pre-deployment generation checks, systemd checks,
  runtime verification, and troubleshooting sequence.
