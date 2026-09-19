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
from pathlib import Path
import subprocess
import tempfile
from collections.abc import Mapping
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import yaml


REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("skill_reports", REPO / ".github/scripts/skill_reports.py")
reports = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reports)
SHA = "a" * 40


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        self.skill = self.workspace / ".apm/skills/podman"
        self.skill.mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("---\nname: podman\n---\n")
        reports.write_json(self.skill / "evals/evals.json", {"evals": [{"id": 1}]})
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
        self.assertIn("Missing or linked JSON", summary)
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
                           "n_concurrent": 2, "stop_on_pass": False, "timeout_multiplier": 1.0,
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
        reports.write_json(root / "versions.json", {"python": "3.13.15", "skillevaluator": "0.3.0", "harbor": "0.13.2"})
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

    def test_wrong_python_runtime_prevents_history(self):
        root, _, _ = self.benchmark("standard")
        reports.write_json(root / "versions.json", {"python": "3.14.0", "skillevaluator": "0.3.0", "harbor": "0.13.2"})
        with self.assertRaises(ValueError):
            reports.benchmark_report(self.workspace, root, "podman", "standard", self.root / "metrics")

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
        reports.benchmark_artifacts(self.workspace, root, "podman", destination)
        for path in unexpected:
            self.assertFalse((destination / path.relative_to(root)).exists())
        self.assertTrue((destination / "dependencies/evaluator.json").is_file())
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
        destination = self.root / "publication"
        reports.benchmark_artifacts(self.workspace, root, "podman", destination)
        self.assertTrue((destination / (run / "codex/without-skill/trials/case-1/failure.json").relative_to(root)).is_file())


class UpstreamTests(unittest.TestCase):
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

    def test_pinned_evaluator_patch_preserves_codex_version_and_preflight_error_tail(self):
        from skillevaluator.tier3.harbor import runner, runtime_preflight, secure_docker_environment
        from harbor.agents.installed.codex import Codex
        runner_source = Path(inspect.getfile(runner)).read_text()
        preflight_source = Path(inspect.getfile(runtime_preflight)).read_text()
        secure_docker_source = Path(inspect.getfile(secure_docker_environment)).read_text()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner_target = root / "src/skillevaluator/tier3/harbor/runner.py"
            preflight_target = root / "src/skillevaluator/tier3/harbor/runtime_preflight.py"
            secure_docker_target = root / "src/skillevaluator/tier3/harbor/secure_docker_environment.py"
            runner_target.parent.mkdir(parents=True)
            runner_target.write_text(runner_source)
            preflight_target.write_text(preflight_source)
            secure_docker_target.write_text(secure_docker_source)
            # Benchmark setup is already patched; quality setup is the pristine source.
            if ('command.extend(["--ak", "version=0.155.1"])' not in runner_source
                    or 'marker = " ... [truncated] ... "' not in preflight_source
                    or 'def _startup_failure_diagnostics' not in secure_docker_source):
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
            codex = Codex(logs_dir=Path(directory) / "logs", model_name=reports.POLICY["model"], version="0.155.1")
            with patch.object(codex, "exec_as_root", new_callable=AsyncMock), \
                    patch.object(codex, "exec_as_agent", new_callable=AsyncMock) as execute:
                asyncio.run(codex.install(object()))
                install_command = execute.call_args.kwargs["command"]
            self.assertIn("npm install -g @openai/codex@0.155.1", install_command)
            self.assertNotIn("@latest", install_command)

            preflight_tree = ast.parse(preflight_target.read_text())
            formatter = next(node for node in preflight_tree.body if isinstance(node, ast.FunctionDef)
                             and node.name == "_first_trial_exception_detail")
            namespace = vars(runtime_preflight).copy()
            exec(compile(ast.Module(body=[formatter], type_ignores=[]), str(preflight_target), "exec"), namespace)
            job = root / "job"
            trial = job / "trial-1"
            trial.mkdir(parents=True)
            terminal_error = "terminal Docker build failure"
            reports.write_json(trial / "result.json", {"exception_info": {
                "exception_type": "RuntimeError",
                "exception_message": "preflight head " + ("x" * 1600) + terminal_error,
            }})
            detail = namespace["_first_trial_exception_detail"](job)
            self.assertLessEqual(len(detail), 1500)
            self.assertTrue(detail.startswith("trial-1: RuntimeError | preflight head"))
            self.assertIn(" ... [truncated] ... ", detail)
            self.assertTrue(detail.endswith(terminal_error))

            secure_tree = ast.parse(secure_docker_target.read_text())

            def assignment(name):
                return next(node for node in secure_tree.body if isinstance(node, ast.Assign)
                            and any(isinstance(target, ast.Name) and target.id == name for target in node.targets))

            secure_class = next(node for node in secure_tree.body if isinstance(node, ast.ClassDef)
                                and node.name == "SkillEvaluatorDockerEnvironment")
            diagnostics = next(node for node in secure_class.body if isinstance(node, ast.AsyncFunctionDef)
                               and node.name == "_startup_failure_diagnostics")
            run_compose = next(node for node in secure_class.body if isinstance(node, ast.AsyncFunctionDef)
                               and node.name == "_run_docker_compose_command")
            format_diagnostic = next(node for node in secure_tree.body if isinstance(node, ast.FunctionDef)
                                     and node.name == "_format_startup_diagnostic")
            bounded_output = next(node for node in secure_tree.body if isinstance(node, ast.AsyncFunctionDef)
                                  and node.name == "_bounded_compose_output")
            compose_communication = next(node for node in secure_tree.body if isinstance(node, ast.AsyncFunctionDef)
                                         and node.name == "_compose_communication")
            redact = next(node for node in secure_tree.body if isinstance(node, ast.FunctionDef)
                          and node.name == "_redact")
            redact_result = next(node for node in secure_tree.body if isinstance(node, ast.FunctionDef)
                                 and node.name == "_redact_result")
            secure_namespace = {
                "ExecResult": secure_docker_environment.ExecResult,
                "Mapping": Mapping,
                "asyncio": asyncio,
                "os": os,
                "re": re,
                "_sanitize_docker_compose_project_name": lambda value: value,
            }
            secure_nodes = [
                assignment("_MIN_EXACT_SECRET_LENGTH"),
                assignment("_SECRET_ENV_NAME_RE"),
                assignment("_STARTUP_DIAGNOSTIC_TIMEOUT_SECONDS"),
                assignment("_STARTUP_STATE_MAX_BYTES"),
                assignment("_STARTUP_LOG_MAX_BYTES"),
                assignment("_STARTUP_DIAGNOSTIC_READ_CHUNK_BYTES"),
                assignment("_STARTUP_TRUNCATION_MARKER"),
                redact,
                redact_result,
                bounded_output,
                compose_communication,
                format_diagnostic,
                diagnostics,
                run_compose,
            ]
            exec(compile(ast.Module(body=secure_nodes, type_ignores=[]), str(secure_docker_target), "exec"),
                 secure_namespace)

            secret = "sk-proj-diagnostic-only"
            secret_bytes = secret.encode()
            secret_split = len(secret_bytes) // 2
            diagnostic_limit = 64
            diagnostic_marker = b" ... [truncated] ... "
            terminal_failure = b" terminal Docker build failure"
            exposed_secret_bytes = diagnostic_limit - len(diagnostic_marker) - len(terminal_failure)

            class ComposeDiagnostics:
                def __init__(self):
                    self.calls = []
                    self.responses = iter((
                        SimpleNamespace(stdout='[{"State":"exited","ExitCode":1,"Error":"[REDACTED]"}]',
                                        stderr=None, return_code=0),
                        SimpleNamespace(stdout=" ... [truncated] ... codex exited with status 1 [REDACTED]",
                                        stderr=None, return_code=0),
                    ))

                async def _run_docker_compose_command(self, command, **kwargs):
                    self.calls.append((command, kwargs))
                    return next(self.responses)

            compose = ComposeDiagnostics()
            diagnostic = asyncio.run(secure_namespace["_startup_failure_diagnostics"](
                compose,
                env_overrides={"OPENAI_API_KEY": secret},
                secret_values={secret},
            ))
            self.assertIn("service state (exit 0)", diagnostic)
            self.assertIn("service logs (exit 0)", diagnostic)
            self.assertIn("codex exited with status 1 [REDACTED]", diagnostic)
            self.assertIn(" ... [truncated] ... ", diagnostic)
            self.assertNotIn(secret, diagnostic)
            self.assertEqual([command for command, _ in compose.calls], [
                ["ps", "--all", "--format", "json"],
                ["logs", "--no-color", "--tail", "100"],
            ])
            for _, kwargs in compose.calls:
                self.assertFalse(kwargs["check"])
                self.assertEqual(kwargs["timeout_sec"], 8)
                self.assertEqual(kwargs["env_overrides"], {"OPENAI_API_KEY": secret})
                self.assertEqual(kwargs["redact_values"], {secret})
            self.assertEqual(
                [kwargs["output_tail_bytes"] for _, kwargs in compose.calls],
                [2048, 4096],
            )

            class OutputReader:
                def __init__(self, chunks):
                    self.chunks = iter(chunks)
                    self.read_sizes = []

                async def read(self, size):
                    self.read_sizes.append(size)
                    return next(self.chunks)

            class BoundedOutputProcess:
                def __init__(self, chunks):
                    self.stdout = OutputReader([*chunks, b""])
                    self.communicated = False
                    self.waited = False

                async def communicate(self, *_):
                    self.communicated = True
                    raise AssertionError("bounded diagnostics must not use communicate()")

                async def wait(self):
                    self.waited = True

            process = BoundedOutputProcess([
                b"x" * 10000 + secret_bytes[:secret_split],
                secret_bytes[secret_split:] + terminal_failure,
            ])
            bounded_stdout, bounded_stderr = asyncio.run(secure_namespace["_compose_communication"](
                process,
                stdin_bytes=None,
                output_tail_bytes=diagnostic_limit,
                secret_values={secret},
            ))
            self.assertEqual(bounded_stderr, b"")
            self.assertLessEqual(len(bounded_stdout), diagnostic_limit)
            self.assertTrue(bounded_stdout.startswith(diagnostic_marker))
            self.assertTrue(bounded_stdout.endswith(b"terminal Docker build failure"))
            self.assertIn(b"[REDACTED]", bounded_stdout)
            self.assertNotIn(secret_bytes, bounded_stdout)
            self.assertNotIn(secret_bytes[-exposed_secret_bytes:], bounded_stdout)
            self.assertFalse(process.communicated)
            self.assertTrue(process.waited)
            self.assertEqual(process.stdout.read_sizes, [8192, 8192, 8192])

            class OversizedSecret(str):
                def encode(self, *_args, **_kwargs):
                    raise AssertionError("oversized secrets must not be copied into diagnostic state")

            oversized_length = diagnostic_limit * 4
            oversized_secret = OversizedSecret("s" * oversized_length)
            short_process = BoundedOutputProcess([terminal_failure])
            short_stdout, _ = asyncio.run(secure_namespace["_compose_communication"](
                short_process,
                stdin_bytes=None,
                output_tail_bytes=diagnostic_limit,
                secret_values={oversized_secret},
            ))
            self.assertEqual(short_stdout, terminal_failure)
            self.assertTrue(short_process.waited)

            oversized_process = BoundedOutputProcess([
                b"x" * 10000 + b"s" * (oversized_length // 2),
                b"s" * (oversized_length // 2) + terminal_failure,
            ])
            oversized_stdout, _ = asyncio.run(secure_namespace["_compose_communication"](
                oversized_process,
                stdin_bytes=None,
                output_tail_bytes=diagnostic_limit,
                secret_values={oversized_secret},
            ))
            self.assertEqual(oversized_stdout, diagnostic_marker + b"[REDACTED]")
            self.assertLessEqual(len(oversized_stdout), diagnostic_limit)
            self.assertFalse(oversized_process.communicated)
            self.assertTrue(oversized_process.waited)
            self.assertEqual(oversized_process.stdout.read_sizes, [8192, 8192, 8192])

            class StartupProcess:
                def __init__(self):
                    self.returncode = 1

                async def communicate(self):
                    return f"startup failure {secret}".encode(), b""

            class StartupDiagnosticProcess:
                def __init__(self, label):
                    self.returncode = 0
                    self.stdout = OutputReader([
                        f"{label} emitted {secret}".encode(),
                        b"",
                    ])
                    self.communicated = False
                    self.waited = False

                async def communicate(self, *_):
                    self.communicated = True
                    raise AssertionError("bounded startup diagnostics must not use communicate()")

                async def wait(self):
                    self.waited = True

            class StartupCompose:
                _run_docker_compose_command = secure_namespace["_run_docker_compose_command"]
                _startup_failure_diagnostics = secure_namespace["_startup_failure_diagnostics"]

                def __init__(self):
                    self.session_id = "diagnostic-test"
                    self.environment_dir = root
                    self.environment_name = "diagnostic-test"
                    self._docker_compose_paths = []

                def _compose_env_vars(self, *, include_os_env):
                    if not include_os_env:
                        raise AssertionError("expected inherited Compose environment")
                    return {"OPENAI_API_KEY": secret}

            startup = StartupCompose()
            state = StartupDiagnosticProcess("state")
            logs = StartupDiagnosticProcess("logs")
            with patch.object(asyncio, "create_subprocess_exec", new_callable=AsyncMock,
                              side_effect=[StartupProcess(), state, logs]) as create_subprocess, \
                    self.assertRaises(RuntimeError) as failure:
                asyncio.run(startup._run_docker_compose_command(["up", "--detach", "--wait"]))
            self.assertNotIn(secret, str(failure.exception))
            self.assertIn("[REDACTED]", str(failure.exception))
            self.assertEqual(
                [call.kwargs["stderr"] for call in create_subprocess.call_args_list],
                [asyncio.subprocess.STDOUT] * 3,
            )
            self.assertFalse(state.communicated)
            self.assertFalse(logs.communicated)
            self.assertTrue(state.waited)
            self.assertTrue(logs.waited)


class WorkflowTests(unittest.TestCase):
    def test_setup_private_tool_root_for_provenance_key(self):
        setup = (REPO / ".github/scripts/setup-skillevaluator.sh").read_text()
        self.assertIn("umask 077", setup)
        self.assertLess(
            setup.index("umask 077"),
            setup.index('mkdir -p "$tool_root/bin" "$tool_root/dependencies"'),
        )
        self.assertIn('chmod 700 "$tool_root"', setup)

    def test_permissions_pins_and_exact_history_handoff(self):
        workflow = yaml.safe_load((REPO / ".github/workflows/benchmark-skills.yml").read_text())
        # PyYAML 1.1 parses the bare YAML key `on` as True.
        self.assertEqual(set(workflow.get("on", workflow.get(True))), {"workflow_dispatch"})
        jobs = workflow["jobs"]
        self.assertEqual(jobs["evaluate"]["permissions"], {"contents": "read"})
        self.assertEqual(jobs["evaluate"]["environment"], {"name": "skill-benchmark", "deployment": False})
        self.assertEqual(jobs["evaluate"]["steps"][0]["with"]["ref"], "${{ github.sha }}")
        selection = next(step for step in jobs["evaluate"]["steps"] if step.get("id") == "selection")
        self.assertIn('test "$(git rev-parse HEAD)" = "$GITHUB_SHA"', selection["run"])
        self.assertEqual(jobs["publish-history"]["permissions"], {"contents": "write"})
        for name in ("publish-history", "deploy-pages"):
            self.assertIn("github.ref == 'refs/heads/main'", jobs[name]["if"])
            self.assertIn("inputs.mode == 'standard'", jobs[name]["if"])
            self.assertNotIn("OPENAI_API_KEY", json.dumps(jobs[name]))
            self.assertNotIn("setup-skillevaluator", json.dumps(jobs[name]))
        secret_steps = [step for step in jobs["evaluate"]["steps"] if "OPENAI_API_KEY" in step.get("env", {})]
        self.assertEqual(len(secret_steps), 1)
        self.assertIn("--results-dir", secret_steps[0]["run"])
        self.assertNotIn("--skip-baseline", secret_steps[0]["run"])
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
