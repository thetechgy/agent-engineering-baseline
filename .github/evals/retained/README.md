# Retained offline comparison inputs

These receipts were captured at repository revision
`58cb9698543c546173501887254dc7989d2db396`. Neither receipt grants
execution or publication approval.

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

Exact historical execution uses an explicit checkout of the producing
revision and the retained setup at that revision.
