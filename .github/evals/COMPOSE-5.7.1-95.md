# Issue #95: Compose 5.7.1

The shared operator plugin advances from 5.7.0 to
[5.7.1](https://github.com/docker/compose/releases/tag/v5.7.1), using the official
Linux executable digest `af426722a8af5de812fcee30cc1c39f0639f5f723cbadefb25e5d4db054064cf`.
It includes OCI manifest digest verification, interrupted-cache consistency,
selected-service image preservation and bounded event-stream fixes.
The repository uses reviewed local Compose files; the OCI notes alone do not
establish an exploitable repository vulnerability.

The checksum-first installer, private plugin configuration and owned cleanup
remain unchanged. The active benchmark policy records 5.7.1; historical records
keep their exact recorded versions and fingerprints. Compose is an operator
dependency, separate from the frozen agent/PowerShell/Pester/model profiles.
No task, scoring, skill, candidate, experiment or sandbox change is made.

Eight setup/cleanup and rejection tests pass locally. Docker is unavailable on
this workstation; native retained and opt-in Harbor boundaries require the final
combined draft's credential-free hosted checks. Successful local mocks do not
establish native execution. Final receipts and limitations are recorded on the PR.
