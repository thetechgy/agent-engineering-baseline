# SkillEvaluator 1.0.1 static qualification

Compared with the production 0.9.0 owner on main
`a6d860186a9e7683f9e42c7627a150baff8fe23e` after #164. The scope follows the
[November 19 dependency checkpoint](dependency-qualification-20261119.md).

## Decision evidence

| Same-input check | 0.9.0 offline-v3 | 1.0.1 static-v1 |
| --- | --- | --- |
| Clean control | 0 secrets, complete Gitleaks coverage | 0 secrets, complete Gitleaks coverage |
| Top-level marker | 1 at `input.txt:1`, complete | 1 at `input.txt:1`, complete |
| Authored evaluation marker | 0 secrets, reported complete | 1 at `evals/files/input.txt:1`, complete |
| Repository dataset | Podman admitted, 10 cases | Podman admitted, 10 cases |
| Repository static findings | 88 counted, including 11 SECURITY | 89 counted, including 11 SECURITY |
| Incomplete SkillSpector coverage | 4 of 6 skills | Same 4 of 6 skills |
| Native catalog headlines | 6 failed | 3 failed, 2 incomplete, 1 passed |

Both controls use Gitleaks 8.30.1 from the same binary. The authored marker is
in an input declared by a committed `evals/evals.json` in a disposable skill
checkout. Each case uses the same committed bytes for both producers.
Coverage in the control rows refers to Gitleaks. The fixture also has
independent schema findings. The candidate retains the authored location in
native evidence, public JSON and consolidated HTML. The upload gate checks that the marker value is absent
from every staged file, including the native JSON, HTML, Markdown and
strict-dataset diagnostics. Fixture source and raw scanner streams stay in
scratch. This is a synthetic detection and redaction result. [Upstream fix](https://github.com/NVIDIA/SkillEvaluator/pull/552).

The six skills retain the same two PII-failing skills, 11 SECURITY findings
and four SkillSpector incompleteness markers. The missing-reference counts
remain 3 for a11y, 1 for ansible, 3 for Podman and 6 for
powershell-pester-6. Podman retains its confirmed findings and incomplete
coverage together. Gitleaks reports zero catalog findings on this snapshot.

All six missing-author findings move from high to low under the default
author policy. Six low description-trigger findings appear and six medium
`quality_correctness` findings disappear. The candidate adds 26 advisory
Harness Compatibility findings, one low `OW-READ-BUDGET` for a11y and 25
informational findings, outside the critical/high/medium/low total.
The a11y and powershell-pester-6 headlines become incomplete and
powershell-module-engineering passes. Agent-safety, ansible and Podman still
fail. The release also makes unverified hook payloads a critical gate. The
catalog has no such gate finding and this comparison does not exercise a hook.
[Release notes](https://github.com/NVIDIA/SkillEvaluator/releases/tag/v1.0.1).

| Native Tier 1 heuristic | 0.9.0 | 1.0.1 |
| --- | ---: | ---: |
| a11y | 83.8 | 85.5 |
| agent-safety | 88.5 | 90.2 |
| ansible | 86.8 | 88.5 |
| podman | 88.5 | 90.2 |
| powershell-module-engineering | 88.5 | 90.2 |
| powershell-pester-6 | 85.8 | 87.5 |

Each score rises 1.7 points from the evaluator's scoring change. Treat
the score as release-specific and review decisions against the findings and
coverage. There is no behavioral measurement in this qualification.

## PR #165 qualification setup and reporting

PR #165 opted in through the complete PR comparison. The standard job
used `quality-next` during qualification. The opt-in step installed 1.0.1
from commit `914c15cb3f31562ccffdc9a7166002a87ed2ce1e` with its frozen
upstream lock and checks the owning source, Python 3.14.10 and scanner versions.
The strict dataset CLI imports the Tier 3 extra. The qualification invokes
only Tier 1 collection and offline strict validation. External scanners are
shared directly with the baseline.

The candidate's strict dataset CLI initially passed for Podman while inventory
generation rejected the gh overlay. Upstream 1.0.1 uses a filesystem-only
config reader. The compatibility patch invokes its bounded YAML parser and
schema on the captured bytes, preserving the existing link and race checks.
It adds candidate admission and producer identity to the repository's normal
collection and reporting commands in a disposable copy of the checked-in
tools. That copy scans the same repository inputs. The copy preserves the
byte-bound campaign and replay sources on the checkout. The candidate public
bundle retains the catalog and inventory. Retained 0.9.0 evidence from #141
renders under its original producer identity.

The opt-in attachment contains the matched receipt, both public bundles,
consolidated reports and verified native diagnostics. Candidate evidence uses
`skillevaluator-1.0.1-static-v1`. The tested rollback is the `quality-next`
setup and the same collection, admission and projection commands under
`skillevaluator-0.9.0-offline-v3`. No replay, benchmark or judge selection is
required to use that path.

## Operate the static scanner

The `Skill quality (advisory findings)` job in [Validate](../../.github/workflows/validate.yml)
selects `quality-static` by default. It installs SkillEvaluator 1.0.1 under
`skillevaluator-1.0.1-static-v1` with the #165 pins, scans the repository catalog
once, and uses the isolated reporting tools for strict dataset admission and
public projection. Check `versions.json` in the native `skill-quality` artifact
and the producer ID in the `skill-public-quality-<run>-<attempt>` artifact.
The `scanner-controls` artifact includes the redacted authored-input control,
its public JSON and consolidated HTML at `authored-input/`.

The [Pages publisher](../../.github/workflows/publish-skill-report.yml) authenticates
the successful main producer and loads the public artifact through the same
reporting compatibility, including static policy admission in publication
history. It prepares and renders with its existing 0.9.0
data-only host. Retained 0.9.0 static reports keep the
`skillevaluator-0.9.0-offline-v3` identity. Validate on a draft PR produces the
ordinary artifacts. Live Pages publication follows a successful main run.
For offline Pages rebuilds, stage the same tools with
`python3 -B .github/scripts/static_quality_ci.py tools` and run the resulting
`skill_pages.py build` with the data-only host.

For matched qualification, the existing PR planner enables the comparison
when the complete diff changes `qualify_static_evaluator.py`,
`static_evaluator.py` or `static-evaluator-1.0.1-reporting.patch`. Look for the
separate `static-evaluator-qualification-<attempt>` artifact. The catalog's
findings and coverage are input-dependent. Use #165's 11 SECURITY findings and
four incomplete SkillSpector scans as the comparison snapshot.

To roll back, change the one selector in the Validate quality job from
`bash .github/scripts/setup-static-evaluator.sh quality-static` to
`bash .github/scripts/setup-static-evaluator.sh quality-next`. Keep the
isolated reporting setup and publisher preparation so both producer identities
remain readable.
