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
import shutil
import stat
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))


POLICY = {
    "evaluator_revision": "ac0a04905100acdafc6c95829311a9739c340ff6",
    "harbor": "0.13.2",
    "docker_compose": "5.6.1",
    "codex": "0.155.1",
    "python": "3.13",
    "model": "gpt-5.6-sol",
    "provider": "openai",
    "environment": "docker",
    "grading": "default",
    "concurrency": 2,
    "timeout_multiplier": 2.0,
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
GH_TASK_BUILD = {
    "base_image": "python:3.12-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1",
    "apt_snapshot": "20261010T000000Z",
    "apt_packages": {
        "git": "1:2.47.3-0+deb13u1",
        "jq": "1.7.1-6+deb13u4",
        "nodejs": "20.19.2+dfsg-1+deb13u3",
        "npm": "9.2.0~ds1-3",
        "ca-certificates": "20250419",
    },
}


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


def regular_tree(root, *, excluded_dirs=(), excluded_links=()):
    """Inspect every entry without following links or hiding traversal errors."""
    require(root.resolve() == root.absolute() and stat.S_ISDIR(root.lstat().st_mode),
            "Expected a real directory with no linked path components")
    pending = [root]
    files = []
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                relative = Path(entry.path).relative_to(root)
                metadata = entry.stat(follow_symlinks=False)
                mode = metadata.st_mode
                link_or_reparse = stat.S_ISLNK(mode) or bool(
                    getattr(metadata, "st_file_attributes", 0)
                    & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
                )
                if entry.name in excluded_dirs:
                    require(stat.S_ISDIR(mode) and not link_or_reparse,
                            f"Linked or invalid excluded runtime directory: {relative}")
                    continue  # Never inspect or publish excluded runtime directories.
                if relative in excluded_links:
                    require(link_or_reparse, f"Expected linked input: {relative}")
                    continue  # Recognized generated link; never inspect its target.
                require(not link_or_reparse and (stat.S_ISDIR(mode) or stat.S_ISREG(mode)),
                        f"Linked or special input: {relative}")
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


def benchmark_skill(workspace, name, root=None):
    """Resolve the existing upstream overlay and the bounded local pilot overlay."""
    if name == 'powershell-pester-6':
        import pester_evaluations as pester
        local_skill(workspace, name)
        pester.dataset(workspace)
        if root is not None and (root / 'bundle' / name).exists():
            staged = root / 'bundle' / name
            regular_tree(staged)
            for relative, digest in pester.manifest(workspace / '.apm/skills' / name).items():
                require(hashlib.sha256((staged / relative).read_bytes()).hexdigest() == digest,
                        'Staged local skill drift')
            return staged
        return workspace / pester.OVERLAY
    if name != "gh":
        return local_skill(workspace, name, dataset=True)
    import gh_evaluations as gh
    gh.dataset(workspace)
    regular_tree(workspace / gh.DEPLOYED)
    if root is not None:
        gh.verify_skill(workspace)
        gh.verify_competing(workspace)
    if root is not None and (root / "bundle/gh").exists():
        staged = root / "bundle/gh"
        regular_tree(staged)
        require((staged / "SKILL.md").read_bytes() == (workspace / gh.DEPLOYED / "SKILL.md").read_bytes(),
                "Staged upstream skill drift")
        return staged
    return workspace / gh.OVERLAY


def benchmark_options(name):
    """Execution routing only; this does not define scores or publication schemas."""
    return {
        'gh': {'grading_mode': 'default_plus_custom', 'workspace_mode': 'group', 'diagnostic_only': False},
        'powershell-pester-6': {'grading_mode': 'custom_only', 'workspace_mode': 'isolated', 'diagnostic_only': True},
    }.get(name, {'grading_mode': 'default', 'workspace_mode': 'isolated', 'diagnostic_only': False})


def prepare_benchmark(workspace, root, name):
    source = benchmark_skill(workspace, name)
    root = root.absolute()
    require(root.resolve() == root and not root.is_relative_to(workspace), 'Unsafe preparation root')
    if name == 'gh':
        import gh_evaluations as gh
        source = gh.stage(workspace, root / 'bundle' / name)
    elif name == 'powershell-pester-6':
        import pester_evaluations as pester
        source = pester.stage(workspace, root / 'bundle' / name)
    return source


def benchmark_policy(name):
    if benchmark_options(name)['diagnostic_only']:
        return {**POLICY, 'grading': 'custom_only', 'workspace_mode': 'isolated', 'diagnostic_only': True}
    return {**POLICY, "grading": "default_plus_custom", "upstream_revision":
            "89d7dcec017194af1d6f8853176b2dae9c1da762", "deterministic_gate": 3, "workspace_mode": "group",
            "fixture_boundary": "root-broker-unprivileged-agent-v1", "authorization_policy": "per-case-allowlist-v1",
            "task_source": "native_harbor", "task_build": GH_TASK_BUILD,
            "competing_revision": "d85f762d6e521abf5fe16703946e9b38adc42da7"} if name == "gh" else POLICY


def catalog_report(workspace, root):
    """Only ordinary, fully reported native findings may be advisory."""
    names = catalog_preflight(workspace)
    data = read_json(root / "reports/catalog-summary.json")
    entries = data["skills"]
    require(sorted(item["name"] for item in entries) == names, "Incomplete catalog report")
    require(type(data["total"]) is int and data["total"] == len(names), "Incorrect catalog cardinality")
    exit_code = int((root / "catalog.exit").read_text())
    errors = []
    lines = ["## Native collection and dataset contracts", ""]
    datasets = 0
    if exit_code not in (0, 1):
        errors.append(f"Catalog exited with infrastructure status {exit_code}")
    for item in entries:
        name = item["name"]
        status = "invalid report"
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
            for suffix in (".md", ".html"):
                sibling = root / "reports" / name / Path(filename).with_suffix(suffix)
                require(sibling.is_file() and not sibling.is_symlink() and sibling.stat().st_size > 0,
                        "Missing human-readable report")
        except (ValueError, KeyError, TypeError, IndexError, OSError):
            errors.append(f"{name}: Native report missing or invalid; inspect native JSON, Markdown and HTML evidence.")
        dataset = workspace / ".apm/skills" / name / "evals/evals.json"
        if dataset.exists() or dataset.is_symlink():
            datasets += 1
            try:
                benchmark_skill(workspace, name)
                require(int((root / "datasets" / f"{name}.exit").read_text()) == 0,
                        "Strict eval dataset validation failed")
                checks = read_json(root / "datasets" / f"{name}.json")
                require(isinstance(checks, list) and checks and all(row["status"] == "ok" for row in checks),
                        "Invalid strict-validation report")
            except (ValueError, KeyError, TypeError, OSError):
                errors.append(f"{name}: Strict eval dataset validation failed; inspect dataset reports and collection steps.")
    require(type(data["failed"]) is int and data["failed"] == sum(not item["passed"] for item in entries),
            "Incorrect failure count")
    if (exit_code == 0) != (data["failed"] == 0):
        errors.append("Catalog exit status disagrees with its reports")
    if errors:
        lines += ["**Infrastructure / contract checks failed. Findings remain unresolved.**", ""] + [f"- {error}" for error in errors]
    else:
        lines += [f"Native catalog exit/report checks and {datasets} strict dataset " + ('contract' if datasets == 1 else 'contracts') +
                  f" passed for {len(names)} local skills.",
                  "Findings are advisory. This does not establish skill security or effectiveness; public reporting is validated separately."]
    lines += ["", "The skill-quality artifact retains native JSON, Markdown, HTML and dataset evidence. A richer summary cannot override infrastructure failures."]
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


def recover_benchmark(workspace, root, name, mode, outcome):
    """Collect retained trials with the pinned native collector; never certify a run."""
    from skillevaluator.tier3.case_ids import validate_case_ids
    from skillevaluator.tier3.dataset_utils import load_dataset_entries
    from skillevaluator.tier3.harbor.collector import collect_harbor_results
    from skillevaluator.tier3.results_location import run_directory_sort_key

    skill = benchmark_skill(workspace, name, root)
    require(outcome in {"success", "failure", "cancelled", "skipped"}, "Invalid evaluation outcome")
    root = root.absolute()
    require(root.resolve() == root and not root.is_relative_to(workspace),
            "Recovery must use a real directory outside the checkout")
    root.mkdir(parents=True, exist_ok=True)
    regular_tree(root, excluded_dirs={"_harbor-jobs", "_harbor-tasks"},
                 excluded_links={Path("results") / name / "latest"})
    if outcome == "success":
        return  # Successful native collection/reporting remains authoritative.

    # This existing allowlisted metadata file also covers interruptions before a run exists.
    write_json(root / "provenance.json", {
        "schema_version": 1, "status": "incomplete", "evaluation_outcome": outcome,
        "diagnostic_only": True,
    })
    summary([f"## {name}: incomplete benchmark", "",
             f"Evaluation outcome: {outcome}. Recovered diagnostics cannot enter benchmark history."])
    results = root / "results" / name
    if not results.is_dir():
        return
    entries = load_dataset_entries(skill / "evals/evals.json")
    case_ids = validate_case_ids(entry.get("id") for entry in entries)
    cases = len(case_ids)
    for run in sorted(results.iterdir()):
        if run.name == "latest":
            continue
        require(run.is_dir() and not run.is_symlink(), "Unexpected native run entry")
        jobs = run / "_harbor-jobs"
        result = run / "result.json"
        if result.exists():
            require(result.is_file() and not result.is_symlink(),
                    f"Missing or linked JSON report: {result.name}")
            if run_directory_sort_key(run, require_completed_result=True) is not None:
                continue  # Preserve complete reports already produced by native collection.
        if not jobs.exists():
            continue  # No retained diagnostics are available for native collection.
        require(jobs.is_dir() and not jobs.is_symlink(), "Linked or invalid retained jobs directory")
        collected = collect_harbor_results(
            skill_name=name, agents=["codex"], output_dir=run, jobs_dir=jobs,
            n_attempts=MODES[mode], stop_on_pass=False, expected_cases=cases,
            expected_case_ids=case_ids,
            expected_trials=cases * MODES[mode], env_mode="docker",
            agent_models={"codex": {"model": POLICY["model"], "source": "cli"}},
        )
        # Native diagnostics may include completed trials but are never a completed evaluation.
        write_json(run / "result.json", {**collected, "skill_name": name,
                   "report_status": "incomplete", "diagnostic_only": True})


def benchmark_report(workspace, root, name, mode, destination):
    # These native APIs validate run identity/completeness; never imported by the publisher.
    from skillevaluator.evaluation import EvaluationService
    from skillevaluator.source_identity import evaluated_source_revision

    if benchmark_options(name)['diagnostic_only']:
        return diagnostic_benchmark_report(workspace, root, name, mode)

    if (root / "provenance.json").exists():
        require(read_json(root / "provenance.json").get("status") != "incomplete",
                "Incomplete benchmark recovery cannot produce history metrics")
    skill = benchmark_skill(workspace, name, root)
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
    require(harbor["timeout_multiplier"] == POLICY["timeout_multiplier"], "Timeout policy mismatch")
    require(config["grading"]["mode"] == benchmark_policy(name)["grading"], "Grading policy mismatch")
    revision = os.environ["GITHUB_SHA"]
    require(evaluated_source_revision(config["evaluated_source"]) == revision, "Evaluated source mismatch")
    cases = result["dataset_summary"]["total_tasks"]
    require(type(cases) is int and cases > 0, "Missing dataset cardinality")
    for arm in ("with_skill", "without_skill"):
        condition = agent["conditions"][arm]
        require(condition["execution_status"] == "succeeded" and not condition["execution_errors"]
                and condition["scored_attempts"] == condition["expected_attempts"] == cases * MODES[mode],
                "Incomplete with-skill/baseline coverage")
    if name == "gh":
        import gh_evaluations as gh
        expected_ids = [entry["id"] for entry in gh.dataset(workspace)]
        require(cases == len(expected_ids), "Diagnostic subset cannot publish benchmark history")
        if (root / "selection.json").exists():
            selection = read_json(root / "selection.json")
            require(selection["case_ids"] == expected_ids and (mode != "standard" or not selection["diagnostic_only"]),
                    "Diagnostic selection cannot publish benchmark history")
        deterministic = gh.deterministic_gate(run, expected_ids, MODES[mode])
        write_json(root / "deterministic.json", {"trials": deterministic})
    rows = metric_rows(agent)
    provenance = {
        "schema_version": 1, "skill": name, "mode": mode, "revision": revision,
        "policy": benchmark_policy(name), "patch_sha256": hashlib.sha256((workspace / PATCH).read_bytes()).hexdigest(),
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
    if name == "gh":
        lines += ["", "Mandatory deterministic with-skill gate: passed for every trial. "
                  "Baseline failures remain comparison evidence; separate scores are in deterministic.json."]
    summary(lines)
    if mode == "standard":
        write_json(destination / "metrics.json", provenance)


def diagnostic_benchmark_report(workspace, root, name, mode):
    """Validate native custom-only completion without standard-score projection."""
    from skillevaluator.evaluation import EvaluationService
    from skillevaluator.source_identity import evaluated_source_revision

    require(mode == 'confirmation', 'Diagnostic-only suite cannot enter standard history')
    if (root / 'provenance.json').exists():
        require(read_json(root / 'provenance.json').get('status') != 'incomplete',
                'Interrupted diagnostic recovery cannot certify a complete comparison')
    skill = benchmark_skill(workspace, name, root)
    service = EvaluationService()
    run = service.discover_latest_results(skill, root / 'results')
    require(run is not None and run.is_relative_to((root / 'results').resolve()),
            'No complete diagnostic comparison; retained trials are inconclusive')
    result = read_json(run / 'result.json')
    require(service.failure_reason(result) is None and result['report_status'] == 'complete',
            'Diagnostic comparison is incomplete or unscoreable')
    validate_benchmark_versions(read_json(root / 'versions.json'))
    require(result['skill_name'] == name and set(result['agents']) == {'codex'}, 'Diagnostic identity mismatch')
    config = result['run_config']
    require(config['grading']['mode'] == 'custom_only' and config['judge']['enabled'] is False,
            'Diagnostic grading mismatch')
    require(config['provider'] == {'name': 'openai', 'model': POLICY['model']}
            and result['agents']['codex']['model'] == POLICY['model'], 'Diagnostic model mismatch')
    require(evaluated_source_revision(config['evaluated_source']) == os.environ['GITHUB_SHA'],
            'Diagnostic source mismatch')
    harbor = config['harbor']
    require(harbor['environment']['value'] == 'docker' and harbor['n_attempts'] == MODES[mode]
            and harbor['n_concurrent'] == 2 and harbor['stop_on_pass'] is False
            and harbor['timeout_multiplier'] == POLICY['timeout_multiplier'], 'Diagnostic execution policy mismatch')
    cases = len(read_json(skill / 'evals/evals.json')['evals'])
    expected_ids = {entry['id'] for entry in read_json(skill / 'evals/evals.json')['evals']}
    require(result['dataset_summary']['total_tasks'] == cases, 'Diagnostic case coverage mismatch')
    for arm in ('with_skill', 'without_skill'):
        condition = result['agents']['codex']['conditions'][arm]
        require(condition['execution_status'] == 'succeeded' and not condition['execution_errors']
                and condition['scored_attempts'] == condition['expected_attempts'] == cases * MODES[mode],
                'Unscoreable trial makes the complete pilot comparison inconclusive')
        counts = {case: 0 for case in expected_ids}
        rewards = list((run / 'codex' / arm.replace('_', '-') / 'trials').glob('*/reward.json'))
        require(len(rewards) == cases * MODES[mode], 'Diagnostic retained trial cardinality mismatch')
        for path in rewards:
            reward = read_json(path)
            require(reward.get('entry_id') in counts and reward.get('has_skill') is (arm == 'with_skill'),
                    'Diagnostic retained trial identity mismatch')
            outcome = reward.get('custom_details', {}).get('outcome', {})
            require(outcome.get('classification') in ('passed', 'failed')
                    and reward.get('evaluation_status') == 'complete',
                    'Unscoreable or unclassified trial makes the comparison inconclusive')
            counts[reward['entry_id']] += 1
        require(all(count == MODES[mode] for count in counts.values()), 'Diagnostic retained case coverage mismatch')
    write_json(root / 'provenance.json', {'schema_version': 1, 'status': 'complete',
               'diagnostic_only': True, 'skill': name, 'mode': mode})
    summary([f'## {name}: native diagnostic comparison', '',
             'Native execution is complete. No standard judge metrics were scored. '
             'Custom outcomes remain diagnostic; public normalization and history are unavailable.'])


def validate_metrics(data, workspace, name, revision, *, mode="standard"):
    require(not benchmark_options(name)['diagnostic_only'], 'Diagnostic-only suite cannot publish history')
    require(set(data) == {"schema_version", "skill", "mode", "revision", "policy", "patch_sha256",
                          "dataset_digest", "metrics"}, "Unexpected history artifact fields")
    require(data["schema_version"] == 1 and data["skill"] == name and data["mode"] == mode,
            "History identity/mode mismatch")
    benchmark_skill(workspace, name)
    require(bool(re.fullmatch(r"[0-9a-f]{40}", revision)) and data["revision"] == revision, "Revision mismatch")
    require(data["policy"] == benchmark_policy(name), "Benchmark policy mismatch")
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
    require(not benchmark_options(name)['diagnostic_only'], 'Diagnostic-only suite cannot publish history')
    require(os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
            and os.environ.get("GITHUB_REF") == "refs/heads/main"
            and os.environ.get("BENCHMARK_MODE") == "standard", "History requires a main standard dispatch")
    data = read_json(root / "metrics.json", limit=16384)
    validate_metrics(data, workspace, name, os.environ["GITHUB_SHA"])
    policy_id = hashlib.sha256(json.dumps([benchmark_policy(name), data["patch_sha256"]], sort_keys=True).encode()).hexdigest()[:16]
    rows = [{**row, "extra": f"Dataset {data['dataset_digest']}; policy {policy_id}"} for row in data["metrics"]]
    write_json(root / "benchmark.json", rows)
    outputs(history_dir=f"benchmarks/{name}/{policy_id}")


def benchmark_artifacts(workspace, root, name, destination):
    """Stage only native report contracts, using upstream credential redaction."""
    from skillevaluator.utils.redaction import redact_sensitive_data, redact_sensitive_text

    benchmark_skill(workspace, name)
    root = root.absolute()
    destination = destination.absolute()
    for path in (root, destination):
        require(path.resolve() == path and not path.is_relative_to(workspace),
                "Benchmark artifacts must use real paths outside the checkout")
    require(not destination.is_relative_to(root) and not root.is_relative_to(destination),
            "Artifact staging must be separate from raw results")
    files = regular_tree(
        root,
        excluded_dirs={"_harbor-jobs", "_harbor-tasks"},
        excluded_links={Path("results") / name / "latest"},
    )
    metadata = {"versions.json", "dataset-validation.json", "provenance.json",
                "docker-version.json", "docker-images.jsonl"}
    if name == "gh":
        metadata.update({"deterministic.json", "selection.json"})
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
            value = read_json(source, limit=64 * 1024 * 1024)
            if benchmark_options(name)['diagnostic_only']:
                require('PESTER_VERIFIER_ONLY_' not in json.dumps(value), 'Protected verifier input in diagnostic artifact')
            value = redact_sensitive_data(value)
            if name == "gh":
                from gh_evaluations import redact_publication
                value = redact_publication(value)
            write_json(destination / relative, value)
        else:
            if name == "gh":
                require(source.stat().st_size <= 64 * 1024 * 1024, "Oversized gh diagnostic")
            text = source.read_text(encoding="utf-8")
            if benchmark_options(name)['diagnostic_only']:
                require('PESTER_VERIFIER_ONLY_' not in text, 'Protected verifier input in diagnostic artifact')
            text = redact_sensitive_text(text)
            if name == "gh":
                from gh_evaluations import redact_publication
                text = redact_publication(text)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        copied += 1
    require(copied > 0, "No publishable benchmark reports")
    summary([f"Staged {copied} allowlisted files with upstream redaction; raw runtime directories are excluded."])


def public_strings(value):
    """Detect credential patterns without changing authenticated claims or keys."""
    from skillevaluator.utils.redaction import redact_sensitive_text

    if isinstance(value, str):
        require(redact_sensitive_text(value) == value, "Credential pattern in public value")
    elif isinstance(value, dict):
        for item in value.values():
            public_strings(item)
    elif isinstance(value, list):
        for item in value:
            public_strings(item)


def stage_public(workspace, root, destination, records):
    """Reserve a private bundle; expose readiness only after exact-set validation."""
    import skill_evidence as evidence

    destination = Path(destination).absolute()
    root = Path(root).absolute()
    # The secure writer checks parents, ownership, freshness and input boundaries.
    evidence.write_outputs({}, destination, workspace, root)
    owned = destination.lstat()
    expected = set()
    guards = []
    try:
        for relative, value in records:
            evidence.relative(relative)
            require(relative not in expected, "Duplicate public member")
            member = Path(relative)
            if member.name == "inventory.json":
                require(relative == "inventory/inventory.json", "Unexpected inventory member")
            else:
                name = value["source"]["skill_id"]
                tail = "static" if value["kind"] == "static" else "behavioral/" + value["run_id"]
                require(relative == f"skills/{name}/{tail}/public-report.json", "Unexpected public member")
            parent = destination
            for part in member.parent.parent.parts:
                parent /= part
                if not parent.exists():
                    evidence.write_outputs({}, parent, workspace, root)
                evidence.safe_path(parent, directory=True)
            # Validate immediately before staging, even though projection validated too.
            if member.name == "inventory.json":
                evidence.validate_inventory(value)
            else:
                evidence.validate_public(value)
            public_strings(value)
            evidence.write_outputs({member.name: value}, destination / member.parent, workspace, root)
            guards.extend(evidence.record_guards(value))
            expected.add(relative)
        actual = {path.relative_to(destination).as_posix() for path in evidence.safe_tree(destination)}
        require(actual == expected and bool(expected), "Public bundle file set mismatch")
        # Recheck every captured input after the last report has been written.
        for guard in dict.fromkeys(guards):
            guard()
    except BaseException:
        current = destination.lstat()
        if (current.st_dev, current.st_ino) == (owned.st_dev, owned.st_ino):
            # CPython's descriptor-based rmtree never follows replacement symlinks.
            require(shutil.rmtree.avoids_symlink_attacks, "Secure staging cleanup unsupported")
            shutil.rmtree(destination)
        raise
    return len(expected)


def public_quality(workspace, root, destination):
    import skill_evidence as evidence
    import skill_analysis as analysis

    inv = evidence.inventory(workspace)
    names = sorted(row["source"]["skill_id"] for row in inv["skills"]
                   if row["source"]["owner"] == "local")
    # Capture catalog membership using the same bounded no-follow reader.
    directories = {}; states = {}; members = {}
    catalog = evidence.parse_json(evidence.read_bytes(Path(root) / "reports/catalog-summary.json",
        directory_identities=directories, directory_states=states, file_states=members))
    catalog_guard = evidence.input_guard(directories, states, members)
    require(type(catalog) is dict and type(catalog.get("skills")) is list,
            "Invalid public quality catalog")
    actual = [row["name"] for row in catalog["skills"]]
    if sorted(actual) != names:
        summary(["Public quality unavailable: catalog does not exactly cover discovered local skills."])
        raise ValueError("Public quality catalog membership mismatch")

    runs = []
    summary_bytes = 0

    def records():
        nonlocal summary_bytes
        yield "inventory/inventory.json", inv
        for name in names:
            data = evidence.normalize_static(Path(root), name, workspace)
            public = evidence.project(data)
            run = analysis.static_record(evidence.identity(public), public)
            summary_bytes += len(evidence.encoded(run))
            require(summary_bytes <= analysis.JSON_LIMIT, 'Quality summary input limit')
            runs.append(run)
            yield f"skills/{name}/static/public-report.json", public
        for guard in evidence.record_guards(inv):
            guard()
        catalog_guard()

    count = stage_public(workspace, root, destination, records())
    lines = ["## Skill quality · validated evidence (findings advisory)", "",
             "Infrastructure status is reported separately; this summary does not override a failed job or contract check.",
             f"{len(names)} local skills assessed. Static assessment excludes imported/deployed copies and evaluation overlays.",
             "Behavioral evaluations were not executed by this job; configured suites are not measured results.", "",
             *analysis.render_static_summary(runs), "",
             "| Skill | Native status | Failed / incomplete / skipped checks | Critical / High / Medium / Low | Behavioral suite |",
             "| --- | --- | --- | --- | --- |"]
    configured = {row['source']['skill_id']: row['suite'] is not None for row in inv['skills']}
    for run in runs:
        total = next(s for s in run['scans'] if s['scanner'] == 'catalog-total')
        flags = '; '.join(f"{s['scanner']} {s['status']}" for s in run['scans']
                          if s['scanner'] != 'catalog-total' and s['status'] != 'passed') or 'None recorded'
        counts = ' / '.join(str(total['severity_counts'][level]) for level in analysis.SEVERITIES)
        name = run['source']['skill_id']
        lines.append(f"| {name} | {total['status']} | {flags} | {counts} | " +
                     ('Configured; not executed here' if configured[name] else 'Not configured') + ' |')
    lines += ["", "Incomplete tool markers are coverage evidence, not additional findings. "
              "Detailed findings and reference IDs are in skill-public-quality; full native reports are in skill-quality."]
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    run_id = os.environ.get('GITHUB_RUN_ID', '')
    if (re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*', repo)
            and re.fullmatch(r'[0-9]{1,20}', run_id)):
        public_strings(repo)
        lines += [f"[Run artifacts](https://github.com/{repo}/actions/runs/{run_id}#artifacts)"]
    require(len('\n'.join(lines).encode('utf-8')) <= analysis.MARKDOWN_LIMIT, 'Quality summary size exceeded')
    summary(lines)
    summary([f"Public quality ready: {count - 1} validated skill reports and inventory."])


def public_benchmark(workspace, root, name, mode, destination, selected=None):
    require(not benchmark_options(name)['diagnostic_only'], 'Custom-only public normalization is not supported')
    import skill_evidence as evidence

    evidence.skill_id(name)
    require(mode in MODES, "Unsupported public benchmark mode")
    inv = evidence.inventory(workspace)
    require(any(row["source"]["skill_id"] == name and row["suite"] is not None for row in inv["skills"]),
            "Selected public benchmark has no configured suite")
    data = evidence.normalize_behavioral(Path(root), name, selected, workspace, native_layout=True)
    attempts = data["policy"]["attempts"]
    require(attempts["mode"] in (mode, "unknown") and attempts["maximum"] in (None, MODES[mode]),
            "Public benchmark mode mismatch")
    public = evidence.project(data)
    count = stage_public(workspace, root, destination, [
        ("inventory/inventory.json", inv),
        (f"skills/{name}/behavioral/{public['run_id']}/public-report.json", public),
    ])
    summary([f"Public benchmark ready: {count - 1} validated report; evidence {public['availability']['status']}."])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("preflight")
    select = commands.add_parser("select")
    select.add_argument("skill")
    select.add_argument("mode", choices=MODES)
    prepare = commands.add_parser('prepare')
    prepare.add_argument('root', type=Path)
    prepare.add_argument('skill')
    catalog = commands.add_parser("catalog")
    catalog.add_argument("root", type=Path)
    benchmark = commands.add_parser("benchmark")
    benchmark.add_argument("root", type=Path)
    benchmark.add_argument("skill")
    benchmark.add_argument("mode", choices=MODES)
    benchmark.add_argument("destination", type=Path)
    recover = commands.add_parser("recover")
    recover.add_argument("root", type=Path)
    recover.add_argument("skill")
    recover.add_argument("mode", choices=MODES)
    recover.add_argument("outcome", choices=("success", "failure", "cancelled", "skipped"))
    publish = commands.add_parser("publish")
    publish.add_argument("root", type=Path)
    publish.add_argument("skill")
    artifacts = commands.add_parser("artifacts")
    artifacts.add_argument("root", type=Path)
    artifacts.add_argument("skill")
    artifacts.add_argument("destination", type=Path)
    quality = commands.add_parser("public-quality")
    quality.add_argument("root", type=Path)
    quality.add_argument("destination", type=Path)
    public = commands.add_parser("public-benchmark")
    public.add_argument("root", type=Path)
    public.add_argument("skill")
    public.add_argument("mode", choices=MODES)
    public.add_argument("destination", type=Path)
    public.add_argument("--run")
    args = parser.parse_args()
    workspace = Path(os.environ["GITHUB_WORKSPACE"]).resolve()
    if args.command in {"public-quality", "public-benchmark"}:
        try:
            if args.command == "public-quality":
                public_quality(workspace, args.root, args.destination)
            else:
                public_benchmark(workspace, args.root, args.skill, args.mode, args.destination, args.run)
        except (ValueError, KeyError, TypeError, AttributeError, IndexError, OSError, OverflowError, UnicodeError, RecursionError):
            # Native exceptions may contain credentials or arbitrary prose. Never echo them.
            summary(["Public evidence unavailable: input or publication contract rejected; no bundle is ready."])
            return 1
    elif args.command == "preflight":
        catalog_preflight(workspace)
    elif args.command == "select":
        benchmark_skill(workspace, args.skill)
        options = benchmark_options(args.skill)
        require(not options['diagnostic_only'] or args.mode == 'confirmation',
                'Diagnostic-only suite requires confirmation mode; history is unavailable')
        outputs(skill=args.skill, attempts=MODES[args.mode],
                history_eligible=str(not options['diagnostic_only']).lower(),
                public_supported=str(not options['diagnostic_only']).lower())
    elif args.command == 'prepare':
        skill = prepare_benchmark(workspace, args.root, args.skill)
        options = benchmark_options(args.skill)
        outputs(skill_dir=str(skill), grading_mode=options['grading_mode'], workspace_mode=options['workspace_mode'])
    elif args.command == "catalog":
        try:
            catalog_report(workspace, args.root)
        except (ValueError, KeyError, TypeError, AttributeError, IndexError, OSError, OverflowError, UnicodeError, RecursionError):
            summary(["Native infrastructure contracts failed: catalog, exit, native report or dataset evidence is missing or invalid. "
                     "Inspect collection steps and the skill-quality artifact. Findings are unresolved; a richer summary cannot override this failure."])
            return 1
    elif args.command == "benchmark":
        benchmark_report(workspace, args.root, args.skill, args.mode, args.destination)
    elif args.command == "recover":
        recover_benchmark(workspace, args.root, args.skill, args.mode, args.outcome)
    elif args.command == "artifacts":
        benchmark_artifacts(workspace, args.root, args.skill, args.destination)
    else:
        publish_metrics(workspace, args.root, args.skill)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, TypeError, IndexError, OSError) as error:
        summary(["## Skill evaluation infrastructure failure", "", html.escape(str(error))])
        sys.exit(1)
