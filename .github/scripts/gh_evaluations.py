#!/usr/bin/env python3
"""Repository overlay for the pinned upstream gh skill; no remote writes."""

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import sys
import tempfile


# Also importable through importlib in the existing report tests.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import skill_reports as reports

ROOT = Path(__file__).resolve().parents[2]
OVERLAY = Path(".github/evals/gh")
DEPLOYED = Path(".agents/skills/gh")
UPSTREAM = "ec5b512045db67e5a2a4ff4a1b02660b2fb24390"
SMOKE = ("gh-002", "gh-005", "gh-008", "gh-010")
SETUP = "python3 -I /opt/gh-eval/setup.py --start"
COMPETING = "github-actions-hardening"
APT_SOURCES = [
    "deb [check-valid-until=no signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] "
    f"https://snapshot.debian.org/archive/{archive}/{reports.GH_TASK_BUILD['apt_snapshot']}/ {suite} main"
    for archive, suite in (("debian", "trixie"), ("debian-security", "trixie-security"))
]


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def verify_skill(workspace):
    import yaml

    lock = workspace / "apm.lock.yaml"
    reports.require(
        lock.resolve() == lock.absolute() and lock.is_file(), "Unsafe APM lockfile"
    )
    data = yaml.safe_load(lock.read_text())
    matches = [item for item in data["dependencies"] if item.get("name") == "gh"]
    reports.require(len(matches) == 1, "Ambiguous gh dependency")
    owner = matches[0]
    reports.require(
        owner["repo_url"] == "cli/cli"
        and owner["virtual_path"] == "skills/gh"
        and owner["resolved_commit"] == UPSTREAM,
        "Unreviewed gh upstream ownership or revision",
    )
    files = reports.regular_tree(workspace / DEPLOYED)
    reports.require(
        all(path.stat().st_nlink == 1 for path in files), "Hard-linked gh deployment"
    )
    actual = {
        str(path.relative_to(workspace)): "sha256:"
        + hashlib.sha256(path.read_bytes()).hexdigest()
        for path in files
    }
    reports.require(
        actual == owner["deployed_file_hashes"], "Managed gh file hash mismatch"
    )
    reports.require(
        set(actual) == {str(DEPLOYED / "SKILL.md")}, "Unreviewed upstream gh file set"
    )
    for relative, digest in actual.items():
        deployments = [
            d
            for d in data["deployments"]
            if d["value"] == relative and d["target"] == "codex"
        ]
        reports.require(
            len(deployments) == 1
            and deployments[0]["active_owner"] == "cli/cli/skills/gh"
            and deployments[0]["owners"] == ["cli/cli/skills/gh"]
            and deployments[0]["content_hash"] == digest,
            "APM deployment owner mismatch",
        )
    return workspace / DEPLOYED


def verify_competing(workspace):
    import yaml

    data = yaml.safe_load((workspace / "apm.lock.yaml").read_text())
    owners = [item for item in data["dependencies"] if item["name"] == COMPETING]
    reports.require(
        len(owners) == 1
        and owners[0]["repo_url"] == "github/awesome-copilot"
        and owners[0]["resolved_commit"] == "143a3d976b3c1603cc8932984d5e1f28501cb5fc",
        "Unreviewed competing skill identity",
    )
    source = workspace / ".agents/skills" / COMPETING
    actual = {
        str(p.relative_to(workspace)): "sha256:"
        + hashlib.sha256(p.read_bytes()).hexdigest()
        for p in reports.regular_tree(source)
    }
    reports.require(
        actual == owners[0]["deployed_file_hashes"], "Competing skill hash mismatch"
    )
    return source


def dataset(workspace=ROOT, selected=None):
    files = reports.regular_tree(workspace / OVERLAY)
    reports.require(
        all(path.stat().st_nlink == 1 for path in files),
        "Hard-linked evaluation overlay",
    )
    data = reports.read_json(workspace / OVERLAY / "evals/evals.json")
    reports.require(
        data["skill_name"] == "gh" and bool(data["evals"]), "Invalid gh dataset"
    )
    ids = [entry["id"] for entry in data["evals"]]
    reports.require(
        len(ids) == len(set(ids))
        and all(re.fullmatch(r"gh-\d{3}(?:-[a-z-]+)?", i) for i in ids),
        "Invalid or duplicate gh case IDs",
    )
    reports.require(not selected or set(selected) <= set(ids), "Unknown gh case")
    for entry in data["evals"]:
        contract = entry["contract"]
        reports.require(
            contract["evidence_classification"]
            in ("synthetic", "documentation", "observed-plus-synthetic"),
            "Missing provenance classification",
        )
        reports.require(
            entry["expected_skill"] in ("gh", None), "Invalid activation contract"
        )
        reports.require(
            all((workspace / OVERLAY / f).is_file() for f in entry["files"]),
            "Missing fixture input",
        )
        for relative in entry["files"]:
            reports.require(
                relative.startswith("evals/files/")
                and ".." not in Path(relative).parts,
                "Escaping fixture path",
            )
    return [entry for entry in data["evals"] if not selected or entry["id"] in selected]


def enriched(entry, workspace=ROOT):
    entry = copy.deepcopy(entry)
    files = workspace / OVERLAY / "evals/files"
    entry["contract"]["input_hashes"] = {
        str(Path(relative).relative_to("evals/files")): hashlib.sha256(
            (workspace / OVERLAY / relative).read_bytes()
        ).hexdigest()
        for relative in entry["files"]
    }
    entry["contract"]["fixture_case"] = reports.read_json(
        files / "cases" / (entry["id"] + ".json")
    )
    entry["contract"]["allowed_reads"] = [
        "AGENTS.md", "output/result.json", *entry["contract"]["fixture_case"].get("files", {}),
        "skills/gh/SKILL.md",
        *["skills/" + str(p.relative_to(workspace / ".agents/skills"))
          for p in reports.regular_tree(workspace / ".agents/skills" / COMPETING)],
    ]
    # Native inputs contain only the public protocol; fixtures are private build inputs.
    entry["files"] = []
    # Known-good replay commands are never needed in the native verifier or agent input.
    entry["contract"].pop("good_commands", None)
    return entry


def stage(workspace, destination, selected=None):
    source = verify_skill(workspace)
    competing = verify_competing(workspace)
    entries = dataset(workspace, selected)
    destination = destination.absolute()
    reports.require(
        destination.resolve() == destination and not destination.exists(),
        "Staging requires a new real destination",
    )
    for managed in (".agents", ".apm", ".github/evals"):
        reports.require(
            not destination.is_relative_to(workspace / managed),
            "Staging inside a managed source tree is forbidden",
        )
    reports.require(
        not destination.is_relative_to(workspace), "Stage outside the checkout"
    )
    reports.require(
        not (destination.parent / COMPETING).exists()
        and not (destination.parent / COMPETING).is_symlink(),
        "Competing skill destination exists",
    )
    destination.mkdir(parents=True)
    shutil.copytree(competing, destination.parent / COMPETING)
    subprocess.run(
        ["git", "init", "--quiet", "--template=", str(destination)],
        check=True,
        env={
            **os.environ,
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
        },
    )
    shutil.copyfile(source / "SKILL.md", destination / "SKILL.md")
    shutil.copytree(workspace / OVERLAY / "evals", destination / "evals")
    reports.write_json(
        destination / "evals/evals.json",
        {"skill_name": "gh", "evals": [enriched(e, workspace) for e in entries]},
    )
    # Single standalone BYOG file: fixture model is verifier-owned, never loaded from agent-writable inputs.
    fixture = (
        (workspace / OVERLAY / "evals/files/fixture.py")
        .read_text()
        .rsplit("\nif __name__ ==", 1)[0]
    )
    grader = (workspace / OVERLAY / "evals/grader.py").read_text()
    (destination / "evals/grader.py").write_text(fixture + "\n" + grader)
    native_tasks(destination, entries, workspace)
    return destination


def native_tasks(destination, entries, workspace):
    """Supported BYOT source, leaving skill discovery and grading to the pinned adapter."""
    packages = shlex.join([
        f"{package}={version}" for package, version in reports.GH_TASK_BUILD["apt_packages"].items()
    ])
    sources = shlex.join(APT_SOURCES)
    for original in entries:
        task = destination / "evals/harbor" / original["id"]
        env = task / "environment"
        source = env / "private"
        source.mkdir(parents=True)
        for relative in original["files"]:
            target = source / Path(relative).relative_to("evals/files")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(workspace / OVERLAY / relative, target)
        (env / "input").mkdir()
        (env / "input/README.txt").write_text("Public gh fixture transport. Use gh to obtain observations.\n")
        (env / "Dockerfile").write_text(
            f"FROM {reports.GH_TASK_BUILD['base_image']}\n"
            "RUN rm -f /etc/apt/sources.list.d/* && rm -rf /var/lib/apt/lists/* "
            f"&& printf '%s\\n' {sources} > /etc/apt/sources.list "
            "&& apt-get update --error-on=any "
            f"&& apt-get install -y --no-install-recommends {packages} "
            "&& rm -rf /var/lib/apt/lists/*\n"
            "RUN useradd --create-home --uid 1000 agent && mkdir -p /workspace /opt/gh-eval "
            "&& chmod 700 /opt/gh-eval\n"
            "COPY private /opt/gh-eval/source\n"
            "RUN cp /opt/gh-eval/source/setup.py /opt/gh-eval/setup.py "
            "&& python3 -I /opt/gh-eval/setup.py --build && rm -rf /opt/gh-eval/source\n"
            "WORKDIR /workspace\n"
        )
        (task / "instruction.md").write_text(original["prompt"] + "\n")
        (task / "task.toml").write_text(
            'schema_version = "1.3"\n'
            '[metadata]\nentry_id = ' + json.dumps(original["id"]) + '\n'
            '[agent]\nuser = "agent"\ntimeout_sec = 300.0\n'
            '[verifier]\nuser = "root"\ntimeout_sec = 600.0\n'
            '[environment]\ncpus = 2\nmemory_mb = 4096\nstorage_mb = 2048\n'
            'workdir = "/workspace"\nnetwork_mode = "public"\nskills_dir = "/workspace/skills"\n'
            '[environment.healthcheck]\ncommand = "python3 -I /opt/gh-eval/setup.py --start"\n'
            'interval_sec = 1.0\nretries = 1\n'
        )


def replay_case(entry, *, fault=None, extra_calls=()):
    fixture = module(ROOT / OVERLAY / "evals/files/fixture.py", "fixture")
    setup = module(ROOT / OVERLAY / "evals/files/setup.py", "setup")
    grader = module(ROOT / OVERLAY / "evals/grader.py", "grader")
    with tempfile.TemporaryDirectory(prefix="gh-replay-") as temporary:
        workspace = Path(temporary)
        inputs = workspace / "input"
        for relative in entry["files"]:
            target = inputs / Path(relative).relative_to("evals/files")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / OVERLAY / relative, target)
        (workspace / "output").mkdir()
        env = setup.setup(workspace, inputs)
        socket_path = workspace / "broker/gh.sock"
        broker = setup.start_broker(workspace / ".gh-fixture", socket_path)
        env["GH_FIXTURE_SOCKET"] = str(socket_path)
        try:
            # Replay never inherits API/model credentials or production gh configuration.
            env = {
                k: v
                for k, v in env.items()
                if not re.search(r"TOKEN|SECRET|API_KEY|PASSWORD", k, re.I)
            }
            commands = copy.deepcopy(entry["contract"]["good_commands"])
            if fault == "wrong-repo" and commands:
                commands[0] = [
                    arg.replace("fixture-org/widget", "fixture-fork/other")
                    for arg in commands[0]
                ]
                if "--field" in commands[0]:
                    commands[0] = [
                        arg.replace("owner=fixture-org", "owner=fixture-fork")
                        for arg in commands[0]
                    ]
            if fault == "unsupported":
                commands.insert(0, ["--no-pager"])
            if fault == "pagination":
                commands = [[a for a in cmd if a != "--paginate"] for cmd in commands]
            if fault == "implicit-post":
                commands = [
                    [a for a in cmd if a not in ("--method", "GET")] for cmd in commands
                ]
            if fault == "unauthorized":
                commands.append(
                    ["api", "repos/fixture-org/widget/issues/12", "--method", "POST"]
                )
            if fault == "duplicate":
                commands += [commands[0]]
            calls = []
            for command in commands:
                issued = ["gh", *command]
                if command[:2] == ["run", "watch"] and fault != "unbounded-watch":
                    issued = ["timeout", "30s", *issued]
                result = subprocess.run(
                    issued,
                    cwd=workspace,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                calls.append(
                    {
                        "action": "exec_command",
                        "action_input": {"cmd": shlex.join(issued)},
                        "observation": result.stdout + result.stderr,
                    }
                )
            if not commands:
                result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=workspace,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                calls.append(
                    {
                        "action": "exec_command",
                        "action_input": {"cmd": "git status --porcelain"},
                        "observation": result.stdout,
                    }
                )
            expected = copy.deepcopy(entry["contract"]["expected"])
            if fault == "stale-head":
                expected["status"] = "success"
            if fault == "secret":
                expected["leaked"] = "GH_EVAL_SECRET_SENTINEL_7f03"
            reports.write_json(workspace / "output/result.json", expected)
            if fault == "missing-trace":
                calls = []
            if fault == "tamper-log":
                (workspace / ".gh-fixture/audit.jsonl").write_text("")
            if fault == "tamper-fixture":
                (inputs / "fixture.py").write_text("# replaced")
            if fault == "missing-artifact":
                (workspace / "output/result.json").unlink()
        finally:
            broker.terminate()
            broker.wait(timeout=5)
        # Replay supplies activation evidence synthetically; native runs use native checks.
        return grader.grade(enriched(entry), workspace, [*calls, *extra_calls], True, fixture)


def replay(selected=None):
    entries = dataset(selected=selected)
    good = [replay_case(entry)["custom_metrics"]["gh_gate"] == 1 for entry in entries]
    faults = {
        "gh-001": [
            "wrong-repo",
            "unsupported",
            "unauthorized",
            "missing-trace",
            "tamper-log",
            "tamper-fixture",
            "missing-artifact",
            "secret",
        ],
        "gh-002": ["pagination"],
        "gh-006-changed-head": ["stale-head", "unbounded-watch"],
        "gh-010-partial": ["duplicate"],
        "gh-012": ["implicit-post"],
    }
    bad = [
        replay_case(entry, fault=f)["custom_metrics"]["gh_gate"] == 0
        for entry in entries
        for f in faults.get(entry["id"], [])
    ]
    result = {
        "evidence": "harness replay; synthetic activation; no model or live GitHub validation",
        "good_traces": len(good),
        "good_passed": sum(good),
        "faulty_traces": len(bad),
        "faults_rejected": sum(bad),
    }
    print(json.dumps(result, indent=2))
    reports.require(all(good) and all(bad), "Replay regression failed")
    return result


def native_command(skill, mode, results):
    return [
        "skillevaluator",
        "tier3",
        "evaluate",
        str(skill),
        "--agents",
        "codex",
        "--agent-model",
        "codex=" + reports.POLICY["model"],
        "--env-mode",
        "docker",
        "--skill-workspace-mode",
        "group",
        "--grading-mode",
        "default_plus_custom",
        "--n-attempts",
        str(reports.MODES[mode]),
        "--no-stop-on-pass",
        "--n-concurrent",
        "2",
        "--max-agents",
        "1",
        "--agent-runtime-preflight",
        "--timeout-multiplier",
        "2",
        "--progress",
        "plain",
        "--harbor-keep-jobs",
        "--results-dir",
        str(results),
    ]


def benchmark(args):
    selected = list(SMOKE) if args.smoke else [args.case] if args.case else None
    dataset(selected=selected)
    missing = [
        name
        for name in ("docker", "skillevaluator", "timeout")
        if not shutil.which(name)
    ]
    reports.require(
        not missing, "Unexecuted: missing pinned runtime tools: " + ", ".join(missing)
    )
    reports.require(
        bool(os.environ.get("OPENAI_API_KEY")),
        "Unexecuted: model credential unavailable",
    )
    import importlib.metadata

    versions = {
        "python": sys.version.split()[0],
        "skillevaluator": importlib.metadata.version("skillevaluator"),
        "harbor": importlib.metadata.version("harbor"),
        "docker_compose": subprocess.check_output(
            ["docker", "compose", "version", "--short"], text=True
        ).strip(),
    }
    reports.validate_benchmark_versions(versions)
    from skillevaluator.tier3.harbor import runner
    import inspect

    runner_path = Path(inspect.getfile(runner)).resolve()
    evaluator_root = runner_path.parents[4]
    revision = subprocess.check_output(
        ["git", "-C", str(evaluator_root), "rev-parse", "HEAD"], text=True
    ).strip()
    reports.require(
        revision == reports.POLICY["evaluator_revision"],
        "Unreviewed evaluator revision",
    )
    codex_command = runner.build_harbor_run_command(
        agent="codex", env_mode="docker", dataset_path="unused", job_name="pin-check"
    )
    reports.require(
        "--ak" in codex_command
        and codex_command[codex_command.index("--ak") + 1] == "version=0.155.1",
        "Required pinned Codex patch is absent",
    )
    versions["evaluator_revision"] = revision
    root = args.output.absolute()
    reports.require(
        not root.exists() and root.resolve() == root and not root.is_relative_to(ROOT),
        "Use a new output directory outside checkout",
    )
    root.mkdir(parents=True)
    mode = "standard" if args.smoke else args.mode
    reports.write_json(
        root / "selection.json",
        {
            "case_ids": [e["id"] for e in dataset(selected=selected)],
            "diagnostic_only": bool(selected) or mode != "standard",
            "mode": mode,
        },
    )
    reports.write_json(root / "versions.json", versions)
    skill = stage(ROOT, root / "bundle/gh", selected)
    subprocess.run(
        ["skillevaluator", "tier3", "validate", str(skill), "--strict", "--json"],
        check=True,
    )
    command = native_command(skill, mode, root / "results")
    command += [
        "--evaluated-source-repository",
        os.environ.get("GITHUB_REPOSITORY", "local/diagnostic"),
        "--evaluated-source-revision",
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
    ]
    outcome = "failure"
    try:
        environment = {
            **os.environ,
            "SKILL_EVAL_LLM_PROVIDER": "openai",
            "SKILL_EVAL_LLM_MODEL": reports.POLICY["model"],
            "SKILL_EVAL_JUDGE_MODEL": reports.POLICY["model"],
            "LLM_JUDGE_MODEL": reports.POLICY["model"],
        }
        subprocess.run(
            ["timeout", "--signal=INT", "--kill-after=30s", "8400s", *command],
            cwd=root,
            env=environment,
            check=True,
        )
        outcome = "success"
    finally:
        reports.recover_benchmark(ROOT, root, "gh", mode, outcome)
    from skillevaluator.evaluation import EvaluationService

    run = EvaluationService().discover_latest_results(skill, root / "results")
    reports.require(run is not None, "Missing complete native result")
    result = reports.read_json(run / "result.json")
    reports.require(
        EvaluationService().failure_reason(result) is None
        and result.get("report_status") == "complete",
        "Incomplete native evaluation",
    )
    records = deterministic_gate(
        run, [e["id"] for e in dataset(selected=selected)], reports.MODES[mode]
    )
    reports.write_json(root / "deterministic.json", {"trials": records})
    print(
        json.dumps(
            {
                "evidence": "model-backed",
                "task_trials": len(records),
                "deterministic_gate": "passed",
                "history_published": False,
            }
        )
    )


def redact_publication(value):
    """Supplement native redaction for GitHub token formats and synthetic sentinels."""
    if isinstance(value, str):
        return re.sub(
            r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|GH_EVAL_SECRET_SENTINEL_[A-Za-z0-9_]+)\b",
            "[REDACTED]",
            value,
        )
    if isinstance(value, list):
        return [redact_publication(item) for item in value]
    if isinstance(value, dict):
        return {
            redact_publication(key): redact_publication(item)
            for key, item in value.items()
        }
    return value


def deterministic_gate(run, case_ids, attempts):
    records = []
    for arm in ("with-skill", "without-skill"):
        rewards = sorted((run / "codex" / arm / "trials").glob("*/reward.json"))
        reports.require(
            len(rewards) == len(case_ids) * attempts,
            "Incomplete deterministic trial coverage",
        )
        counts = dict.fromkeys(case_ids, 0)
        for path in rewards:
            reports.require(
                path.resolve() == path.absolute(), "Linked deterministic result"
            )
            reward = reports.read_json(path)
            identity = str(reward.get("entry_id", ""))
            reports.require(identity in counts, "Missing authored case identity")
            counts[identity] += 1
            metrics = reward.get("custom_metrics", {})
            reports.require(
                set(metrics)
                == {
                    "gh_" + k
                    for k in (
                        "evidence",
                        "activation",
                        "commands",
                        "task",
                        "recovery",
                        "authorization",
                        "efficiency",
                        "gate",
                    )
                },
                "Missing deterministic scores",
            )
            reports.require(
                all(type(v) in (int, float) and v in (0, 1) for v in metrics.values()),
                "Invalid deterministic score",
            )
            reports.require(
                metrics["gh_gate"]
                == float(all(v == 1 for k, v in metrics.items() if k != "gh_gate")),
                "Inconsistent deterministic gate",
            )
            if arm == "with-skill":
                reports.require(
                    metrics["gh_gate"] == 1, "With-skill deterministic gate failed"
                )
            records.append({"arm": arm, "case": identity, "metrics": metrics})
        reports.require(
            all(count == attempts for count in counts.values()),
            "Incomplete case/attempt coverage",
        )
    return records


def live(repo):
    reports.require(
        bool(
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", repo)
        ),
        "Expected OWNER/REPO",
    )
    # Fixed GET only, explicit public repository and host; never prints repository data.
    commands = [
        ["api", "--hostname", "github.com", "--method", "GET", "repos/" + repo],
        [
            "api",
            "--hostname",
            "github.com",
            "--method",
            "GET",
            "repos/" + repo + "/issues",
            "--field",
            "per_page=1",
        ],
    ]
    for index, command in enumerate(commands):
        result = subprocess.run(
            ["gh", *command], capture_output=True, text=True, timeout=30
        )
        reports.require(
            result.returncode == 0,
            "Live read unavailable (no response content retained)",
        )
        data = json.loads(result.stdout)
        if index == 0:
            reports.require(
                data.get("private") is False
                and data.get("full_name", "").lower() == repo.lower(),
                "Live suite requires the selected public repository",
            )
        else:
            reports.require(isinstance(data, list), "Unexpected live response shape")
    print(
        json.dumps(
            {
                "evidence": "live read-only",
                "checks_passed": len(commands),
                "model_backed": False,
            }
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "replay", "benchmark", "live", "stage"):
        cmd = sub.add_parser(name)
        cmd.add_argument("skill", choices=["gh"])
        if name in ("replay", "benchmark"):
            cmd.add_argument("--case")
        if name == "benchmark":
            cmd.add_argument("--mode", choices=reports.MODES, default="standard")
            cmd.add_argument("--smoke", action="store_true")
            cmd.add_argument("--output", type=Path, default=Path("/tmp/gh-benchmark"))
        if name == "live":
            cmd.add_argument("--repo", required=True)
        if name == "stage":
            cmd.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.command == "validate":
        verify_skill(ROOT)
        verify_competing(ROOT)
        entries = dataset()
        print(
            json.dumps(
                {
                    "status": "passed",
                    "cases": len(entries),
                    "upstream": UPSTREAM,
                    "cli_contract": "2.102.0",
                }
            )
        )
    elif args.command == "replay":
        replay([args.case] if args.case else None)
    elif args.command == "benchmark":
        reports.require(not (args.smoke and args.case), "Choose --smoke or --case")
        benchmark(args)
    elif args.command == "stage":
        stage(ROOT, args.destination)
    else:
        live(args.repo)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
