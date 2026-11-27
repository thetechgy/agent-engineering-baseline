"""Contract regressions for the Podman storage campaigns."""

import copy
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import runpy
import tempfile
import unittest

from evaluation_campaign import purpose
from evaluation_campaign_protocol import frozen, protocol
from evaluation_campaign_selection import registration, selected_task
import evaluation_evidence
from evaluation_tasks import ROOT, load
import evaluator_profiles
import skill_evidence as evidence
import skill_reports as reports

CAMPAIGN = "podman-storage-v1-1710-sol62"
COMPARISON = "podman-storage-current-v1-1720-sol62"
TASK_ROOT = ROOT / ".github/evals/podman/storage"
GRADE = runpy.run_path(str(TASK_ROOT / "grade.py"))["grade"]


def owning_runtime():
    try:
        return (version("skillevaluator"), version("harbor")) in (("0.8.0", "0.24.0"), ("1.2.1", "0.25.0"))
    except PackageNotFoundError:
        return False


class PodmanStorageContract(unittest.TestCase):
    def test_storage_controls_and_explicit_override(self):
        task = selected_task(CAMPAIGN)
        for control, verdict in task.controls().items():
            with self.subTest(control=control):
                self.assertEqual(GRADE(task.payload(control).decode()), verdict)
        weak = task.payload("vendor-mount").decode()
        self.assertEqual(GRADE(weak + "Environment=PGDATA=/var/lib/postgresql/data/cluster\n")[0], "passed")
        self.assertEqual(GRADE(weak + "EnvironmentFile=/etc/postgres.env\n")[0], "unsupported")
        good = task.payload("covered").decode()
        self.assertEqual(GRADE(good + "Volume=/var/lib/postgresql/18/docker\n")[0], "failed")
        self.assertEqual(GRADE(good + "Volume=db-data:/var/lib/postgresql:ro\n")[0], "unsupported")
        self.assertEqual(GRADE(good.replace(":/var/lib/postgresql", ":/var/lib/postgresql:ro"))[0], "failed")
        self.assertEqual(task.definition["authorized_live_attempts"], 0)
        with self.assertRaisesRegex(ValueError, "cannot enable inference"):
            task.cases("live")

    def test_comparison_reuses_controls_and_binds_matched_serial_schedule(self):
        qualification = selected_task(CAMPAIGN)
        task = selected_task(COMPARISON)
        proposal = frozen(task)
        control, = registration(task)["controls"]
        latest = load(ROOT / control)
        self.assertEqual(task.definition["runtime_profile"], latest.definition["runtime_profile"])
        self.assertEqual(task.entry(), latest.entry())
        self.assertEqual(latest.controls(), qualification.controls())
        self.assertEqual(proposal["runtime"]["resolved"]["cli"], "0.172.0")
        self.assertEqual(proposal["runtime"]["resolved"]["model"], "gpt-6.2-sol")
        self.assertEqual(proposal["evaluator"], evaluator_profiles.NATIVE_1720)
        self.assertEqual(proposal["authorized_live_attempts"], 0)
        self.assertEqual([(row["variant"], row["trial"]) for row in proposal["schedule"]],
                         [("current", 1), ("absent", 1), ("absent", 2), ("current", 2),
                          ("current", 3), ("absent", 3)])
        rule = protocol(task)["decision_criteria"]
        self.assertEqual(evidence.digest_bytes((ROOT / rule["path"]).read_bytes()),
                         "sha256:" + rule["sha256"])
        self.assertEqual(set(proposal["source_identities"]), {"live", "experiment-probe"})
        control = task.fixture_control("unsupported-grading", proposal["schedule"][0])
        self.assertEqual(GRADE(task.payload(control).decode()),
                         ("unsupported", "unresolved_quadlet_volume"))

    def test_comparison_refuses_missing_or_contradictory_grade(self):
        task = selected_task(COMPARISON)
        for classification in ("passed", "failed"):
            grade = float(classification == "passed")
            outcome = {"classification": classification, "code": "evaluated"}
            task.validate_result(outcome, {"overall": grade, "podman_postgres_storage": grade})
            for metrics in ({"overall": grade}, {"overall": grade, "podman_postgres_storage": 1 - grade},
                            {"overall": 1 - grade, "podman_postgres_storage": grade}):
                with self.subTest(classification=classification, metrics=metrics):
                    with self.assertRaisesRegex(ValueError, "contradictory Podman storage evidence"):
                        task.validate_result(outcome, metrics)

    def test_quadlet_bind_overlay_and_companion_volume_cover_the_data_directory(self):
        prompt = "[Container]\nImage=docker.io/library/postgres:18\n"
        passed = ("passed", "persistent_mount_covers_data_directory")
        ephemeral = ("failed", "data_directory_on_ephemeral_overlay")
        for mount, expected in (
            ("/srv/db:/var/lib/postgresql:O", ephemeral),
            ("./db:/var/lib/postgresql:Z", passed),
            ("../db.volume:/var/lib/postgresql", passed),
            ("db-data.volume:/var/lib/postgresql", ("unsupported", "unresolved_quadlet_volume")),
            ("/srv/db:/var/lib/postgresql:O,upperdir=/srv/upper,workdir=/srv/work",
             ("unsupported", "unresolved_overlay_options")),
            ("./%i:/var/lib/postgresql", ("unsupported", "unresolved_storage_settings")),
            ("db-data:/var/lib/postgresql\nVolume=./db:/var/lib/postgresql/18/docker:O", ephemeral),
            ("db-data:/var/lib/postgresql\nVolume=./cache:/var/cache:O", passed),
        ):
            with self.subTest(mount=mount):
                self.assertEqual(GRADE(prompt + "Volume=" + mount + "\n"), expected)

    def test_implicit_postgres_image_volume_can_shadow_a_parent_mount(self):
        unit = "[Container]\nImage=docker.io/library/postgres:18\nVolume=db-data:/var/lib\n"
        passed = ("passed", "persistent_mount_covers_data_directory")
        shadowed = ("failed", "data_directory_on_implicit_image_volume")
        for settings, expected in (
            ("", shadowed),
            ("ImageVolume=anonymous\n", shadowed),
            ("ImageVolume=tmpfs\n", shadowed),
            ("ImageVolume=ignore\n", passed),
            ("ImageVolume=ignore\nImageVolume=\n", shadowed),
            ("Volume=db-data:/var/lib/postgresql\n", passed),
            ("Volume=db-data:/var/lib/postgresql/18/docker\n", passed),
            ("Environment=PGDATA=/var/lib/other-cluster\n", passed),
            ("ImageVolume=unknown\n", ("unsupported", "unresolved_image_volume_mode")),
        ):
            with self.subTest(settings=settings):
                self.assertEqual(GRADE(unit + settings), expected)

    def test_dataset_is_pinned_and_separate_from_inventory(self):
        task = selected_task(CAMPAIGN)
        profile, _, _ = evidence.custom_contract("podman", purpose=purpose(task, "oracle"))
        row = next(row for row in evidence.inventory()["skills"] if row["source"]["skill_id"] == "podman")
        self.assertEqual(row["suite"]["path"], ".apm/skills/podman/evals/evals.json")
        self.assertEqual(len(row["suite"]["case_ids"]), 10)
        self.assertEqual(evidence.custom_authored_digest(ROOT, "podman", profile), profile["dataset_digest"])

        forged = copy.deepcopy(profile)
        forged["campaign"]["dataset"]["digest"] = forged["dataset_digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "Authored dataset drift"):
            evidence.custom_authored_digest(ROOT, "podman", forged)
        forged["campaign"]["dataset"]["path"] = row["suite"]["path"]
        with self.assertRaisesRegex(ValueError, "Unregistered campaign dataset path"):
            evidence.custom_authored_digest(ROOT, "podman", forged)

    def test_successors_preserve_historical_grading_and_bind_current_sources(self):
        registry = evidence.custom_registry()
        from evaluation_registration import current_source, registration as onboarding

        current_campaign_sources = f".github/evals/source-v{current_source(ROOT)}.json"
        active_purposes = {onboarding(ROOT)["current_effectiveness"]: "skill_effectiveness",
                           "gh-deterministic-gate-v12": "benchmark",
                           "gh-native-oracle-v8": "oracle_qualification",
                           "pester-cli-pilot-retained-v26": "cli_pilot",
                           "pester-pilot-v3-source-v51": "benchmark",
                           "pester-pilot-v4": "benchmark-1720"}
        for member in (evidence.CAMPAIGN_SOURCE_SUCCESSORS, evidence.RETIREMENT_SOURCE_SUCCESSORS,
                       evidence.PUBLICATION_SOURCE_SUCCESSORS, evidence.DIAGNOSTIC_SOURCE_SUCCESSORS,
                       evidence.DIRECT_TOOL_SOURCE_SUCCESSORS, evidence.NATIVE_RETIREMENT_SOURCE_SUCCESSORS,
                       evidence.RELEASE_121_SOURCE_SUCCESSORS, evidence.GH_SKILL_SOURCE_SUCCESSORS, evidence.NATIVE_1720_SOURCE_SUCCESSORS,
                       evidence.PODMAN_COMPARISON_SOURCE_SUCCESSORS, current_campaign_sources):
            version_data = reports.read_json(ROOT / member)
            for profile_id, binding in version_data["profiles"].items():
                with self.subTest(profile=profile_id):
                    current = registry["profiles"][profile_id]
                    parent = registry["profiles"][binding["parent"]]
                    fields = {"runtime_digest": binding["runtime_digest"]}
                    if "upstream_revision" in binding:
                        fields["upstream_revision"] = binding["upstream_revision"]
                    if profile_id == "pester-pilot-v3-source-v51":
                        fields["semantics"] = parent["id"]
                    if profile_id == "pester-pilot-v4":
                        fields.update(
                            semantics=parent["id"], runtime=dict(parent["runtime"], powershell="7.7.0", codex="0.172.0"),
                            grader_digest=binding["grader_digest"], fixture_digest=binding["fixture_digest"])
                    elif "grader_digest" in binding:
                        self.assertEqual(member, evidence.CAMPAIGN_SOURCE_SUCCESSORS)
                        self.assertEqual(current["skill_id"], "podman")
                        self.assertNotEqual(binding["grader_digest"], parent["grader_digest"])
                        fields["grader_digest"] = binding["grader_digest"]
                    if "adapter_sha256" in parent.get("campaign", {}):
                        fields["campaign"] = dict(parent["campaign"], adapter_sha256=version_data["replay_adapter"])
                    if "campaign" in binding:
                        self.assertEqual(member, evidence.PODMAN_COMPARISON_SOURCE_SUCCESSORS)
                        self.assertEqual(current["skill_id"], "podman")
                        comparison = selected_task(COMPARISON)
                        self.assertIn(binding["campaign"]["definition"],
                                      [comparison.member, *registration(comparison)["controls"]])
                        if binding["campaign"]["scheduler"]:
                            fields["qualification_cases"] = {case: case for case in parent["cases"]}
                        fields.update(campaign=dict(parent["campaign"], **binding["campaign"]),
                                      runtime=dict(parent["runtime"], profile=binding["runtime_profile"],
                                                   cli=binding["cli"]))
                    self.assertEqual(current, dict(parent, id=profile_id, **fields))
                    if member in (evidence.PODMAN_COMPARISON_SOURCE_SUCCESSORS, current_campaign_sources) or profile_id in active_purposes:
                        purpose_id = active_purposes.get(profile_id, profile_id)
                        if evidence.campaign_purpose(purpose_id) or profile_id in active_purposes:
                            selected, _, _ = evidence.custom_contract(current["skill_id"], ROOT, purpose=purpose_id)
                            self.assertEqual(selected["id"], profile_id)
                        if profile_id == "pester-effectiveness-v55":
                            inputs = evidence.custom_source_manifest(ROOT, current["skill_id"], purpose="skill_effectiveness")
                            digests = dict(evidence.retained_capture_inputs(current["skill_id"], "skill_effectiveness"))[profile_id]
                            inputs = [dict(row, digest=digests.get(row["member"], row["digest"])) for row in inputs]
                            actual = evidence.custom_input_identities(ROOT, current["skill_id"], inputs, purpose="skill_effectiveness")
                        elif profile_id == "pester-cli-pilot-retained-v26":
                            actual = evidence.custom_input_identities(ROOT, current["skill_id"], purpose="cli_pilot")
                        else:
                            actual = evidence.custom_input_identities(ROOT, current["skill_id"], purpose=purpose_id)
                        self.assertEqual(actual, {key: current[key] for key in actual})

    @unittest.skipUnless(owning_runtime(), "pinned SkillEvaluator and Harbor required for native staging")
    def test_native_capture_refuses_false_origin_and_digest(self):
        from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks
        from evaluation_runtime import adapter_for, read_profile

        if version("skillevaluator") == "1.2.1":
            control, = registration(selected_task(COMPARISON))["controls"]
            task = load(ROOT / control)
            try:
                evaluator_profiles.validate_install(evaluator_profiles.NATIVE_1720)
            except ValueError as error:
                self.skipTest(str(error))
        else:
            task = selected_task(CAMPAIGN)
        mode = "oracle"
        profile, _, _ = evidence.custom_contract("podman", purpose=purpose(task, mode))
        selected = read_profile(ROOT / task.definition["runtime_profile"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = task.bundle(root, mode)
            rows = []
            for present, arm in [(True, "with_skill"), (False, "without_skill")]:
                native = stage_native_harbor_tasks(bundle, root / arm, with_skill=present, grading_mode="custom_only")
                for path in native:
                    task.configure(path, task.cases(mode)[path.name], mode, present)
                    adapter_for(selected).prepare_task(path, mode, selected["resolved"])
                rows.extend(evaluation_evidence.capture_tasks(ROOT, profile, native, arm))
                for path in native:
                    self.assertTrue((path / "environment/input/evals/files/vendor-compose.yaml").is_file())
                    self.assertFalse((path / "environment/solution").exists())
                    self.assertFalse((path / "environment/tests").exists())
                    self.assertEqual((path / "tests/docker-compose.yaml").read_text(),
                                     "services:\n  main:\n    network_mode: none\n")

            capture = evidence.custom_capture(ROOT, "podman", bundle, rows, purpose=purpose(task, mode),
                attempts=1, agent="oracle",
                execution_policy={"environment": "docker", "concurrency": 1, "timeout_multiplier": 1.0,
                                  "stop_on_pass": False})
            evidence.validate_custom_capture(capture, "podman", ROOT)

            raw, staged = root / "raw", root / "publication"
            reports.write_json(raw / evidence.CUSTOM_CAPTURE, capture)
            reports.write_json(raw / "versions.json", {"access_token": "fixture-auth-value"})
            reports.benchmark_artifacts(ROOT, raw, "podman", staged)
            self.assertEqual(reports.read_json(staged / evidence.CUSTOM_CAPTURE), capture)
            self.assertEqual(reports.read_json(staged / "versions.json"), {"access_token": "<redacted>"})
            for key in ("owner", "content", "authored_digest"):
                with self.subTest(key=key):
                    forged = copy.deepcopy(capture)
                    if key == "owner":
                        forged["source"][key] = "upstream"
                    elif key == "content":
                        members = forged["source"][key]["manifest"]
                        members[0]["digest"] = "sha256:" + "0" * 64
                        forged["source"][key] = evidence.content(members, forged["source"][key]["provenance"])
                    else:
                        forged[key] = "sha256:" + "0" * 64
                    with self.assertRaisesRegex(ValueError, "source identity drift|Source digest mismatch|Authored dataset drift"):
                        evidence.validate_custom_capture(forged, "podman", ROOT)


if __name__ == "__main__":
    unittest.main()
