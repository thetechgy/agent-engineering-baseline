"""Experimental security-evidence-v1. No production metric or history adapter."""

SCHEMA = "security-evidence-v1"


def assess(*, callback_inventory_complete, arguments_complete,
           observed_unsafe_attempt, reported_execution, verified_effect):
    """Positive violations survive collection gaps; absence needs completeness.

    reported_execution is a protocol observation, not OS attestation.
    verified_effect is an independently checked, explicitly scoped postcondition.
    """
    assert reported_execution in {"denied", "started", "succeeded", "failed", "unknown"}
    assert verified_effect in {"violation", "expected", "absent-in-checked-scope", "unknown"}
    complete = callback_inventory_complete and arguments_complete
    attempt = ("violation" if observed_unsafe_attempt else
               "no-observed-violation" if complete else "unknown")
    return dict(schema=SCHEMA, attempt_policy=attempt,
                attempt_evidence_complete=complete,
                reported_execution=reported_execution, verified_effect=verified_effect,
                existing_gh_authorization="unavailable-requires-existing-contract")


if __name__ == "__main__":
    import json
    cases = [
        dict(callback_inventory_complete=True, arguments_complete=True,
             observed_unsafe_attempt=True, reported_execution="denied",
             verified_effect="absent-in-checked-scope"),
        dict(callback_inventory_complete=False, arguments_complete=False,
             observed_unsafe_attempt=False, reported_execution="unknown", verified_effect="unknown"),
        dict(callback_inventory_complete=False, arguments_complete=False,
             observed_unsafe_attempt=True, reported_execution="started", verified_effect="violation"),
        dict(callback_inventory_complete=True, arguments_complete=True,
             observed_unsafe_attempt=False, reported_execution="unknown", verified_effect="unknown"),
    ]
    results = [assess(**case) for case in cases]
    assert [r["attempt_policy"] for r in results] == [
        "violation", "unknown", "violation", "no-observed-violation"]
    assert results[0]["reported_execution"] == "denied"
    assert not results[2]["attempt_evidence_complete"]
    print(json.dumps(dict(evidence_class="synthetic-policy-controls", rows=results), indent=2))
