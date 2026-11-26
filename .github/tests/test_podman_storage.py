"""Contract regressions for the qualification-only Podman storage campaign."""

import copy
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import runpy
import tempfile
import unittest

from evaluation_campaign import purpose
from evaluation_campaign_selection import selected_task
import evaluation_evidence
from evaluation_tasks import ROOT
import skill_evidence as evidence
import skill_reports as reports

CAMPAIGN = "podman-storage-v1-1710-sol62"
TASK_ROOT = ROOT / ".github/evals/podman/storage"
GRADE = runpy.run_path(str(TASK_ROOT / "grade.py"))["grade"]


def owning_runtime():
    try:
        return version("skillevaluator") == "0.8.0" and version("harbor") == "0.24.0"
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
        active_purposes = {"pester-effectiveness-v49": "skill_effectiveness",
                           "gh-deterministic-gate-v9": "benchmark",
                           "gh-native-oracle-v5": "oracle_qualification"}
        for member in (evidence.CAMPAIGN_SOURCE_SUCCESSORS, evidence.RETIREMENT_SOURCE_SUCCESSORS,
                       evidence.PUBLICATION_SOURCE_SUCCESSORS, evidence.DIAGNOSTIC_SOURCE_SUCCESSORS):
            version_data = reports.read_json(ROOT / member)
            for profile_id, binding in version_data["profiles"].items():
                with self.subTest(profile=profile_id):
                    current = registry["profiles"][profile_id]
                    parent = registry["profiles"][binding["parent"]]
                    fields = {"runtime_digest": binding["runtime_digest"]}
                    if "grader_digest" in binding:
                        self.assertEqual(member, evidence.CAMPAIGN_SOURCE_SUCCESSORS)
                        self.assertEqual(current["skill_id"], "podman")
                        self.assertNotEqual(binding["grader_digest"], parent["grader_digest"])
                        fields["grader_digest"] = binding["grader_digest"]
                    self.assertEqual(current, dict(parent, id=profile_id, **fields))
                    if member == evidence.DIAGNOSTIC_SOURCE_SUCCESSORS or profile_id in active_purposes:
                        purpose_id = active_purposes.get(profile_id, profile_id)
                        selected, _, _ = evidence.custom_contract(current["skill_id"], ROOT, purpose=purpose_id)
                        self.assertEqual(selected["id"], profile_id)
                        actual = evidence.custom_input_identities(ROOT, current["skill_id"], purpose=purpose_id)
                        self.assertEqual(actual, {key: current[key] for key in actual})

    @unittest.skipUnless(owning_runtime(), "pinned SkillEvaluator and Harbor required for native staging")
    def test_native_capture_refuses_false_origin_and_digest(self):
        from skillevaluator.tier3.harbor.adapter import stage_native_harbor_tasks
        from evaluation_runtime import adapter_for, read_profile

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

            capture = evidence.custom_capture(ROOT, "podman", bundle, rows, purpose=purpose(task, mode),
                attempts=1, agent="oracle",
                execution_policy={"environment": "docker", "concurrency": 1, "timeout_multiplier": 1.0,
                                  "stop_on_pass": False})
            evidence.validate_custom_capture(capture, "podman", ROOT)
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
