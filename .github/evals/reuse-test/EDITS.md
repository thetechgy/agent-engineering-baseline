# Podman reuse test

The shared campaign accepted a separate task adapter, grader, and controls for
Podman case 2. The authored source and ten-case inventory suite remain in
`.apm/skills/podman/`. The campaign dataset lives under
`.github/evals/podman/storage/` and has its path and digest registered
separately.

The check reads the submitted PostgreSQL 18 Quadlet. The covered control mounts
the named volume at `/var/lib/postgresql`. The weak control uses the vendor
destination, `/var/lib/postgresql/data`, which leaves the default data directory
outside that mount. A working explicit data-directory override can pass. The
check measures configuration coverage. In two earlier paired benchmarks both
arms corrected the mount, so a future scored comparison is expected to tie.
[Prior Podman review](https://github.com/thetechgy/agent-engineering-baseline/pull/160).

## Shared-file changes

Counts are insertions and deletions against the verified base. The Podman
adapter, definitions, controls, and verifier are task-owned. This edit log is
the measurement record.

| Shared file | Added | Removed | Class | Why the engine needed it | Could be data |
| --- | ---: | ---: | --- | --- | --- |
| `.github/scripts/evaluation_tasks.py` | 5 | 1 | Runner-coupled | Admit the exact Podman definition path and load its task-owned adapter. | Adapter identity and path could be registered data. The adapter still owns staging and verifier expectations. |
| `.github/scripts/evaluation_campaign.py` | 1 | 1 | Runner-coupled | Select the successor source identity for new campaign executions. | Yes. The registry could resolve the active identity. |
| `.github/scripts/evaluation_campaign_selection.py` | 2 | 0 | Runner-coupled | Route the new selector to its own registry so the Pester registry's historical digest stays stable. | Yes. Reviewed registry locations could be registered data. |
| `.github/scripts/skill_evidence.py` | 54 | 15 | Evidence and registry | Resolve the pinned dataset path and digest. Choose Podman's authored skill root and existing case inputs for the capture guard. Check local ownership and the complete inventory source identity. Take the Podman grader verdict from its verified sidecar. Load the appended source and scoring registrations. | Dataset, fixture, source and sidecar identities could be data. Digest and provenance validation stay executable. |
| `.github/evals/source-v40.json` | 474 | 0 | Evidence and registry | Register the Podman metric and two profiles. Bind 86 campaign source successors and one Pester effectiveness source successor. | Yes. The successor records could be produced from the reviewed source manifest. |
| `.github/evals/source-v41.json` | 365 | 0 | Evidence and registry | Preserve source-v40 results and bind the successor source identities after registering Podman in the scored probe. | Yes. The successor entries are manifest data. |
| `.github/scripts/codex_pilot_probe.py` | 1 | 1 | Evidence and registry | Admit Podman to the fixed scored containment probe. The existing assertions run for every admitted skill. | The eligible skill names could be registered data. |
| `.github/scripts/skill_analysis.py` | 1 | 1 | Report | Recognize the successor to the existing Pester effectiveness and CLI pilot profiles. | Yes. Report applicability could follow a registered profile family. |
| `.github/scripts/skill_report.py` | 3 | 3 | Report | Preserve Pester effectiveness and CLI pilot rendering for the successors where the renderer lists profile IDs. | Yes. Report applicability could follow a registered profile family. |
| `.github/scripts/skill_reports.py` | 8 | 6 | Report | Preserve only validated SHA-256 values when the existing redactor masks names of Podman support files. The existing gh publication rule stays in force. | The eligible capture profiles could be data. Typed validation and redaction remain executable. |
| `.github/workflows/evaluation-campaign.yml` | 6 | 2 | Workflow and orchestration | Add the selector and route it through oracle and probe qualification. The new campaign has no experiment preparation or live protocol. Run the qualification contract tests. | Yes. The reviewed selector and available workflow phases could come from registration. |
| `.github/scripts/qualify_model_callers.py` | 4 | 3 | Workflow and orchestration | Add the new selector registry to the wire-level check run by Validate. | Yes. The approved registry list could be read from the same registration. |
| `.github/tests/test_judge_calibration.py` | 1 | 1 | Tests | Check the existing profiles against the current source identity. | The expected successor can be resolved from reviewed registration. |
| `.github/tests/test_podman_storage.py` | 122 | 0 | Tests | Check the controls, separate inventory and dataset identities, forged capture rejection, and source successors. | The controls are data. The negative checks exercise the admission code. |

| Class | Files | Added | Removed |
| --- | ---: | ---: | ---: |
| Runner-coupled | 3 | 8 | 2 |
| Evidence and registry | 4 | 894 | 16 |
| Report | 3 | 12 | 10 |
| Workflow and orchestration | 2 | 10 | 5 |
| Tests | 2 | 123 | 1 |
| **Total** | **14** | **1047** | **34** |

Runner-coupled changes account for 10 of 1081 changed lines. The runner
comparison stays after items 10 through 12.

The five earlier adapters share scheduling, arm matching, and grading
transport. Their task-owned methods still differ. Pester stages test subjects
and reference and mutant implementations. The gh adapters provision a broker
and evaluate the submitted operation trace. Podman submits one configuration
file. Their selection metadata can be data. A common loader alone would still
need task-owned staging and validation.

## Qualification entry points

Use the pinned SkillEvaluator 0.8.0 and Harbor 0.24.0 environment with the
verified Compose and APM tools. Set the output to a new persistent directory
outside the checkout. The named selection runs both the oracle and real
non-forwarding CLI probe.

```sh
"$SKILL_CURRENT_PYTHON" -B .github/scripts/evaluation_campaign_selection.py qualify \
  --campaign podman-storage-v1-1710-sol62 --output "$REUSE_OUTPUT"
```

For hosted qualification dispatch `evaluation-campaign.yml` with
`campaign=podman-storage-v1-1710-sol62` and leave both `allocation` and
`preparation_artifact` empty.
