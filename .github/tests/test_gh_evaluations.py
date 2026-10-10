"""Credential-free production-path regression tests; no model performance claims."""

import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gh_evaluations as gh
import skill_reports as reports


class GhOfflineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gh-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def workspace(self):
        root = self.root / "repo"
        shutil.copytree(gh.ROOT / gh.DEPLOYED, root / gh.DEPLOYED)
        shutil.copytree(
            gh.ROOT / ".agents/skills" / gh.COMPETING,
            root / ".agents/skills" / gh.COMPETING,
        )
        shutil.copytree(gh.ROOT / gh.OVERLAY, root / gh.OVERLAY)
        shutil.copyfile(gh.ROOT / "apm.lock.yaml", root / "apm.lock.yaml")
        return root

    def test_complete_offline_replay_and_injected_faults(self):
        result = gh.replay()
        self.assertEqual(result["good_passed"], 24)
        self.assertEqual(result["faults_rejected"], 13)

    def test_staging_preserves_upstream_and_excludes_provenance(self):
        source = (gh.ROOT / gh.DEPLOYED / "SKILL.md").read_bytes()
        staged = gh.stage(gh.ROOT, self.root / "bundle/gh", ["gh-002"])
        self.assertEqual((staged / "SKILL.md").read_bytes(), source)
        self.assertFalse((staged / "PROVENANCE.md").exists())
        data = reports.read_json(staged / "evals/evals.json")
        self.assertEqual([entry["id"] for entry in data["evals"]], ["gh-002"])
        self.assertNotIn("good_commands", data["evals"][0]["contract"])
        compile((staged / "evals/grader.py").read_text(), "grader.py", "exec")
        self.assertEqual((gh.ROOT / gh.DEPLOYED / "SKILL.md").read_bytes(), source)

    def test_ownership_hash_drift_rejected_before_staging(self):
        root = self.workspace()
        (root / gh.DEPLOYED / "SKILL.md").write_text("modified")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            gh.stage(root, self.root / "bundle/gh")
        self.assertFalse((self.root / "bundle").exists())

    def test_owner_metadata_must_match_lock(self):
        import yaml

        root = self.workspace()
        lock = root / "apm.lock.yaml"
        data = yaml.safe_load(lock.read_text())
        next(
            d
            for d in data["deployments"]
            if d["value"] == str(gh.DEPLOYED / "SKILL.md")
        )["active_owner"] = "other/owner"
        lock.write_text(yaml.safe_dump(data))
        with self.assertRaisesRegex(ValueError, "owner mismatch"):
            gh.verify_skill(root)

    def test_symlinks_special_files_and_destination_escapes(self):
        root = self.workspace()
        fixture = root / gh.OVERLAY / "evals/files/bad"
        fixture.symlink_to("/dev/null")
        with self.assertRaises(ValueError):
            gh.stage(root, self.root / "bundle/gh")
        fixture.unlink()
        os.mkfifo(fixture)
        with self.assertRaises(ValueError):
            gh.stage(root, self.root / "bundle/gh")
        fixture.unlink()
        for target in (
            root / ".agents/skills/new",
            root / ".apm/skills/new",
            root / "local",
        ):
            with self.assertRaises(ValueError):
                gh.stage(root, target)
        (self.root / "link").symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            gh.stage(root, self.root / "link/bundle")

    def test_fixture_executable_supports_aliases_and_filtering(self):
        entry = copy.deepcopy(gh.dataset(selected=["gh-001"])[0])
        entry["contract"]["good_commands"] = [
            [
                "issue",
                "view",
                "12",
                "-R",
                "fixture-org/widget",
                "--json",
                "comments,title",
                "--jq",
                ".title",
            ]
        ]
        self.assertEqual(gh.replay_case(entry)["custom_metrics"]["gh_gate"], 1)

    def test_malformed_graphql_and_body_change_cannot_fabricate_success(self):
        entry = copy.deepcopy(gh.dataset(selected=["gh-003"])[0])
        entry["contract"]["good_commands"] = entry["contract"]["good_commands"][:2]
        self.assertEqual(gh.replay_case(entry)["custom_metrics"]["gh_gate"], 0)
        entry = copy.deepcopy(gh.dataset(selected=["gh-010"])[0])
        entry["contract"]["good_commands"][0] = [
            "pr",
            "comment",
            "17",
            "--repo",
            "fixture-org/widget",
            "--body",
            "wrong body",
        ]
        self.assertEqual(gh.replay_case(entry)["custom_metrics"]["gh_gate"], 0)

    def test_pending_checks_require_fresh_head_observation(self):
        entry = copy.deepcopy(gh.dataset(selected=["gh-006-pending"])[0])
        entry["contract"]["good_commands"].pop()
        self.assertEqual(gh.replay_case(entry)["custom_metrics"]["gh_gate"], 0)

    def test_watch_run_is_discovered_from_checks_observation(self):
        for identity in ("gh-006-pending", "gh-006-changed-head"):
            entry = gh.dataset(selected=[identity])[0]
            case = reports.read_json(gh.ROOT / gh.OVERLAY / entry["files"][-1])
            command = entry["contract"]["good_commands"][1]
            self.assertIn("link", command[command.index("--json") + 1].split(","))
            response = next(r for r in case["routes"] if r["match"]["pos"][:2] == ["pr", "checks"])["responses"][0]
            links = [check["link"] for check in json.loads(response["stdout"])]
            self.assertTrue(any("/actions/runs/71" in link for link in links))

    def test_issue_collection_models_all_states_and_filters_pull_requests(self):
        entry = gh.dataset(selected=["gh-007"])[0]
        command = entry["contract"]["good_commands"][0]
        self.assertEqual(command[command.index("--method") + 1], "GET")
        self.assertIn("state=all", command)
        self.assertIn("--paginate", command)
        self.assertIn("pull_request", command[command.index("--jq") + 1])
        case = reports.read_json(gh.ROOT / gh.OVERLAY / entry["files"][-1])
        items = [item for page in json.loads(case["routes"][0]["responses"][0]["stdout"]) for item in page]
        self.assertTrue(any(item.get("state") == "closed" for item in items))
        self.assertTrue(any("pull_request" in item for item in items))
        self.assertEqual(gh.replay_case(entry)["custom_metrics"]["gh_gate"], 1)

    def test_preinstall_selection_needs_only_python_standard_library(self):
        result = subprocess.run(
            [
                sys.executable,
                "-S",
                str(gh.ROOT / ".github/scripts/skill_reports.py"),
                "select",
                "gh",
                "standard",
            ],
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "GITHUB_WORKSPACE": str(gh.ROOT),
                "GITHUB_OUTPUT": str(self.root / "selection"),
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("attempts=1", (self.root / "selection").read_text())

    def test_authored_cases_and_smoke_policy(self):
        entries = gh.dataset(selected=gh.SMOKE)
        self.assertEqual(len(entries) * reports.MODES["standard"] * 2, 8)
        self.assertEqual(len(gh.dataset()) * reports.MODES["confirmation"] * 2, 144)
        command = gh.native_command(
            Path("/tmp/bundle/gh"), "standard", Path("/tmp/results")
        )
        self.assertIn("default_plus_custom", command)
        self.assertNotIn("--skip-baseline", command)
        self.assertNotIn("--stop-on-pass", command)
        self.assertEqual(reports.benchmark_policy("podman"), reports.POLICY)
        self.assertEqual(
            reports.benchmark_skill(gh.ROOT, "podman"), gh.ROOT / ".apm/skills/podman"
        )
        with self.assertRaises(ValueError):
            gh.dataset(selected=["../podman"])

    def rewards(self):
        for arm in ("with-skill", "without-skill"):
            metrics = {
                "gh_" + k: 1.0
                for k in (
                    "evidence",
                    "activation",
                    "commands",
                    "task",
                    "recovery",
                    "authorization",
                    "efficiency",
                    "gate",
                )
            }
            if arm == "without-skill":
                metrics.update(gh_activation=0.0, gh_gate=0.0)
            reports.write_json(
                self.root / "run/codex" / arm / "trials/one/reward.json",
                {"entry_id": "gh-001", "custom_metrics": metrics},
            )
        return self.root / "run"

    def test_gate_does_not_promote_native_scores_over_failed_assertions(self):
        run = self.rewards()
        self.assertEqual(len(gh.deterministic_gate(run, ["gh-001"], 1)), 2)
        path = run / "codex/with-skill/trials/one/reward.json"
        data = reports.read_json(path)
        data["overall"] = 1
        data["custom_metrics"]["gh_authorization"] = 0
        reports.write_json(path, data)
        with self.assertRaises(ValueError):
            gh.deterministic_gate(run, ["gh-001"], 1)
        data["custom_metrics"]["gh_gate"] = 0
        reports.write_json(path, data)
        with self.assertRaises(ValueError):
            gh.deterministic_gate(run, ["gh-001"], 1)

    def test_gate_rejects_missing_baseline_duplicate_cases_and_unknown_ids(self):
        run = self.rewards()
        with self.assertRaises(ValueError):
            gh.deterministic_gate(run, ["gh-001", "gh-002"], 1)
        with self.assertRaises(ValueError):
            gh.deterministic_gate(run, ["gh-002"], 1)
        (run / "codex/without-skill/trials/one/reward.json").unlink()
        with self.assertRaises(ValueError):
            gh.deterministic_gate(run, ["gh-001"], 1)

    def test_live_interface_is_explicit_get_only_and_never_logs_payload(self):
        with patch.object(gh.subprocess, "run") as run:
            run.side_effect = [
                subprocess.CompletedProcess(
                    [],
                    0,
                    json.dumps({"private": False, "full_name": "public/example"}),
                    "",
                ),
                subprocess.CompletedProcess([], 0, "[]", ""),
            ]
            gh.live("public/example")
            for call in run.call_args_list:
                command = call.args[0]
                self.assertEqual(command[:2], ["gh", "api"])
                self.assertEqual(command[command.index("--method") + 1], "GET")
            self.assertEqual(run.call_count, 2)
        with self.assertRaises(ValueError):
            gh.live("--help")

    def test_real_cli_help_contract_when_installed(self):
        if not shutil.which("gh"):
            self.skipTest("real gh CLI not installed")
        commands = {
            ("api",): ["--method", "--paginate", "--slurp", "--raw-field", "--field"],
            ("issue", "view"): ["--json", "--comments", "--repo"],
            ("pr", "checks"): ["--json", "--interval"],
            ("run", "view"): ["--log-failed"],
            ("search", "prs"): ["--app", "--limit"],
            ("pr", "comment"): ["--body-file", "--attach"],
        }
        version = subprocess.check_output(["gh", "--version"], text=True)
        if "2.102.0" not in version:
            self.skipTest("help contract recorded for gh 2.102.0")
        for command, flags in commands.items():
            help_text = subprocess.check_output(["gh", *command, "--help"], text=True)
            for flag in flags:
                self.assertIn(flag, help_text)


@unittest.skipUnless(
    importlib.util.find_spec("skillevaluator") and importlib.util.find_spec("pydantic"),
    "pinned SkillEvaluator environment unavailable",
)
class GhNativeTests(unittest.TestCase):
    def test_native_task_generation_both_arms_and_hidden_verifier_contract(self):
        from skillevaluator.tier3.harbor.adapter import generate_harbor_tasks

        with tempfile.TemporaryDirectory(prefix="gh-native-") as tmp:
            root = Path(tmp)
            skill = gh.stage(gh.ROOT, root / "bundle/gh", list(gh.SMOKE))
            arms = []
            for with_skill in (True, False):
                tasks = generate_harbor_tasks(
                    skill,
                    root / str(with_skill),
                    with_skill=with_skill,
                    grading_mode="default_plus_custom",
                    pre_agent_setup=[gh.SETUP],
                    workspace_mode="group",
                    workspace_skill_paths=[skill.parent / gh.COMPETING],
                )
                self.assertEqual(len(tasks), 4)
                arms.append(tasks)
                for task in tasks:
                    self.assertTrue((task / "tests/grader.py").is_file())
                    visible_skills = {
                        p.parent.name for p in (task / "environment").rglob("SKILL.md")
                    }
                    self.assertIn(gh.COMPETING, visible_skills)
                    self.assertEqual("gh" in visible_skills, with_skill)
                    self.assertIn(
                        "custom_grader_runner.py", (task / "tests/test.sh").read_text()
                    )
                    self.assertNotIn("contract", (task / "instruction.md").read_text())
                    entry = reports.read_json(task / "tests/entry.json")
                    self.assertEqual(entry["has_skill"], with_skill)
                    self.assertIn("fixture_case", entry["contract"])
                    visible = "\n".join(
                        p.read_text()
                        for p in (task / "environment/input").rglob("*")
                        if p.is_file()
                    )
                    self.assertNotIn("good_commands", visible)
                    self.assertNotIn("required_routes", visible)
            for left, right in zip(*arms):
                self.assertEqual(
                    (left / "instruction.md").read_bytes(),
                    (right / "instruction.md").read_bytes(),
                )
                for source in (left / "environment/input").rglob("*"):
                    if source.is_file():
                        self.assertEqual(
                            source.read_bytes(),
                            (
                                right
                                / "environment/input"
                                / source.relative_to(left / "environment/input")
                            ).read_bytes(),
                        )

    def test_production_grader_uses_native_completed_calls_and_propagates_failure(self):
        from skillevaluator.tier3.harbor.adapter import generate_harbor_tasks
        import shlex

        with tempfile.TemporaryDirectory(prefix="gh-grading-") as temporary:
            root = Path(temporary)
            skill = gh.stage(gh.ROOT, root / "bundle/gh", ["gh-001"])
            task = generate_harbor_tasks(
                skill, root / "tasks", grading_mode="default_plus_custom"
            )[0]
            workspace = root / "workspace"
            workspace.mkdir()
            shutil.copytree(task / "environment/input", workspace / "input")
            setup = gh.module(gh.ROOT / gh.OVERLAY / "evals/files/setup.py", "setup")
            environment = setup.setup(workspace, workspace / "input")
            original = gh.dataset(selected=["gh-001"])[0]
            args = original["contract"]["good_commands"][0]
            result = subprocess.run(
                ["gh", *args],
                cwd=workspace,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            steps = [
                {
                    "source": "agent",
                    "tool_calls": [
                        {
                            "tool_call_id": "read",
                            "function_name": "bash",
                            "arguments": {
                                "command": "cat /workspace/skills/gh/SKILL.md"
                            },
                        }
                    ],
                    "observation": {
                        "results": [
                            {
                                "source_call_id": "read",
                                "content": (skill / "SKILL.md").read_text(),
                            }
                        ]
                    },
                },
                {
                    "source": "agent",
                    "tool_calls": [
                        {
                            "tool_call_id": "command",
                            "function_name": "bash",
                            "arguments": {"command": shlex.join(["gh", *args])},
                        }
                    ],
                    "observation": {
                        "results": [
                            {
                                "source_call_id": "command",
                                "content": result.stdout + result.stderr,
                            }
                        ]
                    },
                },
            ]
            logs = root / "logs"
            (logs / "verifier").mkdir(parents=True)
            reports.write_json(logs / "agent/trajectory.json", {"steps": steps})
            reports.write_json(
                workspace / "output/result.json", original["contract"]["expected"]
            )
            environment.update(
                HARBOR_WORKSPACE=str(workspace),
                HARBOR_TESTS_DIR=str(task / "tests"),
                HARBOR_LOGS_DIR=str(logs),
                HARBOR_ATIF_PATH=str(logs / "agent/trajectory.json"),
                HARBOR_ENTRY_JSON=str(task / "tests/entry.json"),
                HARBOR_GRADER=str(task / "tests/grader.py"),
                HARBOR_REWARD_JSON=str(logs / "verifier/reward.json"),
                HARBOR_REWARD_TXT=str(logs / "verifier/reward.txt"),
            )
            for tamper in (False, True):
                if tamper:
                    (workspace / ".gh-fixture/audit.jsonl").write_text("")
                reports.write_json(
                    logs / "verifier/reward.json", {"overall": 1.0, "accuracy": 1.0}
                )
                reports.write_json(
                    logs / "verifier/skill_evaluator_reward.json",
                    {"overall": 1.0, "accuracy": 1.0},
                )
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(task / "tests/custom_grader_runner.py"),
                        "--mode",
                        "default_plus_custom",
                    ],
                    env=environment,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                reward = reports.read_json(logs / "verifier/custom_reward.json")
                self.assertEqual(
                    reward["custom_metrics"]["gh_gate"], float(not tamper), reward
                )
                self.assertEqual(reward["custom_metrics"]["gh_activation"], 1.0)

    def test_selected_recovery_preserves_ids_and_never_publishes_history(self):
        with tempfile.TemporaryDirectory(prefix="gh-recovery-") as temporary:
            root = Path(temporary)
            gh.stage(gh.ROOT, root / "bundle/gh", ["gh-002", "gh-005"])
            run = root / "results/gh/interrupted"
            (run / "_harbor-jobs").mkdir(parents=True)
            with patch(
                "skillevaluator.tier3.harbor.collector.collect_harbor_results",
                return_value={},
            ) as collect:
                reports.recover_benchmark(gh.ROOT, root, "gh", "standard", "failure")
            self.assertEqual(
                collect.call_args.kwargs["expected_case_ids"], ["gh-002", "gh-005"]
            )
            self.assertEqual(
                reports.read_json(run / "result.json")["report_status"], "incomplete"
            )
            with self.assertRaisesRegex(ValueError, "Incomplete benchmark recovery"):
                reports.benchmark_report(
                    gh.ROOT, root, "gh", "standard", root / "metrics"
                )

    def test_gh_artifact_allowlist_keeps_scores_and_redacts_native_diagnostics(self):
        with tempfile.TemporaryDirectory(prefix="gh-artifacts-") as temporary:
            root = Path(temporary)
            raw = root / "raw"
            reports.write_json(
                raw / "deterministic.json",
                {"trials": [{"case": "gh-002", "metrics": {"gh_gate": 0}}]},
            )
            token = "ghp_" + "A" * 36
            reports.write_json(
                raw / "results/gh/run/codex/with-skill/trials/one/reward.json",
                {"error": token},
            )
            (raw / "secret.log").write_text(token)
            reports.benchmark_artifacts(gh.ROOT, raw, "gh", root / "publish")
            self.assertTrue((root / "publish/deterministic.json").exists())
            self.assertFalse((root / "publish/secret.log").exists())
            content = (
                root / "publish/results/gh/run/codex/with-skill/trials/one/reward.json"
            ).read_text()
            self.assertNotIn(token, content)

    def test_native_strict_dataset_and_custom_reward_propagation(self):
        from click.testing import CliRunner
        from skillevaluator.cli import cli
        from skillevaluator.tier3.harbor.adapter import generate_harbor_tasks

        with tempfile.TemporaryDirectory(prefix="gh-grader-") as tmp:
            root = Path(tmp)
            skill = gh.stage(gh.ROOT, root / "bundle/gh", ["gh-001"])
            result = CliRunner().invoke(
                cli, ["tier3", "validate", str(skill), "--strict", "--json"]
            )
            self.assertEqual(result.exit_code, 0, result.output)
            task = generate_harbor_tasks(
                skill, root / "tasks", grading_mode="default_plus_custom"
            )[0]
            runner = task / "tests/custom_grader_runner.py"
            fake_grader = root / "known_reward.py"
            fake_grader.write_text(
                'import os,json\nfrom pathlib import Path\nPath(os.environ["HARBOR_REWARD_JSON"]).write_text(json.dumps({"custom_metrics":{"gh_gate":0.0}}))\n'
            )
            logs = root / "logs"
            (logs / "verifier").mkdir(parents=True)
            reports.write_json(
                logs / "verifier/reward.json", {"overall": 1.0, "accuracy": 1.0}
            )
            reports.write_json(
                logs / "verifier/skill_evaluator_reward.json",
                {"overall": 1.0, "accuracy": 1.0},
            )
            env = {
                **os.environ,
                "HARBOR_LOGS_DIR": str(logs),
                "HARBOR_TESTS_DIR": str(task / "tests"),
                "HARBOR_GRADER": str(fake_grader),
                "HARBOR_REWARD_JSON": str(logs / "verifier/reward.json"),
            }
            result = subprocess.run(
                [sys.executable, str(runner), "--mode", "default_plus_custom"],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            reward = reports.read_json(logs / "verifier/custom_reward.json")
            self.assertEqual(reward["custom_metrics"]["gh_gate"], 0.0)


if __name__ == "__main__":
    unittest.main()
