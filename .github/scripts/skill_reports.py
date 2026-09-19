#!/usr/bin/env python3
"""CI report checks and data-only benchmark-action handoff; no evaluation/scoring."""

import argparse
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import stat
import sys


POLICY = {
    "evaluator_revision": "ac0a04905100acdafc6c95829311a9739c340ff6",
    "harbor": "0.13.2",
    "docker_compose": "5.0.2",
    "codex": "0.155.1",
    "python": "3.13",
    "model": "gpt-5.6-sol",
    "provider": "openai",
    "environment": "docker",
    "grading": "default",
    "concurrency": 2,
    "standard_attempts": 1,
    "baseline": True,
    "stop_on_pass": False,
}
METRICS = {
    "Skill Lift": ("lift", "overall", "delta"),
    "Effectiveness": ("dimensions_with_skill", "effectiveness", "score"),
    "Correctness": ("dimensions_with_skill", "correctness", "score"),
    "Discoverability": ("dimensions_with_skill", "discoverability", "score"),
}
MODES = {"standard": POLICY["standard_attempts"], "confirmation": 3}
PATCH = ".github/patches/skillevaluator-v0.3.0-pin-codex.patch"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path, limit=8 * 1024 * 1024):
    require(path.is_file() and not path.is_symlink(), f"Missing or linked JSON report: {path.name}")
    require(path.stat().st_size <= limit, f"Oversized JSON report: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def summary(lines):
    text = "\n".join(lines) + "\n"
    print(text)
    if destination := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(destination, "a", encoding="utf-8") as stream:
            stream.write(text)


def outputs(**values):
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
        for key, value in values.items():
            require("\n" not in str(value) and "\r" not in str(value), "Unsafe job output")
            stream.write(f"{key}={value}\n")


def regular_tree(root, *, excluded_dirs=()):
    """Inspect every entry without following links or hiding traversal errors."""
    require(root.resolve() == root.absolute() and stat.S_ISDIR(root.lstat().st_mode),
            "Expected a real directory with no linked path components")
    pending = [root]
    files = []
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                if entry.name in excluded_dirs:
                    continue  # Never inspect or publish excluded runtime directories.
                mode = entry.stat(follow_symlinks=False).st_mode
                require(stat.S_ISDIR(mode) or stat.S_ISREG(mode),
                        f"Linked or special input: {Path(entry.path).relative_to(root)}")
                if stat.S_ISDIR(mode):
                    pending.append(Path(entry.path))
                else:
                    files.append(Path(entry.path))
    return files


def catalog_preflight(workspace):
    regular_tree(workspace / ".apm/skills")
    names = sorted(path.parent.name for path in (workspace / ".apm/skills").glob("*/SKILL.md"))
    require(bool(names), "No local skills found")
    for name in names:
        local_skill(workspace, name)
    return names


def local_skill(workspace, name, *, dataset=False):
    require(bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)) and len(name) <= 64,
            "skill must be a local skill name, not a path")
    path = workspace / ".apm/skills" / name
    require(path.exists(), "Selected local skill does not exist")
    regular_tree(path)
    require((path / "SKILL.md").is_file() and not (path / "SKILL.md").is_symlink(),
            "Selected local skill has no authored SKILL.md")
    if dataset:
        source = path / "evals/evals.json"
        require(source.is_file() and source.resolve() == source.absolute(),
                "Selected skill requires authored evals/evals.json")
    return path


def catalog_report(workspace, root):
    """Only ordinary, fully reported native findings may be advisory."""
    names = catalog_preflight(workspace)
    data = read_json(root / "reports/catalog-summary.json")
    entries = data["skills"]
    require(sorted(item["name"] for item in entries) == names, "Incomplete catalog report")
    require(type(data["total"]) is int and data["total"] == len(names), "Incorrect catalog cardinality")
    exit_code = int((root / "catalog.exit").read_text())
    errors = []
    lines = ["## Skill quality (findings are advisory)", "",
             "| Skill | Native status | Critical / High / Medium / Low | Strict eval contract |",
             "| --- | --- | --- | --- |"]
    if exit_code not in (0, 1):
        errors.append(f"Catalog exited with infrastructure status {exit_code}")
    for item in entries:
        name = item["name"]
        status = "invalid report"
        findings = "unknown"
        strict = "no dataset"
        try:
            require(type(item.get("passed")) is bool, "Missing native pass/fail status")
            require(item.get("reason", "") == ("" if item["passed"] else "validation failed"),
                    "Catalog recorded a configuration/runtime failure")
            filename = item["json_report"]
            require(bool(re.fullmatch(r"skillevaluator-output-[0-9]{14}\.json", filename)),
                    "Unexpected per-skill report filename")
            report = read_json(root / "reports" / name / filename)
            status = report["overall_status"]
            require(status in ("passed", "failed", "incomplete"), "Unknown native report status")
            require(type(report["overall_passed"]) is bool and report["overall_passed"] == item["passed"],
                    "Inconsistent catalog/per-skill result")
            require(report["skills"][0]["name"] == name and len(report["skills"]) == 1,
                    "Report skill identity mismatch")
            require(type(report["total_validators"]) is int
                    and report["total_validators"] == len(report["results"]) > 0, "Missing validator evidence")
            require(all(row.get("status") in ("passed", "failed", "incomplete", "skipped")
                        for row in report["results"]), "Unknown validator status")
            require(isinstance(report["incomplete_scans"], list), "Missing evidence status")
            require(all(isinstance(name, str) and name for name in report["incomplete_scans"]),
                    "Invalid incomplete scanner names")
            expected_status = "incomplete" if report["incomplete_scans"] else (
                "passed" if report["overall_passed"] else "failed")
            require(status == expected_status, "Inconsistent native status/pass/evidence")
            counts = [report["severity_counts"][severity] for severity in ("critical", "high", "medium", "low")]
            require(all(type(count) is int and count >= 0 for count in counts), "Invalid finding counts")
            findings = " / ".join(str(count) for count in counts)
            if report["incomplete_scans"]:
                status += " (" + ", ".join(report["incomplete_scans"]) + ")"
            for suffix in (".md", ".html"):
                sibling = root / "reports" / name / Path(filename).with_suffix(suffix)
                require(sibling.is_file() and not sibling.is_symlink() and sibling.stat().st_size > 0,
                        "Missing human-readable report")
        except (ValueError, KeyError, TypeError, IndexError, OSError) as error:
            errors.append(f"{name}: {error}")
        dataset = workspace / ".apm/skills" / name / "evals/evals.json"
        if dataset.exists() or dataset.is_symlink():
            strict = "failed"
            try:
                local_skill(workspace, name, dataset=True)
                require(int((root / "datasets" / f"{name}.exit").read_text()) == 0,
                        "Strict eval dataset validation failed")
                checks = read_json(root / "datasets" / f"{name}.json")
                require(isinstance(checks, list) and checks and all(row["status"] == "ok" for row in checks),
                        "Invalid strict-validation report")
                strict = "passed"
            except (ValueError, KeyError, TypeError, OSError) as error:
                errors.append(f"{name}: {error}")
        lines.append(f"| {name} | {html.escape(str(status))} | {findings} | {strict} |")
    require(type(data["failed"]) is int and data["failed"] == sum(not item["passed"] for item in entries),
            "Incorrect failure count")
    if (exit_code == 0) != (data["failed"] == 0):
        errors.append("Catalog exit status disagrees with its reports")
    lines += ["", "See the skill-quality artifact for full JSON, Markdown, HTML, and dataset reports."]
    if errors:
        lines += ["", "Infrastructure / contract failures:"] + [f"- {html.escape(error)}" for error in errors]
    summary(lines)
    require(not errors, "Skill evaluation infrastructure or dataset contract failed")


def metric_rows(agent):
    rows = []
    for name, path in METRICS.items():
        value = agent
        for field in path:
            value = value[field]
        require(type(value) in (int, float) and math.isfinite(value), f"Invalid {name} value")
        require((-1 if name == "Skill Lift" else 0) <= value <= 1, f"Out-of-range {name}")
        rows.append({"name": name, "unit": "score", "value": value})
    return rows


def usage_summary(run):
    """Display only native agent fields; no pricing or inferred token accounting."""
    fields = ("n_input_tokens", "n_cache_tokens", "n_output_tokens", "cost_usd")
    lines = ["", "### Native agent usage", "",
             "Reported subtotals only; cache tokens are included in input tokens. Missing values remain unknown.",
             "Cost may be estimated by Harbor and excludes usage not reported here, including judging/preflight.", "",
             "| Arm | Field | Reported subtotal | Trials reporting / recorded |", "| --- | --- | --- | --- |"]
    for arm in ("with-skill", "without-skill"):
        records = {}
        for path in sorted((run / "codex" / arm / "trials").glob("*/result.json")):
            try:
                require(path.resolve().is_relative_to(run), "Escaping trial report")
                data = read_json(path)
                identity = data["id"]
                require(isinstance(identity, str), "Missing trial identity")
                context = data.get("agent_result") or {}
                require(isinstance(context, dict), "Invalid optional agent usage")
                records[identity] = context
            except (ValueError, KeyError, TypeError, OSError):
                continue  # Optional usage never substitutes a zero for unknown data.
        for field in fields:
            values = [record[field] for record in records.values()
                      if type(record.get(field)) in (int, float)
                      and math.isfinite(record[field]) and record[field] >= 0]
            total = f"{sum(values):.6f}" if values and field == "cost_usd" else str(sum(values)) if values else "unknown"
            lines.append(f"| {arm} | {field} | {total} | {len(values)} / {len(records)} |")
    return lines


def validate_benchmark_versions(versions):
    require(versions["python"].startswith("3.13.") and versions["skillevaluator"] == "0.3.0"
            and versions["harbor"] == POLICY["harbor"]
            and versions.get("docker_compose") == POLICY["docker_compose"],
            "Installed evaluator/runtime version mismatch")


def benchmark_report(workspace, root, name, mode, destination):
    # These native APIs validate run identity/completeness; never imported by the publisher.
    from skillevaluator.evaluation import EvaluationService
    from skillevaluator.source_identity import evaluated_source_revision

    skill = local_skill(workspace, name, dataset=True)
    service = EvaluationService()
    run = service.discover_latest_results(skill, root / "results")
    require(run is not None and run.is_relative_to((root / "results").resolve()),
            "No complete external native result; inspect raw artifacts")
    result = read_json(run / "result.json")
    require(service.failure_reason(result) is None and result["report_status"] == "complete",
            "Incomplete or failed native benchmark")
    require((run / "report.html").is_file() and not (run / "report.html").is_symlink(),
            "Missing native HTML benchmark report")
    validate_benchmark_versions(read_json(root / "versions.json"))
    require(result["skill_name"] == name, "Result skill mismatch")
    config = result["run_config"]
    agent = result["agents"]["codex"]
    require(set(result["agents"]) == {"codex"} and agent["model"] == POLICY["model"], "Agent model mismatch")
    require(config["provider"] == {"name": "openai", "model": POLICY["model"]}, "Provider/model mismatch")
    require(config["judge"]["model"] == POLICY["model"] and config["judge"]["provider"] == "openai"
            and config["judge"]["override_applied"] is True, "Judge model mismatch")
    harbor = config["harbor"]
    require(harbor["environment"]["value"] == "docker" and harbor["n_attempts"] == MODES[mode]
            and harbor["n_concurrent"] == 2 and harbor["stop_on_pass"] is False, "Attempt/runtime policy mismatch")
    require(config["grading"]["mode"] == "default", "Grading policy mismatch")
    revision = os.environ["GITHUB_SHA"]
    require(evaluated_source_revision(config["evaluated_source"]) == revision, "Evaluated source mismatch")
    cases = result["dataset_summary"]["total_tasks"]
    require(type(cases) is int and cases > 0, "Missing dataset cardinality")
    for arm in ("with_skill", "without_skill"):
        condition = agent["conditions"][arm]
        require(condition["execution_status"] == "succeeded" and not condition["execution_errors"]
                and condition["scored_attempts"] == condition["expected_attempts"] == cases * MODES[mode],
                "Incomplete with-skill/baseline coverage")
    rows = metric_rows(agent)
    provenance = {
        "schema_version": 1, "skill": name, "mode": mode, "revision": revision,
        "policy": POLICY, "patch_sha256": hashlib.sha256((workspace / PATCH).read_bytes()).hexdigest(),
        "dataset_digest": result["dataset_digest"], "metrics": rows,
    }
    # Reuse the exact same allowlist contract on both sides of the artifact boundary.
    validate_metrics(provenance, workspace, name, revision, mode=mode)
    write_json(root / "provenance.json", provenance)
    lines = [f"## {name}: {mode} benchmark", "", f"{cases * MODES[mode] * 2} task trials; both arms complete.", "",
             "| Metric | Score |", "| --- | --- |"]
    lines += [f"| {row['name']} | {row['value']:.4f} |" for row in rows]
    lines += ["", f"Dataset: `{provenance['dataset_digest']}`", f"Source: `{revision}`",
              "", "Confirmation runs are diagnostic; only successful standard runs dispatched on main publish history."]
    lines += usage_summary(run)
    summary(lines)
    if mode == "standard":
        write_json(destination / "metrics.json", provenance)


def validate_metrics(data, workspace, name, revision, *, mode="standard"):
    require(set(data) == {"schema_version", "skill", "mode", "revision", "policy", "patch_sha256",
                          "dataset_digest", "metrics"}, "Unexpected history artifact fields")
    require(data["schema_version"] == 1 and data["skill"] == name and data["mode"] == mode,
            "History identity/mode mismatch")
    local_skill(workspace, name, dataset=True)
    require(bool(re.fullmatch(r"[0-9a-f]{40}", revision)) and data["revision"] == revision, "Revision mismatch")
    require(data["policy"] == POLICY, "Benchmark policy mismatch")
    require(data["patch_sha256"] == hashlib.sha256((workspace / PATCH).read_bytes()).hexdigest(), "Patch mismatch")
    require(bool(re.fullmatch(r"sha256:[0-9a-f]{64}", data["dataset_digest"])), "Invalid dataset digest")
    rows = data["metrics"]
    require(isinstance(rows, list) and len(rows) == len(METRICS), "Wrong metric count")
    for row, name in zip(rows, METRICS):
        require(set(row) == {"name", "unit", "value"} and row["name"] == name and row["unit"] == "score",
                "Unexpected metric fields")
        value = row["value"]
        require(type(value) in (int, float) and math.isfinite(value)
                and (-1 if name == "Skill Lift" else 0) <= value <= 1, "Invalid numeric metric")


def publish_metrics(workspace, root, name):
    require(os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
            and os.environ.get("GITHUB_REF") == "refs/heads/main"
            and os.environ.get("BENCHMARK_MODE") == "standard", "History requires a main standard dispatch")
    data = read_json(root / "metrics.json", limit=16384)
    validate_metrics(data, workspace, name, os.environ["GITHUB_SHA"])
    policy_id = hashlib.sha256(json.dumps([POLICY, data["patch_sha256"]], sort_keys=True).encode()).hexdigest()[:16]
    rows = [{**row, "extra": f"Dataset {data['dataset_digest']}; policy {policy_id}"} for row in data["metrics"]]
    write_json(root / "benchmark.json", rows)
    outputs(history_dir=f"benchmarks/{name}/{policy_id}")


def benchmark_artifacts(workspace, root, name, destination):
    """Stage only native report contracts, using upstream credential redaction."""
    from skillevaluator.utils.redaction import redact_sensitive_data, redact_sensitive_text

    local_skill(workspace, name, dataset=True)
    root = root.absolute()
    destination = destination.absolute()
    for path in (root, destination):
        require(path.resolve() == path and not path.is_relative_to(workspace),
                "Benchmark artifacts must use real paths outside the checkout")
    require(not destination.is_relative_to(root) and not root.is_relative_to(destination),
            "Artifact staging must be separate from raw results")
    files = regular_tree(root, excluded_dirs={"_harbor-jobs", "_harbor-tasks"})
    metadata = {"versions.json", "dataset-validation.json", "provenance.json",
                "docker-version.json", "docker-images.jsonl"}
    # Reviewed v0.3.0 report/collector contract, restricted to this workflow's Codex agent.
    root_reports = {"result.json", "run_config.json", "dataset_snapshot.json", "report.html",
                    "attempt_policy.json", "comparison.json"}
    agent_reports = {"lift.json", "custom_lift.json", "pass_at_k_lift.json",
                     "security_attribution.json", "findings.json"}
    trial_reports = {"result.json", "config.json", "exception.txt", "trial.log", "trajectory.json",
                     "codex.txt", "reward.json", "failure.json", "artifact_manifest.json"}

    def allowed(relative):
        parts = relative.parts
        if any(part.startswith(".") for part in parts):
            return False
        if len(parts) == 1:
            return parts[0] in metadata
        if len(parts) == 2 and parts[0] == "dependencies":
            return parts[1] in {"evaluator.json", "semgrep.json", "skillspector.json"}
        if len(parts) < 4 or parts[:2] != ("results", name):
            return False
        # Native external layout: results/<skill>/<run>/codex/<arm>/trials/<trial>/...
        tail = parts[3:]
        if len(tail) == 1:
            return tail[0] in root_reports
        if tail[0] != "codex":
            return False
        if len(tail) == 2:
            return tail[1] in agent_reports
        if tail[1] not in {"with-skill", "without-skill"}:
            return False
        return (len(tail) == 3 and tail[2] == "summary.json") or (
            len(tail) == 5 and tail[2] == "trials" and tail[4] in trial_reports)

    destination.mkdir(parents=True, exist_ok=False)
    copied = 0
    for source in sorted(files):
        relative = source.relative_to(root)
        if not allowed(relative):
            continue
        # Recheck the final input immediately before reading; raw results stay untouched.
        require(not source.is_symlink() and source.resolve() == source, "Linked publication input")
        if source.suffix == ".json":
            value = redact_sensitive_data(read_json(source, limit=64 * 1024 * 1024))
            write_json(destination / relative, value)
        else:
            text = redact_sensitive_text(source.read_text(encoding="utf-8"))
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        copied += 1
    require(copied > 0, "No publishable benchmark reports")
    summary([f"Staged {copied} allowlisted files with upstream redaction; raw runtime directories are excluded."])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("preflight")
    select = commands.add_parser("select")
    select.add_argument("skill")
    select.add_argument("mode", choices=MODES)
    catalog = commands.add_parser("catalog")
    catalog.add_argument("root", type=Path)
    benchmark = commands.add_parser("benchmark")
    benchmark.add_argument("root", type=Path)
    benchmark.add_argument("skill")
    benchmark.add_argument("mode", choices=MODES)
    benchmark.add_argument("destination", type=Path)
    publish = commands.add_parser("publish")
    publish.add_argument("root", type=Path)
    publish.add_argument("skill")
    artifacts = commands.add_parser("artifacts")
    artifacts.add_argument("root", type=Path)
    artifacts.add_argument("skill")
    artifacts.add_argument("destination", type=Path)
    args = parser.parse_args()
    workspace = Path(os.environ["GITHUB_WORKSPACE"]).resolve()
    if args.command == "preflight":
        catalog_preflight(workspace)
    elif args.command == "select":
        local_skill(workspace, args.skill, dataset=True)
        outputs(skill=args.skill, attempts=MODES[args.mode])
    elif args.command == "catalog":
        catalog_report(workspace, args.root)
    elif args.command == "benchmark":
        benchmark_report(workspace, args.root, args.skill, args.mode, args.destination)
    elif args.command == "artifacts":
        benchmark_artifacts(workspace, args.root, args.skill, args.destination)
    else:
        publish_metrics(workspace, args.root, args.skill)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, IndexError, OSError) as error:
        summary(["## Skill evaluation infrastructure failure", "", html.escape(str(error))])
        sys.exit(1)
