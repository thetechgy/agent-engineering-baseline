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
from codex_pilot_contract import CATALOG_SHA256, MODEL_CATALOG, needs_model_catalog
from evaluation_campaign import no_credentials
from evaluation_campaign_selection import selected_task
from evaluation_codex import agent_config
from evaluation_runtime import ROOT, read_profile
from qualify_codex_1691 import acquire, check_digest, probe
from qualify_codex_1710 import run_exec
from skill_reports import POLICY, read_json, require, write_json


def qualify(root):
    no_credentials()
    root.mkdir()
    routes = defaultdict(list)
    pilot = PilotCodex.profile
    argv = command(root, "with_skill")
    routes[pilot["cli"]].append(("pilot", pilot, argv[argv.index("--model") + 1]))
    config, _ = launch_config(root, {"position": 1, "trial": 1, "case": "pester-001",
                                     "arm": "with_skill"}, root / "pester-001")
    routes[pilot["cli"]].append(("pester-cohort", pilot, read_json(config)["agent"]["model_name"]))
    registries = (".github/evals/campaigns/selections-sol62.json",
                  ".github/evals/campaigns/selections-1710-sol62.json",
                  ".github/evals/podman/storage/selections.json")
    choices = {name for registry in registries for name in read_json(ROOT / registry)["campaigns"]}
    import yaml
    workflow = yaml.safe_load((ROOT / ".github/workflows/evaluation-campaign.yml").read_text())
    options = workflow.get("on", workflow.get(True))["workflow_dispatch"]["inputs"]["campaign"]["options"]
    require(set(options) == {*choices, "case-observation", "case-observation-1691"}, "Unverified workflow selector")
    for name in options:
        with patch.dict(os.environ, OBSERVATION_SKILL="podman", OBSERVATION_CASE="4"):
            task = selected_task(name)
        if task.definition.get("type") == "judge-only":
            continue
        runtime = read_profile(ROOT / task.definition["runtime_profile"])["resolved"]
        launch = agent_config(task, "experiment-probe", None, runtime, True)
        require(launch["model_name"] == runtime["model"] and launch["kwargs"]["campaign_definition"] == task.member,
                "Harbor campaign dispatch model drift")
        routes[runtime["cli"]].append((name, runtime, launch["model_name"]))

    receipt = {}
    for version, callers in routes.items():
        with TemporaryDirectory(prefix="model-release-") as directory:
            binary = acquire(callers[0][1], Path(directory))
            runtime = callers[0][1]
            if needs_model_catalog(runtime):
                check_digest(ROOT / MODEL_CATALOG, CATALOG_SHA256)
                edit = root / 'native-pilot-edit'
                edit.mkdir()
                result = run_exec(binary, edit, runtime, edit / 'events.jsonl', 'priced-success')
                write_json(edit / 'qualification.json', result)
            for name, runtime, selected_model in callers:
                require(runtime["model"] == POLICY["model"] == "gpt-6.2-sol", "Unapproved model: " + name)
                observed = probe(runtime, binary, root / name, "provider-refusal", selected_model=selected_model)
                receipt[name] = {"cli": version, "model": observed["model"], "effort": observed["reasoning_effort"],
                                 "requests": observed["request_count"], "endpoint": "/v1/responses"}
    write_json(root / "requests.json", receipt)
    for name, row in receipt.items():
        print(name, row, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    qualify(parser.parse_args().output)
