"""Check the model carried from each dispatch selector to the released CLI's HTTP request."""
import argparse
from collections import defaultdict
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from codex_pilot import command
from codex_pilot_agent import PilotCodex
from codex_pilot_cohort import launch_config
from evaluation_campaign import no_credentials
from evaluation_campaign_selection import selected_task
from evaluation_codex import agent_config
from evaluation_runtime import ROOT, read_profile
from qualify_codex_1691 import acquire, probe
from skill_reports import POLICY, read_json, require, write_json


def qualify(root):
    no_credentials()
    root.mkdir()
    routes = defaultdict(list)
    pilot = PilotCodex.profile
    argv = command(root, "with_skill")
    require(argv[argv.index("--model") + 1] == pilot["model"], "Pilot launcher omitted its model")
    routes[pilot["cli"]].append(("pilot", pilot))
    config, _ = launch_config(root, {"position": 1, "trial": 1, "case": "pester-001",
                                     "arm": "with_skill"}, root / "pester-001")
    require(read_json(config)["agent"]["model_name"] == pilot["model"], "Cohort launcher model drift")
    routes[pilot["cli"]].append(("pester-cohort", pilot))
    choices = read_json(ROOT / ".github/evals/campaigns/selections-sol62.json")["campaigns"]
    import yaml
    workflow = yaml.safe_load((ROOT / ".github/workflows/evaluation-campaign.yml").read_text())
    options = workflow.get("on", workflow.get(True))["workflow_dispatch"]["inputs"]["campaign"]["options"]
    require(set(options) == {*choices, "case-observation", "case-observation-1691"}, "Unverified workflow selector")
    for name in options:
        with patch.dict(os.environ, OBSERVATION_SKILL="gh", OBSERVATION_CASE="gh-014"):
            task = selected_task(name)
        if task.definition.get("type") == "judge-only":
            continue
        runtime = read_profile(ROOT / task.definition["runtime_profile"])["resolved"]
        launch = agent_config(task, "experiment-probe", None, runtime, True)
        require(launch["model_name"] == runtime["model"] and launch["kwargs"]["campaign_definition"] == task.member,
                "Harbor campaign dispatch model drift")
        routes[runtime["cli"]].append((name, runtime))

    receipt = {}
    for version, callers in routes.items():
        with TemporaryDirectory(prefix="model-release-") as directory:
            binary = acquire(callers[0][1], Path(directory))
            for name, runtime in callers:
                require(runtime["model"] == POLICY["model"] == "gpt-6.2-sol", "Unapproved model: " + name)
                observed = probe(runtime, binary, root / name, "provider-refusal")
                receipt[name] = {"cli": version, "model": observed["model"], "effort": observed["reasoning_effort"],
                                 "requests": observed["request_count"], "endpoint": "/v1/responses"}
    write_json(root / "requests.json", receipt)
    for name, row in receipt.items():
        print(name, row, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    qualify(parser.parse_args().output)
