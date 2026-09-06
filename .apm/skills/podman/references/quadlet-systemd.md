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
- `.artifact` — OCI artifact pull management (**experimental at Podman 6.1**;
  verify its status in the target version before depending on it)

Prefer the smallest set that expresses the workload. Do not create a pod merely
because several containers belong to the same application; a pod intentionally
shares namespaces and changes network/resource semantics.

## Rootless search paths and ownership models

Current Podman recognizes these rootless search paths:

- `$XDG_RUNTIME_DIR/containers/systemd/` — temporary/runtime-managed;
- `$XDG_CONFIG_HOME/containers/systemd/` or
  `~/.config/containers/systemd/` — user-managed;
- `/etc/containers/systemd/users/` and
  `/etc/containers/systemd/users/$UID/` — administrator-managed;
- `/usr/share/containers/systemd/users/` and
  `/usr/share/containers/systemd/users/$UID/` — distribution-provided.

These paths are searched recursively. Avoid duplicate Quadlet filenames
anywhere in the effective rootless search tree unless intentional shadowing is
explicitly understood and tested: duplicate suppression is by filename across
all searched directories, including recursively searched subdirectories.

If duplicate names matter, verify precedence against the target Podman source.
In Podman 6.1.1, the generator processes the user-controlled runtime/config
paths first, then the generic administrator/distribution `users/` directories
before their per-UID subdirectories, and keeps the first file seen. The man
page lists the rootless paths in a different order but does not define rootless
precedence.

Two useful ownership models remain distinct:

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

Administrator-owned rootless Quadlets provide source ownership, change control,
and configuration-management integrity; they do not constrain a compromised
host service identity's normal authority. Podman searches user-controlled
runtime/config paths first, so a same-named unit there shadows the
administrator's copy, and that identity can also create differently named
Quadlets, ordinary user units, or invoke Podman directly unless host security
policy prevents it. Monitoring the user-controlled paths can detect shadowing;
preventing arbitrary workload changes by that identity requires a stronger
host-level boundary, such as appropriately designed SELinux/account confinement
or a different privilege architecture.

A compromised container workload that cannot write host configuration paths is
a different threat from compromise of the host service identity. Administrator
ownership remains useful against accidental drift and container-only compromise.

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

The default generated names and service types are:

| Source | Default generated unit | Default service type |
| --- | --- | --- |
| `NAME.container`, `NAME.kube` | `NAME.service` | `notify` |
| `NAME.pod` | `NAME-pod.service` | `forking` |
| `NAME.network` | `NAME-network.service` | `oneshot` |
| `NAME.volume` | `NAME-volume.service` | `oneshot` |
| `NAME.image` | `NAME-image.service` | `oneshot` |
| `NAME.build` | `NAME-build.service` | `oneshot` |
| `NAME.artifact` | `NAME-artifact.service` | `oneshot` |

These are defaults, not invariants. `ServiceName=` overrides the generated
service name, and `.container`/`.kube` units may explicitly use `Type=oneshot`
for appropriate jobs.

A `foo.container` generates `foo.service`, but the Podman container defaults to
`systemd-foo`. Pods, networks, and volumes likewise default to resource names
with the `systemd-` prefix unless `PodName=`, `NetworkName=`, or `VolumeName=`
overrides them. Do not rely on a source basename as the network DNS name unless
you set a network alias or explicit resource name.

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

`After=` and `Requires=` express startup ordering and requirement binding; they
do not automatically restart a dependent service whenever its dependency
restarts. Add runtime coupling such as `PartOf=` or `BindsTo=` only when the
desired lifecycle semantics require it.

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

`AutoUpdate=` only marks a workload as eligible. For unattended scheduled
updates, enable `podman-auto-update.timer` in the scope that owns the unit.
Updates can also be invoked manually with `podman auto-update` or
`systemctl start podman-auto-update.service`, or by another systemd unit. For
unattended rootless services, ensure the owning user's systemd manager remains
active across logout/boot, normally through linger.

The shipped `podman-auto-update.service` runs `podman image prune -f` after each
successful invocation, even when nothing was updated. Account for that behavior
if locally retained dangling images matter.

Rollback can see only what systemd readiness reports. An ordinary `.container`
defaults to `Type=notify` with `--sdnotify=conmon`, which signals container
startup rather than application readiness. For typical third-party images,
prefer `Notify=healthy` plus a meaningful healthcheck. Use `Notify=true` only
when the application itself sends sd-notify `READY=1`.

Digest pinning needs a paired update workflow: discover a new digest, update it
in Git, review the change, and deploy it. A pinned image without a bump process
becomes unpatched rather than merely stable.

## `podman quadlet` management commands

Current Podman includes `podman quadlet install`, `list`, `print`, and `rm`.
They are useful for user-managed Quadlet bundles and inspection.

`podman quadlet install` accepts individual Quadlet files, URLs, directories,
and `.quadlets` multi-Quadlet files. Members of a `.quadlets` file are separated
by `---` and each must have a `# FileName=<name>` comment. Application grouping
is explicit: a directory install requires `--application=NAME`, and everything
installed from that directory belongs to one application; members of a
`.quadlets` file belong to one application only when `--application` is
supplied. Removing one member removes the entire application, and application
removal requires `--recursive`. Check `podman quadlet list` before removal.

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
