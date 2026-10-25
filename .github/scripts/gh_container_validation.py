#!/usr/bin/env python3
"""Credential-free checks of the staged native Docker CLI/broker/verifier boundary."""

import asyncio
import json
from pathlib import Path
import shlex
import signal
import subprocess
import tempfile
import tomllib
import uuid

import gh_evaluations as gh
from skillevaluator.tier3.harbor.adapter import _task_environment_context_hash, stage_native_harbor_tasks


SELECTED = ("gh-001", "gh-003", "gh-007", "gh-010")


def run(*argv, check=True):
    return subprocess.run(argv, check=check, capture_output=True, text=True, timeout=600)


async def compose_lifecycle(root, prefix):
    """One real staged Harbor task, without an agent, credentials or inference."""
    from harbor.environments.docker.docker import DockerEnvironment
    from harbor.models.task.config import NetworkMode, NetworkPolicy, TaskConfig
    from harbor.models.trial.paths import TrialPaths

    skill = gh.stage(gh.ROOT, root / "bundle/gh", ["gh-003"])
    task, = stage_native_harbor_tasks(
        skill, root / "tasks", with_skill=True, grading_mode="default_plus_custom",
        workspace_mode="group", workspace_skill_paths=[skill.parent / gh.COMPETING],
    )
    config = TaskConfig.model_validate(tomllib.loads((task / "task.toml").read_text()))
    context_digest = _task_environment_context_hash(task / "environment")
    paths = TrialPaths(root / "trial")
    paths.mkdir()
    mounts = [{"type": "bind", "source": str(paths.agent_dir), "target": "/logs/agent"}]
    environment = DockerEnvironment(
        environment_dir=task / "environment", environment_name=prefix, session_id=prefix,
        trial_paths=paths, task_env_config=config.environment, mounts=mounts,
        network_policy=NetworkPolicy(network_mode=NetworkMode.NO_NETWORK),
    )
    image_ids = []
    image_name = None
    override_paths = []
    try:
        await environment.start(force_build=True)
        override_paths = [environment._mounts_compose_path, environment._resources_compose_path]
        effective = json.loads((await environment._run_docker_compose_command(
            ["config", "--format", "json"])).stdout)
        main = effective["services"]["main"]
        if main["network_mode"] != "none" or main.get("privileged", False):
            raise ValueError("Harbor Compose isolation mismatch")
        volumes = main.get("volumes", [])
        if len(volumes) != 1 or any(volume.get(key) != value for volume in volumes
                for key, value in (("type", "bind"), ("source", str(paths.agent_dir)), ("target", "/logs/agent"))):
            raise ValueError("Unexpected Harbor Compose mount")
        if main.get("environment"):
            raise ValueError("Unexpected container environment inheritance")
        limits = main["deploy"]["resources"]["limits"]
        if float(limits["cpus"]) != config.environment.cpus or int(limits["memory"]) != config.environment.memory_mb * 1024**2:
            raise ValueError("Harbor Compose resource limit mismatch")
        normalized = {"network_mode": main["network_mode"], "limits": limits,
                      "mounts": [{"type": "bind", "target": "/logs/agent"}],
                      "command": main["command"], "environment": main.get("environment", {})}
        print(json.dumps({"evidence": "Harbor Compose configuration", "configuration": normalized,
                          "task_context_digest": context_digest}), flush=True)
        container = (await environment._run_docker_compose_command(["ps", "--quiet", "main"])).stdout.strip()
        inspected, = json.loads(run("docker", "inspect", container).stdout)
        image_name = inspected["Config"]["Image"]
        if inspected["Config"]["Labels"].get("com.docker.compose.project") != prefix:
            raise ValueError("Unexpected Harbor container owner")
        image_ids.append(inspected["Image"])
        if inspected["State"]["Status"] != "running" or inspected["HostConfig"]["NetworkMode"] != "none":
            raise ValueError("Harbor container not ready or isolated")
        if inspected["HostConfig"]["Privileged"] or len(inspected["Mounts"]) != 1:
            raise ValueError("Unexpected Harbor privileges or mounts")
        if (inspected["HostConfig"]["Memory"] != config.environment.memory_mb * 1024**2
                or inspected["HostConfig"]["NanoCpus"] != config.environment.cpus * 10**9):
            raise ValueError("Harbor container resource limit mismatch")
        if (await environment.exec("id -u", user="agent")).stdout.strip() != "1000":
            raise ValueError("Harbor agent is privileged")
        if (await environment.exec(gh.SETUP, user="root")).return_code:
            raise ValueError("Harbor fixture setup failed")
        for forbidden in ("cat /opt/gh-eval/state/case.json", "cat /opt/gh-eval/state/audit.jsonl"):
            if (await environment.exec(forbidden, user="agent")).return_code == 0:
                raise ValueError("Harbor exposed private fixture data")
        marker = root / "transfer.txt"
        marker.write_text("credential-free Compose transfer\n")
        await environment.upload_file(marker, "/tmp/compose-transfer.txt")
        downloaded = root / "roundtrip.txt"
        await environment.download_file("/tmp/compose-transfer.txt", downloaded)
        if downloaded.read_bytes() != marker.read_bytes():
            raise ValueError("Harbor Compose copy mismatch")
        if (await environment.exec("exit 7", user="agent")).return_code != 7:
            raise ValueError("Harbor Compose lost command failure")
        await environment._run_docker_compose_command(["up", "--detach", "--wait"])
        repeated = (await environment._run_docker_compose_command(["ps", "--quiet", "main"])).stdout.strip()
        if container != repeated:
            raise ValueError("Unchanged Compose up recreated the Harbor container")
        # End through an actual nonzero Compose command, then the same finally path.
        try:
            await environment._run_docker_compose_command(["exec", "-T", "main", "sh", "-c", "exit 9"])
        except RuntimeError as error:
            if "Return code: 9." not in str(error):
                raise
        else:
            raise ValueError("Harbor Compose swallowed a checked command failure")
        return {"evidence": "credential-free Harbor Compose lifecycle", "model_trials": 0,
                "compose": run("docker", "compose", "version", "--short").stdout.strip(),
                "configuration": normalized, "repeated_up": "same-container",
                "task_context_digest": context_digest}
    finally:
        # Harbor logs teardown errors; independently enforce observable cleanup.
        for path in (environment._mounts_compose_path, environment._resources_compose_path):
            if path is not None and path not in override_paths:
                override_paths.append(path)
        try:
            await environment.stop(delete=True)
        finally:
            remaining = {}
            for kind in ("container", "network", "volume", "image"):
                result = run("docker", kind, "ls", *(["--all"] if kind in ("container", "image") else []),
                             "--quiet", "--filter", "label=com.docker.compose.project=" + prefix)
                remaining[kind] = result.stdout.split()
            # Observe production teardown before any fallback: cleanup cannot hide a regression.
            if any(remaining.values()):
                for kind, resources in remaining.items():
                    for resource in resources:
                        run("docker", kind, "rm", *(["--force"] if kind == "container" else []),
                            resource, check=False)
                raise ValueError("Harbor Compose resource cleanup incomplete")
            if any(path.exists() for path in override_paths if path is not None):
                raise ValueError("Harbor Compose temporary override cleanup incomplete")
            for image in image_ids:
                if run("docker", "image", "inspect", image, check=False).returncode == 0:
                    if image_name is not None:
                        run("docker", "image", "rm", image_name, check=False)
                    raise ValueError("Harbor Compose image cleanup incomplete")


def validate():
    if run("docker", "compose", "version", "--short").stdout.strip() != gh.reports.POLICY["docker_compose"]:
        raise ValueError("Reviewed Docker Compose runtime required")
    prefix = "gh-eval-validation-" + uuid.uuid4().hex[:12]
    resources = []
    # Make interruption follow the same exact-resource cleanup path as test failures.
    def interrupted(signum, frame):
        raise KeyboardInterrupt

    old = {s: signal.signal(s, interrupted) for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        with tempfile.TemporaryDirectory(prefix=prefix) as temporary:
            root = Path(temporary)
            lifecycle_root = root / "compose"
            lifecycle_root.mkdir()
            print(json.dumps(asyncio.run(compose_lifecycle(lifecycle_root, prefix + "-compose"))), flush=True)
            skill = gh.stage(gh.ROOT, root / "bundle/gh", list(SELECTED))
            entries = {e["id"]: e for e in gh.dataset(selected=SELECTED)}
            tested = 0
            for with_skill in (True, False):
                tasks = stage_native_harbor_tasks(
                    skill, root / str(with_skill), with_skill=with_skill,
                    grading_mode="default_plus_custom", workspace_mode="group",
                    workspace_skill_paths=[skill.parent / gh.COMPETING],
                )
                for task in tasks:
                    if not with_skill and task.name not in ("gh-001", "gh-003"):
                        continue
                    name = f"{prefix}-{tested}"
                    resources.append(name)
                    run("docker", "build", "--label", "gh-eval-validation=" + prefix,
                        "--tag", name, str(task / "environment"))
                    run("docker", "run", "--detach", "--name", name, "--network", "none",
                        "--label", "gh-eval-validation=" + prefix, name, "sleep", "600")
                    installed = run("docker", "exec", "--user", "root", name,
                        "dpkg-query", "--show", "--showformat=${Package}\t${Version}\t${Status}\n",
                        *gh.reports.GH_TASK_BUILD["apt_packages"]).stdout
                    expected = {
                        (package, version, "install ok installed")
                        for package, version in gh.reports.GH_TASK_BUILD["apt_packages"].items()
                    }
                    if {tuple(line.split("\t")) for line in installed.splitlines()} != expected:
                        raise ValueError("installed task package versions differ from reviewed pins")
                    # Check the resulting image, including any adapter-added build steps.
                    sources = run("docker", "exec", "--user", "root", name,
                        "cat", "/etc/apt/sources.list").stdout
                    if sources != "\n".join(gh.APT_SOURCES) + "\n":
                        raise ValueError("apt sources differ from signed fixed snapshots")
                    run("docker", "exec", "--user", "root", name, "python3", "-I", "-c",
                        "from pathlib import Path; assert not list(Path('/etc/apt/sources.list.d').iterdir())")
                    run("docker", "exec", "--user", "root", name,
                        "python3", "-I", "/opt/gh-eval/setup.py", "--start")
                    run("docker", "cp", str(task / "tests"), name + ":/tests")
                    run("docker", "exec", "--user", "root", name, "chmod", "700", "/tests")
                    agent = ("docker", "exec", "--user", "agent", "--workdir", "/workspace", name)
                    if run(*agent, "id", "-u").stdout.strip() != "1000":
                        raise ValueError("agent is privileged")
                    for forbidden in (
                        "cat /opt/gh-eval/state/case.json",
                        "cat /opt/gh-eval/state/audit.jsonl",
                        "cat /tests/entry.json",
                        "printf '%s' forged > /opt/gh-eval/state/audit.jsonl",
                        "printf '%s' forged > /usr/local/bin/gh",
                        "printf '%s' forged > /run/gh-eval/gh.sock",
                    ):
                        if run(*agent, "sh", "-c", forbidden, check=False).returncode == 0:
                            raise ValueError("private fixture access succeeded")
                    if run(*agent, "test", "-e", "/workspace/input/cases", check=False).returncode == 0:
                        raise ValueError("case definitions exposed as public inputs")
                    # Directly inspect the broker environment as root, never print it.
                    probe = """import pathlib
for p in pathlib.Path('/proc').glob('*/cmdline'):
 try:
  if b'--serve' in p.read_bytes():
   keys=[v.split(b'=',1)[0] for v in p.with_name('environ').read_bytes().split(b'\\0')]
   assert not any(any(k in name for k in (b'TOKEN',b'SECRET',b'API_KEY',b'PASSWORD')) for name in keys)
 except (FileNotFoundError,ProcessLookupError): pass
"""
                    run("docker", "exec", "--user", "root", name, "python3", "-c", probe)
                    steps = []
                    def observed(command):
                        result = run(*agent, "sh", "-c", command, check=False)
                        identity = str(len(steps))
                        steps.append({"source": "agent", "tool_calls": [{"tool_call_id": identity,
                            "function_name": "bash", "arguments": {"command": command}}],
                            "observation": {"results": [{"source_call_id": identity,
                            "content": result.stdout + result.stderr}]}})
                        return result

                    if with_skill:
                        if observed("cat /workspace/skills/gh/SKILL.md").returncode:
                            raise ValueError("skill inaccessible")
                    elif run(*agent, "test", "-e", "/workspace/skills/gh", check=False).returncode == 0:
                        raise ValueError("target skill present in baseline")
                    commands = entries[task.name]["contract"]["good_commands"]
                    if task.name == "gh-003":
                        commands = [commands[-1] + ["--slurp"]]
                    for command in commands:
                        result = observed(shlex.join(["gh", *command]))
                        if result.returncode:
                            raise ValueError("known-good CLI call failed")
                        if task.name == "gh-007" and command[:2] == ["api", "repos/fixture-org/widget/issues"]:
                            ids = [item for page in result.stdout.splitlines() for item in json.loads(page)]
                            if ids != list(range(1, 32)):
                                raise ValueError("incomplete or PR-mixed issue collection")
                            raw_command = command[:command.index("--jq")]
                            raw = observed(shlex.join(["gh", *raw_command]))
                            slurp = observed(shlex.join(["gh", *raw_command, "--slurp"]))
                            pages = json.loads(slurp.stdout)
                            if raw.returncode or slurp.returncode or len(pages) != 2 or json.loads(raw.stdout) != [
                                item for page in pages for item in page
                            ]:
                                raise ValueError("REST raw/slurp page semantics differ")
                        if task.name == "gh-003":
                            pages = json.loads(result.stdout)
                            ids = [thread["id"] for page in pages for thread in
                                   page["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]]
                            if ids != ["T1", "T2"]:
                                raise ValueError("incomplete slurped review-thread collection")
                    payload = json.dumps(entries[task.name]["contract"]["expected"])
                    if observed("printf '%s\\n' " + shlex.quote(payload) + " > output/result.json").returncode:
                        raise ValueError("authorized result write failed")
                    trajectory = root / "trajectory.json"
                    trajectory.write_text(json.dumps({"steps": steps}))
                    run("docker", "exec", "--user", "root", name, "mkdir", "-p", "/logs/agent", "/logs/verifier")
                    run("docker", "cp", str(trajectory), name + ":/logs/agent/trajectory.json")
                    run("docker", "exec", "--user", "root", name, "python3", "/tests/grader.py")
                    reward = json.loads(run("docker", "exec", "--user", "root", name,
                        "cat", "/logs/verifier/reward.json").stdout)
                    if reward["custom_metrics"]["gh_gate"] != float(with_skill):
                        raise ValueError("unexpected production verifier gate")
                    if reward["custom_metrics"]["gh_authorization"] != 1:
                        raise ValueError("authorized calls rejected")
                    if task.name == "gh-003":
                        if any(reward["custom_metrics"]["gh_" + dimension] != 1 for dimension in
                               ("evidence", "commands", "task", "recovery", "authorization", "efficiency")):
                            raise ValueError("common task performance failed")
                    tested += 1
            print(json.dumps({"evidence": "credential-free native Docker boundary", "containers_passed": tested,
                "model_trials": 0, "network": "none", "task_build": gh.reports.GH_TASK_BUILD}))
    finally:
        for name in reversed(resources):
            run("docker", "rm", "--force", name, check=False)
            run("docker", "image", "rm", name, check=False)
        for s, handler in old.items():
            signal.signal(s, handler)
        # Cleanup failures are observable and cannot silently qualify the test run.
        if run("docker", "ps", "--all", "--quiet", "--filter", "label=gh-eval-validation=" + prefix).stdout.strip():
            raise ValueError("test container cleanup incomplete")
        if run("docker", "images", "--quiet", "--filter", "label=gh-eval-validation=" + prefix).stdout.strip():
            raise ValueError("test image cleanup incomplete")


if __name__ == "__main__":
    validate()
