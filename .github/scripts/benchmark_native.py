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
import evaluator_profiles as profiles
import gh_candidate
import gh_evaluations as gh
import pester_evaluations as pester
from skill_reports import (MODES, POLICY, benchmark_options, benchmark_policy, local_skill, read_json,
                           recover_benchmark, require, write_json)


ROOT = Path(__file__).resolve().parents[2]
RETAINED_NATIVE_PRODUCER = "skillevaluator-1.0.1-benchmark-native-v2"
NATIVE_PRODUCER = "skillevaluator-1.2.1-benchmark-native-v1"
NATIVE_SOURCE_DIGEST = "sha256:e302395bf4615c57bfeb936e6c097e6b2a22ec80b2179e3351e7b1d361231613"
NATIVE_PATCH_DIGEST = "dc5674786ce86cfeca6ba90bcdeec6cd4f9e6b3fc7d60301b1bfb9a8a61f18d6"
NATIVE_OWNERS = {
    RETAINED_NATIVE_PRODUCER: {
        "backends": (profiles.RELEASE_BENCHMARK, profiles.RETAINED_RELEASE_BENCHMARK),
        "source_tree_digest": "sha256:78dfd05becd4b4e94882aa0305fc58d28a6ef40c10813b384335fd6a7f0be1ef",
        "patch_sha256": "30a03343d670e2b83aeb5519f009549c6528b3cb8235cffc4522aab64b872f57",
    },
    NATIVE_PRODUCER: {
        "backends": (profiles.CURRENT_RELEASE,),
        "source_tree_digest": NATIVE_SOURCE_DIGEST,
        "patch_sha256": NATIVE_PATCH_DIGEST,
    },
}
BACKENDS = {"podman": "aeb-benchmark-docker", "gh": "aeb-gh-fixture"}
DIAGNOSTIC_BACKEND = BACKENDS["podman"]
EXECUTION_BACKENDS = {**BACKENDS, pester.NAME: DIAGNOSTIC_BACKEND}
ENVIRONMENTS = {
    "podman": "skillevaluator.tier3.harbor.secure_docker_environment:SkillEvaluatorSecureDockerEnvironment",
    "gh": "aeb_gh_fixture.backend:TrustedGhEnvironment",
}
CODEX_AGENT = "aeb_gh_fixture.benchmark_codex:BenchmarkCodex"
GH_DATASET_PROFILE = "gh-benchmark-101-v1"
GH_ACCESS_METRIC = "gh_access_policy"
GH_ARMS = {"with_skill": True, "without_skill": False}
NPM_CODEX_VENDOR = "/opt/reviewed/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl"
LOOPBACK_VERIFIER = "services:\n  main:\n    network_mode: none\n"


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


def configure_npm_codex_task(task, profile, *, build_home=None):
    """Pin Codex and its agent-only provider route in an authored image."""
    descriptor = task / "task.toml"
    source = descriptor.read_text()
    config = tomllib.loads(source)
    network = 'network_mode = "public"'
    require(source.count(network) == 1 and "healthcheck" not in config["environment"]
            and config["agent"]["user"] == "agent" and config["verifier"]["user"] == "root",
            "Unexpected native agent or verifier environment")
    descriptor.write_text(source.replace(network, 'network_mode = "allowlist"\nallowed_hosts = ["api.openai.com"]'))

    members = codex_members(profile)
    del members["bin/codex-exec-server"]  # The npm platform package has no standalone exec-server.
    require(set(members) == {"bin/codex", "bin/codex-code-mode-host", "codex-resources/bwrap", "codex-path/rg"}
            and all(re.fullmatch(r"[0-9a-f]{64}", digest) for digest in members.values()),
            "Unexpected Codex package integrity set")
    checksums = shlex.join(f"{digest}  {name}" for name, digest in sorted(members.items()))
    paths = shlex.join(sorted(members))
    package = shlex.quote("@openai/codex@" + profile["cli"])
    version = shlex.quote("codex-cli " + profile["cli"])
    install_home = f"export HOME={shlex.quote(build_home)} && " if build_home else ""
    with (task / "environment/Dockerfile").open("a") as build:
        build.write("\nRUN chgrp -R agent /workspace/skills && chmod -R g+rX,go-w /workspace/skills\n"
                    f"RUN {install_home}npm install --prefix /opt/reviewed --no-audit --no-fund --ignore-scripts "
                    f"--install-strategy=hoisted --registry=https://registry.npmjs.org/ {package} "
                    f"&& cd {NPM_CODEX_VENDOR} && test ! -e bin/codex-exec-server && test ! -L bin/codex-exec-server "
                    f"&& for member in {paths}; do "
                    f'test "$(realpath -- "$member")" = "{NPM_CODEX_VENDOR}/$member" || exit 1; done '
                    f"&& printf '%s\\n' {checksums} | sha256sum --check --strict "
                    "&& chown -hR 0:0 /opt/reviewed && chmod -R a+rX,go-w /opt/reviewed "
                    f"&& ln -s {NPM_CODEX_VENDOR}/bin/codex /usr/local/bin/codex "
                    f'&& test "$(/usr/local/bin/codex --version)" = {version}\n'
                    f"ENV PATH={NPM_CODEX_VENDOR}/codex-path:$PATH\n")


def configure_gh_task(task, profile):
    configure_npm_codex_task(task, profile)


def configure_pester_task(task, profile):
    """Keep the authored scorer and its separate loopback-only container."""
    config = tomllib.loads((task / "task.toml").read_text())
    require(config["verifier"]["environment_mode"] == "separate"
            and config["verifier"]["environment"] == {"network_mode": "no-network", "cpus": 2, "memory_mb": 2048}
            and not config["verifier"].get("env"), "Unexpected Pester verifier environment")
    # The authored image sets HOME=/home/agent. The build's root-owned npm
    # and Codex checks must not initialize caches in the trial user's home.
    configure_npm_codex_task(task, profile, build_home="/root")
    with (task / "environment/Dockerfile").open("a") as build:
        build.write("RUN test ! -e /home/agent/.codex && test ! -L /home/agent/.codex\n")
    # The verifier checks for exactly the loopback interface. A managed egress
    # namespace with no permitted destinations does not satisfy that contract.
    with (task / "tests/docker-compose.yaml").open("x", encoding="utf-8") as override:
        override.write(LOOPBACK_VERIFIER)


def pester_finalizer(skill, emitted):
    profile = read_json(CODEX_PROFILE)
    cases = {entry["id"] for entry in read_json(skill / "evals/evals.json")["evals"]}
    require(set(emitted) == {"codex"} and set(emitted["codex"]) == set(GH_ARMS),
            "Released Pester runner did not stage both arms")
    for arm, tasks in emitted["codex"].items():
        require(len(tasks) == len(cases) and {task.name for task in tasks} == cases,
                "Incomplete staged Pester population")
        for task in tasks:
            peer = task / "environment/skills" / pester.NAME / "SKILL.md"
            require(peer.is_file() is GH_ARMS[arm], "Unexpected staged Pester skill arm")
            configure_pester_task(task, profile)


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


def native_owner(revision, patch):
    """Match a recorded policy to the only release that published it."""
    return next((name for name, pins in NATIVE_OWNERS.items()
                 if pins["backends"][0]["revision"] == revision and patch == "sha256:" + pins["patch_sha256"]), None)


def native_profile(*, backend=None, owner=NATIVE_PRODUCER):
    if backend is None:
        backend = NATIVE_OWNERS[owner]["backends"][0]
    else:
        owner = next((name for name, pins in NATIVE_OWNERS.items()
                      if any(backend is entry for entry in pins["backends"])), None)
        require(owner is not None, "Unsupported native benchmark backend")
    pins = NATIVE_OWNERS[owner]
    return {**backend, "id": owner, "source_tree_digest": pins["source_tree_digest"],
            "patch_sha256": pins["patch_sha256"]}


def native_versions(*, backend=None, owner=NATIVE_PRODUCER):
    if backend is None:
        backend = NATIVE_OWNERS[owner]["backends"][0]
    profile = native_profile(backend=backend)
    return {**profiles.candidate_versions(backend), "patch_sha256": profile["patch_sha256"],
            "source_tree_digest": profile["source_tree_digest"], "producer_profile": profile["id"]}


def adoption_policy():
    return {"schema_version": 1, "runtime": native_versions(), "backends": EXECUTION_BACKENDS,
            "model": POLICY["model"], "agent_reasoning_effort": "high", "judge_reasoning_effort": None}


def validate_adoption(workspace):
    from skill_orchestration import NATIVE_BENCHMARK_POLICY

    require(read_json(workspace / NATIVE_BENCHMARK_POLICY) == adoption_policy(),
            "Released production benchmark policy differs")


def validate_runtime():
    """Verify the launcher owner without changing the prior smoke producer."""
    from evaluator_profiles import validate_install

    validate_install(native_profile())
    return native_versions()


def dataset_profile(name):
    return {"gh": GH_DATASET_PROFILE, pester.NAME: "pester-pilot-v3", "podman": "podman-authored"}[name]


def dataset_sha256(skill):
    return hashlib.sha256((skill / "evals/evals.json").read_bytes()).hexdigest()


def pester_bundle_sha256(skill):
    members = {name: digest for name, digest in pester.manifest(skill).items() if not name.startswith(".git/")}
    return hashlib.sha256(json.dumps(members, sort_keys=True).encode()).hexdigest()


def require_revision(workspace, revision):
    require(re.fullmatch(r"[0-9a-f]{40}", revision), "Invalid benchmark source revision")
    head = subprocess.check_output(["git", "-C", str(workspace), "rev-parse", "HEAD"], text=True, timeout=20)
    require(head.strip() == revision, "Benchmark revision differs from the checkout")


def prepare(workspace, root, name, mode, revision, *, gh_cases=None):
    """Prepare the reviewed dataset and runtime before entering the credential step."""
    from benchmark_smoke import PROVIDER_CREDENTIALS
    from qualify_codex_1691 import acquire

    require(not any(os.environ.get(key) for key in PROVIDER_CREDENTIALS),
            "Benchmark preparation requires a credential-free process")
    require(name in EXECUTION_BACKENDS and mode in MODES
            and (name != pester.NAME or mode == "confirmation"), "Unqualified released benchmark selection")
    require(gh_cases is None or name == "gh", "Case selection is available for local gh benchmarks")
    require_revision(workspace, revision)
    root = root.absolute()
    require(root.resolve() == root and not root.is_relative_to(workspace), "Use a new benchmark directory outside checkout")
    versions = validate_runtime()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    if name == "gh":
        skill = stage_gh(workspace, root / "bundle/gh", gh_cases)
    elif name == pester.NAME:
        skill = pester.stage(workspace, root / "bundle" / name)
    else:
        skill = local_skill(workspace, name, dataset=True)
    validation = [sys.executable, "-B", "-c", "from skillevaluator.cli import cli; cli()",
                  "tier3", "validate", str(skill), "--strict", "--json"]
    with (root / "dataset-validation.json").open("x") as receipt:
        subprocess.run(validation, stdout=receipt, check=True, timeout=90)
    manifest = None
    if name == "gh":
        manifest = prepare_gh_manifest(skill, root).name
    elif name == "podman":
        assets = root / "archive"
        assets.mkdir(mode=0o700)
        acquire(read_json(CODEX_PROFILE), assets)
    (root / "operator-home").mkdir(mode=0o700)
    write_json(root / "versions.json", versions)
    write_json(root / "native-preparation.json", {
        "schema_version": 1, "revision": revision, "skill": name, "mode": mode,
        "backend": EXECUTION_BACKENDS[name], "producer_profile": NATIVE_PRODUCER,
        "dataset_profile": dataset_profile(name),
        "dataset_sha256": dataset_sha256(skill), "gh_manifest": manifest,
        **({"pester_bundle_sha256": pester_bundle_sha256(skill)} if name == pester.NAME else {}),
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


def output_provenance_key(home):
    return home / ".local/state/skillevaluator/output-provenance.key"


@contextmanager
def run_output_provenance(root):
    # Authenticate the result with the same isolated host key used for execution.
    from skillevaluator.tier3.output_provenance import OUTPUT_PROVENANCE_KEY_ENV

    prior = os.environ.get(OUTPUT_PROVENANCE_KEY_ENV)
    os.environ[OUTPUT_PROVENANCE_KEY_ENV] = str(output_provenance_key(root / "operator-home"))
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop(OUTPUT_PROVENANCE_KEY_ENV, None)
        else:
            os.environ[OUTPUT_PROVENANCE_KEY_ENV] = prior


@contextmanager
def provider_environment(home, key, manifest=None):
    from skillevaluator.tier3.output_provenance import OUTPUT_PROVENANCE_KEY_ENV

    original = dict(os.environ)
    names = ("PATH", "TMPDIR", "DOCKER_CONFIG", "DOCKER_HOST", "COMPOSE_PLUGIN_ROOT", "XDG_RUNTIME_DIR")
    env = {name: original[name] for name in names if name in original}
    env[OUTPUT_PROVENANCE_KEY_ENV] = str(output_provenance_key(home))
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
    require(name in EXECUTION_BACKENDS and mode in MODES
            and (name != pester.NAME or mode == "confirmation"), "Invalid released selection")
    require_revision(workspace, revision)
    root = root.absolute()
    require(root.resolve() == root and not root.is_relative_to(workspace), "Invalid prepared benchmark location")
    prepared = read_json(root / "native-preparation.json")
    require(read_json(root / "versions.json") == validate_runtime(), "Prepared benchmark runtime differs")
    skill = root / "bundle" / name if name in ("gh", pester.NAME) else local_skill(workspace, name, dataset=True)
    require(prepared == {"schema_version": 1, "revision": revision, "skill": name, "mode": mode,
                          "backend": EXECUTION_BACKENDS[name], "producer_profile": NATIVE_PRODUCER,
                          "dataset_profile": dataset_profile(name),
                          "dataset_sha256": dataset_sha256(skill), "gh_manifest": prepared.get("gh_manifest"),
                          **({"pester_bundle_sha256": pester_bundle_sha256(skill)} if name == pester.NAME else {})},
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
        require(prepared["gh_manifest"] is None, "Unexpected isolated benchmark approval manifest")
        finalizer = (partial(pester_finalizer, skill) if name == pester.NAME
                     else partial(podman_finalizer, skill, root / "archive"))

    options = benchmark_options(name)
    include = [skill.parent / gh.COMPETING] if name == "gh" else None
    with provider_environment(root / "operator-home", key, manifest):
        return run_harbor_eval(
            skill, ["codex"], env_mode=EXECUTION_BACKENDS[name], n_attempts=MODES[mode], n_concurrent=POLICY["concurrency"],
            max_agents=1, stop_on_pass=False, grading_mode=options["grading_mode"],
            skill_workspace_mode=options["workspace_mode"], include_skills=include,
            custom_dockerfile_mode="disabled" if name == "podman" else "preserve",
            timeout_multiplier=POLICY["timeout_multiplier"], agent_runtime_preflight=True, keep_harbor_jobs=True,
            output_dir=resolve_results_root(skill, root / "results"), agent_models={"codex": POLICY["model"]},
            evaluated_source={"repository": REPOSITORY, "commit": revision}, progress_reporter=progress_reporter,
            _operator_task_finalizer=finalizer,
        )


def validate_trial_population(run, agent, name, cases, attempts, agent_selector):
    """Join each released rollup slot to its distinct physical trial."""
    from skill_evidence import number, read_json, safe_path, token, validate_summary_rollups

    seen = set()
    rewards = {arm: [] for arm in GH_ARMS}
    for arm, present in GH_ARMS.items():
        directory = run / "codex" / arm.replace("_", "-")
        summary = read_json(directory / "summary.json")
        rollup = summary["pass_at_k"]
        require(rollup == agent["pass_at_k"][arm] and set(rollup["cases"]) == set(cases)
                and summary["execution_status"] == "succeeded" and not summary["execution_errors"]
                and summary["num_trials"] == summary["scored_attempts"] == len(cases) * attempts,
                "Released trial summary differs from the complete arm")
        validate_summary_rollups(rollup, rollup["cases"], cases, attempts, False, versioned=True)
        trials = safe_path(directory / "trials", directory=True)
        expected = set()
        for case in cases:
            rows = rollup["cases"][case]["attempts"]
            require(len(rows) == attempts, "Released case attempt population differs")
            for ordinal, row in enumerate(rows, 1):
                token(row["trial"])
                trial = row["trial"]
                require(row["attempt"] == ordinal and trial not in expected,
                        "Duplicate or misplaced released attempt")
                expected.add(trial)
                reward = read_json(trials / trial / "reward.json")
                result = read_json(trials / trial / "result.json")
                token(result["id"])
                require(result["id"] not in seen and result["trial_name"] == reward["trial_id"] == trial
                        and result["exception_info"] is None and result["finished_at"] is not None
                        and result["config"]["agent"]["name"] == agent_selector
                        and result["agent_info"]["name"] == "codex"
                        and result["agent_info"]["version"] == POLICY["codex"]
                        and result["config"]["environment"]["import_path"] == ENVIRONMENTS[name]
                        and result["config"]["timeout_multiplier"] == POLICY["timeout_multiplier"]
                        and reward["entry_id"] == case and reward["has_skill"] is present
                        and reward["metric_set"] == "skill-evaluator-default-v2"
                        and reward["score_policy"] == summary["score_policy"]
                        and result["task_name"] == (case if name == "gh" else f"nvidia/skillevaluator-{case}-{arm.replace('_', '-')}"),
                        "Released trial identity or policy differs")
                seen.add(result["id"])
                score = reward["overall"]
                number(score)
                require(score == row["score"] == result["verifier_result"]["rewards"]["overall"],
                        "Released trial score differs from its verifier or rollup")
                rewards[arm].append({**reward, "_attempt_ordinal": ordinal, "_trial_name": trial})
        require({member.name for member in trials.iterdir()} == expected, "Unexpected released trial member")
    return rewards


def validate_released_aggregates(agent, rewards, cases):
    """Recompute released aggregates from matched rewards, including explicit N/A metrics."""
    from skillevaluator.tier3.harbor import metrics
    from skillevaluator.tier3.harbor.collector import _average_overall, _compute_lift

    not_applicable = {}
    for arm, population in rewards.items():
        condition = agent["conditions"][arm]
        require(len(population) == condition["expected_attempts"] == condition["scored_attempts"],
                "Incomplete released aggregate population")
        for reward in population:
            score = metrics.overall_score(reward)
            require(reward["score_policy"] == metrics.DEFAULT_SCORE_POLICY and score is not None
                    and reward["overall"] == round(score, 4), "Released trial metric disagreement")
        means, metric_set, active = metrics.average_metrics(population)
        skipped = not_applicable[arm] = metrics.not_applicable_metrics(population, active)
        require(metric_set == "skill-evaluator-default-v2" and agent[arm] == means
                and agent["not_applicable_metrics"][arm] == skipped
                and agent["dimensions_" + arm] == metrics.dimension_scores(means, skipped),
                "Released arm metric or applicability disagreement")

    with_rewards, without_rewards = (rewards[arm] for arm in GH_ARMS)
    lift = _compute_lift(agent["with_skill"], agent["without_skill"], with_rewards, without_rewards, cases,
                         score_policy=metrics.DEFAULT_SCORE_POLICY,
                         with_not_applicable=not_applicable["with_skill"],
                         without_not_applicable=not_applicable["without_skill"])
    if ("judge_mixed_cases" not in lift and not lift["basis"]["excluded_case_entries"]
            and not lift["basis"]["excluded_metrics"]):
        with_score, without_score = map(_average_overall, (with_rewards, without_rewards))
        lift["overall"] = {"with_skill": with_score, "without_skill": without_score,
                           "delta": round(with_score - without_score, 4)}
    require(agent["lift"] == lift, "Released lift differs from its paired rewards")


def validate_collected_pair(result, run, root, name, mode, revision, cases, *, agent_selector=CODEX_AGENT,
                            statistics=None):
    """Require the selected native report and complete released trial population."""
    from skillevaluator import __version__
    from skillevaluator.evaluation import EvaluationService
    from skillevaluator.tier3.harbor.report_data import load_dataset_snapshot

    from skill_evidence import safe_path
    from skill_pages import REPOSITORY
    from skill_reports import metric_rows

    policy = released_policy(name)
    require(EvaluationService.failure_reason(result) is None and result["report_status"] == "complete"
            and result["execution_status"] == "succeeded" and result["skill_name"] == name
            and result["score_policy"] == policy["scoring_policy"]
            and result["metric_set"] == "skill-evaluator-default-v2", "Incomplete or incompatible released benchmark")
    require(Path(result["run_dir"]) == run and run.resolve() == run and run.parent == root / "results" / name
            and (run / "report.html").is_file() and not (run / "report.html").is_symlink(),
            "Missing or unsafe released benchmark report")
    config = read_json(run / "run_config.json")
    require(config == result["run_config"], "Released benchmark configuration differs from the report")
    require(config["evaluated_source"] == {"repository": REPOSITORY, "commit": revision}
            and config["provider"] == {"name": POLICY["provider"], "model": POLICY["model"]}
            and config["grading"]["mode"] == policy["grading"] and config["task_source"] == policy["task_source"]
            and config["skill_workspace"]["mode"] == policy["workspace_mode"],
            "Released benchmark source or execution policy differs")
    judge = config["judge"]
    require(judge["enabled"] is True and judge["provider"] == POLICY["provider"] and judge["model"] == POLICY["model"]
            and judge["override_applied"] is True and "reasoning_effort" in judge and judge["reasoning_effort"] is None,
            "Released benchmark judge policy differs")
    harbor = config["harbor"]
    require(harbor["environment"]["value"] == BACKENDS[name] and harbor["n_attempts"] == MODES[mode]
            and harbor["n_concurrent"] == POLICY["concurrency"] and harbor["stop_on_pass"] is False
            and harbor["timeout_multiplier"] == POLICY["timeout_multiplier"], "Released benchmark attempt policy differs")
    safe_path(run / "dataset_snapshot.json")
    snapshot = load_dataset_snapshot(run)
    require(snapshot is not None and snapshot["evaluator_version"] == __version__,
            "Missing or incompatible released dataset snapshot")
    ids = [str(entry["id"]) for entry in snapshot["dataset"]]
    require(set(ids) == set(cases) and len(ids) == len(cases) == result["dataset_summary"]["total_tasks"]
            and snapshot["dataset_digest"] == result["dataset_digest"]
            and snapshot["dataset_summary"] == result["dataset_summary"], "Released benchmark dataset differs")
    require(set(result["agents"]) == {"codex"}, "Released benchmark agent roster differs")
    agent = result["agents"]["codex"]
    require(agent["model"] == POLICY["model"] and set(agent["conditions"]) == set(GH_ARMS),
            "Released benchmark arm or model differs")
    for arm in agent["conditions"].values():
        require(arm["execution_status"] == "succeeded" and not arm["execution_errors"]
                and arm["scored_attempts"] == arm["expected_attempts"] == len(cases) * MODES[mode],
                "Incomplete released benchmark arm")
    rewards = validate_trial_population(run, agent, name, cases, MODES[mode], agent_selector)
    validate_released_aggregates(agent, rewards, cases)
    if name == "gh":
        gh.deterministic_gate(run, cases, MODES[mode], authorization_metric=GH_ACCESS_METRIC)
    if statistics is not None:
        advisory = advisory_statistics(agent, rewards, cases, MODES[mode])
        if advisory:
            statistics.update(advisory, not_applicable_metrics=agent["not_applicable_metrics"])
    return metric_rows(agent)


def advisory_statistics(agent, rewards, cases, attempts):
    """Recompute upstream report statistics from the already admitted reward population."""
    from skillevaluator.tier3.harbor.collector import _pass_summary
    from skillevaluator.tier3.harbor.run_statistics import ArmInput, agent_statistics

    if not agent.get("lift_uncertainty") or "reliability" not in agent:
        return {}
    try:
        arms = {
            name: ArmInput(rows, "succeeded", _pass_summary(
                rows, n_attempts=attempts, pass_threshold=0.5, expected_cases=len(cases), expected_case_ids=cases))
            for name, rows in rewards.items()
        }
        expected = agent_statistics(arms, expected_case_ids=cases, stop_on_pass=False, lift_eligible=True)
        if any(expected[field] != agent[field] for field in ("lift_uncertainty", "reliability")):
            return {}
        interval = expected["lift_uncertainty"]["effectiveness"]
        if interval is not None and (interval["partial"] or interval["n_cases"] != len(cases)):
            expected["lift_uncertainty"]["effectiveness"] = None
        return expected
    except (ArithmeticError, KeyError, TypeError, ValueError):
        return {}


def statistics_summary(statistics):
    if not statistics:
        return []
    lines = []
    interval = statistics["lift_uncertainty"]["effectiveness"]
    if interval and interval["ci_low"] is not None and interval["ci_high"] is not None:
        lines += [f"Case-weighted lift {interval['estimate']:+.4f}, 95% interval "
                  f"[{interval['ci_low']:+.4f}, {interval['ci_high']:+.4f}]. "
                  f"{interval['n_cases']} paired cases, {interval['precision'].replace('_', ' ')} precision."]
        if interval["ci_low"] <= 0 <= interval["ci_high"]:
            lines.append("The interval includes zero.")
    for name, row in statistics["reliability"].items():
        if row["k"] > 1 and row["pass_at_k"] is not None and row["pass_hat_k"] is not None:
            omitted = ", ".join(statistics["not_applicable_metrics"][name]) or "none"
            lines.append(f"{name.replace('_', ' ')} ({row['n_cases']} cases). "
                         f"Pass@{row['k']} {row['pass_at_k']:.1%}, pass^{row['k']} {row['pass_hat_k']:.1%}. "
                         f"Metrics outside this arm’s rubric: {omitted}.")
    if not lines:
        return []
    return ["", "### Advisory benchmark statistics", "", *lines]


def released_policy(name, *, owner=NATIVE_PRODUCER):
    require(name in BACKENDS and owner in NATIVE_OWNERS, "Unsupported released score policy")
    if owner == RETAINED_NATIVE_PRODUCER:
        return read_json(ROOT / ".github/evals/benchmark-native-101-policies.json")[name]
    profile = NATIVE_OWNERS[owner]["backends"][0]
    options = benchmark_options(name)
    return {**benchmark_policy(name), "grading": options["grading_mode"], "workspace_mode": options["workspace_mode"],
            "evaluator_revision": profile["revision"], "harbor": profile["harbor"],
            "python": profile["python"], "environment": BACKENDS[name],
            "producer_profile": owner, "scoring_policy": profile["scoring"],
            "judge_contract": "skill-evaluator-judges-v2", "lock_sha256": profile["lock_sha256"],
            "task_source": "native_harbor" if name == "gh" else "evals_json",
            "dataset_profile": GH_DATASET_PROFILE if name == "gh" else "podman-authored"}


def score_series(name, mode, *, owner=NATIVE_PRODUCER):
    require(mode in MODES, "Unsupported released score mode")
    pins = NATIVE_OWNERS[owner]
    identity = [released_policy(name, owner=owner), pins["patch_sha256"], pins["backends"][0]["codex_tool_surface"], mode]
    material = json.dumps(identity, sort_keys=True).encode()
    return hashlib.sha256(material).hexdigest()[:16]


def score_record(workspace, root, name, mode, revision, *, selected=None, statistics=None):
    """Project complete released scores into their own versioned record."""
    from skillevaluator.tier3.dataset_utils import load_dataset_entries

    from skill_evidence import select_run

    require(name in BACKENDS, "Released diagnostic suite cannot produce standard scores")
    root, skill, _ = validate_preparation(workspace, root, name, mode, revision)
    if (root / "provenance.json").exists():
        require(read_json(root / "provenance.json").get("status") != "incomplete",
                "Incomplete released recovery cannot produce benchmark scores")
    cases = [str(entry["id"]) for entry in load_dataset_entries(skill / "evals/evals.json")]
    if name == "gh":
        require(cases == [entry["id"] for entry in gh.dataset(workspace)],
                "Released score report requires the full authored gh cohort")
    run = select_run(root, name, selected)
    result = read_json(run / "result.json")
    metrics = validate_collected_pair(result, run, root, name, mode, revision, cases, statistics=statistics)
    return {"schema_version": 1, "skill": name, "mode": mode, "revision": revision,
            "series": score_series(name, mode), "policy": released_policy(name), "patch_sha256": NATIVE_PATCH_DIGEST,
            "dataset_digest": result["dataset_digest"], "metrics": metrics}


def recover(workspace, root, name, mode, revision, outcome):
    root, _, _ = validate_preparation(workspace, root, name, mode, revision)
    with run_output_provenance(root):
        recover_benchmark(workspace, root, name, mode, outcome, environment=EXECUTION_BACKENDS[name])
    if outcome != "success":
        original = read_json(root / "provenance.json")
        score_provenance = ({"native_policy": released_policy(name), "native_series": score_series(name, mode)}
                            if name in BACKENDS else {})
        write_json(root / "provenance.json", {**original, "skill": name, "mode": mode, "revision": revision,
                                             **score_provenance})


def diagnostic_report(workspace, root, name, mode, revision):
    from skill_reports import capture_benchmark_custom, diagnostic_benchmark_report

    require(name == pester.NAME and os.environ.get("GITHUB_SHA") == revision, "Unqualified diagnostic report scope")
    root, _, _ = validate_preparation(workspace, root, name, mode, revision)
    with run_output_provenance(root):
        capture_benchmark_custom(workspace, root, name)
        diagnostic_benchmark_report(workspace, root, name, mode)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("verify-runtime")
    for command in ("prepare", "execute", "recover", "score-report", "diagnostic-report", "operation"):
        entry = subcommands.add_parser(command)
        entry.add_argument("root", type=Path)
        suites = {"score-report": BACKENDS, "diagnostic-report": (pester.NAME,)}
        entry.add_argument("skill", choices=suites.get(command, EXECUTION_BACKENDS))
        entry.add_argument("mode", choices=MODES)
        entry.add_argument("revision")
        if command == "prepare":
            entry.add_argument("--gh-case", action="append")
        if command in ("recover", "operation"):
            entry.add_argument("outcome", choices=("success", "failure", "cancelled", "skipped"))
        if command in ("score-report", "operation"):
            entry.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.command in ("prepare", "execute"):
        validate_adoption(ROOT)
    if args.command == "verify-runtime":
        validate_runtime()
        return 0
    if args.command == "prepare":
        prepare(ROOT, args.root, args.skill, args.mode, args.revision, gh_cases=args.gh_case)
        return 0
    if args.command == "recover":
        recover(ROOT, args.root, args.skill, args.mode, args.revision, args.outcome)
        return 0
    if args.command == "diagnostic-report":
        diagnostic_report(ROOT, args.root, args.skill, args.mode, args.revision)
        return 0
    if args.command == "operation":
        from skill_reports import operation_receipt

        with run_output_provenance(args.root):
            operation_receipt(ROOT, args.root, args.skill, args.mode, args.outcome, args.destination)
        return 0
    if args.command == "score-report":
        from skill_evidence import select_run, write_outputs
        from skill_reports import summary, usage_summary

        run = select_run(args.root, args.skill, None)
        statistics = {}
        record = score_record(ROOT, args.root, args.skill, args.mode, args.revision, selected=run.name,
                              statistics=statistics)
        if args.skill == "gh":
            gate = gh.deterministic_gate(run, [entry["id"] for entry in gh.dataset(ROOT)], MODES[args.mode],
                                         authorization_metric=GH_ACCESS_METRIC)
            write_json(args.root / "deterministic.json", {"trials": gate})
        publications = {"released-scores.json": record}
        advisory = statistics_summary(statistics)
        if advisory:
            publications["advisory-statistics.json"] = statistics
        write_outputs(publications, args.destination, workspace=ROOT, input_path=args.root)
        lines = [f"## {args.skill} {args.mode} benchmark", "", "| Metric | Score |", "| --- | --- |"]
        lines.extend(f"| {row['name']} | {row['value']:.4f} |" for row in record["metrics"])
        lines.extend(["", f"Dataset `{record['dataset_digest']}`", f"Source `{args.revision}`"])
        summary(lines + advisory + usage_summary(run))
        return 0
    require(args.command == "execute", "Unknown released benchmark command")
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
