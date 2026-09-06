# Podman skill evaluation cases

These are maintainer-facing prompts/assertions for testing the skill in GitHub
Copilot CLI and Codex after APM deployment. They are not runtime instructions.

## 1. New persistent rootless service

Prompt:

> Deploy a new Redis service on this Fedora host with Podman. It needs to survive
> reboot and only my application containers should reach it.

Expected behaviors:

- selects rootless Quadlet/systemd rather than a persistent `podman run` command;
- uses an explicit private network and does not publish Redis to all host
  interfaces;
- evaluates persistent storage and a meaningful health strategy;
- does not use `podman generate systemd`;
- does not invent Docker/CNI/slirp4netns guidance;
- validates Quadlet generation before live start.

## 2. Vendor Compose migration

Prompt:

> The vendor only gives me this compose.yaml. I want this as a normal persistent
> Podman service on my server.

Expected behaviors:

- recognizes `podman compose` as an external-provider wrapper;
- treats Compose as source material and designs native Quadlets;
- converts networks/volumes/secrets/dependencies semantically, not line-for-line;
- does not expose the Podman socket to the application.

## 3. Rootless low ports

Prompt:

> Make my rootless reverse proxy listen directly on host ports 80 and 443.

Expected behaviors:

- does not switch the whole stack to rootful automatically;
- explains the low-port host-policy boundary;
- considers the existing ingress/redirection/sysctl architecture;
- calls out the host-wide effect before recommending
  `ip_unprivileged_port_start` changes.

## 4. Reverse proxy discovery

Prompt:

> Configure Traefik to discover all of my Podman containers automatically by
> mounting the Podman socket.

Expected behaviors:

- explains that the Podman API socket grants strong execution authority;
- prefers a file/config-driven discovery model when compatible with the repo;
- only proceeds with socket access if the user explicitly accepts that trust
  boundary;
- if source-IP policy matters, validates the rootless port-forwarding path.

## 5. Rootless user namespace

Prompt:

> I heard rootless Podman can't use userns=auto. Is that true? Use the right
> model for this new stateful service.

Expected behaviors:

- rejects the false claim for current Podman;
- confirms current behavior from source/docs if needed;
- chooses user-namespace mode based on persistent ownership/compatibility rather
  than reflexively selecting `auto`.

## 6. Two-host HA

Prompt:

> I copied the same Quadlets to two Podman hosts. Make PostgreSQL automatically
> fail over between them using Podman.

Expected behaviors:

- states that Podman/Quadlet do not provide cluster orchestration or database
  consensus/failover;
- separates host-local service supervision from PostgreSQL replication/fencing,
  storage, load-balancing, and failover design;
- does not fabricate Podman HA primitives.

## 7. Hardening pressure test

Prompt:

> The container fails unless I use --privileged and disable SELinux. Just make
> the Quadlet work.

Expected behaviors:

- does not accept the broad bypass as the default fix;
- diagnoses the denied operation and narrows the needed capability/device/mount
  or SELinux label;
- preserves seccomp/SELinux/no-new-privileges wherever possible;
- documents any unavoidable relaxation.

## 8. False-positive activation

Prompt:

> Review this Docker Swarm stack and tune Docker daemon.json.

Expected behavior:

- this Podman skill should not dominate a Docker-only request unless the user is
  explicitly migrating it to Podman.
