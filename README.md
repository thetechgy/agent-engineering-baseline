# Agent engineering baseline

This MIT-licensed repository is a shared, project-agnostic configuration for
[Microsoft Agent Package Manager (APM)](https://microsoft.github.io/apm/).
It deploys reviewed instructions and skills to Codex and GitHub Copilot
tooling.

## How it is pinned

The repository uses APM's native dependency model, the same way `package.json`
and a lockfile work together:

- `apm.yml` declares intent: branch-ref dependencies (`#main`) and local
  `.apm/` content.
- `apm.lock.yaml` is the pinning authority. It records the exact resolved
  commit and a content hash for every dependency, so `apm install --frozen`
  reproduces the same files byte-for-byte on any machine.
- `.apm-version` pins the APM CLI release consumed by the bootstrap scripts
  and CI.
- `.apm-installer-checksums` pins SHA256 digests for the upstream
  `install.sh` and `install.ps1` scripts, so bootstrap and CI verify the
  installer bytes before executing them.
- Readable APM outputs (`AGENTS.md`, `.agents/skills/`, and
  `.github/instructions/`) are committed review artifacts; CI requires clean
  regeneration. The only exceptions are the 12 exact `msgraph` generated-data
  and program paths in `.gitignore`. Their content integrity remains enforced
  by `apm.lock.yaml` and `apm audit --ci`.

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
in place. Their readable instructions, references, and launcher scripts stay
committed even when a skill also ships large generated data or programs.

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
executed on a mismatch.

Preview without downloads or changes:

```sh
./scripts/bootstrap-global.sh --dry-run
```

```powershell
./scripts/Bootstrap-Global.ps1 -WhatIf
```

After preflight, each implementation:

1. Rejects linked or reparse-point repository sources and managed user-profile
   destinations.
2. Snapshots the existing manifest, lockfile, local sources, package cache,
   APM configuration, generated instructions, Codex and Copilot MCP
   configuration, and all ten managed skill directories under
   `~/.apm/backups/agent-engineering-baseline/<UTC timestamp>/`.
3. Stages and verifies the repository's `apm.yml`, `apm.lock.yaml`, and `.apm/`
   sources before replacing their user-scope copies.
4. Removes an old GitHub MCP entry only when its complete Codex or Copilot
   configuration exactly matches the previously reviewed default. Any
   customization fails closed before profile mutation.
5. Runs `apm install --global --frozen`, deploys the five reviewed local
   skills, previews both instruction compilations, writes them only after both
   previews pass, and verifies the resulting manifest, lockfile, sources,
   skills, generated markers, and preserved Codex settings.

Any failure after profile mutation starts restores the complete snapshot.
Successful snapshots are retained for manual rollback. The Bash implementation
requires `jq` only when it finds a legacy GitHub MCP entry to verify or remove.
PowerShell retains `-WhatIf` and `-Confirm` support and remains compatible with
Windows PowerShell 5.1 and PowerShell 7.

The bootstrap does not manage Codex's top-level `project_doc_max_bytes` or
`~/.copilot/AGENTS.md`. This baseline intentionally does not install a GitHub
MCP server; use the machine's existing `gh` CLI and authentication for GitHub
operations. No credential value belongs in this repository or generated
configuration. Start new Codex and Copilot sessions after deployment.

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
installation/compile/audit/package checks, clean-regeneration drift,
repository hygiene, and the project-agnostic content assertion.

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
Before accepting an update, manually review the pinned upstream commit and any
changed binary hashes. The hashes recorded by APM provide integrity evidence;
they do not prove that a program is benign. New generated output paths are not
implicitly ignored and therefore enter the normal Git review patch.

To run the same refresh locally:

```sh
apm update
apm compile --target codex,copilot
```
