# Agent engineering baseline

This MIT-licensed repository is a shared, project-agnostic configuration for
[Microsoft Agent Package Manager (APM)](https://microsoft.github.io/apm/).
It deploys shared instructions and skills to Codex CLI and GitHub Copilot CLI
through APM's native install, update, and compile commands.

The bootstrap has one deliberately custom security boundary: acquiring and
promoting a trusted APM CLI. Package installation, executable trust, dependency
resolution, updates, compilation, audit, and packing remain native APM
operations.

## Pinning and review boundary

The repository uses APM's native dependency model, like a manifest and lockfile:

- `apm.yml` declares branch-ref dependencies and reviewed local `.apm/`
  content.
- `apm.lock.yaml` records this checkout's resolved dependency snapshot: exact
  commits, deployed files, platform launchers, and content hashes.
- `.apm-version` pins the complete APM release version.
- `.apm-checksums` contains exactly ten reviewed SHA-256 digests: the five
  supported release archives and the executable inside each archive.
- Readable compiled outputs are committed review artifacts and CI requires a
  clean mechanical regeneration. The only ignored APM outputs are the six large
  `msgraph` indexes and six platform binaries named exactly in `.gitignore`;
  the lockfile and `apm audit --ci` retain their integrity contract.

The bootstrap verifies the downloaded CLI archive and executable against the
committed hashes. This repository's lockfile and generated outputs describe its
reviewed dependency snapshot; native frozen installation and audit check that
snapshot in this checkout. Hashes establish integrity against the recorded
values, not whether the content is benign.

### What the review boundary does and does not cover

The committed pins govern exactly one thing: which APM CLI executes on the
consumer's machine. They do not pin skill content.

- `apm.yml` tracks five third-party skills at their upstream `main` branch.
- Bootstrap runs native `apm install --trust-bin --trust-transitive-mcp` and
  then `apm update --yes`, so every run resolves those branch refs to their
  *current* upstream commits and trusts any launcher binaries and transitive
  MCP servers they declare. The `msgraph` skill, for example, ships a prebuilt
  launcher that `--trust-bin` authorizes.
- A consumer installation uses native APM resolution and its own destination
  lockfile. This repository's `apm.lock.yaml` is a reviewed snapshot of one
  checkout; it is never what a consumer installs from. Installing a fixed
  baseline commit therefore does not force transitive dependencies to match
  this lockfile.

Treat an upstream skill compromise as code execution on every consumer at its
next bootstrap. Review the destination's resolved content and lockfile when
assessing what was actually deployed. If deterministic skill content is
required, pin the dependencies to commits in the destination manifest and use
native APM directly instead of the wrappers.

A CLI update first enters a review-only pull request as hashes and generated
output. The candidate CLI is not executed by the privileged update workflow.

## Local content

`.apm/` contains the reviewed local sources:

- `instructions/personal.instructions.md` provides shared engineering
  boundaries.
- `skills/a11y`, `agent-safety`, `ansible`, `podman`, and
  `powershell-module-engineering` are maintained local adaptations.
- `skills/powershell-pester-6` is locally authored and remains the selected
  source of truth.

Installed `.agents/skills/` content is generated; edit its source or dependency
and regenerate rather than editing installed output directly.

## Microsoft Learn documentation

`apm.yml` declares the
[official Microsoft Learn MCP server](https://learn.microsoft.com/en-us/training/support/mcp)
as `microsoft-learn` using APM's native named-endpoint configuration
(`registry: false`). It provides online Microsoft documentation and code
samples for GitHub Copilot CLI and Codex CLI. The existing `msgraph` skill
remains available for offline Graph API lookups.

The server uses Streamable HTTP at `https://learn.microsoft.com/api/mcp`,
without API keys or authentication. The endpoint is declared directly in the
manifest; future endpoint changes require a reviewed manifest change. Its tool
allowlist contains only:

- `microsoft_docs_search`
- `microsoft_docs_fetch`
- `microsoft_code_sample_search`

The manifest explicitly supplies Copilot's `tools` and Codex's `enabled_tools`
using APM's native passthrough support and a YAML alias to keep both lists
identical. The pinned APM does not derive `enabled_tools` from `tools`, so
the passthrough is required; APM reports it once per dependency resolution as
`[!] MCP dependency 'microsoft-learn': unknown key(s) preserved in extra:
enabled_tools`. That warning is expected native output. New tools require a
reviewed manifest change; the list does not auto-expand.

APM generates `.github/mcp.json` and `.codex/config.toml` for repository
installs, or the user-scoped Copilot and Codex MCP configs for global installs.
These repository configs and the lockfile's MCP metadata are review artifacts;
regenerate them with APM rather than editing them directly. Codex loads
project-scoped configuration only for trusted projects.

Tool queries and fetch URLs leave the machine for Microsoft's service. Do not
include secrets or private repository content. The service requires network
access, and neither its returned content nor its implementation is pinned by
the lockfile: it records the named endpoint, allowlists, and target ownership,
while the generated CLI configs contain the same endpoint. Treat
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

Linux and macOS promotion holds an atomic directory lock at
`lib/.apm-install.lock` beside the bundle, waiting up to two minutes for another
installer. Normal exit and handled signals release the lock. If a process is
forcibly terminated, confirm that no installer is running and inspect the
release and rollback paths before manually removing its stale lock directory.
Both wrappers verify the executable at its promoted release path before
publishing the command link.

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
configuration. Every bootstrap run therefore refreshes the baseline deployment
from its configured ref (`main` by default) and resolves upstream dependencies
natively. On a fresh machine, install resolves current branch refs; update
refreshes them again if they have advanced.

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
auto-detection cannot redirect the baseline; global install persists
`codex,copilot` in `~/.apm/apm.yml`, so `apm compile --global` writes only
those two root contexts rather than every harness APM supports. Repository
mode intentionally updates that project's manifest, lockfile, package cache,
and compiled outputs. The update step refreshes every branch-ref dependency
declared in the destination manifest, not only the baseline; review that
manifest before running bootstrap if it declares other dependencies.

Native output written by each mode:

| Mode | Manifest, lockfile, config | Root contexts | MCP configuration | Skills |
|---|---|---|---|---|
| Global | `~/.apm/apm.yml`, `~/.apm/apm.lock.yaml`, `~/.apm/config.json` | `~/.codex/AGENTS.md`, `~/.copilot/AGENTS.md`, `~/.copilot/copilot-instructions.md` | `~/.codex/config.toml`, `~/.copilot/mcp-config.json` | `~/.agents/skills/*` |
| Repository | `./apm.yml`, `./apm.lock.yaml`, `./apm_modules/` | `./AGENTS.md`, `./.github/copilot-instructions.md` | `./.codex/config.toml`, `./.github/mcp.json` | `./.agents/skills/*` |

The two Copilot context files carry the same instruction body under different
generated headers; that duplication is native Copilot target behavior. Expected
native diagnostics during a bootstrap are the `enabled_tools` passthrough
warning described above, the unscoped-instruction warning for the universal
instruction, and APM's own `A new version of APM is available … Run apm
self-update` notice. Ignore the self-update notice: this repository pins the
CLI, and `apm self-update` would replace the reviewed executable with an
unreviewed one.

## Repository validation

Use the reviewed absolute APM executable that bootstrap reported as
`done; reviewed CLI: <path>` and reproduce the deployment:

```sh
APM="$HOME/.local/lib/apm/apm"   # the path bootstrap printed
"$APM" install --frozen --trust-bin
"$APM" compile --target codex,copilot --validate
"$APM" compile --target codex,copilot
"$APM" audit --ci
"$APM" pack --dry-run
```

Run the complete local gate, which includes the Bash fixture suite:

```sh
pwsh -NoLogo -NoProfile -File ./scripts/Invoke-Validation.ps1
```

For the fast loop, `./tests/bootstrap.sh` runs the Bash fixtures alone and
`./scripts/Invoke-Validation.ps1 -Suite Pester` runs Pester and the analyzer.

The gate covers Pester (including both CLI MCP allowlists and endpoint checks),
PSScriptAnalyzer, Bash fixture archives, ShellCheck,
Markdown linting, frozen trusted-bin installation, compile validation and clean
regeneration, audit, pack dry-run, an offline `msgraph openapi-search` launcher
and index smoke test, and `git diff --check`. CI adds a
macOS Bash lane and Windows PowerShell 5.1 fixture execution.

The pinned APM CLI does not expose `--trust-bin` on `audit` and skips bin
deployment in its non-TTY scratch replay. Validation therefore runs the unchanged
`apm audit --ci` command in a local pseudo-terminal so its full drift check
includes the launcher set installed with `--trust-bin`; it does not use
`--no-drift`.

## Skill evaluation

[NVIDIA SkillEvaluator](https://github.com/NVIDIA/SkillEvaluator/tree/ac0a04905100acdafc6c95829311a9739c340ff6)
is a separate, read-only consumer of authored `.apm/skills/` content. APM remains
the sole producer of `.agents/skills/` and the deployment authority for Codex
and GitHub Copilot. Evaluation is not an APM dependency or installation step.

The independent **Skill quality** job in `Validate` runs deterministic Tier 1
checks with the public/external profile and all required security scanners.
It uses pinned SkillEvaluator v0.3.0 and uv-managed Python 3.13, disables LLM
checks and Tier 2, and invokes native strict validation for every authored
`evals/evals.json`. Deliberately flawed evaluation fixtures remain test inputs
under the evaluator's native scan exclusions.
Before evaluation, the authored input tree must contain only real directories
and regular files; symlinks and special files fail the preflight.

Skill findings and incomplete baseline evidence are initially **advisory**.
Broken setup/runtime, missing or malformed reports, invalid eval datasets, and
checkout mutations fail the job. Review the job summary and the `skill-quality`
artifact (14 days) for JSON, Markdown, HTML, and strict dataset reports before
changing existing skill content to address the baseline.

In **Settings > Actions > General > Actions permissions**, retain the selected
actions policy and full-SHA pinning requirement. Allow GitHub-owned actions and
these exact reviewed external refs:

<!-- external-action-requirements:start -->

```text
astral-sh/setup-uv@bec219d24cd3e171d82865faccec33120bb574f4
benchmark-action/github-action-benchmark@4322e5726e6334590d251fc4f92bec0efafc45dc
docker/setup-compose-action@54042514f505b273907334ae2b9cdbb9a0213c1a
```

<!-- external-action-requirements:end -->

`astral-sh/setup-uv` is required for validation and benchmarking;
`benchmark-action/github-action-benchmark` publishes durable history;
`docker/setup-compose-action` installs the benchmark's pinned Compose runtime.
Without these entries, GitHub rejects the workflow before starting jobs. No
broader third-party action access is needed. CI checks this list against every
workflow's external action references; live repository settings must also match.

### Manual behavioral benchmarks

In **Actions > Benchmark skills > Run workflow**, select a branch, a local
skill name with an authored dataset (initially `podman`), and a mode:

| Mode | Attempts per case in each arm | Podman task trials | Durable history |
| --- | --- | --- | --- |
| `standard` | 1 | 20 | Successful main dispatches only |
| `confirmation` | 3 | 60 | Diagnostic only |

Both modes retain the without-skill baseline and use native Codex evaluation
in Docker, with concurrency 2, a 600-second per-trial agent timeout, and a
three-hour workflow-job limit. Codex and the evaluator/judge explicitly use
**OpenAI GPT-5.6 Sol**. Native runtime smoke tests and judging add calls beyond
the task-trial counts. Runs consume OpenAI API usage; neither mode runs
automatically on pushes, PRs, or a schedule. Only one benchmark workflow runs
at a time.

The Evaluate job waits for approval through the protected `skill-benchmark`
environment. Review the dispatched commit SHA, workflow, skill, dataset, and
fixtures before approving. Reviewed feature branches are supported. The job
checks out that exact SHA and validates inputs before using the credential.
Environment approval does not make malicious prompts safe: native Codex can
access its API credential inside the container.

Both modes and feature-branch runs produce job summaries and native collected
results as `skill-benchmark-<run>-<attempt>` artifacts, retained for 30 days.
Native token counts and any available `cost_usd` appear in the summary. These
are reported subtotals, may include Harbor's cost estimates, and are not a
complete API bill; missing usage remains unknown. Publication stages only known
native reports, dataset snapshots, provenance, and collected diagnostics, using
upstream redaction helpers. Transient Harbor execution directories, hidden
files, credentials, links, and unexpected files are excluded. Redaction is
best-effort and cannot prevent deliberate encoded secret disclosure; review is
the trust boundary. Treat downloaded prompts and agent outputs as untrusted.

Evaluation is capped at 140 minutes and shortens when setup consumes part of
the 160-minute window established by the job's first step. This reserves about
20 minutes of the 180-minute job for recovery, redaction, and upload. Native
Harbor retention keeps completed trials available to the native collector
after interruption;
raw execution directories stay on the runner. Recovered runs are explicitly
incomplete and cannot publish history. Recovery and upload require a live
runner; runner loss or forced cancellation can prevent them.

Successful **standard** runs explicitly dispatched against `main` additionally
append Skill Lift, Effectiveness, Correctness, and Discoverability to
[github-action-benchmark](https://github.com/benchmark-action/github-action-benchmark/tree/4322e5726e6334590d251fc4f92bec0efafc45dc)
history on `gh-pages`. Security and efficiency remain in complete results.
Each skill and benchmark policy has a separate series; dataset digests and
source revisions identify each point. The Pages deployment summary links the
series at `<Pages URL>/<skill>/<policy-id>/`. Confirmation runs never publish.

Evaluation has read-only repository permission; only its live step receives
the OpenAI secret. A separate publisher receives only allowlisted numeric
metrics and has repository-write permission. A third job deploys the exact
published history commit through native Pages Actions. Neither publishing job
receives the inference credential or executes the evaluator, Codex, or skills.

All outputs live under the runner's temporary directory, and CI explicitly
requires an unchanged checkout, including ignored files. Ignore rules for
accidental `evals/results/` directories are defense in depth, not isolation.
Do not save reports or `BENCHMARK.md` into either APM-managed skill tree.

### One-time benchmark setup

1. In **Settings > Environments**, create `skill-benchmark` with a required
   trusted maintainer reviewer. Allow reviewed feature branches as well as main;
   do not restrict this environment to main. Leave **Prevent self-review** off
   for a single-maintainer repository. Independent approval can be enabled when
   additional trusted maintainers are available. The workflow sets
   `deployment: false`, so required-reviewer and secret gating apply without
   creating deployment records; do not add incompatible custom deployment
   protection apps.
2. Add **environment secret** `OPENAI_API_KEY` to `skill-benchmark`, with access
   to `gpt-5.6-sol`. Remove any repository-level secret with that name so another
   workflow cannot access that copy without environment approval. GitHub cannot
   reveal an existing secret for migration: re-enter it from your secure source
   or create a replacement. Only approve reviewed workflow and skill revisions.
3. Initialize an empty `gh-pages` branch once. From a disposable clone, create
   an orphan branch, remove its inherited tracked files, make an empty initial
   commit, and push only that branch. No raw results belong on this branch.
4. In **Settings > Pages > Build and deployment > Source**, select
   **GitHub Actions**. Keep default Actions token permissions read-only; the
   workflow requests its required publishing permissions explicitly.
5. In **Settings > Environments > github-pages**, restrict deployment branches
   to `main`. The workflow dispatch ref remains main even though the static
   content is checked out at the published history commit.

The reviewed tool pins and the small Codex compatibility patch are CI-owned
under `.github/`. The patch passes Codex 0.155.1 through Harbor's native version
argument only for Docker Codex execution; tests reject patch drift. Evaluator
Python is pinned to 3.13 and its full resolved version is recorded. Harbor's
native container base, Node patch version, and verifier runtime dependencies
remain upstream-managed; consider runtime drift when comparing results.
No custom grading or model fallback policy is introduced. Copilot deployment
compatibility continues through APM; live behavioral evaluation uses Codex.

SkillSpector reuses its reviewed upstream frozen lock in a separate environment;
Semgrep uses uv's isolated tool installation with CI-owned version constraints.
Artifacts record scanner versions and resolved Python dependency inventories.
To deliberately update Semgrep's constraints with uv 0.12.17, run:

```bash
uv pip compile --python-version 3.13 --python-platform x86_64-unknown-linux-gnu \
  .github/requirements/semgrep.in --output-file .github/requirements/semgrep.txt \
  --no-header --no-annotate
```

Review the resulting dependency changes and rerun deterministic validation.
These are Python runtime dependency constraints, not recursive OS/build-tool
locks; no automatic dependency update mechanism is added.

Tier 2 remains available through upstream's on-demand commands. Recurring
overlap analysis, Copilot adapters, PR comments, SARIF, and cost charts are
outside this initial integration.

## Scheduled reviewed updates

`.github/workflows/update-baseline.yml` runs weekly and on manual dispatch. Its
generate job checks out `main`, acquires the currently reviewed CLI, uses a
token only for the isolated latest-release metadata query, and downloads all
five candidate archives without credentials. Each archive must match its
upstream `.sha256` sidecar before the job inspects the archive layout and
computes the ten replacement hashes without executing candidate code.

The previously reviewed CLI performs dependency update, frozen trusted-bin
installation, and compilation. The job then captures the review patch and
rejects any change outside the regeneration allowlist (`.apm-version`,
`.apm-checksums`, `apm.lock.yaml`, the compiled root contexts and MCP
configs, and `.agents/skills/`). Only after the patch exists does the job run
validation and audit, so branch-ref dependency content that is executed
during validation can no longer influence what gets published. A separate
write-capable job checks out `main`, applies the patch only after
`git apply --check`, and opens or updates a pull request without executing
patched content. That job selects only an open pull request whose head branch
lives in this repository and was authored by the Actions bot, so a fork branch
using the automation branch name cannot receive the trusted update body.
Ordinary unprivileged pull-request validation is the first place the
candidate CLI runs after its hashes are part of the reviewed patch.

Update pull requests never auto-merge. The pull request body names the
candidate release, its upstream publication date, and the release page.
Review the upstream release, all ten digests, resolved dependency commits,
generated outputs, and CI results.

In repository **Settings > Actions > General**, enable **Allow GitHub Actions
to create and approve pull requests**. Keep default workflow permissions
read-only; the publish job requests only the write permissions it needs.
The workflow creates review requests and does not submit approving reviews.

Pull requests created or updated with `GITHUB_TOKEN` require a maintainer with
write access to select **Approve workflows to run** in the pull request before
candidate validation starts. Review the candidate changes before approving
execution, then require all validation checks to pass before merging. See
[GitHub's token-triggered workflow behavior](https://docs.github.com/en/actions/concepts/security/github_token).
