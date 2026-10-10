# GitHub CLI skill evaluation runbook

This repository owns the evaluation overlay, not the deployed `gh` skill.
The suite has 24 cases across `gh-001` through `gh-014`, with suffixed variants.
The [dataset](evals/evals.json) records prompts, activation expectations,
permitted mutations, required observations, task artifacts, failure gates,
and evidence classifications. [Provenance](PROVENANCE.md) is outside the
agent-visible input tree.

## Offline checks

From the repository root, with Python and PyYAML available:

```bash
python3 .github/scripts/gh_evaluations.py validate gh
python3 .github/scripts/gh_evaluations.py replay gh
python3 .github/scripts/gh_evaluations.py replay gh --case gh-002
python3 -m unittest discover -s .github/tests -v
```

Replay invokes the actual fixture executable in fresh disposable Git repositories
with separate configuration and audit state. It exercises good commands and
injected errors; activation evidence is synthetic. Replay is harness regression
evidence, not fresh model performance or live GitHub validation. Ordinary CI runs
replay, dataset validation, and native integration tests without model credentials.
The full test suite needs the existing pinned SkillEvaluator environment.

## Native model runs

Use the existing protected **Benchmark skills** manual workflow with `skill=gh`.
No workflow dispatch is necessary for offline work. The workflow keeps its existing
runtime/model pins, deadline, recovery, artifact, and history policies. Podman's
selection and default grading remain unchanged.

A prepared local environment can run the same native evaluator through:

```bash
python3 .github/scripts/gh_evaluations.py benchmark gh --mode standard --output /tmp/gh-standard
python3 .github/scripts/gh_evaluations.py benchmark gh --mode confirmation --output /tmp/gh-confirmation
python3 .github/scripts/gh_evaluations.py benchmark gh --case gh-003 --output /tmp/gh-case
python3 .github/scripts/gh_evaluations.py benchmark gh --smoke --output /tmp/gh-smoke
```

Use the evaluator's Python 3.13 interpreter and place its executables on `PATH`.
The exact dependencies and Codex patch come from
[setup-skillevaluator.sh](../../scripts/setup-skillevaluator.sh). Docker Compose
5.0.2, Harbor 0.13.2, SkillEvaluator 0.3.0 at `ac0a049`, Codex 0.155.1, and
`gpt-5.6-sol` remain pinned. Do not substitute a newer host Codex or Podman.
The runner refuses missing runtime tools and credentials. It does not install them.

Standard runs use one attempt per case per arm (48 task trials); confirmation
runs use three (144 task trials). The bounded smoke selects `gh-002`, `gh-005`,
`gh-008`, and `gh-010`, one attempt per arm (eight task trials). Selected cases,
smoke runs, confirmation, and interrupted results cannot publish standard history.
Local execution never publishes history. Provider/runtime preflight and judging
may incur additional work beyond the stated task-trial counts.

Staging checks the APM lockfile owner, pinned revision, deployed file hashes,
regular files, and destination before copying. It copies the unchanged skill into
a new bundle outside the checkout, then overlays evaluation files. It also stages
the lock-verified `github-actions-hardening` skill in both comparison arms. Native
`group` skill discovery removes only `gh` from the baseline; prompts, fixtures,
and baseline instructions remain identical. No skill text is pasted into prompts.

## Grading and diagnostics

`default_plus_custom` retains native scores and adds `gh_evidence`, `gh_activation`,
`gh_commands`, `gh_task`, `gh_recovery`, `gh_authorization`, `gh_efficiency`, and
`gh_gate`. With-skill trials must pass every deterministic dimension. Baseline
failures remain valid comparison evidence. Native aggregate scores cannot
outvote this gate. Publication also requires complete authored case/attempt
coverage in both arms and the existing complete-native-result checks.

Every command records its arguments, explicit repository, output, exit code,
and modeled mutation. Receipts in completed tool observations bind the audit to
the normalized native trajectory. The verifier replays state transitions against
its private fixture copy, checks fixture hashes, and reads `output/result.json`.
Missing traces, altered fixture bytes, log deletion/truncation, unsupported
commands, implicit REST POST, duplicate writes, wrong targets, incomplete
pagination, stale-head success, and exposed synthetic secret sentinels fail.
Expected answers, known-good replay traces, and grading rules are not staged as
agent inputs. Native activation checks, not self-reported activation, score routing.

The executable models the documented command subset in each case. Unsupported
commands fail explicitly. It accepts long flags, the relevant short aliases,
field ordering, GraphQL whitespace, and `--jq` filtering using the installed `jq`.
Help responses are captured from `gh` 2.102.0. This is not a complete GitHub CLI
emulator: alternate API strategies, templates, arbitrary GraphQL, and manual
cursor loops outside the modeled routes fail. Treat such failures as coverage
limitations to review before interpreting a benchmark score.

Pending watches require a completed `timeout` wrapper bounded to 30 seconds and
return a modeled timeout; they do not wait on real CI.
Missing CLI, authentication, permission, network, rate-limit, unavailable-resource,
and partial upload cases model failures. They do not qualify real executables,
credential handling, transport behavior, upload bytes, or GitHub permission models.
The same-container integrity checks detect tested tampering; they are not an
isolation boundary against an adversarial root process forging all evidence.
The fixture never forwards requests to GitHub. Agents must obey the no-network
fixture instructions; network isolation itself remains the native runtime's concern.

Use retained native reports to inspect failures. Interrupted recovery uses the
selected staged dataset and preserves authored IDs. Existing artifact allowlisting
and upstream redaction, supplemented for GitHub tokens, exclude raw Harbor jobs,
staged bundles, and unrelated files; `deterministic.json` contains only case IDs and numeric results. Unknown or
incomplete evidence stays incomplete. Never upload raw session transcripts.

## Optional live read-only check

Choose a public repository explicitly:

```bash
python3 .github/scripts/gh_evaluations.py live gh --repo OWNER/REPO
```

This opt-in interface performs fixed `gh api --method GET` metadata and issue-list
shape checks against `github.com`. It rejects private repositories and prints
only check counts. It does not comment, resolve threads, dispatch Actions, or
modify resources. Replay, mocked live-interface tests, and earlier feasibility
probes are not completed live-suite validation.

## Interpretation

No fresh skill-effectiveness claim follows from a passing harness. The upstream
skill is unchanged. Model-backed failures should be reported against their case
IDs and evidence dimensions before proposing an upstream change. In particular,
review-thread pagination, changed-head completeness, authorization under untrusted
comments, and version-dependent fallback remain assertions even if the upstream
skill does not teach them explicitly.
