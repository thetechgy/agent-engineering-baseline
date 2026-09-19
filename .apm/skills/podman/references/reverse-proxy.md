# Reverse proxy and service discovery

Read this when Traefik or another reverse proxy must discover/reach Podman
services, or when Docker/Podman API socket access is proposed.

## Default: do not use the Podman API as the discovery plane

The Podman API is not a read-only inventory interface. Access permits full
Podman functionality as the API user and can be used to execute arbitrary code
with that user's authority.

Do not mount the Podman socket into a reverse proxy merely to emulate a Docker
label-discovery workflow when the proxy has a file/configuration provider or
another lower-authority mechanism.

For Traefik, prefer a Git/config-management-generated dynamic file provider when
that fits the repository architecture. Keep proxy routing configuration next to
(or generated from the same desired state as) the Quadlet definitions so there
is one reviewable deployment intent.

## Reachability patterns

Choose one intentional pattern rather than exposing every application port.

### Shared ingress network

When the reverse proxy and backends run under the same rootless Podman identity,
a named ingress network can let the proxy reach backends by a stable
`NetworkAlias=` without publishing backend ports to the host.

Keep private databases/cache services on backend networks that the proxy does
not join.

### Explicit host-published backend

If architecture requires a host boundary between proxy and backend, publish the
backend only on the required host address/port and point the proxy configuration
at that endpoint. Do not use an all-interfaces binding when loopback or a
specific interface is sufficient.

Do not assume containers owned by different rootless Podman users share the
same Podman networks or storage. Cross-user designs need an explicit host-level
communication boundary.

## Client source IPs

If the reverse proxy performs IP-based logging, allow/deny policy, or rate
limiting, test the address Traefik/proxy actually sees.

On rootless bridge networks, normal `rootlessport` publishing does not preserve
the original source IP. Current Podman offers a pasta/Pesto bridge-forwarding
option that can preserve it, but its support/stability is version-sensitive.
Do not enable an experimental forwarding path solely because it sounds better;
verify the current Podman/containers-common implementation and test IPv4/IPv6
before depending on it for security decisions.

## TLS and exposed ports

Prefer a single intended ingress surface (typically the reverse proxy) rather
than publishing each application independently. Backends should generally
receive no public host port when the proxy can reach them on a Podman network.

Rootless binding of host ports below 1024 requires a deliberate host policy.
Solve 80/443 at the ingress layer; do not make unrelated application containers
rootful for low-port convenience.

## Dynamic configuration safety

Treat generated proxy configuration as deployment code:

- keep it version controlled or deterministically generated;
- do not embed secrets that belong in a secret manager/runtime secret;
- validate configuration before reloading;
- ensure removed services also remove stale routes;
- keep health semantics consistent between the proxy and systemd/Podman.

## Upstream anchors

For Podman authority, verify against:

- `docs/source/markdown/podman-system-service.1.md`
- `docs/source/markdown/options/publish.md`
- `docs/source/markdown/options/network.md`
- `rootless.md`

For proxy-specific behavior, use the current upstream documentation for the
actual proxy/provider rather than Docker examples copied into Podman guidance.
