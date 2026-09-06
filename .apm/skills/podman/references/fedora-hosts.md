# Fedora and Fedora CoreOS hosts

Read this only when the target is Fedora Linux, Fedora Server, or Fedora CoreOS
(FCOS), or when Butane/Ignition is part of provisioning.

## Fedora family defaults

Use the Podman version actually shipped/installed on the target and verify
version-sensitive behavior before generating Quadlets. Fedora-family hosts make
SELinux part of the normal security model; do not disable it as a generic
container workaround.

Keep host-level Podman policy (service users, subordinate IDs, sysctls,
containers.conf, Quadlet ownership, firewall/ingress rules) separate from
application-level Quadlet content where that improves reviewability.

## Fedora CoreOS

Treat FCOS as an image-based, declaratively provisioned host rather than a
traditional server to be manually configured over time.

Prefer provisioning host identities, persistent host policy, configuration
files, and administrator-managed Quadlets through the intended FCOS
provisioning/configuration path. Butane compiles human-friendly configuration to
Ignition; validate the Butane configuration before provisioning.

Do not hardcode a newer/experimental Butane shortcut merely because it exists in
source. If using Butane-native Quadlet syntax, verify that the target Butane/FCOS
release supports it. Writing validated Quadlet files to the documented Podman
search paths remains conceptually clear and version-checkable.

Ignition primarily establishes machine state during provisioning/first boot.
Do not treat it as a general continuous-reconciliation engine. If ongoing drift
management is required, choose an explicit mechanism that fits the immutable
host model.

## Rootless service identities on FCOS

If persistent services run under a dedicated rootless account:

- provision the account and subordinate IDs intentionally;
- establish linger/user-manager behavior intentionally;
- deploy administrator-owned per-UID Quadlets under
  `/etc/containers/systemd/users/<UID>/` when Git/config management owns policy;
- keep persistent data paths/volumes compatible with reprovisioning and backup;
- avoid ad-hoc edits under the service user's home as the authoritative config.

Administrator ownership provides source-file integrity and change control; it
does not constrain a compromised service identity's normal Podman or user
systemd authority. If that threat is in scope, use a stronger host-level
account/SELinux boundary rather than treating `/etc` ownership as enforcement.

## Docker coexistence

If the host standard is Podman, avoid accidentally activating a Docker daemon
through socket activation or tooling assumptions. Current FCOS documentation
has specifically warned about running Docker and Podman together because of
runtime/network/firewall interactions.

If Docker is intentionally absent from the architecture, make that a host policy
rather than relying on operators to remember not to type `docker`.

## Host updates

An image-based host update can also change Podman, Netavark, Aardvark,
containers-common, systemd, and SELinux policy. After a meaningful host/runtime
update, re-run the Quadlet generation/validation gate and smoke-test ingress,
health, persistent storage, and rootless networking before declaring the host
healthy.

For multi-host maintenance, draining/removing a host from load balancing is an
external orchestration/ingress concern. Quadlet supervises services on one host;
it does not coordinate rolling maintenance across hosts.

## Upstream anchors

Use current upstream sources:

- Podman: `https://github.com/podman-container-tools/podman`
- Fedora CoreOS docs: `https://github.com/coreos/fedora-coreos-docs`
- Butane: `https://github.com/coreos/ignition/tree/main/butane`

The former standalone `coreos/butane` repository is archived; current
development lives under `coreos/ignition/butane`.

Prefer the documentation/specification matching the actual FCOS stream and
Butane version being deployed.
