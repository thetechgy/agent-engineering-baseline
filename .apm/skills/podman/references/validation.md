# Validation and troubleshooting

Read this before applying a new/changed Quadlet or when a unit does not generate,
start, become healthy, survive reboot, or provide expected network/storage
behavior.

## Validation loop

Use a plan -> generate -> verify -> start -> observe -> test loop. Do not jump
from editing a Quadlet to assuming a successful `systemctl start` proves the
architecture is correct.

### 1. Confirm target runtime

```bash
podman version
podman info
```

Record rootless/rootful mode, cgroup version, network backend, storage driver,
and the target user's identity when those affect the design.

If a requested key or behavior is uncertain, verify it against the Podman source
and tests matching this version before changing the design.

### 2. Validate Quadlet generation before live deployment

For files already in the normal search path, use the current generator dry-run:

```bash
/usr/lib/systemd/system-generators/podman-system-generator --user --dryrun
```

Drop `--user` for system/root Quadlets.

For a repository/staging directory, isolate validation with
`QUADLET_UNIT_DIRS` so unrelated host units do not obscure the result:

```bash
QUADLET_UNIT_DIRS=/path/to/staged/quadlets \
  /usr/lib/systemd/system-generators/podman-system-generator --user --dryrun
```

Use systemd's generator verification as a second check:

```bash
systemd-analyze --user --generators=true verify NAME.service
```

Adapt the scope for system units. Fix generator errors before starting the
service.

### 3. Reload and inspect generated service

After deployment to the real search path:

```bash
systemctl --user daemon-reload
systemctl --user status NAME.service
systemctl --user cat NAME.service
```

For a non-login service account, use the host's supported method to address that
user's systemd manager rather than starting a second accidental user manager.

Do not run `systemctl enable NAME.service` for a generated Quadlet service.
Enablement belongs in the source Quadlet's `[Install]` section.

### 4. Start only when execution is authorized

If the user requested deployment:

```bash
systemctl --user start NAME.service
journalctl --user -u NAME.service -b --no-pager
```

Use the corresponding system scope if rootful.

If startup fails, inspect the generated unit and journal before invoking raw
`podman run` commands that may bypass the service definition and create a second
source of truth.

### 5. Verify runtime state

Check what Podman actually created:

```bash
podman ps -a
podman inspect CONTAINER
podman network inspect NETWORK
podman volume inspect VOLUME
podman port CONTAINER
```

Verify:

- expected image digest;
- rootless identity/user namespace;
- capabilities/no-new-privileges/seccomp/SELinux assumptions;
- read-only and writable paths;
- resource limits;
- health status;
- network attachments, aliases, and published addresses;
- persistent volume/bind locations.

### 6. Test the service contract

Test from the same locations that real clients/dependencies use:

- reverse proxy -> backend;
- app -> database/cache;
- management host -> intended admin endpoint;
- external/LAN client -> intended ingress;
- prohibited zone -> confirm the port is not reachable.

For health-gated units, confirm both successful readiness and failure behavior.
If `HealthOnFailure=kill` + restart policy is intended, test that an unhealthy
instance actually recovers as designed rather than entering a tight restart
loop.

### 7. Persistence and reboot

For stateful services, verify recreation/restart without deleting the container's
authoritative data. Validate backup and restore paths, not only that a volume
exists.

For rootless persistent services, test after logout/reboot (or the closest safe
host-maintenance simulation) to confirm the user manager/linger and `[Install]`
behavior actually starts the service.

### 8. Report precisely

When finishing a plan/review/implementation, state:

- what was changed or proposed;
- target Podman version/source assumptions;
- validation commands actually run and their outcome;
- runtime checks not run;
- security controls intentionally relaxed and why;
- remaining host-specific or multi-host dependencies.

Do not claim success for checks that were not executed.
