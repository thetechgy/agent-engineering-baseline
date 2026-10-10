# Agent engineering baseline

[![Validate CI](https://github.com/thetechgy/agent-engineering-baseline/actions/workflows/validate.yml/badge.svg?branch=main)](https://github.com/thetechgy/agent-engineering-baseline/actions/workflows/validate.yml)
[![Dependabot](https://img.shields.io/badge/Dependabot-enabled-025e8c?logo=dependabot)](.github/dependabot.yml)
[![Bootstrap shells: PowerShell 5.1 / 7 and Bash](https://img.shields.io/badge/Bootstrap_shells-PowerShell_5.1_%2F_7_%7C_Bash-5391FE?logo=powershell&logoColor=white)](#get-started)
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
the skills: some follow upstream branches and can change when you install. See
[Security and safety](#security-and-safety) before running the scripts.

GitHub Actions checks PRs and pushes to `main`, including scripts, generated files,
skill quality, and installation tests on Windows, Linux, and macOS.
[Validation results](https://github.com/thetechgy/agent-engineering-baseline/actions/workflows/validate.yml)
are public. Paid behavioral evaluations require separate approval. A
[weekly update workflow](.github/workflows/update-baseline.yml) proposes changes through
PRs; nothing auto-merges.

## Get started

The wrappers support Windows x86_64 with PowerShell 5.1 or 7, and Linux/macOS x86_64 or
arm64 with Bash. Install your agent CLI separately. You'll need network access to
releases/dependencies or a mirror. Bash needs `curl`, `tar`, and `sha256sum` (Linux) or
`shasum` (macOS).

**Before installing:** Default bootstrap trusts bundled executables and transitive MCP
servers and refreshes branch-based dependencies, including ones already in the
destination. Review the [security details](#security-and-safety). User scope changes
your shared agent configuration; project scope changes the current project.

From the baseline checkout, on Windows:

```powershell
./scripts/Bootstrap-Baseline.ps1 -WhatIf # preview: local metadata only
./scripts/Bootstrap-Baseline.ps1         # user scope, the default
./scripts/Bootstrap-Baseline.ps1 -Scope Repo
```

On Linux or macOS:

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
wrapper's checkout aren't automatically installed.

Both scopes configure both CLIs. Codex only loads project configuration for trusted
projects. APM writes these files:

| Scope | APM state | Instructions | MCP configuration | Skills |
| --- | --- | --- | --- | --- |
| User | `~/.apm/apm.yml`, `~/.apm/apm.lock.yaml`, `~/.apm/config.json` | `~/.codex/AGENTS.md`, `~/.copilot/AGENTS.md`, `~/.copilot/copilot-instructions.md` | `~/.codex/config.toml`, `~/.copilot/mcp-config.json` | `~/.agents/skills/*` |
| Project | `./apm.yml`, `./apm.lock.yaml`, `./apm_modules/` | `./AGENTS.md`, `./.github/copilot-instructions.md` | `./.codex/config.toml`, `./.github/mcp.json` | `./.agents/skills/*` |

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
| `APM_INSTALL_DIR` | CLI command directory; defaults to `~/.local/bin` on Linux/macOS and `%LOCALAPPDATA%\Programs\apm\bin` on Windows. Windows uses its parent as the installation root. |
| `APM_RELEASE_BASE_URL` | Authoritative HTTPS mirror on all platforms; `file://` mirrors work on Linux/macOS only. Downloads use no credentials and never retry against the public source. |
| `APM_NO_DIRECT_FALLBACK=1` | Requires a configured mirror. |
| `BASELINE_PACKAGE_REF` | Overrides the installed baseline reference. |

`--cli-only` or `-CliOnly` installs just the reviewed APM CLI. Preview (`--dry-run` or
`-WhatIf`) checks local metadata without downloading, executing, or changing anything.

On Linux/macOS, rerun bootstrap after moving the installation tree because its
command link uses an absolute path. After a forced kill, confirm bootstrap has
stopped before removing the diagnostic's `lib/apm/.lock`. Windows uses relative
`bin\apm.cmd`, a named mutex, temporary TLS 1.2, and process/User PATH updates.
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
- **Your installation:** default bootstrap also refreshes **all branch-tracking
  dependencies in the destination**, including unrelated packages. Seven imported skills
  follow upstream branches (`main` or `trunk`). Your destination manifest and lockfile
  govern the result, not this repo's lockfile. Even a fixed baseline commit doesn't
  freeze the skills.

Review the destination's manifest, resolved skills, and source overrides. `--trust-bin`
authorizes bundled executables, including `msgraph`. `--trust-transitive-mcp` trusts MCP
servers across the **whole dependency graph**, not just Microsoft Learn. A compromised
upstream skill could execute code on your next bootstrap.

For fixed skill content, use immutable commit references in the destination manifest and
native APM commands without branch updates. To limit MCP trust, declare the reviewed
server directly and omit `--trust-transitive-mcp`.

### Verified tooling and reviewed refreshes

The wrappers never rely on an existing `apm` from PATH. They use the release in
[`.apm-version`](.apm-version) and ten reviewed SHA-256 hashes in
[`.apm-checksums`](.apm-checksums), covering five archives and their executables.
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
locks. PowerShell Gallery modules have version pins but no native hash pins.

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
astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7
benchmark-action/github-action-benchmark@4322e5726e6334590d251fc4f92bec0efafc45dc
docker/setup-compose-action@54042514f505b273907334ae2b9cdbb9a0213c1a
```

<!-- external-action-requirements:end -->

Missing entries prevent jobs from starting. CI checks that this list matches the
workflows; keep live repository settings synchronized.

Enable **Allow GitHub Actions to create and approve pull requests** for update PRs.
The workflow never submits an approving review. For token-created PRs, a maintainer
with write access must select **Approve workflows to run** after reviewing the
candidate, then require all validation checks before merging. See
[GitHub's token-triggered workflow behavior](https://docs.github.com/en/actions/concepts/security/github_token).

SkillSpector uses its upstream frozen lock; Semgrep and rumdl use reviewed hashed
locks in [.github/requirements](.github/requirements). CI rejects unverified Python
installers and records tool versions and dependency inventories. To refresh with
uv 0.12.17, replace `semgrep` with `rumdl` in both paths for the linter:

```bash
uv pip compile --python-version 3.13 --python-platform x86_64-unknown-linux-gnu \
  .github/requirements/semgrep.in --output-file .github/requirements/semgrep.txt \
  --no-header --no-annotate --generate-hashes
```

Review dependency changes and rerun validation. These locks cover Python artifacts,
not every underlying OS or build tool.

</details>
<!-- rumdl-enable MD033 -->

## Maintaining the baseline

If you're only installing this setup, you can skip this section. To maintain the
collection, change `.apm/` sources or `apm.yml` and regenerate with APM. Don't edit
installed `.agents/skills/`, generated instructions, MCP config, or lock metadata
directly.

Repository review guidance lives in
[`baseline-review.instructions.md`](baseline-review.instructions.md). Pinned APM
0.33.0 discovers this root source during local compilation and generates it into
the shared `AGENTS.md`; the separate Copilot instruction files stay unchanged.
Keep this source outside `.apm/` and leave the manifest's explicit `includes`
unchanged so downstream instructions and packages exclude these review rules.

For skill-specific conventions, see
[PowerShell module engineering](.apm/skills/powershell-module-engineering/SKILL.md),
[Pester 6](.apm/skills/powershell-pester-6/SKILL.md), and
[Podman maintenance](.apm/skills/podman/MAINTENANCE.md).

### Regenerate and validate

To reproduce the reviewed checkout, use the command path reported by bootstrap:

```powershell
$apmCommand = "$env:LOCALAPPDATA\Programs\apm\bin\apm.cmd"
& $apmCommand install --frozen --trust-bin
& $apmCommand compile --target codex,copilot --validate
& $apmCommand compile --target codex,copilot
& $apmCommand audit --ci
& $apmCommand pack --dry-run
```

**Audit caveat:** The pinned APM release can report false drift when you run
`apm audit --ci` without a terminal, even after `install --frozen --trust-bin`.
Its scratch replay doesn't retain launcher trust in that mode. For noninteractive
full validation on Linux/macOS, use `Invoke-Validation.ps1` below; it runs the
same audit in a pseudo-terminal with drift checking enabled. Don't bypass this
with `--no-drift`.

Bash uses the same arguments with `"$apm_command"`, after setting
`apm_command="$HOME/.local/bin/apm"` to the reported path.
For comparison, bootstrap's user-scope sequence is:

```text
apm install --global --target codex,copilot --trust-bin --trust-transitive-mcp <ref>
apm update --global --yes --target codex,copilot
apm compile --global
```

Project scope omits `--global` and compiles with `--target codex,copilot`.

On Linux or macOS, run the [full validation suite](scripts/Invoke-Validation.ps1) with
PowerShell 7 and the required Unix tools and validation dependencies installed:

```powershell
./scripts/Invoke-Validation.ps1
```

From Bash, use `pwsh -NoLogo -NoProfile -File ./scripts/Invoke-Validation.ps1`.
Full validation includes linting, regeneration, audit, packing, MCP contracts,
Graph smoke checks, and diff hygiene.

On Windows, run the Pester and PSScriptAnalyzer suite in PowerShell 5.1 or 7:

```powershell
./scripts/Invoke-Validation.ps1 -Suite Pester
```

For Bash fixtures alone on Linux/macOS, run `./tests/bootstrap.sh`. CI runs
the full suite on Linux, Pester/analyzer on Windows, and Bash fixtures on macOS.

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
