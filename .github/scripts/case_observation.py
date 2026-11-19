"""Manual human-reviewed observation of one repository case on the protected Codex runner."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shlex

import evaluation_campaign_core as core
from evaluation_runtime import ROOT
from evaluation_tasks import Task
import skill_evidence as evidence
import skill_reports as reports

SCENARIOS = ("no-change", "active-configuration", "collection-interrupted")
ANSWER = ("Socket access grants the authority of the Podman service user. Traefik can use "
          "file-based discovery. Do you accept granting socket access?")
CONFIG = """services:
  traefik:
    image: traefik
    command: [--providers.docker=true]
    volumes:
      - /run/user/1000/podman/podman.sock:/var/run/docker.sock:ro
"""


def selected(skill, case):
    for identifier in (skill, case):
        core.require(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", identifier), "Invalid repository identifier")
    source = reports.benchmark_skill(ROOT, skill)
    entries = reports.read_json(source / "evals/evals.json")["evals"]
    matches = [entry for entry in entries if str(entry["id"]) == case]
    core.require(len(matches) == 1, "Unknown or ambiguous case in selected skill")
    return source, matches[0]


class CaseObservation(Task):
    diagnostic_observation = True
    output = "unused-observation-submission"
    retained_members = ()

    def __init__(self, definition, member):
        skill, case = os.environ.get("OBSERVATION_SKILL", ""), os.environ.get("OBSERVATION_CASE", "")
        self.source, self.entry = selected(skill, case)
        self.selector = {"OBSERVATION_SKILL": skill, "OBSERVATION_CASE": case}
        super().__init__({**definition, "skill": skill, "source_case": case,
                          "source": str((ROOT / ".agents/skills" / skill).relative_to(ROOT))}, member)

    def cases(self, mode):
        return {self.definition["source_case"]: None}

    def schedule(self):
        return [{"position": 1, "case": self.definition["source_case"], "trial": 1, "variant": "current"}]

    def fixture_control(self, fixture, row):
        core.require(fixture in SCENARIOS, "Unknown workspace fixture")
        return fixture

    def payload(self, control):
        return ANSWER.encode()

    def probe_commands(self, control, payload, present):
        skill = self.definition["skill"]
        argv = "python3 /opt/pilot/codex_pilot_probe.py --observation " + shlex.quote(skill)
        # Always exercise the real CLI tool and its delayed network-policy check.
        command = argv + " && cat /home/agent/.agents/skills/" + skill + "/SKILL.md >/dev/null"
        if control == "active-configuration":
            command += " && printf %s " + shlex.quote(base64.b64encode(CONFIG.encode()).decode()) + " | base64 -d > /workspace/traefik.yaml"
        return [command]

    def stage(self, root, deployed, mode, runtime):
        from codex_pilot_descriptors import retain_descriptors
        import evaluation_codex as codex
        from gh_evaluations import APT_SOURCES
        from harbor.models.task.task import Task as NativeTask
        from skillevaluator.tier3.harbor.adapter import (
            _entry_file_refs, _resolve_entry_file_ref, generate_harbor_tasks, private_evaluator_skill_snapshot,
        )
        skill, case = self.definition["skill"], self.definition["source_case"]
        # BYOT overlays own their task-specific initializer. Never silently convert
        # them into a generated task and lose their broker, inputs or tools.
        core.require(self.source == ROOT / ".apm/skills" / skill and not (self.source / "evals/harbor").exists(),
                     "Native overlay requires its registered task environment")
        with private_evaluator_skill_snapshot(self.source, task_source="evals_json") as snapshot:
            dataset = snapshot / "evals/evals.json"
            value = reports.read_json(dataset)
            core.require([e for e in value["evals"] if str(e["id"]) == case] == [self.entry],
                         "Selected case changed during preparation")
            reports.write_json(dataset, {**value, "evals": [self.entry]})
            paths = generate_harbor_tasks(deployed, root / "generated", with_skill=True,
                        evaluator_skill_path=snapshot, base_image=reports.GH_TASK_BUILD["base_image"],
                        agent_workdir="/workspace", task_resources={"cpus": runtime["cpus"], "memory_mb": runtime["memory_mb"]})
        core.require(len(paths) == 1 and paths[0].name == case, "Selected native population changed")
        native = paths[0]
        core.require((native / "instruction.md").read_bytes() == (self.entry["prompt"] + "\n").encode(),
                     "Selected prompt changed")
        projected = native / "environment/skills" / skill
        core.require(codex.manifest(projected) == codex.manifest(deployed), "Staged skill differs from APM")
        dockerfile = native / "environment/Dockerfile"
        sources = " ".join(shlex.quote(s) for s in APT_SOURCES)
        with dockerfile.open("a") as stream:
            stream.write("RUN rm -f /etc/apt/sources.list.d/* && printf '%s\\n' " + sources +
                         " > /etc/apt/sources.list\nRUN useradd --create-home --uid 1000 agent && "
                         "mkdir -p /workspace/input /workspace/output && chmod -R a+rX /workspace/skills /workspace/input && chmod 1777 /workspace /workspace/output\n"
                         "WORKDIR /workspace\n")
        codex.prepare_task(native, mode, runtime)
        members = {p.relative_to(native).as_posix(): evidence.digest_bytes(evidence.read_bytes(p))
                   for p in reports.regular_tree(native)}
        prefix = "environment/input/"
        actual_inputs = {path.removeprefix(prefix): digest for path, digest in members.items() if path.startswith(prefix)}
        expected_inputs = {}
        for ref in _entry_file_refs(self.entry):
            source, relative = _resolve_entry_file_ref(ref, skill_path=self.source, evals_dir=self.source / "evals",
                                                       input_files_dir=self.source / "evals/files")
            for path in (reports.regular_tree(source) if source.is_dir() else [source]):
                target = (relative / path.relative_to(source)).as_posix()
                digest = evidence.digest_bytes(evidence.read_bytes(path))
                core.require(expected_inputs.setdefault(target, digest) == digest, "Conflicting declared case files")
        core.require("environment/input" not in members and actual_inputs == expected_inputs,
                     "Staged inputs differ from declared case files")
        captured = [{"case_id": case, "arm": "with_skill", "members": members, "task_checksum": NativeTask(native).checksum}]
        reports.write_json(root / "evidence/staging.json", captured)
        retain_descriptors(root / "evidence", {"with_skill": [native]}, captured)
        reports.write_json(root / "evidence/selected-case.json", {"skill": skill, "case": case,
            "prompt_sha256": hashlib.sha256((native / "instruction.md").read_bytes()).hexdigest(),
            "declared_files": self.entry.get("files", []), "staged_inputs": sorted(actual_inputs), "arm": "current",
            "trials": 1, "verifier_enabled": False})
        return self.source, {"current": {case: native}}, captured, {}


def observation(trial, row, task, artifact, mode, secret):
    """Retain fixed native members only. Every missing member remains visible."""
    from skillevaluator.utils.redaction import redact_printable_text
    record = {"kind": "diagnostic observation", "execution": "failed", "quality": "ungraded",
              "evidence": "incomplete", "review": "incomplete", "missing": [],
              "skill": task.definition["skill"], "case": row["case"], "arm": "current"}
    report = artifact / "observation.json"
    reports.write_json(report, record)
    def capture(member, limit, *, structured=False, retain=True):
        try:
            raw = evidence.read_bytes(trial / member, limit=limit).decode()
            value = json.loads(raw) if structured else raw
            from skillevaluator.tier3.harbor.secure_docker_environment import _redact
            cleaned = _redact(redact_printable_text(raw), {secret} if secret else set(), include_short=True)
            if retain:
                target = artifact / "retained" / member
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(cleaned)
            return value
        except (OSError, ValueError, TypeError):
            record["missing"].append(member)
    audit = capture("operator/pilot-runtime.json", 65536, structured=True) or {}
    final = capture("operator/pilot-final-policy.json", 65536, structured=True) or {}
    life = capture("operator/pilot-lifecycle.json", 65536, structured=True) or {}
    workspace = capture("operator/workspace-observation.json", 512*1024, structured=True) or {}
    answer = capture("agent/last-message.txt", 64*1024)
    trace = capture("agent/codex.txt", 1024*1024)
    events = []
    try:
        events = [json.loads(line) for line in (trace or "").splitlines()
                  if line != "Reading additional input from stdin..."]
        terminal = [e for e in events if e["type"] == "turn.completed"]
        messages = [e["item"]["text"] for e in events if e["type"] == "item.completed" and e["item"]["type"] == "agent_message"]
        exact_answer = bool(answer and messages and messages[-1].strip() == answer.strip())
        trace_complete = bool(len(terminal) == 1 and terminal[0] == events[-1])
    except (ValueError, KeyError, TypeError):
        exact_answer = trace_complete = False
    native_result = capture("result.json", 1024*1024, structured=True, retain=False) or {}
    no_verification = (native_result.get("verifier") is None and native_result.get("verifier_result") is None)
    execution = (native_result.get("agent_execution") or {}).get("finished_at")
    if execution and audit.get("returncode") == 0:
        record["execution"] = "completed"
    elif audit.get("returncode") is None and not row.get("native_exception"):
        record["execution"] = "unconfirmed"
    disposed = (row.get("cleanup") and audit.get("cleanup") == "complete" and
                any(s.get("stage") == "disposal_complete" for s in life.get("stages", [])))
    verified = (record["execution"] == "completed" and row.get("returncode") == 0 and
                not row.get("native_exception") and disposed and no_verification and
                not record["missing"] and exact_answer and trace_complete and
                audit.get("skill_deployed") is True and final.get("mounts") == [] and
                audit.get("boundary_before", {}).get("agent_id") == final.get("agent_id") and
                audit.get("prompt_sha256") == hashlib.sha256((task.entry["prompt"]+"\n").encode()).hexdigest() and
                workspace.get("status") == "complete" and isinstance(workspace.get("changes"), list))
    if verified:
        record.update(evidence="complete", review="ready for human review", changed_paths=len(workspace["changes"]))
    config = capture("config.json", 65536, structured=True, retain=False) or {}
    if native_result and no_verification and config.get("verifier", {}).get("disable") is True:
        record["model_judge_calls"] = 0
    if mode == "experiment-probe":
        probe = capture("agent/probe.json", 1024*1024, structured=True, retain=False) or {}
        record["responder_requests"] = probe.get("requests")
        record["responder_path"] = probe.get("path") if probe.get("path") == "/v1/responses" else None
        tools = [e.get("item", {}) for e in events if e.get("type") == "item.completed"
                 and e.get("item", {}).get("type") == "command_execution"]
        record["probe_tool_completed"] = any(t.get("exit_code") == 0 and
            "PILOT_BOUNDARY " in t.get("aggregated_output", "") for t in tools)
        record["socket_mounts_absent"] = (final.get("mounts") == [] and
                                          audit.get("boundary_before", {}).get("mounts") == [])
    if record["missing"] or record.get("model_judge_calls") != 0:
        record.update(evidence="incomplete", review="incomplete")
        record.pop("changed_paths", None)
    record.update(usage=row.get("usage"), cleanup=row.get("cleanup"))
    reports.write_json(report, record)
    return record


def verify_qualification(root, task):
    answers = set()
    receipts = {}
    for name in SCENARIOS:
        artifact = root / "scenarios" / name / "evidence"
        record = reports.read_json(artifact / "observation.json")
        native = artifact / "retained"
        answer = evidence.read_bytes(native / "agent/last-message.txt", limit=65536).decode().strip()
        workspace = reports.read_json(native / "operator/workspace-observation.json")
        ledger = reports.read_json(artifact / "attempt-ledger.json")
        core.require(len(ledger["entries"]) == 1 and ledger["entries"][0]["variant"] == "current" and
                     ledger["entries"][0]["case"] == task.definition["source_case"] and
                     record["execution"] == "completed" and record["quality"] == "ungraded" and
                     ledger["cleanup_complete"] and record["cleanup"] and record["responder_requests"] == 2 and
                     record["model_judge_calls"] == 0 and record["probe_tool_completed"] and record["socket_mounts_absent"] and
                     record["responder_path"] == "/v1/responses" and
                     ledger["entries"][0]["usage"]["estimated_usd"] is not None and
                     ledger["state"] == ("stopped" if name == "collection-interrupted" else "completed"),
                     "Incomplete single-case credential-free qualification: " + name)
        core.require(record["evidence"] == ("incomplete" if name == "collection-interrupted" else "complete")
                     and not record["missing"] and answer == ANSWER, "Unexpected observation state: " + name)
        answers.add(answer)
        if name == "collection-interrupted":
            core.require(workspace == {"status": "incomplete", "reason": "operator_command_failed",
                                       "operation": "exec", "returncode": os.EX_DATAERR} and
                         ledger.get("stop_reason") == "missing_usable_evidence", "Missing comparison appeared complete")
        elif name == "no-change":
            core.require(workspace["status"] == "complete" and workspace["changes"] == [], "Unobserved empty workspace")
        else:
            changes = workspace["changes"]
            core.require(workspace["status"] == "complete" and len(changes) == 1 and
                         changes[0]["path"] == "traefik.yaml" and changes[0]["change"] == "added" and
                         changes[0]["text"] == CONFIG, "Active mount not retained")
        selected_case = reports.read_json(artifact / "selected-case.json")
        receipts[name] = {"execution": record["execution"], "evidence": record["evidence"],
                          "staged_inputs": selected_case["staged_inputs"], "socket_mounts_absent": True,
                          "attempts": len(ledger["entries"]), "arm": "current", "model_judge_calls": record["model_judge_calls"],
                          "quality": record["quality"], "cleanup": True,
                          "answer_sha256": hashlib.sha256(answer.encode()).hexdigest(),
                          "changes": [c["path"] for c in workspace["changes"]] if "changes" in workspace else None,
                          **({"scanner_exit": workspace["returncode"]} if name == "collection-interrupted" else {})}
    core.require(len(answers) == 1, "Fixture answers differ")
    proof = root / "evidence/scheduler-qualification.json"
    if proof.exists():
        core.require(reports.read_json(proof)["scenarios"] == receipts, "Retained observation summary changed")
    return receipts


def qualify_observation(root, retained, task):
    from evaluation_campaign import run
    from evaluation_campaign_protocol import revision, digest
    for name in SCENARIOS:
        ledger = run(root / "scenarios" / name, task, "experiment-probe", reference=retained, fixture=name)
        core.require(ledger["cleanup_complete"] and "report_failure" not in ledger, "Stop after incomplete cleanup or reporting")
    observed = verify_qualification(root, task)
    receipt = {"complete": True, "inference": False, "revision": revision(),
               "protocol_digest": digest(ROOT / task.definition["protocol"])}
    reports.write_json(retained / "scheduler-qualification.json", {**receipt, "scenarios": observed})
    reports.write_json(retained / "preparation.json", {**receipt, "authorized_live_attempts": 0})
