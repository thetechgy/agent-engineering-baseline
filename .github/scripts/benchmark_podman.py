"""Stage Podman benchmark cases through the released evaluator projector."""

from pathlib import Path
import re
import shutil
import subprocess
import tomllib

from skill_reports import POLICY, benchmark_options, read_json, require

CODEX_ROOT = "/opt/reviewed/codex"
CODEX_PROFILE = Path(__file__).resolve().parents[1] / "evals/codex-execution-1720.json"
RETAINED_CODEX_PROFILE = CODEX_PROFILE.with_name("codex-execution-1710.json")
SMOKE_CASE = "1"


def stage_tasks(skill: Path, work: Path, *, cases: tuple[str, ...], with_skill: bool) -> tuple[Path, ...]:
    from skillevaluator.tier3.harbor.adapter import generate_harbor_tasks

    options = benchmark_options("podman")
    require((options["workspace_mode"], options["grading_mode"]) == ("isolated", "default"),
            "Unexpected Podman benchmark policy")
    generated = generate_harbor_tasks(skill, work / "generated", with_skill=with_skill,
                                      workspace_mode=options["workspace_mode"], grading_mode=options["grading_mode"],
                                      custom_dockerfile_mode="disabled")
    by_case = {str(read_json(task / "tests/entry.json")["id"]): task for task in generated}
    require(len(by_case) == len(generated) and cases and len(set(cases)) == len(cases)
            and set(cases) <= by_case.keys(), "Unexpected staged Podman case population")
    staged = work / "tasks"
    staged.mkdir()
    tasks = []
    for case in cases:
        selected = by_case[case]
        task = selected.rename(staged / selected.name)
        configure_agent(task, case=case, with_skill=with_skill)
        tasks.append(task)
    return tuple(tasks)


def configure_agent(task: Path, *, case: str, with_skill: bool):
    descriptor = task / "task.toml"
    source = descriptor.read_text()
    config = tomllib.loads(source)
    require(config["metadata"]["entry_id"] == case and config["metadata"]["has_skill"] is with_skill,
            "Staged Podman task does not match the requested arm")
    require(config["environment"]["network_mode"] == "public" and "user" not in config["agent"]
            and source.count("[agent]") == 1, "Unexpected released Podman task descriptor")
    descriptor.write_text(source.replace("[agent]", '[agent]\nuser = "agent"'))
    with (task / "environment/Dockerfile").open("a") as build:
        build.write("\nRUN useradd --create-home --uid 1000 agent "
                    "&& chown agent:agent /workspace/output "
                    "&& chgrp -R agent /workspace/skills && chmod -R g+rX,go-w /workspace/skills\n")


def stage_task(skill: Path, work: Path, *, case: str, with_skill: bool) -> Path:
    task, = stage_tasks(skill, work, cases=(case,), with_skill=with_skill)
    return task

def codex_members(profile):
    require(profile["cli"] in (POLICY["codex"], "0.172.0"), "Unexpected benchmark Codex pin")
    return {"bin/codex": profile["cli_executable_sha256"], **profile["helper_sha256"]}


def stage_codex(image: Path, source: Path, profile: dict):
    """Install the reviewed native release before opening runtime networking."""
    from qualify_codex_1691 import check_digest

    members = codex_members(profile)
    for name, expected in members.items():
        binary = source / name
        check_digest(binary, expected)
        destination = image / "reviewed/codex" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(binary, destination)
    (image / "reviewed/codex/SHA256SUMS").write_text(
        "".join(f"{expected}  {name}\n" for name, expected in sorted(members.items())))
    with (image / "Dockerfile").open("a") as build:
        build.write(f"\nCOPY --chown=0:0 reviewed/codex {CODEX_ROOT}\n"
                    f"RUN cd {CODEX_ROOT} && sha256sum --check --strict SHA256SUMS "
                    f"&& chmod -R a+rX,go-w {CODEX_ROOT} "
                    f"&& ln -s {CODEX_ROOT}/bin/codex /usr/local/bin/codex\n"
                    f"ENV PATH={CODEX_ROOT}/codex-path:$PATH\n")


def configure_openai_task(task: Path, assets: Path, profile: dict):
    """Bind the published API endpoint and the verified, preinstalled CLI."""
    from harbor.models.task.task import Task

    descriptor = task / "task.toml"
    source = descriptor.read_text()
    marker = 'network_mode = "public"'
    require(source.count(marker) == 1, "Unexpected staged network policy")
    descriptor.write_text(source.replace(marker, 'network_mode = "allowlist"\nallowed_hosts = ["api.openai.com"]'))
    stage_codex(task / "environment", assets, profile)
    native = Task(task)
    network = native.config.environment.resolve_baseline()
    require(network.network_mode.value == "allowlist" and network.allowed_hosts == ["api.openai.com"]
            and native.config.agent.user == "agent", "Unexpected released Podman network or agent policy")
    return native


def compose_teardown_complete(project: str) -> bool:
    require(re.fullmatch(r'[a-z0-9][a-z0-9_-]+', project), 'Invalid native Compose project identity')
    selector = 'label=com.docker.compose.project=' + project
    return all(not subprocess.check_output(
        ['docker', member, 'ls', '--quiet', *extra, '--filter', selector], text=True, timeout=10).strip()
        for member, extra in (('container', ['--all']), ('network', [])))



def scope(workspace: Path, revision: str, *, released=False):
    from evaluator_profiles import CURRENT_RELEASE
    from skill_orchestration import candidate_podman_fingerprint

    profile = CODEX_PROFILE if released else RETAINED_CODEX_PROFILE
    return {
        "revision": revision,
        "fingerprint": candidate_podman_fingerprint(workspace, revision, released=released),
        "skill": "podman",
        "case": SMOKE_CASE,
        "arms": ["with_skill", "without_skill"],
        "planned_trials": 2,
        "attempts_per_arm": 1,
        "agent": {"cli": read_json(profile)["cli"], "model": POLICY["model"], "reasoning_effort": "high",
                  "tool_surface": CURRENT_RELEASE["codex_tool_surface"]},
        "verifier": {"model": POLICY["model"], "reasoning_effort": None},
        "history_eligible": False,
    }
