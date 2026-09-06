# Quadlet and systemd

Read this when designing, creating, reviewing, or troubleshooting a persistent
Podman service.

## Choose Quadlet resource types intentionally

Current Podman supports these Quadlet source types:

- `.container` — one long-running or one-shot container
- `.pod` — a Podman pod
- `.network` — a Podman network
- `.volume` — a named Podman volume
- `.image` — image pull/cache management
- `.build` — build from a Containerfile
- `.kube` — `podman kube play` under systemd
- `.artifact` — OCI artifact pull management

Prefer the smallest set that expresses the workload. Do not create a pod merely
because several containers belong to the same application; a pod intentionally
shares namespaces and changes network/resource semantics.

## Rootless ownership models

Two useful models are distinct:

### User-managed

The service identity owns Quadlets under:

```text
~/.config/containers/systemd/
```

This is appropriate when the user itself is the deployment authority.

### Administrator-managed rootless

An administrator/configuration-management system owns Quadlets under:

```text
/etc/containers/systemd/users/<UID>/
```

or, deliberately, the all-users path:

```text
/etc/containers/systemd/users/
```

Use the per-UID path for infrastructure policy unless the same Quadlet is truly
intended for every user session. The container still runs rootless as that user;
the service definition need not be writable by the workload identity.

Do not attempt to make a system Quadlet rootless by putting `User=`, `Group=`,
or `DynamicUser=` in `[Service]`. Podman requires the Quadlet to be discovered
by the target user's rootless generator/search path.

## Native keys before raw Podman arguments

Use first-class Quadlet keys whenever they exist. Current examples include:

```ini
[Container]
Image=REGISTRY/ORG/IMAGE@sha256:DIGEST
Network=app.network
NetworkAlias=app
PublishPort=127.0.0.1:8080:8080
NoNewPrivileges=true
DropCapability=all
ReadOnly=true
Tmpfs=/tmp
Secret=app-secret,type=mount
Memory=512m
PidsLimit=256
HealthCmd=/app/healthcheck
HealthOnFailure=kill
Notify=healthy
```

This is an illustrative vocabulary, not a template to paste unchanged. Every
setting must match the workload. In particular, do not invent a healthcheck
binary or force a read-only filesystem on software that has not been evaluated
for it.

Use `PodmanArgs=` only after verifying that the target Podman version lacks a
native key. Upstream explicitly warns that the generator cannot account for
unexpected interactions from arbitrary appended Podman arguments.

## Names and dependencies

A `foo.container` generates `foo.service`, but the Podman container defaults to
`systemd-foo`. Do not rely on `foo` as the network DNS name unless you set a
network alias or explicit container name.

Prefer references between Quadlet resources rather than manually reproducing
creation order. For example:

```ini
[Container]
Image=REGISTRY/ORG/APP@sha256:DIGEST
Network=app.network
Volume=app-data.volume:/var/lib/app:Z
```

Quadlet understands these resource references and creates systemd dependencies.

For service-to-service ordering, systemd dependencies can refer directly to
Quadlet units; current Quadlet translates them to generated service units:

```ini
[Unit]
Requires=db.container
After=db.container
```

Ordering is not readiness by itself. If `app` must wait for a ready database,
ensure the database unit's startup semantics actually represent readiness; a
meaningful healthcheck with `Notify=healthy` is one way to make systemd wait for
container health.

## Network-online behavior

Current Quadlet adds its own implicit network dependency:

- root/system units wait on `network-online.target`;
- rootless/user units wait on `podman-user-wait-network-online.service`.

Do not duplicate `Wants=network-online.target` / `After=network-online.target`
in every rootless Quadlet. Add custom network ordering only for a separate,
real dependency not already represented by Quadlet.

## Service startup and install behavior

Quadlet-generated services are transient. They are not enabled with
`systemctl enable`. Express boot/user-manager activation in the source Quadlet:

```ini
[Install]
WantedBy=default.target
```

For persistent rootless services that must run without an interactive login,
ensure the user systemd manager is active across boots/logouts, normally through
an intentional linger policy.

Image pulls/builds and health-gated startup can exceed systemd's normal startup
timeout. Set `TimeoutStartSec=` only when needed and size it for the actual pull,
startup, and health-ramp path rather than copying a universal value.

Choose `Restart=` based on service semantics. A service expected to run
continuously commonly needs restart-on-failure or stronger behavior; a one-shot
job may not.

## Health and readiness

Use a health check that validates something the service must actually provide.
Examples are an internal readiness command, database readiness probe, or local
HTTP readiness endpoint.

`Notify=healthy` maps Quadlet readiness to Podman's health state and requires a
healthcheck. Use it when systemd should consider startup incomplete until the
container is healthy.

`HealthOnFailure=kill` turns an unhealthy health state into container
termination. Combine it with a suitable systemd restart policy only when that is
the desired recovery behavior.

Use startup-health options for services whose initialization legitimately takes
longer than their steady-state health interval.

## Image/update strategy

For Git-controlled infrastructure, default to a fully-qualified digest:

```ini
Image=ghcr.io/example/app@sha256:...
```

This makes the deployed artifact reviewable and rollbackable through desired
state. A human-readable version can be recorded in repository metadata/comments
rather than replacing the immutable digest.

`AutoUpdate=registry` and `AutoUpdate=local` are valid Podman mechanisms, and
Podman can roll back an image when restarting the updated systemd unit fails.
Use them only when the repository intentionally selects pull-based auto-update.
Do not combine a digest-pinned image with an expectation that a mutable registry
tag will auto-update.

## `podman quadlet` management commands

Current Podman includes `podman quadlet install`, `list`, `print`, and `rm`.
They are useful for user-managed Quadlet bundles and inspection.

Do not assume rootless `podman quadlet install` implements an
administrator-owned `/etc/containers/systemd/users/<UID>/` policy. For that
model, deploy the files through the host's configuration-management/provisioning
mechanism and then reload the user's systemd manager.

## Upstream anchors

Verify version-sensitive behavior against the target version in the canonical
Podman repository, especially:

- `pkg/systemd/quadlet/`
- `docs/source/markdown/podman-systemd.unit.5.md`
- `docs/source/markdown/podman-container.unit.5.md.in`
- `docs/source/markdown/podman-quadlet*.md*`
- `docs/source/markdown/options/podman-args.md`
