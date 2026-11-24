"""Task-owned staging for the case 2 PostgreSQL mount qualification."""

import json
from pathlib import Path
import shlex
import shutil
import subprocess

from evaluation_campaign_core import require
from evaluation_tasks import ROOT, Task
import skill_reports as reports

HOME = Path(__file__).resolve().parent
SOURCE = ROOT / ".apm/skills/podman/evals"
METRIC = "podman_postgres_storage"


class PodmanStorage(Task):
    family = "podman-storage-v1"
    output = "postgres.container"
    environment = "codex_pilot_environment:PilotEnvironment"
    source_directories = (HOME.relative_to(ROOT).as_posix(),)
    source_files = tuple(f".apm/skills/podman/evals/{member}" for member in (
        "evals.json", "files/vendor-compose.yaml", "files/vendor-web/Containerfile",
    ))
    probe_controls = ("covered", "vendor-mount")

    def controls(self):
        return {
            "covered": ("passed", "persistent_mount_covers_data_directory"),
            "vendor-mount": ("failed", "data_directory_outside_persistent_mount"),
        }

    def entry(self):
        definition = reports.read_json(HOME / "eval.json")
        source = next(row for row in reports.read_json(SOURCE / "evals.json")["evals"]
                      if row["id"] == definition["source_case"])
        # The fixture is staged at the original relative path under input.
        return {"id": definition["id"], "expected_skill": "podman",
                "prompt": source["prompt"] + "\n\n"
                + "The supplied paths are under input/. " + definition["deliverable"]}

    def payload(self, control):
        require(control in self.controls(), "Unknown Podman control")
        return (HOME / "controls" / (control + ".container")).read_bytes()

    def base_bundle(self, root):
        bundle = root / "bundle/podman"
        shutil.copytree(ROOT / self.definition["source"], bundle, ignore=shutil.ignore_patterns("evals"))
        subprocess.run(["git", "init", "--quiet", "--template=", str(bundle)], check=True)
        native = bundle / "evals/harbor" / self.definition["source_case"]
        for member, raw in self.expected_members(native.name, "with_skill").items():
            target = native / member
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        for member, template in (("environment/Dockerfile", "Dockerfile"),
                                 ("tests/Dockerfile", "Verifier.Dockerfile"),
                                 ("task.toml", "task.toml")):
            shutil.copyfile(HOME / template, native / member)
        (native / "tests/docker-compose.yaml").write_text("services:\n  main:\n    network_mode: none\n")
        return bundle

    def expected_members(self, case, arm):
        entry = {"id": case, "grading_mode": "custom_only", "has_skill": arm == "with_skill"}
        members = {
            "instruction.md": (self.entry()["prompt"] + "\n").encode(),
            "tests/test.sh": (HOME / "test.sh").read_bytes(),
            "tests/verifier/grader.py": (HOME / "grade.py").read_bytes(),
            "tests/entry.json": (json.dumps(entry, indent=2) + "\n").encode(),
        }
        for relative in self.source_files[1:]:
            path = ROOT / relative
            members["environment/input/evals/" + path.relative_to(SOURCE).as_posix()] = path.read_bytes()
        return members

    def configure(self, task, control, mode, present):
        arm = "with_skill" if present else "without_skill"
        (task / "tests/entry.json").write_bytes(self.expected_members(task.name, arm)["tests/entry.json"])
        with (task / "environment/Dockerfile").open("a") as dockerfile:
            dockerfile.write("RUN chmod -R a+rX /workspace/input\n")
        if mode == "oracle":
            descriptor = task / "task.toml"
            descriptor.write_text(descriptor.read_text().replace('network_mode = "public"', 'network_mode = "no-network"'))
            solution = task / "solution"
            solution.mkdir(mode=0o755)
            solution.chmod(0o755)
            candidate = solution / "candidate"
            candidate.write_bytes(self.payload(control))
            candidate.chmod(0o644)
            (solution / "solve.sh").write_text(
                "#!/bin/sh\nset -eu\n"
                "test ! -e /tests || { echo 'Verifier files visible to oracle'; exit 1; }\n"
                "test -r /workspace/input/evals/files/vendor-compose.yaml || { echo 'Public fixture unreadable'; exit 1; }\n"
                "cp /solution/candidate /workspace/output/postgres.container\n")
        else:
            require(not (task / "solution").exists(), "Unexpected Podman solution outside oracle")

    def probe_commands(self, control, payload, present=True):
        return ["test -r /workspace/input/evals/files/vendor-compose.yaml && "
                "printf %s " + shlex.quote(payload) + " | base64 -d > /workspace/output/" + self.output]

    def check(self, control, present, outcome, metrics):
        expected, reason = self.controls()[control]
        require(outcome == {"classification": expected, "code": "evaluated", "reason": reason}
                and metrics == {METRIC: float(expected == "passed")},
                "Unexpected Podman control verdict: " + control)
