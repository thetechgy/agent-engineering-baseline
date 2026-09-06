# Security, storage, and secrets

Read this whenever creating or reviewing a persistent workload, or when a
permission, mount, privilege, device, secret, or resource-limit decision is
involved.

## Security model

Treat the workload image as potentially compromiseable. Rootless Podman limits
the host privilege available after an escape, but the container still shares the
host kernel and the rootless service account may own valuable persistent data.
Use multiple independent controls rather than treating rootless mode as the only
boundary.

## Privilege defaults

### Application user

Prefer the image's intended non-root user. Do not override it to root to make a
permission problem disappear. If the vendor image requires root, understand what
it does as root and whether a safer configuration/image exists.

### No new privileges

For normal application services, use:

```ini
NoNewPrivileges=true
```

unless the application demonstrably requires privilege escalation. Current
Quadlet defaults this option to false, so an explicit policy matters.

### Capabilities

For new services, try a deny-by-default capability set:

```ini
DropCapability=all
```

Then add back only the specific capabilities the workload proves it needs.
Document every add-back. Do not use `--privileged` as a debugging shortcut;
privileged mode disables multiple isolation layers at once.

### Seccomp and SELinux

Keep the default seccomp profile in force. If a syscall is blocked, identify the
actual requirement before considering a custom profile. Do not use an
unconfined seccomp profile as the first fix.

On SELinux hosts, keep labels/enforcement enabled. Permission failures on bind
mounts usually require correct ownership and labeling, not
`SecurityLabelDisable=true` or permissive mode.

## Read-only root filesystem

Where the application supports it, prefer:

```ini
ReadOnly=true
```

with explicit persistent volumes and tmpfs mounts for the paths that must be
writable.

Be precise about `ReadOnlyTmpfs=`. Podman's read-only mode normally permits
writable tmpfs for standard transient paths. If the security requirement is
"every writable path must be explicitly declared", evaluate disabling implicit
read-only tmpfs behavior and add only the required `Tmpfs=` paths. Test the
application; many services legitimately need `/run`, `/tmp`, or similar paths.

## Storage choices

Use a named volume when Podman should manage durable application data and the
host path is not itself part of the desired configuration interface.

Use a bind mount when the host/config-management system intentionally manages a
specific file or directory, such as a version-controlled generated
configuration. Mount configuration read-only whenever possible.

On SELinux hosts:

- `:Z` is appropriate for a bind mount private to one container;
- `:z` is appropriate when the same content is intentionally shared by multiple
  containers;
- ownership-shifting options can mutate host ownership, so understand their
  effect before using them on valuable data.

Never solve a mount problem by recursively changing broad host directories or
disabling SELinux without first determining the container's effective UID/GID,
user-namespace mapping, and required label.

Backups are part of persistence design. Before declaring a service complete,
identify which volumes/bind-mounted paths contain authoritative state and how
they are backed up and restored.

## Secrets

Do not store plaintext secrets in Quadlet files, Compose files, container image
layers, Git, or shell history.

Prefer an external secret source appropriate to the repository/host (for
example, a configuration-management vault or dedicated secret manager), then
materialize a Podman runtime secret during deployment.

Prefer file exposure:

```ini
Secret=app-secret,type=mount
```

when the application can read a secret file. Use `type=env` only when the
application requires an environment variable and the compatibility tradeoff is
accepted.

Do not describe Podman's default secret storage as encrypted at rest. The
standard file driver stores access-protected data; Podman also supports other
secret drivers such as `pass`. The deployment's real secret source of truth and
rotation workflow should be explicit.

A secret change normally requires an intentional service restart/reload path;
do not assume every application re-reads mounted secret content automatically.

## Resource containment

Set limits based on observed/expected workload needs, not arbitrary tiny values.
For persistent services evaluate at least:

```ini
Memory=...
PidsLimit=...
```

and systemd controls where they better express host-level policy. PID limits in
particular reduce the blast radius of process-exhaustion bugs/attacks.

Do not set limits so tightly that normal startup, updates, database maintenance,
or backup jobs become unreliable. Validate under representative load.

## Image trust and reproducibility

For long-lived Git-managed services:

- use a fully qualified registry/repository name;
- prefer an immutable digest for the deployed artifact;
- review how image updates are discovered and promoted;
- avoid ambiguous short names;
- do not put credentials in image references or build arguments.

Image vulnerability scanning/signature policy can be valuable, but do not
invent a signing/scanning system unless the repository actually uses one.
Integrate with the project's existing supply-chain controls rather than creating
parallel policy.

## Podman API socket

Treat Podman API access as authority equivalent to the rootless service user.
Upstream Podman states that the API exposes full Podman functionality and can
execute arbitrary code as the user running the API, without an internal
fine-grained authorization/audit boundary.

Therefore:

- do not mount `podman.sock` into general application containers;
- do not expose it over TCP for convenience;
- do not grant it to a reverse proxy or monitoring agent merely for discovery;
- if an integration truly requires it, minimize the owning user's host
  privileges and explicitly document the accepted trust boundary.

## Upstream anchors

Verify details against the target version in:

- `pkg/systemd/quadlet/`
- `pkg/specgen/generate/security_linux.go`
- `docs/source/markdown/podman-container.unit.5.md.in`
- `docs/source/markdown/options/secret.md`
- `docs/source/markdown/podman-system-service.1.md`
