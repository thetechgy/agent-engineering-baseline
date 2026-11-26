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

`private-review-101.zip` holds the fixed public source for the
`review-101-v1` private review profile. It contains the regular tracked
files under `.github/scripts` and `.github/evals` from
`c1d0f61d29e1a2dfad964a4406964ad068cd0a5b`. The launcher verifies the
archive SHA-256 `376fe25f26672a98a878c6d946a7700a6f463d5ae6d0599fb2b8da7f05c5ba9d`
before unpacking. The archived files supply the evaluator and campaign
registries used when reconstructing contexts. Review creation and offline
attachment validation use the same snapshot.

`private-review-101-v2-overlay.zip` binds the ten updated source and registry
members from `86899d9356c94cead240ec14d8592b53db556b89` to profile
`review-101-v2`. The archive SHA-256 is
`73c2dc9059c0b8830a21f611b70fbff00d14ddca8272999c570e743414e9d2eb`.
The launcher verifies both archives and overlays these members in a new
temporary source directory. The original archive continues to own every
`review-101-v1` attachment.

`private-review-101-v3-overlay.zip` binds 12 reporting and registry members
from `cbfec6eec2dfce00b2234624a62cf88e88014780` to `review-101-v3`. The
archive SHA-256 is
`9e28a852608b8249d390c4521c58653a05695d66ee173a96f0906caf549fba60`.
The launcher verifies all three archives for v3. Earlier review profiles
select their own verified source and registry.

`private-review-101-v4-overlay.zip` binds 12 report reader and registry members
from `af379d06d08d621910a1abe2cce1bb04e12a72c8` to `review-101-v4`.
The archive SHA-256 is
`4d2dfd9e49bfc1d253d25621cf8a38023469fbaabd4b1ac16299b47d8476eafe`.
The v4 reader recognizes the separately recorded direct-tool and released
diagnostic evidence. The prior profiles keep their original source
snapshots and validator identities.

`private-review-101-v5-overlay.zip` binds eight reporting and registry members
from `f2d5d766ce5149dcc80dc851e64895c442d4e912` to `review-101-v5`. Its
SHA-256 is `21ac911579c5f4ccfb3d11f3db1bf2b1e5fc748a44e5f64650d1fa06659e206a`.
The v5 producer and validator use the released benchmark reader and source-v48
registry. Profiles v1 through v4 keep their original snapshot chains.
