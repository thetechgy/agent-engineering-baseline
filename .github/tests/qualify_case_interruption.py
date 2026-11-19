"""Interrupt the real campaign wait with a credential-free child in place of Harbor."""
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
from unittest.mock import patch

import evaluation_campaign as campaign
from evaluation_campaign_protocol import frozen
from evaluation_campaign_selection import selected_task
import evaluation_codex
import qualify_evaluator_candidate as candidate
from skill_reports import read_json, write_json

EVENT = "agent/codex.txt"
LIFECYCLE = "operator/pilot-lifecycle.json"
CANARY = "qualification-example-only"
CHILD = """
import json, os, signal, sys
from pathlib import Path
trial, pidfile = map(Path, sys.argv[1:3])
(trial / 'agent').mkdir(parents=True)
(trial / 'operator').mkdir()
(trial / 'agent/codex.txt').write_text(json.dumps({'type':'item.completed',
    'item':{'type':'agent_message','text':'Partial fixture event. Bearer ' + sys.argv[3]}}) + '\\n')
(trial / 'operator/pilot-lifecycle.json').write_text(json.dumps({'stages':[{'stage':'agent_started'}]}))
(trial / 'agent/private.txt').write_text('Outside the diagnostic allowlist')
(trial / 'operator/pilot-final-policy.json').write_text('{')
pidfile.write_text(str(os.getpid()))
signal.alarm(15)
assert os.getppid() == int(sys.argv[4])
os.kill(os.getppid(), signal.SIGTERM)
signal.pause()
"""


def qualify(root):
    campaign.no_credentials()
    root.mkdir(exist_ok=False)
    prepared = root / "preparation"
    prepared.mkdir()
    with patch.dict(os.environ, OBSERVATION_SKILL="podman", OBSERVATION_CASE="4"):
        task = selected_task("case-observation")
    campaign.stage(prepared, task, "live")
    reference = prepared / "evidence"
    write_json(reference / "frozen-proposal.json", frozen(task))

    output = root / "campaign"
    pidfile = root / "fixture.pid"
    native_wait = candidate.run_native

    def resources():
        # The fixture's only workload resource is the real child process.
        if pidfile.exists() and Path("/proc", pidfile.read_text()).exists():
            return ["fixture-child"]
        return []

    def launch(command, *, env, log, timeout):
        config = read_json(Path(command[-1]))
        trial = Path(config["trials_dir"]) / config["trial_name"]
        return native_wait([sys.executable, "-I", "-c", CHILD, str(trial), str(pidfile),
                            CANARY, str(os.getpid())], env=env, log=log, timeout=30)

    with patch.object(candidate, "run_native", launch), patch.object(evaluation_codex, "resources", resources):
        try:
            campaign.run(output, task, "experiment-probe", reference=reference, fixture="no-change")
        except KeyboardInterrupt as error:
            frames = [frame.f_code for frame, _ in traceback.walk_tb(error.__traceback__)]
            assert native_wait.__code__ in frames
            assert subprocess.Popen.wait.__code__ in frames
        else:
            raise AssertionError("Expected handled SIGTERM in the campaign wait")

    dest = output / "evidence"
    ledger = read_json(dest / "attempt-ledger.json")
    row, = ledger["entries"]
    trial = output / row["native_trial"]
    assert ledger["stop_reason"] == ledger["state"] == row["state"] == "interrupted"
    assert ledger["failure"] == "KeyboardInterrupt" and ledger["inference"] is False
    assert pidfile.exists() and not resources() and ledger["cleanup_complete"]
    assert read_json(dest / "cleanup.json") == {"complete": True, "unlaunched_positions": []}
    source = {name: (trial / name).read_text() for name in (EVENT, LIFECYCLE)}
    retained = dest / "retained"
    members = sorted(p.relative_to(retained).as_posix() for p in retained.rglob("*") if p.is_file())
    # This receipt includes only names and observed status. Raw jobs stay private.
    write_json(dest / "signal-fixture.json", {"signal": "SIGTERM", "native_wait_interrupted": True,
        "source_members": sorted(source), "retained_members": members, "fixture_child_reaped": True})
    assert members == sorted(source), members
    assert CANARY in source[EVENT] and CANARY not in (retained / EVENT).read_text()
    assert "Partial fixture event." in read_json(retained / EVENT)["item"]["text"]
    assert (retained / LIFECYCLE).read_text() == source[LIFECYCLE]
    observation = read_json(dest / "observation.json")
    assert observation["execution"] == "interrupted" and observation["quality"] == "ungraded"
    assert observation["evidence"] == observation["review"] == "incomplete"
    assert observation["cleanup"] is True and "changed_paths" not in observation
    assert observation["retention_failures"] == {"operator/pilot-final-policy.json": "JSONDecodeError"}
    assert {"agent/last-message.txt", "operator/workspace-observation.json"} <= set(observation["missing"])
    print("Handled SIGTERM retained the partial event and lifecycle. Workspace changes are unknown.")


if __name__ == "__main__":
    qualify(Path(sys.argv[1]).absolute())
