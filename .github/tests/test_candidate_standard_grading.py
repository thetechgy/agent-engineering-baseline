"""Controlled standard-grading contracts; no agent/model execution claims."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.environ.get("CANDIDATE_EVIDENCE_CHILD") == "1", "candidate owning runtime only")
class CandidateStandardTests(unittest.TestCase):
    def test_podman_twenty_standard_fixture_collection_and_interrupted_recovery(self):
        from harbor.models.job.result import JobResult, JobStats
        from harbor.models.task.task import Task
        from harbor.models.trial.result import TrialResult
        from skillevaluator.tier3.harbor import adapter
        from skillevaluator.tier3.harbor.collector import collect_harbor_results
        from skillevaluator.tier3.harbor.templates import eval as verifier
        from skillevaluator.evaluation.tier3_report import render_agent_eval_html_report
        import skill_reports as reports
        now = datetime(2026, 11, 4, tzinfo=timezone.utc)
        skill = ROOT / ".apm/skills/podman"
        with tempfile.TemporaryDirectory(prefix="podman-controlled-") as temporary:
            root = Path(temporary)
            jobs = root / "jobs"
            coverage = set()
            records = []
            for present in (True, False):
                tasks = adapter.generate_harbor_tasks(skill, root / "tasks" / str(present), with_skill=present,
                    base_image="", custom_dockerfile_mode="disabled")
                self.assertEqual(len(tasks), 10)
                job = jobs / ("podman-codex-with" if present else "podman-codex-without")
                trials = []
                for number, task in enumerate(tasks, 1):
                    native = Task(task)
                    entry = json.loads((task / "tests/entry.json").read_text())
                    case = str(entry["id"])
                    coverage.add((case, present))
                    inputs = task / "environment/input"
                    actual = {p.relative_to(inputs).as_posix() for p in inputs.rglob("*") if p.is_file()}
                    expected = {"2": {"vendor-compose.yaml", "vendor-web/Containerfile"}, "9": {"postgres.container"}}.get(case, set())
                    self.assertEqual(actual, expected)
                    command = "cat /workspace/skills/podman/SKILL.md" if present and entry.get("expected_skill") else "printf fixture"
                    trajectory = {"steps": [{"source": "agent", "tool_calls": [{"tool_call_id": "fixture-call",
                        "function_name": "exec_command", "arguments": {"cmd": command}}],
                        "observation": {"results": [{"source_call_id": "fixture-call", "content": "controlled fixture"}]}},
                        {"source": "agent", "message": "Controlled answer; no model was executed."}]}
                    name = "skillevaluator-" + case + "__attempt001"
                    trial = job / name
                    output = trial / "verifier"; output.mkdir(parents=True)
                    result_paths = {"ENTRY_PATH": task / "tests/entry.json", "REWARD_JSON": output / "reward.json",
                        "REWARD_TXT": output / "reward.txt", "SKILL_EVALUATOR_REWARD_JSON": output / "skill_evaluator_reward.json"}
                    # These mocks qualify assembly only. SDK/network dispatch is forbidden by the parent audit guard.
                    with patch.multiple(verifier, **result_paths), \
                            patch.object(verifier, "load_trajectory_with_fallback", return_value=(trajectory, {"source": "trajectory.json"})), \
                            patch.object(verifier, "judge_accuracy", return_value={"score": 1.0, "reason": "controlled judge fixture"}), \
                            patch.object(verifier, "judge_goal_accuracy", return_value={"score": 1.0, "reason": "controlled judge fixture"}), \
                            patch.object(verifier, "judge_behavior_check", return_value={"score": 1.0, "reason": "controlled judge fixture"}):
                        verifier.main()
                    numeric = json.loads((output / "reward.json").read_text())
                    rich = json.loads((output / "skill_evaluator_reward.json").read_text())
                    self.assertNotEqual(rich.get("evaluation_status"), "failed")
                    self.assertIn("security", numeric)
                    self.assertTrue(all(type(value) in (int, float) for value in numeric.values()))
                    records.append({"case": case, "arm": "with_skill" if present else "without_skill",
                        "task_checksum": native.checksum,
                        "metrics": {key: numeric[key] for key in (*verifier.DISPLAY_METRICS, "overall") if key in numeric}})
                    result = TrialResult.model_validate({"id": UUID(int=number), "task_name": "nvidia/skillevaluator-" + case,
                        "trial_name": name, "trial_uri": trial.as_uri(), "task_id": {"path": str(task)},
                        "task_checksum": native.checksum, "config": {"task": {"path": str(task)}, "trial_name": name},
                        "agent_info": {"name": "codex", "version": "0.155.1", "model_info": {"name": "controlled-fixture"}},
                        "agent_result": {"n_input_tokens": 0, "n_output_tokens": 0, "n_cache_tokens": 0},
                        "verifier_result": {"rewards": numeric}, "started_at": now, "finished_at": now})
                    (trial / "result.json").write_text(result.model_dump_json(indent=2))
                    trials.append(result)
                native_job = JobResult(id=UUID(int=100 + int(present)), started_at=now, updated_at=now, finished_at=now,
                    n_total_trials=10, stats=JobStats.from_trial_results(trials, n_total_trials=10), trial_results=trials)
                (job / "result.json").write_text(native_job.model_dump_json(indent=2))
            self.assertEqual(coverage, {(str(i), arm) for i in range(1, 11) for arm in (True, False)})
            output = root / "collected"
            collected = collect_harbor_results("podman", ["codex"], output, jobs, expected_cases=10,
                expected_case_ids=[str(i) for i in range(1, 11)], expected_trials=10,
                agent_models={"codex": {"model": "controlled-fixture", "source": "qualification"}})
            agent = collected["agents"]["codex"]
            self.assertEqual((agent["num_trials_with"], agent["num_trials_without"]), (10, 10))
            reports.write_json(output / "result.json", {**collected, "skill_name": "podman", "diagnostic_only": True,
                "report_status": "incomplete", "qualification": {"inference": False, "producer": "controlled fixtures"}})
            reports.write_json(output / "run_config.json", {"grading": {"mode": "default"}, "judge": {"enabled": False}})
            render_agent_eval_html_report(skill, output, use_llm_judge=False)
            self.assertTrue(list(output.rglob("*.html")))
            if destination := os.environ.get("AEB_CURRENT_NATIVE"):
                from skillevaluator.tier3.harbor.report_data import build_dataset_snapshot
                from evaluator_profiles import CANDIDATE
                native_root = Path(destination)
                run = native_root / "results/podman/offline-transport"
                shutil.copytree(output, run)
                snapshot = build_dataset_snapshot(json.loads((skill / 'evals/evals.json').read_text())['evals'], evaluator_version='0.8.0')
                result = json.loads((run / 'result.json').read_text())
                result.update(dataset_digest=snapshot['dataset_digest'], dataset_summary=snapshot['dataset_summary'])
                reports.write_json(run / 'result.json', result)
                reports.write_json(run / 'dataset_snapshot.json', snapshot)
                reports.write_json(run / 'attempt_policy.json', {'max_attempts': 1, 'stop_on_pass': False, 'pass_threshold': 0.5})
                policy = {**reports.POLICY, 'evaluator_revision': CANDIDATE['revision'], 'harbor': CANDIDATE['harbor'],
                          'python': CANDIDATE['python'], 'model': 'controlled-fixture'}
                reports.write_json(native_root / 'versions.json', {'skillevaluator': CANDIDATE['version'],
                    'evaluator_revision': CANDIDATE['revision'], 'harbor': CANDIDATE['harbor'], 'python': CANDIDATE['python'],
                    'lock_sha256': CANDIDATE['lock_sha256'], 'patch_sha256': CANDIDATE['patch_sha256']})
                reports.write_json(native_root / 'provenance.json', {'schema_version': 1, 'skill': 'podman',
                    'mode': 'standard', 'policy': policy, 'patch_sha256': CANDIDATE['patch_sha256']})
            recovered = root / "recovered"
            run = recovered / "results/podman/qualification"
            shutil.copytree(jobs, run / "_harbor-jobs")
            (run / "_harbor-jobs/podman-codex-with/skillevaluator-1__attempt001/result.json").unlink()
            reports.recover_benchmark(ROOT, recovered, "podman", "standard", "cancelled")
            diagnostics = reports.read_json(run / "result.json")
            self.assertEqual(diagnostics["report_status"], "incomplete")
            self.assertTrue(diagnostics["diagnostic_only"])
            self.assertEqual(reports.read_json(recovered / "provenance.json")["status"], "incomplete")
            # A native JobResult embeds the same original TrialResult; hiding
            # only its duplicate child file does not remove native evidence.
            self.assertEqual(diagnostics["agents"]["codex"]["num_trials_with"], 10)
            partial_job_path = run / "_harbor-jobs/podman-codex-with/result.json"
            original_job = JobResult.model_validate_json(partial_job_path.read_text())
            retained = [row for row in original_job.trial_results if row.trial_name != "skillevaluator-1__attempt001"]
            partial_job = original_job.model_copy(update={"finished_at": None, "trial_results": retained,
                "stats": JobStats.from_trial_results(retained, n_total_trials=10)})
            partial_job_path.write_text(partial_job.model_dump_json(indent=2))
            reports.recover_benchmark(ROOT, recovered, "podman", "standard", "cancelled")
            diagnostics = reports.read_json(run / "result.json")
            self.assertEqual(diagnostics["report_status"], "incomplete")
            # The owning collector refuses scores from a nonterminal job whose
            # counters cannot attest the complete physical trial population.
            partial = diagnostics["agents"]["codex"]
            self.assertEqual(partial["num_trials_with"], 0)
            self.assertEqual(partial["with_skill"], {})
            self.assertNotEqual(partial["conditions"]["with_skill"]["execution_status"], "succeeded")
            retained_files = list((run / "codex/with-skill/trials").glob("*/result.json"))
            self.assertEqual(len(retained_files), 9)
            self.assertEqual(diagnostics["agents"]["codex"]["num_trials_without"], 10)
            import importlib.metadata
            destination = os.environ.get("AEB_CANDIDATE_FIXTURE_RESULT")
            if destination:
                Path(destination).write_text(json.dumps({"schema": 1, "success": True, "diagnostic_only": True,
                    "inference": False, "evidence": "controlled fixture and mocked judges", "cases": records,
                    "runtime": {key: importlib.metadata.version(key) for key in ("skillevaluator", "harbor")},
                    "html_diagnostics": True, "interrupted_recovery": {"successful_scores": False,
                        "retained_original_trials": 9, "unaffected_baseline_trials": 10}}, indent=2) + "\n")
