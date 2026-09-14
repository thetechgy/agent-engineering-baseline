# Podman skill evaluation runbook

The executable test-case inventory is `evals/evals.json`, using the current
Agent Skills evaluation format. Fixture inputs live in `evals/files/`.

Run every case in a clean context:

1. once with this skill deployed;
2. once without the skill (or against a snapshot of the prior version);
3. in both GitHub Copilot CLI and Codex when validating APM portability.

Store outputs, timing, grading, feedback, and aggregate benchmark files in a
sibling workspace such as `podman-skill-workspace/iteration-1/`, never inside
the distributable skill. Grade each assertion with concrete output evidence and
compare the with-skill and baseline results.

## Trigger matrix

| Prompt family | Expected activation |
| --- | --- |
| Current Podman, rootless, Quadlet, systemd-container deployment | Activate |
| Compose-to-Podman/Quadlet migration | Activate |
| Podman networking, Netavark, Aardvark, pasta/Pesto | Activate |
| Fedora/FCOS Podman provisioning | Activate |
| Podman hardening, SELinux, devices, storage, secrets | Activate |
| Docker-only daemon or Swarm work with no Podman migration | Do not dominate |
| Kubernetes cluster orchestration with no Podman-specific task | Do not activate |

Add or refine evals when a real agent mistake reveals an unclear instruction.
Prefer assertions that distinguish the skilled behavior from a baseline model;
remove assertions that pass equally without the skill.
