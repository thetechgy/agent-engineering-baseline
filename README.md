# Agent engineering baseline

This MIT-licensed repository is a shared, project-agnostic configuration for
[Microsoft Agent Package Manager (APM)](https://microsoft.github.io/apm/).
It deploys reviewed instructions, skills, and the official hosted GitHub MCP
server to Codex and GitHub Copilot tooling.

## Review-pinned inputs

The repository treats APM as a reviewed dependency:

- `apm-cli.lock.yml` approves one stable CLI release, the exact release commit,
  pinned installer hashes, release archive hashes, and executable hashes for
  supported Windows and Linux builds.
- `apm.yml` uses exact commit SHAs for every APM dependency.
- `apm.lock.yaml` and its content hashes are the frozen dependency authority.
- `upstream-sources.json` records the repository, path, commit, Git blob,
  SHA-256, and declared transformation for each mechanically mirrored skill.
- `.apm/` contains the local reviewed sources. Generated harness files are
  committed so drift is reviewable.

The native upstream `dependabot`, `git-commit`,
`github-actions-hardening`, `msgraph`, and `code-simplification` skills are
installed unchanged by APM. Accessibility, agent-safety, Ansible, and
PowerShell instruction sources are mechanically converted into skills by
replacing only their instruction frontmatter. Their Markdown bodies remain
byte-identical to the recorded upstream sources. `powershell-pester-6` is a
project-agnostic, user-authored local skill.

Verify or regenerate the mechanical mirrors with:

```powershell
./scripts/Sync-UpstreamSkills.ps1 -Check
./scripts/Sync-UpstreamSkills.ps1
```

The second command fetches only the exact commits recorded in the provenance
manifest. Installed `.agents/skills/` outputs are generated artifacts; never
edit them in place.

## Global bootstrap

Run the wrapper for the current platform from the repository root.

Linux (x86_64 or ARM64):

```sh
./scripts/bootstrap-global.sh
```

Windows (Windows PowerShell 5.1 or PowerShell 7):

```powershell
./scripts/Bootstrap-Global.ps1
```

Bootstrap reads `apm-cli.lock.yml` and behaves as follows:

- missing CLI: install the approved version;
- older CLI: upgrade to the approved version;
- matching CLI: leave it unchanged;
- newer CLI: stop before deployment rather than downgrade or run unreviewed
  behavior.

The wrapper downloads the official installer from its pinned release tag,
checks the installer SHA-256, and passes an explicit `VERSION`. The official
Windows installer also validates the matching release checksum sidecar. After
the CLI preflight, the wrapper delegates to native commands:

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

APM owns its mutable user-scope modules, caches, compiled instructions, and the
same-named official GitHub MCP entry. The wrapper preserves unrelated user
configuration and refuses to continue when an existing `github-mcp-server`
Codex entry is customized. Provide `GITHUB_TOKEN` only at runtime; no credential
value belongs in this repository or generated configuration.

The hosted GitHub MCP implementation is the sole intentionally mutable APM
runtime boundary. The manifest pins its registry identity and configuration,
but the registry currently exposes no server content hash or version for this
remote service. Runner images and local operating-system tools are outside the
APM immutability boundary.

## Repository install and validation

Use the approved CLI version, then reproduce the committed project deployment:

```sh
apm install --frozen
apm compile --target codex,copilot --validate
apm compile --target codex,copilot
apm audit --ci
apm pack --dry-run
```

Run the platform behavior and provenance tests plus normal hygiene:

```sh
./tests/bootstrap-global.sh
pwsh -NoLogo -NoProfile -File ./scripts/Invoke-Validation.ps1
```

The validation workflow also exercises Pester on PowerShell 7 and Windows
PowerShell 5.1, PSScriptAnalyzer, ShellCheck, Markdown linting, frozen APM
installation/compile/audit/package checks, clean-regeneration drift, and the
project-agnostic content assertion.

## Scheduled reviewed updates

`.github/workflows/update-baseline.yml` runs weekly and on manual dispatch. It
checks the latest stable APM release and the latest commit affecting each
recorded upstream path. When anything changes, it refreshes the CLI lock,
exact dependency references, provenance, mirrored skills, APM lockfile, and
generated outputs; runs validation; and creates or updates one
`automation/apm-baseline-update` pull request.

The update PR is never auto-merged. Review the upstream bodies, provenance,
release hashes, generated diff, and CI results before merging. GitHub Actions
dependencies remain pinned to full commit SHAs and are updated separately by
Dependabot.

To run the same refresh locally:

```powershell
./scripts/Update-Baseline.ps1
```
