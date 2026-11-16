# Permission successor qualification

Base: merged #144, `6d063563746651a7e70a570007ed4c23eee9b9d9`.
The [contract/matrix](CONTRACT.md) was written before successor result inspection.
[Local receipt](local-controls.json): 34 independent synthetic trajectories ran
through trusted native staging and the generated isolated native grader. They are
not observations of model behavior or a new container-lifecycle qualification.
No historical trace was used as a replacement control or rescored.

The first staging attempt correctly rejected workstation APM 0.35.0. Retrying with
an existing pinned APM 0.35.1 exposed shared-object mutation in the deliberate
invalid-metadata fixture; the correction copies metadata before injecting it.
The first isolated native matrix then exposed a null observation normalized to an
empty string. The successor now checks original call/result linkage and string
content before interpreting normalized calls. The repeated matrix passes all 34
expected outcomes. Failed attempts are retained separately, not overwritten.

Hosted native oracle/CLI qualification, authenticated artifacts, cleanup, report
reproduction and final required/change-selected CI are pending. Their final
revision and receipts will be recorded here before delivery. No pending check is
claimed passed. Local Docker is unavailable; the existing credential-free hosted
route owns container qualification. Non-forwarding CLI controls use the pinned
CLI with a local stub, not a provider or model judge.
