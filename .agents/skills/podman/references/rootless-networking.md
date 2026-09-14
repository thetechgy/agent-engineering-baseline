# Rootless Podman and networking

Read this for rootless service identities, UID/GID mapping, user namespaces,
ports, Podman networks, DNS, reverse-proxy reachability, or source-IP questions.

## Rootless identity

For a persistent service identity, verify that the account and subordinate ID
configuration are appropriate before deploying stateful containers. Inspect the
actual host rather than assuming `/etc/subuid`/`/etc/subgid` layout when an
identity provider manages subordinate IDs.

Useful checks include:

```bash
id SERVICE_USER
podman info
```

When the user manager must survive logout and start at boot, make linger an
explicit host policy rather than relying on an interactive login.

Rootless Podman reduces host privilege; it does not make every process inside a
container unprivileged within that container. Preserve or set a non-root image
user where the application supports it.

## User namespaces

Current rootless Podman supports user-namespace modes including `auto`,
`keep-id`, and rootless-only `nomap`. Do not use outdated advice that
`--userns=auto` is rootful-only.

Do not force a non-default `UserNS=` mode merely because it sounds more secure.
Choose it to solve a concrete identity/ownership/isolation problem:

- default mapping is often simplest for service containers;
- `keep-id` is useful when host-user identity must map predictably into the
  container;
- `nomap` excludes the host user's UID/GID from the container mapping, reducing
  direct access to files owned by that host identity at the cost of ownership
  friction for shared or bind-mounted storage;
- `auto` creates a distinct automatically allocated mapping but can complicate
  volume ownership and consumes subordinate-ID ranges. Like `nomap`, it does
  not map the caller's UID into the container.

`auto` requires sufficient unused `/etc/subuid` and `/etc/subgid` range for the
invoking identity. Current Podman documents that `keep-id` consumes all of that
user's subordinate IDs and `nomap` all except the user's own ID. For a given
rootless Podman identity, `auto` therefore cannot allocate while that user's
`nomap` containers exist or while that user's `keep-id` containers consume the
range without an appropriate size limit. This conflict is per Unix identity;
one user's containers do not block another user's allocation.

For every selected mode, test persistent-volume ownership and a restore path
before standardizing it.

## Current rootless network stack

For current Podman 6 deployments, reason in terms of:

- Netavark for container network management;
- Aardvark DNS for DNS-enabled Podman networks;
- pasta for direct/default rootless network-mode handling;
- `rootlessport` as the normal rootless bridge-network port forwarder.

Do not introduce CNI or `slirp4netns` into a new Podman 6 design.

## Explicit bridge networks

Use named bridge networks to express communication boundaries. Current Podman 6
bridge networks default to `isolate=strict`, which blocks traffic to and from
all other bridge networks. `isolate=true` isolates the network except for
traffic toward other non-isolated networks; `isolate=false` restores the
pre-Podman-6 open behavior. Keep `strict` unless cross-network traffic is a
deliberate requirement.

If a service needs both ingress and a private backend, attaching it to both
networks is clearer than disabling isolation globally.

Aardvark DNS registers container names and aliases on DNS-enabled Podman
networks. Because Quadlet's default container name is `systemd-<unit>`, use an
intentional `NetworkAlias=` for application-level names such as `db`, `redis`,
or `keycloak` instead of depending on implicit naming.

For a database or other backend used only by containers on a named network, do
not publish its port to the host merely to make it discoverable.

Bridge isolation does not eliminate separately published host ports. Treat
`PublishPort=` as an independent exposure path and restrict it deliberately.

## Host networking

Avoid `Network=host` as a convenience fix. It removes the network namespace and
changes the container's visibility into and binding authority over host
networking. Require a concrete technical need and document it.

Host-dependent discovery such as mDNS/SSDP can be a legitimate exception when
the application's actual protocol requirements cannot be met through a
deliberately scoped bridge design. Document and test the resulting exposure
rather than generalizing the exception to unrelated workloads.

## Port publishing and low ports

Publish only required ports and bind intentionally:

```ini
PublishPort=127.0.0.1:8080:8080
```

is materially different from an unspecified host address that listens on all
interfaces.

Rootless processes cannot normally bind host ports below 1024. For 80/443,
prefer solving the problem at the ingress/host-policy layer rather than making
the whole workload rootful. Valid approaches can include an existing privileged
front end, firewall/redirection policy, or a deliberate adjustment of
`net.ipv4.ip_unprivileged_port_start` after assessing the host-wide effect.

## Client source IPs

Do not assume the address observed inside a rootless bridged container is the
original client address.

Current Podman normally uses `rootlessport` for published ports on rootless
bridge networks; it is a userspace proxy and does not preserve the original
client source IP.

As of Podman 6.1, the pasta/Pesto rootless bridge forwarder is experimental. It
is selected with `rootless_port_forwarder="pasta"` in the `[network]` table of
`containers.conf` and can preserve client source IP where `rootlessport` cannot.
Before using it for security policy, rate limiting, audit attribution, or proxy
access controls:

1. verify the target Podman, container-libs `common`, and passt/pesto versions
   (on Fedora-family hosts, common configuration is shipped by the
   `containers-common` package, and passt must provide the `pesto` binary);
2. verify IPv4 and IPv6 behavior;
3. test the actual address observed by the reverse proxy/application;
4. document the dependency rather than assuming the default preserves it.

## Networking validation

Useful diagnostics include:

```bash
podman network ls
podman network inspect NETWORK
podman port CONTAINER
podman inspect CONTAINER
ss -lntup
```

Test reachability from every relevant trust zone, not only from localhost. Also
test that intentionally private services are *not* reachable from zones that
should be denied.

## Multi-host boundary

Podman networks are host-local. Identically named networks on two hosts do not
form an overlay or cluster network. Load balancing, service discovery, fencing,
database replication, and failover across hosts must be designed outside
Podman/Quadlet.

## Upstream anchors

Check the target Podman version in:

- `rootless.md`
- `docs/source/markdown/options/network.md`
- `docs/source/markdown/options/publish.md`
- `docs/source/markdown/podman-network*.md*`
- `pkg/specgen/generate/container_create.go`
