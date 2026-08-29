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
- `.apm-checksums` pins SHA256 digests for the upstream Linux installer, every
  supported release archive, and each archive's executable member. Bootstrap
  and CI authenticate downloaded CLI code before it can execute.
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
- CLI with the reviewed executable digest and pinned reported version: leave it
  unchanged;
- any other existing CLI: stop before executing it or changing profile state.
  Remove or replace that unverified executable before rerunning bootstrap; the
  bootstrap never silently downgrades it.

On Linux, bootstrap verifies the pinned `install.sh`, the architecture-specific
archive, and its `apm` member. It then exposes only that verified archive through
a private local mirror and runs the official installer with an explicit
`VERSION`, `APM_RELEASE_BASE_URL=file://...`, and
`APM_NO_DIRECT_FALLBACK=1`. The promoted executable is rehashed before the
wrapper invokes native APM deployment commands. An existing executable is
likewise rehashed before its first `--version` call.

On Windows, bootstrap deliberately does not run upstream `install.ps1`, because
that script launches `apm.exe` before returning. A narrow adapter downloads and
verifies the x86_64 ZIP, verifies `apm.exe` before promotion, and maintains the
upstream `releases/<tag>`, `current` junction, and `bin/apm.cmd` layout. It honors
`APM_INSTALL_DIR`, rejects unsafe reparse targets, restores the prior CLI layout
if promotion fails, writes an ASCII-only location-relative command shim, and
rehashes the promoted or existing executable before its first `--version` call.
Neither platform uses sidecar, pip, or unpinned direct fallbacks.

Preview without downloads or changes:

```sh
./scripts/bootstrap-global.sh --dry-run
```

```powershell
./scripts/Bootstrap-Global.ps1 -WhatIf
```

Linux prerequisites are Bash and the standard GNU utilities used by the
wrapper; `curl` is needed only when the pinned APM CLI must be installed.
Windows requires Windows PowerShell 5.1 or PowerShell 7. Codex and Copilot CLIs
are not bootstrap prerequisites, and the Bash wrapper does not require `jq`.

After preflight, each implementation:

1. Authenticates any required CLI download and rejects linked or reparse-point
   repository sources and managed user-profile destinations.
2. Snapshots the existing manifest, lockfile, local sources, package cache,
   APM configuration, both generated instruction files, and all ten managed
   skill directories under
   `~/.apm/backups/agent-engineering-baseline/<UTC timestamp>/`. The inventory
   contains 17 managed paths.
3. Stages and verifies the repository's `apm.yml`, `apm.lock.yaml`, and `.apm/`
   sources before replacing their user-scope copies.
4. Runs `apm install --global --frozen`, deploys the five reviewed local
   skills, previews both instruction compilations, writes them only after both
   previews pass, and verifies the resulting manifest, lockfile, sources,
   skills, and generated markers.

Any failure after profile mutation starts restores every path the bootstrap
manages. Successful snapshots are retained for manual rollback. PowerShell
retains `-WhatIf` and `-Confirm` support and remains compatible with Windows
PowerShell 5.1 and PowerShell 7.

The bootstrap owns only the APM files, generated instructions, and skill paths
listed above. It does not inspect, modify, snapshot, or restore Codex or Copilot
configuration files, and it leaves `~/.copilot/AGENTS.md` user-owned. Users are
responsible for their own tool integrations and authentication. No credential
value belongs in this repository or generated configuration. Start new Codex
and Copilot sessions after deployment.

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
It refreshes `.apm-version` to the latest stable APM release, downloads all
supported release archives, re-pins the installer/archive/executable hashes in
`.apm-checksums`, re-resolves the branch-ref dependencies with native
`apm update --yes`, regenerates compiled outputs, runs the full validation
suite, and creates or updates one `automation/apm-baseline-update` pull request.
The workflow performs those update operations with the already reviewed CLI;
it does not execute a newly downloaded candidate release before its hashes are
reviewed and merged.

The update PR is never auto-merged. Review the lockfile diff, regenerated
outputs, and CI results before merging. GitHub Actions dependencies remain
pinned to full commit SHAs and are updated separately by Dependabot.
Before accepting an update, manually review the pinned upstream commit and every
changed installer, archive, and executable hash. The update pull request is the
human review boundary for new hashes. Hashes provide integrity evidence; they do
not prove that a program is benign. New generated output paths are not
implicitly ignored and therefore enter the normal Git review patch.

To run the same refresh locally:

```sh
apm update
apm compile --target codex,copilot
```
