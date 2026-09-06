# Podman Compose and Compose-to-Quadlet migration

Read this when `compose.yaml`, `docker-compose.yml`, `podman-compose`, Docker
Compose, or `podman compose` is part of the task.

## Know what `podman compose` is

`podman compose` is a thin wrapper around an external Compose provider. Podman
sets up the environment so that provider can talk to Podman and then passes the
Compose arguments through.

Current default provider candidates include `docker-compose` and
`podman-compose`; provider selection/order can be configured. Do not attribute a
provider-specific behavior to Podman itself.

Before troubleshooting or relying on Compose semantics, identify and record the
actual provider and version in use. If a repository intentionally pins a
provider through `PODMAN_COMPOSE_PROVIDER` or `containers.conf`, preserve that
policy.

## When Compose is appropriate

Use Compose when:

- the user explicitly wants a Compose workflow;
- local development/test parity depends on Compose;
- a vendor distributes a Compose file that is useful as source material;
- a migration starts from an existing Compose deployment.

For a new persistent systemd-host deployment, prefer converting the *intent* to
native Quadlet rather than keeping Compose as the service supervisor merely
because the example arrived as YAML.

## Migration procedure

Do not mechanically transliterate YAML keys. First determine the operational
meaning of each service.

Map concepts deliberately:

| Compose intent | Typical current Podman/Quadlet representation |
| --- | --- |
| long-running service | `.container` |
| named network | `.network` + `Network=` |
| named durable volume | `.volume` + `Volume=` |
| host bind mount | `Volume=`/`Mount=` with SELinux/ownership review |
| published port | `PublishPort=` with explicit host exposure |
| runtime secret | Podman secret + `Secret=` |
| restart behavior | `[Service] Restart=` |
| service ordering | systemd `[Unit]` dependencies |
| readiness dependency | meaningful healthcheck + readiness-aware startup |
| resource limits | native Quadlet/systemd controls |
| image build | CI-built immutable image normally; `.build` when host build is intentional |

For each Compose service:

1. identify whether it needs to be a distinct container or belongs in a pod;
2. determine which networks are ingress, backend, or internal-only;
3. classify every volume as config, cache, disposable state, or authoritative
   persistent data;
4. move plaintext secrets out of YAML/environment where the application permits;
5. replace `depends_on` assumptions with explicit systemd ordering and real
   readiness semantics where needed;
6. decide the image/update strategy rather than carrying over `latest` by
   default;
7. preserve only labels/extensions that still have a real consumer.

## Provider and socket caveat

Because the external Compose provider communicates with Podman through its API
compatibility surface, a Compose workflow can require the rootless Podman socket
to be active for the provider. Do not extrapolate that into a policy of mounting
the socket into deployed application containers.

## Validation

After migration, compare the effective behaviors rather than only the file
shape:

- expected containers start and become ready;
- dependencies start in the required order;
- networks permit and deny the intended flows;
- published ports match the old external contract;
- data survives recreation;
- secrets are available but not committed/logged;
- restart/boot behavior works through systemd;
- teardown does not delete authoritative data unexpectedly.

Keep the original Compose file during the migration/review period if it is
useful evidence, but designate one source of truth for the deployed state.

## Upstream anchors

Verify provider behavior against:

- `cmd/podman/compose.go`
- `docs/source/markdown/podman-compose.1.md.in`

Verify migrated Quadlet keys against the matching version under
`docs/source/markdown/podman-*.unit.5.md*` and `pkg/systemd/quadlet/`.
