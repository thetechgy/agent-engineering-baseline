# Agent engineering baseline

This MIT-licensed repository is a shared, project-agnostic configuration for
[Microsoft Agent Package Manager (APM)](https://microsoft.github.io/apm/).
It deploys reviewed instructions, skills, and the official hosted GitHub MCP
server to Codex and GitHub Copilot tooling.

## How it is pinned

The repository uses APM's native dependency model, the same way `package.json`
and a lockfile work together:

- `apm.yml` declares intent: branch-ref dependencies (`#main`), local `.apm/`
  content, and the GitHub MCP server.
- `apm.lock.yaml` is the pinning authority. It records the exact resolved
  commit and a content hash for every dependency, so `apm install --frozen`
  reproduces the same files byte-for-byte on any machine.
- `.apm-version` pins the APM CLI release consumed by the bootstrap scripts
  and CI.
- `.apm-installer-checksums` pins SHA256 digests for the upstream
  `install.sh` and `install.ps1` scripts, so bootstrap and CI verify the
  installer bytes before executing them.
- Compiled outputs (`AGENTS.md`, `.agents/skills/`, `.github/instructions/`,
  `.codex/config.toml`, `.vscode/mcp.json`) are committed so drift stays
  reviewable; CI requires clean regeneration.

## Local content

`.apm/` holds the reviewed local sources:

- `instructions/personal.instructions.md` — shared engineering boundaries.
- `skills/a11y`, `skills/agent-safety`, `skills/ansible`, and
  `skills/powershell-module-engineering` — adapted from
  `github/awesome-copilot` instruction files into on-demand skills so their
  broad guidance stays out of always-on context. Their bodies are reviewed
  local copies; refresh them by comparing against upstream when desired.
- `skills/powershell-pester-6` — locally authored. Upstream awesome-copilot
  now ships a `powershell-pester-6.instructions.md`; the local skill remains
  the source of truth here by choice.

Installed `.agents/skills/` outputs are generated artifacts; never edit them
in place.

## Global bootstrap

Run the wrapper for the current platform from the repository root.

Linux:

```sh
./scripts/bootstrap-global.sh
```

Windows (Windows PowerShell 5.1 or PowerShell 7):

```powershell
./scripts/Bootstrap-Global.ps1
```

Bootstrap reads `.apm-version` and behaves as follows:

- missing CLI: install the pinned version;
- older CLI: upgrade to the pinned version;
- matching CLI: leave it unchanged;
- newer CLI: stop before deployment rather than downgrade or run unreviewed
  behavior.

Installation uses the official installer from the pinned release tag with an
explicit `VERSION`; the official Windows installer validates the matching
release checksum sidecar. The downloaded installer script itself is verified
against the SHA256 digest pinned in `.apm-installer-checksums` and is never
executed on a mismatch. After the CLI preflight, the wrapper delegates to
native commands:

```sh
apm install --global --frozen
apm compile --global --dry-run
apm compile --global
```

Preview without downloads or changes:

```sh
./scripts/bootstrap-global.sh --dry-run
```

```powershell
./scripts/Bootstrap-Global.ps1 -WhatIf
```

APM owns its mutable user-scope modules, caches, compiled instructions, and
the official GitHub MCP entry. Provide `GITHUB_TOKEN` only at runtime; no
credential value belongs in this repository or generated configuration.

## Repository install and validation

Use the pinned CLI version, then reproduce the committed project deployment:

```sh
apm install --frozen
apm compile --target codex,copilot --validate
apm compile --target codex,copilot
apm audit --ci
apm pack --dry-run
```

Run the platform behavior tests plus normal hygiene:

```sh
./tests/bootstrap-global.sh
pwsh -NoLogo -NoProfile -File ./scripts/Invoke-Validation.ps1
```

The validation workflow also exercises Pester on PowerShell 7 and Windows
PowerShell 5.1, PSScriptAnalyzer, ShellCheck, Markdown linting, frozen APM
installation/compile/audit/package checks, clean-regeneration drift, and the
project-agnostic content assertion.

## Scheduled reviewed updates

`.github/workflows/update-baseline.yml` runs weekly and on manual dispatch.
It refreshes `.apm-version` to the latest stable APM release, re-pins the
matching installer checksums in `.apm-installer-checksums`, re-resolves the
branch-ref dependencies with native `apm update --yes`, regenerates compiled
outputs, runs the full validation suite, and creates or updates one
`automation/apm-baseline-update` pull request.

The update PR is never auto-merged. Review the lockfile diff, regenerated
outputs, and CI results before merging. GitHub Actions dependencies remain
pinned to full commit SHAs and are updated separately by Dependabot.

To run the same refresh locally:

```sh
apm update
apm compile --target codex,copilot
```
