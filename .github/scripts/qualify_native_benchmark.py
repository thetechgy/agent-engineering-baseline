"""Exercise the prepared released launcher up to its native runtime preflight."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

from aeb_gh_fixture import MANIFEST_ENV
from aeb_gh_fixture.manifest import approve, prerequisites
from harbor.models.task.task import Task
from skillevaluator.evaluation import EvaluationService
from skillevaluator.tier3.harbor import runner, runtime_preflight

import benchmark_native as native
from benchmark_smoke import PROVIDER_CREDENTIALS
from qualify_benchmark_101 import restrict_network
from skill_reports import MODES, PATCH, POLICY, benchmark_policy, read_json, require, write_json


SENTINEL = "released-launcher-fixture-not-a-credential"
STOP = "Credential-free control stopped before Docker runtime preflight"


def interrupted_podman(root, revision):
    """Recover reviewed synthetic native jobs with one result missing."""
    from harbor.models.job.result import JobResult, JobStats
    from evaluator_profiles import RELEASE_BENCHMARK
    from qualify_benchmark_evidence import fixture
    from skillevaluator.tier3.harbor.collector import _interrupted_trial_roots

    simulated = fixture(root / "interruption-fixture", "complete", producer=RELEASE_BENCHMARK,
                        model=POLICY["model"], codex=POLICY["codex"], workspace=native.ROOT)
    for member in ("native-preparation.json", "versions.json"):
        write_json(simulated / member, read_json(root / member))
    run = simulated / "results/podman/complete"
    with_skill = run / "_harbor-jobs/podman-codex-with"
    job_path = with_skill / "result.json"
    job = JobResult.model_validate_json(job_path.read_text())
    trial = "skillevaluator-1__attempt001"
    retained = [item for item in job.trial_results if item.trial_name != trial]
    require(len(retained) == len(job.trial_results) - 1, "Expected one interrupted fixture trial")
    job_path.write_text(job.model_copy(update={"finished_at": None, "trial_results": retained,
        "stats": JobStats.from_trial_results(retained, n_total_trials=job.n_total_trials)}).model_dump_json())
    (with_skill / trial / "result.json").unlink()
    (run / "result.json").unlink()
    roots = _interrupted_trial_roots(with_skill, 10)
    require(roots is not None and len(roots) == 9, "Interrupted job lost its physical trial matches")
    physical = roots[0] / "result.json"
    original = physical.read_bytes()
    changed = read_json(physical)
    changed["id"] = "00000000-0000-0000-0000-000000000001"
    write_json(physical, changed)
    try:
        require(_interrupted_trial_roots(with_skill, 10) is None, "Mismatched physical trial entered recovery")
    finally:
        physical.write_bytes(original)

    native.recover(native.ROOT, simulated, "podman", "standard", revision, "cancelled")
    recovery = read_json(simulated / "provenance.json")
    result = read_json(run / "result.json")
    arms = result["agents"]["codex"]["conditions"]
    counts = {arm: cell["scored_attempts"] for arm, cell in arms.items()}
    require(recovery["status"] == "incomplete" and recovery["evaluation_outcome"] == "cancelled"
            and result["diagnostic_only"] is True and result["report_status"] == "incomplete"
            and counts == {"with_skill": 9, "without_skill": 10} and all(cell["expected_attempts"] == 10 for cell in arms.values()),
            "Released recovery changed the interrupted result population")
    return {"expected_attempts": 20, "scored_attempts": 19, "origin": "simulated_jobs", "mismatched_trial_rejected": True, "history_eligible": False}


def qualify(root, name, mode, revision):
    require(not any(os.environ.get(key) for key in PROVIDER_CREDENTIALS),
            "Released launcher qualification requires a credential-free process")
    native.prepare(native.ROOT, root, name, mode, revision)
    sys.addaudithook(restrict_network)
    observed = []
    docker_host = "unix:///run/aeb-qualification/docker.sock"
    docker_config = root / "compose-plugin"

    def catalog(provider):
        require(provider.provider == "openai" and provider.model == POLICY["model"]
                and provider.base_url == "https://api.openai.com/v1" and provider.api_key == SENTINEL,
                "Credential catalog route differs from the reviewed OpenAI route")
        return runtime_preflight.ModelProbeResult(True, provider.provider, provider.model, "Synthetic catalog result")

    def backend(**options):
        require(options["env_mode"] == native.BACKENDS[name], "Released backend selection differs")
        return prerequisites(options["environment_kwargs"]) if name == "gh" else []

    def preflight(*, dataset, agent, model, env_mode, run_env, timeout_multiplier, agent_import_path, **_):
        require(agent == "codex" and model == POLICY["model"] and env_mode == native.BACKENDS[name]
                and agent_import_path == "aeb_gh_fixture.benchmark_codex:BenchmarkCodex"
                and run_env["OPENAI_API_KEY"] == SENTINEL and timeout_multiplier == POLICY["timeout_multiplier"],
                "Released runtime preflight contract differs")
        require(run_env.get("DOCKER_HOST") == docker_host and run_env.get("DOCKER_CONFIG") == str(docker_config)
                and "DOCKER_AUTH_CONFIG" not in run_env, "Docker host handoff changed or received registry credentials")
        cases = []
        for path in sorted(dataset.iterdir()):
            if not path.is_dir():
                continue
            entry = read_json(path / "tests/entry.json")
            task = Task(path)
            environment = task.config.environment.resolve_baseline()
            require(entry["has_skill"] is True and task.config.agent.user == "agent"
                    and environment.network_mode.value == "allowlist" and environment.allowed_hosts == ["api.openai.com"],
                    "Staged native preflight task is outside the approved policy")
            if name == "gh":
                row, _ = approve(os.environ[MANIFEST_ENV], path)
                require(row["arm"] == "with_skill", "Preflight selected the wrong sealed arm")
            cases.append(entry["id"])
        observed.append(len(cases))
        return runtime_preflight.PreflightResult(False, agent, model, STOP, "fixture")

    with (patch.dict(os.environ, DOCKER_HOST=docker_host, DOCKER_CONFIG=str(docker_config),
                     DOCKER_AUTH_CONFIG="fixture-registry-config-must-stay-on-host"),
          patch.object(runner, "_check_prerequisites", side_effect=backend),
          patch.object(runtime_preflight, "probe_model", side_effect=catalog),
          patch.object(runtime_preflight, "run_agent_runtime_preflight", side_effect=preflight),
          patch.object(runner, "_run_agent_pair", side_effect=AssertionError("Native matrix escaped qualification")) as launch):
        result = native.execute(native.ROOT, root, name, mode, revision, SENTINEL)
        launch.assert_not_called()
    count = 24 if name == "gh" else 10
    reason = EvaluationService.failure_reason(result)
    require(observed == [count] and result["execution_status"] == "failed" and reason and STOP in reason,
            "Release launcher did not reach or retain the expected preflight result")
    retained = Path(result["run_dir"])
    require(retained.resolve().is_relative_to(root.resolve()), "Unexpected released report location")
    snapshot = read_json(retained / "dataset_snapshot.json")
    config = result["run_config"]
    require(snapshot["dataset_summary"]["total_tasks"] == count
            and config["harbor"]["n_attempts"] == MODES[mode]
            and config["harbor"]["n_concurrent"] == POLICY["concurrency"], "Released plan or dataset changed")
    require(SENTINEL.encode() not in (retained / "result.json").read_bytes(), "Fixture credential entered diagnostics")
    historical_patch = hashlib.sha256((native.ROOT / PATCH).read_bytes()).hexdigest()
    historical_policy = json.dumps([benchmark_policy(name), historical_patch], sort_keys=True).encode()
    series = {native.score_series(name, current) for current in MODES}
    require(len(series) == len(MODES) and hashlib.sha256(historical_policy).hexdigest()[:16] not in series,
            "Released score modes share a series with each other or historical scores")
    native.recover(native.ROOT, root, name, mode, revision, "failure")
    recovery = read_json(root / "provenance.json")
    require(recovery["diagnostic_only"] is True and recovery["status"] == "incomplete"
            and recovery["native_series"] == native.score_series(name, mode), "Preflight failure acquired a completed series")
    incomplete = read_json(retained / "result.json")
    require(incomplete["report_status"] == "incomplete" and incomplete["error"] == result["error"],
            "Recovery lost or changed the initiating preflight error")
    interruption = interrupted_podman(root, revision) if name == "podman" and mode == "standard" else None
    write_json(root / "qualification.json", {
        "schema_version": 1, "revision": revision, "skill": name, "mode": mode, "producer": native.NATIVE_PRODUCER,
        "backend": native.BACKENDS[name], "cases_per_arm": count, "dataset_digest": snapshot["dataset_digest"],
        "planned_trials": count * MODES[mode] * 2, "docker_started": False, "provider_requests": 0,
        "matrix_started": False, "preflight_intercepted": True, "docker_host_handoff_verified": True,
        "history_eligible": False,
        "recovery": "incomplete", "native_series": recovery["native_series"], "interruption": interruption,
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("skill", choices=native.BACKENDS)
    parser.add_argument("mode", choices=MODES)
    parser.add_argument("revision")
    args = parser.parse_args()
    qualify(args.root, args.skill, args.mode, args.revision)


if __name__ == "__main__":
    main()
