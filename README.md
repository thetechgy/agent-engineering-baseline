# Agent engineering baseline

This repository uses
[Microsoft Agent Package Manager (APM)](https://microsoft.github.io/apm/)
to deploy shared instructions, skills, and Model Context Protocol (MCP)
servers for Codex CLI and GitHub Copilot tooling. The configuration and
commands below were validated with APM 0.28.0.

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

APM deploys the small shared instruction core to `.github/instructions/`, the
task-specific skills to `.agents/skills/`, Codex MCP configuration to
`.codex/config.toml`, and VS Code-compatible MCP configuration to
`.vscode/mcp.json`. When GitHub Copilot CLI is installed and visible on `PATH`,
the same installation also merges the MCP servers into the current user's
`~/.copilot/mcp-config.json`. Compilation generates the root `AGENTS.md`
consumed by Codex and also recognized by GitHub Copilot CLI.

The editable local sources are under `.apm/`:

- `instructions/personal.instructions.md` contains only cross-project planning,
  branch, publication, security, and preservation boundaries.
- `skills/a11y/`, `skills/agent-safety/`, `skills/ansible/`, and
  `skills/powershell-module-engineering/` hold specialist guidance that loads
  only when the task matches each skill description.

The PowerShell skill determines the repository's declared Pester version
before applying test guidance. FACT Pester 6 work routes to FACT's canonical
`.github/instructions/powershell-pester-6.instructions.md`; this package does
not maintain a second copy of that contract.

Commit `apm.yml`, `apm.lock.yaml`, the deployed files, and generated
`AGENTS.md`. Do not commit `apm_modules/`; it is a reproducible package cache.
The deployed `.agents/skills/msgraph/` directory is also ignored: it contains
roughly 110 MB of platform binaries and index databases that `apm install`
regenerates locally, so it stays out of version control.

## Install globally

Use APM's user scope when the same baseline should be available in every
repository. APM 0.28.0 reads global dependency state from `~/.apm/`, so copy
the repository's reviewed manifest and lockfile there before installing:

```sh
mkdir -p ~/.apm
cp apm.yml ~/.apm/apm.yml
cp apm.lock.yaml ~/.apm/apm.lock.yaml
mkdir -p ~/.apm/.apm
cp -R .apm/. ~/.apm/.apm/
apm install --global --frozen
for skill in a11y agent-safety ansible powershell-module-engineering; do
  mkdir -p ~/.agents/skills/"$skill"
  cp ~/.apm/.apm/skills/"$skill"/SKILL.md ~/.agents/skills/"$skill/SKILL.md"
done
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
New-Item -ItemType Directory -Force -Path "$HOME/.apm/.apm" | Out-Null
Copy-Item -Path './.apm/*' -Destination "$HOME/.apm/.apm" -Recurse -Force
apm install --global --frozen
foreach ($skillName in @('a11y', 'agent-safety', 'ansible', 'powershell-module-engineering')) {
    $skillDestination = "$HOME/.agents/skills/$skillName"
    New-Item -ItemType Directory -Force -Path $skillDestination | Out-Null
    Copy-Item -LiteralPath "$HOME/.apm/.apm/skills/$skillName/SKILL.md" -Destination $skillDestination -Force
}
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

Copy the manifest, lockfile, and `.apm/` sources together so the global
installation cannot mix versions. `--frozen` refuses to re-resolve dependencies
and deploys the exact commits already reviewed in this repository. The
installation stores dependency package content under `~/.apm/`, deploys
dependency skills under `~/.agents/skills/`, and configures supported
user-scope MCP clients. APM 0.28.0 deliberately skips root-local `.apm/`
primitives during a global install, so the explicit copy step deploys the four
reviewed local skill sources already synchronized into `~/.apm/.apm/`. The
compiler commands ensure that both CLIs receive the same small personal
instruction core; specialist skill bodies remain on demand.

Use the normal APM compiler against the global package state as shown above to
generate both user-scope instruction files. They remain APM-generated files;
the explicit targets, single-file mode, and output paths make the destinations
reviewable and deterministic. Re-evaluate this APM 0.28.0 workflow when
updating the CLI.

APM 0.28.0 has no global audit mode. Run `apm audit --ci` in this
repository against the committed project deployment; running it from
`~/.apm/` incorrectly checks project-relative `.github/` and `.agents/` paths
instead of their user-scope destinations.

APM does not overwrite a hand-authored user-scope instruction file. Before a
global rollout, create one timestamped backup directory containing the active
`~/.apm/apm.yml`, `~/.apm/apm.lock.yaml`, `~/.codex/AGENTS.md`,
`~/.codex/config.toml`, `~/.copilot/copilot-instructions.md`,
`~/.copilot/mcp-config.json`, `~/.apm/config.json`, any skill being retired,
and any existing skill that the deployment replaces. Do not edit the new
generated instruction files directly; change the package sources and compile
again instead.

This package does not manage Codex's project-documentation ceiling. Preserve an
existing top-level setting such as the following when deploying:

```toml
project_doc_max_bytes = 131072
```

Start new Codex and Copilot sessions after changing user-scope instructions or
configuration. Credentials are still user-managed: provide `GITHUB_TOKEN` at
runtime and never store its value in this repository or generated files.

APM 0.28.0's Codex MCP adapter can return an already-configured error when a
frozen global install is repeated with the same self-defined
`github-mcp-server` entry. Before a repeat global install, verify that the
existing entry matches the reviewed endpoint and backup, remove only that
APM-owned entry with `codex mcp remove github-mcp-server`, and let the frozen
installation recreate it. Do not use `--force` for this workaround because it
also broadens file-collision and security-finding behavior.

Global instructions are loaded for every repository, so keep the personal core
small. Domain manuals belong in discoverable skills and should not be added to
the compiled user instruction files. The 128 KiB ceiling may still be needed
for repositories with unusually large or deeply nested project instructions.

Microsoft Learn MCP ownership is intentionally outside this package. Codex
keeps the descriptive user-level `microsoft-learn` server with its restricted
tool allowlist, while GitHub Copilot receives `microsoft-learn` from the
installed Microsoft Docs plugin. Do not add a second generic `mcp` registration
for the same endpoint.

## Validate

Use the lockfile-only workflow and APM integrity audit in automation:

```sh
apm install --frozen
apm audit --ci
```

The generated primitives and compiled instructions are byte-stable on replay.
APM 0.28.0 may rewrite the lockfile's `generated_at` value on installation,
including `--frozen`; compare content separately from that documented
timestamp. The Codex MCP adapter limitation above means the complete install
command is not exit-code idempotent until its managed entry is reconciled.

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
mkdir -p ~/.apm/.apm
cp -R .apm/. ~/.apm/.apm/
apm install --global --frozen
for skill in a11y agent-safety ansible powershell-module-engineering; do
  mkdir -p ~/.agents/skills/"$skill"
  cp ~/.apm/.apm/skills/"$skill"/SKILL.md ~/.agents/skills/"$skill/SKILL.md"
done
(cd ~/.apm && apm compile --target codex --single-agents \
  --output ~/.codex/AGENTS.md)
(cd ~/.apm && apm compile --target copilot --single-agents \
  --output ~/.copilot/copilot-instructions.md)
```

Do not run `apm update --global` as a substitute for this workflow: it would
resolve changes in the user-scope copy before they were reviewed and committed
here. Global updates affect every repository, so keep dependency resolution
and diff review in this repository.

## Rollback

To roll back a user deployment, restore the timestamped backup copies of the
APM manifest and lockfile, instruction files, Codex/Copilot MCP configuration,
and any retired skill. Then run the frozen global installation and compile both
user instruction files from the restored `~/.apm` state. Start new Codex and
Copilot sessions after either deployment or rollback.

## Authentication and current limitations

No credentials are stored in this repository. The GitHub MCP server uses the
registry's remote HTTP transport. Codex reads its bearer token at runtime from
`GITHUB_TOKEN`; project MCP configuration becomes active after the repository
is trusted in Codex.

For private GitHub dependency resolution, APM can use
`GITHUB_COPILOT_PAT`, `GITHUB_TOKEN`, `GITHUB_APM_PAT`, or
`GITHUB_PERSONAL_ACCESS_TOKEN`. The generated Codex and GitHub Copilot CLI MCP
configurations preserve `GITHUB_TOKEN` as a runtime environment-variable
reference rather than writing its value. GitHub Copilot CLI configuration is
user-scoped and generated for each user by `apm install`; it is not committed
to this repository.

After deployment, verify skill and MCP discovery in fresh sessions. Existing
sessions retain their startup context and are not valid acceptance evidence.
