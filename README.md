# Agent engineering baseline

This repository uses
[Microsoft Agent Package Manager (APM)](https://microsoft.github.io/apm/)
to deploy shared instructions, skills, and Model Context Protocol (MCP)
servers for Codex CLI and GitHub Copilot tooling. The configuration and
commands below were validated with APM 0.25.0.

## Prerequisites

Install APM using an official installer:

```sh
# macOS or Linux
curl -sSL https://aka.ms/apm-unix | sh
```

```powershell
# Windows PowerShell 5.1 or PowerShell 7
irm https://aka.ms/apm-windows | iex
```

Confirm the installed version before using the repository:

```sh
apm --version
```

## Install and deploy

From the repository root, install the dependencies and compile the combined
instruction file used by Codex:

```sh
apm install
apm compile --target codex,copilot --validate
apm compile --target codex,copilot
```

APM deploys the individual instructions to `.github/instructions/`, the shared
skills to `.agents/skills/`, Codex MCP configuration to `.codex/config.toml`,
and VS Code-compatible MCP configuration to `.vscode/mcp.json`. When GitHub
Copilot CLI is installed and visible on `PATH`, the same installation also
merges the MCP servers into the current user's `~/.copilot/mcp-config.json`.
Compilation generates the root `AGENTS.md` consumed by Codex and also
recognized by GitHub Copilot CLI.

Commit `apm.yml`, `apm.lock.yaml`, the deployed files, and generated
`AGENTS.md`. Do not commit `apm_modules/`; it is a reproducible package cache.

## Validate

Use the lockfile-only workflow and APM integrity audit in automation:

```sh
apm install --frozen
apm audit --ci
```

Running the installation and compilation commands again leaves the deployed
configuration unchanged. APM 0.25.0 still rewrites only the lockfile's
`generated_at` value on each installation, including `--frozen`, so a raw
repository diff contains that timestamp-only change.

APM 0.25.0 currently reports `config-consistency` errors for the four requested
virtual skill-directory packages because it looks for an `apm.yml` inside each
upstream `SKILL.md` directory. Installation, frozen installation, compilation,
and drift replay still succeed, and the audit reports no repository drift. Do
not add placeholder manifests to the managed skill directories; retain the
upstream package roots and review this limitation when updating APM.

## Update

Refresh dependencies intentionally, materialize the updated lockfile,
regenerate the combined instructions, and audit the result:

```sh
apm update
apm install
apm compile --target codex,copilot --validate
apm compile --target codex,copilot
apm audit --ci
```

Review upstream changes and the full repository diff before committing an
update.

## Authentication and current limitations

No credentials are stored in this repository. Microsoft Learn MCP uses its
public remote endpoint. The GitHub MCP server uses the registry's remote HTTP
transport. Codex reads its bearer token at runtime from `GITHUB_TOKEN`; project
MCP configuration becomes active after the repository is trusted in Codex.

For GitHub Copilot CLI, set one of APM's supported GitHub token variables before
installation: `GITHUB_COPILOT_PAT`, `GITHUB_TOKEN`, `GITHUB_APM_PAT`, or
`GITHUB_PERSONAL_ACCESS_TOKEN`. APM then injects the authorization header.
GitHub Copilot CLI configuration is user-scoped and generated for each user by
`apm install`; it is not committed to this repository.

The requested Awesome Copilot plugin source cannot currently be installed by
APM 0.25.0. The supplied `.github` directory is not a valid virtual package
root, while the parent plugin package and marketplace entry fail validation
because their manifest refers to agent and skill paths outside the isolated
plugin directory. The plugin is therefore not included or manually copied.
