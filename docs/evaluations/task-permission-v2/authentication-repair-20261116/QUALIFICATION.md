# Allocation-bound authentication repair qualification

The [stopped dispatch 43908693565/A1](https://github.com/thetechgy/agent-engineering-baseline/actions/runs/43908693565)
executed `3bafc85e1a4fd650bc62d3aa3ed66aa429c1bfaf` and failed before a protected
gate or agent. Its bare `python3` interpreter lacked `skillevaluator`, imported by
trusted task-member identity reconstruction. Preparation and inspection used an
installed owner and did not cover that dependency boundary. The exact original
CLI failure was reproduced locally using fixture-only GitHub IO and bare system
Python; the retained traceback reaches `GhPermission.verifier_entry` and ends in
`ModuleNotFoundError`. Both unused slots and that authorization stay closed.

## Correction and maintenance

Authentication and preparation use `setup-campaign-authentication.sh`, which
resolves the registered task's runtime owner and calls the existing hash-checked,
frozen `setup-skillevaluator.sh` recipe. Its owning-runtime guard verifies the
actual Python, evaluator, Harbor, dependencies, source, lock and backend. Existing
0.8.0 consumers keep their owner; this successor uses held 0.9.0 / Harbor 0.25.0
and Python 3.14.10. No dependency version or upstream normalization logic changes.
The authentication job allows 20 minutes for pinned acquisition plus its existing
bounded GitHub IO; agent/launch/cleanup limits are unchanged. The sixth unchanged
uv 0.13.8 workflow consumer is explicitly inventoried.

`campaign_authentication_qualification.py` invokes the real selection CLI as a
subprocess with a strict fixture `gh` executable. It never falls back to network.
Parsing, selection, `authenticate`, frozen identity construction, task-member
generation, admission and receipt serialization remain real. Only GitHub API/ZIP
transport, the persistence-failure injection and the expired-authority clock are
fixtures. Temporary fixture authority uses synthetic IDs/nonce and isolated
storage, never the closed allocation. Fixture receipts are deleted with scratch
and are not uploaded as authorization. The actual live gate rejects the fixture
job context. No agent, verifier, judge or provider credential is involved.

The positive case packages the actual authentication output layout, boundedly
extracts it as data and validates its receipt through the real downstream
consumer. Removing any required receipt field must reject. The 19 successor cases
cover successful receipt generation, wrong source/campaign/protocol/producer,
archive/task-identity tampering, expired artifact/authority, mismatched authority,
duplicate/replayed dispatch, incomplete preparation, missing dependency, failed or
incomplete receipt writing, missing/incomplete readiness proof and injected
preparation authorization. Each negative case must fail for its expected reason,
retain a bounded failure diagnostic and leave no receipt or live claim. Existing
metadata/layout and trust controls remain in place.

Authentication now rejects expired declared authority before GitHub acquisition.
Receipt validation requires every existing field, including producer identity.
A receipt is written to a pending file, read back and independently validated,
then atomically renamed only after all checks pass. Failure removes pending or
injected authorization and writes `authentication-failure.json`, preserving the
primary exception/stderr. The workflow uploads that bounded diagnostic under a
distinct failure-artifact name; it never substitutes for valid authorization.
No real claim-persistence boundary is reached by these tests.

## Readiness and hosted qualification

On preparation's fresh runner, the shared pinned setup precedes the CLI qualifier,
which is the first test step. Its proof records the actual interpreter/dependency
identities and source/setup/CLI bindings. Preparation consumes that proof; other
registered preparation entry points run the same qualifier if no proof is supplied.
Exact-source admission and fresh consumption reject missing, stale or incomplete
proof. A failed qualification retains partial cases with `complete: false` and
cannot create `preparation.json` readiness. This adds a readiness invariant to the
existing campaign; it adds no runner, workflow framework or report format.

Source-v22 profiles append new shared-runtime identities while preserving all 733
prior profiles (including the intermediate source-v21 identities) and all 15 metric
definitions. Task instructions, grading criteria,
resource inventories, target access, skills and held runtime/model versions remain
unchanged. Independent correctness, task authorization, activation and operational
failure keep their separate meanings. Historical gh-007 diagnosis is not reopened.

The original missing-dependency failure and local fixture qualification remain
working-tree evidence until executable freeze. Final required/change-selected
CI, fresh hosted CLI proof, exact-revision preparation artifact/digest, automatic
consumption and authenticated fresh inspection are published together in the
[PR #147 receipt](https://github.com/thetechgy/agent-engineering-baseline/pull/147).
No older artifact is relabeled as qualification of the repaired source. Failed,
interrupted and superseded attempts retain their actual states. Existing component
receipts are reused only for unchanged source/input identities.

Intermediate hosted preparation `43916530291/A1` passed setup and all 19 actual
CLI cases at `f0e8cee`, then correctly rejected two constructor-control receipt
fixtures missing the newly required producer field. Their fixtures now supply the
existing field; the validator is preserved. Native oracle/scheduler work never
started in that failed attempt. Its diagnostics remain retained. Authentication
proof diagnostics upload separately, preserving the registered preparation archive
root; a focused workflow regression enforces that layout. Queued CI `43916527767`
was cancelled as superseded and remains inconclusive.

## Proposal boundary

Any refreshed proposal remains current then absent on existing successor gh-014,
two serial attempts, at most two deterministic verifiers, custom_only, zero model
judges, no automatic retries/replacements and no continuation after an operational
stop. It preserves the $2 estimate, $3 estimated-usage scheduling threshold and $3
reserve within a $6 planning allocation, subject to official-price recheck. These
are not a provider billing cap; CI costs are separate. The fresh proposal window
ends November 23, 2026 at 23:59:59 UTC and does not extend any previous authority.
Its exact allocation/nonce, source/ref, protocol/preparation identities and UNRUN
combined dispatch/gate approval wording belong only in the final PR receipt.

Real GitHub allocation-bound authentication and successor model behavior remain
unexecuted by this credential-free repair. Fixture transport is not live GitHub
attestation. Accepted credential/log/child-process/egress/producer-accounting
limitations remain. Production defaults, schedules, skills, dependencies, isolation,
deferred Pester adoption, Pages, history and closed allocations remain unchanged.
No live gate approval, paid dispatch, inference, model judge or merge occurred.
