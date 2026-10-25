"""Keyless tests for CI trust boundaries and the pinned upstream integration."""

import ast
import asyncio
import contextlib
import hashlib
import importlib.util
import inspect
import io
import json
import os
import re
import signal
import sys
import time
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import yaml


REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("skill_reports", REPO / ".github/scripts/skill_reports.py")
reports = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reports)
SHA = "a" * 40
# Every Python install command in CI must be hash-verified or lock-frozen; ad-hoc
# installers that resolve at run time are forbidden. Applied to each logical
# command line of every workflow `run:` body and every `.github/scripts/*.sh`.
INSTALL_POLICY = (
    (re.compile(r'\b(pip3?|python3? -m pip)"?\s+install\b'), ("--require-hashes", "--only-binary :all:")),
    (re.compile(r"\buv pip (install|sync)\b"), ("--require-hashes", "--only-binary :all:")),
    (re.compile(r"\buv sync\b"), ("--frozen",)),
)
FORBIDDEN_INSTALLERS = re.compile(r"\b(pipx|uvx|uv tool install)\b")


def _workflow_files():
    # Actions loads both extensions, so every workflow-wide policy must scan both.
    return sorted((REPO / ".github/workflows").glob("*.y*ml"))


def _command_sources():
    for workflow in _workflow_files():
        for name, job in yaml.safe_load(workflow.read_text())["jobs"].items():
            for step in job.get("steps", []):
                if "run" in step:
                    yield f"{workflow.name}:{name}", step["run"]
    for script in sorted((REPO / ".github/scripts").glob("*.sh")):
        yield script.name, script.read_text()


def _command_lines(text):
    # Join shell continuations regardless of the whitespace around the escaped newline.
    for line in re.sub(r"[ \t]*\\\n[ \t]*", " ", text).splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            yield line


def _external_action_references(workflow):
    references = set()
    for job in workflow["jobs"].values():
        action = job.get("uses", "")
        if action:
            references.add(action)
        for step in job.get("steps", ()):
            action = step.get("uses", "")
            if action:
                references.add(action)
    return {
        action for action in references
        if not action.startswith(("./", "$/", "actions/", "github/"))
    }


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        self.skill = self.workspace / ".apm/skills/podman"
        self.skill.mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("---\nname: podman\n---\n")
        reports.write_json(self.skill / "evals/evals.json", {"skill_name": "podman", "evals": [{"id": 1, "prompt": "Harmless fixture", "expected_output": "Done"}]})
        patch_file = self.workspace / reports.PATCH
        patch_file.parent.mkdir(parents=True)
        patch_file.write_bytes((REPO / reports.PATCH).read_bytes())
        self.output = self.root / "github-output"
        self.env = patch.dict(os.environ, {"GITHUB_OUTPUT": str(self.output), "GITHUB_SHA": SHA,
            "GITHUB_STEP_SUMMARY": str(self.root / "summary"),
            "SKILLEVALUATOR_OUTPUT_PROVENANCE_KEY_FILE": str(self.root / "state/provenance.key")})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.stdout = contextlib.redirect_stdout(io.StringIO())
        self.stdout.__enter__()
        self.addCleanup(self.stdout.__exit__, None, None, None)

    def metrics(self):
        return {
            "schema_version": 1, "skill": "podman", "mode": "standard", "revision": SHA,
            "policy": reports.POLICY.copy(), "dataset_digest": "sha256:" + "b" * 64,
            "patch_sha256": hashlib.sha256((REPO / reports.PATCH).read_bytes()).hexdigest(),
            "metrics": [{"name": name, "unit": "score", "value": -0.1 if name == "Skill Lift" else 0.8}
                        for name in reports.METRICS],
        }

    def catalog(self):
        root = self.root / "quality"
        root.mkdir()
        (root / "catalog.exit").write_text("1\n")
        filename = "skillevaluator-output-20260919000000.json"
        reports.write_json(root / "reports/catalog-summary.json", {
            "total": 1, "failed": 1, "skills": [{"name": "podman", "passed": False,
                "reason": "validation failed", "json_report": filename}],
        })
        report = root / "reports/podman" / filename
        reports.write_json(report, {"overall_status": "incomplete", "overall_passed": False,
            "skills": [{"name": "podman"}], "total_validators": 1,
            "severity_counts": {"critical": 0, "high": 1, "medium": 0, "low": 0},
            "results": [{"status": "incomplete"}], "incomplete_scans": ["skillspector"]})
        for extension in (".html", ".md"):
            report.with_suffix(extension).write_text("Native report")
        reports.write_json(root / "datasets/podman.json", [{"status": "ok"}])
        (root / "datasets/podman.exit").write_text("0\n")
        return root

    def test_skill_selection_rejects_paths_and_symlinks(self):
        for name in ("../podman", "/podman", "podman\nother", "Podman", "missing"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                reports.local_skill(self.workspace, name, dataset=True)
        (self.skill.parent / "linked").symlink_to(self.skill, target_is_directory=True)
        with self.assertRaises(ValueError):
            reports.local_skill(self.workspace, "linked", dataset=True)
        self.assertEqual(reports.local_skill(self.workspace, "podman", dataset=True), self.skill)

    def test_complete_findings_are_advisory(self):
        reports.catalog_report(self.workspace, self.catalog())

    def test_nested_links_and_special_files_fail_before_evaluation(self):
        fixture = self.skill / "evals/files/input.txt"
        fixture.parent.mkdir()
        outside = self.root / "external.txt"
        outside.write_text("sentinel must never be read")
        for target in (outside, self.skill / "SKILL.md", self.root / "missing", fixture.parent):
            fixture.symlink_to(target)
            for operation in (lambda: reports.local_skill(self.workspace, "podman", dataset=True),
                              lambda: reports.catalog_preflight(self.workspace)):
                with self.subTest(target=target), self.assertRaises(ValueError):
                    operation()
            fixture.unlink()
        os.mkfifo(fixture)
        with self.assertRaises(ValueError):
            reports.catalog_preflight(self.workspace)
        fixture.unlink()
        with patch.object(reports.os, "scandir", side_effect=PermissionError("unreadable directory")):
            with self.assertRaises(PermissionError):
                reports.catalog_preflight(self.workspace)

    def test_catalog_rejects_linked_datasets_and_uncatalogued_directories(self):
        dataset = self.skill / "evals/evals.json"
        dataset.unlink()
        dataset.symlink_to(self.root / "missing-dataset")
        with self.assertRaises(ValueError):
            reports.catalog_preflight(self.workspace)
        dataset.unlink()
        (self.skill.parent / "unlisted").symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            reports.catalog_preflight(self.workspace)

    def test_catalog_counts_require_exact_nonnegative_integers(self):
        root = self.catalog()
        for filename, field in (("catalog-summary.json", "total"), ("catalog-summary.json", "failed"),
                                ("podman/skillevaluator-output-20260919000000.json", "total_validators")):
            path = root / "reports" / filename
            original = reports.read_json(path)
            for value in (True, False, 1.0, 1.5, -1, "1", 2):
                reports.write_json(path, {**original, field: value})
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    reports.catalog_report(self.workspace, root)
            reports.write_json(path, original)

    def test_native_status_follows_pass_and_incomplete_evidence(self):
        root = self.catalog()
        path = root / "reports/podman/skillevaluator-output-20260919000000.json"
        catalog_path = root / "reports/catalog-summary.json"
        report = reports.read_json(path)
        catalog = reports.read_json(catalog_path)
        for passed in (True, False):
            catalog["skills"][0].update(passed=passed, reason="" if passed else "validation failed")
            catalog["failed"] = int(not passed)
            reports.write_json(catalog_path, catalog)
            (root / "catalog.exit").write_text("0" if passed else "1")
            for incomplete in ([], ["skillspector"]):
                expected = "incomplete" if incomplete else "passed" if passed else "failed"
                for status in ("passed", "failed", "incomplete"):
                    reports.write_json(path, {**report, "overall_passed": passed,
                        "overall_status": status, "incomplete_scans": incomplete})
                    with self.subTest(passed=passed, incomplete=incomplete, status=status):
                        if status == expected:
                            reports.catalog_report(self.workspace, root)
                        else:
                            with self.assertRaises(ValueError):
                                reports.catalog_report(self.workspace, root)

    def test_catalog_runtime_exit_one_is_not_advisory(self):
        root = self.catalog()
        path = root / "reports/catalog-summary.json"
        data = reports.read_json(path)
        data["skills"][0]["reason"] = "unexpected error: simulated failure"
        reports.write_json(path, data)
        with self.assertRaises(ValueError):
            reports.catalog_report(self.workspace, root)

    def test_configuration_and_runtime_exit_codes_fail(self):
        root = self.catalog()
        for exit_code in (2, 3):
            (root / "catalog.exit").write_text(str(exit_code))
            with self.subTest(exit_code=exit_code), self.assertRaises(ValueError):
                reports.catalog_report(self.workspace, root)

    def test_all_strict_dataset_failures_are_collected(self):
        root = self.catalog()
        second = self.skill.parent / "second"
        second.mkdir()
        (second / "SKILL.md").write_text("---\nname: second\n---\n")
        reports.write_json(second / "evals/evals.json", {"evals": [{"id": 2}]})
        data = reports.read_json(root / "reports/catalog-summary.json")
        data.update(total=2, failed=2)
        data["skills"].append({**data["skills"][0], "name": "second"})
        reports.write_json(root / "reports/catalog-summary.json", data)
        for name in ("podman", "second"):
            (root / "datasets" / f"{name}.exit").write_text("1\n")
        with self.assertRaises(ValueError):
            reports.catalog_report(self.workspace, root)
        text = (self.root / "summary").read_text()
        for name in ("podman", "second"):
            self.assertIn(f"{name}: Strict eval dataset validation failed", text)

    def test_missing_reports_and_strict_failures_are_hard_failures(self):
        root = self.catalog()
        (root / "reports/podman/skillevaluator-output-20260919000000.json").unlink()
        (root / "datasets/podman.exit").write_text("1\n")
        with self.assertRaises(ValueError):
            reports.catalog_report(self.workspace, root)
        summary = (self.root / "summary").read_text()
        self.assertIn("Native report missing or invalid", summary)
        self.assertIn("Strict eval dataset validation failed", summary)

    def test_invalid_numeric_and_extra_artifact_fields_are_rejected(self):
        for value in (float("nan"), float("inf"), True, "0.8", 2):
            data = self.metrics()
            data["metrics"][0]["value"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                reports.validate_metrics(data, self.workspace, "podman", SHA)
        data = self.metrics()
        data["arbitrary_payload"] = "not permitted"
        with self.assertRaises(ValueError):
            reports.validate_metrics(data, self.workspace, "podman", SHA)

    def test_only_main_standard_dispatch_can_publish(self):
        directory = self.root / "metrics"
        reports.write_json(directory / "metrics.json", self.metrics())
        for event, ref, mode in (("push", "refs/heads/main", "standard"),
                                 ("workflow_dispatch", "refs/heads/feature", "standard"),
                                 ("workflow_dispatch", "refs/heads/main", "confirmation")):
            with patch.dict(os.environ, {"GITHUB_EVENT_NAME": event, "GITHUB_REF": ref, "BENCHMARK_MODE": mode}):
                with self.assertRaises(ValueError):
                    reports.publish_metrics(self.workspace, directory, "podman")
        with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
                                    "BENCHMARK_MODE": "standard"}):
            reports.publish_metrics(self.workspace, directory, "podman")
        data = reports.read_json(directory / "benchmark.json")
        self.assertEqual(len(data), 4)
        self.assertEqual(data[0]["value"], -0.1)
        self.assertRegex(self.output.read_text(), r"^history_dir=benchmarks/podman/[0-9a-f]{16}\n$")

    def test_confirmation_artifact_cannot_masquerade_as_standard(self):
        data = self.metrics()
        data["mode"] = "confirmation"
        with self.assertRaises(ValueError):
            reports.validate_metrics(data, self.workspace, "podman", SHA)

    def benchmark(self, mode):
        from skillevaluator.tier3.output_provenance import mark_generated_output_root
        root = self.root / "benchmark"
        run = root / "results/podman/20260919_000000_111_aaaaaaaaaaaa"
        cases = 10
        attempts = cases * reports.MODES[mode]
        condition = {"execution_status": "succeeded", "execution_errors": [],
                     "expected_attempts": attempts, "scored_attempts": attempts}
        data = {
            "skill_name": "podman", "execution_status": "succeeded", "execution_errors": [],
            "report_status": "complete", "dataset_summary": {"total_tasks": cases},
            "dataset_digest": "sha256:" + "b" * 64,
            "run_config": {"config_file": "none", "task_source": "evals_json",
                "provider": {"name": "openai", "model": reports.POLICY["model"]},
                "judge": {"model": reports.POLICY["model"], "provider": "openai", "override_applied": True},
                "harbor": {"environment": {"value": "docker", "source": "cli"}, "n_attempts": reports.MODES[mode],
                           "n_concurrent": 2, "stop_on_pass": False,
                           "timeout_multiplier": reports.POLICY["timeout_multiplier"],
                           "base_image_mode": "reuse", "jobs_retained": False},
                "agents": {"codex": {"agent": "codex", "model": reports.POLICY["model"], "source": "cli"}},
                "grading": {"mode": "default"}, "evaluated_source": {"commit": SHA}},
            "agents": {"codex": {"model": reports.POLICY["model"],
                "model_source": "cli", "model_resolution": {"model": reports.POLICY["model"], "source": "cli"},
                "with_skill": {"overall": 0.8}, "without_skill": {"overall": 0.9},
                "custom_with_skill": {}, "custom_without_skill": {}, "dimensions_without_skill": {},
                "custom_lift": {}, "security_attribution": {},
                "pass_at_k": {"with_skill": {}, "without_skill": {}, "lift": {}},
                "agent_runtime_failures": {"with_skill": [], "without_skill": []},
                "trial_failures": {"with_skill": [], "without_skill": []},
                "job_failures": {"with_skill": "", "without_skill": ""},
                "execution_status": "succeeded", "execution_errors": [],
                "expected_attempts": attempts * 2, "scored_attempts": attempts * 2,
                "num_trials_with": attempts, "num_trials_without": attempts, "output_dir": str(run / "codex"),
                "conditions": {"with_skill": condition.copy(), "without_skill": condition.copy()},
                "lift": {"overall": {"delta": -0.1}}, "dimensions_with_skill": {
                    name: {"score": 0.8} for name in ("effectiveness", "correctness", "discoverability")}}},
        }
        data.update(run_id=run.name, run_dir=str(run), result_path=str(run / "result.json"), duration_seconds=1.0,
                    attempt_policy={"max_attempts": reports.MODES[mode], "pass_threshold": 0.5,
                                    "stop_on_pass": False, "score_definition": "native fixture"})
        run.mkdir(parents=True)
        mark_generated_output_root(run)
        reports.write_json(run / "run_config.json", data["run_config"])
        reports.write_json(run / "result.json", data)
        (run / "report.html").write_text("Native HTML fixture")
        reports.write_json(root / "versions.json", {"python": "3.13.15", "skillevaluator": "0.3.0",
                                                     "harbor": "0.13.2", "docker_compose": reports.POLICY["docker_compose"]})
        return root, run, data

    def test_confirmation_gets_summary_and_provenance_but_no_history_artifact(self):
        root, run, _ = self.benchmark("confirmation")
        reports.benchmark_report(self.workspace, root, "podman", "confirmation", self.root / "metrics")
        self.assertTrue((root / "provenance.json").exists())
        self.assertFalse((self.root / "metrics").exists())
        self.assertIn("60 task trials", (self.root / "summary").read_text())

    def test_partial_baseline_prevents_standard_history(self):
        root, run, data = self.benchmark("standard")
        data["agents"]["codex"]["conditions"]["without_skill"]["scored_attempts"] -= 1
        reports.write_json(run / "result.json", data)
        with self.assertRaises(ValueError):
            reports.benchmark_report(self.workspace, root, "podman", "standard", self.root / "metrics")
        self.assertFalse((self.root / "metrics").exists())

    def test_native_result_discovery_and_standard_metric_extraction(self):
        root, _, _ = self.benchmark("standard")
        reports.benchmark_report(self.workspace, root, "podman", "standard", self.root / "metrics")
        data = reports.read_json(self.root / "metrics/metrics.json")
        self.assertEqual(data["metrics"][0]["value"], -0.1)
        self.assertEqual(data["metrics"][3]["name"], "Discoverability")
        self.assertEqual(data["policy"]["timeout_multiplier"], 2.0)

    def test_missing_or_wrong_timeout_policy_prevents_history(self):
        root, run, data = self.benchmark("standard")
        harbor = data["run_config"]["harbor"]
        for timeout in (None, 1.0):
            if timeout is None:
                harbor.pop("timeout_multiplier", None)
            else:
                harbor["timeout_multiplier"] = timeout
            reports.write_json(run / "result.json", data)
            with self.subTest(timeout=timeout), self.assertRaises((KeyError, ValueError)):
                reports.benchmark_report(self.workspace, root, "podman", "standard", self.root / "metrics")
            self.assertFalse((self.root / "metrics").exists())

    def test_wrong_python_runtime_prevents_history(self):
        root, _, _ = self.benchmark("standard")
        reports.write_json(root / "versions.json", {"python": "3.14.0", "skillevaluator": "0.3.0",
                                                     "harbor": "0.13.2", "docker_compose": reports.POLICY["docker_compose"]})
        with self.assertRaises(ValueError):
            reports.benchmark_report(self.workspace, root, "podman", "standard", self.root / "metrics")

    def test_missing_or_wrong_docker_compose_runtime_prevents_history(self):
        for version in (None, "5.0.2", "2.38.2"):
            versions = {"python": "3.13.15", "skillevaluator": "0.3.0", "harbor": "0.13.2"}
            if version is not None:
                versions["docker_compose"] = version
            with self.subTest(version=version), self.assertRaises(ValueError):
                reports.validate_benchmark_versions(versions)

    def test_compose_policy_change_separates_history_and_rejects_old_admission(self):
        directories = []
        with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_dispatch",
                                     "GITHUB_REF": "refs/heads/main", "BENCHMARK_MODE": "standard"}):
            for version in ("5.0.2", reports.POLICY["docker_compose"]):
                with patch.dict(reports.POLICY, {"docker_compose": version}):
                    data = self.metrics()
                    reports.write_json(self.root / "metrics.json", data)
                    reports.publish_metrics(self.workspace, self.root, "podman")
                    directories.append(self.output.read_text().splitlines()[-1])
                if version == "5.0.2":
                    with self.assertRaisesRegex(ValueError, "Benchmark policy mismatch"):
                        reports.validate_metrics(data, self.workspace, "podman", SHA)
        self.assertNotEqual(*directories)

    def test_native_usage_unknown_and_duplicate_trial_handling(self):
        for name in ("trial", "duplicate"):
            reports.write_json(self.root / "codex/with-skill/trials" / name / "result.json", {
                "id": "same-physical-trial", "agent_result": {
                    "n_input_tokens": 100, "n_cache_tokens": 20, "n_output_tokens": 30, "cost_usd": None}})
        text = "\n".join(reports.usage_summary(self.root))
        self.assertIn("n_input_tokens | 100 | 1 / 1", text)
        self.assertIn("cost_usd | unknown | 0 / 1", text)

    def test_artifact_staging_allowlist_and_native_redaction(self):
        root, run, data = self.benchmark("standard")
        destination = self.root / "publication"
        sentinel = "sk-proj-" + "synthetic-review-only-" * 3
        diagnostic_marker = " ... [truncated] ... "
        data["execution_errors"] = [
            f"preflight head {sentinel}{diagnostic_marker}"
            f"Startup diagnostics: service logs (exit 0): terminal Docker build failure"
        ]
        reports.write_json(run / "result.json", data)
        trial = run / "codex/with-skill/trials/case-1"
        reports.write_json(trial / "result.json", {"output": sentinel, "OPENAI_API_KEY": sentinel})
        (run / "report.html").write_text(f"<p>{sentinel}</p>")
        reports.write_json(root / "dependencies/evaluator.json", [{"name": "harbor", "version": "0.13.2"}])
        unexpected = [root / ".env", root / "unexpected.json", run / "unknown.txt",
                      run / "_harbor-jobs/job/result.json", trial / "auth.json"]
        for path in unexpected:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(sentinel)
        latest = root / "results/podman/latest"
        latest.symlink_to(run.name)
        reports.benchmark_artifacts(self.workspace, root, "podman", destination)
        for path in unexpected:
            self.assertFalse((destination / path.relative_to(root)).exists())
        self.assertTrue((destination / "dependencies/evaluator.json").is_file())
        self.assertFalse((destination / latest.relative_to(root)).exists())
        for path in (trial / "result.json", run / "report.html"):
            self.assertNotIn(sentinel, (destination / path.relative_to(root)).read_text())
            self.assertIn(sentinel, path.read_text())  # No mutation of raw evidence.
        staged_result = (destination / (run / "result.json").relative_to(root)).read_text()
        self.assertIn(diagnostic_marker, staged_result)
        self.assertIn("terminal Docker build failure", staged_result)
        self.assertNotIn(sentinel, staged_result)
        self.assertEqual(reports.read_json(run / "result.json"), data)

    def test_artifact_staging_rejects_links_and_checkout_destinations(self):
        root, run, _ = self.benchmark("standard")
        for linked in (run / "report.html", run / "linked-dir"):
            if linked.exists():
                linked.unlink()
            linked.symlink_to(self.root / "missing")
            with self.assertRaises(ValueError):
                reports.benchmark_artifacts(self.workspace, root, "podman", self.root / "publication")
            self.assertFalse((self.root / "publication").exists())
            linked.unlink()
        latest = root / "results/podman/latest"
        latest.write_text("unexpected collision")
        with self.assertRaises(ValueError):
            reports.benchmark_artifacts(self.workspace, root, "podman", self.root / "publication")
        self.assertFalse((self.root / "publication").exists())
        latest.unlink()
        with self.assertRaises(ValueError):
            reports.benchmark_artifacts(self.workspace, root, "podman", self.workspace / "publication")
        with self.assertRaises(ValueError):
            reports.benchmark_artifacts(self.workspace, root, "podman", root / "publication")

    def test_failed_runs_retain_allowlisted_diagnostics(self):
        root, run, _ = self.benchmark("standard")
        (run / "result.json").unlink()
        (run / "report.html").unlink()
        reports.write_json(run / "codex/without-skill/trials/case-1/failure.json",
                           {"status": "unscored", "error": "native runtime failure"})
        (root / "results/podman/latest").symlink_to(run.name)
        destination = self.root / "publication"
        reports.benchmark_artifacts(self.workspace, root, "podman", destination)
        self.assertTrue((destination / (run / "codex/without-skill/trials/case-1/failure.json").relative_to(root)).is_file())

    def test_interrupted_trial_survives_native_retention_collection_and_redaction(self):
        root = self.root / "interrupted"
        run = root / "results/podman/interrupted-run"
        sentinel = "sk-proj-" + "synthetic-interruption-only-" * 3
        # Exercise the evaluator's real interruption cleanup in a harmless child process.
        # Only workload execution is replaced; native retention and collection run unchanged.
        code = r"""
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch
from skillevaluator.tier3.harbor import runner
from skillevaluator.tier3.harbor.progress import ProgressEvent
run = Path(sys.argv[1])
secret = sys.argv[2]
def harmless_trial(**kwargs):
    trial_name = 'skillevaluator-1__attempt001'
    for condition in ('with', 'without'):
        job = run / f'_harbor-jobs/podman-codex-{condition}'
        trial = job / trial_name
        verifier = trial / 'verifier'
        verifier.mkdir(parents=True)
        (trial / 'result.json').write_text(json.dumps({
            'task_name': 'nvidia/skillevaluator-1', 'trial_name': trial_name,
            'finished_at': '2026-01-01T00:00:00Z',
        }))
        (verifier / 'reward.json').write_text(json.dumps({
            'entry_id': 'skillevaluator-1', 'metric_set': 'skill_evaluator_default_v1',
            'effectiveness': 0.8, 'correctness': 0.8, 'discoverability': 0.8,
            'security': 1.0, 'skill_execution': 1.0, 'skill_efficiency': 1.0,
            'accuracy': 0.8, 'goal_accuracy': 0.8, 'behavior_check': 0.8, 'overall': 0.8,
        }))
        (job / 'result.json').write_text(json.dumps({
            'n_total_trials': 1,
            'stats': {
                'n_completed_trials': 1, 'n_errored_trials': 0, 'n_running_trials': 0,
                'n_pending_trials': 0, 'n_cancelled_trials': 0, 'n_retries': 0,
                'evals': {'agent__model___harbor-tasks': {
                    'n_trials': 1, 'n_errors': 0,
                    'reward_stats': {'reward': {'0.8': [trial_name]}},
                }},
            },
        }))
    trial = run / '_harbor-jobs/podman-codex-with' / trial_name
    (trial / 'trial.log').write_text('completed harmless trial ' + secret)
    (trial / 'auth.json').write_text(secret)
    kwargs['progress_reporter'].emit(ProgressEvent(stage='with-skill-tasks', state='running', output_dir=str(run)))
    (run / 'ready').touch()
    while True:
        time.sleep(1)
try:
    with patch.object(runner, '_run_harbor_eval_impl', harmless_trial):
        runner.run_harbor_eval(keep_harbor_jobs=True)
except KeyboardInterrupt:
    sys.exit(130)
"""
        process = subprocess.Popen([sys.executable, "-c", code, str(run), sentinel],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 20
            while not (run / "ready").exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            if not (run / "ready").exists():
                process.kill()
                _, stderr = process.communicate()
                self.fail("Harmless trial did not finish before interruption: " + stderr)
            process.send_signal(signal.SIGINT)
            _, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 130, stderr)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
        raw_trial = run / "_harbor-jobs/podman-codex-with/skillevaluator-1__attempt001"
        self.assertIn(sentinel, (raw_trial / "trial.log").read_text())
        (run / "result.json").write_text("{", encoding="utf-8")
        reports.recover_benchmark(self.workspace, root, "podman", "standard", "cancelled")
        destination = self.root / "publication"
        reports.benchmark_artifacts(self.workspace, root, "podman", destination)
        trial = destination / run.relative_to(root) / "codex/with-skill/trials/skillevaluator-1__attempt001"
        self.assertIn("completed harmless trial", (trial / "trial.log").read_text())
        self.assertNotIn(sentinel, (trial / "trial.log").read_text())
        self.assertFalse((trial / "auth.json").exists())
        self.assertFalse(any(path.name.startswith("_harbor-") for path in destination.rglob("*")))
        result = reports.read_json(destination / run.relative_to(root) / "result.json")
        self.assertEqual(result["report_status"], "incomplete")
        for condition in ("with_skill", "without_skill"):
            cases = result["agents"]["codex"]["pass_at_k"][condition]["cases"]
            self.assertEqual(set(cases), {"1"})
        self.assertEqual(reports.read_json(destination / "provenance.json")["status"], "incomplete")
        with self.assertRaisesRegex(ValueError, "cannot produce history"):
            reports.benchmark_report(self.workspace, root, "podman", "standard", self.root / "metrics")
        self.assertFalse((self.root / "metrics/metrics.json").exists())
        with self.assertRaises(ValueError):
            reports.validate_metrics(reports.read_json(root / "provenance.json"), self.workspace, "podman", SHA)

    def test_recovery_marks_early_failures_and_preserves_native_reports(self):
        early = self.root / "early"
        reports.recover_benchmark(self.workspace, early, "podman", "standard", "skipped")
        self.assertEqual(reports.read_json(early / "provenance.json")["status"], "incomplete")
        root, run, data = self.benchmark("standard")
        reports.recover_benchmark(self.workspace, root, "podman", "standard", "success")
        self.assertEqual(reports.read_json(run / "result.json"), data)
        self.assertFalse((root / "provenance.json").exists())
        reports.recover_benchmark(self.workspace, root, "podman", "standard", "failure")
        self.assertEqual(reports.read_json(run / "result.json"), data)
        with self.assertRaisesRegex(ValueError, "cannot produce history"):
            reports.benchmark_report(self.workspace, root, "podman", "standard", self.root / "metrics")

    def test_recovery_rejects_result_json_directories(self):
        root, run, _ = self.benchmark("standard")
        result = run / "result.json"
        (run / "_harbor-jobs").mkdir()
        result.unlink()
        result.mkdir()
        with self.assertRaisesRegex(ValueError, "Missing or linked JSON report: result.json"):
            reports.recover_benchmark(self.workspace, root, "podman", "standard", "failure")

    def test_recovery_rejects_linked_job_roots(self):
        root, run, _ = self.benchmark("standard")
        (run / "result.json").unlink()
        (run / "_harbor-jobs").symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "excluded runtime directory"):
            reports.recover_benchmark(self.workspace, root, "podman", "standard", "failure")

    def test_regular_tree_rejects_linked_excluded_runtime_directories(self):
        for name in ("_harbor-jobs", "_harbor-tasks"):
            root = self.root / name.removeprefix("_")
            root.mkdir()
            (root / name).symlink_to(self.root, target_is_directory=True)
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "excluded runtime directory"):
                reports.regular_tree(root, excluded_dirs={"_harbor-jobs", "_harbor-tasks"})

    def test_regular_tree_rejects_windows_reparse_runtime_directories(self):
        root = self.root / "reparse"
        root.mkdir()
        metadata = SimpleNamespace(
            st_mode=reports.stat.S_IFDIR,
            st_file_attributes=getattr(reports.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400),
        )

        def entry_stat(*, follow_symlinks):
            self.assertFalse(follow_symlinks)
            return metadata

        entry = SimpleNamespace(
            name="_harbor-jobs",
            path=str(root / "_harbor-jobs"),
            stat=entry_stat,
        )
        with patch.object(reports.os, "scandir", return_value=contextlib.nullcontext([entry])), \
                self.assertRaisesRegex(ValueError, "excluded runtime directory"):
            reports.regular_tree(root, excluded_dirs={"_harbor-jobs", "_harbor-tasks"})

    def test_recovery_cli_dispatches_all_arguments(self):
        root = self.root / "recovery"
        arguments = ["skill_reports.py", "recover", str(root), "podman", "confirmation", "cancelled"]
        with patch.dict(os.environ, {"GITHUB_WORKSPACE": str(self.workspace)}), \
                patch.object(sys, "argv", arguments), \
                patch.object(reports, "recover_benchmark") as recover:
            reports.main()
        recover.assert_called_once_with(
            self.workspace.resolve(), root, "podman", "confirmation", "cancelled")


class UpstreamTests(unittest.TestCase):
    def test_pinned_cli_forwards_native_retention(self):
        from click.testing import CliRunner
        from skillevaluator.cli import cli
        from skillevaluator.tier3 import commands

        captured = {}

        def evaluate(skill_path, **kwargs):
            captured["skill_path"] = skill_path
            captured.update(kwargs)
            return {"execution_status": "succeeded", "execution_errors": []}

        skill = REPO / ".apm/skills/podman"
        with patch.object(commands, "evaluate", side_effect=evaluate):
            result = CliRunner().invoke(cli, [
                "tier3", "evaluate", str(skill), "--agents", "codex", "--env-mode", "docker",
                "--harbor-keep-jobs", "--progress", "off",
            ])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(captured["skill_path"], skill)
        self.assertIs(captured["harbor_keep_jobs"], True)

    def test_podman_native_negative_control_and_strict_validation(self):
        from click.testing import CliRunner
        from skillevaluator.cli import cli
        from skillevaluator.tier3.dataset_utils import load_dataset_entries
        from skillevaluator.tier3.harbor.report_data import summarize_dataset_entries
        from skillevaluator.tier3.harbor.templates.eval import resolve_should_trigger, score_skill_execution
        skill = reports.local_skill(REPO, "podman", dataset=True)
        entries = load_dataset_entries(skill / "evals/evals.json")
        case = next(case for case in entries if case["id"] == 8)
        self.assertIsNone(case["expected_skill"])
        self.assertFalse(resolve_should_trigger(case))
        self.assertEqual(summarize_dataset_entries(entries)["negative_tasks"], 1)
        self.assertEqual(score_skill_execution([], None, should_trigger=False,
                         evaluated_skill="podman", require_evaluated_skill=True)["score"], 1)
        result = CliRunner().invoke(cli, ["tier3", "validate", str(skill), "--strict", "--json"])
        self.assertEqual(result.exit_code, 0, result.output)

    def test_pinned_evaluator_patch_only_pins_codex_for_docker_runs(self):
        from skillevaluator.tier3.harbor import runner
        from harbor.agents.installed.codex import Codex
        patch_text = (REPO / reports.PATCH).read_text()
        self.assertEqual(
            re.findall(r"^diff --git a/(\S+)", patch_text, re.MULTILINE),
            ["src/skillevaluator/tier3/harbor/runner.py"],
            "the reviewed patch must touch only Harbor's run-command builder",
        )
        self.assertEqual(len(re.findall(r"^@@", patch_text, re.MULTILINE)), 1)
        added = [line[1:] for line in patch_text.splitlines() if line.startswith("+") and not line.startswith("+++")]
        self.assertEqual([line.strip() for line in added],
                         ['if agent == "codex":', 'command.extend(["--ak", "version=0.155.1"])'])
        self.assertFalse(any(line.startswith("-") and not line.startswith("---") for line in patch_text.splitlines()))

        runner_source = Path(inspect.getfile(runner)).read_text()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner_target = root / "src/skillevaluator/tier3/harbor/runner.py"
            runner_target.parent.mkdir(parents=True)
            runner_target.write_text(runner_source)
            # Benchmark setup is already patched; quality setup is the pristine source.
            if 'command.extend(["--ak", "version=0.155.1"])' not in runner_source:
                subprocess.run(["git", "apply", "--check", str(REPO / reports.PATCH)], cwd=root, check=True)
                subprocess.run(["git", "apply", str(REPO / reports.PATCH)], cwd=root, check=True)
            runner_tree = ast.parse(runner_target.read_text())
            function = next(node for node in runner_tree.body if isinstance(node, ast.FunctionDef)
                            and node.name == "build_harbor_run_command")
            namespace = vars(runner).copy()
            exec(compile(ast.Module(body=[function], type_ignores=[]), str(runner_target), "exec"), namespace)
            build = namespace["build_harbor_run_command"]
            common = {"dataset_path": "unused", "job_name": "keyless-test"}
            command = build(agent="codex", env_mode="docker", **common)
            self.assertEqual(command[command.index("--ak") + 1], "version=0.155.1")
            for agent, environment in (("claude-code", "docker"), ("codex", "local"), ("codex", "daytona")):
                self.assertNotIn("--ak", build(agent=agent, env_mode=environment, **common))
            codex = Codex(logs_dir=root / "logs", model_name=reports.POLICY["model"], version="0.155.1")
            with patch.object(codex, "exec_as_root", new_callable=AsyncMock), \
                    patch.object(codex, "exec_as_agent", new_callable=AsyncMock) as execute:
                asyncio.run(codex.install(object()))
                install_command = execute.call_args.kwargs["command"]
            self.assertIn("npm install -g @openai/codex@0.155.1", install_command)
            self.assertNotIn("@latest", install_command)


class WorkflowTests(unittest.TestCase):
    @staticmethod
    def _run_step(step, env, cwd):
        """Execute a workflow step's shell body the way the runner does."""
        base = {"PATH": env.pop("PATH", os.environ["PATH"]), "HOME": str(cwd)}
        return subprocess.run(
            ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", step["run"]],
            cwd=cwd, env={**base, **env}, capture_output=True, text=True, timeout=60,
        )

    def test_update_uses_isolated_refresh_with_only_the_reviewed_cli(self):
        workflow = yaml.safe_load((REPO / ".github/workflows/update-baseline.yml").read_text())
        step = next(step for step in workflow["jobs"]["generate"]["steps"]
                    if step.get("name") == "Update APM dependencies with reviewed CLI")
        for status in (0, 23):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                executable = root / "python3"
                executable.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$CALL_LOG"\nexit "$FAIL_STATUS"\n')
                executable.chmod(0o755)
                log = root / "calls"
                completed = self._run_step(step, {
                    "PATH": str(root) + os.pathsep + os.environ["PATH"],
                    "APM_EXECUTABLE": str(root / "reviewed apm"),
                    "CALL_LOG": str(log), "FAIL_STATUS": str(status),
                }, root)
                self.assertEqual(completed.returncode, status, completed.stderr)
                self.assertEqual(log.read_text().splitlines(), [
                    "scripts/apm_regeneration.py", "--mode", "refresh", "--apm", str(root / "reviewed apm"),
                ])


    def test_update_acquisition_generates_the_supported_checksum_set_without_execution(self):
        import stat
        import tarfile
        import zipfile

        workflow = yaml.safe_load((REPO / ".github/workflows/update-baseline.yml").read_text())
        step = next(step for step in workflow["jobs"]["generate"]["steps"]
                    if step.get("name") == "Inspect candidate release archives without execution")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            releases = root / "releases"
            releases.mkdir()
            expected = {}
            # An executable payload would leave a sentinel if the updater ran it.
            payload = f"#!/bin/sh\ntouch '{root / 'candidate-executed'}'\nexit 99\n".encode()
            for platform in ("linux-arm64", "linux-x86_64", "windows-x86_64"):
                directory = f"apm-{platform}"
                executable = f"{directory}/apm" + (".exe" if platform.startswith("windows") else "")
                entries = {executable: payload, f"{directory}/_internal/data": b"fixture"}
                archive = releases / (directory + (".zip" if platform.startswith("windows") else ".tar.gz"))
                if platform.startswith("windows"):
                    with zipfile.ZipFile(archive, "w") as bundle:
                        for name, content in entries.items():
                            entry = zipfile.ZipInfo(name)
                            entry.external_attr = (stat.S_IFREG | 0o644) << 16
                            bundle.writestr(entry, content)
                else:
                    with tarfile.open(archive, "w:gz") as bundle:
                        for name, content in entries.items():
                            entry = tarfile.TarInfo(name)
                            entry.size = len(content)
                            bundle.addfile(entry, io.BytesIO(content))
                digest = hashlib.sha256(archive.read_bytes()).hexdigest()
                archive.with_name(archive.name + ".sha256").write_text(f"{digest}  {archive.name}\n")
                expected[archive.name] = digest
                expected[executable] = hashlib.sha256(payload).hexdigest()
            bin_dir = root / "bin"
            bin_dir.mkdir()
            curl = bin_dir / "curl"
            curl.write_text(
                "#!/bin/sh\nwhile [ $# -gt 0 ]; do\n"
                "  if [ \"$1\" = --output ]; then output=$2; shift 2; else url=$1; shift; fi\n"
                "done\ncp \"$FIXTURE_RELEASE_ROOT/${url##*/}\" \"$output\"\n")
            curl.chmod(0o755)
            completed = self._run_step(step, {
                "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                "RUNNER_TEMP": str(root / "runner"), "CANDIDATE_VERSION": "0.34.0",
                "FIXTURE_RELEASE_ROOT": str(releases),
            }, root)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            checksums = dict(reversed(line.split()) for line in (root / ".apm-checksums").read_text().splitlines())
            self.assertEqual(checksums, expected)
            self.assertEqual((root / ".apm-version").read_text(), "0.34.0\n")
            self.assertFalse((root / "candidate-executed").exists())

    def test_evaluation_budget_bounds_the_native_run_and_preserves_recovery_time(self):
        job = yaml.safe_load((REPO / ".github/workflows/benchmark-skills.yml").read_text())["jobs"]["evaluate"]
        steps = job["steps"]
        budget = next(step for step in steps if step.get("id") == "budget")
        evaluation = next(step for step in steps if step.get("id") == "evaluation")
        recovery = next(step for step in steps if "skill_reports.py recover" in step.get("run", ""))
        staging = next(step for step in steps if step.get("id") == "artifacts")
        self.assertIs(steps[0], budget)
        self.assertEqual(budget["timeout-minutes"], 1)
        self.assertEqual(evaluation["env"]["EVALUATION_DEADLINE_EPOCH"],
                         "${{ steps.budget.outputs.deadline_epoch }}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "github_output"
            output.touch()
            started = int(time.time())
            completed = self._run_step(budget, {"GITHUB_OUTPUT": str(output)}, root)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            deadline = int(re.fullmatch(r"deadline_epoch=(\d+)\n", output.read_text()).group(1))
            budget_seconds = deadline - started
            # The budget is the job minus recovery and a fixed staging reserve; the
            # observed value may only exceed it by the clock drift between the two reads.
            intended_budget = (job["timeout-minutes"] - recovery["timeout-minutes"] - 15) * 60
            self.assertEqual(intended_budget, 9600)
            self.assertTrue(intended_budget <= budget_seconds <= intended_budget + 10, budget_seconds)
            self.assertGreaterEqual(evaluation["timeout-minutes"] * 60, budget_seconds - 30 * 60)

            bin_dir = root / "bin"
            bin_dir.mkdir()
            timeout_log = root / "timeout.log"
            (bin_dir / "timeout").write_text(
                "#!/usr/bin/env bash\nprintf '%s\\n' \"$@\" > \"$TIMEOUT_LOG\"\n"
            )
            (bin_dir / "timeout").chmod(0o700)
            (bin_dir / "skillevaluator").write_text("#!/usr/bin/env bash\nexit 97\n")
            (bin_dir / "skillevaluator").chmod(0o700)
            runner_temp = root / "runner"
            (runner_temp / "skill-benchmark").mkdir(parents=True)
            env = {
                "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                "TIMEOUT_LOG": str(timeout_log),
                "RUNNER_TEMP": str(runner_temp),
                "GITHUB_WORKSPACE": str(REPO),
                "GITHUB_REPOSITORY": "owner/repo",
                "GITHUB_SHA": "0" * 40,
                "BENCHMARK_SKILL": "ansible",
                "ATTEMPTS": "3",
                "SKILLEVALUATOR_RESULTS_DIR": str(runner_temp / "skill-benchmark/results"),
                "OPENAI_API_KEY": "placeholder-for-test",
            }

            # The real budget output leaves plenty of time: the run is still capped below the deadline.
            completed = self._run_step(evaluation, {**env, "EVALUATION_DEADLINE_EPOCH": str(deadline)}, root)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            args = timeout_log.read_text().splitlines()
            self.assertEqual(args[:3], ["--signal=INT", "--kill-after=30s", "8400s"])
            policy = reports.POLICY
            self.assertFalse(policy["stop_on_pass"])
            self.assertTrue(policy["baseline"])
            self.assertEqual(args[3:], [
                "skillevaluator", "tier3", "evaluate", str(REPO / ".apm/skills/ansible"),
                "--agents", "codex", "--agent-model", f"codex={policy['model']}",
                "--env-mode", policy["environment"],
                "--skill-workspace-mode", "isolated", "--grading-mode", policy["grading"],
                "--n-attempts", "3", "--no-stop-on-pass",
                "--n-concurrent", str(policy["concurrency"]), "--max-agents", "1",
                "--agent-runtime-preflight", "--timeout-multiplier", f"{policy['timeout_multiplier']:g}",
                "--progress", "plain", "--harbor-keep-jobs",
                "--results-dir", env["SKILLEVALUATOR_RESULTS_DIR"],
                "--evaluated-source-repository", "owner/repo", "--evaluated-source-revision", "0" * 40,
            ])

            # Little time left: the run gets what remains minus termination grace.
            now = int(time.time())
            completed = self._run_step(evaluation, {**env, "EVALUATION_DEADLINE_EPOCH": str(now + 600)}, root)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            remaining = int(timeout_log.read_text().splitlines()[2].rstrip("s"))
            self.assertTrue(560 <= remaining <= 570, remaining)

            # Exhausted deadline and missing secret both fail before any native run.
            timeout_log.unlink()
            completed = self._run_step(evaluation, {**env, "EVALUATION_DEADLINE_EPOCH": str(now - 1)}, root)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("::error::Benchmark setup exhausted the evaluation deadline.", completed.stdout)
            completed = self._run_step(
                evaluation, {**env, "OPENAI_API_KEY": "", "EVALUATION_DEADLINE_EPOCH": str(now + 600)}, root
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("::error::Add OPENAI_API_KEY", completed.stdout)
            self.assertFalse(timeout_log.exists())

        self.assertIn("always()", recovery["if"])
        self.assertEqual(recovery["env"], {"EVALUATION_OUTCOME": "${{ steps.evaluation.outcome }}"})
        pre_evaluation = steps[:steps.index(evaluation)]
        self.assertTrue(all(step.get("timeout-minutes", 0) > 0 for step in pre_evaluation))
        self.assertLessEqual(sum(step["timeout-minutes"] for step in pre_evaluation), 40)
        self.assertLess(steps.index(evaluation), steps.index(recovery))
        self.assertLess(steps.index(recovery), steps.index(staging))
        metrics = next(step for step in steps if step.get("with", {}).get("name") == "skill-metrics")
        self.assertIn("success()", metrics["if"])

    def _assert_hash_locked(self, source, lock):
        requirement = re.compile(
            r"(?P<name>[A-Za-z0-9_.-]+)"
            r"(?:\[(?:[A-Za-z0-9_.-]+(?:,[A-Za-z0-9_.-]+)*)?\])?"
            r"==(?P<version>[A-Za-z0-9][A-Za-z0-9.!+_-]*)"
        )

        def parse_pin(header):
            match = requirement.fullmatch(header)
            self.assertIsNotNone(match, f"Not an exact requirement pin: {header}")
            return match["name"].lower(), match["version"]

        pins = {}
        for line in source.splitlines():
            if line and not line.startswith("#"):
                name, version = parse_pin(line)
                pins[name] = version
        # One block per requirement: a pinned header followed by indented hash lines.
        blocks = re.split(r"\n(?=\S)", lock.strip())
        locked = {}
        for block in blocks:
            header, *hashes = block.split(" \\\n")
            name, version = parse_pin(header)
            self.assertTrue(hashes, f"{header} has no hashes")
            for entry in hashes:
                self.assertRegex(entry, r"^    --hash=sha256:[0-9a-f]{64}$")
            locked[name] = version
        # The source pin must be what the lock actually installs, not merely present by name.
        for name, version in pins.items():
            self.assertEqual(locked.get(name), version, f"Source pins {name}=={version}")
        return pins

    def test_hash_lock_accepts_extras_in_source_and_lock_headers(self):
        digest = "    --hash=sha256:" + "a" * 64
        for requirement in ("pyjwt==2.13.0", "pyjwt[]==2.13.0", "pyjwt[crypto]==2.13.0",
                            "PyJWT[crypto,other-extra]==2.13.0"):
            for source in ("pyjwt==2.13.0", requirement):
                with self.subTest(source=source, requirement=requirement):
                    self._assert_hash_locked(source, requirement + " \\\n" + digest)

    def test_hash_lock_rejects_malformed_or_unpinned_requirements_and_bad_hashes(self):
        digest = "    --hash=sha256:" + "a" * 64
        invalid = (
            "pyjwt[,crypto]==2.13.0", "pyjwt[crypto,]==2.13.0", "pyjwt[crypto==2.13.0",
            "pyjwt>=2.13.0", "pyjwt==2.*", "pyjwt==2.13.0;python_version>='3.13'",
        )
        for requirement in invalid:
            with self.subTest(matching_invalid_pins=requirement), self.assertRaises(AssertionError):
                self._assert_hash_locked(requirement, requirement + " \\\n" + digest)
            with self.subTest(source=requirement), self.assertRaises(AssertionError):
                self._assert_hash_locked(requirement, "pyjwt==2.13.0 \\\n" + digest)
            with self.subTest(lock=requirement), self.assertRaises(AssertionError):
                self._assert_hash_locked("pyjwt==2.13.0", requirement + " \\\n" + digest)
        for lock in ("pyjwt==2.13.0", "pyjwt==2.13.0 \\\n    --hash=sha256:bad", "pyjwt==2.12.0 \\\n" + digest):
            with self.subTest(lock=lock), self.assertRaises(AssertionError):
                self._assert_hash_locked("pyjwt==2.13.0", lock)

    def test_python_tooling_is_hash_locked(self):
        for lock in ("semgrep", "rumdl"):
            pins = self._assert_hash_locked(
                (REPO / f".github/requirements/{lock}.in").read_text(),
                (REPO / f".github/requirements/{lock}.txt").read_text(),
            )
            self.assertIn(lock, pins)
        # Both locks are consumed by the commands the policy below verifies.
        sources = list(_command_sources())
        self.assertIn('"$GITHUB_WORKSPACE/.github/requirements/semgrep.txt"',
                      next(text for source, text in sources if source == "setup-skillevaluator.sh"))
        self.assertEqual(
            sum("--requirement .github/requirements/rumdl.txt" in text for _, text in sources), 2)
        matched = 0
        for source, text in sources:
            for line in _command_lines(text):
                self.assertNotRegex(line, FORBIDDEN_INSTALLERS, source)
                for pattern, flags in INSTALL_POLICY:
                    if pattern.search(line):
                        matched += 1
                        for flag in flags:
                            self.assertIn(flag, line, f"{source}: {line.strip()}")
        # Sanity check that the patterns still match the known install commands:
        # pip (rumdl x2), uv pip sync (Semgrep), uv sync (SkillEvaluator, SkillSpector).
        self.assertGreaterEqual(matched, 5)

    def test_setup_private_tool_root_for_provenance_key(self):
        setup = (REPO / ".github/scripts/setup-skillevaluator.sh").read_text()
        self.assertIn("umask 077", setup)
        self.assertLess(
            setup.index("umask 077"),
            setup.index('mkdir -p "$tool_root/bin" "$tool_root/dependencies"'),
        )
        self.assertIn('chmod 700 "$tool_root"', setup)
        self.assertIn('["docker", "compose", "version", "--short"]', setup)

    def test_setup_provenance_records_the_selected_scanner_revision(self):
        setup = (REPO / ".github/scripts/setup-skillevaluator.sh").read_text()
        self.assertIn("printf 'SKILL_EVALUATION_KIND=%s\\n' \"$kind\"", setup)
        producer = setup.split("<<'PY' > \"$tool_root/versions.json\"\n", 1)[1].rsplit("\nPY", 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "dependencies").mkdir()
            for name in ("semgrep", "skillspector"):
                (root / "dependencies" / f"{name}.json").write_text(
                    json.dumps([{"name": name, "version": "fixture-version"}]))
            for kind in ("quality", "benchmark"):
                output = io.StringIO()
                with self.subTest(kind=kind), patch.object(sys, "argv", ["-", str(root), kind, SHA]), \
                        patch.object(subprocess, "check_output", return_value="fixture-version\n"), \
                        contextlib.redirect_stdout(output):
                    exec(compile(producer, "setup-provenance", "exec"), {})
                versions = json.loads(output.getvalue())
                if kind == "quality":
                    self.assertEqual(versions["skillspector_revision"], SHA)
                    self.assertEqual(versions["scanners"]["skillspector"], "fixture-version")
                else:
                    self.assertNotIn("skillspector_revision", versions)

    def test_benchmark_contracts_allow_the_intentionally_absent_scanner(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = {**os.environ, "SKILL_EVALUATION_KIND": "benchmark",
                "SKILLEVALUATOR_SKILLSPECTOR_PATH": str(Path(directory) / "absent-skillspector"),
                "SKILLEVALUATOR_SEMGREP_PATH": str(Path(directory) / "absent-semgrep"),
                "PYTHONDONTWRITEBYTECODE": "1"}
            result = subprocess.run([sys.executable, "-m", "unittest", "-v", "test_skillspector", "test_semgrep",
                "test_public_reports.PublicReportsTests.test_pinned_native_quality_cli_provenance_titles_and_public_handoff"],
                cwd=REPO / ".github/tests", env=environment, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("skipped", result.stderr)

    def test_permissions_pins_and_exact_history_handoff(self):
        workflow = yaml.safe_load((REPO / ".github/workflows/benchmark-skills.yml").read_text())
        # PyYAML 1.1 parses the bare YAML key `on` as True.
        self.assertEqual(set(workflow.get("on", workflow.get(True))), {"workflow_dispatch"})
        jobs = workflow["jobs"]
        self.assertEqual(jobs["evaluate"]["permissions"], {"contents": "read"})
        self.assertEqual(jobs["evaluate"]["environment"], {"name": "skill-benchmark", "deployment": False})
        checkout = next(step for step in jobs["evaluate"]["steps"]
                        if step.get("uses", "").startswith("actions/checkout@"))
        self.assertEqual(checkout["with"]["ref"], "${{ github.sha }}")
        selection = next(step for step in jobs["evaluate"]["steps"] if step.get("id") == "selection")
        self.assertIn('test "$(git rev-parse HEAD)" = "$GITHUB_SHA"', selection["run"])
        compose = next(step for step in jobs["evaluate"]["steps"]
                       if step.get("run") == "bash .github/scripts/setup-compose.sh")
        self.assertFalse(any(step.get("uses", "").startswith("docker/setup-compose-action@")
                             for step in jobs["evaluate"]["steps"]))
        compose_index = jobs["evaluate"]["steps"].index(compose)
        evaluator_index = next(index for index, step in enumerate(jobs["evaluate"]["steps"])
                               if "setup-skillevaluator.sh" in step.get("run", ""))
        self.assertLess(compose_index, evaluator_index)
        verification = jobs["evaluate"]["steps"][compose_index + 1]
        self.assertEqual(verification["name"], "Verify pinned Docker Compose")
        self.assertIn("docker compose version --short", verification["run"])
        self.assertIn(reports.POLICY["docker_compose"], verification["run"])
        for file in ("validate.yml", "benchmark-skills.yml"):
            candidate = yaml.safe_load((REPO / ".github/workflows" / file).read_text())
            job = candidate["jobs"]["skill-quality" if file == "validate.yml" else "evaluate"]
            installs = [step for step in job["steps"] if step.get("run") == "bash .github/scripts/setup-compose.sh"]
            cleanups = [step for step in job["steps"] if step.get("run") == "bash .github/scripts/setup-compose.sh cleanup"]
            self.assertEqual(len(installs), 1)
            self.assertEqual(len(cleanups), 1)
            self.assertEqual(cleanups[0]["if"], "always()")
            self.assertLess(job["steps"].index(installs[0]), job["steps"].index(cleanups[0]))
        setup = (REPO / ".github/scripts/setup-compose.sh").read_text()
        self.assertEqual(re.search(r"^compose_version=(\S+)$", setup, re.M)[1], reports.POLICY["docker_compose"])
        self.assertEqual(jobs["publish-history"]["permissions"], {"contents": "write"})
        for name in ("publish-history", "deploy-pages"):
            self.assertIn("github.ref == 'refs/heads/main'", jobs[name]["if"])
            self.assertIn("inputs.mode == 'standard'", jobs[name]["if"])
            self.assertNotIn("OPENAI_API_KEY", json.dumps(jobs[name]))
            self.assertNotIn("setup-skillevaluator", json.dumps(jobs[name]))
        secret_steps = [step for step in jobs["evaluate"]["steps"] if "OPENAI_API_KEY" in step.get("env", {})]
        self.assertEqual(len(secret_steps), 1)
        self.assertIs(secret_steps[0], next(step for step in jobs["evaluate"]["steps"] if step.get("id") == "evaluation"))
        publication = next(step for step in jobs["evaluate"]["steps"]
                           if step.get("with", {}).get("name", "").startswith("skill-benchmark-"))
        self.assertEqual(publication["with"]["path"], "${{ runner.temp }}/skill-benchmark-artifact/")
        self.assertIn("steps.artifacts.outcome == 'success'", publication["if"])
        self.assertFalse(publication["with"].get("include-hidden-files", False))
        quality = yaml.safe_load((REPO / ".github/workflows/validate.yml").read_text())["jobs"]["skill-quality"]
        preflight = next(index for index, step in enumerate(quality["steps"])
                         if "skill_reports.py preflight" in step.get("run", ""))
        setup = next(index for index, step in enumerate(quality["steps"])
                     if "setup-skillevaluator.sh" in step.get("run", ""))
        self.assertLess(preflight, setup)
        checkout = jobs["deploy-pages"]["steps"][0]
        self.assertEqual(checkout["with"]["ref"], "${{ needs.publish-history.outputs.history_sha }}")
        for filename in ("benchmark-skills.yml", "validate.yml"):
            data = yaml.safe_load((REPO / ".github/workflows" / filename).read_text())
            for job in data["jobs"].values():
                for step in job["steps"]:
                    if "uses" in step:
                        self.assertRegex(step["uses"], r"@[0-9a-f]{40}$")
                    if step.get("uses", "").startswith("actions/checkout@"):
                        self.assertIs(step["with"]["persist-credentials"], False)

    def test_external_action_reference_discovery_uses_schema_positions(self):
        external_action = f"example/action@{SHA}"
        external_workflow = f"example/automation/.github/workflows/reusable.yml@{SHA}"
        workflow = {
            "env": {"uses": "ignored-workflow-environment"},
            "jobs": {
                "external-workflow": {
                    "uses": external_workflow,
                    "with": {"uses": "ignored-workflow-input"},
                },
                "steps": {
                    "runs-on": "ubuntu-latest",
                    "env": {"uses": "ignored-job-environment"},
                    "steps": [
                        {
                            "uses": external_action,
                            "with": {"uses": "ignored-action-input"},
                        },
                        {"uses": f"actions/checkout@{SHA}"},
                        {"uses": "./.github/actions/local"},
                    ],
                },
                "local-workflow": {"uses": "./.github/workflows/local.yml"},
                "root-local-workflow": {"uses": "$/.github/workflows/local.yml"},
                "github-workflow": {
                    "uses": f"github/example/.github/workflows/reusable.yml@{SHA}",
                },
            },
        }
        self.assertEqual(
            _external_action_references(workflow),
            {external_action, external_workflow},
        )

    def test_update_workflow_captures_patch_before_validation_and_guards_pr_selection(self):
        workflow = yaml.safe_load((REPO / ".github/workflows/update-baseline.yml").read_text())
        generate = workflow["jobs"]["generate"]["steps"]
        names = [step.get("name", "") for step in generate]
        capture_index = next(i for i, step in enumerate(generate) if "baseline.patch" in step.get("run", ""))
        validate_index = next(i for i, step in enumerate(generate) if "Invoke-Validation.ps1" in step.get("run", ""))
        self.assertLess(
            capture_index,
            validate_index,
            "the candidate patch must be captured before validation runs untrusted branch-ref content",
        )
        capture = generate[capture_index]["run"]
        for tracked_output in (r"\.apm-checksums", r"apm\.lock\.yaml", r"AGENTS\.md", r"\.codex/config\.toml"):
            self.assertIn(tracked_output, capture)
        self.assertIn("grep -Evx", capture)
        inspect = next(step for step in generate if ".sha256" in step.get("run", ""))
        self.assertIn("sha256sum", inspect["run"])
        self.assertNotIn("Install", inspect.get("name", ""))
        self.assertIn("Discover", " ".join(names))

        publish = workflow["jobs"]["publish"]["steps"]
        create = next(step for step in publish if "gh pr create" in step.get("run", ""))["run"]
        self.assertNotIn("--jq '.[0].number", create)
        self.assertIn("--base main", create)
        for guard in ("isCrossRepository == false", "headRepositoryOwner.login == $owner", "author.is_bot == true"):
            self.assertIn(guard, create)
        self.assertIn("-gt 1", create)

    def _publish_candidate_patch(self, before, after):
        """Hand a substituted artifact to the actual publisher in disposable Git repos."""
        workflow = yaml.safe_load((REPO / ".github/workflows/update-baseline.yml").read_text())
        step = next(step for step in workflow["jobs"]["publish"]["steps"]
                    if step.get("name") == "Apply data-only candidate patch").copy()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            producer, consumer = root / "producer", root / "consumer"
            producer.mkdir()

            def git(cwd, *arguments):
                return subprocess.check_output(["git", *arguments], cwd=cwd, stderr=subprocess.PIPE)

            git(producer, "init", "--quiet")
            (producer / ".apm-version").write_bytes(b"0.34.0\n")
            for name, content in before.items():
                path = producer / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            git(producer, "add", "--all")
            git(producer, "-c", "user.name=Boundary fixture", "-c", "user.email=fixture@example.invalid",
                "commit", "--quiet", "-m", "fixture")
            git(root, "clone", "--quiet", "--no-hardlinks", str(producer), str(consumer))
            for name in before.keys() - after.keys():
                (producer / name).unlink()
            for name, content in after.items():
                path = producer / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            git(producer, "add", "--all")
            (root / "baseline.patch").write_bytes(git(producer, "diff", "--cached", "--binary", "--find-renames"))
            # No real publication: the runner must stop before this marker on rejection.
            step["run"] += '\nprintf published > "$RUNNER_TEMP/published"\n'
            completed = self._run_step(step, {"RUNNER_TEMP": str(root)}, consumer)
            self.assertFalse((root / "candidate-executed").exists(), "Publisher executed artifact code")
            paths = git(consumer, "diff", "--cached", "--no-renames", "--name-only", "-z").split(b"\0")[:-1]
            return completed, (root / "published").exists(), paths

    def test_update_publisher_accepts_allowlisted_text_binary_and_rename_changes(self):
        fixtures = (
            ({}, {name: b"updated\n" for name in (
                ".apm-checksums", "apm.lock.yaml", "AGENTS.md", ".github/copilot-instructions.md",
                ".github/mcp.json", ".codex/config.toml", ".agents/skills/example/SKILL.md",
            )}),
            ({".apm-version": b"0.34.0\n"}, {".apm-version": b"0.35.0\n"}),
            ({".agents/skills/example/bin/tool": b"old\0binary"},
             {".agents/skills/example/bin/tool": b"new\0binary"}),
            ({".agents/skills/example/old": b"rename\n"}, {".agents/skills/example/new": b"rename\n"}),
            ({".agents/skills/example/removed": b"removed\n"}, {}),
        )
        for before, after in fixtures:
            with self.subTest(before=list(before), after=list(after)):
                completed, published, paths = self._publish_candidate_patch(before, after)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertTrue(published)
                self.assertEqual(set(paths), {name.encode() for name in before.keys() | after.keys()})

    def test_update_publisher_rejects_substituted_artifacts_before_publication(self):
        shadow_module = (
            b'import os\n'
            b'open(os.path.join(os.environ["RUNNER_TEMP"], "candidate-executed"), "w").close()\n'
            b'raise SystemExit(0)\n'
        )
        fixtures = (
            ({}, {".github/workflows/replacement.yml": b"inert substitution fixture\n"}),
            ({"README.md": b"before\n"}, {"README.md": b"after\n"}),
            ({"README.md": b"removed\n"}, {}),
            ({"README.md": b"rename\n"}, {".agents/skills/example/renamed": b"rename\n"}),
            ({".agents/skills/example/old": b"rename\n"}, {"README.md": b"rename\n"}),
            ({}, {".apm-version.extra": b"prefix collision\n"}),
            ({}, {".agents/skills-extra/example/file": b"prefix collision\n"}),
            ({}, {".github/mcp.json\nAGENTS.md": b"newline path\n"}),
            ({}, {".agents/skills/example/file\nREADME.md": b"newline path\n"}),
            ({}, {"re.py": shadow_module}),
            ({}, {"sitecustomize.py": shadow_module}),
        )
        for before, after in fixtures:
            with self.subTest(before=list(before), after=list(after)):
                completed, published, _ = self._publish_candidate_patch(before, after)
                self.assertNotEqual(completed.returncode, 0)
                self.assertFalse(published)
                self.assertIn("outside the reviewed regeneration allowlist", completed.stderr)

    def test_documented_external_action_requirements_match_all_workflows(self):
        required = set()
        for path in _workflow_files():
            actions = _external_action_references(yaml.safe_load(path.read_text()))
            for action in actions:
                self.assertRegex(action, r"^[^@]+@[0-9a-f]{40}$", path.name)
            required.update(actions)
        readme = (REPO / "README.md").read_text()
        section = readme.split("<!-- external-action-requirements:start -->", 1)[1].split(
            "<!-- external-action-requirements:end -->", 1)[0]
        documented = re.search(r"```text\n(.*?)\n```", section, re.DOTALL).group(1).splitlines()
        self.assertTrue(required)
        for action in documented:
            self.assertRegex(action, r"^[^@*]+@[0-9a-f]{40}$")
        self.assertEqual(len(documented), len(set(documented)), "Duplicate documented action")
        self.assertEqual(set(documented), required)

    def test_git_guard_detects_ignored_untracked_and_tracked_mutations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            (root / ".gitignore").write_text("results/\n")
            subprocess.run(["git", "add", ".gitignore"], cwd=root, check=True)
            # A temporary index baseline avoids committing anything, even in this fixture.
            for path in (root / "results/report.json", root / "unexpected.txt", root / ".gitignore"):
                path.parent.mkdir(exist_ok=True)
                path.write_text("results/\n# changed\n" if path.name == ".gitignore" else "changed\n")
            output = subprocess.check_output(["git", "status", "--porcelain=v1", "--untracked-files=all", "--ignored"], cwd=root).decode()
            self.assertIn("AM .gitignore", output)
            self.assertIn("?? unexpected.txt", output)
            self.assertIn("!! results/", output)


if __name__ == "__main__":
    unittest.main()
