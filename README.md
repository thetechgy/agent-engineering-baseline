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
repository. Use the transactional bootstrap for your shell:

```sh
./scripts/bootstrap-global.sh
```

```powershell
./scripts/Bootstrap-Global.ps1
```

Preview the complete preflight without changing the user profile:

```sh
./scripts/bootstrap-global.sh --dry-run
```

```powershell
./scripts/Bootstrap-Global.ps1 -WhatIf
```

The PowerShell implementation also supports `-Confirm` and runs under Windows
PowerShell 5.1 or PowerShell 7. The Bash repeat-install path requires `jq` only
when `github-mcp-server` is already registered in Codex.

Each implementation preflights required tools and reviewed sources, rejects
symbolic-link or reparse-point sources and managed targets, and then creates a
snapshot under:

```text
~/.apm/backups/agent-engineering-baseline/<UTC timestamp>/
```

The snapshot records originally absent paths and preserves the manifest,
lockfile, local `.apm/` sources, APM package cache and configuration, generated
instructions, Codex and Copilot MCP configuration, and all nine managed skill
directories (including the large `msgraph` payload). The scripts then copy the
reviewed manifest, lockfile, and local sources together, run
`apm install --global --frozen`, explicitly deploy the four local skills, and
compile Codex and Copilot instructions only after both compile dry runs pass.
They verify the generated markers and copied content before reporting success.

Any failure after mutation begins restores the complete snapshot automatically.
Successful snapshots are retained and their location is printed for manual
rollback. Repeated execution is safe: if Codex already has
`github-mcp-server`, the scripts inspect `codex mcp get --json` and recycle the
entry only when its endpoint and every setting exactly match APM's reviewed
default. A customized entry fails preflight without changing the profile. Bash
requires `jq` only for that exact-match inspection.

This deployment does not manage Codex's top-level `project_doc_max_bytes`
setting and does not read or change `~/.copilot/AGENTS.md`. Existing values and
unrelated user files are left untouched. Credentials remain user-managed:
provide `GITHUB_TOKEN` at runtime and never store its value in this repository
or generated files.

### Manual fallback

If neither script can run, reproduce the same transaction rather than using a
plain global install:

1. Verify `apm`, `codex`, the repository's `apm.yml`, `apm.lock.yaml`, `.apm/`
   tree, and the four local skill entrypoints. Reject linked/reparse sources or
   destinations before changing anything.
2. Create the timestamped backup above. Record each originally absent path and
   copy every path listed in the snapshot description, including
   `~/.apm/apm_modules` and the nine directories under `~/.agents/skills/`.
3. Run `codex mcp get github-mcp-server --json`. Continue when the entry is
   absent. If present, remove it only when the complete JSON exactly matches
   the reviewed streamable-HTTP endpoint, `GITHUB_TOKEN` bearer-token variable,
   enabled state, null tool filters/timeouts/headers, and no extra settings.
   Stop for any customization.
4. Stage and replace `~/.apm/apm.yml`, `~/.apm/apm.lock.yaml`, and
   `~/.apm/.apm/` from this repository. Remove only the nine managed skill
   directories and the two generated instruction outputs, then run:

   ```sh
   apm install --global --frozen
   for skill in a11y agent-safety ansible powershell-module-engineering; do
     mkdir -p ~/.agents/skills/"$skill"
     cp -R ~/.apm/.apm/skills/"$skill"/. ~/.agents/skills/"$skill"/
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

5. Verify the manifest and local sources match this repository, all nine skills
   exist, both generated files contain APM's generated marker near the top, and
   the pre-existing Codex documentation limit and `~/.copilot/AGENTS.md` did not
   change. Restore the snapshot immediately if any command or check fails.

APM 0.28.0 has no global audit mode. Run `apm audit --ci` in this
repository against the committed project deployment; running it from
`~/.apm/` incorrectly checks project-relative `.github/` and `.agents/` paths
instead of their user-scope destinations.

Start new Codex and Copilot sessions after changing user-scope instructions or
configuration. Credentials are still user-managed: provide `GITHUB_TOKEN` at
runtime and never store its value in this repository or generated files.

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
timestamp.

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

After accepting a repository update, rerun the platform bootstrap so the
reviewed manifest, lockfile, sources, skills, and instructions move together.

Do not run `apm update --global` as a substitute for this workflow: it would
resolve changes in the user-scope copy before they were reviewed and committed
here. Global updates affect every repository, so keep dependency resolution
and diff review in this repository.

## Rollback

For manual rollback, open the printed snapshot directory and process
`inventory.tsv`: remove each current managed path, restore every `present` path
from the matching location under `snapshot/`, and leave every `absent` path
removed. This restores the APM package cache, configurations, instructions, and
skills directly; do not run another installation over the restored snapshot.
Keep the snapshot until the rollback is verified, then start new Codex and
Copilot sessions.

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
