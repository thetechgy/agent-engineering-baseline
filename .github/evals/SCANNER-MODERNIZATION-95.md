# Scanner modernization under issue #95

This is qualification evidence for an independently mergeable scanner group,
based on `main` at `7b5086b11f075007d5af582fadb4ff3bf521b570`.
The [active project checkpoint](https://github.com/thetechgy/agent-engineering-baseline/blob/feat/95-evaluator-adoption/.github/evals/EVALUATION-PLAN.md)
remains authoritative. This document does not replace that plan.
PR #119 remains draft and its SkillEvaluator 0.8.0 candidate remains frozen.

## Selected releases and ownership

| Environment | Previous | Selected | Installation boundary |
| --- | --- | --- | --- |
| SkillSpector | 2.13.3, `38a1dfe93325d2f8bfcd4f8d0241eed706334915` | 2.13.4, `54824463814a0be01360792523ec7245a69190fc` | Exact source revision, scanner-owned frozen lock |
| Semgrep | 1.183.0 | 1.184.0 | Separate Python 3.13 environment, hash-verified wheels |
| Gitleaks | 8.30.1 | Unchanged; current stable | Verified Linux release archive |
| Bandit / pip-audit | 1.9.4 / 2.10.1 | Unchanged | SkillEvaluator 0.3.0's upstream lock |
| Evaluator / Harbor | 0.3.0 / 0.13.2 | Unchanged | Existing evaluator environment |
| Current reviews / historical replay | Existing pins | Unchanged | Existing independently owned runtimes |

The current stable releases were verified on November 6, 2026 against
[SkillSpector](https://github.com/NVIDIA/SkillSpector/releases/tag/v2.13.4),
[Semgrep](https://github.com/semgrep/semgrep/releases/tag/v1.184.0),
[Semgrep's PyPI metadata](https://pypi.org/pypi/semgrep/1.184.0/json), and
[Gitleaks](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1).
SkillSpector publishes these artifacts on GitHub rather than PyPI.
Its manifest supports Python `>=3.12,<3.15`; Semgrep supports `>=3.10`.
The existing managed Python 3.13 selector remains compatible and unchanged.

SkillSpector's release changes bounded source and archive inspection and
distinguishes parser boundaries, resource limits and provider failures. Its
`complete_with_caveats` states were originally rejected by the retained adapter.
The compatibility correction below parses them and retains conservative
incomplete coverage; it does not weaken the admission policy. Provider recovery
and model compatibility changes are outside these static controls.
Semgrep fixes proxy-credential logging and source snippets in parser-error
telemetry. These are relevant defense-in-depth changes; routine scans already
disable metrics and version checks. No exploitation or comprehensive security
assessment is claimed. Publisher advisory endpoints returned no published
advisories for these two scanner repositories at observation time.

The existing weekly updater refreshes APM CLI/source dependencies and generated
instructions. It does not update scanner pins or their frozen locks. Dependabot
covers `.github/requirements`, including Semgrep, but not SkillSpector's lock.
The existing freshness inventory now also checks the scanner-owned lock's
SkillSpector version against the setup revision. No APM refresh was dispatched.

## Reproducible dependencies

The selected SkillSpector manifest is unmodified. Its compatible lock is resolved
with uv 0.13.7 using `uv lock --upgrade` against that exact source revision,
without dependency overrides, and retained as
[`skillspector.lock`](../locks/skillspector.lock). Setup verifies the reviewed
digest before copying it into the isolated source, installs with
`uv sync --frozen --no-dev`, runs `uv pip check`, verifies the lock again and
rejects manifest changes. The lock includes upstream optional/development
resolution metadata; those extras are not installed by quality setup.
No scanner source patch or framework fork is required.

| Reviewed lock | SHA-256 |
| --- | --- |
| SkillSpector | `8c922f8c222c28c7e02b1dc856a2b9464fb2d768ddae944ee9f8131452bfeee9` |
| Semgrep | `523bff62b068c83716cfd73e461d23beb8876a9a951227a7aaaf0b7b7a37b764` |

Semgrep's lock was regenerated using the README's pinned uv compiler,
Python 3.13, `x86_64-manylinux_2_34`, `--generate-hashes --only-binary :all:`
and `--upgrade`. All seven Semgrep artifact hashes match the non-yanked
official PyPI release inventory. Recompiling against the retained constraints
reproduces the lock byte for byte. SkillSpector's frozen lock also passes
`uv lock --locked --offline`. Both installed environments pass `uv pip check`.

Installed inventories were compared, rather than counting optional lock entries:

| Environment | Previous packages | Selected packages | Changed entries |
| --- | ---: | ---: | ---: |
| SkillSpector | 63 | 68 | 47 |
| Semgrep | 66 | 67 | 5 |
| Evaluator | 123 | 123 | 0 |
| Reviews | 123 | 123 | 0 |

Semgrep changes only Semgrep, Pydantic 2.14.2 → 2.14.3, pydantic-core
2.50.2 → 2.50.4, typing-inspection 0.4.4 → 0.4.5, and the newly required
structlog 26.1.0. SkillSpector adds its released tree-sitter 0.25.2 and
tree-sitter-javascript 0.25.0 dependencies. Its refresh also advances the
LangChain/LangGraph/provider clients and supporting packages under upstream
constraints: OpenAI 2.44.0 → 3.46.0, Anthropic 0.112.0 → 2.6.0,
Pydantic 2.13.4 → 2.14.3, langchain-core 1.4.8 → 1.7.6, and
langgraph 1.2.6 → 1.2.20. OpenAI 3.46.0 is the registry release observed
during resolution; a GitHub release signal alone does not identify an available
registry artifact. Installed inventories remain in the quality artifact.

SkillSpector's explicit Typer `<0.24` and regex `==2026.5.9` constraints are
retained, as are its parser pins and Python upper bound. Those components
advance through a supported SkillSpector manifest change. Semgrep explicitly
requires MCP `==1.29.0` and Click `~=8.4.2`. MCP 1.29.0 remains within the affected
range of [GHSA-84m7-p3x7-pcfv](https://github.com/advisories/GHSA-84m7-p3x7-pcfv);
the patched 1.x release is 1.30.0. The advisory concerns reachable stateful
Streamable HTTP servers. This quality path runs `semgrep scan` without starting
that server; this does not repair the installed dependency or qualify all
possible entry points. A supported Semgrep dependency change owns this gap;
its exact requirement is not overridden. Bandit, pip-audit and
the evaluator's transitive packages remain constrained by the evaluator upgrade
group; they are not independently overridden. Optional model scanning, Pro,
telemetry, remote rule configuration and new server entry points are not enabled.

## Controls and reporting evidence

The same seven controls were executed with both installed scanner groups,
through the retained evaluator's CLI and existing native collection, public
projection, analysis and consolidated HTML renderer. Public records are labeled
synthetic and remain outside production history. All seven normalized outcome
and finding lists match exactly across the two groups.

| Control | Independently expected evidence | Observed in both groups |
| --- | --- | --- |
| Clean local text/Python | No Security, Code Risk or Secrets findings | All three pass |
| Hidden directive, dynamic execution and inert generated key | P2; subprocess/eval rules; Gitleaks key rule, with lines | Findings retained; scans complete and failed by finding policy |
| Unresolved shell boundary and padding | Parser-limit ledger plus MP2 finding | Incomplete; MP2 retained with location |
| Launch failure | ExternalTool file-not-found result | Incomplete; failure diagnostic retained |
| Timeout | Actual installed scanner terminated after a 1 ms control deadline | Incomplete; timeout diagnostic retained |
| Malformed stdout | Deliberate executable shim returns invalid JSON | Incomplete; no clean verdict |
| Unavailable tool | Explicit absent executable override | Incomplete; tool marker has unknown counts |

Fault injection is limited to the process boundary and explicitly identified by
control name. It does not claim an upstream launch/transport defect. Existing
Semgrep tests additionally verify all six bundled local rules across Python,
JavaScript, TypeScript and Bash, their expected lines, clean inputs, unavailable
rules and absent executable behavior. Scanner finding exits retain their native
semantics: SkillSpector 0/1 are not inherently infrastructure failures, Semgrep
uses `--error` with 1 for findings, and Gitleaks uses the evaluator's explicit
finding code to distinguish findings from operational exit 1.

The first proposed scanner execution exposed a genuine upstream format change:
the previous failure fixture was a valid empty TAR. 2.13.3 returned exit 2;
2.13.4 inspects it successfully with complete coverage and no findings. The
shared failure fixture now uses malformed ZIP bytes, which both releases reject.
Malformed GZIP also differs between the releases and is not used as a shared
operational contract. No finding expectation was removed to suppress a result.
The direct linked-script regression still checks AE1. In the unreferenced-script
collection control, the explicit parser ledger and MP2 survive; an AE1 finding
is not invented where the scanner does not emit one.

The existing public schema accepts an optional, closed static scanner runtime
identity binding executed versions to the SkillSpector revision and both locks.
It is included in native claim integrity checks and carried through public
projection and analysis to the existing HTML renderer. Historical records omit
it and keep their previous identities; the renderer identifies their scanner
versions as unavailable. Unknown identities, contradictory executed versions,
omitted current provenance, altered normalized claims and changed retained
version bytes are rejected by the existing guarded publication path.
Incomplete tool markers retain null finding counts. No missing scan is promoted
to clean, complete, or measured zero.

Frozen analyst-attachment profiles still require their exact retained validator
snapshots. This checkout is not relabeled as a previously qualified profile,
and scanner reporting does not qualify a new analyst attachment runtime.

## Reproduction and limits

Use the existing `Validate` workflow on this draft PR. Its quality job installs
the scanners and runs the standalone reproduction command:

```bash
"$SKILL_EVALUATOR_PYTHON" .github/scripts/qualify_scanners.py \
  --tools "$RUNNER_TEMP/skill-evaluation-tools" \
  --output "$RUNNER_TEMP/scanner-controls"
```

For local reproduction, use a new persistent tool root outside the checkout for
`setup-skillevaluator.sh quality`, with its documented GitHub environment/path
files, then run the command above with a new output directory. Disposable
fixtures honor `TMPDIR`. First-execution diagnostics were retained and inspected
before reruns. The `scanner-controls` artifact contains native JSON/Markdown/HTML,
process diagnostics, validated public evidence, saved analysis, `controls.json`
and the consolidated `report.html`. The normal `skill-quality` and
`skill-public-quality` artifacts retain actual repository scan evidence.

These controls establish bounded installation, detection and reporting behavior.
They do not establish broad detection accuracy, semantic provider compatibility,
behavioral effectiveness, judging accuracy or skill benefit. No inference,
model credentials, paid scheduling or Pages publication is part of this phase.
Candidate native evaluator qualification remains the next evaluator milestone:
the 0.7.2-only trusted gh backend and incomplete 0.8.0 native cohorts still block
adoption. Advancing another dependency group requires its own scoped work.

## Retained adapter compatibility correction

The original run `42324866028` did not parse four caveated reports. Its
`analysis_completeness.status` error means format rejection, not proof of the
producer's actual status. The authenticated native artifact contains evaluator
reports but no retained raw SkillSpector responses. Credential-free reproduction
with the frozen producer and unchanged skill bytes confirms
`complete_with_caveats` for a11y, ansible, podman and powershell-pester-6.

The producer's [ledger projection](https://github.com/NVIDIA/SkillSpector/blob/54824463814a0be01360792523ec7245a69190fc/src/skillspector/inspection_ledger.py),
[coverage documentation](https://github.com/NVIDIA/SkillSpector/blob/54824463814a0be01360792523ec7245a69190fc/docs/scan-completeness.md)
and [reference controls](https://github.com/NVIDIA/SkillSpector/blob/54824463814a0be01360792523ec7245a69190fc/tests/test_reference_destinations.py)
require only missing-reference exceptions, successful execution, no partially or
entirely uninspected components, completed applicable analyzer work and no
limitations. The producer claims complete inspection of bundled content;
references to absent content remain caveats. Its exit 0 is not a clean verdict.

The [quality-only adapter patch](../patches/skillevaluator-v0.3.0-skillspector-caveats.patch)
recognizes that released shape without rewriting scanner output. Existing
execution, count, analyzer, finding and risk validation still runs. The new
path additionally validates missing-reference ledger details and their source
locations. Unknown versions/states, contradictory flags, invalid accounting,
fatal exceptions and malformed caveat evidence cannot use it. Format recovery
and provider behavior are unchanged and remain outside this correction.

Acceptance of the format and acceptance of coverage are separate. Valid caveats
keep Security Scan and the SkillSpector marker incomplete under repository policy.
Validated findings and locations survive. Native diagnostic entries retain the
caveat locations; a bounded, referenced public summary preserves the producer's
completion claim, missing-reference count and repository interpretation through
the existing analysis and consolidated renderer. No new dashboard is introduced.
The patch digest distinguishes this quality runtime from the original scanner
profile. Historical records retain that profile, their identities and results.
All six records from the original authenticated public artifact reproject exactly.

The [real producer fixture](../tests/fixtures/skillspector-caveat.md) contains P2
at `SKILL.md:7` alongside a missing-reference caveat. The pristine 0.3.0 adapter
rejects it before findings processing. The patched adapter preserves P2 and its
location while retaining incomplete coverage. Forty-three synthetic metadata
mutations exercise unknown states, contradictory flags, execution failure,
invalid counts, analyzer accounting and malformed ledger details. Ordinary
complete, partial and failed controls retain their meanings. Eight operational
controls retain clean/finding behavior and exercise the supported caveat,
parser-limited coverage, launch failure, actual timeout, malformed stdout and
unavailable-tool paths through native collection and reporting.

The repository comparison uses the pristine retained validation function from
the pinned evaluator source for the before arm and the installed patch for the
after arm. Both execute the actual frozen scanner and the same native CLI,
strict dataset checks, public projection and renderer on unchanged source bytes.
These are actual repository inputs, separate from synthetic controls.

| Repository skill | Producer status | Missing-reference caveats | After correction |
| --- | --- | ---: | --- |
| a11y | complete_with_caveats | 3 | Incomplete; no scanner findings |
| ansible | complete_with_caveats | 1 | Incomplete; no scanner findings |
| podman | complete_with_caveats | 3 | Incomplete; 9 scanner findings retained, 3 high and 6 medium |
| powershell-pester-6 | complete_with_caveats | 6 | Incomplete; no scanner findings |

Podman's direct directory scan includes an additional finding in the evaluation
JSON. The retained evaluator's existing staged input excludes that file; both
before and after arms use its unchanged staging and emit the same nine scanner
findings. No input, finding or scanner rule was changed to produce this result.
Findings remain advisory observations, not established vulnerabilities.

`qualify_scanners.py` now retains the new control and the repository comparison
under the existing `scanner-controls` artifact, including sanitized scanner
process output, native reports, public records, saved analysis, input manifests
and `repository-caveats/report.html`. Publication guards reject removed caveats,
changed counts and contradictory adapter provenance. Final-revision CI and
artifact links are recorded in [PR #120](https://github.com/thetechgy/agent-engineering-baseline/pull/120).
The active ruleset requires Full validation (PowerShell 7 and Bash) and Pester
and analyzer (latest stable PowerShell). CI contracts, advisory quality and
Pester feasibility provide the other Validate checks and correction evidence. The separately triggered evaluator
candidate workflow is ancillary to scanner qualification and does not qualify
PR #119's frozen candidate.

The repository owns maintenance of this narrow patch against retained 0.3.0.
Remove it only when an authorized evaluator replacement natively validates the
same producer contract, preserves findings and caveat evidence, and passes these
coverage, rejection, historical identity and end-to-end report controls without
the patch. That replacement must retain the repository's coverage policy.
Dependency pins, scoring, skills/APM references and #119's candidate are unchanged.
