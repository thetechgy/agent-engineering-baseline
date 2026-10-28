# Experimental workflow review

| Severity | Findings |
|---|---:|
| Critical | 0 identified |
| High | 0 identified |
| Medium | 0 identified |
| Low | 0 identified |

Scope: `.github/workflows/experimental-native-qualification.yml` and invoked qualification scripts at the tested source.
These are bounded review findings, not a general security certification.

- Only `push` to `experiment/native-codex-qualification` with explicit experimental paths triggers the workflow. No
  privileged PR trigger, schedule, protected environment, deployment or automatic paid dispatch. A branch push works
  without putting `workflow_dispatch` on main.
- `contents: read` ; no repository/provider secrets passed to scripts, no OIDC or write token scope. Checkout disables
  credential persistence. Evaluated containers receive no repository checkout, token, Docker socket, host bind mount or
  provider credential.
- All actions use full SHA pins. Codex package hash, Python base digest, immutable evaluator revisions and unchanged
  frozen locks are checked; dependency setup precedes isolated trials. Setup/build failure remains failure.
- No attacker-derived expression is interpolated into a shell script. The sole workflow expression supplies the trusted
  runner temporary directory to the artifact action. Trial outputs are bounded data and never executed.
- Ubuntu hosted runner, serialized concurrency, 25-minute job/20-minute execution step; each standalone trial has 1 GiB
  memory, 2 CPU, 128 PID limit and bounded subprocess deadlines. No privileged containers, added capabilities or
  unconfined seccomp. Outer trial network is `none` ; local provider binds loopback. Unsupported inner sandbox is
  reported rather than weakening runtime policy.
- Always-run export validates regular/no-link evidence, fewer than 1024 paths and less than 16 MiB before uploading only
  the validated directory. Retention 14 days; important originals are separately preserved in Git with authenticated run
  metadata and archive digests. No cache or secondary publication pipeline.
- Exact trial containers are removed in `finally` and absence verified. Hosted runner teardown is an additional boundary
  after catastrophic interruption; it is not claimed as a qualified production gh initializer cancellation test.
