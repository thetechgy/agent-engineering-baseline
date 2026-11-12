# Issue #95: APM 0.35.1 refresh

The existing reviewed updater generated this refresh from main `f1867ba` in
[run 43328758922](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43328758922).
Both generation and publication succeeded. It reuses draft
[PR #125](https://github.com/thetechgy/agent-engineering-baseline/pull/125).
No installed skill was hand edited.

The active bootstrap CLI advances from 0.35.0 to
[0.35.1](https://github.com/microsoft/apm/releases/tag/v0.35.1).
All three platform archives matched their official checksum sidecars; the
maintained checksum file records archive and extracted executable hashes.
Generation, frozen restoration, compilation, deployment audits, packaging,
Pester, analyzer and lint checks passed in the updater's Linux environment.
The separate PR validation must establish native candidate installation and
lifecycle behavior on latest stable PowerShell on Windows and on Bash/Linux.
The updater's successful reviewed-CLI regeneration alone does not establish
those candidate-binary guarantees. Final checks are recorded on the PR.

The source lock updates branch-tracking dependency revisions. The only deployed
skill-content changes clarify how Dependabot discards added commits during
rebasing when `[dependabot skip]` is present. They add no executable or tool
access. The msgraph source revision changes without changing deployed file
hashes relative to current main. The gh, git-commit, local Pester skill,
frozen Pester candidate and experiment inputs retain their bytes.

The release includes scoped-install cache/receipt recovery, Windows activation
retry and symlinked-lock rejection changes. Native bootstrap checks remain
necessary; no ownership, archive validation, MCP allowlist or sandbox boundary
is relaxed here.

## Security applicability

[GHSA-xmj3-9gf7-h52w](https://github.com/advisories/GHSA-xmj3-9gf7-h52w)
affects setuptools `>=38.2.2,<84.1.0` on the Windows legacy
`Wheel.install_as_egg` namespace-package conversion path. Released APM 0.35.0's
lock contains setuptools 83.0.0; 0.35.1's lock contains the fixed 84.1.0.
That is an affected bundled-version signal. Reachability through this
repository's APM archive/bootstrap and native dependency installation has not
been established, so this is not a confirmed exploitable APM vulnerability.
The bootstrap consumes hash-verified release executables, not a host pip
installation or an independently overridden setuptools version.

The historical locks and qualification evidence remain unchanged. No evaluator
promotion, inference, paid judge, protected gate, deployment or merge is part
of this refresh.

## Source-policy compatibility

Initial final-head CI rejected the refreshed hardening source revision before
native execution: the gh policy still required 61fa1fa while APM's reviewed lock
resolved 30a0d74. All deployed hardening file hashes are identical to main.
The active policy now records the actual reviewed source revision; ownership
and full deployed-file verification remain required. Historical public policy
fingerprints retain their original revisions. Pester reporting's new v14 source
identity binds these shared helper changes without changing any older profile,
grading, task input, runtime pin, candidate or experiment result.
The failed run 43330324946 and available validation diagnostics remain retained.
Superseded validation is inconclusive; only final-head replacement checks count.

Campaign source-v5 identities bind the changed shared reporting files; all prior
entries, frozen definitions, candidate content and expected grades remain unchanged.
No closed experiment, model setting or allocation is updated.
