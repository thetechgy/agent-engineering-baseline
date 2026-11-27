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

Relative bind paths can qualify. A temporary overlay at the data directory
fails. Custom overlay backing and separate Quadlet volume dependencies leave
coverage unmeasured when only the container unit is available. The PostgreSQL
image volume shadows a mount at its parent directory unless the unit disables
image volumes or supplies an explicit mount at or below the image volume.

## Shared-file changes

Counts are insertions and deletions against the verified base. The Podman
adapter, definitions, controls, and verifier are task-owned. This edit log is
the measurement record.

| Shared file | Added | Removed | Class | Why the engine needed it | Could be data |
| --- | ---: | ---: | --- | --- | --- |
| `.github/scripts/evaluation_tasks.py` | 5 | 1 | Runner-coupled | Admit the exact Podman definition path and load its task-owned adapter. | Adapter identity and path could be registered data. The adapter still owns staging and verifier expectations. |
| `.github/scripts/evaluation_campaign.py` | 1 | 1 | Runner-coupled | Select the successor source identity for new campaign executions. | Yes. The registry could resolve the active identity. |
| `.github/scripts/evaluation_campaign_selection.py` | 2 | 0 | Runner-coupled | Route the new selector to its own registry so the Pester registry's historical digest stays stable. | Yes. Reviewed registry locations could be registered data. |
| `.github/scripts/skill_evidence.py` | 62 | 15 | Evidence and registry | Resolve the pinned dataset path and digest. Choose Podman's authored skill root and existing case inputs for the capture guard. Check local ownership and the complete inventory source identity. Take the Podman grader verdict from its verified sidecar. Load the appended source and scoring registrations. | Dataset, fixture, source and sidecar identities could be data. Digest and provenance validation stay executable. |
| `.github/evals/source-v40.json` | 474 | 0 | Evidence and registry | Register the Podman metric and two profiles. Bind 86 campaign source successors and one Pester effectiveness source successor. | Yes. The successor records could be produced from the reviewed source manifest. |
| `.github/evals/source-v41.json` | 365 | 0 | Evidence and registry | Preserve source-v40 results and bind the successor source identities after registering Podman in the scored probe. | Yes. The successor entries are manifest data. |
| `.github/evals/source-v42.json` | 363 | 0 | Evidence and registry | Bind revised grader and campaign inputs while preserving earlier qualification identities. | Yes. The successor entries are manifest data. |
| `.github/evals/source-v43.json` | 363 | 0 | Evidence and registry | Bind the image-volume grader correction and preserve source-v42 for replay. | Yes. The successor entries are manifest data. |
| `.github/scripts/codex_pilot_probe.py` | 1 | 1 | Evidence and registry | Admit Podman to the fixed scored containment probe. The existing assertions run for every admitted skill. | The eligible skill names could be registered data. |
| `.github/scripts/skill_analysis.py` | 1 | 1 | Report | Recognize the successor to the existing Pester effectiveness and CLI pilot profiles. | Yes. Report applicability could follow a registered profile family. |
| `.github/scripts/skill_report.py` | 3 | 3 | Report | Preserve Pester effectiveness and CLI pilot rendering for the successors where the renderer lists profile IDs. | Yes. Report applicability could follow a registered profile family. |
| `.github/scripts/skill_reports.py` | 8 | 6 | Report | Preserve only validated SHA-256 values when the existing redactor masks names of Podman support files. The existing gh publication rule stays in force. | The eligible capture profiles could be data. Typed validation and redaction remain executable. |
| `.github/workflows/evaluation-campaign.yml` | 6 | 2 | Workflow and orchestration | Add the selector and route it through oracle and probe qualification. The new campaign has no experiment preparation or live protocol. Run the qualification contract tests. | Yes. The reviewed selector and available workflow phases could come from registration. |
| `.github/scripts/qualify_model_callers.py` | 4 | 3 | Workflow and orchestration | Add the new selector registry to the wire-level check run by Validate. | Yes. The approved registry list could be read from the same registration. |
| `.github/tests/test_judge_calibration.py` | 1 | 1 | Tests | Check the existing profiles against the current source identity. | The expected successor can be resolved from reviewed registration. |
| `.github/tests/test_pester_return_contract.py` | 15 | 0 | Tests | Exclude only the exact Podman registration, import and path addition from the historical Pester hash. | The expected registration could be data. The original hash check stays executable. |
| `.github/tests/test_podman_storage.py` | 163 | 0 | Tests | Check the mount controls, separate inventory and dataset identities, forged capture rejection, and source successors. | The controls are data. The negative checks exercise the admission code. |

| Class | Files | Added | Removed |
| --- | ---: | ---: | ---: |
| Runner-coupled | 3 | 8 | 2 |
| Evidence and registry | 6 | 1628 | 16 |
| Report | 3 | 12 | 10 |
| Workflow and orchestration | 2 | 10 | 5 |
| Tests | 3 | 179 | 1 |
| **Total** | **17** | **1837** | **34** |

Runner-coupled changes account for 10 of 1871 changed lines. The runner
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

## Item 9 scored comparison preparation

The scored selector is `podman-storage-current-v1-1720-sol62`. Its controls
and scored rehearsal use Codex CLI 0.172.0, SkillEvaluator 1.2.1, Harbor
0.25.0, and Python 3.14.10. The task-owned rule and protocol declare one
six-slot pair at GPT-6.2 Sol High. Source and registry bindings preserve the
earlier selection. These counts cover preparation through the paid gate.

| Shared file | Added | Removed | Class | Why the engine needed it | Could be data |
| --- | ---: | ---: | --- | --- | --- |
| `.github/evals/campaigns/codex-1720-scored.json` | 11 | 0 | Evidence and registry | Pin the reviewed Codex 0.172.0 scored runtime. | Already data. |
| `.github/evals/codex-execution-1720-scored.json` | 32 | 0 | Evidence and registry | Bind the current CLI and helper hashes and the existing scored execution policy. | Already data. |
| `.github/evals/source-v52.json` | 413 | 0 | Evidence and registry | Admit the Podman comparison and controls and bind the source changes for the existing campaigns and pilot profiles. | Already data. The digests can be derived from reviewed inputs. |
| `.github/scripts/codex_pilot_agent.py` | 3 | 3 | Evidence and registry | Run the scored request and accounting fixture for the new CLI profile. | The profile capability could be data. |
| `.github/scripts/evaluation_campaign.py` | 1 | 1 | Runner-coupled | Select the new source identities for current execution. | The active identity could be registered data. |
| `.github/scripts/evaluation_campaign_protocol.py` | 2 | 2 | Runner-coupled | Admit the reviewed probe-only descriptor substitution for the new scored profile. | The profile capability could be data. |
| `.github/scripts/evaluation_campaign_selection.py` | 2 | 1 | Runner-coupled | Resolve the two new Podman definitions through the task-owned selection file. | The registry location could be data. |
| `.github/scripts/evaluation_codex.py` | 5 | 5 | Runner-coupled | Apply the scored runtime and request checks and label native events with the emitting CLI. | The eligible profiles could be data. The event and request checks remain executable. |
| `.github/scripts/skill_reports.py` | 6 | 4 | Report | Preserve only authenticated Podman capture digests under the latest redactor. | The validated campaign registration already supplies the owner. |
| `.github/scripts/evaluation_evidence.py` | 5 | 0 | Evidence and registry | Resolve the evaluator owner selected by a campaign profile. | The owner identity comes from registration. |
| `.github/scripts/evaluation_runtime.py` | 11 | 2 | Runner-coupled | Admit and bind the current scored CLI and evaluator owner. | Runtime capabilities and owning setup could be registered data. |
| `.github/scripts/evaluation_tasks.py` | 9 | 2 | Runner-coupled | Admit the exact comparison and control paths. | The adapter and allowed paths could be data. |
| `.github/scripts/evaluator_profiles.py` | 2 | 2 | Evidence and registry | Resolve the latest installed evaluator build by its exact pins. | Already backed by pinned profile data. |
| `.github/scripts/setup-campaign-authentication.sh` | 7 | 2 | Workflow and orchestration | Use the repository’s current native evaluator setup for the selected owner. | The setup profile could be registered data. |
| `.github/scripts/skill_evidence.py` | 38 | 17 | Evidence and registry | Bind the new scored profiles and use the selected evaluator in native and public admission. Preserve retained Pester inputs. | Profile and retained input identities could be data. |
| `.github/tests/test_judge_calibration.py` | 1 | 1 | Tests | Check the historical scoring profiles against their current source successors. | The successor could be resolved from registration. |
| `.github/tests/test_pester_return_contract.py` | 11 | 3 | Tests | Project out only the reviewed Podman registration before checking the frozen Pester hash. | Reviewable registration data could avoid this source projection. |
| `.github/tests/test_podman_storage.py` | 79 | 9 | Tests | Check matching, grading, latest-runtime staging, and source and rule bindings. | The verdict fixtures are data. Admission checks stay executable. |
| `.github/workflows/evaluation-campaign.yml` | 8 | 6 | Workflow and orchestration | Offer the scored Podman selection through the existing preparation and gate and install its required uv version. | The workflow choices could be derived from registration. |

| Class | Files | Added | Removed |
| --- | ---: | ---: | ---: |
| Evidence and registry | 7 | 504 | 22 |
| Runner-coupled | 6 | 30 | 13 |
| Report | 1 | 6 | 4 |
| Workflow and orchestration | 2 | 15 | 8 |
| Tests | 3 | 91 | 13 |
| **Total** | **19** | **646** | **60** |

Runner-coupled changes account for 43 of 706 changed lines.

## Item 9 stopped comparison and report

The first live dispatch stopped after two verifier grades when slot 2 failed
its native observation. This reporting change adds the stop card and the
byte-preserved partial bundle. The results did not require runner or grader
changes. The table counts additional edits to shared files since the execution
revision `d31f7dc`.

| Shared file | Added | Removed | Class | Why it changed | Could be data |
| --- | ---: | ---: | --- | --- | --- |
| `.github/evals/REPORT-EVIDENCE.md` | 9 | 4 | Report | Include the retained input in the report command and explain the stopped result. | The input list could be part of the manifest. |
| `.github/scripts/skill_report_decisions.py` | 28 | 1 | Report | Show inconclusive live evidence only when the admitted witness records the stated stop. | The finding notes and citations are data. The stop check remains executable. |
| `.github/tests/test_skill_report_decisions.py` | 43 | 17 | Tests | Cover the stopped card and reject a mismatched stop reason. Include its retained input in the renderer tests. | Test fixture inputs and evidence identities could be registered. |
| `docs/evaluations/report-decisions.json` | 28 | 0 | Report | Cite the stopped record, runtime and earlier case 2 evidence. | Already data. |
| **Total** | **108** | **22** | | | |

The report phase changed four shared files and zero runner-coupled lines.
Totals exclude the task-specific receipt and bundle and this edit log.

## Item 10 onboarding plan

| Logged edit | Item 10 treatment |
| --- | --- |
| `evaluation_tasks.py`, `evaluation_campaign_selection.py`, `qualify_model_callers.py` | Resolve reviewed task-family registrations, exact definitions, and selector registry paths from data. Task adapters still own staging, grading, and containment expectations. |
| `evaluation_campaign.py`, `source-v40.json` through `source-v43.json`, `source-v52.json`, `test_judge_calibration.py` | Select the active source version from reviewed data. Register source successors without changing earlier identities. Keep registry consolidation in item 12. |
| `skill_evidence.py`, `skill_reports.py` | Bind the dataset, local skill capture, and typed redaction exception to reviewed campaign registration. Keep provenance, native outcome consistency, and digest validation in code. |
| `codex_pilot_probe.py` | Keep the allowlist for the fixed in-container probe. Adding a new subject to that probe is a review of what runs inside the container. |
| `evaluation-campaign.yml` | Keep the fixed dispatch choices, runtime setup and paid gates. Offering a new hosted selector requires an explicit workflow edit and review. |
| `codex-1720-scored.json`, `codex-execution-1720-scored.json`, `codex_pilot_agent.py`, `evaluation_campaign_protocol.py`, `evaluation_codex.py`, `evaluation_evidence.py`, `evaluation_runtime.py`, `evaluator_profiles.py`, `setup-campaign-authentication.sh` | Reuse the existing runtime pins and owner for a new skill. A new native CLI or evaluator version still needs its own capability, wire, and setup qualification. Those item 9 edits were for a runtime upgrade. |
| `skill_analysis.py`, `skill_report.py` | Keep legacy pilot rendering and scoring applicability with their existing evidence contracts. New campaign cards use the shared decision report. |
| `REPORT-EVIDENCE.md`, `skill_report_decisions.py`, `test_skill_report_decisions.py`, `docs/evaluations/report-decisions.json` | Declare the report's retained inputs in its manifest. The stopped card uses the generic scheduler witness check. Preserve explicit input usage and existing replay assertions. |
| `test_pester_return_contract.py`, `test_podman_storage.py` | Preserve the frozen hash and negative admission controls. Add a fixture family through the reviewed data path and exercise the shared loader without patching its source. |
