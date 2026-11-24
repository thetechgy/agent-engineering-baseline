# Retained offline comparison inputs

These receipts retain their original evaluator and report identities. The
standard score and Podman inputs were captured at
`58cb9698543c546173501887254dc7989d2db396`.

- `standard-scores-030.json` records the 73 synthetic inputs defined by
  `evaluator_scoring_compatibility.py` at that revision (source SHA-256
  `fe763a9520fd99dec63519ef8ff91825e8b1c9b2005c4fa8987b0bb24c8941c8`).
  The original subprocess verified the SkillEvaluator 0.3.0 lock, scorer and
  verifier sources. Its receipt records the actual versions and observed
  scores. The comparison authenticates the complete receipt before use.
- `podman-public-030.json` is the canonical projection from the existing
  `.github/tests/fixtures/skill_evidence/podman-native` retained extraction.
  Its extraction manifest has SHA-256
  `4f8ab06638a37c970dfd5a97f057da8505a0b57767a332b41d4e0c2c8e8066ea`.
  The original owner performed native admission, projection and capture
  rechecks. The current comparison authenticates and validates the public
  record while preserving all its original score and producer fields.
- `pester-public-030.zip` is the original public oracle upload from artifact
  `14905952006`, attempt 1 of Validate run `45360027374` at head
  `aa2599f078202cd9f1918e889d72adaef84642cf`. Its GitHub-reported archive
  SHA-256 is `4adddcd1501c1613675631e0e2a51413658d6ac1f59ef3318dba5f04a2a981e8`.
  The producing job passed both arms using SkillEvaluator 0.3.0 and Harbor
  0.13.2. The original report retains 52 outcomes and records incomplete
  coverage for the intentionally unscoreable controls. The adoption qualifier
  copies that public projection byte for byte after verifying the archive and
  the report identity. [Original GitHub artifact](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/45360027374/artifacts/14905952006)

Exact historical execution uses an explicit checkout of the producing
revision and the retained setup at that revision.
