---
description: Repository-only review rules for the agent engineering baseline
applyTo: "**"
---

# Baseline repository review guidance

## Code Review Rules

### Artifact provenance and generated outputs

- Flag changes to installed upstream skills, generated instructions, MCP configs,
  or lock metadata without a corresponding source change and pinned APM
  regeneration. Preserve upstream bytes, attribution, dependency pins, and the
  manifest's explicit publication boundary.
- Keep these repository review rules outside published `.apm/` instructions and
  package contents; downstream baseline consumers must not inherit them.

### Bootstrap ownership, recovery, and supported runtimes

- Flag bootstrap paths that bypass reviewed archive/executable hashes, version
  checks, absolute executable dispatch, or native APM ownership of deployment.
  Preserve unrelated destination settings and recover the prior usable state
  after interrupted or failed installation.
- Verify changed bootstrap behavior through the production entry point or a
  representative pinned fixture for affected Bash and PowerShell 5.1/7 runtimes.
  Do not treat mocks or one platform's CI as proof for unexercised runtimes.

### Credentials, MCP, and privileged automation

- Flag credentials or sensitive evidence entering instructions, generated
  configs, logs, packages, or uploaded evaluation artifacts. Keep documentation
  queries public and nonsensitive, and retrieved content outside authorization.
- Flag expanded MCP servers/tool access, executable trust, privileged workflow
  triggers, token permissions, or paid evaluations without explicit scoped
  authorization. Preserve sandbox, approval, and secret-handling boundaries.
