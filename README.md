# Agent engineering baseline

[![Validate CI](https://github.com/thetechgy/agent-engineering-baseline/actions/workflows/validate.yml/badge.svg?branch=main)](https://github.com/thetechgy/agent-engineering-baseline/actions/workflows/validate.yml)
[![Dependabot](https://img.shields.io/badge/Dependabot-enabled-025e8c?logo=dependabot)](.github/dependabot.yml)
[![Bootstrap shells: PowerShell 7 and Bash](https://img.shields.io/badge/Bootstrap_shells-PowerShell_7_%7C_Bash-5391FE?logo=powershell&logoColor=white)](#get-started)
[![License: MIT](https://img.shields.io/badge/License-MIT-2E7D32)](LICENSE)

## Purpose

I use this repo to maintain the instructions and skills I use with Codex CLI and GitHub
Copilot CLI, both at work and for personal projects like my homelab. I'm a systems
engineer working mostly in infrastructure and security, with a lot of PowerShell
scripting and module development.

I wanted one place to manage that setup instead of maintaining it separately for each
CLI. Projects can still have their own instructions. If you do similar work, feel free
to use this as a starting point and adapt it.

A **skill** is a set of instructions and references for a particular kind of work. Mine
cover:

- **PowerShell:** module development, Pester 6 testing, and simplifying code.
- **Infrastructure:** Ansible and Podman.
- **Security and Git:** agent safety, GitHub Actions hardening, dependency updates,
  accessibility, commits, and GitHub CLI usage.
- **Microsoft documentation:** API references and offline Graph lookups.

Most skills are imported or adapted from other projects; the Pester 6 skill is one I
wrote. Browse the [installed skills](.agents/skills/) or
[locally maintained sources](.apm/skills/) to see what's included.

The [shared instructions](.apm/instructions/personal.instructions.md) tell agents to
inspect the repo, keep changes focused, preserve unrelated work, and report what they
actually verified. Commits, pushes, and other remote changes require approval. Project
instructions can add more specific requirements.

## How it works

[Microsoft Agent Package Manager (APM)](https://microsoft.github.io/apm/) handles
installation and generates the configuration for both CLIs. The [manifest](apm.yml)
lists the skills, shared instructions, and Microsoft Learn connection. See the
[APM command reference](https://microsoft.github.io/apm/reference/) for its native
commands.

Microsoft Learn uses **Model Context Protocol (MCP)** to let agents search official
Microsoft documentation. There's also an offline Microsoft Graph reference skill.

The bootstrap scripts verify and install a pinned APM CLI. That's different from pinning
the skills: fresh installations can resolve upstream branches, while unchanged
destination locks are retained on reinstall. See
[Security and safety](#security-and-safety) before running the scripts.

GitHub Actions checks PRs and pushes to `main`, including scripts, generated files,
skill quality, and installation tests on Windows and Ubuntu.
[Validation results](https://github.com/thetechgy/agent-engineering-baseline/actions/workflows/validate.yml)
are public. Paid behavioral evaluations require separate approval. A
[weekly update workflow](.github/workflows/update-baseline.yml) proposes changes through
PRs; nothing auto-merges.

## Get started

The supported targets are Windows 11 x86_64 with the latest stable PowerShell, and
Ubuntu 26.04 LTS x86_64 or arm64 with Bash. Install PowerShell 7 separately from the
Windows-provided Windows PowerShell, and install your agent CLI separately. You'll
need network access to releases/dependencies or a mirror. Bash needs `curl`, `tar`,
and `sha256sum`.

**Before installing:** Default bootstrap trusts bundled executables and transitive MCP
servers. Ordinary installation retains matching destination locks; it does not
refresh dependency branches. A fresh installation can still select upstream revisions
that have not been individually reviewed here. Review the
[security details](#security-and-safety). User scope changes your shared agent
configuration; project scope changes the current project.

From the baseline checkout, on Windows:

```powershell
./scripts/Bootstrap-Baseline.ps1 -WhatIf # preview: local metadata only
./scripts/Bootstrap-Baseline.ps1         # user scope, the default
./scripts/Bootstrap-Baseline.ps1 -Scope Repo
```

On Ubuntu:

```sh
./scripts/bootstrap.sh --dry-run  # preview: local metadata only
./scripts/bootstrap.sh            # user scope, the default
./scripts/bootstrap.sh --repo
```

Project scope uses your **current directory**, not the script's directory. To install
into another project, run the wrapper from there:

```powershell
Set-Location C:\work\target-project
& C:\work\agent-engineering-baseline\scripts\Bootstrap-Baseline.ps1 -Scope Repo
```

```sh
cd /path/to/target-project
/path/to/agent-engineering-baseline/scripts/bootstrap.sh --repo
```

The wrapper uses the APM pins from its own checkout but installs
`https://github.com/thetechgy/agent-engineering-baseline.git#main` by default. Set
`BASELINE_PACKAGE_REF` to install a different reviewed revision; local edits to the
wrapper's checkout aren't automatically installed. Reinstalling unchanged `#main`
keeps the destination's locked baseline commit; it does not adopt newer commits
on that branch. See [deliberate updates](#install-and-update-deliberately).

Both scopes configure both CLIs. Codex only loads project configuration for trusted
projects; Copilot CLI also requires folder trust before loading project MCP servers.
APM maintains the following state and CLI instruction sources:

| Scope | APM state | Instructions | MCP configuration | Skills |
| --- | --- | --- | --- | --- |
| User | `~/.apm/apm.yml`, `~/.apm/apm.lock.yaml`, `~/.apm/config.json` | Codex: `~/.codex/AGENTS.md`; Copilot: `~/.copilot/instructions/personal.instructions.md` | `~/.codex/config.toml`, `~/.copilot/mcp-config.json` | `~/.agents/skills/*` |
| Project | `./apm.yml`, `./apm.lock.yaml`, `./apm_modules/` | Both: `./AGENTS.md`; Copilot also: `./.github/instructions/personal.instructions.md` | `./.codex/config.toml`, `./.github/mcp.json` | `./.agents/skills/*` |

With APM 0.35.0, user-scope compilation also generates `~/.copilot/AGENTS.md`.
Local discovery with Copilot CLI 1.0.103 selected the modular user instruction above,
not that generated root file. At project scope it discovered both `AGENTS.md` and
the modular instruction. For these baseline inputs, native compilation removes
the redundant `.github/copilot-instructions.md`; it does not generate a user
`~/.copilot/copilot-instructions.md`. Generated-file checks establish delivery;
they do not by themselves establish what a CLI loads.

### Install and update deliberately

Ordinary bootstrap uses native `apm install` followed by compilation. Matching
locked revisions stay fixed even when upstream branches move. New or changed
dependency declarations resolve natively. Missing locks require new resolution;
a selected install does not reconstruct unrelated packages' lock entries, even
when their declarations and deployed files remain. Restore the reviewed lock in
an existing multi-package destination rather than treating bootstrap as lock
repair. Malformed or conflicted locks fail rather than being silently reset. Preserve the
destination manifest and lockfile, and inspect APM's reported resolved commits.

**Adopt a specific reviewed baseline commit:** set the existing override, then run
bootstrap for the intended scope. For example:

```sh
export BASELINE_PACKAGE_REF='https://github.com/thetechgy/agent-engineering-baseline.git#<reviewed-commit>'
./scripts/bootstrap.sh --global  # or --repo from the destination project
```

```powershell
$env:BASELINE_PACKAGE_REF = 'https://github.com/thetechgy/agent-engineering-baseline.git#<reviewed-commit>'
./scripts/Bootstrap-Baseline.ps1 -Scope Global # or Repo from the destination project
```

Replace `<reviewed-commit>` with the reviewed commit SHA. **Reuse this override on
every bootstrap invocation**, or persist it in your own shell configuration for
future sessions. These assignments persist only in the current shell. Bootstrap
otherwise selects `#main` and can change an existing SHA declaration back to that
branch. Fetching newer wrapper code alone does not update an unchanged locked
baseline. Changing the baseline ref adopts its instructions/local skills and any
changed dependency declarations; unchanged transitive declarations retain their
destination locks. It does not import the new baseline's source lockfile.

**Deliberately refresh branch-tracking dependencies:** use the reviewed executable
reported by bootstrap. The following paths are the defaults; adjust them for
`APM_INSTALL_DIR`. Select the same baseline reference you intend to retain.

On Ubuntu:

```sh
apm_path="$HOME/.local/bin/apm"
baseline_ref="${BASELINE_PACKAGE_REF:-https://github.com/thetechgy/agent-engineering-baseline.git#main}"
# User scope:
"$apm_path" install --global --update --target codex,copilot --trust-bin --trust-transitive-mcp "$baseline_ref"
"$apm_path" compile --global
# Repository scope, from the destination project:
"$apm_path" install --update --target codex,copilot --trust-bin --trust-transitive-mcp "$baseline_ref"
"$apm_path" compile --target codex,copilot
```

On Windows, with the latest stable PowerShell:

```powershell
$apm = Join-Path $env:LOCALAPPDATA 'Programs/apm/bin/apm.cmd'
$baselineRef = if ($env:BASELINE_PACKAGE_REF) { $env:BASELINE_PACKAGE_REF } else {
    'https://github.com/thetechgy/agent-engineering-baseline.git#main'
}
# User scope:
& $apm install --global --update --target codex,copilot --trust-bin --trust-transitive-mcp $baselineRef
& $apm compile --global
# Repository scope, from the destination project:
& $apm install --update --target codex,copilot --trust-bin --trust-transitive-mcp $baselineRef
& $apm compile --target codex,copilot
```

Run only the pair for your intended scope and stop if installation fails. The
positional package scopes refresh to the baseline and its dependency subtree;
with a valid destination lock, independent unrelated packages retain their locked
commits. Shared dependency
identities can affect other consumers, subject to APM's native conflict rules.
Both trust flags are intentionally retained in these commands. A SHA-selected baseline stays
at that SHA while its branch-tracking children refresh; a `#main` selection also
adopts the current baseline branch tip. Inspect the resulting commits and deployed
configuration before use. This is deliberate upstream resolution, **not** replay of
this repository's reviewed transitive lock. Avoid bare `apm update` when you do not
intend to refresh every dependency in the destination.

The daily freshness report detects candidates, review approves changes, and the
weekly updater proposes source/lock changes. Installing an approved baseline ref
and deliberately refreshing a destination are separate actions. Neither process
makes every fresh-installed transitive revision individually reviewed.

### Reinstall when adopting APM 0.35

An in-place upgrade from APM 0.34 to 0.35 is unsupported here. Existing skills
lack the installation-local deployment receipts required by 0.35; bootstrap can
report success while removing dependency skills. This personal baseline uses a
manual clean reinstall instead of maintaining a version migration path. Bootstrap
does not detect or repair the old installation automatically.

For my user-scope installation, all skills come from this baseline. Close agent
sessions, then move the deployed skills aside as a backup. On Windows:

```powershell
$skills = Join-Path $HOME '.agents/skills'
$backup = "$skills.pre-apm-0.35-$([Guid]::NewGuid().ToString('N'))"
Move-Item -LiteralPath $skills -Destination $backup -ErrorAction Stop
```

On Ubuntu:

```sh
skills="$HOME/.agents/skills"
backup="$skills.pre-apm-0.35-$(date -u +%Y%m%dT%H%M%SZ)"
mv -T --no-clobber -- "$skills" "$backup"
```

After the move succeeds, rerun the appropriate bootstrap command above. Keep APM
metadata and the Codex/Copilot configuration in place so their settings survive.
The missing skills are deployed afresh and APM establishes its own receipts.
This recipe assumes the entire skills directory belongs to this baseline; it is
not a reset procedure for an installation containing other sources or local edits.
For project scope, use the target project's `.agents/skills` directory and the
repository-scope bootstrap command.

Before removing the backup, confirm every expected skill is present, exercise the
Microsoft Graph launcher, rerun bootstrap, and run `apm audit --ci` interactively
from the APM metadata directory (`~/.apm` for user scope, the project root for
project scope). Keep the backup if any check fails. Native Windows reinstall
behavior has not been verified; see the PR's platform validation results.

### Example: maintain a PowerShell module

For a routine change, I might ask:

> This module accepts an empty server name and fails later with an unclear error.
> Review the code, project instructions, and supported PowerShell versions.
> Fix the validation on a new branch without changing valid calls or unrelated
> code. Use the PowerShell module and Pester 6 skills, test empty and valid input,
> and run the relevant checks. Tell me what changed, what passed, and what you
> couldn't verify. Don't commit or push.

For Microsoft APIs, match examples to the project's SDK version and hosting model.
Verify deployment behavior and recovery separately; an agent's answer isn't evidence
that infrastructure works.

### Options and troubleshooting

| Variable | Effect |
| --- | --- |
| `APM_INSTALL_DIR` | CLI command directory; defaults to `~/.local/bin` on Ubuntu and `%LOCALAPPDATA%\Programs\apm\bin` on Windows. Windows uses its parent as the installation root. |
| `APM_RELEASE_BASE_URL` | Authoritative HTTPS mirror on all platforms; `file://` mirrors work on Ubuntu only. Downloads use no credentials and never retry against the public source. |
| `APM_NO_DIRECT_FALLBACK=1` | Requires a configured mirror. |
| `BASELINE_PACKAGE_REF` | Overrides the installed baseline reference. |

`--cli-only` or `-CliOnly` installs just the reviewed APM CLI. Preview (`--dry-run` or
`-WhatIf`) checks local metadata without downloading, executing, or changing anything.

On Ubuntu, rerun bootstrap after moving the installation tree because its
command link uses an absolute path. After a forced kill, confirm bootstrap has
stopped before removing the diagnostic's `lib/apm/.lock`. Windows uses relative
`bin\apm.cmd`, a named mutex, PowerShell 7 HTTPS downloads, and process/User PATH updates.
User PATH failure is a warning; both wrappers warn about other commands masking APM.

Bootstrap sets `VERSION=<pin>` to avoid release lookup. Don't use `apm self-update`; it
replaces the reviewed CLI. An unscoped-instructions warning and this MCP warning are
expected:

```text
[!] MCP dependency 'microsoft-learn': unknown key(s) preserved in extra: enabled_tools
```

See the [PowerShell](scripts/Bootstrap-Baseline.ps1) and
[Bash](scripts/bootstrap.sh) wrappers for diagnostics.

## Security and safety

I treat agent tooling like other dependencies: review updates, check what gets
installed, and limit what it can access. The checks here help, but don't replace
approvals or reviewing code from other projects.

### Prompt injection and operating boundaries

Files, tool results, documentation, and test inputs can contain instructions that try to
redirect an agent, expose secrets, or trigger actions you didn't approve. The
[shared rules](.apm/instructions/personal.instructions.md) tell agents to treat these
sources as untrusted. They can't override your instructions or authorization.

Rules in a prompt aren't enforcement. Keep sandboxing and approval controls enabled,
limit access to credentials, and review actions that affect code, infrastructure, or
remote systems.

### Reviewed upstream changes and installation trust

**The repo and your installation have different update boundaries.**

- **This repo:** [`apm.lock.yaml`](apm.lock.yaml) records the reviewed dependency
  revisions, files, launchers, and hashes. Updates to `main` need a PR and review; they
  don't auto-merge. Ignored Graph indexes and binaries still have lockfile and audit
  checks.
- **Your installation:** its own manifest and lock govern the result. Ordinary
  bootstrap retains matching locks, including an unchanged baseline branch ref.
  Fresh installations or new declarations can resolve branch-tracking skills to
  current upstream commits rather than this repository's reviewed commits. Even a
  fixed baseline commit does not freeze those transitive branches. Five imported
  skills track `main`; git-commit and gh retain explicit commit declarations.

Review the destination's manifest, resolved skills, executable assets and source
overrides. `--trust-bin` remains necessary for `msgraph`: APM 0.35.0 can exit zero
without it while omitting the skill's platform binaries. Package approvals alone
do not replace noninteractive bin consent; adding destination approval policy is
outside this change.

`--trust-transitive-mcp` temporarily remains and trusts self-defined MCP servers
across the **whole dependency graph**, not just Microsoft Learn. This is broader
trust than desired and **not a completed security remediation**. The reviewed
Learn declaration still specifies HTTP transport, `https://learn.microsoft.com/api/mcp`,
and exactly `microsoft_docs_search`, `microsoft_docs_fetch` and
`microsoft_code_sample_search` through both clients' intended allowlists.

APM 0.35.0 automatically trusts the baseline's direct-package Learn declaration
without the blanket flag. Nevertheless, Copilot lifecycle probes demonstrated
success with a preserved but incorrect local endpoint, and deletion of edited
connections during stale cleanup. Codex rejected the corresponding edited
connection. Retaining today's flags does not fix those native risks, and an exit
code of zero alone does not establish complete installation or correct native
settings. Preserve user changes and inspect deployed functionality; do not use
`--force` to take over foreign configuration.

[Issue #88](https://github.com/thetechgy/agent-engineering-baseline/issues/88)
tracks safe native MCP trust narrowing **and** reviewed transitive reproducibility
for fresh installations. It includes the tagged source evidence, reproduced
limitations and Windows/Ubuntu acceptance criteria. A fresh probe of baseline
`8c5f7af` selected msgraph `5da043b2` while the reviewed source lock contained
`e77b382d`, illustrating the executable supply-chain gap. Removing automatic
updates stabilizes subsequent installs; it does not retroactively review those
initial choices. Immutable declarations or reviewed native bundles require a
separate installation/publication design. No custom resolver, MCP restoration
mechanism or extra bootstrap runtime is introduced here.

### Verified tooling and reviewed refreshes

The wrappers never rely on an existing `apm` from PATH. They use the release in
[`.apm-version`](.apm-version) and six reviewed SHA-256 hashes in
[`.apm-checksums`](.apm-checksums), covering three archives and their executables.
Downloads use no credentials. Bootstrap rejects unsafe or incomplete bundles, checks the
executable and version, and runs it by absolute path. Matching hashes prove integrity
against the reviewed values, **not** that the code is safe.

The previous installation stays available until the new one is activated. Cleanup checks
ownership and paths, avoids unmarked directories, links, and Windows reparse points, and
rejects concurrent runs. Another process with write access to the installation root is
outside these protections.

The update workflow uses the previously reviewed CLI. It checks new archives against
upstream hashes and inspects their layouts **without running the candidate**. Generated
changes are restricted to approved paths; a separate job opens the PR without executing
changed content. Normal PR validation runs the candidate CLI. Before merging, review the
release and date, all hashes, dependency changes, generated files, and CI.

### Daily dependency review

[Dependency freshness](https://github.com/thetechgy/agent-engineering-baseline/actions/workflows/dependency-freshness.yml)
runs daily at 13:43 UTC and supports manual dispatch. Its first default-branch run
creates one bot-owned **Dependency freshness and upgrade review** issue. The issue
holds the current inventory and review evidence; its workflow-health link exposes
failed or interrupted collection. Reports are also retained as seven-day artifacts.
Find the issue through [its title](https://github.com/thetechgy/agent-engineering-baseline/issues?q=is%3Aissue+%22Dependency+freshness+and+upgrade+review%22+in%3Atitle)
and subscribe to receive material-change comments through your GitHub notification
settings. The publisher also links the issue from its job summary.

Freshness and management policy are separate. An outdated component can remain on
an intentional hold or belong to another updater. Actions and branch-tracking APM
skills show their actual pins with freshness **not checked** where this report
delegates upstream polling. Dependabot provides routine Actions version updates;
the Python security update in PR #77 does not establish routine Python version
coverage. The existing reviewed weekly APM update workflow remains responsible for
CLI/hash refreshes and branch dependencies. Neither mechanism is replaced.

The report monitors direct tooling and the explicitly constrained Harbor, OpenAI
and Pydantic compatibility group. It extracts pins from existing installation,
requirements, policy and manifest files; it does not copy version literals into
the [monitoring metadata](.github/dependency-freshness.json). Evaluator/scanner
transitives remain governed by upstream frozen locks. Container digests, Debian
snapshots, Python/model selectors and CLI fixture contracts retain their distinct
reproducibility boundaries; no OS package or container vulnerability scan is added.

Release metadata and public GitHub advisories provide evidence, not upgrade
approval. The report preserves advisory source, package/ecosystem, severity,
affected/fixed versions and GitHub's affected-version query result. A version match
does not establish platform applicability or exploitability; modified evaluators
retain build uncertainty. Publisher and GitHub-reviewed severities can differ.
Missing mappings, failed queries and incomplete pagination stay unknown. Security
mentions in release notes are signals rather than confirmed vulnerabilities. No
matching advisory is not a comprehensive safety assessment.

The issue body changes only with findings. Notification comments identify new
security or compatibility risks and newly outdated direct pins; routine drift
within held groups stays visible without a comment. Stable evidence markers on
bot comments prevent repeated notifications. Maintainer comments are preserved.
Multiple marker issues or a closed tracking issue stop publication for manual
correction. Do not delete notification markers if their alerts should remain
deduplicated. No dependency pins or upgrade PRs are generated by this report.

Discovery has read-only permissions and never executes upstream assets. A separate
default-branch job has only the issue-write permission needed for publication,
validates the data against its trusted inventory, and renders it independently.
Validated partial results can update the issue while discovery remains failed;
catastrophic failures retain the prior snapshot with a failing workflow status.
The publisher rejects superseded revisions. Neither job receives an API key or
extra advisory credential; public publisher-advisory queries are unauthenticated.

To inspect pins offline or run read-only discovery locally with Python 3.11+:

```bash
python3 -I -B .github/scripts/dependency_freshness.py inventory
report_root="$(mktemp -d)"
python3 -I -B .github/scripts/dependency_freshness.py check --output "$report_root/report"
```

An optional `GH_TOKEN` can avoid public API rate limits; never put it in commands,
reports or committed files. Exit 0 means configured lookups completed, 1 means a
validated partial report, and 2 means the report could not be safely produced.
Neither success nor a newer stable release establishes upgrade safety.

Maintenance: add an explicit metadata entry and targeted extraction assertions for
a new direct tool, including its official release source, package identity where
available, ownership/hold and validation requirements. Run the offline freshness
tests and a read-only smoke test. New arbitrary installer forms are not discovered
automatically. The bounded monitor is not a general dependency parser. Release
excerpts are selective; review the full pin-to-candidate comparison for intervening
changes. Evaluation upgrades require coordinated qualification and preservation of
historical tools, scoring and policy identities.

### Documentation access and privacy

The [Microsoft Learn MCP server](https://learn.microsoft.com/en-us/training/support/mcp)
at `https://learn.microsoft.com/api/mcp` is free and unauthenticated; model usage still
follows your agent plan. Both CLIs can use only `microsoft_docs_search`,
`microsoft_docs_fetch`, and `microsoft_code_sample_search`. Endpoint and tool changes
need manifest review.

Queries and fetch URLs leave your machine. Use only public API names and minimal
nonsensitive context, **never** secrets or private source. The lockfile pins the
connection and tool list, not the remote service or its results. Treat results as
untrusted reference material, and match examples to the installed SDK and hosting model.

If Learn isn't available, use an already authorized source or report the limitation.
Running fallback tools such as `npx @microsoft/learn-cli` or a global npm install
requires approval. The upstream MIT notice is retained in shared instructions and
generated outputs.

### CI permissions, credentials, and dependency checks

Validation uses read-only repository access without retained checkout credentials.
GitHub Actions are pinned to commit SHAs; Python dependencies use hashed or frozen
locks. Both evaluation workflows install Compose 5.6.1 through the shared
[checksum-first helper](.github/scripts/setup-compose.sh), verifying reviewed
release bytes before execution in an isolated temporary Docker CLI configuration.
Its always-run cleanup removes only that installation. Historical evidence keeps
its recorded Compose version; changed versions use separate benchmark policy
identities and are not directly comparable.
PowerShell Gallery modules have version pins but no native hash pins.

Paid evaluation requires approval through `skill-benchmark`, and only the live step
receives the API key. History and Pages jobs don't get it or execute skills; history
accepts only approved numeric metrics. Reports and temporary tools stay outside the
checkout. Don't put reports or `BENCHMARK.md` in either APM-managed skill collection.

Codex can access its key inside the evaluation container. Review the branch, workflow,
skill, cases, and inputs before approval. Upload filtering and redaction are best
effort; they cannot guarantee secrets won't leak, including in encoded output. Treat all
evaluation inputs and outputs as untrusted.

<!-- rumdl-disable MD033 -->
<details>
<summary>Repository CI settings and Python lock maintenance</summary>

In **Settings > Actions > General**, keep default permissions read-only and retain
selected-action and full-SHA requirements. Allow GitHub-owned actions and these
exact external references:

<!-- external-action-requirements:start -->

```text
astral-sh/setup-uv@1c37ad07a6a961277cf70c0d37d6f313000f5884
benchmark-action/github-action-benchmark@4322e5726e6334590d251fc4f92bec0efafc45dc
```

<!-- external-action-requirements:end -->

Missing entries prevent jobs from starting. CI checks that this list matches the
workflows; keep live repository settings synchronized.

When updating an external action, update its workflow references and this list
together. Add the new exact SHA to the live allowlist before validating the PR;
remove the superseded SHA after merging. Branches that still use the old SHA
must refresh from `main` before rerunning their workflows.

Enable **Allow GitHub Actions to create and approve pull requests** for update PRs.
The workflow never submits an approving review. For token-created PRs, a maintainer
with write access must select **Approve workflows to run** after reviewing the
candidate, then require all validation checks before merging. See
[GitHub's token-triggered workflow behavior](https://docs.github.com/en/actions/concepts/security/github_token).

SkillSpector uses its upstream frozen lock; Semgrep and rumdl use reviewed hashed
locks in [.github/requirements](.github/requirements). CI rejects unverified Python
installers and records tool versions and dependency inventories. Both locks use
uv 0.13.5. Semgrep installation requires wheels; regenerate its lock for Python
3.13 and the Linux x86_64 / glibc 2.34 wheel floor:

```bash
uv pip compile --python-version 3.13 --python-platform x86_64-manylinux_2_34 \
  .github/requirements/semgrep.in --output-file .github/requirements/semgrep.txt \
  --no-header --no-annotate --generate-hashes --only-binary :all:
```

For rumdl, substitute `rumdl` in both paths and retain its existing
`x86_64-unknown-linux-gnu` target. Review dependency changes and rerun validation.
These locks cover Python artifacts, not every underlying OS or build tool.

Semgrep version freshness uses official PyPI metadata, matching the package
installation source. Its GitHub release notes/tags and advisory checks remain
separate evidence; a PyPI patch can precede a public GitHub tag. See the
[Semgrep 1.182.1 assessment](.github/evals/SEMGREP-1.182.1.md) for artifact
verification, scanner comparisons, and residual MCP dependency risk.

Evaluation setup pins uv 0.13.5 and retains the managed Python 3.13 selector.
Fresh installations currently select Python 3.13.17; the exact interpreter version
is recorded in `versions.json`. Historical evaluation records retain their original
runtime identities, including Python 3.13.15; they are not rebaselined by this update.

</details>
<!-- rumdl-enable MD033 -->

## Maintaining the baseline

If you're only installing this setup, you can skip this section. To maintain the
collection, change `.apm/` sources or `apm.yml` and regenerate with APM. Don't edit
installed `.agents/skills/`, generated instructions, MCP config, or lock metadata
directly.

Repository review guidance lives in
[`baseline-review.instructions.md`](baseline-review.instructions.md). Pinned APM
0.35.0 discovers this root source during local compilation and generates it into
the shared `AGENTS.md`. Copilot CLI discovers that file and the deployed
`.github/instructions/personal.instructions.md`; native compilation removes the
redundant `.github/copilot-instructions.md`.
Keep this source outside `.apm/` and leave the manifest's explicit `includes`
unchanged so downstream instructions and packages exclude these review rules.

For skill-specific conventions, see
[PowerShell module engineering](.apm/skills/powershell-module-engineering/SKILL.md),
[Pester 6](.apm/skills/powershell-pester-6/SKILL.md), and
[Podman maintenance](.apm/skills/podman/MAINTENANCE.md).

### Regenerate and validate

Use the full validation suite below to reproduce the reviewed checkout. Its
[regeneration helper](scripts/apm_regeneration.py) copies current tracked inputs
(including staged additions and unstaged edits) into an independent temporary
checkout with the same Git origin. It regenerates skills from their sources,
checks frozen pins, compiles instructions, runs both native audit passes and
packaging, and compares generated outputs with the supplied checkout. It leaves
the caller's files, index, installation identity, and APM settings unchanged.
Stage new source files before running it; untracked files are not inputs.

APM 0.35 records rendered deployment receipts locally. A fresh checkout has no
such receipts, so installing over committed generated skills can skip or remove
them. Isolated regeneration starts with no deployed skills and establishes its
own temporary receipts. Output drift is a failure, not an instruction to repair
the caller's checkout or use `--force`.

The update workflow uses the same helper in refresh mode with the currently
reviewed CLI. It refuses pre-existing generated edits, verifies source files
remain unchanged, and returns only allowlisted generated outputs before the
existing patch capture and independent publisher checks. The candidate CLI is
still validated separately in its PR.

**Audit caveat:** Native audit replay does not retain launcher trust without a
terminal. The helper runs `apm audit --ci` in a pseudo-terminal with full drift
checking enabled. Do not bypass it with `--no-drift`.

For comparison, bootstrap's user-scope sequence is:

```text
apm install --global --target codex,copilot --trust-bin --trust-transitive-mcp <ref>
apm compile --global
```

Project scope omits `--global` and compiles with `--target codex,copilot`.

On Ubuntu, run the [full validation suite](scripts/Invoke-Validation.ps1) with
PowerShell 7 and the required Unix tools and validation dependencies installed:

```powershell
./scripts/Invoke-Validation.ps1
```

From Bash, use `pwsh -NoLogo -NoProfile -File ./scripts/Invoke-Validation.ps1`.
Full validation includes linting, regeneration, audit, packing, MCP contracts,
Graph smoke checks, and diff hygiene.

On Windows, run the Pester and PSScriptAnalyzer suite in the latest stable PowerShell:

```powershell
./scripts/Invoke-Validation.ps1 -Suite Pester
```

For Bash fixtures alone on Ubuntu, run `./tests/bootstrap.sh`. CI uses
`ubuntu-latest` for the full suite and `windows-latest` for Pester/analyzer and
Windows installation checks. Each platform job acquires the latest published stable
PowerShell, verifies its official release SHA256, and invokes its absolute path;
previews, betas, and release candidates are excluded. The actual host and runtime
versions appear in the job log. CI runs on PRs and pushes to `main`, without a
separate schedule. Rolling hosted images provide compatibility evidence; they do
not establish exact Windows 11 or Ubuntu 26.04 acceptance.

### Evaluate authored skills

A skill can look useful without improving results. I use NVIDIA's
[SkillEvaluator](https://github.com/NVIDIA/SkillEvaluator/blob/ac0a04905100acdafc6c95829311a9739c340ff6/README.md)
(pinned at v0.3.0) to evaluate locally maintained skills in `.apm/skills/`, separately
from installation.

Automated **Skill quality** checks cover security scanners and test-case data; LLM
checks and Tier 2 are disabled. Findings and incomplete scanner evidence are advisory.
Broken setup, invalid cases, missing reports, and checkout changes fail the job. See the
job summary and 14-day `skill-quality` artifact; a setup failure isn't behavioral
evidence.

For paid behavioral tests, I've started with
[Podman cases](.apm/skills/podman/evals/evals.json) that describe realistic work and
measurable expectations. I run each request in clean contexts **with and without the
skill** and compare outputs against assertions. **Skill Lift** is the score difference:
positive means the skill helped on those cases; negative means it hurt. Reports also
cover task completion (Effectiveness), accuracy (Correctness), activation
(Discoverability), safety (Security), and tool use (Efficiency).

I look at the actual outputs, not just the score. Assertions that pass equally without
the skill aren't useful measures of its value. See
[Podman evaluation guidance](.apm/skills/podman/EVALS.md) and keep local results in a
sibling workspace outside the skill collection.

The repository-owned [GitHub CLI evaluation suite](.github/evals/gh/EVALS.md)
adds 24 fixture cases and deterministic grading around the unchanged upstream
`gh` skill. Its credential-free replay runs in ordinary CI; native paid runs use
`skill=gh` in the same protected manual workflow. Replay, model-backed results,
and optional live read-only checks are reported separately.

[Benchmark reports](https://github.com/thetechgy/agent-engineering-baseline/actions/workflows/benchmark-skills.yml)
include the underlying evidence. The
[historical Podman charts](https://thetechgy.github.io/agent-engineering-baseline/podman/bcf6348b71caddcb/)
used a different policy, so account for policy and runtime changes when comparing them.

The cases cover **Podman** and **gh**, and automated runs use **Codex**. Harness
checks alone do not establish model performance or portability to Copilot. An agent's result also doesn't prove
infrastructure is working; verify deployment, readiness, exposure, backups, and recovery
in the target environment.

For one private offline view of all skills in validated public evidence, generate
a saved analysis and the [consolidated HTML report](.github/evals/REPORT-EVIDENCE.md#private-offline-html-report).
The report shows native metrics, separate with/without-skill coverage, case
regressions, mandatory gates, static findings and evidence gaps. It includes
unmeasured skills; its deterministic priorities describe investigations without
causal claims or corrective skill edits. It runs locally without inference,
external assets or publication; keep the generated file outside the checkout.
Optional [private analyst attachments](.github/evals/REPORT-EVIDENCE.md#optional-private-analyst-attachments)
add independently revalidated model interpretation and separately attributed
assessments. Historical tooling, record identities, citations and current support
availability must match exactly. Supplied ChatGPT assessments are not authenticated
human approval; the analyst remains `not_quality_qualified` and publication ineligible.

<!-- rumdl-disable MD033 -->
<details>
<summary>Manual behavioral-run setup and operation</summary>

The [benchmark workflow](.github/workflows/benchmark-skills.yml) uses paid OpenAI
API calls, one run at a time. Setup:

1. Create environment `skill-benchmark` with a trusted maintainer reviewer and
   reviewed feature branches allowed alongside main. For one maintainer, leave
   **Prevent self-review** off. The job uses `deployment: false`; avoid incompatible
   deployment protection apps.
2. Add environment secret `OPENAI_API_KEY` with `gpt-5.6-sol` access. Remove any
   repository-level copy to preserve approval gating; re-enter it securely or replace
   it.
3. Initialize an empty `gh-pages` branch from a disposable clone with an orphan
   branch and empty initial commit; push only that branch, never raw results.
4. Set **Pages > Build and deployment > Source** to **GitHub Actions**, keep default
   permissions read-only, and restrict `github-pages` to `main`.

Dispatch **Actions > Benchmark skills > Run workflow** with a reviewed branch and
dataset such as `podman`. `standard` makes one attempt per case per comparison
(20 Podman trials); diagnostic-only `confirmation` makes three (60 trials).
Codex runs in Docker; agent and judge use GPT-5.6 Sol. Smoke tests/judging add calls.
Follow the
[security review requirements](#ci-permissions-credentials-and-dependency-checks)
before approval.

Review summaries and 30-day `skill-benchmark-<run>-<attempt>` artifacts. Costs and
usage are subtotals; missing usage is unknown. Time limits reserve recovery/upload
time. Recovered runs are incomplete and cannot publish; runner loss or cancellation
can prevent recovery. Raw execution directories stay on the runner.

Only successful standard runs on main publish Skill Lift, Effectiveness,
Correctness, and Discoverability to separate skill/policy histories on `gh-pages`;
Security and Efficiency remain in complete reports. Source revisions and dataset
hashes identify points, and Pages deploys the exact history commit.

CI pins the evaluator/runtime and its Codex compatibility patch; policy changes
start a new history series. Recorded versions help track runtime drift: some
container, Node, and verifier dependencies remain upstream-managed.

</details>
<!-- rumdl-enable MD033 -->
