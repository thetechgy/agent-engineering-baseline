#!/usr/bin/env python3
"""Credential-free checks of the staged native Docker CLI/broker/verifier boundary."""

import json
from pathlib import Path
import shlex
import signal
import subprocess
import tempfile
import uuid

import gh_evaluations as gh
from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks


SELECTED = ("gh-001", "gh-007", "gh-010")


def run(*argv, check=True):
    return subprocess.run(argv, check=check, capture_output=True, text=True, timeout=600)


def validate():
    if run("docker", "compose", "version", "--short").stdout.strip() != "5.0.2":
        raise ValueError("Docker Compose 5.0.2 required")
    prefix = "gh-eval-validation-" + uuid.uuid4().hex[:12]
    resources = []
    # Make interruption follow the same exact-resource cleanup path as test failures.
    def interrupted(signum, frame):
        raise KeyboardInterrupt

    old = {s: signal.signal(s, interrupted) for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        with tempfile.TemporaryDirectory(prefix=prefix) as temporary:
            root = Path(temporary)
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
                    if not with_skill and task.name != "gh-001":
                        continue
                    name = f"{prefix}-{tested}"
                    resources.append(name)
                    run("docker", "build", "--label", "gh-eval-validation=" + prefix,
                        "--tag", name, str(task / "environment"))
                    run("docker", "run", "--detach", "--name", name, "--network", "none",
                        "--label", "gh-eval-validation=" + prefix, name, "sleep", "600")
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
                    for command in entries[task.name]["contract"]["good_commands"]:
                        result = observed(shlex.join(["gh", *command]))
                        if result.returncode:
                            raise ValueError("known-good CLI call failed")
                        if task.name == "gh-007" and command[:2] == ["api", "repos/fixture-org/widget/issues"]:
                            if json.loads(result.stdout) != list(range(1, 32)):
                                raise ValueError("incomplete or PR-mixed issue collection")
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
                    tested += 1
            print(json.dumps({"evidence": "credential-free native Docker boundary", "containers_passed": tested,
                "model_trials": 0, "network": "none"}))
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
