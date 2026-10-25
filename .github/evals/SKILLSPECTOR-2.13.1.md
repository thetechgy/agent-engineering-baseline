# SkillSpector 2.13.1 adoption assessment

## Decision and provenance

Adopt 2.13.1. Tagged security/correctness fixes, successful integration checks,
two corrected HIGH false positives, and better reference accounting provide
material value. No finding loss beyond those verified false positives was
observed. This is bounded static-analysis evidence, not skill safety or
behavioral-effectiveness qualification. A new conservative PowerShell parser
limitation remains explicitly recorded below.

| Input | Identity |
| --- | --- |
| Repository source | `9777ea23313c6dde0d785b65926a59665a173cc7` |
| Complete `.apm/skills` Git tree | `438e2dc2239e6126f35b298b21469620ab0f1069` |
| Before | SkillSpector 2.11.2, `69dcdfb74487d361ba4c811d088cfdea2ff3a9dc` |
| After | SkillSpector 2.13.1, `f3b25697d76256998ca9d42c198d256258d4c035` |
| Evaluator | SkillEvaluator 0.3.0, `ac0a04905100acdafc6c95829311a9739c340ff6` |
| Runtime | Managed CPython 3.13.15, uv 0.12.17, Linux x86_64 |
| Other tools, unchanged | Semgrep 1.177.0, Bandit 1.9.4, pip-audit 2.10.1, Gitleaks 8.30.1, Harbor 0.13.2 |
| Before scanner lock SHA-256 | `5de3b0c121a34472026462c9fad368019accbe094ba4693198364c105e5ea93c` |
| After scanner lock SHA-256 | `be67af98205cee9b517a154c7a74dbde2944a4af55f54f58718350bb48a22b37` |

The two frozen locks contain the same 157 third-party package records; only the
SkillSpector package version changes. Installed evaluator and Semgrep inventories
also match exactly. Both tool roots were installed independently through the
production setup script. Neither scanner checkout nor its lock was modified.
Production changes are the scanner pin, passing that selected revision to version
metadata rather than repeating a literal SHA, and recording `SKILL_EVALUATION_KIND`
for the shared test suite. Scanner-only checks skip explicitly in benchmark setup,
which intentionally does not install the scanner; quality setup still requires it.

[Upstream releases](https://github.com/NVIDIA/SkillSpector/releases/tag/v2.13.1)
and tagged implementation/tests were reviewed across 2.12.0, 2.13.0 and 2.13.1.
Relevant changes include bounded HTML-comment matching, host-language/string and
prose ownership, retained shell detections, stronger inspection accounting,
atomic/no-follow report output, and tool-misuse deadline/context hardening.
Provider, MCP, contributed-batch, image and Office changes are not qualified by
this local static catalog. The scanner's disabled Codex analysis provider does
not change this repository's separately pinned benchmark runtime.

A direct CLI output-security control independently verifies an upstream fix:
2.11.2 writes a JSON report through a symlinked parent directory (exit 0), while
2.13.1 rejects the destination (exit 2) without writing the report. Both input
and destination were private task-owned fixtures. To reproduce, create a valid
minimal skill and a directory symlink outside that input, then run
`skillspector scan "$input" --no-llm --format json --output "$alias/report.json"`.
The evaluator normally consumes stdout, so this verifies upstream hardening
rather than claiming a newly exercised output-file path in routine evaluation.

The historical [run 40149844098](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/40149844098)
recorded evaluated merge commit `29c335e34d6e8b297d05f1b905abe4b098f17229`,
distinct from its PR head. Its skill tree equals the tree above. A fresh baseline
reproduced its aggregate and SECURITY counts exactly. Historical reports retain
their original toolchain identities and are not relabeled.

## Before and after

Every scanner process completed successfully: exit 0 for five skills and exit 1
for Podman's risk gate, in both versions. Execution success is separate from
completeness and evaluator pass/fail. Counts below are **SECURITY** C/H/M/L;
the 91 historical findings were across all evaluator checks, not SkillSpector.

| Skill | Native SECURITY status before → after | Completeness before → after | C/H/M/L before → after | Assessment |
| --- | --- | --- | --- | --- |
| a11y | incomplete → incomplete | partial → partial | 0/2/0/0 → 0/0/0/0 | Beneficial: two confirmed cross-comment false positives removed |
| agent-safety | incomplete → failed | partial → complete | 0/1/2/0 → 0/1/2/0 | Beneficial: complete scan; retained findings correctly keep the check failed |
| ansible | incomplete → incomplete | partial → partial | 0/0/0/0 → 0/0/0/0 | Better reference accounting; conservative missing-reference warning remains |
| podman | incomplete → incomplete | partial → partial | 0/3/6/0 → 0/3/6/0 | Better reference accounting; all nine native findings retained |
| powershell-module-engineering | incomplete → incomplete | partial → partial | 0/0/0/0 → 0/0/0/0 | Mixed: prose-reference noise removed; new parser limitation below |
| powershell-pester-6 | incomplete → incomplete | partial → partial | 0/0/0/0 → 0/0/0/0 | Better accounting; example paths/configuration references remain limited |

Total SECURITY findings: **14 → 12**, HIGH **6 → 4**, MEDIUM **8 → 8**;
no CRITICAL/LOW findings, additions or severity reclassifications. Aggregate
catalog findings: **91 → 89**, C/H/M/L **1/15/41/34 → 1/13/41/34**.
All non-SECURITY findings are unchanged. In particular, Ansible's CRITICAL
`PII / hardcoded_secrets` finding at `SKILL.md:42` flags an Ansible Vault
template example; this upgrade neither fixes nor suppresses that separate check.

Finding matching used multisets of rule, file, line, severity and matched text,
then checked category, pattern, confidence, occurrences and source context.
All 12 retained findings preserve category, pattern, confidence, severity,
primary file/line and matched text. Finding IDs change; occurrence columns and
some context windows change. One Podman RA2 fingerprint changes while its
matched source does not. These are representational changes, not new findings.
A11y's risk score changes from 26 to 0 (MEDIUM → LOW, maximum issue severity
HIGH → NONE); its recommendation remains CAUTION because analysis is partial.
Other risk assessments are unchanged, including Podman's score 73 and
DO_NOT_INSTALL recommendation.

Material finding review:

- Removed a11y `P2` findings at `SKILL.md:121` and `:261` previously crossed
  closed HTML comments into visible prose/code. Neither span contains the
  claimed hidden directive. A real-CLI regression fails on 2.11.2 and passes
  on 2.13.1; actual hidden directives remain detectable.
- Retained agent-safety `RA1` at `SKILL.md:92`, and `EA1` at `:17`/`:68`,
  occur in a common-mistakes list, an explicit prohibition, and a labeled bad
  example. These remain contextual false-positive candidates for later triage.
- Retained Podman `RA1` at `EVALS.md:31` concerns removing nondiscriminating
  evaluation assertions. `PE5` at `references/security-storage-secrets.md:43`
  and `:108` flags explicit prohibitions on `--privileged`.
- Podman `RA2` at `references/quadlet-systemd.md:20` matches a prohibition on
  unnecessary pods; `EA1` at `references/reverse-proxy.md:9` and
  `references/security-storage-secrets.md:193` matches warnings about API
  authority. Three other `RA2` findings match prohibitions on enabling generated
  services: `SKILL.md:189`, `references/quadlet-systemd.md:196`, and
  `references/validation.md:66`. These unchanged contexts warrant downstream
  interpretation, not automatic acceptance, suppression, or skill rewriting.

### Completeness and the PowerShell limitation

| Skill | Ledger exceptions before → after | Remaining candidate explanation |
| --- | --- | --- |
| a11y | 23 → 3 | `reference_missing` at lines 96, 128, 545: version notation, application file examples and `document.title` |
| agent-safety | 4 → 0 | Ordinary slash-separated prose is no longer treated as unresolved local files |
| ansible | 2 → 1 | `reference_missing` at line 27 around the external Ansible documentation link |
| podman | 29 → 3 | `reference_missing` at lines 31, 78, 172: upstream source examples, address notation and `network-online.target` |
| powershell-module-engineering | 5 → 1 | New `static_parse_limit` in `static_patterns_tool_misuse`; no source line supplied |
| powershell-pester-6 | 9 → 6 | `reference_missing` at lines 42, 67, 80, 192, 207, 213: example files, test/output paths and configuration names |

These counts are ledger events, not counts of distinct reference candidates.
Some remaining missing references describe the consumer's project or external
documentation; they do not prove omitted bundled files. No references were
downloaded and transitive scanning remains disabled.
Both versions inventory the same 17 native-scope files, with no entirely
uninspected files. The improvements do not establish inspection of additional
bundled files; Podman's four excluded evaluation files remain outside native scope.

The PowerShell result needs special care: its file counters change from one
fully inspected file to one partially inspected file (100% → 0% fully-inspected
coverage). Every other applicable analyzer completes; the tool-misuse analyzer
is degraded. Tracing its new runtime-selected-command operand safeguard reaches
PowerShell string interpolation in a Markdown code example. The old safeguard
skipped non-printf substitutions. This is a new conservative completeness
limitation on benign host-language content, not a timeout or scanner crash.

The unchanged input reproduces that result. A private copy with a real hidden
directive and destructive shell command appended retains the same `P2`, `TM1`
and `YR4` detections in both versions, including detections after the apparent
parser-bound location. Source review confirms the completeness hook records
the limitation while finding production continues. A narrower interpolation
counterfactual did not remove the limitation; a minimal reproducer/root-cause
fix is still follow-up work. No workaround is applied to the skill or scanner.

This is a negative completeness result, explicitly retained rather than called
an improvement. It is nonblocking for this adoption: both versions already mark
the skill partial, the existing public pipeline remains incomplete, no finding
loss was observed, and downstream positive controls still detect actual risks.
This evidence does not prove exhaustive detection beyond the scanner's bounds.

### Execution overhead

Single sequential raw scans of evaluator-equivalent inputs, seconds / peak RSS
KiB, including CLI startup:

| Skill | Before seconds / KiB | After seconds / KiB |
| --- | ---: | ---: |
| a11y | 6.46 / 143636 | 8.56 / 137376 |
| agent-safety | 3.13 / 142032 | 3.61 / 135764 |
| ansible | 2.81 / 142080 | 3.28 / 136108 |
| podman | 11.12 / 143340 | 11.99 / 136668 |
| powershell-module-engineering | 4.89 / 143292 | 5.51 / 136760 |
| powershell-pester-6 | 4.47 / 142288 | 5.95 / 136376 |

Native catalog wall time was 38.27 → 46.32 seconds. These observations show
modest added local overhead, not a speed improvement or statistically established
performance ratio. No timing repetitions were needed to decide the upgrade;
only the unexpected PowerShell completeness result received targeted repeats
and detection controls. No per-artifact runtime limit was reached, so the
supplementary 30-second-budget comparison was unnecessary. Upstream's default
artifact allowance is now 300 rather than 30 seconds; the evaluator's existing
300-second whole-process deadline and CI job deadline remain unchanged.

## Reproduction and evidence retention

Run from this PR's checkout with Git, pinned uv 0.12.17, and Python acquisition
available. Use private external storage, keep both frozen environments separate,
and verify the source tree identity above. The following are the measurement
commands; temporary outputs must stay outside the checkout.

```bash
umask 077
workspace=$(pwd -P)
study=$(mktemp -d)
base=9777ea23313c6dde0d785b65926a59665a173cc7
test "$(git rev-parse HEAD:.apm/skills)" = 438e2dc2239e6126f35b298b21469620ab0f1069
git diff HEAD --exit-code -- .apm/skills
test -z "$(git status --porcelain=v1 --untracked-files=all --ignored -- .apm/skills)"

for label in before after; do
  run="$study/$label"
  mkdir -p "$run/home" "$run/quality"
  if [ "$label" = before ]; then
    git show "$base:.github/scripts/setup-skillevaluator.sh" > "$run/setup.sh"
  else
    cp .github/scripts/setup-skillevaluator.sh "$run/setup.sh"
  fi
  RUNNER_TEMP="$run" GITHUB_WORKSPACE="$workspace" \
    GITHUB_ENV="$run/github-env" GITHUB_PATH="$run/github-path" \
    bash "$run/setup.sh" quality > "$run/setup.log" 2>&1
  tools="$run/skill-evaluation-tools"
  python="$tools/evaluator/.venv/bin/python"
  clean=(env -i HOME="$run/home" LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1
    PATH="$tools/evaluator/.venv/bin:$tools/bin:/usr/bin:/bin"
    XDG_CACHE_HOME="$tools/cache" XDG_STATE_HOME="$tools/state"
    SKILLEVALUATOR_RESULTS_DIR="$run/quality/results"
    SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE="$tools/provenance.key")
  cp "$tools/versions.json" "$run/quality/versions.json"
  cp -r "$tools/dependencies" "$run/quality/dependencies"
  (
    cd "$run/quality"
    status=0
    "${clean[@]}" "$tools/evaluator/.venv/bin/skillevaluator" validate \
      "$workspace/.apm/skills" --external --tiers 1 --no-llm --no-dedup \
      --continue-on-failure --evaluated-source-repository thetechgy/agent-engineering-baseline \
      --evaluated-source-revision "$base" -r json,markdown,html -o reports \
      > "$run/catalog.stdout" 2> "$run/catalog.stderr" || status=$?
    printf '%s\n' "$status" > catalog.exit
  )
  # Reuse the pinned evaluator's actual staging policy, not an invented exclusion list.
  "${clean[@]}" "$python" - "$workspace/.apm/skills" "$run/inputs" <<'PY'
from pathlib import Path
import shutil
import sys
from skillevaluator.validators.security import _ignore_artifact_dirs
for skill in sorted(Path(sys.argv[1]).iterdir()):
    if (skill / 'SKILL.md').is_file():
        shutil.copytree(skill, Path(sys.argv[2]) / skill.name,
                        symlinks=True, ignore=_ignore_artifact_dirs)
PY
  mkdir "$run/raw"
  for skill in "$run"/inputs/*; do
    name=$(basename "$skill")
    status=0
    (cd "$run/quality"; "${clean[@]}" /usr/bin/time -q \
      -f 'wall=%e user=%U system=%S max_rss_kib=%M' -o "$run/raw/$name.resources" \
      "$tools/bin/skillspector" scan "$skill" --format json --no-llm) \
      > "$run/raw/$name.json" 2> "$run/raw/$name.stderr" || status=$?
    printf '%s\n' "$status" > "$run/raw/$name.exit"
  done
done
```

Also run the unchanged workflow's strict dataset collection/catalog checks and
`public-quality` handoff. The actual study retained input byte manifests,
commands, exits, dependency inventories, raw JSON/stdout/stderr, native reports,
resource observations and targeted controls privately. Original diagnostics
are hashed and kept unchanged; only reviewed summaries are committed. Full
source scans were additionally retained; Podman's full source has 14 files and
10 issues, whereas the evaluator stages 10 files and reports 9 issues because
it excludes `evals/`. Before/after conclusions above use the native scope.

## Validation and follow-up

Local validation:

- Full offline Python suite at `97f315a`, before the benchmark-mode review fix:
  589 tests run, 588 passed, one skipped because the
  installed gh version differs from the recorded 2.102.0 help contract. Runtime
  was 1537.136 seconds. The four new real-scanner tests all passed; the benign
  regression also failed against 2.11.2 before passing against 2.13.1.
- Review follow-up reproduced four scanner-test failures and the native/public
  P2 assertion failure with the scanner absent. After recording setup kind,
  quality mode passes all four scanner tests and the native/public handoff;
  benchmark mode intentionally skips only those four scanner tests and passes
  the existing native/public contract without the scanner. Quality mode with
  the scanner absent still fails all four assertions. Both setup contract tests
  pass. All 80 affected setup, public-report and scanner tests pass after the fix,
  including a permanent scanner-absent benchmark regression. The complete local
  suite was not repeated for this narrow mode guard;
  final-revision hosted validation remains required.
- Both production installations, fresh six-skill catalogs, catalog infrastructure
  contracts, and native strict Podman dataset validation passed.
- Both six-skill public bundles, combined offline analysis and HTML generation
  passed without changing ownership, provenance, redaction or projection guards.
- Keyless gh catalog validation, broker replay (24/24 good traces accepted;
  13/13 faulty traces rejected), staging and native strict validation passed.
- PowerShell 7.6.6 / Pester 6.2.0: 29 passed, 52 platform skips, no failures.
  PSScriptAnalyzer 1.25.0 and Bash bootstrap fixtures passed. Verified APM 0.35.0
  performed isolated frozen regeneration, compilation, packaging, two 10-check
  audits and offline Graph smoke without generated-output differences.
- Full local repository validation stopped at six existing SC2329 informational
  findings from host ShellCheck 0.11.0 in unchanged Bash test functions. These
  reproduce from the exact baseline files; the full command is not claimed green.
  Changed setup ShellCheck, repository Markdown lint (rumdl 0.2.34, 25 files),
  changed Python parsing and whitespace checks passed separately.

Permanent additions are four small real-scanner tests, selected-revision and
scanner-absent benchmark tests, and a stronger native-CLI/public-handoff test. They
cover benign comments and Python strings, real hidden directives and shell
execution, retained findings from partial scans, contradictory accounting, and
failed/unavailable tools. No generalized compatibility framework or new fixture
archive is introduced. Exact-final-revision hosted validation is recorded in
the PR separately from these local results. No paid inference, behavioral agent
trials, complete upstream test suite, or local native Windows execution was run.

SkillEvaluator 0.3.0 validates but then discards the detailed completeness
ledger, analyzer states/accounting, coverage counters, exclusions and reference
reasons. Native/public findings keep primary rule/severity/member/line but not
the scanner's full occurrence columns, fingerprints and diagnostic context.
The strict public projection intentionally excludes arbitrary scanner prose.

Read-only inspection of [SkillEvaluator 0.6.0](https://github.com/NVIDIA/SkillEvaluator/blob/5320d9329c36ecc72bc94c4f58cc813d6b54224b/src/skillevaluator/validators/security.py)
shows the same completeness-retention gap; its HTML scanner-version display
does not resolve it. The smallest sustainable follow-up is upstream retention
of validated bounded completeness metadata in native results/JSON, then a
separately reviewed repository projection of safe counts, enums and relative
locations with provenance. Evaluate 0.6.0's other contract/dependency changes in
its own PR before deciding between upgrading, an upstream contribution, or a
narrow adapter. Do not introduce a recurring raw-output wrapper here.

Outstanding work: reduce the PowerShell parser example, triage remaining
reference and defensive-language false positives, and improve diagnostic
visibility before AI-assisted recommendations. No issues or upstream changes
are created by this PR. No imported or local skills, evaluator version,
benchmark model/runtime, Harbor pin, schema, suppression policy, CI privilege,
deadline, redaction, publication allowlist or generated APM output changes.
