# Agent engineering baseline

[![Validate CI](https://github.com/thetechgy/agent-engineering-baseline/actions/workflows/validate.yml/badge.svg?branch=main)](https://github.com/thetechgy/agent-engineering-baseline/actions/workflows/validate.yml)
[![Dependabot](https://img.shields.io/badge/Dependabot-enabled-025e8c?logo=dependabot)](.github/dependabot.yml)
[![Bootstrap shells: PowerShell 5.1 / 7 and Bash](https://img.shields.io/badge/Bootstrap_shells-PowerShell_5.1_%2F_7_%7C_Bash-5391FE?logo=powershell&logoColor=white)](#get-started)
[![License: MIT](https://img.shields.io/badge/License-MIT-2E7D32)](LICENSE)

## Purpose

This is the AI setup I use with Codex CLI and GitHub Copilot CLI for professional
and personal work, including my homelab. I'm a systems engineer working in
infrastructure, with substantial PowerShell scripting and module development
alongside identity and messaging work. This repository gives me a portable,
version-controlled way to maintain that setup. Others are welcome to use it.

Most guidance is collected or adapted from other sources; I've also started
writing custom skills. **Skills** are task-specific instructions, references,
and examples for the work I do:

- **Automation and module development:** PowerShell modules, Pester 6 tests, and
  clearer scripts.
- **Infrastructure management:** Ansible and Podman.
- **Security and review:** agent safety, CI workflow security, dependency updates,
  accessibility, and Git change preparation.
- **Documentation and API lookup:** Microsoft code references and offline Graph
  API searches.

Browse the [deployed collection](.agents/skills/) or
[locally maintained sources](.apm/skills/) for individual skills. Local adaptations
and custom skills remain my responsibility; imported skills remain upstream-owned.

The [shared instructions](.apm/instructions/personal.instructions.md) require the
agent to inspect the environment, keep changes scoped, preserve unrelated work,
and report validation evidence. Commits, publication, and remote changes need
explicit authorization. Project instructions add requirements for your environment.

## How it works

[Microsoft Agent Package Manager (APM)](https://microsoft.github.io/apm/) installs
this baseline and generates configuration for both agent CLIs.
[apm.yml](apm.yml) selects the skills, instructions, and documentation connection.
Microsoft Learn supplies official documentation through a **Model Context Protocol
(MCP)** connection.
See the [APM command reference](https://microsoft.github.io/apm/reference/) for commands.

GitHub Actions provides **continuous integration (CI)**: automated checks on pull
requests and pushes to `main`, covering scripts, generated configuration, and skill
quality. Installation tests cover Linux, macOS, and Windows.
[Validation reports](https://github.com/thetechgy/agent-engineering-baseline/actions/workflows/validate.yml)
show results. Paid behavioral evaluations run separately with approval.

The [weekly update workflow](.github/workflows/update-baseline.yml), also available
manually, proposes tooling and skill updates through a pull request (PR). Updates
require review and never auto-merge. See [Security and safety](#security-and-safety)
for the separate repository and consumer update boundaries.

## Security and safety

### Prompt injection and operating boundaries

Prompt injection is an explicit design consideration here: files, tool results,
documentation, or evaluation inputs may contain instructions to redirect an agent,
obtain secrets, or trigger unauthorized actions. The
[shared rules](.apm/instructions/personal.instructions.md) treat that content as
untrusted; documentation cannot override repository rules or user authorization.

The implementation limits documentation tools, separates CI permissions, and
keeps publication apart from evaluation. These controls reduce access; they do
not make malicious skills or prompts safe. Review skills and requested actions,
keep secrets out of prompts, and retain sandbox and approval controls.
Instructions alone do not enforce permissions.

### Reviewed upstream changes and installation trust

**This repository does not automatically adopt every upstream skill change.** Its
[lockfile](apm.lock.yaml) records specific revisions, files, launchers, and hashes.
Upstream refreshes and generated changes reach `main` through a review PR so I can
inspect them before accepting them into the recorded baseline. This review boundary
is a deliberate safety choice. Ignored Graph indexes and binaries retain lockfile
and audit checks.

**Default bootstrap is different:** it installs into your destination, then
refreshes **all dependencies that follow a branch**, including unrelated packages.
The manifest follows upstream `main` for six imported skills. The destination's
manifest and lockfile govern that install, not this checkout's lockfile. Choosing
a fixed baseline commit alone does not freeze upstream skills.

Review the destination manifest, resolved skills, and source overrides. Bootstrap's
`--trust-bin` authorizes bundled executables, including `msgraph`;
`--trust-transitive-mcp` trusts MCP servers across **the entire dependency graph**,
not just Microsoft Learn. A compromised upstream skill can lead to code execution
on the next bootstrap.

For fixed skill content, use immutable commit references in the destination manifest
and native APM commands without branch updates. To narrow MCP trust, declare the
reviewed server directly in that manifest and omit `--trust-transitive-mcp`.

### Verified tooling and reviewed refreshes

The wrappers use the release in [.apm-version](.apm-version) and ten reviewed
SHA-256 hashes in [.apm-checksums](.apm-checksums), covering five archives and their
executables. Downloads use no credentials. Bootstrap verifies the complete bundle,
rejects unsafe/incomplete layouts, checks its version, and invokes the reviewed
executable by absolute path. Hashes verify integrity, not safety.

The previous installation stays usable until activation; cleanup warns on failure.
Ownership and path checks protect unrelated files, unmarked
bundles, links, and Windows reparse points. Concurrent runs against the same root
fail immediately; another process able to rewrite that root is outside these protections.

Refreshes use the previously reviewed CLI. Candidate archives must match upstream
checksums and pass layout checks before new hashes are calculated, **without
executing the candidate CLI**. A patch restricted to approved generated paths is
captured before validation. A separate write-capable job applies it and opens or
updates this repository's Actions-bot PR without executing changed content.
Ordinary PR validation first executes the candidate CLI.

Review the release, publication date, upstream release page, all ten hashes,
dependency revisions, generated changes, and CI results before merging.

### Documentation access and privacy

The [Microsoft Learn MCP server](https://learn.microsoft.com/en-us/training/support/mcp)
at `https://learn.microsoft.com/api/mcp` is free and unauthenticated; model usage
follows your agent plan and billing. Both CLIs are limited to
`microsoft_docs_search`, `microsoft_docs_fetch`, and `microsoft_code_sample_search`.
Endpoint or tool changes require manifest review; the list does not auto-expand.

Queries and fetch URLs leave the machine. Send only public API names and minimal
nonsensitive context, never secrets or private source. The lockfile records the
connection and allowed tools, not the remote service or its content. Treat results
as untrusted reference material.

Match documentation and samples to the installed SDK/library version and hosting
model. If Learn is unavailable, use an already authorized documentation path or
report the limitation. Installing or executing fallback tools, including
`npx @microsoft/learn-cli` or global npm installs, requires explicit authorization.
The upstream MIT notice remains in shared instructions and generated outputs.

### CI permissions, credentials, and dependency checks

Validation jobs have read-only repository access and retain no checkout credentials.
Actions use fixed commit identifiers (SHAs); Python dependencies use reviewed
hashes or frozen locks. PowerShell Gallery modules remain version-pinned without
native hash pins.

Paid evaluation requires approval through `skill-benchmark`; only the live step
receives the inference key. Separate history/Pages jobs receive no inference
credential and execute no skills; history accepts only approved numeric metrics.
Reports and temporary tools stay outside the checkout, including ignored paths.
Never put reports or `BENCHMARK.md` in either APM-managed skill collection.

Codex can access its API key inside the evaluation container. Before approval,
review the revision, workflow, skill, cases, and inputs. Uploads exclude credentials
and unexpected files; redaction is best effort and cannot prevent encoded secret
disclosure. Treat inputs and outputs as untrusted.

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

## Get started

Supported releases are Linux/macOS on x86_64 or arm64 and Windows x86_64.
Use Bash on Linux/macOS, or Windows PowerShell 5.1 or PowerShell 7 on Windows.
Configure your agent CLI separately. Have a reviewed checkout and network access
to releases/dependencies or mirrors. Bash needs `curl`, `tar`, and `sha256sum`
(Linux) or `shasum` (macOS).

**Before installing:** read [Security and safety](#security-and-safety), especially
the destination-wide branch updates and trust permissions. Default user scope
changes shared user configuration; project scope changes the project's APM files
and agent configuration.

From the baseline checkout, Windows:

```powershell
./scripts/Bootstrap-Baseline.ps1 -WhatIf # preview: local metadata only
./scripts/Bootstrap-Baseline.ps1         # user scope, the default
./scripts/Bootstrap-Baseline.ps1 -Scope Repo
```

Linux and macOS:

```sh
./scripts/bootstrap.sh --dry-run  # preview: local metadata only
./scripts/bootstrap.sh            # user scope, the default
./scripts/bootstrap.sh --repo
```

Project scope uses the **current working directory**. To install into another
project, stay there and invoke the wrapper from a separate checkout:

```powershell
Set-Location C:\work\target-project
& C:\work\agent-engineering-baseline\scripts\Bootstrap-Baseline.ps1 -Scope Repo
```

```sh
cd /path/to/target-project
/path/to/agent-engineering-baseline/scripts/bootstrap.sh --repo
```

The wrapper uses its checkout's CLI pins but installs
`https://github.com/thetechgy/agent-engineering-baseline.git#main` by default.
Set `BASELINE_PACKAGE_REF` for another reviewed source; running a local wrapper
does not automatically install local edits.

Both scopes configure both CLIs. Codex loads project configuration only for
trusted projects. APM writes:

| Scope | APM state | Instructions | MCP configuration | Skills |
| --- | --- | --- | --- | --- |
| User | `~/.apm/apm.yml`, `~/.apm/apm.lock.yaml`, `~/.apm/config.json` | `~/.codex/AGENTS.md`, `~/.copilot/AGENTS.md`, `~/.copilot/copilot-instructions.md` | `~/.codex/config.toml`, `~/.copilot/mcp-config.json` | `~/.agents/skills/*` |
| Project | `./apm.yml`, `./apm.lock.yaml`, `./apm_modules/` | `./AGENTS.md`, `./.github/copilot-instructions.md` | `./.codex/config.toml`, `./.github/mcp.json` | `./.agents/skills/*` |

### Example: maintain a PowerShell module

Give your agent a concrete maintenance request:

> This module accepts an empty server name and fails later with an unclear error.
> Inspect the module, project instructions, and supported PowerShell versions.
> On a dedicated branch, fix parameter validation without changing valid calls or
> unrelated work. Use the PowerShell module and Pester 6 guidance, test empty input
> and valid calls, and run the relevant checks. Match any Microsoft API guidance to
> the installed library and hosting model. Report the changes, test evidence, and
> checks unavailable here. Do not commit or publish.

Verify the actual command and supported runtimes, or the deployed infrastructure
and recovery paths. Your project owns validation and deployment approval.

### Installation settings and recovery

| Variable | Effect |
| --- | --- |
| `APM_INSTALL_DIR` | CLI command directory; defaults to `~/.local/bin` on Linux/macOS and `%LOCALAPPDATA%\Programs\apm\bin` on Windows. Windows uses its parent as the installation root. |
| `APM_RELEASE_BASE_URL` | Authoritative HTTPS or file mirror; downloads use no credentials and never retry against the public source. |
| `APM_NO_DIRECT_FALLBACK=1` | Requires a configured mirror. |
| `BASELINE_PACKAGE_REF` | Overrides the installed baseline reference. |

`--cli-only` or `-CliOnly` installs the reviewed CLI without deploying the baseline.
Preview downloads and executes nothing and changes no files or PATH.

On Linux/macOS, rerun bootstrap after moving the installation tree because its
command link uses an absolute path. After a forced kill, confirm bootstrap has
stopped before removing the diagnostic's `lib/apm/.lock`. Windows uses relative
`bin\apm.cmd`, a named mutex, temporary TLS 1.2, and process/User PATH updates.
User PATH failure is a warning; both wrappers warn about other commands masking APM.

Bootstrap sets `VERSION=<pin>` to suppress release lookup. Ignore `apm self-update`:
it replaces the reviewed CLI. Unscoped-instruction and this configuration warning
are expected:

```text
[!] MCP dependency 'microsoft-learn': unknown key(s) preserved in extra: enabled_tools
```

See the [PowerShell](scripts/Bootstrap-Baseline.ps1) and
[Bash](scripts/bootstrap.sh) wrappers for diagnostics.

## Maintaining the baseline

Edit `.apm/` sources or `apm.yml`, then regenerate through APM. Never hand-edit
installed `.agents/skills/`, generated instructions, MCP configuration, or lock
metadata. Consult the [PowerShell module](.apm/skills/powershell-module-engineering/SKILL.md),
[Pester 6](.apm/skills/powershell-pester-6/SKILL.md), and
[Podman maintenance](.apm/skills/podman/MAINTENANCE.md) guidance for focused changes.

### Regenerate and validate

To reproduce this checkout's recorded setup, use the command path printed by bootstrap:

```powershell
$apmCommand = "$env:LOCALAPPDATA\Programs\apm\bin\apm.cmd"
& $apmCommand install --frozen --trust-bin
& $apmCommand compile --target codex,copilot --validate
& $apmCommand compile --target codex,copilot
& $apmCommand audit --ci
& $apmCommand pack --dry-run
```

Bash uses the same arguments with `"$apm_command"`, after setting
`apm_command="$HOME/.local/bin/apm"` to the reported path.
For comparison, bootstrap's user-scope sequence is:

```text
apm install --global --target codex,copilot --trust-bin --trust-transitive-mcp <ref>
apm update --global --yes --target codex,copilot
apm compile --global
```

Project scope omits `--global` and compiles with `--target codex,copilot`.

Run the [complete local checks](scripts/Invoke-Validation.ps1) from PowerShell:

```powershell
./scripts/Invoke-Validation.ps1
```

From Bash: `pwsh -NoLogo -NoProfile -File ./scripts/Invoke-Validation.ps1`.
Use `-Suite Pester` for Pester/analyzer or `./tests/bootstrap.sh` for Bash fixtures.
Full validation includes linting, regeneration, audit, packing, MCP contracts,
Graph smoke checks, and diff hygiene. CI also covers Windows PowerShell 5.1 and 7.

### Evaluate authored skills

Evaluation checks skill content and asks whether guidance improves responses to
real work. This repository uses
[pinned NVIDIA SkillEvaluator v0.3.0](https://github.com/NVIDIA/SkillEvaluator/blob/ac0a04905100acdafc6c95829311a9739c340ff6/README.md)
as a read-only consumer of `.apm/skills/`, separate from installation.

Automated **Skill quality** checks require security scanners and valid case data;
LLM checks and Tier 2 are disabled. Ordinary findings and explicitly reported
incomplete scanner evidence are advisory. Broken setup/runtime, invalid datasets,
missing or malformed reports, and checkout changes fail the job. Review summaries
and the 14-day `skill-quality` artifact; a setup failure supplies no behavioral evidence.

Paid comparisons use [authored Podman cases](.apm/skills/podman/evals/evals.json):
realistic requests, expected behavior, concrete assertions, and representative
inputs. Run the same request in clean contexts **with and without the skill**,
then grade assertions using output evidence. **Skill Lift** is the overall score
difference: positive means improvement over the baseline; negative means worse
results. Reports also cover task completion (Effectiveness), answer accuracy
(Correctness), skill activation (Discoverability), safety (Security), and efficient
tool/skill use (Efficiency).

Read scores alongside outputs to identify useful guidance and regressions without
guaranteeing correctness. Refine cases after mistakes and remove assertions that
pass equally without the skill. Follow the
[Podman evaluation guidance](.apm/skills/podman/EVALS.md); store local results in a
sibling workspace outside the skill collection.

[Behavioral runs and reports](https://github.com/thetechgy/agent-engineering-baseline/actions/workflows/benchmark-skills.yml)
provide evidence and provenance. The
[historical Podman charts](https://thetechgy.github.io/agent-engineering-baseline/podman/bcf6348b71caddcb/)
use a different policy from this checkout; consider recorded policy and runtime
changes when comparing results.

Current cases cover **Podman**, and automated behavioral runs use **Codex**.
Broader skills and Copilot behavior need separate evidence; portability checks
should compare both CLIs. A successful model response does not prove infrastructure
correctness: verify deployment, readiness, exposure, backup, and recovery in the
target environment.

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
   repository-level copy to preserve approval gating; re-enter it securely or replace it.
3. Initialize an empty `gh-pages` branch from a disposable clone with an orphan
   branch and empty initial commit; push only that branch, never raw results.
4. Set **Pages > Build and deployment > Source** to **GitHub Actions**, keep default
   permissions read-only, and restrict `github-pages` to `main`.

Dispatch **Actions > Benchmark skills > Run workflow** with a reviewed branch and
dataset such as `podman`. `standard` makes one attempt per case per comparison
(20 Podman trials); diagnostic-only `confirmation` makes three (60 trials).
Codex runs in Docker; agent and judge use GPT-5.6 Sol. Smoke tests/judging add calls.
Follow the [security review requirements](#ci-permissions-credentials-and-dependency-checks)
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
