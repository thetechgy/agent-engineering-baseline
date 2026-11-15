# Podman negative-selection dataset correction

Main was verified at PR #139's merge `a50f693df6f024a6b8063b41e1b6dc2ac40e3f7a`,
with no intervening changes. Data-only reporting/orchestration already uses
0.9.0. Static quality and benchmarks retain their existing owners.

Only entry 8's `expected_output` changes:

- Before: “The Podman skill does not dominate a Docker-only request unless the user explicitly asks to migrate it to Podman.”
- After: “A response scoped to Docker Swarm stack review and Docker daemon.json tuning, without unsolicited
  migration to Podman or Quadlet or application of Podman-specific networking or systemd assumptions.”

The prompt, id, files, assertions, `expected_skill: null` and `should_trigger: false`
are identical. This corrects evaluation design; it is not evidence of a skill
weakness. Skill selection remains separate from task quality. An absent-skill
agent can meet these same criteria; identifying, reading or mentioning a skill
alone earns no task-quality credit. No technical requirement or preference is added.

## Criterion review

A Docker-focused response that reviews the supplied Swarm configuration and
`daemon.json` within Docker's scope satisfies this criterion, whether or not
it accessed a skill. No stack/config content is supplied by this dataset case,
so asking for the missing configuration is compatible with the task; the revision
adds no fixture or invented tuning requirement.

A response that replaces the requested review with an unsolicited Podman/Quadlet
migration fails both the outcome criterion and the unchanged first assertion.
Applying Podman-specific networking or systemd assumptions fails the unchanged
second assertion. These are manual criterion reviews, not executed model/judge
verdicts. The executable regression exercises the real strict validator and
case preservation; it does not pretend to judge these responses through word matching.

## Deployment and historical identity

Authored input is `.apm/skills/podman/evals/evals.json`. The repository-pinned
APM 0.35.1 CLI was acquired by `scripts/bootstrap.sh --cli-only`; native
`apm install --frozen --trust-bin` deploys local skills, then
`apm compile --target codex,copilot` compiles instructions. As in
`scripts/apm_regeneration.py`, deployment starts without preexisting generated
skill files. The first attempt against the fresh Git checkout refused missing
local ownership receipts; its log and the original deployment were preserved.
The clean deployment succeeded. Only the authored and deployed dataset differ
within skill content, byte-identically. `SKILL.md`, supporting guidance, other
cases/skills, dependency pins and generated instructions remain unchanged. Pinned `apm install
--trust-bin` (without update/refresh) regenerates the current local deployment
ledger: only the two dataset hash entries and generation timestamp change in
`apm.lock.yaml`. Frozen install alone retained the old local hash; hosted audit
caught that drift. The regenerated ledger is then checked through the full isolated
frozen regeneration/audit entry point. Historical lock bytes remain in Git.

[Receipt](receipt.json) records both byte hashes and the unchanged pinned runtime.
Future native evaluations retain the existing authored digest, staged snapshot
digest and case-cohort provenance mechanisms in `skill_evidence.py`; no hash
allowlist or frozen profile is rewritten. Different expected outcomes produce a
new dataset identity and cannot be pooled as matched historical criteria.

The original dataset remains at the verified base commit. The original
[#137 strict receipt](../evaluator-090-adoption/receipt.json), captured snapshots,
grades, [historical replay route](../../../.github/evals/REPORT-EVIDENCE.md)
and original owning interpreters remain intact. No retained work was rescored.

## Qualification

The same pinned Python 3.14.10 / SkillEvaluator 0.9.0 offline-v3 owner rejects
the original case with exit 1 and the exact entry 8 skill-use warning, then
accepts the revised dataset with exit 0. The adoption regression repeats both
CLI calls against pinned original bytes and current bytes, compares every other
field/case, and verifies deployed equality. The original #137 receipt remains failed.

The existing `qualify_scanners.py --evaluator-next` path runs all eight scanner
controls and the complete six-skill repository catalog, strict-validates every
authored static dataset, collects native reports, normalizes/projects public
evidence and renders consolidated HTML. No case or validation rule is excluded.
The catalog contains one authored dataset (Podman, ten cases); its strict check
passes. Native catalog exit 1 reflects retained advisory findings, while the
collection contract and public projection pass. There are 90 findings, including
13 SECURITY findings (three agent-safety, ten Podman). Missing-reference counts
remain a11y 3, ansible 1, Podman 3 and powershell-pester-6 6; those four skills
retain incomplete scanner coverage. All eight clean/bad/incomplete/error scanner
controls pass, distinguishing scanner faults from catalog findings. All six public
records reproduce exactly, as do the current and unchanged historical #137 HTML.
Final results and report reproduction hashes are recorded in the receipt; exact
final-revision selected CI and artifact receipts belong to the PR description.

Strict admission establishes dataset admissibility, not model-judge accuracy or
skill effectiveness. Known scanner findings, missing references and incomplete
coverage remain visible. No credentials, inference, judges, allocation, benchmark,
Pages publication or production runtime change is part of this qualification.

**One next action:** decide separately whether to migrate the complete static-quality
consumer to pinned 0.9.0 after reviewing this correction and its qualification.
