# Semgrep 1.182.1 qualification

## Decision and inputs

Upgrade the isolated CI scanner from 1.177.0 to the official PyPI package
[1.182.1](https://pypi.org/project/semgrep/1.182.1/). Its required PyJWT update
removes four affected-version advisory matches in the Semgrep environment. Paired local-rule controls
preserve detection results and coverage. This is bounded scanner compatibility
evidence, not proof of skill safety or complete parser coverage.

| Input | Identity |
| --- | --- |
| Verified repository base | `2a4f9d369c6d5a40f3b28466cd6aeeeb6b6d7e55` |
| Identical `.apm/skills` Git tree | `438e2dc2239e6126f35b298b21469620ab0f1069` |
| Evaluator | 0.3.0, `ac0a04905100acdafc6c95829311a9739c340ff6` |
| SkillSpector | 2.13.1, `f3b25697d76256998ca9d42c198d256258d4c035` |
| Runtime | uv 0.13.5, managed CPython 3.13.17, Linux x86_64 |
| Local six-rule file SHA-256 | `fff4537f6679a52c48e024e001b73e163b24587635a028e5c012583f19876abf` |
| Baseline Semgrep lock SHA-256 | `0954724464cc2cff10de9a100a64721d78937eeeb74082cd852624dff0a839a7` |
| Candidate Semgrep lock SHA-256 | `0667ebbddc8193dca90a737581b5ae2fc818100e76c25cfce5b6992421c2ea64` |

Both tool roots were installed through the production setup script, with
separate environments and a task-owned shared download cache. All 123 evaluator
and 63 SkillSpector installed package records match exactly. The Semgrep
environments each contain 66 packages; only Semgrep and PyJWT change.

## Artifact and release provenance

The selected artifact is the CPython 3.10–3.14-compatible
`manylinux_2_34_x86_64` wheel. Its SHA-256 is
`bba25e5a38db5061d725c0920699ecee3e8137026427e722a271bd9bb8d25a40`.
Downloaded bytes match PyPI metadata, the reviewed lock, and the signed
attestation subject.

Pinned `pypi-attestations 0.0.30` and its hash-locked dependencies were installed
in a separate temporary verifier environment. Verification checked the
production Sigstore certificate chain, transparency evidence and artifact
subject, with these exact identity constraints:

```text
Issuer: https://token.actions.githubusercontent.com
Identity: https://github.com/semgrep/semgrep-proprietary/.github/workflows/pro-release.yml@refs/heads/release-1.182.0
```

The verified certificate records GitHub-hosted execution and source digest
`4d7c7d9541cb34804ff75fd47d0e466aa27d762b`. The publisher matches the official
1.177.0 and 1.182.0 wheel provenance; 1.182.1 uses the release branch rather
than their `develop` identity. Wrong identity, wrong issuer, and wrong artifact
digest controls are rejected. The saved provenance JSON SHA-256 is
`ba2d2aca8b467edf15d593a34730afa38d5204cc38b33d17f4f015b340d90ef7`.
Publication provenance establishes an authenticated publication identity and
subject, not a security guarantee or a public source-to-binary reproduction.

As observed on 2026-10-25, the latest public GitHub release/tag is
[v1.182.0](https://github.com/semgrep/semgrep/releases/tag/v1.182.0), while PyPI
publishes the stable, non-yanked 1.182.1 patch. There is no matching public
1.182.1 GitHub tag or release. Comparing hash-verified Linux wheels for 1.182.0
and 1.182.1 finds only the version constant and `semgrep-core` changed within
the installed Python package; distribution metadata adds `certifi>=2026.10.19`.
The changed binary is qualified by the tests below; its implementation is not
inferred from a nonexistent public tag.

Reviewed [tagged release notes through 1.182.0](https://github.com/semgrep/semgrep/blob/240da9f30cd06fb4ee00c2c31c114c1c1f5ee0f4/CHANGELOG.md)
include Python exception-parser corrections, dependency security updates,
telemetry hang prevention, language-parser changes, and QL removal. The local
rules remain pinned and self-contained; Pro, remote configuration, Supply Chain,
and newly supported languages are not qualified by these fixtures.

## Lock and installation contract

Regeneration uses reviewed uv 0.13.5, Python 3.13 and
`--python-platform x86_64-manylinux_2_34 --only-binary :all:`. The generic Linux
selector rejects the published wheel in a wheel-only resolution; explicit
glibc 2.34 matches the wheel floor already used by 1.177.0 and supported by CI.

The complete resolved diff contains only Semgrep 1.177.0 → 1.182.1 and PyJWT
2.13.0 → 2.15.1, with eight and two replacement hashes respectively. Every
replacement hash matches the corresponding PyPI release artifact inventory.
The other 64 requirement blocks are byte-identical. uv strips the redundant
PyJWT extra from the emitted header; cryptography remains locked and installed.
Regeneration against the retained pins reproduces the lock byte-for-byte, and
the installed environment passes `uv pip check`.

Production Semgrep sync now explicitly combines `--require-hashes` with
`--only-binary :all:`. Previously only the hash requirement was explicit for
Semgrep; rumdl already required wheels. No source-build fallback is introduced.
A corrupted Semgrep hash is rejected without installing Semgrep. The temporary
attestation verifier is not added to CI or the evaluation runtime.

PyJWT 2.13.0 matches GitHub-reviewed advisories
[GHSA-pxh4-856f-4h89](https://github.com/advisories/GHSA-pxh4-856f-4h89),
[GHSA-jwrc-g2q2-pq5p](https://github.com/advisories/GHSA-jwrc-g2q2-pq5p),
[GHSA-p4g4-x82p-q773](https://github.com/advisories/GHSA-p4g4-x82p-q773), and
[GHSA-2gx3-rcp4-g85q](https://github.com/advisories/GHSA-2gx3-rcp4-g85q).
The same affected-version query returns no records for 2.15.1. This establishes
dependency-version applicability, not exploitation in this local scan path or
comprehensive vulnerability coverage.

The separate frozen evaluator environment still contains PyJWT 2.13.0 and MCP
1.28.1. This scanner upgrade does not repair those dependencies or establish
their exploitability. Evaluator/Harbor runtime qualification remains separately
tracked in [issue #86](https://github.com/thetechgy/agent-engineering-baseline/issues/86);
its lock and installed inventory are unchanged.

## MCP advisory and execution path

**MCP remains pinned at 1.29.0; this upgrade does not fix
[GHSA-84m7-p3x7-pcfv](https://github.com/advisories/GHSA-84m7-p3x7-pcfv).**
The affected dependency can accumulate sessions when its stateful Streamable
HTTP server is exposed to accepted clients. A supported dependency update
remains upstream work in [Semgrep issue #11992](https://github.com/semgrep/semgrep/issues/11992).
No MCP override, authorization-policy change, or server configuration is applied.

The repository configures no Semgrep MCP server. Quality setup invokes
`semgrep --version`; the pinned evaluator's Code Risk validator invokes
`semgrep scan` with a bundled local rules file, JSON output, metrics off, version
checking disabled, and the existing artifact/test exclusions. Candidate wheel
inspection shows server construction and `mcp.run(transport="streamable-http")`
inside the separate `semgrep mcp` command. Merely importing that command does
not start its server.

Process/socket tracing of real scanner controls and native validation observes
the local scan/core subprocess path, no MCP command, and no `listen` or `accept`
calls. The observed ephemeral `::1` binds match urllib3's import-time IPv6
capability probe; they are not HTTP listeners. The affected session-server path
is not exercised by these CI commands. This conclusion is limited to the
reviewed workflow and tested dispatch; the vulnerable dependency remains
installed, and manually starting MCP or changing dispatch requires reassessment.
If that path becomes reachable, stop adoption and propose supported remediation.

## Before/after scanner evidence

The evaluator labels Semgrep findings **SEMGREP** within **Code Risk Analysis**.
SkillSpector findings belong to **SECURITY**. These observations are separate:

| Observation | 1.177.0 → 1.182.1 |
| --- | --- |
| Six local rules, four positive Python/JS/TS/Bash files | 8 → 8 HIGH findings; all six rule IDs retained |
| Four benign code files | 0 → 0 findings |
| Raw scanned-file sets, finding paths/lines/spans, severity, messages and rule metadata | Identical |
| Positive / benign CLI exit | 1 / 0 → 1 / 0; no reported scan errors |
| Excluded evaluation artifact containing a detection control | Excluded in both versions |
| Missing local rules file / unavailable executable | Incomplete, never passed, in both versions |
| Six-skill catalog Code Risk results | Passed with no executable inputs in either version |
| SkillSpector SECURITY totals, C/H/M/L | 0/4/8/0 → 0/4/8/0 |
| Aggregate catalog totals, C/H/M/L | 1/13/41/34 → 1/13/41/34 |

Every native catalog finding identity, location, message and metadata matches.
SECURITY remains incomplete for five skills and failed for agent-safety; no
existing finding or completeness limitation is suppressed. All six skills have
zero code files under the production Code Risk classifier, so catalog agreement
alone would not establish Semgrep detection. The separate executable fixtures
provide that evidence.

### Retained limitations and failed checks

An initial test expected malformed Python to make the scan incomplete. Both
versions instead list all four malformed files as scanned, emit `errors: []`,
and retain the real finding in a separate valid file. The native status is
failed because of that finding, without an incomplete marker. This is an
unchanged scanner/reporting limitation: a listed file and empty error list do
not prove complete parsing. The failed assertion and both raw reproductions
are retained. A separate real missing-rule-file control verifies failure
handling without changing the evaluator or its completeness policy.

The native/public handoff preserves the Semgrep rule, severity and source line.
Its absolute native file path is redacted by the existing public projection,
leaving the public member unset. An initial assertion expecting a relative
member failed and was corrected to verify this existing privacy boundary;
no path conversion or publication-policy change is introduced.

## Freshness and reproduction

Semgrep alone uses fixed-host, unauthenticated PyPI metadata for version
availability. The collector validates package identity, stable/non-yanked
releases, artifact metadata, latest-version consistency and pin ordering. It
retains the existing shared request/time/response limits, caching, failure
handling and independent GitHub advisory checks. GitHub release-note signals
identify their actual tag and require a tag within the available upgrade
interval: newer than the installed pin and no newer than PyPI's latest release.
Older or not-yet-available GitHub notes cannot turn a PyPI-only patch into a security-update signal.
Reporting links to PyPI and never invents a GitHub
comparison for an untagged patch. Other dependencies retain GitHub discovery.

The live production collector reports 1.182.1 current with no inventory or
discovery errors. With the same controlled 1.182.1 package pin and GitHub
1.182.0 release, the original collector fails with
`release:pin_ahead_of_latest_release`; the updated collector verifies PyPI and
reports current. Offline regressions cover the PyPI-only patch, newer releases,
stale/inconsistent and malformed metadata, yanks/prereleases, source failures,
credential isolation, redirects, request bounds, caching and unaffected tools.

To reproduce, create private disk-backed storage outside the checkout, install
the verified base and candidate through their respective
`.github/scripts/setup-skillevaluator.sh quality` entry points, and retain the
same interpreter, evaluator/scanner pins and input byte manifest. Run
`python -m unittest -v test_semgrep` from `.github/tests` in each tool environment.
Run each native catalog with the workflow's `--external --tiers 1 --no-llm
--no-dedup --continue-on-failure` options, then its strict dataset, `catalog` and
`public-quality` checks. Keep HOME, caches, state and outputs outside the checkout.

Both production installations, paired catalogs, strict datasets and validated
public bundles pass their infrastructure contracts. The four real-scanner
regressions pass in both environments. Quality mode deliberately fails all four
when Semgrep is unavailable; benchmark mode skips the scanner-dependent checks.

The full local run executed 658 tests in 1,658.813 seconds and was **not green**:
15 errors occurred in two unchanged fixtures, plus one gh help-contract skip
(installed 2.103.2 versus recorded 2.102.0). The long disk-backed temporary path
made 14 gh broker subcases exceed Linux's Unix-socket path limit; a direct bind
rejects the representative 120-byte path. A privacy/injection fixture also embeds
its temporary path into evidence text, correctly rejected when that path is
under a home directory. Both unchanged tests pass using a short, private
disk-backed temporary directory. No socket, privacy, assertion, or deadline
policy is changed. The original errors are retained; no whole-suite rerun is
claimed. All 37 freshness tests pass after the final note-attribution correction.
Exact-head hosted results are recorded separately in the PR.

Raw metadata, attestations, verifier lock, commands, exits, inventories, parser
probes, traces and reports remain outside the checkout. No historical evidence,
skills, evaluator/benchmark pins, scanner rules, validation thresholds, deadlines,
CI privileges, generated APM output or publication allowlists are changed.
