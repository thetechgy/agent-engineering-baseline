"""Case selection and bounded workspace evidence on real local files."""
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from case_observation import CONFIG, selected
from case_workspace import MAX_FILE, compare


class CaseObservationTests(unittest.TestCase):
    def test_retention_error_preserves_only_the_diagnostic_interruption(self):
        from evaluation_campaign import preserve_interruption
        from types import SimpleNamespace

        for diagnostic in (True, False):
            task = SimpleNamespace(diagnostic_observation=diagnostic)
            row = {}
            with self.subTest(diagnostic=diagnostic):
                with self.assertRaises(KeyboardInterrupt if diagnostic else OSError):
                    try:
                        raise KeyboardInterrupt
                    finally:
                        with preserve_interruption(task, row, "observation_retention_failure"):
                            raise OSError("fixture write failed")
                self.assertEqual(row, {"observation_retention_failure": "OSError"} if diagnostic else {})
                with self.assertRaises(OSError), preserve_interruption(task, row, "observation_retention_failure"):
                    raise OSError("ordinary error")

    def test_original_ids_resolve_without_runtime_or_credentials(self):
        self.assertEqual(selected("podman", "4")[1]["files"], [])
        self.assertEqual(selected("gh", "gh-014")[1]["id"], "gh-014")
        for skill, case in (("podman", "404"), ("../podman", "4"), ("gh", "4")):
            with self.assertRaises(ValueError):
                selected(skill, case)

    @unittest.skipUnless(os.environ.get("APM_EXECUTABLE"), "Pinned APM required for native staging")
    def test_case9_staging_checks_declared_input_before_launch(self):
        import evaluation_campaign as campaign
        from evaluation_campaign_selection import selected_task
        from skillevaluator.tier3.harbor import adapter

        generate = adapter.generate_harbor_tasks
        with patch.dict(os.environ, OBSERVATION_SKILL="podman", OBSERVATION_CASE="9"):
            task = selected_task("case-observation")
        declared = "evals/files/postgres.container"
        self.assertEqual(task.entry["files"], [declared])
        original = (task.source / declared).read_bytes()

        for fault in (None, "missing", "substituted", "extra"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)

                def generate_case(*args, **kwargs):
                    paths = generate(*args, **kwargs)
                    native, = paths
                    member = native / "environment/input/postgres.container"
                    self.assertEqual(member.read_bytes(), original)
                    if fault == "missing":
                        member.unlink()
                    elif fault == "substituted":
                        member.write_bytes(b"X" * len(original))
                    elif fault == "extra":
                        member.with_name("extra.container").write_bytes(original)
                    return paths

                with patch.object(adapter, "generate_harbor_tasks", generate_case):
                    if fault:
                        with self.assertRaisesRegex(ValueError, "Staged inputs differ from declared case files"):
                            campaign.stage(root, task, "live")
                        self.assertFalse((root / "evidence/staging.json").exists())
                    else:
                        _, tasks, captured, _ = campaign.stage(root, task, "live")
                        native = tasks["current"]["9"]
                        member = "environment/input/postgres.container"
                        dockerfile = (native / "environment/Dockerfile").read_text().splitlines()
                        self.assertIn("COPY input/ /workspace/input/", dockerfile)
                        self.assertEqual((native / member).read_bytes(), original)
                        self.assertEqual(captured[0]["members"][member], "sha256:" + hashlib.sha256(original).hexdigest())
                        receipt = json.loads((root / "evidence/selected-case.json").read_bytes())
                        self.assertEqual(receipt["staged_inputs"], ["postgres.container"])

    def test_missing_oversized_and_linked_members_cannot_attest_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(OSError):
                compare(root / "missing", {})
            workspace = root / "task"
            workspace.mkdir()
            baseline = compare(workspace, None)["baseline"]
            self.assertEqual(compare(workspace, baseline), {"changes": []})
            config = workspace / "traefik.yaml"
            config.write_text(CONFIG)
            row, = compare(workspace, baseline)["changes"]
            self.assertEqual((row["path"], row["change"], base64.b64decode(row["data"]).decode()),
                             ("traefik.yaml", "added", CONFIG))
            config.write_bytes(bytes(MAX_FILE + 1))
            with self.assertRaises(ValueError):
                compare(workspace, baseline)
            config.unlink()
            config.symlink_to(root / "private")
            with self.assertRaises(ValueError):
                compare(workspace, baseline)

    def test_successors_change_only_producer_identity(self):
        registry = json.loads((SCRIPTS.parent / "evals/custom-metrics.json").read_bytes())
        registry['profiles'].pop('gh-deterministic-gate-v6')
        registry['profiles'].pop('gh-native-oracle-v2')
        registry['active_profiles']['gh'] = 'gh-deterministic-gate-v5'
        profiles = registry["profiles"]
        original = {k: v for k, v in profiles.items() if "-source-v33-" not in k and "-source-v35-" not in k and "-source-v36-" not in k and "-source-v32-" not in k and "-source-v31-" not in k and "-source-v30-" not in k and "-source-v29-" not in k
                    and k not in ("pester-effectiveness-v32", "pester-effectiveness-v33", "pester-effectiveness-v34", "pester-effectiveness-v35", "pester-effectiveness-v39", "pester-effectiveness-v38", "pester-effectiveness-v36", "pester-cli-pilot-retained-v20")}
        self.assertEqual(hashlib.sha256((json.dumps({**registry, "profiles": original}, indent=2) + "\n").encode()).hexdigest(),
                         "e2421338db925697590201424cb8453bc7e44b555701dddf985047a4809dde13")
        previous = {k.replace("-source-v28-", "-source-v29-"): k for k in profiles if "-source-v28-" in k}
        previous.update({"pester-effectiveness-v32": "pester-effectiveness-v31",
                         "pester-cli-pilot-retained-v20": "pester-cli-pilot-retained-v19"})
        for new, old in previous.items():
            successor = profiles.pop(new)
            predecessor = profiles[old]
            self.assertNotEqual(successor["runtime_digest"], predecessor["runtime_digest"])
            successor.update(id=old, runtime_digest=predecessor["runtime_digest"])
            if "adapter_sha256" in successor.get("campaign", {}):
                successor["campaign"]["adapter_sha256"] = predecessor["campaign"]["adapter_sha256"]
            self.assertEqual(successor, predecessor)
