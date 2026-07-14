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

## Install globally

Use APM's user scope when the same baseline should be available in every
repository. APM 0.25.0 reads global dependency state from `~/.apm/`, so copy
the repository's reviewed manifest and lockfile there before installing:

```sh
mkdir -p ~/.apm
cp apm.yml ~/.apm/apm.yml
cp apm.lock.yaml ~/.apm/apm.lock.yaml
apm install --global --frozen
(cd ~/.apm && apm compile --target codex --single-agents \
  --output ~/.codex/AGENTS.md --dry-run)
(cd ~/.apm && apm compile --target copilot --single-agents \
  --output ~/.copilot/copilot-instructions.md --dry-run)
(cd ~/.apm && apm compile --target codex --single-agents \
  --output ~/.codex/AGENTS.md)
(cd ~/.apm && apm compile --target copilot --single-agents \
  --output ~/.copilot/copilot-instructions.md)
```

PowerShell equivalent:

```powershell
New-Item -ItemType Directory -Force -Path "$HOME/.apm" | Out-Null
Copy-Item -LiteralPath './apm.yml' -Destination "$HOME/.apm/apm.yml" -Force
Copy-Item -LiteralPath './apm.lock.yaml' -Destination "$HOME/.apm/apm.lock.yaml" -Force
apm install --global --frozen
Push-Location -LiteralPath "$HOME/.apm"
try {
    apm compile --target codex --single-agents --output "$HOME/.codex/AGENTS.md" --dry-run
    apm compile --target copilot --single-agents --output "$HOME/.copilot/copilot-instructions.md" --dry-run
    apm compile --target codex --single-agents --output "$HOME/.codex/AGENTS.md"
    apm compile --target copilot --single-agents --output "$HOME/.copilot/copilot-instructions.md"
}
finally {
    Pop-Location
}
```

Copy both files together so the global installation cannot mix a newer
manifest with an older lockfile. `--frozen` refuses to re-resolve dependencies
and deploys the exact commits already reviewed in this repository. The
installation stores package content under `~/.apm/`, deploys shared skills
under `~/.agents/skills/`, configures supported user-scope MCP clients, and
generates GitHub Copilot CLI's native user-scope instruction file. APM 0.25.0
only includes some virtual instruction-file packages in that generated Copilot
file, so the explicit compiler command above replaces it with the complete
five-package context.

APM 0.25.0's `compile --global` does not discover the virtual instruction-file
packages used by this baseline. Run the normal APM compiler against the global
package state as shown above to generate both user-scope instruction files.
They remain APM-generated files; the explicit targets, single-file mode, and
output paths are the version-specific workaround. Re-evaluate it when updating
APM.

APM 0.25.0 also has no global audit mode. Run `apm audit --ci` in this
repository against the committed project deployment; running it from
`~/.apm/` incorrectly checks project-relative `.github/` and `.agents/` paths
instead of their user-scope destinations.

APM does not overwrite a hand-authored user-scope instruction file. Before the
first global compilation, move any existing `~/.codex/AGENTS.md`,
`~/.copilot/AGENTS.md`, or `~/.copilot/copilot-instructions.md` to inactive,
timestamped backup names after reviewing them. Do not edit the new generated
files directly; change the package sources and compile again instead.

The generated Codex instruction file is larger than Codex's default project
documentation budget. Preserve all other user configuration and add this
top-level setting to `~/.codex/config.toml`:

```toml
project_doc_max_bytes = 131072
```

Start new Codex and Copilot sessions after changing user-scope instructions or
configuration. Credentials are still user-managed: provide `GITHUB_TOKEN` at
runtime and never store its value in this repository or generated files.

Global instructions are loaded for every repository. This improves fidelity
and avoids missed skill activation, but increases context usage and exposes
unrelated tasks to domain-specific guidance. The 128 KiB ceiling can also be
reached when a repository has unusually large or deeply nested instructions.

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

After accepting a repository update, synchronize its reviewed manifest and
lockfile and replay the user-scope installation:

```sh
cp apm.yml ~/.apm/apm.yml
cp apm.lock.yaml ~/.apm/apm.lock.yaml
apm install --global --frozen
(cd ~/.apm && apm compile --target codex --single-agents \
  --output ~/.codex/AGENTS.md)
(cd ~/.apm && apm compile --target copilot --single-agents \
  --output ~/.copilot/copilot-instructions.md)
```

Do not run `apm update --global` as a substitute for this workflow: it would
resolve changes in the user-scope copy before they were reviewed and committed
here. Global updates affect every repository, so keep dependency resolution
and diff review in this repository.

## Authentication and current limitations

No credentials are stored in this repository. Microsoft Learn MCP uses its
public remote endpoint. The GitHub MCP server uses the registry's remote HTTP
transport. Codex reads its bearer token at runtime from `GITHUB_TOKEN`; project
MCP configuration becomes active after the repository is trusted in Codex.

For private GitHub dependency resolution, APM can use
`GITHUB_COPILOT_PAT`, `GITHUB_TOKEN`, `GITHUB_APM_PAT`, or
`GITHUB_PERSONAL_ACCESS_TOKEN`. The generated Codex and GitHub Copilot CLI MCP
configurations preserve `GITHUB_TOKEN` as a runtime environment-variable
reference rather than writing its value. GitHub Copilot CLI configuration is
user-scoped and generated for each user by `apm install`; it is not committed
to this repository.

The requested Awesome Copilot plugin source cannot currently be installed by
APM 0.25.0. The supplied `.github` directory is not a valid virtual package
root, while the parent plugin package and marketplace entry fail validation
because their manifest refers to agent and skill paths outside the isolated
plugin directory. The plugin is therefore not included or manually copied.
