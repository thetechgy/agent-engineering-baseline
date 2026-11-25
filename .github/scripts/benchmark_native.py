#!/usr/bin/env python3
"""Prepare inputs for the released native benchmark owner."""

import argparse
from contextlib import contextmanager
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tomllib

from benchmark_podman import CODEX_PROFILE, codex_members, configure_agent, configure_openai_task
import gh_candidate
import gh_evaluations as gh
from skill_reports import (MODES, POLICY, benchmark_options, benchmark_policy, local_skill, read_json,
                           recover_benchmark, require, write_json)


ROOT = Path(__file__).resolve().parents[2]
NATIVE_PRODUCER = "skillevaluator-1.0.1-benchmark-native-v1"
NATIVE_SOURCE_DIGEST = "sha256:21f6252f1c56f85c75762c804f4064085f30160e24695a51c7b21dad372bb1ec"
NATIVE_PATCH_DIGEST = "0cbf3aa1d0a84ec740d42a5744c41c5a8de4f04c319e4fc6e1b3fe9092c672c9"
BACKENDS = {"podman": "aeb-benchmark-docker", "gh": "aeb-gh-fixture"}
GH_DATASET_PROFILE = "gh-benchmark-101-v1"
GH_ACCESS_METRIC = "gh_access_policy"
GH_ARMS = {"with_skill": True, "without_skill": False}
GH_CODEX_VENDOR = "/opt/reviewed/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl"


def stage_gh(workspace, destination, selected=None, *, fixture=False):
    """Project the prospective task from the retained gh case definition."""
    bundle = gh_candidate.stage(workspace, destination, selected, fixture=fixture)
    grader = bundle / "evals/grader.py"
    source = grader.read_text()
    export = 'metrics = {"gh_" + key: float(value) for key, value in scores.items()}'
    require(source.count(export) == 1, "Unreviewed gh metric export")
    # The released collector rejects sensitive key names. Export the same
    # verifier-owned binary measurement under a registered prospective name.
    grader.write_text(source.replace(
        export, export + f'\n    metrics["{GH_ACCESS_METRIC}"] = metrics.pop("gh_authorization")'))
    dataset_file = bundle / "evals/evals.json"
    dataset = read_json(dataset_file)
    for entry in dataset["evals"]:
        if entry["id"] != "gh-001":
            continue
        instruction = bundle / "evals/harbor/gh-001/instruction.md"
        original = entry["prompt"]
        prefix = "Use the gh skill to read issue 12 and its conversation comments"
        require(original.startswith(prefix) and instruction.read_bytes() == (original + "\n").encode(),
                "Unreviewed gh-001 prompt or staged instruction")
        entry["prompt"] = "Read issue 12 and its conversation comments" + original.removeprefix(prefix)
        instruction.write_bytes((entry["prompt"] + "\n").encode())
        write_json(dataset_file, dataset)
        break
    return bundle


def configure_gh_task(task, profile):
    """Pin the image's native Codex assets without adding them to the task tree."""
    descriptor = task / "task.toml"
    source = descriptor.read_text()
    config = tomllib.loads(source)
    network = 'network_mode = "public"'
    require(source.count(network) == 1 and "healthcheck" not in config["environment"]
            and config["agent"]["user"] == "agent" and config["verifier"]["user"] == "root",
            "Unexpected staged gh environment contract")
    descriptor.write_text(source.replace(network, 'network_mode = "allowlist"\nallowed_hosts = ["api.openai.com"]'))

    members = codex_members(profile)
    del members["bin/codex-exec-server"]  # The npm platform package has no standalone exec-server.
    require(set(members) == {"bin/codex", "bin/codex-code-mode-host", "codex-resources/bwrap", "codex-path/rg"}
            and all(re.fullmatch(r"[0-9a-f]{64}", digest) for digest in members.values()),
            "Unexpected gh Codex package integrity set")
    checksums = shlex.join(f"{digest}  {name}" for name, digest in sorted(members.items()))
    paths = shlex.join(sorted(members))
    package = shlex.quote("@openai/codex@" + profile["cli"])
    version = shlex.quote("codex-cli " + profile["cli"])
    with (task / "environment/Dockerfile").open("a") as build:
        build.write("\nRUN chgrp -R agent /workspace/skills && chmod -R g+rX,go-w /workspace/skills\n"
                    "RUN npm install --prefix /opt/reviewed --no-audit --no-fund --ignore-scripts "
                    f"--install-strategy=hoisted --registry=https://registry.npmjs.org/ {package} "
                    f"&& cd {GH_CODEX_VENDOR} && test ! -e bin/codex-exec-server && test ! -L bin/codex-exec-server "
                    f"&& for member in {paths}; do "
                    f'test "$(realpath -- "$member")" = "{GH_CODEX_VENDOR}/$member" || exit 1; done '
                    f"&& printf '%s\\n' {checksums} | sha256sum --check --strict "
                    "&& chown -hR 0:0 /opt/reviewed && chmod -R a+rX,go-w /opt/reviewed "
                    f"&& ln -s {GH_CODEX_VENDOR}/bin/codex /usr/local/bin/codex "
                    f'&& test "$(/usr/local/bin/codex --version)" = {version}\n'
                    f"ENV PATH={GH_CODEX_VENDOR}/codex-path:$PATH\n")


def prepare_gh_manifest(bundle, root):
    """Seal both prospective arms before the protected inference step."""
    from aeb_gh_fixture.manifest import write_manifest
    from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks

    # The pinned OpenAI route uses these names. Values are resolved by the
    # released runner only in the protected process, outside the staged tree.
    agent = {name: f"${{{name}}}" for name in ("OPENAI_API_KEY", "OPENAI_BASE_URL")}
    verifier = {name: f"${{{name}}}" for name in ("SKILL_EVAL_LLM_PROVIDER", "SKILL_EVAL_LLM_MODEL")} | agent
    approval = root / "gh-task-approval"
    profile = read_json(CODEX_PROFILE)
    identities = {entry["id"] for entry in read_json(bundle / "evals/evals.json")["evals"]}
    paired = []
    for arm, present in GH_ARMS.items():
        tasks = stage_native_harbor_tasks(
            bundle, approval / arm, with_skill=present, workspace_mode="group",
            grading_mode="default_plus_custom", custom_dockerfile_mode="preserve",
            workspace_skill_paths=[bundle.parent / gh.COMPETING],
            runtime_env=agent, verifier_env=verifier, arm_suffix="-" + arm.replace("_", "-"),
        )
        require(len(tasks) == len(identities) and {task.name for task in tasks} == identities,
                "Incomplete staged gh approval population")
        for task in tasks:
            configure_gh_task(task, profile)
        paired.extend(tasks)
    return write_manifest(root / "gh-operator", paired, staged_roots=[bundle.parent, approval])


def gh_finalizer(manifest, emitted):
    """Verify that the released runner will launch the approved task bytes."""
    from aeb_gh_fixture.manifest import load_manifest, task_identity

    approved, _ = load_manifest(manifest)
    require(set(emitted) == {"codex"} and set(emitted["codex"]) == set(GH_ARMS),
            "Released gh runner did not stage both approved arms")
    profile = read_json(CODEX_PROFILE)
    actual = {}
    for arm, tasks in emitted["codex"].items():
        for task in tasks:
            configure_gh_task(task, profile)
            row = task_identity(task)
            identity = row["case"] + "__" + arm
            require(row["arm"] == arm and identity not in actual, "Invalid or duplicate released gh task identity")
            actual[identity] = row
    require(actual == approved["tasks"], "Released gh task staging differs from the prepared approval")


def validate_runtime():
    """Verify the launcher owner without changing the prior smoke producer."""
    from evaluator_profiles import RELEASE_BENCHMARK, candidate_versions, validate_install

    validate_install({**RELEASE_BENCHMARK, "id": NATIVE_PRODUCER, "source_tree_digest": NATIVE_SOURCE_DIGEST})
    return {**candidate_versions(RELEASE_BENCHMARK), "patch_sha256": NATIVE_PATCH_DIGEST,
            "source_tree_digest": NATIVE_SOURCE_DIGEST, "producer_profile": NATIVE_PRODUCER}


def dataset_sha256(skill):
    return hashlib.sha256((skill / "evals/evals.json").read_bytes()).hexdigest()


def require_revision(workspace, revision):
    require(re.fullmatch(r"[0-9a-f]{40}", revision), "Invalid benchmark source revision")
    head = subprocess.check_output(["git", "-C", str(workspace), "rev-parse", "HEAD"], text=True, timeout=20)
    require(head.strip() == revision, "Benchmark revision differs from the checkout")


def prepare(workspace, root, name, mode, revision):
    """Prepare the reviewed dataset and runtime before entering the credential step."""
    from benchmark_smoke import PROVIDER_CREDENTIALS
    from qualify_codex_1691 import acquire

    require(not any(os.environ.get(key) for key in PROVIDER_CREDENTIALS),
            "Benchmark preparation requires a credential-free process")
    require(name in BACKENDS and mode in MODES, "Unqualified released benchmark selection")
    require_revision(workspace, revision)
    root = root.absolute()
    require(root.resolve() == root and not root.is_relative_to(workspace), "Use a new benchmark directory outside checkout")
    versions = validate_runtime()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    skill = stage_gh(workspace, root / "bundle/gh") if name == "gh" else local_skill(workspace, name, dataset=True)
    validation = [sys.executable, "-B", "-c", "from skillevaluator.cli import cli; cli()",
                  "tier3", "validate", str(skill), "--strict", "--json"]
    with (root / "dataset-validation.json").open("x") as receipt:
        subprocess.run(validation, stdout=receipt, check=True, timeout=90)
    manifest = None
    if name == "gh":
        manifest = prepare_gh_manifest(skill, root).name
    else:
        assets = root / "archive"
        assets.mkdir(mode=0o700)
        acquire(read_json(CODEX_PROFILE), assets)
    (root / "operator-home").mkdir(mode=0o700)
    write_json(root / "versions.json", versions)
    write_json(root / "native-preparation.json", {
        "schema_version": 1, "revision": revision, "skill": name, "mode": mode,
        "backend": BACKENDS[name], "producer_profile": NATIVE_PRODUCER,
        "dataset_profile": GH_DATASET_PROFILE if name == "gh" else "podman-authored",
        "dataset_sha256": dataset_sha256(skill), "gh_manifest": manifest,
    })


def podman_finalizer(skill, assets, emitted):
    from skillevaluator.tier3.case_ids import validate_case_ids
    from skillevaluator.tier3.dataset_utils import load_dataset_entries

    entries = load_dataset_entries(skill / "evals/evals.json")
    cases = set(validate_case_ids(entry["id"] for entry in entries))
    require(set(emitted) == {"codex"} and set(emitted["codex"]) == set(GH_ARMS),
            "Released Podman runner did not stage both approved arms")
    profile = read_json(CODEX_PROFILE)
    for arm, tasks in emitted["codex"].items():
        require(len(tasks) == len(cases) and {task.name for task in tasks} == cases,
                "Incomplete staged Podman population")
        for task in tasks:
            configure_agent(task, case=task.name, with_skill=GH_ARMS[arm])
            configure_openai_task(task, assets, profile)


@contextmanager
def provider_environment(home, key, manifest=None):
    original = dict(os.environ)
    names = ("PATH", "TMPDIR", "DOCKER_CONFIG", "DOCKER_HOST", "COMPOSE_PLUGIN_ROOT", "XDG_RUNTIME_DIR")
    env = {name: original[name] for name in names if name in original}
    env.update(HOME=str(home), OPENAI_API_KEY=key, PYTHON_DOTENV_DISABLED="1", PYTHONDONTWRITEBYTECODE="1",
               LITELLM_LOCAL_MODEL_COST_MAP="True", SKILL_EVAL_LLM_PROVIDER=POLICY["provider"],
               SKILL_EVAL_LLM_MODEL=POLICY["model"], SKILL_EVAL_JUDGE_MODEL=POLICY["model"],
               LLM_JUDGE_MODEL=POLICY["model"], LLM_JUDGE_FALLBACK_MODELS="")
    if manifest is not None:
        from aeb_gh_fixture import MANIFEST_ENV
        env[MANIFEST_ENV] = str(manifest)
    os.environ.clear()
    os.environ.update(env)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(original)


def validate_preparation(workspace, root, name, mode, revision):
    require(name in BACKENDS and mode in MODES, "Invalid released selection")
    require_revision(workspace, revision)
    root = root.absolute()
    require(root.resolve() == root and not root.is_relative_to(workspace), "Invalid prepared benchmark location")
    prepared = read_json(root / "native-preparation.json")
    require(read_json(root / "versions.json") == validate_runtime(), "Prepared benchmark runtime differs")
    skill = root / "bundle/gh" if name == "gh" else local_skill(workspace, name, dataset=True)
    require(prepared == {"schema_version": 1, "revision": revision, "skill": name, "mode": mode,
                          "backend": BACKENDS[name], "producer_profile": NATIVE_PRODUCER,
                          "dataset_profile": GH_DATASET_PROFILE if name == "gh" else "podman-authored",
                          "dataset_sha256": dataset_sha256(skill), "gh_manifest": prepared.get("gh_manifest")},
            "Prepared benchmark scope differs")
    return root, skill, prepared


def execute(workspace, root, name, mode, revision, key, *, progress_reporter=None):
    """Run the same paired release entry under protected or non-forwarding execution."""
    from skill_pages import REPOSITORY
    from skillevaluator.tier3.harbor.runner import run_harbor_eval
    from skillevaluator.tier3.results_location import resolve_results_root

    require(key, "Missing benchmark credential")
    root, skill, prepared = validate_preparation(workspace, root, name, mode, revision)
    manifest = None
    if name == "gh":
        from aeb_gh_fixture.manifest import load_manifest
        member = prepared["gh_manifest"]
        require(type(member) is str and re.fullmatch(r"manifest-[0-9a-f]{64}\.json", member), "Invalid gh approval manifest name")
        manifest = root / "gh-operator" / member
        load_manifest(manifest)
        finalizer = partial(gh_finalizer, manifest)
    else:
        require(prepared["gh_manifest"] is None, "Unexpected Podman approval manifest")
        finalizer = partial(podman_finalizer, skill, root / "archive")

    options = benchmark_options(name)
    include = [skill.parent / gh.COMPETING] if name == "gh" else None
    with provider_environment(root / "operator-home", key, manifest):
        return run_harbor_eval(
            skill, ["codex"], env_mode=BACKENDS[name], n_attempts=MODES[mode], n_concurrent=POLICY["concurrency"],
            max_agents=1, stop_on_pass=False, grading_mode=options["grading_mode"],
            skill_workspace_mode=options["workspace_mode"], include_skills=include,
            custom_dockerfile_mode="preserve" if name == "gh" else "disabled",
            timeout_multiplier=POLICY["timeout_multiplier"], agent_runtime_preflight=True, keep_harbor_jobs=True,
            output_dir=resolve_results_root(skill, root / "results"), agent_models={"codex": POLICY["model"]},
            evaluated_source={"repository": REPOSITORY, "commit": revision}, progress_reporter=progress_reporter,
            _operator_task_finalizer=finalizer,
        )


def validate_collected_pair(result, root, name, mode, revision, cases):
    """Require a complete released pair before any benchmark report is admitted."""
    from skillevaluator.evaluation import EvaluationService

    from skill_pages import REPOSITORY
    from skill_reports import metric_rows

    policy = released_policy(name)
    require(EvaluationService.failure_reason(result) is None and result["report_status"] == "complete"
            and result["execution_status"] == "succeeded" and result["skill_name"] == name
            and result["score_policy"] == policy["scoring_policy"]
            and result["metric_set"] == "skill-evaluator-default-v2", "Incomplete or incompatible released benchmark")
    run = Path(result["run_dir"])
    require(run.resolve() == run and run.parent == root / "results" / name
            and (run / "report.html").is_file() and not (run / "report.html").is_symlink(),
            "Missing or unsafe released benchmark report")
    config = read_json(run / "run_config.json")
    require(config == result["run_config"], "Released benchmark configuration differs from the report")
    require(config["evaluated_source"] == {"repository": REPOSITORY, "commit": revision}
            and config["provider"] == {"name": POLICY["provider"], "model": POLICY["model"]}
            and config["grading"]["mode"] == policy["grading"], "Released benchmark source or execution policy differs")
    judge = config["judge"]
    require(judge["enabled"] is True and judge["provider"] == POLICY["provider"] and judge["model"] == POLICY["model"]
            and judge["override_applied"] is True and "reasoning_effort" in judge and judge["reasoning_effort"] is None,
            "Released benchmark judge policy differs")
    harbor = config["harbor"]
    require(harbor["environment"]["value"] == BACKENDS[name] and harbor["n_attempts"] == MODES[mode]
            and harbor["n_concurrent"] == POLICY["concurrency"] and harbor["stop_on_pass"] is False
            and harbor["timeout_multiplier"] == POLICY["timeout_multiplier"], "Released benchmark attempt policy differs")
    snapshot = read_json(run / "dataset_snapshot.json")
    ids = [str(entry["id"]) for entry in snapshot["dataset"]]
    require(set(ids) == set(cases) and len(ids) == len(cases) == result["dataset_summary"]["total_tasks"]
            and snapshot["dataset_digest"] == result["dataset_digest"], "Released benchmark dataset differs")
    require(set(result["agents"]) == {"codex"}, "Released benchmark agent roster differs")
    agent = result["agents"]["codex"]
    require(agent["model"] == POLICY["model"] and set(agent["conditions"]) == set(GH_ARMS),
            "Released benchmark arm or model differs")
    for arm in agent["conditions"].values():
        require(arm["execution_status"] == "succeeded" and not arm["execution_errors"]
                and arm["scored_attempts"] == arm["expected_attempts"] == len(cases) * MODES[mode],
                "Incomplete released benchmark arm")
    return metric_rows(agent)


def released_policy(name):
    from evaluator_profiles import RELEASE_BENCHMARK

    require(name in BACKENDS, "Unsupported released score policy")
    options = benchmark_options(name)
    return {**benchmark_policy(name), "grading": options["grading_mode"], "workspace_mode": options["workspace_mode"],
            "evaluator_revision": RELEASE_BENCHMARK["revision"], "harbor": RELEASE_BENCHMARK["harbor"],
            "python": RELEASE_BENCHMARK["python"], "environment": BACKENDS[name],
            "producer_profile": NATIVE_PRODUCER, "scoring_policy": RELEASE_BENCHMARK["scoring"],
            "judge_contract": "skill-evaluator-judges-v2", "lock_sha256": RELEASE_BENCHMARK["lock_sha256"],
            "dataset_profile": GH_DATASET_PROFILE if name == "gh" else "podman-authored"}


def score_series(name, mode):
    require(mode in MODES, "Unsupported released score mode")
    material = json.dumps([released_policy(name), NATIVE_PATCH_DIGEST, mode], sort_keys=True).encode()
    return hashlib.sha256(material).hexdigest()[:16]


def recover(workspace, root, name, mode, revision, outcome):
    root, _, _ = validate_preparation(workspace, root, name, mode, revision)
    recover_benchmark(workspace, root, name, mode, outcome, environment=BACKENDS[name])
    if outcome != "success":
        original = read_json(root / "provenance.json")
        write_json(root / "provenance.json", {**original, "skill": name, "mode": mode, "revision": revision,
                                             "native_policy": released_policy(name), "native_series": score_series(name, mode)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("verify-runtime")
    for command in ("prepare", "execute", "recover"):
        entry = subcommands.add_parser(command)
        entry.add_argument("root", type=Path)
        entry.add_argument("skill", choices=BACKENDS)
        entry.add_argument("mode", choices=MODES)
        entry.add_argument("revision")
        if command == "recover":
            entry.add_argument("outcome", choices=("success", "failure", "cancelled", "skipped"))
    args = parser.parse_args()
    if args.command == "verify-runtime":
        validate_runtime()
        return 0
    if args.command == "prepare":
        prepare(ROOT, args.root, args.skill, args.mode, args.revision)
        return 0
    if args.command == "recover":
        recover(ROOT, args.root, args.skill, args.mode, args.revision, args.outcome)
        return 0
    from skillevaluator.evaluation import EvaluationService
    from skillevaluator.tier3.harbor.progress import PlainProgressReporter

    result = execute(ROOT, args.root, args.skill, args.mode, args.revision, os.environ.get("OPENAI_API_KEY"),
                     progress_reporter=PlainProgressReporter())
    if EvaluationService.failure_reason(result) is not None:
        print("Released native benchmark failed. Inspect the retained diagnostics.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, TypeError, ValueError, subprocess.SubprocessError) as error:
        print(f"Released benchmark contract failed ({type(error).__name__}).", file=sys.stderr)
        raise SystemExit(1) from None
