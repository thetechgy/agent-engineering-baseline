# Trusted task metadata and live launch construction correction

This corrects the composition defect observed in
[stopped run 43762601398](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43762601398).
Starting PR/check-out head was verified as `3bc9cbf89c9e8538ea5df48d22e2d85e4a5a957c`.
The [original execution receipt](execution/EXECUTION.md), allocation closure, raw
outcomes and published report remain unchanged. The old allocation is closed;
this correction grants no paid dispatch, protected approval or new allocation.
[PR #143](https://github.com/thetechgy/agent-engineering-baseline/pull/143) records
final executable revision, selected CI, hosted preparation and fresh-consumption
run/artifact identities and digests. Only terminal receipts at that exact source
qualify it; a later source or merge needs new credential-free qualification.

## Trust boundary

The parent live gate still rejects ambient task metadata and unknown `AEB_*`,
probe/control flags and provider overrides. Authorization, exact source binding,
first-attempt/replay restrictions, expiration and allocation claiming remain with
the existing protocol. Real provider credentials are never used by qualification.

After trusted staging and comparison with authenticated preparation, the task
adapter builds a host-only launch context. For gh it verifies the existing backend
manifest's content-addressed filename, owner/private permissions, initializer
payload digest, exact native task identity and complete captured task inventory.
The path must be the selected campaign's private `operator` directory, outside all
staged/agent-visible inputs; its contents and checksum must agree with the trusted
staging capture. The context binds the selected task/arm and manifest seal. The
parent validates it **before attaching the provider key** to the child environment.

One shared `construct_launch` function builds both the actual production TrialConfig
and final child environment. The context travels in that protected host configuration;
it cannot come from an ambient variable. The child live constructor keeps its guard,
revalidates the receipt and task-owned context against the fixed live root and
selected deployment, then accepts only the metadata names returned by that successful
adapter validation. A valid variable name alone is insufficient. Gh-specific metadata
verification stays in `GhFixture`; the shared launcher has no gh case exception.
The backend independently revalidates at its existing startup consumer.

This relies on the existing trusted host workflow/staging boundary. It does not
protect against a compromised host that can rewrite the configuration, captured
staging evidence and manifest. Agent containers receive no host mount or operator
manifest; no isolation protection is relaxed.

## Failing before and passing after

[The retained failing-before receipt](launch-failing-before.json) used trusted live
staging, the frozen final composed environment and the released Harbor `Trial.create`
path into `CampaignCodex.__init__`. Both current and absent deployments reproduced
`Live runtime requires protected workflow; overrides refused`. Test-only receipts
were used; no allocation was claimed, no agent container started and no provider
interaction occurred. This revision had the same executable code as failed paid
revision `b3e190d143e2cbc7b44938d4d01b690dc9f67c10`; its intervening commit was report-only.

The corrected regression uses the shared production launch builder and actual
Harbor agent factory, live guard, `CampaignCodex` and upstream Codex initialization.
It stops immediately after real agent initialization, before environment construction.
A separate test fixture executes the **actual** gh startup consumer with the real
staged task/trial paths and composed environment, stopping at its first secure
container-start call. The fixture is not an initialized environment. No readiness
result is fabricated and no kernel, network, mount or sandbox check is disabled in
production. Existing native preparation controls continue to qualify full container
startup, non-forwarding CLI execution, lifecycle, interruption and cleanup.

Both deployments must initialize with the held CLI/model/provider settings and
reach manifest consumption. Representative negative controls cover missing manifest,
a valid manifest substituted outside the operator location, tampered content,
wrong task binding and a correctly sealed but wrong task population; unknown `AEB_*`,
probe flags, live control payloads, provider override, mismatched authorization and
replayed attempts must reject before agent initialization. Parent checks also prove
rejection before even accessing the key-to-be-attached, including missing metadata
and expired authority.

The fixture creates no real dispatch or reservation. Its synthetic receipt and clock
controls exist only in the qualification module, with no runtime gate bypass. Workers
use an empty home and a small public environment plus a dummy key. An audit hook
blocks network and subprocesses except fixed read-only Git identity/version queries;
LiteLLM's supported local cost-map mode prevents import-time metadata fetching.
That test-only setting does not change CLI/model/provider configuration. Workers
reuse the existing bounded native subprocess lifecycle, and must exit cleanly with
zero provider requests, workload launches and credential handoffs.

Preparation now requires the complete live-construction proof, including both arms,
all declared rejection cases and selected identities. Fresh consumption validates
that retained proof and reruns the same boundary on fresh trusted staging. Thus a
future paid launch cannot be its first exercise. These controls do not establish
actual provider authentication, request/event compatibility or live task success.

## Scheduler-backed reporting

New source-bound campaign evidence captures a bounded scheduler witness alongside
the native results and binds its retained bytes into the existing custom capture.
Admission checks its exact frozen order/population, deployment/task identities,
execution source and matching live dispatch evidence where applicable. The witness
uses the existing producer/API/archive authentication boundary; public structural
validation alone does not authenticate a producer.

The report displays scheduler execution separately from unchanged native collection
status. An explicitly unlaunched scheduler slot is shown as **unlaunched**; a failed
launch is **launch attempted; infrastructure failed**. A **measured task failed**
label requires matching native measured evidence. Native observations, grades and
execution/coverage counts are never overwritten or manufactured. Missing files alone
cannot establish nonexecution, and a contradictory native observation is refused.

A focused regression passes the stopped-before-launch shape through the released
collector, capture/admission, public JSON and existing HTML renderer. It retains zero
observations/recorded attempts, identifies the failed current launch and unlaunched
absent slot, rejects contradictory scheduler evidence and reproduces the new report
byte for byte. This is a declared credential-free scheduler fixture, not live work.

The original published stopped report still reproduces byte for byte with the new
renderer when supplied its original public input:

```text
sha256:5acc463c73bf87fc50b741c6d7a94528b4d63bbc19f1caddf6feba8cceebc04f
```

It is not rewritten as a corrected retrospective report. Its historical empty-arm
aggregates and the authoritative failed/unlaunched ledger retain their original
meaning. The new scheduler extension is required only by the new registered source
profiles; all 562 prior profiles remain unchanged. Thirty-three source successors
bind the changed shared code, retaining fixtures, grading and runtime settings.

## Validation, limits and rollback

Local related contracts, the actual live-construction regression and original report
reproduction are recorded in the PR. Final source qualification requires normal
change-selected CI, both platform checks, the selected-results gate, selected hosted
preparation and fresh-runner consumption with matching manifests and report digests.
Artifacts are bounded, authenticated data and are never executed.

SkillEvaluator 0.9.0, Harbor 0.25.0, Codex 0.155.1, `gpt-5.6-sol`, high reasoning,
unified-exec settings, task wording/grading and isolation remain frozen. Production
Benchmark remains 0.3.0 / Harbor 0.13.2. The standard judge route, live providers,
actual provider billing and skill improvement remain unqualified. Pester clarification
and skill adoption remain deferred. No paid run, protected gate, Pages publication,
production history append or merge is part of this correction.

Rollback the focused correction and its appended source profiles together, preserving
all retained evidence. Rollback does not revive an allocation or make the rejected
live path safe. Any future pilot needs a separate exact-source preparation and
explicit authorization; the old nonce, artifact authority and allocation cannot be reused.

**One next action:** review the qualified correction and its exact-revision receipts
in PR #143.
