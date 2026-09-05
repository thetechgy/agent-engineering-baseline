# Agent engineering baseline

This MIT-licensed repository is a shared, project-agnostic configuration for
[Microsoft Agent Package Manager (APM)](https://microsoft.github.io/apm/).
It deploys reviewed instructions and skills to Codex, GitHub Copilot, and the
other harnesses supported by APM's native global compiler.

The bootstrap has one deliberately custom security boundary: acquiring and
promoting a trusted APM CLI. Package installation, executable trust, dependency
resolution, updates, compilation, audit, and packing remain native APM
operations.

## Pinning and review boundary

The repository uses APM's native dependency model, like a manifest and lockfile:

- `apm.yml` declares branch-ref dependencies and reviewed local `.apm/`
  content.
- `apm.lock.yaml` records the exact resolved commit, deployed files, platform
  launchers, and content hashes for every dependency.
- `.apm-version` pins the complete APM release version.
- `.apm-checksums` contains exactly ten reviewed SHA-256 digests: the five
  supported release archives and the executable inside each archive.
- Readable compiled outputs are committed review artifacts and CI requires a
  clean mechanical regeneration. The only ignored outputs are the six large
  `msgraph` indexes and six platform binaries named exactly in `.gitignore`;
  the lockfile and `apm audit --ci` retain their integrity contract.

Hashes prove that consumers received the reviewed bytes; they do not prove
that those bytes are benign. A CLI update first enters a review-only pull
request as hashes and generated output. The candidate CLI is not executed by
the privileged update workflow.

## Local content

`.apm/` contains the reviewed local sources:

- `instructions/personal.instructions.md` provides shared engineering
  boundaries.
- `skills/a11y`, `agent-safety`, `ansible`, and
  `powershell-module-engineering` are maintained local adaptations.
- `skills/powershell-pester-6` is locally authored and remains the selected
  source of truth.

Installed `.agents/skills/` content is generated; edit its source or dependency
and regenerate rather than editing installed output directly.

## Microsoft Learn documentation

`apm.yml` declares the
[official Microsoft Learn MCP server](https://learn.microsoft.com/en-us/training/support/mcp)
through APM's `microsoftdocs/mcp` registry entry. It provides online Microsoft
documentation and code samples for GitHub Copilot CLI and Codex CLI. The
existing `msgraph` skill remains available for offline Graph API lookups.

The server uses Streamable HTTP at `https://learn.microsoft.com/api/mcp`,
without API keys or authentication. Its tool allowlist contains only:

- `microsoft_docs_search`
- `microsoft_docs_fetch`
- `microsoft_code_sample_search`

APM 0.29 applies `tools` to Copilot but does not translate it to Codex's
`enabled_tools`. The manifest uses APM's native passthrough support and a YAML
alias to supply the same list to both. APM also passes `enabled_tools` through
to Copilot, where `tools` is the operative setting. New tools require a
reviewed manifest change; the list does not auto-expand.

APM generates `.github/mcp.json` and `.codex/config.toml` for repository
installs, or the user-scoped Copilot and Codex MCP configs for global installs.
These repository configs and the lockfile's MCP metadata are review artifacts;
regenerate them with APM rather than editing them directly. Codex loads
project-scoped configuration only for trusted projects.

Tool queries and fetch URLs leave the machine for Microsoft's service. Do not
include secrets or private repository content. The service requires network
access, and neither its returned content nor its implementation is pinned by
the lockfile: it records the registry declaration, allowlists, and target
ownership, while the generated CLI configs record the resolved endpoint. Treat
retrieved documentation and samples as untrusted input, not agent instructions.

## Bootstrap

Linux and macOS:

```sh
./scripts/bootstrap.sh            # install at user scope, the default
./scripts/bootstrap.sh --repo     # install into the current repository
./scripts/bootstrap.sh --dry-run  # validate only local pin/checksum metadata
```

Windows PowerShell 5.1 or PowerShell 7:

```powershell
./scripts/Bootstrap-Baseline.ps1
./scripts/Bootstrap-Baseline.ps1 -Scope Repo
./scripts/Bootstrap-Baseline.ps1 -WhatIf
```

Every non-preview run uses a fresh network or configured mirror download. It
never executes or reuses an ambient, older, newer, aliased, or previously
installed APM executable because an executable digest cannot authenticate the
loadable `_internal` tree beside it.

The acquisition sequence is fail closed:

1. Select the reviewed archive for the operating system and architecture.
2. Download it from the official GitHub release or the authoritative
   `APM_RELEASE_BASE_URL` mirror without credentials or public retry.
3. Authenticate the archive with `.apm-checksums`.
4. Reject absolute, traversing, wrong-root, duplicate-executable, linked,
   reparse, unsupported, or incomplete onedir layouts.
5. Extract the complete bundle, authenticate its executable, and execute that
   staged absolute path only for the exact full-version postcondition.
6. Transactionally promote the complete bundle, including `_internal` and
   `.apm-installed`, reauthenticate it, and invoke APM only by absolute path.

Set `APM_NO_DIRECT_FALLBACK=1` to require a configured mirror. Preview never
downloads, creates a temporary directory, stages, extracts, executes, installs,
changes PATH, or creates a junction or symlink.

On Linux and macOS, `${APM_INSTALL_DIR:-$HOME/.local/bin}/apm` links to the
owned full bundle under the sibling `lib/apm` directory. Linux uses
`sha256sum`; macOS uses `shasum -a 256`. An existing unrelated command or
unowned bundle is not overwritten.

On Windows, the default root is `%LOCALAPPDATA%\Programs\apm`.
`APM_INSTALL_DIR`, when set, identifies the `bin`/shim directory just as it
does in APM's native installer; the installation root is its parent. The
complete bundle lives in `releases\v<pin>`, `current` is a validated junction,
and the ASCII `bin\apm.cmd` shim is location-relative:

```bat
"%~dp0..\current\apm.exe" %*
```

Windows promotion uses a named mutex, sibling staging, rollback, reparse-point
rejection, temporary TLS 1.2 enablement with restoration, and a PowerShell
5.1-safe junction deletion. `current` and `bin` are prepended to the current
process and User PATH. Both wrappers warn if another PATH command may still
shadow the reviewed location in new shells.

## Native deployment behavior

The default reference is the direct Git URL
`https://github.com/thetechgy/agent-engineering-baseline.git#main`, avoiding
default-registry shorthand routing. Override it with
`BASELINE_PACKAGE_REF` when a different reviewed source is required.

Global mode:

```sh
apm install --global --target codex,copilot --trust-bin --trust-transitive-mcp <ref>
apm update --global --yes --target codex,copilot
apm compile --global
```

Repository mode:

```sh
apm install --target codex,copilot --trust-bin --trust-transitive-mcp <ref>
apm update --yes --target codex,copilot
apm compile --target codex,copilot
```

Native `apm install` honors existing lockfile resolutions for branch refs, so
by itself a re-run would keep deploying the previously locked commit. The
native `apm update --yes` step therefore runs on every bootstrap: install
declares and deploys the baseline on first use, update re-resolves every
branch-ref dependency in the destination manifest to its latest commit and
redeploys the refreshed content, including the transitive Microsoft Learn MCP
configuration. Every bootstrap run therefore converges the baseline deployment
to its configured reviewed ref (`main` by default). On a fresh machine the
update is a no-op because install just resolved the latest refs.

The baseline's MCP dependency is transitive when the baseline is installed as
a package. `--trust-transitive-mcp` permits native APM deployment of that
reviewed dependency. This flag trusts transitive MCP dependencies across the
entire install graph, not just Microsoft Learn. Review any other packages
already in the destination manifest and any `BASELINE_PACKAGE_REF` override
before running bootstrap. For narrower trust, use native APM directly,
redeclare the reviewed MCP dependency in the destination's top-level manifest,
and omit `--trust-transitive-mcp`.

Scope and target selection are independent. Global mode deploys user-scoped
Codex and Copilot primitives for use across repositories; repository mode
deploys the same targets into the current project. Install, update, and
repository compile all supply explicit targets so saved APM configuration or
auto-detection cannot redirect the baseline. Repository mode intentionally
updates that project's manifest, lockfile, package cache, and compiled
outputs. The update step refreshes every branch-ref dependency declared in
the destination manifest, not only the baseline; review that manifest before
running bootstrap if it declares other dependencies.

Global compilation is intentionally broad native APM behavior: it writes root
contexts for roughly eleven supported harnesses and cannot be narrowed with
`--target` in global mode. It also writes this universal instruction into both
Copilot global context files. The duplicate Copilot context and unscoped
instruction warning are accepted native outputs.

### Migrating from the earlier custom deployment

Older repository versions directly generated two files without native APM
ownership markers. If those exact legacy generated files remain, remove them
once before the first native bootstrap:

```sh
rm -f ~/.copilot/copilot-instructions.md ~/.codex/AGENTS.md
```

Do not remove `~/.copilot/AGENTS.md`; user-authored global files remain
protected by APM's collision behavior. Old snapshots under
`~/.apm/backups/agent-engineering-baseline/` may be retained or removed by the
user after migration.

## Repository validation

Use the reviewed absolute APM executable and reproduce the deployment:

```sh
apm install --frozen --trust-bin
apm compile --target codex,copilot --validate
apm compile --target codex,copilot
apm audit --ci
apm pack --dry-run
```

Run the complete local gate:

```sh
./tests/bootstrap.sh
pwsh -NoLogo -NoProfile -File ./scripts/Invoke-Validation.ps1
```

The gate covers Pester (including both CLI MCP allowlists and endpoint checks),
PSScriptAnalyzer, Bash fixture archives, ShellCheck,
Markdown linting, frozen trusted-bin installation, compile validation and clean
regeneration, audit, pack dry-run, an offline `msgraph openapi-search` launcher
and index smoke test, repository hygiene, and `git diff --check`. CI adds a
macOS Bash lane and Windows PowerShell 5.1 fixture execution.

APM 0.29 does not expose `--trust-bin` on `audit` and skips bin deployment in
its non-TTY scratch replay. Validation therefore runs the unchanged
`apm audit --ci` command in a local pseudo-terminal so its full drift check
includes the launcher set installed with `--trust-bin`; it does not use
`--no-drift`.

## Scheduled reviewed updates

`.github/workflows/update-baseline.yml` runs weekly and on manual dispatch. Its
generate job checks out `main`, acquires the currently reviewed CLI, uses a
token only for the isolated latest-release metadata query, and downloads all
five candidate archives without credentials. It validates every archive layout
and computes the ten replacement hashes without executing candidate code.

The previously reviewed CLI performs dependency update, frozen trusted-bin
installation, compilation, validation, audit, and packing. A separate
write-capable job checks out `main`, applies the review patch only after
`git apply --check`, and opens or updates a pull request without executing
patched content. Ordinary unprivileged pull-request validation is the first
place the candidate CLI runs after its hashes are part of the reviewed patch.

Update pull requests never auto-merge. Review the upstream release, all ten
digests, resolved dependency commits, generated outputs, and CI results.
